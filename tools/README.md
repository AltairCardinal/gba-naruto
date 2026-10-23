# Tools

## 字段普查与完成度核对（2026-10-22）

### `audit_claims.py`（**门禁**）

**文档的完成度宣称必须与机器事实一致。** 内容包里凡还标着
「未解字节 / 未知NN / 字节NN」的字段，只要文档里出现
「**语义 / 字段类缺口已清零**」这类断言，**退出码就是 1**。

```powershell
python tools\audit_claims.py
```

它存在的理由：上一轮提交写「所有语义类缺口已清零」，而同一时刻
忍具记录表那 16 格在编辑器里**全是**「未解字节」—— 用户一眼就看出来了。

### `field_semantics_census.py`

全包字段清单 + 文档里的完成度宣称清单。**按字段定义去重**：
90 张音频表共用同两个字段，不该算成 180 条。

```powershell
python tools\field_semantics_census.py
python tools\field_semantics_census.py --json build\field-census.json
```

### `table_reader_census.py`

任意表的「谁读哪一格」普查：扫出所有装载该表基址的指令（读者入口），
并列出这些函数里带立即数偏移的 load。

```powershell
python tools\table_reader_census.py --table 0x545458 --stride 16 --window 0x100
```

> **两个坑**：① 16 位 Thumb 的 `LDR(literal)` 在 `r1..r7` 时 **imm8 要乘 4**；
> ② 工具给出的偏移是**候选**，每一条都要回反汇编确认基址寄存器是不是记录指针。

证据：`notes/evidence/field-census-20261022.md`。

## 逐字节字段取证（2026-10-22）

### `item_record_fields.py`

忍具记录表 `0x08545BE4` 的**逐字节**取证与自检。三件事：

1. **读者普查** —— 全 ROM 扫 Thumb 的 `ldr Rt,[pc,#imm]`（位模式 `01001`，
   不依赖线性反汇编），把装载 `0x08545BE4` 的 7 条指令列出来；
2. **字段触达核对** —— 对每条已登记的读点，**直接解码那两字节 Thumb 指令**
   （`ldrb/ldrh` 的立即数偏移、`adds rX,#imm8`、`cmp rX,#imm8`），
   取出「偏移 + 宽度」与登记表比对，**对不上就 exit 1**；
3. **无读者证明** —— 所有读点的偏移并起来，并集里没有的字节就是
   「原生代码根本不读」的格子（`+0x01` / `+0x0E` / `+0x0F`）。

```powershell
python tools/item_record_fields.py rom/base.gba
python tools/item_record_fields.py rom/base.gba --json build/item-fields.json
```

> **踩过的坑**：16 位 Thumb 的 `LDR(literal)` 在寄存器是 `r1..r7`（字长）时，
> **imm8 要乘 4**。不乘 4 就会把字面量池地址算错 4 倍，普查会得出
> 「0 处读者」这种假结论。工具里写死了这条规则。

证据：`notes/evidence/item-record-fields-20261022.md`。

## L4 / L2 运行时证据闸门（2026-10-21）

### `mgba_probe/l4_battle_matrix.py`

L4 的可执行闸门：**全流程 / 全人物组合 / 全地图** 三条轴各跑一遍，
缺证据时**退出码非 0**。

* **全流程** —— 55 场逐场调度（脚本指针与根表条目逐位相等），
  外加**游戏自己驱动**的场景转移（见下面的 `l4_playthrough_flow.py`）。
* **全人物组合** —— 85 组真实队伍**全部被游戏自己打进过**。
  机制是三处内存写：停在状态机循环头 `0x0808F752`，然后
  `0x020311E6`←`0x0110`、`0x020311EA`←组号、`0x020311ED`←子配置号。
* **全地图** —— 47 个地图描述符全部被游戏真正载入并渲染，
  **47 个互不相同的 VRAM 哈希**。

```powershell
python tools\mgba_probe\l4_battle_matrix.py rom\base.gba --axis all \
    --out build\l4-bm --json build\l4-battle-matrix.json
```

### `mgba_probe/l4_playthrough_flow.py`

采集**游戏自己走出的场景转移图**。这个游戏的故事是**分支图**而不是一条链
（场景 39 给出 40..45 的分支，场景 45 把相位设成 `0x0100` 表示本章结束），
所以「全流程」的证据是**边集**：每条边都记录游戏选的场景号，
以及游戏随后**实际执行**的脚本指针（必须等于根表条目）。

```powershell
python tools\mgba_probe\l4_playthrough_flow.py rom\base.gba --scenes 1-55 \
    --out build\l4-graph --json build\l4-scene-graph.json
```

### `l2_runtime_capture.py`

