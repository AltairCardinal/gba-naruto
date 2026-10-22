# Story visual 透明层全量导出证据（2026-07-29）

## 结论

历史名为 `battle-encounters` 的 `0x0854229C` 表已经从“24 条三指针
descriptor 可识别”推进为全量、可重复的图像成果：

- 24/24 条 descriptor 均导出为 256×256 indexed PNG；
- 共有 24 份唯一 4bpp gfx、1 份共享 16 色 palette、24 份唯一 tilemap；
- 每份 tilemap 都精确引用 gfx 的连续 tile 范围，没有越界或未引用 tile；
- 水平翻转和垂直翻转均按 GBA text-BG entry 的 bit 10/11 还原；
- palette index 0 保留为透明色，其他 15 个 BGR555 颜色逐项保留；
- 每条记录的 ROM 指针、压缩流、解压资源、PNG 和关联 descriptor ID
  均写入 manifest。

这些输出是 story slideshow 使用的透明 BG3 文本/标题层，不是完整合成截图。
`config_id` 还会索引 `0x085A320C` 的另一组视觉 descriptor；在那组资源的
图形与布局语义闭合前，不把两层冒充为完整画面。

## ROM、表与 consumer 锚点

- ROM：`rom/base.gba`
- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- descriptor 表文件偏移：`0x54229C`
- descriptor 表 GBA 地址：`0x0854229C`
- 表范围：`24 × 0x10`
- 表 SHA-256：
  `33acbc117fa59c56d7af11728c6519367c9d5db177de75c199ec91c1c59ec289`
- consumer：`0x08087C9C`
- 三路解压：`0x08087E76 / 0x08087E82 / 0x08087E90`

consumer 建立的 BG3 布局为：

| 项目 | 原作值 |
|---|---:|
| character base | `0x0600C000` |
| gfx destination | `0x0600E800` |
| 首个 tile index | `0x140`（320） |
| palette destination | `0x050001E0` |
| palette bank | 15 |
| tilemap destination | `0x06001800` |
| screen block | 3 |
| 画布 | 32×32 tile，即 256×256 |

这里的最终 `BG3CNT=0x030C` 由两步建立：通用 helper `0x08065404` 先写中间值
`0x0300`，剧情 caller 随后在 `0x08087CEA` 覆盖为 `0x030C`，再于
`0x08087EAA` 启用 BG3。后者明确选择 charblock 3、screenblock 3、priority 0，
与 gfx 目标地址和 tile base 精确一致；不能用中间值 `0x0300` 推翻最终布局。

`0x08087DE8..0x08087E00` 先读取当前 descriptor 的 `+0x0C config_id`，
再按 `config_id × 0x44` 索引 `0x085A320C`。因此 manifest 把它记录为
`linked_visual_descriptor_id`，但不猜测尚未闭合的可见名称和 OAM/布局。

## 可重复成果

- 通用 GBA 图像底座：`tools/gba_image_export.py`
- 导出器：`tools/export_story_visual_layers.py`
- 独立验证器：`tools/verify_story_visual_layer_export.py`
- 定向测试：`tests/test_export_story_visual_layers.py`
- 通用底座测试：`tests/test_gba_image_export.py`
- 产物：`artifacts/story-visual-layers-v1/`
- 清单：`artifacts/story-visual-layers-v1/manifest.json`
- 清单 schema：`story-visual-layer-export-v1`

重复执行：

```bash
python3 tools/export_story_visual_layers.py \
  --root . \
  --output-dir artifacts/story-visual-layers-v1
```

导出器不依赖 Butano。它逐条比较 bank 与 ROM 原始 16 字节 descriptor，
严格截取三份单独的 LZ77 记录，验证 gfx/palette/tilemap 的尺寸、tile 连续性、
palette bank 和 flip 位，再生成稳定 indexed PNG。关联的 `0x085A320C`
`79 × 0x44` 表也逐字与 ROM 比较，表 SHA-256 为
`0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73`。

## 验证结果

```text
python3 -m unittest \
  tests.test_gba_image_export \
  tests.test_export_story_visual_layers \
  tests.test_export_menu_portraits \
  tests.test_battle_encounter_identity \
  tests.test_text_and_visual_table_identity

Ran 28 tests in 3.055s
OK
```

额外独立复核由单独工具执行：

```bash
python3 tools/verify_story_visual_layer_export.py \
  --root . \
  --artifact-dir artifacts/story-visual-layers-v1
```

该验证器没有调用新 renderer 或共享 PNG encoder，而是直接从 ROM 重新解压三路
资源、从 consumer literal 推导 tile base，并逐像素解释 1024 个 tilemap entry：

- 24/24 个 PNG 的 65,536 个 palette index 全部与独立重算一致；
- 24/24 个 PLTE 与 ROM BGR555 palette 一致；
- 24/24 个 PNG 透明索引均为 0；
- 24/24 个 PNG SHA-256 与 manifest 一致；
- 24 个 PNG 哈希均唯一；
- 实际产物约 140 KiB；
- 导出耗时 0.87 秒，最大 RSS 24,264,704 字节，40 次 page fault、0 次 swap。

本里程碑只需离线读取 ROM，没有启动 mGBA，不存在导航重放或快照需求。
没有写入 `butano-sequel/`，不会覆盖并行 Butano 重制任务。

## 剩余图像边界

1. `0x5A320C` 的 79 条 battle/effect visual descriptor 是这些 layer 的
   关联视觉来源之一；gfx/palette 字段已有 consumer 线索，完整图形布局仍需闭合。
2. `0x53DF70` 的 4 条 cutscene gfx/palette bundle 尚缺全量 atlas；
   相邻 definition/animation 的最终 OAM 布局仍需解析。
3. `0x53F140` 的 43 条 sprite definition/animation pair 仍需追踪到实际
   gfx/palette 分配链。

后续继续优先选择能一次覆盖整表、能静态复核且不需要重复模拟器导航的任务。
