# 458 动画池：固定来源图前驱与共享 callee 缺口

> 后续[五callee原指令保存分析](rom-animation-callee-effects-20261001.md)已完成：数量仍13／22，
> 第一层跨越后暴露七个上游目标及循环回边。下文“五目标”只指当时frontier，非完整依赖。

状态：批量研究闭环完成，完整 caller／生命周期合同开放；promotion=0，未新增 Tier-1。
永久收据：`notes/evidence/rom-animation-caller-predecessor-20261001-v1/`，59 成员，
manifest SHA `1ba62270af82fec601f758a6fb2637521f5e05f5a46efde4ce9cdc213fa918c8`。
权威输出为 `predecessors-v4.json`、`frontiers-v3.json`、`callee-windows.json`；
`versions.json` 标明早期报告被取代的原因。完整失败日志、旧实现和旧结果均保留。

## 方法、复用与分母

复用“固定目标 BL 分母／动画池 caller 批量局部审计”任务模式，首先采用可复现脚本，
无子代理。固定上包 63 个 receipt 成员及其全部输入身份；九组 source CFG 曾在上包
经独立 verifier 实际验真，本包核对原报告、输入与指令分区，不重复运行它们。
继续使用原 raw decoder、vendored Capstone 和局部参数 transfer，不另建游戏动画系统。

九组来源并集为 **64,926** 条真实 Thumb 指令。取 artifact 显式根、直接 call 入口、
缺少非 call 前驱的入口及无已证明入口的孤立环节点作根，最终 **918** 根、孤立节点 0。
来源外的 indirect／ARM 入口并未穷尽；不能由此声称完整自然执行的 caller 域。
从固定图传播寄存器常量、SP-word 常量和有效比较条件；汇合只保留所有前驱相同事实。
可能别名的写入清除 stack 事实；未知 callee 清除所有寄存器和 stack 事实。
返回、BX、上下文切换为 opaque stop；call fallthrough 明确依赖未证明的恢复条件。

两个模型都重建上包 **47/47** 双表地址与 group，不把47扩展成全ROM消费者分母：

| 固定图模型 | flags 固定 | callback 固定 | 两字段同时固定 |
| --- | ---: | ---: | ---: |
| 所有 callee 对参数事实 opaque | 24 | 15 | 13 |
| 仅 allocator 有条件保留 r4..r11 | 46 | 23 | 22 |

后者绑定 `626B4..62786` 原始完整 frame SHA、prologue 和 return bytes；其必要前提仍
未证明：callee 私有 `[entrySP-40, entrySP)` 与对象池 `03003BB8..030059B8` 不重叠。
即使启用该规则，**caller stack facts 仍全部清除**。伪造合同或修改 restore bytes 拒绝。
两个模型的数量都是固定图内的候选参数事实，不是完整生命周期／自然路径已闭合数量。

## 剩余25个字段合并成一个共享 callee 工作包

条件模型仍缺 1 个 flags、24 个 callback。反向依赖规划不做分支收窄，不签发值域；
遇到 callee、动态定义、可能别名 store、frame／entry 边界明确输出 frontier。
真实缺口只有以下五个 callee 目标，不再拆成25个单点实验：

| 目标 | 缺口数量及所需事实 | 固定原字节观察与后续义务 |
| --- | --- | --- |
| 6571C | 14 callback；r5/r7/r9 保存 | 4条指令 `0149012008707047`，literal65724指向0201BD68；仅全局byte store。优先证明完整纯leaf保存规则，尚未接受 |
| 66758 | 7 callback；r5/r6/r9 保存 | 固定66758..667A0窗口，save/restore与655B4、6626C、655F4子调用；需私有frame不被写坏及子调用恢复，不套用通用ABI |
| 6F5BC | 1 flags；r6 保存 | 固定6F5BC..6F70C窗口；6F914另一前驱常量为8，内部r6会被覆盖，需实际恢复证明 |
| 8D580 | 2 callback；r9 保存 | 固定8D580..8D65E窗口；r9未直接写但有子调用，需绑定其effects；r8保存不能替代r9证明 |
| 626B4 | 1 callback；caller SP+0x48 不变 | 77E4E在先前allocator后重载SP+0x48；callee可能改写caller stack，不能凭寄存器恢复规则保留内存 |

