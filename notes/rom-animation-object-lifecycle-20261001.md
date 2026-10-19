# 动画对象初始化／分配／释放与共享计数器联合验证

> 后续联合writer分母、启动DMA与向量别名见[2026-10-01继承包](rom-animation-writer-domain-20261001.md)；
> 本记录保存原25tests／526states／672trace身份，下文下一步为当时计划。

状态：固定来源与人工 RAM 状态闭环完成；自然对象域、全 writer、别名、BIOS 和协程恢复仍开放。
沿用登记表的固定 BL／混合动画池模式，脚本优先，无子代理。永久收据：
`notes/evidence/rom-animation-object-lifecycle-20261001-v1/`，41 成员，manifest SHA
`7c34067d76ae81ecc15d03b9681295e78ac8971df2d05e59c024e3a69c12db8b`。
权威 `lifecycle.json` SHA `2a9422fc79e004db15fa6402abe1c32a73e7178335dd66235034216871ef748a`；
`source-additions.json` SHA `f9ae16c775ad19e23dec36fba27bc517e55c75cde0e64a5eb23746d7290a6464`；
原 literal 盘点 SHA `d65dd6f3802bb97917714446b746930eb9d193181c77d3dedc62c3edeecbf123`。

## 复用与验证边界

直接复用前包 54 成员来源图／固定输入检查和旧 advance probe，不另建自然运行模型。
旧 probe 的入口、对象地址和 literal 域硬编码，无法直接执行两个完整对象池的初始化；
本包从它抽取共享 `bounded_thumb.py`，保留旧 `probe` API，扩展当前固定来源所需的
PUSH/POP、SP 调整、减法、MUL、STRB 与条件分支。所有入口 wrapper 共用同一执行器。
这解决逆向者对初始化、两个分配器与推进使用不同执行模型的问题，不改游戏用户入口。

每次取指必须属于指定 CFG 指令成员，ROM 读取逐字节列入允许域，RAM 仅有显式 fixture
字节；未对齐访问、缺来源、未知 opcode、ARM interwork、未授权 callee 和预算耗尽均拒绝。
返回哨兵与入口／来源重叠也拒绝。它是有限 Thumb 子集，**不是完整 ARMv4T/GBA 模拟器**；
不支持的 BIOS 不设 no-op，不声明所有指令／不可预测 flags 行为已模拟。
synthetic 算术测试用独立整数 oracle 检查 3 类操作×8 组输入×14 条件及 6 个 shift 边界。

固定人工 SP=`03007000`，对象池=`03003BB8..030059B8`，128×`3C`；
另一池=`03003078..03003BB8`，16×`B4`。fixture 中它们与私有栈 disjoint，只是人工前提，
不能替代自然 SP／handle／callback alias 的证明。参数故意含高位和不合法自然 group，
仅检查截断和写入；分配器返回这些指针不意味着 descriptor/sequence 索引合法。
另一分配器使用明确填充的人工 RAM 表 `03007200`，不是 ROM 资源表的消费者合同。

## 来源固定与 literal 分母

先重建旧 66,295 来源指令，再实际独立重放四组 verifier：

| 本包来源验证 | 固定指令／新增 union | 用途 |
| --- | ---: | --- |
| CFG inventory v2 | 40,872；已在旧图 | 两 allocator、初始化、filter、counter restore |
| boot Thumb handoff | 583／583 | 6101E、653A8 等真实 counter consumer |
| boot interwork continuation | 29／29 | 610A2；仅 Thumb promotion code，不把 ARM 字节当 Thumb |
| story-state callback | 336／336 | 8F746 literal 与 8F74A 写1 |

union **67,243 指令**；948 是已有受证来源新增到本次工作图，**不是新 ROM 分类字节**。
63 当前输入身份（ROM、canonical/proof/bank、artifact、实际导入 verifier/helper/vendor）
在执行前后比较；前包 manifest 与成员及 source_inputs 也核对。
本轮主批次和永久重放各四次 verifier，合计八次调用，不是八个新来源合同。

可复现盘点对 `03000070..0300007F` 与 `03000000` 先枚举全 ROM 逐字节指针出现，
再枚举全部 halfword 的 raw PC-relative LDR 形态：313 word 出现／42 ref 形态。
03000075 自身 **14 出现／14 ref**，扩展来源图中 12 ref 有实际指令 membership，
另 **68DE6、85880** 保持候选。诊断 `counter-windows.txt` 是线性显示，可能从半条 BL
开始或穿过 literal；不能把显示行当 CFG/source 证明。

