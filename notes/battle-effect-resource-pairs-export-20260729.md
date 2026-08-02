# 战斗特效资源对全量导出（2026-07-29）

## 结论

原 ROM 的战斗特效静态资源表位于 `0x0859911C`（文件偏移 `0x59911C`），共
19 个 8 字节记录。group 0 是全零哨兵；group 1..18 均为有效的
`graphics_pointer + palette_pointer`：

- 18/18 graphics 均为 GBA LZ77，解压后均按 4bpp tile 对齐；
- 18/18 palette 均为 GBA LZ77，解压后恰为 32 字节/16 色；
- 合计 53,344 字节、1,667 个逻辑 tile；
- 去重后为 17 份 graphics 和 17 份 palette：group 2/3 共享 graphics，
  group 16/17 共享 palette；
- 所有解压二进制和索引色 atlas 已写入
  `artifacts/battle-effect-resource-pairs-v1/`。

资源表 SHA-256 为
`7d9f94e05b975940bd2e17f55681120782cb7b6f07d0ab6245adef7260d24130`；
基准 ROM SHA-256 为
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

## 全表

| Group | Graphics | 解压大小 | Palette | 解压内容哈希前缀 |
|---:|---|---:|---|---|
| 1 | `0x083406F0` | 1,024 B / 32 tiles | `0x083409D0` | `d2bdbe77b17e…` / `baf6d1600521…` |
| 2 | `0x08340AF8` | 9,728 B / 304 tiles | `0x08341FA8` | `eb9589427bab…` / `70c511e326da…` |
| 3 | `0x08340AF8` | 9,728 B / 304 tiles | `0x08342340` | `eb9589427bab…` / `c0e21753834c…` |
| 4 | `0x083426D8` | 2,048 B / 64 tiles | `0x08342898` | `20ba57e9b2ee…` / `4d7cc7492e04…` |
| 5 | `0x08342938` | 3,840 B / 120 tiles | `0x08342DC8` | `6628fdc3365f…` / `c00b7ea1d674…` |
| 6 | `0x0834311C` | 960 B / 30 tiles | `0x0834330C` | `483d47b29f6f…` / `6393b73a92bf…` |
| 7 | `0x08343760` | 1,024 B / 32 tiles | `0x08343A5C` | `4839e96e1374…` / `ade17055c76e…` |
| 8 | `0x08343D88` | 2,304 B / 72 tiles | `0x083442A0` | `42f39b22b077…` / `609fd93993e4…` |
| 9 | `0x08344580` | 1,024 B / 32 tiles | `0x083447AC` | `d0474020d782…` / `04cfd5469052…` |
| 10 | `0x08344E18` | 768 B / 24 tiles | `0x08344F04` | `942c4ee118b7…` / `5c973ed0591a…` |
| 11 | `0x0834529C` | 1,664 B / 52 tiles | `0x08345484` | `0b5d70562a4c…` / `29df643a21db…` |
| 12 | `0x08345568` | 2,176 B / 68 tiles | `0x083459BC` | `e1da042b138c…` / `79c80aa69e19…` |
| 13 | `0x08345AC8` | 1,952 B / 61 tiles | `0x08345CF4` | `64033fc15513…` / `afb5d06c793a…` |
| 14 | `0x08345E64` | 5,120 B / 160 tiles | `0x083466C0` | `878505bd0d11…` / `2a4e16536349…` |
| 15 | `0x08346918` | 3,584 B / 112 tiles | `0x08346F30` | `caf034cec9cf…` / `cb86625b5c5d…` |
| 16 | `0x0834716C` | 2,560 B / 80 tiles | `0x0834747C` | `1ba47dbc5ca5…` / `3856b4b91a67…` |
| 17 | `0x0834754C` | 256 B / 8 tiles | `0x083475B4` | `842b8ef56a35…` / `3856b4b91a67…` |
| 18 | `0x083478F4` | 3,584 B / 112 tiles | `0x083480C8` | `9162bda2e905…` / `d53a7a56bded…` |

group 18 与 type-2 到期及 type-1 zero-event 到期两条 sequence 7 生产路径一致；
后者已有自然修改 ROM 最终像素 A/B。解压 graphics SHA-256 为
`9162bda2e90536bbe5982e94b4d4de9b18111538b548137ca057701d36b7bc55`，
palette SHA-256 为
`d53a7a56bded0b6727002a3fb4ad69454dccee15e8f849ad3a16c3b5639244c1`。

## 可复现性

```sh
python3 tools/export_battle_effect_resource_pairs.py \
  --root . \
  --output-dir artifacts/battle-effect-resource-pairs-v1
python3 tools/verify_battle_effect_resource_pairs.py \
  --root . \
  --artifact-dir artifacts/battle-effect-resource-pairs-v1
python3 -m unittest tests.test_export_battle_effect_resource_pairs -v
```

独立 verifier 不导入 exporter 或其他 `tools.*` 模块，会重新读取基准 ROM、独立
解压 36 个 LZ77 流、核对表/consumer 代码哈希、二进制、PNG 索引像素、RGB palette、
透明色和文件集合；另以 36 个固定解压 golden digest、手写 LZ77/4bpp fixture 及
PNG 篡改测试防止 exporter/verifier 的同构错误共同通过。生产导出验证结果为
18 个资源对、18 张 atlas、`errors=[]`；
导出耗时 0.22 秒，最大 RSS 约 27 MiB，无 swap。

## 边界

本成果闭合的是 `0x0859911C` 表中全部静态 graphics/palette 像素来源，不等于完整
战斗动作表现：

- resource group 到全部 effect sequence、87 个 active action 及 94 个 ninja
  tool 编码的映射已在 `artifacts/battle-effect-sequence-bindings-v1/` 闭合；
- 178 个 child frame、437 个 component 和逐帧 hold 已在
  `artifacts/battle-effect-sprite-animations-v1/` 闭合；最终 screen-space
  position、对战侧镜像、priority 与 affine rasterization 尚未全量闭合；
- palette transform、blend 和音频绑定不在本次范围；
- atlas 只按 ROM tile 顺序展示，不宣称它本身是一帧最终画面。

因此后续可直接复用这些原始像素和 child timeline，不应重新抓取或程序化重画；
构建最终屏幕动画仍需补齐动态 screen-space/OAM 合成证据。