L2（原生定点）闸门：断点命中原生消费者，寄存器/内存与字段一一对应，
再与静态表交叉核对，并带**反向对照**（故意改坏寄存器时检查必须失败）。
内置 `title` / `dispatch` / `battle` / `battle+sweep` 四条路线。

```powershell
python tools\l2_runtime_capture.py --list
python tools\l2_runtime_capture.py --self-test --json build\l2-runtime.json
```

### `mgba_probe/callback_census.py`

**回调表派发断点普查**。把哨兵点（战斗包装 `0x080732B4`、角色属性读数
`0x0806D98C`、地图载入读数 `0x08069040`）与**所有**已知派发点
（`0x0807FD28` / `0x0807F0FC` / `0x0807EE98` / `0x0807FE56` / `0x08080E44` …）
一起挂上，再跑 `battle` / `save` / `sweep` 三条路线。

用途：把「某个结构的原生读者够不到」从**猜测**变成**实测**——
哨兵命中而派发点 0 命中，就说明缺的是**一条能进入该模式的路线**，
而不是「还没试对按键」。结论见
`notes/evidence/callback-dispatch-tables-20261021.md`。

```powershell
python tools\mgba_probe\callback_census.py rom\base.gba --route battle --groups 0-5 --presses 40
python tools\mgba_probe\callback_census.py rom\base.gba --route sweep --scenes 1-55
```

### `mgba_probe/unitslot_probe.py`

在战斗里读出 12 个战斗单元槽的关键字段（`+0x00` / `+0x0C` / `+0x0E` /
`+0xBE` / `+0xC0`），并可**改写** `unit[0x0C]`。
`fn 0x0806DF88` 只在 `unit[0x0C] <= 9` 时才会走到回调派发路径，
这个工具用来测那个门控到底成不成立。

```powershell
python tools\mgba_probe\unitslot_probe.py rom\base.gba --groups 0,9
python tools\mgba_probe\unitslot_probe.py rom\base.gba --groups 0 --force
```

### `mgba_probe/spawn_forcer.py`

战斗包装 `fn 0x080732B4` 里**确实**有实体生成（`bl 0x080722A8` → `fn 0x08080E30`），
但它被两道门控挡住：`ctrl[0] != 0` 会跳过战斗入口，
`ctrl[0xCD] == 0xFF` 才走生成分支。这个工具在判定点现场改写门控字节，
看游戏自己的代码会不会走进去。

```powershell
python tools\mgba_probe\spawn_forcer.py rom\base.gba --groups 0,1,2
```

### `closure_portrait_pieces.py` / `closure_portrait_probe.py`

头像的两条 evidence 闭环：

* `closure_portrait_pieces.py` —— 拼块表基址的运行时读数：
  在头像加载路径上读静态描述符 `0x0846443C`，跟进它拿到拼块表 `0x084643C0`，
  核对 6×20 = 120 字节与 ROM **逐字节相等**。
* `closure_portrait_probe.py` —— `param << 4` 的运行时读数：
  在 VRAM 拷贝点断下，**WRAM 暂存缓冲 `0x02002880`** 的前 6144 字节与
  「ROM LZ77 解压结果 + 单个 `param<<4` 平移」逐字节相等（0 不符）。
  比对目标**必须**是 WRAM 暂存缓冲而不是 VRAM —— VRAM 里装的是拼好的成品。

```powershell
python tools\closure_portrait_pieces.py rom\base.gba --scene 1
python tools\closure_portrait_probe.py rom\base.gba --scene 1
```

### `m4a_block_table.py`

m4a **block 表**格式的逐字段拆解 + 往返自检：decode→encode 对 45 个原生
block **逐字节相同**（9952 字节 / 6333 条命令）。
同时提供块级重写（就地重写 / 重建 / 停在自由区并改指针）。

```powershell
python tools\m4a_block_table.py rom\base.gba --self-test
python tools\m4a_block_table.py rom\base.gba --sound-id 1 --json build\audio\blocks_001.json
```

### `build_editor_db.py`

`sequel/editor.db` 被 gitignore，所以**纯净检出下编辑器→构建的 override 链
安静地空转**。本工具从仓库内容（`sequel/content/*/bank.json`）**重建**它，
并当场验证链真的产出补丁（`--check` 会逐个生成器报 applied/rejected，
「全部被拒」就是基址或字段名过期的信号）。

```powershell
python tools\build_editor_db.py
python tools\build_editor_db.py --check
```

### `capstone_loader.py`

capstone 的统一加载器。仓库自带的 `tools/_vendor/capstone` 在本机
**加载不了**它的原生库（`ImportError: fail to load the dynamic library`），
真正能用的是 `build/python-deps` 里那份。直接 `import capstone` 的工具
会直接崩，所以统一走这里。