| 03000075 ref | 已确认关系／边界 |
| --- | --- |
| 6101E、610A2 | 主流程读取／传参，不能视为写入 |
| 6323A、632E4 | 推进读 byte；旧 sentinel suffix 风险保持 |
| 653A8、67D1E、95FD4 | 用 byte 增量更新另一字段，未直接写 counter |
| 66516、666BC、96F9E | 和1比较，选择协程参数；不证明 byte 只能0/1 |
| 85806 | 已有 root857E4 从03005E2D恢复 counter，条件见下文 |
| 8F746 | 已验真的 story callback 在8F74A写1 |
| 68DE6 | raw候选68DE4..68DF8中出现写1；缺受证来源，不晋升 |
| 85880 | raw候选保存当前 counter→03005E2D，再写1；缺受证来源，不晋升 |

基址03000000的 raw ref 为61538、624C8、62514；其他基址、地址运算、IRQ、BIOS、
DMA／批量清零、跨对象 alias 尚未穷尽。literal 分母不是全 writer 分母，不能因只见
常量1或某个场景给出的“mode flag”名称，就把共享 byte 定成全局0/1域。

## 原指令状态结果

`lifecycle.json` 保存 **526 个有限状态**的输入、全 trace／memory SHA、step/read/write
数量、SP／return／stop，完整 trace 可由脚本重建；不把大量重复内存拷贝写成 ROM artifact。

| 状态族 | 数量 | 独立 oracle／结果 |
| --- | ---: | --- |
| 初始化62560 | 1 | 144 个指定 flags word 清0，其余非栈 poison 字节逐字节保持 |
| 直接 allocator626B4 | 128 | 每次仅一个 free slot，遍历0..127，返回该 slot，恢复r4..r11/SP |
| alternate625A4简单双表路径 | 128 | 相同 slot 分母，人工表 entry 生效，恢复r4..r11/SP |
| 两 allocator 全占用 | 2 | 返回0，不写 pool；永久复验精确检查各128次flags read倒序，无第129项 |
| active scan627B0 | 3 | 全inactive／全active／混合128槽，精确列表及count0/128/64 |
| disable→保留→scan→分配 | 4 | slot127真实 helper 与扫描接线，不跳过中间保留阶段 |
| restore857E4 | 256 | saved逐一0..255；saved非零时原样恢复，saved0保留counter173 |
| restore guard错误分支 | 4 | counter/saved保持；wait byte增量及255→0截断 |

初始化 raw loop：62568..6257A 对 n=0..127 写 pool+n×60 的第一个word；
62584..62594 对 n=0..15 写另一池+n×180 的第一个word。实际1,435条执行指令、146
store，包括2个PUSH栈word和144个flags word；不清 group/slot/timer/table/callback/context。
因此“初始化过”不能换成“所有残留字段均0”。未研究完整自然启动下的初始化顺序。

两 allocator 搜索条件是 flags&3==0，倒序检查128槽。直接 allocator在人工参数下有
16个object store／38B，另外22B保持旧值，包括+1A..1B、+24..27、+2C..3B。
flags写 caller flags|1；u16/u8截断、group+14、slot/timer=0、desc+1C、seq+20和callback+28
分别核对。alternate 简单路径按 index×8 查表；flags&400000 的四word路径到62696
真实 BL9C0DC就拒绝，不能把已写入部分和 stub 成功算作完整 allocator 验证。

停用62788：`(flags & FFFFFFFE) | 2`。原active task A0000001→A0000002，立即分配
仍返回0。随后真实 scan 的 inactive 分支62800..62806以 FFFFFFFD清bit1，得到
A0000000，此后可重新分配。这是有明确其他槽占用／无外部 writer 的人工联合链。
scan重建列表按 slot 升序；**stop62816是在排序阶段之前**，不是普通函数return。
完整排序、其后consumer、callback与扫描之间的所有 writer／handle同步未验证。

