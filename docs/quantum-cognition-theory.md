# QCF：量子认知场统一理论

> 2026-11-10 · 覆盖 2000–2026 文献 · 只读调研现有实现 · **不修改任何现有文件**
> 理论依据；实现见 `Ravendrel/runtime/include/qai/*.hpp` 与
> `Chimera/src/chimera_qge|qwm|qim|qdo.rvdl`（全部为新增文件）。

---

## 0. 现有能力盘点（只读调研）

| 方向 | 已有 | 完全缺失 |
| --- | --- | --- |
| 神经无死角延伸 | `chimera_continual.rvdl`、`chimera_reservoir.rvdl`、`QVM::allocate_qubits/prepare_amplitudes` | 无「覆盖缺口」度量、无结构增长触发判据、无「生成并测试新单元」 |
| 生成式世界模型 | `chimera_world.rvdl`、`chimera_generative.rvdl`、`chimera_imagine.rvdl` | 无显式轨迹缓冲/回放、动作序列固定、只返回末态、无反事实对照评估 |
| 内生动机 | `intrinsic_motivation`、`novelty_score`、`free_energy_minimizer`、`tau_price_gate` | `empowerment`/`information_gain` 全库 0 匹配；无函数把动机写回 reward；无 noisy-TV 防护 |
| 发育式自组织 | `chimera_continual.rvdl`、`chimera_mipt.rvdl`、阈值分化 | `prune/grow/spawn/stage/critical_period` 全库 0 匹配；结构不增长；组数编译期硬编码 |

可复用接缝：`qhal/IQuantumBackend.hpp`、`qlm::TrainOptions` 的 `std::function` hook、
`qlm::TrainProgress`、`LOAD_MMI` + `MMI_INVOKE`（≤4 数字参数）。新增 `CMD_*` 需改
`main.cpp`，故**不新增**命令字，用现有命令字等价接入。

---

## 1. 文献基础（2000–2026，已核验原文）

