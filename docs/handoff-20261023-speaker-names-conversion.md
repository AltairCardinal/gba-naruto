# 交接文档：ROM 编辑器「说话人名表变长化」这一轮的现状（2026-10-23）

> 这份文档接替两个已经跑偏的会话：
>
> | 会话 | ID | 时间 | 结局 |
> |---|---|---|---|
> | 原始 | `mvs_98a2c77634e643398f28f552bbb5aabf` | 2026-10-21 00:33 → 10-23 02:53 | runtime 崩溃中断（`interrupted` / crash-recovery） |
> | 接手 | `mvs_39e499d2896644f1b9be05346e12f193` | 2026-10-23 02:48 → 14:51 | Goal `tg_qtuqa3zan3mvjw9ggy` 被用户置为 `paused(user_requested)` |
>
> 两个会话陷进同一种「无限循环思考」，成因分析见
> `notes/evidence/session-loop-analysis-20261023.md`。
> **本文档只讲工作本身的状态，不讲会话的运行事故。**

---

## 0. 任务原文

2026-10-23 用户在原始会话里追加了 4 条要求（落盘在 `messages.jsonl` 的 `#485`）：

1. 用模拟器去真机验收
2. 搞清楚那些孤儿代码来历
3. 人工协调不可接受，处理
4. 从结构上变不了的那 2 张，也改成可变的

其中第 4 条承接自 `docs/sequel-roadmap.md` 的「2026-10-22（夜）第十六/十七轮」：
11 张文本表里 9 张是指针表驱动（本来就可变长），剩下 **2 张结构上变不了** ——
`speaker_names`（定长内联槽，12 字节写死在表里）与 `battle_objectives`（绝对地址引用）。

---

## 1. 四条要求的完成情况

| # | 要求 | 状态 | 证据 |
|---|---|---|---|
| 1 | 模拟器真机验收 | **部分** | 剧本搬迁 ✅、孤儿字节 ✅；说话人名表 ❌（见 §3） |
| 2 | 孤儿代码来历 | ✅ **已查明** | `notes/evidence/story-orphan-bytes-20261023.md` |
| 3 | 消除「人工协调」 | ✅ **已消除** | `battle_objectives` 改成指针表驱动 + 多槽机制（§2.3） |
| 4 | 2 张变不了的表改成可变 | ⚠️ **1 张完成、1 张根因已找到、修法已实测并已落地** | `battle_objectives` ✅；`speaker_names`：根因 = 补丁末尾的 `0xBF00`（§3.1），产品侧已落地（§5） |

### 1.1 孤儿代码来历（要求 2，已闭合）

`notes/evidence/story-orphan-bytes-20261023.md`（探针 `tools/probe_orphan_bytes.mjs`，
输出 `build/story-orphan-bytes.txt`）：

- 剧本区跨度 = 文件偏移 `0x009F2E..0x05CD40`（339,474 字节）；
- 202 个剧本、190 个不同起始地址，指令字节并集 337,238 字节（99.34%）；
- 剩下的 **2,236 字节 / 91 个区间**里，**≥5 字节的只有 3 个、合计 2,145 字节**
  （即常说的「2,145 字节」），其余 88 个区间合计 91 字节；
- **结论**：这 2,145 字节**不是别的表、也不是 ARM 代码**，而是**三段被汉化补丁挤下来的、
  仍然完全合法的 story-VM 剧本**（字节码 + 中文对白）+ 缝隙里的残留字节；
- 全 ROM **无任何指针可达** ⇒ 运行时永远不会被执行 ⇒ **无害，不用处理**。

验收：`tools/mgba_probe/orphan_acceptance.py`（真机跑一遍确认不崩、不影响剧情）。

### 1.2 真机验收（要求 1，已做的部分）

`notes/evidence/story-relocation-live-20261023.md`（工具
`tools/mgba_probe/relocation_acceptance.py` + `tools/build_reloc_test_rom.mjs`，
宿主 `build/mgba-probe/mgba-probe.exe` —— 仓库自带的无头 mGBA）：

四条动态证据全部拿到 ——
① 游戏跟着改过的根表指针走；② 跑中的剧本里就是变长后的新正文；
③ 改过的那句之后脚本继续往下跑（分支重基对了）；④ 画面只在对白那一行变。

> 这一轮**之前**「搬迁后的 ROM 没在模拟器里真机跑过」是 roadmap 上挂着的一条未闭合项，
> 现在闭合了。**说话人名表**那一半仍然没闭合（§3）。

---

## 2. 已经落地、但**还没提交**的工作

工作树里有 **12 个已修改文件 + 40 个未跟踪文件**（工具与证据笔记），
全部属于这一轮，**没有提交**。请先看这份清单再动代码。

