# 逆向完成度审计（2026-10-20）

**工具**: `tools/completion_audit.py`（可复现审计脚本，扫仓库现状重算本表）
**本表生成时间**: 见 `build/completion-audit.json` 的 `generated_at`
**上一版**: `notes/re-completion-audit.md`（2026-07-11，已被本文件取代；历史内容保留）
**证据分级**: `notes/runtime-verification-gates-20260710.md` §四级证据分级
**关联**: `notes/external-konoha-workshop-gap-20261020.md` §12 对账、
`notes/runtime-and-object-tables-20261020.md`、`notes/battle-tables.md`、
`notes/fixture-coverage-20261020.md`、`notes/font-encoding.md`、
`notes/story-script-vm.md`、`notes/mechanisms-20261020.md`、
`notes/sprite-frame-format-20261020.md`、`notes/resource-locations.md`、
`notes/tile-asset-rules-20261020.md`、`notes/character-template-format-20261020.md`

---

## 0. 结论摘要

- 本审计覆盖 **47 个结构**（32 个 legacy content bank + 15 个 2026-10-20 起新确认、
  但还没有 bank 的结构）。
- 等级分布：**L4 = 3 / L3 = 33 / L2 = 1 / L1 = 7 / 无独立证据 = 3**
  （「无独立证据」= 该结构声明的基址已被证明**在整个 ROM 里零引用**，
  身份问题关闭：基址无效，需要重新定位，见
  `notes/legacy-table-base-correction-20261020.md`）。
- **L4 的三个结构**（`notes/evidence/l4-battle-matrix-20261021.md` +
  可执行闸门 `tools/mgba_probe/l4_battle_matrix.py`）：
  `story-vm-roots`（全流程 55/55 + 游戏自己驱动的场景链 39 → 45）、
  `maps`（**47/47** 个地图描述符真的被载入并渲染，47 个互不相同的 VRAM 哈希）、
  `positions`（**85/85** 组真实队伍真的被游戏打进过）。
- **格式已被独立证明**：`44 / 47`；**写回路径可用**：`24 / 47`。
- **P1 已达成**：47 个结构**全部**达到 L1 或以上，或被显式裁决（无独立证据 = 0）。
- **P2 已达成**：地图/战斗配置、剧情脚本、文本编码**三类必测面全部达到 L3**。
- 阻塞缺口 **0 条** —— **P3 已达成**；
  加固缺口 **20 条**（**全部是 labelled**：按审计语义已属「未知字段已显式标注」的
  **已满足**项，非阻塞；**L2 / L3 / 文档 / 语义 / 证据类缺口已清零**）。
  阻塞缺口从本轮开始时的 **31 条**降到 **0 条**。
- **2026-10-22 晚：上面那句「语义类缺口已清零」**说法本身有问题**，本轮更正：
  - 当时忍具记录表 `0x545BE4` 那 16 格在编辑器里**全是「未解字节 +0xNN」** ——
    「已显式标注为未解」被当成了「已闭合」。用户指着编辑器截图问
    「怎么还有未解字节」，是对的。
  - 本轮把这张表**逐字节钉死**（`notes/evidence/item-record-fields-20261022.md`、
    工具 `tools/item_record_fields.py`）：7 个原生读者分别读哪些格、读成什么宽度
    都有指令级依据；**原生代码不读的三格（+0x01 / +0x0E / +0x0F）证明为「保留」**；
    内容包已改成 16 个有名字的字段，编辑器里这一页给的是字段名而不是十六进制框。
  - 同时给审计加了**独立于 SPECS 清单的交叉检查**：
    内容包里凡还标着「未解字节」的字段，一律算成一条 open gap
    （`undecoded-fields`），不再依赖谁记得在 SPECS 里补一条 unresolved。
    ⇒ 加固缺口从 20 条变成 **27 条**（20 labelled + **7 undecoded-fields**），
    这 7 条是**真实存在**的未解字段（`battle-rules` 1、`maps` 1、`positions` 3、
    `character-template` 1、`battle-config`（忍术记录表）5、`encounter-zones` 1、
    `tile-assets` 1），不是虚数。
  - **一句话结论**：逆向**没有**「全部闭合」；闭合的是结构与读者，
    剩下的是「某个字节到底是什么业务含义」这一类，仓库现在把它们**逐条列出来**
    而不是笼统计成「已完成」。
- **2026-10-22 晚：`story_config[0]` 的非零读数已闭合**
  （`notes/evidence/runtime-state-story-config-20261022.md`）——
  旧归因「调度器 `0x0808F5C8` 写入、`0x0808F5CC` 随即清零，所以任何快照都
  拍不到」**归因错误**：逐指令核对显示 `0x0808F5C8` **只**在 `state[0x18] == 0`
  的「before」路径上执行 ⇒ **恒写 0**；真正的写入者是剧情 VM 的 **opcode `0x1F`**
  （`0x08097C40: strb r0,[r1,#0x19]`，操作数 = 战斗 sub-config），
  场景 2/3/4/6/7 的 before 脚本都写 `1F 01`。实测（场景 2 + 作答行 1）
  `0x08097C40` 命中、`r0 = 1`、内存 `0x020311ED` 读回 **`0x01`**。
  ⇒ 动态证据闭环从 2 条降到 **1 条**（剩 `cutscene-scripts`）。
- **2026-10-22 晚：关卡数据块表 `0x0853DF70` 的动态证据已闭合**
  （`notes/evidence/cutscene-scripts-l3-20261022.md`）——
  旧注记「加载器一次都没命中，属于剧情/战斗之外的第四种模式，本轮探针能到达的
  范围内**无法触发**」**作废**：**相位 `0x0118`**（`0x0808F94A`：置战斗标志
  bit 1 → `bl 0x080732B4` 跑剧情战斗 → 清标志）就能命中判定点 `0x08072F0E`，
  此时 **`r4 = 0x0853DF70`**，表首 32 字节被 dump 出（4 条 8 字节记录，
  word0 = ROM 源地址 `0x0812xxxx`）。同时更正：**表读取没有前提条件** ——
  `0x08072EEE` 处的 `cmp r2,#0 / beq 0x08072F0C` 只决定要不要顺手置标志。
  ⇒ **动态证据闭环清零**（2 条 → 0 条）。
- **2026-10-22 晚：忍术名表 `0x08599634` 升到 L3**
  （`notes/evidence/ninjutsu-names-vm-20261022.md`）——
  该表有 **12 个读者**（旧笔记只押了一个判定点，还把 `fn 0x080794F4` 当成读者，
  它不是）；剧情 VM 的 **opcode `0x1D`**（`0x08097CC4`）在**模式 0** 时读表，
  下标 = 操作数字节 2。实测场景 43（`1D 00 49`）：`0x08097352` 命中，
  `r0 = 0x08599758` = `0x08599634 + 0x49 × 4`，且**全程没有菜单** ⇒ 纯正常按键。
- **2026-10-22 晚：`story-e`（声音 id 14）升到 L3**
  （`notes/evidence/story-e-l3-20261022.md`）——
  旧结论「id 14 的请求在地图/事件脚本，剧情路线跑不到」**作废**：
  全 ROM 只有 `0x080894FC` 一处常量调用点，在**章节/任务列表**里；
  章节菜单 = 状态机相位 **`0x0120`**。实测：`0x080894FC` 命中 `r0 = 0x0E`，
  随后 `0x0809AAD6` 读到条目 `0x08465BE0` = `0x08465B70 + 14×8`，
  其 word0 = **`0x0853C3BC`**。
- **2026-10-22 晚：`fonts` 与 `sprite-frame-descriptors` 升到 L3**
  （`notes/evidence/fonts-spriteframe-l3-20261022.md`）——
  `0x0853E698` 其实是 **256 条 8 字节的回调记录表 `(handler_A, handler_B)`**，
  下标字节在 **`0x02027428`**（运行时实测；旧笔记写的 `0x02027350` **作废**）。
  `fn 0x0807F064`（字宽表 `0x0853E596` 的读者）是 **168/256 条**的 B 槽。
  实测：字体内读者处 `r0 = 0x0853E635` = 表基址 + 159、`r1 = 0x0D` = 字宽；
  精灵帧描述符处 `r1 = 0x0853EE98`、`r4 = 0x0853EEA2 / 0x0853EEB6 / 0x0853EED4`
  = **基址 + 下标 × 10**（步长 10 字节得到运行时证实）。
  ⇒ 加固缺口 **31 → 27**；等级分布 **L4=3 / L3=37 / L2=0 / L1=4 / 无=3**。
- **2026-10-22 晚：`mechanism-effects` 升到 L3**
  （`notes/evidence/mechanism-effects-l3-20261022.md`）——
  **`0x0808136C` 不是数据表，是 13 项函数指针跳转表**
  （`0x08081350: ldr r1,[pc,#0x14]` 装基址 → `mov pc, r0` 的 Thumb-2 switch，
  下标 = 传入值 - 1，必须落在 0..12）；旧注记把它当「13 项效果表」**作废**。
  路线：剧情战斗 `fn 0x080732B4` → `0x0807498C` → `fn 0x08081544`
  （第二个关卡对象处理器）→ `0x08081ADE` → `fn 0x080812DC` → 读 `0x0808136C`。
  实测判定点 `0x08081350` 命中，`r2 = 1` = 机制下标（= `record[+6]`）。
  ⇒ 加固缺口 **27 → 25**；等级分布 **L4=3 / L3=38 / L2=0 / L1=3 / 无=3**。
- **2026-10-22 晚：`items` / `skills`（同一张表 `0x08545BE4`）升到 L3**
  （`notes/evidence/items-skills-l3-20261022.md`）——
  路线：剧情战斗 `fn 0x080732B4` 的**单位扫描**（`0x08074200`：
  `unit[0] != 0`、`unit[0xCC] == 0`、`unit[0xC0] & 0x70 == 0`、
  `unit[0xCD] ∉ {0,0xFF}`）→ `0x0807425A: bl fn 0x080851F8`
  → `fn 0x080833A8` → `0x08083812: bl fn 0x0806D910`。
  分岔点是每条道具记录的**标志字节（`0x0202D4CD + r4*6`）的 bit 7**：
  置位才走读者那一臂。
  实测（场景 10，相位 `0x0110`）：判定点 `0x0806D91A` 命中 **3 次**，
  `r0 = id × 16` = 表内字节偏移（id 1 / 0x4A / 5），
  **步长 16 字节得到运行时证实**。
  ⇒ 加固缺口 **25 → 21**；等级分布 **L4=3 / L3=40 / L2=0 / L1=1 / 无=3**。