## ROM editor content pack (new, 2026-10-21)

### `export_content_pack.py`

Exports the editor's **initial data** — a self-describing dump of every
editable structure in `rom/base.gba`:

* 40 structures / 6,676 records (角色定义表、忍术记录表、道具记录表、奖励表、
  战场描述符、编成矩阵、战斗目标、剧情脚本四根根表、任务索引表、字形段表 …);
* 11 text tables / 2,418 texts (忍者问题表 1,524 槽、任务三张文本表、各类名字表、
  **战斗目标说明文字 219 条** …);
* the font code table, in both directions (decode + **canonical** encode);
* the base ROM, gzip-compressed, for the editor to rebuild from.

Two invariants make "an untouched pack rebuilds the original ROM byte for byte"
true: every structure's field list **tiles its record exactly** (unknown bytes
become `hex` fields), and every record keeps its original bytes next to the
decoded values.

Two more invariants for the text tables:

* **0x0A (换行) is a legal code** (`notes/font-encoding.md` §2).  The
  whole-ROM text scan used to reject it and dropped **1,126 strings** — among
  them the 32 battle-objective sentences.
* **One byte, one home.**  The battle-objective sentences have their own table
  and are excluded from the whole-ROM text index, so two tables never write
  the same address.

```powershell
python tools\export_content_pack.py            # → rom-editor/content/
python tools\export_content_pack.py --check    # 只校验内容包是否与 ROM 一致
```

The editor itself is `rom-editor/` (see `docs/rom-editor.md`); its
command-line self-check is `node rom-editor/tools/verify_pack.mjs`, and the
headless view check is `node rom-editor/tools/verify_views.mjs`.

## Text encoding (new, 2026-10-20)

The game's Chinese text uses a **custom double-byte font code**, not Shift-JIS.
See `notes/font-encoding.md`. These tools are the foundation for anything
that reads or writes game text.

### `text_codec.py`

The **single entry point** for encoding and decoding ROM text. Every writer
should go through it - it is the only place that can refuse to write bytes
the game cannot render.

- `encode(text, "font", mapping)` — writes the ROM's own glyph codes
- `decode(data, mapping)` — bytes → the text a player actually sees
- `decode_bounded(rom, offset, max_bytes, mapping)` — decode within a slot budget
- `encode_tokens` / `decode_tokens` — rewrite existing text with control codes intact
- Legacy encodings (`cp932` …) still work but raise `DeprecationWarning`
- ROM lookup order: `--rom` → `$KONOHA_ROM` → `rom/base.gba` → repo `*.gba`

```bash
python3 tools/text_codec.py
python3 tools/text_codec.py --encode "漩涡鸣人"
python3 tools/text_codec.py --decode-hex "89df95d1"
```

### `verify_text_writeback.py`

Acceptance gate for the write path: applies the dialogue patches to the base
ROM, reads the result back, and asserts the rendered text equals the authored
text. Also checks an already built ROM.

```bash
python3 tools/verify_text_writeback.py
python3 tools/verify_text_writeback.py --verify-rom build/naruto-sequel-dev.gba
```

### `hook_points.py`

Runtime hook sites in the base ROM with their **verified original-byte
preimages** — the same precondition our patch pipeline enforces with
`before_hex`. Sourced from the vendored third-party package; all 16 preimages
match our ROM byte for byte, so they can be used directly as patch anchors.

Also carries the original function entry addresses (for tail-call forwarding).

```bash
python3 tools/hook_points.py
python3 tools/hook_points.py --json build/hook-points.json
```

## Process improvements (new, 2026-10-20)

Adopted from the third-party package's own test/build discipline.
See `notes/re-methodology-improvements-20261020.md`.

### `synthetic_fixture.py`

Proves a table's **format** without the emulator: write content of known
meaning into the ROM, point the game at it, read it back with the production
reader, and require the read to equal the write. Works on a copy; the result
lands in `build/synthetic-fixtures/`.

```bash
python3 tools/synthetic_fixture.py
python3 tools/synthetic_fixture.py --fixture story_before
```

### `table_registry.py`

The single authoritative source for table base addresses, and the cross-check
against the `sequel/content/*/bank.json` offsets. A mismatch is an error, not
a warning — base pointers must not come from editable content files.

```bash
python3 tools/table_registry.py
```

### Build change radius

`tools/build_mod.py` now reports `change_radius` in the build report and
**fails the build** if any byte changed outside a declared patch range.

### `process` test suite

`python3 tools/automated_test.py --suite process` runs the synthetic
fixtures, the registry cross-check and the change-radius gate on every
standard test run.

