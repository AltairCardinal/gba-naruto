# ROM 字节级语义逆向当前交接（2026-09-05）

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

> 2026-10-01 [显示文本受管Tier-1](../notes/rom-display-text-delta-tier1-20261001.md)通过：
> 92site/85record/1,053B/85claims，最终56输入，18项测试（含真实CLI）与稳定双重重建通过。
> live unknown投影独立收据通过；新显示文本1包与旧命令脚本1包分开，库存总2,721B。
> 未达同类/净增门槛，不做Tier-2；canonical87,631B/175 blockers不变。下一步动画与bank。

> 2026-10-01用户取消3%研究门禁并授权推进至周剩20%；Goal active，恢复时周使用52%。
> [显示参数TDD实现](../notes/rom-display-text-parameter-flow-tdd-20261001.md)9/9通过，
> 92真实ROM路径/559指令出现的raw参数证明稳定重放；下一步完整显示合同与managed发布。
> 尚未新Tier-1或promotion，canonical/proof及旧脚本1包/1,668B保持，未提交。

> 2026-10-01 [显示文本局部路径成本](../notes/rom-renderer-flow-cost-20261001.md)：
> 92条路径各4～7指令，共559次出现；全部路径在自身instruction claim内，75/17走两桥。
> 下一包可用有限Thumb raw效果verifier，避免动态/通用符号执行；只是研究，尚未参数验收。

> 2026-10-01 [六来源语义重放](../notes/rom-renderer-source-replay-20261001.md)6/6通过，
> errors=[]且非降级；首轮采集误读guard的问题及修正原始产物保留。
> 下一步只需补新literal到显示桥接路径及文本合同；尚未Tier-1，canonical/proof/队列不变。

> 2026-10-01 [六来源核对/复用更正](../notes/rom-renderer-source-plan-20261001.md)：
> 92site全部指令类owner，六组CFG证据/manifest/verifier身份吻合；语义重放仍缺。
> 旧1,668B是67158命令脚本，新候选是直接显示文本，不能追加旧语法或合计同类包。
> 双parser与发布投影框架可复用；更正仅影响方案，canonical/proof/正式队列不变。

> 2026-10-01 [下一文本包验收设计](../notes/rom-renderer-batch-plan-20261001.md)：
> 92site/85record/1,053B研究集合，与既有包无交叠；完整来源raw验证仍缺。
> 规划单一同类包，禁止拆包凑里程碑；canonical、proof及正式队列不变。

> 2026-10-01 [研究执行顺序](../notes/rom-ram-protocol-tag-preflight-20261001.md)：
> 60条renderer候选578B，三池共1,053B假设；另25 RAM标签路径需stage/共享writer证明。
> 研究已收敛：先固定文本合同，再动画生命周期；同步bank/资源严格验收，复杂状态路线后置。
> 本轮仅研究，promotion=0；canonical、proof及1包/1,668B队列不变，未提交。

> 2026-10-01 [116 literal批量调用](../notes/rom-animation-pool-caller-screen-20261001.md)完成：
> 45832C池是animation/text混合，44局部fixed group0 calls/7对base，11renderer roots合123B假设。
> 下一步分别冻结文本来源合同和animation stack flags/slot生命周期，不把整段认领，未新晋升。

> 2026-10-01 [双base用途](../notes/rom-animation-base-pairs-preflight-20261001.md)确认：
> 626B4的新458池样例和旧包共享pointer/sequence/0x14语法，旧verifier本次实际通过。
> 下一步批量caller参数域与flags bit8/slot证明，不沿用旧0..2槽域或0x54长度，未新晋升。

> 2026-10-01 [大段消费锚点](../notes/rom-large-unknown-anchor-screen-20261001.md)已归档：
> 45832C..458794两对固定base调用626B4，allocator SHA匹配旧合同；12EE10有12B复制及RAM
> 存指针路径。下一轮优先完整固定描述器合同；计数不是消费者证明，所有大段仍unknown。

> 2026-10-01 [资源门禁重放](../notes/rom-release-gate-work-plan-20261001.md)实跑6/7；
> battle-effect implementation mismatch已定位为test_import_battle_effect_resources.py历史SHA漂移。
> 没有改旧manifest或扩大gate声明；完整方案已包含字节、bank矩阵和发布依赖三条主线。

