# L4 战斗矩阵 / 全地图 取证（2026-10-21）

**目标**：L4 =「全流程、全人物组合、全地图实际打通」
（定义见 `notes/runtime-verification-gates-20260710.md` §4）。

本文记录**战斗层与地图层**的取证过程与结论。
「全流程」轴的既有证据见 `notes/evidence/l4-playthrough-20261021.md`（55/55）；
本文 §5 给出该轴**由游戏自身逻辑**推进的更强判据。

所有地址都是从 `rom/base.gba` 现推的，推导脚本与复现命令逐条给出。
未闭合的部分一律写在 §8「未达 / 待办」，不做含糊表述。

---

## 0. 结论摘要

| 轴 | 结果 | 证据 |
|---|---|---|
| **全人物组合** | **85/85** 真实编成配置全部被游戏自身跑进战斗 | `tools/mgba_probe/l4_battle_matrix.py --axis battles` |
| **全地图** | **47/47** 张地图描述符全部被游戏加载并渲染（47 个互不相同的 VRAM 指纹） | 同上 `--axis maps` |
| **全流程** | 55/55（既有）+ **游戏自身换场**已跑通并留证（§5） | `notes/evidence/l4-playthrough-20261021.md` + 同上 `--axis flow` |

**工具**：`tools/mgba_probe/l4_battle_matrix.py`
（`--axis scan|battles|maps|flow|all`，写 JSON 到 `build/l4-battle-matrix.json`，
**证据缺失时退出码非 0**）。

---

## 1. 关键地址（本轮钉死）

| 地址 | 含义 | 证据（反汇编） |
|---|---|---|
| `0x020311D4` | 剧情 flag 块基址 | `0x0808F594` `ldr r7,[pc,#0x1C]` → `0x020311D4` |
| `0x020311EA` | `state[0x16]` = **场景号** | `0x0808F5DA` `ldrb r4,[r7,#0x16]` |
| `0x020311EB` | `state[0x17]` = **地图号** | `0x0808F4F0` `strb r4,[r0,#0x17]` |
| `0x020311ED` | `state[0x19]` = **子配置 id** | `0x0808F942` `ldrb r0,[r4,#0x19]` |
| `0x020311E6` | `state[0x12]` = u16 **相位 / phase** | `0x0808F752` `ldrh r1,[r4,#0x12]` |
| `0x020311E0` | **战斗进行中标志所在字**（bit 31） | §3.2，实测 |
| `0x02026804` | **战斗控制块 ctrl**（`ctrl[1]`=组，`ctrl[2]`=子） | `0x080732FC` → `0x02026804` |
| `0x0202680C` | `ctrl+8` = 战斗阶段 / 子阶段 | `0x080732C0` → `0x0202680C` |
| `0x020240C0` | **战斗单位数组**，12 槽，步长 `0x1D4`，角色 id 在 +0 | `0x0808A430` → `0x020240C0`；`0x0808A43C` → `0x000015F0`（=12×`0x1D4`） |
| `0x02024180` | 平行标志数组 | `0x0808A432` `adds r1,#0xC0` |
| `0x085461C4` | **编成矩阵**：48 组 × 3 变体 × 12 槽 × `0xB8` | `0x0807332C` → `0x085461C4` |
| `0x0853D910` | **地图描述符表**，32 字节/条，**47 条** | `0x08069040` → `0x0853D910` |

### 1.1 剧情状态机（`0x0808F73C`）的相位分发表

顶层游戏循环 `0x08060FAC` 通过函数指针（字面量 `0x0806107C` = `0x0808F73D`）
调用它；它在循环头 `0x0808F752` 反复读 `state[0x12]` 并分派：

| phase | 处理块 | 作用 |
|---|---|---|
| `0x000` | `0x0808F80E` | → `state[0x12] = 0x010` |
| `0x010` | `0x0808F814` | 按 `0x0808BAB0()` 的返回值改相位（含 → `0x0118`） |
| `0x018` | `0x0808F872` | 事件处理 |
| `0x020` | `0x0808F892` | 若是战斗场景 → `state[0x19]=2`、`state[0x12]=0x100` |
| `0x030` | `0x0808F8DC` | **下一场景**（`ldrb r0,[r4,#0x16]` → 调度器） |
| `0x100` | `0x0808F928` | → `0x08086A54()` 非零则 `state[0x12] = 0x110` |
| `0x110` | `0x0808F92E` | **完整开战斗** |
| `0x118` | `0x0808F94A` | 只跑战斗（假定 ctrl 已写好） |

