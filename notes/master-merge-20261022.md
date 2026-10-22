# master 第二轮合入复刻主线（2026-10-22）

**操作**：把 `origin/master`（`f5575265`，2026-10-20/21 的 **40 个**逆向侧提交，
+303,963 行——完整 ROM 编辑器六个域 + 分层取证工具链 + 16 处缺口闭合）
合入 `codex/butano-foundation-research`（复刻复刻线）。

**结果**：25 个冲突路径全部逐项裁决；`tools/alias_audit.py` 对 `rom/base.gba` 报
**RESULT: OK**（registry-vs-bank 不一致 0、未裁决冲突 0、失败的判死检验 0）。

**保全**：合入前先做工作区快照提交 `b35351db`
（"round-25 战场 overlay 第二轮在飞工作保全快照"，91 个新采集产物 +
生成器/头文件/测试的续作）。

---

## 0. 为什么这次不能机械合并

上一轮（2026-10-21）的合并已经把两条分支的**裁决口径**统一了：master 的
`tools/table_registry.py` 当时只有 32 条 `BANK_TO_REGISTRY`、73 条 `TABLES`，
legacy 条目还占据着 bank 映射。**本轮 master 把注册表重构了**：

- `TABLES` 从 73 条扩到 **73+ 条**，把 `legacy_*` 换成了**有规范名的已证明条目**：
  `data_pointer_table_a` (0x5A143C)、`data_pointer_table_b` (0x5A2034)、
  `tile_asset_records` (0x5A320C)、`portrait_table` (0x5A4DEC)、
  `font_width_table` (0x53E596)、`function_pointer_table` (0x53D5F0)、
  `battle_handler_table` (0x53E698)、`character_template` (0x54241C)、
  `story_before_root` (0x060C74)、`story_after_root` (0x060D54) 等；
- `CONFLICTS` 从 8 条扩到 **17 条**，并逐条写明旧基址**错在第几条**
  （data-table-a 错 26 项、data-table-b 错 59 项、fonts 晚 30 字节、
  function-pointers 旧基址是槽 1、battle-handlers 错 8 条）。

**关键验证**：master 独立加入了我上一轮推导的 8 条裁决中的 **5 条**
（`0x53eb08` / `0x5a14a4` / `0x5a2120` / `0x5a5774` / `0x5a3218`）——
方法论得到**独立交叉验证**。剩下 3 条（units / story / story-b）master 还没写，
本轮补齐。

---

## 1. 冲突裁决（25 个路径）

### 1.1 bank.json：20 个

两侧是**同一批记录的两套字段命名**：master 用通用名（`field_0` / `rom_ptr` /
`ptr_0` / `code_ptr_0` / `slot_value`），复刻线用已证明的语义名
（`config_id` / `text_ptr` / `func_ptr` / `primary_handler_ptr` / `character_id` …）。

**判据**：**复刻线与 master 的工具链实际消费哪一套 schema**。
`tools/analyze_battle_action_template_semantics.py`（master 新增）要读
`raw_hex`、`tools/butano/verify_s49_battle_roster.py` 要读 `character_id`、
`tools/extract_battle_content_catalog.py` 要读 skills 指针——
**这些都在用复刻线的 schema**（master 自己的树同样跑不起来这些工具）。
所以：**基址/条目数按新的证据，字段 schema 按复刻线**。

