# Chimera Evaluation Specification (CES)

> Status: **v1.0 · 2026-11-11 · living document**
> Scope: Chimera 架构 + Jarvis 模型 + Ravendrel QVM/QM 运行时 + OpenButler burn-in 流水线。
> 本文是**增量规范**：不修改 `benchmark/results.md`、`results.json`、`run_benchmark.py`
> 或任何既有 `.rvdl` 模块。

---

## 0. 认识论定位

`README.md` 的「重要声明」已说明：本仓库关于量子混沌意识、元认知与情绪的论述是
**思想实验 / 概念设计，未经实验验证或同行评议**。因此本文所有数字都是对**实现**的
测量，不是认知、意识或通用智能的证据。

**CES 刻意不产出单一的类 IQ 分数**：系统目前没有流体推理、迁移、规划、持续学习或
人类基线评测，标量「智能」分数不可证伪。CES 定义六个正交指标族 + 明确的证伪规则。

---

## 1. 能力层级（L0–L5）

非行业标准阶梯，仅用于沟通距离。层级**不可补偿**（吞吐再高也不能替代缺失的推理门槛），
且必须**全部**门槛通过才算达到。

| Tier | 定义 | 门槛 | 当前（2026-11-11） |
| --- | --- | --- | --- |
| L0 | 机制清单 | 每个机制有可调用入口 + 测试 | PASS — 13 Studio 特性、QCF 4 函数、24 个导出 `qai_*` |
| L1 | 单任务可训练可复现 | 固定种子、确定性 loss/grad、与参考实现 parity | PASS — 48/96 f64 参数、dense/BAT parity ≤1e-16、41 项 QCF 检查 |
| L2 | 多模态 / 多任务种子 | ≥2 模态独立种子且可加载 | PARTIAL — 文本 + synthetic-CC0 + research-only 图像种子 |
| L3 | 持续学习 + 世界模型 + 内在动机闭环 | 动作、反馈、回放、动机写回的 agent loop | NOT MET — 机制离线验证（41 断言、10 次 MMI 调用），无 agent loop |
| L4 | 组合泛化、迁移、因果反事实 | 留出任务族 + 扰动测试 | NOT MET — 无 benchmark |
| L5 | 人类水平通用认知 | 跨领域人类基线 | NOT MET |

**当前位置：L1 完成 / L2 部分。** 不要报告「接近 L5 的百分比」——层级是序数，不是比例尺度。

---

## 2. 指标族

每条指标必须记录：`metric id`、`unit`、测量流程、`seed`、`hardware`、`software commit`、
数据集分片 + `sha256`、样本数、置信区间或 run-to-run 方差、`verdict (pass/fail/inconclusive)`。

### 2.1 模型质量（MQ）

| ID | 指标 | 单位 | 流程 | 基线 |
| --- | --- | --- | --- | --- |
| MQ-1 | `best_loss` | MSE | QKM1 元数据 `train.best_loss` | 0.69–0.83 dense；1.36–1.56 MoE-32 |
| MQ-2 | 8-bit 读出准确率 | ratio | `train.last_accuracy` | 0.689–0.720（随机 0.5） |
| MQ-3 | Dense-vs-sparse parity | max abs grad diff | 相同 θ/ket/seed，双后端 | ≤1e-16 |
| MQ-4 | burn-in 下 loss 单调性 | 上升分片数 | 逐分片 `train.best_loss` 链 | 0（非单调分片须解释） |
| MQ-5 | Lyapunov 单调性 | ΔF ≤ 0 | QCF `descent_step`，10 步 | 10/10（F₁₀ = −0.75129703） |

MQ-1/MQ-2 仅是**下一字节预测**，不得引用为语言理解、推理或通用能力。

### 2.2 吞吐与能耗（TE）

| ID | 指标 | 单位 | 流程 |
| --- | --- | --- | --- |
| TE-1 | 训练吞吐 | samples/s | `train.total_steps / train.duration_sec` |
| TE-2 | 能效 | samples/joule | TE-1 ÷ 实测板卡功率 |
| TE-3 | 全语料覆盖率 | bytes/s | `cursor.burnedBytes` 增量 ÷ 墙钟时间 |
| TE-4 | GPU 利用率 / 占用 | % | adjoint kernel 前后设备计时 |
| TE-5 | P50 / P99 步延迟 | ms | 逐步插桩，≥10⁴ 步 |
| TE-6 | 相对稠密基线加速 | × | 同工作负载 CUDA+BAT+sparse vs 稠密 CPU |

已测参考点：CPU→CUDA 1.80×、MoE-32 3.16×、BAT B32/tile8 3.15×；完整 36.83 GiB
epoch 按当前吞吐约 3–4 年，Ultra `epochs:40` 约 120–160 年。**TE 描述吞吐，不描述能力。**

### 2.3 稀疏表示可信度（ST）