## Asset formats & battle objects (new, 2026-10-20)

### `sprite_frames.py`

Battle sprite animation format: the action table at `0x596CCC + id*144 + action*16`
(frames / animations / gfx / palette pointers), the 20-byte piece descriptors
inside each frame, and the 8x8 4bpp tile layout. Reports anomalies instead of
hiding them.

```bash
python3 tools/sprite_frames.py rom/base.gba --stats
```

### `tile_asset_rules.py`

Everything about replacing a single map cell: how a palette bank is allocated,
the 1024-tile and 1024-metatile ceilings, the per-cell cost, and the three
failure conditions. Includes `--selftest` and a full end-to-end simulation
across all 47 maps.

```bash
python3 tools/tile_asset_rules.py rom/base.gba --stage 40
python3 tools/tile_asset_rules.py rom/base.gba --selftest
```

### `mechanism_map.py`

The native pickup dispatch table `0x815E4` (7 handlers) with disassembly
evidence, and the 8 map-object record types with their measured distribution.

```bash
python3 tools/mechanism_map.py rom/base.gba --stats
```

### `portrait_assets.py`

Portrait format: the pointer table `0x5A4DEC`, the 6 pieces at `0x4643C0`
that assemble an 80x80 portrait, and the raw 128-byte palette.

```bash
python3 tools/portrait_assets.py --json build/portrait_assets.json
```

### `extract_tileset.py` / `extract_audio.py`

Resource extraction. `extract_audio.py` is based on the real sound-ID table
at `0x465B70` (the old `0x599634` "audio table" was a text-script command
table). See `notes/resource-locations.md`.

```bash
python3 tools/extract_tileset.py rom/base.gba
python3 tools/extract_audio.py rom/base.gba --extract
```

## Runtime state & battle objects (new, 2026-10-20)

Absorbed from the third-party package and re-derived against our ROM.
See `notes/runtime-and-object-tables-20261020.md`.

### `runtime_state.py`

The game's WRAM state map. Every address is cross-checked against the ROM:
a field the game itself loads shows up as a literal in its code, so the tool
distinguishes **native fields** from the third party's own bookkeeping.

```bash
python3 tools/runtime_state.py --json build/runtime_state.json
```

### `extract_rewards.py`

Reward table `0x59EAE0` — per-battle loot, with the tail layout
`(item id << 8) | count` derived from the ROM's own data.

```bash
python3 tools/extract_rewards.py --json build/rewards.json
```

### `object_tables.py`

Battle map objects: the 8 record types, the 16 records per scene, the native
pickup dispatch table `0x815E4` and the story background table `0x59903C`.

```bash
python3 tools/object_tables.py --stage 40 --sub 0
```

### `event_queue_budget.py`

Static analysis of the battle logic scripts: how many conditional dialogue
events a scene can still take. The 16-entry queue limit is confirmed by
stage 1's original script reaching exactly 16.

```bash
python3 tools/event_queue_budget.py --json build/queue_budget.json
```

### `portrait_assets.py`

Portrait format: the pointer table `0x5A4DEC`, the 6 pieces at `0x4643C0`
that assemble an 80x80 portrait, and the raw 128-byte palette.

```bash
python3 tools/portrait_assets.py --json build/portrait_assets.json
```

### `migrate_text_bank_to_font.py`

Migrates the dialogue bank/content from the old cp932 mojibake to the font
codes, and rewrites the bank notes with the real Chinese the ROM contains.

```bash
python3 tools/migrate_text_bank_to_font.py --out build/migrate.json
python3 tools/migrate_text_bank_to_font.py --apply --bank-only
```

### `konoha_font.py`

Builds the code→character mapping for the ROM's baked-in font.

- Parses the font segment table at `0x53D644` (31 slots × 8 bytes)
- Fingerprints each segment with FNV-1a and only applies a character table
  when the font bytes match the table it was derived from
- Seeds the mapping from the ROM's own character-name table at `0x599280`
- `decode_at()` / `encode_text()` for reading and writing
- `read_character_names()` decodes the 62-character roster from the ROM

```bash
python3 tools/konoha_font.py
```

### `font_roundtrip.py`

Proves the mapping is correct and writes new text safely.

- Re-encodes real in-game text and checks `encode(decode(x)) == x` byte for byte
- Compares the old hand-made `sjis-to-tile-mapping.json` against the ROM
- Can emit a full code→character map that supersedes the hand-made table

```bash
python3 tools/font_roundtrip.py
python3 tools/font_roundtrip.py --emit-mapping sequel/content/text/font-code-map.json
```

## Story script VM (new, 2026-10-20)

