# S49 `needs_guard` 结论转真实门禁（2026-10-20）

## 本轮目标

`docs/butano-reverse-gap-roadmap.md` §7.3 起反复强调同一句话：**分类不等于消费**。
`artifacts/reverse-notes-index-v1/notes-index.json` 把 435 条逆向结论分进 5 个桶，
其中 `needs_guard` **339** 条——笔记本身给出了可核验的原版结论，但本树**没有任何测试
消费它**。M5 把这些笔记分了桶，只是分类；真正让它们离开 `needs_guard` 的动作是
**写出一条会真的断言该结论的行为门禁**。

本轮只做一件事：挑出 **S49 相关**且**结论可用本树已有收据机械复核**的 `needs_guard`
笔记，把每条变成一个独立测试方法。

产出：

- `tests/test_s49_needs_guard_gates.py`——10 个测试方法，**每个方法对应且只对应一条
  逆向笔记**。
- 本文件——转换清单、拒绝清单、值的更正、实跑记录。

## 口径：什么才算「转成门禁」

本轮自定三条硬口径，不满足任一条就不转：

1. **断言值必须来自本树已有的收据**，不能只来自笔记正文。收据 = 不可变的基础 ROM
   `rom/base.gba`、本树已采到的运行时证据 JSON、S49 battle-14 名册捕获、或
   `artifacts/reverse-results-index-v1/index.json`。
2. **断言必须是可观察值**：精确字节区间、ROM 指针、图层/槽位计数、哈希、单位坐标。
   「文件存在」「文本包含」一律不算。
3. **失败关闭**：收据缺失或哈希对不上时，测试必须**报错**并说清是哪一份收据、期望
   什么、实际什么，**不得 skip**。

> 收据钉在 SHA-256 上是刻意的：ROM 换版、名册重采、证据文件被改，门禁必须立刻炸，
> 而不是悄悄放过。`artifacts/reverse-results-index-v1/index.json` **不钉文件哈希**
> （发布轮会重建索引），只钉它记录的**成果族 manifest 哈希**与公式字符串。

## 转换清单（10 条）

