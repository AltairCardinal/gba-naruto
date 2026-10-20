# 内容包导出证据 — 2026-10-21

**一句话**：`tools/export_content_pack.py` 端到端可用；导出后 `--check` 与 ROM
一致，并且**每一条记录都能只靠字段值逐字节重建回 ROM**（5,740/5,740 条通过）。
本轮修掉了 6 张表的**记录模型错误**（字段描述了整张表、却按单条记录存放），
并给 `tile()` 加了越界检查防止复发。

---

## 0. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'

# (1) 导出（默认写到 rom-editor/content/）
python tools\export_content_pack.py

# (2) 校验：包与 ROM 逐字节一致（退出码 0 = 一致）
python tools\export_content_pack.py --check

# (3) 强校验：只用字段值重建每条记录，再和 raw / ROM 对比
python build\content_pack_roundtrip.py

# (4) 枚举包内容，并和 tools/table_registry.py 对表找出缺口
python build\content_pack_gaps.py
```

> `build/` 下的两个脚本是本次调查的可复现探针，不进版本库；
> 结论已写进本文件。

**当前实测输出**

```
$ python tools\export_content_pack.py
已导出内容包: ...\rom-editor\content\pack.json (3,608,394 字节)
  浏览器用: ...\pack.min.json.gz (226,920 字节 gzip，解压后 2,699,063 字节)
  结构 25 个 / 记录 5,740 条
  文本表 10 个 / 文本 2,199 条
  字形码 4,261 个
已导出原版 ROM: ...\base-rom\base-rom.bin.gz (6,291,456 字节 → 2,702,839 字节 gzip)
已导出全 ROM 文本索引: ...\text-index.json.gz (16,008 条)

$ python tools\export_content_pack.py --check
OK: 内容包与 ROM 一致

