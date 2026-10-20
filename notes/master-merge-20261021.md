# master 合入重制主线（2026-10-21）

**操作**：把 `origin/master`（`411041a6`，2026-10-20/21 的 11 个逆向侧提交）
合入 `codex/butano-foundation-research`（重制复刻线）。

**结果**：37 个冲突路径全部逐项裁决，未使用机械 `checkout --theirs/--ours`；
合并后 `tools/alias_audit.py` 对 `rom/base.gba` 报 **RESULT: OK**
（registry-vs-bank 不一致 0、未裁决冲突 0、失败的判死检验 0）。

**保全**：合入前先做了一次工作区快照提交 `777b2c96`
（"拉取 master 前的工作保全快照"，2394 文件 / +191358 / 约 91.8 MB 采集产物），
保证冲突处置失误不会丢在飞工作。

---

## 0. 这次合入为什么不是机械合并

`master` 与重制线是**两条平行分支**，各自的最新提交互不包含：

- `origin/master` 领先 11 个提交（逆向侧）；
- 当前分支领先 525 个提交（复刻侧）；
- 共同祖先是 `43d7e159`。

两侧对**同一批 ROM 结构**各自做了一遍推导，而且**在多处互相矛盾**：
master 的 `sequel/content/*/bank.json` 与它的裁决表 `tools/table_registry.py`
本身就不是同一套结论——注册表里定义了 `sound_id_table`（0x465B70）、
`sprite_frame_descriptors`（0x53EE98）、`visual_descriptor_table` 邻近区等
一批**已证明结构**，但**没有任何 bank 承载它们**；承载的是 legacy 版本。

所以判定原则是：**以两侧各自的证据强度为准，而不是以分支新旧为准**。

---

## 1. 裁决表（37 个冲突）

### 1.1 bank.json：22 个

`sequel/content/**/bank.json`。判据统一为「**基址是否有原生读者**」——
这是 master 自己在 `notes/legacy-table-base-correction-20261020.md` 里立的
判据（"某地址在整个 ROM 里一次都没出现 → 它不是 ROM 认识的地址"）。
用 `tools/alias_audit.py` 的字面量索引直接复核。

| bank | 采纳 | 基址 | 证据 |
|---|---|---|---|
| `skills` | master | 0x545BE4 | 注册表 `item_skill_records`，7 个原生读者；两边一致 |
| `items` | master | 0x545BE4 | 同上（弃用别名）。HEAD 侧是空墓碑，master 侧保留内容+别名标记，**两者结论一致** |
| `character-stats` | master | 0x545068 | 注册表 `per_character_stats`；两边一致 |
| `character-stats-b` | master | 0x545068 | 旧基址 0x545200 是错位窗口（`0x545068 + 25*16 + 8`），两边结论一致 |
| `battle-encounters` | master | 0x54229C | 注册表 `battle_encounter_records`，2 个原生读者；两边一致 |
| `levels` | master | 0x5459C8 | 注册表 `character_perks`，6 个原生读者；两边一致 |
| `map-sprites` | master | 0x53F140 | 两边一致（43 vs 86 是条目粒度差，取 master 的 86 项指针表） |
| `sprite-animations` | master | 0x596CCC | 注册表 `sprite_action_table`，18 个原生读者；HEAD 侧旧基址 0x53F200 零引用 |
| `resource-pointers` | master | 0x596F0C | 同基址，master 条目更全（20 vs 5） |
| `cutscene-scripts` | master | 0x53DF70 | master 的 4 项×8 字节由唯一读者 0x08072F0C 证明；相邻第二张表在 0x53DF90，master 注明其内部格式**未解**，故取更保守的 4 项版 |
| `story-c/d/e` | master | 0x538FEC / 0x53AB74 / 0x53C3BC | m4a SongHeader（sound id 8/11/14）。HEAD 侧墓碑写的是「+4 偏移的切片」，master 把基址纠正到头部起点，**结论一致** |
| `encounter-zones` | master | 0x53D910 | 与 `maps` 同址，master 记为别名（HEAD 侧是空墓碑，结论一致） |
| `sappy-engine` | master | 0x079668 | 已证伪（0x08079668 是文本分派函数，不是 Sappy 引擎），注册表 `FALSIFIED` |
| `audio` | **HEAD** | 0x465B70 | HEAD 侧是 master 注册表 `sound_id_table`（0x465B70，sound-ID 表）的**内容**；master 的 bank 装的是已证伪的 0x53F138 窗口。注册表定了这张表却没 bank 承载 |
| `palettes` | **HEAD** | 0x53EE98 | 同上 —— HEAD 侧 15 条 10 字节记录 = master 注册表的 `sprite_frame_descriptors`（0x53EE98，3 个原生读者）；master 的 bank 是已证伪的 0x53F138 窗口 |
| `tile-assets` | **HEAD** | 0x5A320C | master 自己的消费者扫描把 0x5A3218 记为**零读者**，其邻居 0x5A320C 有 **10 个原生读者**（`notes/evidence/consumer-evidence.json`）。HEAD 侧正是 0x5A320C 的 79×0x44 战斗视觉描述符表，且被 `tools/export_story_visual_layers.py` 用 SHA-256 逐字节核对 |
| `story` | **HEAD** | 0x060C74 | = master 剧情 VM 的 **before 根表**（`notes/story-script-vm.md` §1 四张根表：0x060C74/0x060D54/0x060E34/0x060EF0）。master 把 m4a SongHeader 填进了 `story` 这个名字，属于命名回退 |
| `story-b` | **HEAD** | 0x060D54 | 同上（after 根表） |
| `units` | **HEAD**（未冲突，自动保留） | 0x54241C | 63×0xB4 角色定义表；master 的旧基址 0x53F298 实为 43 项 u16 重映射表（`unit_slot_remap`） |
| `maps` | **HEAD**（未冲突） | 0x53D910 | 47×32 字节，runtime_verified，master 未改动 |
| `data-table-a/b`、`map-events`、`menu-ui` | **HEAD**（未冲突） | 0x5A143C / 0x5A2034 / 0x53E698 / 0x5A4DEC | 旧基址 0x5A14A4 / 0x5A2120 / 0x53EB08 / 0x5A5774 **全部零读者**，修正后基址各有 1–2 个原生读者 |

