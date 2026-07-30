# ROM 直接 CpuSet/CpuFastSet 资源盘点（2026-07-30）

## 目的

`rom-pointer-lz77-inventory-v1` 已明确不覆盖未压缩图形和 raw palette。下一静态
分母不按字节外观猜测资源，而从 ROM 中对 BIOS copy wrapper 的直接调用及调用时
参数出发。

## 只读初筛

对基准 ROM 的全部 halfword 位置解码 Thumb BL，共得到：

| wrapper | 直接调用 |
|---|---:|
| `CpuFastSet` `0x0809C0DC` | 20 |
| `CpuSet` `0x0809C0E0` | 126 |
| 合计 | 146 |

再从所有加载 mapped-ROM 常量的 literal user 开始，在 32-byte 窗口内复用现有
fail-closed 参数数据流；只有 BL 时 `r0` 为固定 ROM 源、`r1` 为固定 GPU 地址、
`r2` 为固定非零值才接纳。去重后得到 23 个固定 ROM→GPU 操作：

- 全部 23 个目标均为 PRAM；
- 没有直接常量 ROM→VRAM graphics/tilemap；
- 共 15 个唯一 ROM 源；
- `rom-pointer-lz77-graphics-v1` 已覆盖 20 个操作、12 个源；
- 新增三个 32-byte 源：`0x083F1E60 → 0x05000120`、
  `0x083F1F08 → 0x05000140`、`0x08406010 → 0x05000200`。

`0x08405FF0` 的 256-byte copy 与真实 LZ77 源 `0x084060A8` 有区间重叠；后者已由
`scene-visual-packs-v1` 绑定。新目录必须按操作记录这项重叠，但不得把重叠字节再次
打包成新的纯 raw 资源。32-byte copy 路径不与该 LZ77 区间重叠。

低成本 MiniMax 初筛曾把 203 条“无对齐指针的 LZ77 语法候选”误写为未压缩图形；
该结论与 LZ77 parser 证据冲突，已拒绝，不进入设计。

## 下一有限分母

建立 `rom-direct-cpuset-gpu-inventory-v1`：

1. 固定审计输入是全 ROM 146 个 direct BL；
2. 接纳条件是 32-byte 窗口内 fail-closed 证明固定 ROM→PRAM/VRAM 与固定 control；
3. 每个调用记录 CpuSet 位宽/fill/count 或 CpuFastSet word count，并验证源/目标区间；
4. 与严格 LZ77 compressed span 的交集单独标记，不重复进入 raw bundle；
5. 与现有 graphics catalog 的 20 个操作按 callsite/source/destination/size 精确绑定；
6. 三个新增 palette 源无损打包，并由独立 verifier 从 ROM 重做 BL、参数、交集、
   上游绑定与 bundle；
7. 123 个未能在该窗口证明常量 GPU copy 的直接调用保留为明确 excluded 分母。

该成果只能证明“静态参数可证明的直接 BIOS copy”。间接 BLX、wrapper、动态表源、
跨基本块/跨函数数据流、DMA、ROM→WRAM→VRAM 两段搬运和自定义 copy loop 均有意
留到后续分母。由于本轮没有发现直接常量 ROM→VRAM，未压缩 tiles 主线下一步应优先
枚举表驱动源和自定义搬运消费者。
