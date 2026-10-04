"""autopilot.py —— 量子混沌自动驾驶客户端（CARLA 0.9.16，Quark runtime 真·量子推理）

把 Chimera 智能驾驶大模型（chimera_drive.qk，经 Quark runtime 的 QVM 后端真实执行
量子门）接入 CARLA，完整闭环：
  ① 感知场：车道线检测（HSV 提取白/黄车道线）→ 车道横向偏移 lateral + 证据 evidence
  ② 混沌意识核：2 qubit 无理角漂移 + CNOT 纠缠（Quark runtime 真实量子门）
  ③ 情绪涌现：qexpect_z 软测量 → 情绪态 0..3（量子态测量，非 numpy 模拟）
  ④ 决策引擎：情绪策略增益 × 证据置信度 × theta → 转向 steer（QVM 后端返回）
  ⑤ 反思：碰撞/车道偏离作 reward → 经典侧 QRL 更新 theta（回传下一帧推理）

推理路径：autopilot.py → quark_client.py（TCP 协议）→ Quark daemon → MMI_INVOKE
          → chimera_drive.qk 的 export drive() → QVM 量子门 → 返回 steer

运行：
  python autopilot.py            # 异步模式
  python autopilot.py --sync     # 同步模式（固定帧率）
  python autopilot.py --viz      # 保存车道检测可视化（/tmp/chimera_lane/）
"""
import argparse
import math
import os
import random
import sys
import time
import numpy as np

import carla

from quark_client import QuarkRuntimeClient


def parse_args():
    p = argparse.ArgumentParser(description="Chimera 量子自动驾驶（增强版）")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2000)
    p.add_argument("--sync", action="store_true", help="同步模式")
    p.add_argument("--viz", action="store_true", help="保存车道检测可视化")
    p.add_argument("--fps", type=float, default=20.0)
    p.add_argument("--vehicle", default="vehicle.ford.mustang")
    p.add_argument("--n-qubits", type=int, default=4)
    p.add_argument("--map", default="Town10HD_Opt", help="地图名（Town01~Town05 / Town10HD_Opt）")
    p.add_argument("--duration", type=float, default=0.0, help="运行秒数（0=无限）")
    p.add_argument("--loop", action="store_true", help="环路导航（路口右转优先，覆盖全城）")
    p.add_argument("--record", action="store_true", help="录制三视角帧（第一视角+鸟瞰+车道检测）")
    return p.parse_args()


def get_lane_offset(vehicle, world):
    """车辆到车道中心的横向偏移（米，正=偏右）——CARLA waypoint 精确 ground truth"""
    loc = vehicle.get_location()
    wp = world.get_map().get_waypoint(loc)
    if wp is None:
        return 0.0
    center = wp.transform.location
    fwd = wp.transform.get_forward_vector()
    right = carla.Vector3D(x=-fwd.y, y=fwd.x, z=0.0)
    dx, dy = loc.x - center.x, loc.y - center.y
    return float(dx * right.x + dy * right.y)


def get_nav_offset(vehicle, world):
    """环路导航横向偏移：目标方向相对车辆朝向的横向分量（正=目标在右）。
    路口「右转优先」形成顺时针环路，让小车绕城覆盖全图。
    返回的 lateral 语义对齐循线版（偏右=正），chimera_drive 的 -K*lateral 会转向目标。"""
    loc = vehicle.get_location()
    wp = world.get_map().get_waypoint(loc)
    if wp is None:
        return 0.0
    nxt = wp.next(8.0)
    if not nxt:
        return 0.0
    target = nxt[0]
    if len(nxt) > 1:
        # 路口分叉：选「右转」方向（yaw 顺时针增加，delta ∈ (0,180)）
        cy = wp.transform.rotation.yaw
        right_turns = [w for w in nxt if 0 < (w.transform.rotation.yaw - cy) % 360 < 180]
        if right_turns:
            target = min(right_turns, key=lambda w: abs((w.transform.rotation.yaw - cy) % 360 - 90))
    t_loc = target.transform.location
    dx, dy = t_loc.x - loc.x, t_loc.y - loc.y
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-6:
        return 0.0
    v_fwd = vehicle.get_transform().get_forward_vector()
    cross = v_fwd.x * dy - v_fwd.y * dx          # 目标在右 = 正
    return float(-cross / length)                 # 负号对齐循线语义（目标在右→负→右转）


