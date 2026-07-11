# 32 结构运行时验证门禁与联合采集方案（2026-07-10）

## 目的与结论

本文件复核 `notes/dynamic-verification-audit.md` 中 32 个内容结构，并把“动态
验证”拆成可以执行、可以复核的门禁。经后续 WASM 首战编成探针和 maps A/B 复核，
当前证据为 **3 dynamic / 4 code / 24 static / 1 none**；构建、ROM 字节一致或画面中出现
相关内容均不能替代运行时
消费证据。

一次从新游戏开场推进到第一场战斗、完成至少一个回合并进入战后剧情的联合采集，
理论上可覆盖 **16 项核心候选**：`audio`、`battle-config`、
`battle-encounters`、`battle-handlers`、`character-stats`、
`character-stats-b`、`cutscene-scripts`、`map-events`、`maps`、
`map-sprites`、`positions`、`sappy-engine`、`skills`、
`sprite-animations`、`story`、`units`。其中只有已有消费者地址的项目可直接下
断点；其余项目必须先由已知入口采集 PC/LR/ROM 指针，再把消费者地址固化，不能
因为同一局游戏中出现了地图、角色或声音便判定通过。

## 统一证据门禁

每项标记为 `dynamic` 前，必须把以下材料写入仓库：

1. 原始调试器日志或 JSON，含明确的 `Hit breakpoint`、PC、LR、寄存器和相关
   ROM/WRAM dump；仅有设置断点或 `status` 输出不算命中。
2. 被消费的 ROM 地址必须落入该结构的已声明表项或其指针目标，并记录表索引的
   计算过程。
3. 至少一个字段必须和运行时值或可见行为对应。只命中函数、只看到相同数值、只
   有截图或 PNG hash 都不足以证明字段语义。
4. 若通过 A/B ROM 验证，必须只改变一个已知字段，保留 base/patched 构建报告、
   ROM diff、相同输入路线和预期方向的结果；崩溃或“画面不同”不是通过。
5. 同一命中可以为多个结构提供证据，但每个结构必须分别满足第 2、3 条，不能用
   `maps` 的 loader 命中顺带宣称 `positions` 已验证。

建议联合日志每个命中至少记录：`frame/cycle, PC, LR, r0-r12, SP, active
chapter/map id (0x02026805), battle_control (0x02026804 起), source ROM 32 bytes,
destination WRAM 32 bytes`。单位槽按 `0x020240C0 + slot*0x1D4` 计算。

## 一次章节/战斗运行的联合断点组

### A. 地图与章节进入

| 断点/观察点 | 观察值 | 成功判定 | 可贡献结构 |
|---|---|---|---|
| `0x080968A0`（已证明开场对白上层入口） | LR、上游活动 ROM 指针、当前截图帧 | 上游指针落入 `0x0853636C` 表某项的目标范围；仅命中该 PC 不通过 | `story` |
| `0x08068FF0`（地图 loader） | 调用参数、`0x02026805`、`0x0853D914 + id*0x20` 的 32 字节 | 明确命中；运行时 id 与地址公式一致；至少一个描述符字段对应加载结果 | `maps` |
| 由地图 loader 的子调用记录 ROM 源指针和目标 VRAM/WRAM | 指向 `0x0853E1DC` 的选中指针及目标动画数据 | 表索引和当前 map id 对应，并观察到该目标被遍历/拷贝 | `map-sprites` |
| 首个地图事件分派点（由 `0x0853EB08` 选中指针反查 PC） | map id、表项地址、间接调用目标 | 间接调用目标等于选中表项 Thumb 地址，且事件在同一帧/邻近帧发生 | `map-events` |
| cutscene 调度（现有静态引用 ROM `0x072F3C`，表 `0x0853DF70`） | 表索引、目标 `0x0812xxxx`、脚本读取 PC | 运行时从 16 项表选中目标，并至少读取一条脚本命令且对应当前过场 | `cutscene-scripts` |

`story-b` 至 `story-e` 不应被首章 `story` 命中顺带升级；只有运行到实际选择各自
表项的章节，或建立能证明其共同调度器和独立索引的轨迹，才分别通过。

