# RAS：Rank-Adaptive State —— 振幅矩阵的秩自适应因子化

**状态**：2026-11-14 实现并验证（`Ravendrel/runtime/include/qhal/LowRankState.hpp`，
`runtime/tests_sparse/lowrank_state_test.cpp`，95 checks / 0 failures）。
纯新增，不改任何既有态表示或训练数值路径。

---

## 1. 文献脉络（1936–2026）

| 工作 | 年份 | 关系 |
| --- | --- | --- |
| Eckart & Young, *Psychometrika* 1:211；Mirsky | 1936 / 1960 | 低秩最优逼近与 Frobenius / 谱范数误差（L1 来源） |
| Golub & Kahan / Golub & Reinsch SVD | 1965 / 1970 | 奇异值分解的数值基础 |
| Vidal, *PRL* 91:147902 / 93:040502 | 2003 / 2004 | MPS / TEBD：用纠缠限制有效秩 |
| Oseledets, *SIAM J. Sci. Comput.* 33:2295 | 2011 | Tensor-Train 分解 |
| Schollwöck, *Ann. Phys.* 326:96 | 2011 | MPS/DMRG 综述：截断维数 χ 与丢弃权重 |
| Halko, Martinsson & Tropp, *SIAM Review* 53:217 | 2011 | 随机化 SVD / 幂迭代 |
| cuQuantum arXiv:2308.01999；DiaQ arXiv:2405.01250；Atlas arXiv:2408.09055；VQCSim arXiv:2607.11985 | 2023–2026 | GPU 态矢量、电路态稀疏性、层次化分区、批处理向量化（25.95×） |

**共同缺口**：MPS/TT 按 qubit 顺序做张量链，每次门作用都要相邻收缩与截断；随机 SVD
未把「门位落在行域还是列域」变成因子上的直接变换；此前稀疏态（DQ-Sparse、DiaQ）
只跳过低质量 tile，活跃 tile 内部仍是稠密 L 维向量。RAS 补的是这一层。

> 文献为领域公认工作的引用；本轮未逐篇重新抓取原文。所有新结论由本文证明 +
> 95 条数值断言独立保证，不依赖外部未核验表述。

---

## 2. 表示与核心思路

把 `2^n` 维态按低 `t` 位重排成矩阵：

\[
A \in \mathbb{C}^{L\times C},\quad A[k][c] = \psi[(k\ll t)\,|\,c],
\quad L\cdot C = 2^n,\ C = 2^t
\]

保留秩-`r` 分解 `A ≈ UΣV†`，其中 `U∈ℂ^{L×r}`、`V∈ℂ^{C×r}`、
`Σ=diag(σ₁≥…≥σ_r)`。

- **稳态内存** `r(L+C)` 个复数，而非 `LC`；10 qubit / t=6 / r=6 时
  `16×64=1024 → 6×(16+64)=480`，压缩 **2.13×**。
- 门演化 `O(r(L+C))`，读出 `O(r²(L+C))`（Gram 矩阵，不物化全态）。
- **与 DQ-Sparse 正交**：DQ-Sparse 裁列方向 tile，RAS 在秩方向压缩，两者可叠加。

---

## 3. 四条定理

### L1（Eckart–Young–Mirsky 的可计算形式）

设 `σ₁≥…≥σ_m` 为 `A` 的全部奇异值，`A_r` 为前 `r` 项，则
`‖A−A_r‖_F² = Σ_{j>r}σ_j²`，且在全部秩 ≤ r 矩阵中最小。定义
`δ = Σ_{j>r}σ_j² / ‖A‖_F²`，归一化纯态的 trace distance 满足

\[
D(\rho,\tilde\rho) \le 2\sqrt{\delta} + \delta \tag{L4}
\]

（与 DQ-Sparse / EBAT 同一界，δ 同量纲，可直接相加。）

### L2（同位域门秩不变）

