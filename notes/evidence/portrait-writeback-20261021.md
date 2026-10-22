# 头像写回能力证据 — 2026-10-21

**一句话**：头像资产的布局、解压格式、**压缩预算**都已经从本 ROM 的原生消费者
里挖出来并证明；**写回是安全的**，并且带一条可执行的往返自检
（`--portrait-self-test`：**310/310** 个头像全部通过）。
工具在 `tools/export_content_pack.py`（本轮我拥有的文件）里。

- 头像表：`0x085A4DEC`，40 字节/行，`id*40 + expr*8` → `(图像指针, 调色板指针)`
- 原生消费者：`0x08096138`（地址计算）/ `0x08096158`（表基址装载），外层函数 `0x08096168`
- 图像：**GBA BIOS LZ77**（`svc #0x11` = Lz77UnCompWram）→ **恰好 6400 字节**
- 调色板：**128 字节原始数据** = 64 条 BGR555
- 压缩预算：**2,320 .. 4,008 字节/头像**（中位数 3,156）

---

## 0. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'

# (1) 往返自检（导出 → 写回 → 再导出，逐字节比对 + 未声明字节不得变动）
python tools\export_content_pack.py --portrait-self-test

# (2) 导出全部头像素材（图形 + 调色板）
python tools\export_content_pack.py --portrait-out build\portrait-assets

# (3) 写回一个头像（写的是 ROM 的**副本**，rom/base.gba 永不被改）
python tools\export_content_pack.py `
    --portrait-write 1 --portrait-expression 0 `
    --portrait-graphics build\portrait-assets\portrait_01_expr0.gfx.bin `
    --portrait-palette build\portrait-assets\portrait_01_expr0.pal.bin `
    --portrait-rom-out   build\portrait-patched.gba

# (4) 端到端演示脚本（改一个像素 + 一个调色板项，再导出比对）
python build\portrait_writeback_demo.py
```

> `build/` 下的脚本是本次调查的可复现探针，不进版本库；
> 结论已写进本文件。

**当前实测输出**

```
$ python tools\export_content_pack.py --portrait-self-test
portrait self-test: 310 portraits round-tripped
PORTRAIT SELF-TEST: PASS

