# m4a block 表逐字段拆解（轨数据 = 「块」）— 2026-10-21

**一句话**：本 ROM 的 m4a **没有**独立的「block 链表」结构。
所谓「block 表」就是 **SongHeader 里的轨道指针表**（`track_ptr[track_count]`），
每个指针指向一段**命令字节流**，这段字节流就是 m4a 语境下的一个 **block / sound data**，
它由 **FINE（`0xB1`）** 结束。本文把 SongHeader 与 block 的每一个字段
都用**本 ROM 自己的引擎反汇编**钉死，给出可证伪的检验，并用
`tools/m4a_block_table.py` 做**字节级往返**与**渲染器逐事件交叉比对**。

- 工具：`tools/m4a_block_table.py`（新增）
- 证据等级：ROM 静态反汇编（L1）+ 可执行往返自检（自检内含）+ 与
  `tools/audio_song_export.py` 的逐事件交叉比对
- 所有地址都是本 ROM 的 ARM 地址（Thumb 代码，入口偶地址）
- 覆盖 **sound id 1 / 2 / 8 / 11 / 14**（= 旧的 `story` / `story-b` /
  `story-c` / `story-d` / `story-e` 五个 legacy bank）

---

## 0. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'

# (1) 本文的工具自检：五首歌 decode -> encode 字节级往返 + 引擎走查 +
#     跳转目标校验 + 与渲染器逐事件比对 + 块级重写往返
python tools\m4a_block_table.py rom\base.gba --self-test

# (2) 导出某一首歌的 block 结构（JSON + 终端摘要）
python tools\m4a_block_table.py rom\base.gba --sound-id 1 --json build\audio\blocks_001.json

# (3) 反汇编本文引用的任意一段引擎代码
python tools\disasm_thumb.py rom\base.gba 0x0809A4E8 --before 0 --size 0x50
python tools\disasm_thumb.py rom\base.gba 0x0809B25C --before 0 --size 0x30

# (4) 本文用到的可复现探针（build/ 下，不进版本库）
python build\m4a_engine_dump.py     # 引擎区间反汇编 -> build/m4a_engine.txt
python build\m4a_cmdtable.py        # 命令表 30 项 + 各处理函数 -> build/m4a_cmdtable.txt
python build\m4a_divergence.py      # 分歧点证据 -> build/m4a_divergence.txt
python build\m4a_numbers.py         # 汇总数字 -> build/m4a_numbers.txt
python build\m4a_extra_events.py    # 渲染器多出的音符 -> 终端
python build\m4a_negative_test.py   # 负例：改坏一个 GOTO 目标，自检必须 exit 1

