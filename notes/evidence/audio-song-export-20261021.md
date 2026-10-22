# 音频导出证据（m4a → PCM / CGB PSG）— 2026-10-21

**一句话**：`tools/audio_song_export.py` 现在可以**被证明**地把本 ROM 的
sound id 渲染成 PCM/WAV，并把 CGB PSG 通道导出成寄存器级数据；
PSG 频率表的真实布局是 **12 条有符号 16 位**（不是 16 条无符号），
旧工具的表常量**越界压到了噪声表上**——已修复。

- 工具：`tools/audio_song_export.py`
- 证据等级：ROM 静态反汇编（L1/L2）+ 可执行往返自检（自检内含）
- 所有地址都是本 ROM 的 ARM 地址（Thumb 代码，入口偶地址）

---

## 0. 复现命令（全部可复制执行）

```powershell
$env:PYTHONIOENCODING='utf-8'

# (1) 工具自检（含 PSG 与原始 ROM 字节的逐事件比对）
python tools\audio_song_export.py rom\base.gba --self-test

# (2) 五首歌的 PSG 导出与逐事件校验
foreach ($id in 1,2,8,11,14) {
    python tools\audio_song_export.py rom\base.gba --sound-id $id `
        --wav    "build\audio\sound_$('{0:d3}' -f $id).wav" `
        --json   "build\audio\sound_$('{0:d3}' -f $id).json" `
        --psg-json "build\audio\sound_$('{0:d3}' -f $id)_psg.json" `
        --psg-text "build\audio\sound_$('{0:d3}' -f $id)_psg.txt"
    python tools\audio_song_export.py rom\base.gba --verify-psg $id
}

# (3) 本笔记的每条反汇编结论都可以用这三个脚本复核
python build\audio_engine_dump.py     # 按函数边界反汇编 m4a 引擎
python build\thumb_range.py 0x0809A2E8 0x20   # 任意 Thumb 区间
python build\audio_tables_dump.py     # 打印全部音频表
python build\audio_evidence_rows.py   # 打印本笔记里的数值行
```

> 注：`build/` 下的脚本是本次调查的**可复现探针**，不进版本库；
> 结论本身已写进本文件。

---

## 1. ROM 的音频数据地图（已验证）

| 用途 | 文件偏移 | ARM 地址 | 形状 | 原生读取指令 |
|---|---|---|---|---|
| sound id 表 | `0x465B70` | `0x08465B70` | 159 × 8 B | `0x0809AAC4` |
| m4a 命令处理表 | `0x464534` | `0x08464534` | 30 × u32（opcode `0xB1`..`0xCE`） | `0x0809A520` |
| 等待 / 音符时长表 | `0x4647A8` | `0x084647A8` | 49 × u8 | `0x0809A536`、`0x0809A720` |
| 音高选择表（DirectSound） | `0x4645C4` | `0x084645C4` | 180 × u8 | `0x0809A9AC` |
| 八度基数表 | `0x464678` | `0x08464678` | 16 × u32 | `0x0809A9B2` |
| PSG 音高选择表 | `0x4646C0` | `0x084646C0` | 132 × u8 | `0x0809B4EA` |
| **PSG 方波频率表** | `0x464744` | `0x08464744` | **12 × s16（有符号）** | `0x0809B4F0` / `0x0809B4FE` |
| **PSG 噪声音高表** | `0x46475C` | `0x0846475C` | 60 × u8 | `0x0809B4BE` |

> **关键更正**：旧资料里的 `0x53636C / 0x536BC8 / 0x538FF0 / 0x53AB78 /
> 0x53C3C0` 比 SongHeader 起点晚 4 字节，指向的是 `voicegroup_ptr` 字段。
> 正确的 SongHeader 起点是 `0x536368 / 0x536BC4 / 0x538FEC / 0x53AB74 /
> 0x53C3BC`（sound id 1/2/8/11/14）。

### 1.1 「PSG 频率表是 12 条有符号 16 位」——已证实

上一位代理留下的线索**成立**，但「12」和「有符号」是两个独立的事实：

```
; 0x0809B4EA  ldr r3, [pc, #0x48]   ; r3 = 0x084646C0  (PSG 音高选择表)
; 0x0809B4EC  adds r0, r5, r3
; 0x0809B4EE  ldrb r6, [r0]         ; sel = 选择表[key]
; 0x0809B4F0  ldr r4, [pc, #0x44]   ; r4 = 0x08464744  (频率表)
; 0x0809B4F4  adds r0, r6, #0
; 0x0809B4F6  ands r0, r2           ; r0 = sel & 0x0F   (半音 0..11)
; 0x0809B4F8  lsls r0, r0, #1       ; *2               (字节偏移)
; 0x0809B4FA  adds r0, r0, r4
; 0x0809B4FC  movs r7, #0
; 0x0809B4FE  ldrsh r1, [r0, r7]     ; <<< 有符号 16 位读取
; 0x0809B500  asrs r0, r6, #4        ; <<< 算术右移 (八度)
```