### `decode_story_script.py`

Decodes the story bytecode into a node graph. See `notes/story-script-vm.md`.

```bash
python3 tools/decode_story_script.py --scene 1
python3 tools/decode_story_script.py --all --stats --out build/story_scripts.json
```

### `dump_story_text.py`

Renders the story scripts as readable Chinese with speaker attribution.

```bash
python3 tools/dump_story_text.py --all --out build/story_text.txt --json build/story_text.json
```

## Battle tables (new, 2026-10-20)

### `extract_battle_tables.py`

Extracts the victory/defeat condition table (`0x594758`), the mission text
tables (`0x348DAC` + three text tables) and the character slot table
(`0x5461C4`). See `notes/battle-tables.md`.

```bash
python3 tools/extract_battle_tables.py
python3 tools/extract_battle_tables.py --stage 40 --json build/battle_tables.json
```

---

## Native consumer locating & completion audit (new, 2026-10-20)

The audit's C2 rule accepts a "native code addressing" proof, but until now
every such proof was a human reading a disassembly and typing an address into
a note. These tools make it **mechanical and re-checkable**.

### `consumer_locate.py`

Builds a **whole-ROM literal index** (ARM `LDR Rn,[pc,#imm]`, Thumb-1
`LDR Rt,[pc,#imm]`, Thumb-2 `LDR.W Rt,[pc,#imm]`) and then, for any table
base, answers three questions:

* which native instructions read it (function boundary + usage class +
  deduced entry stride),
* is the address **real at all** — 21 legacy bases turned out to be named
  nowhere in the ROM, not even by a data pointer,
* what is the *real* base nearby (`--neighbors`).

```bash
python3 tools/consumer_locate.py rom/base.gba --all \
    --evidence notes/evidence/consumer-evidence.json
python3 tools/consumer_locate.py rom/base.gba --target 0x54241C
python3 tools/consumer_locate.py rom/base.gba --target 0x546100 --neighbors 4096
```

The evidence file carries the ROM's SHA-256, so stale evidence expires by
itself. See `notes/legacy-table-base-correction-20261020.md`.

For a legacy bank whose declared base is referenced **nowhere** in the ROM,
`--suggest` lists the strongest candidate bases around it (ranked by how many
native instructions read them), so the hunt for the real base starts from
evidence instead of a guess:

```bash
python3 tools/consumer_locate.py rom/base.gba --target 0x546100 --suggest 4096
```

### `completion_audit.py`

Recomputes the per-structure completion table from what is actually in the
repository. Three probe kinds were added:

* `codecite` — the machine-checked form of "native code addressing": it
  re-reads the consumer evidence, verifies the ROM digest, and requires the
  structure to be read by the game's own code;
* `notatable` — the negative proof: the declared base is named nowhere in
  the ROM, so the identity question is closed (the base is wrong);
* `writeback` — the **executable** write-back proof: the audit *runs* the
  structure's round-trip case from `writeback_paths.py` against a copy of
  the ROM and requires (a) the read-back to equal the author input and
  (b) no byte outside the declared known-field set to have moved.  A
  write-back path only counts once it actually round-trips.

`codecite` / `notatable` are attached **automatically by base address**, so
new evidence needs no audit change.  See `notes/completion-audit-20261020.md`.

```bash
python3 tools/completion_audit.py --check
python3 tools/completion_audit.py --note notes/completion-audit-20261020.md
```

### `writeback_paths.py`

The self-check every write-back path must pass: for each structure, read a
native entry out of the ROM, apply an author change, read it back and assert
that the read-back equals the author input **and** that the bytes whose
meaning is unknown were left alone.  Non-zero exit on any mismatch.

```bash
python3 tools/writeback_paths.py rom/base.gba
python3 tools/writeback_paths.py rom/base.gba --json build/writeback-paths.json
```

Covers 12 paths: the four story VM root tables, the character template, the
16-byte jutsu record table, the sprite action table, the battle map
descriptor, the formation matrix, the reward table, the scene object
descriptor table, the level data pointer table, the WRAM allocation table and
the u16 offset table.

### `alias_audit.py`

Re-derives every same-address collision between the 32 content banks and
re-checks the adjudication recorded in `tools/table_registry.py`
(`CONFLICTS` / `ALIASES` / `FALSIFIED`) against the ROM itself.
See `notes/alias-conflicts-20261020.md`.

```bash
python3 tools/alias_audit.py rom/base.gba
```

## Opcode & field semantics (new, 2026-10-20)

### `story_vm_ops.py`

The story VM's opcode set, derived from the ROM: interpreter entry
`0x080977B8`, jump table `0x080977F4`, and a per-opcode proof status.
38 of 44 opcodes are **proved**, 6 remain inferred.
See `notes/story-vm-opcodes-20261020.md`.

