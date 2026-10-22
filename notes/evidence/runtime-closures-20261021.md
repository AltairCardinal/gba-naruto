# 运行时闭环 2026-10-21（A..H 八项）

本文件记录 2026-10-21 这一轮对 `tools/completion_audit.py` 中 **八个具名未闭合项**
（`battle-rules` / `maps` / `runtime-state` / `cutscene-scripts` /
`portrait-table` ×2 / `story-background-table` / `sound-id-table`）的闭环过程。

每项固定四段：

1. **方法**（做了什么，为什么这么做）
2. **证据**（读数 / 反汇编 / 截图，附地址）
3. **可证伪测试**（一条能证伪本结论的命令或读数）
4. **审计条目应改成的确切文字**（可直接粘贴的 `unresolved` / `corrections` 文本）

> 本文件是**唯一的**汇总入口；分项事实同时**追加**到拥有该事实的既有笔记
> （`notes/battle-tables.md`、`notes/evidence/cutscene-block-format-20261020.md`、
> `notes/evidence/portrait-writeback-20261021.md`、`notes/resource-locations.md`、
> `notes/runtime-and-object-tables-20261020.md`、`notes/evidence/audio-song-export-20261021.md`）。
> 追加一律**只追加**，不重写既有内容。

---

## 0. 起始状态（八项审计原文）

抄录自 `tools/completion_audit.py`（本轮**未修改**该文件），作为闭环前的基线。

### A. `battle-rules` — `0x0202680C` 是不是回合计数？

`unresolved[evidence]` 原文：

> `0x0202680C` 已收窄为「每场战斗计数/标志块的首字节」，
> 仅在结算时被读（类型 2/4/9 的闸门 + `0x08077BB6` 的兜底）；
> **运行时读数已证明它不是回合计数**：
> 真实战斗（组 9 / 子 0）里按 40 轮按键，它**全程为 0**，
> 而它周围的 `0x0202680F/10/11/12/13/15/17` 都被写过；
> 它其实是战斗初始化时从 WRAM `0x02024068` 复制来的那一字节
> （复制点 `0x08068BA4`）。
> **残留**：该场战斗在战斗界面停住（只按了 A），
> 所以「打满回合后它才动」这一种可能还没被彻底排除

### B. `maps` — metatile 缓冲的 2048 上限从哪来？

`unresolved[evidence]` 原文：

> metatile 缓冲的 2048 上限是由两侧原生结构
> （`0x0201BE2C+0x1000` 与 `0x02021E2C`）夹出来的边界，
> 而不是一条明确的分配语句

### C. `runtime-state` — `story_progress` / `story_branch` / `story_config`

`unresolved[evidence]` 原文：

> `story_progress` / `story_branch` / `story_config` 三个字段
> 仍无运行时读数

### D. `cutscene-scripts` — 四个关卡图块集属于哪四个场景？

`unresolved[evidence]` 原文：

> 这四个关卡图块集具体对应哪四处场景仍未定位
> （已排除「47 张战斗地图」这个假设；
> 剧情底图表 `0x59903C` 的指针在 `0x0832xxxx` 段，
> 与块的 `0x0812D9E4` 段不同，也不是同一批数据）

### E. `portrait-table` — `param << 4` 的运行时改写

`unresolved[evidence]` 原文：

> 「参数 << 4」的运行时改写语义未证实（它改的是 VRAM 上的副本，
> 不影响 ROM，所以不影响写回安全性，但影响编辑器预览是否与游戏一致）

### F. `portrait-table` — `portrait_pieces` 背后的共享图块表

`unresolved[evidence]` 原文：

> 拼块表 `portrait_pieces`（0x4643C0）的 tile 下标
> （最大 135）超出头像自己那 6400 字节缓冲里的 100 张图块，
> 说明它指向另一张**共享图块表** —— 这条链需要一次运行时定点
> （读出共享图块表的基址并核对 tile 下标）才能闭合

### G. `story-background-table` — 8bpp 条目用哪一路 BG、是否 256 色

`unresolved[evidence]` 原文：

> 剧情底图的 8bpp 条目用哪一路硬件 BG、是否开 256 色模式
> （`BGxCNT` bit8）仍需一次 IO 寄存器抓取；
> 已确认的是 4bpp 与 8bpp **互斥**而不是叠加

### H. `sound-id-table` — DirectSound 弯音插值

`unresolved[capability]` 原文：

> DirectSound 弯音（pitch bend）插值未实现

---

## 1. 工作日志

（按时间追加；每个条目写完即落盘，避免崩溃丢失。）

### 2026-10-21 起步

- 环境确认：`build/mgba-probe/mgba-probe.exe` 已构建；`build/python-deps/capstone` 可用。
- 基线复核：见本文件末尾「回归结果」一节。
- 复用的现成工具：
  - `tools/mgba_probe/l4_battle_matrix.py::Harness` —— 战斗路由（三次 poke 直达任意战斗）
  - `tools/mgba_probe/l4_playthrough.py::Probe/capture/arm/KEY_BITS` —— 探针协议
  - `tools/consumer_locate.py::LiteralIndex.readers_of(arm_address)` —— 找原生读者
  - `tools/disasm_thumb.py`、`tools/konoha_font.py`、`tools/m4a_block_table.py`

---

## H. `sound-id-table` —— DirectSound 弯音插值（**已闭环**）

### H.1 方法

**先把引擎的弯音路径整条静态拆出来，再用探针把引擎自己的数值读出来对拍。**

1. 用 `tools/m4a_block_table.py` 统计五个原生曲子的命令直方图，确认
   **BEND(0xC0) 出现 74 次、BENDR(0xC1) 0 次**，KEYSH 45 次、MOD 248 次、
   LFOS 6 次、TUNE 0 次。⇒ 弯音是**真实在用**的效果，但**弯音量程
   （bend range）始终是通道复位时的默认值 2**。
