# 假设台账：说话人名表变长化（`speaker_names` → 指针表）

> 这张表是**给下一个接手的人用的**：从「已确认 / 已证伪」直接开始，**不要从头再想一遍**。
>
> 背景：两个会话（`mvs_98a2…` / `mvs_39e4…`）都死在这一个点上，
> 成因见 `notes/evidence/session-loop-analysis-20261023.md`。
> 整体交接见 `docs/handoff-20261023-speaker-names-conversion.md`。
> 本轮总览见 `notes/evidence/speaker-name-round-summary-20261023.md`。
>
> **用法**：一行一个假设。做完「判定动作」就填「结果」和「状态」。
> 状态只有三种：`未验` / `已证伪` / `已确认`。
> **判定动作必须一次就能得出是/否** —— 「再看看」不算判定动作。

---

## 0. 现象（判定的前提）

- 造 ROM：`node tools/build_speaker_test_rom.mjs` → `build/speaker-test.gba`
  （把 id 1 的「鸣人」改成「鸣人测试」）。
- 构建**成功**、无 error；但**跑起来卡死**：画面在按第 5 次 A 之后**彻底不再变化**，
  冻结画面哈希恒为 `fa4fd7206ccc`（`notes/evidence/speaker-name-patch-bisect-20261023.md` §3）。
- **本轮已查明死法**：不是「指针坏了」，而是**未定义指令异常死循环** ——
  14 处代码补丁末尾的填充字节用了 `0xBF00`（Thumb NOP 编码），
  而 `0xBF00` 在 **ARMv4T**（GBA 的 ARM7TDMI）上是**未定义指令**（§4）。
- **可靠判据**：**画面还推不推进**（每按一次 A 截一张 mGBA 渲染缓冲，比相邻两张哈希，
  最后 3 张相同 ⇒ 卡死）。**不要用断点命中与否当判据**（§5）。

---

## 1. 已确认（作为前提，不必再验）

### 1.1 转换机制本身（机械层面全对）

| # | 事实 | 怎么验的 | 复核命令 |
|---|---|---|---|
| F1 | 转换机制**能跑**：14 处补丁逐字节落地、长度全变不了、指针表 64 槽全合法、保护区未动、串池内容正确、转换后能解析回来 | `node rom-editor/tools/verify_speaker_conversion.mjs`（**42 条断言**全过） | 同左 |
| F2 | 14 处补丁的**反汇编**与清单一致，补丁之后 8 字节未被误伤。**长度有两种口径，别混着写**：① **按字节数**（`byte_length`）= **12 条 10 字节 + 2 条 8 字节**（合计 136 字节）；② **按指令条数**（`new_disasm` 的行数）= **12 条 5 条指令 + 2 条 4 条指令** | capstone 逐处反汇编 `build/speaker-test.gba` | `node rom-editor/tools/verify_speaker_conversion.mjs`（42 条断言，exit=0）；逐处 capstone 对拍见下面 ⚠️ 备注 |
| F3 | 12 处 `ldr [pc,#imm]` 取到的字面量**全是 `0x085A57C4`**；两处 variant D 沿用寄存器里的基址 | 手算 PC 基准 + imm8 | 同 F2 |
| F4 | 跨调用依赖的 **r4/r5 被保住**（渲染器 `push {r4,r5,r6,r7,lr}`；strlen `push {r4,r5,lr}`） | 反汇编两个被调函数的序言 | 同 F2 |
| F5 | 指针表 64 槽都在 ROM 内；`id 63 → 池里的「没有」` | 读构建产物 | — |
| F6 | 保护区（说话人全名表 `0x085A5AB8..0x085A5F78`）**逐字节未动** | 与原版对比 | 同 F1 |
| F7 | **串池奇数起始不是原因**（64 条里 32 条起始地址是奇数）：渲染器全程 `ldrb` 逐字节读字符串，16 位读只发生在 RAM 对象和字体表 | 反汇编 `0x0806626C..0x08066500` | — |
| F8 | **串池与剧本搬迁不抢 `0x5DFBEC`**：`allocate()` 只找 `0xFF` 段，池写进去后不再是 `0xFF` | 读 `rom-editor/js/rom.js` | `node rom-editor/tools/verify_free_space.mjs`（16 条断言全过） |
| F9 | **补丁末尾的 `0xBF00` 是唯一的病灶**：只把这 14 个字节换成 `0x46C0`（`mov r8,r8`），别的什么都不动 ⇒ 卡死变能跑 | A/B 对照 | `python tools/mgba_probe/speaker_freeze_trace.py --fix-nop`（§4.1） |
| F10 | **14 处补丁全部以 `0xBF00` 结尾** ⇒ 每一个被补丁过的取名读者，**只要被执行到就会立刻炸** | 逐处反汇编 `tools/data/speaker_name_code_patches.json` | `notes/evidence/speaker-name-freeze-trace-20261023.md` §0 / §3.3 |
| F11 | **14 处补丁的两版读的是同一个字面量槽**（`0x08097A40` = `0x085A57C4`）；id 都是同一条 `ldrb` 取出的字节 | 逐处字节与语义核对 | 同上 §3 |
| F12 | **标志位语义不受影响**：原序列末条 `adds rX,rX,rY`（写标志）与新序列末条 `ldr`（不写标志）之间，参与 `adds` 的量只差 `id*12` vs `id*4`，和都是 `0x085A57C4 + 小数` ⇒ N/Z/C/V 取值相同 | 理论核对 | 同上 §4.2 |

