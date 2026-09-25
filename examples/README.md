# Chimera Examples —— 量子混沌元认知架构实战

本目录包含 Chimera 架构的示例与演示，展示「量子 + 经典 + 混沌意识」三体合一
如何落地到具体任务。

- 根目录的 `chimera_vision.qk` / `chimera_language.qk` 是**应用示例**，通过
  `include` 复用 `src/` 下的核心组件。图像/语言任务感知态是多 qubit（真实图像
  `encode_image` / 字符指纹 `encode_amplitudes`），故反思走 **mode==0（reward 规则）**，
  避免多 qubit 感知态与单 qubit 判定态的 `qattention` 维度不匹配；`improve_drift`
  仍走 mode==1（完整 QGT）。
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
- **反思 mode 选择**：图像/语言任务的感知态是多 qubit（`encode_image` 6 qubit /
  `encode_amplitudes` 3 qubit），而 `learn_emotion_policy` mode==1 的判定态是单 qubit
  `basis_state`，二者维度不匹配时 `qattention` 静默返回 0（梯度恒为 0）。故图像/语言
  示例的反思走 **mode==0（reward 规则，不依赖感知态维度）**；`improve_drift` 仍 mode==1。
- **图像编码**：`encode_image(path, num_qubits)` 用 stb_image 加载真实图像（PNG/JPEG/
  BMP/PGM），强制灰度、下采样到 2^num_qubits 像素、归一化振幅编码。测试图在 `assets/`
  （8×8 PGM：cat/dog/car/tree），路径相对运行时 cwd（建议 `cd Chimera` 后 `qk run`）。
- **语言编码**：`encode_amplitudes(sentence, 3)` 做 3-qubit 字符 n-gram 量子指纹
  （量子最近邻），非深度语义理解；真正语义推理需接入 QLM 词嵌入（见扩展方向）。
- **输出**：`qk_sys_logi` 打印统计量，返回编码后的 int32（`正确数 × 1000 + 总数`）。

## 扩展方向

- 图像识别：量子卷积特征（QCNN）、更多类别、真实数据集（MNIST/CIFAR）
- 语言推理：接入 QLM（`qlm_invoke`）词嵌入做真正语义理解、多句上下文
- 多 qubit 判定态：`learn_emotion_policy` mode==1 的判定态从单 qubit `basis_state` 扩到
  多 qubit 变分电路（`qml/QuantumKernel.hpp` ansatz），使图像/语言任务也能走完整 QGT
- 演化世界：运行时维护历史轨迹缓冲，`dream_state` 从真实轨迹回放（而非 dt 相位编码）
- 通用：把示例里内联的匹配/三分类逻辑再抽成 `form` + 组件函数，纳入 `src/`