### 1.2 证据等级：5 个

master 的 `tools/populate_bank_json.py` 把所有 bank 一律写成 `static_verified`
（一刀切默认值，不是逐条降级结论）。而 master 自己的注册表证明这些结构
已被原生读者 / 运行时证明，因此恢复 HEAD 侧的等级：

| bank | static_verified → | 依据 |
|---|---|---|
| `battle-encounters` | `code_verified` | 注册表：2 个原生读者 |
| `cutscene-scripts` | `code_verified` | 原生读者 0x08072F0C |
| `levels` | `code_verified` | 注册表：6 个原生读者 |
| `character-stats` | `runtime_verified` | HEAD 的两因子首战 A/B 证据 |
| `skills` | `runtime_verified` | HEAD 的运行时证据 |

**这一档不能丢**：`tools/export_story_visual_layers.py` 把
`verification == "code_verified"` 当**硬闸门**（不满足直接 raise），
一刀切成 `static_verified` 会静默打断重制侧的资源导出。

### 1.3 工具：8 个

| 文件 | 处置 |
|---|---|
| `tools/translate_sjis_to_chinese.py` | **master**。该工具已被**证伪退役**：ROM 存的是游戏自有双字节字形码不是 Shift-JIS；手工表的值本身是双重编码乱码（抽样 20 条 0 条对得上）；它还从 dev ROM 读、往 editor.db 写。master 的版本是"响亮失败" shim（exit 2 + 说明） |
| `tools/import_dialogue_var.py` | **合成**：master 的字体编码 + HEAD 的失败关闭检查（空闲区必须全 0xFF 且在 ROM 内、指针必须匹配、指针表偏移唯一且在 ROM 内、分配不得越界、编码不得含嵌入 NUL）+ `overrides` 参数 |
| `tools/decode_dialogue_record.py` | **master**。其 docstring 明确证伪了旧行为：`0x8B62` 是「的」（U+7684）**不是分隔符**，旧手工表退役 |
| `tools/extract_audio.py` | **master** |
| `tools/build_db_patches.py` | **master** |
| `tools/automated_test.py` | **master** |
| `tools/populate_bank_json.py` | **合成**：HEAD 的已证明基址与墓碑空实现 + master 的 `_adjudicated_banks()` 裁决守卫 + `write_text_lf` + 回填 `force`/`verification` 参数 |
| `tools/extract_tileset.py` | **HEAD**（详见 1.6 撞名） |

### 1.4 文档：5 个

