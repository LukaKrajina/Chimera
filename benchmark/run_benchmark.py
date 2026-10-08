"""run_benchmark.py —— 统一运行 Chimera(qk) 与 Transformer(numpy) 基准, 并汇总对比。

使用:  cd D:\\Project\\Chimera
       python benchmark/run_benchmark.py

流程:
  1) 重启 Quark daemon(避免模块间符号重复定义污染), 截获 runtime.log 增量;
  2) `qk run benchmark/chimera_metrics_bench.qk` → 三条 Chimera 指标;
  3) `python benchmark/transformer_baseline.py` → 三条 Transformer 对照指标;
  4) 写 benchmark/results.json 与 benchmark/results.md。
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib  # noqa: F401
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]              # Chimera/
LOG = Path(os.environ["LOCALAPPDATA"]) / "Quark" / "runtime.log"
QK = ["node", str(ROOT.parent / "Quark" / "server" / "out" / "cli.js")]


def log_tail_lines(prev_bytes: int) -> list[str]:
    try:
        data = LOG.read_bytes()[prev_bytes:]
    except FileNotFoundError:
        return []
    return data.decode("utf-8", errors="replace").splitlines()


def parse_qcos(lines: list[str]) -> dict[str, int]:
    metrics: dict[str, int] = {}
    pending = None
    for line in lines:
        m = re.match(r"\[QCOS:WARN \] (.+)", line)
        if not m:
            continue
        body = m.group(1).strip()
        if body.startswith("METRIC "):
            pending = body[len("METRIC "):]
        elif pending is not None and body.lstrip("-").isdigit():
            metrics[pending] = int(body)
            pending = None
    return metrics


def restart_daemon(wait_s: float = 4.0) -> int:
    subprocess.run(["taskkill", "/F", "/IM", "runtime.exe"],
                   capture_output=True)
    time.sleep(1.0)
    exe = ROOT.parent / "Quark" / "bin" / "win32-x64" / "runtime.exe"
    kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                  cwd=str(exe.parent), creationflags=0x00000008)  # DETACHED_PROCESS
    subprocess.Popen([str(exe), "--daemon"], **kwargs)
    # 等端口
    for _ in range(int(wait_s * 5)):
        try:
            socket.create_connection(("127.0.0.1", 50052), timeout=0.5).close()
            return len(LOG.read_bytes()) if LOG.exists() else 0
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("Quark daemon 未在预期时间内上线")


def main() -> None:
    prev = restart_daemon()
    time.sleep(0.5)

    # --- Chimera ---
    subprocess.run(QK + ["run", "benchmark\\chimera_metrics_bench.qk"],
                   cwd=str(ROOT), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    chimera = parse_qcos(log_tail_lines(prev))

    # --- Transformer ---
    proc = subprocess.run([sys.executable, str(ROOT / "benchmark" / "transformer_baseline.py")],
                          capture_output=True, text=True, cwd=str(ROOT))
    tf: dict[str, int] = {}
    pending = None
    for line in proc.stdout.splitlines():
        if line.startswith("METRIC "):
            pending = line[len("METRIC "):]
        elif pending is not None and line.lstrip("-").isdigit():
            tf[pending] = int(line)
            pending = None

    # --- 汇总 ---
    def f(v: float) -> str:
        return f"{v:.3f}"

    rows = [
        ("内部状态熵(S/nats)", chimera.get("chimera_entropy", float("nan")) / 1000.0,
         tf.get("transformer_entropy", float("nan")) / 1000.0),
        ("设定点迭代步数", chimera.get("chimera_setpoint_iters", float("nan")),
         tf.get("transformer_setpoint_iters", float("nan"))),
        ("设定点残差误差", chimera.get("chimera_setpoint_err", float("nan")) / 1000.0,
         tf.get("transformer_setpoint_err", float("nan")) / 1000.0),
        ("误差识别准确率", chimera.get("chimera_error_detect_acc", float("nan")) / 1000.0,
         tf.get("transformer_error_detect_acc", float("nan")) / 1000.0),
    ]

    results = {
        "chimera": chimera,
        "transformer": tf,
        "table": [
            {"metric": name, "chimera": c, "transformer": t} for name, c, t in rows
        ],
    }
    (ROOT / "benchmark" / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Chimera vs Transformer 基准结果",
        "",
        "| 指标 | Chimera (qk) | Transformer (numpy) |",
        "| --- | ---: | ---: |",
    ]
    for name, c, t in rows:
        lines.append(f"| {name} | {f(c)} | {f(t)} |")
    lines += [
        "",
        "生成自 `benchmark/run_benchmark.py`, 数据来源于对量子混沌意识回路 (`src/`)",
        "与 1 层 2 head Transformer (`benchmark/transformer_baseline.py`) 的相同协议测试。",
    ]
    (ROOT / "benchmark" / "results.md").write_text("\n".join(lines) + "\n",
                                                   encoding="utf-8")

    import sys as _s
    _s.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(l for l in lines))
    print("\nresults.json / results.md written.")


if __name__ == "__main__":
    main()