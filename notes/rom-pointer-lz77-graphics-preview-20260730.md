# ROM 指针可达 LZ77 新图形预览（2026-07-30）

## 结论

`rom-pointer-lz77-inventory-v1` 新增的 31 条记录中有 20 条被静态消费者送入
VRAM graphics；旧计数中的 `0x08349368` 已按静态目标与 payload 结构纠正为
32×20 text-BG tilemap。本轮用 `tools/export_rom_pointer_lz77_graphics.py` 将
20 条建立为有限图形预览分母：

- 12 条图形在同一 loader 的 32-byte 代码窗口内绑定到 raw ROM palette；
- 4 条图形在同一窗口内绑定到 LZ77 palette；
- 2 条图形由 91 份已跟踪 checkpoint 中的 payload、hardware OAM 与 PRAM 状态绑定
  到唯一 ROM palette；
- 18/20 条因此生成 33 张源调色板候选 atlas；
- 其余 2 条生成 2 张明确标记为 `synthetic_index_only` 的灰阶索引 atlas；
- 总计 20 条图形、35 张确定性 indexed PNG，分母内没有未导出的图形记录。

成果位于 `artifacts/rom-pointer-lz77-graphics-v1/`。它包含 35 张 PNG、一个
catalog、一个 608-byte raw palette bundle 和 promotion manifest，共 38 个文件。

## 调色板证据

raw palette 集合共 12 段：

| graphics | raw palette | 关系 |
|---|---|---|
| `0x08348A3C` | `0x08348BE4` | 直接 CpuSet |
| `0x08348F00` | `0x0834941C` | 直接 CpuSet |
| `0x0834943C` | `0x083496B0` | 直接 CpuSet |
| `0x083F21E4` | `0x083F2794` | 直接 CpuSet |
| `0x083F2A18` | `0x083F2CB0` | 直接 CpuSet |
| `0x08405EA4` / `0x08405F10` | `0x08405FF0` | 共享，按路径复制 32 或 256 bytes |
| `0x08457D3C` | `0x08457EA8` | 直接 CpuSet |
| `0x084580C8` | `0x0845830C` | 直接 CpuSet |
| `0x08463688` | `0x084638D4` / `0x084638F4` | 双 palette bank |
| `0x085B6000` | `0x08463FFC` | CpuSet/CpuFastSet，多 PRAM bank |
| `0x085B6880` | `0x083F0AF0` | 跨 WRAM metadata 的同 loader |

其中 `0x08405FF0` 在 `0x0808BFF2` 以 CpuSet `r2=0x80` 复制 128 halfwords，
所以源段按 256 bytes 接纳并输出 8 个 16-color bank 变体；另两条路径只复制其
32-byte 前缀。`0x08463FFC` 在 `0x080706DC` 使用 CpuFastSet `r2=8`，即 8 个
32-bit word、仍为 32 bytes，不能误算成 16 bytes。

另有四条使用 LZ77 palette：

- `0x080B9E94 → 0x080B9F5C`
- `0x083481E0 → 0x08348668`
- `0x083F00C8 → 0x083F0AC8`
- `0x083F08F4 → 0x083F0AC8`

两条静态未绑定图形已由自然 checkpoint 的 hardware OAM 闭合：

- `0x0812C8B0` 在 `0x06016FE0`，覆盖 OBJ tile 895..898；
  `actionable-move-grid.ss9` 有 8 个相交 OAM 观测；
- `0x0812D134` 在 `0x06017060`，覆盖 OBJ tile 899..900；同一 checkpoint
  有 4 个相交 OAM 观测。

两者全部选择 OBJ palette bank 15（PRAM `0x050003E0`）；32-byte palette 哈希为
`dc72a37cfa3893bc9979d1801b80c9e356b04990751d4bf525e2879fa6e52393`，
在 ROM 中只有一个精确来源 `0x08457EA8`。导出器仍扫描全部 91 份已跟踪 `.ss9`；
只要出现不同 palette bytes、不同 bank 或 ROM 中非唯一来源，就拒绝运行时绑定。
catalog 只保存词法序最早的接纳 checkpoint 作为紧凑证据，同时记录扫描量和命中量。

仍无可接纳 palette 的两条图形是：

- `0x0812D2F0`
- `0x083496F8`

它们的灰阶 PNG 只用于看见 4bpp nibble 索引分布，catalog 明确保存合成 palette
哈希和用途，不能当作原游戏颜色成果。

## 验证

```bash
python3 -m unittest -v tests.test_export_rom_pointer_lz77_graphics
python3 tools/export_rom_pointer_lz77_graphics.py \
  --root . \
  --output-dir artifacts/rom-pointer-lz77-graphics-v1
python3 tools/verify_rom_pointer_lz77_graphics.py \
  --root . \
  --artifact-dir artifacts/rom-pointer-lz77-graphics-v1
```

独立 verifier 不导入 exporter 或其他 `tools` 模块，也不保存绑定结论表。
它从 ROM 重新解压 20 条图形和 3 条唯一 LZ palette，从全部 graphics literal user
重新枚举 32-byte 窗口，并以 fail-closed 的 Thumb 数据流跟踪 BL 当时真实
`r0/r1/r2`；未知指令和 BL 后均使 caller-clobbered 寄存器失效。由此独立发现
raw palette 的 CpuSet/CpuFastSet 调用、单位数和 PRAM 目标，再重建 608-byte
bundle。对静态未绑定项，验证器自行严格解析 `.ss9` PNG/`gbAs`、GPU memory 与
hardware OAM，重算 payload 位置、tile 交集、palette bank 和 ROM 唯一来源，再重建
4bpp atlas 和 PNG 全字节。专用测试覆盖确定性、外来目录拒绝、跨 BL 旧 `r0`
假绑定反例，以及 PNG、catalog 语义、runtime palette bank、raw bundle、manifest
重哈希和额外文件篡改拒绝。

## 边界与下一步

这些 PNG 是“source-order 4bpp tile atlas 候选”。两条 runtime 记录只使用 OAM
选择源 palette，没有按 OAM 尺寸、坐标、优先级或其他图层生成最终画面，因此不声称
是最终可见画面。两条未知图形继续保持未决；下一图像主线建立未压缩图形的有限分母。