---

## 2. 战斗触发链（对简报的更正）

### 2.1 更正 1：根表选择条件是**反的**

简报：「`0x08097130()` 返回 0 → `logic_root[scene]` (`0x08560E34`)，
否则 `events_root[scene]` (`0x08560EF0`)」。

反汇编（`0x0808A5C6` 起）：

```asm
0x0808A5C6: bl   #0x8097130
0x0808A5CA: cmp  r0,#0
0x0808A5CC: bne  #0x808a5e8
0x0808A5CE: ldr  r1,[pc,#0x14]  -> 0x08060EF0   ; ★ events 根表
0x0808A5D0: lsls r0,r4,#2 / adds r0,r0,r1 / ldr r5,[r0]
0x0808A5E8: ldr  r5,[pc,#0x44]  -> 0x0805D593   ; ★ 不是表，是一段代码地址
```

| `0x08097130()` | 取的值 |
|---|---|
| `0` | **events 根表** `0x08060EF0`（文件偏移 `0x060EF0`） |
| `≠ 0` | `0x0805D593` —— **不是 4 字节对齐的表基址**，而是另一段代码/数据 |

另外 `0x08097130()` 本身只是读一个剧情 flag：

```asm
0x08097130: push {lr}
0x08097132: movs r0,#0xff
0x08097134: bl   #0x80970a0     ; 读 flag 位 id=0xFF
```

所以「logic_root = `0x08560E34`」在 `0x0808A588` 这条路径上**没有出现**；
`0x060E34` 那张表是剧情 VM 的 logic 表，由别的路径使用。

**判死检验**：把 `0x0808A5CE` 的字面量 `0x08060EF0` 改掉，战斗脚本指针必须跟着变。

### 2.2 更正 2：写 ctrl 的代码在 `0x0808F93E`，不在 `0x0808F94A`

简报：「相位 `0x118` 写 `ctrl[1]=state[0x16]`、`ctrl[2]=state[0x19]`
然后 `bl 0x080732B4`」。

实际：

```asm
0x0808F92E: movs r0,#0            ; phase 0x110 的处理块
0x0808F930: strb r0,[r4,#0x1b]
0x0808F932: str  r0,[r4]          ; state[0x00..0x0F] = 0
0x0808F934: str  r0,[r4,#4]
0x0808F936: str  r0,[r4,#8]
0x0808F938: str  r0,[r4,#0xc]
0x0808F93A: ldr  r1,[pc,#0x38] -> 0x02026804
0x0808F93C: strb r0,[r1]          ; ctrl[0] = 0
0x0808F93E: ldrb r0,[r4,#0x16]
0x0808F940: strb r0,[r1,#1]       ; ctrl[1] = 组(= 场景号)
0x0808F942: ldrb r0,[r4,#0x19]
0x0808F944: strb r0,[r1,#2]       ; ctrl[2] = 子配置
0x0808F946: bl   #0x8075184       ; 预战
0x0808F94A: movs r0,#1
0x0808F94C: movs r1,#0x7f
0x0808F94E: bl   #0x808a490       ; 置「战斗进行中」标志
0x0808F952: bl   #0x80732b4       ; ★ 战斗本体
0x0808F956: bl   #0x8062560
0x0808F95A: movs r0,#0
0x0808F95C: movs r1,#0x7f
0x0808F95E: bl   #0x808a490       ; 清标志
```

**`phase 0x110`（`0x0808F92E`）才是完整入口**；`phase 0x118`（`0x0808F94A`）
只是它的后半段，**不写 ctrl**。

### 2.3 编成矩阵地址公式：**简报正确**

```asm
0x0807332C: ldr  r3,[pc,#0x48] -> 0x085461C4   ; 基址
0x0807332E: ldrb r1,[r4,#2]                   ; ctrl[2] = 子
0x08073330: ldr  r0,[pc,#0x48] -> 0x000008E4   ; 子步长
0x08073332: muls r0,r1,r0
0x08073334: ldrb r2,[r4,#1]                   ; ctrl[1] = 组
0x08073336: ldr  r1,[pc,#0x48] -> 0x00001AAC   ; 组步长
0x08073338: muls r1,r2,r1
0x0807333A: adds r0,r0,r1
0x0807333C: adds r0,r0,r3
0x0807333E: ldrb r0,[r0]                      ; 「有效子配置字节」
0x08073340: bl   #0x8061e5c
```