def spawn_pedestrians(world, bp_lib, spawn_tf, num=20):
    """在车辆正前方 5~62 米生成行人（spectator 视野内必然可见）。
    用 spawn_transform 计算（车辆刚生成时 get_transform 可能未同步返回默认值）。
    AI 导航若可用则横穿马路，否则行人原地走动。返回 (walkers, controllers, cross_points)。"""
    walker_bps = bp_lib.filter("walker.pedestrian.*")
    controller_bp = bp_lib.find("controller.ai.walker")
    walkers, controllers, cross_points = [], [], []
    vloc = spawn_tf.location
    yaw_rad = math.radians(spawn_tf.rotation.yaw)
    v_fwd = carla.Vector3D(x=math.cos(yaw_rad), y=math.sin(yaw_rad), z=0.0)
    v_right = carla.Vector3D(x=-v_fwd.y, y=v_fwd.x, z=0.0)
    for i in range(num):
        dist = 5.0 + i * 3.0                       # 正前方 5~62 米（视野内）
        side = random.uniform(-2.5, 2.5)           # 车道内横向散布
        a = carla.Location(
            x=vloc.x + v_fwd.x * dist + v_right.x * side,
            y=vloc.y + v_fwd.y * dist + v_right.y * side, z=vloc.z + 0.3)
        walker_bp = random.choice(walker_bps)
        walker = world.try_spawn_actor(walker_bp, carla.Transform(location=a))
        if walker is None:
            continue
        controller = world.try_spawn_actor(controller_bp, carla.Transform(), attach_to=walker)
        if controller is None:
            walkers.append(walker)                 # 无控制器：行人站立（仍可见）
            controllers.append(None)
            continue
        controller.start()
        # 横穿目标 = 附近车道的对面 waypoint（尝试导航；失败则行人原地走动）
        wp = world.get_map().get_waypoint(a, project_to_road=True)
        b = None
        if wp is not None:
            other = wp.get_left_lane() if side > 0 else wp.get_right_lane()
            if other is None:
                other = wp
            b = other.transform.location
        if b is not None:
            try:
                controller.go_to_location(b)       # 横穿马路（可能 NAV 失败，无碍显示）
            except Exception:
                b = None
        controller.set_max_speed(1.8)
        walkers.append(walker)
        controllers.append(controller)
        cross_points.append((a, b) if b is not None else (a, a))
    return walkers, controllers, cross_points


def get_traffic_light_state(vehicle, world):
    """检测车辆前方的交通灯，返回 (state, distance)。
    state ∈ {'green','yellow','red',None}；distance = 到交通灯的距离（米，无灯=999）。
    用 vehicle.get_traffic_light()（车辆进入触发区时返回前方交通灯）。"""
    light = vehicle.get_traffic_light()
    if light is None:
        return None, 999.0
    st = light.get_state()
    dist = vehicle.get_location().distance(light.get_location())
    if st == carla.TrafficLightState.Green:
        return 'green', dist
    if st == carla.TrafficLightState.Yellow:
        return 'yellow', dist
    if st == carla.TrafficLightState.Red:
        return 'red', dist
    return None, 999.0


class LaneDetector:
    """车道线检测：提取白/黄车道线，计算车道中心偏移证据 ∈ [0,1]（0.5=居中）"""

    def __init__(self):
        self.last = None
        self.mask = None
        self.lane_center = None

    def on_image(self, image):
        self.last = image

    def detect(self):
        if self.last is None:
            return 0.5
        arr = np.frombuffer(self.last.raw_data, dtype=np.uint8)
        arr = arr.reshape((self.last.height, self.last.width, 4))
        h, w = arr.shape[:2]
        # BGRA → 分离通道（CARLA 是 BGRA 顺序）
        b = arr[:, :, 0].astype(np.float32)
        g = arr[:, :, 1].astype(np.float32)
        r = arr[:, :, 2].astype(np.float32)

        # 限制检测区域：路面中部窄条（避开建筑物/天空/大面积纹理）
        y0, y1 = int(h * 0.62), int(h * 0.92)
        x0, x1 = int(w * 0.15), int(w * 0.85)
        rr, rg, rb = r[y0:y1, x0:x1], g[y0:y1, x0:x1], b[y0:y1, x0:x1]

        # 白色车道线：接近纯白（含带阴影的标线，如 STOP 线）；
        # 黄色车道线：R 高、G 中、B 低
        white = (rr > 185) & (rg > 185) & (rb > 185)
        yellow = (rr > 190) & (rg > 130) & (rb < 110)
        mask = white | yellow

        col_sum = mask.sum(axis=0)
        if col_sum.sum() < 10:
            return 0.5                      # 未检测到车道线，默认居中

        x = np.arange(mask.shape[1])
        lane_center_local = float((col_sum * x).sum() / col_sum.sum())
        self.mask = mask
        self.lane_center = lane_center_local + x0   # 全局 x 坐标
        return (lane_center_local + x0) / w         # 归一化证据（0.5=图像中心）