| 文件 | 处置 |
|---|---|
| `docs/sequel-roadmap.md` | **并集**。5 个冲突块逐个裁决：保留 master 的 2026-10-20/21 新章节（静态重编译、mGBA 无头探针、剧情 VM L3 证据）与 HEAD 的复刻侧进展；`0x596D5C` 取 master 的精确认定（精灵动作表 id=1 行，18 个原生读者）并注明 HEAD 的"旧 312 行地图 tile 解释已撤销"；战斗配置表取 master 的 32 字节字段顺序更正 |
| `docs/structure-field-semantics.md` | **master 的字段表 + HEAD 的画布成果段**，并加"命名沿革"说明：两套命名指**同一批槽位**，只是读法与宽度不同 |
| `notes/resource-locations.md` | **并集**。地图图块章节取 master 的更正布局 + HEAD 的调色板解压细节与历史表说明；**Battle Unit Visual Slot Table** 与 master 的 `sprite_action_table` 实为同一张表（master 的 `id` ≡ HEAD 的 `character_id`，master 的 `action` ≡ HEAD 的 `visual_slot`，9×16=144 字节/角色），已互相标注；音频章节两侧都保留；`0x53F138` 的"未解决"改为"已裁决" |
| `notes/dynamic-verification-audit.md` | **HEAD**。master 相对合并基只改了日期（+1/-1），HEAD 是 2026-07-13 的重写：证据等级从 static 升到 runtime/code，且地址已更正（battle-encounters 0x542384→0x54229C、character-stats 0x54507A→0x545068、palettes 0x53F138→0x53EE98 等） |
| `notes/units-unsafe-table-fix-20260711.md` | **并集**。HEAD 的 0x54241C runtime 证据 + master 的 2026-10-21「表被拆成三张」章节，并更正 master 那句已过时的"本轮没有改 units/bank.json" |

### 1.5 其他：3 个

| 文件 | 处置 |
|---|---|
| `.gitignore` | **并集**。master 的 `build/*` + 三个 `!` 例外（续作 dev ROM 是 README 引用的工作流产物）+ HEAD 的 `butano-sequel/*`、`audio-runtime-*`、s49 采集产物与 sentinel ROM 忽略项 |
| `sequel/content/text/dialogue-patches.json` | **master**。`encoding: "font"` 契约、真正的中文剧本文本、ASCII run-id 锚点。HEAD 侧的 `group0.label2` 文本「第二話・新たなる任務」含 **「話」「務」两个 ROM 字体里没有的字符**，在 `encoding=font` 下会直接 `KeyError`；且变长重定位能力已由 master 的分配器路径（`tools/import_dialogue_var.py` + `tests/test_text_writeback.py::test_variable_length_redirect_renders_the_authored_text`，端到端"写入→渲染"断言）覆盖，故不保留该条目 |
| `openspec/.../.comet/subagent-progress.md` | **HEAD**。master 的 73 行是 Task 5 快照，HEAD 的 390 行延续到 Task 6 Step 5 |

### 1.6 撞名：`tools/extract_tileset.py`

两侧各有一个**同名但完全不是同一个工具**的文件：

- HEAD 侧：地图资源提取器，提供 `read_map_entries` / `decode_4bpp_tiles` /
  `analyze_map_resource_semantics` / `extract_entry`，被**18 个重制侧工具**
  与 `tests/test_extract_tileset.py` 依赖；
- master 侧：逆向侧 PNG 图集导出器（战斗地图图块 + 剧情背景图块）。

master 侧版本在 master 树里几乎没有功能调用方（只有 `tools/completion_audit.py`
把它列为 evidence 引用），HEAD 侧版本却是重制流水线的承重件。
**处置**：HEAD 侧保留原名 `tools/extract_tileset.py`；master 侧改名
`tools/extract_scene_tilesets.py`（docstring 写明改名原因），
`tools/completion_audit.py` 的 3 处 probe/render 引用同步改名。

---

## 2. 注册表修正（`tools/table_registry.py`）

为了让上面的裁决**可机器复核、且生成器不会把结论冲掉**，注册表补了 8 条裁决：