# (5) 负例（证明自检真的会失败）
# build\m4a_negative_test.py 会把 sound id 1 track 7 的 GOTO 目标改坏一字节，
# 然后跑自检：退出码必须是 1，并报
#   ! sound id 1: the renderer cannot execute the decoded block:
#     track 0x536337 jumped to 0x5363BE, which is not a command boundary
```

---

## 1. 结论摘要（TL;DR）

1. **「block 表」= SongHeader**。`track_count` 个轨道指针，每个指针就是一个 block。
2. **block 没有自己的头**，第一个字节就是命令；block 由 **FINE（`0xB1`）** 结束，
   FINE 之后到下一个 block / SongHeader 之间是 **`0x00` 填充**。
3. **opcode 分四类**（引擎 `0x0809A4EC` / `0x0809A4FE` / `0x0809A514`）：
   `0x00..0x7F` 续写字节、`0x80..0xB0` WAIT、`0xB1..0xCE` 命令表、`0xCF..0xFF` NOTE。
4. **命令表在 `0x08464534`**，30 项，索引 = `opcode - 0xB1`，表项是带 Thumb 位的处理函数地址。
5. **跳转目标是小端 32 位 ROM 地址**（**更正**旧笔记的「大端」说法）。
6. **「running opcode」是通用机制**：引擎对**所有 `>= 0xBD` 的 opcode** 都保存
   running opcode，续写字节（`< 0x80`）会被当成 **running opcode** 的第一个操作数。
   现有 `tools/extract_audio.py` 只保存「running **note**」，因此在五首歌的
   **101 个字节**上与 ROM 不一致 —— 详见 §8。
7. **块级重写可行**：block 的字节预算 = 原 block 自己的跨度；
   也可以把新 block 写进 `notes/free-space.md` 记录的空闲区并改写 SongHeader 的轨道指针。

---

## 2. SongHeader：逐字段

| 偏移 | 大小 | 含义 | 引擎读取处（证明） |
|---|---|---|---|
| `+0x00` | u8 | **轨道数** `track_count` | `0x0809B25C ldrb r1, [r7]`；`0x0809B25E cmp r6, r1` / `0x0809B28A ldrb r0, [r7]` 循环 `track_count` 次 |
| `+0x01` | u8 | **未知 / 本 ROM 未使用**（见 §2.2） | 引擎在任何路径都**不读**这个字节 |
| `+0x02` | u8 | **优先级** `priority` | `0x0809B208 ldrb r2, [r7, #2]`；`0x0809B22C ldrb r0, [r7, #2]`；`0x0809B230 ldrb r0, [r5, #9]`（播放器当前优先级）→ `0x0809B232 cmp r0, r2` / `0x0809B234 bhi`（优先级不够就拒绝启动） |
| `+0x03` | u8 | **标志位**，bit 7 = 启用混响 | `0x0809B2B6 movs r0, #0x80` / `0x0809B2B8 ldrb r1, [r7, #3]` / `0x0809B2BA ands r0, r1` / `0x0809B2C0 ldrb r0, [r7, #3]` / `0x0809B2C2 bl 0x0809AFD8`（开混响） |
| `+0x04` | u32 | **音色组指针** `voicegroup_ptr`（12 字节/条的音色表） | `0x0809B242 ldr r0, [r7, #4]` → `0x0809B244 str r0, [r5, #0x30]`（存进播放器）；`0x0809A320 ldr r3, [r0, #0x30]`（VOICE 时取音色） |
| `+0x08` | u32 × `track_count` | **block 指针表** `track_ptr[i]` | `0x0809B27C adds r0, r7, #0` / `0x0809B27E adds r0, #8` / `0x0809B27A lsls r1, r6, #2` / `0x0809B280 adds r0, r0, r1` / `0x0809B282 ldr r0, [r0]` → `0x0809B284 str r0, [r4, #0x40]` |

### 2.1 指针表 → 通道读指针（block 的入口）

`track_ptr[i]` 被直接写进通道结构的 `+0x40`，而 `+0x40` 就是**引擎的字节流读指针**：

```
; 0x0809B282  ldr  r0, [r0]        ; r0 = SongHeader.track_ptr[i]
; 0x0809B284  str  r0, [r4, #0x40] ; channel->data_ptr = track_ptr[i]

; 0x0809A250  ldr  r2, [r1, #0x40] ; 取当前字节
; 0x0809A252  adds r3, r2, #1
; 0x0809A254  str  r3, [r1, #0x40] ; 读指针 +1
; 0x0809A256  ldrb r3, [r2]
```

**结论**：block **没有自己的头**，第一个字节就是命令。
`track_ptr[i]` 既是「block 的起点」也是「block 的第一条命令」。

**可证伪检验**：若 `track_ptr[i]` 指向的不是命令流，`0x0809A250` 读到的第一个字节
就不是合法 opcode，五首歌都会立刻跑飞；实测五首歌的 45 个 block 全部解码成功
且逐事件与渲染器一致。

### 2.2 `+0x01` 这个字节：本 ROM 里是死的

* 全 ROM 159 个 sound id 的 SongHeader，`+0x01` **全部为 0**；
* 引擎的反汇编里**没有任何一条指令读 `[header, #1]`**
  （只有 `[r7]`、`[r7, #2]`、`[r7, #3]`、`[r7, #4]`、`[r7, #8]`）。

**结论**：本 ROM 的 m4a 引擎**不读**这个字段。
通用 m4a 文档把这个位置叫 `blockCount`，但**在本 ROM 里它是未使用字段**，
本文按事实记作「未知 / 未使用」，**不**臆断语义。

> **可证伪检验**：若某个 sound id 的 `+0x01` 非 0 而引擎行为不变，
> 则该字段确实未被使用；反之若改动一个字节就改变播放结果，则本结论被推翻。

---

## 3. block（轨道字节流）的命令编码

引擎的取指循环（**这是整张表的钥匙**）：

```
; 0x0809A4E8  ldr  r2, [r5, #0x40]   ; 读指针
; 0x0809A4EA  ldrb r1, [r2]          ; 当前字节
; 0x0809A4EC  cmp  r1, #0x80
; 0x0809A4EE  bhs  0x809a4f4         ; >= 0x80 : 是 opcode
; 0x0809A4F0  ldrb r1, [r5, #7]      ; <  0x80 : 用「running opcode」
; 0x0809A4F2  b    0x809a4fe
; 0x0809A4F4  adds r2, #1
; 0x0809A4F6  str  r2, [r5, #0x40]   ; 消费掉 opcode 字节
; 0x0809A4F8  cmp  r1, #0xbd
; 0x0809A4FA  blo  0x809a4fe
; 0x0809A4FC  strb r1, [r5, #7]      ; running opcode = 当前 opcode（仅 >= 0xBD）
; 0x0809A4FE  cmp  r1, #0xcf
; 0x0809A500  blo  0x809a514
;             ; ---------- 0xCF..0xFF : NOTE ----------
; 0x0809A514  cmp  r1, #0xb0
; 0x0809A516  bls  0x809a536         ; ---------- 0x80..0xB0 : WAIT ----------
;             ; ---------- 0xB1..0xCE : 命令表 ----------
; 0x0809A518  adds r0, r1, #0
; 0x0809A51A  subs r0, #0xb1        ; 索引 = opcode - 0xB1
; 0x0809A520  ldr  r3, [r3, #0x34]   ; 命令处理表指针（song + 0x34）
; 0x0809A522  lsls r0, r0, #2
; 0x0809A524  ldr  r3, [r3, r0]      ; handler = table[opcode - 0xB1]
```

### 3.1 四个 opcode 区间（256 个取值全部有归属）

| 区间 | 数量 | 类别 | 处理方式 |
|---|---|---|---|
| `0x00..0x7F` | 128 | **续写字节** | 不消耗读指针；当作 **running opcode** 的操作数（`0x0809A4F0`） |
| `0x80..0xB0` | 49 | **WAIT** | 时值 = `duration_table[opcode - 0x80]`（`0x0809A536 ldr r0, [pc, #0x150]` → `0x084647A8`） |
| `0xB1..0xCE` | 30 | **命令表命令** | `handler = command_table[opcode - 0xB1]`（表在 `0x08464534`） |
| `0xCF..0xFF` | 49 | **NOTE** | 时值 = `duration_table[opcode - 0xCF]`（`0x0809A508 subs r0, #0xcf` / `0x0809A720` / `0x0809A724`） |

> **一张表服务两类 opcode**：`duration_table`（`0x084647A8`，49 字节）同时给
> WAIT（`opcode - 0x80`）和 NOTE（`opcode - 0xCF`）用。
> 所以 NOTE `0xCF` 的时值是 `table[0] = 0` tick（零长音符），
> `0xD0` 是 `table[1] = 1` tick，`0xE7` 是 `table[24] = 24` tick。

**可证伪检验**：若 opcode 空间不是这四段，`0x0809A4EC` / `0x0809A4FE` / `0x0809A514`
三处比较就不可能覆盖全部 256 个取值；实测五首歌的 6333 条命令**没有一条**
落在四段之外。

### 3.2 NOTE 的 0..3 个可选参数字节

```
; 0x0809A728  ldr  r3, [r5, #0x40]
; 0x0809A72A  ldrb r0, [r3]        ; 第 1 个可选字节
; 0x0809A72C  cmp  r0, #0x80
; 0x0809A72E  bhs  0x809a74e       ; >= 0x80 -> 没有参数
; 0x0809A730  strb r0, [r5, #5]     ; channel[5] = key
; 0x0809A732  adds r3, #1
; 0x0809A734  ldrb r0, [r3]        ; 第 2 个可选字节
; 0x0809A736  cmp  r0, #0x80
; 0x0809A738  bhs  0x809a74c
; 0x0809A73A  strb r0, [r5, #6]     ; channel[6] = velocity
; 0x0809A73C  adds r3, #1
; 0x0809A73E  ldrb r0, [r3]        ; 第 3 个可选字节
; 0x0809A740  cmp  r0, #0x80
; 0x0809A742  bhs  0x809a74c
; 0x0809A744  ldrb r1, [r5, #4]
; 0x0809A746  adds r1, r1, r0       ; duration += gate
; 0x0809A748  strb r1, [r5, #4]
; 0x0809A74A  adds r3, #1
; 0x0809A74C  str  r3, [r5, #0x40]  ; 读指针跳过这些参数
```

**结论**：NOTE 后面**连续**跟着最多 3 个 `< 0x80` 的字节，依次是
**key / velocity / gate**；遇到 `>= 0x80` 就停。

> **注意**：没有 key 参数的 NOTE **不会**把 `channel[5]` 清零，
> 于是它沿用上一个音的 key。现有渲染器把这种音符的 key 记成 `0`
> （`tools/audio_song_export.py` 的 `key = args[0] if len(args) >= 1 else 0`），
> 这是**渲染器模型**与 ROM 的差异，不影响 block 格式本身。

### 3.3 「running opcode」（续写机制）

* running opcode 只在 **opcode >= 0xBD** 时被写入（`0x0809A4F8 cmp r1, #0xbd` /
  `0x0809A4FC strb r1, [r5, #7]`）。
* 当读指针处的字节 `< 0x80` 时，引擎**不消费**它，而是用 running opcode 重新进 handler，
  该字节本身成为这个命令的**第一个操作数**。

**这意味着**：一条 NOTE 后面如果跟了 **4 个以上** `< 0x80` 的字节，
第 4 个字节会**开启一条新的、同 duration 索引的 NOTE**（key 不同）；
一条 EOT / MOD 后面跟 `< 0x80` 字节，则该字节是 **EOT 的 key** 或 **MOD 的值**。

---

## 4. 命令表（`0x08464534`，30 项，opcode `0xB1`..`0xCE`）

表项是 **带 Thumb 位（bit0=1）的处理函数地址**，索引 = `opcode - 0xB1`
（`0x0809A51A subs r0, #0xb1` / `0x0809A522 lsls r0, r0, #2` / `0x0809A524 ldr`）。
下表全部由 `0x08464534` 的 30 个 u32 与各处理函数自身的反汇编得出，
并由 `tools/m4a_block_table.py::verify_command_table` 每次自检时核对。

| opcode | handler | 名字 | 操作数字节 | 引擎里的落点 |
|---|---|---|---|---|
| `0xB1` | `0x0809A1EC` | **FINE**（停止该播放器的全部通道） | 0 | `0x0809A1EC` 起 |
| `0xB2` | `0x0809A25C` | **GOTO** | 4（LE 目标地址） | `0x0809A276 str r0, [r1, #0x40]` |
| `0xB3` | `0x0809A27C` | **PATT** | 4（LE 目标地址） | `0x0809A28A str r2, [r3, #0x44]`（压栈） |
| `0xB4` | `0x0809A298` | **PEND** | 0 | `0x0809A2A8 str r2, [r1, #0x40]`（弹栈） |
| `0xB5` | `0x0809A2AC` | **REPT** | 1（count）+ 4（LE 目标地址） | `0x0809A2D2 adds r2, #5` |
| `0xB6..0xB9` | `0x0809A1EC` | **保留**（与 FINE 同一处理函数） | 0 | — |
| `0xBA` | `0x0809A2DC` | **PRIO** | 1 | `0x0809A2E2 strb r3, [r1, #0x1D]` |
| `0xBB` | `0x0809A2E8` | **TEMPO** | 1 | `0x0809A2F0 strh r3, [r0, #0x1C]` |
| `0xBC` | `0x0809A2FC` | **KEYSH** | 1 | `0x0809A302 strb r3, [r1, #0xA]` |
| `0xBD` | `0x0809A310` | **VOICE** | 1（音色序号） | `0x0809A31A lsls r2, r3, #1` … `0x0809A320 ldr r3, [r0, #0x30]` |
| `0xBE` | `0x0809A340` | **VOL** | 1 | `0x0809A346 strb r3, [r1, #0x12]` |
| `0xBF` | `0x0809A354` | **PAN** | 1（−0x40） | `0x0809A35C strb r3, [r1, #0x14]` |
| `0xC0` | `0x0809A368` | **BEND** | 1（−0x40） | `0x0809A370 strb r3, [r1, #0xE]` |
| `0xC1` | `0x0809A37C` | **BENDR** | 1 | `0x0809A382 strb r3, [r1, #0xF]` |
| `0xC2` | `0x0809A970` | **LFOS** | 1 | `0x0809A976 strb r3, [r1, #0x19]` |
| `0xC3` | `0x0809A390` | **LFODL** | 1 | `0x0809A396 strb r3, [r1, #0x1B]` |
| `0xC4` | `0x0809A984` | **MOD** | 1 | `0x0809A98A strb r3, [r1, #0x17]` |
| `0xC5` | `0x0809A39C` | **MODT** | 1 | `0x0809A3A8 strb r3, [r1, #0x18]` |
| `0xC6`,`0xC7` | `0x0809A1EC` | **保留** | 0 | — |
| `0xC8` | `0x0809A3B4` | **TUNE** | 1（−0x40） | `0x0809A3BC strb r3, [r1, #0xC]` |
| `0xC9..0xCB` | `0x0809A1EC` | **保留** | 0 | — |
| `0xCC` | `0x0809A3C8` | **MEMACC** | 1（表下标） | `0x0809A3D8 strb r3, [r0]` |
| `0xCD` | `0x0809A1EC` | **保留** | 0 | — |
| `0xCE` | `0x0809A908` | **EOT** | 0 或 1（key，`< 0x80`） | `0x0809A912 strb r3, [r1, #5]` |

> **重要更正**：`notes/evidence/audio-song-export-20261021.md` §2.8 写的是
> 「读 4 字节**大端** ROM 指针」。**这是错的**。引擎的移位链是
> `r0 = b3<<24 | b2<<16 | b1<<8 | b0`，其中 `b0 = r2[0]`、`b1 = r2[1]`、
> `b2 = r2[2]`、`b3 = r2[3]` —— **ROM 里第 0 字节是最小有效字节 → 小端**。
> 现有工具 `tools/extract_audio.py` 用的 `struct.unpack_from("<I", ...)` 是对的。
> **可证伪检验**：五首歌全部 45 个 block 的 GOTO / PATT / REPT 目标，
> 按小端读出来**全部落在命令边界上**（`0x0809A4E8` 之后的第一条指令就会读到一个
> 非法 opcode）；按大端读全部得到 `0x4xxxxxxx` 这种不在 ROM 内的地址。

---

## 5. 循环结构

| 命令 | 语义 | 引擎证据 |
|---|---|---|
| **GOTO** `0xB2` | 读指针 = 4 字节 LE 目标地址（绝对 ROM 地址） | `0x0809A25E..0x0809A276` |
| **PATT** `0xB3` | 压入返回地址（= 读指针 + 4），跳到目标地址；**栈深上限 3**，越界直接停掉整个播放器 | `0x0809A27E cmp r2, #3` / `0x0809A280 bhs 0x809a294` → `0x809a1ec` |
| **PEND** `0xB4` | 弹栈；**栈空时不是错误**，而是「继续执行下一条」 | `0x0809A29A cmp r2, #0` / `0x0809A29C beq 0x809a2aa` |
| **REPT** `0xB5` | `[count:1][target:4]`；`count == 0` 时引擎**跳进 target 无限循环**；`count != 0` 时重复满则读指针 += 5 | `0x0809A2B2 cmp r3, #0` / `0x0809A2B4 bne 0x809a2bc`；`0x0809A2C8 cmp ip, r3` / `0x0809A2CA bhs 0x809a2ce` → `0x0809A2D2 adds r2, #5` |

> REPT 的重复计数器在 `channel + 0x03`（`0x0809A2BC ldrb r3, [r1, #3]`），
> PATT 栈深在 `channel + 0x02`（`0x0809A27C ldrb r2, [r1, #2]`）。

---

## 6. block 的边界与 padding

* **block 的结束标记是 FINE**（`0xB1`）。五首歌 45 个 block，**每个 block 恰好一个
  FINE，且都在 block 的最后一个字节**。
* FINE 之后到下一个 block 起点 / SongHeader 之间是 **`0x00` 填充**，
  长度 = 让下一个 SongHeader 4 字节对齐所需的字节数（0～3 字节）。
  只有每首歌的**最后一个** block 后面有填充（因为它后面紧跟 SongHeader）。

> **可证伪检验**：若 block 没有 FINE 结束标记，`0x0809A1EC` 永远不会执行，
> 播放器的通道不会停止；实测 45 个 block 的最后一个字节都是 `0xB1`。

---

## 7. 往返自检结果（decode → encode → 字节相同）

`tools/m4a_block_table.py --self-test` 的硬性检查（任何一条不过就 **exit 1**）：

| 检查 | 内容 | 结果 |
|---|---|---|
| 命令表 | `0x08464534` 的 30 项与本文的处理函数表一致 | ✅ 30/30 |
| **往返** | 每个 block：解码成字段 → 只用字段重新编码 → 与 ROM 字节**逐字节相同** | ✅ 45/45 block，9952 字节 |
| **引擎走查** | 第二套独立实现按引擎的读指针语义重新切分字节流，必须与字段解码逐命令一致，且正好消费掉整个 block | ✅ 45/45 |
| **跳转目标** | 所有 GOTO / PATT / REPT 目标必须落在命令边界上 | ✅ 45/45 |
| **重写往返** | 改写 → 读回 → 必须解出作者写的命令列表 | ✅ 3 种模式（见 §9） |
| **负例** | 改坏一个 GOTO 目标字节后重跑，自检必须 **exit 1** | ✅ exit 1（`build/m4a_negative_test.py`） |

| sound id | legacy bank | SongHeader | block 数 | block 字节 | 命令数 | 事件数 |
|---|---|---|---|---|---|---|
| 1 | `story` | `0x536368` | 8 | 1643 | 1017 | 1956 |
| 2 | `story-b` | `0x536BC4` | 10 | 2098 | 1323 | 1892 |
| 8 | `story-c` | `0x538FEC` | 9 | 1856 | 1159 | 1882 |
| 11 | `story-d` | `0x53AB74` | 10 | 2397 | 1602 | 2448 |
| 14 | `story-e` | `0x53C3BC` | 8 | 1958 | 1232 | 2274 |
| **合计** | | | **45** | **9952** | **6333** | **10452** |

五首歌用到的 opcode（**没有任何保留 opcode 被使用**）：

```
0x81x94  0x82x51  0x83x140 0x84x230 0x86x414 0x88x101 0x89x11  0x8Ax2
0x8Bx24  0x8Cx952 0x8Ex2   0x8Fx9   0x90x22  0x92x94  0x94x24  0x97x8
0x98x237 0x99x7   0x9Ax1   0x9Bx8   0x9Cx23  0x9Dx3   0x9Ex6   0xA0x91
0xA4x3   0xA5x2   0xA8x15  0xA9x2   0xABx5   0xACx11  0xADx4   0xAEx1
0xAFx1   0xB0x215 0xB1x45  0xB2x45  0xB3x357 0xB4x148 0xBBx5   0xBCx45
0xBDx45  0xBEx45  0xBFx45  0xC0x74  0xC2x6   0xC4x248 0xCEx16  0xCFx10
0xD1x57  0xD2x136 0xD3x274 0xD5x483 0xD7x59  0xD8x4   0xDBx1035 0xDFx8
0xE1x36  0xE3x18  0xE7x132 0xE9x7   0xEAx2   0xEBx25  0xEDx6   0xEFx53
0xF3x3   0xF5x2   0xF7x26  0xFBx9   0xFFx11
```

---

## 8. 与 `tools/audio_song_export.py` 的比对

`tools/m4a_block_table.py::compare_with_renderer` 把两套解码器放在一起比：

* **字节切分**：每个字节是「opcode 字节」还是「操作数字节」——
  **45/45 个 block 完全一致**。这证明两个解码器把字节流切成了同一批命令。
* **opcode 归属**：每个操作数字节归哪个 opcode —— **101 个字节不一致**。
* **事件流**：45 条轨道里有 **11 条**的流不同（两边的音符总数 10452）。

### 8.1 分歧的根因：running opcode 的适用范围

`tools/extract_audio.py::decode_track` 只在遇到 **NOTE** 时更新 running opcode，
而引擎对**所有 `>= 0xBD` 的 opcode** 都更新（`0x0809A4F8 cmp r1, #0xbd` /
`0x0809A4FC strb r1, [r5, #7]`）。于是：

| 位置 | ROM（本工具） | 现有解码器 |
|---|---|---|
| `0x53653D`（sound id 2 track 2） | 续写字节 → running opcode = `0xC4` **MOD** | 续写字节 → running note = `0xEB` **NOTE** |
| `0x53A4AC`（sound id 11 track 3） | 续写字节 → running opcode = `0xCE` **EOT** | 续写字节 → running note = `0xCF` **NOTE** |

分歧字节按 running opcode 分类：`0xC4`（MOD）**93** 个、`0xCE`（EOT）**8** 个，
合计 **101** 个，分布在 **11 条轨道**上。

### 8.2 判定：**现有解码器错，ROM 对**

四条互相独立的证据：

1. **指令本身**：`0x0809A4F8 cmp r1, #0xbd` 的比较值是 `0xBD`，不是 `0xCF`。
   若 running opcode 只限 NOTE，比较值必然是 `0xCF`。**这一条就足以判定。**
2. **EOT 处理函数自己就吃续写字节**：`0x0809A90A ldr r2, [r1, #0x40]` /
   `0x0809A90C ldrb r3, [r2]` / `0x0809A90E cmp r3, #0x80` / `0x0809A912 strb r3, [r1, #5]`
   —— EOT 的可选 key 字节用的就是「`< 0x80` 才是参数」这条规则。
   如果续写字节只服务于音符，EOT 就不可能有可选 key。
3. **数据自证（和声）**：sound id 11 track 3 的 `0x53A4A0` 起是
   ```
   CF 2F 3C   NOTE key 0x2F
   CF 32      NOTE key 0x32
   CF 36      NOTE key 0x36
   B0         WAIT 96
   B4         PEND
   AD         WAIT 84
   CE 2F      EOT key 0x2F
   32 36      ->  ROM: EOT key 0x32, EOT key 0x36
   82         WAIT 2
   ```
   `CE 2F 32 36` 正好**释放刚刚按下的 0x2F / 0x32 / 0x36 三个音**（一个和弦）。
   现有解码器把它读成「EOT(0x2F) + 一个 key=0x32 的新音符」，
   那个音符永远不会被关掉 —— 和弦不会被释放。
4. **不可能的音符**：按现有解码器，sound id 2 track 2 会多出 **28 个音符**
   （其中 **7 个 key = 0x00**，即最低音，不是音乐；其余的 key 也只是
   MOD 的参数值 0x40/0x43/0x45/… 被当成了音高）。
   key 0 不是音乐。

> **本工具不修改 `tools/extract_audio.py` / `tools/audio_song_export.py`**
> （不在本次的文件所有权范围内）。自检把这类分歧**单独列出并解释**，
> 而不是当成自己的失败；任何**不能**用 running opcode 解释的分歧
> （字节切分不同、opcode 归属不同但没有续写字节）都会让自检 **exit 1**。

### 8.3 附带发现：渲染器对「无 key 音符」的建模与 ROM 不同

§3.2 已说明：ROM 里没有 key 参数的 NOTE **沿用上一个音的 key**；
`tools/audio_song_export.py` 把这种音符的 key 记成 `0`
（`key = args[0] if len(args) >= 1 else 0`）。这是**渲染器模型**问题，
不是 block 格式问题，本次未改动。

---

## 9. 块级重写（bonus）：可行，尺寸预算如下

`tools/m4a_block_table.py` 提供三个可执行的重写模式：

| 模式 | 函数 | 预算 |
|---|---|---|
| **原地改写** | `rewrite_track_block` | **原 block 自己的跨度**（从轨道指针到它的 FINE，含 FINE）。新 block 必须放得下；剩余空间补 `0x00`（与 ROM 自己的 padding 一致） |
| **原地重排** | 同上 | 同上；命令列表可增删，只要新块更短 |
| **新块 + 改指针** | `rewrite_track_block_at` + `find_free_slot` | 写到 `notes/free-space.md` 记录的空闲区 `0x5DFBEC..0x5FFFFF`（~128 KB），再把 `SongHeader.track_ptr[i]` 改指过去。旧 block 原封不动，改回去只需还原 4 字节指针 |

**引擎接受空闲区地址**：字节读取例程 `0x0809A234` 的地址检查是
`0x0809A238 lsrs r0, r2, #0x19` / `0x0809A23A bne 0x809a248` ——
地址 `>= 0x02000000` 一律放行（`0x085DFBEC` 满足），
低于 `0x02000000` 才被清零。所以空闲区里的 block 和原生 block 读法完全一样。

**原地改写预算（每首歌每个 block 的字节数）**：

| sound id | 每个 block 的字节数 | 最小 | 最大 | 合计 |
|---|---|---|---|---|
| 1 | 214, 291, 308, 214, 213, 230, 125, 48 | 48 | 308 | 1643 |
| 2 | 166, 217, 253, 339, 148, 287, 184, 72, 172, 260 | 72 | 339 | 2098 |
| 8 | 242, 231, 205, 257, 164, 301, 147, 98, 211 | 98 | 301 | 1856 |
| 11 | 259, 186, 185, 111, 335, 290, 256, 267, 172, 336 | 111 | 336 | 2397 |
| 14 | 279, 411, 205, 171, 133, 260, 209, 290 | 133 | 411 | 1958 |

**约束**：

* 新 block **必须以 FINE（`0xB1`）结尾** —— 否则引擎会读进下一个 block。
  工具会拒绝不含 FINE 的命令列表。
* 空闲区 `0x5DFBEC..0x5FFFFF` **与 `tools/import_dialogue_var.py` 的变长对话文本
  共用**（见 `notes/free-space.md`）。音频侧的分配器必须与它协商，
  不能各自从头扫。本工具的 `find_free_slot` 只是**示例分配器**，
  没有跨工具的全局账本。

---

## 10. 仍然开放的问题

1. `SongHeader + 0x01` 的语义未证实（本 ROM 全部为 0 且引擎不读）。
2. `0xB6..0xB9` / `0xC6` / `0xC7` / `0xC9..0xCB` / `0xCD` 这些保留 opcode
   在本 ROM 里与 FINE 同处理函数；**写回时能否使用**未证实（保守做法：不用）。
3. `MEMACC`（`0xCC`）写入的那张表在 ROM 里的确切位置与语义未逐字段拆解。
4. LFO / MOD 调制链（`0xC2` / `0xC3` / `0xC4` / `0xC5`）的运行时行为未建模
   （`0xC4` 只落地 `channel + 0x17`）。
5. 现有渲染器把「无 key 音符」的 key 记成 `0`，与 ROM 的「沿用上一个音」不同（§8.3）。
6. 现有渲染器的 running-opcode 模型与 ROM 不同（§8.2），**本次未修**，
   需要改 `tools/extract_audio.py::decode_track` 的 running 状态。
7. block 的**字节长度没有长度字段**：block 的边界由 FINE 决定，
   而「下一个 block 起点」要靠全 ROM 扫描所有轨道指针才能得到。

---

## 11. 需要别人改动的地方（本次不在文件所有权范围内）

`tools/completion_audit.py` 里的 6 条审计项是硬编码的，本次**不得修改**
（见任务的所有权限制）。需要拥有者做：

1. **`story` / `story-b` / `story-c` / `story-d` / `story-e`**（`tools/completion_audit.py`
   约 1883 行，`LEGACY_REIDENTIFIED` 分支）：删掉
   `{"type": "ambiguity", "text": "轨数据的块级格式（m4a 的 block 表）未逐字段拆解"}`，
   并在 `spec["probes"]` 里加上
   `{"kind": "tool", "path": "tools/m4a_block_table.py"}`、
   `{"kind": "note", "path": "notes/evidence/m4a-block-table-20261021.md"}`、
   `{"kind": "code", "path": "notes/evidence/m4a-block-table-20261021.md",
   "need": ["0x08464534", "0x0809A4E8", "0x0809B25C"], "address_required": False}`。
2. **`sound-id-table`**（约 205 行）：删掉
   `{"type": "capability", "text": "**块级（block）轨道的重写不支持** …"}`，
   并把 `tools/import_audio_song.py` 的说明改成「现在可以重写块级轨道：
   见 `tools/m4a_block_table.py::rewrite_track_block` / `rewrite_track_block_at`」。
3. `tools/import_audio_song.py` 本身仍只允许「复用原生曲目块」。
   要真正支持块级重写，它应改为调用
   `tools/m4a_block_table.py` 的重写函数（或共享同一份解码逻辑）。
   本次按所有权限制未改动该文件。
4. `tools/extract_audio.py::decode_track` 的 running 状态应改成
   「所有 `>= 0xBD` 的 opcode 都更新 running opcode」（§8.2）。
   本次按所有权限制未改动该文件；改动后
   `tools/audio_song_export.py --self-test` 的事件数会变，需要重新核对 PSG 校验。

---

## 2026-10-21 追加（仓库所有者执行）：§11 的 4 条待办**已全部落地**

§11 列的、需要所有者动手的 4 件事，现在都做完了：

1. **§11.4 —— `tools/extract_audio.py::decode_track` 的 running 状态已修。**
   现在是「**所有 `>= 0xBD` 的 opcode 都更新 running opcode**」：

   ```python
   if explicit:
       cursor += 1
       if opcode >= 0xBD:
           running_opcode = opcode      # 引擎 0x0809A4F8 cmp r1,#0xbd
   elif running_opcode is not None:
       opcode = running_opcode
   ```

   **独立验证**：修完之后，`tools/m4a_block_table.py --self-test` 的
   「renderer cross check」从 **101 字节 / 11 条轨道分歧**变成
   **0 running-opcode divergences / 0 tracks with a different event stream**
   （五首曲子全部）。两个互相独立的解码器现在逐字节一致。
   `tools/audio_song_export.py --self-test` 仍然 PASS
   （978 音符 / 616 个 PSG 事件与 ROM 原始字节对上）。

2. **§8.3 —— 「无 key 音符」的模型已修**：
   `tools/audio_song_export.py` 里 `key = args[0] if len(args) >= 1 else 0`
   改成 `else current_key` —— ROM 的语义是**沿用上一个音的 key**，
   记成 0 会凭空造出游戏根本没弹的最低音。

3. **§11.1 —— 审计里的 5 个 `story*` 歧义项已删**，
   并按 §11.1 的要求补上了 `tools/m4a_block_table.py` 的 tool / note / code 三条探针。
   加上 §11.2，审计的「轨数据块级格式未逐字段拆解」与
   「块级轨道重写不支持」两条缺口**都清零了**。

4. **§11.3 —— `tools/import_audio_song.py` 现在支持块级重写**：
   新增 `write_song_track_block(rom, sound_id, track_index, commands, target_offset=None)`
   与 CLI 的 `--block trackN=json[,offset]`：
   * 不给 offset = **就地重写**（新 block 必须塞进原 block 自己的跨度里，
     剩余用 `0x00` 补齐，和 ROM 自己的 padding 一样）；
   * 给 offset = 把新 block **停在指定位置并改写 SongHeader 的轨道指针**。

   并且新增了一条**可执行**的写回自检
   `tools/writeback_paths.py::case_audio_block`（case 名 `audio-block-1`）：
   就地重写 sound id 1 的 track 0、读回后要求 ROM 正好解出作者给的命令列表，
   且 block 跨度之外一个字节都不许动。
   写回路径自检现在 **19/19 PASS**。

**复现命令**

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools\m4a_block_table.py rom\base.gba --self-test
python tools\audio_song_export.py rom\base.gba --self-test
python tools\writeback_paths.py rom\base.gba
```
