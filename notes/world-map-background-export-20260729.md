# 世界地图背景与标签导出（2026-07-29）

## 结论

`0x085A8014` 是三条 `gfx/map/palette` 世界地图背景记录，唯一直接背景消费者
`0x0808EDBC` 按 `u8[0x020311D4 + 0x14]` 选择记录。三张背景均为 8bpp、512 tiles，
经 30×20 tilemap 组成原生 240×160 画布；消费者把 gfx 解压至 `0x06004000`，
把 160 色 palette 复制至 `0x05000000`，并通过 `0x08063604` 把 map 展开到
`0x06000000`，最后设置 BG0CNT=`0x0086`。

紧邻的 `0x085A8038` 不是 OBJ/overlay 资源指针表，而是三条 16-byte 定长编码标签。
同一选择函数以 `index*0x10` 取标签并调用 `0x08066758` 文本 wrapper；每条含四个
双字节字形码、一个 `00` 终止符和七个零填充字节。九个唯一字形均已由
`artifacts/dialogue-font-v2/` 覆盖，本成果只建立标签到已有字形的绑定，并输出组合
mask 预览，不重复建立字体资产库。

## 源表与消费者证据

- 背景表：`0x085A8014..0x085A8037`，3×`0x0C`，SHA-256
  `9ccd6d722b87a8bf910fb45072ad682d89b9cf3432979b163f57283902396f35`。
- 标签表：`0x085A8038..0x085A8067`，3×`0x10`，SHA-256
  `67b4a34289072f9a89b7f79721df851e6f23409d1c23dc4f90ae7f5d6130d052`。
- 背景 loader：`0x0808EDBC..0x0808EE25`，SHA-256
  `e66468161801a8d10f070d8d505efdfd39b966fdcd96c60fc1b6c384c7cecd12`。
- 标签选择及背景调用：`0x0808F284..0x0808F2A1`，SHA-256
  `256b740d579cbf6f61a29c2504f7f4eb414dd9e7fbd1e21955ba520d1cf19b2c`。
- tilemap copier：`0x08063604..0x080636BF`，SHA-256
  `844be072d9572bd9a657357e745977ed9435c647d0ec0e811f66c953c84a1bd6`。
- 文本 wrapper：`0x08066758..0x0806678D`，SHA-256
  `2a90d5fc068dec5c806ec3c973772d726efdaa3a48ac6d2fc64a805f3c40c5ef`。
- 背景 loader literal pool：`0x0808EE28..0x0808EE3F`，SHA-256
  `5fad3d9b96d7d52dd1f3f06892e1184a46209023f887ab25bc352f289322e19f`；
  它把 loader 绑定到背景表、state、VRAM/WRAM、scroll 和 BG0CNT 地址。
- 选择函数关键 literals：`0x0808F2F8..0x0808F2FF`，SHA-256
  `5c1f9eb562810b706dcf6ca68342e8fe10e7a4e9b57dcff81f885245884acc2f`；
  两个值分别为 state `0x020311D4` 和标签表 `0x085A8038`。

loader 本身不做索引上界检查；导出器和 verifier 固定拒绝三条以外的静态记录。

## 三条背景记录

| ID | gfx | map | palette | 标签码 |
|---:|---|---|---|---|
| 0 | `0x084414E4` | `0x084491D8` | `0x084413A4` | `92BB 99DE 9BD6 90EC` |
| 1 | `0x084497BC` | `0x08450298` | `0x0844967C` | `8140 89A5 9BD6 8D99` |
| 2 | `0x0845087C` | `0x08457898` | `0x0845073C` | `8140 965E 9BD6 954B` |

三条压缩 map 指针不同，但解压后的 1,200 bytes 完全一致，SHA-256 均为
`6713f99e017c9e29c80972f338b577ee9fd5e1873cc8051ace13ab32e3803412`，因此 artifact
只保留一份 `shared/tilemap-30x20.bin`。该 map 恰好引用全部 512 tiles，没有 H/V flip，
palette bank bits 均为零；三张 gfx 的像素索引范围均为 1..159，不使用 index 0。

人工检查三张导出 PNG：画布均为完整 240×160 世界地图插画，边框连续、没有 tile
错位或裁切；三组 gfx/palette 显示不同地点。首次静态导出曾沿用字体成果的错误水平
假设；后续消费者审计与 page 0 GPU capture 均证明运行时把两个有序 8×8 half-tile
上下排列，所以字体图集和本成果均按四个 8×16 字形生成 32×16 标签预览。
ID 1/2 的首码 `8140` 为空白字形，与源记录一致。
汉化 ROM 替换了名义 SJIS 字形，
因此在没有更强文本映射证据前不擅自签发自然语言地点名。

## 持久成果与复核

- 产物：`artifacts/world-map-backgrounds-v1/`
- 导出器：`tools/export_world_map_backgrounds.py`
- 独立验证器：`tools/verify_world_map_backgrounds.py`
- 测试：`tests/test_export_world_map_backgrounds.py`
- manifest SHA-256：
  `b9b879841b7605af80e143a9f2f9bbe2e64754d6390b708033f92cc831bd4dd3`

```sh
python3 tools/export_world_map_backgrounds.py \
  --root . \
  --output-dir artifacts/world-map-backgrounds-v1
python3 tools/verify_world_map_backgrounds.py \
  --root . \
  --artifact-dir artifacts/world-map-backgrounds-v1
python3 -m unittest tests.test_export_world_map_backgrounds -v
```

独立 verifier 不依赖导出器或共享图像 helper，而是重新实现 ROM 表校验、LZ77、
8bpp tilemap raster、2bpp 字形展开和 PNG 编码；它同时拒绝缺失、额外或被篡改的文件。
字体依赖还绑定 `dialogue-font-v2` 的 schema、ROM SHA-256 和 manifest SHA-256，
修改其身份元数据或字形来源都会拒绝。
导出全程离线读取 ROM，没有启动 mGBA，也没有写入 `butano-sequel/`。完成时
`memory_pressure -Q` 报告系统可用内存 67%。

## 边界与后续

本成果闭合三条背景表、三条标签表及标签到现有字体的绑定，但没有证明文本 context
最终使用的 BG tile 基址、screenblock、BGR555 palette、屏幕坐标，也没有闭合选择光标、
解锁状态或最终 BG priority/scroll 合成。因此 `runtime_label_palette`、
`runtime_label_screen_position`、`selection_cursor` 和 `final_screen_composition`
在本静态 artifact 中保持未完成。page 0 的这些字段随后已由受守卫 GPU state capture
闭合，证据见 `notes/world-map-runtime-composition-20260729.md`；page 1/2 与选择转换
时序仍需从该快照做最小输入复放，不重新导航主线。