> ⚠️ **复核命令的口径提示**（2026-10-23 独立验收复查时实测，别照着旧命令跑出红就以为清单坏了）：
> - **`node rom-editor/tools/verify_speaker_conversion.mjs` = 当前权威门禁**，**42 条断言**、exit=0。
>   它只查 `new_disasm` 的**末条**（必须是 `mov r8, r8`、且不再是 `nop`）与 `after_hex` 的末 2 字节
>   —— **不读**解引用那一行的文本。
> - **`node tools/probe_speaker_code_patches.mjs`（旧的逐处探针）目前是红的**（检查项 231 / 失败 42）。
>   原因**不是清单写错**，而是**这个探针自己还停在第十八/十九轮修正之前**：
>   ① 它要求补丁末尾是 `0xBF00`（`isNop()`），而 `0xBF00` 早已**禁用**（现行 = `0x46C0`）；
>   ② 它的「含且仅含一条解引用 `ldr rD,[rD]`」按**寄存器偏移**位域解码（`0x58xx`），
>      而正确写法是**立即数偏移**（`0x68xx`，imm5=0）⇒ 永远对不上；
>   ③ 它按 capstone 原样文本比对 `new_disasm`，而本清单写的是**语义等价**的 `ldr rX, [rX, #0]`
>      （本机 Capstone 5.0.7 印成 `ldr rX, [rX]`）。
>   ⇒ **要修的是探针，不是清单**；修探针不在本轮范围内。

### 1.2 工具链与门禁（本轮收口状态）

| # | 事实 | 怎么验的 | 复核命令 |
|---|---|---|---|
| F13 | **21 道门禁全绿**（`rom-editor/tools/verify_*.mjs` 全部 exit=0） | 本轮重跑全部 21 个脚本 | `Get-ChildItem rom-editor/tools -Filter verify_*.mjs` → 逐个 `node` |
| F14 | `verify_views` / `verify_pack` / `verify_load_flow` 三道门禁里**过期的断言已改写**成对当前正确行为的断言；其中一条被改弱、一条是**空转断言**，已修正 | 独立验收复查 | 同上 |
| F15 | **`rom-editor/js/parsepack.js` 的一个真 bug 已修**：解析**原版** ROM 时 `speaker_names` 的 `capacity` 被读成「名字长度+1」（5/7/3/9）而不是真实的 **12**（定长内联槽）—— 原因是 `fixedSlot` 判定没有覆盖「未转换的可转换表」；修后 `capacity` 全是 12、`raw` 全 12 字节、往返重建仍与原版逐字节相同 | 往返重建对拍 | `node rom-editor/tools/verify_pack.mjs` |
| F16 | 门禁新增 `report.textsRead`（每张表**实际从 ROM 读到几条记录**）作为「形态判对没」的判据 | 读 `rom-editor/js/parsepack.js` | 同上 |
| F17 | **产品侧已落地**：清单 `tools/data/speaker_name_code_patches.json` 的 14 处 `after_hex` 末 2 字节已是 `c046`、`new_disasm` 末条已是 `mov r8, r8`，并新增 `conventions.filler`（固定用 `0x46C0`、**禁用 `0xBF00`**）；内容包 `pack.json` / `pack.min.json.gz` 由 `tools/export_content_pack.py` 从清单**重新导出**（清单是唯一真相源）；门禁 `verify_speaker_conversion.mjs` 新增断言（禁用 `0xBF00` / 必须是 `0x46C0` / 清单与内容包逐字节同步）；真机验收脚本 `tools/mgba_probe/speaker_acceptance.py` 已建 | 读产品数据 + 跑门禁 | `notes/evidence/speaker-name-fix-20261023.md`（**该笔记 §3–§5 仍在补**）；`node rom-editor/tools/verify_speaker_conversion.mjs` |
| **F18** | **真机验收 §A5「读者覆盖」的实测结果：当前按键路线只覆盖 1/14 处读者**（**仅 `vm_0x08`**）；其余 **13 处**属**战斗消息 / 命令消息 / 战斗日志**场景，当前按键路线**到不了**。⇒ 这是**未闭合的覆盖缺口**，**不影响「修复正确」的结论**（修复本身已由 42 条静态断言 + A/B 实测证明有效）。另注：`tools/mgba_probe/speaker_acceptance.py` 在验收期间被**并行修改**过（新增了 A5 读者覆盖）；验收者跑的第 **3** 次（**最新版**）**exit=0** | 真机验收脚本 §A5 的逐处命中统计 | `python tools/mgba_probe/speaker_acceptance.py`（A5 节）；`notes/evidence/speaker-name-fix-20261023.md` |

