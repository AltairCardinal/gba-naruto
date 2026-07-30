# 两条 LZ77 图形调色板缺口复核（2026-07-30）

## 结论

`rom-pointer-lz77-graphics-v1` 中仍标为 `palette_binding.kind=unresolved` 的
两条记录已经完成静态链和 91 份 tracked checkpoint 的定向复核。当前证据不足以
把任何候选 palette 提升为真实绑定，因此 catalog 保持不变：

| 图形源 | 静态目标 | 图块范围 | 已证明事实 | 未闭合点 |
|---|---|---:|---|---|
| `0x0812D2F0` | `0x06016400` | OBJ tile 800..841 | 唯一 literal user `0x08071BC2`；18 个 checkpoint 完整驻留该 payload | 没有 checkpoint 的 hardware/shadow OAM 引用该范围 |
| `0x083496F8` | `0x06017580` | OBJ tile 940..943 | 唯一 literal user `0x0808B5E6`；同一初始化器先把 `0x083496B0` 写入 OBJ palette bank 14 | 没有 attr2 证明该图形选择 bank 14 |

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

## 最小运行时闭环

后续只在自然入口出现时执行以下受守卫探针，不重新从标题或序章进行长导航：

1. 从 profile browser 或相关 battle 的最近已验证快照恢复；
2. 每帧先确认目标 VRAM payload 完整，再检查 hardware/shadow OAM 是否引用目标
   tile 范围；
3. 命中时保存新 checkpoint，并记录 attr2 bank、对应 PRAM 32 bytes、ROM 精确
   匹配数和其间 PRAM 覆盖；
4. 只有 bank 唯一、palette bytes 一致且 ROM 来源唯一时才升级绑定；
5. 若完整自然路线仍从未引用目标 tile，则把“加载但未观察使用”作为独立负结论，
   不推断 palette。

本轮只做 ROM 与既有 checkpoint 的离线读取，没有启动 mGBA，也没有生成新的大文件。
