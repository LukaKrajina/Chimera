# Chimera vs Transformer 基准结果

| 指标 | Chimera (qk) | Transformer (numpy) |
| --- | ---: | ---: |
| 内部状态熵(S/nats) | 1.307 | 1.378 |
| 设定点迭代步数 | 30.000 | 30.000 |
| 设定点残差误差 | 0.154 | 0.257 |
| 误差识别准确率 | 1.000 | 0.500 |

生成自 `benchmark/run_benchmark.py`, 数据来源于对量子混沌意识回路 (`src/`)
与 1 层 2 head Transformer (`benchmark/transformer_baseline.py`) 的相同协议测试。
