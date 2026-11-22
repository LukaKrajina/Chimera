# A2L：自研高并发基础层

> v1.2 · 2026-11-14 · 配套 `EVALUATION.md`、`sparse-amplitude-theory.md`、`lowrank-amplitude-theory.md`
> 实现：`A2L.hpp`、`A2LIntegration.hpp`、`A2LNet.hpp`、`A2LNetIo.hpp`、`A2LCollective.hpp`
> 测试：`tests_a2l/` 四套共 **118 checks / 0 failures**（`a2l_test` 29、`a2l_net_test` 34、
> `a2l_netio_test` 18、`a2l_collective_test` 37）

***

## 0. 文献与验证边界

验证：

- **已在本机验证**：C++20 `jthread` / `atomic` / `latch` / `barrier` / coroutines
  （g++ 16.2.0 `-std=c++20 -Wall -Werror` 编译通过；`Capabilities::has_coroutine` 用特性宏判定）。
- **未核验**：P2300 `std::execution` 定稿状态、C++26/29 内容、Tokio/Trio 原文、
  io\_uring / IOCP / epoll 的 API 细节（v1.1 起已改为真实系统 API，见 §7）。
- **已核验可直接引用**：arXiv:1803.10122、1705.05363、2406.09787、2610.27921、
  2308.01999、2408.09055、2405.01250、2101.02138、2105.14377；Nature 2024
  PMID 39169245；PNAS 2012 PMC3386878。

实现基线：纯 C++20/23（clang-cl 23.1.4 + MSVC 14.51 与 g++ 16.2.0 双验证），
C++29 仅作前瞻，不引入 Rust 运行时依赖。`A2L.hpp` 对每个 C++ 特性用 `__cpp_*` 宏做
可判定探测——「没有这个东西」必须是可判定的 false，而不是静默给垃圾值。

***

## 1. 两层定位

| 层     | A2L 组件                                                                                               | 对标思想                                          |
| ----- | ---------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| 语言模型层 | `Sender/Receiver`、`StructuredScope`、`Strand`                                                         | P2300 senders/receivers；Tokio/Trio 结构化并发与串行域  |
| 工程吞吐层 | `ThreadPool`、`MpmcQueue`、`CoopBudget`、`ShardMap`、`EpochReclaimer`、`Reactor`、`DistributedCoordinator` | work-stealing、协作预算、分片锁、epoch 回收、IO 多路复用、分布式分片 |

***

## 2. 自研创新结构（11 个）

| #  | 结构                       | 创新点                                                     |
| -- | ------------------------ | ------------------------------------------------------- |
| 1  | `CoopBudget`             | 每任务固定操作预算，耗尽强制 yield，防单任务饿死同 worker                     |
| 2  | `MpmcQueue<T>`           | bounded 无锁队列，slot 序号按 Vyukov 初始化为 `i`（初始化为 0 会误判「满」）    |
| 3  | `ThreadPool`             | 注入队列 + 本地 deque + 三级降级：注入满→fallback→绝不丢任务               |
| 4  | `Strand`                 | 原子 flag + 待办队列实现「逻辑串行、物理并行」；200 任务严格按序无重叠               |
| 5  | `ShardMap<K,V>`          | 16 分片独立锁，把 daemon 全局 MMI 表锁粒度从 1 降到 16                  |
| 6  | `EpochReclaimer`         | epoch 登记/注销 + 安全线回收（hazard pointer 轻量替代）                |
| 7  | `Reactor`                | IOCP/io\_uring/epoll 统一为「就绪事件 + 回调」，无后端时轮询回退            |
| 8  | `Sender<T>`              | `just/then/via` 最小可组合子集，可平滑映射到 C++26 `std::execution`   |
| 9  | `StructuredScope`        | 作用域析构保证全部子任务完成（RAII 结构化并发）                              |
| 10 | `DistributedCoordinator` | 分片归属 + epoch 租约 + 原子 checkpoint，零网络库依赖                  |
| 11 | `A2LIntegration::Hub`    | 六目标共享进程级资源池 + `parallel_rows` + 原子事件计数 + 可核对 `report()` |

***

## 3. 六个 C++ 执行程序及 OpenButler 的接入结果

| 目标             | 文件                                    | 深度 | 改动                                                               | 验证                               |
| -------------- | ------------------------------------- | -- | ---------------------------------------------------------------- | -------------------------------- |
| runtime daemon | `runtime/src/main.cpp`                | 深度 | 全局 map+mutex → `a2l::ShardMap`(16 分片) + `atomic<int>`；11 处协议路径全改 | 编译通过；MMI 实调 10/10 无回归            |
| train\_cli     | `runtime/tools/train_cli.cpp`         | 深度 | `ThreadPool` 并行 4 分块 IO 预检；DQ-Sparse 策略评估；新增 CLI 参数与元数据键         | `best_loss=0.7348113519` 与基线完全一致 |
| Transmitter    | `runtime/include/qml/Transmitter.cpp` | 接入 | `A2L_TOUCH` 接入共享资源池                                              | 目标编译通过                           |
| runtime\_api   | `runtime/src/runtime_api.cpp`         | 接入 | 入口探针                                                             | `rvdl_rt` 编译通过                   |
| RSP 主程序        | `RSP/src/main.cpp`                    | 深度 | `make_sphere` 双重串行循环 → `parallel_rows` 按行并行                      | `rvdlRSP` 编译通过                   |
| RSP 仿真宿主       | `RSP/gui/src/simulation_host.cpp`     | 中度 | 并行资源路径预检，保持原依赖顺序                                                 | `rvdlRSP_gui/sim` 编译通过           |
| OpenButler     | `packages/desktop/native/shell.cpp`   | 中度 | `A2L_TOUCH` + mmi/data/icons 并行预检                                | `desktop:build` 通过               |