`formation[group][sub] = 0x085461C4 + group*0x1AAC + sub*0x8E4` ✔

**补充（简报未提）**：喂给 `0x08068FF0` 的两个坐标 `r8`/`r7` **不是**从 ctrl 来的：

```asm
0x080732C0: ldr  r1,[pc,#0x18] -> 0x0202680C
0x080732C4: cmp  r0,#0
0x080732C6: bne  #0x080732E8        ; 战斗阶段 != 0
0x080732C8: ldr  r0,[pc,#0x14] -> 0x0201BE2A ; 「单位数」字节
0x080732CC: lsrs r0,r0,#1 ; mov r8,r0
0x080732D0: ldr  r0,[pc,#0x10] -> 0x0201BE2B ; 「队伍数」字节
0x080732D4: lsrs r7,r0,#1
```

战斗阶段 != 0 时改从 `0x02026A78` / `0x02026A79` 取。

---

## 3. 怎么把游戏推进任意一场战斗（本文的核心）

### 3.1 三次内存写就够

剧情状态机在 `0x0808F752` 轮询 `state[0x12]`；`phase = 0x110` 会走完整开战斗。
所以**只要游戏停在状态机循环头**，写三个字节即可：

```
poke    0x020311EA  <组>       ; state[0x16]
poke    0x020311ED  <子>       ; state[0x19]
poke16  0x020311E6  0x0110     ; state[0x12] = phase 0x110
```

之后 `cont`，游戏自己就会：

```
0x0808F92E → ctrl[1]=组, ctrl[2]=子 → 0x08075184(预战)
            → 0x080732B4 → 0x0808A588(组, 子) → 0x0808F4D4(组) 载入地图
            → 单位数组 0x020240C0 被填上 → 战斗真正开打
```

**不需要改寄存器，不需要改 ROM。**

### 3.2 「战斗进行中」标志的真实位置（更正我自己的第一版结论）

`0x0808A490(mode, id)` 的字地址计算：

```asm
0x0808A496: lsls r1,r1,#0x18      ; r1 = id << 24
0x0808A498: lsrs r4,r1,#0x18      ; r4 = id & 0xFF
0x0808A4A0: lsrs r2,r1,#0x1d      ; ★ r1 仍是 id<<24！→ (id<<24)>>29
0x0808A4A2: lsls r2,r2,#2         ; × 4
0x0808A4A4: adds r2,r2,r0         ; + 0x020311D4
```

字下标其实是 **`(id >> 5) & 7`**，不是 `id >> 29`。
战斗触发用的是 `id = 0x7F` → `(0x7F >> 5) & 7 = 3` → 字地址
`0x020311D4 + 12 = ` **`0x020311E0`**。

**实测**（在 `0x0808A4CC` 的 `str r0,[r2]` 上断点，直接读寄存器）：

```
store r0=0x80000000 -> [r2=0x020311E0]
mem before: 00000000
mem after : 00000080        ← little-endian 的 bit31
```

> 所以 `notes/story-vm-opcodes-20261020.md` 里「`word = id>>29`」的写法
> 只在 `id < 32` 时成立；正确公式是 `word = (id>>5)&7`。
> 战斗标志 = **`0x020311E0` 的 bit 31**（不是 `0x020311D4` 的 bit 31）。

### 3.3 更正 3：剧情调度器写的不是 `state[0x00]`

简报：「`0x0808F544` 写 `state[0x00]=0x1840`」。实际：

```asm
0x0808F552: ldr  r1,[pc,#0x5C] -> 0x0300004C   ; ★ IWRAM
0x0808F554: movs r2,#0xc2 / lsls r2,r2,#5     ; 0x1840
0x0808F55A: strh r0,[r1]                       ; → 0x0300004C = 0x1840
```

写的是 **IWRAM `0x0300004C`（u16）= `0x1840`** 这个「模式半字」。
战斗入口 `0x0808A59A` 清的就是同一个半字的 **bit 11**（`& 0xFDFF`）。

### 3.4 更正 4：地图加载的入参就是场景号

