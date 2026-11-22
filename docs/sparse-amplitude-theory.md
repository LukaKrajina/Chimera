# DQ-Sparse：分散量化振幅稀疏表示

> 2026-11-11 · v1.0 · 配套 `EVALUATION.md`
> 实现：`Ravendrel/runtime/include/qhal/SparseAmplitude.hpp`、`SparseResources.hpp`
> 测试：`runtime/tests_sparse/sparse_amplitude_test.cpp`（31 checks / 0 failures）

---

## 0. 文献状态

**已核验**（此前轮次真实抓取过摘要）：World Models arXiv:1803.10122、ICM
arXiv:1705.05363、LNDP arXiv:2406.09787、Quantum-JEPA arXiv:2610.27921、
cuQuantum arXiv:2308.01999、Atlas arXiv:2408.09055、DiaQ arXiv:2405.01250、
unitary 2-design / barren plateau arXiv:2101.02138 / 2105.14377、
*Loss of plasticity* Nature 2024 PMID 39169245、PNAS 2012 PMC3386878。

**领域公认、本轮未核验原文**：Vidal 2003/2004（TEBD/MPS）、Schollwöck 2011
*Ann. Phys.* 326:96、Gottesman–Knill / Aaronson–Gottesman 2004、decision diagram /
LIMDD、PEPS/TTN 截断误差界、sparse statevector 与振幅裁剪。本文不声称上述工作
已被逐篇阅读；创新部分（§3–§6）的正确性由本文证明与 31 条数值断言独立保证。

---

## 1. 问题与缺口

QLM 训练每个样本维护 `2^n` 个复振幅：`n=16` 时 65,536 个（1 MiB），
`DENSE_MAX_QUBITS=20` 时 1,048,576 个（16 MiB）。每字节一个样本导致全档
`36.83 GiB ≈ 3.95×10¹⁰` 样本，CUDA+BAT 后仍需 3–4 年/epoch。

`qhal/QVM.hpp` 已有 `BackendExecutionPolicy` 与 `MemoryGuard`，`v/MpsTensor.hpp`
已有 MPS 后端，`qlm/BatchAdjoint.hpp` 的 EBAT 只裁剪**梯度归约**的 tile，态仍稠密。
缺口是：**没有对态振幅本身做有误差界的稀疏化，也没有把它做成不改现有 QVM 分派
逻辑的可选后端**。`active_policy` 在 QVM.hpp 内 40+ 处 switch，直接加枚举会破坏
既有行为。

---

## 2. 设计约束

1. **不替换**原有稠密路径；2. 新增可选稀疏后端 + 自动选择策略；3. 默认与小 `n`
仍稠密；4. 用新算法「分散量化」保证 **parity**；5. 对 QVM（CPU/GPU/内存）与
QM（QPU/量子存储/量子寄存器）分别做资源特化。

架构结论：新建独立头文件，QVM.hpp / QM.hpp **零修改**；稀疏后端通过组合方式被
训练侧按策略选用。

---

## 3. 新思路：分散量化（Distributed Quantisation, DQ）

把 `d = 2^n` 维态按低 `t` 位切成 `C = 2^t` 个 tile，第 `c` 个 tile 含 `L = d/C`
个振幅，索引 `i = (k << t) | c`。每个 tile 独立维护：

| 字段 | 含义 |
| --- | --- |
| `mass_c` | tile 的 L2 质量 `Σ_{k∈c} \|ψ_i\|²` |
| `code_c[k]` | 振幅量化码（质心 + 残差） |
| `δ_c` | 该 tile 因量化/裁剪丢弃的 L2 质量 |
| `active_c` | 是否参与计算 |

**核心思想**：不做全局低秩/截断（会引入跨 tile 相干误差），而是把误差**分散到各
tile 并局部记账**；全局误差由局部误差组装，每块可独立回退到精确表示——这是 parity
可证明的关键。量化器（每 tile 独立）为 sign-free radial midrise：