两条结论各自独立成立：

1. **有符号**：`ldrsh`（不是 `ldrh`）。12 个值全部为负：
   `-2004, -1891, -1785, -1685, -1591, -1501, -1417, -1337, -1262, -1192, -1125, -1062`。
   旧工具用 `struct.unpack_from("<H", ...)` 读成 `63532 … 64474`，
   再 `>>` 会得到完全错误的寄存器值。
2. **只有 12 条**：下标是 `sel & 0x0F`，而 `sel` 的低半字节**永远是半音
   0..11**（见 `0x084646C0` 的取值：`0x00-0x0B, 0x10-0x1B, …, 0xA0-0xAB`）。
   所以频率表按半音索引，天然就是 12 条。
   旧工具写死 `16 × u16`（32 字节），**从 `0x46475C` 起越界 16 字节，
   正好压在噪声表上**。

**复现命令**：
```powershell
python build\audio_tables_dump.py
```
若把频率表长度改成 16，该命令打印的 `[12]..[15]` 四行会显示
`s16=-10537 / -11051 / -14649 / -15163` —— 这些其实是噪声表的前 8 个字节
（`0xD7 0xD6 0xD5 0xD4 …` 被当成小端 s16 解读），不是频率。

---

## 2. m4a 语义（以**本 ROM 自己的引擎**为准）

通用 m4a 文档只作对照；下面每条都给出本 ROM 的反汇编地址。

### 2.1 时值表（等待 / 音符）

```
; 0x0809A536（等待）                        ; 0x0809A720（音符）
; ldr r0, [pc, #0x150]  ; 0x084647A8        ; ldr r1, [pc, #0x1e0] ; 0x084647A8
; subs r1, #0x80                            ; adds r0, r0, r1
; adds r1, r1, r0                           ; ldrb r0, [r0]
; ldrb r0, [r1]                             ; strb r0, [r5, #4]
; strb r0, [r5, #1]   ; 等待计数
```

- 等待时长 = `table[opcode - 0x80]`（opcode `0x80..0xB0`，49 条）。
- 音符时长 = `table[opcode - 0xCF]`（opcode `0xCF..0xFF`，49 条），
  再加上可选的第 3 个参数字节（gate）：
  ```
  ; 0x0809A744  ldrb r1, [r5, #4]
  ; 0x0809A746  adds r1, r1, r0     ; duration += gate
  ; 0x0809A748  strb r1, [r5, #4]
  ```
- **与通用文档的差异**：时长表指针不是全局常量，而是**每首歌可指定**，
  存在 `song_struct + 0x38`：
  ```
  ; 0x0809A502  mov r0, r8
  ; 0x0809A504  ldr r3, [r0, #0x38]   ; 每首歌的时长表指针
  ; 0x0809A506  adds r0, r1, #0
  ; 0x0809A508  subs r0, #0xcf
  ```
  本 ROM 的五首歌都指向默认表 `0x084647A8`。

### 2.2 速度（TEMPO，opcode `0xBB`）

命令表 `0x08464534` 的第 10 项（`0xB1 + 10 = 0xBB`）= `0x0809A2E9`，
处理函数在 `0x0809A2E8`：

```
; 0x0809A2E8  mov ip, lr
; 0x0809A2EA  bl  0x809a250      ; 从轨道读一个参数字节 -> r3
; 0x0809A2EE  lsls r3, r3, #1   ; tempo_reg = byte * 2
; 0x0809A2F0  strh r3, [r0, #0x1c]
; 0x0809A2F2  ldrh r2, [r0, #0x1e]   ; = 256 (tempo 单位)
; 0x0809A2F4  muls r3, r2, r3
; 0x0809A2F6  lsrs r3, r3, #8         ; (tempo_reg * 256) >> 8
; 0x0809A2F8  strh r3, [r0, #0x20]   ; tick_period
```

**结论**：`tick_period = 2 × tempo_byte`（因为 `256 >> 8 == 1`）。
这与通用 m4a 文档「tempo 是 BPM×2」的写法一致，但这里的**推导链是本 ROM 的
两条指令**，不是文档。

### 2.3 歌曲启动与节拍栅格

