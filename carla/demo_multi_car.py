#!/usr/bin/env python3
"""demo_multi_car.py —— 两辆车真实 chimera_drive 超大模型驱动，自动驾驶超车情形。

场景：Town04 高速公路东向直行段，车 0（特斯拉）是「慢车」在一车道低速挡路，
车 1（雪佛兰）是「快车」追上慢车后触发自动驾驶超车：
  巡航 → 检测前方慢车 → 变道（二车道）→ 加速超车 → 超过后回原车道。

每辆车独立加载一个 chimera_drive.mmi 实例（独立量子大脑、独立全局状态）。
超车决策（何时变道）在 CARLA 侧完成；转向控制（怎么打方向）由 chimera_drive 的
drive(lateral, evidence, reward) 输出——lateral 传入「到目标车道的横向偏移」，
量子模型据此输出转向，完成变道/回正。

推理路径：demo_multi_car.py → quark_client.py → Quark daemon → chimera_drive.qk 的
export drive() → QVM 量子门 → steer（每车一个 mmi 实例）。
"""
import argparse
import math
import os
import random
import time

import carla

from quark_client import QuarkRuntimeClient

VEHICLE_BPS = [
    "vehicle.tesla.model3",
    "vehicle.chevrolet.impala",
]

# 每辆车的巡航 throttle：车 0 是「慢车」挡路，车 1 是「快车」会超车
CRUISE_THROTTLE = [0.2, 0.5]
LANE_WIDTH = 3.5           # 变道横向偏移（米）
OVERTAKE_THROTTLE = 0.45   # 超车时加速（降低，减少变道惯性过冲）
TRIGGER_DIST = 14.0        # 前方慢车距离 < 此值触发超车
CLEAR_DIST = 3.0           # 慢车落到后方 > 此值判定已超过


def get_lane_offset(vehicle, world):
    """车辆到车道中心的横向偏移（米，正=偏右）。"""
    loc = vehicle.get_location()
    wp = world.get_map().get_waypoint(loc)
    if wp is None:
        return 0.0
    center = wp.transform.location
    fwd = wp.transform.get_forward_vector()
    right = carla.Vector3D(x=-fwd.y, y=fwd.x, z=0.0)
    dx, dy = loc.x - center.x, loc.y - center.y
    return float(dx * right.x + dy * right.y)


def get_lateral_abs(vehicle, base_loc, base_right):
    """车辆相对「基准直线」（base_loc + base_right 横向方向）的绝对横向偏移（正=偏右）。

    直行段超车专用：原车道是直线、横向方向恒定，此值即「到原车道的横向偏移」，
    变道跨中线时不会像 get_lane_offset 那样因「最近车道」切换而跳变。"""
    loc = vehicle.get_location()
    dx = loc.x - base_loc.x
    dy = loc.y - base_loc.y
    return float(dx * base_right.x + dy * base_right.y)


def get_front_vehicle(ego, vehicles, world, lane_offset=0.0):
    """检测 ego 前方（指定车道横向偏移 lane_offset）最近的车。返回 (vehicle, distance)。"""
    ego_loc = ego.get_location()
    wp = world.get_map().get_waypoint(ego_loc)
    if wp is None:
        return None, 999.0
    fwd = ego.get_transform().get_forward_vector()
    right = carla.Vector3D(x=-fwd.y, y=fwd.x, z=0.0)
    best = None
    best_d = 999.0
    for other in vehicles:
        if other is ego or not other.is_alive:
            continue
        o_loc = other.get_location()
        dx = o_loc.x - ego_loc.x
        dy = o_loc.y - ego_loc.y
        dist = math.hypot(dx, dy)
        if dist > 40.0:
            continue
        if fwd.x * dx + fwd.y * dy <= 0.0:      # 只关心前方
            continue
        lat = dx * right.x + dy * right.y - lane_offset
        if abs(lat) > 2.5:                       # 同车道（横向 < 2.5m）
            continue
        if dist < best_d:
            best_d = dist
            best = other
    return best, best_d


def is_slower(front, ego, margin=0.5):
    """前车是否比 ego 慢（速度差 > margin）。"""
    fs = front.get_velocity()
    es = ego.get_velocity()
    f = math.hypot(fs.x, fs.y)
    e = math.hypot(es.x, es.y)
    return f < e - margin


