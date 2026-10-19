# 动画调用：无环子身份与固定 dispatch 的联合重算

> 后续 [callback／关键写入联合审计](rom-animation-critical-writers-20261001.md)已绑定八入口与查表顺序；
> 全writer、counter域与handle仍开放，本文31／16的条件模型统计保持。

状态：23 个 callee 库根、两轮目标发现与一次整图重算已完成；永久路径重放通过。
本包仅推进固定来源图下的条件候选，完整生命周期和自然域仍开放，promotion=0。

## 复用方式与输入

复用登记表的固定 BL／动画 caller 批量审计模式，脚本优先，无子代理。
旧上游包 manifest `24b1b0705de42cc3b0f37eda2ff3f6d01889468b08e4c53710fe845ef2c8150c`
及其 40 成员逐项验真；其权威 payload 为 `204f2ec47509b2b24ee74c5b5d7e20c0d1dee33acc943de2591442966388ff7a`。
沿用 64,926 条来源 Thumb 指令／918 根和原 47 条双表／group 分母；不复制新全 ROM 分析器。
复用 frame identity、constant-flow、dependency 与既有 CFG v2/v3 独立 verifier 的 raw dispatch 重建。
新能力追加到这些工具的实验副本；不改旧封存 receipt、生产 canonical 或 Butano。

永久目录 `notes/evidence/rom-animation-interprocedural-identities-20261001-v1/`。
权威输出 `interprocedural-identities-v2.json`，SHA
`d84f8a7232f1a84d4b95b74e2ed2e99d5a0df352bb832a98f9976dbf19210237`。
第一遍 21 根报告和对应 driver 保留；v2 在同包追完新目标，不将四条新字段再拆微包。

## 新接线的可验证边界

`callee_effects.py`递归重建每层 child 的原 ROM、指令分区、return/SP 身份与保存寄存器，
逐字段比较完整摘要；`flow.py`再核对每层 instruction membership 属于固定来源图。
循环自证和深度超过 32 失败关闭。未知 child 仍销毁所有 GPR；已验真的 child 只保留其
实际证明的 r0..r12。BL 本身覆盖 LR，不能因 child leaf 保留 LR 而继承父入口 LR。
strict 父调用即使 child 已知仍清空 memory；caller stack 永不摘要为不变。

私有保存区不别名、opaque child 按原 SP 返回且不破坏保存区等仍是**未证明前提**；
递归 child 也以摘要 SHA 关联自身条件。存在保存摘要不等于所有 memory effects、
终止性、任意中断、ABI 或自然运行已闭合。例如 96168 的保存区候选仍带多个 child
返回前提，其中包含 BIOS veneer；不能把四条新零 callback 宣称为 BIOS effects 已验证。

固定 6D964 callee 的 terminal `6DC72`复用旧十槽 dispatch：CMP bound 9／BLS guard
`6DC64/6DC66`，inside `6DC6A`，table `6DC7C..6DCA4`。全部 10 槽都纳入分析，
包括重复目标；不任选单支。独立 verifier 从 v2 raw baseline 重建全部 29 个 dispatch，
与 v3 public static_dispatches 整体相等后才绑定这一表。6 个 live 输入 SHA 每次重查；
缓存只避免同进程重复 raw 重建，返回防御副本，不放宽 live identity。
移除 guard inside edge 后 root 不能再到 terminal，直接进入 terminal 的 root 必须拒绝。
本包没有声称重跑整个 v3 verifier；实际仅调用其独立 baseline／dispatch 重建部分。

## 结果与剩余字段

| 固定条件模型 | 前包 | 本包 |
| --- | ---: | ---: |
| 双表／group 重建 | 47 | 47 |
| flags 固定 | 46 | 46 |
| callback 固定 | 26 | 32 |
| 双字段固定 | 25 | 31 |
| 未固定字段 | 22 | 16 |

两轮目标发现：第一轮新增 `92018`、`96168`，第二轮无新目标；库 23 根中 21 根
有条件或 strict return identity，9C0E0 的 SVC 与 9C574 的 ARM 切换保留拒绝。
本包只重算增强的条件模型，不混称旧全 opaque 模型也得到 31。
新增 callback=0：`77E7C`、`77EA2`、`9391E`、`93946`、`9396E`、`93994`，flags 均 0x20。

| 第一未闭合边界 | 字段数 | 要求 |
| --- | ---: | --- |
| 9C0E0 | 8 callback | 外部 SVC #11 的 r5/r7/r9 效果，ROM 不签发 BIOS 合同 |
| 8D580 | 2 callback | r9 不保存，不能用 r4..r8 的摘要代替；child SVC 效果仍开放 |
| 92018 | 4 callback | 仅有 r4/r5/r6/SP 条件保存，r7/r9 需完整 8A4D8 数据效果 |
| 9C574 | 1 flags | 协程同上下文恢复，不能按普通 returning callee |
| 626B4 | 1 callback | 77E4E 的 caller SP+0x48 重载，GPR 保存不证明 caller memory 不变 |

