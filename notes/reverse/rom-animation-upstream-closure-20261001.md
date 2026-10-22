# 458 动画池：有界上游依赖批量枚举与字段重算

> 后续无环child与固定dispatch接线已由 [联合重算](rom-animation-interprocedural-identities-20261001.md)完成；
> 本文25双字段／22缺口是历史条件模型，当前为31／16；BIOS／栈／协程义务仍开放。

状态：固定来源图的依赖枚举／条件模型闭环完成，完整effects、生产链与生命周期仍开放。
永久收据 `notes/evidence/rom-animation-upstream-closure-20261001-v1/`，40成员，manifest
SHA `24b1b0705de42cc3b0f37eda2ff3f6d01889468b08e4c53710fe845ef2c8150c`。
权威输出 `upstream-closure-v2.json`，SHA
`204f2ec47509b2b24ee74c5b5d7e20c0d1dee33acc943de2591442966388ff7a`。
旧报告、旧返回处理实现、实际red与green日志保留；`versions.json`说明取代原因。

## 复用与批量方法

采用已有固定BL／动画caller批量审计模式，首先用可复现脚本与TDD；无子代理。
复用前包56成员receipt、其源图59成员receipt、64,926条真实Thumb指令／918根，以及
raw decoder、frame identity、constant-flow和dependency工具副本。旧封存产物不改。

`closure.py`从真实source成员取root，按非call边做worklist；child单独登记，返回不
虚构后继，SVC／indirect／模式切换与缺root保持显式frontier。共享目标仅分析一次，
循环用visited集合收敛；32,000节点／128目标或identity依赖／64轮限制触发必须报错，
不把部分结果称为闭合。不存在的source root不能靠ROM位形补进原分母。

`upstream.py`先批量追25字段的上游callee，三轮内分析五个新目标、四个再上游目标，
第三轮无新目标。callee registry由5增至11；包括子依赖审计共17个packet／19个
(target, register)状态。无保存保护的寄存器继续审计实际child，直到固定保存规则、
SVC／源边界／模式或本地effects。最后只做**一次**47调用整图重算，不逐代重跑整图。

固定frontier仅表示本实现与固定source图下不再发现新目标；它不是所有callee效果、
自然caller分母或完整ROM已闭合。源图外间接／ARM入口、caller stack域、私有保存区
不别名、child恢复与callback／critical writer仍有未证明义务。

## 实际推进与未闭合范围

| 条件模型统计 | 前包 | 本包 |
| --- | ---: | ---: |
| 双表与group重建 | 47 | 47 |
| flags固定 | 46 | 46 |
| callback固定 | 23 | 26 |
| 两字段同时固定 | 22 | 25 |
| 未固定字段 | 25 | 22 |

新增 `9252E`、`9254E`、`92572` 的callback=0，caller flags=0x60；producer为9243A。
这些仍依赖已列出的frame／call恢复前提，不是自然运行或accepted动画字段合同。
上包13个callee全部opaque的统计未在本包重算；本包只运行增强的条件模型，不混称新strict结果。

剩余22字段为1 flags／21 callback，仍按完整47分母保留：

| 第一未闭合目标 | 字段数量 | 原因与证据入口 |
| --- | ---: | --- |
| 667A0 | 10 callback | r7/r9未压栈保护；655F4→9C3EC的实际child保存关系已枚举，但跨child GPR绑定尚未实现 |
| 9C0E0 | 4 callback | 8E202的r9与95AA4的r5经SVC #11；ROM不签发外部BIOS效果 |
| 6D964 | 4 callback | 6DC72为indirect_branch，需要绑定既有固定dispatch表／source合同；不能跳过switch分支 |
| 8D580 | 2 callback | r9未保存，9C0E0／9C1E4子effects；软件helper与SVC分开处理 |
| 9C574 | 1 flags | 6F992调用的callee首指令为BX PC，切换ARM；不是普通Thumb return |
| 626B4 | 1 callback | 77E4E重载caller SP+0x48，caller memory可能被写入，不靠GPR保存推导内存不变 |

报告的fixed_field_reports仍包括原25项规划分母，其中三项现在已找到零常量；
当前未闭合项以remaining_fields／caller_counts为准，不能将旧25再重复累计。