### 2.1 已提交（HEAD = `18982789`）

前 20 个提交是之前 17 轮编辑器的成果，与本轮无关，本轮**没有新提交**。

### 2.2 本轮的代码改动（未提交）

```
 rom-editor/content/pack.json              | 1207 +++++++++++++++++++++++------
 rom-editor/content/pack.min.json.gz       |  Bin 324974 -> 327452 bytes
 rom-editor/js/editors.js                  |   34 +-      ← 写回规则文案 + 「可转换」表不再当场拦
 rom-editor/js/modules/common.js           |    1 +
 rom-editor/js/pack.js                     |   17 +       ← textSlotKind 新增 'convertible'
 rom-editor/js/parsepack.js                |   38 +-      ← 解析时能认出「已转换」形态的 ROM
 rom-editor/js/rom.js                      |  134 +++-    ← applyInlineToPointer()：定长内联槽 → 指针表
 rom-editor/tools/verify_variable_text.mjs |   86 +-      ← 门禁扩到 82 条断言
 rom-editor/tools/verify_views.mjs         |   15 +-      ← ⚠️ 改了一半（见 §4.1）
 tools/export_content_pack.py              |  105 +-
 tools/import_dialogue_var.py              |   69 +-
 tools/mgba_probe/story_vm_capture.py       |    9 +-
```

核心新增是 `rom-editor/js/rom.js::applyInlineToPointer()`：
把一张「定长内联槽」的文本表就地转成**指针表 + 变长串池**，
并把 ROM 里的**取名读者**从 `基址 + id*12` 改成 `基址 + id*4` 再解引用
（**指令数与字节数都不变 ⇒ 不挪动任何后续代码**）。

### 2.3 「人工协调」的消除（要求 3）

`battle_objectives` 原来是「绝对地址引用」（地址写死在代码里），现在改成**指针表驱动**，
并且补上了**一条说明被多条战斗目标共用**的情况：

- `rom-editor/js/rom.js::pointerSlotsOf()` —— 一条文本记录可以带**多个**指针槽
  （`pointer_offsets`），写回时**每个槽都要改**；漏一个，共用它的那条战斗目标
  就还指着旧地址，界面上看到的和游戏里跑的就对不上；
- 门禁断言：「**每一个**槽都改到了新地址（2 个）」✅。

### 2.4 新增的证据笔记（`notes/evidence/`）

| 文件 | 内容 |
|---|---|
| `speaker-name-table-20261023.md` | 说话人名表（`0x085A57C4`）的 12 个原生读者考证 + 变长可行性 |
| `speaker-names-hypothesis-ledger.md` | **假设台账**：已确认 16 条 / 已证伪 15 条 / U1–U5 已判定 —— 下一个会话从这里接着干，**不用重推一遍** |
| `speaker-name-code-patches-20261023.md` | 14 处代码补丁清单（机器可读）+ 逐处反汇编核对 |
| `story-orphan-bytes-20261023.md` | 2,145 字节孤儿代码的来历（要求 2） |
| `story-relocation-live-20261023.md` | 剧本搬迁的真机验收（要求 1 的一半） |

**2026-10-23 晚补（本轮新增的 7 篇证据笔记）**：

| 文件 | 内容 |
|---|---|
| `speaker-name-round-summary-20261023.md` | **本轮总览**（要什么 → 做了什么 → 结论 → 证据在哪）—— **先读这篇** |
| `speaker-name-patch-bisect-20261023.md` | **补丁级二分（14 行表）** —— U5：14 处补丁单独开 / 去掉都没有差别 |
| `speaker-name-relocation-experiment-20261023.md` | **指针表搬家实验（V0..V4）** —— 搬走照样卡 ⇒ 病灶与指针表位置无关 |
| `speaker-name-align-experiment-20261023.md` | **串池对齐 / 指针指向实验（P0..P4）+ 按读者二分** —— 只有一个读者会坏 |
| `speaker-name-freeze-trace-20261023.md` | **逐指令定位（根因在这里）** —— §4.0 / §4.1 是 A/B 证据；§6 是 mGBA 调试器的五个坑 |
| `speaker-name-read-paths-20261023.md` | **全 ROM 读名路径穷举普查** —— U1：没有第 13 个读者 |
| `speaker-name-id63-20261023.md` | **id 63 语义考证** —— U4；顺带查出地点名表（N1/N2/N3） |

### 2.5 新增的工具（`tools/`）

