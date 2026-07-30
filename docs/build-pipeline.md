# 构建流水线

## 目标

把续作内容文件、ROM 补丁定义和最终开发 ROM 构建串成一个可重复执行的最小流水线。

## 当前入口

- 项目元数据：`sequel/project.json`
- 补丁清单：`sequel/patches/manifest.json`
- 主构建脚本：`tools/build_mod.py`

## 已支持的补丁类型

### `bytes`

直接按偏移写入固定字节。

```json
{
  "id": "my_patch",
  "type": "bytes",
  "offset": 1901,
  "before_hex": "89df95d1",
  "after_hex": "8e8e8cb1"
}
```

### `dialogue`

从高层对白内容文件导入。同长度替换：直接将编码后的文本（含 null 填充）写入 ROM 偏移。

**格式**：`import_dialogue.py` 读取 `bank`（定义 ROM 源位置）和 `content`（定义新文本），生成补丁。

```json
{
  "id": "my_dialogue",
  "type": "dialogue",
  "bank": "sequel/content/text/dialogue-bank.json",
  "content": "sequel/content/text/dialogue-patches.json",
  "entry_id": "group0.main"
}
```

支持变长文本（需在 bank 中配置 `redirect_offset` 指向已验证的空闲 ROM 区域）。

### `pointer_redirect`

更新指针表条目，指向新的文本位置。用于变长对话导入。

```json
{
  "id": "ptr_redirect.group0.main",
  "type": "pointer_redirect",
  "pointer_table_offset": 4594920,
  "expected_pointer_hex": "14944508",
  "new_pointer_hex": "148C6628"
}
```

### `chapter_script`

从语义 command 或受基准指针约束的原脚本范围生成章节 payload，并在独立分区中
四字节对齐分配。resolver 会先验证全部脚本、codec、容量、FF 空间与基准表指针，
再成对发出 `bytes` + `pointer_redirect`；构建失败时不会写出部分 ROM。

```json
{
  "id": "chapter_script_allocator",
  "type": "chapter_script",
  "spec": "sequel/content/story-b/scenario-39-relocation.json",
  "free_space_start": "0x5F8000",
  "free_space_end": "0x600000"
}
```

### `menu_portrait`

把80×80索引色 PNG 原位回编到菜单/剧情立绘的 LZ77 图形槽和128字节
BGR555 调色板。导入器按 `resource_id` 修改共享资源，因此清单会报告受影响的
全部逻辑立绘别名。

```json
{
  "id": "portrait_import",
  "type": "menu_portrait",
  "spec": "sequel/content/menu-portraits/portrait-edits.json"
}
```

规格文件必须使用 `menu-portrait-import-v1`，并为每项编辑提供：

- `resource_id` 和80×80、透明索引0、最多64色的模式 `P` PNG；
- catalog 中的 gfx/palette 指针；
- 原压缩图形和调色板 SHA-256。

构建器只做原位固定长度写回。新 LZ77 数据超过原槽时直接失败，不扩 ROM、不移动
资源，也不改指针；BGR555 未使用的 bit15 逐色继承原 ROM，避免无修改 PNG
产生隐式字节变化；写入前仍经过全局 immutable-base 和补丁冲突门禁。

### `map_resource`

把已导出的地图 graphics、palette、主/备选 layout、metatile 和 collision 原始
资源按内容身份原位回编。规格使用 `map-resource-import-v1`；一次修改会同步全部
map-header 别名，并验证 layout→metatile→tile/palette 跨资源索引。任一索引越界
或任一物理 LZ77 槽容量不足时整项失败，不修改 header 指针。

### `battle_effect_resource`

把18组战斗特效的4bpp graphics 或16色 BGR555 palette 原位回编。规格使用
`battle-effect-resource-import-v1`，并以“资源类型 + 原始解压 SHA-256”标识
34份内容资源。默认同步同内容的全部物理槽；如果相同内容位于不同指针，可显式提供
`target_physical_offsets` 子集分别编辑，真正共用同一指针的逻辑 group 始终联动。
任一目标槽超限时整项失败，不修改`0x0859911C` pair table。

```json
{
  "id": "battle-effect-resource-import",
  "type": "battle_effect_resource",
  "spec": "sequel/content/battle-effect-resources/resource-edits.json"
}
```

### `character_battle_palette`

把角色战斗视觉矩阵引用的16色 BGR555 palette 原位回编。规格使用
`character-battle-palette-import-v1`，以物理 palette 指针和原始32-byte
SHA-256 标识48个槽；同指针的全部 resource/slot 自动联动，内容相同但指针不同的
槽保持独立。输入必须恰好32 bytes，构建器会核对 catalog、descriptor 指针、
resource ID、slot row 和 immutable base，不迁移资源或修改指针。