原始窗口与来源instruction membership保存在 `callee-windows.json`，窗口并不等于
已签发的完整callee合同。`9C0E0` 的四字节为 **`0bdf7047`（SVC #11 / BX LR）**，
不是 ARM memcpy interwork veneer。BIOS／HLE的寄存器effects必须另建固定边界，
ROM字节本身不能证明外部BIOS行为；mGBA源码事实也不能升级成实体硬件证明。

## TDD纠错与验证

常量flow初始9测试先红后绿；追加失效合同、BL suffix与flags变更反例后，共12项。
新的 MOVS 反例发现 vendored Capstone 的 `regs_access()` 会漏报部分 CPSR写入，
已以 raw Thumb flags 类补充失效规则。再追加2项反例，发现高MOV或SP reload覆盖
比较寄存器后，旧predicate错误把新值收窄为零；已在真实红测试后修正失效规则。
`refactor-tests.log` 和 `predicate-red.log` 保留两轮实际失败；最终14项flow全部通过。
反向dependency另4项先红后绿，验证常量来源、callee边界、stack事实不保留与预算耗尽。

从永久notes路径执行 `replay_receipt.py` 到新的active受管run：**18/18测试**通过，
完整64,926指令传播、47条参数、25字段依赖与原始callee窗口均逐字节重放一致。
实际31.0s、峰值276.2MiB，统一 `build/experiments/heavy.lock`，非降级，exit0。
本包两轮语义纠错重跑后，ROM统计仍为上表；旧报告不得因计数相同而继续作为证据。
权威JSON的实现SHA与父报告SHA均重新绑定，原始封存receipt不修改。

Python AST、所有脚本行尾空白检查通过；真实全图与跨目录重放是本包集成验证。
本包新增source CFG verifier运行0次、mGBA启动0次；未运行全局formal或硬件验收，
因为未修改其输入或游戏行为。复验不读取原caller-predecessor build脚本；已封存产物只读。

## 重放与下一验收

在逆向工作树根运行，输出必须新建，不得覆盖旧run：

```sh
python3 tools/experiment_workspace.py --root . init --task animation-caller-predecessor-replay --run-id CHECK_UNIQUE
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/animation-caller-predecessor-replay/CHECK_UNIQUE/guard.json --wall-timeout-s 240 --idle-timeout-s 120 --max-tree-rss-mib 1536 -- python3 notes/evidence/rom-animation-caller-predecessor-20261001-v1/replay_receipt.py build/experiments/active/animation-caller-predecessor-replay/CHECK_UNIQUE/output build/experiments/active/animation-caller-predecessor-replay/CHECK_UNIQUE/replay.log
python3 tools/experiment_workspace.py --root . complete --task animation-caller-predecessor-replay --run-id CHECK_UNIQUE
```

先合并处理五个callee的原指令保存／memory effects，最短6571C作低成本入口；
对privateframe／BIOS仍不能证明的部分保持条件或opaque。再联合两个callback、对象
critical-field writer及counter/timer域，统一descriptor与sequence两层sentinel边界。
能闭合的完整子集才进入独立exporter/verifier、变异与受管Tier-1发布；496B候选不提前晋升。
canonical/proof/bank-proofs SHA保持，unknown **87,631B**，旧正式175 blockers未重算。
未提交或push；Goal active，周额度读数剩38%，用户保留20%的限制继续有效。

### 【功能特性】
- 从本记录进入收据，可查看47条调用的两个保守模型，以及25个缺口对应的五个共同调用目标；仅供继续逆向。

### 【BUG 修复】
- 分析器错误收窄已修复：MOVS漏报flags或比较寄存器被覆盖后沿用旧predicate → 清除失效条件，反例保持unknown；未改变游戏行为。

### 【验收清单】
- [ ] 查看predecessors-v4 → 64,926指令、918根、两模型47/47双表重建，13/22有明确适用前提。
- [ ] 查看frontiers-v3 → 25字段、五个callee目标；不是25个已经签发的值域。
- [ ] 查看portable-report → 18测试与三个JSON完全复现，promotion=0、自然执行未证明。
- [ ] 查看versions与两个red日志 → 被取代原因、实际失败和修复证据完整；正式unknown仍87,631B。