2. 反汇编 m4a 引擎的通道结构与弯音累加器，定位到：
   - BEND 命令处理函数 `0x0809A368`：`strb r3, [r1, #0xe]`，其中
     `r3 = 操作数 - 0x40` ⇒ **通道+0x0E = 弯音值（有符号）**；
   - BENDR 命令处理函数 `0x0809A37C`：`strb r3, [r1, #0xf]`
     ⇒ **通道+0x0F = 弯音量程**（通道复位时 `0x0809A4D6` 写 2）；
   - 累加器 `0x0809B450`..`0x0809B486`；
   - 音符处理函数 `0x0809A708`，它把音符键写进 voice+0x08；
   - 每 tick 的音高重算 `0x0809A61C`..`0x0809A658`；
   - DirectSound 音高函数 `0x0809A998`（内含一个 **ARM 模式**的乘法助手）。
3. 用 `tools/closure_pitch_probe.py` 在真实战斗/真实剧情场景里打断点，
   把引擎自己的数值读出来。
4. 把这套算法**逐指令**转写进 `tools/audio_song_export.py`，
   再用 `tools/closure_pitch_check.py` 对拍引擎读数。

### H.2 证据

**(a) 引擎的弯音累加器（`0x0809B450`..`0x0809B486`）**

```
0x0809B450  movs  r0, #0xe
0x0809B452  ldrsb r0, [r2, r0]     ; bend   = (s8)channel[0x0E]
0x0809B454  ldrb  r1, [r2, #0xf]   ; range  = (u8)channel[0x0F]
0x0809B456  muls  r0, r1, r0      ; bend * range
0x0809B45A  ldrsb r1, [r2, #0xc]  ; tune   = (s8)channel[0x0C]
0x0809B45C  adds  r1, r1, r0
0x0809B45E  lsls  r1, r1, #2      ; * 4
0x0809B462  ldrsb r0, [r2, #0xa]  ; key shift = (s8)channel[0x0A]
0x0809B464  lsls  r0, r0, #8
0x0809B46A  ldrsb r0, [r2, #0xb]  ; channel[0x0B]：无任何命令写它，恒 0
0x0809B470  ldrb  r0, [r2, #0xd]  ; channel[0x0D]：无任何命令写它，恒 0
0x0809B482  asrs  r0, r1, #8
0x0809B484  strb  r0, [r2, #8]    ; 通道+0x08 = 半音偏移（s8）
0x0809B486  strb  r1, [r2, #9]    ; 通道+0x09 = 分数（u8）
```

即

```
S          = (tune + bend * range) * 4 + (keyShift << 8)
semitone   = (s8)((S >> 8) & 0xFF)
fraction   = (u8)S
```

**(b) 音高键与插值（`0x0809A89C`..`0x0809A658` / `0x0809A998`）**

```
0x0809A89C  ldrb  r1, [r4, #8]    ; 音符键（voice+0x08）
0x0809A8A0  ldrsb r0, [r5, r0]    ; 通道+0x08 的半音偏移
0x0809A8A2  adds  r2, r1, r0
0x0809A8A4  bpl   0x809a8a8
0x0809A8A6  movs  r2, #0          ; 负数夹到 0
0x0809A650  ldrb  r2, [r5, #9]    ; fraction
0x0809A654  bl    #0x809a998      ; GetPitch(wave, key', fraction)
0x0809A658  str   r0, [r4, #0x20] ; 写进 voice+0x20
```

`0x0809A998` 内部：

```
0x0809A9AC  ldr  r3, [pc, #0x44]  ; 0x084645C4 选择表
0x0809A9C0  ldr  r5, [r0]         ; octave_base[semitone]
0x0809A9C2  lsrs r5, r1           ; f(key)   = base >> octave
0x0809A9DC  subs r0, r0, r5       ; f(key+1) - f(key)
0x0809A9E0  bl   #0x8099d7c       ; * (fraction << 24) >> 32
0x0809A9E6  adds r1, r5, r1       ; f(key) + delta
0x0809A9EA  bl   #0x8099d7c       ; * wave[4] >> 32
```

`0x08099D7C` 是 **Thumb→ARM 切换跳板**（`adr r2,#0` / `bx r2`），
真正的乘法在 ARM 态 `0x08099D80`：

```
0x08099D80  umull r2, r3, r0, r1   ; r2=低 32 位，r3=高 32 位
0x08099D84  add   r0, r3, #0      ; 取高位 ⇒ 结果 = (a*b) >> 32
```

所以两次乘法分别是 `(delta * fraction) >> 8` 与 `(base * wave[4]) >> 32`，
**这正是「弯音插值」**：引擎在 `f(key)` 与 `f(key+1)` 之间按 8 位分数线性插值。

**(c) 运行时读数（引擎自己的数值）**

用 `tools/closure_pitch_probe.py --scene 40 --poke-bend <值> --poke-range <量程>`
在真实剧情场景里驱动引擎自己的弯音路径（在音符处理函数尾声
`0x0809A8F0` 处写入 `通道+0x0E` / `通道+0x0F` 并置位「音高脏」位
`通道[0] bit2`，引擎随后自己跑累加器与重算）：

| 注入的 BEND 操作数 | 存进 0x0E | 量程 | 引擎算出的 S | 引擎的 通道+0x08 / +0x09 | 引擎写下的音高寄存器 |
|---|---|---|---|---|---|
| 0x50 | 16 | 2 | 128 | 0 / 128 | 0x3850（key 60） |
| 0x60 | 32 | 8 | 1024 | 4 / 0 | — |
| 0x20 | −32 | 2 | −256 | −1 / 0 | — |
| 无弯音 | 0 | 2 | 0 | 0 / 0 | 0x36B0（key 60） |

`0x0809B486` 断点处的 `r1` 与通道字节与上表逐项一致。

**(d) 对拍：179 条引擎读数，0 处不符**

