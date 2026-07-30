# Tile-assets 全量可变长迁移（2026-07-31）

## 结论

`0x085A320C` 的 79×`0x44` tile-assets descriptor 已从无损静态导出推进到
可变长资源迁移和指针回写。当前闭合分母为：

- 75 个非 sentinel descriptor；
- 236 个完整静态图层和 descriptor 0 的 1 个 partial D tilemap；
- 323 个物理资源：107 graphics、108 tilemap、108 palette；
- 709 条 descriptor 逻辑指针引用；
- 全 ROM 四字节对齐精确指针扫描中，额外未知引用为 0。

`tools/import_tile_asset_resources.py` 以物理源指针和内容 SHA-256 标识资源。
每项编辑先写入父分区内注册的 `tile-assets` 区域，再重定向规格明确选择的
descriptor 别名；未选择的别名继续引用原资源。全部编辑和跨资源约束验证完成后才生成补丁，
因此陈旧 catalog、重复别名、格式错误或分区溢出不会留下部分计划。

## 可编辑格式与失败边界

- graphics：GBA LZ77 存储，解压后是完整 4bpp/8bpp tile；允许在 1024 tile
  硬件上限内改变长度。
- tilemap：GBA LZ77 存储，尺寸必须继续匹配 descriptor 的宽高，tile index
  必须落入同一完整图层的 graphics；高 palette-bank 保留位必须为 0。
- palette：raw BGR555；4bpp 图层为 32 bytes，C 层 8bpp 资源按原契约为
  128 bytes/64 色。
- 8bpp graphics 的每个像素索引必须小于相连图层的 `palette_color_count`；
  不能用硬件可表示的 0..255 掩盖本资源实际只有 64 色的事实。
- descriptor 0 的 D 层只有 tilemap，graphics/palette 生产者仍未知；导入器维持
  partial 契约，不为它伪造资源。

本里程碑不证明修改后资源在所有自然路线中的最终像素等价，也不闭合
window/blend/跨帧时序。

## 容量与独立审计

全量 preservation 迁移把 323 个资源按源指针顺序、四字节对齐写入
`0x800000..0x980000`：

| 项目 | 数值 |
|---|---:|
| 原存储字节 | 635,194 |
| 解压/raw 内容字节 | 1,159,684 |
| 迁移后存储字节 | 633,773 |
| 实际占用跨度 | 634,112 |
| 末端 | `0x89AE00` |
| 区域剩余 | 938,752 |

成果位于 `artifacts/tile-asset-resource-relocation-v1/`。独立 verifier 不导入
importer 或 exporter；它重新解析 ROM 表、重建 323/709 分母、复验完整
`RomLayout`、实现哈希集合、preservation spec、全部资源字节和 16 MiB 输出
SHA-256。它还拒绝重新签名后的逻辑引用删减、实现哈希缺失和重叠分区。

区域注册表更新后的受守卫重签导出峰值进程树RSS为78.43359375 MiB，独立验证
峰值为54.81640625 MiB，均`completed/0`、非降级。本里程碑没有启动mGBA；扩容ROM
的取指、读数及快照恢复能力沿用已验收的
`artifacts/rom-expansion-profile-v1/`，不重复执行冗长导航。

复现：

```bash
python3 tools/export_tile_asset_resource_relocation_audit.py \
  --root . --output artifacts/tile-asset-resource-relocation-v1

python3 tools/verify_tile_asset_resource_relocation_audit.py \
  --root . --artifact artifacts/tile-asset-resource-relocation-v1
```