- **2026-10-22 晚：`resource-pointers` 裁决为精灵动作表同址（其「读者」是死代码）**
  （`notes/evidence/resource-pointers-deadcode-20261022.md`）——
  旧基址 `0x596F0C` 是精灵动作表 `0x596CCC` 的 `+0x240` 窗口；
  **全 ROM 里 `0x596F0C` 只出现一次**（池项 `0x0807B278`），
  由 `0x0807B220` 装载，而该指令在 `fn 0x0807AE04` 的 **case 7** 里 ——
  case 7 只能由 `arg1 = 7` 进入，37 个调用点里只有
  `0x0807C3D6` / `0x0807C4D6` 传 7，而它们都在 `fn 0x0807B8B8` 的循环里，
  该循环入口把 `r8` 硬编码成 2，`0x0807C4CC: cmp r0,#1` 永远失败
  ⇒ **两处都是死代码**。
  运行时阴性对照（20 场剧情战斗）：同一次运行里 items 读者命中 **72** 次，
  资源读者 **0** 次、`arg1=7` 调用点 **0** 次（正对照 + 阴性）。
  ⇒ 本 bank 按 `LEGACY_REBASE` 先例重定基址到 `0x596CCC`。
  ⇒ 加固缺口 **21 → 20**；等级分布 **L4=3 / L3=41 / L2=0 / L1=0 / 无=3**；
  **所有 L2 / L3 / 文档 / 语义 / 证据类缺口清零，阻塞缺口 0**。
- **2026-10-22 凌晨：回调派发点其实可达**（`notes/evidence/callback-dispatch-runtime-20261021.md`）
  —— 2026-10-21 的「派发点 0 命中 ⇒ 只属于关卡/过场模式」结论**作废**：
  那次断点普查有**工装 bug**（松手只在「没命中断点」时执行 ⇒ 游戏收不到按下沿
  ⇒ 战斗过场不推进 ⇒ 单位永远不建），门控 `fn 0x0806DF88` 本身还有一个
  结构性死因（`unit[0xC0] & 1` 永远不等于战斗中的 `ctrl[10]` = `0x0E`/`0x0F`）。
  打开门控后，派发点全部命中并拿到运行时读数：
  `battle-handlers` / `map-events` / `map-sprites` / `units` / `levels` 升到 **L3**，
  `mission-text` 也拿到 **L3**（任务面板 `fn 0x080884DC` 的四张表）。
  同时打通了**剧情 VM 的章节交接链**（`notes/evidence/menu-answer-channel-20261021.md`）：
  菜单作答通道是 `0x0200A880`（选中行）+ `0x0200A882`（完成标志），
  并且**推翻了**「`fn 0x0808F654` 是 `state[0x18]==1` 的消费者」——
  全 ROM 原始半字扫描证明它是**死代码**，真正的消费者是 `0x0808F904`。
  进一步**关卡模式也进得去了**（`notes/evidence/level-mode-l3-20261022.md`）：
  `character-stats` / `character-stats-b` / `battle-config` /
  `sprite-animations` / `sprite-action-table` 拿到 L3，
  并顺带发现了此前未登记的函数指针表 `0x0853ECB0`（字宽表读者的调用表）。
  第三个工装 bug 同时被挖出并修掉：**30 个观测点下在字面量池上**（数据，
  断点永不命中）⇒ 修好后 `tile-assets`（`0x085A320C`）在**纯自然剧情路线**上
  命中并拿到 L3（`r0 = 0x085A37E4` = 基址 + 22×68）。
  音频方向也拿到两条 L3：**战斗 BGM 真的在放**，m4a 播放入口读了
  `story`（`audio_song_1`）的 SongHeader 字段，剧情音效读了
  `sound-id-table`（`0x08465B70`）
  （`notes/evidence/m4a-songheader-l3-20261022.md`），
  同时推翻了「引擎从不读 id 1 的 header 字段」这句旧结论。
  第四个工装 bug 同时被挖出并修掉：**断点命中时寄存器被错位归档**
  （`|pc - addr| <= 4` 才算真命中）。
  价值最高的一条缺口也在这轮关掉：**对白指针表 `0x08461CE8`** 的读者
  既无字面量读者也不在剧情路径上，而是**状态机相位 `0x0210`** 的处理器
  （`notes/evidence/text-pointer-table-l3-20261022.md`）。
  由此得到**相位路线**这个方法：状态机的 16 个相位分派就是各结构的
  「读者入口表」，逐个 poke 相位再按 A 键，一次拿下
  `data-table-a`（相位 `0x0300`）、`battle-encounters`（相位 `0x8000`）、
  `data-table-b`（相位 `0x0000`/`0x0010`/`0x0700`）、
  `function-pointers`（相位 `0x0110`/`0x0118`）的 L2+L3
  （`notes/evidence/phase-route-l3-20261022.md`）。
- **2026-10-21 退役的 3 个作废 bank**（`tools/table_registry.py::RETIRED`）：
  `sappy-engine`（`0x08079668` 是文本分派函数）、`audio`（`0x53F138` 与音频无关）、
  `palettes`（`0x53F138` 只是 `0x53F140` 数组的窗口，调色板真身在 VRAM `0x05000380`）。
  三个 bank 保留文件作为审计留痕，但标记 `retired: true`、不再拥有任何表、
  也不再被任何工具重新导入 —— 此前「身份作废应退役」这 2 条与
  「基址需改指」这 1 条硬化缺口因此清零。
- **2026-10-21 补齐的 9 个 legacy 基址**（`notes/evidence/legacy-rebase-final-20261021.md`）：
  `battle-handlers` → `0x53E698`、`map-events` → `0x53E698`（同表）、
  `fonts` → `0x53E596`、`data-table-a` → `0x5A143C`、
  `data-table-b` → `0x5A2034`、`menu-ui` → `0x5A4DEC`（头像表）、
  `function-pointers` → `0x53D5F0`、`tile-assets` → `0x5A320C`（79 条）、
  `sappy-engine` **退役**。这批把「基址无效需重新定位」从 12 条降到 3 条，
  格式已证明从 35/47 提到 **44/47**。
- **2026-10-21 补齐的 5 个 L2 运行时证据**（`notes/evidence/l2-runtime-evidence-20261021.md`
  + 可执行闸门 `tools/l2_runtime_capture.py --self-test`）：
  `font-segments`、`sound-id-table`、`character-template`、`maps`、`portrait-table`
  —— 断点命中原生消费者，寄存器/内存与字段一一对应，
  并与静态表交叉核对。L2 从 **1** 提到 **5**。
- **2026-10-21 补齐的能力项**（`notes/evidence/audio-song-export-20261021.md`、
  `portrait-writeback-20261021.md`、`content-pack-export-20261021.md`）：
  m4a → PCM 端到端合成已实现（修正了 PSG 频率表等 4 个真 bug）；
  头像写回已实现并登记为**可执行**写回路径（`portrait-table` case，18/18 PASS）；
  内容包导出 `--check` 通过，5740/5740 条记录逐字节可重建。
- 本轮新增的三类**机器化**探针（见 §2.3）：
  ①`codecite` —— 原生代码定址（`notes/evidence/consumer-evidence.json` + ROM 指纹）；
  ②`notatable` —— 反向证明（基址在 ROM 里零引用 ⇒ 基址无效，身份已裁决）；
  ③`writeback` —— **可执行**的写回往返自检（`tools/writeback_paths.py` 真的跑一遍，
  断言「回读 == 作者输入」且「未知字节原样保留」）。
- 旧审计（`notes/re-completion-audit.md`）的 "32/32 完整" 口径是**元数据齐全**
  （偏移 / 格式描述 / 条目 / 文档引用 / 基准 ROM 字节一致），
  它自己在第 5 行就写明 *"no runtime or write-back validation ... cannot prove
  runtime semantics or actual write-back closure"*。
  本审计换的是**另一个口径**：格式有没有被**独立证明**。两个数字不可直接比较。
- 本审计**不采信未提交的产物**：`build/` 下未被 git 跟踪的探针 JSON / 渲染 PNG
  一律不作为持久证据（详见 §8）。

---

## 1. 「100% 完成」的定义

### 1.1 单个结构「算完成」的六条（可逐条核验）

| 编号 | 条件 | 核验方式 |
|---|---|---|
| **C1** | **身份唯一**：该结构在 ROM 中有唯一地址，不与别的结构共用；同址冲突必须已裁决（合并为一个结构，或明确拆分） | 地址去重 + `tools/table_registry.py` 的 alias 检查 |
| **C2** | **格式已证明**：存在一条**可复现**的证明，四选一 —— ①**合成夹具**：把已知内容写进 ROM → 用**生产读取器**读回 → 逐字节相等；②**渲染可视证明**：把结构内容渲染成图/音频，人工可辨且"错一步就碎"；③**字节级往返**：`encode(decode(x)) == x`；④**原生代码定址**：反汇编里该地址出现在字面量池/立即数，且指令解释了字段。证明必须由**仓库内已提交**的工具或夹具产出，能一条命令复现 | `tools/completion_audit.py` 的 fixture / render / roundtrip / code 四类探针 |
| **C3** | **字段语义已知**：每个字段都有名字与含义；未解字段必须显式列出并标"未解"，且**不影响**写回模型（复制原生条目 + 只改已知字段） | 逐结构笔记 + 探针的 `need` 标记 |
| **C4** | **写回可用**：有写回路径，且有"回读渲染/解码结果 == 作者输入"的验收；**或**被显式声明为只读参考结构 | 写回探针 + 结构目录里的 `readonly` 标记 |
| **C5** | **有笔记**：地址、字段、证据文件、复现命令在 `notes/` 里有记录 | 笔记探针（文件存在 + 命中该地址） |
| **C6** | **无待裁决冲突**：涉及的所有地址复用 / 别名冲突都已裁决 | alias 冲突表 |

> C2 的四类证明都**不是**"数据看起来合理"。泛用提取器（`tools/extract_all_structures.py`）
> 把一段字节 dump 出来，不构成 C2。

### 1.2 项目级「逆向 100% 完成」的判据

同时满足以下三条，才叫 100%：

- **P1** 本表里**每一个**结构都达到 **L1 或以上**（即 C1 / C2 / C3 / C5 全部满足），
  或被显式裁决为"重复项 / 只读项"并记录在案；
- **P2** 三类必测面**各至少一个**结构达到 **L3（模拟器正常按键复现）**：
  地图与战斗配置、剧情脚本、文本编码；
- **P3** 阻塞缺口表**清零** —— 每个结构要么有写回路径，要么被显式标为只读。

### 1.3 明确**不算**完成

- **L4 完整通关**（当前 0）：全流程 / 全人物 / 全地图实际打通。
- **L2 原生定点**（当前 1）：断点命中消费者，寄存器/内存与字段对应。
  —— 本轮新增：战斗胜负条件的类型 2 判据拿到了 L2 证据
  （`notes/evidence/battle-rules-l2-20261020.md`）。
- 仅有"工具跑通"而没有 C2 那四类证明之一。
- `bank.json` 里写着 `static_verified` —— 那是**元数据标签**，不是证据。
- 未提交的本地产物（`build/` 下未被 git 跟踪的文件）。

### 1.4 当前距离

| 判据 | 现状 | 差多少 |
|---|---|---|
| P1 | **44 / 47 达 L1 或以上，另 3 个已裁决（身份作废 / 别名退役）** | **0 个「无独立证据」——P1 已达成** |
| P2 | 三类必测面**全部**达 L3（地图/战斗配置、剧情脚本、文本编码） | **P2 已达成** |
| P3 | **0 条**阻塞缺口 | **P3 已达成** |

> **100% 的含义**：P1 / P2 / P3 三条判据同时满足。
> 这**不等于**「整个 ROM 每一处都反编译完了」——
> L4（完整通关）只覆盖到 3 个结构，3 个结构是已裁决退役的别名/作废 bank，
> 27 条加固缺口列在下方（其中 19 条是「未知字段已显式标注」的满足项，
> 8 条是 4 个结构各缺 L2+L3）。