```
; 0x0809B24A  movs r0, #0x96      ; 150
; 0x0809B24C  strh r0, [r5, #0x1c]
; 0x0809B24E  strh r0, [r5, #0x20] ; tick_period = 150
; 0x0809B250  adds r0, #0x6a      ; 150 + 106 = 256
; 0x0809B252  strh r0, [r5, #0x1e] ; tempo 单位 = 256
; 0x0809B254  strh r1, [r5, #0x22] ; 累加器 = 0
; 0x0809B256  strh r1, [r5, #0x24]
```

节拍推进：

```
; 0x0809A474  ldrh r0, [r7, #0x22]   ; 累加器
; 0x0809A476  ldrh r1, [r7, #0x20]   ; tick_period
; 0x0809A478  adds r0, r0, r1       ; 累加器 += tick_period
; 0x0809A47A  b    0x809a5c4
...
; 0x0809A5C0  ldrh r0, [r7, #0x22]
; 0x0809A5C2  subs r0, #0x96         ; 累加器 -= 150
; 0x0809A5C4  strh r0, [r7, #0x22]
; 0x0809A5C6  cmp  r0, #0x96         ; 150
; 0x0809A5C8  blo  0x809a5cc         ; 不够 150 -> 不跑这一步
; 0x0809A5CA  b    0x809a47c         ; 跑一次音序器 tick
```

**结论**：引擎每帧给累加器加 `tick_period`，**满 150 才走一个音序器 tick**。
所以 `tick_rate = 60 × tick_period / 150`（引擎每游戏帧被调用一次）。
`tick_period = 2 × tempo_byte` 代入得 `tick_rate = 0.8 × tempo_byte`。
五首歌实际写入的 tempo 字节：

| sound id | TEMPO 指令地址 | 字节 | tick_period | tick/s | 24 tick/拍 → BPM |
|---|---|---|---|---|---|
| 1 | `0x535D00` | 80 | 160 | 64 | 160 |
| 2 | `0x536394` | 37 | 74 | 29.6 | 74 |
| 8 | `0x5388B0` | 87 | 174 | 69.6 | 174 |
| 11 | `0x53A218` | 47 | 94 | 37.6 | 94 |
| 14 | `0x53BC18` | 52 | 104 | 41.6 | 104 |

> 「24 tick = 一拍」是**工具的模型常量**（`TICKS_PER_QUARTER = 24`），
> 不是 ROM 直接证明的；ROM 只证明「49 级 tick 栅格」和「150 累加单位 = 1 tick」。
> 因此上表最后一列是**模型推论**，不是 ROM 事实。

### 2.4 音色记录（12 字节）与 VOICE

```
; 0x0809A770  lsls r1, r0, #1     ; r0 = 音色序号
; 0x0809A772  adds r1, r1, r0     ; *3
; 0x0809A774  lsls r1, r1, #2     ; *12
; 0x0809A776  ldr r0, [r5, #0x28] ; voicegroup 基址
; 0x0809A778  adds r1, r1, r0     ; 音色 = voicegroup + 12 * 序号
```

音色记录布局（12 字节，引擎读取处）：

| 偏移 | 含义 | 证据 |
|---|---|---|
| +0 | 类型（`0x00`=DirectSound，`0x80`=PSG，低 3 位=PSG 波形） | `0x0809A77E`、`0x0809A7B8` |
| +1 | 音高键 | `0x0809A79C` |
| +2 | 时长 | `0x0809A8B0` |
| +3 | pan / sweep（bit7 置位=pan，否则 sweep） | `0x0809A78E`、`0x0809A8B4` |
| +4..7 | 波表指针（DirectSound）或 PSG 乐器表指针 | `0x0809A88C` |
| +8..11 | attack / decay / sustain / release | `0x0809A890`（一次读 4 字节） |

VOICE（opcode `0xBD`，命令表第 12 项 = `0x0809A311`）就是选音色序号：
```
; 0x0809A31A  lsls r2, r3, #1
; 0x0809A31C  adds r2, r2, r3
; 0x0809A31E  lsls r2, r2, #2     ; 序号 * 12
```

### 2.5 音高表（DirectSound）

函数 `0x0809A998`：

```
; 0x0809A9AC  ldr r3, [pc, #0x44]   ; 0x084645C4  选择表
; 0x0809A9AE  adds r0, r6, r3
; 0x0809A9B0  ldrb r5, [r0]         ; sel = 选择表[key]
; 0x0809A9B2  ldr r4, [pc, #0x44]   ; 0x08464678  八度基数
; 0x0809A9B8  ands r0, r2           ; sel & 0x0F  -> 半音
; 0x0809A9BA  lsls r0, r0, #2
; 0x0809A9BC  adds r0, r0, r4
; 0x0809A9BE  lsrs r1, r5, #4        ; sel >> 4     -> 八度
; 0x0809A9C0  ldr r5, [r0]           ; 八度基数[半音]
; 0x0809A9C2  lsrs r5, r1            ; >> 八度
```