| 地址 | 裁决 | 判死检验 |
|---|---|---|
| `0x5a3218` | repoint → `tile-assets` @ 0x5A320C | 0x5A3218 必须仍零读者；0x5A320C 至少 1 个读者 |
| `0x54241c` | repoint → `units` @ 0x54241C | 0x54241C 至少 1 个读者 |
| `0x536368` | split → `story` @ 0x060C74 | 0x060C74 至少 1 个读者 |
| `0x536bc4` | split → `story-b` @ 0x060D54 | 0x060D54 至少 1 个读者 |
| `0x5a14a4` | repoint → `data-table-a` @ 0x5A143C | 0x5A14A4 零读者；0x5A143C ≥1 读者 |
| `0x5a2120` | repoint → `data-table-b` @ 0x5A2034 | 同上 |
| `0x53eb08` | repoint → `map-events` @ 0x53E698 | 同上 |
| `0x5a5774` | repoint → `menu-ui` @ 0x5A4DEC | 同上 |

同时：新增 4 个 `TABLES` 条目（`visual_descriptor_table`、
`character_definition_table`、`story_script_root_before`、
`story_script_root_after`）；修正 10 个 `BANK_TO_REGISTRY` 映射；
`ALIASES` 移除 `palettes`（已是独立已证明结构）；`FALSIFIED` 移除 `audio`
（已改指已证明的 sound-ID 表）。

**副作用是好的**：裁决条目同时进 `_adjudicated_banks()`，
`tools/populate_bank_json.py` 从此**拒绝**再用 legacy 基址覆盖这些 bank。

---

## 3. 被证伪后改写的测试：2 个

| 测试 | 处置 |
|---|---|
| `tests/test_decode_dialogue_record.py` | **改写**。旧断言钉的是**已证伪**的行为（19 条手工表、`0x8B62` 是未解析分隔符）。新断言钉 master 的已验证事实：映射来自 `tools/text_codec.py`（4261 条码，26/26 段指纹全中）、`0x8B62` == 「的」、`0x0A` 在段内换行、字体外码（0x8001）被报告为 unknown 而非丢弃 |
| `tests/test_import_dialogue_var.py` | **适配签名**。分配/指针重定向/拒绝路径的断言契约全部保留，只把旧的位置参数改成新的关键字参数，并显式说明 fixture 用 `cp932` 是为了让期望字节可读（编码本身由 `tests/test_text_writeback.py` 覆盖） |

**没有做的事**：没有为了让测试变绿而弱化任何断言。

---

## 4. 第二轮：全量套件暴露的 43 项回归及其处置

**方法**：合入后在 `777b2c96`（保全提交）上另开一个 worktree 跑**同一套**全量测试
（`python3 -m unittest discover -s tests -t tests`），得到逐用例的基线，
再与合并后逐用例对照。基线 1990 项 / 170 个失败用例；合并后 2077 项 / 149 个。
**合并修好 64 项、引入 43 项**。这 43 项全部是**我第一轮裁决过粗**造成的，
逐条处置如下。

### 4.1 `tools/build_db_patches.py`：写回安全层被 master 版覆盖（最主要原因）

master 的 `build_db_patches.py`（2059 行）把 legacy 镜像表的写回**从"诊断只读"
改成了"真写"**——而那些基址（0x54507A / 0x546100 / 0x53EB08 / 0x53E6D8 /
0x5A14A4 / 0x5A2120 / 0x53E5B4 / 0x5A5774 / 0x5459D4 / 0x542384 / 0x596F0C）
正是 master 自己的消费者扫描判定为**全 ROM 零引用**的那些地址。
复刻线的 `generate_*` 函数是**editor→ROM 的写回安全层**，
master 的 `generate_*` 则是逆向侧的直接写入器——两者不是同一层。

**处置**：以复刻线版本为基底，移植 master 的 11 个 `build_*` 直接写入器
（`build_character_template_patches` … `build_unit_offset_patches`）
及其 3 个 helper 与 8 个常量；逐函数裁决 `generate_*`：

| 取 master | 取复刻线 |
|---|---|
| `generate_sprite_animation_patches`（写已证明的 0x596CCC 精灵动作表） | 其余 17 个 `generate_*`（legacy 镜像一律诊断只读） |
| `generate_save_state_patches`（WRAM 分配表框架修正） | |
| `generate_editor_dialogue_overrides`（两套 id 空间按 ROM 偏移 join） | |
| `generate_palette_patches` / `generate_resource_pointer_patches`（带裁决依据的诊断） | |
| `generate_cutscene_script_patches`（带原生读者证据） | |

### 4.2 bank 的**字段级结构**（不是基址问题，是同批字节的不同粒度）

6 个 bank 在两侧指向**同一批字节**，但表示粒度不同，复刻线的工具与测试依赖
字段级结构：