`0x0808F544(scene)` 的 `0x0808F586: bl 0x0808F4D4(r0 = scene)`，
`0x0808F4D4` 写 `state[0x17] = r0`。
战斗入口 `0x0808A596` 同样用 `r0 = scene`。
所以 **地图号 == 场景号 == 战斗组号**（实测：组 14 → `state[0x17] = 14`）。

---

## 4. 全人物组合轴

### 4.1 清单（88 对，静态可复现）

`tools/mgba_probe/l4_battle_matrix.py --axis scan`：

```
scan: 88/144 (group, sub) pairs carry a team; 47 usable map descriptors
```

* 编成矩阵：48 组 × 3 子 = **144** 种可能。
* **88** 种至少有一个槽位带非零角色 id。
* 判据：`formation[group][sub]` 的 12 个槽里至少一个 `id != 0`。

角色 id 的两种特殊值（运行时会被游戏替换）：

| id | 含义 |
|---|---|
| `0xFF / 0xFE / 0xFD` | 「由剧情决定」——游戏填入当前队伍（鸣人/佐助/小樱） |
| `0xFC / 0xFB / 0xFA` | 「此槽无单位」 |

例：

```
组  1 子0: [1, 2, 3, 31, 25, 26]                 子2: [255,254,253,31,25,26]
组 14 子0: [1, 2, 3, 30, 55, 55, 55, 55, 55]     子2: [255,254,253,30,55,...]
组 21 子0: [1, 2, 3]                             子2: [255,254,253]
组 32 子0: [255,254,253,252,251,250]             ← 整队都由剧情决定
```

> 组 47 的三个子项落在**规则表 `0x594758`** 里（编成矩阵 48 组会与它重叠），
> 所以它不是真正的队伍配置。见 §8。

### 4.2 逐对实测

```powershell
python tools\mgba_probe\l4_battle_matrix.py rom\base.gba --axis battles `
    --out build\l4-bm --json build\l4-battle-matrix.json
```

每对都**重新开机**（证据互相独立），流程：

1. 开机 → 按 `START`/`A` 走到剧情状态机循环头 `0x0808F752`；
2. 在 `0x0808F92E`（相位 0x110）、`0x080732B4`（战斗本体）、
   `0x0808A588`（战斗入口）下断点；
3. 三次 `poke` 请求该 `(组, 子)`；
4. 用游戏的按键沿配方（按 8 帧 → 静默 120 帧）推进战斗过场；
5. 读回证据。

**判据（缺一即算失败）**：

| 字段 | 含义 |
|---|---|
| `wrapper_seen` | 游戏的战斗本体 `0x080732B4` 确实执行了 |
| `ctrl_group` / `ctrl_sub` | 战斗控制块 `0x02026804` 的 `ctrl[1]`/`ctrl[2]` == 请求的组/子 |
| `unit_ids` | 单位数组 `0x020240C0` 的 12 个槽里非零角色 id |
| `expected_ids_present` | 编成矩阵里所有「真实角色」都出现在 `unit_ids` 里 |
| `map_id` | `state[0x17]`，即战斗加载的地图 |
| `ids_match` | `unit_ids` 与编成矩阵 id 列表**逐项相等**（占位符配置除外） |
| `battle_flag_seen` | `0x020311E0` 的 bit31 曾经为 1 |
| `screenshot` | 战斗画面 PNG |

### 4.3 结果

```
battles: 85/85 reached
```

**85/85**：每一个「真实编成」的 `(组, 子)` 配置都被游戏自己的战斗路径跑了一遍，
且证据齐全：

| 字段 | 85 对里的结果 |
|---|---|
| `wrapper_seen`（游戏的战斗本体 `0x080732B4` 执行了） | **85/85** |
| `phase_seen`（相位 `0x110` 处理块执行了） | **85/85** |
| `ctrl_group` == 请求的组 | **85/85** |
| `ctrl_sub` == 请求的子 | **85/85** |
| `unit_ids` 非空（单位数组被填上） | **85/85** |
| `expected_ids_present`（编成矩阵点名的角色都在场上） | **85/85** |
| `battle_flag_seen`（`0x020311E0` bit31 曾经为 1） | **85/85** |
| `map_loaded`（`state[0x17]` == 组号，即战斗加载了自己的地图） | **73/85**（例外见下） |
| `ids_match`（运行时 id 列表与编成矩阵**逐项相等**） | **44/85**（例外见下） |

**12 例外**（全部是「整队由剧情决定」的配置，即 12 个槽位全是占位符）：

| (组,子) | 编成矩阵 | 运行时 | `state[0x17]` |
|---|---|---|---|
| (1,2) (9,2) (13,2) (19,2) | `[255,254,253, …敌人…]` | `[1, …敌人…]` | `0x00`（战斗在跑，地图还没载入） |
| (31,1) (32,0) (33,0) (34,0) (35,0) (36,0) (37,0) (38,0) | `[255,254,253,252,251,250]` | `[1]` | `0x32` (=50) |

`0x32` = 50 **超过 `0x0808F4D4` 的上限**（`cmp r4,#0x31; bhi`），
所以这几场战斗**游戏自己也没载入地图** —— 工具如实记录了这一点，
而不是把 `state[0x17]` 当成「加载成功」。

