# 旧剧情表族（`story` / `story-b` … `story-e`）：真实身份与原生到达路径（2026-10-20）

**一句话结论**：这五张 legacy bank **根本不是剧情表**，而是 **m4a 曲头（SongHeader）的
`voicegroup` 字段 + `trackList[]`**。声明基址比真实基址**晚 4 字节**；游戏通过
**声音 ID 表 `0x08465B70` 的数据指针**到达它们，**不是**通过任何字面量。

**工具**：`tools/story_table_locate.py`（新增，本文 §2.4）
**ROM**：`rom/base.gba`，SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
**关联**：`notes/resource-locations.md`（声音 ID 表 / m4a 结构 / 描述符格式）、
`tools/extract_audio.py`（m4a 提取器）、`notes/legacy-table-base-correction-20261020.md`
（22 个 legacy 基址「ROM 零引用」的裁决）、`notes/evidence/consumer-evidence.json`
（**只读**，仅用于核对 ROM 指纹与交叉引用）

---

## 0. 结论摘要

| bank | 声明基址 | **真实基址（= base-4）** | 声明条目数 | **真实 `track_count`** | 对应声音 ID | 原生读者（读 `voicegroup` 字段） |
|---|---|---|---|---|---|---|
| `story` | `0x53636C` | **`0x536368`** | 9 | **8** | 1 | `0x0809B242` `ldr r0,[r7,#4]` |
| `story-b` | `0x536BC8` | **`0x536BC4`** | 11 | **10** | 2 | `0x0809B242` |
| `story-c` | `0x538FF0` | **`0x538FEC`** | 10 | **9** | 8 | `0x0809B242` |
| `story-d` | `0x53AB78` | **`0x53AB74`** | 11 | **10** | 11 | `0x0809B242` |
| `story-e` | `0x53C3C0` | **`0x53C3BC`** | 9 | **8** | 14 | `0x0809B242` |

结构本体（m4a `SongHeader`）：

```
+0x00 u8  track_count      <- 恰好等于「声明条目数 - 1」
+0x01 u8  block_count      (5 张全为 0)
+0x02 u8  priority         (5 张全为 0)
+0x03 u8  reverb           (5 张全为 128)
+0x04 u32 voicegroup_ptr   <- **legacy 提取器把这一项当成了「第 1 条」**
+0x08 u32 track_ptrs[track_count]   <- legacy 提取器把其余 track_count 项当成「第 2..N 条」
```

因此「每个 bank 都是 N 条 u32 指针」这个观察**是对的**（`voicegroup + trackList` 恰好是
连续 N 个 u32），但**起点错了 4 字节**，而且这些指针不是「章节数据」，是
**音色组（voicegroup）+ 音轨字节码**。

---

## 1. 被证伪的假设与仍成立的事实

### 1.1 仍成立：ROM 从未命名这五个地址

`raw_occurrences`（整个 ROM 里作为 32 位值出现的次数）：

| 地址 | 出现次数 | 位置 |
|---|---:|---|
| `0x0853636C` | **0** | — |
| `0x08536BC8` | **0** | — |
| `0x08538FF0` | **0** | — |
| `0x0853AB78` | **0** | — |
| `0x0853C3C0` | **0** | — |

所以 `notes/legacy-table-base-correction-20261020.md` §5.1「这 21 个基址 ROM 从来没提过」
对这五个**成立**，本轮**没有推翻**它。

### 1.2 仍成立：payload 在前、指针表在后

每个 bank 的数据块确实紧挨在它自己基址之前。**但原因不是「剧情章节」**：

- m4a 的音轨字节码被**连续存放**，每条音轨从自己的起点一直延伸到**下一条音轨的起点**；
- **最后一条音轨的结束位置正好就是 SongHeader 的起点**；
- SongHeader 的 `trackList[]` 反过来指回这些音轨。

实测（`story`，真实基址 `0x536368`）：