```
$ python tools\closure_pitch_check.py rom\base.gba build\closure-pitch.json \
      build\closure-pitch-bend.json build\closure-pitch-b60-r8.json \
      build\closure-pitch-b20-r2.json build\closure-pitch-s40.json \
      build\closure-pitch-s44.json build\closure-pitch-s50.json \
      build\closure-pitch-s54.json
closure-pitch.json: 9 engine pitch readings checked, 0 mismatch(es)
closure-pitch-bend.json: 22 engine pitch readings checked, 0 mismatch(es)
closure-pitch-b60-r8.json: 14 engine pitch readings checked, 0 mismatch(es)
closure-pitch-b20-r2.json: 14 engine pitch readings checked, 0 mismatch(es)
closure-pitch-s40.json: 84 engine pitch readings checked, 0 mismatch(es)
closure-pitch-s44.json: 12 engine pitch readings checked, 0 mismatch(es)
closure-pitch-s50.json: 12 engine pitch readings checked, 0 mismatch(es)
closure-pitch-s54.json: 12 engine pitch readings checked, 0 mismatch(es)
TOTAL: 179 readings, 0 mismatch(es)
```

检查内容：`tools/audio_song_export.py::bend_pitch_offset` 必须复现引擎的
`通道+0x08/+0x09`；`engine_pitch_base` 必须复现引擎写下的音高寄存器
`(base * wave[4]) >> 32`。

### H.3 可证伪测试

```
python tools\closure_pitch_check.py rom\base.gba build\closure-pitch-b60-r8.json
```

* 断言 1（累加器）：`bend_pitch_offset(32, 8) == (4, 0)`、
  `bend_pitch_offset(16, 2) == (0, 128)`、`bend_pitch_offset(-32, 2) == (-1, 0)`。
  改错 `*4`、`<<8` 或量程相乘，断言立刻失败。
* 断言 2（插值）：引擎的音高寄存器必须等于
  `((f(key+offset) + ((f(key+offset+1) - f(key+offset)) * fraction >> 8)) * wave[4]) >> 32`。
  把 `>> 8` 改成 `>> 16`、或把 `wave[4]` 换成 `wave[0]`，对拍立刻报 mismatch。
* 回归：`python tools\audio_song_export.py rom\base.gba --self-test` 必须 `SELF-TEST: PASS`；
  `python tools\audio_song_export.py rom\base.gba --verify-psg 2` 必须仍然
  「534 PSG events checked against the ROM」（sound id 2 正是带 BEND 的曲子）。

### H.4 审计条目应改成的文字

`sound-id-table` 的 `unresolved` **清空**，并在 `corrections` 里追加：

> **DirectSound 弯音（pitch bend）插值已实现**（2026-10-21）：
> 引擎的弯音链已按本 ROM 的代码逐条转写并用探针对拍：
> BEND(0xC0) 写 `通道+0x0E = 操作数-0x40`（`0x0809A368`）、
> BENDR(0xC1) 写 `通道+0x0F = 量程`（`0x0809A37C`，复位默认 2，`0x0809A4D6`）；
> 累加器 `0x0809B450`..`0x0809B486` 给出
> `S = (tune + bend*range)*4 + (keyShift<<8)`、
> `通道+0x08 = (s8)(S>>8)`（半音偏移）、`通道+0x09 = (u8)S`（分数）；
> 音高键 = 音符键 + 半音偏移（负则夹 0，`0x0809A8A2`），
> DirectSound 音高 = `((f(k) + ((f(k+1)-f(k))*fraction>>8)) * wave[4]) >> 32`
> （`0x0809A998`；`>>32` 来自 ARM 态助手 `0x08099D80`
> `umull r2,r3,r0,r1` / `add r0,r3,#0`）。
> `tools/audio_song_export.py` 现在算的是**同一套整数**，
> 并用 `tools/closure_pitch_check.py` 对拍引擎自己的读数：
> **179 条引擎音高读数 0 处不符**（含弯音分数 128/160 与半音偏移 +4/−1）。
> 五个原生曲子的 PSG 导出仍与 ROM 原始字节逐事件相符（616/534/746/612/498）。

## A. `battle-rules` —— `0x0202680C` 是不是回合计数？（**已闭环；旧结论作废**）

### A.1 方法

1. 先在**静态**上把类型 2 的胜利条件读出来（`0x0807790C`..`0x0807791A`）；
2. 再在**运行时**用**真的能把回合打过去**的按键序列重跑一场战斗。

### A.2 证据

**静态**：`0x0202680C` = 战斗控制块 `0x02026804` 的 **+8** 字节，
而类型 2 规则正是拿它跟 `ctrl[6]`（`0x0202680A`，回合上限）比：

```
0x0807790C  ldrb r1, [r6, #6]      ; ctrl[6] = 回合上限
0x0807790E  cmp  r1, #0
0x08077910  bne  0x8077914        ; 上限 0 -> 规则不生效
0x08077914  ldr  r0, [pc, #8]      ; 0x0202680C
0x08077916  ldrb r0, [r0]          ; 当前回合计数
0x08077918  cmp  r1, r0
0x0807791A  beq  0x807791e        ; 计数 == 上限 -> 规则成立
```

**运行时**（`tools/closure_round_probe.py`，战斗 组 9 / 子 0）：

```
press  24 key=DOWN ctrl=000900000000000001000000000000000000000000000000 limit=0 counter=1
press  25 key=DOWN ctrl=000900000000000002000000000000000000000000000000 limit=0 counter=2
distinct round counter values: [1, 2]
```

**旧结论作废**：旧审计写「运行时读数已证明它不是回合计数」，
那次运行**只按了 A**，战斗停在界面、回合没推进；
加上 `DOWN` 选指令 + `A` 确认之后，**计数从 1 变成 2**。
这一场的回合上限 `ctrl[6]` = 0，所以类型 2 规则没有触发。

