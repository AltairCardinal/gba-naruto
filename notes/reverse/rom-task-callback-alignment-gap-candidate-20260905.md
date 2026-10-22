# Task callback 邻接对齐候选（2026-09-05）

状态：仅候选，新增分类为 **0 bytes**。任务模式复用既有“固定代码范围到其实际消费
literal range 之间的短 align4 边界”，不直接修改既有13项 alignment artifact/verifier。
父代理复核 Sol medium 的分母初筛及 Luna max 的冻结合同草案后，明确要求一个新的
additive packet；第五项 `BX r0` 必须使用 `indirect_pc_target`，不得称为 return。

| unknown range | terminal | 目标 |
| --- | --- | --- |
| `[0x078E6E,0x078E70)` | `0x078E6C: 65e0` | B → `0x078F3A` |
| `[0x078F02,0x078F04)` | `0x078F00: 06e0` | B → `0x078F10` |
| `[0x07905E,0x079060)` | `0x07905C: 04e0` | B → `0x079068` |
| `[0x079106,0x079108)` | `0x079104: 15e0` | B → `0x079132` |
| `[0x079146,0x079148)` | `0x079144: 0047` | BX r0，opaque frontier |

这五项是 task-callback artifact 的完整 `closure.holes` 与
`promotion.unknown_holes` 分母，合计10 bytes；每项均为 `0000`，满足
`align4(left_end)=right_start`，两侧都有精确 accepted code/literal owner。
当前 canonical SHA 为 `1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6`，
unknown 为87,749。原 callback artifact 内的旧precoverage身份保持不变。

可复现候选记录位于
`build/experiments/active/task-callback-alignment-gaps/contract-preflight-20260905/`：
`freeze_candidate.py` 用原始 Thumb opcode 独立重算四个branch目标，并绑定全部输入
SHA/size、两侧完整claim、逐字节摘要、实际unknown segment和原frontier。
`candidate.json` 保存结果；首次因 literal claim_kind 拼写错误而失败关闭，未写候选；
原脚本和 `preflight-v1-failure.json` 均保留。此预检不是TDD或独立gap验收。

## 新增 Tier-1 复验（13:14 UTC）

Luna max 已完成纯 producer；父代理新增独立 verifier，复用既有 callback raw worklist
重建342指令、61blocks、15literal bindings，再独立派生五个边界与完整baseline owner。
输入采用已提交 `notes/evidence/rom-evidence-selector-repair-20260905/coverage-after.json.gz`，
不读取会随接入改变的live coverage。scope继续保留生命周期未在本包重跑等非声明。

新run为 `build/experiments/active/cfg-dependent-small-packets/wrapper-dispatcher-boundary-preflight-20260905/`，
packet为 `callback-gaps-luna/`。公共合同SHA
`e80b4686c1a9eeda3b7c0a36fd5794eb30682b74d66d9755a73236db50ec7f58`。
`candidate-parent-v1/payload.json` SHA
`190b1a13162df0f00631cf1e35b52a09cd47c72b92dfda55dc4c10befb2ba715`；
两份独立report相同，SHA
`254399f91b973cc849c6ee32f3b538cd222eea05d99e43bb4b45a489f34cec1f`。

15/15测试在13:06:15Z–13:06:18Z通过，非降级、峰值240.14MiB；两次稳定复验在
13:14:14Z–13:14:16Z通过，非降级、峰值199.09MiB。父级RED/GREEN修复了分支进入
gap/literal及literal多word缺少真实consumer两项边界缺口。测试包含10个gap字节逐一
变异、假structured return、伪owner、扩大claim范围、附加accepted字段。Sol medium
只读复核无P0/P1；`tier1-receipt-v1.json`固定全部源码、合同、测试和报告身份。

本包只进入Tier-1待接入队列，canonical新增仍为0。Tier-2再持久化实现、复现命令与
输出成员，独立验证必须成为原子发布的前置门，真实canonical集成重查whole-unknown与
跨包无重叠，并统一更新coverage/proof/formal。不得外推其余相邻洞、padding/NOP意图、
自然不可达、structured return、编辑/重定位安全或free/allocatable space。
