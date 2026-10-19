# 剩余逆向工作推进方案（2026-10-01）

> 2026-10-01 [map-sprites 部分 bank 合同](../notes/rom-map-sprites-partial-bank-20261001.md)通过：
> 19 固定输入、ID 1 / definition_ptr 的 1/86 单元，19 项测试及真实 auditor CLI 接线通过。
> proposal 保留离线，全量 bank gate 正确拒绝；正式矩阵和 canonical/proof 不变。
> 动画七对参数仍缺 flags/slot 生命周期，不认领整池；下一步 cutscene 两类种子与批量矩阵。

> 2026-10-01 [显示文本Tier-1](../notes/rom-display-text-delta-tier1-20261001.md)实际通过：
> 92site/85record/1,053B、56输入，18测试含真实CLI通过，稳定重建与live unknown投影通过。
> 当前待接入为显示文本1包和独立命令脚本1包（合计2,721B库存），不合计同类数；
> 未触发Tier-2，canonical仍87,631B。下一主线转向458动画flags/slot闭包及bank矩阵。

> 2026-10-01用户已取消3%研究限制；Goal现为“推进逆向工程，直到完成或周额度只剩20%”。
> 本文件保留原研究背景；其中“只研究/不实现/3%上限”是历史范围，已由本条授权取代。
> [局部参数TDD实现](../notes/rom-display-text-parameter-flow-tdd-20261001.md)9测试通过，
> 92条raw路径已证明；显示记录合同与受管发布尚未完成，继续按里程碑执行。

本轮只研究路线，授权上限为约3个百分点周额度；不把预算用满作为目标，不执行新
功能实现、canonical接入或全量formal。输入与重放收据见
`notes/evidence/reverse-work-plan-20261001-v1/`。这是规划，不是新的语义验收。

## 当前事实与真正的完成距离

- 当前canonical：6,203,825已分类、87,631未知字节，1,763个未知段；SHA为
  `b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`。
- 17个至少1KiB的段合计42,880B，占未知区约48.9%。其余44,751B分散在1,746段。
  单纯清理2B洞或数十字节小包，不应继续成为主要工作量。
- 当前待接入为命令脚本1包/29record/1,668B及显示文本1包/85record/1,053B；
  二者语法不同、分别积累同类里程碑，均不从87,631提前扣除。旧12B包不可重复累计。
- 最近正式验收为107/107合同、ROM97/97通过，但global complete=false、175 blockers。
  本轮只读取历史验收，不重跑formal。22个有效bank声明覆盖23/2,954条记录，字段
  分母部分仍unknown；10/32的完成项是disproved候选，不是有效bank穷尽完成。
- 七个全局门分别为字节覆盖、资源round-trip、编辑器round-trip、逻辑修改、干净重建、
  模拟器回归、实体硬件。前六仍partial，硬件blocked_external。因此98.607%字节分类
  不能换算成剩余工时，更不能以unknown清零替代整体完成。

## 优先级与验收里程碑

| 顺序 | 工作包与稳定入口 | 先做什么 | 完成产物与停止条件 |
| --- | --- | --- | --- |
| P1 | v15–v21已晋升CFG的固定文本消费者；`0x463914..0x463B18`附近 | 从来源完整分母重枚举literal，证明寄存器流分别进入66758/r0或66EFC/r1；先复验实际用到的来源合同 | 单独受管Tier-1包，明确接受/排除分母、双实现解析、变异与CLI集成；遇到不支持callee、分支或覆盖身份即排除，不扩大窗口猜测 |
| P2 | 低脚本池578C..7554（7,624B）、42AB..542E（4,483B）、CEA..12F0（1,542B）及1781..1CD0（1,359B） | 先固定真实table/index consumer，复用旧语法解析器；动态完整索引域未闭合时，只做可证明的固定root delta | 与既有1,668B去重后积累同信任边界包；零后缀、邻接文本和新opcode不自动认领 |
| P3 | AI配置与formation controller的联合生命周期 | 合并main/extra池及slot13别名；重建初始化、两类来源、copy、inherit/clear、lookup前后和scorer入口域 | 一份完整producer→writer→consumer合同；不能证明域就保持unknown。不要再靠新增零散窗口来宣称进展 |
| P4 | 协程/任务记录与新opcode依赖 | 从7C5E8稳定入口独立重建到7C61C，补slot域及current-record/SP/LR写入和恢复；与现有scheduler链共用模型 | 先闭合生命周期依赖，再重开opcode2/6/7/8；125B旧候选不是收益。缺新根证据时停止该路线 |
| P5 | 字节调查以外的严格完成债务 | 先固定22个有效bank的记录×字段矩阵，优先复用已有独立runtime verifier的bank；补缺少verifier的历史A/B | 能显示每个ID/字段的未验证项与证据类型；受控调用与自然路径分开，样本和ROM fidelity不冒充穷尽 |
| P6 | round-trip与发布 | 资源提取/编码先行，重建和运行矩阵随后，编辑器UI在相应语义稳定后接入；实体GBA最后独立验收 | 七门按既有固定case集合验收；硬件是外部依赖，不能用模拟器替代 |