```
track0 0x08535CFC  (下一个起点 0x08535DD2，长 0xD6)
track1 0x08535DD2  (0x123)
track2 0x08535EF5  (0x134)
track3 0x08536029  (0xD6)
track4 0x085360FF  (0xD5)
track5 0x085361D4  (0xE6)
track6 0x085362BA  (0x7D)
track7 0x08536337  (0x31)  <- 结束于 0x536368 = SongHeader 起点
```

「payload 在前、指针表在后」是 **m4a 曲目的排布**，不是剧情章节的排布。

### 1.3 被证伪：`0x084648xx..0x08464Cxx` 是「剧情条目描述符族」

不是。那五个「首指针」是**音色组（voicegroup）**指针，指向**12 字节 tone 记录数组**。

实测（`story`，`voicegroup = 0x0846480C`）：

```
0046480C  type=0 key=60 len=0 pan_sweep=0 ptr=0x0846606C atk=255 dec=0 sus=255 rel=0
```

- `type=0` = DirectSound；`ptr=0x0846606C` 指向 16 字节 wave 头
  （实测 `freq=0x00DAC000 / 1024 = 14000 Hz`，`loop_start=10505`，`samples=20789`，
  PCM 从 `0x46607C` 开始）——与 `notes/resource-locations.md` 记的样本完全一致；
- 其余四张同构：

| bank | voicegroup | 首 tone: type/key | wave 指针 | wave 频率 |
|---|---|---|---|---|
| `story` | `0x0846480C` | 0 / 60 | `0x0846606C` | 14000 Hz |
| `story-b` | `0x08464854` | 0 / 60 | `0x0846B1B4` | 14000 Hz |
| `story-c` | `0x08464A40` | 0 / 60 | `0x0846606C` | 14000 Hz |
| `story-d` | `0x08464B48` | 0 / 60 | `0x0846606C` | 14000 Hz |
| `story-e` | `0x08464C5C` | 0 / 60 | `0x0846B1B4` | 14000 Hz |

这五个地址在 ROM 里**各只出现 1 次**，而且**恰好就出现在各自的 legacy 基址处**
（`0x0846480C` 在 `0x53636C`，`0x08464854` 在 `0x536BC8`，……）——
即它们就是 SongHeader 的 `voicegroup` 字段本身。

### 1.4 部分成立：这些是「同一重复结构的多个实例，由更高层表索引」

**成立，但索引空间是「声音 ID」而不是「章节」**：五张都是同一种 SongHeader 结构，
由**声音 ID 表 `0x08465B70`**（159 行 × 8 字节）索引。

---

## 2. 方法

### 2.1 候选集必须是**全量**字面量索引，不是 54 表证据文件

`notes/evidence/consumer-evidence.json` 只含完成度审计关心的 **54 张表**；而
`tools/consumer_locate.LiteralIndex` 持有 ROM 加载的**每一个**常量：

```
literal index : 18051 distinct values, 29920 reader instructions
live literals : 1196   （值落在 ROM 地址区间 0x08000000..0x08600000）
```

> **踩坑记录（必须记下来）**：证据文件是**截断子集**。拿它当候选集会静默丢掉
> 54 张表以外的所有候选——这正是第一轮调查得出错误答案的机制。
> 本轮起，`tools/story_table_locate.py` **直接**用 `tools.consumer_locate.LiteralIndex`
> 全量索引；证据文件**只读**，用途仅限 (a) 核对 ROM SHA-256、(b) 交叉引用已知消费者。

### 2.2 扫描 (a)：`target == L + index*stride + imm`

对**每个** live literal `L`（1196 个）：

- `delta = target - L`（`L` 必须 `< target`，正步长）；
- 步长空间**穷举**：`STRIDE_CATALOG`（24 项，含 1/2/4/8/12/16/…/0xB4/0xCC/0x100/0x180/0x200）；
- `index ∈ [1, max_index]`（默认 4096），`|imm| ≤ imm_span`（默认 0x40）。