$ python build\portrait_writeback_demo.py
graphics survive the round trip : True
palette survives the round trip  : True
bytes that differ in the ROM copy: 2932
first byte outside the fields    : none
rom/base.gba untouched           : True
compressed length native=3277 new=3278 budget=3308
```

---

## 1. 布局（从原生消费者倒推）

### 1.1 地址计算：`0x08096138`

```
08096138  push {lr}
0809613A  lsls r0, r0, #0x18      ; r2 = id   (u8)
0809613C  lsrs r2, r0, #0x18
0809613E  lsls r1, r1, #0x18      ; r1 = expr (u8)
08096140  lsrs r1, r1, #0x18
08096142  cmp  r1, #5             ; expr == 5 ?
08096144  bne  0x8096150
08096146  ldr  r0, [pc, #4]       ; 0x085A4DE4  (字面量池)
08096148  b    0x809615e
08096150  lsls r0, r2, #2         ; id * 4
08096152  adds r0, r0, r2         ; id * 5
08096154  lsls r0, r0, #3         ; id * 40          <<<
08096156  lsls r1, r1, #3         ; expr * 8         <<<
08096158  ldr  r2, [pc, #8]       ; 0x085A4DEC       <<< 表基址
0809615A  adds r1, r1, r2
0809615C  adds r0, r0, r1         ; &entry[id*40 + expr*8]
0809615E  pop  {r1}
08096160  bx   r1
```

**结论**：头像条目地址 = `0x085A4DEC + id*40 + expr*8`，
每条 8 字节 = `(u32 图像指针, u32 调色板指针)`。

`expr == 5` 走特例，返回字面量 `0x085A4DE4`（= 表基址 + 8）。
**本 ROM 里没有任何一行用 expr 5**（见 §1.3），所以这条分支没有实际作用。

### 1.2 图像与调色板的取用：`0x08096168`

```
080961BE  bl   0x8096138          ; r0 = &entry[id*40 + expr*8]
080961C4  lsls r0, r7, #5
080961C6  ldr  r1, [pc, #0x60]    ; 0x06010000  (VRAM 图块区)
080961C8  adds r5, r0, r1         ; VRAM 目标
080961CA  mov  r1, r8
080961CC  ldr  r0, [r1]           ; r0 = 图像指针
080961CE  ldr  r4, [pc, #0x5c]    ; 0x02002880  (WRAM 暂存)
080961D0  adds r1, r4, #0
080961D2  bl   0x809c0ec          ; <<< Lz77UnCompWram(图像, 0x02002880)
...
080961FA  ldr  r0, [pc, #0x30]    ; 0x02002880
080961FC  movs r2, #0xc8
080961FE  lsls r2, r2, #3         ; 1600 字 = 6400 字节
08096200  adds r1, r5, #0         ; VRAM
08096202  bl   0x809c0dc          ; <<< CpuFastSet(VRAM, WRAM, 1600 字)
08096206  ldr  r0, [pc, #0x2c]    ; 0x05000200  (BG 调色板 RAM)
08096208  adds r5, r6, r0
0809620A  mov  r1, r8
0809620C  ldr  r0, [r1, #4]       ; r0 = 调色板指针
0809620E  adds r1, r5, #0
08096210  movs r2, #0x40          ; 64 字 = 256 字节
08096212  bl   0x809c0e0          ; <<< CpuSet(调色板, BG 调色板槽, 64)
```

BIOS 包装（`0x0809C0DC` 起）：

| 地址 | 指令 | 含义 |
|---|---|---|
| `0x0809C0DC` | `svc #0x0C` | **CpuFastSet** |
| `0x0809C0E0` | `svc #0x0B` | **CpuSet** |
| `0x0809C0E8` | `svc #0x12` | Lz77UnCompVram |
| `0x0809C0EC` | `svc #0x11` | **Lz77UnCompWram** ← 头像解压 |

**结论**

- 图像是 **GBA BIOS LZ77（类型 0x10）** 流：
  4 字节头（`0x10` + 24 位解压长度）+ 压缩载荷。
- 解压后**恰好 6400 字节**（310 个头像全部如此）。
  6400 = 100 张 8bpp 图块 × 64 字节 = 80×80 像素 @ 8bpp。
  > **更正**：`tools/portrait_assets.py` 里写的
  > 「80*80/2 = 6400 bytes of 4bpp indices」**算错了**（80×80/2 = 3200）。
  > 6400 对应的是 **8bpp**，不是 4bpp。该文件不归我修改，需求记在 §5。
- 调色板是**原始数据**：ROM 里每条调色板占 **128 字节 = 64 条 BGR555**。
  （引擎的 `CpuSet` 计数是 64 字 = 256 字节，会多读 128 字节到下一个资源，
  但只用前 64 条，无副作用。）
- 解压后引擎还会**原地改写**缓冲：
  ```
  080961DE  ldrb r0, [r4]
  080961E0  cmp  r0, #0
  080961E2  beq  0x80961e8
  080961E4  adds r0, r0, r2      ; 非 0 字节 += (参数 << 4)
  080961E6  strb r0, [r4]
  ```
  循环上界 `cmp r0, #0x18FF`（`0x080961F6`）→ 只处理前 **6144** 字节，
  比 6400 少 256 字节。**这条改写的确切用途（换色/描边）未证实**，
  只记录事实。
- 存储的字节值范围是 **0..63**（310 个头像全部如此），
  与 64 条调色板刚好对上 —— 这是「8bpp 索引 + 64 色调色板」的自洽证据。

### 1.3 表里到底有多少有效头像

| 范围 | 情况 |
|---|---|
| 行 0 | 全 0（空槽） |
| 行 1..62 | 有效，5 个表情全有数据（**310 条**） |
| 行 63 | **不是头像表的一部分** —— 它**就是紧跟着的说话人名表**（见下面的订正） |

**2026-10-22 订正**：本节原写「行 63 的指针是垃圾（`0x9A9A5992` / `0xC8949892` / …）」。
实测：`0x085A4DEC + 63 × 40 = 0x085A57C4` —— **正好是说话人名表的基址**。
那里的字节 `92 59 9a 9a 00 00 …` 是名字表第 0 条「没有」（字形码 0x9259、0x9A9A）与
第 1 条「鸣人」；按 u32 指针读出来自然是「垃圾」（`92 59 9a 9a` → `0x9A9A5992`，
正是本节列的第一个「垃圾值」）。
⇒ **头像表只有 id 0..62 这 63 行**（id 0 空槽、id 1..62 有效 = 310 条表情），
「第 63 行无效」的说法**作废** —— 它不是无效，是**把两张表读串了**。
详见 `notes/evidence/portrait-render-chain-20261022.md` §2.1。
`tools/portrait_assets.py` 报「63 个 id 有数据」是因为它只检查
`gfx`/`palette` 是否非零，没有检查指针是否落在 ROM 内 —— 这也是需要修正的点（§5）。

---

## 2. 压缩预算（本节是写回能不能做的关键）

### 2.1 格式极限

| 限制 | 值 | 出处 |
|---|---|---|
| LZ77 类型字节 | `0x10` | `tools/lib/lz77.py` 解码器 |
| 解压长度 | 24 位，**固定 6400** | 每个头像的头部 |
| 匹配长度 | 3..18（4 位存 len-3） | `tools/lib/lz77.py` |
| 匹配距离 | 1..4096（12 位存 dist-1） | 同上 |
| 标志位顺序 | **从高位到低位**（bit7 先用） | 同上 |

### 2.2 每个头像有多少字节可用

图像流在 ROM 里是**背靠背**存放的：下一个资源的地址就是这张头像的**硬上限**。
实测（`build/portrait_budget.py`）：

| 量 | 最小 | 中位 | 最大 |
|---|---|---|---|
| ROM 给这张头像的预算（到下一个资源） | 2,320 | 3,156 | 4,008 |
| 原生压缩流长度 | 2,320 | — | 4,008 |
| 流末尾到下一个资源的余量 | 0 | — | 3 字节 |
| 本工具重新压缩后的长度 | 2,309 | 3,130 | 3,986 |
| **重新压缩后的余量** | **+11** | **+29** | **+51** |

**结论**

1. **310 个头像全部装得下**：本工具的压缩器对**每一个**原生头像都产出
   **严格更短**的流（最短的那张也还剩 11 字节余量）。
2. 写回时**新流必须 ≤ 原生流长度**，否则会覆盖下一个资源。
   工具的 `import_portrait()` 会检查这个上限并**直接报错**，不会写出越界的 ROM。
3. 仓库里现成的 `tools/lib/lz77.py` 只提供**纯字面量**编码器：
   6400 字节的图 → 6400 + 800 = **7200 字节**，比任何一张头像的预算都大，
   **根本不能用来写回**。本轮因此在 `tools/export_content_pack.py` 里补了
   一个带回溯引用的编码器（三种策略取最小：最长匹配 / 最近匹配 / 惰性匹配）。

### 2.3 一个必须知道的坑：图形被多个头像共用

**50 份图形流被不止一个表情引用**。例如：

```
0x408BD8 -> 1/0, 36/0..36/4, 37/0..37/4, 38/0..38/4, 39/0..39/4,
            40/0..40/4, 42/0..42/4, 55/0..55/4
```

改 `portrait 1 / expr 0` 的图形，**这 30 个表情会一起变**。
工具会在写回时打印共用者清单，导出索引里也有 `shared_graphics_with` 字段。

---

## 3. 写回是怎么做的（安全在哪）

### 3.1 声明的「已知字段」集合

一次写回只允许改动两个区间：

1. **图像流**：`[gfx_ptr, gfx_ptr + len(新流))`；
2. **调色板**：`[palette_ptr, palette_ptr + 128)`。

**流末尾到下一个资源之间的残留字节保持原样**（仓库的写回模型：
「复制原生条目，只覆盖已知字段，未知字节原样保留」）。
残留字节不会被解码器读到 —— LZ77 解码器产出满 6400 字节就停，
不会把残留当成新 token。

### 3.2 可执行的自检（`--portrait-self-test`）

对**全部 310 个**头像逐个做：

1. 导出：解压得到 6400 字节图形 + 128 字节调色板；
2. 原样写回；
3. 再导出：结果必须与第 1 步**逐字节相等**（图形 + 调色板）；
4. **声明字段之外**的每一个字节都必须与原 ROM 相同。

任何一条不满足就打印 `FAIL:` 并以非零码退出。

```
$ python tools\export_content_pack.py --portrait-self-test
portrait self-test: 310 portraits round-tripped
PORTRAIT SELF-TEST: PASS
```

### 3.3 端到端演示（`build/portrait_writeback_demo.py`）

改 1 个图形字节 + 1 个调色板字节 → 写回 ROM **副本** → 再导出比对：

```
graphics survive the round trip : True
palette survives the round trip  : True
bytes that differ in the ROM copy: 2932
first byte outside the fields    : none
rom/base.gba untouched           : True
```

`rom/base.gba` **永远不被修改**：`--portrait-rom-out` 必须给一个输出路径，
工具只写那个文件。

---

## 4. 现在能做什么 / 还差什么

### 能做

- **导出**：把 310 个头像的图形（6400 字节）与调色板（128 字节）导出成二进制 +
  索引 JSON（`--portrait-out`），索引里带 ROM 地址、压缩预算、共用者清单。
- **写回**：把新的图形 + 调色板写进 ROM 副本；越界（压缩后装不下）直接拒绝。
- **自检**：310/310 的无损往返 + 未声明字节不动，全部可执行。

### 还差什么（明确列出）

1. **写回路径还没有登记进 `tools/writeback_paths.py`**。
   该文件不归我修改（属于仓库的写回路径登记表），
   需要 session owner 加一条 `portrait` 用例。需要满足：
   - 作者输入 = 一份 6400 字节图形 + 一份 128 字节调色板；
   - 读回值 = 从 ROM 再解压得到的图形 + 再读出的调色板，必须等于作者输入；
   - 声明字段集合 = 上面 §3.1 的两个区间，其余字节必须原样。
2. **工具归属**。本轮为了不越权，把头像代码放在了 `tools/export_content_pack.py`
   里（该文件是「导出 ROM 可编辑内容」的工具，头像素材属于这个范畴）。
   如果 owner 更希望拆成 `tools/portrait_writeback.py`（或 `tools/import_portrait.py`），
   可以整体搬过去 —— 本文件里的
   `lz77_compress()` / `portrait_entries()` / `portrait_budget()` /
   `portrait_assets()` / `import_portrait()` / `verify_portrait_roundtrip()` /
   `export_portrait_assets()` 都是自洽的，搬迁不需要改逻辑。
3. **「参数 << 4」的运行时改写语义未证实**（§1.2）。
   它改的是 VRAM 上传的副本，不影响 ROM，所以**不影响写回的安全性**，
   但影响「编辑器预览是否与游戏一致」。
4. **拼块表（`portrait_pieces`, `0x4643C0`）与头像图形的关系未证实**。
   6 块拼出 80×80，但块里的 `tile` 下标（0/8/24/40/56/72，最大到 135）
   **超出 6400 字节缓冲里的 100 张图块**，所以拼块表指向的**不是**每个头像
   自己的图块缓冲，而是另一张共享图块表。这条链没有查清。
5. ~~**行 63 的垃圾指针**（§1.3）需要在注册表里标注「无效」。~~ —— **2026-10-22 作废**：行 63 其实是紧跟着的说话人名表，不是垃圾（见 §1.3 的订正）。注册表应标成「**63 行头像 + 紧跟着是说话人名表**」。

---

## 5. 给其他 owner 的需求（不在我的文件里）

| 文件 | 需求 |
|---|---|
| `tools/portrait_assets.py` | ① 注释「80*80/2 = 6400 bytes of 4bpp」算错了：6400 是 **8bpp**（100 张 64 字节图块）；`TILE_BYTES = 32` 对头像不成立。<br>② 「portrait ids with data: 63」应过滤掉**行 63** —— 但**理由要改**：行 63 不是「指针不在 ROM 内」，它**就是紧跟着的说话人名表**（`0x085A4DEC + 63×40 = 0x085A57C4`，见 §1.3 的 2026-10-22 订正）。有效 id 仍是 **62 个 / 310 条表情**。<br>③ 调色板长度应按 128 字节判定（现在写的是 `palette_is_raw_128`，判据可以保留）。 |
| `tools/lib/lz77.py` | 纯字面量编码器**不能**用于写回（6400 → 7200 字节）。本轮在 `tools/export_content_pack.py` 里另写了带回溯引用的 `lz77_compress()`；若 owner 想收敛，建议把它挪进本模块。 |
| `tools/writeback_paths.py` | 登记 `portrait` 写回路径（见 §4.1 的验收条件）。 |
| `tools/table_registry.py` | 头像表 `0x085A4DEC` 的行数应标成「**63 行（id 0..62，只有 1..62 有效）；紧跟着的第 63 行是说话人名表 `0x085A57C4`，不是垃圾指针**」（见 §1.3 的 2026-10-22 订正）。 |

---

## 6. 回归

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m unittest discover -s tests -p 'test_*.py'
python tools\automated_test.py
python tools\completion_audit.py --check
```

结果见本轮工作报告。

---

## 2026-10-21 追加：头像的 `param << 4` 改写与拼块表

### 1. `param << 4` 到底是什么（`0x080961D6`..`0x080961F8`）

```
0x080961D6  lsls r2, r6, #4        ; r2 = param << 4      <<< 那个「参数」
0x080961DA  lsls r6, r6, #5        ; r6 = param * 32
0x080961DC  ldr  r3, [pc, #0x50]   ; 0x18FF = 6144        <<< 循环上界
0x080961DE  ldrb r0, [r4]          ; 解压后的一个字节
0x080961E0  cmp  r0, #0
0x080961E2  beq  0x80961e8         ; 0 字节不动
0x080961E4  adds r0, r0, r2        ; 非 0 字节 += (param << 4)   (mod 256)
0x080961E6  strb r0, [r4]
0x080961F6  cmp  r0, r3            ; 只处理前 6144 字节
0x080961F8  ble  0x80961de
```

**同一个 `param`（r6）还决定了两件事**：

```
0x08096206  ldr  r0, [pc, #0x2c]   ; 0x05000200  BG 调色板 RAM
0x08096208  adds r5, r6, r0        ; 槽位 = 0x05000200 + param*32
0x0809620C  ldr  r0, [r1, #4]      ; 头像自己的调色板指针
0x08096210  movs r2, #0x40         ; 64 字 = 256 字节
0x08096212  bl   0x809c0e0         ; CpuSet
```

**结论（可证伪）**：这是一次**调色板索引平移**，不是描边。
头像是 8bpp、索引值 0..63（64 色调色板，128 字节），
引擎把**整张 64 色调色板**拷进 `0x05000200 + param*32` 这个槽，
同时把像素索引整体抬高 `param*16`，
于是「这个头像实际用的那一段 16 色窗口」落到 0..15，
与它上传的 16 色调色板槽对齐。

**因此**：

- 它**不是**换色（调色板数据本身没被改）；
- 它**不是**描边（没有任何邻域判断，只有一次加法）；
- 它**是**「选哪一段 16 色调色板」的索引重基。

旧笔记里「用途未证实（换色/描边）」的说法**作废**。

### 2. 拼块表 `portrait_pieces`（`0x4643C0`）的结构

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

6 块拼出 80×80：块 5 = (0,0) 64×64，块 4 = (0,64) 32×16，
块 3 = (32,64) 32×16，块 0 = (64,64) 16×16，
块 2 = (64,0) 16×32，块 1 = (64,32) 16×32。

**旧笔记的前提成立**：第 5 块从 tile 72 起、宽 64，
覆盖 tile 72..135，**超出单个头像自己那 100 张图块（6400 字节）**。
⇒ 这些拼块**不是**从某个头像自己的缓冲里取的。

**仍未闭合**：这张**共享图块表**的基址本轮没能在运行时读出 ——
`0x084643C0` 在 ROM 里**没有任何字面量读者**
（`tools/consumer_locate.py` 的 `LiteralIndex.readers_of` 读数 = 0），
所以它不是被 `ldr rX, [pc, #imm]` 直接取址的，
只能由消费方算出来。运行时探针
（`tools/closure_portrait_probe.py`）已经写好：
它会在 `0x08096202`（拷贝到 VRAM 的那一刻）读 VRAM 与 ROM 解压结果逐字节比对
（同时给出 E 的验证），并检查拼块用到的 0..135 号图块在
VRAM OBJ 图块池 `0x06010000` 里是否非空；
但本轮在**战斗（组 9 / 子 0）与剧情场景 40**里
`0x08096202` **一次都没命中**（头像只在别的对话场景出现）。

### 可证伪测试

```
python tools\closure_portrait_probe.py --scene <有头像的对话场景> --hits 2
```

命中后必须满足：VRAM 的 6400 字节 = ROM 解压结果，
其中前 6144 字节的非 0 值全部 `+= (param<<4) (mod 256)`，后 256 字节逐字节相同。