---

## 2. 审计方法

### 2.1 脚本

```powershell
python tools/completion_audit.py                       # 汇总 + Markdown
python tools/completion_audit.py --json build/completion-audit.json
python tools/completion_audit.py --markdown build/completion-audit.md
python tools/completion_audit.py --note notes/completion-audit-20261020.md
python tools/completion_audit.py --check                # 有探针失配时返回 1
```

### 2.2 脚本到底读了什么

结论不是写死在脚本里的，而是从这些真实文件算出来的：

| 输入 | 用途 |
|---|---|
| `sequel/content/*/bank.json`（32 个） | 各 bank 声明的 `table_offset`、legacy `verification` 标签 |
| `tools/table_registry.py` | 权威表基址 + 哪些表**没有**被独立验证 + alias 冲突 |
| `tools/synthetic_fixture.py`（导入 `FIXTURES` 注册表） | 已注册的合成夹具及其定义模块 |
| `tools/`、`notes/`、`docs/` 全量扫描 | 按**数值**匹配地址（同时接受 file offset 与 `0x08xxxxxx` ARM 形式） |
| `git ls-files` | 区分"已提交的持久证据"与"只在本地存在的产物" |

### 2.3 探针类型与判据

| 探针 | 通过条件 |
|---|---|
| `fixture` | 夹具名在 `FIXTURES` 注册表里 **且** 其定义模块提到本结构地址 **且** 夹具名出现在 `notes/fixture-coverage-20261020.md`（即"跑过且全绿"的已提交记录） |
| `tool` | 工具文件存在 **且** 提到本结构地址（或显式声明 `address_required: False`）**且** 含要求的标记 |
| `note` | 笔记存在 **且** 提到本结构地址（或显式声明 `address_required: False`）**且** 含要求的标记 |
| `code` | 文件含指定的**原生代码证据片段**（如 `0x08069046` / `adds r0, r5, #4`） |
| `roundtrip` | 文件含字节级往返断言标记（如 `bytes_equal`） |
| `render` | 工具存在 + 提到地址 + 有媒体产出标记；产物是否存在、是否已提交单独记录 |
| `dynamic` | 动态证据文件存在 + 含指定的运行时标记（PC/LR、寄存器、运行时值、唯一匹配） |
| `codecite` | **原生代码定址**（C2 第 ④ 类）的机器化版本：读 `notes/evidence/consumer-evidence.json`，校验 ROM 的 SHA-256 仍然匹配、该基址确实被游戏自己的字面量加载读过、且要求的指令片段出现在消费者的反汇编里 |
| `notatable` | **反向证明**：同一份证据显示该基址**零原生读者且在整个 ROM 里零出现** —— 身份问题已裁决（基址无效），但**不算**格式证明 |
| `writeback` | **可执行的写回往返自检**：把 `tools/writeback_paths.py` 里该结构的那条 case **真的跑一遍**（对着 `rom/base.gba` 的副本），要求①回读值 == 作者输入、②记录里 `problems` 为空、③该 case 声明的基址与本结构的基址一致 |

> `codecite` / `notatable` 是**按结构基址自动挂上**的：审计器拿到结构的
> `rom` 地址，去证据文件里查同一地址，命中就加对应探针。
> 因此新增证据不需要改审计器，改完重新生成证据文件即可。
>
> 证据文件带 **ROM 的 SHA-256**；换了 ROM 证据自动作废（审计会报 `stale`）。

### 2.3.1 `writeback` 探针为什么重要

C4 原来只要求「存在一条写回路径 + 有验收」，实现上却是
「`grep` 到生成器文件里有这个词」—— 一条**从不运行**的路径也算数。
本轮把它换成**可执行**判定：

1. `tools/writeback_paths.py` 为每个结构准备一条 case：读一条原生记录 →
   施加作者改动 → 回读 → 断言回读 == 作者输入 → 断言**记录里除已知字段外
   没有任何字节被改动**；
2. 审计器按结构基址找到对应的 case 并**执行**它，任何一条不满足即该结构
   的写回探针失败；
3. case 自己声明的基址会和结构的基址**交叉核对**，所以一条路径不可能被
   记到别的表头上。

当前 `tools/writeback_paths.py` 覆盖 **12 条**写回路径
（剧情 VM 四根表、角色模板、战斗记录表、精灵动作表、地图描述符、
战斗编成矩阵、奖励表、场景对象描述符、关卡数据指针表、WRAM 分配表、
u16 偏移表、动作表窗口），全部 PASS。

### 2.3.2 未结项的分类（本轮新增）

旧的审计把**所有**未结项都算成「字段语义未解」，于是「没有 m4a→PCM 导出器」
和「某个字段不知道是什么意思」被混在同一栏里 —— 前者根本不是语义问题。
现在每个未结项带一个类型：

| 类型 | 含义 | 是否阻塞 |
|---|---|---|
| `field` | 某个**字段**的含义未知 | 阻塞，除非它被显式列出**且**写回路径不会碰它（机器判定：见下） |
| `relation` | 本表与另一张表的关系未裁决 | **阻塞** |
| `evidence` | 静态推导还缺一次运行时读数闭环 | 不阻塞（属加固项） |
| `capability` | 缺一个导出 / 导入 / 写回的工具能力 | 不阻塞 |
| `integrity` | 素材取值范围或损坏点未逐条核实 | 不阻塞 |
| `ambiguity` | 一条查找 / 编码规则还不能收敛成唯一一条 | 不阻塞 |

`field` 类要判为「已满足」必须同时满足三条（这正是 C3 的原文）：

1. 未知字段在笔记里**被逐条列出**（探针用 `need` 标记机器校验）；
2. 写回路径**不会改动**这些字节（由 `writeback` 探针的
   「未知字节原样保留」断言机器证明）；
3. 该结构要么有可执行的写回自检，要么被显式声明为只读。

不满足就仍然是阻塞缺口 —— 不会被悄悄降级。

### 2.4 等级怎么算

```
L1 = (fixture | render | code | roundtrip | codecite 至少一个通过) 且 (有 tool 探针通过) 且 (有 note 探针通过)
L2 = 一个 L2 级 dynamic 探针通过
L3 = 一个 L3 级 dynamic 探针通过
L4 = 一个 L4 级 dynamic 探针通过
已裁决 = 一个 notatable 探针通过（基址被证明无效）
```

L2 与 L3 是**两条独立的取证路线**（断点定点 / 模拟器按键），所以 L3 不强制包含 L2。
一个结构如果连 L1 的三个前提都不满足，且也没有 `notatable` 裁决，
报的是 `无独立证据`，**不会**退化成 `static_verified`。

> **注意（2026-10-20 修正）**：此前 `tool` / `note` 探针拿不到结构的 `rom`，
> 「提到本结构地址」这一条**其实从未被检查**（只查了文件存在 + `need` 标记）。
> 现在 `evaluate_structure` 会把 `rom` 传进探针上下文，地址检查**真的生效了**；
> 修完只有两处失配（`tools/extract_battle_tables.py` 未提技能表地址、
> 角色模板笔记的证据字符串与规格不一致），都已改对。

### 2.5 探针会失配

证据被删掉、被改写、地址被挪走，等级会**自动掉下来**。例如：

```
$ python tools/completion_audit.py --check
failed probes:
  fixture tools/synthetic_fixture.py::battle_rules: 夹具 battle_rules 不在 FIXTURES 注册表
```

---

## 3–5. 逐结构表 / 汇总 / 缺口清单（由脚本生成）

下面三节由 `tools/completion_audit.py` 生成（`--note` 可原地重算）。
「证据文件」列给出的是**产生该等级的那条证据**，不是全部引用。

<!-- BEGIN GENERATED: tables -->
## 逐结构表