> 2026-10-01 [bank债务矩阵](../notes/rom-bank-proof-work-plan-20261001.md)已冻结：22有效bank
> 11有verifier command、0严格typed合同、6字段分母差异；map-sprites旧样本离线重放通过。
> 原始证据/命令身份均吻合，未增加records_covered；后续先合同迁移再小bank矩阵。

> 2026-10-01 [文本路径预检](../notes/rom-fixed-text-route-preflight-20261001.md)双次重放一致：
> 13/1/2/2/2/1六类，假设482B不是Tier-1收益。先验已有14site/352B桥接；
> 90A20 wrapper保存义务未闭合，66EFC仅22B暂缓新合同；正式队列和账本未改。

> 2026-10-01 用户授权约3个百分点周额度的路线研究已形成
> [剩余工作方案](remaining-reverse-work-plan-20261001.md)，不启动新实现或全量审计。
> 下一包建议绑定v15–v21固定文本入口；screen落盘实际33点而非旧摘要32点，
> 21个文本簇候选尚未语义验收；66EFC的计数截断/byte1消费须独立合同。
> 本轮无新promotion，canonical87,631B、正式队列1包/1,668B不变。

> 2026-10-01 [受管renderer合并包Tier-1](../notes/rom-renderer-records-delta-tier1-20261001.md)通过：47site、29record、1,668B/29claims；10项完整回归+1项inactive-run检查通过，真实CLI及双重稳定重放/实际unknown投影通过。
> 原12B错误发布包保留历史，由同一raw-input合并包取代；当前正式待接入1包/1,668B，保存在唯一受管final，未promote。canonical87,631B、175 blockers保持，未提交。

> 2026-10-01 [后续CFG renderer消费者预检](../notes/rom-later-cfg-renderer-consumers-preflight-20261001.md)：v1/v3/v6三来源raw verifier通过，36site双参数流、27record双parser一致，共1,656B候选。opcode6使用RAM文本而非inline，六新opcode根仍排除。
> 候选尚未Tier-1；下一步TDD批量旧语法包。12B包静态通过但直接artifacts发布门需补正，正式可接入队列暂0包；canonical87,631B、175 blockers保持，未提交。

> 2026-10-01 [低地址脚本增量Tier-1](../notes/rom-low-script-delta-tier1-20261001.md)正式验收：六site分母、两条record、12B/2claims，8/8含真实CLI与coverage adapter集成测试通过。
> 待Tier-2累计1包/12B；canonical unknown仍87,631B，全局175 blockers保持，opcode2/6和7/8生命周期仍开放，未提交。

> 2026-10-01 [共享任务记录预检](../notes/rom-coroutine-record-lifecycle-preflight-20261001.md)已归档：固定8记录模板与slot0 marker，7C61C/coarse owner和全局恢复链仍开放，125B候选暂不晋升。
> 转向[低地址固定消费者](../notes/rom-low-script-fixed-consumers-preflight-20261001.md)：6 site、两套参数流/语法重放，得到12B旧语法候选，尚未Tier-1；canonical87,631B、Goal active，未提交。

> 2026-09-30 [renderer handler原始图与任务上下文依赖](../notes/rom-renderer-handler-context-preflight-20260930.md)已复现：7/8含早退与9C574→ARM026C的SP保存/恢复；16/16测试通过，缓存漏检已修复。完整续读合同仍开放，125B候选未晋升，unknown87,631B，Goal active。

> 2026-09-30 脚本五根预检完成：[推进形态与语法候选](../notes/rom-renderer-excluded-roots-preflight-20260930.md)，6/6含真实CLI测试通过；125B只是候选，完整7/8 handler合同未闭合，promotion=0。
> 上轮[extra pool复制与成对CD写入](../notes/rom-ai-extra-pool-lifecycle-preflight-20260930.md)已稳定重放归档，生命周期仍开放；canonical unknown仍87,631B，Goal active。

