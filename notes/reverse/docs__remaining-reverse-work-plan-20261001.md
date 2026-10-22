# 剩余逆向工作推进方案（2026-10-01）

> 2026-10-02 [地图完整批次重定位/真实构建](../notes/rom-map-resource-relocation-roundtrip-20261002.md)完成：
> 197冻结输入，保留166/变异166/溢出96/图像增1tile四批接受，五类拒绝均不发布ROM/report。
> 16相关测试、9真CLI、217旧槽/249引用/16MiB整ROM及fixture ledger独立核对；全变异余663,333B。
> 196非ROM输入持久化，仅供ROM的199文件迁移再次9CLI，全result精确一致；原slot拒绝仍成立。
> 只证明固定批次和空fixture父ledger、对齐u32引用，不证明任意子集/计算消费者/自然运行。
> 下一里程碑集中复验map41两类自然视觉旧证据及47×9分母，再接typed部分合同或新迁移A/B；
> maps与已否证encounter-zones分开，flags/其余map开放。canonical/proof/bank不变，Goal active。

> 2026-10-02 [地图全固定变异写回](../notes/rom-map-resource-fixed-roundtrip-20261002.md)完成：
> 184输入／166content／217slots／249refs，167真实build CLI；70接受（91slots/105refs）、
> 96容量拒绝无ROM/report，关联域独立重算全部通过。34图像变异全部溢出，不能认领图像任意编辑。
> 三个历史安全编码测试失配已修正，容量双重重建语义不变，旧receipt原样保留；27相关测试通过，
> 186文件迁移167CLI全result精确重放。下一闭环复用已有地图重定位器，对96溢出资源统一验证
> 分区/ledger/指针分母、所有alias及冲突；不另建allocator。runtime/UI/全graphics门保持开放。
> canonical/proof/bank不变，Goal active；3%门禁已取消，按用户授权推进至周剩20%。

> 2026-10-01 [四类部分 bank 集中复验](../notes/rom-partial-bank-joint-matrix-20261001.md)与
> [battle-effect 全固定变异写回](../notes/rom-battle-effect-fixed-roundtrip-20261001.md)完成：
> 141 输入／4 CLI／8 假声明拒绝，候选4/811单元；全bank门仍拒绝，正式0 typed保持。
> 容量证据按当前身份独立双重重建，语义不变；51输入、34content/35slots/36refs贯通35个
> 真build CLI，23接受（24slots/24refs）、11容量拒绝不发布输出；22相关测试、53文件目录
> 迁移全result精确一致。固定变异／无DB／无runtime，未完成graphics整体release case。
> 下一里程碑转map resource 166/217/249第二族，先审mutation合法域，再复用fixture/CLI，
> 域拒绝与容量拒绝分别记账；不继续逐字段微包。canonical／proof／bank不变，Goal active。

> 2026-10-01 [data-table-b 部分字段合同／可移植重放](../notes/rom-data-table-b-partial-bank-20261001.md)完成：
> 22 固定输入、1/79 text_ptr 单元、928 像素，23 相关测试与真实 auditor CLI 通过。
> 24 文件目录迁移在禁止源工作树／旧 Qt 读取及进程启动下仍精确重放；旧 manifest 不改。
> 两历史采集没有零输入对照和外层共享锁身份，限制明确保留；全量 bank gate 仍拒绝。
> 下一里程碑集中重放四类 partial 合同的 record×field 矩阵与依赖，不继续逐像素拆包，
> 再选择小 bank 完整矩阵／资源 round-trip 入口。promotion=0，canonical／proof／bank不变，
> Goal active，最近周剩25%，用户允许推进至剩20%。

> 2026-10-01 [完整renderer／body／序列边界验证](../notes/rom-animation-full-renderer-20261001.md)完成：
> 5集成tests、3,684完整调用／7,368轨迹，611输入、三来源verifier及永久444.13s精确重放通过。
> 3,020组body／664组隐藏或zero-scale；369组division SWI执行225,908步内置BIOS ARM代码。
> slot/timer与旧解释器一致，descriptor sentinel suffix未读；29条件caller接入，18项排除。
> 单活动对象、旧context快路径、人工transform，不证明自然多对象／pending重工作／全writer。
> 下一里程碑转data-table-b自然message0指针A/B的typed partial／79×1分母与可移植身份；
> 先审旧archive的scope与guard/control，不合现行合同就保留限制或补捕获，不扩全bank。
> promotion=0，canonical／proof／bank账本不变，Goal active，最近周剩26%。

> 2026-10-01 [对象／回调／完整排序／两层终止符联合验证](../notes/rom-animation-object-native-20261001.md)完成：
> 16tests、5,381原生轨迹，549输入、三来源verifier及永久167.61s精确重放通过。
> 管理器无匹配返回index10而非NULL；释放扫描保留20高位，复用保留旧context；真实callback已接线。
> 完整sort两深度字段、672序列差分和八descriptor head通过，body仍未执行，不认领496B候选。
> 下一包贯通62924完整renderer／body／BIOS arithmetic／返回，再回接自然writer域；
> 若自然域仍开放则转bank矩阵／round-trip。promotion=0，canonical保持，Goal active，最近周剩26%。