| 结构 | ROM 范围 | 格式已证明 | 写回可用 | 等级 | 证据文件 | 剩余缺口 |
|---|---|:---:|:---:|:---:|---|---|
| 剧情脚本 VM 四根表 | `0x060C74` | ✅ | ✅ | **L4** | tools/synthetic_fixture.py::story_before；tools/mgba_probe/render_screen.py；notes/evidence/consumer-evidence.json::0x08060C74 | —（已更正：44 条指令里 **38 条已由原生代码证明、6 条仍为推定** —— 2026-10-21 已全部定案：6 个 helper 逐条反汇编完，字段语义已定，全部升为 `proved`（44/44）；**L4 的「全流程」轴已达成 55/55**：每一场都能被调度到，且游戏实际使用的脚本指针与根表条目逐位相等（见 `notes/evidence/l4-playthrough-20261021.md`）） |
| 战斗地图表（场景描述符） | `0x53D910` | ✅ | ✅ | **L4** | notes/resource-locations.md；tools/extract_tileset.py；notes/evidence/consumer-evidence.json::0x0853D910 | —（已更正：metatile 缓冲的容量**不再是从两侧结构夹出来的**：缓冲**基址 `0x0201DE2C`** 与**末端 `0x02021E2C`** 是 ROM 代码里**成对出现的两个字面量常量**（分别在 `0x08068F58` 与 `0x080690E8`，同一个字面量池），步长 **8 字节**（`0x08068F38 lsls r0,r0,#3`），因此容量 = `0x4000/8` = **2048 项**。**仍未证实**：引擎没有一条显式的「下标 < 2048」越界检查，「越界会被拒绝」这句话**无证据**；metatile 缓冲真实容量已闭环：WRAM `0x0201DE2C`，每项 **8 字节**（`0x08068F38 lsls r0,r0,#3`），容量 **2048 项**（= 0x4000 字节），实际最多用到 770 项；「没有图层 1」的判据已固化为 **`layer1_ptr == 0`（NULL）**：`0x08069082 cmp r2,#0` / `0x08069084 beq 0x0806909E`，没有别的哨兵值；47 条里 14 条非空、33 条为 NULL（已复核：非空下标 0/7/8/9/10/11/12/21/22/23/31/32/34/35）；地图描述符表有 **47** 条有效条目（0..46），不是 8 条） |
| 战斗角色槽 / 编成表 | `0x5461C4` | ✅ | ✅ | **L4** | tools/synthetic_fixture.py::battle_actors；notes/evidence/consumer-evidence.json::0x085461C4 | group/variant 等索引字段名仍是暂定名（槽内 +0x00/+0x01/+0x04/+0x0F 已证）（已更正：索引字段名已由消费者代码定名：`group_id`→**battle_stage**（`ctrl[1]`，步长 `0x1AAC`）、`variant_id`→**battle_sub**（`ctrl[2]`，步长 `0x8E4`）、`record_id`→**actor_slot**（0..11，`0xB8`）、`selector`→**character_id**（`+0x00`）、`aux_u32`→**unit_flags**（`+0x08`，bit0 = 阵营）、`+0x02/+0x03`→**spawn_x/spawn_y**、`+0x04`→**facing**） |
| m4a SongHeader（sound id 11） | `0x53AB74` | ✅ | ✅ | **L3** | notes/evidence/story-table-family-20261020.md；notes/evidence/m4a-block-table-20261021.md | —（已更正：旧基址 0x53AB78 晚了 4 字节 —— 它锚在 `voicegroup_ptr` 字段（+0x04）而不是表头起点。本结构**不是**剧情表，而是 sound id 11 的 **m4a SongHeader**（由 sound-ID 表 `0x465B70` 的第 11 行指向）；**轨数据的块级格式已逐字段拆解**（2026-10-21）：「block 表」就是 SongHeader 本身 —— `+0x00` u8 轨道数、`+0x01` u8（本 ROM 全为 0 且引擎不读）、`+0x02` u8 优先级、`+0x03` u8 标志（bit7 = 混响）、`+0x04` u32 voicegroup 指针、`+0x08` 起 `u32 track_ptr[轨道数]`；每个 `track_ptr[i]` 指向一个**无头**的 block —— 扁平命令流，以 FINE（`0xB1`）结束、其后是 0x00 padding。命令编码：`0x00-0x7F` 是**续写字节**（running opcode 的操作数）、`0x80-0xB0` 是 WAIT、`0xB1-0xCE` 是命令表（`0x08464534`，30 项，索引 `op-0xB1`）、`0xCF-0xFF` 是 NOTE（0~3 个可选参数字节）。**running opcode 规则**（`0x0809A4F8 cmp r1,#0xbd` / `0x0809A4FC strb r1,[r5,#7]`）：**所有 `>= 0xBD` 的 opcode 都更新 running opcode**（不只是音符）。循环：GOTO `0xB2`（4 字节**小端**目标）、PATT `0xB3`（栈深 3）、PEND `0xB4`（空栈 = 继续）、REPT `0xB5`（`count` + 目标，count 0 = 无限）。往返自检：5 首曲子 45 个 block（9952 字节 / 6333 条命令）**45/45 逐字节相同**。见 `notes/evidence/m4a-block-table-20261021.md`） |
| m4a SongHeader（sound id 14） | `0x53C3BC` | ✅ | ✅ | **L3** | notes/evidence/story-table-family-20261020.md；notes/evidence/m4a-block-table-20261021.md | —（已更正：旧基址 0x53C3C0 晚了 4 字节 —— 它锚在 `voicegroup_ptr` 字段（+0x04）而不是表头起点。本结构**不是**剧情表，而是 sound id 14 的 **m4a SongHeader**（由 sound-ID 表 `0x465B70` 的第 14 行指向）；**轨数据的块级格式已逐字段拆解**（2026-10-21）：「block 表」就是 SongHeader 本身 —— `+0x00` u8 轨道数、`+0x01` u8（本 ROM 全为 0 且引擎不读）、`+0x02` u8 优先级、`+0x03` u8 标志（bit7 = 混响）、`+0x04` u32 voicegroup 指针、`+0x08` 起 `u32 track_ptr[轨道数]`；每个 `track_ptr[i]` 指向一个**无头**的 block —— 扁平命令流，以 FINE（`0xB1`）结束、其后是 0x00 padding。命令编码：`0x00-0x7F` 是**续写字节**（running opcode 的操作数）、`0x80-0xB0` 是 WAIT、`0xB1-0xCE` 是命令表（`0x08464534`，30 项，索引 `op-0xB1`）、`0xCF-0xFF` 是 NOTE（0~3 个可选参数字节）。**running opcode 规则**（`0x0809A4F8 cmp r1,#0xbd` / `0x0809A4FC strb r1,[r5,#7]`）：**所有 `>= 0xBD` 的 opcode 都更新 running opcode**（不只是音符）。循环：GOTO `0xB2`（4 字节**小端**目标）、PATT `0xB3`（栈深 3）、PEND `0xB4`（空栈 = 继续）、REPT `0xB5`（`count` + 目标，count 0 = 无限）。往返自检：5 首曲子 45 个 block（9952 字节 / 6333 条命令）**45/45 逐字节相同**。见 `notes/evidence/m4a-block-table-20261021.md`） |
| m4a SongHeader（sound id 1） | `0x536368` | ✅ | ✅ | **L3** | notes/evidence/story-table-family-20261020.md；notes/evidence/m4a-block-table-20261021.md | —（已更正：旧基址 0x53636C 晚了 4 字节 —— 它锚在 `voicegroup_ptr` 字段（+0x04）而不是表头起点。本结构**不是**剧情表，而是 sound id 1 的 **m4a SongHeader**（由 sound-ID 表 `0x465B70` 的第 1 行指向）；**轨数据的块级格式已逐字段拆解**（2026-10-21）：「block 表」就是 SongHeader 本身 —— `+0x00` u8 轨道数、`+0x01` u8（本 ROM 全为 0 且引擎不读）、`+0x02` u8 优先级、`+0x03` u8 标志（bit7 = 混响）、`+0x04` u32 voicegroup 指针、`+0x08` 起 `u32 track_ptr[轨道数]`；每个 `track_ptr[i]` 指向一个**无头**的 block —— 扁平命令流，以 FINE（`0xB1`）结束、其后是 0x00 padding。命令编码：`0x00-0x7F` 是**续写字节**（running opcode 的操作数）、`0x80-0xB0` 是 WAIT、`0xB1-0xCE` 是命令表（`0x08464534`，30 项，索引 `op-0xB1`）、`0xCF-0xFF` 是 NOTE（0~3 个可选参数字节）。**running opcode 规则**（`0x0809A4F8 cmp r1,#0xbd` / `0x0809A4FC strb r1,[r5,#7]`）：**所有 `>= 0xBD` 的 opcode 都更新 running opcode**（不只是音符）。循环：GOTO `0xB2`（4 字节**小端**目标）、PATT `0xB3`（栈深 3）、PEND `0xB4`（空栈 = 继续）、REPT `0xB5`（`count` + 目标，count 0 = 无限）。往返自检：5 首曲子 45 个 block（9952 字节 / 6333 条命令）**45/45 逐字节相同**。见 `notes/evidence/m4a-block-table-20261021.md`） |
| m4a SongHeader（sound id 2） | `0x536BC4` | ✅ | ✅ | **L3** | notes/evidence/story-table-family-20261020.md；notes/evidence/m4a-block-table-20261021.md | —（已更正：旧基址 0x536BC8 晚了 4 字节 —— 它锚在 `voicegroup_ptr` 字段（+0x04）而不是表头起点。本结构**不是**剧情表，而是 sound id 2 的 **m4a SongHeader**（由 sound-ID 表 `0x465B70` 的第 2 行指向）；**轨数据的块级格式已逐字段拆解**（2026-10-21）：「block 表」就是 SongHeader 本身 —— `+0x00` u8 轨道数、`+0x01` u8（本 ROM 全为 0 且引擎不读）、`+0x02` u8 优先级、`+0x03` u8 标志（bit7 = 混响）、`+0x04` u32 voicegroup 指针、`+0x08` 起 `u32 track_ptr[轨道数]`；每个 `track_ptr[i]` 指向一个**无头**的 block —— 扁平命令流，以 FINE（`0xB1`）结束、其后是 0x00 padding。命令编码：`0x00-0x7F` 是**续写字节**（running opcode 的操作数）、`0x80-0xB0` 是 WAIT、`0xB1-0xCE` 是命令表（`0x08464534`，30 项，索引 `op-0xB1`）、`0xCF-0xFF` 是 NOTE（0~3 个可选参数字节）。**running opcode 规则**（`0x0809A4F8 cmp r1,#0xbd` / `0x0809A4FC strb r1,[r5,#7]`）：**所有 `>= 0xBD` 的 opcode 都更新 running opcode**（不只是音符）。循环：GOTO `0xB2`（4 字节**小端**目标）、PATT `0xB3`（栈深 3）、PEND `0xB4`（空栈 = 继续）、REPT `0xB5`（`count` + 目标，count 0 = 无限）。往返自检：5 首曲子 45 个 block（9952 字节 / 6333 条命令）**45/45 逐字节相同**。见 `notes/evidence/m4a-block-table-20261021.md`） |
| m4a SongHeader（sound id 8） | `0x538FEC` | ✅ | ✅ | **L3** | notes/evidence/story-table-family-20261020.md；notes/evidence/m4a-block-table-20261021.md | —（已更正：旧基址 0x538FF0 晚了 4 字节 —— 它锚在 `voicegroup_ptr` 字段（+0x04）而不是表头起点。本结构**不是**剧情表，而是 sound id 8 的 **m4a SongHeader**（由 sound-ID 表 `0x465B70` 的第 8 行指向）；**轨数据的块级格式已逐字段拆解**（2026-10-21）：「block 表」就是 SongHeader 本身 —— `+0x00` u8 轨道数、`+0x01` u8（本 ROM 全为 0 且引擎不读）、`+0x02` u8 优先级、`+0x03` u8 标志（bit7 = 混响）、`+0x04` u32 voicegroup 指针、`+0x08` 起 `u32 track_ptr[轨道数]`；每个 `track_ptr[i]` 指向一个**无头**的 block —— 扁平命令流，以 FINE（`0xB1`）结束、其后是 0x00 padding。命令编码：`0x00-0x7F` 是**续写字节**（running opcode 的操作数）、`0x80-0xB0` 是 WAIT、`0xB1-0xCE` 是命令表（`0x08464534`，30 项，索引 `op-0xB1`）、`0xCF-0xFF` 是 NOTE（0~3 个可选参数字节）。**running opcode 规则**（`0x0809A4F8 cmp r1,#0xbd` / `0x0809A4FC strb r1,[r5,#7]`）：**所有 `>= 0xBD` 的 opcode 都更新 running opcode**（不只是音符）。循环：GOTO `0xB2`（4 字节**小端**目标）、PATT `0xB3`（栈深 3）、PEND `0xB4`（空栈 = 继续）、REPT `0xB5`（`count` + 目标，count 0 = 无限）。往返自检：5 首曲子 45 个 block（9952 字节 / 6333 条命令）**45/45 逐字节相同**。见 `notes/evidence/m4a-block-table-20261021.md`） |
| map-sprites | `0x53F140` | ✅ | ✅ | **L3** | notes/evidence/consumer-evidence.json::0x0853F140 | 描述符记录内部字段名未定。已收窄：记录**变长自描述**（实测 12 或 28 字节交替），不是旧笔记说的「11 个字」；每条以一个 u32 ROM 指针开头，末尾带下一条记录的地址（已更正：权威基址 `0x53F140`（86 项 u32 指针表）；bank 里的 `0x53F1DC` 是它的第 39 项窗口） |
| save-state | `0x53D848` | ✅ | ✅ | **L3** | tools/mgba_probe/l3_evidence_sweep.py；notes/evidence/consumer-evidence.json::0x0853D848 | —（已更正：`0x53D848` 已证实是 **WRAM 分配表**（10 组 `{u32 wram_addr, u32 size}`，4 个原生读者 `0x0806869A / 0x08068954 / 0x08068CC0 / 0x08068D98`），**不是**存档描述符表 —— 存档数据在 SRAM，不在 ROM） |
| units | `0x53F298` | ✅ | ✅ | **L3** | tools/mgba_probe/l3_evidence_sweep.py；notes/evidence/consumer-evidence.json::0x0853F298 | —（已更正：`0x53F298` **不是**「u16[64] 角色 ID 表」，而是 **43 项的 u16 重映射表**（{0..48} 去掉 {14,15,16,17,19,20} 的排列）；旧框架还横跨了`0x53F2EE`（16 项有符号增量表，读者 `0x08080AE0`）与 `0x53F318`（代码指针表）另外两张结构；消费者的取值方式已由原生代码证明：表值 **加上 WRAM `0x0202CA24` 的 u16**（运行时值）后 **掩到 16 位** ⇒ 目标是 64 KB 窗口内的索引。2026-07-11 笔记提出的可证伪判据「是否加到某个基址上」**已证实**；因为基址是运行时量，写回仍须限制在原生出现过的取值内 —— 见 `notes/evidence/units-offset-table-20261020.md`） |
| 任务文字三表（标题/说明/提示） | `0x348DAC` | ✅ | ✅ | **L3** | tools/fixtures_extended.py::mission_text；notes/evidence/consumer-evidence.json::0x08348DAC | — |
| 关卡数据块表（bank 名为 cutscene-scripts） | `0x53DF70` | ✅ | ✅ | **L3** | notes/evidence/cutscene-block-format-20261020.md；tools/mgba_probe/l3_evidence_sweep.py；notes/evidence/consumer-evidence.json::0x0853DF70 | —（已更正：`0x53DF70` **不是剧情 VM 脚本表**，而是**关卡数据块表**：**4 项 × 8 字节**，每项一对指针（LZ77 4bpp 图块 → VRAM `0x06016000`、LZ77 16 色调色板 → 调色板 RAM `0x05000380`），由 BIOS `svc 0x12`（LZ77UnCompVram）解压 —— 剧情 VM 从头到尾没碰过这些块；旧结构库「16 项 × u32」**作废**：原生步长是 8 字节；旧的 16 槽模型允许下标越过表尾写进下一张表（`0x53DFB0`）；**「这四块对应哪四张原版战斗地图」的前提已被证伪**（2026-10-21）：四个块用 BIOS `svc 0x12` 解压出 **4096/4096/4096/2048 字节**（= 128/128/128/64 张 4bpp 图块），而 47 个战斗地图描述符的原图图块集只有 **156–276 字节（4–8 张图块）**；把每张地图的图块集逐张（32 字节）对上四个块的图块集合，**一张都匹配不上**。所以它们是**关卡/过场自己的 4bpp 图块集**，不是战斗地图的图块集；**加载器已被自然触发（2026-10-22）** —— 旧注记「55 个剧情场景、开机流程、真实战斗里加载器一次都没命中，属于剧情/战斗之外的第四种模式，本轮探针能到达的范围内无法触发」**作废**：**相位 `0x0118`**（`0x0808F94A`：置战斗标志 bit 1 → `bl 0x080732B4` 跑剧情战斗 → 清标志）就能命中判定点 `0x08072F0E`，此时 **`r4 = 0x0853DF70`**、表首 32 字节被 dump 出（4 条 8 字节记录，word0 = ROM 源地址 `0x0812xxxx`）。同时更正：**表读取没有前提条件** —— `0x08072EEE` 处的 `cmp r2,#0 / beq 0x08072F0C` 只决定要不要顺手置标志，`beq` 直接跳到装载指令，两条路径都会读表。见 `notes/evidence/cutscene-scripts-l3-20261022.md`） |
| 函数指针表（0x53D5F0，13 槽 u32） | `0x53D5F0` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-final-20261021.md；notes/evidence/consumer-evidence.json::0x0853D5F0 | 记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址 0x53D5F4 是槽 1；槽 0 与槽 12 是 FFFFFFFF 哨兵，槽 1..11 是 11 个代码指针（0x08061C8D 起每槽 +12 字节等距）） |
| 剧情底图表 | `0x59903C` | ✅ | ✅ | **L3** | tools/fixtures_extended.py::background_table；tools/mgba_probe/l3_evidence_sweep.py；notes/evidence/consumer-evidence.json::0x0859903C | —（已更正：8bpp 底图条目用哪一路 BG、是否开 256 色模式**已闭环**（2026-10-21）：底图加载器 `0x08088348` 的第二个参数就是 **BG 号**（`0x0808835C`），运行时遍历 **55 个剧情场景**读到**每一次都是 BG0**（`DISPCNT` bit 8，`0x080883EA` 写 `1 << (8+BG)`），**8bpp 底图走 BG0**。256 色模式确实开着，但**位号是 `BGxCNT` bit 7（0x80），不是 bit 8**（bit 8 是屏幕基址块的最低位）—— 写入点在 `0x0808840E`（`movs r0,#0x80` / `orrs r3,r0`），4bpp 分支（`0x0808840C beq`）不置这一位。运行时 IO 抓取：8bpp 场景（50 / 47）`BG0CNT = 0x0087`（bit7 = 1），4bpp 场景（40）`BG0CNT = 0x0007`（bit7 = 0），`DISPCNT = 0x1F40`。底图表 320 条里有 **192 条**是 8bpp（`条目+0x0C != 0`）；8bpp 条目与 4bpp 条目**互斥**，不是图层：每条都是一整张 32×32 硬件 BG 地图（320 个真实条目 + 704 个填充条目 = 正好 2 KB 一屏；4bpp 填充 tile 0、8bpp 填充 tile 30），走同一个 loader、同一批 VRAM 槽、同一个调色板 bank；旧结论「8bpp 条目的层叠关系未还原」**作废** —— 不存在层叠） |
| 图块/精灵资源记录表（0x5A320C，68 字节/条 x 79） | `0x5A320C` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-final-20261021.md；notes/evidence/consumer-evidence.json::0x085A320C | 记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址 0x5A3218 是记录 0 的 +0x0C 指针块窗口（6 个 u32），不是表基址；记录数 79 由「指针块结构在 0x5A4708 处干净断裂」确定。2026-10-21 补充：本表有 **9 个**字面量读者（0x08087E30 / 0x0809851C / 0x08098840 / 0x08098AF0 / 0x08098DB0 / 0x08098FC0 / 0x08099464 / 0x08099698 / 0x08099D10），旧笔记只记了 2 个） |
| 处理程序分派表（0x53E698，8 字节/条 x 256） | `0x53E698` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-final-20261021.md；notes/evidence/consumer-evidence.json::0x0853E698 | 记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址 0x53E6D8 是本表第 8 条起、只读每条第一个 u32 的错位窗口；真实基址 0x53E698 有 2 个原生读者（决策点 0x0807F934 与 0x0807FD36），表尾正好接精灵帧描述符表 0x53EE98。2026-10-21 更正：消费者不是 fn 0x0807F414（它不读本表）；两个派发点都用 **同一个 u8 索引字节 0x02027350**，0x0807FD36 处是 'ldrb r0,[sb+0x770]' -> '*8' -> 'ldr' -> 'bl 0x0809C114'） |
| 处理程序分派表（同表，0x53E698 另一个窗口） | `0x53E698` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-final-20261021.md；notes/evidence/consumer-evidence.json::0x0853E698 | 记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址 0x53EB08 = 0x53E698 + 142*8，是 8 字节记录按 4 字节步长读出来的窗口；map-events 与 battle-handlers 是同一张表） |
| 头像指针表（0x5A4DEC，40 字节/条 x 63） | `0x5A4DEC` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-final-20261021.md；tools/mgba_probe/l3_evidence_sweep.py；notes/evidence/consumer-evidence.json::0x085A4DEC | 记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址 0x5A5774 = 0x5A4DEC + 61*40，是头像表第 61..62 行的窗口，不是独立的菜单 UI 表；读者 0x08096158 按 id*40 + expr*8 索引） |
| 头像表 + 拼块表 | `0x5A4DEC` | ✅ | ✅ | **L3** | tools/fixtures_extended.py::portrait_table；tools/mgba_probe/l3_evidence_sweep.py；notes/evidence/consumer-evidence.json::0x085A4DEC | —（已更正：头像素材 = BIOS LZ77（`svc 0x11`）解压的 **6400 字节 8bpp 图形** + **128 字节原始 BGR555 调色板**；每条表情的压缩预算 2320–4008 字节，310 条表情全部能用回引用 LZ77 **压得更小**（余量 11–51 字节）⇒ 写回可行；旧的「80*80/2 = 6400 字节 4bpp」算法**作废**：6400 字节是 8bpp（100 张 64 字节图块）；有效头像是 **62 个 id / 310 条表情**（行 63 的指针不在 ROM 内，是垃圾指针）；2026-10-21：「参数 << 4」的语义**已由原生代码钉死**（`0x080961D6`..`0x080961F8`）：它是 `if (byte != 0) byte = (byte + (param << 4)) & 0xFF`，只作用于解压后 6400 字节里的**前 6144 字节**。**同一个 `param` 决定调色板槽 `0x05000200 + param*32`**（整张 64 色调色板被 CpuSet 进去），所以这次改写是**调色板索引平移**（把实际使用的 16 色窗口重基到 0..15），**不是描边、也不是换色**。旧结论「换色/描边未证实」**作废**。**运行时读数已拿到**（`tools/closure_portrait_probe.py`，场景 1 与 5 各一次）：在头像加载器的 VRAM 拷贝点 `0x08096202` 断下，**WRAM 暂存缓冲 `0x02002880` 的前 6144 字节**与「ROM LZ77 解压结果 + 单个 `param<<4` 平移」**逐字节相等（0 不符）**，其中 `param<<4 = 0x40`（param = 4）—— 差分直方图只有这一个值，作用在 4309 个**非零**字节上，**零字节一个都没动**。**比对目标必须是 WRAM 暂存缓冲**：VRAM `0x06011900` 装的是**6 块拼好的 80×80 成品**，布局与源图不同（旧工具拿它跟单块源图比，得出 4925 个不符 —— 那是**模型错了**，不是数据错）；另外暂存缓冲**尾部 256 字节不是 ROM 的尾部**（是这块共享缓冲的残留），所以「后 256 字节不动」应理解为「后 256 字节不属于图形」。；2026-10-21：拼块表 `portrait_pieces`（`0x4643C0`）的**基址已闭合** —— 旧说「`0x084643C0` 零字面量读者 ⇒ 拿不到基址」**作废**：这张表的地址是指针，存放在静态描述符 `0x0846443C` 的**首字**，而该描述符地址被 **7 处原生代码**加载（`0x08077D12` / `0x08089B06` / `0x0808B356` / `0x08091036` / `0x08091680` / `0x08093846` / `0x08096618`，其中 `0x08096618` 在头像加载路径上）。运行时读数（`tools/closure_portrait_pieces.py`）：描述符首字读出 **`0x084643C0`**，6×20 = 120 字节与 ROM **逐字节相等**。6 条记录字段 = 「起始 tile / 0 / x / y / w / h / 0x0100 / 0x0100 / 0x20FF / 0」，**无重叠**拼出 80×80（256+512+512+512+512+4096 = 6400）。顺带钉死池结构：源 tile 100 张来自条目 u32[0] 的 LZ77 头像（解压正好 6400 字节），另外 **36 个空位**（4..7 / 16..23 / 32..39 / 48..55 / 64..71）是**表情差分**（条目 u32[1] 的原始图块数据）的落点） |
| 字宽表（0x53E596，1 字节/条 x 256，按字符码索引） | `0x53E596` | ✅ | ❌ | **L3** | notes/evidence/fonts-spriteframe-l3-20261022.md；notes/evidence/consumer-evidence.json::0x0853E596 | 记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址 0x53E5B4 晚了 30 字节；唯一原生读者 0x0807F0FC 用 'ldrb' 取字符码后加到 0x0853E596 取宽度，所以表长是 256（与字符码一一对应）。2026-10-21 更正：旧笔记说「消费者是 fn 0x0807EE50」**不成立** —— fn 0x0807EE50 读的是另一张表 0x0853E328（字形度量，6 字节/字形）；0x0853E596 全 ROM 只有 1 处字面量引用（0x0807F114），消费者函数是 0x0807F064 起的那段。索引字节与 battle-handlers 共用：u8 @ 0x02027350） |
| 字形段表 / 文本编码 | `0x53D644` | ✅ | ✅ | **L3** | tools/font_roundtrip.py；tools/mgba_probe/screen_text.py；notes/evidence/consumer-evidence.json::0x0853D644 | —（已更正：反向映射已从「取最小码位」改为**规范码**：基础 GB2312 序里的那个码（扩展块里的同字是冗余拼写，不规范）。证据与 5 条可证伪检验见 `notes/evidence/font-reverse-mapping-20261020.md`；**「8 个字符两个码位」在字节级不再是歧义**（2026-10-21）：ROM 的 **9141 个真实文本块**逐个做「码级 token 流 → 字节」往返，**9141/9141 逐字节相同**（含全部 794 个含双码位字符的块）。唯一且字节精确的表示是**码级 token 流**；`tools/text_codec.py::encode_tokens` 直接写码、不走「字符 → 码位」反查表，所以对两种拼写都精确。「字符 → 码位」只是方便层，在这 8 个字符上**必然有损**，规范码是**约定**而不是唯一解） |
| 对白文本写回（字形码） | `0x461CE8` | ✅ | ✅ | **L3** | tools/verify_text_writeback.py | —（已更正：`tools/find_sjis_blocks.py` 与 `tools/decode_dialogue_record.py` **已改用** `tools/text_codec.py`，不再依赖旧手工表 `sequel/content/text/sjis-to-tile-mapping.json`；**「`sequel/editor.db` 被 gitignore ⇒ 纯净检出下 override 链空转」已解决**：新增 `tools/build_editor_db.py`，从仓库内容（`sequel/content/*/bank.json`）**重建**数据库，并当场验证「编辑器 → 构建」链真的产出补丁（实测 applied 5533 / rejected 549）；`--check` 模式会逐个生成器报 applied/rejected，「全部被拒」就是基址或字段名过期的信号。见 `notes/evidence/editor-db-override-chain-20261021.md`） |
| 忍具名表 | `0x599634` | ✅ | ❌ | **L3** | tools/fixtures_extended.py::ninjutsu_names；notes/evidence/consumer-evidence.json::0x08599634 | — |
| 战斗奖励表 | `0x59EAE0` | ✅ | ✅ | **L3** | tools/synthetic_fixture.py::reward_entry；notes/evidence/consumer-evidence.json::0x0859EAE0 | 记录尾部 +0x16 / +0x17 两个字节语义未定（112 条全为 0、无消费者读取）；类别 3（技术）的取值域只能由代码给出上界，因为本 ROM 的 112 条记录里没有一条用类别 3（已更正：尾部低字节已定为**奖励类别标签**（0=忍具 / 1=强化素材 / 2=认识卡 / 3=技术），不是数量也不是档位；条目步长已由消费者证明为 **24 字节** —— 旧笔记的 16 字节说法作废；类别 → 名字表对应由 ROM 自带的 4 槽指针表 `0x0859F5E0` 证明（`0x0808A02A` 载入，用尾字节做下标），不再只靠四个 arm 各挂一张字面量；328 个尾部槽位的 id **全部落在各自类别的名字表容量内**（0 越界）） |
| 战斗胜负条件表 | `0x594758` | ✅ | ✅ | **L3** | tools/synthetic_fixture.py::battle_rules；tools/mgba_probe/l3_evidence_sweep.py；notes/evidence/consumer-evidence.json::0x08594758 | —（已更正：`0x0202680C` **就是回合计数**（2026-10-21，旧的「不是回合计数」结论**作废**）：它是战斗控制块 `0x02026804` 的 **+8** 字节，类型 2 的胜利条件正是「`0x0202680C` == `ctrl[6]`（回合上限，`0x0202680A`）」（`0x08077914`..`0x0807791A`；上限为 0 时该规则不生效）。运行时读数（`tools/closure_round_probe.py`，组 9 / 子 0）：只按 A 时战斗停在界面、计数不动；**按 DOWN + A 真的把回合打完**时，计数从 **1 变 2**。旧审计「40 轮按键全程为 0」的那次读数是因为**战斗没推进过回合**；类型 2 的判据已由原生代码证明为**回合上限到达**（`0x08077904` 比对 `ctrl[6]`=回合上限 与 `byte[0x0202680C]`），而且**从不读 `rule.a` / `rule.b`** —— 旧笔记「与类型 3 成对出现、意图是类型 3 的反面」的说法**作废**：它本来就不看 a/b，所以成对出现没有语义冲突；类型 3 = 「指定角色已离场」（`rule.a`=阵营、`rule.b`=角色 id，判据在 `0x020240C0` 的 12 个单位槽）） |
| 战斗遭遇记录表（0x54229C，16 字节/条） | `0x54229C` | ✅ | ❌ | **L3** | notes/evidence/remaining-rebase-leads-20261021.md | 记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址错位，已更正为 `0x54229C`（详见 notes/evidence/remaining-rebase-leads-20261021.md）） |
| 技能 bank（0x546100，与 items 同址） | `0x545BE4` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-nearby-20261020.md | 记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址 `0x546100` 是这张表的**第 81 条 + 12 字节**的错位窗口；真基址是 `0x545BE4`（16 字节/条，94 条，7 个原生读者）；与 `items` 同址已裁决：同一张表，规范名 `skills`） |
| 技能表（bank 名为 battle-config） | `0x545458` | ✅ | ✅ | **L3** | tools/fixtures_extended.py::skill_table；notes/evidence/consumer-evidence.json::0x08545458 | —（已更正：`0x545458` 已确认为 16 字节记录表（87 条），不是 u32 指针表 —— 旧结论作废，写回路径见 `tools/import_character_template.py`） |
| 数据指针表 A（0x5A143C，u32 ROM 指针 x 46） | `0x5A143C` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-final-20261021.md；notes/evidence/consumer-evidence.json::0x085A143C | 记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址 0x5A14A4 = 0x5A143C + 26*4；46 项全部是 ROM 指针。2026-10-21 补充：本表有 **2 个**字面量读者 0x0808A704 与 0x0808B214，旧笔记只记了后者） |
| 数据指针表 B（0x5A2034，u32 x 90） | `0x5A2034` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-final-20261021.md；notes/evidence/consumer-evidence.json::0x085A2034 | 记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址 0x5A2120 = 0x5A2034 + 59*4；90 项里 79 项是 ROM 指针） |
| 机关效果表 / 拾取分派表 / 建立期分支 | `0x0808136C` | ✅ | ❌ | **L3** | notes/mechanisms-20261020.md；notes/evidence/consumer-evidence.json::0x0808136C | —（已更正：**这张表不是数据表，是 13 项函数指针跳转表**（2026-10-22）：`0x08081350: ldr r1,[pc,#0x14]` 装 `0x0808136C`、`0x08081352/54/56` 算 `&表[下标]` 并 `mov pc, r0` —— Thumb-2 switch 惯用法，下标 = 传入值 - 1，必须落在 0..12。旧注记把它当「13 项效果表」是错的；target 9 **根本到不了效果表**：`0x08081984` 先把它截走，走「两个剧情 VM 脚本 + 计数器 + 单位 `+0xCE += 25`」的分支；表槽 `0x0808138C → 0x080814CC` 是死代码；target 11 是**空操作**：`0x08081394 = 0x080814CC`，直接落到共享收尾（关窗 → 播 `config[0]` BGM → 等按键），而且原版 46 关里一次都没用过 target 11；type 5/6/7 **不决定脚本**，脚本由 target 决定：`0x080815E4[4]=[5]=[6]=0x08081984` 共用一个处理分支；type 只决定运行时对象类型（3/4/5-6 ⇒ 精灵 + 拾取音效）；旧结论「13 项效果表中 target 9/11 语义未定」**作废**；**运行时读数已取得（2026-10-22）**：路线是剧情战斗 `fn 0x080732B4` → `0x0807498C` → `fn 0x08081544`（第二个关卡对象处理器，按 `record+4` 做 7 路分派）→ `0x08081ADE` → `fn 0x080812DC` → 读 `0x0808136C`。判定点 `0x08081350` 命中，`r2 = 1` = 机制下标（= `record[+6]`）。见 `notes/evidence/mechanism-effects-l3-20261022.md`） |
| 精灵动作表 | `0x596CCC` | ✅ | ✅ | **L3** | notes/sprite-frame-format-20261020.md；notes/evidence/consumer-evidence.json::0x08596CCC | —（已更正：ROM `0x25A8E5` 的字节已定为 **`0xFF`**：它是 4 字节终止符 `ff ff 00 00` 里 u16 `tile` 的高字节。把这一字节改成 `0xFF` 后，全 ROM 的完整终止符数量恰好 +1（复核：5546 → 5547），且合法的最大 tile 下标只有 **768**（`0xFBFF`=64511 超出取值域 84 倍）；「帧描述符上限 32 片」**不是 ROM 约束**：实测单帧最多 **5** 片（分布 1 片 2562 / 2 片 70 / 3 片 26 / 5 片 16），触到 32 的条目为 0） |
| 精灵动作表（0x596CCC，id*144 + action*16） | `0x596CCC` | ✅ | ❌ | **L3** | notes/evidence/consumer-evidence.json::0x08596CCC | —（已更正：旧基址 0x53F200 是 0x53F140 起的指针数组第 48 项起的 38 字节窗口，不是独立表；真实基址 0x596CCC 有 18 个原生读者，条目 = 4 个 u32 指针 (frames, animations, gfx, palette)；本 bank 与 `sprite-action-table` 是同一张表；写回路径与判死检验统一走 `sprite-action-table`（见 tools/writeback_paths.py 的 `sprite-action-table` case），本行只作别名留档） |
| 精灵帧描述符表（0x53EE98，10 字节步长） | `0x53EE98` | ✅ | ❌ | **L3** | notes/evidence/units-offset-table-20261020.md | 五个 u16 字段（+0 类别/链表结束、+2/+4 有符号量、+6 类别、+8 结束标志）的业务名未定（已更正：这张表此前**完全没有被登记**：它在 ROM 里有 3 个原生读者（`0x080806BA` / `0x0808077E` / `0x0808082E`），步长 10 字节、15 条记录（`0x53EE98`..`0x53EF2E`）；它之所以查不到，是因为 `notes/evidence/consumer-evidence.json` 只存了 54 张表，而字面量索引有 18051 个值（1196 个是活的）—— 邻域分析必须查全量索引；暂列**只读参考**：五个字段的业务名都还没定，写它没有可写的已知字段；**运行时读数已取得（2026-10-22）**：读者 `fn 0x08080670` 在`--force-dispatch` 路线上命中，判定点 `0x080806BC` 处 `r1 = 0x0853EE98`（表基址）、`r4 = 0x0853EEA2 / 0x0853EEB6 / 0x0853EED4` = **基址 + 下标 × 10**，**步长 10 字节得到运行时证实**。见 `notes/evidence/fonts-spriteframe-l3-20261022.md`） |
| 角色定义表 | `0x54241C` | ✅ | ✅ | **L3** | notes/character-template-format-20261020.md；tools/mgba_probe/l3_evidence_sweep.py；notes/evidence/consumer-evidence.json::0x0854241C | 12 字节头的 +0x00 / +0x07、以及 0x545458 记录里的 +0x00/+0x01 与 +0x03/+0x0A/+0x0B/+0x0D/+0x0F 语义未定；条目字节 4（pad）未定（已更正：`0x545458` 已确认为 **16 字节忍术记录表**（87 条，下标 = 忍术 id），不是 u32 指针表 —— 旧结论作废，写回路径见 `tools/import_character_template.py`；`+0x0A` 已由原生代码证明是**体力基数**（`0x0806DA46`），不再存疑；仓库内已有可复现提取器 `tools/character_templates.py` 与往返自检（`tools/writeback_paths.py::character-template`）） |
| 角色特性表（0x5459C8，12 字节/条） | `0x5459C8` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-nearby-20261020.md；notes/evidence/consumer-evidence.json::0x085459C8 | 记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址错位，已更正为 `0x5459C8`（详见 notes/evidence/legacy-rebase-nearby-20261020.md）） |
| 资源指针表（0x596CCC，与精灵动作表同址；旧基址 0x596F0C 是其 +0x240 窗口） | `0x596CCC` | ✅ | ✅ | **L3** | notes/evidence/resource-pointers-deadcode-20261022.md；notes/evidence/consumer-evidence.json::0x08596CCC | 记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：2026-10-22：旧基址 `0x596F0C` 是精灵动作表 `0x596CCC` 的第 36 项窗口（+0x240），**不是独立的资源指针表**；全 ROM 里 `0x596F0C` 只出现一次（池项 `0x0807B278`），由 `0x0807B220` 装载，而该指令在 `fn 0x0807AE04` 的 **case 7** 里 —— case 7 只能由 `arg1 = 7` 进入，两个 `arg1 = 7` 的调用点（`0x0807C3D6` / `0x0807C4D6`）都在 `fn 0x0807B8B8` 的循环里，该循环入口把 `r8` 硬编码成 2，`0x0807C4CC: cmp r0,#1` 永远失败 ⇒ **两处都是死代码**。运行时阴性对照（20 场剧情战斗）：同路线 items 读者命中 72 次，资源读者 0 次、`arg1=7` 调用点 0 次。⇒ 本 bank 按 `LEGACY_REBASE` 的先例重定基址到 `0x596CCC`（有活着的原生读者 `0x0806B76C` 真正装载的那个基址），与 `sprite-animations` / `sprite-action-table` 同址；旧结论「唯一原生读者是 `0x0807B220`」**作废**。详见 `notes/evidence/resource-pointers-deadcode-20261022.md`） |
| 运行时状态（WRAM 字段） | `—` | ✅ | ❌ | **L3** | notes/runtime-and-object-tables-20261020.md | —（已更正：运行时读数已闭环：`scene_id`（`0x020311EA`）在开场剧情里是 **54 → 50 → 40**，`battle_stage`（`0x02026805`）= 40、`battle_sub`（`0x02026806`）= 0、队伍槽 1（`0x02022EF0`）= 角色 1（漩涡鸣人）等级 1；旧推断「`0x020311EA` 是场景号」**已被运行时读数证实**；**`story_config[0]` 的非零读数已闭合（2026-10-22）**：旧归因「由调度器 `0x0808F5C8` 写入、`0x0808F5CC` 随即清零，所以任何快照都拍不到」**归因错误** —— 逐指令核对显示 `0x0808F5C8` **只**在「before」路径上执行，而那条路径的前提正是 `state[0x18] == 0`，所以调度器**恒写 0**；真正的写入者是剧情 VM 的 **opcode `0x1F`**（`0x08097C40: strb r0,[r1,#0x19]`，操作数 = 战斗 sub-config）。场景 **2/3/4/6/7** 的 before 脚本都用 `1F 01`，因此游戏自己会写 **1**。实测（`tools/mgba_probe/runtime_state_probe.py`，场景 2 + 作答行 1）：`0x08097C40` 命中、`r0 = 1`、内存 `0x020311ED` = **`0x01`** ⇒ 非零读数成立。见 `notes/evidence/runtime-state-story-config-20261022.md`；`story_progress` = `0x020311E4`（u16，VM 的「设进度」opcode 在 `0x08097BD4` 置成绝对值；调度器在 `0x0808F5E0` 跟 **360** 比较）；`story_branch` = `0x020311EC`（u8，调度器在 `0x0808F5A0` 读它来选「after」根表，`0x0808F5CC` 清零；**场景 31** 读出 **1**）；`story_config` = `0x020311ED..EF`） |
| 逐角色属性表（0x545068，16 字节/条） | `0x545068` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-nearby-20261020.md；notes/evidence/consumer-evidence.json::0x08545068 | 记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址错位，已更正为 `0x545068`（详见 notes/evidence/legacy-rebase-nearby-20261020.md）） |
| 逐角色属性表（同表，0x545068 另一个错位窗口） | `0x545068` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-nearby-20261020.md；notes/evidence/consumer-evidence.json::0x08545068 | 记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址错位，已更正为 `0x545068`（详见 notes/evidence/legacy-rebase-nearby-20261020.md）） |
| 道具/技能记录表（0x545BE4，与 skills 同址） | `0x545BE4` | ✅ | ❌ | **L3** | notes/evidence/legacy-rebase-nearby-20261020.md | 记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废）（已更正：旧基址 `0x546100` 是这张表的**第 81 条 + 12 字节**的错位窗口；真基址是 `0x545BE4`（16 字节/条，94 条，7 个原生读者），表尾正好接战斗编成矩阵 `0x5461C4`） |
| 遭遇区 bank（0x53D910，与 maps 同址） | `0x53D910` | ✅ | ✅ | **L3** | tools/mgba_probe/l3_evidence_sweep.py；notes/evidence/consumer-evidence.json::0x0853D910 | —（已更正：与 `maps` 同称 `0x53D910`：已裁决为**同一张表**的别名，规范名 `maps`；旧结论「地图描述符从 `0x53D914` 起」**作废** —— 那是旧逻辑的错误基址；原生 loader `0x08069040` 直接以 `0x0853D910` 为基址、步长 32 字节，首条目就是 `0x53D910`（见 `notes/battle-config-unsafe-template-fix-20260710.md`）） |
| 音频 sound-ID 表 | `0x465B70` | ✅ | ❌ | **L3** | notes/resource-locations.md；tools/extract_audio.py；notes/evidence/consumer-evidence.json::0x08465B70 | —（已更正：**DirectSound 弯音（pitch bend）插值已实现**（2026-10-21）：引擎的弯音链已按本 ROM 的代码逐条转写并用探针对拍：BEND(0xC0) 写 `通道+0x0E = 操作数-0x40`（`0x0809A368`）、BENDR(0xC1) 写 `通道+0x0F = 量程`（`0x0809A37C`，复位默认 2，`0x0809A4D6`）；累加器 `0x0809B450`..`0x0809B486` 给出 `S = (tune + bend*range)*4 + (keyShift<<8)`、`通道+0x08 = (s8)(S>>8)`（半音偏移）、`通道+0x09 = (u8)S`（分数）；音高键 = 音符键 + 半音偏移（负则夹 0，`0x0809A8A2`），DirectSound 音高 = `((f(k) + ((f(k+1)-f(k))*fraction>>8)) * wave[4]) >> 32`（`0x0809A998`；`>>32` 来自 ARM 态助手 `0x08099D80`）。`tools/audio_song_export.py` 现在算的是**同一套整数**，并用 `tools/closure_pitch_check.py` 对拍引擎自己的读数：**179 条引擎音高读数 0 处不符**（含弯音分数 128/160 与半音偏移 +4/−1）。五个原生曲子的 PSG 导出仍与 ROM 原始字节逐事件相符（616/534/746/612/498）；**PSG 频率表只有 12 项有符号 16 位**（`ldrsh` @ `0x0809B4FE`），不是 16 项无符号 —— 旧工具读 16 个 u16，**读进了噪声表**；旧工具还有 `+0x800` 偏置、算术右移、噪声 key 重映射（`key<=20 ? 0 : min(key-21,59)`）与 `key-36` 先减后夹的顺序错误。现在五个已知 SongHeader 的 PSG 事件数（616/534/746/612/498）已与 ROM 原始字节逐条对上；m4a 引擎语义（tempo `0x0809A2E8`、tick 栅格 `0x0809A474`/`0x0809A5C6`、命令表 `0x08464534`、音符频率 `0x0809A998`、PSG 频率 `0x0809B494`、循环 `0x0809A25C/27C/298/2AC`）已按**本 ROM 的代码**逐条反汇编证实；**块级轨道重写已实现**（2026-10-21）：block 表就是 SongHeader 本身，`track_ptr[i]` 指向无头的命令流（FINE 结束）；`tools/m4a_block_table.py` 的 decode→encode 对 45 个原生 block **逐字节相同**，并支持就地重写 / 重建 / 停在自由区并改指针；`tools/import_audio_song.py --block trackN=json[,offset]` 已接上，写回自检新增 case `audio-block-1`（19/19 PASS）；**running opcode 规则已修**：`0x0809A4F8 cmp r1,#0xbd` 表明**所有 `>= 0xBD` 的 opcode 都更新 running opcode**（不只是音符）；旧解码器只在音符时更新，把 MOD/EOT 的参数读成了 key=0 的假音符（101 字节 / 11 条轨道）。修完后两个独立解码器**零分歧**） |
| Sappy 引擎 bank（0x079668，已被证伪） | `0x079668` | ❌ | ❌ | **none** | —；[基址已裁决：ROM 零引用] | —（已更正：**已退役**（`tools/table_registry.py::RETIRED`）：0x08079668 已证实是文本/消息对象分派函数，不是 Sappy 音频分发器；bank 里的 command_handlers / event_audio_mapping 结论作废） |
| 调色板 bank（已退役：是 map-sprites 的别名窗口） | `0x53F138` | ❌ | ❌ | **none** | —；[基址已裁决：ROM 零引用] | —（已更正：**已退役**（`tools/table_registry.py::RETIRED`）：`0x53F138` 只是 `0x53F140` 起的 86 项 u32 指针数组头部 2 个代码指针的窗口；那里不是 RGB555 调色板。真正的调色板数据在 `0x05000380`（VRAM 调色板 RAM，由 `0x53DF70` 关卡数据块经 BIOS `svc 0x12` 解压写入）） |
| 音频 bank（已退役：0x53F138 与音频无关） | `0x53F138` | ❌ | ❌ | **none** | —；[基址已裁决：ROM 零引用] | —（已更正：**已退役**（`tools/table_registry.py::RETIRED`）：`0x53F138` 处是 `0x53F140` 指针数组头部的 2 个代码指针（场景对象/motion/callback 描述符），与音频无关；本 bank 的 Sappy 叙事整体作废。真正的 sound-ID 表在 `0x465B70`（见 sound-id-table 行）） |

