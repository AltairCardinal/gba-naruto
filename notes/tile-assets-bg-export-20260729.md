# `tile-assets` BG 图层全量导出证据（2026-07-29）

## 结论

历史名为 `tile-assets` 的 `0x085A320C` 表现已从“79 条 `0x44` descriptor
可识别”推进为可直接使用的全量静态图像成果：

- 79/79 条 descriptor 均逐字绑定到 ROM；
- 4 条全零记录确认为有效 sentinel：`13, 31, 32, 46`；
- A/B/C 各导出 75 个完整逻辑图层，D 导出 11 个，共 236 个 indexed PNG；
- index 0/D 是唯一允许的 map-only 残缺项：保留 tilemap、definition 与哈希，
  不伪造缺失的 gfx/palette 或 PNG；
- 236 个逻辑图层引用 107 份唯一 gfx、107 份唯一 palette 和
  107 份完整 tilemap；加上残缺 D 的独立 tilemap 后为 108 份；
- 按 `(gfx, palette)` 去重生成 108 个无损 tile atlas，确保 tilemap 没有引用的
  graphics tile 也全部被提取；
- 完整 `(gfx, tilemap, palette)` 三元组共 108 种。

产物共有 344 个 PNG 和 1 个 manifest，约 `2.4 MiB`。

## ROM 与表

- ROM：`rom/base.gba`
- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 表文件偏移：`0x5A320C`
- 表 GBA 地址：`0x085A320C`
- 表范围：`79 × 0x44`
- 表 SHA-256：
  `0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73`

每个非 sentinel descriptor 的静态资源字段为：

| 层 | definition | gfx | tilemap | palette | 完整数 |
|---|---:|---:|---:|---:|---:|
| A | consumer 固定 `30×14` | `+0x0C` | `+0x10` | `+0x14` | 75 |
| B | consumer 固定 `32×14` | `+0x18` | `+0x1C` | `+0x20` | 75 |
| C | `+0x24` | `+0x28` | `+0x2C` | `+0x30` | 75 |
| D | `+0x34` | `+0x38` | `+0x3C` | `+0x40` | 11 |

palette 是原始 32 字节、16 色 BGR555，不是 LZ 流。gfx 与 tilemap 是严格
校验边界的 GBA type-`0x10` LZ 记录。所有 gfx 均为完整 4bpp tile，所有源 tilemap
的 palette-bank bits 均为 0。

## 图层布局与边界

- A 的原生图层为 `(x=0,y=0,w=30,h=14)`、screen stride 32；
- B 的原生图层为 `(x=0,y=0,w=32,h=14)`、screen stride 32；
- C/D 的 packed definition 已确定为
  `{x_tile,y_tile,width_tiles,height_tiles}`，consumer 使用 64-tile stride；
- C 的 tile base 来自运行期 `state[0x16] >> 1`；D consumer 在
  `0x080992FA` 依次读取 `state[0x12]`、`state[0x16]` 并相加后截为
  16 位，因此 D 的 tile base 是 `u16(state[0x12] + state[0x16])`；
  A 的 tile base 与 palette bank 来自 consumer 参数，B/C/D 也受运行期
  state 与后续 palette transform 影响；
- PNG 因此保存 ROM 内的相对 tile index 和原始 palette，正确处理 bit 10/11 的
  H/V flip，但不宣称是运行时最终调色或完整画面；
- C/D 可越过 32-tile viewport，导出器保存完整原生图层，不做误导性的
  256×256 截断。

图层 PNG 复原 tilemap 当前引用的像素；atlas 则按 ROM tile 顺序保存全部 gfx，
两者共同构成无损静态资源成果。

## 可重复成果

- 导出器：`tools/export_tile_asset_bg_layers.py`
- 独立验证器：`tools/verify_tile_asset_bg_export.py`
- 共享 indexed/atlas 底座：`tools/gba_image_export.py`
- 测试：`tests/test_export_tile_asset_bg_layers.py`
- 产物：`artifacts/tile-assets-bg-v1/`
- manifest：`artifacts/tile-assets-bg-v1/manifest.json`
- schema：`tile-assets-bg-export-v1`

重复导出：

```bash
python3 tools/export_tile_asset_bg_layers.py \
  --root . \
  --output-dir artifacts/tile-assets-bg-v1
```

独立复核：

```bash
python3 tools/verify_tile_asset_bg_export.py \
  --root . \
  --artifact-dir artifacts/tile-assets-bg-v1
```

验证器不调用导出器、共享 renderer 或 PNG encoder。它直接从 ROM 重新解压，
独立实现 4bpp nibble、tilemap、H/V flip 和 atlas 排列，并逐像素比较：

```text
verified_descriptors: 79
verified_complete_layers: 236
verified_atlases: 108
errors: []
```

定向回归：

```text
python3 -m unittest \
  tests.test_gba_image_export \
  tests.test_export_tile_asset_bg_layers

Ran 15 tests in 16.422s
OK
```

与菜单肖像、剧情视觉层及视觉表身份一起回归：

```text
python3 -m unittest \
  tests.test_gba_image_export \
  tests.test_export_tile_asset_bg_layers \
  tests.test_export_story_visual_layers \
  tests.test_export_menu_portraits \
  tests.test_text_and_visual_table_identity

Ran 35 tests in 19.322s
OK
```

生产导出耗时 3.97 秒，最大 RSS 27,975,680 字节，page fault 和 swap 均为 0。
本里程碑只离线读取 ROM，没有启动 mGBA，也没有写入 `butano-sequel/`。

## 剩余图像边界

1. 这 79 条记录的运行期 scroll、tile base、palette bank、palette transform、
   layer enable 与 blend 时序仍需在对应动画/剧情语义需要时闭合；不影响资源无损提取。
2. `0x53DF70/0x53DF90` 的 4 组 cutscene OBJ gfx、frame definition 与 sequence
   已完成静态审计，下一步可批量导出 4 个 atlas 和 10 个静态 frame。
3. `0x53F140` 的 43 条 sprite definition/animation pair 仍需追踪到实际
   gfx/palette 分配链。
