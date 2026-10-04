"""test_drive.py —— 端到端验证 chimera_drive.mmi 的 drive() 能否在 daemon 上真实运行

用法（先启动 daemon）：
  python test_drive.py [帧数]

逐帧调用 drive(lateral, evidence, reward)，打印 steer 与耗时，验证：
  1. MMI 加载成功；
  2. drive() 每帧返回合法的标量（steer ∈ [-1,1] 或倒车 2.0）；
  3. 跨帧可学习状态（全局变量）正常保持（连续调用不崩溃）。
"""
import sys
import time

from quark_client import QuarkRuntimeClient


def main():
    frames = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    qc = QuarkRuntimeClient(host="127.0.0.1", port=50052)
    qc.connect()
    import os
    mmi_name = sys.argv[2] if len(sys.argv) > 2 else "chimera_driveMoE.mmi"
    mmi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), mmi_name)
    mid = qc.load_mmi(mmi_path)
    print(f"[test] 已加载 {mmi_path}，module id={mid}")

    t0 = time.time()
    ok = 0
    for f in range(frames):
        # 模拟一条先偏左后回正、偶尔偏离的车道轨迹
        lateral = 0.4 * ((f % 20) - 10) / 10.0        # [-0.4, +0.4] 波动
        evidence = 0.5 + 0.2 * ((f % 7) - 3) / 3.0    # 摄像头证据 [0.3, 0.7]
        reward = 0.15 if f % 10 != 0 else -0.3        # 偶尔轻微偏离
        try:
            steer = float(qc.invoke("drive", [lateral, evidence, reward], mid))
        except Exception as e:
            print(f"[test] frame={f} 调用失败: {e}")
            break
        if -1.001 <= steer <= 2.001:
            ok += 1
        if f % 10 == 0:
            print(f"[test] frame={f} lat={lateral:+.2f} ev={evidence:.2f} "
                  f"reward={reward:+.2f} -> steer={steer:+.4f}")
    dt = time.time() - t0
    print(f"[test] 完成 {ok}/{frames} 帧，{dt:.2f}s（{frames/dt:.1f} 帧/s）")
    qc.close()


if __name__ == "__main__":
    main()