门位 `q≥t` 只改行索引，等价于左乘酉 `G`：`A' = GA = (GU)ΣV†`；门位 `q<t` 只改列
索引，等价于右乘 `K`：`A' = AK = UΣ(K†V)†`。两者保持 `Σ` 与 `rank(A)=r` **严格不变**，
无需重分解。RY 对 `U` 的行与 `V†` 的列是同一实旋转；RZ 在列域时 `V` 乘 `conj(φ)`；
同位域 CNOT 只是 `U` 或 `V` 的索引置换。6 个同位域门连续作用的秩不变断言已通过。

### L3（跨位域 CNOT 秩上界）

control 与 target 分属行域/列域时，条件置换无法分解为独立的行列置换。写
`A' = P₁A + (P₂−P₁)ΠA`，则 `rank(A') ≤ rank(P₁A) + rank((P₂−P₁)ΠA) ≤ 2r`。
实现上物化一次、施加门、以 `2r` 为上限重新分解；两轮截断误差按三角不等式相加，
仍由 (L4) 给出可计算上界。

> 初版只重分解未施加门，产生「门被静默丢弃」的语义错误；测试用
> `diff_from_unchanged > 1e-6` 与 `diff_from_expected ≈ 0` 两条断言钉住。

### L4（误差可加与 parity）

多轮重分解 `δ₁,…,δ_m` ⇒ `D ≤ Σ_k(2√δ_k+δ_k)`。`ε=0` 或 `r≥min(L,C)` 时走
**exact 稠密分支**：不分解、不量化、不重归一化，门/读出/`to_dense()` 与 host
实现**逐位差 0**。

---

## 4. 算法

```
RAS-BUILD(ψ, t, r_max, ε):
  A ← reshape(ψ) as L×C
  if ε=0 or r_max≥min(L,C): return EXACT(ψ)          # L4 parity
  R ← A; σ,U,V ← []
  for j in 1..r_max:
      (u,σ_j,v) ← POWER-DEFLATE(R)                    # Halko 2011 风格
      if σ_j² ≤ ε²‖A‖²: break                        # 能量预算自适应
      R ← R − σ_j u v†
  sort by σ descending                                # 规范 SVD 形式
  δ ← (‖A‖² − Σσ²)/‖A‖²
  return (U,Σ,V, δ, bound=2√δ+δ)

RAS-GATE(g):
  if EXACT: apply dense gate
  elif q(g) 与 q_target 同域: 变换 U 或 V 的对应索引   # L2
  else: ψ ← to_dense(); apply dense CNOT; RAS-BUILD(ψ, 2r) # L3

RAS-READ(bits):                                       # 不物化全态
  G ← V†V; F ← U†U                                    # r×r Gram
  p1_j ← Σ_{k or c: bit set} Σ_{a,b} σ_aσ_b U_a[k]conj(U_b[k]) G[a][b]
```

**复杂度**：构建 `O(N·r·iters)`；稳态存储 `O(r(L+C))`；同位域门 `O(r(L+C))`；
读出 `O(r²(L+C))`。`r ≪ min(L,C)` 时相对稠密 `O(N)` 是量级下降。

---

## 5. 实测（2026-11-14）

```
g++ 16.2.0 -std=c++20 -O2 -Wall -Werror  → 零警告
lowrank_state_test.exe                    → 95 checks, 0 failures
  exact 分支：门序列 / 读出 / to_dense 逐位差 0
  RAS      ：rows=16 cols=64 rank=6/16, compress=2.13x
             delta=4.2034e-01 bound=1.7170e+00 measured=6.4833e-01（≤ bound）
  因子级读出 vs 物化稠密读出：maxerr = 8.882e-16
  L2      ：6 个同位域门后 rank 不变，refactor_count=0
  L3      ：跨位域 CNOT 触发 1 次重分解，态确实改变，误差在界内
  矩阵    ：36 组 (t × r × ε × seed) 误差全部 ≤ 报告上界
train_cli --lowrank-epsilon 0.01 --lowrank-rank 4：
  RAS rank=3, compress=20.08x, best_loss 0.8229257445 与默认完全一致
```