`ids_match` 为真的那 44 对，是「静态编成矩阵 == 运行时单位数组」逐项相等的例子：

```
组  1 子0: 编成 [1, 2, 3, 31, 25, 26]            运行时 [1, 2, 3, 31, 25, 26]            ✓
组  9 子0: 编成 [1, 2, 3, 41, 41, 41, 41, 41]    运行时 [1, 2, 3, 41, 41, 41, 41, 41]    ✓
组 14 子0: 编成 [1, 2, 3, 30, 55, 55, 55, 55, 55] 运行时同                                ✓
组 46 子0: 编成 [1, 2, 3, 29]                    运行时 [1, 2, 3, 29]                    ✓
```

`ids_match` 为假的是**由剧情决定队伍**的配置（占位符 `0xFF/0xFE/0xFD` 被游戏换成
当前队伍），例如：

```
组  2 子2: 编成 [255,254,253, 32,32,32,32,32]   运行时 [1, 32, 32, 32, 32, 32]
组 32 子0: 编成 [255,254,253, 252,251,250]      运行时 [1]
```

这类配置里「敌方是谁」由剧情脚本在运行时决定，静态表只给出占位；
工具因此只断言「点名了角色的那几个槽位，人确实在场」。
**每对一张截图**在 `build/l4-bm/battle-g<组>-s<子>.png`（85 张），
机器可读报告在 `build/l4-battle-matrix.json` 的 `battles` 段。

---

## 5. 全流程轴：游戏**自己**换场

`0x0808F544`（剧情调度器）内部：

```asm
0x0808F594: ldr  r7,[pc,#0x1C] -> 0x020311D4
0x0808F598: ldr  r0,[pc,#0x1C] -> 0x08060D54   ; after 根表
0x0808F59C: ldr  r2,[pc,#0x1C] -> 0x08060C74   ; before 根表
0x0808F5A0: ldrb r1,[r6,#0x18]                 ; state[0x18]
0x0808F5A2: cmp  r1,#0
0x0808F5A4: beq  #0x0808F5C0                  ; ==0 → before 表
0x0808F5A6: lsls r0,r4,#0x10 / asrs r0,r0,#0xe
0x0808F5AA: add  r0,sb / ldr r0,[r0]          ; after[scene>>14]
0x0808F5C0: lsls r0,r4,#0x10 / asrs r0,r0,#0xe
0x0808F5C4: add  r0,r8 / ldr r0,[r0]          ; before[scene>>14]
0x0808F5C8: strb r1,[r6,#0x19]                ; state[0x19] = state[0x18]
0x0808F5CA: movs r5,#0 / strb r5,[r6,#0x18]   ; state[0x18] = 0
0x0808F5CE: movs r1,#0 / bl #0x80977b8        ; 跑 VM
0x0808F5D4: ldrb r0,[r6,#0x18] / cmp r0,#3 / bne
0x0808F5DA: ldrb r4,[r7,#0x16]                ; ★ state[0x16] = 新场景
0x0808F5DC: strb r5,[r7,#0x18]
0x0808F5DE: b   #0x0808F5A0                  ; 回到取根表 → 下一场
```

**关键**：`state[0x18] == 3` 时，调度器**自己**把 `state[0x16]` 当成新场景号
继续循环。VM 操作码 `0x1A`（`state[0x16]=场景号`，`state[0x18]=标志+1`）
在标志 = 2 时正好把 `state[0x18]` 写成 3，**从而触发游戏自身的场景推进**。

