# 残余 WRAM 派生 tilemap ABI 与迁移（2026-07-31）

## 结论

`rom-pointer-lz77-inventory-v1` 中 7 条 `WRAM_dynamic / visual_metadata`
已全部闭合为 tilemap 源，未决从 4 降为 0：

- 既有 3 条是 LZ77 解压后直接进入 status-3 逐行 GPU queue；
- `0x083F2108` 是 `40×10` u16 源，consumer 每行取前 32 项，直写
  `0x06001100`，即 screenblock 2 的 row 4–13；
- `0x084634B8`、`0x0846356C`、`0x084635D8` 都是 `12×12` u16
  tilemap 源。状态机用独立的坐标 keyframe 表选择窗口，读取源 entry 后加
  `0x02BC`，写入 `0x0200A760`，再向 `0x06000806` 提交 `12×12`。

`0x0846356C` 并非“加载后未使用”：`0x08090D56` 解压后，同一次函数调用经
`0x08090D60..0x08090DAC` 落入共享渲染段
`0x08090E82..0x08090F3C`，在 `0x08090EF4` 从 `0x0200A640`
读取。后续阶段才由 `0x084635D8` 覆盖同一缓冲。

综合 ABI 位于：

- `artifacts/residual-wram-visual-metadata-abi-v2/`
- `tools/export_residual_wram_visual_metadata_abi.py`
- `tools/verify_residual_wram_visual_metadata_abi.py`

独立 verifier 从 ROM、有限 inventory、代码窗口和 LZ77 数据重建 7/7
来源、1,489 个 u16 entry、2,978 bytes，`remaining_unresolved=[]`。

## 四条派生源迁移

新迁移类型 `residual_wram_derived_tilemap_relocation` 接受四份固定几何的
little-endian u16 文件：

| ROM 源 | 几何 | palette bank | 可用 tile 范围 | 运行时路径 |
|---|---:|---:|---:|---|
| `0x083F2108` | `40×10` | 10 | 1–16 | 每行裁掉右侧 8 项后 CPU 直写 |
| `0x084634B8` | `12×12` | 12 | 0–54 | 坐标裁剪、`+0x02BC`、queue |
| `0x0846356C` | `12×12` | 13 | 0–75 | 第一阶段坐标裁剪、`+0x02BC`、queue |
| `0x084635D8` | `12×12` | 13 | 0–95 | 第二阶段坐标裁剪、`+0x02BC`、queue |

四条均允许标准 H/V flip；尺寸、palette bank、tile 范围和变换后
10-bit tile index 都是失败关闭约束。

图像区域注册表从 future 区域切出
`0xBC1400..0xBC1C00`，归
`residual_wram_derived_tilemaps` 独占。原样迁移：

- 4 个 allocation、4 个唯一根指针 redirect；
- 压缩存储 597 bytes；
- 含对齐占用 603 bytes，末端 `0xBC165B`；
- 区域剩余 1,445 bytes；
- 四条全 literal LZ77 最坏含对齐为 1,888 bytes，仍余 160 bytes。

迁移审计位于：

- `artifacts/residual-wram-derived-tilemap-relocation-v1/`
- `tools/export_residual_wram_derived_tilemap_relocation_audit.py`
- `tools/verify_residual_wram_derived_tilemap_relocation_audit.py`

独立 verifier 不导入生产 importer/exporter，自行实现 LZ77 解码、编码、区域
连续性、四个根指针扫描和 16 MiB ROM 重建；另独立重建“四条首 entry 同时
切换 H-flip”的 capability fixture，证明成果不只接受原样迁移。

## 验证

- TDD 红阶段分别由缺失 ABI exporter 和缺失 relocation importer 正确失败；
- 新旧 WRAM tilemap、区域注册、patch safety 与构建 wiring 共 48 项测试通过；
- 区域哈希变化涉及的 21 个既有 artifact 已重建，连同两个新增 artifact 共
  23 个 manifest verifier 全部通过；
- 递归核对 241 项 implementation/registry 哈希，失配为 0；
- artifact 刷新峰值 99 MiB，verifier sweep 峰值约 65 MiB，均由同一 heavy
  lock 保护；本里程碑没有启动 mGBA，因此不需要新增快照。

## `0x083F2108` 自然运行时闭环

`artifacts/residual-wram-crop-tilemap-runtime-v1/` 从已验收的
`residual-wram-tilemap-runtime-v2/scene-panel-setup.ss9` 零输入续跑 5 帧：

- frame 3 命中 load `0x0808BC2E`，固定
  `0x083F2108→0x02002880`；紧随其后的首个 consumer `0x0808B79C` 的
  LR=`0x0808BC3B`，与 scene-panel submit 返回点一致。
- consumer 入口保存的 `0x02002880` 运行时 WRAM 800 bytes 与 ROM 解压源逐字节
  一致；同刻 `0x06001100..0x06001380` 尚不等于目标。最终 640 bytes 精确等于
  该 WRAM 每行保留前 32 项、丢弃右侧 8 项后的结果，640/640 bytes 发生变化。
- 专用探针保留 load/consumer/final 三个可复用快照；运行经统一 heavy lock，
  `completed/0`、非 degraded、无残留，峰值 owned-tree RSS 106.78515625 MiB。

独立 verifier 不导入导出器，也不复用其 LZ77；它固定父 runtime v2、综合 ABI、
ownership、audit/done、guard、load/consumer 寄存器、800-byte WRAM 与两份 96 KiB
VRAM，并从运行时 WRAM 重新构造 32×10 裁切结果。重签后篡改 consumer、任一行
边界、裁切宽度或最终 VRAM 均会失败。
四条派生 WRAM tilemap 的自然运行时子分母由 0/4 推进为 **1/4**。

## 边界

本里程碑证明 7/7 有限 WRAM visual-metadata 来源的静态 ABI，并完成后四条的
可变存储迁移，其中 `0x083F2108` 已补齐自然 load、consumer 与最终 VRAM 闭环。后续
`notes/residual-wram-tilemap-resource-ownership-20260731.md` 已闭合对应
BG/graphics/palette 归属并将固定哈希接入本迁移规格；另外三条变换源仍不证明自然
入口、queue 槽与 flush。本成果也不签发精确业务名称、排他 writer 因果，或修改后
最终屏幕的像素和跨帧时序等价。