| ID | 门槛 |
| --- | --- |
| ST-1 | 与稠密态保真度 ≥ 1 − δ |
| ST-2 | 逐 tile 与聚合报告丢弃的 L2 质量 δ |
| ST-3 | trace-distance 界 `2√δ + δ`（EBAT）成立；实测误差 ≤ 界 |
| ST-4 | 梯度 parity：`ε=0` 或 `n ≤ n₀`（默认稠密）时 ≤1e-16 |
| ST-5 | 策略选择正确：在标注套件上选中代价模型 argmin |
| ST-6 | 格式兼容：`.rvdlm` 不变；`rvdl serve` 加载返回 200 |

### 2.4 并发与资源伸缩（CR）

面向 A2L 并发层与六个 C++ 可执行程序。

| ID | 门槛 |
| --- | --- |
| CR-1 | 强伸缩：2/4/8/16 线程相对 1 线程加速比 + Amdahl 拟合 |
| CR-2 | 弱伸缩：固定每线程工作量时效率 ≥ 0.7（Gustafson） |
| CR-3 | 锁竞争：µs/spin、最大队列深度、10⁶ 操作无饥饿 |
| CR-4 | work-stealing 效率：窃取比、空闲线程时间 |
| CR-5 | IO 多路复用：1k 并发连接下的 connections/s 与 P99 延迟 |
| CR-6 | 分布式分片：N 节点线性扩展、checkpoint/rollback 正确性 |
| CR-7 | 无数据竞争：所有新代码路径 TSAN 风格干净 |
| CR-8 | 无回归：MMI 命令字、协议帧、`.rvdlm`、burn-in cursor 语义不变 |

### 2.5 认知闭环 / 持续学习（CL）

| ID | 门槛 |
| --- | --- |
| CL-1 | 灾难性遗忘：训练任务 B 后任务 A 的 Δaccuracy |
| CL-2 | k 步规划成功率：世界模型 rollout 与真实轨迹差距在 `qwm_fidelity_bound` 内 |
| CL-3 | 内在动机有效性：reward 写回 vs 无动机控制的探索覆盖率 |
| CL-4 | 发育收敛：QCF `F` 单调、gap ≤ τ_g、残差 → 0 |
| CL-5 | 覆盖完备性：扩展前后 frame-potential 缺口 `Δ = FP − 2/(d(d+1))` |
| CL-6 | 反事实一致性：不同动作序列产生可区分轨迹 |

### 2.6 可复现、安全与许可（RS）

| ID | 要求 |
| --- | --- |
| RS-1 | 固定种子、配置哈希、分片 sha256、确定性重放 |
| RS-2 | `research_only` 图文数据不得进入商业评测或商业模型；以 `commercial-index.json` / `multimodal-index.json` 为准 |
| RS-3 | 数值健康：loss / θ / 元数据无 NaN/Inf；`to_str` 拒绝非有限值 |
| RS-4 | 可恢复：任意分片 kill 后从 `cursor.json` 重启，最多重跑一个分片 |
| RS-5 | 所有上报数字链接到产物路径 + 命令 |

---

## 3. Benchmark 套件（新增，不替换现有）

| 套件 | 用途 | 位置 |
| --- | --- | --- |
| `ces-core` | 固定分片上的 MQ-1..5 + ST-1..6 | `benchmark/ces_core/` |
| `ces-throughput` | TE-1..6（含能耗采样） | `benchmark/ces_throughput/` |
| `ces-concurrency` | CR-1..8 harness | `Ravendrel/runtime/tests_a2l/` |
| `ces-continual` | CL-1..6 agent loop | `benchmark/ces_continual/` |
| `ces-report` | 汇总为带 verdict 的 `EVALUATION_RESULTS.json` | `benchmark/ces_report/` |

现有 `benchmark/results.md`（熵 1.307 vs 1.378、30 迭代、残差 0.154 vs 0.257、
错误识别 1.000 vs 0.500，对比 1 层 2 头 NumPy Transformer）作为**历史 smoke test**
保留，标注 `toy-smoke`，不作为 L2–L5 的证据。

---

## 4. 证伪规则

1. 「稀疏后端保持 parity」为假，若 ST-4 在 `ε=0` 或 `n ≤ n₀` 时超过 1e-16，
   或 ST-3 实测误差超过报告界。
2. 「并发提升吞吐」为假，若 CR-7 干净时 TE-1 在 4+ 线程无提升，或 CR-8 回归。
3. 「持续学习」为假，若 CL-1 劣化超出声明容差，或 RS-4 在任一注入 kill 点失败。
4. 「达到能力层级 Lk」为假，若任一 Lk 门槛缺少记录结果。
5. 缺少 `seed / shard sha256 / command` 字段的指标**无效**，而非「不完整」。

---

## 5. 报告格式

`EVALUATION_RESULTS.json` 每条指标一个条目：

