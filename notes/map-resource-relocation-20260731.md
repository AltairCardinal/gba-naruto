# 战斗地图资源全量可变长迁移（2026-07-31）

## 结论

47 张战斗地图的六类静态资源已从受限原位回编推进到可变长迁移：

- 166 份按“资源类型+解压SHA-256”去重的内容；
- 217 个原始物理 LZ77 槽；
- 249 条 map-header 逻辑指针；
- 全 ROM 四字节对齐精确指针扫描的额外未知引用为 0。

新 `map_resource_relocation` 构建类型可迁移 tile graphics、BG palette、
主/备选 layout、metatile definition 和 collision grid。一次编辑默认重定向该内容
的全部 map-header 别名，也可用经 catalog 验证的
`target_header_pointer_offsets` 显式拆分。旧 `map_resource` 原位回编保持兼容。

## 共享图像分配

多个图像迁移器若都从 `sequel-image-assets` 起点分配，会在组合构建中互相覆盖。
`sequel/image-resource-regions.json` 现把父分区无缝划分为：

| 区域 | 所有者 | 范围 |
|---|---|---|
| `tile-assets` | `tile_asset_resources` | `0x800000..0x980000` |
| `map-resources` | `map_resources` | `0x980000..0xA80000` |
| `menu-portraits` | `menu_portrait_resources` | `0xA80000..0xB00000` |
| `regular-bg` | `regular_bg_resources` | `0xB00000..0xB40000` |
| `battle-effects` | `battle_effect_resources` | `0xB40000..0xB50000` |
| `story-visual-layers` | `story_visual_resources` | `0xB50000..0xB71000` |
| `world-map-backgrounds` | `world_map_background_resources` | `0xB71000..0xB90000` |
| `generic-sprite-bundle` | `generic_sprite_resources` | `0xB90000..0xBA0000` |
| `future-image-resources` | `sequel_image_assets` | `0xBA0000..0xC00000` |

`tools/image_resource_regions.py` 验证父分区身份、全部边界、对齐、无重叠和无空洞。
tile-assets 与地图的全量组合测试在同一 `PatchSafetyGate` 中应用 489 个分配补丁和
958 个游戏有效指针补丁，共 1,447 项；没有范围冲突。

## 格式与原子失败

生成任何补丁前，导入器会重新验证：

- 基准 ROM、catalog、区域注册表及全部源指针；
- 47 张地图的 width/height 与 layout/collision 尺寸；
- layout→metatile→tile/palette 的完整跨资源索引；
- graphics 32-byte tile、palette bank、metatile 和 collision 对齐；
- 所有选中 header 指针的 immutable-base 前置条件；
- `map-resources` 区域容量。

任一编辑、别名、索引或容量失败时不返回部分计划。对同内容的别名子集编辑只影响被
选中的地图，其余地图继续读取原物理资源。

## 容量与审计

| 项目 | 数值 |
|---|---:|
| 去重内容解压字节 | 548,704 |
| 217个原物理槽存储字节 | 468,956 |
| 迁移后166份存储字节 | 384,459 |
| 实际占用跨度 | 384,707 |
| 迁移末端 | `0x9DDEC3` |
| 区域剩余 | 663,869 |

正式成果位于 `artifacts/map-resource-relocation-v1/`。独立 verifier 不导入新
importer/exporter；它重新解析 47 个 header 和资源、重做精确指针扫描、验证完整
`RomLayout`及区域注册表、重建166/217/249分母和16 MiB输出，并拒绝重签后的摘要
篡改。

区域注册表更新后的受守卫重签导出峰值进程树RSS为70.5859375 MiB，独立验证峰值
为50.57421875 MiB，均`completed/0`、非降级。本里程碑没有运行mGBA；它不声明
修改后全地图最终像素、动态overlay、camera或碰撞玩法语义已经运行时等价。