---

## 2. 已证伪（**不要再往这些方向查**）

### 2.1 老表（上一轮之前就证伪的）

| # | 曾经的假设 | 为什么是假的 | 证据 |
|---|---|---|---|
| H1 | 「指针表 `0x5A57C4..0x5A58C3` 盖住了头像表 `portrait_table` 的最后一条 ⇒ 0x08 处理器读到坏指针」 | **本轮再次实测证伪**：把头像 id 63 整条记录（40 字节）改回原版内容，**冻结点一点没变**（`(5,5)` 仍是 `(5,5)`）。而且原版 ROM 里那 40 字节本就是名字表的字形码（`92 59 9a 9a 00 …`），**原版里它已经是死区** | `notes/evidence/speaker-name-patch-bisect-20261023.md` §4.7；`docs/handoff-20261023-speaker-names-conversion.md` §3.4 |
| H2 | 「补丁里的解引用写错了（`ldr r0,[r0,0]` 算的是 `2×r0`）」 | 已修：改成立即数偏移 `ldr r0,[r0,#0]`（Thumb-1 `LDR (imm)` T1，imm5=0） | `tools/data/speaker_name_code_patches.json` 的「第十八轮更正」；F2；`notes/evidence/speaker-name-align-experiment-20261023.md` §5.6 |
| H3 | 「字形码 lead/trail 字节序错了」 | 已修。抽查池里 `鸣人测试` = `92 98 94 c8 89 df 95 d1` ✅ | `tools/fix_speaker_deref.py`；`tools/probe_speaker_deref_encoding.py` |
| H4 | 「名字串池的起始地址没有 2 字节对齐」 | 见 F7；另见 H7 | — |
| H5 | 「文本串池和剧本搬迁抢同一段空闲区」 | 见 F8 | — |

### 2.2 本轮新增证伪（这一轮走掉的支线，全部封死）

