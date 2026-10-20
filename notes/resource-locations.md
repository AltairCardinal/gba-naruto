# Resource Locations

Known addresses for graphics, palette, and audio resources in the ROM.

> 基线 ROM：`rom/base.gba`（SHA-1 `26f60795fa5e63b4f0264b84e453beffd56b9f7d`）。
> 本文件所有地址都写 **file offset**（`0x08xxxxxx` 形式的 ARM 地址另行标注）。

---

## 战斗地图图块（Battle Map Tilesets）

场景表定义在 ROM `0x0853D910`（**47 entries × 32 bytes**）。
Entry access: `base_file = 0x53D910 + map_id * 32`。
（其中 8 条为有效战斗场景配置，其余为地图/场景资源行。）

### 字段顺序（32 字节）

场景表 **file `0x53D910`**（ARM `0x0853D910`），8 条 × 32 字节。

> **2026-10-20 字段顺序更正**：本文件此前把 `+0x00` 当成 `tile_gfx_ptr`、
> `+0x1C` 当成 `packed_dims`，据此写的 `tools/extract_tileset.py` 取到的
> "指针"其实是 `0x0040005C` 这类维度数，**导出的全是空图**。
> 正确布局由 `tools/probe_external_re_claims.py` 按 LZ77 解压长度逐字段验证，
> 并由本次反汇编 `0x08068FF0`（场景表加载器）独立复核。

| Offset | Type | Name | Description |
|---|---|---|---|
| +0x00 | u16 | raw_width | 原始宽（`>> 2` = 图块宽） |
| +0x02 | u16 | raw_height | 原始高（`>> 1` = 图块高） |
| +0x04 | u32 ptr | tile_gfx_ptr | LZ77 压缩 tile 图形（4bpp，32 字节/图块） |
| +0x08 | u32 ptr | palette_ptr | LZ77 压缩调色板（384 字节 = 192 × BGR555 = 12 bank × 16 色） |
| +0x0C | u32 ptr | layer0_ptr | LZ77，图块层 0（metatile 索引平面，2 × cells u16） |
| +0x10 | u32 ptr | layer1_ptr | LZ77，图块层 1（可为 0） |
| +0x14 | u32 ptr | metatile_ptr | LZ77，组合图块表（8 字节/项 = 4 个 tile 描述符） |
| +0x18 | u32 ptr | terrain_ptr | LZ77，通行值表（每格 u16） |
| +0x1C | u8 | background_id | 剧情底图 ID（对应 `0x59903C` 表） |

> **命名沿革（2026-10-21 合并）**：重制侧此前用另一套名字描述**同一批槽位**
> —— `width`/`height`（`+0x00`/`+0x02`）、`bg_palette_ptr`（`+0x08`）、
> `primary_layout_ptr`（`+0x0C`）、`alternate_layout_ptr`（`+0x10`，
> 33 行为 null）、`metatile_attributes_ptr`（`+0x14`）、
> `collision_grid_ptr`（`+0x18`）、`flags`（`+0x1C`，u32）。
> **槽位偏移两套完全一致**；差别在读法与宽度：逆向侧按 `0x08068FF0`
> 加载器反汇编 + LZ77 解压长度逐字段验证，确认 `+0x00/+0x02` 是**原始**
> 宽高（÷4 / ÷2 才是图块数）、`+0x08` 是调色板、`+0x0C/+0x10` 是 layer0/layer1
> 两层 tilemap、`+0x18` 是通行（terrain）表、`+0x1C` 是 1 字节剧情底图 ID。
> 上表采用逆向侧的修正读法；`tools/extract_tileset.py`（重制侧）仍用重制侧命名，
> 两边指同一批槽位。

> **2026-07-12 correction**: the earlier shifted `base+4` view was wrong.
> `0x08068FB4/0x08068FF0/0x08069264` all agree on the unshifted row above.

**代码级证据（`0x08068FF0` 场景表加载器）**：