纯算术上几乎任何 `L` 都能配出解（例如 `L=0x08465B70`、`delta=0xD07FC`、
stride 256、`index=3336`、`imm=-4`），**所以算术可行 ≠ 证据**。
因此命中必须再过一道**代码佐证**：该 literal 的读者所在函数里必须**真的**出现
同样的步长写法：

| 识别到的写法 | 推出的步长 |
|---|---|
| `add rX, rY, rZ, lsl #n` | `1 << n` |
| `lsls rY, rZ, #n` + `lsrs rY, rY, #m` | `2**(n-m)` |
| `lsls rY, rZ, #n` 后 `add rX, rY, rY`（索引缩放） | `1 << n` |
| `movs rT, #imm` + `muls rX, rT, rY` | `imm` |

只有「算术可行 **且** 代码佐证」的组合才计入 `corroborated by code`。

> **为什么必须有代码佐证**：只匹配 `imm` 是假阳性重灾区——`adds rX, rY, #4`
> 在代码里遍地都是，任意对齐偏移都能对上。第一版把 `imm` 命中也算「佐证」，
> 于是 `story-c` / `story-d` 各冒出 1~2 条看似合理的假命中；加上步长佐证后归零。

### 2.3 扫描 (b)：raw data + 邻域指针

- 目标地址自身在整个 ROM 里作为 32 位值出现的**所有位置**；
- 目标**邻域**（默认 ±0x400）内每个 4 字节对齐地址，在整个 ROM 里被**存进别处**的位置；
  并标出「它落在哪张被代码引用的表里」（取其下方最近的 live literal）。

这一步是**找到真正的到达路径**的关键：`L + i*stride` 这一形式**根本解释不了**
这五个地址，真正的形态是**两跳**：

```
target = P + 4          P = 数据指针，存放在某张表里
P      = L + i*stride   L = 字面量（表基址），i = 行号
```

### 2.4 工具：`tools/story_table_locate.py`

```
python tools/story_table_locate.py rom/base.gba --target 0x53636C
python tools/story_table_locate.py rom/base.gba --all-story
python tools/story_table_locate.py rom/base.gba --all-story --json build/story-table-locate.json
```

- **ROM 指纹闸门**：读 `notes/evidence/consumer-evidence.json` 的 `rom_sha256`，
  与实际 ROM 的 SHA-256 比对；不一致即**以退出码 3 拒绝运行**（不重新生成证据文件）。
- 候选集来自 `tools.consumer_locate.LiteralIndex`（全量），**不是**证据文件的 54 张表。
- 输出 (a) 字面量可达性（算术可行数 + 代码佐证数）与 (b) raw data / 邻域指针。

**自检（工具有效性）**：拿一张**确实由字面量索引**的已知表跑同一个工具 ——
`0x5461C4`（战斗配置矩阵）报出 **71 条代码佐证命中**，读者含 `0x0806DF28`、
`0x08069040` 等；同一工具对五张 story bank 报 **0 条**。工具不是恒返回 0。

---

## 3. 机器扫描结果

### 3.1 (a) 字面量可达性：`L + index*stride + imm`

| 目标 | live literals 扫描数 | 算术可行 | **代码佐证命中** |
|---|---:|---:|---:|
| `0x0853636C` | 1196 | 20788 | **0** |
| `0x08536BC8` | 1196 | 20863 | **0** |
| `0x08538FF0` | 1196 | 20991 | **0** |
| `0x0853AB78` | 1196 | 20891 | **0** |
| `0x0853C3C0` | 1196 | 20924 | **0** |

> **结论（严格否定）**：**没有任何一个被原生代码加载的常量**能以
> `L + index*stride + imm` 的形式算出这五个地址。假设「游戏靠算术算出基址」被证伪。

### 3.2 (b) raw data