P1是建议的下一包：现有筛选域仅7,436B/3,515指令，落盘清单实际33个literal消费点，
其中21个不同target位于上述文本簇。前次摘要32点是计数错误，以本轮输入重算为准。
这不是33个都可接受，也不是完整CFG或全ROM消费者分母；来源语义verifier本轮未重跑。

后续[实际调用路径预检](../notes/rom-fixed-text-route-preflight-20261001.md)将21site分成
六类：13直接renderer、1已知桥接、2新wrapper、2截断复制、2固定长度复制及1开放callee。
假设总量仅482B，未验收。下一包先复用14site/352B已有bridge，再评估wrapper的102B；
66EFC只涉及22B，暂缓新增解析合同。完成同类delta后转向大池/生命周期，不无限深挖。

### P1的关键技术边界：66EFC不是普通NUL整串复制

有限原字节反汇编显示：66F08把r1保存到r5；66F46/66F9C读取源字节，66F4E/66FA0按零
判断；66F74在byte==1时额外推进并复制一个字节；66F90常规推进；66F98/66F9A还以
输出计数0x23截断，然后66FC0向目的写零。因此不得以“寻找首个NUL”直接认领整串，
也不得复用66758 renderer grammar代替该循环。必须独立重建两种退出边界和实际源读取
集合，证明早停、控制byte==1及截断附近的变异均失败关闭；实际消费到的源NUL与合成
目的NUL要区分。本轮窗口包含末尾literal，线性反汇编不是CFG验收，也不证明RAM容量、
自然运行或callee返回安全。反汇编原输出保存在规划收据，禁止由此直接promotion。

### P3应怎样一次解决依赖，避免反复小切片

复用`notes/rom-ai-config-writer-preflight-20260930.md`、
`notes/rom-ai-extra-pool-lifecycle-preflight-20260930.md`和已知入口局部域分析。
目标同时覆盖53F348配置base、5411E4+lookup×AC+2来源，以及main/extra复制链；
5411E4是大未知簇内的真实局部读取锚点，却不证明整个53F89C..541368（6,860B）结构。
已有FF初始化、index24读到9的反例意味着“所有writer都在0..7”的捷径不可用。
先证明到达scorer时的域，不能把未发生的任意u8试读说成自然越界。
59EAE0..59F560（2,688B）已有08F654 producer/lifecycle拒绝记录，保持停用；只有新
root-to-source证据能够解除门禁，不能换may-read标签绕开。

## 研究收敛后的执行顺序

[局部路径成本核对](../notes/rom-renderer-flow-cost-20261001.md)：92site各4～7条直线指令，
全部路径在自身instruction claim内，75/17分别调用66758/667A0。下一步使用有限Thumb
编码子集的失败关闭raw verifier即可；不引入通用符号执行或模拟器，不重复六来源审计。
寄存器效果仍需独立TDD证明，局部预检不得当Tier-1验收。

[六组来源实际重放](../notes/rom-renderer-source-replay-20261001.md)6/6通过、errors为空、
非降级；历史CFG验证依赖已解除。下一步聚焦92site参数到显示桥接的独立raw路径合同，
不是重做来源探索，也不是将85记录直接晋升。

[六来源身份与复用更正](../notes/rom-renderer-source-plan-20261001.md)：92site均有指令类
claim、证据身份吻合；六来源verifier后续已实际通过。此前直接追加旧renderer delta的建议已
取代：旧包是命令脚本，本次是显示文本，只复用发布投影框架及显示文本双parser。

[下一文本包去重与验收设计](../notes/rom-renderer-batch-plan-20261001.md)已冻结研究分母：
92site/85record/1,053B，无跨组或已有包交叠，仍全部unknown。建议一个同类包，
不得分池拆包凑Tier-2。旧1,668B是命令脚本、新1,053B是显示文本，不合计同类包。

1. 固定 renderer 文本：三处候选352+123+578=1,053B，先冻结完整来源合同，再TDD进入
   显示文本专用消费合同与公共发布框架；已有脚本1包/1,668B受管Tier-1不重复实现，不为小收益反复跑formal。
2. 458动画混合池：复用旧序列/descriptor语法，冻结7对base的完整caller、stack flags与
   slot生命周期；标签和文本另分合同。12EE的60条显示文本比RAM状态链更适合先推进。
3. bank/资源验收：与字节闭包同步推进严格typed样本及小bank矩阵；新受管证据处理
   battle-effect测试SHA漂移。随后扩固定分母，再做干净重建、UI、mGBA与真实硬件门禁。
4. 低脚本有固定索引才追加delta；AI、协程和RAM标签先闭合全部相关writer/index/lifetime。
   无新锚点的大簇登记搁置；不凭相似字节、邻接范围或假设自然执行扩大完成量。

新增[12EE混合池预检](../notes/rom-ram-protocol-tag-preflight-20261001.md)：115项形态中
69首调用renderer，去重60条578B假设；另25局部RAM标签初始化候选。emit固定读取14B，
match遇NUL、14B或不匹配停止；两者与显示文本不同，不统一按NUL或整池分类。
目前所有新候选promotion=0，unknown87,631B、175 blockers及Tier-1队列保持原值。
本次3个百分点是研究上限，研究结论已收敛，不必把剩余额度用尽；未来实现需另按授权范围推进。