| bank | 采纳 | 基址 | 条数 | 等级 | 理由 |
|---|---|---|---|---|---|
| `battle-encounters` | 复刻线 | 0x54229C | 24 | code_verified | 字段级 schema 被复刻侧测试钉住 |
| `character-stats` | 复刻线 | 0x545068 | 63 | runtime_verified | `character_id` / `raw_hex` 被依赖 |
| `skills` | 复刻线 | 0x545BE4 | 94 | runtime_verified | 同上（master 新工具要 `raw_hex`） |
| `data-table-a` | 复刻线 | 0x5A143C | 46 | runtime_verified | 同基址同条数 |
| `data-table-b` | **master** | 0x5A2034 | **90** | code_verified | master 把 79 条指针行**扩展成 90 行**（79 项是指针，11 项非指针） |
| `levels` | 复刻线 | 0x5459C8 | 45 | code_verified | 字段级 schema |
| `map-events` | 复刻线 | 0x53E698 | 256 | code_verified | 字段级 schema |
| `menu-ui` | 复刻线 | 0x5A4DEC | 63 | runtime_verified | 字段级 schema |
| `tile-assets` | 复刻线 | 0x5A320C | 79 | code_verified | 字段级 schema |
| `audio` | 复刻线 | 0x465B70 | 80 | runtime_verified | = master 自己的 `sound_id_table` |
| `palettes` | 复刻线 | 0x53EE98 | 15 | code_verified | = master 自己的 `sprite_frame_descriptors` |
| `story` | 复刻线 | 0x060C74 | 56 | runtime_verified | = master 自己的 `story_before_root` |
| `story-b` | 复刻线 | 0x060D54 | 56 | runtime_verified | = master 自己的 `story_after_root` |
| `units` | 复刻线 | 0x54241C | 63 | runtime_verified | = master 自己的 `character_template` |
| `map-sprites` | 复刻线 | 0x53F140 | 43×8 | code_verified | 成对结构被复刻侧工具/测试依赖 |
| `resource-pointers` | 复刻线 | 0x596F0C | 5×16 | code_verified | 描述符结构被复刻侧依赖 |
| `cutscene-scripts` | 复刻线 | 0x53DF70 | 8×8 | code_verified | 含第二张表，复刻侧导出器依赖 |
| `fonts` | **master** | **0x53E596** | 256 | code_verified | 基址从 legacy 0x53E5B4 更正（唯一原生读者 0x0807F0FC） |
| `function-pointers` | **master** | **0x53D5F0** | **13** | runtime_verified | 基址更正为消费者字面量指向处；13 槽含首尾双哨兵 |
| `battle-handlers` | **master** | **0x53E698** | 256 | code_verified | 与 map-events 是同一张表；旧基址错 8 条 |

`function-pointers` 另把复刻线的**运行时证据元数据**（`verification_method` 里的
"natural cold-load profile route hit callback ID 2" 与 `consumer` 块）回填到
master 的 13 槽框定上——master 的 `verification_method` 只写了"静态分析"，
不该把已有的运行时证据降级。

### 1.2 工具：4 个

| 文件 | 处置 |
|---|---|
| `tools/build_db_patches.py` | **以 master 版为基底**（master 已把写入器修到更正基址），**回填**复刻线的 `_reject_unproven_legacy_rows` 与 6 条复刻侧专属写回路径（`generate_character_definition_patches` / `generate_audio_sound_id_patches` / `generate_map_header_patches` / `generate_chapter_flow_primary_patches` / `generate_chapter_flow_alternate_patches`），并逐函数裁决 22 个 `generate_*` |
| `tools/find_thumb_calls.py` | **复刻线**。master 版是**线性反汇编**全 ROM（会把 literal pool 当指令读——正是 master 自己在 `notes/legacy-table-base-correction-20261020.md` 里警告的坑），且不支持 `--start/--end` 区间过滤；复刻线版委派给 `tools/thumb_branch.py` |
| `tools/import_rom_to_editor.py` | **master 版**（编辑器本轮是 master 的主战场），但 `import_units` / `import_skills` **取复刻线**：master 的 `import_units` 要读 `char_id`/`hp`/`attack`/`defense`——复刻线的 bank 里**没有这些字段**（成长率 ≠ 基础属性，复刻线的 docstring 明确写了这一点），master 的 `import_skills` 会往编辑器里灌 94 行无意义数据，而复刻线是**刻意不填**（"Keep legacy semantic skills empty until byte fields receive UI meaning"） |
| `tools/table_registry.py` | 见下节 |

### 1.3 测试与文档：2 个

| 文件 | 处置 |
|---|---|
| `tests/test_u32_pointer_patches.py` | **master 版**。它用**裁决后的基址**建合成 editor.db（0x5A143C/46、0x5A2034/90、0x53D5F0/13、0x5A4DEC/63、0x5A320C/79、0x53F140/86），与新的写入器完全对齐；复刻线那版钉的是已被证伪的 legacy 基址 |
| `notes/resource-locations.md` | **并集**：复刻线的「0x53F138 已裁决」条目 + master 的「2026-10-21 追加：metatile 缓冲容量与剧情底图 BG 的两条更正」新章节 |

---

## 2. 注册表（`tools/table_registry.py`）

以 master 版为基底（73+ 条 `TABLES`、17 条 `CONFLICTS`），本轮改动：

1. **补 3 条裁决**（master 尚未收录的）：`0x54241c`（units → 角色定义表）、
   `0x536368` / `0x536bc4`（story / story-b → 剧情脚本根表）。
2. **改 5 个 bank 映射**：`audio` → `sound_id_table`、`palettes` →
   `sprite_frame_descriptors`、`story` → `story_before_root`、
   `story-b` → `story_after_root`、`units` → `character_template`
   ——这 5 个 bank 承载的是 master **自己 TABLES 里已登记**的已证明结构，
   master 的映射当时仍指向 legacy 名。