def cleanup_world(world):
    for actor in world.get_actors():
        tid = actor.type_id
        if tid.startswith("vehicle.") or tid.startswith("sensor.") or tid.startswith("walker."):
            try:
                actor.destroy()
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="Town04")
    ap.add_argument("--duration", type=float, default=0.0, help="运行秒数（0=无限）")
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    client = carla.Client(args.host, 2000)
    client.set_timeout(30.0)
    world = client.load_world(args.map)
    m = world.get_map()
    bp_lib = world.get_blueprint_library()
    print(f"[Demo] 地图 {m.name}")

    cleanup_world(world)

    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1.0 / 20.0
    world.apply_settings(settings)

    spawn_points = m.get_spawn_points()
    # 东向长直行段（yaw≈90，前方 ~95m 直行）作基准；5 辆车纵向错开 12m
    base = spawn_points[0]
    for s in spawn_points:
        if 85 <= s.rotation.yaw <= 95:
            base = s
            break
    print(f"[Demo] 基准 spawn 点: yaw={base.rotation.yaw:.0f}（东向直行段）")
    base_loc = base.location
    base_rot = base.rotation
    yaw = math.radians(base_rot.yaw)
    fwd = carla.Vector3D(x=math.cos(yaw), y=math.sin(yaw), z=0.0)
    base_right = carla.Vector3D(x=-fwd.y, y=fwd.x, z=0.0)   # 横向方向（正=偏右）

    # 两辆车并排：车 0（慢车）在一车道（横向 0），车 1（快车）在二车道（横向 -3.5，偏左）
    LATERAL_OFFSET = [0.0, -3.5]
    vehicles = []
    for i, bp_id in enumerate(VEHICLE_BPS):
        bp = bp_lib.find(bp_id)
        lat_off = LATERAL_OFFSET[i]
        tf = carla.Transform(
            carla.Location(
                base_loc.x + base_right.x * lat_off,
                base_loc.y + base_right.y * lat_off,
                base_loc.z + 0.3),
            base_rot)
        v = world.try_spawn_actor(bp, tf)
        if v is None:
            v = world.try_spawn_actor(bp, spawn_points[i % len(spawn_points)])
        if v is None:
            print(f"[Demo] 车辆 {i} 生成失败: {bp_id}")
            continue
        vehicles.append(v)
        print(f"[Demo] 车辆 {i}: {bp_id}  throttle={CRUISE_THROTTLE[i]}  lateral={LATERAL_OFFSET[i]}")

    if len(vehicles) == 0:
        print("[Demo] 无车辆生成，退出")
        return

    # 每辆车一个独立 mmi 实例（独立量子大脑）
    qc = QuarkRuntimeClient(host=args.host, port=50052, timeout=60)
    qc.connect()
    mmi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chimera_drive.mmi")
    mmi_ids = []
    for i in range(len(vehicles)):
        mmi_ids.append(qc.load_mmi(mmi_path))
    print(f"[Demo] {len(vehicles)} 个量子大脑就绪（Quark runtime 真·量子推理），Ctrl+C 退出")

    n = len(vehicles)
    prev_rewards = [0.0] * n
    reverse_frames = [0] * n
    reverse_steers = [0.0] * n
    collision_stuck = [0] * n
    # 超车状态机：0=原车道巡航，-1=左车道超车
    overtake_lane = [0] * n
    overtake_target = [None] * n
    # 目标横向偏移 = 各自初始车道（车 0 在一车道=0，车 1 在二车道=-3.5），保持各自车道
    target_offset = [LATERAL_OFFSET[i] for i in range(n)]
    home_lane = list(LATERAL_OFFSET)   # 每辆车的「原车道」横向偏移（超车时相对它变道）

    spectator = world.get_spectator()

    try:
        frame = 0
        t0 = time.time()
        while True:
            world.tick()

            for i, v in enumerate(vehicles):
                # ── 超车决策状态机（慢车不参与超车）──
                if CRUISE_THROTTLE[i] < 0.3:
                    # 慢车：不超车，始终在原车道巡航挡路
                    overtake_lane[i] = 0
                    overtake_target[i] = None
                elif overtake_lane[i] == 0:
                    front, d = get_front_vehicle(v, vehicles, world, lane_offset=home_lane[i])
                    if front is not None and d < TRIGGER_DIST and is_slower(front, v):
                        overtake_lane[i] = -1
                        overtake_target[i] = front
                        print(f"[Demo] 车 {i} 触发超车（前方慢车 {d:.1f}m，frame={frame}）")
                else:
                    tgt = overtake_target[i]
                    if tgt is None or not tgt.is_alive:
                        overtake_lane[i] = 0
                        overtake_target[i] = None
                    else:
                        vloc = v.get_location()
                        tloc = tgt.get_location()
                        vfwd = v.get_transform().get_forward_vector()
                        dx, dy = tloc.x - vloc.x, tloc.y - vloc.y
                        if vfwd.x * dx + vfwd.y * dy < -CLEAR_DIST:
                            overtake_lane[i] = 0
                            overtake_target[i] = None
                            print(f"[Demo] 车 {i} 超车完成，回原道（frame={frame}）")

                # ── 目标横向偏移平滑过渡（相对原车道：超车时向左变道一车道宽）──
                desired_offset = home_lane[i] + overtake_lane[i] * LANE_WIDTH
                target_offset[i] += (desired_offset - target_offset[i]) * 0.3
                # ── lateral 输入 = 到目标车道的横向偏移（绝对横向，跨中线不跳变）──
                current_lateral = get_lateral_abs(v, base_loc, base_right)
                lateral_input = current_lateral - target_offset[i]
                evidence = max(0.1, 0.7 - abs(current_lateral) * 0.4)
                steer = float(qc.invoke("drive", [lateral_input, evidence, prev_rewards[i]],
                                        mmi_id=mmi_ids[i]))
                # 变道阻尼：限制转向幅度，避免全速转向惯性过冲
                if overtake_lane[i] != 0:
                    if steer > 0.6:
                        steer = 0.6
                    if steer < -0.6:
                        steer = -0.6

                # 倒车脱困
                if steer >= 1.5 and reverse_frames[i] <= 0:
                    reverse_frames[i] = 20
                    reverse_steers[i] = random.uniform(-0.8, 0.8)

                if reverse_frames[i] > 0:
                    steer = reverse_steers[i]
                    throttle, brake = -0.6, 0.0
                    reverse_frames[i] -= 1
                elif overtake_lane[i] != 0:
                    throttle, brake = OVERTAKE_THROTTLE, 0.0
                else:
                    throttle, brake = CRUISE_THROTTLE[i], 0.0

                # 反思 reward（用「到目标车道的偏移」而非绝对横向，避免并排车道误判偏离）
                reward = 0.15
                if abs(lateral_input) > 1.5:
                    reward = -0.5
                elif abs(lateral_input) > 0.5:
                    reward = -0.1
                prev_rewards[i] = reward

                # 卡死恢复
                if reward < -0.4:
                    collision_stuck[i] += 1
                else:
                    collision_stuck[i] = 0
                if collision_stuck[i] > 40:
                    wp = m.get_waypoint(v.get_location(), project_to_road=True)
                    if wp is not None:
                        tf = wp.transform
                        tf.location.z += 0.3
                        v.set_transform(tf)
                        v.apply_control(carla.VehicleControl(throttle=0.0, steer=0.0, brake=1.0))
                        collision_stuck[i] = 0
                        reverse_frames[i] = 0
                        print(f"[Demo] 车 {i} 卡死恢复 (frame={frame})")

                v.apply_control(carla.VehicleControl(throttle=throttle, steer=steer, brake=brake))

            # spectator 跟随车 0
            lead = vehicles[0].get_transform()
            spec_fwd = lead.get_forward_vector()
            spectator.set_transform(carla.Transform(
                lead.location - spec_fwd * 12.0 + carla.Location(z=6.0),
                carla.Rotation(pitch=-14, yaw=lead.rotation.yaw)))

            if frame % 40 == 0:
                lat = " ".join(f"{get_lateral_abs(v, base_loc, base_right):+.2f}" for v in vehicles)
                lane = " ".join(str(x) for x in overtake_lane)
                print(f"[Demo] frame={frame} lateral=[{lat}] overtake=[{lane}]")

            frame += 1
            time.sleep(0.02)
            if args.duration > 0 and (time.time() - t0) > args.duration:
                break

    except KeyboardInterrupt:
        print("\n[Demo] 停止")
    finally:
        qc.close()
        settings = world.get_settings()
        settings.synchronous_mode = False
        world.apply_settings(settings)
        for v in vehicles:
            try:
                v.destroy()
            except Exception:
                pass
        cleanup_world(world)
        print("[Demo] 已清理")


if __name__ == "__main__":
    main()