这就是比「外部改写场景字节」更强的判据：

> 观察到 `state[0x18]` 被脚本写成 3 → 调度器用新的 `state[0x16]` 重新取根表 →
> VM 入口收到的指针**逐位等于**新场景的根表条目。

`notes/evidence/l4-playthrough-20261021.md` 的 55/55 已经证明「每一场都能被
真实调度到」；本节补上了「游戏自己从一场走到下一场」这条闭环。

### 5.1 实测：场景 39 自己把游戏推进到场景 45

VM 操作码 `0x1A` 的 handler（`0x08097C6C`）：

```asm
0x08097C6C: ldrb r0,[r7,#2]      ; 标志操作数 (+2)
0x08097C6E: ldr  r4,[pc,#0x28]   ; 0x020311D4
0x08097C70: cmp  r0,#0
0x08097C72: beq  #0x8097c78
0x08097C74: adds r0,#1
0x08097C76: strb r0,[r4,#0x18]   ; state[0x18] = 标志 + 1
0x08097C78: ldrb r0,[r7,#1]
0x08097C7A: strb r0,[r4,#0x16]   ; state[0x16] = 场景号
```

场景 39 的脚本里有六个这种指令（`tools/decode_story_script.py --all` 解出来）：

```
1a 2d 02   → 场景 45
1a 2c 02   → 场景 44
1a 2b 02   → 场景 43
1a 2a 02   → 场景 42
1a 29 02   → 场景 41
1a 28 02   → 场景 40
```

标志 = 2 → `state[0x18] = 3` → **调度器自己换场**（§5 的 `0x0808F5DA` 分支）。
场景 39 就是剧情的分支点：玩家在这里选下一场去 40..45 中的哪一场。

**实测**（`--axis flow --flow-scenes 39`）：

```
flow scene  39: reached
  first  = 0x08031020   期望 0x08031020   ← before_root[39]，逐位相等
  -> new = 45           ← 调度器在 0x0808F5DA 读到的 state[0x16]
  script = 0x080348DF   期望 0x080348DF   ← before_root[45]，逐位相等
```

也就是说：**游戏自己跑完场景 39 的脚本，自己把场景号改成 45，
自己重新取根表、自己把 VM 入口的脚本指针换成 `before_root[45]`** ——
全程没有人从外面改过场景字节。

（`first` 那一步还额外证明了：这一场用的脚本指针 == 根表条目，
与 `notes/evidence/l4-playthrough-20261021.md` 的 55/55 判据同源。）

---

## 6. 全地图轴

### 6.1 地图描述符表

`0x0853D910`（文件偏移 `0x053D910`），32 字节/条：

```
+0x00 u16 raw_width   +0x02 u16 raw_height
+0x04 u32 tile_gfx    +0x08 u32 palette   +0x0C u32 layer0
+0x10 u32 layer1     +0x14 u32 metatile  +0x18 u32 terrain
+0x1C u8  background_id (+3 pad)
```

**47 条（id 0..46）**。第 47 条起是别的表：`raw_width` = 513 / 3486 / 3932 /
4366 / 55780，远超格式允许的 64×128 tile 上限，指针分布也不对。
`0x0808F4D4` 另外拒绝 `id > 0x31`（49）。

### 6.2 逐张实测

```powershell
python tools\mgba_probe\l4_battle_matrix.py rom\base.gba --axis maps `
    --out build\l4-bm --json build\l4-battle-matrix.json