| # | 曾经的假设 | 为什么是假的（关键数字） | 证据 |
|---|---|---|---|
| **H6** | 「**指针表占用了旧名字表那片地址** ⇒ 病灶」 | 把它从 `0x085A57C4` 搬到空闲区 `0x085B56E0`（12 处字面量同步改、14 处补丁全开）⇒ **V1 仍卡**，且 16 张截图与「原地放」的基线**逐帧完全相同**（同一冻结哈希 `fa4fd7206ccc`）；自检证明 V1 里旧内联表那 256 字节**逐字节没被动过** | `notes/evidence/speaker-name-relocation-experiment-20261023.md` §0 / §3.2 / §4 |
| **H7** | 「**串池没对齐**」 | P1 补齐到 2 字节对齐（奇地址 **0/64**）、P2 补齐到 4 字节对齐（奇地址 **0/64**、非 4 字节对齐 **0/64**）⇒ 两个变体**都卡在同一帧、同一哈希** `fa4fd7206ccc` | `notes/evidence/speaker-name-align-experiment-20261023.md` §2（P1/P2） |
| **H8** | 「**名字太长 / 名字框放不下 / 名字内容**」 | 3/4/6 字变体冻结点完全一样；**P3 把指针指回原版内联槽、名字一个字节都没动、串池完全不写** ⇒ 仍卡在同一帧；**P4 名字确实改长、仍住原位** ⇒ 仍卡在同一帧 | `notes/evidence/speaker-name-patch-bisect-20261023.md` §4.4；`notes/evidence/speaker-name-align-experiment-20261023.md` §2（P3/P4） |
| **H9** | 「**存在第 13 个没被识别出来的读者**」（U1） | 全 ROM 穷举：29 871 个字面量站点里**恰好 12 个**是 `0x085A57C4`；原始 u32 **恰好 12 次**；ARM 模式 `ldr [pc,#±imm]` 437 条**0 命中**；`×12` 步长序列 93 处里**恰好 14 处**以该基址为基址 = 14 处补丁一一对应；污点分析窄窗口 38 条路径 / 26 站点全在补丁内，宽窗口 0 新增 ⇒ **多出来的读者为 0** | `notes/evidence/speaker-name-read-paths-20261023.md` §0 / §2 |
| **H10** | 「**12 个字面量槽被别的代码共用**」 | 每个槽**恰好 1 条**引用、就是它自己的读者；全 ROM `u32 == 0x085A57C4` **恰好 12 次**（就是那 12 个池单元）；`0x08097A40` 所在区域除了这一个字面量**没有跳转表、没有别的常量表** | `notes/evidence/speaker-name-freeze-trace-20261023.md` §3.5；`notes/evidence/speaker-name-relocation-experiment-20261023.md` §5.1 |
| **H11** | 「**id 63 的全名 / 简称语义冲突**」（U4） | 剧情 VM **从未用过 id 63**：`op 0x08` 用过的 49 个 id 全在 `1..61`，`op 0x0E` 只用 `{1,2,3,25,26}`；三处「没有」是作者**刻意的存储别名** | `notes/evidence/speaker-name-id63-20261023.md` §2 / §5 |
| **H12** | 「**串池起始地址是奇数 ⇒ 16 位读被 GBA 旋转**」 | 渲染器 `0x0806626C`、名字长度函数 `0x08067110`、游戏自己的 strlen `0x0809C528` **全部按字节扫**，strlen 还有不对齐的字节回退路径 `0x0809C560` ⇒ 单字节 `0x00` 终止符不会漏判 | `notes/evidence/speaker-name-relocation-experiment-20261023.md` §6.3；`notes/evidence/speaker-name-align-experiment-20261023.md` §5.6 |
| **H13** | 「**串池用单个 `0x00` 终止符**（内联槽是 `0x00` + 填充）有问题」 | 同上：三个消费者都遇 `0x00` 就停 ⇒ 无害 | 同上 |
| **H14** | 「**14 处补丁里有某一处单独就坏**」（U5） | 单独开 / 单独去掉**都没有可观测差别**；只有 #13（`vm_0x08`）看起来有影响，是因为**它跑得最早**（见 §3 U5） | `notes/evidence/speaker-name-patch-bisect-20261023.md` §3 |
| **H15** | 「**改 12 处字面量会改坏别的代码路径**」 | 每个字面量**只被 1 条指令**读；全 ROM 只有这 12 个 `u32`；V2（搬家 + 字面量不动 + 0 处补丁）**能跑**且与原版逐帧相同 ⇒ 改字面量本身无害 | `notes/evidence/speaker-name-align-experiment-20261023.md` §4；`notes/evidence/speaker-name-relocation-experiment-20261023.md` §3.2b |

---

## 3. 未验 → **本轮已判定（U1–U5）**

> 每条都写好了「判定动作」和「判据」。**做完一条立刻填结果。**
> **一次只做一条**，做完再开下一条。

