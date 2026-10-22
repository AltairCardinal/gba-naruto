# MP2K note allocator 字节闭合（2026-08-29）

## 结论

`rom-mp2k-note-allocator-v1` 已完成 TDD、canonical artifact、独立 verifier、coverage
接入与 formal proof。它只把四段、562 个此前 unknown 的 ROM 字节分类为 550-byte
bounded Thumb code、8-byte instruction-consumed literals 与 4-byte
initializer-consumed Thumb entry pointer。canonical coverage 从
6,123,937 classified / 167,519 unknown 提升到 6,124,499 / 166,957；净减少
562 unknown bytes。

本成果是静态结构闭包，不声明自然运行时可达、全局 caller/code/indirect/computed
producer 或 RAM writer 分母、literal target 业务语义、音频行为、编辑、写回、重定位、
free/allocatable space 或完整 m4a runtime。

## 可复用任务模式

输入是哈希固定的 ROM、precoverage、既有 MPlayMain/M4A owner、固定 entry/call
provenance 与候选根。主要操作是：

1. 用 target-limited raw scanner 重建 Thumb BL/B、ARM B/BL、u32 entry 与 Thumb-pointer
   producer 分母；
2. 用独立 Thumb decoder 重建 bounded CFG、block、internal/external edge、return 与
   frontier；
3. 从 PC-relative load 逐项重建实际消费的 literal word；
4. 将唯一 entry pointer 绑定到 initializer writer、真实 consumer 与固定命令域；
5. 把 current-unknown promotion 与既有 owner provenance 分开，并对相邻排除范围失败关闭；
6. 由独立 verifier 从原始 ROM 重算，不导入 exporter 的结果充当证明。

适用边界是 producer、entry pointer、writer/consumer/domain、完整 CFG 与 literal
分母均能冻结且 frontier 为零的小型静态工作包。若存在动态 RAM 目标、computed producer、
开放 frontier 或业务语义歧义，必须升级为开放式分析并停止字节晋升。

## 精确 promotion 与排除范围

| 类别 | ROM 范围 | 字节 | SHA-256 |
| --- | --- | ---: | --- |
| bounded Thumb code | `[0x09A6D8,0x09A708)` | 48 | `04988bf8e911a12b477d9aafa24342b68e83960a06796e555869cc67b24bd4d2` |
| bounded Thumb code | `[0x09A708,0x09A8FE)` | 502 | `4c78dfb62e2d92b0b0ed96c8d05e86d3d2867a1bb2a76c82818a672f380eee2e` |
| consumed literals | `[0x09A900,0x09A908)` | 8 | `aea41d042f130b46329f8b5a5fdb976816ec280b367dc424f28bc624072867c1` |
| initializer-consumed entry pointer | `[0x09AF24,0x09AF28)` | 4 | `ee8951cbf1e4a1f69fce481a4537a84678e2615bc7e3f175ff69a97044ab7016` |

总计 562 bytes；packed SHA-256：
`3c3a1dab618964db40570b65c28ae08500a30392c65c25d870291ee5abb1587c`；
union range-vector SHA-256：
`bd9139f26305fea7813e7daf944d6a6e131861b31c3c98065b5e7d13bf65c88b`。

以下四段合计 68 bytes 仍是 unknown：

- `[0x09A6D2,0x09A6D8)`：6 bytes；
- `[0x09A8FE,0x09A900)`：2 bytes；
- `[0x09AEF4,0x09AF24)`：48 bytes；
- `[0x09AF28,0x09AF34)`：12 bytes。

这些范围不能仅凭邻接、零值、对齐或音频包络分类。

## CFG、producer 与 consumer 分母

- 269 条 Thumb instruction；
- 550 个 code bytes；
- 66 个 basic block；
- 99 条 internal edge、5 条 external edge；
- 2 个结构化 return；
- 0 个 unresolved frontier；
- entry-pointer consumer 固定接受 0..48，共 49 个值；
- 全局 RAM writer denominator 未闭合，因此只声明已固定的 initializer writer/consumer
  关系，不声明所有 RAM writer。

独立 verifier 对原始 ROM、producer 编码、root、branch target、literal ref、pointer
slot、consumer/domain、range hash、precoverage 身份和既有 owner 均失败关闭。单字节
mutation、错误 gap、partial owner、重复 claim、身份漂移和非对象 JSON 均有定向测试。

## Artifact 与实现身份

canonical artifact：`artifacts/rom-mp2k-note-allocator-v1/`

- manifest：18,914 bytes，SHA-256
  `a2f61cb3596c8e48294ba07c710a2681bbe8ca8173c6d9288beccd5dd3e1cf8a`；
- payload：381,177 bytes，SHA-256
  `a4ccf706d2c8db658b6fa402d13155c73d15e84c197f9da4e8975759a14b0fa6`；
- binary：562 bytes，SHA-256
  `3c3a1dab618964db40570b65c28ae08500a30392c65c25d870291ee5abb1587c`。