restore root857E4：当 `[030009E8] & 3F0F == 303`，先清03005E4A；
saved=`[03005E2D]`非零时85808 STRB写counter，再8580A清saved，返回1；saved0
不写counter。其余分支按截断u8 argument决定wait是否+1，wait>3B时返回2，否则0。
256人工保存值验证说明 parser/执行器没有擅自收窄保存字节；它们不是自然可达256态证明。
saved的初始化／所有生产者仍待闭合，不能据此宣称天然counter是任意byte或仅0/1。

## TDD、复验与保留失败

11项新增测试先因缺 lifecycle_probe 模块正确失败，再最小实现11/11通过。共享执行器
抽取后接入旧10项advance测试与4项ISA/boundary测试，最终 **25/25**。首次alignment
fixture默认返回哨兵等于synthetic root0，发现执行器静默返回；更正fixture后alignment等
测试通过，专门collision回归真正red（3pass/1fail），最小修复后25项全green。
这个探针BUG已修复；不是游戏BUG，也不把误设fixture日志算成独立ROM否证。
旧实现、fixture、red/green与版本映射都在41成员收据中，历史日志不覆盖。

随后用新共享执行器重跑旧672条advance人工轨迹，先以旧实现核对原 trace SHA，再
逐字段对比新旧完整输出，全部相同；旧API与sentinel/freeze/timer语义未因抽取漂移。
这些是旧人工轨迹的差分回归，不是672个新自然 runtime／mGBA捕获。

主批次108.50s／峰值234.74MiB；永久目录重放108.46s／197.47MiB，均显式
`build/experiments/heavy.lock`、非降级exit0，25tests、526states、672trace、4fresh
verifier与四个输出逐字节相同。永久入口另外核对实际导入的wrapper路径及两allocator
精确128次读分母。AST／脚本行尾空白检查通过；两个 owned run都completed。

复验：在逆向工作树根选择新的 CHECK_UNIQUE，约两分钟，结果只写新的受管目录：

```sh
python3 tools/experiment_workspace.py --root . init --task animation-object-lifecycle-replay --run-id CHECK_UNIQUE
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/animation-object-lifecycle-replay/CHECK_UNIQUE/guard.json --wall-timeout-s 240 --idle-timeout-s 120 --max-tree-rss-mib 1536 -- python3 notes/evidence/rom-animation-object-lifecycle-20261001-v1/replay_receipt.py build/experiments/active/animation-object-lifecycle-replay/CHECK_UNIQUE/output build/experiments/active/animation-object-lifecycle-replay/CHECK_UNIQUE/replay.log
python3 tools/experiment_workspace.py --root . complete --task animation-object-lifecycle-replay --run-id CHECK_UNIQUE
```

## 下一里程碑与完成边界

应统一追踪counter/saved byte、pool关键字段及批量基址writer，再接callback／IRQ／BIOS
alias和合法handle域；两个raw候选须有真实producer根与source合同后才能纳入。
在同一包里回答 init→reserve/release→reuse→lookup 的不变量和counter域，避免继续
把几字节保存窗口分别冻结。若全writer／自然域仍不能证明，保持候选，不接入bank合同。
原31双字段候选／16缺口没有重算，source扩展不替代callee／协程／caller SP+48义务。

canonical SHA仍 `b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`，
unknown87,631B；proof SHA仍 `465a13104b6c9a6d0ea418ca513dd0be732438634f1124a3a531c893b11db568`；
bank SHA仍 `f52524fbba244cf0497ffa021503702da9a185485c13027872f2a65dad56bed2`。
175 blockers是历史正式结果，本包未重跑formal；新Tier-1／canonical promotion／mGBA／
hardware均0。未提交、push或修改Butano。Goal active，周剩33%，20%预算边界继续有效。

### 【功能特性】
- 从本记录和收据查看两个对象池的初始化、两allocator、释放复用和counter restore结果；仅用于逆向。

### 【BUG 修复】
- 探针返回哨兵碰撞入口时静默跳过指令 → 现在明确拒绝；已按专门red/green测试修复。

### 【验收清单】
- [x] 查看 `source-additions.json` → 67,243指令，counter14ref中12来源／2候选，四组verifier通过。
- [x] 运行上述新目录复验 → 25tests、526人工case、672旧trace、四输出精确重建，BIOS分支拒绝。
- [x] 查看 `portable-report.json` → 两allocator各128个倒序flags read，没有第129槽；自然域仍false。
