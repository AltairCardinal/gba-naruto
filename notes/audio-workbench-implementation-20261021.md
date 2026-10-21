# 音频域交互重设计的落地记录（2026-10-21）

> 规格与证据见 `notes/audio-ux-redesign-20261021.md`。本文件只记录**落地结果**
> 与落地过程中**新查到 / 更正**的事实。
> 范围：本轮只做 L1（描述符层 + 指针反查 + 派生索引），L3（音效 id → 代码级使用点）不做。

## 1. 交付的文件

| 文件 | 负责什么 |
|---|---|
| `tools/export_content_pack.py` | 导出全部 81 个 m4a 描述符、描述符下拉的选项集、通道 enum、轨道成表、派生统计段 |
| `rom-editor/js/modules/audio.js` | 音频域首页（三张入口卡 + 统计一览）、面板路由 |
| `rom-editor/js/modules/audio-workspace.js` | 音效工作台：音效分派表、乐曲描述符、函数指针表 |
| `rom-editor/css/audio.css` | 本域样式（入口卡栅格、状态徽章、推定标注） |
| `build/verify_audio_workbench.mjs` | 规格 §7 七条验收标准的无头机器检查 |

## 2. 导出器改了什么

* 结构数 **40 → 116**：新增 81 张 `audio_song_*`（80 个真实描述符 + 1 个空哨兵）。
* 记录数 6,752；内容包 4,547,281 字节。
* `sound_id_table` 新增 `id_is_index: true`、`record_labels`（音效 #0…#158）、
  `ptr_relation`（见 §3）。
* 乐曲结构的轨道指针补上 `array="tracks"` / `index` / `item="ptr"` → 渲染成一张 N 行的表。
* `derived` 段新增 `sound_stats`（**没有**动 `pointer_targets`）。
* 描述符**不再硬编码**（原来只有 5 个 `AUDIO_SONG_BASE`）：改成读 sound-ID 表 →
  去重 → 逐个读 SongHeader。

## 3. 内容包里的新契约（主代理接 `fields.js` 时用这个）

### 3.1 结构级 `ptr_relation`（指针型关系，替代字段级 relation）

```json
"ptr_relation": {
  "kind": "pointer_map",
  "field": "descriptor_ptr",
  "options": [
    {
      "value": 138829928,          // 字段里存的值（ROM 地址）
      "label": "空哨兵描述符（没有声音）",
      "structure": "audio_song_empty",   // 目标结构
      "record_id": 0,
      "tracks": 0, "blocks": 0,
      "kind": "empty",             // song | sfx | empty
      "empty": true,
      "sound_ids": [0, 19, 20, "…共 79 个"],
      "shared": 79                 // 被几个音效共用
    }
  ]
}
```

**没有**给 `descriptor_ptr` 挂字段级 `relation`：`fields.js::relationOptions` 的
`kind:"pointer"` 只能挂**一张**目标表，而 81 个描述符分散在 81 张表里；挂上去会让
通用编辑器只剩一个选项（比裸十六进制框更糟）。音频域的下拉因此由
`audio-workspace.js` 自己渲染。

### 3.2 顶层 `derived.sound_stats`

```
sound_id_count / descriptor_count / real_descriptor_count / descriptor_kinds
empty_descriptor / empty_descriptor_offset / empty_sound_ids
channel_histogram / channel_kinds / channel_enum / config_equals_channel
descriptors{ "0x08536368": {structure,label,kind,tracks,blocks,sound_ids} }
function_pointer_slots{ "0": {kind:"sentinel",…}, "1": {kind:"play_entry",sound_id:1,…} }
function_pointer_note
```

## 4. 新查到 / 更正的事实

1. **11 条播放 thunk 的共享例程是 `0x08061C58`，不是 `0x08061C5C`**
   （规格 §1.5 写的是后者，差 4 字节）。
   逐字节复核：表里存的是 **Thumb** 入口（地址低位 1 = Thumb），指令从偶地址开始：

   ```
   0x08061C8C: B500 2001 F7FF FFE2 BC01 4700
                push  movs r0,#1  bl      pop   bx
   ```

   BL 的偏移按 Thumb 规则解码 → 目标 `0x08061C58`（11 条 thunk 全部相同）。
   导出器现在**自己解码**这段字节（`tools/export_content_pack.py::read_play_thunk`），
   不再把地址写死。
2. **通道 × 音效种类的交叉表**（已证）：
   通道 0 = 18 首乐曲 + 79 条空哨兵；通道 1 = 8 条短音效；通道 2 = 50 条短音效；
   通道 3 = 4 首乐曲。`+0x06` 播放配置在 159 行里与 `+0x04` 播放通道**逐行相等**。
3. **L1 落地后 81 个地址全部已解码**，规格 §7 第 5 条里「音效 #3 是未解码描述符」
   的例子不再成立（#3 现在是 `audio_song_3`，10 轨）。
   「未解码描述符 · ROM 0x…」现在只针对**不在导出表里**的地址（作者自填的自定义地址）。
4. **描述符下拉的选项数**：下拉是 81 个已解码描述符（80 真实 + 1 空哨兵），
   规格 §7 第 2 条写的是「80 个有内容描述符 + 1 个自定义项」。
   空哨兵必须可选（作者要能看到「这个音效没有声音」），所以下拉固定 81 项，
   「自定义地址」改成下拉之外的一行十六进制输入框。

## 5. 验收

`node build/verify_audio_workbench.mjs` —— 规格 §7 七条逐条机器检查，全过。
另有仓库自检：`verify_syntax.mjs` / `verify_views.mjs` / `unittest discover -s tests`
/ `build/content_pack_roundtrip.py` / `verify_pack.mjs` 全过。

## 6. 留给主代理

* `rom-editor/index.html` 加一行 `<link rel="stylesheet" href="css/audio.css">`
  （`audio.js` 里有运行时兜底，但正式做法是进 index.html）。
* `rom-editor/js/fields.js`：若希望**通用**编辑器里也出现描述符下拉，需要新增一种
  「指针映射」关系种类，读 `structure.ptr_relation`（§3.1 的字段名与结构）。
* `rom-editor/tools/verify_views.mjs`：把 `build/verify_audio_workbench.mjs` 的断言并进去
  （该目录由别的维护者拥有，本轮没有动）。
* `docs/rom-editor.md` §3 / §7、`docs/sequel-roadmap.md`：本轮没有动（docs 归主代理）。