| 目标 | 目标自身 raw 次数 | `base-4`（真实基址）的 raw 位置 | 落在哪张表 |
|---|---:|---|---|
| `0x0853636C` | **0** | `0x465B78` | `0x08465B70+0x8`（code-referenced） |
| `0x08536BC8` | **0** | `0x465B80` | `0x08465B70+0x10` |
| `0x08538FF0` | **0** | `0x465BB0` | `0x08465B70+0x40` |
| `0x0853AB78` | **0** | `0x465BC8` | `0x08465B70+0x58` |
| `0x0853C3C0` | **0** | `0x465BE0` | `0x08465B70+0x70` |

`0x08465B70` 正是**声音 ID 表**（`notes/resource-locations.md` §音效 ID 表），
行距 8 字节；`+0x8 / +0x10 / +0x40 / +0x58 / +0x70` = **第 1 / 2 / 8 / 11 / 14 行**。
每张 bank 的真实基址在整个 ROM 里**只出现这一次**，就在声音 ID 表里。

---

## 4. 命中的原生代码

### 4.1 声音 ID 分发器 `0x0809AAC0`（Thumb）

```
0x0809AAC0: push  {lr}
0x0809AAC2: lsls  r0, r0, #0x10
0x0809AAC4: ldr   r2, [pc, #0x1c]     ; raw=074a
0x0809AAC6: ldr   r1, [pc, #0x20]     ; raw=0849   -> 字面量池 0x0809AAE8 = 0x08465B70
0x0809AAC8: lsrs  r0, r0, #0xd        ; raw=400b   -> r0 = sound_id * 8
0x0809AACA: adds  r0, r0, r1          ; raw=4018   -> r0 = 0x08465B70 + id*8
0x0809AACC: ldrh  r3, [r0, #4]        ; raw=8388   -> player_index
0x0809AD8: ldr   r1, [r0]            ; raw=0868   -> **r1 = 曲头指针（数据指针）**
0x0809AADC: bl    #0x809b1f4
```

字面量池实测：`0x0809AAE4 = 0x08465B40`（播放器槽数组）、`0x0809AAE8 = 0x08465B70`（声音 ID 表）。

### 4.2 曲头安装 `0x0809B1F4`（Thumb）—— **三个字段的读者**

```
0x0809B1FC: adds  r7, r1, #0          ; raw=0f1c   ; r7 = 曲头指针（SongHeader）
0x0809B208: ldrb  r2, [r7, #2]        ; raw=ba78   ; priority
0x0809B242: ldr   r0, [r7, #4]        ; raw=7868   ; **voicegroup  <- 读的就是 legacy 基址**
0x0809B244: str   r0, [r5, #0x30]     ; raw=2863
0x0809B25C: ldrb  r1, [r7]            ; raw=3978   ; **track_count (= legacy 条目数 - 1)**
0x0809B25E: cmp   r6, r1              ; raw=8e42
0x0809B27A: lsls  r1, r6, #2          ; raw=b100   ; index * 4
0x0809B27C: adds  r0, r7, #0          ; raw=381c
0x0809B27E: adds  r0, #8              ; raw=0830   ; **trackList = 曲头 + 8**
0x0809B280: adds  r0, r0, r1          ; raw=4018
0x0809B282: ldr   r0, [r0]            ; raw=0068   ; **track_ptrs[index]**
0x0809B284: str   r0, [r4, #0x40]     ; raw=2064
```

三个字段全部被原生代码读到：

| 字段 | 偏移 | 读者指令 | 语义 |
|---|---|---|---|
| `track_count` | `+0` | `0x0809B25C ldrb r1,[r7]` | 音轨条数 |
| `voicegroup` | `+4` | `0x0809B242 ldr r0,[r7,#4]` | 音色组指针（= legacy 基址本身） |
| `track_ptrs[i]` | `+8+4i` | `0x0809B27A`~`0x0809B282` | 第 i 条音轨字节码（步长 4） |