```
0x08069046: adds r0, r5, #4      ; r0 = &entry.tile_gfx      (+0x04)
0x0806905A: adds r0, r5, #8      ; r0 = &entry.palette       (+0x08)
0x0806906A: adds r0, r5, #0xc    ; r0 = &entry.layer0        (+0x0C)
0x0806907A: adds r0, r5, #0x10   ; r0 = &entry.layer1        (+0x10)
0x0806909E: adds r0, r5, #0x14   ; r0 = &entry.metatile      (+0x14)
```

- header `+8` decompresses to the actual 4bpp BG palette:
  - BGR555 u16 values, bit 15 = transparency flag (must be masked off: `bgr &= 0x7FFF`)
  - Contains 16 sub-palettes of 16 colors each = 256 colors = 512 bytes minimum
  - Entry 0 palette decompresses to 6160 bytes (may include tilemap attributes appended)
- header `+14` is metatile/attribute data, not colors; header `+18` is the
  collision/passability grid.

维度换算同样由代码确认（`0x08068FC0`）：

```
0x08068FC4: ldrh r0, [r0, #2]    ; raw_height
0x08068FCC: lsrs r0, r0, #2      ; width_tiles  = raw_width  >> 2
0x08068FD4: lsrs r0, r0, #1      ; height_tiles = raw_height >> 1
```

### Historical per-entry addresses (revoked shifted IDs)

The table below predates the 47-row correction and is retained only to explain
old artifact names. Do not use its IDs or palette column for new probes.

**逐条数据**（`tiles` = 图块数 = gfx 长度 / 32；`cells` = raw_width/4 × raw_height/2）：

## Battle Unit Visual Slot Table

- **Location**: ROM file `0x596D5C`
- **Shape**: 62 character IDs × 9 slots = 558 rows × 16 bytes
- **Population**: 342 valid rows, 216 all-zero reserved rows
- **Mapping**: `row = (character_id - 1) * 9 + visual_slot`
- **Structure**: 4 × u32 ARM pointers per valid row:
  - col0: frame descriptor pointer table
  - col1: animation descriptor pointer table
  - col2: raw 1D 4bpp OBJ tile data
  - col3: raw 16-color BGR555 OBJ palette
- **Idle**: slot 0 is valid for all 62 character IDs
- **Analysis/generation**:
  `tools/generate_butano_battle_unit_visual_content.py`,
  `tools/analyze_tile_table.py` (legacy filename)

The old `312 rows` boundary and map-tile interpretation were caused by stopping at the
first sparse gap and are invalid. 旧 312-row 地图 tile 解释已撤销. The independent battle
map header/metatile/collision chain remains at `0x53D910`; do not use this OBJ table as a
map tilemap.

> **与逆向侧 `sprite_action_table` 是同一张表（2026-10-21 合并确认）**：
> 逆向侧的 `tools/table_registry.py` 把 `0x596CCC` 记为**精灵动作表**
> `id*144 + action*16`，每项 4 个 u32 指针
> `(frames, animations, gfx, palette)`，18 个原生读者
> （例 `0x0806B76C`，`muls r1, r0, r1` 做 id 索引），id 1..62 有效。
> 与上面的记法对照：**逆向侧的 `id` ≡ 本节的 `character_id`，
> 逆向侧的 `action` ≡ 本节的 `visual_slot`**（9 × 16 = 144 字节/角色），
> 两边描述的是同一批 4 指针记录，只是基准框不同
> （本节从 id=1 的 `0x596D5C` 起算，逆向侧从 id=0 的 `0x596CCC` 起算）。
> 见 `tools/table_registry.py` 的 `sprite_action_table`。

