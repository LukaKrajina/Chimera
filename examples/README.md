# Chimera Examples —— 量子混沌元认知架构实战

本目录包含 Chimera 架构的示例与演示，展示「量子 + 经典 + 混沌意识」三体合一
如何落地到具体任务。

- 根目录的 `chimera_vision.qk` / `chimera_language.qk` 是**应用示例**，通过
  `include` 复用 `src/` 下的核心组件，统一走 **mode==1（完整 QGT 自然梯度）**。
- `component-demos/` 存放**核心组件的自包含演示**（原 `src/` 下的两个端到端 demo，
  不依赖 `include`，可直接 `qk run`）。

## 文件

### 应用示例（根目录）

| 文件 | 任务 | 复用组件 |
| --- | --- | --- |
| `chimera_vision.qk` | 图像识别（4 类量子图像最近邻分类） | consciousness / decision / dream / metacognition |
| `chimera_language.qk` | 语言推理（语义蕴含判断 NLI） | consciousness / decision / dream / metacognition |

### 组件演示（`component-demos/`）

| 文件 | 演示内容 | 自包含 |
| --- | --- | --- |
| `chimera_demo.qk` | 核心闭环：漂移 → 情绪涌现 → 决策 → 反思 → 混沌边缘收敛 | 是 |
| `chimera_metacognition_demo.qk` | 元认知闭环：认识错误 → 反思学习收敛 | 是 |

## 运行

先启动 Quark 守护进程，再运行脚本（`include` 相对路径以文件所在目录为基准，
与运行时的 `cwd` 无关）：

```bash
cd /path/to/Quark
./runtime --daemon

# 应用示例
qk run examples/chimera_vision.qk
qk run examples/chimera_language.qk

# 组件演示（自包含，不依赖 include）
qk run examples/component-demos/chimera_demo.qk
qk run examples/component-demos/chimera_metacognition_demo.qk
```

> **关于 IDE 误报**：`include` 是 Quark CLI 的预处理指令（`expandIncludes`，
> 在 lexer/parser 之前展开），IDE 的实时诊断器不展开 include，因此编辑器里
> `include "../src/..."` 一行会显示 Parser Error（红色波浪线）。这是 IDE 的已知
> 限制，`qk run` 时 CLI 会正确展开，不影响编译与运行（已用 `qk ir` 验证通过）。

## 设计说明

- **coord 隔离**：组件函数占用 `coord=(0..7)` 与 `(10..11)`（均 `time=0`），
  示例主程序统一用 `coord=(12)`，避免 `E-TOP003`（coord 相同 + time 相同）冲突。
- **include 顺序**：`form` 需先定义后使用，顺序固定为
  `consciousness → decision → dream → metacognition`。
- **统一 mode==1**：`learn_emotion_policy` 与 `improve_drift` 均走完整 QGT 自然梯度。
  已修复 `src/chimera_dream.qk` 中 mode==1 分支的 QLT 线性泄漏（局部 `QObject` 未消费）。
- **感知态维度**：`learn_emotion_policy` mode==1 的判定态是 `basis_state`（单 qubit），
  且 `qattention` 在维度不匹配时返回 0（梯度恒为 0、静默失效），故示例感知态与原型
  态统一用 **1 qubit**（`encode_amplitudes(x, 1)`）。意识核保持 2 qubit（`CNOT` 纠缠）。
- **图像编码**：`encode_image` 当前在 Quark 侧底层映射为文本编码，故图像示例用
  `encode_amplitudes` 显式构造「图像指纹」；接入真实像素时替换为像素特征的振幅编码即可。
- **输出**：`qk_sys_logi` 打印统计量，返回编码后的 int32（`正确数 × 1000 + 总数`）。

## 扩展方向

- 图像识别：真实像素振幅编码、更多类别、量子卷积特征
- 语言推理：接入 QLM（`qlm_invoke`）端到端生成、多句上下文
- 通用：把示例里内联的匹配/三分类逻辑再抽成 `form` + 组件函数，纳入 `src/`