## 大簇研究的取舍

后续[17段锚点筛选](../notes/rom-large-unknown-anchor-screen-20261001.md)补出两条可行动路线：
45832C..458794存在固定双base参数进入已有626B4 allocator，优先于开放AI生命周期；
12EE10..12F298有12B固定复制及RAM存文本指针路径，第二顺位，但必须追实际消费。
171,916B显式Thumb代码域的LDR形态及全ROM对齐word均只作筛选，不是来源/语义验收。
54136F、04BE31、5A4708三段本次零形态，登记搁置而非判定未使用。

[双base预检](../notes/rom-animation-base-pairs-preflight-20261001.md)进一步确认两样例使用
旧指针/序列/0x14条目语法；旧合同CLI重放通过。但flags bit8影响slot advance，不能
搬旧group域和0x54长度；下一步完整冻结该池固定caller分母、stack flags及slot生命周期。

[116项批量调用筛选](../notes/rom-animation-pool-caller-screen-20261001.md)更正该簇为动画/
文本混合池：局部44个固定group0调用去重7对base，另有11个旧renderer root合123B假设
文本；可与352B文本候选同类处理，但475B不是验收收益。动画与文本分合同维护，
完整来源、stack flags和record lifecycle仍须TDD实现前冻结。

有效bank的具体拆包见[严格完成债务与复用路线](../notes/rom-bank-proof-work-plan-20261001.md)：
11/22已有verifier命令，22/22缺严格typed合同、6处字段分母差异、3条命令含机器绝对路径。
map-sprites record1旧证据实际离线重放通过。先迁移单样本合同，再做cutscene 8×2和
map-sprites 43×2完整矩阵；不要等unknown清零才发现运行时证据仍缺。

除了上述有入口的方向，0A1954..0A2154（2,048B字体gap）、04BE31..04C616（2,021B
脚本gap）、5A4708..5A4CE8（1,504B）尚无完整消费合同。对它们只做一次批量来源索引
筛选：固定入口、指针出现及已验证消费者；无正向锚点就登记搁置，不继续猜格式。
54136F..542204（3,733B）与599924..599F5C（1,592B）分别有复杂索引/混合资源风险，
与AI/selector数据流共用调查，不另建凭物理步长推断的“表”。

## 复用、执行成本与批量审计

资源/发布的[实际重放及依赖方案](../notes/rom-release-gate-work-plan-20261001.md)已补齐：
七组固定slot验证实跑6/7，失败battle-effect仅测试实现SHA不同；后续以新受管证据取代，
保留旧manifest。干净重建不能用当前build suite代替，UI/模拟器/硬件分别保持固定分母。
六门19case仍为空，离线产物成功不等于严格全门完成。

1. 直接复用现有CFG raw verifier、renderer两套parser、来源身份固定、受管发布与
   coverage adapter；旧证据源码和manifest不改写。66EFC需独立消费合同，因为输出
   截断和控制字节处理不同；可共用字节读取/CFG基础能力，不能共用语法结论。
2. 新显示文本root绑定显示消费合同；复用发布/投影框架，不能沿用67158命令脚本语法。
   AI与协程是不同生命周期信任边界，分别维护依赖合同。
   本轮是相同背景下的串行规划，未启动子代理，不为占满并发而分派。
3. 脚本优先。合同、输入、停止规则、独立验收完全冻结后，才适用登记表的小包模型
   执行；模型工具未提供的身份不得假称可调用。开放式生命周期推理由主代理整合。
4. Tier-1严格TDD红绿重构、独立raw verifier、身份/重叠/unknown投影和失败关闭测试；
   涉及发布、adapter或CLI的变更必须集成测试。不是每包都跑formal。
5. 同信任边界达到4包、10KiB或0.15个百分点任一条件才Tier-2。0.15个百分点对本ROM
   约9,438B；只计算去重净增。晋升前固定immutable precoverage、双重稳定报告，再统一
   canonical/proof与一份formal。不得把P1/P3/P4异构证据硬拼以凑4包。
6. heavy命令使用同一`build/experiments/heavy.lock`；正式审计idle至少7200s，不能因
   静默反复重启。后续每轮先检查额度与Goal，预算是上限而非必须消耗的配额。

## 本轮验证与边界

库存脚本两次输出逐字节一致，重新累计unknown段、bank记录及gate集合；guard exit0且
非降级。首轮用过期摘要32点作断言而失败，原脚本/日志保留，后续按实际33点重算。
输入哈希及文档链接另行检查；没有新增功能代码，未声称执行功能TDD、运行时测试或
全量formal。未提交、未push、未修改ROM、coverage或proof。本方案无游戏UI入口，入口
是本文件和页首路线图；数据缺失保持“待证明”，不承诺工期或假定候选全部可闭合。

可执行验收：打开库存检查87,631B/1,763段与23/2,954；打开copy-consumer.txt检查66F9A
截断；确认Tier-1仍只有1包/1,668B；依P1先形成完整消费合同后才启动实现。