| id | cells | tiles | metatiles | tile gfx | palette | layer0 | layer1 | metatile | terrain | bg id |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 23×32 | 672 | 770 | 0x0B9F80 | 0x0BD608 | 0x0BD70C | 0x0BDF00 | 0x0BE10C | 0x0BF250 | 1 |
| 1 | 15×15 | 320 | 144 | 0x0BF318 | 0x0C166C | 0x0C1710 | — | 0x0C18EC | 0x0C1CAC | 1 |
| 2 | 9×18 | 352 | 165 | 0x0C1CF8 | 0x0C416C | 0x0C4210 | — | 0x0C43E4 | 0x0C4844 | 1 |
| 3 | 9×20 | 224 | 121 | 0x0C4880 | 0x0C5F24 | 0x0C5FC8 | — | 0x0C6140 | 0x0C6410 | 1 |
| 4 | 9×20 | 288 | 164 | 0x0C6450 | 0x0C8454 | 0x0C84F8 | — | 0x0C86D8 | 0x0C8ABC | 1 |
| 5 | 9×23 | 320 | 163 | 0x0C8AF4 | 0x0CAA94 | 0x0CAB30 | — | 0x0CAD38 | 0x0CB138 | 1 |
| 6 | 15×16 | 256 | 169 | 0x0CB18C | 0x0CCB54 | 0x0CCC28 | — | 0x0CCE1C | 0x0CD21C | 2 |
| 7 | 15×16 | 672 | 443 | 0x0CD260 | 0x0D0054 | 0x0D0154 | 0x0D041C | 0x0D0638 | 0x0D1238 | 2 |

**自洽性检验**（可判死）：

- terrain 解压长度 = `cells × 2` 字节（entry 0：1472 = 23×32×2；entry 1：450 = 15×15×2）；
- layer0 解压长度 = `cells × 4` 字节（entry 0：2944 = 23×32×4）；
- metatile 解压长度 = 8 的整数倍（entry 0：6160 = 770×8）；
- metatile 里的 tile id 全部 < 本条目图块数（entry 0 最大 659 < 672；entry 7 最大 641 < 672）；
- metatile 里的 palette bank ∈ 0..10 ⊂ 调色板的 12 个 bank。

### 剧情底图表（Story Backgrounds）

**file `0x59903C`**，每 id 16 字节：

| Offset | Type | Name |
|---|---|---|
| +0x00 | u32 ptr | tile 图形（LZ77；4bpp 或 8bpp） |
| +0x04 | u32 ptr | 调色板（LZ77，384 字节 = 192 × BGR555） |
| +0x08 | u32 ptr | tilemap（LZ77，u16 GBA 格式：bit0-9 tile id / bit10 H-flip / bit11 V-flip / bit12-15 bank） |
| +0x0C | u32 | flags，bit0 = 8bpp 图形 |

非空 id：1..7（4bpp）、9..13（8bpp）、15（4bpp，tilemap 4864 项）。
8bpp 判定来自 `+0x0C` 的 bit0（id 9..13 置位），不是靠长度猜；这些条目的
gfx 长度也恰好是 64 的整数倍（id 9..11：19264 = 301 × 64 字节 = 301 个 8bpp 图块）。

### 提取器

`tools/extract_tileset.py` —— 正确处理 LZ77、4bpp/8bpp 图块、BGR555 调色板、
图块描述符里的 H/V 翻转标志与 palette bank。

```powershell
python tools/extract_tileset.py rom/base.gba --output-dir build/tiles
```

产出：`battle_XX_tiles.png`（图块图集）、`battle_XX_metatiles.png`（2×2 组合图块图集，
含翻转与 bank）、`battle_XX_map_layer*_*.png`（按 metatile 平面渲染的地图）、
`story_XX_tiles.png` / `story_XX_map.png`，以及 `build/tiles/manifest.json`。

**目视判据**：`build/tiles/battle_00_map_layer0_0.png` 渲染出连贯的木叶村
（屋顶/墙/草地连续、边界整齐），若 LZ77、4bpp 顺序、BGR555、metatile 排列
任一环节错位，图像会立刻碎成噪点或错位拼接。

---

## 音频（Audio）

### 结论速览