### B. 首战初始化（同一暂停点批量采集）

| 断点/观察点 | 观察值 | 成功判定 | 可贡献结构 |
|---|---|---|---|
| `0x0806D866` 附近（加载 `0x08545458`） | 实际源地址、索引、读出的行、下游 WRAM/参数 | 地址落在 battle-config 表内，行索引与当前战斗一致，并有一字段进入运行时配置 | `battle-config` |
| `0x0806E41E` 或 `0x0806E71E` | `r5`、`r3[1:2]`、`record[+0..+8]`、调用后 slot | `r5 = 0x085461C4 + group*0x1AAC + variant*0x8E4 + 4 + index*0xB8`；`+2/+3` 等于新单位 `+0xC4/+0xC5` 和 `+0xC7/+0xC8` | `positions` |
| `0x0806AC70` → `0x0806AA64` | 参数 x/y/type、返回/分配 slot、单位完整前后差异 | 写入目标符合 `0x020240C0 + slot*0x1D4`，并与画面格坐标一致 | 强化 `positions`；提供 `units` 关联上下文但不单独验证 units 表 |
| 角色定义表消费者（`0x0806D4A0` 链） | `0x0854241C + character_id*0xB4`、模板池 `0x02022E34`、创建后单位 slot `+0` | ROM 记录索引、模板 `+0`、战斗槽 `+0` 和画面角色三者一致；旧 `0x0853F298` 只能作为 legacy u16 对象/渲染偏移查找，不再是 units 门禁 | `units` |
| 角色属性装载写点 `0x02022EF0`（watch） | 非 BIOS writer PC、源 ROM 地址、单位/角色索引、写前后 | 源可解析至 `0x0854507A` 对应行或有完整中间拷贝链，至少一字段落入当前单位 | `character-stats` |
| 上一 writer 的并行/后续源地址 | 是否解析至 `0x08545200` | 独立证明第二表一字段被读取并进入运行时；第一表命中不自动通过第二表 | `character-stats-b` |
| encounter 选择入口（从当前 battle id 反查 `0x08542384` 表项） | 表项、指针目标、battle id/敌方编成 | 运行时索引选中该表项且目标决定当前敌方/战斗；单纯 ROM 值匹配不通过 | `battle-encounters` |
| handler 间接调用（表 `0x0853E778`） | 表项索引、目标 PC（3 个唯一 handler 之一）、事件上下文 | 调用目标等于当前表项 Thumb 指针并在对应战斗事件触发 | `battle-handlers` |

首战初始化的最佳暂停顺序是：先命中 `0x0806D866`，随后在
`0x0806E41E/0x0806E71E` 连续采集最多 12 条记录，再观察 WRAM writer。这样一
次运行可共享 battle id、map id 和 battle_control，避免事后无法把不同日志的
索引关联起来。

### C. 战斗操作、音频和战后剧情

| 断点/观察点 | 观察值 | 成功判定 | 可贡献结构 |
|---|---|---|---|
| 音频 dispatcher `0x08079668` | 命令、索引、实际查表地址、音频状态前后 | 查表地址可归属已确认 audio 表且命令与听到/记录的 BGM/SFX 对应 | `audio` |
| Sappy handler 区（主入口/命令 handler 由 `sappy-engine` bank 已记录） | 命令字节、handler PC、声道状态 | 同一音频事件的命令被 handler 消费并产生相应声道状态变化 | `sappy-engine` |
| 执行一个已知技能时的表读取 | 源地址是否落入 `0x08546100` 声称的行、技能 id、效果参数 | 被读取行与 UI 选择技能及战斗效果至少一字段一致 | `skills` |
| battle handler 表间接调用 | 见上表 | 主动操作/回合/胜败事件触发的实际间接调用得到记录 | `battle-handlers` |
| sprite frame 遍历 | `0x0853E200` 表项、帧目标、当前 unit/action | 选中表项并连续读取帧结构，动画与当前角色动作对应 | `sprite-animations` |
| 战后 cutscene/story 调度 | 脚本表项、故事表目标、画面帧 | 分别满足各自 ROM 来源门禁，可在同一事件中同时验证 | `cutscene-scripts`, `story`（或实际章节对应的 story-*） |

