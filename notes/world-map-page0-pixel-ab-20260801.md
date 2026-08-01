# 世界地图 page 0 生产迁移自然像素 A/B（2026-08-01）

## 结论

`artifacts/world-map-page0-pixel-ab-v1/` 将世界地图 page 0 从静态导出、运行时
composition 和可变长迁移，推进到修改 ROM 后的自然首次加载与最终单像素 A/B。

两份 16 MiB ROM 均通过 production `world_map_background_relocation` 把 page 0
graphics 从 `0x084414E4` 迁移到 `0x08B71000`，并只重写 descriptor pointer
`0x5A8014`。page 1/2 的六个 descriptor pointer 保持原字节。candidate 只把
32 KiB 8bpp graphics 的 byte `15588`、即 tile 243 local `(4,4)`、画布
`(116,76)` 从 palette index `112` 改为 `137`；tile 243 在 30×20 tilemap 中只
出现一次。

两边独立编码后的 LZ77 均为 31,963 bytes，ROM SHA-256 分别为：

- baseline：`58b2a447b125fdf4ae0099a0b41de9c5ea7e32fa5f2bde600f1c2d867198e6c1`；
- candidate：`a859355a2a370ee46fab7648224a2f3e31497262a52559e6cfa243b8f40a3a8b`。

## 自然预加载与输入

输入使用已持久化 checkpoint：

- `artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-11.ss9`；
- SHA-256 `bf821ecdd9945c123576ff7f26717c4d2018f07e623c36cb83dc2bb0fa569555`；
- script cursor `0x08031FE7`；
- 输入前 `BG0CNT=0x0007`、`BG3CNT=0x0300`，page 0 graphics、palette 和
  30×20 tilemap 均未安装。

baseline/candidate 分别只在 frame 5 按 A、frame 13 松开，frame 80 捕获。
两边均进入世界地图 page 0，`BG0CNT=0x0086`、`BG3CNT=0x030C`。没有自动输入、
恢复输入、脚本游标修改、selector 强制或运行时内存补丁。

## 运行结果

- 完整 EWRAM、IWRAM、IO、PRAM、OAM 均零差异；
- 完整 VRAM 只在 relative `0x7CE4`、即 `0x06007CE4` 有
  `112→137`；
- page 0 palette 的 320 bytes 与静态资源逐字节相等；
- BG0 screenblock 的 20 行、每行前 30 entry 与共享 tilemap 逐字节相等；
- 两边各自的 Mode-0 compositor 输出与 mGBA PNG 逐 RGB 完全一致；
- 最终 PNG 只有 `(116,76)` 一个像素不同：
  `(189,165,107)→(66,33,0)`。

frame 80 的 32 KiB graphics 区并非整段仍等于 loader 输出：两边都有完全相同的
806 个 byte 被后续运行时 writer 覆盖。独立 verifier 对这些 offset 以有序 u32
序列哈希建账，要求两边 offset 集合和运行值完全相同，并确认目标 byte 15588 不在
覆盖集合中。因此本成果只签发目标像素因果链，不把捕获帧误报为“完整 32 KiB
graphics 仍保持首次加载值”。

## 被排除的 tile 1 候选

首轮曾选择 graphics byte 64，即 tile 1 local `(0,0)`，把 index `154→153`。
静态 tilemap 中 tile 1 只出现一次，看似应只改变画布 `(0,0)`。实际自然 A/B 却在
VRAM 产生 13 个差异，并改变 155 个最终像素；重复的边缘像素表明该 tile 在 page 0
加载后又被当作过程式模板或经后续 writer 扩散。该候选不能证明“一个 authored
byte 对应一个最终像素”，已明确拒绝，相关 r1 仅作为临时失败实验清理，不进入
accepted artifact。

## 证据、安全与复现

正式 raw 只保留两边的 32 KiB authored graphics、ss9、PNG、audit、sentinel、
guard、spec 和 build manifest；两份构建 ROM 与 staged ROM 不进入 Git。mGBA 两次
运行都经共享 heavy lock 和 owned-tree 守卫，`completed/0`、非 degraded、无进程或
监听残留，峰值 RSS 为 56.0234375 / 55.77734375 MiB。promotion exporter/verifier
也经同一守卫运行，最终重签导出峰值 93.30859375 MiB；没有重新启动 mGBA。

```bash
python3 tools/export_world_map_page0_pixel_ab_evidence.py \
  --root . \
  --raw-root artifacts/world-map-page0-pixel-ab-v1/raw \
  --output artifacts/world-map-page0-pixel-ab-v1

python3 tools/verify_world_map_page0_pixel_ab_evidence.py \
  --root . \
  --artifact artifacts/world-map-page0-pixel-ab-v1
```

独立 verifier 不导入 builder、exporter 或 production importer。它从基准 ROM 重建
page 0 descriptor、tile/pixel 地址、两份 LZ77 和完整 16 MiB ROM，验证 page 1/2
descriptor 不变、自然 pre-load、六个完整内存域、806 个共同覆盖、palette、
tilemap、renderer、最终像素、audit/guard、文件全集及实现哈希。负测覆盖重签后的
像素语义和 raw savestate 篡改。

## 边界

本成果只签发 page 0 graphics 的一个代表性自然最终像素。它不外推至 page 1/2、
页面切换和解锁时序、标签、选择光标、所有转场、其余 graphics byte 或实体 GBA。
Goal 保持 active。