| # | 假设 | 判定动作（一次得出是/否） | 结果 | 状态 |
|---|---|---|---|---|
| **U1** | 存在第 13 个没被识别出来的读者：某个代码路径还在按 `基址 + id*12` 读名字 | 扫描全 ROM，找出所有**读得到 `0x085A57C4` 区域**的代码路径（含**不用该字面量**、从别的基址算出来的），产出一张「读名路径」清单，与 14 处补丁逐一对照 | 清单里每一条路径都能对应到 14 处补丁之一：字面量 **12/12**、原始 u32 **12/12**、`×12` 步长 **14/14**、污点分析窄窗口 38 条路径 / 26 站点全在补丁内、宽窗口 **0 条新增** ⇒ **多出来的读者 = 0**。证据：`notes/evidence/speaker-name-read-paths-20261023.md` §0/§2（探针 `tools/probe_speaker_read_paths.py`） | **已证伪** |
| **U2** | 某个读者的 id **不是「一个字节」**，或那个 `ldrb` 在补丁窗口之前**不一定执行到** | 对 14 处补丁逐处，把「取 id 的那条 `ldrb`」到「补丁窗口」之间的指令列出来，看有没有分支能跳过它 | 14 处逐条核对通过：id 都是**同一条路径上取到的字节**，两版读的是**同一个字面量槽**（`0x08097A40` = `0x085A57C4`）。证据：`notes/evidence/speaker-name-freeze-trace-20261023.md` §3（配合 F11） | **已证伪** |
| **U3** | 补丁的**语义**在某处不同（原代码在别处还有别的用法，补丁后含义变了） | 对 14 处补丁逐处，把 **OLD 与 NEW 的完整上下文**（前后各 8 条指令）对照着读 | 逐处语义核对通过；渲染器逐字节读字符串，把指针与内联槽地址**当同一种东西**（字符地址）用 ⇒ 补丁语义对；标志位语义也核对过（F12）。证据：`notes/evidence/speaker-name-freeze-trace-20261023.md` §3.1 / §4.2 | **已证伪** |
| **U4** | 转换后 **id 63 的语义**变了：原版 id 63 落在全名表第 0 条（「没有」），游戏某处可能用 id 63 的**全名**（19 字节步长） | 查剧情脚本里 `op 0x08` / `op 0x0E` 的操作数字节实际取过哪些值；再查全名表的 3 个读者读到的语义 | `op 0x08` 用过 **49** 个 id，**全在 1..61**；`op 0x0E` 只用 **{1,2,3,25,26}**；两路独立数据源（ROM 全量走查 5748 站点 / 内容包 202 条剧本 6999 站点）**id 集合逐位相同**；全名表 3 个读者步长 **19**（符号求值器机器验证）；区域内部第 4 处引用步长 **18** = 地点名表。证据：`notes/evidence/speaker-name-id63-20261023.md` §2/§3/§5 | **已证伪** |
| **U5** | **补丁级二分**：14 处补丁里有某一处（或某几处组合）单独开就坏 | 用 `tools/mgba_probe/speaker_bisect.py` 逐处开关，每次跑一次，记录「能跑 / 卡住」 | 产出 14 行表：**单独开 #13 ≡ 全部 14 处一起开**（冻结第 6 步）；**全开去掉 #13 ≡ 一处都不开**（冻结第 8 步）；**其余 13 处单独开 / 去掉都没有可观测差别**。⇒ 「14 处补丁里有某一处单独就坏」这个假设**不成立**（不是「查不出来」，是**测出来没有差别**）。证据：`notes/evidence/speaker-name-patch-bisect-20261023.md` §3（表）、§4.3（等长改名 + 全 14 处 ⇒ 能跑） | **已证伪**（假设不成立） |

---

## 4. 这一轮的最终结论（根因）

### 4.1 根因一句话

> **14 处代码补丁末尾的填充字节用了 `0xBF00`（Thumb NOP 编码）；
> `0xBF00` 在 ARMv4T（GBA 的 ARM7TDMI）上是未定义指令 ⇒ 未定义指令异常 ⇒ 死循环。**

### 4.2 机制（逐环节都有实测）

1. 补丁把「取名字」的那段代码**等长替换**成「取指针再解引用」，末尾留了 2 字节填充。
2. 填充字节 = `0xBF00`。`NOP/YIELD/WFE/WFI/SEV` 这些 hint 指令是 **ARMv5T 才有的**；
   ARMv4T 的 Thumb 状态里 `0xBFxx` **本身就是未定义指令**。
3. 执行到它 ⇒ 抛 **Undefined Instruction 异常**：
   - 冻结现场 `CPSR = 0x0000009B` ⇒ **T=0（ARM 状态）、mode=0x1B（Undefined）、I=1**；
   - `LR = 0x08097A16` = **出错指令地址 `0x08097A14` + 2**（Thumb 未定义指令异常的返回地址规则）；
   - `sp = 0` 是**异常模式下的 banked SP（SP_und）**，不是游戏把栈写坏了（用户栈一直是 `0x030011F8`）。