| 文献 | 年份 | 贡献 |
| --- | --- | --- |
| Weng et al., *Science*；Lungarella et al., developmental robotics | 2001–2003 | 发育式自组织：结构随经验由简入繁 |
| Schmidhuber, *Formal Theory of Creativity…* | 1990–2010 | 学习进展（compression progress）作为内在奖励 |
| Klyubin et al., empowerment；Friston, active inference | 2005–2009 | 信息增益、期望自由能 |
| [World Models](https://arxiv.org/abs/1803.10122) | 2018 | VAE+RNN 潜空间，在自生成梦境里训练策略 |
| PlaNet / MuZero / DreamerV3 | 2019–2025 | 潜动力学想象规划 |
| [ICM](https://arxiv.org/abs/1705.05363) | 2017 | 预测误差作内在奖励；明确忽略不可控因素 |
| [Continual Backprop](https://arxiv.org/abs/2108.06325)；[*Loss of plasticity*, Nature 2024](https://pubmed.ncbi.nlm.nih.gov/39169245/) | 2022/2024 | 持续注入新单元维持可塑性；generate-and-test |
| [LNDP](https://arxiv.org/abs/2406.09787) | 2024 | 活动/奖励依赖的结构可塑性 |
| TD-MCL、developmental initialization、成年海马神经发生（Nature 2026） | 2026 | 时序发育、临界期、修剪而非单纯增长 |
| [Quantum-JEPA](https://arxiv.org/abs/2610.27921) | 2026-10 | 条件 Born 先验生成多模态未来 |
| [*Active inference and artificial reasoning*, Nat. Commun.](https://www.nature.com/articles/s41467-026-77209-5) | 2026 | 用期望自由能选择最大化结构信息的采样 |
| unitary 2-design / frame potential / Welch bound；[expressibility](https://arxiv.org/abs/2101.02138)；[DLA](https://arxiv.org/abs/2105.14377) | 2003–2026 | 用 frame potential 量化 ansatz 覆盖度 |

**共同缺口**：上述工作把四个方向当**四个独立机制**；经典侧用标量奖励/静态图结构，
量子侧（Quantum-JEPA）只做生成先验，没有把「覆盖缺口、生成误差、内在动机、发育
时钟」放进同一个可优化泛函，也没有在 **Hilbert 空间**上给出可计算的覆盖度量与误差界。

---

## 2. 统一对象与 QCF 自由能

设 `H=(ℂ²)^⊗n`，`d=2^n`，认知态 `ρ`（纯态 `|ψ⟩`），ansatz 可达集
`A_Θ = {U(θ)|s⟩ : θ∈Θ}`，观测 POVM `{M_o}`。

**定义 1（QCF 认知自由能）**

\[
\mathcal F[\rho;\Theta,t]
= \underbrace{\mathcal E_{\rm wm}(\rho)}_{\text{生成误差}}
+ T(t)\underbrace{\big[\mathcal C(\Theta)-S_{\rm L}(\rho)\big]}_{\text{覆盖缺口} - \text{熵}}
- \mu(t)\underbrace{\chi(\rho,\mathcal A)}_{\text{可控信息}}
+ \lambda_\tau c_\tau
\]

| 量 | 定义 | 复杂度 |
| --- | --- | --- |
| `E_wm` | `−log F(ρ_pred, ρ_obs)`，`F = \|⟨ψ\|φ⟩\|²` | `O(d)` |
| `C(Θ)` | `FP(A_Θ) − FP_Haar`，`FP = (1/m²)Σ_{ij}\|⟨ψ_i\|ψ_j⟩\|⁴`，`FP_Haar=2/(d(d+1))` | `O(m²d)` |
| `S_L(ρ)` | `1 − Tr ρ²`（线性熵） | `O(d²)`（纯态 0） |
| `χ` | Holevo 信息的二次近似 | `O(\|A\|d²)` |
| `c_τ` | `tau_fold_plan` 调度代价，与 `v−λc` 衔接 | 标量 |

用线性熵而非 von Neumann 熵是刻意的：二者单调一致，但 `S_L` 只需矩阵乘法，
避免 `O(d³)` 特征分解与 `log0` 数值问题。

**核心主张**：四个功能不是四个模块，而是 `F` 的**四个梯度方向**：

| 功能 | 更新方向 | 对应项 |
| --- | --- | --- |
| ① 神经无死角延伸 | `−∂F/∂Θ`：减小 `C` | 覆盖 |
| ② 生成式世界模型 | `−∂F/∂ρ`：减小 `E_wm` | 预测 |
| ③ 内生动机 | `+∂F/∂χ`：增大 `χ` | 探索 |
| ④ 发育式自组织 | `−∂F/∂t`：退火 `T, μ`，增/删结构 | 调度 |

### 定理 1（四向下降 / Lyapunov 单调性）

设 `F` 关于 `(ρ,Θ)` 是 `L`-smooth 且有下界 `F ≥ F_min = −λ_τ c_max`。若四步均以
步长 `η_k ∈ (0, 2/L)` 沿上表方向更新且 `T, μ ≥ 0`，则

\[
\mathcal F_{k+1}\le \mathcal F_k-\sum_{j=1}^{4}\eta_k^{(j)}\Big(1-\tfrac{L\eta_k^{(j)}}2\Big)\|g_k^{(j)}\|^2 ,
\qquad \lim_{k\to\infty}\|g_k\|=0.
\]

*证明*：对每个方向用下降引理求和；四步串行，`L` 由同一个 `F` 的 Hessian 上界控制；
telescoping 得 `Σ‖g_k‖² < ∞`。∎ 工程含义：每步输出 `delta_F ≤ 0` 断言，`F` 上升
即说明步长/退火越界。

---

## 3. ① 神经无死角延伸（QGE）

**定义 2（可计算盲区）**

\[
\Delta_\Theta = \operatorname{FP}(\mathcal A_\Theta)-\frac{2}{d(d+1)}\ \ge\ 0,
\qquad \bar\rho_\Theta=\frac1m\sum_i|\psi_i\rangle\langle\psi_i| .
\]

`Δ=0` 表示可达集已是 2-design（无死角）；`Δ>0` 即存在未被覆盖的子空间。与
barren-plateau 文献同源，但这里把 **FP 超出 Haar 的部分**用作**结构增长触发信号**。

### 定理 2（残差生成元延伸）

取生成元集合 `𝔤 = {σ_y^{(q)}, σ_z^{(q)}, CNOT}`，令
`G* = argmax_{G∈𝔤} ‖[G, ρ̄_Θ]‖_F`。若 `Δ_Θ > τ_g` 且 `‖[G*,ρ̄]‖_F > 0`，则以
`e^{−iεG*}` 增广 ansatz（`ε` 充分小）满足 `FP(A_{Θ+}) ≤ FP(A_Θ)`，且当 `G*` 不与
`ρ̄` 对易时严格不等。∎（`FP` 是 `U` 的四次多项式；沿 `e^{−iεG}` 的一阶导正比于
`Tr([G,ρ̄]·M)`；扩 qubit 时新维初始为 `|0⟩` 张量积，`FP` 重新归一化不增。）

**算法 QGE**

```
输入: 可达态采样 A (m 个), 阈值 τ_g, 单次最多新增 Δn 个 qubit
1  Δ ← frame_potential(A) − 2/(d(d+1))
2  if Δ ≤ τ_g: return NO_EXTENSION
3  G* ← argmax_G ‖[G, ρ̄_A]‖_F
4  若 ‖·‖=0 且 get_num_qubits()<get_max_qubits(): plan ← EXTEND_HILBERT(Δn)
   否则 plan ← APPEND_GENERATOR(G*)
5  返回 ExtensionPlan{new_qubits, generators, expected_Δ_reduction}
```

只调用 `IQuantumBackend::prepare_amplitudes/get_max_qubits`；既有门序列、θ 布局、
`.rvdlm` 格式不变。实现见 `qai/GapFreeGrowth.hpp`。

---

## 4. ② 生成式世界模型（QGWM）

补 `chimera_dream.rvdl:15` 自注的缺口：显式轨迹缓冲、可变动作序列、Born 采样、
反事实对照。

**定义 3（量子生成轨迹）**：`τ = (s_0, a_1…a_K)`，`s_{k+1} = U(a_k)s_k`；按 Born
规则采样 `o_k ~ Tr(M_o U(a_k)ρ_k U†)`；`TrajectoryBuffer` 存 `(ρ_k, a_k, o_k, F_k)`，
可回放与反事实重演。

### 定理 3（酉想象误差线性累积——量子相对经典的关键优势）

设真实转移酉 `U`、模型酉 `Û` 满足 `‖U−Û‖ ≤ ε_U`，读出/解码误差 `≤ ε_M`，则 `k` 步
想象的 Bures 距离

\[
D_B(\rho_k,\hat\rho_k)\ \le\ k\,\varepsilon_U+\varepsilon_M ,
\qquad
F(\rho_k,\hat\rho_k)\ \ge\ 1-\tfrac14(k\varepsilon_U+\varepsilon_M)^2 .
\]

*证明*：`U` 保 Bures 距离，归纳用三角不等式累加；`F = cos²(D_B/2)` 给下界。∎
经典自回归世界模型误差通常随 `k` 指数放大（Lipschitz 常数 >1），酉演化的等距性把
增长压成**线性**。推论：给定容错 `δ`，可安全想象 `k_max = ⌊(δ−ε_M)/ε_U⌋` 步，
与 `tau_deadline` 对齐。

**量子 ELBO**：

\[
\log p(o_{1:K}) \ge \sum_k \mathbb E_{q_k}[\log\operatorname{Tr}(M_{o_k}\rho_k)]
-\sum_k D(\rho_k\|\hat\rho_k),
\quad D(\rho\|\sigma)=\operatorname{Tr}\rho(\log\rho-\log\sigma).
\]

纯态时用 `−log F` 代替 `D`（单调一致、免特征分解），输出可计算 `elbo_lower_bound`；
生成采样用 `born_sample`。实现见 `qai/GenerativeWorldModel.hpp`。

---

## 5. ③ 内生动机（QIM）

**定义 4（量子内在奖励）**

\[
r_{\rm int}(a)=\beta\,\Delta S_{\rm L}(a)
+\gamma\,\Delta\chi(a)-\lambda_\tau c_\tau(a)-\zeta\,\hat\sigma^2_{\rm aleatoric}
\]

- `ΔS_L`：**新颖度**（Schmidhuber 学习进展 / Pathak 预测误差的量子版）
- `Δχ`：**赋能**的 Holevo 二次近似（Klyubin empowerment 的量子推广，上界 `log d_A`）
- `c_τ`：`tau_price_gate` 时间成本，避免「为了好奇无限想」
- `−ζσ̂²_aleatoric`：**noisy-TV 防护**，只奖励可减少的不确定性

### 定理 4（内生动机 ≡ 期望自由能下降）

生成模型精确、动作集有限时，令期望自由能
`G(a) = E_q[D(q(s'|o,a)‖q(s'))] − E_q[log p(o|a)]`，则 `r_int(a) ≤ −G(a) + const`，
两者在纯态酉极限同时取最大值；以 `r_int` 为奖励的策略改进满足

\[
V^{\pi'}(s)\ge V^{\pi}(s)+\frac{1}{1-\gamma_{\rm RL}}\min_a r_{\rm int}(a)
\quad(\text{当 }\min_a r_{\rm int}(a)\ge 0).
\]

∎（`−log p(o)` 由 `−log F` 上界控制，`D(q‖prior)` 由 `Δχ` 的纯度差控制，
`−λc_τ` 是 pragmatic 代价项。）

**补缺口**：Chimera 有 `intrinsic_motivation/novelty_score/free_energy_minimizer`，
但没有任何函数把动机写回 reward。QIM 提供 `write_back(base_reward)`，与外部奖励
（如 carla 的 `0.15/碰撞−1.0`）合成，并由 `TrainOptions::progress` 在线喂信号，
零侵入。实现见 `qai/IntrinsicMotivation.hpp`。

---

## 6. ④ 发育式自组织（QDO）

**定义 5（发育时钟与临界期）**

\[
T(t)=\frac{T_0}{1+t/t_c},\qquad
\mu(t)=\mu_0 e^{-t/t_\mu},\qquad
\text{Stage}(t)=\big(n_q(t),\,|\mathfrak g(t)|,\,T(t),\,\mu(t)\big).
\]

`T` 是覆盖缺口权重（早期大 → 鼓励结构探索），`μ` 是内生动机权重（后期衰减 →
从探索转利用），`t_c` 即**临界期**。三条结构规则：

1. **生长**：`Δ_Θ(t) > τ_g(t)` 触发 QGE 增广；
2. **修剪**：振幅 tile 质量 `< ε²` 时剪枝，丢弃 L2 质量 `δ`，界
   `‖ρ−PρP‖₁ ≤ 2√δ+δ`（与 EBAT 同构）；
3. **自组织**：局部 Hebbian/Oja 规则 `Δθ_j = η·Re⟨∂_{θ_j}ψ | r⟩`，`r` 为残差。

### 定理 5（收敛与谱隙）

设 QFI 在不变子空间上的最小特征值 `λ_min>0`、最大 `λ_max`。若 `0<η<2/λ_max`，则
局部规则使残差投影线性收敛：`‖P_inv r_k‖ ≤ (1−ηλ_min)^k ‖P_inv r_0‖`；结合定理 1，
发育过程在有限阶段内停于结构稳态（`Δ≤τ_g` 且 `‖g‖≤ε`）。∎

`t` 由 `on_epoch_start` 推进；`n_q` 增长只调 `allocate_qubits`；`init_weights` 扩展
θ 维度；既有 `p00..p63` 与编译期 MoE 组数不动。实现见 `qai/DevelopmentalSelfOrg.hpp`。

---

## 7. 与现有系统的接入（零改动）

| 层 | 新增文件 | 接入方式 |
| --- | --- | --- |
| Ravendrel 底层 | `qai/QCFField.hpp` + 4 个功能头 | header-only，仅 STL + `numqk` + `IQuantumBackend`；不链 Kokkos/LLVM/rvdl_rt |
| Ravendrel 验证 | `runtime/tests_qai/qai_cognition_test.cpp` | 独立 `g++ -std=c++20` 编译，不进 CMake |
| Chimera 语言层 | `src/chimera_q{ge,wm,im,do}.rvdl` | 纯新增；`rvdl mmi` 编译 `.rvdli`；经 `LOAD_MMI`(0x05)+`MMI_INVOKE`(0x06) 调用 |
| 现有文件 | **0 个被修改** | 不改 `main.cpp` enum/switch、`SandboxJIT.hpp` 白名单、`QM.hpp` 后端枚举、任何既有 `.rvdl` |

---

## 8. 可证伪的数值断言（测试逐个验证）

1. `FP(正交集)=1/m`、`FP(同一态)=1`、`FP_Haar=2/(d(d+1))`、`Δ≥0`；
2. QGE 增广后 `FP` 不增；`Δ≤τ_g` 时**不触发**结构改动；
3. 10 步四向更新 `F_{k+1} ≤ F_k + 1e-12`（定理 1）；
4. `fidelity_bound(k)` 随 `k` **线性**下降（定理 3），轨迹缓冲长度 `=K+1` 且可回放；
5. 新颖态 `r_int` > 重复态；纯噪声加入 aleatoric 估计后 `r_int` 被抑制；
6. `T(t)`、`μ(t)` 单调递减；剪枝误差 `≤ 2√δ+δ`；Hebbian 残差单调下降（定理 5）。

任何一条不成立，对应公式即被证伪——这是把「新理论」做成**可验证工程**的关键。

---

## 9. 实测结果（2026-11-10）

**C++ 权威实现**：`g++ 16.2.0 -std=c++20 -O2 -Wall -Werror` 零警告，
`qai_cognition_test.exe` → **41 checks / 0 failures**：

```
FP(正交完备集)=1/d · FP(同一态集合)=1 · FP_Haar=2/(d(d+1)) · Δ≥0
QGE: FP 0.17348843 → 0.13659102 (m 6→30)，Δ≤τ 时不改结构
F_10 = −0.75129703，10 步四向更新单调不增
轨迹缓冲长度 K+1，回放 fidelity=1，Bures 界等间隔差分相等
r_novel=0.525988 > r_repeat=0.477986；noisy-TV 抑制；reward 写回
prune δ=2.049e-13 bound=9.053e-07 actual=2.056e-13（误差落在界内）
```

**Chimera 语言层**：4 个新 `.rvdl` 由 `rvdl mmi`（v0.3.3）编译为 `.rvdli`，
导出 **5 / 6 / 6 / 7 = 24** 个函数；经 `LOAD_MMI` + `MMI_INVOKE` 实调 10 个关键
公式，**10/10 与解析值一致**：

```
qge_haar_bound(8)=0.027778      qge_coverage_gap(.125,8)=0.097222
qge_should_extend(.1,.02)=1     qwm_bures_bound(5,.02,.01)=0.11
qwm_fidelity_bound=0.996975     qim_reward(.2,.1,.5,0)=0.25
qim_noisy_tv_guard=0.06         qdo_temperature(3,20,1)=0.869565
qdo_prune_error_bound(.01)=0.21 qdo_safe_hebbian_lr(.1,1)=0.1
```

**两处被证伪后修正的口径**：定理 3 的线性性属于 **Bures 距离**，fidelity 下界对
`D_B` 是二次的（最初拿 fidelity 差分检验线性是错误口径）；`rvdl mmi` 需要显式
`export` 关键字，否则每模块只打包 1 个函数（已为 24 个函数补齐）。

**边界**：L3（持续学习 agent loop）未达成——四机制只在离线断言中验证，未接入动作、
反馈、回放、动机写回的闭环（见 `EVALUATION.md` §1）。

---

## 10. 新增文件清单（现有文件 0 修改）

| 类别 | 路径 |
| --- | --- |
| 理论 | `Chimera/docs/quantum-cognition-theory.md` |
| Ravendrel 底层（header-only，仅 STL） | `runtime/include/qai/QCFField.hpp`、`GapFreeGrowth.hpp`、`GenerativeWorldModel.hpp`、`IntrinsicMotivation.hpp`、`DevelopmentalSelfOrg.hpp` |
| Ravendrel 独立测试 | `runtime/tests_qai/qai_cognition_test.cpp` |
| Chimera 语言层 | `src/chimera_qge.rvdl`、`chimera_qwm.rvdl`、`chimera_qim.rvdl`、`chimera_qdo.rvdl` |
| 编译产物 | `D:/JarvisModel/qai/*.rvdli`（4 个，共 24 个 export） |

接入走现有 `LOAD_MMI`(0x05) + `MMI_INVOKE`(0x06) 命令字，`main.cpp` 的 enum/switch、
`SandboxJIT.hpp` 白名单、`QM.hpp` 后端枚举均未动。