## 汇总

- L4 完整通关：`3`
- L3 模拟器按键：`41`
- L2 原生定点：`0`
- L1 工具产出：`0`
- 无证据：`3`
- 格式已证明：`44` / `47`
- 写回可用：`24` / `47`
- 基址已裁决（ROM 零引用，基址无效）：`3`
- 原生消费者证据：`notes/evidence/consumer-evidence.json` （状态 `ok`，覆盖 61 张表）

> 下列渲染产物**未被 git 跟踪**，纯净检出下不存在；本审计只把它们当作“可由已提交工具重新生成”的附带证据：
> - `build/tiles/battle_00_map_layer0_0.png`（maps，本地已生成，未提交）
> - `build/audio/manifest.json`（sound-id-table，本地已生成，未提交）

## 距离 100% 的缺口（按解锁价值/难度排序）

### 阻塞缺口（`0` 条，必须清零才算 100%）

| # | 结构 | 等级 | 缺口 | 需要的证据 | 价值 | 难度 |
|---:|---|:---:|---|---|---:|---:|

### 加固缺口（`20` 条，不属于 100% 门槛，但会提高可信度）

| # | 结构 | 等级 | 缺口 | 需要的证据 | 价值 | 难度 |
|---:|---|:---:|---|---|---:|---:|
| 1 | 战斗角色槽 / 编成表 | L4 | 未知字段已显式标注：group/variant 等索引字段名仍是暂定名（槽内 +0x00/+0x01/+0x04/+0x0F 已证） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 4 | 2 |
| 2 | 角色定义表 | L3 | 未知字段已显式标注：12 字节头的 +0x00 / +0x07、以及 0x545458 记录里的 +0x00/+0x01 与 +0x03/+0x0A/+0x0B/+0x0D/+0x0F 语义未定；条目字节 4（pad）未定 | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 3 | 3 |
| 3 | 战斗奖励表 | L3 | 未知字段已显式标注：记录尾部 +0x16 / +0x17 两个字节语义未定（112 条全为 0、无消费者读取）；类别 3（技术）的取值域只能由代码给出上界，因为本 ROM 的 112 条记录里没有一条用类别 3 | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 3 | 3 |
| 4 | 精灵帧描述符表（0x53EE98，10 字节步长） | L3 | 未知字段已显式标注：五个 u16 字段（+0 类别/链表结束、+2/+4 有符号量、+6 类别、+8 结束标志）的业务名未定 | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 2 | 3 |
| 5 | 战斗遭遇记录表（0x54229C，16 字节/条） | L3 | 未知字段已显式标注：记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 6 | 处理程序分派表（0x53E698，8 字节/条 x 256） | L3 | 未知字段已显式标注：记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 7 | 逐角色属性表（0x545068，16 字节/条） | L3 | 未知字段已显式标注：记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 8 | 逐角色属性表（同表，0x545068 另一个错位窗口） | L3 | 未知字段已显式标注：记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 9 | 数据指针表 A（0x5A143C，u32 ROM 指针 x 46） | L3 | 未知字段已显式标注：记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 10 | 数据指针表 B（0x5A2034，u32 x 90） | L3 | 未知字段已显式标注：记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 11 | 字宽表（0x53E596，1 字节/条 x 256，按字符码索引） | L3 | 未知字段已显式标注：记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 12 | 函数指针表（0x53D5F0，13 槽 u32） | L3 | 未知字段已显式标注：记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 13 | 道具/技能记录表（0x545BE4，与 skills 同址） | L3 | 未知字段已显式标注：记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 14 | 角色特性表（0x5459C8，12 字节/条） | L3 | 未知字段已显式标注：记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 15 | 处理程序分派表（同表，0x53E698 另一个窗口） | L3 | 未知字段已显式标注：记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 16 | map-sprites | L3 | 未知字段已显式标注：描述符记录内部字段名未定。已收窄：记录**变长自描述**（实测 12 或 28 字节交替），不是旧笔记说的「11 个字」；每条以一个 u32 ROM 指针开头，末尾带下一条记录的地址 | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 17 | 头像指针表（0x5A4DEC，40 字节/条 x 63） | L3 | 未知字段已显式标注：记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 18 | 资源指针表（0x596CCC，与精灵动作表同址；旧基址 0x596F0C 是其 +0x240 窗口） | L3 | 未知字段已显式标注：记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 19 | 技能 bank（0x546100，与 items 同址） | L3 | 未知字段已显式标注：记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |
| 20 | 图块/精灵资源记录表（0x5A320C，68 字节/条 x 79） | L3 | 未知字段已显式标注：记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废） | 该结构的未知字段已经逐条列出，且写回路径的往返自检证明这些字节不会被改动 —— 不影响“复制原生条目 + 只改已知字段”的写回模型。 | 1 | 3 |