> 2026-09-30 四包Tier-2验收完成：真实净增118B/21claims，unknown87,631B。
> coverage与formal均exit0、非降级；完整formal 107/107合同通过，ROM97/97，
> coverage errors=[]，global complete=false、175 blockers保持。新增永久formal收据
> 与3/3集成测试通过，见[本轮验收记录](../notes/rom-small-cfg-dependency-tier2-20260930.md)。
> 当前无running heavy，恢复读acceptance run的resume-state-after-formal.json，勿重跑已完成审计。
> [AI入口](../notes/rom-ai-entry-local-domains-20260930.md)7/7测试通过，
> [渲染脚本依赖](../notes/rom-ai-renderer-script-dependencies-20260930.md)复用两条preplanner
> 参数流与已分类脚本；postplanner两点尚缺指令owner，82B只是待查窗口，promotion=0。
> Goal active、最近余量55%，停止边界40%；未提交、未push。下文旧状态为历史基线。
> 后续[入口分母与单位池别名](../notes/rom-ai-producer-and-pool-alias-20260930.md)：
> 五目标整ROM raw scan仅9个BL，B/Bcond/ARM/精确指针均0，独立复验一致；
> slot13地址等于extra pool slot0，初始化不提供CD==0保证，须合并其复制/继承生命周期。
> 本轮仍promotion=0，静态字样分母不能关闭computed/RAM入口。



## 最新恢复点：A/B/C已提交，干净检出的证据闭包验收通过

- A=`47d9a60e668a5c3fe6e1123524864d21a2c93545`：固定历史身份验收包，91文件。
- B=`80faaebd2d441e94afbe7f0c7921609659f4d0fe`：ROM证据闭包，835文件；85项既有
  工具回归、430个Python源码编译通过。两处历史exporter行尾空格因原artifact固定源码
  哈希保留，例外及原始诊断已归档。
- C=`37bfe8bc40479040f25a5ab57960a8d3c9623c6f`：补三份原始运行合同与初始化，36文件。
  11项TDD/consumer集成通过。新检出必须先运行
  `python3 tools/prepare_rom_verifier_contracts.py --restore`，详见checkout setup文档。
- 干净C：68/68测试、64历史根/160个Git成员、282固定输入的逐字节gzip重建通过。
  独立报告SHA `42e1d5628834efdf871a175d20feeba66d915b63daae66d669ac710f9821577c`，
  重建包SHA `184f34a1871e7d451b429ecab0c6e1b9502080665e96db5290ac108d25fa0b93`。
  最终guard10:45:01Z–10:45:39Z成功，无降级，峰值406.28125MiB；clean git status为空。
  初次B缺合同及初次C脚本将无关submodule误当blob的失败均保留，没有覆盖原始日志。

永久收据：`notes/evidence/rom-committed-artifact-acceptance-20260905/`，56文件加manifest，
manifest SHA=`8272ca6c8f2dc634dabf625e0eddc14f4a18b077d9d6d513c4d6aff53d26b3ba`；
运行输入TDD收据另见`notes/evidence/rom-verifier-runtime-inputs-20260905/`。
提交run为`build/experiments/active/committed-artifact-acceptance/post-selector-repair-20260905/`，
`clean-checkout`仍在C，可复用；`clean-c-v2-receipt.json`固定全部提交、输入及结果身份。
当前余量73%，没有running heavy；主index为空时再开始下一包。本仓库无持久hook，
各次提交均用`git -c core.hooksPath=.githooks commit`显式启用现有入口，未push。

canonical/proof仍为1c6af01a…df584b6 / c2862ea5…4857cbb，6,203,707 classified /
87,749 unknown。123项selector修复后的完整formal在08:40:40Z–09:21:38Z成功结束：
106/106 contracts、ROM96/96、coverage errors=0，非降级，global complete=false/175 blockers。
永久报告/guard位于notes/evidence/rom-evidence-selector-repair-20260905，SHA分别为
`aa125c7e80ea4364522698c04557b3d6a819f77000c28c58871bc74cf13938bc` /
`3e1722f8979fa68723acf3e5940cf7eacd5beaabde6d19c2c14bf277a6736c54`。
提交复验只补原始运行输入，已核对正式输入字节一致；没有重跑已结束的full formal。

最新候选恢复点：59EAE0 的最小局部 may-read 域已由独立 raw verifier 复现，26/26测试
及两次稳定report通过；候选1,145B/162ranges（256lookup+889record），overlap2,583B。
旧“前22B/2,500B”估算被零flag和首个callee前stop否决。C1仅0..503行前6B；C2仅
0..255行的+7，以及192个非零flag行的+6。该结论只属显式局部机器状态的存在性witness，
不证明must-read、前序callee保存寄存器、自然可达或物理表边界。canonical仍87,749 unknown。
run为`build/experiments/active/strided-logical-read-domain/base-59eae0-preflight-20260905/`；
`luna-packet/tier1-candidate-receipt-v3.json`和`snapshots/tier1-v3/`可恢复。
后续父级复核否决接入：组合持久RAM索引的lifecycle门未闭合，keep_unknown、promotion=0。
不能靠may-read标签或accepted wrapper解除AGENTS的08F654 producer frontier门；该包移出
待接入队列，暂停其抽象索引扩张。前述1,145B仅是局部实验交集，不计批次收益。
详见`notes/rom-strided-prefix-local-read-domain-20260905.md`。当前余量71%、无running heavy，
下一步按批次处理task-callback 10B边界、三个wrapper 54B及dispatcher 40B候选。Goal保持active。
下文预检和旧106/96结果为历史过程，由本段当前状态取代。

