# `story_config[0]` 的非零运行时读数（2026-10-22）

## 1. 这个字段到底是什么

`story_config` 是剧情状态块 `0x020311D4` 里的一段字节，
`story_config[0]` = **`0x020311ED`** = `state[0x19]`。
它同时是**战斗的 sub-config 字节**：状态机的战斗相位把它抄进
`ctrl[2]`（`0x02026806`）。

## 2. 旧结论为什么一直拿不到非零读数

旧笔记的说法是：

> 「它由调度器 `0x0808F5C8` 写入、`0x0808F5CC` 随即清零，
> 所以任何快照都拍不到它」

**这句话前半段对、后半段错。**
调度器 `fn 0x0808F544` 的那两行逐指令是：

```
0x0808F5A0: ldrb  r1, [r6, #0x18]      ; r1 = state[0x18]  (story_branch)
0x0808F5A2: cmp   r1, #0
0x0808F5A4: beq   0x0808F5C0           ; branch == 0 -> "before" 根表
0x0808F5A6: lsls  r0, r4, #0x10
0x0808F5A8: asrs  r0, r0, #0xe
0x0808F5AA: add   r0, sb               ; "after" 根表 0x08060D54
0x0808F5AC: ldr   r0, [r0]
0x0808F5AE: b     0x0808F5CA            ; ← 跳过 0x0808F5C8！
0x0808F5C0: lsls  r0, r4, #0x10
0x0808F5C2: asrs  r0, r0, #0xe
0x0808F5C4: add   r0, r8               ; "before" 根表 0x08060C74
0x0808F5C6: ldr   r0, [r0]
0x0808F5C8: strb  r1, [r6, #0x19]      ; state[0x19] = r1
0x0808F5CA: movs  r5, #0
0x0808F5CC: strb  r5, [r6, #0x18]      ; state[0x18] = 0
```

**`0x0808F5C8` 只在「before」路径上执行，而那条路径的前提正是
`r1 == 0`**（`beq 0x0808F5C0`）。所以：

* 调度器**永远**把 `story_config[0]` 写成 **0**；
* 「after」路径（`state[0x18] != 0`）**根本不写**这个字段，
  它保留旧值。

⇒ **调度器不是非零值的来源。** 旧结论「快照拍不到」把原因归错了地方。

## 3. 真正的写入者：剧情 VM 的 opcode `0x1F`

全 ROM 扫 `strb [r?, #0x19]`（`state + 0x19`）只有两处命中：
`0x0808F5C8`（上面那个）和

```
0x08097C3C: ldr  r1, [pc, #4]     ; r1 = 0x020311D4
0x08097C3E: ldrb r0, [r7, #1]     ; r0 = 操作数字节 1
0x08097C40: strb r0, [r1, #0x19] ; state[0x19] = 操作数
```

剧情 VM 的 opcode 跳转表在 `0x080977F4`（58 项，**下标 = opcode 编号**，
已由 `0x01`/`0x05`/`0x0B`/`0x0C`/`0x1A`/`0x1B` 逐条核对）：

```
[31] 0x08097870: 0x08097c3c  code      ⇒ opcode 0x1F
```

**opcode `0x1F` 就是「设置战斗 sub-config」。**
`build/probe_opcode_ops.py --op 0x1F` 扫全部剧情脚本：

| 场景 | 根表 | 脚本偏移 | 字节 |
|---|---|---|---|
| 2 | before | 0x0000C69F | `1F 01` |
| 3 | before | 0x0000DB49 | `1F 01` |
| 4 | before | 0x0000FEE0 | `1F 01` |
| 6 | before | 0x00011342 | `1F 01` |
| 7 | before | 0x00012D60 | `1F 01` |

**五个脚本都用操作数 1** ⇒ 游戏自己会往 `story_config[0]` 写 **1**。

## 4. 运行时读数（非零）

`tools/mgba_probe/runtime_state_probe.py`：

```
python tools/mgba_probe/runtime_state_probe.py rom/base.gba \
    --scenes 2 --force-row 1 --presses 140 --trace --json build/runtime-state-proof.json
```

命中记录：

```json
{"scene": 2, "hit": "0x08097C40", "pc": "0x08097C42",
 "label": "VM opcode 0x1F: WRITES state[0x19]",
 "r0": "0x00000001", "state19": "0x01", "answer_row": "0x01"}
```

* `0x08097C40` 被命中，`r0 = 1`（= 操作数字节 1）；
* **紧接着读回内存 `0x020311ED` = `0x01`** ⇒ `story_config[0]` 的非零读数。

### 为什么场景 2 需要 `--force-row 1`

场景 2 的 before 脚本在 `0x0000C3A3` 有一条 **branch2**（opcode `0x06`）：

```
0x080979D6: ldr  r0, [pc, #0xc]   ; r0 = 0x0200A880   ← 菜单作答行
0x080979D8: ldrb r0, [r0]         ; r0 = 选中的行
0x080979DA: lsls r0, r0, #2
0x080979DC: adds r0, #1
0x080979DE: adds r0, r7, r0       ; 跳到分支表项
```

分支表有两项：**行 0 → `0x0000C3AC`，行 1 → `0x0000C536`**，
而 opcode `0x1F`（`0x0000C69F`）在**行 1** 那条路径上。
所以必须把作答行设成 1 —— 探针在菜单收尾点 `0x080960BE` 处
poke `0x0200A880 = 1`（这就是已知的**菜单作答通道**）。

## 5. 同一个字段的另外两个读者

| 读者 | 指令 | 作用 |
|---|---|---|
| VM opcode `0x39` | `0x08097E00: ldrb r0,[r0,#0x19]` | 「若 `state[0x19] == 操作数` 则跳转」 |
| 状态机战斗相位 | `0x0808F942: ldrb r0,[r4,#0x19]` | 抄进 `ctrl[2]`（`0x02026806`）= 战斗 sub-config |

## 6. 判死检验

| 检验 | 期望 | 实际 |
|---|---|---|
| 调度器 `0x0808F5C8` 的写入值 | 旧笔记以为能写非零 | ❌ 恒为 0（`beq` 前提 + 路径跳过）⇒ 旧归因作废 |
| 场景 2 + 作答行 0 | 走 `0x0000C3AC` 分支，不到 `0x1F` | ✅ 未命中 `0x08097C40` |
| 场景 2 + 作答行 1 | 走 `0x0000C536` 分支，命中 `0x1F` | ✅ `r0 = 1`，`0x020311ED` = `0x01` |
| 读回内存 | `state[0x19]` 非零 | ✅ `0x01` |

**⇒ `story_config[0]` 的非零读数缺口（`runtime-state` 的 evidence 类
缺口）闭合。**

## 7. 顺带更正

旧笔记「`0x0808F5C8` 写 `state[0x19]`、`0x0808F5CC` 清 `state[0x18]`」
在**地址层面是对的**（本次逐指令核对无误），但**语义归因错了**：
`0x0808F5C8` 写进去的值**恒为 0**，真正的非零写入者是
VM 的 opcode `0x1F`（`0x08097C40`）。