> 2026-10-01 [IRQ RAM／协程／内置BIOS联合验证](../notes/rom-animation-irq-arm-native-20261001.md)完成：
> 13tests、10,270原生夹具轨迹，447输入／70provider项绑定，永久60.63s精确重放通过。
> RAM入口勘误为03005CE8／03005D50；IRQ进入两真实回调，CpuSet进入固定内置BIOS。
> 协程r1/r2恢复交叉，wait1保留、wait0回绕255，不能签发上下文恒等或普通callee返回摘要。
> 下一里程碑合并handle/group/slot/timer、long callback后半与两层sentinel，复用原生内核；
> 自然入口／全writer／实机BIOS开放，promotion=0、canonical不变，Goal active、最近周剩28%。

> 2026-10-01 [动画save回调来源／保存恢复／freeze联合验证](../notes/rom-animation-save-source-20261001.md)完成：
> slot5真实注册85A08／literal85A14→8584C，三来源／lifecycle verifier重放；12tests、521raw状态、
> 11局部source group／350指令及永久46.68s精确重放通过。非零counter保存恢复，原0按空marker恢复为1。
> timeout清slot1–4 marker，精确扫描128对象、只active flags置bit3；stop在context／后续资源操作之前。
> 85880已有固定注册来源；68DE6仍由8F654未知入口阻断，不晋升。下一包合并IRQ／ARM／BIOS effects、
> object handle与同上下文恢复，不重复保存微窗口；全writer／自然域／bank开放，promotion=0、canonical不变。

> 2026-10-01 [动画writer分母／启动DMA／向量别名联合验证](../notes/rom-animation-writer-domain-20261001.md)完成：
> 16测试、512索引态与永久目录80.76s逐字节重放通过；两组来源verifier重放。
> 工作图88,472声明Thumb指令（非新增45组语义验真）、9,730传输，8,785地址未知仍保留。
> 条件启动DMA清零03000000..03007B00；向量u8索引29可影响counter，五直接caller仅0/2，
> 计算／ARM／间接producer未穷尽。saved初始化857B8接线，两个BL跨claim分区工具问题已修复。
> 下一包统一68DE4／8584C候选来源、IRQ RAM／ARM边界与handle／writer域，不拆孤立store；
> promotion=0，正式87,631B／175历史blockers／31与16条件统计保持。

> 2026-10-01 [动画对象初始化／分配／释放与counter联合验证](../notes/rom-animation-object-lifecycle-20261001.md)完成：
> 25测试、526人工状态、672旧trace差分与永久目录逐字节重放通过；四来源verifier重放，工作图67,243指令。
> 初始化仅清144个flags word；两allocator各128单free槽与全满分母闭合，disable后须scan清bit1才能复用。
> counter75有14ref／12实际来源／2候选，saved非零恢复原byte，不能假定全局0/1；排序前62816stop明确。
> BIOS路径明确拒绝，全writer／自然handle／alias仍开放。下一包统一counter/saved与关键字段writer域，
> 不继续孤立微窗口；正式87,631B、175历史blockers及31／16候选统计不变，promotion=0。

> 2026-10-01 [动画callback／critical writer联合审计](../notes/rom-animation-critical-writers-20261001.md)完成：
> 八入口有限来源假设、66,295来源指令，9测试／两组独立来源verifier与notes逐字节重放通过。
> long callback三处当前task写入在context区，14 unknown store保留；short22B仅候选根，未晋升。
> 活动列表在callback后重建，序列查表早于freeze；timer u16／duration signed16已绑定，
> counter03000075生产域、全writer／别名与handle生命周期仍开放。下一包联合counter、
> 128对象初始化／分配／释放复用域，不继续孤立保存窗口。正式87,631B及31／16候选统计保持。

> 2026-10-01 [动画子身份／固定dispatch联合重算](../notes/rom-animation-interprocedural-identities-20261001.md)完成：
> 两轮发现、23库根／21身份摘要，47双表不变，条件模型双字段25→31、缺口22→16，
> 新增六条callback0／flags0x20。63测试与永久路径234.1s逐字节重放通过。
> 6D964十槽dispatch独立重建且guard支配；9C574已对上既有协程ARM026C，恢复义务仍开放。
> BIOS、caller memory和92018软件effects保留边界；下一里程碑合并callback、critical writer、
> timer/slot域及两层sentinel，不继续孤立保存微包。promotion=0、canonical87,631B保持。

> 2026-10-01 [动画上游批量依赖枚举](../notes/rom-animation-upstream-closure-20261001.md)完成：
> 3轮发现／17packet，最后只重算一次64,926指令图；47双表重建，条件模型双字段22→25、
> 缺口25→22，新增三条callback0／flags0x60。48测试与永久路径53.8s重放通过。
> MOV PC LR返回已补齐，BX PC保持ARM边界；child寄存器递归接线、BIOS、dispatch、
> caller stack与完整生命周期仍开放。下一包合并17packet子身份、软件return、ARM与旧dispatch合同；
> 不把已枚举child当已签发effects，promotion=0、canonical87,631B保持。

