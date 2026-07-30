# ROM 指针可达 LZ77 新图形预览（2026-07-30）

## 结论

`rom-pointer-lz77-inventory-v1` 新增的 31 条记录中有 21 条被静态消费者送入
VRAM。本轮用 `tools/export_rom_pointer_lz77_graphics.py` 将这 21 条建立为有限
图形预览分母：

- 12 条图形在同一 loader 的 32-byte 代码窗口内绑定到 raw ROM palette；
- 4 条图形在同一窗口内绑定到 LZ77 palette；
- 16/21 条因此生成 31 张源调色板候选 atlas；
- 其余 5 条生成 5 张明确标记为 `synthetic_index_only` 的灰阶索引 atlas；
- 总计 21 条图形、36 张确定性 indexed PNG，分母内没有未导出的图形记录。

成果位于 `artifacts/rom-pointer-lz77-graphics-v1/`。它包含 36 张 PNG、一个
catalog、一个 608-byte raw palette bundle 和 promotion manifest，共 39 个文件、
约 204 KiB。

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

五条尚无 PRAM palette 静态绑定：

- `0x0812C8B0`
- `0x0812D134`
- `0x0812D2F0`
- `0x08349368`
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

独立 verifier 不导入 exporter 或其他 `tools` 模块，也不保存 12/4/5 的绑定结论表。
它从 ROM 重新解压 21 条图形和 3 条唯一 LZ palette，从全部 graphics literal user
重新枚举 32-byte 窗口，并以 fail-closed 的 Thumb 数据流跟踪 BL 当时真实
`r0/r1/r2`；未知指令和 BL 后均使 caller-clobbered 寄存器失效。由此独立发现
raw palette 的 CpuSet/CpuFastSet 调用、单位数和 PRAM 目标，再重建 608-byte
bundle、4bpp atlas 和 PNG 全字节。专用测试覆盖确定性、外来目录拒绝、跨 BL
旧 `r0` 假绑定反例，以及 PNG、catalog 语义、raw bundle、manifest 重哈希和额外
文件篡改拒绝；人工抽查了彩色、multi-bank 与 index-only 三类预览。

## 边界与下一步

这些 PNG 是“source-order 4bpp tile atlas 候选”，没有 tilemap、OAM、palette
bank 选择、优先级或运行时组合，因此不声称是最终可见画面。下一步优先沿五条
palette 未知图形的 caller 和 PRAM 状态继续闭合颜色来源；随后再建立未压缩图形的
有限分母。