<!-- END GENERATED: tables -->

---

## 6. 哪些结论是**推断**而不是**证明**

这一节是本审计的"自陈清单"，对应 `notes/runtime-verification-gates-20260710.md`
§4.1「明确不宣称的内容」。

| # | 结论 | 现在是推断的原因 | 什么证据能把它变成证明 |
|---|---|---|---|
| 1 | 剧情 VM 里标 `[推]` 的指令语义（`0x08` / `0x19` / `0x0B` / `0x0C` / `0x33` / `0x13` / `0x1E` / `0x22` / `0x1C` / `0x12` / `0x17` / `0x23` / `0x35` …） | 按操作数分布与上下文推断，未逐条运行验证 | 跑一段含该指令的关卡，取运行时的可见行为 |
| 2 | 奖励表尾部 `(忍具 id << 8) \| 小整数` 的**低字节**（0/1/2）是数量还是档位 | 高字节 326/328 落在忍具表 id 范围、低字节全在 0..2，分布吻合；但低字节语义没有独立锚点 | 拾取弹窗里读出实际数量（依赖 L3 跑起来） |
| 3 | 角色模板 `0x54241C` 的 `+0x0A` 是体力上限（鸣人 80 / 卡卡西 70 / 小樱 50） | 只是"看着像"；笔记已明确标未证实 | 运行时读该单位 HP 上限并与模板字段对照 |
| 4 | `0x545458` 的正确读法 | 既不是 u32 指针表（前 16 字节全 0），也不是任何已知紧凑结构 | 反汇编它的消费者，或写一个夹具往返 |
| 5 | 运行时 WRAM 的 10 个"原生字段"（`0x020311EA` / `0x02026805` …） | "原生"来自 ARM 字面量池引用核验，是**强静态证据**；但字段语义本身仍多为推断 | 在 mGBA 探针里读出该地址并与游戏内可见状态对照 |
| 6 | 事件队列上限 = 16 | stage 1 的原始 logic 脚本静态深度**恰好 16** 是独立实证；但 stage 20 静态值 17 说明静态分析是**过近似**，"运行时上限 16" 仍是推断 | 在运行期插桩统计真实队列深度 |
| 7 | `0x53F138` 到底是什么 | 实测该处横跨 motion / callback / sprite 对象，**与音频、调色板都无关**——这一条是实测结论；但"它究竟是哪张表"仍未定 | 定位它的消费者并反汇编 |
| 8 | positions 的 L2 等级 | 仓库旧文档把 positions 记为 L2（原生定点），但唯一的动态证据是网页 WASM 探针，**没有 PC/LR 与寄存器对应**；本审计按严格判据只给 **L3** | 在 `0x0806E41E` / `0x0806E71E` 真实断点命中，保存 r5、record+2/+3 与创建后 slot 坐标 |
| 9 | 「地图渲染出连贯的木叶村」是可视证明 | 判据是人眼；产物 `build/tiles/battle_00_map_layer0_0.png` **未被 git 跟踪**，纯净检出下不存在 | 提交该 PNG，或改成可自动判定的校验（如连通性/调色板计数） |
| 10 | mGBA 探针足以支撑 L2/L3 | 探针能注入按键、造 savestate、断点取 PC/LR，**但截图能力不可用**（`mCoreTakeScreenshotVF` 需要 mGBA 编 PNG 支持），所以"画面判据"这条路目前不存在 | 给 mGBA 编 PNG 支持，或用内存/寄存器判据替代画面判据 |