| # | 笔记 | 钉住的结论 | 收据（sha256） |
|---|---|---|---|
| 1 | `notes/battle-scenario-config.md` | 战斗场景配置表在 `0x53D910`，16 条 × 16 字节；S49 的 battle 14 = 第 14 条 = 60×32 tiles、`ptr1=0x080CD260`、`ptr2=0x080D0054`、`flag=0x0154`；8 条有效行逐条核对 | `rom/base.gba` `1198ece7…` |
| 2 | `notes/battle-action-detail-renderer-20260713.md` | 详情渲染器 `0x080708BC`；按 action_id bit 7 分流（effect `0x080708F0→0x0806D85C` / skill `0x08070906→0x0806D910`）；「忍者组合拳」传的是 `effect_id=2` 不是 `skill_id=2`；writer 命中数 4 / 2 / 10 与首末调用点；强制 skill A/B 的 runtime block 只差 +4 字节 6→7 | `artifacts/runtime-checkpoints/action-detail-renderer-evidence.json` `c89e91e8…` |
| 3 | `notes/battle-status-bars-export-20260730.md`（逆向树） | 状态条是运行时生成的，不是静态图：生成器代码体 `[0x08068370,0x08068642)`（722 B）与含 literal pool 的整段 `[0x08068370,0x08068660)`（752 B）两个 SHA-256 逐字节命中 | `rom/base.gba` `1198ece7…` + `artifacts/reverse-results-index-v1/index.json`（族 `battle-status-bars-v1` manifest `d88242fa…`） |
| 4 | `notes/battle-start-control-flow-20260713.md`（逆向树） | `0x0200A884/0x0200A885` 是**同一个 16-bit 过滤位图**；全 ROM 对 `0x0200A885` 的字面量引用数为 **0**，而 `0x0200A884` 为 20、`0x0200A882` 为 64 | `rom/base.gba` `1198ece7…` |
| 5 | `notes/character-battle-visuals-export-20260729.md` | 战斗 OBJ 矩阵 `0x596D5C..0x59903C`（558×16 = `0x22E0`，sha256 `baa3f867…`）；342 四指针齐全 / 216 全零 / **0 条半填**；槽 0–4 各 62 条、槽 5–8 各 8 条；寻址式 `0x08596CCC + character_id*0x90 + visual_slot*0x10` 逐条命中；矩阵在 `0x59903C` 精确结束且下一表首行是全零哨兵 | `rom/base.gba` `1198ece7…` |
| 6 | `notes/battle-presentation-glyphs-export-20260729.md` | `0x5A2B08..0x5A2C44` = 79 条 NUL 串指针；`0x5A2C44..0x5A2EF4` = 172 个 LZ77 指针（全部带 `0x1` 头）；`0x5A2EF4..0x5A320A` = 79×10 binding：槽位 294、其中 **10** 个 `0xFF` 跳过槽 ⇒ **284** 个实际字形槽；138 个被引用字形 id、34 个未绑定；空 binding 是 message 13/31/32/46；运行时调色板与初始化代码切片两个 SHA-256 命中 | `rom/base.gba` `1198ece7…` |
| 7 | `notes/battle-visual-catalog-export-20260729.md` | 79 个 descriptor 在 `0x5A320C`、每条 `0x44` 字节（末字节 `0x5A4707`）；全零哨兵是 13/31/32/46；「三指针全非零」口径数出 **236** 个完整静态图层（A 75 / B 75 / C 75 / D 11）；descriptor 0 的 D 只有 tilemap `0x0836774C`、gfx 指针为 0；descriptor 4 的 D 三件套完整；全表只有 1 条 D 缺 gfx | `rom/base.gba` `1198ece7…` + index（族 manifest `1ccbdfda…`、选择链公式字符串） |
| 8 | `notes/battle-visual-runtime-timelines-export-20260729.md` | descriptor 头字段：#0 `origin_x=72` / cue `119`；#2 callback mode 3、同 `origin_x=72`、同 cue `119`；#1 与 #3 是 `0x0100` 分支且 cue `137`；79 条里 **75** 条可播（其余 4 条是全零哨兵） | `rom/base.gba` `1198ece7…` + index（族 manifest `7a3fd143…`） |
| 9 | `notes/text-and-battle-visual-consumers-20260713.md` | 角色/档案描述文本是 `0x5A143C` 的 46 指针表（末字节 `0x5A14F3`，历史 `0x5A14A4` = 第 26 项）；hook `0x0808B1A4` 下 entry 0 → `0x0859F988`、entry 7 → `0x0859FDE8`；visual variant 矩阵 `0x5A4DEC + record_id*40 + variant*8`，record 7/var 0 在 `0x5A4F04` 且为 `(0x08418A88, 0x084196C8)`，record 3/var 0 为 `(0x08411CD4, 0x08412984)`；record 0 全零、63 条到 `0x5A57C4` | `artifacts/runtime-checkpoints/profile-text-runtime-evidence.json` `552b94be…` + `artifacts/runtime-checkpoints/visual-variant-runtime-evidence.json` `3abe72dd…` + `rom/base.gba` `1198ece7…` |
| 10 | `notes/first-battle-savestate-checkpoints-20260712.md` | 单位实时位置在**单位池记录**里而不是光标：池基址 `0x020240C0`、步长 `0x1D4`、坐标在 `+0xC4/+0xC5`；S49 battle-14 实采池里 9 个占用槽全部满足（`+0x00`=character id、`+0xC4`=x、`+0xC5`=y），池长 6084 = 13×`0x1D4`；ROM 的 WRAM 分配表那一行也写明基址与 6084 字节 | `artifacts/s49-original-battle14-roster-v1/unit_pool.bin` `9d508d99…` + `.../roster.json` `b53417ce…` + `rom/base.gba` `1198ece7…` |

其中 8 条笔记在本树 `notes/`，2 条（#3、#4）只存在于只读的逆向树
`/Users/altair/github/gba-naruto-reverse/notes/`，测试里已用 `reverse tree:` 前缀标出。

### 顺带钉住的「反向消费」

#7、#8 两条笔记还把**逆向成果族的 manifest 哈希**与本树
`artifacts/reverse-results-index-v1/index.json` 记录的值对上了：笔记里写的哈希和索引
里写的哈希必须相等。这让「笔记的出处」本身也成了可核验的事实——逆向侧产物一旦换代、
manifest 变了，门禁会立刻响。