```bash
python3 tools/story_vm_ops.py rom/base.gba
```

### `reward_rules_semantics.py`

The reward table's tail byte (a **category tag**, not a quantity) and the
battle-rule condition types. See `notes/reward-and-rules-semantics-20261020.md`.

```bash
python3 tools/reward_rules_semantics.py rom/base.gba
```

### `character_templates.py`

The character template table `0x54241C` (0xB4 bytes per id), the per-character
growth table `0x545068` and the 16-byte battle records at `0x545458`.
See `notes/character-template-format-20261020.md`.

```bash
python3 tools/character_templates.py rom/base.gba
```

### `import_reward.py`

The write-back path for the battle reward table `0x59EAE0` (24-byte records:
gold / upgrade points / tier plus eight two-byte tail slots, each slot being
a category tag and an item id).  The author-supplied item id is validated
against the capacity of that category's **own** name table, taken from the
ROM's category→name-table pointer table at `0x59F5E0`.
See `notes/reward-and-rules-semantics-20261020.md`.

```bash
python3 tools/import_reward.py rom/base.gba --index 0 --set gold=500 \
    --set slots='[{"category":0,"item_id":3}]' --out build/naruto.gba
```

### `audio_song_headers.py` / `import_audio_song.py`

The m4a **SongHeader**s behind the sound-ID table at `0x465B70` (8 bytes per
row, each row pointing at a header).  Five of those headers are what the
legacy content banks called `story`, `story-b`, `story-c`, `story-d` and
`story-e` — their bases were 4 bytes late because the legacy extractor
anchored on the `voicegroup_ptr` field instead of the header start.

    +0x00 u8   track_count
    +0x01 u8   block_count
    +0x02 u16  pad
    +0x04 u32  voicegroup_ptr
    +0x08 u32  track_ptr[track_count]

The extractor self-checks; the writer is the **write-back path** for swapping
a music track.  Because the track *block* format is not proved, the writer
only accepts a target that already occurs as a track pointer in the sound
table — the same rule the `units` offset table uses.

```bash
python3 tools/audio_song_headers.py rom/base.gba
python3 tools/import_audio_song.py rom/base.gba --sound-id 1 \
    --set track0=0x08535CFC --out build/naruto.gba
```

### `legacy_rebase.py` / `story_table_locate.py`

Triage for the legacy banks whose declared base the ROM never names.  Both
query the **full** literal index (`consumer_locate.LiteralIndex`, 18051
values) — **not** the 54-table evidence subset, which silently truncates
the candidate set.  `legacy_rebase.py` also re-derives entry strides with a
symbolic pass scoped to each reader's own dataflow, so one load's immediate
cannot be paired with another load's multiply.

```bash
python3 tools/legacy_rebase.py rom/base.gba --target 0x54507A
python3 tools/legacy_rebase.py rom/base.gba --all-legacy
python3 tools/story_table_locate.py rom/base.gba --target 0x53636C
```

### `frame_descriptors.py`

The sprite frame descriptor table `0x53EE98` — found 2026-10-21 while
settling the `units` offset table.  It is live: three native instructions
load `0x0853EE98` (`0x080806BA`, `0x0808077E`, `0x0808082E`) and all three
index it with a **10-byte** stride.  The tool prints the five u16 fields per
record, marks the two structural fields (`list_end` at +0 == -1, `walk_end`
at +8 != 0) and **fails loudly** when the observed value domains drift —
it is a check, not a formatter.  See
`notes/evidence/units-offset-table-20261020.md`.

```bash
python3 tools/frame_descriptors.py rom/base.gba
python3 tools/frame_descriptors.py rom/base.gba --json build/frame-descriptors.json
```

### `battle_rules_runtime.py` / `runtime_capture.py`
Runtime evidence tools built on the headless probe: the first drives the
native battle-rule dispatcher and records the decision matrix of the type-2
("turn limit reached") arm, the second dumps the runtime state block with
real readouts.  Both exit non-zero when the ROM's layout does not match what
they assume.  See `notes/evidence/battle-rules-l2-20261020.md` and
`notes/evidence/runtime-state-l3-20261020.md`.

```bash
python3 tools/battle_rules_runtime.py rom/base.gba
python3 tools/runtime_capture.py rom/base.gba
```

### `cutscene_block.py`

A breadth-first Thumb disassembler that **skips literal pools** (a linear
disassembly reads the constant pool as instructions), plus the reader
forensics for the level data block table `0x53DF70`: it extracts the
stride, the BIOS SWI and the destination addresses, decodes the LZ77
blocks and checks them against the story VM script set.
See `notes/evidence/cutscene-block-format-20261020.md`.