| 文件 | 用途 |
|---|---|
| `tools/data/speaker_name_code_patches.json` | **14 处补丁清单（机器可读）** |
| `tools/probe_speaker_code_patches.mjs` | 校验补丁：逐处反汇编对比 + 全 ROM 差异扫描 |
| `tools/probe_speaker_{names,readers,scan,decode,space,tail,ids,dynamic,render,box,arm,budget}.py` | 12 个只读探针，找出 12 个读者 |
| `tools/build_speaker_test_rom.mjs` | 造「说话人名变长」的测试 ROM |
| `tools/build_speaker_probe_rom.mjs` | 造探针用的 ROM |
| `tools/build_reloc_test_rom.mjs` | 造「对白变长」的测试 ROM |
| `tools/mgba_probe/relocation_acceptance.py` | 剧本搬迁的真机验收 |
| `tools/mgba_probe/orphan_acceptance.py` | 孤儿字节的真机验收 |
| `tools/mgba_probe/speaker_bisect.py` | **补丁级二分**（U5，已跑完） |
| `tools/mgba_probe/speaker_relocate_probe.py` | **指针表搬家实验**（V0..V4，已跑完） |
| `tools/mgba_probe/speaker_align_probe.py` | **串池对齐 / 指针指向实验 + 按读者二分**（P0..P4，已跑完） |
| `tools/mgba_probe/speaker_freeze_trace.py` | **逐指令定位 + `--fix-nop` A/B**（读 CPSR / 单断点 / 解引用链 / 冻结现场解剖 / 非法指令识别） |
| `tools/probe_speaker_read_paths.py` | **全 ROM 读名路径穷举**（U1，已跑完） |
| `tools/probe_speaker_id63.py` | **id 63 语义考证**（U4，已跑完） |
| `tools/mgba_probe/speaker_read_trace.py` | 取名读者的读值追踪 |
| `tools/fix_speaker_deref.py` | 解引用指令形态的修正（见 §3.3） |
| `tools/probe_orphan_bytes.mjs` | 孤儿字节普查 |
| `rom-editor/tools/verify_speaker_conversion.mjs` | **新门禁（42 条断言，全过）**：转换路径的无头验收 —— 没改过的包仍逐字节相同 / 14 处补丁逐字节落地 / 指针表 64 槽合法 / 保护区未动 / 串池内容正确 / 转换后能解析回来 |
| `rom-editor/tools/verify_free_space.mjs` | **新门禁（16 条断言，全过）**：编辑器与 Python 老链路**两个空闲区分配器互不踩踏** |

> 会话分析用的三个探针也一并留在仓库里：
> `tools/analyze_session_loop.py`、`tools/analyze_toolcall_leak.py`、`tools/extract_session_users.py`
> （用法见 `notes/evidence/session-loop-analysis-20261023.md`）。

---

## 3. 唯一的未闭合项：说话人名表变长化的真机验收（要求 4 的另一半）

### 3.1 症状（**2026-10-23 晚补已改正：下面是真实死法**）

`node tools/build_speaker_test_rom.mjs` 造出 `build/speaker-test.gba`
（把 id 1 的「鸣人」改成「鸣人测试」），构建报告：

```
转换 speaker_names（inline_to_pointer）：指针表基址 0x5A57C4，64 条名字
串池：64 条名字，0x5DFBEC 起
```

ROM 构建**成功**（无 error），但**跑起来卡死**：按第 5 次 A 之后**画面彻底不再变化**，
冻结画面哈希恒为 `fa4fd7206ccc`。

**真实死法（2026-10-23 查明）**：**未定义指令异常死循环**，不是「指针坏了」。

- 14 处代码补丁末尾的填充字节用了 **`0xBF00`**（Thumb NOP 编码）；
- `0xBF00` 在 **ARMv4T**（GBA 的 ARM7TDMI）上是**未定义指令**
  （`NOP/YIELD/WFE/WFI/SEV` 这些 hint 指令是 ARMv5T 才有的）
  ⇒ 一执行就抛 **Undefined Instruction 异常**；
- 进 BIOS 异常向量 ⇒ BIOS 异常处理程序**回到出错的指令**（`LR = 出错指令地址 + 2`）
  ⇒ 同一条指令再次出错 ⇒ **无限异常循环** ⇒ 画面不再推进。
- 死循环的 4 条指令：
  ```
  0x00000008   BIOS 未定义指令向量（ARM, mode=0x1B）
  0x000001A8   BIOS 异常返回
  0x08097A14   op 0x08 handler 里的 0xBF00   ← 出错点
  0x08097A16   adds r0, r6, #0
  → 0x00000008（再次异常）→ 无限循环
  ```