## 32 项逐项最终门槛

“联合”表示可由上述一次开场→首战→战后路线自然触发；“条件联合”表示仍在同一
次运行内，但必须主动执行特定操作；“专门路线”表示首战录像本身不够。

| # | 结构（ROM 重要范围） | 路线 | 最终成功判定摘要 |
|---:|---|---|---|
| 1 | audio（当前 bank `0x0853F138`，身份有冲突） | 联合 | 先解决与 palettes 的别名；dispatcher `0x08079668` 实际访问确认后的音频表并产生对应声音状态 |
| 2 | battle-config (`0x08545458`) | 联合 | `0x0806D866` 路径读取当前战斗行，字段进入运行时配置 |
| 3 | battle-encounters (`0x08542384`) | 联合 | 当前 battle/encounter id 选中表项并决定敌方或战斗目标 |
| 4 | battle-handlers (`0x0853E778`) | 联合 | 间接调用目标等于选中表项，且事件语义对应 |
| 5 | character-stats (`0x0854507A`) | 联合 | ROM 行到当前单位 WRAM 的可追踪拷贝，至少一字段对应 |
| 6 | character-stats-b (`0x08545200`) | 联合 | 独立 ROM 行消费链及字段对应 |
| 7 | cutscene-scripts (`0x0853DF70`) | 联合 | 16 项之一被选中并读取命令，命令对应当前过场 |
| 8 | data-table-a (`0x085A14A4`) | 专门路线 | 先定位消费者；命中选中表项/目标并证明一个字段用途 |
| 9 | data-table-b (`0x085A2120`) | 专门路线 | 同上，且不能用 A 的消费者代替 |
| 10 | encounter-zones (`0x0853D610`) | 条件联合 | 进入/移动至实际触发区域，捕获 zone 索引和遭遇判定；与 maps 同址声明需先拆清边界 |
| 11 | fonts (`0x0853E5B4`) | 专门 A/B | 证明选中文字使用此宽度表；单字节改动产生预期字距/换行变化 |
| 12 | function-pointers (`0x0853D5F4`) | 专门菜单/UI 路线 | 运行时间接调用选中 11 项之一，参数和可见操作对应 |
| 13 | items (`0x08546100` 声称值) | 条件联合 | 先与 skills 拆分身份；使用物品时捕获独立表读取和效果字段，否则保持 none |
| 14 | levels (`0x085459B4`) | 专门升级路线 | 发生升级/经验阈值判断时读取目标条目，阈值与等级变化对应 |
| 15 | map-events (`0x0853EB08`) | 联合 | 当前 map id 选中表项并间接调用实际事件 handler |
| 16 | maps (`0x0853D910`, 描述符 `+4`) | 联合 | width/height 已通过 row 40 width 36→32 A/B：runtime `[36,44,9,22]` 变为 `[32,44,8,22]`；资源指针字段仍需独立消费/字段证据 |
| 17 | map-sprites (`0x0853E1DC`) | 联合 | 当前 map 索引选中目标并遍历/拷贝动画数据 |
| 18 | menu-ui (`0x085A5774`) | 专门菜单路线 | 菜单操作命中表项消费者，指针目标与可见 UI 元素对应 |
| 19 | palettes（当前 bank `0x0853F138`） | 专门 A/B | 先与 audio 拆分身份；目标 RGB555 数据实际上传到 palette RAM，单色改动方向符合预期 |
| 20 | positions (`0x085461C4`) | 联合 | `0x0806E41E/0x0806E71E` 的 r5 公式成立，`+2/+3` 写到 slot 坐标并与画面一致 |
| 21 | resource-pointers (`0x08596F0C`) | 专门资源路线 | 表项及嵌套目标被加载，目标与具体资源输出对应 |
| 22 | sappy-engine (`0x08079268` 代码范围) | 联合 | 实际命令 handler 命中且声道状态按命令变化 |
| 23 | save-state (`0x08086248` 表/数据，handler `0x08068684`) | 专门保存路线 | SRAM 20 字节记录发生预期变化，第 19 字节符合校验算法，字段与操作对应 |
| 24 | skills (`0x08546100` 声称值) | 条件联合 | 主动技能读取独立已确认表行，至少一参数与实际效果对应；需解决 items 冲突 |
| 25 | sprite-animations (`0x0853E200`) | 联合 | 当前动作选中表项并遍历帧，帧与角色动作对应 |
| 26 | story (`0x0853636C`) | 联合 | 开场/战后活动指针落入本表目标并读取剧情数据 |
| 27 | story-b (`0x08536BC8`) | 后续章节 | 实际章节选择该表项及目标；共同格式或 story 命中不够 |
| 28 | story-c (`0x08538FF0`) | 后续章节 | 同上 |
| 29 | story-d (`0x0853AB78`) | 后续章节 | 同上 |
| 30 | story-e (`0x0853C3C0`) | 后续章节 | 同上 |
| 31 | tile-assets (`0x085A3218`) | 专门资源/A-B | loader/decompressor 消费选中目标并写 VRAM；受控图块改动出现在预期位置 |
| 32 | units (`0x0854241C`) | 联合 | `0x0806D4A0` 按 character ID 读取 63×`0xB4` 角色定义记录，进入 `0x02022E34` 模板池，再复制到 `0x020240C0 + slot*0x1D4`；WASM 样本已证明 ID 1 template→battle slot 复制，`0x5424D1` byte `0x0e→0x0f` A/B 已证明具体 ROM record 字段进入模板；剩余门槛是逐字段语义和安全语义写回 |