**这解释了一切**：legacy 提取器把 `+4` 当成「第 1 条」，于是把
`voicegroup` 和 `trackList[]` 一起看成了一张 N 条 u32 的「剧情指针表」，
而**真正被游戏读的第一个 u32 就是 `0x0846480C` 本身**——所以它的地址在 ROM 里
当然一次都不会出现（它只作为「曲头 + 4」这个**字段偏移**存在）。

### 4.3 为什么 `0x084648xx` 那一族看起来像「一族描述符」

因为它们**确实是**一族同构结构的首地址：12 字节 tone 记录数组（voicegroup）。
`notes/resource-locations.md` 记的「23 个 voicegroup、400 条 12 字节 tone 记录」
里的 5 个就是这五个。

---

## 5. 逐 bank 结论

| bank | 结论（一句话） | 真实基址 | 真实条目数 | 真实条目大小 | 原生读者 |
|---|---|---|---|---|---|
| `story` | **不是剧情表**：是声音 ID 1 的 m4a SongHeader（`voicegroup` + 8 条音轨指针），声明基址晚了 4 字节 | `0x536368` | 8 条音轨（+1 音色组） | 4 字节（指针数组）/ 8 字节（曲头头字段） | `0x0809B242 ldr r0,[r7,#4]`（读 `voicegroup`）；`0x0809B25C ldrb r1,[r7]`（读 `track_count`）；`0x0809B282 ldr r0,[r0]`（读 `track_ptrs[i]`）；到达路径 `0x0809AD8 ldr r1,[r0]` ← 声音 ID 表 `0x08465B70` 第 1 行 |
| `story-b` | 同上，是声音 ID **2** 的 SongHeader（10 条音轨） | `0x536BC4` | 10 | 4 | 同上；声音 ID 表第 2 行（`0x465B80`） |
| `story-c` | 同上，是声音 ID **8** 的 SongHeader（9 条音轨） | `0x538FEC` | 9 | 4 | 同上；声音 ID 表第 8 行（`0x465BB0`） |
| `story-d` | 同上，是声音 ID **11** 的 SongHeader（10 条音轨） | `0x53AB74` | 10 | 4 | 同上；声音 ID 表第 11 行（`0x465BC8`） |
| `story-e` | 同上，是声音 ID **14** 的 SongHeader（8 条音轨） | `0x53C3BC` | 8 | 4 | 同上；声音 ID 表第 14 行（`0x465BE0`） |

**身份裁决**：这五张 bank 的**“剧情”语义被证伪**，它们是**音频**内容。
legacy 命名（`story` / `story-b` …）与真实结构无关。

---

## 6. 判死检验（可推翻本文结论的检验）

| # | 结论 | 检验（能推翻它） | 判死条件 |
|---|---|---|---|
| T1 | 真实基址 = 声明基址 − 4，且 `track_count` = 声明条目数 − 1 | 读 `rom[base-4]`、`rom[base-3..base-1]` | 任一 bank 不满足 `rom[base-4] == entry_count-1` 且 `(block,prio,reverb) == (0,0,128)` |
| T2 | 五个真实基址由声音 ID 表索引 | 读 `read_u32(0x465B70 + id*8)`，id = 1/2/8/11/14 | 任一行的值 ≠ 对应 `base-4` |
| T3 | 原生读者是 `0x0809B242` / `0x0809B25C` / `0x0809B282`，派发器是 `0x0809AAC6`+`0x0809AD8` | 字节级核对 ROM：`0x0809B242`=`78 68`、`0x0809B25C`=`39 78`、`0x0809B282`=`00 68`、`0x0809AAC6`=`08 49`、`0x0809AD8`=`08 68`；池 `0x0809AAE8` = `0x08465B70` | 任一字节不符 |
| T4 | 首指针是 voicegroup（12 字节 tone 记录） | 解析 `base` 处 12 字节：`type ∈ {0,0x80}`；`type==0` 时 `ptr` 指向的 wave 头 `freq/1024 ∈ [1000,22050]` 且 `samples > 0` | 任一 bank 解析失败 |
| T5 | 「字面量算术可达」被严格否定 | `python tools/story_table_locate.py rom/base.gba --all-story` | 任一 bank 报出 `corroborated by code > 0` |
| T6 | 「payload 在前」是 m4a 音轨排布，不是剧情章节 | 逐条核对：第 i 条音轨的起点 = 上一个终点，`track_ptrs[last]` 的终点 = SongHeader 起点；并用 `tools/extract_audio.py rom/base.gba` 解出该曲目的音轨 | 音轨字节码无法解码 / 边界对不上 |