| 身份 | file offset | ARM | 结构 |
|---|---|---|---|
| **音频索引表（sound-ID 表）** | **`0x465B70`** | `0x08465B70` | 159 行 × 8 字节，索引 = `sound_id * 8` |
| 引擎初始化代码 | `0x09AE3C` | `0x0809AE3C` | 写 GBA 声音/FIFO/DMA 寄存器 |
| 音效 ID 分发器 | `0x09AAC0` | `0x0809AAC0` | `sound_id*8` → 描述符 → `0x0809B1F4` |
| 公开调用入口 | `0x061E6C` | `0x08061E6C` | `bl 0x0809AAC0` |
| 曲目/通道初始化 | `0x09B1F4` | `0x0809B1F4` | 初始化播放器/通道状态（结构偏移用到 +0x34） |
| **旧结论 `0x599634` 实为** | `0x599634` | `0x08599634` | **忍具名称文本指针表（94 项），不是音频** |

### 音频索引表：file `0x465B70` / ARM `0x08465B70`

每行 8 字节：

| Offset | Type | Name |
|---|---|---|
| +0x00 | u32 | descriptor_ptr（空行统一指向 `0x08466068`） |
| +0x04 | u16 | player_index（播放器槽位） |
| +0x06 | u16 | player_config |

- 行数 **159**（id 0..158）。id 159 的位置已经是空描述符数据本身（`0x466068`），
  不是第 160 行。
- **80 个非空 id**：`1..18`、`51..54`、`101..158`；其余行指向空描述符 `0x08466068`。

**判据 1 —— 代码确实查这张表**（`0x0809AAC0` 的字面量池）：

```
0x0809AAC2: lsls r0, r0, #0x10
0x0809AAC8: lsrs r0, r0, #0xd    ; r0 = sound_id * 8
0x0809AACA: adds r0, r0, r1      ; r1 = 0x08465B70
0x0809AACC: ldrh r3, [r0, #4]    ; player_index
0x0809ACE: lsls r1, r3, #1
0x0809AD0: adds r1, r1, r3
0x0809AD2: lsls r1, r1, #2       ; r1 = player_index * 12
0x0809AD4: adds r1, r1, r2       ; r2 = 0x08465B40 player slot 数组
0x0809AD6: ldr r2, [r1]          ; 该槽位当前曲目
0x0809AD8: ldr r1, [r0]          ; 新描述符
0x0809ADC: bl  0x0809b1f4
```

字面量池（Thumb：`[pc, #imm]` 基址 = `(insn+4) & ~3`）：

```
0x0809AAC4: ldr r2, [pc, #0x1c] -> 0x0809AAE4 = 0x08465B40   (player slot 数组)
0x0809AAC6: ldr r1, [pc, #0x20] -> 0x0809AAE8 = 0x08465B70   (sound-ID 表)
```

引擎初始化 `0x0809AE3C`（file `0x09AE3C`）的常量池里出现的 I/O 地址
（`tools/disasm_thumb.py` + 字面量池扫描）：

```
0x04000084  SOUNDCNT_L
0x040000A0  FIFO_A
0x040000A4  FIFO_B
0x040000C4 / 0x040000C6 / 0x040000D0  DMA 声音 FIFO 控制
```

—— 确认这是 GBA 的 FIFO/DMA 声音引擎，不是 PC/PSG 音源。

**判据 2 —— 指针链能解出真实音频数据**（`tools/extract_audio.py` 自带）：

```
sound id 1  -> descriptor 0x08536368 (file 0x536368)
                track_count=8 block_count=0 priority=0 reverb=128
                voicegroup=0x0846480C  track0=0x08535CFC
              -> 217 条 track 字节码全部解码通过（无未知 opcode、无越界控制目标）
              -> 23 个 voicegroup、400 条 12 字节 tone 记录
              -> 79 个 DirectSound wave 头（16 字节：u16 type/status、u32 频率、
                 u32 loop_start、u32 采样数）+ 849,634 字节有符号 8-bit PCM
```

wave 头实测样本：`0x46606C` → 频率 `0x00DAC000 / 1024 = 14000 Hz`，
loop_start 10505，20789 采样，PCM 从 `0x46607C` 开始。

### 描述符与 m4a 结构

描述符 = m4a `SongHeader`：

```
+0x00 u8 track_count      +0x04 u32 voicegroup_ptr
+0x01 u8 block_count      +0x08 u32 track_ptrs[track_count]
+0x02 u8 priority
+0x03 u8 reverb
```