4. 进 BIOS 异常向量 ⇒ BIOS 异常处理程序**回到出错的指令** ⇒ 同一条指令再次出错 ⇒ **无限异常循环**：
   ```
   0x00000008   BIOS 未定义指令向量（ARM, mode=0x1B）
   0x000001A8   BIOS 异常返回
   0x08097A14   op 0x08 handler 里的 0xBF00   ← 出错点
   0x08097A16   adds r0, r6, #0
   → 0x00000008（再次异常）→ 无限循环
   ```
   - 400 步单步的 PC 直方图：`0x000001A8` ×150、`0x08097A14` ×150、`0x08097A16` ×150、`0x00000008` ×150（**均匀循环**）；
   - mGBA 自己就打出来了：**`Hit illegal opcode at 0x08097A14: 0x0000BF00`**（死循环里一次 `frames` 刷 **195 827 行**），
     它自己的反汇编器在 `0x08097A14` 打的是 **`BF00: ill`**；
   - 冻结后每按一次 A 要 **18 秒**（宿主 `host_main.c` 的 2M 步上限）。
5. ⇒ 画面不再推进 ⇒ 表现成「卡死」。

### 4.3 修法

- 把 14 处补丁 `after_hex` 的**最后 2 字节**（`00 bf`）换成 **`c0 46`（`0x46C0` = `mov r8,r8`）**：
  - ARMv4T **合法**的 Thumb 高寄存器 MOV（capstone 与 mGBA 都解成 `mov r8,r8`）；
  - **不写任何标志位**（补丁后本来就没有写标志的指令）；
  - **不改变任何寄存器的值**（r8 写回自己）；
  - **长度不变（2 字节）** ⇒ 不用挪动任何后续代码，12 处字面量地址也不用动。
- **适用范围**：14 处**全部**要改，不能只改 #12/#13 —— 其余 13 处只要被执行到就会同样炸。
- 备选填充：`0x0000`（`movs r0,r0`，**会写标志**）、`0x46C0`（**推荐**）、`0xBF00`（**禁用**）。

### 4.4 A/B 证据（`notes/evidence/speaker-name-freeze-trace-20261023.md` §4.0 / §4.1）

| ROM | 判定 | 画面变化步数 | 冻结步 | 逐次画面哈希 |
|---|---|---|---|---|
| `build/sp-bisect-all.gba`（14 处补丁原样） | **卡死** | 6 | 6 | `9e1ea29042ea e6bdfce77108 62638d1b3442 d4b626347dd1` 之后 **恒为** `fa4fd7206ccc` |
| `build/trace_fixnop.gba`（**只**把 14 个 `00bf` 换成 `c046`） | **能跑** | **13** | **None** | 13 步**每次都变**（`206d8e494058 f3ec126bc855 221c83534c4f … dd7396561d17`） |

（工具输出：`build/trace_fixnop_report.json` / `.md`；
`sp-bisect-all.gba: 卡死 变化 6 步 冻结 6` / `trace_fixnop.gba: 能跑 变化 13 步 冻结 None`）

⇒ **只改这 14 个字节就能治好** ⇒ 指针表布局、串池、12 个字面量、渲染器语义**都不是病灶**。

> ✅ **产品侧已落地**（另一条支线，见 `notes/evidence/speaker-name-fix-20261023.md`：
> 清单 14 处 `after_hex` 末 2 字节 = `c046`、内容包由 `tools/export_content_pack.py`
> 从清单重新导出、门禁新增「禁用 `0xBF00` / 必须是 `0x46C0`」断言、
> 真机验收脚本 `tools/mgba_probe/speaker_acceptance.py` 已建）。
> 本表只记录「修法已定位并实测有效（A/B 证据见 freeze-trace 报告 §4.1）」。

---

## 5. 被推翻的前提（**下一轮不要再拿它们当前提**）

