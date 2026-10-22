# 残余 WRAM tilemap ABI 审计（2026-07-31）

> 后续更新：原文保留的是第一阶段 3/7 结论。其余 4 条已在
> `notes/residual-wram-derived-tilemap-relocation-20260731.md` 闭合；
> 当前综合 ABI 为 `artifacts/residual-wram-visual-metadata-abi-v2/`，
> 7/7 已完成，未决为 0。

## 结论

指针可达 LZ77 inventory 中 7 条 `WRAM_dynamic` visual metadata 已建立有限分母。
其中 3 条不再只依赖 payload 外形，而是由同一局部代码中的解压和 status-3
逐行 GPU 队列调用证明为局部 BG tilemap：

| ROM 源 | 解压 | 几何 | VRAM 矩形 | palette bank | tile |
|---|---:|---:|---|---:|---:|
| `0x0834928C` | 600 B | 15×20 | screenblock 0，row 0 / column 15 | 1 | 6–67 |
| `0x083F1C98` | 576 B | 24×12 | screenblock 31，row 0 / column 8 | 8 | 0–267 |
| `0x085B67E0` | 138 B | 23×3 | screenblock 31，row 17 / column 7 | 9 | 0–86 |

共 657 个 little-endian u16 entry、1,314 bytes。其余
`0x083F2108`、`0x084634B8`、`0x0846356C`、`0x084635D8` 仍保留为未决
WRAM visual metadata，不因同为偶数字节或单 palette bank 就升级为 tilemap。

## ABI 证据

三条路线都先由 `0x0809C0EC` 解压到动态 WRAM，再在同一局部窗口调用
`0x08063604`：

- 队列 status 为 3，保存 source、destination、u16 width 和 row count；
- consumer `0x0806365C` 对每行调用 CpuSet；
- source 每行前进 `width×2` bytes；
- destination 每行固定前进 64 bytes，即 32 个 screen entry。

`0x0834928C` 的目标还可进一步静态算出为
`0x02002880 + (0xB2<<2) = 0x02002B48`。它随后以
`destination=0x0600001E, width=15, rows=20` 入队，因此精确覆盖 screenblock 0
的 columns 15..29、rows 0..19。该 callback 由代码指针注册到 task `+0x28`，
但没有 direct Thumb-BL 外层 caller，不能据此宣称自然路线必达。

## 成果与验证

- exporter：`tools/export_residual_wram_tilemap_abi.py`
- 独立 verifier：`tools/verify_residual_wram_tilemap_abi.py`
- 测试：`tests/test_export_residual_wram_tilemap_abi.py`
- artifact：`artifacts/residual-wram-tilemap-abi-v1/`

测试先因 exporter 缺失失败；首次正式运行又暴露脚本直接启动时项目根不在
`sys.path`，新增 clean-subprocess 测试复现后修复。独立复核随后发现两个证据缺口：
测试没有直接验真仓库内正式 artifact，implementation 哈希也没有覆盖 exporter
直接依赖的两个解码模块。两项都先补失败测试，再把
`tools/extract_tileset.py`、`tools/gba_image_export.py` 纳入实现哈希并重建正式成果。
首次提交又由 artifact-policy 正确拒绝旧的通用 manifest；新增失败测试后，正式成果
改用 `git-artifact-promotion-v1`，记录 accepted 状态、payload 和 verifier 命令。
最终本模块 8 项测试、连同上游 inventory 的 10 项测试全部通过。正式导出和独立验证
均经统一 heavy lock，峰值进程树 RSS 分别为 0.921875 MiB 和 0.98828125 MiB，无降级。
verifier 不导入 exporter，自行重解压 ROM、核对 7 条分母、
三段局部代码、队列 consumer、tilemap 字段、bundle、manifest 和实现哈希，并拒绝
重新签名后的 destination、queue-call 语义篡改和非规范重序列化。

本轮完全离线，没有运行 mGBA，因此不需要新快照，也没有触碰 Butano 工作树。

## 边界与下一步

本成果证明 3/7 条 WRAM metadata 的 tilemap ABI，但不证明：

- status-3 queue 每次一定有空槽或每次自然运行必然 flush；
- BGxCNT、charblock、tile graphics 或 palette 的所有权；
- 四条剩余 WRAM payload 的消费者；
- 自然语言画面身份、最终像素或跨帧时序等价；
- 三条 tilemap 已具备 ROM 迁移或编辑回写能力。

下一步应先把这 3 条作为一个批量迁移域，而不是建立三个重复迁移器；同时继续追踪
其余 4 条的直接消费者，只有 ABI 被代码闭合后才纳入可编辑 schema。