tone 记录 12 字节：`u8 type, u8 key, u8 length, u8 pan_sweep, u32 pointer,
u8 attack, u8 decay, u8 sustain, u8 release`；type 0 = DirectSound（pointer 指向
wave 头），type 0x80 = 鼓组表。

**命令集来源**：m4a/MP2K 命令 ID 与参数宽度取自 pret/pokeemerald
`sound/MPlayDef.s`（<https://github.com/pret/pokeemerald/blob/master/sound/MPlayDef.s>），
并在本 ROM 上逐条校验——217 条 track 全部解码无未知 opcode、0 个控制流目标越界。

### 提取器

`tools/extract_audio.py` —— 基于上表重新实现（**不再使用 `0x599634`**）。

```powershell
python tools/extract_audio.py rom/base.gba                       # 清单（控制台表格）
python tools/extract_audio.py rom/base.gba --extract             # 导出
python tools/extract_audio.py rom/base.gba --extract --output-dir build/audio
```

产出（`build/audio/`）：

- `manifest.json` —— 159 行 sound-ID 表、80 条曲目描述符、217 条 track、
  400 条 tone、79 个 wave、命令直方图；
- `tracks/track_XXXXXX.bin` —— 217 条 m4a 字节码（边界 = 下一个 track / 描述符）；
- `waves/wave_XXXXXX_<rate>hz.wav` —— 79 个 DirectSound 采样（RIFF 需要无符号，
  故 ROM 的有符号 PCM 逐字节 `^0x80`）；
- `midi/sound_XXX.mid` —— 80 个 format-1 MIDI（24 PPQN，单次循环策略）。

MIDI 是**结构试听件**，不是位级还原：DirectSound 采样映射、0x80 鼓组、PSG 合成、
包络与音量/声像 LFO、跨循环 tie 释放、真实混音都还没有实现。

---

## 旧结论 `0x599634` 错在哪

**旧结论**：「`0x08599634` 是 Sappy 音频索引表，`0x08079668` 的 dispatcher
对命令 `0x80-0xE3` 查这张表」。

**它错在把「命令索引表」直接当成了「音频索引表」，而且把 `0x08079668`
当成了 Sappy 音频分发器。** 逐条判死：

1. **`0x08079668` 是文本/消息脚本解释器，不是音频分发器。**
   它对 cmd ≥ 0x80 取 `0x08599634[(cmd & 0x7F)]`，对 cmd < 0x80 取
   `0x0859937C[cmd]`，两张表都指向 **零结尾的字符串**：

   ```
   0x080796D8: ldr r1, [pc, #4]   -> 0x080796E0 = 0x0859937C   (cmd 0x00..0x7F, 87 项)
   0x080796E4: ldr r1, [pc, #0x18] -> 0x08079700 = 0x08599634   (cmd 0x80..0xE3, 94 项)
   0x080796F0: ldr r0, [r0]
   0x080796FA: bl  0x08066758
   ```

2. **取到的指针被送进文本解析器**：`0x08066758` 建消息对象后
   `mov r1, sb; bl 0x0806626C`；`0x0806626C` 是控制码解析器
   （分支处理 0x01/0x02/0x03/0x0A/0x1F 等控制码）。音频引擎不会解析控制码。

3. **表内容确实是中文文本**：用 `tools/text_codec.py`（不是 cp932）解码
   `0x599634` 的 94 个指针（index 0 是分隔线，index 1..93 是 93 个忍具名称）：

   ```
   [  0] ptr 0x08002288 -> '————————'   (分隔线)
   [  1] ptr 0x08002299 bytes=95ab9ca095d390ec8f41 -> '十字手里剑'
   [  2] ptr 0x080022A4 bytes=88c98c5b95d390ec8f41 -> '八方手里剑'
   [  3] ptr 0x080022AF -> '强力八方手里剑'
   ...
   [ 91] ptr 0x08002657 -> '万能丸'
   [ 92] ptr 0x0800265E -> '强力万能丸'
   [ 93] ptr 0x08002669 -> '超万能丸'
   ```

   第 94 个 u32（`0x599634 + 94*4`）为 0，表到此为止 —— 94 项 = 1 + 93。

