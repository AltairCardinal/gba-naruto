# L2 运行时证据：五张 ROM 表的原生消费者定点检查（2026-10-21）

**一句话**：`font-segments`、`sound-id-table`（含 5 个 m4a SongHeader）、
`character-template`、`maps`、`portrait` 这 **5 张表全部达到 L2** ——
断点命中了它们的**原生消费者**，命中瞬间的寄存器与表项字段逐位对应，
且寄存器的值与 ROM 静态字节互相印证。

**工具**：`tools/l2_runtime_capture.py`（门禁，不是转储器；不满足对应关系就退出非零）。

```powershell
python tools\l2_runtime_capture.py --self-test --json build\l2-runtime.json
```

ROM：`rom/base.gba`，sha256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

---

## 1. 判定结果

| 结构 | 基址 | L2 消费者（ARM） | 判定点 | 状态 | 运行时下标 |
|---|---|---|---|---|---|
| `font-segments` | `0x0853D644` | `0x08065EE6`（fn `0x08065EB8`） | `0x08065EF0` | ✅ L2 | 段 21 |
| `sound-id-table` | `0x08465B70` | `0x0809AAC6`（fn `0x0809AAC0`） | `0x0809AACE` | ✅ L2 | sound id 102 |
| `sound-id-table` | `0x08465B70` | `0x0809AB92`（fn `0x0809AB8C`） | `0x0809AB9A` | ✅ L2 | sound id 1 |
| `sound-id-table` | `0x08465B70` | `0x08061E9E`（fn `0x08061E98`） | `0x08061EA6` | ✅ L2 | sound id 154 |
| `character-template` | `0x0854241C` | `0x0806D984`（fn `0x0806D964`） | `0x0806D988` | ✅ L2 | 角色 id 1 |
| `character-template` | `0x0854241C` | `0x0806D4D2`（fn `0x0806D4A0`） | `0x0806D4F8` | ✅ L2 | 角色 id 1（ROM→RAM 拷贝） |
| `maps` | `0x0853D910` | `0x0808F4F6`（fn `0x0808F190`） | `0x0808F4FE` | ✅ L2 | 章节 36 |
| `portrait` | `0x085A4DEC` | `0x08096158`（fn `0x08096138`） | `0x0809615A` | ✅ L2 | id 1 / expr 1 |

“消费者地址”是**真正读表的那条指令**（`ldr rX,[pc,#imm]` 把表基址装进寄存器）；
“判定点”是工具下断点的位置——选在**基址、下标、字段值都已经在寄存器里**的那条指令。

---

## 2. 方法（本轮新定案的三件事）

### 2.1 基址与消费者都不许手写

* 基址来自 `tools/table_registry.py` 的 `TABLES`（本仓库的唯一权威），加 `ROM_BASE`；
* 消费者来自 `tools/consumer_locate.py` 的 `LiteralIndex`——**全 ROM** 的
  pc-relative 字面量索引。工具在每次运行时都会重新索引，并断言
  “本结构声明的消费者地址 ∈ 索引给出的读者集合”，否则直接失败。
  于是“消费者地址写错了”这件事**不可能**悄悄发生。

`LiteralIndex` 给出的读者（静态检查输出）：

```
font-segments      : 0x08065E88 0x08065EE6
sound-id-table     : 0x08061E3A 0x08061E9E 0x08061F00 0x08061F2C
                     0x0809AAC6 0x0809AAF2 0x0809AB3E 0x0809AB92 0x0809ABC6
character-template : 0x0806D4D2 0x0806D984 0x08089A00 0x080926D8
maps               : 0x08068FB8 0x08069040 0x08069220 0x08069268
                     0x0807AA90 0x0808067C 0x0808096C 0x0808F4F6
portrait           : 0x08096158
```

### 2.2 mGBA 断点的确切语义（此前没人写下来，本轮实测钉死）

用 `0x08065E88 ldr r4,[pc,#0x14]`（`r4` 应得 `0x0853D644`）做对照：

| 时刻 | `r4` | `r15` |
|---|---|---|
| 命中瞬间 | `0x00000002`（**旧值**） | `0x08065E8A` = 断点地址 + 2 |
| 命中后 `next` | `0x0853D644`（**已执行**） | `0x08065E8C` = 断点地址 + 4 |

⇒ **断点在目标指令执行之前命中**；命中时 `r15` 已经指向下一条指令，
但目标指令的副作用**还没发生**。这有两个直接后果：

1. 想看“寄存器里已经是基址/字段值”的时刻，必须把断点下在**消费者指令之后**，
   而不是下在读者指令上；
2. 命中后如果不 `delete` 断点就 `cont`，mGBA 会因为
   “刚执行过的指令地址 == 断点地址”而**立刻再报一次同一个命中**并把寄存器状态回滚。
   `tools/l4_playthrough.py` 的 `rearm()`（delete + 重挂）就是为此存在的。

### 2.3 两条确定性路线 + 存档复用

`savestate` 缓存在 `build/l2-states/`（`title.ss9` / `dispatch.ss9`），
**每条路线用独立的探针进程构建**——存档是一次运行的快照，
在已经打过剧情的会话里给下一条路线建存档会拿到“不是标题画面”的状态。

| 路线 | 走法 | 能到的消费者 |
|---|---|---|
| `title` | 开机 → 标题画面 → `START` → 剧情场景 54 → 连按 `A` | 字形段、sound id、角色模板、头像 |
| `dispatch` | 开机 → 导航到 `0x0808F8DC`（“下一场景”分派）→ `poke 0x020311EA` → `next` | 地图描述符 |

按键配方沿用已验证的那条：**按 8 帧 → 静默 120 帧**（游戏只认按下沿）。

> `maps` 必须在 `dispatch` 路线上取：故事侧读者 `0x0808F4F6` 之前有
> `cmp r4,#0x31`，章节号 **> 49 直接跳过读表**。自然流程跑的是场景 54 / 50，
> 两者都 > 49，所以自然流程**永远命中不到**地图表——这正是把它单列一条路线的原因。

---

## 3. 逐结构证据

### 3.1 `font-segments`（`0x0853D644`，31 槽 × 8 字节）

**消费者**：`0x08065EE6 ldr r2,[pc,#0x84]`（fn `0x08065EB8`，字形绘制）。
**判定点**：`0x08065EF0`。

```asm
08065ED8  adds r0, r5, #0        ; r5 = 字符码
08065EDA  bl   #0x8065e80        ; 段查找
08065EDE  lsls r0, r0, #0x18
08065EE0  lsrs r1, r0, #0x18     ; r1 = 段下标
08065EE6  ldr  r2, [pc, #0x84]   ; r2 = 0x0853D644   ← 表基址
08065EE8  lsls r0, r1, #3        ; r0 = 下标*8
08065EEA  adds r1, r2, #4
08065EEC  adds r1, r0, r1
08065EEE  adds r0, r0, r2        ; r0 = 基址 + 下标*8   ← 表项地址
08065EF0  ldrh r0, [r0]          ; 段首码点
```

**命中瞬间（原始值）**

```
pc=0x08065EF2  lr=0x08065EDF  sp=0x03001148
r0=0x0853D6EC  r1=0x0853D6F0  r2=0x0853D644  r3=0x000098EA
r4=0x00000002  r5=0x000098EA  r6=0x00000002  r7=0x0200DE94
r8=0x0200DE9E  r9=0x00000002  r10=0x0200DE94 r11=0x00000000 r12=0x00000002
表基址字节(16): 40 81 6d 00 54 d9 09 08 40 82 b2 00 54 e9 09 08
表项 @0x0853D6EC (16): 73 98 8a 00 00 e8 5a 08 40 99 bd 00 40 f9 5a 08
```

**寄存器 ↔ 字段对应**

| 寄存器 | 值 | 对应字段 |
|---|---|---|
| `r2` | `0x0853D644` | **字形段表基址** |
| `r0` | `0x0853D6EC` | 表项地址 = 基址 + 21×8 |
| `r5` | `0x000098EA` | 正在渲染的字符码 |

**静态交叉验证**：表项第 21 号 = `u16 start = 0x9873`、`u8 width = 138`
⇒ 覆盖区间 `[0x9873, 0x98FD]`；**寄存器里的字符码 `0x98EA` 落在区间内**。
模拟器在该表项读到的 16 字节与 ROM 逐字节相同
（`73 98 8a 00 00 e8 5a 08 40 99 bd 00 40 f9 5a 08`）。

### 3.2 `sound-id-table`（`0x08465B70`，159 项 × 8 字节）

**消费者**：`0x0809AAC6 ldr r1,[pc,#0x20]`（fn `0x0809AAC0`，声音分派）。
**判定点**：`0x0809AACE`。

```asm
0809AAC0  push {lr}
0809AAC2  lsls r0, r0, #0x10     ; r0 = sound id << 16
0809AAC4  ldr  r2, [pc, #0x1c]   ; r2 = 0x08465B40（voicegroup 表）
0809AAC6  ldr  r1, [pc, #0x20]   ; r1 = 0x08465B70   ← sound id 表基址
0809AAC8  lsrs r0, r0, #0xd      ; r0 = sound id * 8
0809AACA  adds r0, r0, r1        ; r0 = 基址 + id*8
0809AACC  ldrh r3, [r0, #4]      ; r3 = 表项 +4 的 u16
```

**命中瞬间（原始值，sound id 102）**

```
pc=0x0809AAD0  lr=0x08061E77  sp=0x030011D0
r0=0x08465EA0  r1=0x08465B70  r2=0x08465B40  r3=0x00000001
r4=0x00000001  r5=0x00000081  r6=0x0200A884  r7=0x0200A8A4
r8=0x00000000  r9=0x08060D54  r10=0x0201BD60 r11=0x00000000 r12=0x00000088
表基址字节(16): 68 60 46 08 00 00 00 00 68 63 53 08 00 00 00 00
表项 @0x08465EA0 (16): 88 ce 53 08 01 00 01 00 a4 ce 53 08 01 00 01 00
```

**寄存器 ↔ 字段对应**

| 寄存器 | 值 | 对应字段 |
|---|---|---|
| `r1` | `0x08465B70` | **sound id 表基址** |
| `r0` | `0x08465EA0` | 表项地址 = 基址 + 102×8 |
| `r3` | `0x00000001` | 表项 `+0x04` 的 u16（voice 索引） |

**静态交叉验证**：表项 `+0x00` = `0x0853CE88`（m4a SongHeader），
`+0x04` = `1` —— 与寄存器 `r3` **逐位相等**；模拟器读到的表项字节与 ROM 相同。

**另外两个消费者（同表）**

| 消费者 | 判定点 | sound id | 表项 | `+0x00` 指针 | `+4` u16 |
|---|---|---|---|---|---|
| `0x0809AB92`（fn `0x0809AB8C`） | `0x0809AB9A` | **1** | `0x08465B78` | `0x08536368` | 0 |
| `0x08061E9E`（fn `0x08061E98`） | `0x08061EA6` | **154** | `0x08466040` | `0x0853D4F4` | 2 |

（`0x08061E98` 这条路在读 `+4` 时把 `r1`（基址）覆盖成了字段值，
所以它的判定点上基址已经不在寄存器里——工具对此**显式声明**，
基址由静态检查里的“读者 ∈ LiteralIndex 读者集合”承担。）

### 3.3 五个 m4a SongHeader：**基址要更正**