**结论**：`f(key) = octave_base[sel & 0xF] >> (sel >> 4)`，
其中 `octave_base[i] ≈ 2^(31 + i/12)`，`sel = 选择表[key] = (14 - key/12)*16 + key%12`。
化简后 **`f(key) = 2^(17 + key/12)`**，与工具自检第 2 条一致。
引擎随后用 `f(key+1)` 做**分数插值**（`0x0809A9DC`..`0x0809A9D6`），
再乘以波头的采样率字段（`wave[0x04]`，`0x0809A9DA`）。
工具在无弯音时用 `f(key)`，等价。

### 2.6 PSG 频率（本 ROM 与通用文档**不一致**的地方）

函数 `0x0809B494`（方波 + 噪声都在这里）：

```
; 0x0809B4A4  cmp r0, #4         ; 波形 == 4 ? (噪声)
; 0x0809B4A6  bne 0x809b4cc      ; 否 -> 方波
; --- 噪声 ---
; 0x0809B4A8  cmp r5, #0x14      ; key <= 20 ?
; 0x0809B4AA  bhi 0x809b4b0
; 0x0809B4AC  movs r5, #0        ; 下标 = 0
; 0x0809B4B0  subs r0, #0x15     ; 下标 = key - 21
; 0x0809B4B8  cmp r5, #0x3b      ; 上限 59
; 0x0809B4BE  ldr r0, [pc, #8]   ; 0x0846475C 噪声表
; 0x0809B4C2  ldrb r0, [r0]      ; 原始字节（NR43）
; 0x0809B4C4  b   0x809b52e      ; 直接返回，【不加 0x800、不插值】
; --- 方波 ---
; 0x0809B4CC  cmp r5, #0x23      ; key <= 35 ?
; 0x0809B4D0  movs r0, #0
; 0x0809B4D2  mov ip, r0         ; 分数 = 0
; 0x0809B4D4  movs r5, #0        ; 下标 = 0
; 0x0809B4D8  adds r0, r5, #0
; 0x0809B4DA  subs r0, #0x24     ; 下标 = key - 36      <<< 先减 36
; 0x0809B4E0  cmp r5, #0x82      ; 再夹到 0x82
; 0x0809B4E4  movs r5, #0x82
; 0x0809B6E6  movs r1, #0xff     ; 分数 = 255
; 0x0809B4EA  ldr r3, [pc, #0x48] ; 0x084646C0 选择表
; 0x0809B4FE  ldrsh r1, [r0, r7] ; 有符号 16 位基准
; 0x0809B504  asrs r6, r0        ; 算术右移（八度）
; 0x0809B51C  subs r0, r0, r6   ; 下一音的基准 - 当前基准
; 0x0809B520  muls r7, r0, r7   ; × 分数
; 0x0809B524  asrs r0, r0, #8   ; >> 8
; 0x0809B526  adds r0, r6, r0   ; 插值
; 0x0809B52C  adds r0, r0, r1   ; + 0x800 (0x0809B528..0x0809B52C)
```

**与通用 m4a 文档的三处差异**（都以本 ROM 为准）：

1. **寄存器值要加 `0x800`**。通用文档里 PSG 频率就是表里的数；
   本 ROM 返回的是 `基准 + 0x800`（11 位 GB 频率寄存器）。
2. **噪声走完全不同的分支**：下标是 `key<=20 ? 0 : min(key-21, 59)`，
   取到的是**原始字节**，**不加 `0x800`、不插值**。
   通用文档没有这个「键号重映射」。
3. **方波键号先减 36 再夹紧**，且 `key <= 35` 一律落到下标 0
   （最低音）。通用文档里 PSG 键号直接索引音高表。
   顺序很重要：`key = 200` 时 ROM 得到「164 → 夹到 130、分数 255」，
   而不是「先夹到 130 → 减 36 得 94」。工具旧版本正是先夹后减，
   已在本次修复。

### 2.7 PSG 乐器表（每条 12 字节）

音色记录 +4 指向一张 12 字节/条的乐器表。本 ROM 里抽样到的表内容**完全相同**：

```
@0x464D7C:  01 3C 00 00 02 00 00 00 00 00 0F 00
@0x464FA4:  00 3C 00 D8 B4 51 48 08 FF 00 FF 00
@0x464FC8:  00 3C 00 A8 90 93 48 08 FF 00 FF 00
```