**T1~T4 的复现脚本**（纯静态、无副作用）：

```powershell
python -c "import struct; rom=open(r'rom/base.gba','rb').read(); \
 banks=[('story',0x53636C,9,1),('story-b',0x536BC8,11,2),('story-c',0x538FF0,10,8), \
        ('story-d',0x53AB78,11,11),('story-e',0x53C3C0,9,14)]; \
 print([(n, rom[b-4]==c-1, struct.unpack_from('<I',rom,0x465B70+sid*8)[0]==(b-4)+0x08000000) \
        for n,b,c,sid in banks])"
```

实测输出（每项 = (bank, T1, T2)）：

```
[('story', True, True), ('story-b', True, True), ('story-c', True, True),
 ('story-d', True, True), ('story-e', True, True)]
```

> 注意口径：legacy 的 `table_offset` 是**文件偏移**（`0x53636C`），
> 声音 ID 表里存的是 **ROM 地址**（`0x08536368`），两者差 `0x08000000`。

### 6.1 独立交叉验证：`tools/extract_audio.py`（本轮**未改动**该工具）

`python tools/extract_audio.py rom/base.gba` 的清单行（`id / slot / descriptor / trk / prio / rev`）：

```
  1     0  0x536368      8     0   128     978    1923    one_loop
  2     0  0x536BC4     10     0   128     974    1899    one_loop
  8     0  0x538FEC      9     0   128     961    2307    one_loop
 11     0  0x53AB74     10     0   128    1274    1923    one_loop
 14     0  0x53C3BC      8     0   128    1151    2115    one_loop
```

合计 `217 tracks / 400 tones / 79 waves`，`invalid control targets: 0`。
这条**独立于**本轮全部推导的第三方证据，与 §5 表逐行吻合。

---

## 7. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'
# disasm_thumb.py 需要 capstone.dll 的目录（story_table_locate.py 会自动探测，可不设）
$env:LIBCAPSTONE_PATH='build/python-deps/capstone/capstone/lib'

# 1) 全量字面量可达性 + raw data 扫描（五个 bank）
python tools/story_table_locate.py rom/base.gba --all-story
python tools/story_table_locate.py rom/base.gba --all-story --json build/story-table-locate.json

# 2) 单个目标
python tools/story_table_locate.py rom/base.gba --target 0x53636C --neighbors 0x400

# 3) 指纹闸门自检（必须以退出码 3 拒绝）
python tools/story_table_locate.py rom/experiment-00076d.gba --target 0x53636C
$LASTEXITCODE   # -> 3

# 4) 工具有效性自检（已知字面量索引表应报出大量命中）
python tools/story_table_locate.py rom/base.gba --target 0x5461C4    # -> corroborated by code: 71

# 5) 原生代码反汇编
python tools/disasm_thumb.py rom/base.gba 0x0809AAC0 --before 0 --size 0x40
python tools/disasm_thumb.py rom/base.gba 0x0809B1F4 --before 0 --size 0xA0