- 现场证据：冻结时 `CPSR = 0x0000009B`（T=0 ⇒ ARM 状态、mode=0x1B Undefined、I=1）、
  `LR = 0x08097A16`（= `0x08097A14` + 2）、`sp = 0`（**异常模式的 banked SP**，不是栈被写坏）；
  mGBA 自己报 **`Hit illegal opcode at 0x08097A14: 0x0000BF00`**，它自己的反汇编打的是 **`BF00: ill`**。

> ⚠️ **旧描述作废**：本文档原先写的是「渲染器入口 `0x0806626C` 能命中、返回点 `0x08097A1C`
> 永远不命中 ⇒ 渲染器拿着一个坏指针进循环」。**这是 mGBA 调试器假象** ——
> 软件断点命中后会把那条指令**再执行一遍**，**原版 ROM 上同样不命中**。
> 转换版里「名字渲染」那一次调用**根本没有发生**（不是坏指针，是没调用）。
> ⇒ **可靠判据只有一个：画面还推不推进。**

**修法（已实测有效）**：14 处补丁 `after_hex` 的**最后 2 字节** `00 bf` → `c0 46`
（`0x46C0` = `mov r8,r8`：ARMv4T 合法、**不改寄存器**、**不改标志位**、**长度不变 2 字节**）。
A/B：转换版从**卡死**（变化 6 步 / 冻结第 6 步）变成**能跑**（按 14 次 A，**变化 13 步，全程不冻结**）。
证据：`notes/evidence/speaker-name-freeze-trace-20261023.md` §4.0 / §4.1。

### 3.2 我复核过的部分（都**排除**了）

以下每一项我都重新验算过，**不是**原因，**不要再往这些方向查**：

| 检查项 | 方法 | 结果 |
|---|---|---|
| 14 处补丁的反汇编 | `capstone` 逐处反汇编 `build/speaker-test.gba` | 14/14 与清单一致，**长度全对**（10/10/10/10/10/10/10/10/**8**/10/10/12…共 10、10、10、10、10、10、10、10、8、10、10、10、10、8） |
| 补丁有没有误伤后续代码 | 对比补丁窗口**之后 8 字节** | 14/14 **逐字节未动** |
| 12 处 `ldr [pc,#imm]` 指向的字面量 | 手工算 PC 基准 + imm8 | 12/12 取到的都是 `0x085A57C4` ✅（两处 variant D 沿用寄存器里的基址） |
| 跨调用依赖的寄存器 | `0x0806626C` 渲染器 `push {r4,r5,r6,r7,lr}`；`0x0809C528` strlen `push {r4,r5,lr}` | **r4/r5 被保住** ✅ |
| 指针表 64 项 | 读 `build/speaker-test.gba` | 64/64 都落在 ROM 内；`id 63 → 池里的「没有」` ✅ |
| 保护区（全名表 `0x085A5AB8..0x085A5F78`） | 逐字节对比原版 | **一个字节都没动** ✅ |
| 串池对齐（64 条里 32 条起始地址是奇数） | 反汇编渲染器 | 渲染器全程 `ldrb` **逐字节**读字符串；16 位读只发生在 RAM 对象和字体表 ⇒ **对齐不是原因** |
| 文本串池与剧本搬迁抢 `0x5DFBEC` | 读 `rom.js::allocate()` | `allocate()` 只找 `0xFF` 段；池写进去后不再是 `0xFF` ⇒ **不会互相覆盖** |

### 3.2b **2026-10-23 晚补：这一轮又排除的 11 项**（同样**不要再往这些方向查**）