| 偏移 | 本笔记的解释 | 依据 |
|---|---|---|
| +0 | PSG 波形（低 3 位）：0=12.5% 1=25% 2=50% 3=75% 4=噪声 | 工具读 `record[0] & 7`；`0x0809B6CC` 判 bit6 |
| +1 | 乐器基准键（本 ROM 恒为 `0x3C` = 60） | 采样观察 |
| +2 | pan/sweep | `0x0809A8B0` 区段 |
| +3 | pan 值（bit7 置位表示「这是 pan」） | `0x0809A8B4`..`0x0809A8C4` |
| +4..7 | 未解（`02 00 00 00` 或指针样数值） | 未证实 |
| +8..11 | attack / decay / sustain / release | 引擎在 `0x0809A890` 一次读 4 字节并存入通道 |

> **未证实项**：乐器表的下标到底是「音符键」还是「音符键 − 基准键」，
> 本 ROM 无法判别——抽样到的每张表里所有条目都一模一样，
> 无论用哪种下标结果相同。工具按「音符键」索引（与 `0x464D7C` 这类表的
> 实际布局一致），此项标注为**待证**。

### 2.8 循环结构

命令表 `0x08464534` 的前 5 项就是循环相关命令：

| opcode | 处理函数 | 行为（反汇编） |
|---|---|---|
| `0xB2` GOTO | `0x0809A25C` | 读 4 字节大端 ROM 指针写回轨道读指针（`0x0809A25E`..`0x0809A276`） |
| `0xB3` PATT | `0x0809A27C` | 压栈返回地址，**栈深上限 3**（`0x0809A27E cmp r2,#3 / bhs`），越界直接退出 |
| `0xB4` PEND | `0x0809A298` | 弹栈；**栈空时是「继续执行下一条」而不是出错**（`0x0809A29C beq`） |
| `0xB5` REPT | `0x0809A2AC` | 格式 `[count:1][target:4]`；count=0 时引擎**跳进 target 无限循环**（`0x0809A2B4 bne`），count≠0 时计数满则跳过 5 字节（`0x0809A2D2`） |

> **与通用文档/旧工具的差异**：
> - PATT 栈深上限是 **3**，旧工具用无上限 list。
> - REPT 的 count=0 在 ROM 里是**无限循环**，旧工具当成「不重复」。
>   本 ROM 的轨道里是否真的存在 count=0 的 REPT，尚未统计（见 §5）。

### 2.9 包络

- DirectSound 通道的包络由 `0x0809B58C` 生成：它比较通道的 +2 / +3 两个
  字节，写出 `+0x1B`（包络形状）、`+0xA`（sustain = `min(15, (a+d)>>4)`）、
  `+0x19`（`+0xA` 与 +6 的乘积）。
- 通道的 +2/+3 由 `0x0809A6D8` 从 **速度 × 弯音** 算出
  （`muls r3, r1, r3` + `asrs r0, r0, #0xe`），**不是**直接取音色记录的
  attack/decay 字节。
- 音色记录的 attack/decay/sustain/release 在 `0x0809A890` 被整块写进通道 +4，
  供 DirectSound 通道使用。

> 因此「音色 attack/decay/sustain/release 就是 GB NR12 包络」**与本 ROM 不符**：
> GB 风格的包络整形器用的是通道里的另两个字节。

---

## 3. PSG 导出的保真度验证（可执行）

`tools/audio_song_export.py` 自带一条**独立实现**的交叉校验：
`_psg_register_from_raw_rom()` 不使用 `tables` 字典，也不用
`psg_frequency_register()`，而是**直接从 ROM 字节按字面偏移重新读表并重新实现
引擎算术**，然后与 `psg_export()` 的输出逐事件比对。

```powershell
python tools\audio_song_export.py rom\base.gba --verify-psg 1
# verify-psg: sound id 1: 616 PSG events checked against the ROM
```

五个 sound id 全部通过：

| sound id | 比对事件数 | 结果 |
|---|---|---|
| 1 | 616 | ✅ |
| 2 | 534 | ✅ |
| 8 | 746 | ✅ |
| 11 | 612 | ✅ |
| 14 | 498 | ✅ |

自检里还钉了三个手算值，防止回归：

| key | 选择表下标 | 选择字节 | 半音/八度 | 基准 | 寄存器 |
|---|---|---|---|---|---|
| 0 | 0 | `0x00` | 0 / 0 | `-2004` | **44**（65.41 Hz） |
| 46 | 10 | `0x0A` | 10 / 0 | `-1125` | **923**（116.51 Hz） |
| 49 | 13 | `0x11` | 1 / 1 | `-1891 >> 1 = -946` | **1102**（138.55 Hz） |

### 3.1 一首歌的逐事件对照（sound id 1）