## 返回支持与仍需接入的语义

新增原字节 `F746` 的Thumb **MOV PC, LR**返回身份处理：仅在LR仍为入口return token、
SP回到入口时签发同Thumb caller的身份；LR被覆盖则失败关闭。这是当前固定Thumb调用
模型的属性，不外推任意ARM caller、终止性、异常或自然恢复。
`7847` **BX PC**明确标为ARM mode-switch，不当普通返回；9C574保持开放。

补齐返回后，9C1E0成为纯leaf身份合同；9C14C／9C1E4的条件packet可证明返回，但
本模型因opaque child销毁全部GPR，暂只保留SP。它们真实child的保存关系不能靠
存在摘要自动获得，需要递归绑定、验证每层原ROM和source成员，并拒绝循环自证。
同样，667A0的十个callback仍需655F4→9C3EC关系真正进入模型；本包只枚举证据。

下一包应合并17个packet的无环子依赖身份接线、软件MOV-PC返回、9C574的受证ARM
interwork，以及6D964既有dispatch edges；直接复用可验真的旧来源合同。BIOS与caller
stack仍不因工具能力增强而放宽。新callee自证循环、输入／节点／方法身份漂移失败关闭。
随后联合两类callback、critical-field writer、counter/timer域和两层sentinel。
八descriptor／24entry的496B仍仅候选，promotion=0，不认领整段混合池。

## 验证与可重放证据

批量worklist七测试先红后绿，覆盖共享目标、有限循环、缺root和预算失败；追加
MOV-PC返回与BX-PC模式边界三反例后，真实红日志为一failure＋一error，随后最小
修正与重构通过。复用38项frame／flow／summary／dependency测试，总 **48/48**。
LR覆盖的负例必须继续拒绝；它原本已失败关闭，不把该测试夸大成新bug修复。

真实批量依赖与一次全source graph传播为集成验证。永久notes路径执行新的active
受管run：48测试、17packet、3轮发现和47调用报告逐字节复现，53.8s、峰值282.5MiB、
非降级、exit0，显式同 `build/experiments/heavy.lock`。实验及重放均complete。
AST、脚本行尾空白和改动文档git diff检查通过；本包新source CFG verifier、mGBA、
global formal与硬件运行均0。跨目录重放是同一实现的新进程复现，不是第二套语义实现。

复验（逆向工作树根；使用全新CHECK_UNIQUE）：

```sh
python3 tools/experiment_workspace.py --root . init --task animation-upstream-closure-replay --run-id CHECK_UNIQUE
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/animation-upstream-closure-replay/CHECK_UNIQUE/guard.json --wall-timeout-s 240 --idle-timeout-s 120 --max-tree-rss-mib 1536 -- python3 notes/evidence/rom-animation-upstream-closure-20261001-v1/replay_receipt.py build/experiments/active/animation-upstream-closure-replay/CHECK_UNIQUE/output build/experiments/active/animation-upstream-closure-replay/CHECK_UNIQUE/replay.log
python3 tools/experiment_workspace.py --root . complete --task animation-upstream-closure-replay --run-id CHECK_UNIQUE
```

canonical/proof/bank-proofs身份保持，unknown87,631B，旧175 blockers未重算。
未新增Tier-1、未提交或push；Butano不改。Goal active，最新周额度剩36%，保留20%仍有效。

### 【功能特性】
- 从本记录可查看47条调用的上游图、三项新增零callback候选和全部22个开放字段；仅用于继续逆向。

### 【BUG 修复】
- 分析器返回边界已修复：普通MOV PC, LR被判为未支持、BX PC混在返回候选 → 前者核对LR/SP身份，后者显式留ARM切换边界。

### 【验收清单】
- [ ] 查看caller_counts → 双字段25、callback26、缺口22，47双表均重建，promotion=0。
- [ ] 查看9252E／9254E／92572 → callback0、caller flags0x60，仍带条件保存前提。
- [ ] 查看proof_packets／unsaved_identity_dependencies → 17packet，9C574为mode_switch、9C0E0为SVC，子身份接线仍开放。
- [ ] 查看portable-report → 48测试、一次整图重算和权威JSON完全复现；正式unknown保持87,631B。
