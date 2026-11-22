# Changelog

Chimera 架构的重要变更记录。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

**版本约定**：整数版本号表示「组件范式集」的断代变化；同一版本内的组件增删与参数
调整记为补丁级条目。兼容承诺：旧版组件签名与坐标布局保持可用；Jarvis（基于 Chimera
的 SI 大模型）依赖的 `chimera_morphs`、`perception`、`consciousness`、`decision`、
`dream`、`metacognition`、`chimera_moe` 导出签名跨版本升级保持不变。

***

## \[v3.0] - 2026-11-03

### Added

- **第 30 个范式集群：时间缩微（τ）**（`src/chimera_tau.rvdl`，6 组件）。
  数学来源：何庭波《A time scaling theory for multi-layer electronic systems》
  （ChinaXiv:202605.00224v2，韬定律 / τ scaling）的公式启发（诚实地感谢她），尝试并改造到量子 AI 层：
  - `tau_deadline` —— 分层复合截止期 τ = f(τ\_state, τ\_gate, τ\_measure, τ\_comm)
  - `tau_domain_alpha` —— 领域年度缩放因子（移动 1.3 / 自驾 1.5 / AI 10）
  - `tau_generational_step` / `tau_anneal_budget` —— 代际法则 τ\_{n+1} = τ\_n/α 与多代退火
  - `tau_fold_plan` —— LogicFolding 量子化：串行深度折进并行 tier、齿轮比
    g = 跨层边/层内边（阈值 3）、调度总代价 τ\_gate·D + τ\_comm·D·g
  - `tau_price_gate` —— 时间影子价格门控（净价值 v − λ·c，时间即货币的路由判决）
- **自包含演示** `examples/component-demos/chimera_tau_demo.rvdl`：六原语数值行为
  验证（含齿轮比阈值、影子价格转负关闭路由的判据）。
- **Runtime 侧支持**（Ravendrel runtime ≥ 0.10.0）：`qml/TauScale.hpp`（算法内核）+
  `TauAbi.hpp`（语言内建 `tau_alpha` / `tau_generational` / `tau_fold_depth` /
  `tau_gear_ratio` / `tau_route_cost` / `tau_route_price`），测试
  `tests/tau_scale_test.cpp`（55 项性质断言）。

### Changed

- 组件总数 256 → **262**；范式集群 29 → **30**。

### 兼容性

- 未修改任何既有组件的导出签名与坐标布局；Jarvis 模型（`jarvis_core.rvdl`、
  `jarvis_core_moe.rvdl`、`jarvis_vision.rvdl`）不改一行即可继续编译运行。
- 新增 `tau_*` 语言内建为纯新增符号，不占用既有名字空间。

***

## \[v2.0] - 2026（历史存档，补记）

- 从 25 个核心组件扩展到 **256 组件 / 29 范式集群**（耗散 / MIPT / 因果 / 几何 /
  拓扑记忆 / QRC / QEC / 意识扩展 / 语言 / 优化器 / 路由 / 生成 / 鲁棒 / 多体 /
  RL / 图网络 / 时序 / 信号 / 核方法 / 集成 / 元迁移 / 连续学习 / XAI / 神经符号 /
  QAOA / 动力系统 / 信息论 / 压缩 / 聚类）。
- `src/chimera_morphs.rvdl`：morph 态射宏库（22 个语义态射）。
- 元认知核（`chimera_metacognition.rvdl`）：认识错误（量子预测误差征象
  ε = 1 − |⟨预测|结果⟩|²）→ 反思学习。
- MoE 稀疏变体（`chimera_moe.rvdl`）：曲率玻尔兹曼软门控 + 对偶融合。

## \[v1.0] - 2026 前（历史存档，补记）

- 六大组件 + 一个闭环的量子混沌元认知核心：感知场、混沌意识核、演化世界、
  决策引擎、几何优化器、元认知核。