4. **真正的音频表在别处**：`0x0809AAC0`（经 `0x08061E6C` 公开入口）按
   `sound_id * 8` 查 `0x08465B70`，且指针链能解出 wave 头 + PCM（见上）。

**复现命令**：

```powershell
# 1) dispatcher 反汇编：看它查哪两张表
$env:LIBCAPSTONE_PATH = 'D:\Shell\Github\gba-naruto\build\python-deps\capstone\capstone\lib'
python tools/disasm_thumb.py rom/base.gba 0x08079668 --before 0 --size 0x180
python tools/disasm_thumb.py rom/base.gba 0x0809AAC0 --before 0 --size 0xC0

# 2) 0x599634 的内容是文本
python tools/probe_external_re_claims.py        # 见 notes/external-konoha-workshop-gap-20261020.md §4 C3

# 3) 真正的音频表与指针链
python tools/extract_audio.py rom/base.gba
```

**影响面**：`notes/unknown-bgm-sfx.md` 与 `docs/structure-field-semantics.md` #22
里 "0x599634 = Sappy 音频索引表" 的表述同样应作废；
`notes/patch-generator-audit.md` 中 `audio_events` 指向 `0x599634` 的写回路径
属高风险，应禁用。

---

## 图块描述符表（精灵动作表）

- **位置**：ROM file `0x596D5C`
- **真实解释**：`0x596CCC + id*144 + action*16`（60 角色 × 9 动作 × 16 字节），
  4 个指针 `frames / animations / gfx / palette`；`0x596D5C` 恰是 `id=1` 行。
- 调色板 32 字节 = 16 × BGR555（含 `0x7FFF` 透明），是**精灵**调色板，
  不是地图调色板。
- 分析工具：`tools/analyze_tile_table.py`

## Tilemap 数据

多个 32×32 网格 tilemap（1024 u16 = 2048 字节）：

| File offset | Description |
|---|---|
| `0x14D000` | Battle map A |
| `0x195000` | Battle map B |
| `0x1CB000` | Battle map C |
| `0x1C2000` | Battle map D |
| `0x1F1000` | Battle map E |

格式：u16/图块 —— bit 9-0 = tile ID，bit 10 = H-flip，bit 11 = V-flip，bit 12-15 = bank。

---

**Status**: real engine, 159-ID master domain, 80 non-empty descriptors and one
live sound ID are located. The former 10 heuristic PCM hits are revoked.

### Proven locations

- sound-ID master: `0x465B70`, IDs 0..158
- non-empty IDs: 1..18, 51..54, 101..158
- descriptor/data range currently important: `0x536368..0x53D58B`
- public wrapper: `0x08061E6C`
- ID dispatch: `0x0809AAC0`
- song/track initialization: `0x0809B1F4`
- sound/FIFO/DMA initialization: `0x0809AE3C`

The heuristic `tools/extract_audio.py` scan found byte patterns resembling
DirectSound headers, but neither those headers nor their `+12` data addresses
have aligned pointer references. They are false-positive candidates and must
not be presented as samples, BGM, durations, or successful WAV extraction.
Real extraction now follows the m4a SongHeader voicegroup and track pointers.
`tools/extract_audio_assets.py` exports 217 bounded track blobs and 79 unique
pointer-reachable DirectSound WAV files under `build/audio-v2/`; the 16-byte
wave header and signed-to-unsigned PCM conversion are tested. Full chain and
runtime evidence: `notes/audio-engine-runtime-chain-20260712.md`.

---

## 对话字体（16×16 2bpp）——与 `0x53D644` 字形段表**不是同一套**

2026-10-20 用无头 mGBA 探针把场景 54 的对白真的画出来之后
（画面 `notes/evidence/story-scene-l3.png`），实测：