3. **`TABLES` 支持 `None` 基址**（复合/分析型 bank）：复刻侧有两个不声明
   `table_offset` 的分析产物（`battle-presentation-scripts`、`battle-results`），
   master 的新测试要求注册表**覆盖每个 content bank**。为此
   `verify_table_bases` 的 `hex(expected)` 两处要能处理 `None`。

---

## 3. 被改写的旧测试：3 个

这三个测试钉的是**已被 master 的新证据推翻的身份**，按新事实改写，
**并保留 legacy 基址的证伪记录**：

| 测试 | 原来 | 现在 |
|---|---|---|
| `test_remaining_static_identity::test_false_font_bank_is_empty_tombstone` | fonts 是 0x53E5B4 的空墓碑 | fonts 是 0x53E596/256 的**已证明字宽表**（逐条与 ROM 比对），并断言 `CONFLICTS["0x53e5b4"]` 仍在案 |
| `test_function_pointer_consumer` | 11 个指针 @0x53D5F4，字段 `func_ptr` | 13 槽 @0x53D5F0（首尾双哨兵，槽 1..11 是指针），字段 `slot_value`；**运行时证据断言原样保留** |
| `test_battle_handler_identity::test_old_fourteen_entries_are_seven_pairs_from_handler_table` | battle-handlers 是 0x53E6D8 的空墓碑 | battle-handlers 是 0x53E698/256 的**已证明处理程序对表**（与 map-events 同表），并断言 `CONFLICTS["0x53e6d8"]` 仍在案 |

**没有做的事**：没有为了让测试变绿而弱化任何**安全属性**断言。
"legacy 基址不得产生 ROM 字节补丁"这条不变——只是诊断类型标记随实现变化
（`db_font_unmapped` → `db_font_error`），断言里同时写明了原因。

---

## 4. 过程中发现并修掉的自身缺陷

1. **合成脚本的常量判据写错**：上一轮我用 `c not in out` 判断"常量是否已存在"，
   结果**名字在引用处出现就跳过了追加**，导致 `SPRITE_ACTION_*` / `LEVEL_BLOCK_*`
   共 8 个常量**只有引用没有定义**（`NameError` 被生成器自己的 `except` 吞掉，
   表现成补丁数量不对）。判据必须是"**有赋值**"而不是"名字出现过"。
2. **master 的 `function-pointers` bank 帧定**：master 把该表框成 13 槽
   （槽 0/12 是 `0xFFFFFFFF` 哨兵），复刻线此前只存 11 个指针。核对 ROM 后
   确认**两者是同一张表**，master 的框定更完整（13/13 条与 ROM 逐字节一致），
   复刻线的运行时证据元数据回填其上。

---

## 4.5 第二轮：全量套件暴露的 8 项回归及其处置

与上一轮同样，**在保全提交 `b35351db` 上另开 worktree 跑同一套全量测试**做逐用例
基线（不是靠猜）。基线 2173 项 / 147 个失败用例 → 合并后 2243 项 / 101 个，
**修复 54 项，引入 8 项**。这 8 项全部来自「master 把写入器从 legacy 基址改到
更正基址」这一根本变化，逐条处置如下。

### 4.5.1 master 侧两处**真 bug**（本轮修掉，不只是改测试）

1. **`generate_encounter_zone_patches` 会覆盖 map flags 字段**。
   master 把 zone_id 当 **u32 写在 +0x1C**；而运行时证据（复刻线
   `notes/dynamic-verification-audit.md`）明确：**+0x1C 是 map flags u32，
   zone 字节在 +0x1D**（消费者 `0x0806922A`）。也就是说 master 的写入器
   **用 4 字节盖掉了 flags**，且写在了错误的偏移上。
   → **改回复刻线的只读版本**（别名只做诊断，不写 ROM）。
2. **旧 schema 的行会让写入器 `IndexError` 崩溃**。
   SQLite 把双引号里的未知标识符当**字符串字面量**，所以 `SELECT ... "code_ptr_0"`
   在列不存在时**不会报错**，而是在读行时抛 `IndexError: No item with that key`
   ——构建流水线会以看不懂的异常中断。
   → 新增 `_row_field()`：缺列的行变成**干净拒绝**（`db_pointer_table_error`
   + 明确原因），不再是崩溃。