| # | 被排除的怀疑 | 判定实验与关键数字 | 证据 |
|---|---|---|---|
| 1 | **指针表占用了旧名字表那片地址** | 搬到空闲区 `0x085B56E0`（12 处字面量同步改、14 处补丁全开）⇒ **V1 仍卡**，且 16 张截图与基线**逐帧完全相同**（同一冻结哈希 `fa4fd7206ccc`）；自检证明旧内联表那 256 字节**逐字节没被动过** | `notes/evidence/speaker-name-relocation-experiment-20261023.md` §0/§4 |
| 2 | **串池没对齐** | 补齐到 2 字节对齐（奇地址 **0/64**）、4 字节对齐（奇地址 **0/64**、非 4 字节对齐 **0/64**）⇒ 两个变体**都卡在同一帧、同一哈希** | `notes/evidence/speaker-name-align-experiment-20261023.md` §2 |
| 3 | **名字太长 / 名字框放不下** | 3/4/6 字变体**冻结点完全一样**；**等长**名字（V4）照样卡 | `notes/evidence/speaker-name-patch-bisect-20261023.md` §4.4；`notes/evidence/speaker-name-relocation-experiment-20261023.md` §6.2 |
| 4 | **名字内容 / 「名字被搬进池子」本身** | **P3 把指针指回原版内联槽、名字一个字节都没动、串池完全不写** ⇒ 仍卡在同一帧；**P4 名字确实改长、仍住原位** ⇒ 仍卡在同一帧 | `notes/evidence/speaker-name-align-experiment-20261023.md` §2（P3/P4） |
| 5 | **存在第 13 个没被识别出来的读者** | 全 ROM 穷举：字面量 **12/12**、原始 u32 **12/12**、`×12` 步长 **14/14**、污点分析窄窗口 38 条路径 / 26 站点**全在 14 处补丁内**、宽窗口 **0 条新增** ⇒ **多出来的读者 = 0** | `notes/evidence/speaker-name-read-paths-20261023.md` §0/§2 |
| 6 | **12 个字面量槽被别的代码共用** | 每个槽**恰好 1 条**引用、就是它自己的读者；全 ROM `u32 == 0x085A57C4` **恰好 12 次**；`0x08097A40` 区域**没有跳转表、没有别的常量表** | `notes/evidence/speaker-name-freeze-trace-20261023.md` §3.5 |
| 7 | **id 63 的全名 / 简称语义冲突** | 剧情 VM **从未用过 id 63**：`op 0x08` 用过的 **49** 个 id 全在 **1..61**，`op 0x0E` 只用 **{1,2,3,25,26}**；三处「没有」是作者**刻意的存储别名** | `notes/evidence/speaker-name-id63-20261023.md` §2/§5 |
| 8 | **头像表 id 63 被指针表盖住** | 把头像 id 63 那 **40 字节改回原版内容**，**冻结点一点没变**（`(5,5)` 仍是 `(5,5)`） | `notes/evidence/speaker-name-patch-bisect-20261023.md` §4.7 |
| 9 | **14 处补丁里有某一处单独就坏** | 单独开 / 单独去掉**都没有可观测差别**；只有 #13（`vm_0x08`）看起来有影响，是因为**它跑得最早**（14 处补丁全部以 `0xBF00` 结尾，谁先被执行到谁先炸） | `notes/evidence/speaker-name-patch-bisect-20261023.md` §3；`notes/evidence/speaker-name-freeze-trace-20261023.md` §0 |
| 10 | **串池用单个 `0x00` 终止符** | 渲染器 `0x0806626C`、名字长度函数 `0x08067110`、游戏自己的 strlen `0x0809C528` **全部按字节扫**（strlen 还有不对齐的字节回退路径 `0x0809C560`）⇒ 无害 | `notes/evidence/speaker-name-relocation-experiment-20261023.md` §6.3 |
| 11 | **「`0x08097A1C` 永远不命中 ⇒ 渲染器拿着坏指针」** | **mGBA 调试器假象**：断点是软件断点，命中后会把那条指令**再执行一遍**；**原版 ROM 上同样不命中** | `notes/evidence/speaker-name-patch-bisect-20261023.md` §1.1；`notes/evidence/speaker-name-freeze-trace-20261023.md` §3.1 |

> ⚠️ **被推翻的前提，下一轮不要再拿它们当前提**：
> 「渲染器拿着坏指针进了循环」（调试器假象）·「病灶在数据侧的指针表布局上」（已被搬家实验推翻）。
> ⇒ **可靠判据只有一个：画面还推不推进。**

### 3.3 已知的两个历史坑（都已修，列出来免得重犯）

1. **解引用指令形态**：Thumb-1 里 `ldr r0, [r0, 0]` 算的是 `0 + 0 = 2×r0`（寄存器偏移），
   **不是** `*(r0)`。补丁清单里的「第十八轮更正」把它改成了立即数偏移形式
   `ldr r0, [r0, #0]`（= Thumb-1 `LDR (imm)` T1，imm5=0）✅
2. **字形码字节序**：lead（0x80–0x9F）在前、trail 在后。已修 ✅
   （抽查池里 `鸣人测试` = `92 98 94 c8 89 df 95 d1`，对）。

### 3.4 ⚠️ 会话 1 最后一个结论**不成立**（重要，别跟着它走）

原始会话的最后一条消息（约 02:28）宣布「**找到根因了**」：

> 指针表 `0x5A57C4..0x5A58C3` **盖住了头像表（`portrait_table`）的最后一条记录**
> ⇒ 头像表 id 63 被毁 ⇒ 0x08 处理器读头像表 ⇒ 这就是 VM 死循环的原因。
> 修法：把指针表挪到 `0x5A57EC`。

**这条结论是错的。** 我复核过：

- `portrait_table` = 64 条 × 40 字节 = `0x5A4DEC..0x5A57EC`，
  **第 64 条**（id 63）= `0x5A57C4..0x5A57EC`；