| # | 曾经的前提 | 实测反证 | 证据 |
|---|---|---|---|
| **P1** | 「`0x08097A1C` 永远不命中 ⇒ **渲染器拿着坏指针进了循环**」 | 这是 **mGBA 调试器假象**：断点是**软件断点**（把指令原地改成 `BE00: bkpt`），命中后会把那条指令**再执行一遍**。**原版 ROM 上同样不命中**（同一个断点，原版命中 1 次、同时多挂一个断点就连原版都不命中）。而且在转换版里，**「名字渲染」那一次调用根本没有发生**（不是坏指针，是没调用） | `notes/evidence/speaker-name-patch-bisect-20261023.md` §1.1 / §4.6；`notes/evidence/speaker-name-freeze-trace-20261023.md` §3.1 |
| **P2** | 「**指针表占用了旧名字表那片地址** ⇒ 病灶」 | 搬到空闲区 `0x085B56E0` 后**逐帧完全相同**地卡（同一冻结哈希 `fa4fd7206ccc`） | `notes/evidence/speaker-name-relocation-experiment-20261023.md` §0 / §4 |
| **P3** | 「**串池没对齐 / 名字太长 / 名字内容有问题**」 | 2 字节对齐（奇地址 0/64）、4 字节对齐（0/64）、名字一字节不动（指回原位内联槽）、名字确实改长 —— **全都卡在同一帧、同一哈希** | `notes/evidence/speaker-name-align-experiment-20261023.md` §2 / §4 |

> **可靠判据只有一个：画面还推不推进。**
> 断点命中与否**不能**当判据（mGBA 软件断点会重执行指令，还会破坏栈）。

---

## 6. 新事实（这一轮查出来的）

| # | 事实 | 关键数字 | 证据 |
|---|---|---|---|
| **N1** | **`0x085A5F65` 起是第三张表 —— 地点名表**（地图地名），**步长 18 字节/条**、**55 条（id 0..54）**、范围 `0x085A5F65..0x085A6342`；它的 id 0「没有」与说话人全名表 id 63 **同址** | 步长 18（符号求值器验证）；读者 `0x0808CD8E` | `notes/evidence/speaker-name-id63-20261023.md` §3.5 / N1 |
| **N1b** | ⇒ 项目里的「保护区 `0x085A5AB8..0x085A5F78`」**只覆盖了全名表**（`0x085A5AB8..0x085A5F77` = 64 × 19 = 1216 字节），**地点名表的 id 1..54 在保护区之外** | 全名表 64 条、地点名表 55 条 | 同上 §1.3 / §4 |
| **N2** | **地点名表与说话人全名表都还没登记进 `tools/table_registry.py` 和内容包**（`table_registry.py` 里 `0x5A5AB8` / `0x5A5F65` 都不存在；内容包 116 张结构表里也没有步长 18 / 19 的表） ⇒ **内容包缺口** | — | 同上 §5 的 N2 |
| **N3** | **`speaker_names` 在原版里其实只有 63 个槽（id 0..62）**；id 63 那一格**没有自己的字节**，它借用了全名表第 0 条的存储 ⇒ 这是作者**刻意的存储别名**，不是 bug | 简称表 63 条 + 全名表 64 条 + 地点名表 55 条；三条「没有」共用同一批字节 `92 59 9a 9a 00` | 同上 §1.1 / §5 的 N1 |
| **N4** | **三张表在 ROM 里的落点与读者**（完整版）：简称表 `0x085A57C4`（步长 12，**12 个读者**）/ 全名表 `0x085A5AB8`（步长 19，**3 个读者**）/ 地点名表 `0x085A5F65`（步长 18，**1 个读者**）⇒ 全 ROM **只有 16 处** pc 相对字面量落在这片区域 | 12 + 3 + 1 = 16，没有第 17 处 | 同上 §3.5 / §4 |
| **N5** | **补 `0x46C0` 之后仍待验的三件事**：① 13 处读者在**战斗消息 / 命令消息 / 战斗日志**场景里被执行到（这一轮只跑到剧情开场的 `op 0x08`）；② 名字本身**画得对不对**（只验了「不再卡死」，没逐像素比对「鸣人测试」是否正确画在名字框里）；③ 14 处补丁的标志位语义**未逐处实测** | — | `notes/evidence/speaker-name-freeze-trace-20261023.md` §4.3 / §8 |
| **N6** | **产品侧落地的位置**（谁改了、怎么改的）：`tools/data/speaker_name_code_patches.json` = **唯一真相源**；内容包由 `python tools/export_content_pack.py --no-rom --no-text-index` 重新导出（不是手改）；`rom-editor/js/rom.js` **不用改**（填充指令来自内容包，目录里 grep `bf00` 零命中） | 213,678 行里只有 **14 行**不同，全是 `after_hex` 那一行 | `notes/evidence/speaker-name-fix-20261023.md` §2 |

---

## 7. 怎么用这张表