## 拒绝清单

拒绝的判据只有一条：**结论无法用本树已有的收据机械复核**（缺收据、或结论本身是运行时
现象而本树没有对应采集）。凡是能用收据钉住的，本轮都已转；下面每条给出具体理由。

| # | 笔记 | 拒绝理由（具体） |
|---|---|---|
| R1 | `notes/rom-battle-message-text-inventory-20260811.md`（逆向树） | 笔记的结论是 **parser 级**的字节闭包：79 条记录 1,411 B + 逐字节零填充 1,329 B = 闭合 `0x5A1580..0x5A2034` 的 2,740 B，以及 4 个 SHA-256。判定字节边界要跑它自己的 grammar（控制字节 + SJIS range table，`0x0806626C` parser），本树**没有**该 parser、也没有 `artifacts/rom-battle-message-text-inventory-v1/`。唯一 ROM 可核的部分是 79 指针表 `0x5A2034` 与「全 ROM 两个 literal」，而那不是这条笔记的结论，且同一张表已被 #9 覆盖 ⇒ 只能钉一个更弱的指针事实，不足以让这条笔记出桶。 |
| R2 | `notes/character-battle-visual-resource-matrix-20260801.md`（逆向树） | 结论全是**改过的 ROM** 的像素级 A/B：4 份 16 MiB 诊断 ROM（bundle 放到 `0x08600000..0x08604B60`）、palette `84→85`、component `F0→F1`、timeline `03→04`、最终 PNG 268 像素变化、边界 `[109,25,131,68]`。这些 PNG / PRAM dump 在逆向树的产物目录里，本树没有；引用的偏移 `0x600002 / 0x60486C / 0x604A64` 是**那 4 份改过 ROM** 的偏移，在 6 MiB 的 `rom/base.gba` 里不存在 ⇒ 无法在本树复核。 |
| R3 | `notes/battle-effect-resource-pairs-export-20260729.md` | 结论是 10 段战斗特效资源对（LZ77 图块 + 调色板）及其装载器绑定，产物 `artifacts/battle-effect-resource-pairs-v1/`（连同依赖的 `battle-effect-sequence-bindings-v1`、`battle-effect-sprite-animations-v1`）**都不在本树**。本树没有对应的 ROM 字节范围收据，也没有这些族的预览/帧 ⇒ 无法断言。 |
| R4 | `notes/battle-effect-sprite-animations-export-20260729.md` | 同 R3：结论依赖 `artifacts/battle-effect-sprite-animations-v1/` 与 `battle-effect-affine-runtime-v1/`，两者都不在本树；仿射参数属于运行时状态，本树没有对应采集。 |
| R5 | `notes/menu-portrait-export-20260729.md` | 结论是菜单立绘族（`artifacts/menu-portraits-v1/`）的分层与格位，该产物**不在本树**。本树与「立绘」有关的锚点是 `0x5A4DEC` 变体矩阵，已被 #9 用 ROM 字节 + `visual-variant-runtime-evidence.json` 钉住——但那是**角色/剧情立绘变体**（`ShowPortrait`），不是菜单立绘族 ⇒ 两者不能互相顶替。另外 `artifacts/s49-original-ui-reference-v1/` 是**字格裁剪源截图**（S49 战斗菜单画面），不是立绘族产物，不能拿来当这条笔记的收据。 |
| R6 | `notes/sprite-definition-animations-export-20260729.md` | 结论是 sprite definition 动画族（`artifacts/sprite-definition-animations-v1/`、`sprite-definition-assets-v2/`），产物不在本树；地图/剧情侧立绘与 S49 战斗 OBJ 是两套资源，#5 钉的 `0x596D5C` 矩阵不能顶替。 |
| R7 | `notes/bg-scene-selection-export-20260729.md` | 结论是 BG 场景选择族（`artifacts/bg-scene-selection-v1/`），产物不在本树。 |
| R8 | `notes/story-scene-timelines-export-20260729.md` | 结论是剧情场景时间线（`artifacts/story-scene-timelines-v1/`），产物不在本树，且**与 S49 战斗场景无关**（本轮范围是 S49）。 |
| R9 | `notes/battle-config-unsafe-template-fix-20260710.md` | 结论是**编辑器侧**的行为修正：旧 `battle_configs` CRUD 现在返回 `db_battle_config_unmapped`、不再产生任何 ROM 字节补丁，只有带 `_idx`/`_rom_offset` 的 `rom_*` 镜像能进无损构建链。编辑器与其 DB 都在逆向树，本树没有这套 CRUD 可供断言；`conflicting patch overlap at 0x547934..0x547948` 是**构建管线**的诊断信息，不是原版 ROM 的稳定事实。⚠️ 诚实补充：其中「旧基址 `0x53D914` 乘 32 会跨区」这半句**是** ROM 可核的（`0x53D914 + 0x0501*32 = 0x547934`），但它已被 #1 隐含覆盖（正确基址是 `0x53D910`），而笔记的**最终结论**在编辑器侧 ⇒ 仍判拒绝。 |
| R10 | `notes/scenario-41-*-runtime-*.md`（8 条 scenario 41 笔记） | **不在 S49 范围**（scenario 41 是教程战）。其中 `notes/scenario-41-player-control-runtime-20260715.md` 的 checkpoint 哈希与 `0x02024294` 单位记录其实**可以**用本树 `artifacts/runtime-checkpoints/actionable-battle-runtime-evidence.json`（battle_id 41、map `[36,44,9,22]`、unit slot 1 在 `(4,10)`）钉住，但那是下一轮「教程战」里程碑的料，本轮不混进来，故显式拒绝而不是漏掉。 |