`build/audio/sound_001_psg.txt` 头部：

```
# GBA m4a PSG export - sound id 1
# columns: track time  dur  key  wave            vol pan  atk dec sus rel  reg  Hz
    4    0.050  0.400   46  square 12.5%    105  64  255   0 255   0   923   116.51
    4    0.450  0.400    0  square 25%      105  64    0   0  15   0    44    65.41
```

对应的 ROM 字节（`build/audio_evidence_rows.py` 输出）：

```
track 4 t=0.050 key 46 wave square 12.5%  reg=923 (116.51 Hz)
    instrument @0x464FA4 = 00 3C 00 D8 B4 51 48 08 FF 00 FF 00
    envelope a/d/s/r = 255/0/255/0  pan_sweep=0 pan=216
    key 46 -> psg_key_table index 10 (0x0809B4DA: key-0x24)  selector=0x0A
             -> semitone 10 octave 0  s16[10]=-1125 >> 0 = -1125  +0x800 = 923
```

即：**导出里的每一个寄存器值，都可以由 ROM 里的 3 个字节
（`0x084646C0` 选择字节、`0x08464744` 有符号基准、`+0x800` 偏置）重算出来。**

---

## 4. 工具能做什么 / 不能做什么

**能做**

- 把一个 sound id 的所有轨道、所有循环渲染成 16 位立体声 WAV。
- 导出全部音符事件（tick / 时间 / 键 / 力度 / 音色 / 包络 / 弯音）。
- 导出 PSG 通道的寄存器级数据（波形、GB 频率寄存器、Hz、包络、pan）。
- 用一条独立实现与 ROM 原始字节逐事件交叉校验 PSG（`--verify-psg`）。

**不能做（明确边界）**

- **不是位精确的引擎仿真**。DirectSound 的包络是工具自建的 ADSR 模型
  （`envelope_gain()`，注释里写明是 model 而非 ROM 状态机）；
  PSG 的波形是理想方波 / 简化 LFSR，不是 GB 音频仿真。
- **不做弯音插值**。ROM 的 `0x0809B494` / `0x0809A998` 用 8 位分数在
  `f(key)` 与 `f(key+1)` 之间插值；工具固定取不插值的基准值。
- **不还原 LFO / MOD / MODT / TUNE 的全部调制链**：`0x0809A971`（LFOS）、
  `0x0809A985`（MOD）、`0x0809A39D`（MODT）三个处理函数只被记录，未建模。
- **不支持块级（block）轨道的重写**：`tools/import_audio_song.py` 只能复用
  原生 song 块，因为块级轨道格式尚未完全解码。
- **PSG 乐器表下标未证实**（见 §2.7）。

---

## 5. 已知缺口（逐条列出）

1. `REPT count == 0` 在 ROM 里是无限循环，工具按「不重复」处理；
   本 ROM 轨道中是否出现 `count == 0` 的 REPT **尚未统计**。
   待办命令：`python build/audio_evidence_rows.py` 需扩展为统计所有轨道的
   REPT count 分布。
2. PATT 栈深上限 3 未在工具里模拟（工具用无上限 list）。
3. PSG 乐器表下标语义未证实。
4. DirectSound 弯音插值未实现。
5. LFO / MOD 调制未建模。
6. 工具的 `SEQUENCER_HZ = 60`（每游戏帧一次）是**模型假设**；
   ROM 侧只证明了「每帧累加 tick_period、满 150 走一个 tick」，
   引擎被调用的频率未在运行时核实。

---

## 6. 本次修复摘要（`tools/audio_song_export.py`）

| 问题 | 旧行为 | 新行为 | 证据 |
|---|---|---|---|
| PSG 频率表长度 | 16 × u16（32 B）**越界压噪声表** | 12 × s16（24 B） | `0x0809B4FE ldrsh` |
| PSG 频率表符号 | 无符号 `u16` → 63532..64474 | 有符号 `s16` → 全负 | 同上 |
| PSG 移位 | 逻辑 `>>` | 算术 `>>`（负值向下取整） | `0x0809B504 asrs` |
| PSG 寄存器偏置 | 无 | `+ 0x800` | `0x0809B52C` |
| PSG 键号处理 | 直接索引 | 先 `- 36`、后夹紧；`<=35` 落 0 | `0x0809B4DA` / `0x0809B4E4` |
| 噪声下标 | `noise[key]` | `key<=20 ? 0 : min(key-21, 59)` | `0x0809B4A8`..`0x0809B4BC` |
| 噪声频率 Hz | 当成方波周期算 | NR43 语义 `524288/(r·2^(s+1))` | GB NR43 位定义 |
| 噪声寄存器 | 也加 `0x800`（错） | 不加、不插值 | `0x0809B4C4 b 0x809b52e` |
| 死代码 | `frequency = gb_frequency_to_hz(131072 - register …)` 立刻被覆盖 | 删除 | — |
| 交叉校验 | 无 | `--verify-psg` + 自检内 3 个定点值 | 本文件 §3 |

