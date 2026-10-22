# 458 动画池：原指令保存区证明与多层调用缺口

> 后续[上游批量枚举](rom-animation-upstream-closure-20261001.md)以17packet／3轮推进，
> 双字段22→25、字段缺口25→22；下文25／七目标是上一阶段分母，不能重复累计。

状态：第一层五callee身份分析及前驱重算闭环完成；完整生产链／生命周期未闭合。
永久收据 `notes/evidence/rom-animation-callee-effects-20261001-v1/`，56成员，manifest
SHA `43cc8b641d17f22d8ed5caba54be59b80c8260a6d69f76a33aa3adcd0110e663`。
权威输出：`callee-effects-v2.json`、`caller-effects-v2.json`、`updated-frontiers.json`。
旧结果与SP-alias错误实现、所有red/green日志保留，`versions.json`说明取代原因。

## 方法与复用

沿用固定目标BL／动画caller批量模式，先做可复现脚本与TDD，无子代理。复用上包
59成员receipt、64,926条source指令／918根、raw decoder、vendored Capstone、
constant-flow与dependency框架；本包副本在新active run中维护，不修改任何旧封存产物。
31个current source/input身份另逐项核对一致；source CFG verifier本包新运行0次。

新增的 `callee_effects.py` 在固定真实指令分区中，以入口寄存器身份token、相对SP和
保存word传播实际push/pop、copy与store效果；分支两边都走，汇合只保留共同身份。
动态SP／PC、重叠指令与预算耗尽拒绝；未知返回与SVC留frontier，不从通用ABI猜保存。

两个模型：strict不越过未知child，不保留可能被alias store破坏的保存区；conditional
明确假定非SP store不碰保存word、child返回相同SP且保存区完整。child仍销毁全部GPR
事实，只有实际从word恢复的身份才能保留。这些条件**未对自然caller证明**。
SP-token可明确定位的store按真实覆盖范围失效保存word，不能被disjoint假设豁免。

## 五个callee的固定图结果

| 目标 | 访问指令／最深SP | 原指令可保留的相关身份 | 边界 |
| --- | --- | --- | --- |
| 626B4 | 98／-40B | conditional：r4..r11 | 16项非SP store保存区前提；caller stack内存仍不保留 |
| 6571C | 4／0B | strict：r2..r12、SP、LR | 仅r0/r1改写，全局byte store；未升级为自然运行／硬件证明 |
| 66758 | 33／-24B | conditional：r4/r5/r6/r8/r9 | 三child及保存区前提；r7/r10/r11未由本模型证明 |
| 6F5BC | 152／-20B | conditional：r4..r7 | 61E6C子调用与保存区前提；内部r6覆盖后实际恢复 |
| 8D580 | 91／-28B | conditional：r4..r8 | r9未保存，child effects未知，**不保留r9** |

这里“返回身份证明”是固定图内可观察返回的身份属性，不证明一定终止或真实caller
能恢复到fallthrough。原caller分析的unverified-call-continuation仍标记，不删除。
`9C0E0`仍为SVC #11 / BX LR的外部BIOS边界，callee效果不能从ROM凭空签发。

调用摘要由同一ROM与实际source成员重新计算；修改ROM、遗漏指令、伪造保存寄存器
或声明caller stack不变均被拒绝。摘要不能仅靠原始字节SHA或函数名称获得信任。

## 没有增加固定字段，第一层不是完整依赖

47/47双表及group均重建。leaf-only模型仍为flags24／callback15／双字段13；
五callee条件保存模型仍为flags46／callback23／双字段22，与上包计数相同。
这不说明保存分析无效，而是此前只看到首个callee阻断，不能把14+7+1样本直接加到
“字段已固定”数量。实际传播与反向追踪发现更早／循环回边上的调用仍销毁来源值。

25缺口依赖现在为constant producer 1、callee register effect 24、callee stack effect 1，
目标变为七个，完整分组保存在 `updated-frontiers.json`：