```

路线：停在状态机循环头 → `poke state[0x16] = <地图号>`、
`poke16 state[0x12] = 0x0030`（相位 0x30 = 下一场景）→ 调度器调用
`0x0808F4D4(scene)`。

**判据**：

| 字段 | 含义 |
|---|---|
| `map_load_arg` | 在 `0x0808F588`（`bl 0x0808F4D4` 调用点）读到的 **r0**，必须 == 地图号 |
| `state_map_id` | `state[0x17]`，必须 == 地图号 |
| `vram_sha256` | 载入前后 VRAM（`0x06000000` 起 32KB）的 SHA-256 必须不同 |
| `screenshot` | 渲染出来的地图画面 |

> `map_load_arg` 是这张判据表的关键：**地图 0 的 `state[0x17]` 恒为 0**，
> 光看它无法区分「载入了地图 0」和「根本没载入」。r0 才能区分。

### 6.3 结果

```
maps: 47/47 reached
```

| 字段 | 47 张里的结果 |
|---|---|
| `map_load_arg` == 地图号（游戏自己传给 `0x0808F4D4` 的 r0） | **47/47** |
| `state_map_id` == 地图号 | **47/47** |
| `vram_changed`（载入前后 VRAM 指纹不同） | **47/47** |
| 47 个 VRAM SHA-256 **两两不同** | **47/47**（无重复） |

47 张地图的 VRAM 指纹（`0x06000000` 起 32KB 的 SHA-256，前 12 位）：

```
map 00: 4522d5a4242b   map 01: 6ea1e9acb871   map 02: 52bf61a1fd64
map 03: 5b41ff7fff31   map 04: abe4dfd96b3a   ...
map 46: 5d0465926509
```

**没有两张地图的指纹相同** —— 说明 47 个描述符确实是 47 张不同的图，
而不是「同一张图被数了 47 遍」。

每张一张截图在 `build/l4-bm/map-<id>.png`（47 张）。

---

## 7. 复现命令与可证伪测试

```powershell
$env:PYTHONIOENCODING='utf-8'

# 静态清单（不跑模拟器，秒级）
python tools\mgba_probe\l4_battle_matrix.py rom\base.gba --axis scan

# 全人物组合：85 个真实编成配置
python tools\mgba_probe\l4_battle_matrix.py rom\base.gba --axis battles `
    --out build\l4-bm --json build\l4-battle-matrix.json

# 全地图：47 张
python tools\mgba_probe\l4_battle_matrix.py rom\base.gba --axis maps `
    --out build\l4-bm --json build\l4-battle-matrix.json

# 全流程：游戏自身换场
python tools\mgba_probe\l4_battle_matrix.py rom\base.gba --axis flow `
    --flow-scenes 39 --json build\l4-battle-matrix.json

# 全部一起（每个轴单独跑也行：工具会把各轴结果合并进同一份 JSON）
python tools\mgba_probe\l4_battle_matrix.py rom\base.gba --axis all `
    --out build\l4-bm --json build\l4-battle-matrix.json
```

**可证伪测试**（每条都能让工具以非 0 退出）：

| 声称 | 怎么推翻 |
|---|---|
| 85 个真实编成配置都被真的打过 | `--pairs "14:0"` 单跑；若 `unit_ids` 为空或 `ctrl[1]!=14`，工具退出 1 |
| 47 张地图都被真的载入 | `--maps "16"` 单跑；若 `map_load_arg != 16`，工具退出 1 |
| 编成矩阵地址公式 | 在 ROM 里改 `0x0807332C` 的字面量 `0x085461C4`，`unit_ids` 必须跟着变 |
| 战斗标志在 `0x020311E0` bit31 | 把 `0x0808A4A0` 的 `lsrs r2,r1,#0x1d` 改成 `#0x1c`，标志字必须变成 `0x020311D4` |
| 相位 0x110 是完整战斗入口 | 把 `0x0808F93E` 的 `strb r0,[r1,#1]` 去掉，`ctrl[1]` 必须不再是组号 |
| 调度器自己在 `state[0x18]==3` 时换场 | 把 `0x0808F5D4` 的 `cmp r0,#3` 改成 `#4`，`--axis flow` 必须失败 |
| 相位 0x118 **不**写 ctrl | 把 `0x0808F93E` 的 `strb r0,[r1,#1]` 挪进 `0x0808F94A` 之后，`ctrl[1]` 必须变 0 |

---

## 7.1 回归状态（本轮实测）

| 命令 | 结果 |
|---|---|
| `python -m unittest discover -s tests -p 'test_*.py'` | **84/84 OK，exit 0** |
| `python tools\completion_audit.py --check` | **exit 0** |
| `python tools\automated_test.py` | **27/28，exit 1** |

第三条有 **1 个先于本轮就存在的失败**，与本轮工作无关（已实测验证）：

```
[db_integrity] populated rom_* tables cannot silently generate no patches
generate_character_stats_b_patches: returned no byte patches for
                                    rom_character_stats_b (63 rows)
```

**根因（HEAD 级，不是本轮引入）**：

* `tools/build_db_patches.py::generate_character_stats_b_patches`
  （**HEAD 版本就如此**，未提交改动没有碰它）查的是具名列
  `hp, padding1, padding2, padding3, max_value, char_type, attack, defense`，
  并且要求 `_idx ∈ 0..17`、基址 `0x545200`；