```json
{
  "metric": "ST-4",
  "value": 1.3e-16,
  "unit": "max_abs_grad_diff",
  "verdict": "pass",
  "tier_gate": ["L1", "ST"],
  "run": {
    "seed": 42,
    "command": "...",
    "shard_sha256": "...",
    "hardware": "...",
    "samples": 4094,
    "repeats": 3,
    "variance": 0.0
  },
  "artifact": "D:/JarvisModel/.../manifest.json"
}
```

汇总报告必须声明**最低通过层级**，不得给出复合分数。

---

## 6. 当前公开基线（2026-11-11）

| 项 | 值 | 来源 |
| --- | --- | --- |
| 可训练权重 | 48 / 96 f64 | `D:/JarvisModel/index.json` |
| 运行时状态 | 2^16 复振幅（1 MiB）；稠密上限 2^20 | `qhal/QVM.hpp` `DENSE_MAX_QUBITS=20` |
| 上下文 | 32 tokens | `context.window=LF2C_32Tokens_16Q` |
| 种子 | 8 文本 + 2 research-only 多模态 + 2 商业合成 | `index.json`、`multimodal-index.json`、`commercial-index.json` |
| 每模型种子样本 | 4,094 | `train.steps_done` |
| 数据集 | 39,547,450,331 B（36.83 GiB） | `JarvisLearnData/manifest/manifest.json` |
| burn-in 覆盖 | 90,120 B = 0.000228% | `cursor.json` |
| 测试门槛 | 251/251、372/372、11/11、8/8、41/41、10/10 | 各项目测试套件 |
| 最低通过层级 | **L1**（L2 部分） | §1 |

人类规模参照（数量级，非目标）：86 × 10⁹ 神经元、约 20–25 W（PNAS 2012,
PMC3386878）；突触 10¹⁴–10¹⁵ 为估计值而非直接计数。该文亦指出神经元/突触总数
不决定认知能力，故此比较仅是尺度合理性检查，**不是充分性论证**。

---

## 7. 验证记录汇总（2026-11-11 → 11-16）

| 检查 | 结果 |
| --- | --- |
| CES v1.0 落地 | `EVALUATION.md` 新增；既有 benchmark 文件未动；稀疏 31/31、A2L 29/29、QCF 41/41 |
| 全量构建 | Ravendrel 10 目标 ALL TARGETS OK；OpenButler desktop build OK |
| MMI 回归 | `LOAD_MMI` + `MMI_INVOKE` 10/10 数值不变 |
| 训练 parity | `train_cli` best_loss 0.7348113519（A2L 前后一致）；0.8229257445（sparse/ras 默认路径一致） |
| ST-4 CPU/CUDA | `--sparse-epsilon 0` 与 auto/dense 完全一致（0.8229257445） |
| ST-3 界 | `ε=0.01` → 44/64 tiles、skipped_mass 8.3266e-4、报告界 0.272793884，实测在界内 |
| 主机长回归 | `state_backend_regression` 205 checks / 0 failures |
| 设备长回归 | `quantum_accel_test` 176 checks / 0 failures（CUDA sparse/dense 64 例矩阵） |
| 真实 IO | `NativeReactor::probe()` IOCP usable=1；`a2l_net_test` 34/34；`a2l_netio_test` 18/18 |
| 分布式 AllReduce | `a2l_collective_test` 37/37；两节点 GRAD 交换归约为 2.5/3.5/4.5 |
| RAS 低秩态 | `lowrank_state_test` 95/95；rank 6/16 压缩 2.13×；实测 0.6483 ≤ 界 1.7170 |
| RAS adjoint | `ras_adjoint_test` 89/89；同域 corr 0.9999、跨域 0.9997–0.9998 |
| 独立套件总计 | 582 checks / 0 failures（WSL 9 个可执行文件，`-Wall -Werror` 干净） |
| 下游回归 | OpenButler 251/251、desktop 372/372、Jarvis 11/11、annotate 8/8 |
| 声明的边界 | Linux io_uring 仅实现未在本机执行；RAS 的 CUDA device 热路径仍用 tile 紧凑态 |

落地过程中发现并修复的真实缺陷（记录以免遗忘）：MPMC slot 序号初始化、
`ThreadPool::submit` move 后空 `std::function`、epoch retire 使用当前 epoch、
CLI `extra_meta` 键冲突覆盖 `train.sparse_error_bound`、sparse adjoint 反向循环
`param` 越界写堆、跨域 CNOT 未施加门即重分解、幂迭代奇异值未降序、RAS 梯度
中途 `.real()` 丢虚部、RY 配对项方向写反、重分解上限触发 exact 空因子、
`set_factors` 未设 `max_rank_`，以及两处测试夹具错误。全部由断言钉住。

## 8. 变更策略

- CES v1 为增量规范。修改任何既有 benchmark 文件须显式版本升级 + 迁移说明。
- 新指标必须以新 ID 增量加入；既有 ID 永不重定义。
- 每项声称的改进必须附带 §5 完整运行记录。