---

## 7. 回归

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m unittest discover -s tests -p 'test_*.py'
python tools\automated_test.py
python tools\completion_audit.py --check
```

结果见本轮工作报告。

---

## 8. 补充（2026-10-21）：m4a block 表已逐字段拆解

**本节追加于 2026-10-21，晚于本文件其余部分。**
详细证据见新笔记 **`notes/evidence/m4a-block-table-20261021.md`**，
可执行工具见 **`tools/m4a_block_table.py`**。

### 8.1 被取代的结论

| 本文件旧说法 | 新结论（以新笔记为准） |
|---|---|
| §4「**不支持块级（block）轨道的重写**：`tools/import_audio_song.py` 只能复用原生 song 块，因为**块级轨道格式尚未完全解码**」 | **已解码。** SongHeader 的逐字段布局、block 的命令编码、命令表 `0x08464534` 的 30 项、循环结构（GOTO/PATT/PEND/REPT）都已用本 ROM 自己的引擎反汇编钉死；`tools/m4a_block_table.py` 实现了 **decode → encode 字节级往返**、**跳转目标校验**、**与本渲染器的逐事件交叉比对**，以及**块级重写**（原地改写 / 空闲区新块 + 改指针）。 |
| §2.8「GOTO / PATT / REPT 读 4 字节**大端** ROM 指针」 | **更正为小端。** 引擎的移位链是 `r0 = b3<<24｜b2<<16｜b1<<8｜b0`，其中 `b0 = r2[0]` —— ROM 里第 0 字节是最小有效字节。五首歌 45 个 block 的全部跳转目标按小端读都落在命令边界上，按大端读全部越界。 |
| §2.1 / §2.4 只描述了「时值表」「音色记录」，没有描述**轨道数据本身的块级格式** | 已补：opcode 分四类（`0x00..0x7F` 续写字节 / `0x80..0xB0` WAIT / `0xB1..0xCE` 命令表 / `0xCF..0xFF` NOTE），block 由 **FINE `0xB1`** 结束，其后是 `0x00` 填充。 |

因此，完成度审计里 `story` / `story-b` / `story-c` / `story-d` / `story-e`
五条「轨数据的块级格式（m4a 的 block 表）未逐字段拆解」与 `sound-id-table`
一条「块级（block）轨道的重写不支持」的**前提已经消失**：
审计条目本身硬编码在 `tools/completion_audit.py`（本次未修改，见新笔记 §11）。

### 8.2 本文件 §2.8 的一条旧结论也需要更正

旧 §2.8 写「REPT 的 count=0 在 ROM 里是无限循环」——**这条仍然成立**
（`0x0809A2B2 cmp r3, #0` / `0x0809A2B4 bne` → 跳进 target），
但**本文件 §4 已知缺口第 1 条**（“本 ROM 轨道中是否出现 count == 0 的 REPT 尚未统计”）
现在可以回答：**五首歌的 6333 条命令里没有出现过 `0xB5`**，所以该问题对本 ROM 不存在。

### 8.3 与本渲染器的一处已知分歧（未修改本渲染器）

新笔记 §8 用引擎指令、命令处理函数和数据里的和声证据三方交叉验证后判定：
**本渲染器所依赖的 `tools/extract_audio.py::decode_track` 在「running opcode」的
适用范围上与 ROM 不一致** —— 它只保存 running **note**，而引擎
（`0x0809A4F8 cmp r1, #0xbd`）对**所有 `>= 0xBD` 的 opcode** 都保存 running opcode。
影响面：五首歌共 **101 个续写字节**，其中 **11 条轨道**的事件流因此不同
（例如 sound id 11 track 3 的 `CE 2F 32 36`，ROM 读成「释放 0x2F / 0x32 / 0x36 三个音」，
现有解码器读成「释放 0x2F + 多一个 key=0x32 的新音符」）。

**本文件 §3 的 PSG 校验结论不受影响**：`--verify-psg` 用的是
「从 ROM 字节按字面偏移重算寄存器」的自带实现，与事件流的产生路径无关；
它验证的是**寄存器算术**正确，不是音符切分正确。

按文件所有权限制，本次**没有修改** `tools/extract_audio.py` /
`tools/audio_song_export.py`。需要修改时的具体要求见
`notes/evidence/m4a-block-table-20261021.md` §8.2 与 §11。