1. **一行一个假设。** 每行 = 假设 / 判定动作 / 判据 / 结果 / 状态。
   判定动作写完就必须**一次能得出是/否**。
2. **状态只有三种**：`未验` / `已证伪` / `已确认`。
   - `已确认` = 事实（可以当前提用，附复核命令）；
   - `已证伪` = **不要再往这个方向查**（附反证的关键数字）；
   - `未验` = 还没做。
3. **判定动作的输出要是「能跑的」**：一个 pass/fail、一个数字、一个 diff 像素数、一个哈希。
   「日志里没看出异常」**不算**判定结果。
4. **做完一条立刻回填本表**，别攒到最后。
5. **连续 3 次同样的结果 ⇒ 停。** 把「这条路走不通」写进这张表，换方法。
6. **每做完一条，把结论也写回 `docs/sequel-roadmap.md`**（AGENTS.md 第 6 条）。
7. 自检：`python tools/loop_guard.py <会话的 messages.jsonl>` ——
   命中就说明你又在同一处打转了。
8. **⚠️ 假设被推翻时，除了填「状态」，还要把它挪进 §2「已证伪」表并写清关键数字** ——
   不然下一个会话还会拿它当前提（这一轮就发生过：`0x08097A1C` 那个断点判据白查了两轮）。

---

## 8. 纪律（照着做就不会再陷进去）

1. **一次只开一条假设。** 做完填表，再开下一条。
2. **判定动作的输出要是「能跑的」**—— 一个 pass/fail、一个数字、一个 diff 像素数。
   「日志里没看出异常」不算判定结果。
3. **连续 3 次同样的结果 ⇒ 停。** 把「这条路走不通」写进这张表，换方向。
4. **每做完一条，把结论写回这张表 + `docs/sequel-roadmap.md`。**
5. 自检：`python tools/loop_guard.py <会话的 messages.jsonl>` ——
   命中就说明你又在同一处打转了。

---

## 9. 相关文件

| 文件 | 作用 |
|---|---|
| `notes/evidence/speaker-name-round-summary-20261023.md` | **本轮总览**（要什么 → 做了什么 → 结论 → 证据在哪）—— 先读这篇 |
| `docs/handoff-20261023-speaker-names-conversion.md` | 整轮工作的交接（4 条要求 / 未提交资产 / 基线 / 下一步） |
| `notes/evidence/session-loop-analysis-20261023.md` | 两个会话陷进循环的成因与教训 |
| `notes/evidence/speaker-name-table-20261023.md` | 12 个原生读者的考证 |
| `notes/evidence/speaker-name-code-patches-20261023.md` | 14 处补丁清单与逐处核对 |
| `notes/evidence/speaker-name-patch-bisect-20261023.md` | **补丁级二分（14 行表）** —— U5 |
| `notes/evidence/speaker-name-relocation-experiment-20261023.md` | **指针表搬家实验（V0..V4）** |
| `notes/evidence/speaker-name-align-experiment-20261023.md` | **串池对齐 / 指针指向实验（P0..P4）** |
| `notes/evidence/speaker-name-freeze-trace-20261023.md` | **逐指令定位（根因在这里）** —— §4.1 是 A/B 证据 |
| `notes/evidence/speaker-name-read-paths-20261023.md` | **全 ROM 读名路径普查** —— U1 |
| `notes/evidence/speaker-name-id63-20261023.md` | **id 63 语义考证（兼 N1/N2/N3）** —— U4 |
| `notes/evidence/speaker-name-fix-20261023.md` | **产品侧落地 + 门禁 + 真机验收脚本**（§3–§5 仍在补） |
| `tools/data/speaker_name_code_patches.json` | 补丁清单（机器可读） |
| `tools/mgba_probe/speaker_bisect.py` | 补丁级二分（U5） |
| `tools/mgba_probe/speaker_relocate_probe.py` | 指针表搬家实验 |
| `tools/mgba_probe/speaker_align_probe.py` | 串池对齐 / 读者二分实验 |
| `tools/mgba_probe/speaker_freeze_trace.py` | 逐指令定位 + `--fix-nop` A/B |
| `tools/probe_speaker_read_paths.py` | 读名路径穷举（U1） |
| `tools/probe_speaker_id63.py` | id 63 语义考证（U4） |
| `tools/probe_speaker_code_patches.mjs` | 补丁逐处反汇编核对 |
| `tools/loop_guard.py` | 死循环自检 |
