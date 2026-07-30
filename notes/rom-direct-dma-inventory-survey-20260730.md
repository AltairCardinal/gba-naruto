# ROM 直接 DMA 资源盘点（2026-07-30）

## 目的

`rom-direct-cpuset-gpu-inventory-v1` 已闭合 BIOS `CpuSet/CpuFastSet` 的
direct-BL 分母，但明确不覆盖 DMA。为避免按图像外观猜测未压缩资源，本轮从全 ROM
中所有指向 DMA0–DMA3 寄存器块的 Thumb-shaped PC-relative literal user 建立下一
个有限静态分母。

## 固定分母与结果

对基准 ROM 的全部 halfword 对齐位置扫描，只有 literal 解出的 32 位值位于
`0x040000B0..0x040000DF` 才进入分母：

| 项目 | 数量 |
|---|---:|
| DMA 寄存器 literal user | 21 |
| DMA0 | 2 |
| DMA1 | 7 |
| DMA2 | 2 |
| DMA3 | 10 |
| 96-byte 窗口内固定 ROM→GPU 操作 | 0 |
| `not_proven_in_window` | 21 |
| 新 ROM 资源源地址 | 0 |

扫描器从每个 literal user 开始做 96-byte fail-closed 符号执行，只传播固定 literal、
立即数、移位、加减和有限高寄存器 move/add。未知指令会清空 `r0..r7` 和待提交 DMA
字段。它同时支持：

- 32 位 `STR` 一次写入 `CNT_L+CNT_H`；
- 16 位 `STRH` 分别写入 count 与 `CNT_H`，只有两个半字、source、destination
  都固定时才组合 control；
- source 必须在已映射基准 ROM 内，destination 必须完整落在 PRAM、VRAM 或 OAM，
  control 必须证明 enable、非零 count、位宽和源边界。

`STRH` 路径有独立合成测试。测试在修复前因未观察到 split count/control 正确失败，
修复后重建 `0x08000100 → 0x06000000`、control `0x84000010` 的 DMA0 操作，防止
“真实 ROM 当前为零”掩盖解码器假阴性。

## 代表性否定路径

- `0x080611CA` 和 `0x08061386` 均证明 DMA3 把 IWRAM shadow OAM
  `0x0300027C` 的 1024 bytes 提交到 `0x07000000`；目标是 OAM，但 source
  不是 ROM。
- `0x08061628` 证明 DMA3 把 ROM `0x08000104` 的 512 bytes 搬到
  `0x0300007C`；source 是 ROM，但 destination 是 IWRAM，不是 GPU。
- `0x080617AC` 的 destination 为 `0x03000998`，source 未在窗口内证明。
- `0x0809AE46..0x0809B14E` 属于音频 DMA 初始化/控制区域；split `STRH`
  控制写现已被识别，但 source、destination 或 count 不是该 literal-seeded
  窗口内的固定 ROM→GPU 三元组。
- `0x080645C2` 的 DMA0 HBlank/effect 路径含动态 source 和 IO destination；
  fail-closed 数据流不会把它提升为静态 ROM 图像。
- `0x085CCD50`、`0x085CCDA4`、`0x085DFB50`、`0x085DFBA4` 只是满足 Thumb
  形状和 literal 规则的 ROM halfword；本成果不声称它们运行时可达。

## 成果与边界

正式成果位于 `artifacts/rom-direct-dma-gpu-inventory-v1/`：

- `rom-direct-dma-gpu-inventory.json`：21 个 literal user、逐项窗口哈希、观察到的
  control write、拒绝原因和 scope；
- `manifest.json`：精确文件集合、内容哈希、实现哈希及独立验证报告。

独立 verifier 不导入导出器，重新实现 literal 扫描、Thumb 符号传播、word/split
halfword DMA control、GPU 域和 ROM 边界检查，并从基准 ROM 重建全部 JSON 语义。
测试还会在重算 manifest 文件哈希后分别篡改 literal value、scope 和 status，验证
这些变化仍被拒绝。

```sh
python3 tools/export_rom_direct_dma_gpu_inventory.py \
  --root . \
  --output-dir artifacts/rom-direct-dma-gpu-inventory-v1
python3 tools/verify_rom_direct_dma_gpu_inventory.py \
  --root . \
  --artifact-dir artifacts/rom-direct-dma-gpu-inventory-v1
python3 -m unittest -v tests.test_export_rom_direct_dma_gpu_inventory
```

这里的零命中只证明“全 ROM 21 个 Thumb-shaped DMA-register literal user，在各自
向后 96 bytes 的固定传播规则内，没有直接固定 ROM→PRAM/VRAM/OAM 操作”。它不
证明运行时可达性、非 literal DMA 基址、跨函数参数、间接 wrapper、自定义 copy
loop、ROM→RAM→GPU 两段搬运、未压缩图形全量或通用图像回写。下一主线应闭合
分阶段 RAM slot 与已知 GPU consumer 的连接分母，而不是扩大窗口直到得到想要的
结果。