```bash
python3 tools/cutscene_block.py rom/base.gba
python3 tools/cutscene_block.py rom/base.gba --disasm 0x08072EDC
```

## Headless runtime probe (new, 2026-10-20)

### `mgba_probe/runtime_probe.py`

Drives the headless mGBA probe: injects keys, arms breakpoints and **write
watchpoints**, and records the game's own key state (`0x0300000C` held,
`0x0300000E` newly pressed) plus the registers at every hit.
See `notes/mgba-probe-runtime-20261020.md`.

```bash
python3 tools/mgba_probe/runtime_probe.py rom/base.gba --press START --press A
python3 tools/mgba_probe/runtime_probe.py rom/base.gba \
    --breakpoint 0x080977B8 --json build/runtime-trace.json
```

### `mgba_probe/render_screen.py`

Draws the emulated screen and saves it as a PNG.

`--live` asks the probe for **mGBA's own rendered frame** (the host's
`rawshot` command dumps the core's 240x160 RGBA video buffer), so the
picture is exactly what a player sees.  That path needs neither PNG
support in mGBA nor a second implementation of the PPU.

`--live-vram` reconstructs the picture from VRAM / PALRAM / the display
registers instead; it is a debugging aid for the PPU understanding.

```bash
python3 tools/mgba_probe/render_screen.py build/shot.png --live --rom rom/base.gba
python3 tools/mgba_probe/render_screen.py build/shot.png --live --rom rom/base.gba \
    --press START --press A --press A
```

### `mgba_probe/screen_text.py`

Reads the text off the emulated screen and maps the glyph cells back to
the ROM's font codes, which turns "the game shows Chinese" into a
checkable statement.

```bash
python3 tools/mgba_probe/screen_text.py rom/base.gba \
    --press START --press A --press A --press A --rect 8,104,224,48
```

---

## `scan_rom.py`

Preliminary static scanner for a GBA ROM.

Current checks:

- aligned 32-bit values that point back into the ROM address space
- ASCII-like runs
- zero-filled runs that may indicate free space
- coarse byte-frequency summary

Example:

```bash
python3 tools/scan_rom.py '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba'
```

The machine-readable output is written to `notes/scan-report.json` by default.

## `find_pointer_refs.py`

Finds all aligned `32-bit` references to a target ROM offset or GBA address.

Example:

```bash
python3 tools/find_pointer_refs.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x4081 \
  --output notes/pointer-refs-004081.json
```

## `analyze_table.py`

Analyzes a ROM region as a fixed-size table and classifies each `u32` field.

Example:

```bash
python3 tools/analyze_table.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x596F98 \
  0x10 \
  16 \
  --output notes/table-596F98-10.json
```

## `inspect_block.py`

Inspects a pointed ROM block and makes a coarse guess about whether it looks like:

- nested descriptor
- palette-like data
- sparse binary
- binary or compressed data

Example:

```bash
python3 tools/inspect_block.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x17A1A4 \
  0x40 \
  --output notes/block-17A1A4.json
```

## `profile_table_blocks.py`

Walks a fixed-size pointer table and classifies the blocks referenced by each column.

Example:

```bash
python3 tools/profile_table_blocks.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x596F98 \
  0x10 \
  16 \
  --output notes/profile-596F98.json
```

## `find_sjis_blocks.py`

Scans the ROM for Shift-JIS-like text regions, useful for locating script or encoded Japanese resources.

Example:

```bash
python3 tools/find_sjis_blocks.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  --output notes/sjis-blocks.json
```

## `extract_text_block.py`

Splits a suspected text block into candidate strings using `0x00` and line breaks as separators.

Example:

```bash
python3 tools/extract_text_block.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x76C \
  0x1A0 \
  --output notes/text-block-00076C.json
```

## `find_similar_tables.py`

Searches the ROM for runs of `0x10`-byte rows that look like four-pointer resource tables.

Example:

```bash
python3 tools/find_similar_tables.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  --start 0x500000 \
  --min-rows 4 \
  --output notes/similar-tables.json
```

## `patch_sjis.py`

Creates a patched ROM copy by writing Shift-JIS text at a fixed ROM offset.

Example:

```bash
python3 tools/patch_sjis.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  'rom/experiment.gba' \
  0x76D \
  試験 \
  --expected-len 4
```

## `mgba_trace_dialogue_writes.lua`

Headless scripted watchpoint probe for the opening dialogue scene.

Supported targets through `NARUTO_TRACE_TARGET`:

- `wram`
- `vram_tilemap`
- `vram_glyph`

