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

### `battle_effect_resource_relocation`

把18组战斗特效的34份去重graphics/palette内容确定性重压缩到注册的
`battle-effects`扩展区域，并重写36个经全ROM精确扫描闭合的pair-table指针。
规格使用`battle-effect-resource-relocation-v1`，以资源类型、原内容SHA-256、
物理payload列表和完整指针列表固定来源；可用`target_pointer_offsets`选择
catalog允许的别名子集。所有内容、格式、别名、区域容量和旧指针前置条件均在返回
计划前验证，失败时不产生部分分配。

```json
{
  "id": "battle-effect-resource-relocation",
  "type": "battle_effect_resource_relocation",
  "spec": "sequel/content/battle-effect-resources/relocation-edits.json"
}
```

### `world_map_background_relocation`

把三页世界地图的 graphics、tilemap 和 palette 分配到注册的
`world-map-backgrounds` 扩展区域，并重写 `0x085A8014` 表中的9个精确指针。
规格使用 `world-map-background-relocation-v1`；graphics 支持1–512个完整8bpp
tile，tilemap固定30×20，palette固定160色。构建前会联合验证tile索引、像素色号、
别名子集、旧指针、区域容量和catalog来源，任一失败不产生部分分配。

```json
{
  "id": "world-map-background-relocation",
  "type": "world_map_background_relocation",
  "spec": "sequel/content/world-map-backgrounds/relocation.json"
}
```

### `generic_sprite_bundle_relocation`

把固定 `0..42` 的43个通用 Sprite ID、共享 graphics/palette 及每项 component
list迁移到注册的 `generic-sprite-bundle` 扩展区域。规格使用
`generic-sprite-bundle-relocation-v1`；graphics允许1–97个完整4bpp tile，
palette固定16色，每个ID允许1–2个合法GBA OBJ component。animation 0继续固定
为frame 0保持1 tick后停止。构建前核对两个源catalog、174条精确源引用、43个
ID全集、OBJ tile范围、区域容量和旧指针前置条件。

```json
{
  "id": "generic-sprite-bundle-relocation",
  "type": "generic_sprite_bundle_relocation",
  "spec": "sequel/content/generic-sprites/relocation.json"
}
```

### `cutscene_obj_bundle_relocation`

把固定 `0..3` 的四个 Cutscene OBJ ID、各自 graphics/palette、固定
`2/2/2/4` 个 frame/animation 槽及其 component/timeline 迁移到注册的
`cutscene-obj-bundle` 扩展区域。规格使用
`cutscene-obj-bundle-relocation-v1`；每个 graphics 支持1–256个完整4bpp
tile，palette固定16色，每个frame支持1–2个合法GBA OBJ component，每个
animation槽支持非空变长keyframe序列。构建前核对两张四记录表、4个自然loader
调用、36条精确源引用、固定ID/槽位、tile/OAM范围和区域容量。

```json
{
  "id": "cutscene-obj-bundle-relocation",
  "type": "cutscene_obj_bundle_relocation",
  "spec": "sequel/content/cutscene-obj/relocation.json"
}
```

### `residual_lz77_graphics_relocation`

把十个表驱动图像域之外、仍由对齐 ROM 指针直接加载的20条4bpp LZ77图形迁移到
注册的`residual-lz77-graphics`扩展区域。规格使用
`residual-lz77-graphics-relocation-v1`，必须一次提供完整20项；每项保持原解压
tile数，但可替换全部4bpp内容并使用可变压缩长度。构建前重新验证基准ROM、
inventory/catalog哈希、20项全集、34个全ROM精确根指针、LZ77 round-trip、
旧指针前值和64 KiB区域容量。palette仍从原位置加载，两条未知palette绑定不会被
自动提升。

```json
{
  "id": "residual-lz77-graphics-relocation",
  "type": "residual_lz77_graphics_relocation",
  "spec": "sequel/content/residual-lz77-graphics/relocation.json"
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

### `character_battle_graphics`

把角色战斗视觉矩阵的250套 raw 4bpp graphics 固定长度原位回编。规格使用
`character-battle-graphics-import-v1`；每项以物理 graphics 指针、原始 SHA-256、
resource ID、tile 数和完整 slot rows 标识。输入必须与原资源长度完全相同并按
32-byte tile 对齐。

构建器会从 catalog 和基准 ROM 重建342个逻辑槽、2,190个 component 和60,430个
tile，验证每个资源的 `max(tile_end)==tile_count`，并确认 graphics 与 palette、
component、frame/timeline 表零交叉。只改目标 graphics 字节，不修改 descriptor
或结构指针。

```json
{
  "id": "character-battle-graphics-import",
  "type": "character_battle_graphics",
  "spec": "sequel/content/character-battle-graphics/graphics-edits.json"
}
```

### `character_battle_structure`

按高层字段编辑角色战斗视觉的现有 component 和 animation keyframe。规格使用
`character-battle-structure-import-v1`；component 可改 tile、H/V flip、局部
x/y 和已验证 OBJ 尺寸，keyframe 可改 frame ID 和非零 hold。

构建器会重建250个资源、2,004帧、2,190个 component、784条 animation 和
3,187个 keyframe，验证 tile/frame 边界及完整 slot alias。每项修改只覆盖原
20-byte component 或4-byte keyframe；pointer table、数量、region 长度和
terminator 均不可改变，唯一 `fffb0000` 异常 frame trailer 原样保留。

```json
{
  "id": "character-battle-structure-import",
  "type": "character_battle_structure",
  "spec": "sequel/content/character-battle-structures/structure-edits.json"
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
- `battle_effect_resource_relocation` 34份战斗特效内容及36条指针的可变长迁移
- `world_map_background_relocation` 三页世界地图的7份内容及9条指针的可变长迁移
- `generic_sprite_bundle_relocation` 43个固定通用Sprite ID、共享像素/调色板
  及component list的可变长迁移
- `cutscene_obj_bundle_relocation` 4个固定Cutscene OBJ ID、10个frame/component
  与10条可变timeline的可变长迁移
- `residual_lz77_graphics_relocation` 20条残余4bpp LZ77图形及34个根指针的
  固定解压尺寸、可变压缩长度迁移
- `character_battle_palette` 48个角色战斗物理调色板槽的固定长度安全回编
- `bg_resource` 31份 regular BG graphics/palette/tilemap 内容的受守卫原位回编
- `character_battle_graphics` 250套角色战斗 raw 4bpp 图形的固定长度安全回编
- `character_battle_structure` 角色 component/keyframe 的同布局高层语义回编
- `map` / `battle_config` 补丁类型入口（待格式逆向后填充）
- 构建报告生成（`build/naruto-sequel-build-report.json`）

未完成：

- 地图格式逆向 + `import_map.py` patch 生成
- 战斗配置格式逆向 + `import_battle_config.py` patch 生成
- Unicode 到熊组汉化字形的完整反向映射（章节 `RenderText` 当前使用已编码字节）