| bank | 复刻线（采纳） | master |
|---|---|---|
| `battle-encounters` | 24×16，`gfx_lz_ptr`/`palette_lz_ptr`/`tilemap_lz_ptr`/`config_id` | 24 项但字段是 legacy 命名 |
| `cutscene-scripts` | 8×8，`primary_ptr`/`secondary_ptr`/`pair_kind` | 4 项（只第一张表） |
| `levels` | 45×12，`target_type`/`base_a`/`per_level_a` … | 字段名不同 |
| `map-sprites` | 43×8，`definition_ptr`/`animation_ptr`（成对） | 86×4，扁平 u32 |
| `resource-pointers` | 5×16，`resource_ptr_0..3` | 20×4，扁平 u32 |
| `character-stats` | 63×16，`character_id`/`template_02_growth` …（有运行时证据） | 63×16，`field_0..7`（语义未证明） |

### 4.3 被证伪的旧测试（改写，不是删除）

| 测试 | 原断言 | 改成的断言 |
|---|---|---|
| `test_decode_dialogue_record` | 19 条手工表；`0x8B62` 是未解析分隔符 | 映射来自 `tools/text_codec.py`（4261 条码、26/26 段指纹全中）；`0x8B62` == 「的」 |
| `test_export_dialogue_font_atlases::test_group0_control_byte_...` | 用已退役的 `translate_sjis_to_chinese` 解出另一句话 | 用已验证的字形码解码 0x459414：`把九尾妖狐封印在鸣人体内的\n是第几代火影？` |
| `test_overlapping_visual_table_identity::test_old_sprite_animation_bank_is_exact_pair_subset` | `sprite-animations` 是 0x53F200 墓碑 | 保留 **0x53F200 是 0x53F140 数组窗口**的证明；断言 bank 现为已证明的 0x596CCC 动作表 |
| `test_u32_pointer_patches::test_second_batch_wrappers_cover_declared_real_tables` | 要求对 0x5A14A4/0x5A2120/0x5A5774/0x5A3218 **真写** | 改用复刻线版本：这些基址一律**诊断只读**（master 自己的注册表也这么判） |
| `test_process_improvements::test_alias_conflicts_are_reported` | 0x53f138 仍应出现 audio/palettes 同址冲突 | 断言剩余两个已裁决同址冲突（0x545068 / 0x545be4），并断言 0x53f138 的**裁决记录仍在** CONFLICTS 里 |

**没有做的事**：没有为了让测试变绿而放宽任何**安全属性**断言。
`test_corrected_partial_views_are_diagnostic_only` 与
`test_all_three_legacy_editor_shapes_are_diagnostic_only` 里，
"不得对已证伪基址产生 ROM 字节补丁"这条安全属性**原样保留**；
只有"必须带某个诊断标记"这一实现细节按实际实现调整。

### 4.4 第三轮：master 新工具与复刻线 bank schema 的对接

第二轮之后还剩 7 项合并引入的失败，全部是同一根因：master 的新工具
`tools/analyze_battle_action_template_semantics.py` 要读
`sequel/content/skills/bank.json` 与 `sequel/content/battle-config/bank.json`
的**逐条原始 16 字节**（`raw_hex`），而 master 自己的 `skills` bank 用的是
`field_0..field_7` 的扁平命名、**没有 `raw_hex`**——也就是说
**这个新工具在 master 自己的树上同样跑不起来**。

**处置**：恢复复刻线的 `skills` bank（0x545BE4，94×16）。
它带 `raw_hex`、`runtime_verified`，以及已证明的语义字段
（`effect_code` / `ninja_tool_id` / `target_policy_and_flags` / `cost_kind` …），
master 的 `field_0..7` 注释「旧字段名来自错位窗口，已作废」指的是
**legacy 基址 0x546100** 的旧字段，不是 0x545BE4 这张已证明表的字段。

### 4.5 并行写入：合并窗口期工作区被同时修改

排查最后 2 项失败时发现，**合并窗口期（02:19–02:23）本工作区被同时写入了
7 组重制侧 round-25 战场 overlay 在飞工作**：

- `butano-sequel/game/include/konoha/generated_battle_battlefield_overlay_content.h`（新）
- `tools/generate_butano_battlefield_overlay.py`（新）
- `butano-sequel/game/include/konoha/battle_range_ui_style.h`（改）
- `butano-sequel/game/src/battle_runtime_scene.cpp`（改）
- `tests/test_s49_overlay_implementation.py`（新）
- `notes/battle-persistent-passive-stat-bindings-20260727.json`（新）
- `artifacts/s49-remake-overlay-step1-20261021-v1/`（新，75 个文件）