```json
{
  "id": "character-battle-palette-import",
  "type": "character_battle_palette",
  "spec": "sequel/content/character-battle-palettes/palette-edits.json"
}
```

### `bg_resource`

把 regular BG 表的 graphics、384-byte BGR555 palette 和32×10 u16 tilemap
按内容身份原位回编。规格使用 `bg-resource-import-v1`；31份内容覆盖12个场景的
36个物理 LZ77 槽和36条逻辑引用。默认同步同内容的全部物理槽，也可用 catalog
约束的 `target_physical_offsets` 子集分别编辑。

构建器会按 descriptor 的4bpp/8bpp mode 重新验证修改后的
graphics/palette/tilemap：tile index、4bpp palette bank 和8bpp像素索引均必须
合法。任一目标槽容量不足时整项失败，不修改 `0x0859903C` descriptor 表。

```json
{
  "id": "bg-resource-import",
  "type": "bg_resource",
  "spec": "sequel/content/bg-resources/resource-edits.json"
}
```

### `map`

从地图规格文件生成 ROM 补丁。当 `patch_ready: true` 且包含 `patches` 数组时触发。

```json
{
  "id": "map.episode01.mountain_pass",
  "type": "map",
  "spec": "sequel/content/maps/episode-01-mountain-pass.json"
}
```

**当前状态**：仅在 `patch_ready: true` 时生效，否则静默跳过。地图格式逆向完成后填充 `patches` 数组。

### `battle_config`

从单位/剧情规格生成 ROM 补丁。当 `patch_ready: true` 时触发。

```json
{
  "id": "battle.episode01.slice",
  "type": "battle_config",
  "units": "sequel/content/units/sequel-units.json",
  "story": "sequel/content/story/episode-01.json"
}
```

**当前状态**：同上，战斗配置格式逆向完成后填充 `patches` 数组。

## 当前内容文件

| 文件 | 用途 |
|------|------|
| `sequel/content/text/dialogue-bank.json` | ROM 对话文本源位置定义 |
| `sequel/content/text/dialogue-patches.json` | 新对话内容 |
| `sequel/content/story/episode-01.json` | 第一章剧情骨架 |
| `sequel/content/maps/episode-01-mountain-pass.json` | 地图规格（draft） |
| `sequel/content/units/sequel-units.json` | 角色/敌方单位规格 |

## 已验证补丁

当前开发 ROM 包含以下已验证补丁：

| Entry ID | 替换前 | 替换后 | 策略 |
|----------|--------|--------|------|
| `proof.menu.same_length_00076d` | 過篇 | 試験 | 同长度 |
| `group0.main` | 委渉留夘笹戟嗚妣著畔問潰誼↵米休七机誌噐？ | 木葉村国境に異変あり小隊が調査に向かう。 | 同长度（null 填充） |
| `group1.main` | 繁岔妣文嚶奉誼憤搾↵儡參誼壷壘熟扮坦丁悛？ | 忍刀の残党が附近に潜伏警戒せよ。 | 同长度（null 填充） |
| `group2.main` | 著畔立駒愧丈掘猪誼↵囹汲肘誼奉熟扮坦丁悛？ | 輸送巻物守るべし。敵の狙いは明白だ。 | 同长度（null 填充） |

## 常用命令

```bash
python3 tools/build_mod.py
python3 tools/import_dialogue.py
python3 tools/import_dialogue.py --bank sequel/content/text/dialogue-bank.json --content sequel/content/text/dialogue-patches.json
python3 tools/import_map.py sequel/content/maps/episode-01-mountain-pass.json
python3 tools/import_battle_config.py
python3 tools/import_menu_portraits.py sequel/content/menu-portraits/portrait-edits.json
```

## 当前状态

已完成：

- `bytes` 补丁构建
- `dialogue` 高层导入补丁构建（同长度 + 变长 redirect 框架）
- `pointer_redirect` 补丁类型
- `chapter_script` 语义 codec、独立 allocator 与 payload+pointer 原子计划
- `menu_portrait` 74套菜单/剧情立绘的受守卫原位图形/调色板回编
- `map_resource` 166份地图内容资源的受守卫原位回编
- `battle_effect_resource` 34份战斗特效图形/调色板内容的受守卫原位回编
- `character_battle_palette` 48个角色战斗物理调色板槽的固定长度安全回编
- `bg_resource` 31份 regular BG graphics/palette/tilemap 内容的受守卫原位回编
- `map` / `battle_config` 补丁类型入口（待格式逆向后填充）
- 构建报告生成（`build/naruto-sequel-build-report.json`）

未完成：

- 地图格式逆向 + `import_map.py` patch 生成
- 战斗配置格式逆向 + `import_battle_config.py` patch 生成
- Unicode 到熊组汉化字形的完整反向映射（章节 `RenderText` 当前使用已编码字节）