- 对白框里的**汉字是 16×16**（字距实测约 12 px = 汉字 16 px + ASCII 标点 8 px），
  而 `0x53D644` 字形段表是 **8×8 4bpp**（渲染器 `0x08065EF4` 的
  `lsls r0, r0, #5` = 32 字节/字形）。
- 把屏幕像素反查成调色板索引后逐字节比对，**对话汉字的位图也不在
  `0x53D644` 那张表里**；对话字形是 **2bpp**。

新定位到的数据区：

| File offset | 内容 | 证据强度 |
|---|---|---|
| `0x08142890` | 对话字形数据区起点（连续 2bpp 字形的猜测） | **未证实** |
| `0x0813E040` | 一张 **u16 字形偏移表**（0x0045, 0x0066, 0x0087, 0x00a7 … 递增） | **未证实** |
| `0x0813E120` | 字形数据（看起来是 2bpp） | **未证实** |
| `0x0596D60` | 一张 **u32 指针表**指向对话字形区（多处指向 `0x0813E070`，疑为空白字形） | **未证实** |
| `0x0142A70` | 一张 **24 字节步进的 u32 指针表**（指向 `0x081428xx`） | **未证实** |
| `0x0142AC0` | 一张 **(u16 code, u16 count) 对表**（`0xFFFF` 为段尾标记） | **未证实** |

> **一次被推翻的断言（留档）**：本轮曾用「屏幕像素 → 调色板索引 → 重新打包」
> 的方法，声称屏幕上一个 8×16 单元与 ROM `0x0813E209` 的 32 字节**逐字节相同**。
> 该结论**是错的**：
> ① 那个格子只有 2 个墨迹像素，匹配到的大概率是 ROM 里的**零填充区**；
> ② 随后用 16×16 单元重测，**所有**文字格都匹配不上，
> 说明「屏幕 → 调色板索引 → ROM 字节」这条反推链在**密集汉字**上不成立
> （文字带抗锯齿/半透明混合，屏幕颜色不是字形索引的直接投影）。
>
> 因此：**对话汉字的字形位图尚未定位**。上表是**候选**，不是结论。
> 已确证的只有一件事：对话里的汉字是 **16×16**、标点是 **8×8**，
> 两者都不是 `0x53D644` 那张 8×8 4bpp 表的位图。

**影响面**：`notes/font-encoding.md` §1.1/§1.2 已相应更正；
`tools/mgba_probe/screen_text.py` 只把**逐位精确**的格子记为 CONFIRMED。

**复现命令**：

```powershell
python tools/mgba_probe/render_screen.py notes/evidence/story-scene-l3.png \
    --live --rom rom/base.gba --press START --press A --press A --press A --press A
python tools/mgba_probe/screen_text.py rom/base.gba \
    --press START --press A --press A --press A --press A --rect 16,96,216,44
```

---

## 仍然无法导出的内容

- **完整乐曲音频渲染**：m4a → PCM 的端到端合成（DirectSound 通道分配、
  0x80 鼓组、PSG 噪声、包络/ADSR、跨循环 tie 释放、真实 DMA/混音）未实现；
  目前只有结构 MIDI 与原始 PCM 采样。
- **CGB（Game Boy）声道**（PSG 方波/噪声）的合成结果无法导出。
- **剧情底图 8bpp 条目**（id 9..13）只按 tilemap 顺序铺成 32×10 网格，
  它们在游戏里实际是整屏 8bpp 背景，层叠关系尚未还原。
- ~~`0x53F138` 的身份冲突（audio/palettes 两个 bank 同名此址）**未解决**~~
  —— **已于 2026-10-21 裁决**（见 `tools/table_registry.py` 的
  `CONFLICTS["0x53f138"]`）：该址是 `0x53F140` 起的 88 槽指针数组的头部窗口，
  与音频、地图调色板都无关；`audio` 已改指 `0x465B70` 的 sound-ID 表
  （`sound_id_table`），`palettes` 已改指 `0x53EE98` 的精灵帧描述符表
  （`sprite_frame_descriptors`），规范结构是 `0x53F140` 的对象描述符表。