### A.3 可证伪测试

```
python tools\closure_round_probe.py --battle 9:0 --rounds 30
```

断言：在**推进了回合**的战斗里 `0x0202680C` 必须出现 ≥ 2 的值；
若它是「初始化时复制过来的常量」，该值会恒为 1。

### A.4 审计条目应改成的文字

`battle-rules` 的 `unresolved` **清空**，`corrections` 里把旧结论替换为：

> `0x0202680C` **就是回合计数**（2026-10-21，旧的「不是回合计数」结论**作废**）：
> 它是战斗控制块 `0x02026804` 的 **+8** 字节，类型 2 的胜利条件正是
> 「`0x0202680C` == `ctrl[6]`（回合上限，`0x0202680A`）」
> （`0x08077914`..`0x0807791A`；上限为 0 时该规则不生效）。
> 运行时读数（`tools/closure_round_probe.py`，组 9 / 子 0）：
> 只按 A 时战斗停在界面、计数不动；**按 DOWN + A 真的把回合打完**时，
> 计数从 **1 变 2**。旧审计「40 轮按键全程为 0」的那次读数
> 是因为**战斗没推进过回合**。

---

## B. `maps` —— metatile 缓冲的 2048 上限从哪来？（**部分闭环**）

### B.1 方法

把「缓冲基址」「步长」「末端」三个量分别去 ROM 的**字面量池**里找，
看它们是不是引擎自己的常量。

### B.2 证据

| 量 | 值 | 出处 |
|---|---|---|
| 基址 | **`0x0201DE2C`** | 字面量池 `0x08068F58`（查找函数 `0x08068F08` 的 `ldr r1,[pc,#0x18]`）与 `0x080690E4`（地图加载器），**各一份** |
| 步长 | **8 字节** | `0x08068F38 lsls r0, r0, #3`（下标 × 8） |
| 末端 | **`0x02021E2C`** | 字面量池 `0x080690E8`，与基址**在同一个字面量池里相隔 4 字节**，由同一段代码装载（`0x080690B4` 装基址、`0x080690BC` 装末端） |

⇒ 容量 = `(0x02021E2C − 0x0201DE2C) / 8` = `0x4000 / 8` = **2048 项**。

**这推翻了旧审计的说法**：「2048 上限是由两侧原生结构夹出来的边界」
—— 它其实是**引擎代码里成对出现的两个常量**，不是夹出来的。

**仍未闭合**：没有找到一条显式的「下标 < 2048」越界检查，
所以「引擎会拒绝越界写入」目前**无证据**。

### B.3 可证伪测试

```
python build\closure_allloaders.py 0x0201DE2C 16
python build\closure_allloaders.py 0x02021E2C 16
```

两个常量都必须有**真实的 `ldr rX,[pc,#imm]` 装载点**；
若 2048 只是夹出来的，这两个装载点就不会同时存在。

### B.4 审计条目应改成的文字

`maps` 的 `unresolved` **清空**，`corrections` 追加：

> metatile 缓冲的容量**不再是从两侧结构夹出来的**：
> 缓冲**基址 `0x0201DE2C`** 与**末端 `0x02021E2C`** 是 ROM 代码里
> **成对出现的两个字面量常量**（分别在 `0x08068F58` 与 `0x080690E8`，
> 同一个字面量池），步长 **8 字节**（`0x08068F38 lsls r0,r0,#3`），
> 因此容量 = `0x4000/8` = **2048 项**。
> **仍未证实**：引擎没有一条显式的「下标 < 2048」越界检查，
> 「越界会被拒绝」这句话**无证据**。

---

## C. `runtime-state` —— `story_progress` / `story_branch` / `story_config`（**部分闭环**）

### C.1 方法

在 ROM 里找**装载剧情标志块 `0x020311D4`** 的代码，
再在它周围找 `+0x10 / +0x18 / +0x19..0x1B` 的访问点；
然后在运行时逐次按键读整块。

### C.2 证据

| 字段 | 地址 | 读点 | 写点 | 语义 |
|---|---|---|---|---|
| `story_progress` | `0x020311E4`（u16） | `0x0808F5E0`、`0x08095338`、`0x08097BCA` | `0x0808F696`（新游戏清 0）、**`0x08097BD4`（剧情 VM 写绝对值）** | 剧情进度；剧情 VM 的一个 opcode 把它**置成绝对值**；调度器拿它跟 **360** 比 |
| `story_branch` | `0x020311EC`（u8） | `0x0808F5A0`、`0x0808F5D4`、`0x0808F67E` | `0x0808F5CC`、`0x0808F5DC`、`0x0808F670` | **分支选择器**：非 0 时调度器改用「after」根表，用完即清 |
| `story_config` ×3 | `0x020311ED..EF` | — | `0x0808F5C8`（把分支值抄进 `+0x19`） | `+0x19` = 分支 id（**同时就是战斗 sub-config 字节**） |

```
; 剧情 VM 的「设进度」opcode
0x08097BC8  ldr  r1, [pc, #0x24]   ; 0x020311D4
0x08097BCA  ldrh r0, [r1, #0x10]  ; 旧进度
0x08097BCC  cmp  r0, r4           ; r4 = 操作数
0x08097BD4  strh r4, [r1, #0x10]  ; 进度 = 目标值   <<< 唯一的进度写入点

; 调度器
0x0808F5A0  ldrb r1, [r6, #0x18]  ; story_branch
0x0808F5C8  strb r1, [r6, #0x19]  ; 抄进 story_config[0]
0x0808F5CC  strb r5, [r6, #0x18]  ; 分支用完清零
0x0808F5E0  ldrh r1, [r7, #0x10]  ; story_progress
0x0808F5E2  movs r0, #0xb4 / lsls r0, r0, #1   ; 360
0x0808F5E6  cmp  r1, r0
```