这 7 组**在 master 和保全提交 `777b2c96` 里都不存在**，是并行写入的在飞工作，
不是合并产物。**处置**：从合并提交 `68ab647a` 中排除（索引回退到 HEAD 版本、
新文件从索引移除但保留磁盘），另做独立保全提交 `b8a49c7e`，
避免把在飞工作混进合并提交，同时不让这批未入库的新文件失去保护。

### 4.6 其它

- `tools/automated_test.py`：master 把 `build_report_path()` /
  `output_rom_path()` 合并成了 `build_output_paths()`，且**读模块常量**而非
  每次读 `BUILD_OUTPUT_DIR`——破坏了"所有产物路径都跟随 `BUILD_OUTPUT_DIR`"
  的隔离契约。已把三个 API 统一到 `tools/build_mod.py::load_context`
  （它按调用读环境变量）。
- `tools/table_registry.py`：master 的新测试要求注册表**覆盖每个 content bank**。
  复刻侧有两个**不声明 `table_offset` 的分析型 bank**
  （`battle-presentation-scripts`、`battle-results`），注册表原本不支持这种条目。
  已让 `TABLES` 的基址允许为 `None`（复合/分析型 bank）并补两条登记。
- 本仓库 `core.autocrlf` 原为全局 `input`；master 的新门禁
  `test_core_autocrlf_is_false` 要求它是 false。已在**本仓库局部**设为 false
  （`git config --local core.autocrlf false`），**未改动用户的全局 `~/.gitconfig`**。

## 5. 验证

```
$ python3 tools/alias_audit.py rom/base.gba
registry-vs-bank 不一致: 0
未裁决冲突: 0
失败的判死检验: 0
RESULT: OK
```

```
$ python3 -m unittest tests.test_decode_dialogue_record tests.test_import_dialogue_var \
      tests.test_text_writeback tests.test_extract_tileset
Ran 25 tests ... OK
```

---

## 6. 遗留与风险

1. **`tools/extract_scene_tilesets.py` 改名后**，master 侧若有外部引用
   （`docs/`、`tools/README.md`）需要跟进；本树内已同步
   `tools/completion_audit.py` 的 3 处引用。
2. **master 的 `legacy_*` 注册表条目仍在**（`legacy_fonts` 0x53E5B4、
   `legacy_battle_handlers` 0x53E6D8、legacy_function_pointers 0x53D5F4 等），
   其中前两个是零读者基址。本树当前靠**空墓碑 + 生成器空实现**挡住，
   但注册表本身未做 repoint 裁决——留待 owner 统一处理，不在本次合入范围。
3. **`function-pointers` 0x53D5F4 是零引用但保留 runtime_verified**：
   它的证据来自**间接派发**（运行时字节选中槽位后回调触发），
   字面量扫描看不到这种寻址。这与「零读者即证伪」的一般判据不同，
   需要在裁决表里单列，本次未动。
4. 全量测试套件（370 个测试文件）的结果见
   `artifacts/merge-20261021-v1/full-suite.log` 与
   `artifacts/merge-20261021-v1/full-suite-summary.json`。
5. 这次合入**没有**把 master 的静态重编译工程（`recomp/`）与 web-editor
   接进重制线的构建链；那属于 roadmap 上的独立工作项。
6. **`tests/test_s49_overlay_implementation.py` 有 2 项失败，不是合并引入的**：
   该文件在 master 与保全提交 `777b2c96` 里**都不存在**，是合并窗口期出现在
   工作区的重制侧 round-25 在飞工作（`mtime 02:21`）。两项失败都是
   **断言自相矛盾**，不是代码回归：
   - `test_the_four_bpp_expansion_is_two_pixels_per_byte`：断言
     `len(data) == 1024`（32 个图块）却去索引 `data[262*32:263*32]`
     （第 262 块，偏移 8384）——取到空切片；
   - `test_the_selected_unit_lands_on_the_lens_centre`：期望网格
     `[0,1,1,2,2,3]` 与实测 `[0,1,2,3]` 不符。
   另有一处 `test_generated_header_is_up_to_date` **通过**，说明生成头文件与
   生成器当前一致——即测试期望的是尚未生成的图块数据。
   **处置：原样保留，不弱化断言、不删除**，交由该工作的 owner 收束。
7. 基线对照用的临时 worktree（`/tmp/gba-premerge`）已删除。