- 但在**原版 ROM** 里，这 40 字节是 `92 59 9a 9a 00 00 …` —— **是字形码，不是头像指针**。
  也就是说，**原版里这 40 字节本来就被说话人名表占着**，
  `portrait_table` 的 id 63 在原版里**已经是死区**（读出来是垃圾指针，游戏本来就不用它）；
- 新的指针表 256 字节**完整落在旧名字表 756 字节的footprint 之内**
  （`0x5A57C4..0x5A5AB8`）⇒ **没有制造任何新的冲突**。

⇒ 那个「重叠」是**原版就存在的**，不是转换引入的。**按它去改（挪到 `0x5A57EC`）
只会引入 12 处字面量地址补丁，把事情搞得更复杂。**

**2026-10-23 晚补（这条仍然成立，而且后面还补了一刀）**：
后来查出的**真根因是 `0xBF00`**（14 处补丁末尾的填充字节在 ARMv4T 上是**未定义指令**
⇒ 未定义指令异常死循环，§3.1），**与头像表毫无关系**。
而且把头像 id 63 那 40 字节**改回原版内容**，**冻结点一点没变**
⇒ 头像 id 63 **也不是**病灶（`notes/evidence/speaker-name-patch-bisect-20261023.md` §4.7）。

### 3.5 我当时列的三个嫌疑（**三个都已查完，结论见下**）

| # | 当时的嫌疑 | 现在的结论 |
|---|---|---|
| 1 | **有没有第 13 个没被识别出来的读者** | **没有。** 全 ROM 穷举：字面量 **12/12**、原始 u32 **12/12**、`×12` 步长 **14/14**、污点分析窄窗口 38 条路径 / 26 站点**全在 14 处补丁内**、宽窗口 **0 条新增** ⇒ **多出来的读者 = 0**（`notes/evidence/speaker-name-read-paths-20261023.md`） |
| 2 | **某个读者的 id 不是「一个字节」/ 那条 `ldrb` 不一定执行到** | **不是。** 14 处逐条核对通过：id 都是**同一条路径上取到的字节**，两版读的是**同一个字面量槽**（`notes/evidence/speaker-name-freeze-trace-20261023.md` §3） |
| 3 | **id 63 的取值域 / 全名 vs 简称语义** | **不是。** 剧情 VM **从未用过 id 63**（`op 0x08` 用过的 49 个 id 全在 `1..61`，`op 0x0E` 只用 `{1,2,3,25,26}`）；三处「没有」是**作者刻意的存储别名**（`notes/evidence/speaker-name-id63-20261023.md`） |

**而且这三个嫌疑之外**，「指针表放哪」「串池对齐」「名字长度与内容」也都被逐条证伪（§3.2b）。
⇒ **当时列的这张清单已经全部走完，真根因在别处：补丁末尾的填充字节（§3.1）。**

---

## 4. 当前可复现的基线（我实测的）

### 4.1 门禁状态（**2026-10-23 晚补：现在是 21 道全绿**）

```
node rom-editor/tools/verify_variable_text.mjs      →  全部通过（82 条断言）✅
node rom-editor/tools/verify_speaker_conversion.mjs →  全部通过（42 条断言）✅
node rom-editor/tools/verify_free_space.mjs         →  全部通过（16 条断言）✅
node rom-editor/tools/verify_views.mjs              →  全部通过 ✅（下面那 3 条过期断言已改写）
⇒ rom-editor/tools/verify_*.mjs 共 21 个脚本，全部 exit=0 ✅
```

**这一轮还修掉了两个真 bug**（都不在 `rom-editor/**` 的门禁覆盖面之外，
是靠独立验收发现的）：

1. **`rom-editor/js/parsepack.js` 解析原版 ROM 时的 `capacity` 判定错误**：
   `speaker_names` 的 `capacity` 被读成「名字长度+1」（5/7/3/9）而不是真实的 **12**
   （定长内联槽）—— 原因是 `fixedSlot` 判定**没有覆盖「未转换的可转换表」**。
   已修：现在 `capacity` 全是 12、`raw` 全 12 字节、**往返重建仍与原版逐字节相同**；
   门禁新增 `report.textsRead`（每张表**实际从 ROM 读到几条记录**）作为「形态判对没」的判据。
2. **三道门禁的过期断言**（`verify_views` / `verify_pack` / `verify_load_flow`）
   已被改写成对当前正确行为的断言；独立验收又查出其中**一条被改弱**、**一条是空转断言**，已修正。

**顺带一条好消息**：上一轮（第十六/十七轮）挂在 roadmap 上的三条「已知未闭合」，
**到这一轮已经全部闭合** ——

