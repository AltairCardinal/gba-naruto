# 残余 WRAM tilemap 资源归属（2026-07-31）

## 结论

7 条 `WRAM_dynamic / visual_metadata` tilemap 的 BG 控制、graphics 与 palette
归属已经全部静态闭合，未决数为 0。成果位于
`artifacts/residual-wram-tilemap-resource-ownership-v1/`，独立 verifier 不导入
导出器，自行重读基准 ROM、ABI、graphics catalog、graphics relocation 和 palette
relocation，并核对代码窗口、LZ77 内容、VRAM/PRAM 目标及 tile 范围。

| tilemap 源 | BG | graphics | palette bank | 有效 tile |
|---|---|---|---:|---:|
| `0x0834928C` | BG0, charbase 1, screenbase 0 | `0x08348F00`, 68 tiles | 1 | 6–67 |
| `0x083F1C98` | BG1, charbase 3, screenbase 31 | `0x085B6880`, 268 tiles | 8 | 0–267 |
| `0x085B67E0` | BG1, charbase 3, screenbase 31 | `0x085B6880`, 268 tiles | 9 | 0–86 |
| `0x083F2108` | BG2, charbase 3, screenbase 2 | `0x085B6880`, 268 tiles | 10 | 1–16 |
| `0x084634B8` | BG1, charbase 1, screenbase 1 | `0x08463688`, 96 tiles | 12 | 700–754 |
| `0x0846356C` | BG1, charbase 1, screenbase 1 | `0x08463688`, 96 tiles | 13 | 700–775 |
| `0x084635D8` | BG1, charbase 1, screenbase 1 | `0x08463688`, 96 tiles | 13 | 700–795 |

后三条源 tile index 为 0–95，运行时统一加 `0x02BC`。BG1 charbase
`0x06004000 + 0x02BC × 32 = 0x06009780`，与共享 graphics 的实际 VRAM
装载地址精确相等。

## 迁移门禁

`residual_wram_tilemap_relocation` 与
`residual_wram_derived_tilemap_relocation` 现在都要求 authoring spec 固定：

- ownership artifact 路径及 SHA-256；
- 7/7 BG、graphics、palette 完成且 `remaining_unresolved=[]`；
- 每条源的 VRAM 目标、源/有效 tile 范围、tile add 和 palette bank 与迁移 ABI
  一致。

两套正式迁移 artifact 已从实验目录重新生成并经 promotion 门禁替换。独立迁移
verifier 同样直接验证 ownership 固定哈希和对应 3/7、4/7 子集，不把生产 importer
的成功当作证据。

## 边界

本成果证明静态资源归属和自然 caller 链，不证明 queue slot 每次可用、自然 flush、
所有静态 caller 的实际运行可达性、三选项 overlay 的精确业务名称，以及修改后的
最终屏幕像素和跨帧时序等价。本轮无需启动 mGBA，也没有产生新的快照或高内存任务。
