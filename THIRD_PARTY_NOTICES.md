# Third-Party Notices / 第三方组件与素材许可声明

本项目（Chimera）以 MIT 许可证发布，详见根目录 [LICENSE](./LICENSE)。

本文件列出本项目使用、参考或分发的第三方组件、代码与图片素材及其许可证，
并向它们致以诚挚感谢。

The Chimera project is distributed under the MIT License (see [LICENSE](./LICENSE)).
The following third-party components and assets are used under their own licenses.

---

## 1. Quark 项目（qk 语言与量子运行时）

| 项目 | 用途 | 许可证 | 版权 |
| --- | --- | --- | --- |
| [Quark](https://github.com/LukaKrajina/Quark) | Chimera 的全部组件以 **qk 语言** 书写，依赖 Quark 的量子/经典运行时、量子虚拟机（QVM）、TQNF 拓扑量子学习范式、`morph` 态射宏系统等全部特性 | [MIT License](https://github.com/LukaKrajina/Quark/blob/main/LICENSE) | Copyright (c) 2026 QuarkProject |

> **感谢**：衷心感谢 Quark 项目作者（Luka Krajina）与 QuarkProject 团队，
> 提供 qk 语言、量子虚拟机（QVM）、TQNF 拓扑量子学习范式与 `morph` 态射宏系统，
> 使 Chimera 的 256 个量子组件（25 现有 + 231 新增）得以用一门统一的语言实现，
> 并复用其全部量子与经典特性。没有 Quark，就没有 Chimera。

---

## 2. 图片素材（Pixabay）

本项目 `assets/` 目录中的示例图片（用于图像识别 / 感知场演示）来自
[Pixabay](https://pixabay.com/)，遵循 [Pixabay Content License](https://pixabay.com/service/license-summary/)。

该许可证允许**免费用于商业与非商业用途、无需署名**，但同时包含以下限制：
不得以原样（未修改）形式再分发或出售图片、不得将图片用于商标/标识/商业品牌、
不得暗示图片中的人物或品牌对本项目背书。

| 文件 | 图片 | 来源链接 | 许可证 |
| --- | --- | --- | --- |
| `assets/dog.png` | 小狗（Puppy Dog） | <https://pixabay.com/zh/photos/puppy-dog-animal-lovely-4337167/> | Pixabay Content License |
| `assets/cat.png` | 英国短毛猫（British Shorthair） | <https://pixabay.com/photos/british-shorthair-breed-cat-cat-8032816/> | Pixabay Content License |
| `assets/tree.png` | 相思树（Acacia Tree，纳米比亚埃托沙） | <https://pixabay.com/photos/acacia-nature-tree-africa-etosha-9565430/> | Pixabay Content License |
| `assets/car.png` | 豪华跑车（Luxury Sports Car） | <https://pixabay.com/photos/car-luxury-car-sports-car-auto-5852188/> | Pixabay Content License |

> **感谢**：感谢 Pixabay 平台与各位摄影师/创作者无偿提供这些高质量图片，
> 作为 Chimera 感知场（`encode_image` 真实图像像素振幅编码）与视觉识别演示的
> 示例素材。各图片的具体作者与详情请见其对应的 Pixabay 页面。

---

## 3. 参考论文与学术思想

Chimera 的架构设计参考了 arXiv / Nature / IEEE 等上的多篇论文（详见
[README](./README.md) 的「论文依据」章节），这些引用仅作为**灵感来源与理论依据**，
遵循学术引用的规范；本项目的实现代码为独立原创，不包含这些论文的代码或数据。

涉及的思想来源包括（但不限于）：量子认知（Busemeyer）、量子储备池计算（QRC）、
测量诱导相变（MIPT）、量子纠错征象提取（QEC）、预测编码 / 自由能（Friston）、
递归自我改进（Dream-RSI）、TQNF 拓扑量子学习范式（Quark 项目）等。

---

## 说明 Notes

- 上述第三方组件与素材的许可证文本以其随附的 `LICENSE` / `NOTICE` 文件为准；
  本文件仅作汇总说明。
- 使用、分发或再分发本项目时，请一并保留各第三方组件与素材的版权与许可声明。
