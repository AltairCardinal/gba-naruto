# 派生 WRAM tilemap 修改 ROM 像素 A/B（2026-08-01）

## 结论

派生 WRAM tilemap `0x084635D8` 已完成一条受控入口的修改 ROM 最终像素闭环。
构建器复用生产迁移器，把 12×12 源的 `(row=8,column=8)` 从 `0xD80C` 改为
`0xD80B`；基线与候选均迁移到运行时指针 `0x08BC15AC`，两份 16 MiB ROM 的
指针重定向相同，目标解压内容只在 byte 208 有一字节差异。

两次 mGBA 序列运行复用已验收的 `choice-state3.ss9`，使用同一输入
`Down:18:20,A:60:62,A:140:142`。两边均在 frame 150 / cycle
`1198116187` 由 `0x08090DC4` 把 `0x08BC15AC` 加载到 `0x0200A640`：

- staging：`0x0C → 0x0B`，仅 byte 208；
- `+0x02BC` 变换输出：`0xDAC8 → 0xDAC7`，仅 byte 208；
- queue flush 后 VRAM `0x06000A16`：`0xDAC8 → 0xDAC7`；
- 从各自 queue-post 快照零输入续跑一帧后，mGBA 截图恰好差 50 个像素，边界
  `x=88..95,y=64..71`，坐标集合与从 ROM `0x08463688` 图形独立解码得到的
  oracle 完全相同；没有边界外差异。

正式证据位于 `artifacts/residual-wram-tilemap-pixel-ab-v1/`。artifact 不保存
两份共 32 MiB 的实验 ROM，而是保存八项 patch ledger 的 before/after 字节，令
独立 verifier 从 6 MiB 基准 ROM 与扩展区 `0xFF` 自行重建两份完整 16 MiB ROM、
校验其 SHA-256，并解压运行时 `0x08BC15AC`。证据包另固定运行时 audit/guard、
load/load-post 快照、staging、变换输出、VRAM 行、queue-post/replay 快照和两张
下一帧 PNG；大小约 656 KiB。verifier 不导入构建器或导出器，还会从快照直接
检查 load 寄存器、BG1 配置/滚动、charbase tile、palette bank 13 和屏幕坐标。
完整 96 KiB VRAM 对照又证明 load/load-post 为零差异，queue-post 和下一帧都只
在 offset `0x0A16` 有一个字节差异。即使篡改 staging、patch ledger、BG1 scroll
或目标区外 VRAM 后重签 manifest 文件哈希，相应语义负例仍会失败。

## 复现与验证

构建实验 ROM：

```bash
python3 tools/build_residual_wram_tilemap_pixel_ab.py \
  --root . \
  --output build/experiments/active/residual-wram-tilemap-pixel-ab/<run-id>
```

mGBA 运行必须经 `tools/run_guarded.py` 的共享 heavy lock。正式 sequence 运行的
峰值 tree RSS 分别为 `122.8203125 MiB` 和 `123.79296875 MiB`，均为
`completed/0`、非 degraded；两个一帧 replay 也完成。验证正式成果：

```bash
python3 tools/verify_residual_wram_tilemap_pixel_ab_evidence.py \
  --root . \
  --artifact artifacts/residual-wram-tilemap-pixel-ab-v1
python3 -m unittest \
  tests.test_build_residual_wram_tilemap_pixel_ab \
  tests.test_residual_wram_tilemap_pixel_ab_evidence -v
```

## 边界

本成果证明一条代表性派生 WRAM tilemap 编辑可从生产迁移器生成 ROM，并通过
加载、坐标变换、queue、VRAM 到达 mGBA 最终像素。入口快照的上游仍含已记录的
受控状态补丁，因此不签发 natural-entry；也不证明完整演出时序、该 VRAM 区域的
全周期排他 writer、另外六条 WRAM tilemap 都已各做修改像素 A/B，或实体 GBA
采集。Goal 继续保持 active。