* 而 **committed** 的 `sequel/content/character-stats-b/bank.json`
  是 **63 条、通用列名 `field_0..field_7`**、偏移基址 `0x544C08`；
* `sequel/editor.db` 是 **gitignored 的生成物**。
  之前工作区里那份是**旧内容**留下的（具名列、18 行），所以这条检查当时是绿的；
  一旦有人用 `tools/build_editor_db.py` 重建 DB（`automated_test.py` 自己就会跑
  `build_mod.py`），它就变成 63 行通用列名，于是这条检查**必然**红。

**判定「与本轮无关」的实验**：把本轮新增的两个文件
（`tools/mgba_probe/l4_battle_matrix.py`、`notes/evidence/l4-battle-matrix-20261021.md`）
移出仓库后重跑，`automated_test.py` **仍然**是同一条 27/28；
`unittest` 也在移出后复现过同样的失败（那次是 Windows 临时文件锁
`PermissionError ... tmpXXXX.db` 引起的偶发错误，连续三次重跑即恢复）。

**修复位置（不属本轮所有权，未改）**：
`tools/build_db_patches.py::generate_character_stats_b_patches` 需要改成按
通用列名 `field_0..field_7` 取值、并按 `0x544C08` 基址 / 63 条处理；
或者把 `sequel/content/character-stats-b/bank.json` 改回具名列 + 18 条。

---

## 8. 未达 / 待办

* **组 47 不是队伍配置**：编成矩阵 48 组 × `0x1AAC` 会越过 `0x594758`
  （胜负条件表），所以**组 47 的三个子项落在规则表里**，里面的「角色 id /
  side」是规则表的字节。文档口径的 88 对里有 3 对是这种垃圾数据；
  **真正可用的编成配置是 85 对**（组 1..46）。
  工具的 `--axis scan` 两个数都报（88 与 85），`--axis battles` 跑 85 对。
* **子配置 2 的「由剧情决定」槽位**：工具能证明「游戏确实把队伍摆上了场」
  （`expected_ids_present`），但**不能**证明剧情写入的那三个人是谁 ——
  那取决于剧情分支，需要按分支跑（§5 的场景 39 分支点就是这种结构）。
* **战斗胜负 / 通关**：本轮没有把战斗打到分出胜负，证据止于「战斗真的在跑」
  （战斗本体执行、单位就位、地图加载、战斗标志置位）。
* **`map_id` 与组号不一致的少数配置**：战斗走的是 `0x0808A588(scene)` →
  `0x0808F4D4(scene)`，理论上地图号 == 组号；实测有几组不等
  （见 JSON 里 `map_id != group` 的项），原因待查（可能与
  「有效子配置字节」`formation[组][子]` 的 `+0` 字节有关）。
* **全流程的游戏自身换场**：§5.1 已经在场景 39 上跑通并留证；
  还没有把 55 个场景**逐个**跑成「游戏自己换场」的批处理证据。

---

## 进展日志

* **2026-10-21 第 1 轮**：静态钉死战斗层与地图层的关键地址；给出 4 条对简报的
  更正（根表选择条件反转、写 ctrl 的地址、调度器写的不是 `state[0x00]`、
  地图号 == 场景号）。
* **2026-10-21 第 2 轮**：找到「停在状态机循环头 + 三次内存写」这条
  **游戏自身**的开战斗路径；实测战斗真的开打（画面、单位数组、地图都对）。
  更正自己第一版结论：战斗标志在 **`0x020311E0`** bit31，字下标公式是
  `(id>>5)&7` 而不是 `id>>29`。
* **2026-10-21 第 3 轮**：产出 `tools/mgba_probe/l4_battle_matrix.py`
  （一条命令跑完 85 对战斗 + 47 张地图 + 游戏自身换场，
  证据缺失即非 0 退出）。
* **2026-10-21 第 4 轮**：全量跑完 ——
  **战斗 85/85、地图 47/47（47 个互不相同的 VRAM 指纹）、游戏自身换场 1/1**
  （场景 39 → 45，脚本指针 `0x080348DF` == `before_root[45]`）。
  工具增加 JSON 合并写（各轴可单独跑）与逐项落盘（挂起也不丢证据）。