| 上一轮的未闭合项 | 现在 |
|---|---|
| 搬迁后的 ROM 没在模拟器里真机跑过 | ✅ `story-relocation-live-20261023.md` |
| 2,145 字节孤儿代码来历不明 | ✅ `story-orphan-bytes-20261023.md`（且已真机验收） |
| `import_dialogue_var.py` 与编辑器共用同一段空闲区、互不知情 | ✅ 两边都改成**只写 0xFF 段**，门禁 `verify_free_space.mjs` |

**（历史记录）当时 `verify_views.mjs` 的 3 项失败全是「过期的断言」，不是新功能坏了** ——
会话 1 最后一步改了行为却没改门禁：

| 失败断言 | 为什么失败 | 怎么修 |
|---|---|---|
| `定长表说明写回规则 — 没有说明` | 断言找一张 `kind==='fixed'` 的表，查文案里有「长度不能变」。但**现在 11 张表里已经没有任何一张是 `fixed` 了** | 改查 `kind==='convertible'` 的 `speaker_names`，断言文案里有「可以变长」 |
| `等长表超长被当场拒绝（记录没变）` | 断言给 `speaker_names` 写超长文本，期待被拒。转换后 `speaker_names` 是 `convertible`，**不再拦**（这正是新功能） | 改成断言「可转换的表**不**拒绝，且提示说会转成指针表」 |
| `超长时给出「放不下」的明确提示` | 同上 | 同上 |

**顺带一个结论**：转换完成后，`editors.js` 里 `kind === 'fixed'` 与默认（绝对地址引用）
两条分支**对当前内容包里的任何一张表都不可达**了 ——
要么在门禁里用构造出来的表把它们测回来，要么把这两条分支删掉。
**不要留着「看起来还有用、其实永远走不到」的代码。**

### 4.2 不变量（仍然成立）

**没改过的内容包重建出来仍与原版逐字节相同**（6,291,456 字节全等）——
转换只由「作者改过这张表」触发。

---

## 5. 下一步该做什么（有序）

> **先看 `notes/evidence/speaker-name-round-summary-20261023.md`**（本轮总览，5 分钟读完），
> 再看 `notes/evidence/speaker-names-hypothesis-ledger.md`（假设台账：
> 16 条已确认的事实、**15 条已证伪的假设**、5 条已判定的假设 U1–U5）。
>
> ⚠️ **静态与动态的所有支线已经走完了** —— 四轮子代理分别做完了
> 补丁级二分 / 指针表搬家 / 串池对齐与读者二分 / 全 ROM 读名路径普查 / id 63 考证 / 逐指令定位。
> **没有别的支线可走**。剩下的是下面这三件**收口**的事。

1. **产品侧落地 `0x46C0`** —— ✅ **已做**（另一条支线，
   见 `notes/evidence/speaker-name-fix-20261023.md`）：
   - `tools/data/speaker_name_code_patches.json`（**唯一真相源**）里
     **14 处 `after_hex` 的最后 2 字节** = `c046`、`new_disasm` 末条 = `mov r8,r8`，
     新增 `conventions.filler`（固定 `0x46C0`、**禁用 `0xBF00`**）；
   - 内容包 `pack.json` / `pack.min.json.gz` 由
     `python tools/export_content_pack.py --no-rom --no-text-index` **重新导出**（不是手改）；
     逐行 diff：**213,678 行里只有 14 行不同**，全是 `after_hex` 那一行；
   - `rom-editor/js/**` **不用改**（填充指令来自内容包，目录里 grep `bf00` 零命中）；
   - 选 `0x46C0`（`mov r8,r8`）的理由：ARMv4T 合法、**不写标志位**、**不改任何寄存器**、
     **长度不变（2 字节）** ⇒ 不用挪动任何后续代码，12 处字面量地址也不用动。
   - ⚠️ **14 处全部要改**，不能只改 #12/#13 —— 其余 13 处只要被执行到就会同样炸。
2. **真机验收** —— 脚本 **已建**（`tools/mgba_probe/speaker_acceptance.py`），
   但**验收结果还没写完**（`speaker-name-fix-20261023.md` 的 §3/§4/§5 还是「待补」）：
   - 门禁侧**已加**断言：**禁用 `0xBF00`** / **必须是 `0x46C0`** / **清单与内容包逐字节同步**
     （`rom-editor/tools/verify_speaker_conversion.mjs`）；
   - 还差：把验收结果写进笔记；**覆盖战斗消息 / 命令消息 / 战斗日志场景**
     —— 那 13 处读者只有被执行到才会被验到（这一轮只跑到剧情开场的 `op 0x08`）。
