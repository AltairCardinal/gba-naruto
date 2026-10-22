# `resource-pointers`（旧基址 `0x08596F0C`）：唯一的引用是死代码（2026-10-22）

> 重定基址后的权威基址（ROM 文件偏移写法，审计的标记按 6 位十六进制核对）：
> **`0x596CCC`**（精灵动作表 `0x08596CCC`）；旧基址 **`0x596F0C`**
> 是它的 `+0x240` 窗口。

## 1. 结论

**`0x08596F0C` 在本 ROM 里没有任何活着的读者。**
它不是一张独立的「资源指针表」，而是**精灵动作表 `0x08596CCC` 的一个窗口**
（`0x08596F0C = 0x08596CCC + 0x240`）。

## 2. 静态证据

**全 ROM 里 `0x08596F0C` 只出现一次** —— 作为字面量池项：

```
file 0x0007B278 (rom 0x0807B278)  →  0x08596F0C
```

装载它的指令只有一条：`0x0807B220: ldr r0, [pc, #0x54]`。

而 `0x0807B220` 在 **`fn 0x0807AE04` 的 8 路 switch 的 case 7 里**：

```
0x0807AE3E: ldr  r3, [sp, #0x18]   ; 第二个参数（arg1）
0x0807AE40: cmp  r3, #7
0x0807AE42: bls  0x0807AE46
0x0807AE44: b    0x0807B05A        ; arg1 > 7 就跳过
0x0807AE46: lsls r0, r3, #2
0x0807AE48: ldr  r1, [pc, #8]       ; 8 项跳转表 0x0807AE58
0x0807AE4C: ldr  r0, [r0]
0x0807AE4E: mov  pc, r0
```

跳转表 `[7] = 0x0807B010`（case 7 的入口），`0x0807B220` 落在它的体内。

**全 ROM 37 个 `fn 0x0807AE04` 的调用点里，只有两个传 `arg1 = 7`**
（`build/probe_resargs.py` 逐个调用点读出 r1 常量）：

```
0x0807C3D6: movs r1, #7 ; bl fn 0x0807AE04      （在 fn 0x0807B8B8 里）
0x0807C4D6: movs r1, #7 ; bl fn 0x0807AE04      （同上）
```

而这两个都在 `fn 0x0807B8B8` 的**第一个循环**里。该循环只有一个入口：

```
0x0807C3B4: movs r1, #2
0x0807C3B6: mov  r8, r1          ; ★ r8 = 2
0x0807C3B8: mov  r2, r8
0x0807C3BA: cmp  r2, #2
0x0807C3C0: cmp  r2, #1
0x0807C3C2: bge  0x0807C3EC      ; → 落穿到循环头 0x0807C3FC
```

循环体（`0x0807C3FC`–`0x0807C4C0`）不改 `r8`，而检查点是：

```
0x0807C4CA: mov  r0, r8
0x0807C4CC: cmp  r0, #1
0x0807C4CE: bne  0x0807C514      ; ★ r8 = 2 ⇒ 永远跳过
0x0807C4D0: ldrb r0, [r6, #1]
0x0807C4D2: movs r1, #7
0x0807C4D4: movs r2, #0x10
0x0807C4D6: bl   fn 0x0807AE04  ; ← arg1 = 7（走不到）
```

**⇒ 两个 `arg1 = 7` 的调用点都是死代码，`case 7` 永远不会被选中，
`0x0807B220` 永远不会执行。**

（`fn 0x0807B8B8` 的另一个 `r8 = 1` 赋值点在 `0x0807BAE2`，
但它跳到的是 `0x0807C096` —— **另一个循环**，进不到上面这个循环。）

## 3. 运行时阴性对照（带正对照）

`build/probe_items2.py --scenes 1..20 --phase 0x0110 --force-item-bit`
（`build/resource-negative.json`）：

| 观察点 | 命中 |
|---|---|
| `SENTINEL level data DMA` | 2 |
| `SENTINEL object list reset` | 2 |
| `story battle: unit scan calls fn 0x080851F8` | 1 |
| `fn 0x080833A8: calls the items reader` | **72** |
| `ITEMS / SKILLS reader fn 0x0806D910` | **72** |
| `fn 0x0807B8B8: calls the resource reader with arg1=7` | **0** |
| `RESOURCE reader fn 0x0807AE04 (table 0x08596F0C)` | **0** |

**同一路线、同一次运行里，items 读者命中 72 次而资源读者 0 次** ——
这既证明路线真的跑起来了（正对照），也证明资源读者确实没被执行（阴性）。

## 4. 对审计的处置

`resource-pointers` 的旧基址 `0x08596F0C` **按 `LEGACY_REBASE` 的既有先例重定基址**
到 **`0x08596CCC`** —— 也就是「有活着的原生读者真正装载的那个基址」
（读者 `0x0806B76C` → `0x08596CCC`，判定点见
`notes/evidence/l2-runtime-evidence-20261021.md`）。

于是它与 `sprite-animations` / `sprite-action-table` **同址**，
共用那份 L2/L3 证据；而「`0x0807B220` 是它的原生读者」这条旧说法
（见 `tools/completion_audit.py` 的 `LEGACY_CORRECTIONS["resource-pointers"]`）
**作废** —— 那条指令在死代码里。

**⇒ `resource-pointers` 的 L2 / L3 缺口闭合（按别名同址 + 死代码裁决）。**