$ python build\content_pack_roundtrip.py
structures checked: 25
records rebuilt from field values alone: 5740
text tables: 10
ROUND-TRIP: PASS (fields -> bytes == raw == ROM for every record)
```

---

## 1. 包里有什么

包格式：`naruto-konoha-content-pack` v1，JSON（`indent=1`，UTF-8，LF）。
顶层键：`format` / `version` / `generated` / `structures` / `texts` / `font` /
（`--text-index` 时额外带一张全 ROM 文本索引表）。

### 1.1 结构（25 张，5,740 条记录）

| id | 名称 | ROM 基址 | 条数 × 记录长度 |
|---|---|---|---|
| `character_template` | 角色定义表 | `0x54241C` | 63 × 180 |
| `per_character_stats` | 逐角色成长表 | `0x545068` | 63 × 16 |
| `character_perks` | 角色特性表（技能） | `0x5459C8` | 45 × 12 |
| `portrait_table` | 头像指针表 | `0x5A4DEC` | 64 × 40 |
| `portrait_pieces` | 头像拼块表 | `0x4643C0` | 6 × 20 |
| `jutsu_record` | 忍术记录表 | `0x545458` | 87 × 16 |
| `item_record` | 道具/忍具记录表 | `0x545BE4` | 94 × 16 |
| `reward_table` | 奖励表 | `0x59EAE0` | 112 × 24 |
| `map_table` | 战场布置描述符 | `0x53D910` | 47 × 32 |
| `battle_actors` | 角色出生点（编成表） | `0x5461C4` | 1,692 × 184 |
| `battle_map_objects` | 战场物件 | `0x5461C4` + 每组 +0x8A4 | 2,256 × 4 |
| `battle_rules` | 战斗目标（胜负条件） | `0x594758` | 141 × 68 |
| `battle_encounter_records` | 战斗遭遇记录表 | `0x54229C` | 24 × 16 |
| `unit_slot_remap` | 单位槽位重映射表 | `0x53F298` | 43 × 2 |
| `unit_delta_table` | 八方向位移表 | `0x53F2EE` | 16 × 2 |
| `level_blocks` | 关卡数据块表 | `0x53DF70` | 4 × 8 |
| `object_descriptors` | 对象描述符表 | `0x53F140` | 86 × 4 |
| `sprite_action_table` | 精灵动作表 | `0x596CCC` | 576 × 16 |
| `background_table` | 剧情底图表 | `0x59903C` | 36 × 16 |
| `story_before_root` | 剧情脚本根表（before） | `0x060C74` | 56 × 4 |
| `story_after_root` | 剧情脚本根表（after） | `0x060D54` | 56 × 4 |
| `story_logic_root` | 战场事件逻辑根表 | `0x060E34` | 47 × 4 |
| `story_events_root` | 战场事件根表 | `0x060EF0` | 47 × 4 |
| `mission_index` | 任务索引表 | `0x348DAC` | 48 × 1 |
| `font_segments` | 字形段表 | `0x53D644` | 31 × 8 |

### 1.2 文本表（10 张，2,199 条文本）

| id | 名称 | 指针表基址 | 条数 | 形态 |
|---|---|---|---|---|
| `character_names` | 人物名表 | `0x599280` | 63 | u32 指针表 |
| `training_names` | 技能名表 | `0x5A7060` | 45 | u32 指针表 |
| `jutsu_names` | 忍术名表 | `0x59937C` | 87 | u32 指针表 |
| `ninjutsu_names` | 忍具名表 | `0x599634` | 94 | u32 指针表 |
| `material_names` | 强化素材名表 | `0x5A7E8C` | 18 | u32 指针表 |
| `mission_titles` | 任务标题表 | `0x59AA5C` | 112 | u32 指针表 |
| `mission_descriptions` | 任务说明表 | `0x59D214` | 112 | u32 指针表 |
| `mission_hints` | 任务提示表 | `0x59E920` | 112 | u32 指针表 |
| `dialogue_slots` | 对白槽位表 | `0x461CE8` | 1,524 | u32 指针表 |
| `speaker_names` | 说话人名表（内联） | — | 32 | **内联 12 字节/条**，不是指针表 |

另外单独产出 **`text-index.json`**：全 ROM 文本索引，**16,008 条**。

### 1.3 字形表

`code_to_char` 4,261 条 / `char_to_code` 4,253 条 / 覆盖 26 段 /
8 个重复字符。文本一律经 `tools/text_codec.py` 的 `load_mapping()` +
`decode()`/`encode()` 处理，**不使用 cp932**。

---

## 2. 文件格式与两条不变量

### 2.1 记录格式

```jsonc
{
  "id": 3,
  "rom_offset": 137886,
  "raw": "…base64…",          // 原始字节，原样保留
  "values": { "field_key": … } // 已知字段的解码值
}
```

字段定义在 `structure["fields"]`，每条字段带
`key / offset / size / type / label / desc / group`。

### 2.2 不变量一：字段表精确铺满记录

`tile(entry_size, fields)` 生成字段表：**已知字段 + `hex` 填充字段**，
加起来正好 `entry_size` 字节，没有空洞、没有重叠、没有越界。

> 本轮新增：`tile()` 现在会在字段超出记录长度时**直接抛错**。
> 消息是「字段必须描述【单条】记录，不是整张表」——这正是本轮修掉的 bug
> 的成因。

### 2.3 不变量二：只用字段值就能重建 ROM

`build/content_pack_roundtrip.py` 对全部 5,740 条记录做：
`values → bytes` → 与 `raw` 比 → 再与 ROM 里 `rom_offset` 处的字节比。
**当前 5,740/5,740 全部一致。**

这条正是「未改动的包能逐字节重建原 ROM」的机器证明。

---

## 3. 本轮修掉的缺陷（6 张表的记录模型错误）

**症状**：字段列表按「整张表」展开（`value_0..value_42`、`ptr_0..ptr_55`…），
但记录模型是「一条记录 = 一行」。于是每条记录的 `values` 里塞进了**跨越到
后续记录**的字段，`tile()` 也不报错。

**后果**：

1. `pack.json` 里同一张表的整行数据被复制到每一行（包从 4,183,694 字节
   膨胀到现在的 3,608,394 字节）。
2. 编辑器的 `recordBytes()`（`rom-editor/js/pack.js:87`）把每个字段写进
   `entry_size` 长的缓冲里，**偏移越界的字段会被静默丢弃** ——
   也就是**改了不生效**。
3. `values` 与 `raw` 不自洽，违反不变量二。

**修复**：每条记录只带**属于自己那几字节**的字段。

| 结构 | 旧字段 | 新字段 |
|---|---|---|
| `unit_slot_remap` | `value_0 … value_42`（43 个，跨 86 字节） | `value`（1 个，2 字节） |
| `unit_delta_table` | `delta_0 … delta_15` | `delta`（1 个，2 字节） |
| `object_descriptors` | `ptr_0 … ptr_85` | `ptr`（1 个，4 字节） |
| `story_before_root` / `story_after_root` | `ptr_0 … ptr_55` | `ptr`（1 个，4 字节） |
| `story_logic_root` / `story_events_root` | `ptr_0 … ptr_46` | `ptr`（1 个，4 字节） |

同时把对应的 `primary_columns` 改成新的单字段名。

**复现命令**（修复前会报 351 条问题）：
```powershell
python build\content_pack_roundtrip.py
```

---

## 4. 已知缺口（**明确列出**，不算「导出完整」）

### 4.1 已被证实、但**尚未导出**的表（15 张）

`tools/table_registry.py` 里标成 `verified=True` 的 68 张表中，有 **15 张
不在包里**：

| 表 | ROM 基址 | 说明 |
|---|---|---|
| `sound_id_table` | `0x465B70` | 音频 sound-ID 表，159 × 8 字节 |
| `audio_song_1` | `0x536368` | m4a SongHeader（sound id 1），8 轨 |
| `audio_song_2` | `0x536BC4` | m4a SongHeader（sound id 2），10 轨 |
| `audio_song_8` | `0x538FEC` | m4a SongHeader（sound id 8），9 轨 |
| `audio_song_11` | `0x53AB74` | m4a SongHeader（sound id 11），10 轨 |
| `audio_song_14` | `0x53C3BC` | m4a SongHeader（sound id 14），8 轨 |
| `function_pointer_table` | `0x53D5F0` | 函数指针表，13 槽 u32 |
| `font_width_table` | `0x53E596` | 字宽表，1 字节/条 × 256 |
| `battle_handler_table` | `0x53E698` | 战斗/地图事件处理程序分派表，8 × 256 |
| `sprite_frame_descriptors` | `0x53EE98` | 精灵帧描述符表，10 × 15 |
| `pickup_dispatch` | `0x0815E4` | 原生拾取分派表，7 个处理程序 |
| `data_pointer_table_a` | `0x5A143C` | 数据指针表 A，u32 × 46 |
| `data_pointer_table_b` | `0x5A2034` | 数据指针表 B，u32 × 90 |
| `tile_asset_records` | `0x5A320C` | 图块/精灵资源记录表，68 × 79 |
| `palette_source_table` | `0x5A57C4` | 调色板源表，12 字节/条 |

> 其余 22 条 registry 记录是**已裁决的旧别名 / 已证伪的说法**
> （`legacy_*`、`falsified_sappy_claim`），**不是缺口**。
> 复现：`python build\content_pack_gaps.py`

### 4.2 指针指向的**资源本体**没有导出

包里只有**指针**，没有它们指向的数据：

- `portrait_table`（`0x5A4DEC`）的 64 × 5 组（图像指针 + 调色板指针）
  指向的**压缩头像图像**与**调色板**本体都不在包里。
  （写回能力的现状见 `notes/evidence/portrait-writeback-20261021.md`。）
- `level_blocks` / `background_table` / `sprite_action_table` 指向的
  **LZ77 压缩图块 / tilemap** 不在包里。
- `tile_asset_records` 指向的图块资源本体不在包里。
- `font_segments` 只描述字形段表本身，字形数据在 ROM 的段区，未单独导出。

### 4.3 未解码字段

包里所有 `hex` 填充字段（`raw_XX`）都是**未解码字节**，按原样保留。
本轮没有新增解码。

### 4.4 其它限制

- `background_table` 的 id 14..35 是另一种记录形态（32 字节调色板），
  字段含义与 id 1..7 / 9..13 **不同**，但包里用的是同一套字段 ——
  这些行的已知字段是**错的**（`note` 里已标注，但字段值仍按同一套解）。
- `speaker_names` 的**记录总数未确证**（按 32 条呈现）。
- 包里没有「重新导入 ROM → 包」的写回路径；`--check` 只验证
  「包 == 当前 ROM」，不验证「包 → ROM」的重建（后者由
  `build/content_pack_roundtrip.py` 覆盖，但它是探针，不在仓库里）。

---

## 5. 结论

- ✅ 导出端到端可用：`python tools\export_content_pack.py` 退出码 0。
- ✅ `--check` 通过：包与 ROM 逐字节一致。
- ✅ 强不变量通过：5,740 条记录都能只用字段值重建回 ROM。
- ⚠️ **不能声称「内容已全部导出」**：§4.1 的 15 张已证实表和 §4.2 的
  资源本体都不在包里。