immutable precoverage：`artifacts/rom-mp2k-note-allocator-precoverage-v1/`

- manifest SHA-256：
  `21c3448891c0afaffa9ebe326f59e58d418b99bacbbea8542a63b45c47503861`；
- gzip coverage SHA-256：
  `6134b9c0e52242e47d5cb8c1c291924f41287ccfc67b97fea696b9b513793921`；
- 解压后的 baseline coverage SHA-256：
  `ab315087593f23bfbcc96c66ac99b8bfd002e5c29cd462088dda343139f9ac27`。

实现身份：

- exporter：`a54f665a7f713f5754cc25a1bc2e2c5761179460a64f44e2cd276a731a9c235a`；
- independent verifier：`177d1fb694b01f5938d6169438cd454db0ff7a1e826cf101b32630ffc51d9716`；
- exporter tests：`0af69ec928c352f41c5e2daf0db1870f2980333d9767f2e207acb22126af64ac`；
- verifier tests：`2e30e8af036a1157a9e0edaf541ee1724aebf5c23b784fa5a675daf5d47e76c6`。

## TDD 与验收证据

RED、GREEN、hardening、coverage 与 proof 日志均保存在
`build/experiments/active/mp2k-note-allocator-acceptance-20260829/`，未覆盖原始运行。

- exporter/verifier 全集：24/24 通过，325.730 秒；日志 SHA-256
  `5cc228099e0ec363173f1ac1e543e618aa5b1757ebd23bae2ad19a6518273f61`，
  guard SHA-256
  `dc2779abf08db55b0ddff95ecd5f73166585670049a8e1e3f6e90a2c0ff96584`，
  峰值 RSS 930.05859375 MiB，非降级；
- acceptance report 与 accepted verifier report 内容一致，SHA-256
  `6aa3208e8d553d60983093aa25aa0428609adce12fddfc9df1994b986f750124`；
- coverage rebuild 后 SHA-256
  `3926d1cd6e09c8b45b85cb33d0b2f77d83578ec71c17d61fa1282d863f220735`，
  23,135,080 bytes；summary 为 6,124,499 classified、166,957 unknown、14,503 claims、
  16,614 segments；
- proof spec SHA-256
  `3fc2e64c558f7a1eb877cbe50ad2ea967006b5f30d23a45342628b608fbd11c0`；
- static report SHA-256
  `dbca8d4627c7641a0e70eb169fe35f13bf62c6e447d7db73701dd1ae9c6e9a9c`；
- formal report / guard SHA-256
  `46b4b0c9b80b7ef2d8eaff9fb0572370c315d47baa05290d4fb2da327a95e7ce` /
  `7a69b38343c8a1b68392368cd0b130d6817b888fa3b3c90cf445a7d05e54adaa`。

formal audit 共执行 86 个唯一结构化 verifier：76 个 ROM-byte contract 与 10 个 bank
contract 全部 `exit_code=0`、`contract_ok=true`。报告保持 `complete=false`、
`claim_status=incomplete`、175 blockers 是正确结果，因为仍有 166,957 unknown bytes、
22 个有效 bank 的全记录/字段穷尽和 7 个最终 gate 未完成。

## 浪费与故障归因

首轮 coverage rebuild 使用 15 分钟 idle timeout，被守卫以 exit 124 停止；峰值
434.015625 MiB，canonical coverage 未被修改。第二轮只调整受守卫 idle 上限，19 分
36 秒后成功，峰值 426.26171875 MiB。这是静态全覆盖任务长时间无 stdout 导致的
基础设施参数不足，不是 ROM、算法或模型能力 blocker。首轮约 15 分钟计入无用耗时，
证据为 `guard-coverage-rebuild-r1.json`；后续同类 full coverage 至少使用 1,500 秒 idle
上限。

另有一次 proof RED 命令使用了错误测试类名，约 0.3 秒即失败；随后以正确测试路径获得
有效 RED。该次只计命令编排浪费，不计产品失败。

## 下一工作包

下一候选是 MP2K 18-entry dispatcher 的 102-byte current-unknown additive delta：

- `[0x09BCB4,0x09BCE2)`：46-byte code；
- `[0x09BD24,0x09BD30)`：12-byte table tail；
- `[0x09BDC4,0x09BDEC)`：40-byte handler code；
- `[0x09BDFC,0x09BE00)`：4-byte consumed literal。

`[0x09BCE2,0x09BCE4)` 与 `[0x09BDFA,0x09BDFC)` 必须保持 unknown。完整表的
前 15 项已有 accepted owner；历史 `similar-table-candidate-027` 整体 rejected 状态
不允许修改。实施前必须由本体从 ROM 独立重建唯一 initializer pointer、0..17 域、
18 个有序 target、bounded worklist 与外部 opaque call，再决定是否冻结为 Luna max
短包。