> 2026-10-01 [五callee原指令保存／多层缺口](../notes/rom-animation-callee-effects-20261001.md)完成：
> strict6571C及四个带保存区前提的摘要重建，38测试／永久路径整图重放通过；8D580不保留r9。
> 47双表均重建，但双字段仍13／22；25缺口移到七目标，原五目标只是第一层，不是完整链。
> 下一包批量追完整上游callee／producer闭包及循环回边，到constant／entry／BIOS／别名边界停止，
> 不逐代冻结重算；随后联合callback、critical writer与两层sentinel。promotion=0，正式账本保持。

> 2026-10-01 [458 caller整图前驱／共享callee缺口](../notes/rom-animation-caller-predecessor-20261001.md)完成：
> 64,926来源指令／918根，两个保守模型都重建47条双表；13条双字段固定，allocator
> 条件保存模型为22条，private-frame／call恢复前提仍未证明，不是自然域闭合。
> 剩25字段聚合为626B4、6571C、66758、6F5BC、8D580五callee；18测试和notes整图重放通过。
> MOVS flags漏报及覆盖比较寄存器后错误收窄已按红绿修复；旧报告保留且标记取代。
> 下一包统一证明五callee保存／内存effects，再接两类callback、critical writer与两层sentinel；
> promotion=0，canonical87,631B及正式175 blockers保持，本包未重跑全局formal。

> 2026-10-01 [458 混合池 caller／flags 局部批量审计](../notes/rom-animation-pool-lifecycle-20261001.md)完成：
> 113 BL 形态中96项来源指令经9组独立 verifier 重放；47固定双表调用（45 group0／2 group1），
> 原44条均保留。新增第8个 descriptor，496B仅候选；12项 flags/callback同时固定，35项仍开放。
> mask应为0x8（bit3），且循环模式会读sequence sentinel后duration；19测试／672有限探针／
> notes路径重放通过。外部writer、完整callback和timer域未闭合，promotion=0，canonical不变。
> 下一包合并47条前驱与allocator跨调用保留规则、两类callback及critical-field writer，
> 然后统一两层sentinel边界；不拆成逐call微实验，也不整段认领混合池。

> 2026-10-01 [menu-ui 指针隔离与新收据](../notes/rom-menu-gfx-pointer-ab-20261001.md)通过：
> 旧内容样本用当前 renderer 重算/独立双验，payload 相同且旧 artifact 不改；新 record1/
> gfx_ptr_0 是独立指针 A/B，40 输入、43 raw 成员、5 个 c16 正确锁捕获、1 像素、1/630 单元。
> 26 项相关测试、受管发布、双重独立重建与真实 auditor CLI 通过，全 bank 仍拒绝。
> EWRAM 前128B只固定观察身份，语义未解；canonical/proof/bank-proofs 与正式0typed保持。
> 下一主线返回458混合池 flags/slot，旧 primary 的合同迁移留待批量，避免继续拆单像素包。

> 2026-10-01 [cutscene 自然调色板部分合同](../notes/rom-cutscene-secondary-ptr-contract-20261001.md)
> 已完成：45 固定输入、43 原始成员、8×2 完整分母中的 ID 1 / secondary_ptr 单元；
> 三零输入与两单输入由正确共享锁重跑，778 像素且只改 PRAM 一字节，31 相关测试通过。
> 独立双重重建、受管发布和真实 auditor CLI 通过，完整 bank gate 仍拒绝部分覆盖。
> 旧捕获错误锁与笔记地址错误已明确取代/更正；canonical/proof/bank-proofs 未变。
> 下一步 menu-ui 新冻结样本及旧 primary 的部分合同迁移；458 动画 flags/slot 仍待闭合。
> 下方保留阶段历史；早先“捕获完成、语义验收待补”已由本条取代。

> 2026-10-01 [cutscene secondary_ptr 输入与捕获](../notes/rom-cutscene-secondary-ptr-ab-20261001.md)：
> 隔离指针 A/B 与相关 8 测试通过，三零输入和两单输入 mGBA 捕获完成；观测 778 像素、
> 仅 PRAM 0x05000382 一字节改变。缺库已按同 commit 库核对/审计恢复，原失败证据保留。
> 独立语义 verifier 与正式发布待下一包；不增加正式 bank/canonical 覆盖。
> [旧 bank runtime 批量重放](../notes/rom-bank-runtime-replay-20261001.md)实际 10/11 通过，
> menu-ui renderer 身份漂移，需新收据；旧 formal 的 175 blockers 不是新全量运行结果。

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

原始研究阶段已结束：当时授权约3个百分点，只规划而未实现。用户后续已取消这一
门禁，当前 Goal 授权推进至周剩20%；不以用满预算为目标。原研究收据保留在
`notes/evidence/reverse-work-plan-20261001-v1/`，最新实现与验收状态以页首里程碑为准。

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