> 顺带说明：#2、#5、#6、#7、#8、#9 这批笔记之所以能转，是因为它们的结论是**ROM 字节级**
> 的（表基址、记录宽度、指针、计数、代码切片哈希）。而 R1–R9 的结论是
> **产物族级**或**运行时级**的——产物不在本树，就没法让测试真的断言它。

## 值的更正（本轮实跑中查出 2 处，均已写进测试的 docstring）

### 更正 1：`notes/battle-scenario-config.md` 的 WRAM 分配表被误解析

笔记的 WRAM 分配表（ARM `0x0853D848`）写的是 `{u16 wram_offset, u16 size}` 8 条，
地址形如 `0x02002E30`、大小 514。**实读 ROM 不符**：记录其实是 `{u32 wram_addr, u16 size}`
共 **10** 条，地址是 `0x0202xxxx`（笔记把一个 `u32` 拆成两个 `u16`，把高半当成了
「大小」）。

ROM 实读（`0x53D848` 起，每条 8 字节）：

```text
0x53d848 0x02022E30  4732      0x53d878 0x02026BC8    24
0x53d850 0x02022E30  4732      0x53d880 0x020240C0  6084   <- 单位池
0x53d858 0x020240AC    20      0x53d888 0x02025884  1404
0x53d860 0x02022E30  4732      0x53d890 0x02026604   512
0x53d868 0x020240AC    20
0x53d870 0x02026804     8
```

旁证：单位池那一行是 `0x020240C0`、6084 字节，而 6084 = **13 × 0x1D4**，正好等于
`notes/first-battle-savestate-checkpoints-20260712.md` 说的「池基址 `0x020240C0`、
步长 `0x1D4`、13 槽」——**这条被 #10 独立钉住**。而 S49 battle-14 实采池恰好 6084
字节、9 个占用槽的 `+0xC4/+0xC5` 与名册逐槽吻合。

⇒ 因此测试 #1 **只钉战斗场景配置表**（8 条有效行逐条核对），**不钉**笔记那张 WRAM 表；
修正后的单位池行由测试 #10 钉住。笔记文件本身本轮未改（不归本轮写权限）。

### 更正 2：`notes/battle-scenario-config.md` 的表范围末地址措辞

笔记写「Total entries: 16 (ARM `0x0853D910` through `0x0853D9F0`)」。`0x53D9F0` 是
**第 14 条（S49 那条）的起始**，不是 16 条的末尾（16×16 字节应到 `0x53DA0F`）。
测试 #1 把它写成一条机械断言：`0x53D910 + 14×16 == 0x53D9F0`，顺带把 S49 记录的位置
钉死；16 条记录本身逐条核对无误。