## 完成门槛与边界

要宣称“32 结构动态验证完成”，必须逐行拥有可复查证据；一次首战联合轨迹最多是
高复用采集入口，不是最终完成证明。尤其以下问题必须先解决：

- `audio` / `palettes` 同称 `0x53F138`；
- `items` / `skills` 同称 `0x546100`；
- `maps` / `encounter-zones` 同称 `0x53D610`，且地图描述符从 `0x53D914`
  开始；
- `story-b..e` 必须有各自章节选择证据；
- `data-table-a/b`、`menu-ui`、`resource-pointers` 和 `tile-assets` 尚缺已确认
  消费者，不能只靠一次游戏流程猜测通过。

当前仓库没有有效战斗 savestate，现有 `.sav` 为擦除态，CLI 调试器不能注入按键；
详见 `notes/runtime-state-entry-audit-20260710.md`。后续已改用网页 WASM 运行时按键
导航进入首战，并用单位槽坐标 `(4,4)` 唯一关联到 positions 的 group 40 / variant 0 /
record 0（ROM `0x588CA8`）；详见 `notes/wasm-formation-probe-result-20260710.md`。
该接口没有 PC/LR/断点能力，所以其余结构的联合采集前置门槛仍是取得带语境的
首战前 `.ss0`，或在支持脚本输入的 mGBA 中复用 `tools/mgba_newgame_walk.lua`。
取得状态时必须同时保存截图、PC/LR、
`0x02026804` 起的 battle_control、`0x02026805` chapter/map id 和单位区摘要，
否则状态本身仍不足以审计。

## 本次复核记录

- 尝试：交叉检查 32-bank 动态证据审计、章节入口、positions ROM→WRAM 静态链、
  现有 mGBA probe 的真实断点判定和运行时状态入口。
- 所学：一次首战流程可联合采集 16 项，但只有 maps、positions、battle-config、
  audio 等已有代码入口的结构可以直接布点；其他项目仍需由日志发现消费者，且
  alias 冲突必须先解决。后续 WASM 路线已独立满足 positions 的动态门禁，但不能
  替代 maps 等结构所需的 ROM 表项消费证据。
- 当前最重要范围：代码 `0x08068FF0`、`0x0806D866`、
  `0x0806E41E/0x0806E71E`、`0x0806AC70`、`0x08079668`；ROM
  `0x0853D914 + map_id*0x20`、`0x08545458`、`0x085461C4`；WRAM
  `0x02026804` 和 `0x020240C0 + slot*0x1D4`。