---

## 7. 与 2026-07-10 旧审计的差异

| 维度 | `notes/re-completion-audit.md`（2026-07-11） | 本文件（2026-10-20） |
|---|---|---|
| 覆盖对象 | 32 个 content bank | 46 个结构（32 bank + 14 个新确认结构） |
| 判据 | 元数据齐全（偏移 / 格式描述 / 条目 / 文档引用 / 基准 ROM 字节一致） | 格式有**独立证明**（夹具往返 / 渲染 / 字节往返 / 原生代码定址） |
| 结论 | "32/32 完整" | L4=0 / L3=1 / L2=0 / L1=15 / 无证据=30 |
| 动态等级 | `static_verified`=30 / `code_verified`=1 / `runtime_verified`=1（bank 自带标签，非本审计判定） | L3=1（positions，唯一有已提交的动态证据） |
| 回写闭环 | 自陈"不能证明实际回写闭环" | 19 / 46 有写回路径（12 条已做成**可执行**往返自检，全部 PASS）；文本写回已端到端验收（5/5 槽位渲染 == 作者文本） |
| 文本编码 | 全部按 cp932 处理（产物是乱码） | 自定义双字节字形码，26/26 段指纹匹配，4261 码位 0 未解析 |

> 两个数字**不可直接比较**。旧审计的 "32/32" 说的是"32 个 bank 的元数据齐全"，
> 本审计的 46 说的是"46 个结构的格式被独立证明"。把旧数字当成"逆向 100%"
> 是这份文件要纠正的核心误解。

