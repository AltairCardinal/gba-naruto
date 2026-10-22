# Tile-assets descriptor 2 玩家可见闭环（2026-08-09）

## 结论

`sequel/content/tile-assets/bank.json` 的 79×`0x44` 记录确为运行时场景视觉
descriptor。自然 base-ROM 路线选择 presentation ID 3，并把 descriptor ID 2
（`0x085A3294`）交给 initializer `0x080983B8`。只替换 descriptor 2 `+0x14`
layer-A palette pointer，就会把另一条已导出 palette 精确写入同一 PRAM 目标并
改变最终画面，因此该 bank 可提升为 `runtime_verified`。

## 可复用路线

- 父状态：`artifacts/residual-wram-tilemap-runtime-v2/scene-panel-setup.ss9`，
  SHA-256 `6fed9fe8db43646a5a5a53901a5f0edf1c743ba5e682fd842d3fd19b12776000`。
- 输入：仅 `A:5:13`；命中 scene-panel 返回 `0xFF` 和 controller mode 0。
- 固化状态：`artifacts/runtime-checkpoints/scene-visual-controller-mode0-preselector.ss9`，
  SHA-256 `6df712f69dd9cc702a77ba8ee25964d348f39cc0440a6362c7407c5321cd88cd`。
- 从固化状态零输入 73 帧依次命中 selector、presentation call、initializer、
  descriptor select、graphics、palette 和 layout 边界；没有恢复输入。
- 历史状态格式为 `0xB`，需使用 mGBA commit
  `c16c3ff55585e71bee83c95539c2ecde15d728c8`，binary SHA-256
  `ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b`。

## 最小 A/B

- ROM 字段：file `0x5A32A8` / address `0x085A32A8`。
- baseline pointer：`0x0834B228`（bytes `28 b2 34 08`）。
- candidate pointer：`0x08349E74`（bytes `74 9e 34 08`）。
- 实际不同 ROM offsets 只有 `0x5A32A8`、`0x5A32A9`。
- baseline/candidate 均从同一固化状态零输入运行到 frame 100；计划/实际运行
  `2/2`，盲目重试 `0`。

运行时只有 PRAM 相对偏移 `0x1E2..0x1FF` 不同；IO、VRAM、OAM、IWRAM、
EWRAM 均相同。PRAM `0x050001E0` 起的 32 字节分别等于两个 ROM palette 源。
透明色相同，因此首两字节不变。最终 240×160 RGB 画面 38,400 个像素不同，
差异包围盒为全屏。两次 owned-tree 峰值 RSS 为 107.72/107.68 MiB，guard 均
`completed`、`pgid_clean=true`。

## 证据与边界

成果位于 `artifacts/tile-asset-descriptor2-pixel-ab-v1/`。独立 verifier 从
base ROM 重建 candidate、从确定性 raw tar 复算自然路线、两份 savestate 的六域
差异及像素哈希；防重签测试会拒绝篡改后的像素计数。

本结论仅证明 descriptor 2 的 layer-A palette pointer 及其自然 consumer 路线；
不声称其他 78 条记录、其他字段或实体 GBA 已逐项验证。