> **更正**：旧笔记写「370 = 原版通关」，**原生代码比的是 360**（`0xB4 << 1`）。

**运行时读数**（`tools/closure_story_probe.py`）：

- **`story_branch` 变了**：55 个剧情场景里只有**场景 31** 读到
  `story_branch = 1`（其余全 0），且 20 次按键里稳定为 1 ⇒ 该字段是活的；
- `story_progress` 与 `story_config` 在**直接调度**的场景里恒为 0：
  进度只有剧情 VM 的那个 opcode 会写，直接调度跑不到它；
  `story_config[0]` 只在分支被消费的那一刻被写入，随后立即被清零。

### C.3 可证伪测试

```
python tools\closure_story_probe.py --scenes 31 --presses 20
```

断言：场景 31 的 `story_branch` 必须读出 **1**；
若 `+0x18` 不是分支选择器，它会恒为 0。

### C.4 审计条目应改成的文字

`runtime-state` 的 `unresolved` 改为：

> 三个字段的地址与读写点已由原生代码钉死：
> `story_progress` = **`0x020311E4`**（u16，剧情 VM 的「设进度」opcode
> 在 `0x08097BD4` 把它置成绝对值；调度器在 `0x0808F5E0` 把它跟
> **360**（`0xB4<<1`，**不是旧笔记写的 370**）比较）；
> `story_branch` = **`0x020311EC`**（u8，调度器在 `0x0808F5A0` 读它来选
> 「after」根表，`0x0808F5C8` 抄进 `story_config[0]` 后 `0x0808F5CC` 清零）；
> `story_config` = **`0x020311ED..EF`**（`+0x19` = 分支 id，也是战斗 sub-config 字节）。
> **运行时读数**：`story_branch` 在**场景 31** 读出 **1**（其余场景 0），
> 证明它是活的；`story_progress` 与 `story_config` 在**直接调度**的场景里
> 恒为 0（进度只有剧情 VM 的 opcode 会写、`story_config[0]` 写完即清），
> **还需要一次真实通关流程的读数**才算完全闭合。

---

## D. `cutscene-scripts` —— 四个关卡图块集属于哪四个场景？（**前提被证伪**）

### D.1 方法

1. 从加载器 `0x08072EDC` 的四个**调用点**看它传进去的**常量下标**；
2. 用探针在 55 个剧情场景 / 开机流程 / 真实战斗里找这个加载器。

### D.2 证据

**加载器**（`0x08072EDC`）：

```
0x08072F0C  ldr  r4, [pc, #0x2c]    ; 0x0853DF70
0x08072F10  lsls r5, r0, #3        ; 下标 * 8
0x08072F16  ldr  r1, [pc, #0x28]   ; 0x06016000  ← OBJ 图块区
0x08072F22  ldr  r1, [pc, #0x20]   ; 0x05000380  ← OBJ 调色板 RAM
```

⇒ 这四块是**四套 OBJ 4bpp 图块集 + 各自的 16 色调色板**。

**四个调用点传的是硬编码下标**：

| 调用点 | 下标 | 上下文 |
|---|---|---|
| `0x0807363A` | **0** | 另一个关卡初始化函数 |
| `0x08073100` | **1** | 状态字节 `[r2+3] == 1`（`0x080730C0`） |
| `0x0807314A` | **2** | 状态字节 `[r2+3] == 2`（`0x08073130`） |
| `0x08073196` | **3** | 同函数第三分支 |

⇒ **下标不是场景号**，是「关卡/过场资源档位」，由一个状态字节选择。
**「这四块对应哪四处场景」这个提法本身不成立。**

**运行时负证据**：

- 55 个剧情场景逐个调度 → `0x08072F0C` **0 命中**；
- 开机流程（标题 → 新游戏 → 开场）→ **0 命中**；
- 真实战斗（组 9 / 子 0）→ **0 命中**。

### D.3 可证伪测试

```
python tools\closure_scene_sweep.py --scenes 1-55 --breaks 0x08072F0C
python tools\closure_boot_probe.py --breaks 0x08072EDC
```

两者都必须是「0 命中」；任何一条真的用了这些块的路径都会命中。

### D.4 审计条目应改成的文字

`cutscene-scripts` 的 `unresolved` 改为：

> **「四个块对应哪四处场景」这个前提已被证伪**（2026-10-21）：
> 这四块是**四套 OBJ（精灵）4bpp 图块集 + 各自的 16 色调色板**
> —— VRAM 目标 `0x06016000` 落在 **OBJ 图块区**、
> 调色板目标 `0x05000380` 落在 **OBJ 调色板 RAM**，
> 都不是背景图块区。加载器 `0x08072EDC` 的四个调用点
> （`0x0807363A` / `0x08073100` / `0x0807314A` / `0x08073196`）
> 传进去的**下标 0/1/2/3 是硬编码常量**，其中 1/2/3 由一个
> **状态字节 `[r2+3]`** 选择 —— 所以这张表是**按资源档位索引**的，
> **不是按场景索引**的，「哪四处场景」这个问法不成立。
> 运行时负证据：55 个剧情场景、开机流程、真实战斗里
> 加载器**一次都没命中**，说明它属于剧情/战斗之外的第四种模式
> （关卡/过场模式），本轮探针能到达的范围内**无法触发**。

---

## E. `portrait-table` —— `param << 4` 的运行时改写（**静态闭环，运行时未命中**）

### E.1 方法

把头像加载函数 `0x08096168` 整段读完，看 `param` 从哪来、被用在哪几处。

### E.2 证据

```
0x080961D6  lsls r2, r6, #4        ; r2 = param << 4      <<< 那个「参数」
0x080961DC  ldr  r3, [pc, #0x50]   ; 0x18FF = 6144        <<< 循环上界
0x080961DE  ldrb r0, [r4]
0x080961E0  cmp  r0, #0
0x080961E2  beq  0x80961e8         ; 0 字节不动
0x080961E4  adds r0, r0, r2        ; 非 0 字节 += (param << 4)  (mod 256)
0x080961E6  strb r0, [r4]
0x080961F6  cmp  r0, r3            ; 只处理前 6144 字节
0x080961F8  ble  0x80961de
```