---

## 8. 已知阻塞与本审计的边界

1. **未提交的产物不算证据。** `build/` 下未被 git 跟踪的探针 JSON
   （`build/mgba-smoke-probe.json`、`build/natural-*.json`、`build/synthetic-fixture.json`）
   与渲染 PNG 都**不在**证据表里。它们是本机工作产物，纯净检出下不存在。
   仓库里唯一被提交的动态证据是 `notes/wasm-formation-probe-result-20260710.md`。
2. **mGBA 探针的截图能力不可用**（`mCoreTakeScreenshotVF` 需要 mGBA 编 PNG 支持），
   所以"画面判据"这一路证据目前不存在；见 §6 第 10 条。
3. **`sequel/editor.db` 被 gitignore**，编辑器 → 构建的 override 链在纯净检出下是空转的。
   这不影响本审计的等级判定（写回能力按**已提交的工具**判定），但影响"编辑器产出"这条链的可用性。
4. **旧编码残留**：`tools/find_sjis_blocks.py` 与 `tools/decode_dialogue_record.py`
   仍依赖旧手工表 `sequel/content/text/sjis-to-tile-mapping.json`（该表已判定为双重编码乱码，0/20 与 ROM 一致）。
5. **本审计不评估**内容质量、关卡设计、剧情完整性——只评估"结构是否被证明"。

---

## 9. 复现

```powershell
python tools/completion_audit.py
python tools/completion_audit.py --note notes/completion-audit-20261020.md
python tools/synthetic_fixture.py          # 9 个夹具、37 项检查
python tools/table_registry.py             # 权威基址 + alias 冲突
```
