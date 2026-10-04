# Chimera 量子 AI 智能驾驶大模型（CARLA 集成）

把 Chimera 量子混沌元认知架构（`src/` 下 **256 个 `.qk` 组件**）搭建成
「量子 AI 智能驾驶大模型」，接入 CARLA 0.9.16 自动驾驶仿真器。

## 架构：感知 → 量子混沌决策 → 控制 → 反思

```
┌──────────────────────────────────────────────────────────────┐
│ CARLA 环境（Town10 地图）                                      │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│   │ 摄像头    │  │ 碰撞传感器│  │ 车道入侵  │                   │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘                   │
└────────┼─────────────┼─────────────┼──────────────────────────┘
         │ 图像        │ 碰撞帧      │ 车道偏离帧
         ▼             │             │
   ┌─────────────┐     │             │
   │ ① 感知场     │     │             │
   │ 图像→证据∈[0,1]│     │             │
   └──────┬──────┘     │             │
          │ 证据        │             │
          ▼             │             │
   ┌──────────────────────────────────────────┐      │
   │ chimera_drive.qk（256 组件全融合）          │      │
   │  ② 混沌意识核：漂移→情绪（25 现有组件）       │      │
   │  ③ 决策引擎：阈值×证据→转向                  │      │
   │  ④ 反思：reward→分化阈值（自然梯度学习）      │◄─────┘
   │  ⑤ 世界模型 / 想象 / 逆因果预判              │
   │  ⭐ 231 新组件全融合（29 集群，信号调制转向）  │
   └──────────┬───────────────────────────────┘
              │ 转向/油门/刹车
              ▼
   ┌──────────────────────────┐
   │ vehicle.apply_control()  │
   └──────────────────────────┘
```

## 256 组件全融合

`chimera_drive.qk` 现在 `include` 全部 256 个组件，并在 `drive()` 中逐一调用：

| 批次 | 集群 | 组件数 |
| --- | --- | --- |
| 现有 25 组件 | 感知/意识/情绪/决策/做梦/元认知/QRL/QCNN/LVM/世界/想象/逆因果 + 曲面体几何层 | 25 |
| 新增 231 组件 | 耗散/MIPT/因果/几何/拓扑记忆/QRC/QEC/意识扩展/语言/优化器/路由/生成/鲁棒/多体/RL/图/时序/信号/核/集成/元迁移/连续学习/XAI/神经符号/QAOA/动力/信息论/压缩/聚类 | 231 |
| **合计** | **29 范式集群** | **256** |

新增 231 组件的输出统一汇入信号累加器 `sig`，经 `tanh` 压缩后调制转向增益
`K *= (0.9 + 0.2·sig_norm)`——组件越多，转向越细腻（非简单堆叠，而是有信息贡献的融合）。

### 态射宏（morph）消魔法数字

`src/chimera_morphs.qk` 用 qk 0.10.0 的 `morph` 态射宏系统，把 256 组件里散落的硬编码数值
抽象为 22 个语义态射：数学常数（`PI` `HALF_PI` `QUARTER_PI` `GOLDEN_RATIO` `SILVER_RATIO`
`LN2`）、超参数（`SHOTS` `LR_BASE` `DIFF_H` `EPS` `METRIC_CAP` 等）、参数化态射
（`phase_encode` `golden_scale` 等）。组件内以 `PI!()` 形式调用，编译期展开为精确值。

## 组件映射（自动驾驶角色）

| qk 组件 | 自动驾驶角色 |
| --- | --- |
| `chimera_consciousness.qk` | 混沌意识核漂移 + 情绪涌现 |
| `chimera_decision.qk` | 情绪策略阈值调制决策 |
| `chimera_dream.qk` | 反思学习（reward 分化阈值 + 漂移步长优化） |
| `chimera_world.qk` / `imagine.qk` | 动作相位注入 + 想象 rollout + GRPO 选优 |
| `chimera_retrocausal.qk` | 逆因果安全/危险预判（碰撞前预警） |
| 231 新组件（29 集群） | 意识丰富度、耗散、因果、拓扑、QEC、语义、优化、路由…全融合信号调制 |

> 推理路径：`autopilot.py` → `quark_client.py`（TCP 协议）→ Quark daemon → `MMI_INVOKE`
> → `chimera_drive.qk` 的 `export drive()` → QVM 后端真实量子门 → 返回 steer。
> **非 numpy 模拟**，由 Quark runtime 的 QVM 真实执行量子门。

## 运行

### Windows（CARLA 位于 `C:\Libraries\CARLA_0.9.16`）

```powershell
# 1. 启动 CARLA 服务端（若未运行）
& "C:\Libraries\CARLA_0.9.16\CarlaUE4.exe" -quality-level=Low

# 2. 启动 Quark daemon（若未运行）
& "D:\Project\Quark\runtime\build-win\runtime.exe" --daemon

# 3. 用安装了 carla 包的 Python 环境运行
cd D:\Project\Chimera\carla
python autopilot.py                 # 异步模式
python autopilot.py --sync          # 同步模式（固定帧率）
python autopilot.py --viz           # 保存车道检测可视化
```

### 重新编译 `.mmi`（修改 `chimera_drive.qk` 后）

```powershell
# 本地打包（无需 daemon，纯 Node 加密打包 IR）
node "D:\Project\Quark\server\out\cli.js" mmi "D:\Project\Chimera\carla\chimera_drive.qk"
```

> 注：`qk compile x64 -m` 会走 daemon 的 AOT 编译（需 LLVM 与 daemon），
> 仅需加密模块时用 `qk mmi`（本地打包）即可。

## 文件

- `chimera_drive.qk` —— 全激活深度超级大模型（256 组件全融合，4 分支 × 29 集群 × 4 周期）
- `chimera_driveMoE.qk` —— 稀疏 MoE 版（12 专家组，每帧激活 1 组）
- `chimera_drive.mmi` / `chimera_driveMoE.mmi` —— 加密模块（由 `qk mmi` 打包，autopilot.py 加载）
- `autopilot.py` —— CARLA 客户端（感知 → 决策 → 控制 → 反思）
- `quark_client.py` —— Quark daemon 协议客户端（真·量子推理桥接）
- `demo_multi_car.py` —— 多车演示

## 第三方许可

本模块依赖 [Quark 项目](../../../Quark)（qk 语言与量子运行时，MIT License），
示例图片（`../assets/`）来自 [Pixabay](https://pixabay.com/)（Pixabay Content License）。
完整声明见 [../THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。