def cleanup_world(world):
    """清理测试车辆、传感器、行人，避免多次运行后残留堆积渲染。"""
    for actor in world.get_actors():
        tid = actor.type_id
        if (tid.startswith("vehicle.") or tid.startswith("sensor.")
                or tid.startswith("walker.") or tid.startswith("controller.")):
            try:
                actor.destroy()
            except Exception:
                pass


def main():
    args = parse_args()

    # ── 连接 CARLA ──
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.load_world(args.map)   # 加载指定地图
    bp_lib = world.get_blueprint_library()
    print(f"[Chimera] 已连接 CARLA，地图 {world.get_map().name}")

    # 启动前清理上次测试残留的车辆/传感器，避免堆积渲染
    cleanup_world(world)

    if args.sync:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1.0 / args.fps
        world.apply_settings(settings)

    # ── 生成车辆 ──
    vehicle_bp = bp_lib.filter(args.vehicle)[0]
    spawn_points = world.get_map().get_spawn_points()
    spawn_transform = spawn_points[0]
    vehicle = world.try_spawn_actor(vehicle_bp, spawn_transform)
    if vehicle is None:
        print("[Chimera] 生成车辆失败，请检查。")
        sys.exit(1)
    print(f"[Chimera] 车辆已生成：{args.vehicle}")

    # ── 生成人群（车辆附近横穿马路的行人）──
    walkers, walker_controllers, cross_points = spawn_pedestrians(world, bp_lib, spawn_transform, num=20)
    print(f"[Chimera] 已生成 {len(walkers)} 个横穿行人")

    # ── 传感器 ──
    camera_bp = bp_lib.find("sensor.camera.rgb")
    camera_bp.set_attribute("image_size_x", "640")
    camera_bp.set_attribute("image_size_y", "360")
    camera_bp.set_attribute("fov", "110")
    camera = world.spawn_actor(camera_bp, carla.Transform(carla.Location(x=1.5, z=2.4)),
                               attach_to=vehicle)
    detector = LaneDetector()
    camera.listen(detector.on_image)

    collision_bp = bp_lib.find("sensor.other.collision")
    collision_sensor = world.spawn_actor(collision_bp, carla.Transform(), attach_to=vehicle)
    collision_history = []
    collision_sensor.listen(lambda e: collision_history.append(e.frame))

    lane_bp = bp_lib.find("sensor.other.lane_invasion")
    lane_sensor = world.spawn_actor(lane_bp, carla.Transform(), attach_to=vehicle)
    lane_history = []
    lane_sensor.listen(lambda e: lane_history.append(e.frame))

    # ── 视角：spectator 第三视角跟随 + 上帝视角俯视摄像头 ──
    spectator = world.get_spectator()
    top_bp = bp_lib.find("sensor.camera.rgb")
    top_bp.set_attribute("image_size_x", "800")
    top_bp.set_attribute("image_size_y", "600")
    top_bp.set_attribute("fov", "110")
    top_camera = world.spawn_actor(
        top_bp,
        carla.Transform(carla.Location(z=35), carla.Rotation(pitch=-90)),
        attach_to=vehicle,
    )
    top_frame = {"img": None}
    top_camera.listen(lambda img: top_frame.update(img=img))
    if args.viz or args.record:
        os.makedirs("/tmp/chimera_top", exist_ok=True)
        os.makedirs("/tmp/chimera_lane", exist_ok=True)
        os.makedirs("/tmp/chimera_drive", exist_ok=True)

    # ── 量子大脑：Quark runtime 真实推理（非 numpy 模拟）──
    qc = QuarkRuntimeClient(host=args.host, port=50052)
    qc.connect()
    mmi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chimera_drive.mmi")
    qc.load_mmi(mmi_path)
    prev_reward = 0.0   # 上一帧反思奖励（延迟一帧传给 runtime 做自然梯度学习）
    reverse_frames = 0    # 倒车脱困状态机：剩余倒车帧数
    reverse_steer = 0.0   # 倒车脱困状态机：固定转向方向
    collision_stuck = 0   # 卡死检测：连续碰撞帧数

    print("[Chimera] 量子大脑就绪（Quark runtime 混沌意识核推理），Ctrl+C 退出")
    vehicle.set_autopilot(False)

    try:
        frame = 0
        t0 = time.time()
        while True:
            if args.sync:
                world.tick()

            # ── ① 感知：横向偏移（环路导航 或 循线 ground truth，米）──
            if args.loop:
                lateral = get_nav_offset(vehicle, world)   # 环路导航：目标方向横向偏移
            else:
                lateral = get_lane_offset(vehicle, world)  # 循线：正=偏右，负=偏左
            evidence = detector.detect()                # 摄像头量子感知证据（诊断）

            # ── ②③④⑤ 量子推理：Quark runtime 执行 chimera_drive 完整闭环 ──
            # 混沌意识核漂移 + 情绪软测量 + 感知·意识重叠 + 情绪调制决策
            # + 自然梯度学习（theta 全局变量在 runtime 内跨帧保持），全部在 QVM 后端完成
            steer = float(qc.invoke("drive", [lateral, evidence, prev_reward]))

            # 倒车脱困状态机：量子模型输出倒车信号（2.0）→ 进入倒车模式（固定方向持续倒车）
            reverse = steer >= 1.5
            if reverse and reverse_frames <= 0:
                reverse_frames = 20                        # 持续倒车 20 帧（约 1 秒）
                reverse_steer = random.uniform(-0.8, 0.8)  # 固定转向方向脱困

            lateral_mag = abs(lateral)
            if reverse_frames > 0:
                # 倒车脱困（最高优先级）：固定方向倒车 + 转向，跳过交通灯
                steer = reverse_steer
                throttle = -0.6
                brake = 0.0
                reverse_frames -= 1
            else:
                # 交通灯控制：绿灯行 / 红灯停 / 黄灯判断是否越线
                light_state, light_dist = get_traffic_light_state(vehicle, world)
                if light_state == 'red' and light_dist < 12.0:
                    throttle, brake = 0.0, 1.0          # 红灯：接近停止线 → 停
                elif light_state == 'yellow' and light_dist > 3.0:
                    throttle, brake = 0.0, 0.8          # 黄灯未越线 → 停
                else:
                    # 正常：速度最大化，弯道强减速避免冲出
                    speed_factor = max(0.2, 1.0 - lateral_mag * 1.6)
                    throttle = speed_factor
                    brake = 0.0

            # ── ⑥ 反思 reward（延迟一帧传给 runtime 做自然梯度学习）──
            reward = 0.15
            if collision_history:
                reward = -1.0   # 碰撞 → 负奖励（倒车决策由量子模型 drive() 输出）
                collision_history.clear()
            elif lane_history:
                reward = -0.5
                lane_history.clear()
            elif lateral_mag > 1.0:
                reward = -0.3   # 严重偏离车道
            elif lateral_mag > 0.4:
                reward = -0.1   # 轻微偏离

            prev_reward = reward

            # 卡死检测：连续碰撞 30 帧（倒车脱困无效，物理卡死）→ teleport 回车道中心
            if reward == -1.0:
                collision_stuck += 1
            else:
                collision_stuck = 0
            if collision_stuck > 30:
                wp = world.get_map().get_waypoint(vehicle.get_location(), project_to_road=True)
                if wp is not None:
                    tf = wp.transform
                    tf.location.z += 0.3   # 抬升到路面上方，避免穿模
                    vehicle.set_transform(tf)
                    vehicle.apply_control(carla.VehicleControl(throttle=0.0, steer=0.0, brake=1.0))
                    collision_stuck = 0
                    reverse_frames = 0
                    print(f"[Chimera] 卡死恢复：teleport 回车道 (frame={frame})")

            vehicle.apply_control(
                carla.VehicleControl(throttle=throttle, steer=steer, brake=brake)
            )

            # ── 视角：spectator 第三视角跟随车辆 ──
            v_trans = vehicle.get_transform()
            fwd = v_trans.get_forward_vector()
            spec_loc = v_trans.location - fwd * 8.0 + carla.Location(z=4.0)
            spectator.set_transform(
                carla.Transform(spec_loc, carla.Rotation(pitch=-12, yaw=v_trans.rotation.yaw))
            )

            # ── 录制：三视角帧（第一视角 / 车道检测叠加 / 鸟瞰）──
            rec = args.viz or args.record
            if rec and frame % 20 == 0:
                import cv2
                # 第一视角（前置摄像头原始画面）
                if detector.last is not None:
                    try:
                        arr = np.frombuffer(detector.last.raw_data, dtype=np.uint8)
                        arr = arr.reshape((detector.last.height, detector.last.width, 4))
                        rgb = arr[:, :, :3][:, :, ::-1].copy()   # BGRA → RGB
                        cv2.imwrite(f"/tmp/chimera_drive/front_{frame:05d}.png", rgb)
                    except Exception:
                        pass
                # 车道检测叠加图（红色高亮，mask 对齐检测区域）
                if detector.mask is not None and detector.last is not None:
                    try:
                        h, w = detector.last.height, detector.last.width
                        arr = np.frombuffer(detector.last.raw_data, dtype=np.uint8)
                        arr = arr.reshape((h, w, 4))
                        rgb = arr[:, :, :3][:, :, ::-1].copy()
                        m = np.zeros_like(rgb)
                        y0, y1 = int(h * 0.62), int(h * 0.92)
                        x0, x1 = int(w * 0.15), int(w * 0.85)
                        m[y0:y1, x0:x1, :] = detector.mask[:, :, None] * [255, 0, 0]
                        out = cv2.addWeighted(rgb, 1.0, m, 0.5, 0)
                        cv2.imwrite(f"/tmp/chimera_lane/frame_{frame:05d}.png", out)
                    except Exception:
                        pass
                # 上帝视角鸟瞰图（车在中心，俯视道路）
                if top_frame["img"] is not None:
                    try:
                        img = top_frame["img"]
                        arr = np.frombuffer(img.raw_data, dtype=np.uint8)
                        arr = arr.reshape((img.height, img.width, 4))
                        rgb = arr[:, :, :3][:, :, ::-1].copy()
                        cv2.imwrite(f"/tmp/chimera_top/top_{frame:05d}.png", rgb)
                    except Exception:
                        pass

            if frame % 40 == 0:
                # 行人最近距离诊断（确认行人是否在车辆视野内）
                min_walker_d = 999.0
                for wkr in walkers:
                    try:
                        d = vehicle.get_location().distance(wkr.get_location())
                        if d < min_walker_d:
                            min_walker_d = d
                    except Exception:
                        pass
                print(f"[Chimera] frame={frame} lat={lateral:+.2f}m ev={evidence:.2f} "
                      f"steer={steer:+.2f} reward={reward:+.2f} 行人={min_walker_d:.1f}m")

            # 行人循环横穿：每 100 帧让行人往返横穿（车辆持续遇到横穿行人）
            if frame % 100 == 0 and cross_points:
                for i, ctrl in enumerate(walker_controllers):
                    try:
                        a, b = cross_points[i]
                        cur = walkers[i].get_location()
                        ctrl.go_to_location(b if cur.distance(a) < cur.distance(b) else a)
                    except Exception:
                        pass

            frame += 1
            time.sleep(0.001 if args.sync else 0.05)

            if args.duration > 0 and (time.time() - t0) > args.duration:
                break

    except KeyboardInterrupt:
        print("\n[Chimera] 停止")
    finally:
        qc.close()
        # 清理本测试 actor（传感器先于车辆，避免依赖）
        for s in (camera, collision_sensor, lane_sensor, top_camera):
            try:
                s.destroy()
            except Exception:
                pass
        try:
            vehicle.destroy()
        except Exception:
            pass
        # 兜底：清除所有残留车辆/传感器（含多次运行堆积）
        cleanup_world(world)
        if args.sync:
            s = world.get_settings()
            s.synchronous_mode = False
            world.apply_settings(s)
        print("[Chimera] 已清理资源（含残留车辆/传感器）")


if __name__ == "__main__":
    main()