### 8.4 复现

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools\m4a_block_table.py rom\base.gba --self-test
```

结果：45/45 block 往返字节相同、引擎走查一致、跳转目标全部合法、
块级重写三种模式读回一致；**SELF-TEST: PASS**。


---

## 2026-10-21 追加：DirectSound 弯音插值已实现并与引擎对拍

### 1. 引擎的弯音链（本 ROM 的代码，逐条转写）

| 位置 | 作用 |
|---|---|
| `0x0809A368` | BEND(0xC0)：`通道+0x0E = 操作数 − 0x40`（有符号） |
| `0x0809A37C` | BENDR(0xC1)：`通道+0x0F = 量程`（通道复位时 `0x0809A4D6` 写 **2**） |
| `0x0809B450`..`0x0809B486` | 累加器：`S = (tune + bend*range)*4 + (keyShift<<8)`；`通道+0x08 = (s8)(S>>8)`（半音偏移）、`通道+0x09 = (u8)S`（分数） |
| `0x0809A89C`..`0x0809A658` | 音高键 = 音符键 + 半音偏移（负则夹 0），分数 = `通道+0x09` |
| `0x0809A998`..`0x0809A9EA` | `f(k) = octave_base[sel&0xF] >> (sel>>4)`；`base = f(k) + ((f(k+1)−f(k))*分数 >> 8)`；`pitch = (base * wave[4]) >> 32` |
| `0x08099D7C` / `0x08099D80` | Thumb→ARM 跳板 + ARM 态乘法助手 `umull r2,r3,r0,r1` / `add r0,r3,#0` ⇒ 取**高 32 位**（`>> 32`） |

### 2. 工具侧

`tools/audio_song_export.py` 新增：

- `bend_pitch_offset(bend, bend_range, tune=0, key_shift=0)` → `(半音偏移, 分数)`；
- `engine_pitch_base(table, key, fraction=0)` → 引擎那份插值后的整数基值；
- `bent_key(note)` → 引擎的音高键（音符键 + 半音偏移，负则夹 0）；
- `TrackRunner` 给每个音符记 `bend_offset` / `bend_fraction`；
- `render_direct_sound` 用 `engine_pitch_base` 取代原来的 `2**((key-60)/12)`；
- `render_psg` / `psg_export` 用弯音后的键与分数；
- `_psg_register_from_raw_rom` 加上分数 ⇒ 交叉校验仍然独立。

### 3. 与引擎对拍（179 条引擎自己的读数，0 处不符）

```
$ python tools\closure_pitch_check.py rom\base.gba build\closure-pitch.json \
      build\closure-pitch-bend.json build\closure-pitch-b60-r8.json \
      build\closure-pitch-b20-r2.json build\closure-pitch-s40.json \
      build\closure-pitch-s44.json build\closure-pitch-s50.json \
      build\closure-pitch-s54.json
TOTAL: 179 readings, 0 mismatch(es)
```

读数是用 `tools/closure_pitch_probe.py` 在真实剧情场景里
打断点 `0x0809A658`（引擎写音高寄存器）与 `0x0809B486`（引擎写分数）拿到的；
弯音是**注入**的（写 `通道+0x0E` / `通道+0x0F` 并置位「音高脏」位），
引擎随后**自己**跑累加器与重算。

覆盖到的读数：分数 0 / 128 / 160，半音偏移 0 / +4 / −1，
5 首曲子里的 4 个场景 + 战斗场景。

### 4. 回归

```
$ python tools\audio_song_export.py rom\base.gba --self-test
self-test: 978 notes rendered, 308 PSG events, 616 PSG events verified against the raw ROM, duration 32.400 s
SELF-TEST: PASS

$ python tools\audio_song_export.py rom\base.gba --verify-psg 2
verify-psg: sound id 2: 534 PSG events checked against the ROM
```

sound id 2 **正是带 BEND 的曲子**，它的 PSG 导出仍与 ROM 原始字节逐事件相符。

### 5. 旧结论的更正

- 旧 §4「**不做弯音插值**」与 §5 第 4 条「DirectSound 弯音插值未实现」**作废**；
- 旧 §2.9「通道的 +2/+3 由 `0x0809A6D8` 从**速度 × 弯音**算出」**作废**：
  `0x0809A6D8` 用的是 `通道+0x12`（VOLUME）与 `通道+0x14`（PAN），
  算出来的是**左右音量**（写 `通道+0x10` / `通道+0x1E`），**与弯音无关**；
- 旧 §2.5 的「引擎随后用 `f(key+1)` 做分数插值」现在有了**确切公式与出处**
  （见上表）。