`frontier_kinds`共有 17 项而非 16 字段：flags 路径既有常量 producer 又有协程缺口，
按 remaining_fields 计分母；不能把两条 frontier 重复算成两个字段。

## ARM 入口的复用结论

原字节 `9C574:7847` BX PC → `9C578:3b8ffdea` ARM B → `026C`，
对应 canonical 中已受证 boot ARM root `024C..03BC`，artifact SHA
`2f78132647235ca1c9fd155b950ff4128e4b01ca10d0fa0ae0fcfa4fdd37e30d`。
这正是已有 [共享任务记录生命周期预检](rom-coroutine-record-lifecycle-preflight-20261001.md)
的调度恢复链，不应另造普通 ARM ABI helper。
03000D18/current-record、任务 SP/LR、slot 域与全部 writer 尚未闭合；既有 92 指令／
0 frontier 的静态 CFG 不证明同任务恢复。相邻 veneer 字节也未晋升。

## 红绿、集成与失败记录

新增 child 6 测试先因未支持 API 正确失败，再最小接线通过；dispatch 初始 5 测试先因
缺绑定模块失败，随后通过。缓存反例先观察两次 raw 重建再修为一次，同时 warm cache
live 输入漂移仍拒绝。嵌套接线正例最初误用 strict 子摘要，不能证明 return；该轮红和
所谓 green 都是 fixture 失败，原日志保留且 versions.json 明示无效。修正为 conditional
fixture 后，临时使用旧 sealed flow 的副本得到真正的 unverified summary 失败，再接入
新递归 validator，正例及丢失深层 source 成员的负例通过。没有回滚用户文件。

合计 **63/63**，含既有 flow/frame/frontier/closure 与新增 child/dispatch/实际 ROM wiring。
真实 ROM 的两轮 callee 库重建及最后一次 47 caller 传播是集成验证；主 run 188.2s，
峰值 274.1MiB，非降级 exit0，统一 `build/experiments/heavy.lock`。
永久路径受管重放 234.1s／峰值 290.95MiB，非降级 exit0；63 测试及权威 JSON
逐字节复现，两个 owned run 均 complete。收据 58 成员，manifest SHA
`1aca46ee19d8af2ddf051f1daa1fbfec1cd660245578020f689303116ff78e70`。AST、脚本行尾空白与输入身份检查通过。

复验（逆向工作树根，使用全新 CHECK_UNIQUE）：

```sh
python3 tools/experiment_workspace.py --root . init --task animation-interprocedural-identities-replay --run-id CHECK_UNIQUE
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/animation-interprocedural-identities-replay/CHECK_UNIQUE/guard.json --wall-timeout-s 420 --idle-timeout-s 120 --max-tree-rss-mib 1536 -- python3 notes/evidence/rom-animation-interprocedural-identities-20261001-v1/replay_receipt.py build/experiments/active/animation-interprocedural-identities-replay/CHECK_UNIQUE/output build/experiments/active/animation-interprocedural-identities-replay/CHECK_UNIQUE/replay.log
python3 tools/experiment_workspace.py --root . complete --task animation-interprocedural-identities-replay --run-id CHECK_UNIQUE
```

本包新 mGBA、硬件、全局 formal 与九来源 CFG verifier 运行均为 0；输入链 SHA 重验
不冒充语义 verifier fresh replay。canonical/proof/bank-proofs 均保持原 SHA，unknown
87,631B；175 blockers 为历史正式结果，未重算。未达到 Tier-2，不新增 Tier-1 或提交/push。

下一里程碑应合并两类 callback、对象 handle、critical-field writer、counter/timer 域与
两层 sentinel；优先实际 writer/入口域，不再追加孤立保存窗口。92018 的软件数据效果可
在同包追 8A4D8；BIOS、caller memory、协程域分别保留外部／别名／恢复义务。
31 条候选仍不能认领 8 descriptor／24 entry／496B 或整段混合池。

### 【功能特性】
- 从本记录进入权威报告可查看 47 条调用、六个新零 callback 候选和完整 16 字段缺口；仅供逆向。

### 【BUG 修复】
- 分析器跨 child 接线已修复：已枚举身份仍按 opaque 丢值 → 逐层验真后保留实际受证 GPR，LR／memory 继续按指令销毁规则处理。

### 【验收清单】
- [ ] 查看 caller_counts → 47 双表、32 callback、31 双字段、16 缺口，promotion=0。
- [ ] 查看新增六个 site → callback0／flags0x20，并保留条件保存标签。
- [ ] 查看 6D964 dispatches → 10 槽、guard dominance，直接 terminal entry 反例拒绝。
- [ ] 查看 context_switch_spine → ARM026C 已有来源，ordinary contract 与同上下文恢复均 false。
- [ ] 重放本包 → 63 测试通过且权威 JSON 逐字节相同；正式 unknown 保持 87,631B。