本轮在 ROM 上逐条核对（`tools/audio_song_headers.py` 的输出与
`tools/table_registry.py` 的 `audio_song_*` 条目一致）：

| sound id | 表项 | 表项 `+0x00` 指针 | 旧称基址（**早 4 字节**） | 正确基址 |
|---|---|---|---|---|
| 1 | `0x08465B78` | `0x08536368` | `0x0853636C` | **`0x08536368`** |
| 2 | `0x08465B80` | `0x08536BC4` | `0x08536BC8` | **`0x08536BC4`** |
| 8 | `0x08465BB0` | `0x08538FEC` | `0x08538FF0` | **`0x08538FEC`** |
| 11 | `0x08465BC8` | `0x0853AB74` | `0x0853AB78` | **`0x0853AB74`** |
| 14 | `0x08465BE0` | `0x0853C3BC` | `0x0853C3C0` | **`0x0853C3BC`** |

⇒ 旧 `story` / `story-b` / `story-c` / `story-d` / `story-e` 五个 bank 的基址
**都比 SongHeader 头部晚 4 字节**（锚在 voicegroup 指针上，不是头部起点）。
这与 `tools/table_registry.py` 里已有的裁决一致
（“each legacy base 4 bytes late”）。

其中 **sound id 1 与 id 2 已在运行时被证明**：
`0x0809AB9A` 命中时 `r0 = 0x08465B78`（= 基址 + 1×8）、
表项 `+0x00` = `0x08536368`，与 registry 的 `audio_song_1` **逐位相等**；
id 2 同理 → `0x08536BC4`。id 8 / 11 / 14 本轮**只做了静态核对**
（见工具的静态检查 `sound id N points at the registered SongHeader`），
**尚未在运行时命中**。

### 3.4 `character-template`（`0x0854241C`，63 条 × `0xB4`）

**消费者 A**：`0x0806D984 ldr r0,[pc,#0xc]`（fn `0x0806D964`，逐角色属性装载）。
**判定点**：`0x0806D988`。

```asm
0806D96E  adds r6, r0, #0
0806D974  ldrb r2, [r6]          ; r2 = 角色 id
0806D97E  movs r0, #0xb4
0806D982  muls r1, r0, r1        ; r1 = id * 0xB4
0806D984  ldr  r0, [pc, #0xc]    ; r0 = 0x0854241C   ← 角色模板表基址
0806D986  adds r1, r1, r0        ; r1 = 基址 + id*0xB4
0806D988  mov  sb, r1
```

**命中瞬间（原始值）**

```
pc=0x0806D98A  lr=0x0806D5CB  sp=0x03001228
r0=0x0854241C  r1=0x085424D0  r2=0x00000001  r3=0x00000001
r4=0x08542580  r5=0x08542578  r6=0x02022EF0  r7=0x00000000
r8=0x08542578  r9=0x00000000  r10=0x00000000 r11=0x00000000 r12=0x02022FA0
表基址字节(16): 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
表项 @0x085424D0 (前16): 01 0e 0d 08 03 05 05 00 0f 00 50 00 02 01 00 00
```

**寄存器 ↔ 字段对应**

| 寄存器 | 值 | 对应字段 |
|---|---|---|
| `r0` | `0x0854241C` | **角色模板表基址** |
| `r2` | `1` | 角色 id |
| `r1` | `0x085424D0` | 表项地址 = 基址 + 1×`0xB4` |

**静态交叉验证**：`r2`（寄存器里的角色 id）**等于**表项下标；
模拟器读到的整条 `0xB4` 记录与 ROM 逐字节相同。

**消费者 B**：`0x0806D4D2 ldr r0,[pc,#0x40]`（fn `0x0806D4A0`），
**判定点** `0x0806D4F8`——这是 **ROM → RAM 的拷贝点**：

```asm
0806D4D4  adds r7, r1, r0        ; r7 = 基址 + id*0xB4（模板项）
0806D4F4  adds r1, r7, r0        ; r1 = 模板 + 4*k
0806D4F6  ldrb r0, [r1, #0xc]    ; r0 = 模板里的一个字节
0806D4F8  strb r0, [r2, #0x14]   ; → 运行时角色结构
```

命中瞬间：`r7 = 0x085424D0`（模板项）、`r1 + 0x0C = 0x085424DC`、
**`r0 = 0x02`**，而 ROM 在 `0x085424DC` 的字节**正是 `0x02`**
（记录 `01 0e 0d 08 03 05 05 00 0f 00 50 00 02 ...` 的第 13 个字节）；
目的地 `r2 + 0x14 = 0x02022F04`（WRAM 里的运行时角色结构）。

### 3.5 `maps`（`0x0853D910`，32 字节 / 条）

**消费者**：`0x0808F4F6 ldr r1,[pc,#0x10]`（fn `0x0808F190`，剧情侧场景设置）。
**判定点**：`0x0808F4FE`。

```asm
0808F4F2  cmp  r4, #0x31         ; 章节号 > 49 就不读这张表
0808F4F4  bhi  #0x808f50c
0808F4F6  ldr  r1, [pc, #0x10]    ; r1 = 0x0853D910   ← 地图描述符表基址
0808F4F8  lsls r0, r4, #5         ; r0 = 章节号 * 32
0808F4FA  adds r0, r0, r1
0808F4FC  ldrb r0, [r0, #0x1c]    ; r0 = 描述符的 +0x1C 字节
0808F4FE  b    #0x808f514
```

**命中瞬间（原始值）**

```
pc=0x0808F500  lr=0x0808F4EF  sp=0x03001238
r0=0x00000007  r1=0x0853D910  r2=0x01000400  r3=0x00000170
r4=0x00000024  r5=0x00000100  r6=0x00000000  r7=0x00000000
r8=0x00000000  r9=0x00000000  r10=0x00000000 r11=0x00000000 r12=0x0000000F
表基址字节(16): 5c 00 40 00 80 9f 0b 08 08 d6 0b 08 0c d7 0b 08
表项 @0x0853DD90 (32): 34 00 22 00 fc e7 0f 08 84 09 10 08 3c 0a 10 08
                   00 00 00 00 38 0c 10 08 34 10 10 08 07 00 00 00
```

**寄存器 ↔ 字段对应**

| 寄存器 | 值 | 对应字段 |
|---|---|---|
| `r1` | `0x0853D910` | **地图描述符表基址** |
| `r4` | `0x24` = 36 | 章节号（= 被分派的场景号） |
| `r0` | `0x07` | 描述符 `+0x1C` 的字节（zone 字段） |

**静态交叉验证**：ROM 在 `0x0853D910 + 36×32 + 0x1C = 0x0853DDAC` 的字节
**就是 `0x07`**；描述符 `+0x04` = `0x080FE7FC`（合法 ROM 图形指针）。
模拟器在 `+0x1C` 读到的字节与 ROM 相同。

> 注意：`+0x1C` 这个字节的**业务名仍未定**（`notes/alias-conflicts-20261020.md`
> 里 `maps` / `encounter-zones` 的裁决把它记为「zone_id 命名待定」）。
> 本轮只证明「消费者按章节号选中描述符并读了 `+0x1C`」，**不宣称它的语义**。

### 3.6 `portrait`（`0x085A4DEC`，`id*40 + expr*8`）

**消费者**：`0x08096158 ldr r2,[pc,#8]`（fn `0x08096138`）。
**判定点**：`0x0809615A`。

```asm
08096138  push {lr}
0809613A  lsls r0, r0, #0x18
0809613C  lsrs r2, r0, #0x18     ; r2 = id
0809613E  lsls r1, r1, #0x18
08096140  lsrs r1, r1, #0x18     ; r1 = 表情号
08096142  cmp  r1, #5            ; 表情 5 是特例
08096144  bne  #0x8096150
...
08096150  lsls r0, r2, #2        ; r0 = id*5
08096152  adds r0, r0, r2
08096154  lsls r0, r0, #3        ; r0 = id*40
08096156  lsls r1, r1, #3        ; r1 = expr*8
08096158  ldr  r2, [pc, #8]      ; r2 = 0x085A4DEC   ← 头像指针表基址
0809615A  adds r1, r1, r2        ; r1 = 基址 + expr*8
0809615C  adds r0, r0, r1        ; r0 = 基址 + id*40 + expr*8
```

**命中瞬间（原始值）**

```
pc=0x0809615C  lr=0x080961C3  sp=0x030011B4
r0=0x00000028  r1=0x00000008  r2=0x085A4DEC  r3=0x00000000
r4=0x00000000  r5=0x00000000  r6=0x00000000  r7=0x00000000
r8=0x00000001  r9=0x00000001  r10=0x00000000 r11=0x00000000 r12=0x00000000
表基址字节(16): 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
表项 @0x085A4E1C (16): 44 99 40 08 a4 a6 40 08 24 a7 40 08 f8 b4 40 08
```

**寄存器 ↔ 字段对应**

| 寄存器 | 值 | 对应字段 |
|---|---|---|
| `r2` | `0x085A4DEC` | **头像指针表基址** |
| `r0` | `0x28` = 40 | `id × 40` ⇒ **id = 1** |
| `r1` | `0x08` | `expr × 8` ⇒ **表情 = 1** |

**静态交叉验证**：两个寄存器合起来指向 `0x085A4DEC + 40×1 + 8×1 = 0x085A4E1C`，
该表项 = `0x08409944` / `0x0840A6A4`（两个头像拼块指针，都是合法 ROM 地址），
且**非空**；模拟器读到的 8 字节与 ROM 相同。

> **关于「表项全零」的旧顾虑**：`portrait` 的 id 0（`0x085A4DEC`）整条是零，
> 若命中落在那里就**没有可对应的字段**。本轮命中的是 id 1 / expr 1，
> 表项非零，所以「读到了哪一条」是可判定的。工具把
> 「表项不得全零」写成硬性检查——命中全零槽位会**判失败**而不是默默放过。

---

## 4. 可证伪测试

每条命令都会在“结论不成立”时**退出非零**。

| # | 结论 | 怎样算被推翻 | 命令 |
|---|---|---|---|
| F1 | 5 张表都有原生消费者且消费者地址正确 | LiteralIndex 的读者集合里不含所用的消费者地址 | `python tools\consumer_locate.py rom\base.gba --target 0x53D644`（其余 4 张同理，把偏移换成 `0x465B70` / `0x54241C` / `0x53D910` / `0x5A4DEC`） |
| F2 | 字形段表基址 `0x0853D644`、段 21 覆盖 `0x98EA` | `r2` 不是基址，或段区间不含寄存器里的字符码 | `python tools\l2_runtime_capture.py font-segments` |
| F3 | sound id 102 → `0x0853CE88`；sound id 1 → `0x08536368` | `r1` 不是基址、`r3` ≠ 表项 `+4`、指针不是 ROM 地址 | `python tools\l2_runtime_capture.py sound-id-table` |
| F4 | 5 个 SongHeader 的**正确**基址 | 表项 `+0x00` 与 `audio_song_*` 注册值不等 | `python tools\audio_song_headers.py`（看 `id 1 / 2 / 8 / 11 / 14` 行的 `header` 列）；或 `python tools\l2_runtime_capture.py --self-test` 的静态检查 `sound id N points at the registered SongHeader` |
| F5 | 角色模板基址 `0x0854241C`、下标 = 角色 id、ROM→RAM 拷贝逐字节相等 | `r0` 不是基址、`r2` ≠ 表项下标、寄存器里的字节 ≠ ROM 字节 | `python tools\l2_runtime_capture.py character-template` |
| F6 | 地图描述符基址 `0x0853D910`、章节 36 的 `+0x1C` = `0x07` | `r1` 不是基址、`r0` ≠ ROM 在 `+0x1C` 的字节 | `python tools\l2_runtime_capture.py maps` |
| F7 | **门禁真的会咬人**（不是空过） | 用一个消费者自己会跳过的章节号，捕获必须失败 | `python tools\l2_runtime_capture.py maps --scene 54` → 消费者 `cmp r4,#0x31` 跳过读表 ⇒ 打印 `[L2 FAIL]` 并**退出 1**（本轮实测：exit=1） |
| F8 | 门禁的对应关系不是空转 | 把关键寄存器改坏后检查必须失败 | `python tools\l2_runtime_capture.py --self-test` 里的 `negative control`（本轮 5/5 全部“咬住”） |