| 目标 | 字段数量 | 具体义务 |
| --- | ---: | --- |
| 66A48 | 9 callback | r5/r6/r9的上游保存与来源 |
| 94654 | 4 callback | r7保存与来源 |
| 667A0 | 4 callback | r9保存与来源 |
| 66AE8 | 4 callback | r5/r9保存与来源 |
| 8D580 | 2 callback | 未保存r9经9C0E0/9C1E4的effects；外部BIOS独立边界 |
| 6ED68 | 1 flags | 6F996处循环后续调用可能改写r6；另一前驱6F774固定8，不能选单条路径 |
| 626B4 | 1 callback | 77E4E重载caller SP+0x48，memory effects仍未知 |

上包“五目标”是**第一层frontier**，不是完整callee闭包。下一包应在固定来源图中
一次构建完整上游callee／producer依赖，包含循环回边；有保存区规则的节点批量分析，
未保存寄存器递归绑定实际child effects。到constant、entry、SVC、未知store／indirect
边界才停止。设置节点／资源上限，保持失败关闭；不要逐代冻结、逐代重跑整图形成微包。

生产链完善后还要联合两类callback与critical-field writer，检查counter/timer域及
对象pool／handle别名，再统一descriptor和sequence两层sentinel。八descriptor／24entry
的496B仍仅候选，不能凭本包保留摘要认领，也不能整段认领混合池。

## TDD、集成与长期重放

原始frame效果11项先红后绿；SP别名STM追加反例实际失败，随后修正并重构，共12项。
保存摘要接线5项先因缺API失败再通过；前驱摘要接线3项同样先红后绿。复用14个flow
及4个dependency旧测试，**38/38**最终通过。测试包括替代返回路径、未知child、
保存word破坏、SVC、SP变更、伪造摘要、ROM／成员身份漂移和预算边界。

真实65K来源图两模型运行及25字段依赖为集成验证。notes永久路径在新的active受管run
重新执行38测试、五callee原指令分析、47调用整图和25字段依赖，三个权威JSON逐字节一致。
实际49.5s、峰值186.5MiB、非降级、exit0，统一 `build/experiments/heavy.lock`。
Python AST、脚本行尾空白及改动文档的git diff检查通过；原实验与portable run已complete。
本包mGBA启动0、正式CFG verifier新运行0、全局formal新运行0，未做硬件验证。
保存规则是条件性ROM研究结果，不把未执行的自然／硬件验证写成通过。

复验命令（逆向工作树根；CHECK_UNIQUE需使用新ID）：

```sh
python3 tools/experiment_workspace.py --root . init --task animation-callee-effects-replay --run-id CHECK_UNIQUE
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/animation-callee-effects-replay/CHECK_UNIQUE/guard.json --wall-timeout-s 240 --idle-timeout-s 120 --max-tree-rss-mib 1536 -- python3 notes/evidence/rom-animation-callee-effects-20261001-v1/replay_receipt.py build/experiments/active/animation-callee-effects-replay/CHECK_UNIQUE/output build/experiments/active/animation-callee-effects-replay/CHECK_UNIQUE/replay.log
python3 tools/experiment_workspace.py --root . complete --task animation-callee-effects-replay --run-id CHECK_UNIQUE
```

canonical/proof/bank-proofs身份未变，unknown87,631B，promotion=0；未新增Tier-1。
旧全局175 blockers未重算，Goal仍active；最新周额度剩37%，保留20%的用户限制有效。
未提交或push；Butano工作树未改动。

### 【功能特性】
- 从本记录进入收据，能查看五callee的真实保存区推导和47条调用的剩余生产链；用于继续逆向，没有新增游戏入口。

### 【BUG 修复】
- SP别名STM错误豁免已修复：把明确写向保存区的STM当成disjoint → 清除可能被破坏的保存word，反例不再错误签发寄存器保存。

### 【验收清单】
- [ ] 查看callee-effects-v2 → 6571C strict通过，8D580保存列表没有r9；其他前提显式列出。
- [ ] 查看caller-effects-v2 → 双字段仍13／22，47双表均重建，caller stack未保留。
- [ ] 查看updated-frontiers → 25字段、七个目标，6F914的循环回边6F996没有漏掉。
- [ ] 查看portable-report → 38测试、三个报告完全复现，promotion=0；正式unknown保持87,631B。