`Transmitter.cpp`（96 KB）与 `runtime_api.cpp`（41 KB）只做**资源池接入与探针**，
未重写全部控制流：不改协议帧、MMI 命令字、`.rvdlm` 格式与烧录游标语义。

***

## 4. 验证结果（2026-11-11）

| 项              | 结果                                                     |
| -------------- | ------------------------------------------------------ |
| `A2L.hpp` 独立编译 | `g++ 16.2.0 -std=c++20 -O2 -Wall -Werror -pthread` 零警告 |
| `a2l_test`     | 29 checks / 0 failures（覆盖 11 个结构）                      |
| 并行 tile 领取     | 8 线程领取 1024 tile 无重复无遗漏                                |
| Strand         | 200 任务严格按序、无并发重叠                                       |
| ShardMap       | 8 线程写 4000 键全部可读                                       |
| Ravendrel 全量目标 | 9 个目标 ALL TARGETS OK                                   |
| OpenButler     | `desktop:build` 成功（shell.cpp、app.rvdli、selftest.rvdli） |
| daemon 协议回归    | `LOAD_MMI` + `MMI_INVOKE` 10/10 数值一致                   |
| 训练 parity      | 接入前后 `best_loss` 完全一致（0.7348113519）                    |

两处实测发现并修复的真实缺陷：`MpmcQueue` slot 序号未初始化导致并发 push 失败；
`ThreadPool::submit` 注入队列满时把已 move 的空 `std::function` 放入 fallback，
触发 `bad_function_call`。此外 `EpochReclaimer` 退休 epoch 取当前 global 导致延迟
回收失效，改为新 epoch。三者均已由测试钉住。

***

## 5. 未完成 / 下一步（诚实边界）

1. Transmitter / runtime\_api 全量并发化：需逐函数依赖分析、进度回调原子化、GUI 与训练线程解耦。
2. CR-1..8 扩展性指标（`EVALUATION.md` §2.4）尚无实测基线，需 `ces-concurrency` 压测套件。
3. C++26/29 定稿后把 `Sender::via` 映射到 `std::execution::on`，并评估标准 hazard pointer。
4. 文献逐篇核验待网络检索恢复后补 DOI/摘要。

***

## 6. 与既有系统的不变式

- MMI 命令字（LOAD\_MMI / MMI\_INVOKE / MMI\_UNLOAD / GET\_SNAPSHOT 等）零改动；
- 协议帧、`.rvdlm` 格式、烧录 `cursor.json` 语义零改动；
- QLM 训练数值、BAT parity（1e-16）、QCF 41 断言、稀疏 31 断言全部保持；
- 新增能力默认不改变行为：`A2L_TOUCH` 只登记计数，稀疏后端默认 Dense；
- 现有测试门槛不降低（见 `EVALUATION.md` §6）。

***

## 7. v1.2：真实完成 IO + collective 层（2026-11-14）

此前「IOCP/io\_uring 只是抽象」的说法已被推翻：

| 文件                        | 实际能力                                                                                                                                                                     |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `utils/A2LNet.hpp`        | Windows `CreateIoCompletionPort/GetQueuedCompletionStatusEx`；Linux 原始 `io_uring_setup` + mmap SQ/CQ + `IORING_OP_POLL_ADD`；epoll/select 回退；帧化 TCP 节点、租约、心跳、checkpoint 广播 |
| `utils/A2LNetIo.hpp`      | 完成驱动全路径：`AcceptEx`、`WSARecv`、`WSASend` + OVERLAPPED；Linux `IORING_OP_{ACCEPT,RECV,SEND}`；半包/粘包/畸形帧组装；`DistributedNodeCompletion` 无就绪探测                                   |
| `utils/A2LCollective.hpp` | `GradientAllReduce`（轮次桶、去重、陈旧轮拒绝、NaN 拒绝、仅用已收贡献的超时降级）、`ReconnectPolicy`（确定性抖动指数退避）、`DistributedTrainer` 适配器                                                               |

真实 loopback 验证：18 条 overlapped-IO 断言；37 条 collective 断言（两 IOCP 节点
交换 GRAD 帧并归约为 2.5/3.5/4.5）。Linux io\_uring 数据路径已实现但**未在本 Windows
主机执行**，声明而非声称已验证。`A2L.hpp` 的 `Capabilities::iocp_backend()` 恒 false
是「抽象层是否注入平台后端」的语义（由 `a2l_test` 钉住）；真实能力由
`a2l::net::NativeReactor::probe()` 报告。