Example:

```bash
NARUTO_TRACE_TARGET=wram \
tools/run_headless_mgba.sh \
  tools/mgba_trace_dialogue_writes.lua \
  build/naruto-sequel-dev.gba
```

Outputs land in `notes/` as `dialogue-watch-*.log`, `dialogue-watch-*.summary.txt`, and `dialogue-watch-*.done`.

## `summarize_watch_hits.py`

Converts raw watchpoint logs into short markdown summaries.

Example:

```bash
python3 tools/summarize_watch_hits.py \
  notes/dialogue-watch-wram.log \
  --title 'Dialogue WRAM Watch Summary' \
  --output notes/dialogue-watch-wram.md
```

## `disasm_thumb.py`

Disassembles a ROM window as GBA Thumb code using the vendored `capstone` package in `tools/_vendor/`.

Example:

```bash
python3 tools/disasm_thumb.py \
  build/naruto-sequel-dev.gba \
  0x08066D74 \
  --before 0x30 \
  --size 0x80 \
  --output notes/disasm-08066D74.txt
```

## `find_thumb_calls.py`

Scans the ROM for Thumb `bl`/`blx`/direct `b` instructions that target a specific ROM address.

Example:

```bash
python3 tools/find_thumb_calls.py \
  build/naruto-sequel-dev.gba \
  0x08066D14 \
  --output notes/calls-08066D14.txt
```

## `mgba_trace_function_entries.lua`

Experimental script-side execution breakpoint tracer for selected dialogue functions.

Targets through `NARUTO_ENTRY_TARGET`:

- `dialogue_wram_func`
- `dialogue_glyph_func`

Current status:

- useful as a recorded experiment
- not yet as reliable as watchpoint-based tracing on this project

## `mgba-headless-snapshot.py --mode probe`

可复现的 mGBA CLI 执行断点探针。它在同一调试器进程内设置 PC
断点，命中后记录寄存器并读取一个或多个 ROM/WRAM 范围。JSON 中只有出现
`Hit breakpoint ...` 时才会令 `hit=true`；普通 `status` 输出不会被误判为命中。

```bash
python3 tools/mgba-headless-snapshot.py \\
  --rom rom/base.gba --mode probe \\
  --breakpoint 0x08068FF0 \\
  --read 0x0853D910:32 --read 0x02024290:64 \\
  --frames 0 --timeout 300 \\
  --output notes/map-position-probe.json
```

边界：CLI 调试器不能注入按键。冷启动若无法自然到达该 PC，会等待超时；
此时应通过可复现的 Lua 导航或有效战斗 savestate 先建立可达状态，不能把
静态 ROM 读取本身当作 map loader 的动态命中证据。

## `inspect_wram_region.py`

Renders a region inside a WRAM dump as bytes, ASCII-like view, and halfwords.

Example:

```bash
python3 tools/inspect_wram_region.py \
  notes/dialogue-2160-wram.bin \
  0x2880 \
  0x140 \
  --output notes/region-02002880-2160.txt
```

## `compare_wram_regions.py`

Shows byte-level differences for a selected region between two WRAM dumps.

Example:

```bash
python3 tools/compare_wram_regions.py \
  notes/dialogue-2160-wram.bin \
  notes/dialogue-2700-wram.bin \
  0x2880 \
  0x140 \
  --output notes/diff-02002880-2160-2700.txt
```

## `import_dialogue.py`

Imports dialogue content from `sequel/content/dialogue/*.json` into the ROM at runtime, replacing dialogue ID entries with strings from the JSON file. Reads current dialogue entries from the running ROM and updates them in-place.

Example:

```bash
python3 tools/import_dialogue.py
```

## `import_map.py`

Imports map scene data from a JSON map definition file into the ROM build. Expects a JSON file with map tile data, dimensions, and scene metadata.

Example:

```bash
python3 tools/import_map.py sequel/content/maps/episode-01-mountain-pass.json
```

## `import_battle_config.py`

Imports battle configuration data (enemy lineups, stage parameters, wave definitions) from the `sequel/content/battles/` directory into the ROM build.

Example:

```bash
python3 tools/import_battle_config.py
```

## `build_mod.py`

Main ROM build entrypoint. Applies all patches and content imports (dialogue, maps, battle configs) to produce `build/naruto-sequel-dev.gba`. Also handles base ROM detection and patch application.

Example:

```bash
python3 tools/build_mod.py
```

## `automated_test.py`

Runs automated headless tests against the built ROM using mGBA. Verifies that dialogue, map, and battle imports are correctly reflected in the emulated game state. Outputs test results to `notes/test-results/`.

Example:

```bash
python3 tools/automated_test.py
```