**同一个 `param`（r6）还决定**：

```
0x08096206  ldr  r0, [pc, #0x2c]   ; 0x05000200  BG 调色板 RAM
0x08096208  adds r5, r6, r0        ; 槽位 = 0x05000200 + param*32
0x0809620C  ldr  r0, [r1, #4]      ; 头像自己的调色板指针
0x08096210  movs r2, #0x40         ; 64 字 = 256 字节
0x08096212  bl   0x809c0e0         ; CpuSet
```

**结论**：这是一次**调色板索引平移**，不是描边、不是换色。
头像是 8bpp、索引 0..63（64 色调色板，128 字节），
引擎把整张 64 色调色板拷进 `0x05000200 + param*32` 这个槽，
同时把像素索引整体抬高 `param*16`，
让「这个头像实际用的那一段 16 色窗口」落到 0..15，
与它上传的 16 色调色板槽对齐。
**旧笔记「用途未证实（换色/描边）」作废。**

**运行时已完成（2026-10-21 晚）**：见下面的 **E'**。
（历史记录：`tools/closure_portrait_probe.py` 最早在战斗（组 9/子 0）与剧情场景 40
里一次都没命中 `0x08096202`；后来发现**剧情场景 1 与 5** 会命中。）

### E.3 可证伪测试

```
python tools\closure_portrait_probe.py --scene <有头像的对话场景> --hits 2
```

断言：VRAM 的 6400 字节 = ROM 解压结果；前 6144 字节的非 0 值全部
`+= (param<<4) (mod 256)`，后 256 字节逐字节相同。

### E.4 审计条目应改成的文字

`portrait-table` 的第一条 `unresolved` 改为：

> 「参数 << 4」的语义**已由原生代码钉死**（`0x080961D6`..`0x080961F8`）：
> 它是 `if (byte != 0) byte = (byte + (param << 4)) & 0xFF`，
> 只作用于解压后 6400 字节里的**前 6144 字节**（后 256 字节不动）。
> **同一个 `param` 决定调色板槽 `0x05000200 + param*32`**
> （整张 64 色调色板被 CpuSet 进去），
> 所以这次改写是**调色板索引平移**（把实际使用的 16 色窗口重基到 0..15），
> **不是描边、也不是换色**。旧结论「换色/描边未证实」**作废**。
> **仍缺**：一次命中头像加载器的运行时读数（VRAM 拷贝 vs ROM 解压结果逐字节比对）。

---

## E'. `portrait-table` —— `param << 4` 的运行时读数**已闭合**（2026-10-21 晚）

> 这一节把上一节的 E「仍缺」**作废**。

### E'.1 先纠正一个**模型错误**（不是数据错误）

旧工具 `tools/closure_portrait_probe.py` 拿 **VRAM `0x06011900`** 的 6400 字节
去跟「ROM 单块解压结果」比，得出 **4925 / 6400 不符** ——
这**不代表**游戏行为异常，而是**比对目标选错了**：
VRAM `0x06011900` 装的是**6 块拼好的 80×80 成品**，
它的字节布局和源图根本不是一回事（拼块按 F 项的 x/y/w/h 重排过）。

**正确的比对目标是 WRAM 暂存缓冲 `0x02002880`**：
加载器把 LZ77 结果解压到那里、做 `param<<4` 改写、再用 CpuFastSet 拷到 VRAM，
所以在拷贝那一刻，暂存缓冲**就是**「改写后的源图」。

### E'.2 运行时读数（场景 1 与场景 5 各一次）

`tools/closure_portrait_probe.py`（已改）在 `0x08096202` 断下，
读 `0x02002880` 的 6400 字节，与「ROM LZ77 解压结果」做**差分直方图**
（这样**不需要预先知道 `param`**）：

| 场景 | 条目 | ROM blob | `param<<4` | 前 6144 字节不符 | 尾部 256 字节不符 |
|---|---|---|---|---|---|
| 1 | `0x085A529C` | `0x0842F308` | **0x40**（param = 4） | **0 / 6144** ✅ | 237 |
| 5 | `0x085A54A4` | `0x084352F8` | **0x40** | **0 / 6144** ✅ | 256 |

差分直方图**只有一个非零值 0x40**，作用在 **4309 个非零字节**上，
**ROM 里为 0 的字节一个都没被改** —— 与静态推导
`if (byte != 0) byte = (byte + (param << 4)) & 0xFF` **完全吻合**。

尾部 256 字节既不是 ROM 的尾部（不符 237/256），也不是图形 ——
它是这块**共享暂存缓冲**里上一次用过的残留。
所以旧笔记「后 256 字节不动」应改写为
「**`param<<4` 只作用于前 6144 字节；尾部 256 字节不属于图形**」。

### E'.3 可证伪测试

```powershell
python tools\closure_portrait_probe.py rom\base.gba --scene 1 --json build\portrait-closure-1.json
python tools\closure_portrait_probe.py rom\base.gba --scene 5 --json build\portrait-closure-5.json
```

判据：`param_shift` 是 16 的倍数 **且** `wram_head_mismatches == 0`。
把 `param<<4` 改成一个不存在的值 → 直方图出现第二个非零值 ⇒ 门禁会咬人。

---


---

## F. `portrait-table` —— `portrait_pieces` 背后的共享图块表（**前提确认，基址未闭合**）

### F.1 方法

把 `0x4643C0` 的 120 字节按 20 字节拆开，解出每条拼块的字段；
再在 ROM 里找这张表的消费者。

### F.2 证据

**6 条 × 20 字节**（本轮解码）：

