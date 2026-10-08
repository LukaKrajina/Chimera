"""autopilotMoE.py —— 量子混沌自动驾驶「MoE 稀疏版」客户端（CARLA 0.9.16）

与 autopilot.py **共享同一套闭环逻辑**（车道感知 → 混沌意识核 → 情绪涌现 →
决策引擎 → 反思学习），但默认加载 **chimera_driveMoE.mmi**（12 专家组稀疏 MoE：
256 组件中每帧只激活 1 个专家组），用于与 autopilot.py（chimera_drive.mmi
全激活深度版，4 分支 × 29 集群 × 4 周期）做**同地图双窗口并行对比**。

双窗口用法（同一张地图，两辆 car 并行，各占一个客户端窗口）：

  窗口 1（全激活版，主客户端，占用 CARLA 渲染窗口）:
      python autopilot.py    --role main      --label Full --mmi chimera_drive.mmi

  窗口 2（MoE 稀疏版，副客户端，不抢渲染窗口）:
      python autopilotMoE.py --role secondary --label MoE

两个客户端互不干扰，副客户端不会：
  • 重载地图（会清掉主客户端的车辆）
  • 全局清理世界（会误删主客户端的车辆）
  • 抢占 spectator 渲染窗口
  • 改同步模式设置 / 调 world.tick()

且**每个客户端窗口都会显示场景中所有车辆的信息**（本车 + 对方车），
便于对比两种模型在同一环境下的驾驶表现。

运行（默认 120 秒三视角录制，由 ffmpeg 后续编码为视频）:
  python autopilotMoE.py --role secondary --label MoE --record --duration 120 --out D:\\rec
"""
import sys

import autopilot


def main():
    # 默认挂载 MoE 模块与 MoE 标签；命令行显式传入时以命令行为准
    argv = list(sys.argv[1:])
    if not any(a == "--mmi" or a.startswith("--mmi=") for a in argv):
        argv += ["--mmi", "chimera_driveMoE.mmi"]
    if not any(a == "--label" or a.startswith("--label=") for a in argv):
        argv += ["--label", "MoE"]
    sys.argv = [sys.argv[0]] + argv
    autopilot.main()


if __name__ == "__main__":
    main()