## 当前恢复状态

- 当前 Goal task：`01a06ff8-6905-78c1-9c36-ad357340ec4d`，用户确认后为 active，目标
  `unknown_bytes=0`。恢复前仍须实时读取 Goal、账户余量、存活代理、Git 与 heavy lock。
- 2026-09-05验收包A提交前账户 `usedPercent=26`，可验证余量74%；不高于5%时停止
  新逆向写入并保存恢复状态。未使用 reset credit，未获 push 授权。
- 逆向工作树 `/Users/altair/github/gba-naruto-reverse`、分支 `codex/reverse-engineering`。
  Butano 工作树未触碰。主代理唯一 writer；Luna/Sol 在本轮只读分析和复核。
- 原 Goal 暂停时76,122,071 tokens / 884,320秒，仅作历史计数，不能与当前 Goal 用量
  混合或伪造逐模型明细。旧交接全文保留在下述 run 的 `.before-tier2-doc-update` 文件。

## 权威 canonical 与当前验收

| classified | unknown | claims | segments | 分类率 |
| ---: | ---: | ---: | ---: | ---: |
| 6,203,707 | **87,749** | 16,891 | 18,664 | **98.60526720682780%** |

- ROM：6,291,456 bytes，SHA-256
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- coverage SHA-256：
  `1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6`。
- proof SHA-256：
  `c2862ea520a39432c94fa2634f2ae5650077738c9474aa96ca15d387a4857cbb`。
- 本批四包已真实接入：fixed-index u8 tail 4B/1claim、story-selector dependency
  80B/1claim、task callback078E38 closure 778B/16claims、V21 116B/3claims。
  净增 **978B/21claims**，不是旧 canonical 加估算。CFG aggregate 为956 ARM、
  173,058 Thumb code bytes、174,046 promoted bytes、4,059 claims、54 kinds。
- coverage guard于06:01:04Z–06:32:46Z成功，exit0、非降级，峰值452.63671875MiB。
  真实canonical/proof/持久收据集成9/9通过。
- 修复前历史formal已成功：106/106 contracts、ROM gate96/96、coverage errors=0，
  06:38:31Z–07:20:01Z，非降级、峰值530.18359375MiB。完整报告仍为
  incomplete / 177 blockers。Tier-1队列归零；committed-artifact门仍待历史格式迁移。
- formal report / guard SHA-256：
  `099580ad012729bbce697779cae732ef8678a0966c2669dad51cce0f58f79f00` /
  `735b9505208758cd009c77d9a59d84f076d47181c9f2fb920d3bd4519f80d891`。
  这次历史run已结束；当前修复后的新formal已通过，见本文最新恢复点。

本批 run：
`build/experiments/active/direct-root-overlap-cfg/root-063400-tier1-20260905/resume-20260905T052627Z/`。
永久收据：`notes/evidence/rom-post-story-four-packet-tier2-20260905/`，manifest逐文件绑定。
新集成测试读取永久路径，不依赖被Git忽略的实验目录。

## V21 的证据与边界

复用固定direct producer + bounded CFG模式，root063400，70 instructions、17blocks，
144 full code bytes、4 literal bytes。只接受06108A producer；06131C的coarse
consumer_code_slice不能作为instruction membership。旧owner切过06347C的BL，完整
解码后只晋升unknown后半；净112code+4literal=116bytes。06348E间接frontier保留，
structured return=0；不证明opaque callee栈/内存副作用或自然运行时可达。