| 偏移 | 类型 | 含义 |
|---|---|---|
| +0x00 | u16 | 起始 tile 下标（0 / 8 / 24 / 40 / 56 / 72） |
| +0x02 | u16 | 0 |
| +0x04 | u16 | x 偏移（0 / 32 / 64） |
| +0x06 | u16 | y 偏移（0 / 32 / 64） |
| +0x08 | u16 | 宽（16 / 32 / 64） |
| +0x0A | u16 | 高（16 / 32 / 64） |
| +0x0C | u16 | 0x0100 |
| +0x0E | u16 | 0x0100 |
| +0x10 | u16 | 0xFF20 |
| +0x12 | u16 | 0 |

6 块拼出 80×80（块 5 = (0,0) 64×64，块 4 = (0,64) 32×16，
块 3 = (32,64) 32×16，块 0 = (64,64) 16×16，
块 2 = (64,0) 16×32，块 1 = (64,32) 16×32）。

**旧笔记的前提成立**：第 5 块从 tile 72 起、宽 64，覆盖 tile **72..135**，
超出单个头像自己那 6400 字节缓冲里的 100 张图块。

**仍未闭合**：共享图块表的**基址没能在运行时读出** ——
`0x084643C0` 在 ROM 里**没有任何字面量读者**
（`tools/consumer_locate.py::LiteralIndex.readers_of` 读数 = 0），
说明它不是被 `ldr rX,[pc,#imm]` 直接取址的，只能由消费方算出来。
运行时探针 `tools/closure_portrait_probe.py` 已经写好
（会检查拼块用到的 0..135 号图块在 VRAM OBJ 图块池 `0x06010000` 里是否非空），
但头像加载器 `0x08096202` 在已试的场景里没被触发。

### F.3 可证伪测试

```
python tools\consumer_locate.py ...   # readers_of(0x084643C0) 必须 > 0
python tools\closure_portrait_probe.py --scene <有头像的对话场景>
```

### F.4 审计条目应改成的文字

`portrait-table` 的第二条 `unresolved` 改为：

> 拼块表 `portrait_pieces`（`0x4643C0`）的结构**已解码**：
> **6 条 × 20 字节**，字段为
> 「起始 tile 下标 / x 偏移 / y 偏移 / 宽 / 高 / 0x0100 / 0x0100 / 0xFF20 / 0」。
> 6 块拼出 80×80，第 5 块覆盖 tile **72..135**，
> **确实超出单个头像自己那 100 张图块**（旧前提成立）。
> **仍未闭合**：共享图块表的**基址**没有拿到 ——
> `0x084643C0` 在 ROM 里**零字面量读者**
> （`LiteralIndex.readers_of` 读数 = 0），不是被 `ldr rX,[pc,#imm]` 直接取址的；
> 运行时探针（`tools/closure_portrait_probe.py`）已就绪，
> 但**头像加载器在已试的对话场景里没被触发**，
> 还差一次能命中它的场景。

---

## F'. `portrait-table` —— 拼块表基址**已闭合**（2026-10-21 晚）

> 这一节把上一节的 F「仍未闭合」**作废**，并给出替代结论。

### F'.1 「零字面量读者」这个前提本身是错的

`0x084643C0` 的确**没有** `ldr rX,[pc]` 形态的字面量读者 ——
但它**不是**「只能由消费方算出来」的地址。
它是一个**指针**，存放在静态描述符 `0x0846443C` 的**首字**：

```
0x08464438: 0x0000FFFF
0x0846443C: 0x084643C0   <- 拼块表基址
0x08464440: 0x0846431C
0x08464444: 0x00000000
0x08464448: 0x0000FFFF
0x0846444C: 0x00000001
0x08464450: 0x0000FFFF
0x08464454: 0x08464444   <- 另一张描述符
```

而**描述符地址 `0x0846443C` 被 7 处原生代码加载**（`ldr r0,[pc,#..]` 的池条目）：

| 指令 | 字面量池 | 所在区域 |
|---|---|---|
| `0x08077D12` | `0x08077D44` | 剧情/对话 |
| `0x08089B06` | `0x08089D44` | 剧情/对话 |
| `0x0808B356` | `0x0808B470` | 剧情/对话 |
| `0x08091036` | `0x08091064` | 剧情/对话 |
| `0x08091680` | `0x080918A0` | 剧情/对话 |
| `0x08093846` | `0x08093C0C` | 剧情/对话 |
| **`0x08096618`** | `0x0809665C` | **头像加载器**（构造 portrait 对象时把 `0x0846443C` 当参数传进去） |

⇒ **拼块表基址 = `0x084643C0`，且它是原生可达的**（7 个读者，其中一个在头像路径上）。
旧说法「零字面量读者 ⇒ 拿不到基址」把「这张表的地址不是字面量」误当成
「这张表没人用」——**表项是数据，指针才是被加载的东西**。

### F'.2 运行时读数（闭合证据）

`tools/closure_portrait_pieces.py`：开机 → 停在场景 1 → 在头像加载器的
VRAM 拷贝点 `0x08096202` 断下 → 读描述符首字 → 读 6 条记录：

```
descriptor_word = 0x084643C0      （从模拟器内存 0x0846443C 读出）
rom_bytes_equal = true             （6×20 = 120 字节与 ROM 逐字节相等）
```

6 条记录（`u16` 依次为 起始 tile / 0 / x / y / w / h / 0x0100 / 0x0100 / 0x20FF / 0）：

| 块 | 起始 tile | x | y | w | h | 覆盖的源 tile |
|---|---|---|---|---|---|---|
| 0 | 0 | 64 | 64 | 16 | 16 | 0..3 |
| 1 | 8 | 64 | 32 | 16 | 32 | 8..15 |
| 2 | 24 | 64 | 0 | 16 | 32 | 24..31 |
| 3 | 40 | 32 | 64 | 32 | 16 | 40..47 |
| 4 | 56 | 0 | 64 | 32 | 16 | 56..63 |
| 5 | 72 | 0 | 0 | 64 | 64 | 72..135 |