## 实跑命令与真实输出

```bash
cd /Users/altair/github/gba-naruto
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
/usr/local/bin/python3 -m unittest tests.test_s49_needs_guard_gates -v
```

真实输出（完整 25 行）：

```text
test_battle_action_detail_renderer_trace (tests.test_s49_needs_guard_gates.S49NeedsGuardGatesTest.test_battle_action_detail_renderer_trace)
notes/battle-action-detail-renderer-20260713.md (this tree). ... ok
test_battle_presentation_glyph_tables (tests.test_s49_needs_guard_gates.S49NeedsGuardGatesTest.test_battle_presentation_glyph_tables)
notes/battle-presentation-glyphs-export-20260729.md (this tree). ... ok
test_battle_scenario_config_table (tests.test_s49_needs_guard_gates.S49NeedsGuardGatesTest.test_battle_scenario_config_table)
notes/battle-scenario-config.md (this tree). ... ok
test_battle_start_control_flow_address_filter (tests.test_s49_needs_guard_gates.S49NeedsGuardGatesTest.test_battle_start_control_flow_address_filter)
notes/battle-start-control-flow-20260713.md (reverse tree: ... ok
test_battle_status_bar_generator_code_slice (tests.test_s49_needs_guard_gates.S49NeedsGuardGatesTest.test_battle_status_bar_generator_code_slice)
notes/battle-status-bars-export-20260730.md (reverse tree: ... ok
test_battle_visual_catalog_descriptor_table (tests.test_s49_needs_guard_gates.S49NeedsGuardGatesTest.test_battle_visual_catalog_descriptor_table)
notes/battle-visual-catalog-export-20260729.md (this tree). ... ok
test_battle_visual_runtime_timeline_descriptor_fields (tests.test_s49_needs_guard_gates.S49NeedsGuardGatesTest.test_battle_visual_runtime_timeline_descriptor_fields)
notes/battle-visual-runtime-timelines-export-20260729.md (this tree). ... ok
test_character_battle_visual_descriptor_matrix (tests.test_s49_needs_guard_gates.S49NeedsGuardGatesTest.test_character_battle_visual_descriptor_matrix)
notes/character-battle-visuals-export-20260729.md (this tree). ... ok
test_first_battle_savestate_unit_pool_layout (tests.test_s49_needs_guard_gates.S49NeedsGuardGatesTest.test_first_battle_savestate_unit_pool_layout)
notes/first-battle-savestate-checkpoints-20260712.md (this tree). ... ok
test_text_and_battle_visual_consumers (tests.test_s49_needs_guard_gates.S49NeedsGuardGatesTest.test_text_and_battle_visual_consumers)
notes/text-and-battle-visual-consumers-20260713.md (this tree). ... ok

----------------------------------------------------------------------
Ran 10 tests in 0.170s

OK
```

⇒ **10 个测试，10 条不同笔记，0 失败 0 错误 0 skip**。

失败关闭已实测（直接调测试模块的守卫函数）：

```text
OK wrong-hash -> receipt rom/base.gba hash mismatch: expected 0000…0000, got 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b
OK missing    -> missing receipt: artifacts/does-not-exist.json
OK missing-family -> artifact family 'no-such-family-v1' is missing from artifacts/reverse-results-index-v1/index.json
```

## 边界与声明

- 本轮**没有**改 notes 索引、ledger、roadmap 或任何 `docs/`；索引/台账重建由本轮之外的
  父代理在收尾时统一做。
- 本轮**没有**改任何既有测试或工具；**没有**启动 mGBA；**没有** commit / push。
- 只读使用逆向树 `/Users/altair/github/gba-naruto-reverse`（只读，未写入）。
- 依赖提示：`artifacts/reverse-results-index-v1/index.json` **不钉文件哈希**（发布轮会
  重建），只钉内容。逆向树若发生 manifest 换代，#3 / #7 / #8 会失败——这是设计意图，
  不是脆弱性。
- 本轮只覆盖 10 条 `needs_guard`（339 条中的 10 条）。剩余量仍然很大，**不得**因为这
  10 条就宣称「结论层已被消费」——`needs_guard` 的真实分母要等父代理重建索引后重算。
