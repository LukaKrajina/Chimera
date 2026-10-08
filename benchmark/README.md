# benchmark/ — Chimera 对比 Transformer 的 AI 指标与基准测试

## 文件

| 文件 | 作用 |
| --- | --- |
| `chimera_metrics_bench.qk` | Chimera 侧基准: 3 项指标, 经 `qk run` 在 Quark daemon 上执行 |
| `transformer_baseline.py` | Transformer 对照组: 纯 NumPy 的 1 层 2 head 小型 encoder, 执行同一协议 |
| `run_benchmark.py` | 统一调度: 重启 Quark daemon → 运行两侧 → 解析 `runtime.log` (QCOS:WARN) 与 stdout → 汇总 |
| `results.json` | 机器可读结果 |
| `results.md` | 人类可读对比表 |

## 指标映射

| # | Chimera (qk) | Transformer (numpy) | 语义 |
| --- | --- | --- | --- |
| 1 | `chimera_entropy`: dt=0.8、drift 8 步后对 2-qubit 输出做 64 次采样, `shannon4(计数)` | `transformer_entropy`: 同一组随机 token 下 attention 权重分布的平均香农熵 | 内部表示多样性 (nats) |
| 2 | `chimera_setpoint_iters` / `_err`: `improve_drift(mode=0)` (有限差分+定步长) 把 `quality_of(dream_state)` 调到目标 S*=0.5 | `transformer_setpoint_*`: 同一条更新律 (dt↔τ, 2·(S−S*)·dS/dτ) 把平均 attention 熵调到 S*=1.0 | 元认知设定点自适应收敛 |
| 3 | `chimera_error_detect_acc`: `recognize_error` 对 16 对 (predicted, actual) 状态的识别准确率 (一半匹配, 一半注入 Rz(π)) | `transformer_error_detect_acc`: 训练后用 1−max softmax>0.5 门控识别噪声污染样本 | 预测误差自检 |

## 运行

```bash
cd D:/Project/Chimera
python benchmark/run_benchmark.py
```

前置要求: `D:/Project/Quark/bin/win32-x64/runtime.exe --daemon` 可启动;
本脚本会自行 `taskkill` 重启它(避免不同 .qk 模块共享同一 JIT 符号空间导致
`duplicate definition` 错误)。

## 说明

- 指标 1/2 的对比是“同族关系”(都是分布离散度/同一外环控制律),
  绝对数值反映两套机制在各自信号空间上的工作点;
- 指标 3 的两侧阈值协议不同(量子对: 态重叠度; 经典对: softmax 置信度),
  因此 1.000 vs 0.500 更多说明"柔性上限 vs 严格上限"的差异,
  并不直接代表谁更准, 真正公平的数值比较需在协议一致化后再做。