F7 的实测输出：

```
== maps  [L2 FAIL]  base=0x0853D910 route=dispatch
FAILED:
  - maps: the runtime correspondence was not observed
（退出码 1）
```

---

## 5. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'

# 全部 5 张表 + 静态检查 + 反向对照；退出码 0 表示全部达到 L2
python tools\l2_runtime_capture.py --self-test --json build\l2-runtime.json

# 单个结构
python tools\l2_runtime_capture.py font-segments
python tools\l2_runtime_capture.py sound-id-table
python tools\l2_runtime_capture.py character-template
python tools\l2_runtime_capture.py maps
python tools\l2_runtime_capture.py portrait

# 列表 / 重建存档
python tools\l2_runtime_capture.py --list
python tools\l2_runtime_capture.py --all --rebuild-states
```

前置：`build/mgba-probe/mgba-probe.exe` 存在（`python tools\mgba_probe\build.py` 构建）。
本轮实测：存档已缓存时整套 **6.6 s**，从零构建存档 **7.8 s**。

---

## 6. 仍未达到 / 本轮放弃的部分

| 项 | 状态 | 试过什么 / 为什么 |
|---|---|---|
| `maps` 的**地图 loader** `0x08069040`（fn `0x08068FF0`） | **未达到 L2** | registry 的裁决把它列为“关键消费者”，但它只在**战斗地图装载**时跑。本轮试过：自然流程（场景 54 → 50）连按 `A` 共 60 步，战斗单位数组 `0x020240C0` 始终为空 ⇒ 没进战斗；逐个分派场景 1..16、每场连按 `A` 40 步，也没有任何一场把战斗单位数组填起来。**结论**：`maps` 的 L2 走故事侧读者 `0x0808F4F6`，loader 侧仍是空的。 |
| `character-template` 的读者 `0x08089A00`（fn `0x080899EC`）、`0x080926D8`（fn `0x08092694`） | **未命中** | 前者只有一个调用者 `0x08089B7E`（紧挨着 `0x0806D964` 的两个调用者 `0x08089B68` / `0x08089B76`）；后者三个调用者是 `0x08092D0E` / `0x080931DA` / `0x0809365C`。标题流程与场景分派流程都触发不到（本轮没有再往下定性它们属于哪个界面）。 |
| sound id 8 / 11 / 14 的**运行时**捕获 | **仅静态核对** | 运行时只命中到 id 1、2、102、154；8/11/14 对应的 SongHeader 由静态检查核对（表项 `+0x00` 与 registry 相等）。 |
| `portrait` 的 id 0（整条为零） | **不可用作证据** | 表项全零，没有可对应字段；工具对此判失败。 |
| `maps` `+0x1C` 字段的业务语义 | **仍未定** | 本轮只证明“按章节号选中描述符并读了 `+0x1C`”，命名仍待定。 |
| L3（模拟器正常按键）/ L4（完整通关） | **不宣称** | 按 `notes/runtime-verification-gates-20260710.md` §4 的自陈清单，本轮只推进了 L2。 |

---

## 7. 对仓库的影响（第一批只新增两个文件；第二批见 §B.8）

| 文件 | 说明 |
|---|---|
| `tools/l2_runtime_capture.py` | 新增。L2 采集门禁：基址来自 `tools/table_registry.py`，消费者来自 `tools/consumer_locate.py` 的 `LiteralIndex`，存档走 `build/l2-states/`，退出码即门禁结果。 |
| `notes/evidence/l2-runtime-evidence-20261021.md` | 新增。本文件。 |

**未改动**：`tools/completion_audit.py`、`tools/table_registry.py`、
`tools/consumer_locate.py`、`tools/mgba_probe/*`、`sequel/content/*`、`docs/*`、
其它笔记。

> **给 owner / 另一条工作线的两条建议（本轮没有动那些文件）**：
> 1. 旧 `story` / `story-b` / `story-c` / `story-d` / `story-e` 五个 bank 的
>    基址早 4 字节，正确值见 §3.3；`sequel/content/` 里对应的 `bank.json`
>    若还写着旧值，需要同步（`tools/table_registry.py` 里已经是正确值）。
> 2. `tools/completion_audit.py` 若要按结构给出 L2 档位，
>    可以把 `tools/l2_runtime_capture.py --self-test` 的 JSON
>    （`build/l2-runtime.json`）作为可机读的证据来源。

---

## 8. 本轮的方法记录

* **断点语义**：mGBA 的断点在目标指令**执行前**命中（§2.2）。因此
  “寄存器里已经有字段值”的快照必须下在消费者指令**之后**。
* **存档隔离**：每条路线用独立探针进程建存档；否则第二条路线拿到的
  不是标题画面（本轮踩过：同一进程里先建 `dispatch` 再建 `title`，
  `title` 存档里的游戏已经在剧情里，角色模板消费者再也命中不到）。
* **消费者发现**：用全 ROM 的字面量索引（`LiteralIndex`）而不是手写地址；
  `notes/evidence/units-offset-table-20261020.md` §3 已经记过一次教训
  ——「证据文件只存了 54 张表，不足以做邻域分析」，全量索引才有 18051 个值。
* **“空表项”与“字段语义”**：表项全零时无法建立字段对应，本轮把这条
  写成硬性检查（`portrait` id 0 即被此判失败）。

---

# 附录 B：L2 第二批（12 张表）的静态消费者分析（2026-10-21）

> 本节先落盘**静态**结论（读者地址 + 反汇编 + 判定点候选），
> 运行时命中结果见下面 §B.5。

## B.0 方法

* 读者地址由 `tools/consumer_locate.py` 的 `LiteralIndex`（全 ROM 字面量索引）
  **重新计算**，不是抄任务书里的地址；任务书给的地址与索引结果一致的地方
  在 §B.3 里逐条对照。
* 反汇编窗口由 `tools/l2_batch2.py`（本轮新增）打印：
  `python tools\l2_batch2.py --all --window 10`。
* **判定点的选法**（沿用第一批的约定）：mGBA 的断点在目标指令**执行前**命中，
  所以判定点必须下在“基址、下标、字段值都已经在寄存器里”的那条指令上，
  即 `ldr rX,[pc,#imm]`（装基址）之后的**下一条**指令。

## B.1 逐表：读者 → 判定点候选

| 结构 key | 基址 | 原生读者（LiteralIndex） | 本轮选用的判定点 | 步长 |
|---|---|---|---|---|
| `battle-handlers` | `0x0853E698` | `0x0807F934`, `0x0807FD28` | `0x0807F942` | 8 |
| `fonts` | `0x0853E596` | `0x0807F0FC` | `0x0807F108` | 1（u8 宽度） |
| `data-table-a` | `0x085A143C` | `0x0808A6BA`, `0x0808B19E` | `0x0808B1A6` | 4 |
| `data-table-b` | `0x085A2034` | `0x080985D8`, `0x08099D26` | `0x08099D2E` | 4 |
| `function-pointers` | `0x0853D5F0` | `0x08061DD4` | `0x08061DDA` | 4 |
| `tile-assets` | `0x085A320C` | 9 个（`0x08087DFC` … `0x08099CE4`） | `0x08098822` | 68 |
| `sprite-frame-descriptors` | `0x0853EE98` | `0x080806BA`, `0x0808077E`, `0x0808082E` | `0x080806BC` | 10 |
| `battle-encounters` | `0x0854229C` | `0x08087D00`, `0x08087DE0` | 见 §B.2 | 16 |
| `ninjutsu-names` | `0x08599634` | 9 个（`0x0806F504` … `0x080973E6`） | `0x080796F0` | 4 |
| `reward-table` | `0x0859EAE0` | `0x080893F0`, `0x08089EA2`, `0x08089F00`, `0x08089F80` | `0x08089EAC` | 24 |
| `cutscene-scripts` | `0x0853DF70` | `0x08072F0C` | `0x08072F14` | 8 |
| `sprite-action-table` | `0x08596CCC` | 18 个（`0x0806A826` … `0x080930A2`） | `0x0806B770` | 144（= 9 × 16） |

## B.2 与任务书不一致 / 需要更正的三处

1. **`cutscene-scripts` 的身份**：任务书写“过场脚本表”，仓库里早已裁决
   （`notes/evidence/cutscene-block-format-20261020.md`）它是
   **关卡数据块表**：4 项 × 8 字节，每项一对指针
   （LZ77 4bpp 图块 → VRAM `0x06016000`、LZ77 16 色调色板 → 调色板 RAM
   `0x05000380`），由 BIOS `svc 0x12` 解压。原生读者 `0x08072F0C` 直接证明
   步长是 **8**，不是 4：
   ```
   08072F0C  ldr  r4, [pc, #0x2c]   ; r4 = 0x0853DF70  ← 基址
   08072F0E  mov  r0, r8            ; r0 = 块下标
   08072F10  lsls r5, r0, #3        ; r5 = 下标 * 8
   08072F12  adds r0, r5, r4        ; r0 = 基址 + 下标*8
   08072F14  ldr  r0, [r0]          ; r0 = LZ77 图块指针
   08072F16  ldr  r1, [pc, #0x28]   ; r1 = 0x06016000 (VRAM)
   08072F18  bl   #0x809c0e8        ; LZ77UnCompVram
   08072F1C  adds r4, #4            ; r4 = 基址 + 4（调色板槽）
   08072F1E  adds r5, r5, r4        ; r5 = 基址 + 下标*8 + 4
   08072F20  ldr  r0, [r5]          ; r0 = LZ77 调色板指针
   08072F22  ldr  r1, [pc, #0x20]   ; r1 = 0x05000380 (调色板 RAM)
   ```
2. **`sprite-action-table` 的寻址**：任务书写 `id*144 + action*16`，
   但原生代码里 **`*144` 的那一项是下标本身**（`ldrb` 取出的字节），
   `+16` 的那一步并不在这条链上；本轮按代码实际算的
   `基址 + 下标*144` 立证（见 §B.4 的 `sprite-action-table`）。
3. **`battle-encounters` 的读者**：`LiteralIndex` 给出的两个读者是
   `0x08087D00` / `0x08087DE0`（都在 fn `0x08087C9C`），
   与任务书“2 个原生读者”一致，但任务书没给地址。

## B.3 读者地址：任务书 vs LiteralIndex（逐条对照）

`tools/l2_batch2.py --all` 的输出与任务书给的地址**逐条一致**：

```
battle-handlers          : 0x0807F934 0x0807FD28
fonts                    : 0x0807F0FC
data-table-a             : 0x0808A6BA 0x0808B19E
data-table-b             : 0x080985D8 0x08099D26
function-pointers        : 0x08061DD4
tile-assets              : 0x08087DFC 0x0809845C 0x0809881E 0x08098A92
                           0x08098D4A 0x08098EEE 0x080990D2 0x0809916A
                           0x080995FE 0x08099CE4
sprite-frame-descriptors : 0x080806BA 0x0808077E 0x0808082E
battle-encounters        : 0x08087D00 0x08087DE0
ninjutsu-names           : 0x0806F504 0x08070642 0x080796E4 0x08079704
                           0x08081642 0x080816FE 0x0808E9F8 0x0808EA62
                           0x08090286 0x08090350 0x0809734C 0x080973E6
reward-table             : 0x080893F0 0x08089EA2 0x08089F00 0x08089F80
cutscene-scripts         : 0x08072F0C
sprite-action-table      : 0x0806A826 0x0806B76C 0x0807AF1C 0x0807AF64
                           0x0807AFA4 0x0807AFE4 0x0807B030 0x0807B092
                           0x0807B28C 0x080862D4 0x080888D0 0x080889CA
                           0x0808937A 0x0808AC00 0x0808D728 0x0808D840
                           0x0808DE0E 0x080930A2
```

## B.4 第三条路线：`battle`（本轮新增，也是第二批的主要突破口）

第一批只有 `title` 和 `dispatch` 两条路线；**战斗子系统里的消费者**（字宽表、
地图事件分派表、图块/精灵资源表、精灵帧描述符表……）两条都到不了。
本轮从 `tools/mgba_probe/l4_battle_matrix.py`（**只读，未改动**）里找到了
“用三次内存写强制进入一场战斗”的配方，并把它实现成第三条路线：

| 步骤 | 地址 | 写法 |
|---|---|---|
| 1 | `0x020311D4 + 0x12` = `0x020311E6`（u16） | `poke16 0x020311E6 0x0110`（相位 = 战斗） |
| 2 | `0x020311D4 + 0x16` = `0x020311EA`（u8） | `poke 0x020311EA <group>`（战场组号） |
| 3 | `0x020311D4 + 0x19` = `0x020311ED`（u8） | `poke 0x020311ED <sub>`（编成子配置） |

写这三次的时候，核心必须**停在剧情状态机的循环头 `0x0808F752`**
（`build/l2-states/battle.ss9` 就是停在这个地址上的存档）。
之后状态机自己跑 `0x0808F92E → 0x080732B4 → 0x0808A588`，
战斗地图和 12 个战斗单位全部被装载。

实测（`tools/l2_batch2.py --battle-diag`）：

```
group= 40 sub=0  seen=['entry','phase_110','vm','wrapper']  units=1  mapid=28
group=  1 sub=0  seen=['entry','phase_110','vm','wrapper']  units=6  mapid=01
group= 11 sub=1  seen=['entry','phase_110','vm','wrapper']  units=0  mapid=0b
```

⇒ **地图号 = group**，战斗单位确实被填进 `0x020240C0` 的 12 槽数组。
编成矩阵有 48 组 × 3 个子配置，所以这条路线可以逐个跑 **144 场战斗**。

## B.5 运行时命中结果：**5 / 12 达到 L2**

| 结构 | 基址 | L2 消费者（ARM） | 判定点 | 状态 | 运行时下标 |
|---|---|---|---|---|---|
| `data-table-b` | `0x085A2034` | `0x080985D8`（fn `0x080983B8`） | `0x080985E0` | ✅ L2 | 56 |
| `function-pointers` | `0x0853D5F0` | `0x08061DD4`（fn `0x08061D8C`） | `0x08061DDA` | ✅ L2 | 2 |
| `reward-table` | `0x0859EAE0` | `0x08089EA2`（fn `0x08089E84`） | `0x08089EAE` | ✅ L2 | 1 |
| `cutscene-scripts` | `0x0853DF70` | `0x08072F0C`（fn `0x08072EDC`） | `0x08072F16` | ✅ L2 | 0 |
| `sprite-action-table` | `0x08596CCC` | `0x0806B76C`（fn `0x0806B720`） | `0x0806B770` | ✅ L2 | 1 |

逐结构的原始寄存器、寄存器↔字段对应表、静态交叉验证与反向对照见
**附录 C**（由 `tools/l2_note_report.py` 从 `build/l2-runtime.json` 生成，
数字不可能与跑出它的那次运行脱节）。

> `cutscene-scripts` 的基址在 registry 里是 `verified=False`：
> 那个标志针对的是**旧名字**（「过场脚本表」已被证伪），不是地址。
> 工具对此**显式声明**（`registry_unverified` 字段），并且静态检查会额外断言
> “该消费者 ∈ LiteralIndex 的读者集合”——运行时证据独立地证明了
> `0x0853DF70` 是一张活表。

## B.6 未达到清单：**7 / 12**

| 结构 | 试过什么 / 为什么没到 |
|---|---|
| `battle-handlers` | 消费者 fn `0x0807F414` 只有一个调用点 `0x0807ABD4`（在 fn `0x0807AA8C` 里，而 `0x0807AA8C` 只被 `0x0807AB72` / `0x0807C694` 调用）。**试过**：① 144 场战斗（48 组 × 3 子配置、每场 16 次 A 键）；② group 0..11 × sub 0..1 共 24 场、每场 24 次按键、键循环 `A,B,UP,DOWN,LEFT,RIGHT,START`（并把 `0x0807ABD4` 一起挂上做监视）；③ 剧情扫场景 1..20 与 30..50（同样的键循环）。**三次都没有进到 `0x0807ABD4`**。下标来自 WRAM `r9+0x770`，说明这是**地图事件**分派器，需要真正的地图事件触发。 |
| `fonts` | 消费者 fn `0x0807EE50` **没有任何 `bl` 调用点**：它的函数地址 `0x0807EE51` 作为**数据字**出现在 `0x0853ECB0`、`0x0853ECB8`、`0x0853ECC0`、`0x0853ECC8`、`0x0853ECD0`、`0x0853ECD8` —— 它是被一张 **8 字节记录（两个代码指针）的回调表**间接调用的。上面那三轮（144 场战斗 / 24 场强化按键战斗 / 剧情扫场景）都没让这张回调表被调用。 |
| `data-table-a` | 消费者 fn `0x0808AFE0` 被 `0x0808B420` / `0x0808B51A` 调用（场景对象创建路径）；同样挂了 `0x0808B420` 做监视，144 场战斗 + 24 场强化按键战斗 + 剧情扫场景 1..20 / 30..50 都没执行到。 |
| `tile-assets` | 消费者 fn `0x0809880C` 唯一调用点是 `0x08098E22`；另一个读者 `0x08087DFC` 在 fn `0x08087C9C` 里，而该 fn 只被 thunk `0x0808A69C` 调用（`bl 0x08087C9C` + 尾跳），thunk 本身没有 `bl` 调用点 → 也是间接回调。两者都被挂上监视过，三轮路线都没被触达。 |
| `sprite-frame-descriptors` | 消费者 fn `0x08080670` 同样**没有 `bl` 调用点**，其地址 `0x08080671` 作为数据字出现在 `0x0853EF74` —— 一张 **20 字节记录（两个回调 + 一个 id + 两个零）的对象类型表**里（相邻记录 id = 2/3/4，回调 `0x08080555`/`0x08080661`/`0x08080765`/`0x080808BD`）。需要游戏实例化这种对象类型才会被调用；三轮路线都没做到。 |
| `battle-encounters` | 同上：消费者 fn `0x08087C9C` 只被 thunk `0x0808A69C` 间接调用（thunk 监视点 `0x0808A69E` 三轮都没命中）。 |
| `ninjutsu-names` | 消费者 fn `0x080794F4` 只被 `0x0806F89C` 调用（角色/技能模块）。战斗与剧情路线都没进到那个界面（需要打开「忍术」列表）。 |

**共同的阻塞点**：这 7 个消费者里有 4 个（`fonts`、`tile-assets`、
`sprite-frame-descriptors`、`battle-encounters`）**没有直接的 `bl` 调用点**，
它们是被 ROM 里的**函数指针回调表**调用的。要在运行时触达它们，
必须让游戏自己**实例化对应的回调表条目**（战斗指令菜单 / 场景对象类型 /
地图事件），而不是简单地“多跑几场战斗”。

**没有做的事**：没有为了凑数而把“静态反汇编证明过读者”写成 L2；
这 7 张表按仓库规则**仍停在 L1**。

> **门禁怎么区分“该证明却没证到”和“本来就声明是 L1”**：
> `tools/l2_runtime_capture.py` 的每个结构带一个 `l2` 标志
> （默认 `True` = 本工具**宣称**它到了 L2）。
> 这 7 张表在 `STRUCTURES` 里显式写 `"l2": False` 并附 `l1_reason`，
> 于是 `--self-test` 对它们只**报告**“declared L1 + 为什么没到”，**不**当成失败；
> 而任何**宣称 L2** 的结构一旦对应关系没被观察到，工具立刻**退出非零**。
> `python tools\l2_runtime_capture.py --list` 的 `claim=` 列就是这张声明表。


## B.7 复现命令（第二批）

```powershell
$env:PYTHONIOENCODING='utf-8'

# 全部 17 张表（第一批 5 + 第二批 12）+ 静态检查 + 反向对照
python tools\l2_runtime_capture.py --self-test --json build\l2-runtime.json

# 只跑第二批
python tools\l2_runtime_capture.py --all --battle-groups 0-47 \
    --battle-subs 0,1,2 --battle-presses 16

# 消费者/反汇编/字面量的静态工具
python tools\l2_batch2.py --all --window 10        # 打印每个读者的反汇编窗口
python tools\l2_batch2.py --battle-diag --battle-groups 40 --watch 0x08098822
python tools\l2_literal.py 0x08087DE0 0x08087DEC   # 解析 pc-relative 字面量
python tools\l2_table_dump.py                     # 打印 12 张表的 ROM 内容
python tools\l2_note_report.py --json build\l2-runtime.json \
    --out build\l2-batch2-section.md              # 由 JSON 生成附录 C
```

本轮实测：存档已缓存时整套 `--self-test` 约 **11 分钟**
（其中 144 场战斗的 `battle` 路线约 9 分钟）；
只跑第二批约 10 分钟。

## B.8 对仓库的影响（第二批）

| 文件 | 说明 |
|---|---|
| `tools/l2_runtime_capture.py` | **扩展**。新增 12 个结构、`battle` 路线、按分组共享断点的采集流程、registry `verified=False` 的显式声明机制。 |
| `tools/l2_batch2.py` | 新增。第二批的静态工具：列出每个结构的原生读者并打印反汇编窗口、`--battle-diag` / `--sweep-diag` 诊断。 |
| `tools/l2_literal.py` | 新增。解析 pc-relative 字面量的目标地址与值。 |
| `tools/l2_table_dump.py` / `tools/l2_table_dump2.py` | 新增。打印 12 张表的 ROM 内容（步长 68 / 144 的两种视图）。 |
| `tools/l2_pointer_search.py` | 新增。在 ROM 里搜函数地址作为**数据字**出现的位置（回调表）。 |
| `tools/l2_words.py` / `tools/l2_map_ids.py` | 新增。按 u32 打印 ROM 区域；列出地图描述符。 |
| `tools/l2_note_report.py` | 新增。由 `build/l2-runtime.json` 生成附录 C。 |
| `tools/l2_note_append.py` | 新增。以 LF 追加本笔记的小工具。 |
| `notes/evidence/l2-runtime-evidence-20261021.md` | 本文件。追加附录 B / C。 |

**未改动**：`tools/completion_audit.py`、`tools/table_registry.py`、
`tools/consumer_locate.py`、`tools/mgba_probe/*`、`sequel/content/*`、`docs/*`、
其它笔记。

> **给 owner 的三条建议（本轮没有动那些文件）**：
> 1. `tools/table_registry.py` 里 `legacy_cutscene_scripts`（`0x53DF70`）的
>    `verified` 标志针对的是**旧名字**；地址本身已被原生读者 `0x08072F0C` 和
>    本轮的运行时证据证明。建议把它改名成“关卡数据块表”并置 `verified=True`。
> 2. `tools/completion_audit.py` 若要按结构给出 L2 档位，
>    可以把 `tools/l2_runtime_capture.py --self-test` 的 JSON
>    （`build/l2-runtime.json`）作为可机读的证据来源。
> 3. **`docs/sequel-roadmap.md` 需要补一条路线进度**（本轮**没有**动
>    `docs/**`，因为它不在本轮的写入授权内）：
>    L2 运行时证据的覆盖从 5 张表扩到 **10 张**（第一批 5 + 第二批 5），
>    并且新增了第三条确定性路线 `battle`（用三次内存写强制进入战斗）。
>    第二批 12 张里有 **7 张仍停在 L1**，原因与“下一步该怎么走”见 §B.6。


# 附录 C：L2 第二批的运行时结果（2026-10-21）

ROM：`rom/base.gba`，sha256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

## C.1 判定结果

| 结构 | 基址 | L2 消费者（ARM） | 判定点 | 状态 | 运行时下标 |
|---|---|---|---|---|---|
| `battle-handlers` | `0x0853E698` | — | 无 | ❌ 未达到 | — |
| `fonts` | `0x0853E596` | — | 无 | ❌ 未达到 | — |
| `data-table-a` | `0x085A143C` | — | 无 | ❌ 未达到 | — |
| `data-table-b` | `0x085A2034` | `0x080985D8`（fn `0x080983B8`） | `0x080985E0` | ✅ L2 | 56 |
| `function-pointers` | `0x0853D5F0` | `0x08061DD4`（fn `0x08061D8C`） | `0x08061DDA` | ✅ L2 | 2 |
| `tile-assets` | `0x085A320C` | — | 无 | ❌ 未达到 | — |
| `sprite-frame-descriptors` | `0x0853EE98` | — | 无 | ❌ 未达到 | — |
| `battle-encounters` | `0x0854229C` | — | 无 | ❌ 未达到 | — |
| `ninjutsu-names` | `0x08599634` | — | 无 | ❌ 未达到 | — |
| `reward-table` | `0x0859EAE0` | `0x08089EA2`（fn `0x08089E84`） | `0x08089EAE` | ✅ L2 | 1 |
| `cutscene-scripts` | `0x0853DF70` | `0x08072F0C`（fn `0x08072EDC`） | `0x08072F16` | ✅ L2 | 0 |
| `sprite-action-table` | `0x08596CCC` | `0x0806B76C`（fn `0x0806B720`） | `0x0806B770` | ✅ L2 | 1 |

**5 / 12 达到 L2**。

## C.2 逐结构证据

### `data-table-b`（0x085A2034）

数据指针表 B（90 项 u32 ROM 指针）。

**消费者**：`0x080985D8`（fn `0x080983B8`），**判定点**：`0x080985E0`，命中 `0x080985E0`。

```
pc=0x080985E2  lr=0x08066D67  sp=0x03001158
r0=0x085A2114
r1=0x085A2034
r2=0x000001C1
r3=0x085A40EC
r4=0x00000000
r5=0x00000000
r6=0x0203120C
r7=0x00000001
r8=0x085A40EC
r9=0x00000004
r10=0x000000D4
r11=0x00000000
r12=0x00000039
sp=0x03001158
lr=0x08066D67
pc=0x080985E2
表基址字节(16): 80 15 5a 08 98 15 5a 08 c0 15 5a 08 f8 15 5a 08
表项 @ 0x085A2114 (16): 24 1d 5a 08 34 1d 5a 08 44 1d 5a 08 50 1d 5a 08
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the structure's table base | ✅ | `register=0x085A2034 expected=0x085A2034` |
| the selected address is base + index*stride inside the table | ✅ | `entry=0x085A2114 index=56 stride=0x4 count=90` |
| emulator memory at the selected entry equals the ROM bytes | ✅ | `live=241d5a08 rom=241d5a08` |
| the index byte in WRAM is the index that selected the entry | ✅ | `wram@0x0203120C=38 index=56` |
| the entry is a ROM pointer | ✅ | `pointer=0x085A1D24` |

**反向对照**：✅ corrupting {'r1': ('base', 4)} makes the check fail —— 2 check(s) failed, first: a register holds the structure's table base

### `function-pointers`（0x0853D5F0）

13 槽 u32 钩子表，槽 0 / 12 是 `FFFFFFFF` 哨兵，槽 1..11 是 11 个代码指针（每槽相差 12 字节）。

**消费者**：`0x08061DD4`（fn `0x08061D8C`），**判定点**：`0x08061DDA`，命中 `0x08061DDA`。

```
pc=0x08061DDC  lr=0x08061D89  sp=0x03001208
r0=0x0853D5F8
r1=0x03000B28
r2=0x00000098
r3=0x0853D5F0
r4=0x00000002
r5=0x03000A88
r6=0x0806E959
r7=0x00000000
r8=0x0000000B
r9=0x00000000
r10=0x00000000
r11=0x00000000
r12=0x0000000F
sp=0x03001208
lr=0x08061D89
pc=0x08061DDC
表基址字节(16): ff ff ff ff 8d 1c 06 08 99 1c 06 08 a5 1c 06 08
表项 @ 0x0853D5F8 (16): 99 1c 06 08 a5 1c 06 08 b1 1c 06 08 bd 1c 06 08
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the structure's table base | ✅ | `register=0x0853D5F0 expected=0x0853D5F0` |
| the selected address is base + index*stride inside the table | ✅ | `entry=0x0853D5F8 index=2 stride=0x4 count=13` |
| emulator memory at the selected entry equals the ROM bytes | ✅ | `live=991c0608 rom=991c0608` |
| the slot index is inside the 13-slot table | ✅ | `r4=2` |
| the slot is either the 0xFFFFFFFF sentinel or a ROM code pointer | ✅ | `value=0x08061C99` |

**反向对照**：✅ corrupting {'r3': ('base', 4)} makes the check fail —— 1 check(s) failed, first: a register holds the structure's table base

### `reward-table`（0x0859EAE0）

奖励表（24 字节/条 x 112）。

**消费者**：`0x08089EA2`（fn `0x08089E84`），**判定点**：`0x08089EAE`，命中 `0x08089EAE`。

```
pc=0x08089EB0  lr=0x0808A177  sp=0x03001214
r0=0x00000000
r1=0x00000018
r2=0x0859EAE0
r3=0x0000000F
r4=0x00000020
r5=0x00000000
r6=0x00000000
r7=0x00000001
r8=0x00000000
r9=0x00000000
r10=0x00000000
r11=0x00000000
r12=0x0859F564
sp=0x03001214
lr=0x0808A177
pc=0x08089EB0
表基址字节(16): c8 00 64 00 0a 00 00 01 00 25 01 04 02 19 02 1a
表项 @ 0x0859EAF8 (16): 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the structure's table base | ✅ | `register=0x0859EAE0 expected=0x0859EAE0` |
| the selected address is base + index*stride inside the table | ✅ | `entry=0x0859EAF8 index=1 stride=0x18 count=112` |
| emulator memory at the selected entry equals the ROM bytes | ✅ | `live=000000000000000000000000000000000000000000000000 rom=000000000000000000000000000000000000000000000000` |
| the scaled index register is index*24 | ✅ | `r1=24 index=1` |
| the index is inside the 112-record reward table | ✅ | `index=1` |
| the register holds the record's +7 byte | ✅ | `r0=0x00 rom=0x00` |

**反向对照**：✅ corrupting {'r2': ('base', 4)} makes the check fail —— 1 check(s) failed, first: a register holds the structure's table base

### `cutscene-scripts`（0x0853DF70）

**关卡数据块表**（4 项 x 8 字节）：每项一对指针（LZ77 4bpp 图块 → VRAM `0x06016000`；LZ77 16 色调色板 → 调色板 RAM `0x05000380`），由 BIOS `svc 0x12` 解压。

**消费者**：`0x08072F0C`（fn `0x08072EDC`），**判定点**：`0x08072F16`，命中 `0x08072F16`。

```
pc=0x08072F18  lr=0x0807363F  sp=0x030011F0
r0=0x0812D9E4
r1=0x00000274
r2=0x00000000
r3=0x00001744
r4=0x0853DF70
r5=0x00000000
r6=0x00000000
r7=0x00000000
r8=0x00000000
r9=0x00000000
r10=0x00000000
r11=0x00000000
r12=0x02000004
sp=0x030011F0
lr=0x0807363F
pc=0x08072F18
表基址字节(16): e4 d9 12 08 e4 de 12 08 4c df 12 08 2c e4 12 08
表项 @ 0x0853DF70 (16): e4 d9 12 08 e4 de 12 08 4c df 12 08 2c e4 12 08
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the level data block table's base | ✅ | `r4=0x0853DF70 expected=0x0853DF70` |
| the scaled index register is index*8 | ✅ | `r5=0 index=0` |
| the index is inside the 4-block table | ✅ | `index=0` |
| the register holds the LZ77 tile pointer the block stores at +0 | ✅ | `r0=0x0812D9E4 rom@0x0853DF70=0x0812D9E4` |
| the LZ77 tile pointer is a ROM address | ✅ | `pointer=0x0812D9E4` |
| the block's palette pointer at +4 is a ROM address | ✅ | `palette=0x0812DEE4` |
| emulator memory at the block equals the ROM bytes | ✅ | `live=e4d91208e4de1208` |

**反向对照**：✅ corrupting {'r4': ('base', 4)} makes the check fail —— 1 check(s) failed, first: a register holds the level data block table's base

### `sprite-action-table`（0x08596CCC）

精灵动作表：`id*144 + action*16`，每项 4 个 u32 指针（frames / animations / gfx / palette），id 1..62 有效。

**消费者**：`0x0806B76C`（fn `0x0806B720`），**判定点**：`0x0806B770`，命中 `0x0806B770`。

```
pc=0x0806B772  lr=0x0806B755  sp=0x030011F8
r0=0x08596D5C
r1=0x08596CCC
r2=0x00000000
r3=0x02024294
r4=0x02024294
r5=0x00000001
r6=0x00000000
r7=0x00000007
r8=0x02024364
r9=0x00000000
r10=0x00000000
r11=0x00000000
r12=0x0000000F
sp=0x030011F8
lr=0x0806B755
pc=0x0806B772
表基址字节(16): 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
表项 @ 0x08596D5C (16): 70 2a 14 08 a0 2b 14 08 90 e0 13 08 70 e0 13 08
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the sprite action table's base | ✅ | `r1=0x08596CCC expected=0x08596CCC` |
| the register holds base + id*144 | ✅ | `entry=0x08596D5C index=1 id*144=144` |
| the sprite id byte in WRAM is the id that selected the block | ✅ | `wram@0x02024294=01 index=1` |
| the action record at +0 equals the ROM bytes | ✅ | `record=0x08596D5C` |
| the record's four u32 pointers are all ROM addresses | ✅ | `0x08142A70 0x08142BA0 0x0813E090 0x0813E070` |

**反向对照**：✅ corrupting {'r1': ('base', 4)} makes the check fail —— 2 check(s) failed, first: a register holds the sprite action table's base

## C.3 未达到清单

这 7 张表在 `tools/l2_runtime_capture.py` 里显式声明为 `"l2": False`（**仍停在 L1**），并附上没到的原因：

* `battle-handlers`（0x0853E698）—— the dispatcher fn 0x0807F414 has a single call site (0x0807ABD4, inside the map-event loop); neither the 144 battles nor the story sweep 1..50 reach it
* `fonts`（0x0853E596）—— fn 0x0807EE50 has no direct call site -- it is invoked through the 8-byte callback table at 0x0853ECB0, which the battle and story routes never dispatch
* `data-table-a`（0x085A143C）—— fn 0x0808AFE0 is only called from 0x0808B420 / 0x0808B51A, neither of which runs in the 144 battles
* `tile-assets`（0x085A320C）—— fn 0x0809880C is only called from 0x08098E22 and the other reader's fn 0x08087C9C is only reached through the callback thunk 0x0808A69C; neither fires in the battles
* `sprite-frame-descriptors`（0x0853EE98）—— fn 0x08080670 has no direct call site -- it is the second callback of the 20-byte object-type record at 0x0853EF70 (id 3); the game never instantiates that object type
* `battle-encounters`（0x0854229C）—— fn 0x08087C9C is only reached through the callback thunk 0x0808A69C, which no battle or story scene dispatches
* `ninjutsu-names`（0x08599634）—— fn 0x080794F4 is only called from 0x0806F89C (the character/skill module); neither the battles nor the story sweep open the ninjutsu list


---

# 附录 D：L2 第三批（14 个结构）的运行时证据（2026-10-21）

> 本附录**只追加**，不改写附录 A/B/C 的正文。
> 工具：`tools/l2_runtime_capture.py`（新增第三批 14 个结构、一个新分组
> `batch3` 与第四条确定性路线 `save`）、
> `tools/l2_batch3.py`（本轮新增：列出每个结构的原生读者并打印反汇编窗口）。
> ROM：`rom/base.gba`，sha256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

## D.0 方法

* **基址与读者仍然不许手写**：基址来自 `tools/table_registry.py` 的 `TABLES`
  （加 `ROM_BASE`），读者来自 `tools/consumer_locate.py` 的 `LiteralIndex`
  （全 ROM 字面量索引）。工具在每次运行时都会**重新索引**并断言
  “本结构声明的消费者地址 ∈ 索引给出的读者集合”，否则静态检查直接失败。
* **判定点的选法**（沿用第一批的约定）：mGBA 的断点在目标指令**执行前**命中，
  所以判定点必须下在“基址、下标、字段值都已经在寄存器里”的那条指令上。
  本批新增的判定点全部是**消费者指令之后**的那一条。
* **分组与路线**：第三批引入**第四条确定性路线 `save`**（把剧情状态机的相位
  写成 `0x0018`，见 §D.7）。第三批 14 个结构合成**一个分组**，
  因为它们的判定点互不重叠（一个断点地址在同一组里只能属于一个结构）。
  `map-sprites` 与 `resource-pointers` 原先都想下在 `fn 0x080625A4` 的
  `0x0806266E`（取 u32 的那条指令），但那个函数有 **15 个调用者**，
  第一次命中往往来自别的调用者；因此本轮把判定点改成**各自消费者的
  独占指令**（`0x08080B74` / `0x0807B222`）。

## D.1 逐表：读者 → 判定点候选

`tools\l2_batch3.py --all --window 14` 的输出（读者地址由 `LiteralIndex` 重新计算，
与任务书给的地址**逐条一致**）：

| 结构 key | 基址 | 原生读者（LiteralIndex） | 本轮选用的判定点 | 步长 |
|---|---|---|---|---|
| `character-stats` | `0x08545068` | `0x0806D98C` | `0x0806D98E` | 16 |
| `character-stats-b` | `0x08545068` | `0x0806D98C` | `0x0806D9D8` | 16 |
| `encounter-zones` | `0x0853D910` | `0x08068FB8` `0x08069040` `0x08069220` `0x08069268` `0x0807AA90` `0x0808067C` | `0x0806904C` / `0x0806922A` | 32 |
| `map-sprites` | `0x0853F140` | `0x08080B12` | `0x08080B74` | 8 |
| `units` | `0x0853F298` | `0x08080B2C` | `0x08080B3C` | 2 |
| `resource-pointers` | `0x08596F0C` | `0x0807B220` | `0x0807B222` | 8 |
| `save-state` | `0x0853D848` | `0x0806869A` `0x08068954` `0x08068CC0` `0x08068D98` | `0x080686A6` `0x08068962` `0x08068CCA` `0x08068DA0` | 8 |
| `sprite-animations` | `0x08596CCC` | 18 个（`0x0806A826` … `0x080930A2`） | `0x0806B770` | 144 |
| `items` | `0x08545BE4` | `0x0806D91A` `0x08078EF8` `0x08078F08` `0x0808FC28` `0x0808FF78` `0x08095394` | `0x0806D924` `0x0808FC30` `0x0808FF80` | 16 |
| `skills` | `0x08545BE4` | 同上 | `0x0806D926` `0x0808FC2E` `0x0808FF7E` | 16 |
| `levels` | `0x085459C8` | `0x0806D6E6` `0x0806D786` `0x0806DB14` `0x0806DC4C` `0x0806DDD6` `0x080932CA` | `0x0806DB1A` `0x0806DC52` `0x0806D6EC` `0x0806D792` `0x0806DDE2` `0x080932D8` | 12 |
| `mission-text` | `0x08348DAC` | `0x080731DA` `0x0808675C` `0x080874FE` `0x080884F8` `0x080893E4` `0x08089E90` | `0x08087510` `0x080731E4` `0x08086766` | 1 |
| `battle-config` | `0x085461C4` | 26 个（`0x0806DF28` … `0x0806FE3A`） | `0x0806DF3E` `0x0806E1FE` `0x0806E3DC` | `0x1AAC` / `0x8E4` / `0xB8` |
| `story-background-table` | `0x0859903C` | `0x08088372` `0x08088400` | `0x0808837C` / `0x0808840A` | 16 |

## D.2 与任务书不一致 / 需要更正的三处
1. **`map-sprites` 的步长是 8，不是 4。**
   任务书写“86 项 u32 指针数组”。原生代码 `fn 0x080625A4` 用的是
   `lsls r0, r7, #3`（**下标 × 8**），并连续取 `+0` 与 `+4` 两个 u32；
   ROM 里 `0x0853F140` 的内容也确实是 `{u32, u32}` 成对
   （`0812F5B0 0812F5BC` / `0812F5D8 0812F5E4` / …）。
   ⇒ 真相是 **43 条 8 字节记录 {u32 指针, u32 指针}**，
   “86 项 u32” 只是同一片字节的 **u32 视图**。
   表尾 `0x53F140 + 43*8 = 0x53F298` **正好接** `unit_slot_remap`，
   这是步长 8 的独立佐证。
2. **`resource-pointers` 的基址是 `sprite_action_table` 的一个窗口。**
   `0x08596F0C = 0x08596CCC + 4*144`，即精灵动作表的**第 5 条记录**（0 起算）。
   原生读者 `0x0807B220` 把它装进 `r0`，交给 `fn 0x080625A4`
   —— 与 `map-sprites` **同一条**取表指令。
   ⇒ **静态**结论是这个窗口的基址确实被消费者装进寄存器并按 ×8 取表；
   **运行时**这条消费者本轮**没有触达**（见 §D.5），所以
   `resource-pointers` 仍停在 L1。本轮**不**宣称它是与精灵动作表并列的
   另一张表（裁决要改 `tools/table_registry.py`，不在本轮的写入授权内）。
3. **`battle-config` 的 registry 名字对不上。**
   `tools/table_registry.py` 的 `BANK_TO_REGISTRY` 把 `"battle-config"`
   指向 `skill_table`（`0x545458`），但任务书给的基址 `0x5461C4`
   是 `battle_actors`（编成矩阵）。本轮按**任务书与原生代码**取
   `battle_actors`；`BANK_TO_REGISTRY` 那一条需要 owner 修正
   （本轮没有动 `tools/table_registry.py`）。

## D.3 判定结果

| 结构 | 基址 | L2 消费者（ARM） | 判定点 | 状态 | 运行时下标 |
|---|---|---|---|---|---|
| `character-stats` | `0x08545068` | `0x0806D98C`（fn `0x0806D964`） | `0x0806D98E` | ✅ L2 | 1 |
| `character-stats-b` | `0x08545068` | `0x0806D98C`（fn `0x0806D964`） | `0x0806D9D8` | ✅ L2 | 1 |
| `encounter-zones` | `0x0853D910` | `0x08069040`（fn `0x08068FF0`） | `0x0806904C` | ✅ L2 | 0 |
| `map-sprites` | `0x0853F140` | — | 无 | ❌ 未达到 | — |
| `units` | `0x0853F298` | — | 无 | ❌ 未达到 | — |
| `resource-pointers` | `0x08596F0C` | — | 无 | ❌ 未达到 | — |
| `save-state` | `0x0853D848` | `0x0806869A`（fn `0x08068684`） | `0x080686A6` | ✅ L2 | 0 |
| `sprite-animations` | `0x08596CCC` | `0x0806B76C`（fn `0x0806B720`） | `0x0806B770` | ✅ L2 | 1 |
| `items` | `0x08545BE4` | — | 无 | ❌ 未达到 | — |
| `skills` | `0x08545BE4` | — | 无 | ❌ 未达到 | — |
| `levels` | `0x085459C8` | `0x0806DB14`（fn `0x0806D964`） | `0x0806DB1A` | ✅ L2 | 2 |
| `mission-text` | `0x08348DAC` | — | 无 | ❌ 未达到 | — |
| `battle-config` | `0x085461C4` | `0x0806E1F0`（fn `0x0806E1B4`） | `0x0806E1FE` | ✅ L2 | 0 |
| `story-background-table` | `0x0859903C` | `0x08088372`（fn `0x08088348`） | `0x0808837C` | ✅ L2 | 13 |

**8 / 14 达到 L2**。

## D.4 逐结构证据

### `character-stats`（0x08545068）

逐角色属性表（16 字节/条 x 63）。

**消费者**：`0x0806D98C`（fn `0x0806D964`），**判定点**：`0x0806D98E`，命中 `0x0806D98E`。

```
pc=0x0806D990  lr=0x0806D5CB  sp=0x03001228
r0=0x08545068
r1=0x00000010
r2=0x00000001
r3=0x00000001
r4=0x08542580
r5=0x08542578
r6=0x02022EF0
r7=0x00000000
r8=0x08542578
r9=0x085424D0
r10=0x00000000
r11=0x00000000
r12=0x02022FA0
sp=0x03001228
lr=0x0806D5CB
pc=0x0806D990
表基址字节(16): 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
表项 @ 0x08545078 (16): aa 05 04 00 64 00 64 00 64 00 00 00 00 00 00 00
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the per-character stat table's base | ✅ | `r0=0x08545068 expected=0x08545068` |
| the scaled index register is the character id times 16 | ✅ | `r1=16 id=1 id*16=16` |
| the selected address is base + id*16 inside the table | ✅ | `entry=0x08545078 index=1 count=63` |
| emulator memory at the selected record equals the ROM bytes | ✅ | `entry=0x08545078 rom=aa 05 04 00 64 00 64 00 64 00 00 00 00 00 00 00` |
| the selected record is not empty | ✅ | `record=aa 05 04 00 64 00 64 00 64 00 00 00 00 00 00 00` |

**反向对照**：✅ corrupting {'r0': ('base', 4)} makes the check fail —— 1 check(s) failed, first: a register holds the per-character stat table's base

### `character-stats-b`（0x08545068）

**弃用别名**：与 `character-stats` 是同一张表。

**消费者**：`0x0806D98C`（fn `0x0806D964`），**判定点**：`0x0806D9D8`，命中 `0x0806D9D8`。

```
pc=0x0806D9DA  lr=0x0806D9CD  sp=0x03001228
r0=0x00000064
r1=0x08545078
r2=0x085424D0
r3=0x00000001
r4=0x0000000E
r5=0x00000000
r6=0x02022EF0
r7=0x00000000
r8=0x08545078
r9=0x085424D0
r10=0x00000000
r11=0x00000000
r12=0x00000064
sp=0x03001228
lr=0x0806D9CD
pc=0x0806D9DA
表基址字节(16): 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
表项 @ 0x08545078 (16): aa 05 04 00 64 00 64 00 64 00 00 00 00 00 00 00
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| the register holds the record base + id*16 | ✅ | `r1=0x08545078 index=1 count=63` |
| the register holds the u16 the record stores at +6 | ✅ | `r0=0x0064 rom=0x0064` |
| emulator memory at the selected record equals the ROM bytes | ✅ | `entry=0x08545078` |

**反向对照**：✅ corrupting {'r1': ('value', 4)} makes the check fail —— 1 check(s) failed, first: the register holds the record base + id*16

### `encounter-zones`（0x0853D910）

**弃用别名**：与 `maps` 是同一张 32 字节地图描述符表。

**消费者**：`0x08069040`（fn `0x08068FF0`），**判定点**：`0x0806904C`，命中 `0x0806904C`。

```
pc=0x0806904E  lr=0x08073319  sp=0x030011C8
r0=0x080B9F80
r1=0x00000105
r2=0x00000000
r3=0x0400000A
r4=0x02022E2D
r5=0x0853D910
r6=0x00000000
r7=0x0300004C
r8=0x00000000
r9=0x00000000
r10=0x00000000
r11=0x00000000
r12=0x00000064
sp=0x030011C8
lr=0x08073319
pc=0x0806904E
表基址字节(16): 5c 00 40 00 80 9f 0b 08 08 d6 0b 08 0c d7 0b 08
表项 @ 0x0853D910 (16): 5c 00 40 00 80 9f 0b 08 08 d6 0b 08 0c d7 0b 08
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the map descriptor table's base | ✅ | `r5=0x0853D910 expected=0x0853D910` |
| the scaled index register is the map id times 32 | ✅ | `r6=0 id=0 id*32=0` |
| the selected address is base + id*32 inside the table | ✅ | `entry=0x0853D910 index=0 stride=0x20 count=50` |
| the register holds the u32 the descriptor stores at +4 | ✅ | `r0=0x080B9F80 rom=0x080B9F80` |
| the descriptor's +4 graphic pointer is a ROM address | ✅ | `terrain=0x080B9F80` |
| emulator memory at the selected descriptor equals the ROM bytes | ✅ | `entry=0x0853D910` |

**反向对照**：✅ corrupting {'r5': ('base', 4)} makes the check fail —— 1 check(s) failed, first: a register holds the map descriptor table's base

### `save-state`（0x0853D848）

WRAM 分配表（8 字节/条：u32 WRAM 地址 + u32 大小）。

**消费者**：`0x0806869A`（fn `0x08068684`），**判定点**：`0x080686A6`，命中 `0x080686A6`。

```
pc=0x080686A8  lr=0x0806893F  sp=0x030011F0
r0=0x02022E30
r1=0x00000001
r2=0x00000000
r3=0x00000000
r4=0x0000127C
r5=0x00000002
r6=0x0853D848
r7=0x0E000000
r8=0x00000002
r9=0x00000001
r10=0x00000001
r11=0x00000000
r12=0x00000200
sp=0x030011F0
lr=0x0806893F
pc=0x080686A8
表基址字节(16): 30 2e 02 02 7c 12 00 00 30 2e 02 02 7c 12 00 00
表项 @ 0x0853D848 (16): 30 2e 02 02 7c 12 00 00 30 2e 02 02 7c 12 00 00
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the WRAM allocation table's base plus an exact 8-byte record offset | ✅ | `r6=0x0853D848 base=0x0853D848 index=0 stride=8 count=11` |
| the register holds the u32 the record stores at +0 (the WRAM address) | ✅ | `r0=0x02022E30 rom=0x02022E30` |
| the register holds the u32 the record stores at +4 (the size) | ✅ | `r4=0x0000127C rom=0x0000127C` |
| the record's WRAM address really is a WRAM address | ✅ | `wram=0x02022E30` |
| emulator memory at the selected record equals the ROM bytes | ✅ | `entry=0x0853D848` |

**反向对照**：✅ corrupting {'r0': ('value', 4)} makes the check fail —— 1 check(s) failed, first: the register holds the u32 the record stores at +0 (the WRAM address)

### `sprite-animations`（0x08596CCC）

**弃用别名**：与 `sprite-action-table` 是同一张表。

**消费者**：`0x0806B76C`（fn `0x0806B720`），**判定点**：`0x0806B770`，命中 `0x0806B770`。

```
pc=0x0806B772  lr=0x0806B755  sp=0x030011F8
r0=0x08596D5C
r1=0x08596CCC
r2=0x00000000
r3=0x02024294
r4=0x02024294
r5=0x00000001
r6=0x00000000
r7=0x00000007
r8=0x02024364
r9=0x00000000
r10=0x00000000
r11=0x00000000
r12=0x0000000F
sp=0x030011F8
lr=0x0806B755
pc=0x0806B772
表基址字节(16): 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
表项 @ 0x08596D5C (16): 70 2a 14 08 a0 2b 14 08 90 e0 13 08 70 e0 13 08
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the sprite action table's base | ✅ | `r1=0x08596CCC expected=0x08596CCC` |
| the register holds base + id*144 | ✅ | `entry=0x08596D5C index=1 id*144=144` |
| the sprite id byte in WRAM is the id that selected the block | ✅ | `wram@0x02024294=01 index=1` |
| the action record at +0 equals the ROM bytes | ✅ | `record=0x08596D5C` |
| the record's four u32 pointers are all ROM addresses | ✅ | `0x08142A70 0x08142BA0 0x0813E090 0x0813E070` |

**反向对照**：✅ corrupting {'r1': ('base', 4)} makes the check fail —— 2 check(s) failed, first: a register holds the sprite action table's base

### `levels`（0x085459C8）

角色特性表（12 字节/条 x 45）。

**消费者**：`0x0806DB14`（fn `0x0806D964`），**判定点**：`0x0806DB1A`，命中 `0x0806DB1A`。

```
pc=0x0806DB1C  lr=0x0806DA45  sp=0x030011E0
r0=0x00000001
r1=0x085459C8
r2=0x00000000
r3=0x085459E0
r4=0x00000013
r5=0x00000000
r6=0x02002880
r7=0x00000000
r8=0x00000000
r9=0x08543A9C
r10=0x00000000
r11=0x00000000
r12=0x000034D8
sp=0x030011E0
lr=0x0806DA45
pc=0x0806DB1C
表基址字节(16): 00 00 00 00 00 00 00 00 00 00 00 00 01 00 1e 00
表项 @ 0x085459E0 (16): 03 00 01 00 00 00 01 00 00 00 00 00 04 00 03 00
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the character perk table's base | ✅ | `r1=0x085459C8 expected=0x085459C8` |
| the selected address is base + index*12 inside the table | ✅ | `r3=0x085459E0 index=2 stride=0xC count=45` |
| the register holds the u16 the record stores at +6 | ✅ | `r0=0x0001 rom=0x0001` |
| emulator memory at the selected record equals the ROM bytes | ✅ | `entry=0x085459E0` |

**反向对照**：✅ corrupting {'r1': ('base', 4)} makes the check fail —— 1 check(s) failed, first: a register holds the character perk table's base

### `battle-config`（0x085461C4）

战斗编成矩阵：`group*0x1AAC + sub*0x8E4 + slot*0xB8 + 4`。

**消费者**：`0x0806E1F0`（fn `0x0806E1B4`），**判定点**：`0x0806E1FE`，命中 `0x0806E1FE`。

```
pc=0x0806E200  lr=0x0806E1CB  sp=0x03001220
r0=0x00000004
r1=0x085461C4
r2=0x02026804
r3=0x085461C4
r4=0x020311D4
r5=0x085461C8
r6=0x00000000
r7=0x00000000
r8=0x02022E30
r9=0x02024045
r10=0x00000000
r11=0x00000000
r12=0x00000064
sp=0x03001220
lr=0x0806E1CB
pc=0x0806E200
表基址字节(16): 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
表项 @ 0x085461C8 (16): 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the formation matrix's base | ✅ | `base register=0x085461C4 expected=0x085461C4` |
| the register holds base + group*0x1AAC + sub*0x8E4 | ✅ | `block=0x085461C4 expected=0x085461C4 group=0 sub=0` |
| the selected address is base + group*0x1AAC + sub*0x8E4 + slot*0xB8 + 4 | ✅ | `entry=0x085461C8 expected=0x085461C8 group=0 sub=0 slot=0` |
| the selected address is inside the formation matrix | ✅ | `entry=0x085461C8` |
| emulator memory at the selected record equals the ROM bytes | ✅ | `entry=0x085461C8` |

**反向对照**：✅ corrupting {'r1': ('base', 4)} makes the check fail —— 1 check(s) failed, first: a register holds the formation matrix's base

### `story-background-table`（0x0859903C）

剧情底图表（16 字节/条 x 14）。

**消费者**：`0x08088372`（fn `0x08088348`），**判定点**：`0x0808837C`，命中 `0x0808837C`。

```
pc=0x0808837E  lr=0x0808F527  sp=0x0300120C
r0=0x0833CA94
r1=0x00000000
r2=0x00000001
r3=0x00000000
r4=0x0859903C
r5=0x000000D0
r6=0x00000000
r7=0x00000000
r8=0x0859910C
r9=0x00000000
r10=0x00000001
r11=0x00000000
r12=0x0000000F
sp=0x0300120C
lr=0x0808F527
pc=0x0808837E
表基址字节(16): 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
表项 @ 0x0859910C (16): 94 ca 33 08 e4 02 34 08 3c 04 34 08 01 00 00 00
```

**寄存器 ↔ 字段对应**

| 检查 | 结果 | 明细 |
|---|---|---|
| a register holds the background table's base | ✅ | `r4=0x0859903C expected=0x0859903C` |
| the selected address is base + id*16 inside the table | ✅ | `r8=0x0859910C index=13 r5=208 id*16=208` |
| the register holds the u32 the record stores at +0 | ✅ | `r0=0x0833CA94 rom=0x0833CA94` |
| that u32 is a ROM pointer (the LZ77 background tiles) | ✅ | `pointer=0x0833CA94` |
| emulator memory at the selected record equals the ROM bytes | ✅ | `entry=0x0859910C` |

**反向对照**：✅ corrupting {'r4': ('base', 4)} makes the check fail —— 1 check(s) failed, first: a register holds the background table's base

## D.5 未达到清单

下列结构在 `tools/l2_runtime_capture.py` 里显式声明为 `"l2": False`（**仍停在 L1**），并附上没到的原因：

* `map-sprites`（0x0853F140）—— the only native reader 0x08080B12 is in fn 0x08080B08, which is only reached from the 12 dispatch branches of fn 0x08080BA0 (0x08080C42 ... 0x08080D5C).  That dispatch belongs to the object-type callback table at 0x0853EF70, and the game never instantiates that object type -- the same blocker the batch-2 note recorded for `sprite-frame-descriptors`.
* `units`（0x0853F298）—— reader 0x08080B2C is in the same fn 0x08080B08 as the `map-sprites` reader, so it has exactly the same blocker: fn 0x08080B08 is only reached from the object type dispatch at 0x08080BA0, which the game never instantiates.
* `resource-pointers`（0x08596F0C）—— reader 0x0807B220 is in fn 0x0807AE04, which is called from eight functions (0x0807B444, 0x0807B6E0, 0x0807B8B8, 0x0807C638, 0x0807DCB8, 0x0807ED20, 0x0807EE50, 0x0807F414).  Two of them -- fn 0x0807EE50 (the font width table consumer) and fn 0x0807F414 (the battle event dispatcher) -- were already proven unreachable in batch 2, and none of the other six runs in the battle, sweep or save routes either.
* `items`（0x08545BE4）—— fn 0x0806D910 (reader 0x0806D91A) is only called from 12 story / map-event functions (0x0806FDA4, 0x080708BC, 0x08070DF8, 0x080722A8, 0x080754A8, 0x08075B58, 0x08082354, 0x080833A8, 0x0808400C, 0x080851F8, 0x08092694) -- none of which the battle, sweep or save routes open.  The other two readers (0x0808FC28, 0x0808FF78) sit behind the branches at 0x0806E892 / 0x0806E8E4 of fn 0x0806E1B4, which only run for a battle unit whose type byte matches; no battle of the 48x3 matrix matched.
* `skills`（0x08545BE4）—— the same table as `items`, and the same consumers: fn 0x0806D910 (reader 0x0806D91A) and the two readers behind the fn 0x0806E1B4 branches (0x0808FC28, 0x0808FF78) are not reached by the battle, sweep or save routes.
* `mission-text`（0x08348DAC）—— all three readers sit in conditional branches.  Reader 0x080874FE (fn 0x08087334) needs the WRAM byte at r8 to be non-zero (0x08087412); the `save` route does reach fn 0x08087334 (through fn 0x08087940 -> 0x0808795C) but always takes the other branch.  Reader 0x080731DA (fn 0x080731D0) needs fn 0x08086EEC, which fn 0x08089E84 only calls when r4 == 0x30 (0x0808A142).  Reader 0x0808675C (fn 0x08086740) needs fn 0x080868AC, called from 0x08086BD0 / 0x080872BA only.

## D.6 可证伪测试

每条命令都会在“结论不成立”时**退出非零**。

| # | 结论 | 怎样算被推翻 | 命令 |
|---|---|---|---|
| F9 | 第三批 14 个结构的原生读者地址正确（不是手写） | `LiteralIndex` 的读者集合里不含所用的消费者地址 | `python tools\l2_batch3.py --all --window 14` |
| F10 | 宣称 L2 的 18 个结构在运行时对应成立 | 工具退出码非零 | `python tools\l2_runtime_capture.py --self-test --json build\l2-runtime.json` |
| F11 | 门禁真的会咬人（不是空过） | 改坏关键寄存器后检查仍然通过 | 同上输出里的 `negative control` 段 |
| F12 | `save-state` 的记录是 `{u32 WRAM 地址, u32 大小}` | 两个寄存器里的 u32 与 ROM 对不上，或那个地址不是 WRAM | `python tools\l2_runtime_capture.py save-state` |
| F13 | `battle-config` 的寻址是 `group*0x1AAC + sub*0x8E4 + slot*0xB8 + 4` | 选中的地址与这四项算出来的不等 | `python tools\l2_runtime_capture.py battle-config` |
| F14 | `levels` 的记录是 12 字节/条、消费者读的是 `+6` 的 u16 | 寄存器里的 u16 与 ROM 的 `+6` 不等 | `python tools\l2_runtime_capture.py levels` |
| F15 | `map-sprites` 的步长是 **8**（不是 4） | 表尾不等于 `0x53F298`（= `unit_slot_remap` 的起点） | `python tools\l2_batch3.py --dump object_descriptor_table --count 44 --stride 8` |
| F16 | `resource-pointers` 的 `0x08596F0C` 是**精灵动作表的窗口**（`+4*144`） | 消费者装进寄存器的不是 `0x08596F0C` | `python tools\l2_runtime_capture.py resource-pointers`（**当前声明 L1，退出码 1 是预期结果**） |
| F17 | `units` 的语义是“表里的 u16 + WRAM `0x0202CA24` 的 u16，掩到 16 位” | `r0 != (remap + runtime) & 0xFFFF`，或 `r2` 不等于 `0x0202CA24` 处的 u16 | 同上（**当前声明 L1**） |

## D.7 新增的第四条路线：`save`（相位 `0x0018`）

第一批的 `title`、第二批的 `battle` 之外，本轮又找到一条确定性路线。

剧情状态机的循环头 `0x0808F752` 按 `state[0x12]`（u16）分派：

```asm
0808F752  ldrh r1, [r4, #0x12]     ; r1 = state[0x12]
...
0808F784  cmp  r1, #0x18
0808F786  beq  #0x808f872          ; <- 相位 0x18 的分支
...
0808F872  bl   #0x8087940          ; fn 0x08087940
```

`fn 0x08087940` 是 **WRAM 分配表**（`fn 0x08068948` → 读者 `0x08068954`）
和 **任务索引表**（`fn 0x08087334` → 读者 `0x080874FE`）的**唯一**调用者，
所以把 `state[0x12]` 写成 `0x0018` 就能一次触达它们。

这条路线与 `battle` 路线共用同一个起始存档
（`STATE_ALIASES = {"save": "battle"}`），写法还是那三次内存写里的第一步：

```powershell
poke16 0x020311E6 0x0018      # 相位 = 0x18（剧情事件分支）
```

## D.8 复现命令（第三批）

```powershell
$env:PYTHONIOENCODING='utf-8'

# 全部 31 个结构（第一批 5 + 第二批 12 + 第三批 14）+ 静态检查 + 反向对照
python tools\l2_runtime_capture.py --self-test --json build\l2-runtime.json

# 只跑第三批
python tools\l2_runtime_capture.py --structures character-stats,character-stats-b,\
levels,encounter-zones,battle-config,items,skills,mission-text,save-state,\
story-background-table,sprite-animations,map-sprites,units,resource-pointers

# 消费者/反汇编/字面量的静态工具
python tools\l2_batch3.py --list
python tools\l2_batch3.py --all --window 14 --json build\l2-batch3-readers.json
python tools\l2_batch3.py --dump unit_slot_remap --count 43 --stride 2 --width 2
python tools\l2_batch3.py --dump object_descriptor_table --count 44 --stride 8
python tools\l2_batch3.py --calls 0x0806D910      # 谁调用了这个函数
python tools\l2_batch3.py --calls 0x08080B08

# 由 JSON 生成附录 D 的运行时小节（数字不可能与跑出它的那次运行脱节）
python tools\l2_batch3.py --report build\l2-appendix-d-runtime.md \
    --report-json build\l2-runtime.json
```

本轮实测（存档已缓存）：整套 `--self-test` 约 **5 分钟**
（其中 `battle` 路线 48 组 × 1 子配置约 2 分钟，
`title` + `sweep`（55 场景）+ `save` 合计约 3 分钟）。

## D.9 对仓库的影响（第三批）

| 文件 | 说明 |
|---|---|
| `tools/l2_runtime_capture.py` | **扩展**。新增第三批 14 个结构与它们的 derive 函数、新增第四条路线 `save`（相位 `0x0018`）、新增 `--structures` 子集选项、新增“粘性断点 + 调用者过滤”（`sticky` / `expect_lr`）机制、修正“路线提前结束”的判定（只有**通过**的对应关系才算数）。 |
| `tools/l2_batch3.py` | 新增。第三批的静态工具：列出每个结构的原生读者并打印反汇编窗口、打印 ROM 里的表内容、`--calls` 列出某个函数的所有 Thumb `bl` 调用点、`--report` 由 `build/l2-runtime.json` 生成附录 D 的运行时小节。 |
| `notes/evidence/l2-runtime-evidence-20261021.md` | 本文件。追加附录 D。 |

**未改动**：`tools/completion_audit.py`、`tools/table_registry.py`、
`tools/consumer_locate.py`、`tools/mgba_probe/*`、`sequel/content/*`、`docs/*`、
其它笔记。

> **给 owner 的四条建议（本轮没有动那些文件）**：
> 1. `tools/table_registry.py` 的 `BANK_TO_REGISTRY` 把 `"battle-config"`
>    指向 `skill_table`（`0x545458`），但原生代码与本轮运行时证据都指向
>    `battle_actors`（`0x5461C4`，编成矩阵）。这一条应当改成
>    `"battle-config": "battle_actors"`。
> 2. `legacy_resource_pointers`（`0x596F0C`）经本轮证明是
>    `sprite_action_table`（`0x596CCC`）**内部第 5 条记录**的窗口
>    （`+4*144`），不是一个并列的表。它的 `verified` 标志与
>    `CONFLICTS` 表里应当补一条“窗口”裁决。
> 3. `object_descriptor_table`（`0x53F140`）的步长是 **8**（43 条 × 8 字节），
>    不是 4；`unit_slot_remap`（`0x53F298`）正好接在它后面
>    （`0x53F140 + 43*8 = 0x53F298`）。registry 的注释里已经写了这一点，
>    但 `object_descriptor_table` 的 `verified` 标志仍是 `False`，
>    而本轮已经用原生读者 `0x08080B12` 证明了它。
> 4. **`docs/sequel-roadmap.md` 需要补一条路线进度**（本轮**没有**动
>    `docs/**`，因为它不在本轮的写入授权内）：
>    L2 运行时证据的覆盖从 10 个结构扩到 **18 个结构**，
>    并新增第四条确定性路线 `save`（把剧情状态机的相位写成 `0x0018`
>    就能触达 WRAM 分配表与任务索引表的消费者）。
>    第三批 14 个里有 **6 个仍停在 L1**，原因与“下一步该怎么走”见 §D.5。