3. **顺带修掉一个 fail-open**：`_generate_u32_pointer_table_patches` 与
   `generate_character_stats_b_patches` 在列名不匹配时整表 `return []`——
   **作者的改动被静默丢弃，没有任何痕迹**。master 自己的 docstring 说
   "the generator used to fail open (empty patch list)"，但只修了列名那一半。
   → 改成退化到「只选索引列」，让每一行都作为**显式拒绝**返回。

### 4.5.2 8 项回归的逐条处置

| 回归 | 原因 | 处置 |
|---|---|---|
| `test_all_four_legacy_tail_shapes_are_diagnostic_only` | 写入器改到更正基址后，旧基址的行被统一的 `db_pointer_table_error` 拒绝（不再是每表一个标记名） | 更新断言类型名；**保留「不产生字节补丁」这条安全属性** |
| `test_legacy_47_map_rows_are_diagnostic_only` | 同上 | 同上 |
| `test_all_three_legacy_editor_shapes_are_diagnostic_only` | `map_sprites` 改走共享 u32 helper | 更新该子用例的诊断类型名 |
| `test_legacy_editor_rows_cannot_write_the_alias` | master 的 zone 写入器有 bug（见 4.5.1） | **改回只读实现**，测试恢复原断言 |
| `test_unproven_legacy_rows_never_generate_rom_bytes` | 旧列名 → 整表静默返回空 | 修 fail-open（见 4.5.1）+ 断言改为「诊断而非写入」 |
| `test_battle_message_table_has_all_seventy_nine_entries` | data-table-b 从 79 槽**扩展成 90 槽**（79 项仍是 ROM 指针，11 项是别的 u32） | 改断言为「90 槽 / 79 项指针」，逐条与 ROM 比对 |
| `test_battle_visual_descriptor_table_has_seventy_nine_records` | 末行断言 `tile-assets.entry_count == data-table-b.entry_count`——那只是旧状态的巧合，两表结构无关 | 删掉这条无意义的跨表相等断言（各自的断言保留） |
| `test_shipped_artifact_matches_a_fresh_build` | 新增了两份合并记录，notes 索引过期 | **重生成** `artifacts/reverse-notes-index-v1/`（implemented_in_code 28 → 29） |

**没有做的事**：没有为了让测试变绿而弱化任何**安全属性**断言。
「已证伪基址不得产生 ROM 字节补丁」这条不变；变的是**诊断标记的名字**
（每表一个 → 统一 `db_pointer_table_error`）和**拒绝的呈现**
（旧实现拒绝一切 → 新实现只拒绝 legacy 基址、正确基址照写）。

---

## 5. 验证

```
$ python3 tools/alias_audit.py rom/base.gba
registry-vs-bank 不一致: 0
未裁决冲突: 0
失败的判死检验: 0
RESULT: OK
```

全量套件对照（基线在 `b35351db` 另开 worktree 跑**同一套**测试，逐用例比对）：

| | 测试数 | 失败用例数 |
|---|---|---|
| 基线（合并前，`b35351db`） | 2173 | 147（29 failures + 127 errors） |
| 合并后 | 2243 | **93**（20 failures + 82 errors） |

**修复 54 项，引入 0 项。** 逐用例差集为空——合并没有引入任何回归；
剩下的 93 个失败用例是**两侧都存在**的既有失败（主要是需要 mGBA 真机、
需要已构建 ROM、或需要逆向树产物的项）。

日志与退出码：`artifacts/merge-20261022-v1/full-suite.log`、
`artifacts/merge-20261022-v1/full-suite.exitcode`。

---

## 6. 遗留与风险

1. **master 侧写入器与 bank 的三处不一致**（master 自身的问题，本轮未替它修）：
   `generate_level_patches` 写 0x5459D4（旧基址 = 正确表的**第 1 条记录**，
   差一条记录）、`generate_character_stat_patches` 写 0x54507A（错位窗口）、
   `generate_item_patches` 写 0x546100（窗口）。这三条本轮**保留复刻线的
   诊断只读实现**（安全优先），修成指向更正基址属于 master 侧的后续工作。
2. `tools/import_rom_to_editor.py` 的 `import_units` / `import_skills` 沿用复刻线
   版本，与 master 编辑器的其余六个域不同源；等编辑器接上复刻线的 bank schema
   后应统一。
3. master 的 `notes/evidence/legacy-rebase-final-20261021.md` 等新证据文件
   已随合并进入本树，但**尚未**被本树的 `notes/dynamic-verification-audit.md`
   （runtime 等级表）逐条吸收——那需要逐条复核，不是合并能自动完成的。
4. 这次合入**没有**把 master 的完整 ROM 编辑器接进复刻侧的构建链；
   编辑器与复刻流水线是两套东西，接线是独立工作项。