- manifest SHA：`b9625a5e45c66bc510deb2a83ceb01882c6ef4fd381ef28fc499d83ec2680f62`。
- payload SHA：`4dba6f7d880a790d92045d838eb78dd253f512d8d3a42b2c3858acf1187c1f9c`。
- verifier SHA：`6d20f681fdd033f2ce25a10ef4d512bc898c9a4b7f97d40adf75f0f3d9a59c7d`。
- 两次稳定report SHA：`4611b27fc0bc643f1de3062f75adf7c52de2e1d51b1fcee1f2078058d88003c8`。
- 本轮按TDD关闭candidate误验收及成员替换竞态两个P1，packet15/15；原始失败日志保留。
  完整经过见 `notes/rom-cfg-proven-roots-v21-20260905.md`。

## 提交闭包预检（修复前历史）

1. 首先实时检查Goal/账户/代理/Git。恢复点 `resume-state-after-tier2.json`，独立index
   `candidate-index-v2/v3`只保存失败预检；主index仍为空。不要将其直接复制到主index。
2. 当前ROM证据提交闭包候选为2,631文件，其中756变化（731新文件+25修改）；均有
   claim/proof/manifest/import引用来源。32-bank动态路径已显式补入，231个未解析token
   经只读核对是fixture/可选输入/推导测试名等，不能盲目创建对应文件。
3. `candidate-staged-policy-v3.log`记录64个历史root/149errors：schema42、status27、
   verifier现代收据64、库存格式16。现有证据桥梁分为32个proof直接verifier、21个
   aggregate调用独立verifier、11个仅绑定gzip/raw baseline。最后一类不能叫每根语义verifier。
4. 必须先冻结历史迁移合同：保留旧manifest原SHA，固定完整成员路径/mode/size/SHA；
   分别绑定直接command/script/contract、aggregate每包verifier/report或baseline原始身份。
   新机制必须TDD、独立verifier、staged Git objects验真及父级复核。尚未实现任何豁免；
   不可改旧manifest哈希伪造modern receipt，不可绕过hook，也不可把任意allowlist当语义证据。
5. 门禁修复已提交`e4b626462`，11/11集成测试通过，独立差量review无新增P0/P1。
   只在迁移和最终路径/hash快照验收后，按精确changed paths提交ROM证据。路径清单包含
   未变tracked依赖，stage时只选实际变化，避免既有ignored目录的无关pathspec拒绝。
6. 更新后的notes和formal收据会使旧v2清单部分哈希过期；最终提交前生成新编号快照。
   旧scene-source precoverage的test生产哈希与当前archive重放测试不同，这是已记录历史
   转换；不可改历史manifest伪造生产身份。两个既有全局gate中的sequel/project.json
   旧hash一字符差异已在selector修复包关闭，并由新的formal重新验收。
7. 本地提交只在相关闭包范围内，push仍需单独授权。保留全部用户已有修改与失败收据。

## 下一批候选（均未晋升）

- 三短入口07ADE8、07B89C、09C12C：21instructions、46code+8literal=54B，5claims
  候选；两个2-byte holes继续unknown。已核对15个已知producer子集与两个opaque
  target的精确artifact块；仍需guarded全ROM target-limited producer分母和新冻结baseline。
  Luna max只读尝试未返回可验证结果后中止，Sol medium完成机械核对。
- dispatcher07DCB8：consumer上界#0x13提示20slots，既有table只认领19slots；候选
  prefix26code+4literal、末slot4B及新target6code=40B。需完整raw dispatcher/index
  及opaque目标边界合同，不能改写旧19slot证据或吞2-byte hole。
- callback07B8B8：pointer07C634→consumer07C612→call07C61C→registrar061D8C，
  callback/arg写入061DC0/061DC6，在061C68/061C6A读取并由061C6C→09C114的BXr1
  调用。但小窗无法证明[r6+1]为二值，固定slot2/3及wrapper索引域仍未闭合；入口仅58B
  候选，不能把整个2088B包络晋升。
- 53F89C..541368与54136F..542204两个大段没有可冻结consumer/index，零比例、伪LZ77
  头或0xAC步长形态不能分类。训练表和低脚本池同样必须补实际索引/字段写入域。

候选细节和read-only报告在同一run的 `next-candidate-scout.json` 与
`candidate-review-followup.json`。下一包仍以脚本优先；公开合同完全冻结后才交Luna max
小包，Luna不适用的可拆只读任务用Sol medium，本体负责最终证据链和验收。

“100%”只表示每字节都有可复验分类且unknown为零，不等于全部动态业务命名或续作发布
门全部完成。当前仍有87,749 unknown，本Goal未完成；后段缺少充分样本，不新增工期承诺。