3. **收口**
   - 21 道门禁保持全绿（**已复验：全部 exit=0**）；
   - 更新 `docs/sequel-roadmap.md` 的「2026-10-23｜ROM 编辑器第十八轮」一节
     与 `notes/evidence/speaker-names-hypothesis-ledger.md`（**均已更新**）。

**仍要验的 3 件小事**
（`notes/evidence/speaker-name-freeze-trace-20261023.md` §8）：
① 战斗消息 / 命令消息 / 战斗日志场景 ——
**验收脚本 §A5「读者覆盖」实测：当前按键路线只覆盖 1/14 处读者（仅 `vm_0x08`）**，
其余 **13 处**当前按键路线**到不了** ⇒ 这是**未闭合的覆盖缺口**，
但**不影响「修复正确」的结论**（修复本身已由 42 条静态断言 + A/B 实测证明有效）；
② 名字**本身画得对不对**（逐像素比对「鸣人测试」是否正确画在名字框里 ——
这一轮只验了「不再卡死」）；
③ 14 处补丁的标志位语义**未逐处实测**（理论核对过，见 freeze-trace §4.2）。

**已经不用再做的事**（旧版 §5 第 1–4 条全部作废）：
① 改 `verify_views.mjs` 的过期断言 —— **已改**（§4.1）；
② 补丁级二分 —— **已做**（14 行表在 `notes/evidence/speaker-name-patch-bisect-20261023.md`）；
③ 查第 13 个读者 —— **已查，没有**（`notes/evidence/speaker-name-read-paths-20261023.md`）；
④ 把指针表挪到空闲区 —— **已证伪，搬了照样卡**（`notes/evidence/speaker-name-relocation-experiment-20261023.md`）
—— **指针表留在 `0x085A57C4` 即可，不要动**。

---

## 6. 复现命令清单

```powershell
cd D:\Github\gba-naruto

# 门禁
node rom-editor/tools/verify_variable_text.mjs      # 期望：全部通过（82 条断言）
node rom-editor/tools/verify_speaker_conversion.mjs # 期望：全部通过（42 条断言）
node rom-editor/tools/verify_free_space.mjs         # 期望：全部通过（16 条断言）
node rom-editor/tools/verify_views.mjs              # 期望：全部通过 ✅（21 道门禁现在全绿）

# 造「说话人名变长」的 ROM
node tools/build_speaker_test_rom.mjs                # → build/speaker-test.gba + build/speaker-test-info.json

# 校验 14 处补丁（只读）
node tools/probe_speaker_code_patches.mjs            # → build/speaker-name-patches.txt

# 真机（无头 mGBA）
python tools/mgba_probe/relocation_acceptance.py     # 剧本搬迁验收（已通过）
python tools/mgba_probe/orphan_acceptance.py         # 孤儿字节验收（已通过）
python tools/mgba_probe/speaker_freeze_trace.py --addr 0x08097A14 --autopsy --cpsr --fix-nop
                                                  # 逐指令定位 + 修法 A/B（根因在这一条）

# 这一轮跑完的静态普查
python tools/probe_speaker_read_paths.py             # 全 ROM 读名路径穷举（U1）
python tools/probe_speaker_id63.py                   # id 63 语义考证（U4）

# 孤儿字节普查 / 说话人名表考证
node tools/probe_orphan_bytes.mjs                    # → build/story-orphan-bytes.txt
python tools/probe_speaker_readers.py                # 12 个读者的清单
```

**宿主**：无头 mGBA 在 `build/mgba-probe/mgba-probe.exe`（仓库自带，C API + mGBA 自己的调试器）；
`capstone` 的位置见 `notes/windows-migration-20261020.md` §2.2（`tools/capstone_loader.py` 会自己找）。

---

## 7. 两句话总结

- **能做的都做完了**：孤儿代码来历已查明（无害）、「人工协调」已消除、战斗目标表已可变长、
  剧本搬迁已真机验收、上一轮挂着的三条「已知未闭合」全部闭合、
  **说话人名表的病灶也已找到并用真机 A/B 证明**（§3.1）、**21 道门禁全绿**。
- **只剩三件事**（§5）：**把 `speaker-name-fix-20261023.md` 的验收结果写完**
  （含**战斗消息 / 命令消息 / 战斗日志**场景）→ **收口** → 更新台账与 roadmap。
  机器码层面（14 处补丁、指针表、串池、保护区）**全都对**；
  会话 1 临死前宣布的那个「根因」是**错的**（§3.4），
  真根因是**补丁末尾的填充字节在 ARMv4T 上是未定义指令**，
  修法**已实测有效并已落进产品数据**（§3.1、§4.1）。
  ⇒ **静态与动态的所有支线都走完了，别再查了。**