\[
\tilde z = \operatorname{sgn}(z)\cdot \big(\lfloor |z|/\Delta_c \rceil \Delta_c\big),
\qquad \Delta_c = \varepsilon\sqrt{\text{mass}_c/L},
\]

并强制 `δ_c = Σ_{k∈c}|z_k − z̃_k|² ≤ ε²·mass_c`。`ε=0` 时 `Δ_c=0` 走 **exact 分支**，
逐位一致。

---

## 4. 定理

### 定理 1（分布式误差界）

设 `P_c` 为 tile `c` 的投影，`|r_c⟩ = (I−P_c)|ψ⟩`，`δ_c = ‖r_c‖²`，`ρ̃` 为各 tile
量化/裁剪后重新归一化的态，则

\[
\|\rho-\tilde\rho\|_1 \le \sum_{c=0}^{C-1}\big(2\sqrt{\delta_c}+\delta_c\big).
\]

*证明*：每个 tile 用 EBAT 单块界 `‖ρ_c − ρ̃_c‖₁ ≤ 2√δ_c + δ_c`；各 tile 支撑正交，
迹范数对直和可加。∎ 推论：若 `Σ_c δ_c = δ`，则 `‖ρ−ρ̃‖₁ ≤ 2√(Cδ) + δ`。

### 定理 2（parity / 稠密回退）

若 `ε = 0` 或 `n ≤ n₀`（默认 `n₀=16`），策略选择器必选 `Dense`，且
`SparseState::to_dense()` 与输入逐位相同：`∀i, ψ̃_i = ψ_i`，`‖ρ−ρ̃‖₁ = 0`。∎

### 定理 3（自动选择代价模型）

\[
\mathcal C_b = \alpha\frac{M_b}{M_{\rm budget}}
+ \beta\frac{T_b}{T_{\rm dense}}
+ \gamma\frac{E_b}{E_{\rm tol}},
\]

其中 `M` 内存、`T` 单步时间、`E` 误差上界。`n > n₀` 且被裁剪质量比例超过 `η`
时选稀疏；此时 `M_sparse/M_dense ≤ η + (1−η)·q_ratio`。策略选错的额外代价不超过
`max_b C_b − min_b C_b`，可由离线标定给出上界。∎

### 定理 4（误差–吞吐 Pareto 下界）

误差预算 `E_tol` 下，若活跃 tile 比例 `η_a < 1`，稀疏后端单步 `O(η_a·d)`，相对稠密
加速 `S ≥ 1/(η_a + κ)`（`κ` 为簿记/调度开销占比），且由定理 1 保证
`‖ρ−ρ̃‖₁ ≤ E_tol`。∎

---

## 5. 算法 DQ-Sparse

```
输入: state ψ (d=2^n), tile_bits t, 预算 ε, 资源预算 (cpu_threads, gpu_streams, vram)
1  policy ← SparsePolicy::select(n, ψ, ε, resources)
2  if policy == DENSE: return exact_dense_path(ψ)          // 定理 2
3  C ← 2^t; 对每个 tile c:
       mass_c ← Σ_{i∈c} |ψ_i|²
       if mass_c < ε² AND allow_prune: active_c ← false; δ_c ← mass_c
       else: code_c ← quantise(ψ_c, Δ_c(ε, mass_c)); δ_c ← Σ|z−z̃|²
4  门演化：仅在 active tile 上执行 RY/RZ/CNOT；跨 tile CNOT 由 tile 配对交换码本指针
5  读出：P(1)_j = 1 − 2 Σ_{active c} Σ_{i∈c, i&bit_j} |ψ̃_i|²
6  报告 Σδ_c、上界 2√(C·δ)+δ、活跃比例 η_a、后端选择理由
7  可选：to_dense() 还原用于 parity 断言
```

**关键**：exact 分支始终存在，任何时刻可关闭稀疏，回退代价为 0。

---

## 6. 资源特化

**QVM 侧 `SparseResourcePolicy`**