两处被证伪后修正的口径：幂迭代 + deflation 不保证 σ 降序，导致「尾部能量」无意义，
改为按 σ 规范重排；跨位域 CNOT 只重分解不施加门，已加入反例断言。

---

## 6. RAS 进入 QLM adjoint 热路径（2026-11-16）

定理 A（λ 的精确 2r 项分解）让整个伴随循环都能在因子上完成，无需近似 λ：

```
c(s) = Σ_j gz_j·sign_j(s) = a(k) + b(c)            （读出位按行/列域拆分）
λ = diag(a)·φ + φ·diag(b)
  = Σ_i σ_i (a∘u_i) v_i† + Σ_i σ_i u_i (b∘v_i)†     （恰好 2r 项，精确）
```

配套 `runtime/include/qlm/RasAdjoint.hpp`（纯新增）：

- 梯度点积用 Gram 型小矩阵，全程复数累加，末端按 RZ 取 Im / RY 取 Re；
- 门演化与逆门**复用** `LowRankState::apply_{ry,rz,cnot}`，避免重复实现不一致；
- 同位域门秩不变（L2），跨位域 CNOT 重分解（L3），误差按 L4 累计；
- `StateBackend::Ras` 成为第三态后端，与 DQ-Sparse 共用
  `DeviceAdjointSparseBatchPOD` 契约；`--state-backend ras
  [--lowrank-epsilon E --lowrank-rank R]`；Auto 在 n≥20 时选 RAS，n≤18 仍选
  DQ-Sparse 或稠密（parity 基线）。

**验证**（WSL Ubuntu + MinGW g++ 16.2.0，`-Wall -Werror` 零警告）：

```
ras_adjoint_test.cpp                89 checks / 0 failures
  A1 exact（ε=0）与稠密 host 逐位一致（含跨位域 CNOT）
  A5 同位域 corr 0.9999；跨位域 corr 0.9997~0.9998（loss 偏差 ≤1.4e-9）
  A3 λ 秩 ≤ 2·rank；纯同位域电路 refactor_count=0
train_cli --state-backend ras：loss 0.8229257445（与 auto/dense/sparse0 一致）
train_cli --state-backend ras --lowrank-epsilon 0.01 --lowrank-rank 4：
  loss 0.8438652509，rank=3，低秩近似路径真实生效
state_backend_regression            209 checks / 0 failures（含 RAS 分支）
WSL 九套独立断言总计                582 checks / 0 failures
```

**落地中证伪并修正的口径**：梯度点积中途 `.real()` 丢虚部（RZ 的 Im 无意义，
相关性 −0.69）；RY 两项配对方向写反（相关性 −1.0）；跨位域重分解把 `max_rank`
提到 `min(L,C)` 触发 exact 分支导致空因子（loss 偏差 1e6）；`set_factors` 未设
`max_rank_` 使 λ 被压到秩 1；两处测试夹具错误（「纯同域」电路实际跨域、
用高秩随机态测低秩压缩）。全部已修正并由断言钉住。

---

## 7. 边界

- QLM adjoint 的 **CUDA device 热路径**仍用 tile 紧凑布局；RAS 走 host 因子级实现。
  搬上 device 需要 Kokkos 上的因子级 kernel，是下一步工作。
- 幂迭代是随机化近似，σ 不是严格最优 SVD；误差界对**实测** trace distance 依然成立，
  但压缩质量不如全 SVD。
- 跨位域 CNOT 重分解要物化一次 `O(Nr)`，深电路中跨位域门多时会退化；可用门重排
  （对易合并）减少跨位域次数。
- Linux io_uring 的 `IORING_OP_{ACCEPT,RECV,SEND}` 在本机（Windows）未实测；
  Windows IOCP 路径 18 条 overlapped 断言 + 37 条两节点断言全过。
