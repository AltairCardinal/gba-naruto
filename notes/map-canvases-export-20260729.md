# 全部战斗地图画布导出（2026-07-29）

## 成果

`tools/export_map_canvases.py` 从基准 ROM 的 47 项地图表
`0x0853D910` 批量生成 `artifacts/map-canvases-v1/`：

- 47 张 primary 完整画布；
- 14 张非空 alternate 候选画布；
- 61 份展开后的 GBA BG u16 tilemap；
- 166 份按解压内容 SHA-256 去重的 graphics、palette、primary/alternate
  layout、metatile 和 collision 原始资源；
- 记录源地址、尺寸、哈希、使用范围和证据边界的 manifest。

成果共 289 个文件、约 2.5 MiB。`manifest.json` SHA-256 为
`12a231a570a1cb9e56bec7e2f87cb6de4ac48d673765b1ba536bbc5b0137e19c`。

## 格式

每个 coarse cell 覆盖 4×2 个 8×8 tile。layout 的每个 little-endian u32
用 low/high u16 指向左、右两个 2×2 metatile；metatile 的四个 little-endian
u16 按 TL/TR/BL/BR 排列。BG entry 使用标准位域：

- bits 0..9：tile index；
- bit 10：水平翻转；
- bit 11：垂直翻转；
- bits 12..15：palette bank。

索引色 PNG 保留 palette bank 语义；透明索引不会被擅自引入。原始布局、展开
tilemap、碰撞网格和像素画布可以分别供地图编辑器读取。

## 独立验证

`tools/verify_map_canvases.py` 不导入 exporter。它独立解析地图表和 LZ77，
对 primary 画布使用既有运行时资源生成链 `reconstruct_map` 交叉验证，对
alternate 独立展开，并检查：

- 基准 ROM 与整张地图表固定哈希；
- 166 份去重资源逐字节等于 ROM 解压内容；
- 61 份 tilemap、PNG 索引像素、RGB palette、尺寸和文件全集；
- map 40 的固定 tilemap/pixel golden digest；
- 对 tilemap 或 PNG 的单字节/像素篡改必须失败。

验证命令：

```sh
python3 -m unittest -q tests.test_export_map_canvases
python3 tools/export_map_canvases.py \
  --root . --output-dir artifacts/map-canvases-v1
python3 tools/verify_map_canvases.py \
  --root . --artifact-dir artifacts/map-canvases-v1
```

本次结果为 47/47 maps、61/61 canvases、`errors=[]`。正式导出耗时约
3.30 秒，最大 RSS 30,638,080 bytes，无 swap。

## 锚点与边界

map 40 是 36×44 tile（288×352 pixel），header file offset
`0x53DE10`。其 primary tilemap SHA-256 为
`adc300b0566b30eb5988d7974e237dd5a4c16847908b2cffaf48bcb4f09015b9`，
索引像素 SHA-256 为
`a4dd82c0d71778e2defc354375cb4819ceea66c5934af48725d6c9dad40cf419`；
tile `(12,16)` 的 BG entry 为 `0x3119`。

视觉抽查覆盖 736×512 的 map 0、544×480 的 map 11 和 map 40。map 0
alternate 呈稀疏遮罩式内容，因此 alternate 只签发为 header 中存在的静态候选层，
不声称它能独立替换 primary。严格运行时资源捕获只证明 map 41 primary 被选择；
其他 primary 是消费者格式支持的静态成果。运行时 alternate 选择、超过单个 BG
宽度时的滚动/分块规则、单位/对象动态占用层仍待后续闭合。本里程碑未运行 mGBA。
