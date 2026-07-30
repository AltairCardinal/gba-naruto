# 两条 LZ77 图形调色板缺口复核（2026-07-30）

## 结论

`rom-pointer-lz77-graphics-v1` 中仍标为 `palette_binding.kind=unresolved` 的
两条记录已经完成静态链、91 份 tracked checkpoint 定向复核和自然入口精确断点
捕获。当前证据不足以
把任何候选 palette 提升为真实绑定，因此 catalog 保持不变：

| 图形源 | 静态目标 | 图块范围 | 已证明事实 | 未闭合点 |
|---|---|---:|---|---|
| `0x0812D2F0` | `0x06016400` | OBJ tile 800..841 | 自然目标确认路线在 frame 114 命中安装于 `0x08071BD0` 的断点，callback PC=`0x08071BD2`，1,344-byte payload 精确 | 命中当刻及 frame 差不超过 240 的后续采样均无 hardware/shadow OAM 引用 |
| `0x083496F8` | `0x06017580` | OBJ tile 940..943 | 自然人物图鉴路线在 frame 54 命中安装于 `0x0808B5EE` 的断点，callback PC=`0x0808B5F0`，128-byte payload 精确 | 命中当刻及 frame 差不超过 240 的后续采样均无 hardware/shadow OAM 引用 |

邻近加载、同帧 PRAM 驻留和图像外观都不是 palette-bank 选择证据。本轮没有为了把
18/20 改写成 20/20 而把候选关系伪装成事实。

## `0x0812D2F0`

ROM 中图形地址和目标地址均只有一个 32-bit literal：

```text
0x08071BC2  ldr r0,[pc,#0x20]  ; 0x0812D2F0
0x08071BC4  ldr r1,[pc,#0x20]  ; 0x06016400
0x08071BC6  bl  0x0809C0E8    ; LZ77UnCompVram
0x08071BCA  ldr r0,[pc,#0x20]  ; 0x08051465
0x08071BCC  bl  0x08067158     ; UI/config interpreter
```

离线检查 91 份 checkpoint 后，有 18 份在 `0x06016400` 完整保存 1,344-byte
解压 payload；它们覆盖多个 battle 13–15 状态。硬件 OAM `0x07000000` 与 shadow
OAM `0x0300027C` 均没有活动对象引用 tile 800..841，所以不能读取真实 attr2
palette bank。

这 18 份状态的 OBJ palette bank 15 始终一致，且 32-byte 值在 ROM 中唯一对应
`0x08457EA8`；邻近图形 `0x0812C8B0`、`0x0812D134` 的自然 OAM 也确实使用该
bank。但目标图形没有活动 OAM，故这些事实只形成候选，不构成绑定。

## `0x083496F8`

profile browser 初始化器 `0x0808B58C` 的线性加载序列为：

```text
0x0808B5CA..D0  CpuSet(0x083496B0,0x050003C0,0x10)
0x0808B5D4..D8  LZ77UnCompVram(0x08348F00,0x06004000)
0x0808B5DC..E2  CpuSet(0x0834941C,0x05000020,0x10)
0x0808B5E6..EA  LZ77UnCompVram(0x083496F8,0x06017580)
```

第一项精确证明 `0x083496B0` 的 32 bytes 被复制到 OBJ palette bank 14，但它
直接服务的前一个 OBJ 图形是 `0x0834943C → 0x06017100`。目标图形加载前又发生
BG graphics/palette 加载，且当前 checkpoint 中没有 tile 940..943 的活动 OAM。
因此“沿用 bank 14”仍只是强候选。

后续 `0x0808B5F8` 是以零值填充 `0x02002880` 工作区并调用 list builder
`0x0808A6AC`，不是遗漏的 ROM→PRAM palette copy。

## 运行时闭环

`tools/mgba_lz77_palette_probe.lua` 固定两条已验证路线，并拒绝其他 route：

- scenario 41 教程提示关闭后的目标选择：`Up×6, A`，frame 114 命中
  `0x08071BD0`；
- 标题人物图鉴菜单：`Down×2, A×2`，frame 54 命中 `0x0808B5EE`。

两次运行都使用 mGBA 0.11.0 `c16c3ff`，二进制 SHA-256
`4856a8f95a32d0d2d97e0141a4dbe33c162abf27295a8f85ed8fb3c17a42ea72`，
经 `tools/run_guarded.py` 的同一 heavy lock 执行。峰值 owned-tree RSS 分别为
`58.9765625/58.21875 MiB`，guard 均为 `completed/0`、`degraded=false`。
探针在命中点保存 PRAM/VRAM/OAM/shadow OAM、截图和 `.ss9`，再逐帧观察至
frame 差 240（含命中当刻采样）；
两条路线均得到 `oam-not-observed`。

命中时 bank 15 和 bank 14 的 32-byte 值分别唯一对应 ROM
`0x08457EA8`、`0x083496B0`，但没有 attr2 选择，仍只能称候选。
成果、输入快照和原始域位于 `artifacts/lz77-palette-runtime-v1/`，可由
`python3 tools/verify_lz77_palette_runtime.py --root .` 独立复核。

后续不再重复这两条自然路线；只有新的静态 OAM 定义、动画 attr2 生成链或其他自然
状态明确引用目标 tile 时，才重新评估 palette 绑定。