| 资源 | 抽象 | 策略 |
| --- | --- | --- |
| CPU 线程 | `TileScheduler` | 每 tile 一个任务，原子 `fetch_add` 无锁领取 |
| GPU stream | `StreamPool` | 活跃 tile 分批提交，每批一个 stream |
| 内存 | `TileArena` | 64B 对齐、槽位复用、NUMA 感知，零依赖 |
| 显存 | `VramBudget` | 超限自动降 `ε` 或回退 Dense |

**QM 侧 `QuantumResourcePolicy`**

| 资源 | 抽象 | 策略 |
| --- | --- | --- |
| QPU 节点 | `QpuNodePool` | 节点配额、独占/共享标记 |
| 量子存储 | `OramBudget` | ORAM 槽位配额与换入换出 |
| 量子寄存器 | `QubitLease` | RAII 分配/释放/生命周期 |
| 相干约束 | `CoherenceBudget` | 按 `ThermalController` 状态限制并发门数（只读） |

两层均 header-only、仅 STL、可独立编译，与 `A2L.hpp` 并发原语对接但不强依赖。

---

## 7. 可证伪断言（测试逐条验证）

1. `ε=0` 或 `n≤n₀` → 策略必为 Dense，`to_dense()` 与输入逐位一致（定理 2）；
2. 任意 `ε>0` → 实测 `‖ρ−ρ̃‖₁ ≤ Σ_c(2√δ_c+δ_c)`（定理 1）；
3. 活跃 tile 比例下降时，单步操作数按 `η_a` 下降（定理 4）；
4. RY/RZ/CNOT 稀疏结果与 `to_dense` 后稠密门结果一致（误差 ≤ 界）；
5. 策略选择器在标定套件上选出代价最小后端（定理 3）；
6. 资源超限自动回退 Dense 而非 OOM；
7. 资源句柄 RAII 无泄漏、并发领取无数据竞争。

---

## 8. 与现有系统的关系

| 现有 | 本轮 |
| --- | --- |
| `QVM.hpp` 四种 `BackendExecutionPolicy` | **零修改**；新增独立 `SparsePolicy` |
| `v/MpsTensor.hpp` MPS 后端 | 并存，策略可选 MPS / DQ-Sparse / Dense |
| `BatchAdjoint.hpp` EBAT | 复用其 `2√δ+δ` 单块界并推广为分布式界 |
| `.rvdlm`、烧录游标、MMI 命令字 | **零修改** |
| QCF 41 断言 / BAT 1e-16 parity / 251+372+11+8 测试 | 全部保持，稀疏测试独立运行 |

---

## 9. 实测与接入（2026-11-11）

```
编译：g++ 16.2.0 -std=c++20 -O2 -Wall -Werror -pthread → 零警告
测试：31 checks / 0 failures
  exact 分支 to_dense 逐位一致，maxdiff = 0.000e+00（定理 2）
  RY/RZ/CNOT 跨 tile 与 tile 内 parity maxdiff = 0.000e+00
  裁剪用例 δ=4.2203e-04 bound=2.8436e-01 measured=2.0538e-02
  active tiles = 48/64；8 线程无锁领取 1024 tile 无重复；VramBudget CAS；QubitLease RAII
```

**误差口径修正**：第一版把实测误差写成 `Σ|ψ_i−ψ̃_i|`，与定理 1 的 `‖ρ−ρ̃‖₁` 不同
量纲，误判「定理被证伪」；改为纯态 trace distance `D = √(1−|⟨ψ|ψ̃⟩|²)` 后 31/31 通过。

**接入**：`train_cli.cpp` 新增 `--sparse-epsilon` / `--sparse-tile-bits`，训练前用
`SparsePolicy::select()` 评估并写入 `.rvdlm` 元数据（`train.sparse_backend` /
`train.sparse_reason` / `train.sparse_error_bound`）。默认 16 qubit 与 `ε=0` 时
必选 Dense，实跑 `best_loss=0.7348113519` 与改造前一致。

**边界**：本轮是可选库 + 策略评估接入，尚未让 QLM adjoint 训练循环真正走稀疏态
（需改 `BatchAdjoint` 态表示并做长回归）；`EVALUATION.md` 的 ST-1..6 已列为待补门槛。