**无重叠拼成 80×80**（面积 256+512+512+512+512+4096 = **6400 = 80×80**）。

### F'.3 顺带钉死的池结构

源 tile 区间：0..3 / 8..15 / 24..31 / 40..47 / 56..63 / 72..135 ——
**用掉 100 张，剩下 36 个「空位」正好在 4..7 / 16..23 / 32..39 / 48..55 / 64..71**。
而头像表条目（`id*40 + expr*8`）的**第二个 u32** 指向**原始（非 LZ77）**图块数据，
`0x084098C4` 那个（被 56 条共用）正好是 **36 张图块 = 2304 字节**。
⇒ 共享图块池 = **136 张**：**100 张**来自条目 u32[0] 的 LZ77 头像
（解压正好 6400 字节 = 100 张），**36 张**空位是**表情差分**（条目 u32[1]）落的位置 ——
而表情差分只覆盖头部区域（块 0..4），不覆盖块 5 的身体区域（所以块 5 没有空位）。

### F'.4 可证伪测试

```powershell
python tools\closure_portrait_pieces.py rom\base.gba --scene 1 --json build\portrait-pieces.json
```

判据：`descriptor_word == 0x084643C0` 且 `rom_bytes_equal == true`。
改坏描述符首字 → 读数立刻不等 ⇒ 门禁会咬人。

---

## G. `story-background-table` —— 8bpp 条目用哪一路 BG、是否 256 色（**已闭环**）

### G.1 方法

1. 静态读底图加载器 `0x08088348` 的 `BGxCNT` 写入；
2. 运行时在 `0x0808841A`（`BGxCNT` 刚写完之后）抓 IO 寄存器；
3. 用 `tools/closure_scene_sweep.py` 遍历 55 个剧情场景，
   记录每次底图加载的**条目下标**与 **BG 号**。

### G.2 证据

**静态**：

```
0x0808835C  lsls r1, r1, #0x18 / lsrs r7, r1, #0x18   ; r7 = BG 号
0x08088374  lsls r5, r0, #4                            ; 条目步长 16 字节
0x080883AA  ldrb r0, [r2, #0xc]                       ; 条目+0x0C
0x080883AE  bne  0x80883cc                           ; 非 0 -> 8bpp 分支
0x080883E4  ldr  r2, [pc, #0x50]                      ; 0x04000000 DISPCNT
0x080883E6  movs r0, #0x80 / lsls r0, r0, #1          ; 0x100
0x080883EA  lsls r0, r7                               ; DISPCNT |= 1 << (8+BG)
0x080883F2  lsls r0, r7, #1 / ldr r5, [pc, #0x44]      ; &BGxCNT
0x08088408  ldrb r0, [r0, #0xc]
0x0808840C  beq  0x8088412                           ; 4bpp -> 跳过
0x0808840E  movs r0, #0x80                            ; <<<< bit 7 = 256 色模式
0x08088410  orrs r3, r0
0x08088418  strh r0, [r4]                             ; 写 BGxCNT
```

**更正**：GBA 的 `BGxCNT` **bit 7（0x80）**才是「256 色 / 8bpp」位；
**bit 8 是屏幕基址块的最低位**。旧审计写的「`BGxCNT` bit8」**作废**。

**运行时**（IO 抓取）：

| 场景 | 底图条目 | 条目+0x0C | BG0CNT | bit7 |
|---|---|---|---|---|
| 40 | 1 | 0x00 | `0x0007` | 0（4bpp） |
| 50 | 9 | 0x01 | **`0x0087`** | **1（256 色）** |
| 47 | 96 | 0xCB | **`0x0087`** | **1（256 色）** |

`DISPCNT` = `0x1F40`（bit 8 = BG0 使能）。
55 个剧情场景里**每一次底图加载的 BG 号都是 0** ⇒ **8bpp 底图走 BG0**。

底图表 `0x0859903C` 共 320 条（16 字节/条），
其中 **192 条**的 `条目+0x0C != 0`（8bpp），4bpp 条目该字节为 0。

### G.3 可证伪测试

```
python tools\closure_battle_probe.py --scene 50 --breaks 0x0808841A --dump 0x04000000:0x10
python tools\closure_battle_probe.py --scene 40 --breaks 0x0808841A --dump 0x04000000:0x10
```

断言：8bpp 场景的 `BG0CNT & 0x80 != 0`，4bpp 场景 `== 0`；
把 `0x0087` 的 0x80 去掉断言立刻失败。

### G.4 审计条目应改成的文字

`story-background-table` 的 `unresolved` **清空**，`corrections` 追加：

> 8bpp 底图条目用哪一路 BG、是否开 256 色模式**已闭环**（2026-10-21）：
> 底图加载器 `0x08088348` 的第二个参数就是 **BG 号**（`0x0808835C`），
> 运行时遍历 **55 个剧情场景**读到**每一次都是 BG0**
> （`DISPCNT` bit 8，`0x080883EA` 写 `1 << (8+BG)`），
> **8bpp 底图走 BG0**。
> 256 色模式确实开着，但**位号是 `BGxCNT` bit 7（0x80），不是 bit 8**
> （bit 8 是屏幕基址块的最低位）——
> 写入点在 `0x0808840E`（`movs r0,#0x80` / `orrs r3,r0`），
> 4bpp 分支（`0x0808840C beq`）不置这一位。
> 运行时 IO 抓取：8bpp 场景（50 / 47）`BG0CNT = 0x0087`（bit7 = 1），
> 4bpp 场景（40）`BG0CNT = 0x0007`（bit7 = 0），`DISPCNT = 0x1F40`。
> 底图表 320 条里有 **192 条**是 8bpp（`条目+0x0C != 0`）。

---

## 8. 回归结果

见本轮工作报告。