# 6) m4a 侧交叉验证（曲目清单）
python tools/extract_audio.py rom/base.gba
```

---

## 8. 走过的弯路（dead ends）

1. **把 `0x084648xx` band 当成「剧情条目描述符族」** —— 错。那是 voicegroup
   （12 字节 tone 记录）数组的首地址；`type/key/ptr/包络` 字段与
   `notes/resource-locations.md` 记录的 wave 样本逐字节吻合。
2. **把「payload 在前、指针表在后」当成剧情章节排布** —— 错。那是 m4a
   音轨字节码 + SongHeader 的排布。
3. **先用 `notes/evidence/consumer-evidence.json` 的 54 张表当候选集** —— 错（截断）。
   改用 `LiteralIndex` 全量索引后，「五个基址附近没有任何 live literal」才成为
   可信的结论；证据文件里的 `neighbors` 字段也只覆盖 ±0x1000 且只对 54 个地址有效。
4. **把「字面量索引里的读者」当真指令** —— 字面量索引是**线性扫全 ROM**，
   数据区里的字节也会被误解码成 `LDR [pc,#imm]`。实测：
   `0x08536A23` 的唯一「读者」是 `0x085369B2`（在数据区里），
   `0x0853C7F9` / `0x0853C8E0` 的读者也在数据区（`0x0853C804` / `0x0853C8BC`）。
   本轮把这些标为 `data-region only`，不计入「code-referenced」。
5. **只匹配 `imm` 的「佐证」** —— 假阳性重灾区（`adds rX, rY, #4` 遍地都是）；
   改为必须同时有**步长**佐证后，`story-c` / `story-d` 的 1~2 条假命中归零。
6. **找 ×12 的音色调色板索引写法** —— 代码里没有 `muls #12`，
   在 `0x08000000..0x080A0000` 全扫也没有命中；voicegroup 的 tone 记录步长 12
   是**数据格式**结论（由 `tools/extract_audio.py` 的解析器 + 本轮字节核对得出），
   本轮**没有**找到读 tone 记录的原生指令，故**不在此断言其原生读者**。
7. **找「章节 / per-chapter 实例」的更高层索引表** —— 不存在剧情层索引；
   更高层索引是**声音 ID 表 `0x08465B70`**（159 行 × 8 字节），
   其中非空 id 共 80 个（`1..18`、`51..54`、`101..158`），本文这 5 个都在其内。

---

## 9. 对现有结论的影响（建议，未擅自改动）

- `notes/completion-audit-20261020.md` 里这 5 条的待办
  「基址无效，需重新定位」可以结案：**基址有效但**偏移 4 字节，且**身份不是剧情表**，
  应改判为「音频曲头（m4a SongHeader）」，与 `notes/resource-locations.md`
  §音效 ID 表 归为同一族。
- `sequel/content/story*/bank.json` 的 `table_offset`（`0x53636C` 等）若继续使用，
  写回会打到**音轨指针数组的第 1 项**（= `voicegroup`）而不是曲头头字段；
  正确落点见 §5 表。这些文件本轮**未改动**（不在本任务所有权内）。
- `notes/legacy-table-base-correction-20261020.md` §5.1 的「21 个基址 ROM 从未提及」
  结论**依然成立**，但「这些是早期提取落点选错的产物」这一句对这 5 条需要修订：
  它们不是**噪声**，而是**真实结构被锚错了 4 字节**。

## 10. 回归基线

本任务只新增 2 个文件（`tools/story_table_locate.py`、`notes/evidence/story-table-family-20261020.md`），
未改动任何测试、生成器或 bank.json。

```
python -m unittest discover -s tests -p 'test_*.py'   -> Ran 84 tests ... OK
python tools/automated_test.py                        -> [PASS] 28/28 tests passed
```

> 注：任务书给的是 `-p 'test__.py'`。该模式在 fnmatch 里是**字面量**
> （`_` 不是通配符），实际匹配到 0 个文件（`Ran 0 tests` / 退出码 5）。
> 能跑出用例的模式是 `-p 'test_*.py'`。
> 79 → 84 的差额来自**其它并发 agent** 对 `tests/test_positions_integration.py`
> 与 `tests/test_u32_pointer_patches.py` 的改动（`git status` 可见），
> 与本任务无关。
