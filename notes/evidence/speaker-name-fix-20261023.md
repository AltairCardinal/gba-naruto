# 说话人名表转换卡死：把根因修进产品 + 补真机验收门禁（2026-10-23）

> 承接 `notes/evidence/speaker-name-freeze-trace-20261023.md`（根因已定位、已实测验证）。
> 本轮把那个根因**修进产品数据**，并补上**真机验收门禁**。
> 本文件是**增量写**的：每查完一条就写一条。

---

## 0. 一句话结论

**根因（14 处补丁末尾的填充字节 `0xBF00`）已修进产品数据并被真机验证**：
清单、内容包、内容包压缩包三处都换成了 `0x46C0`（`mov r8, r8`）；
静态门禁加了 2 类新断言（填充指令白名单 + 清单/内容包逐字节同步，共 42 条断言全绿）；
真机验收 `tools/mgba_probe/speaker_acceptance.py` 实测**原版能跑 + 转换版能跑**（退出码 0），
且**变异测试证明它有牙齿**（把 14 处改回 `00bf` ⇒ 判成「卡死」，画面哈希与上一轮记录逐位相同）。

**本轮（2026-10-23 晚）追加两条**：

1. **「名字画对了」这条补上了** —— 逐像素核对（`tools/mgba_probe/speaker_namebox_check.py`，
   退出码 0）：名字框 = `x[24,55] × y[105,119]`，原版名字那块 `x[24,39] × y[105,119]`
   **逐字节没变** ⇒ 「鸣人」是**原样保留**、「测试」是**追加**上去的；
   196 个差分像素**全部**落在名字框内，**框外差分 0**，**对话正文逐字节相同**。
   详见 §5(e) 与 `notes/evidence/speaker-name-namebox-verification-20261023.md`。
2. **其余 13 处读者的覆盖仍然是缺口** —— 验收脚本新增 §A5 逐处扫描：
   14 处里**只有 `vm_0x08`（读者 12）**被剧情路线走到；
   战斗场景**进得去**但产不出带说话人的消息 ⇒ **未覆盖 + 原因**如实记在 §5(f)。
3. **（2026-10-23 夜·第二轮）一个过期探针修好了** ——
   `tools/probe_speaker_code_patches.mjs`（仓库自带的**代码补丁字节级探针**）
   还停在 `0xBF00` 时代：跑出来是**红的**（检查项 231 / 失败 42 = 14 处 × 3 条）。
   本轮把它改成与现行约定一致：填充指令**从清单 `conventions.filler` 推导**、
   解引用按**立即数偏移**（`0x68xx`）识别并**明确判错**寄存器偏移写法、
   `new_disasm` 改**按语义**比对（不再逐字比对 capstone 打印格式）、
   并**新增**「末尾不得是 `0xBF00`」的断言。
   现在 **261 项检查 / 0 条失败**，且**三组变异都能把它打红**（见 §3.2 / §5(g)）。

---

## 1. 根因回顾（不用重推）

- `0xBF00`（Thumb `nop` 的编码）在 **ARMv4T（GBA 的 ARM7TDMI）上本身就是未定义指令** ——
  `NOP/YIELD/WFE/WFI/SEV` 这些 hint 指令是 ARMv5T 才有的（mGBA 自己的反汇编器在那一格
  打出来的是 `BF00: ill`）。
- 执行到 ⇒ 抛 Undefined Instruction ⇒ 进 BIOS 异常向量 `0x00000008` ⇒
  异常返回按 Thumb 地址的**偶数**回跳 ⇒ **CPU 切进 ARM 状态** ⇒
  再执行 `0xBF000000` ⇒ 又是未定义指令 ⇒ **无限异常循环** ⇒ 画面永远不再推进。
- 上一轮实测：只把 14 个 `0xBF00` 换成 `0x46C0`，转换版从「卡死」变成「能跑」。
- 依据：`notes/evidence/speaker-name-freeze-trace-20261023.md` §0 / §3.2 / §4.0 / §4.1。

> ⚠️ **措辞更正**：任务书里写的是「`0xBF00` 在 **ARM 状态**下不是 NOP」。
> 仓库自己的证据（§3.2）更准确：**ARMv4T 的 Thumb 状态下 `0xBFxx` 就已经是非法指令**；
> 「切进 ARM 状态」是**异常入口之后**才发生的事。
> 本轮落进产品数据的说明一律按证据的措辞写。

---

## 2. 改了什么（产品数据）

### 2.1 `tools/data/speaker_name_code_patches.json`（**唯一真相源**）

- 14 处 `after_hex` 的**末尾 2 字节**：`00bf` → `c046`
  （`0xBF00` → `0x46C0` = Thumb `mov r8, r8`）。
- 14 处 `new_disasm` 的**最后一条**：`nop` → `mov r8, r8`。
- 14 处 `note` 末尾追加了**这个坑的完整解释**（为什么不能用 `0xBF00`、为什么 `0x46C0` 安全）。
- 新增 `conventions.filler`：把「填充指令固定用 `0x46C0`」写成约定，并禁用 `0xBF00`。
- `summary` 追加一句提醒。

**为什么 `0x46C0` 安全**：ARMv4T 合法的 Thumb 高寄存器 MOV；**不写任何标志位**；
**不改变任何寄存器**（r8 写回自己）；**仍是 2 字节** ⇒ 不挪动任何后续代码，
字面量地址（`0x08079108` 等 12 个）也不用动。

### 2.2 `rom-editor/content/pack.json` + `rom-editor/content/pack.min.json.gz`

- `conversions.speaker_names.code_patches[]` 的 14 条 `after_hex` 同样换成 `c046`。
- **不是手改的**：用仓库自带的生成脚本重新导出 ——
  `python tools/export_content_pack.py --no-rom --no-text-index`
  （`tools/export_content_pack.py::build_conversions()` 就是从
  `tools/data/speaker_name_code_patches.json` 读这 14 条补丁 ⇒ **清单是唯一真相源**）。
- `pack.min.json.gz` 由同一个脚本用**确定性 gzip**（`mtime=0`）写出 ⇒ 可复现。
- 核对：`pack.min.json.gz` 解压后的 JSON **与 `pack.json` 完全相等**（`m == p` 为 True）。

**逐行核对（`build/diff_pack_before_after.py`）**：用「修正前的 manifest」重新导一份
`build/pack-old.json`，与当前 `pack.json` 逐行 diff ⇒
**213,678 行里只有 14 行不同**，且全是 `after_hex` 那一行。

### 2.3 `rom-editor/js/**`（**不需要改**）

上一轮笔记建议「检查 `rom.js::applyInlineToPointer()` 里有没有把填充指令写死成 `0xBF00`」。
实测：`rom-editor/js/rom.js:361` 是 `const after = hexToBytes(patch.after_hex || '')` ——
**填充指令来自内容包，不写死**；全目录 grep `bf00` **零命中**。
⇒ 产品逻辑不用动（与本轮任务书的「不要碰 `rom-editor/js/**`」一致）。

---

## 3. 门禁（静态侧）：`rom-editor/tools/verify_speaker_conversion.mjs`

新增两节（文件头注释里也补了 S6 / S7 的说明）：

**§10 补丁末尾的填充指令**
- `after_hex` 末尾**不得是 `00bf`**（`0xBF00`）—— 理由写在断言旁边的注释里；
- 末尾**必须**是 `c046`（`0x46C0` = `mov r8, r8`）；
- 换掉填充之后**补丁长度仍然不变**（长度不变 ⇒ 不挪动后续代码）；
- `new_disasm` 的**最后一条不得是 `nop`**；
- `new_disasm` 末条与填充字节**对得上**（`c046` ⇔ `mov r8, r8`）；
- **转换后 ROM 里真正落地的字节**也不得是 `00bf`、且必须是 `c046`（清单对了、内容包错了也要红）。

**§11 清单与内容包同步（防漂移）**
- 内容包里也必须**有 14 处**补丁；
- 逐条比 `offset` / `before_hex` / `after_hex` —— **逐字节一致**；
- 内容包那 14 条**自己**也不得带 `0xBF00`。

断言数：**42 条**（改前 29 条）。

### 3.1 实测（本轮复测，2026-10-23 晚，命令 + 真实退出码）

**对照组**（挂了 loader hook 但**不**替换文件）⇒ **全部通过（42 条断言）**，退出码 **0**
⇒ 证明 hook 本身没有把门禁弄坏：

```powershell
node --import ./build/mutation/register.mjs rom-editor/tools/verify_speaker_conversion.mjs
# 末行： 全部通过（42 条断言）        退出码 0
```

**变异组**（把**清单**的 14 处末尾改回 `00bf` + `nop`，**清单源文件零改动**）⇒
**5 项失败**，退出码 **1**：

```powershell
python build\mutation\make_mutated_manifest.py
#   wrote build/mutation/manifest-with-bf00.json (14 patches mutated back to 00bf / nop)
$env:MUTATION_MANIFEST = (Resolve-Path 'build\mutation\manifest-with-bf00.json').Path
node --import ./build/mutation/register.mjs rom-editor/tools/verify_speaker_conversion.mjs
# 末行： 5 项失败                      退出码 1
```

本轮实测变红的**具体那 5 条**（原样摘录）：

| # | 失败的断言 | 摘录 |
|---|---|---|
| 1 | 全部 14 处补丁逐字节落地 | `battle_msg_name @0x79086、cmd_msg_name @0x811CC、cmd_msg_name_copy @0x81238、battle_log_name @0x86042…` |
| 2 | 14 处补丁末尾都没有 0xBF00（ARMv4T 未定义指令 ⇒ 异常死循环 ⇒ 卡死） | `battle_msg_name=00bf、cmd_msg_name=00bf、…、vm_0x0E_second_name=00bf`（14 处全中） |
| 3 | 14 处补丁末尾的填充指令都是 0x46C0（mov r8, r8） | 同上 14 处全部 `=00bf` |
| 4 | `new_disasm` 的最后一条不再是 nop | 同上 14 个 site 全部是 `nop` |
| 5 | 清单与内容包的 14 处补丁逐字节一致（offset / before_hex / after_hex） | `battle_msg_name@0x79086：after_hex 不同（清单 00bf / 内容包 c046）`、…共 6 条列出 |

> 第 1、5 条同时说明**内容包**（`rom-editor/content/pack.json`）**没被**这次变异碰到 ——
> 变异只换了清单 ⇒ 内容包仍然是 `c046` ⇒ 两者漂移 ⇒ 第 5 条红。
> 这正是 §11（清单与内容包同步）这条断言存在的意义。

### 3.2 本轮（2026-10-23 夜·第二轮）：静态门禁复测 + **修好一个过期探针**

本轮独立验收发现：清单与 §3 的静态门禁都已经是「`0x46C0` 时代」，
但仓库自带的**代码补丁字节级探针** `tools/probe_speaker_code_patches.mjs`
**还停在旧世界** —— 跑出来是**红的**（**检查项 231 / 失败 42**）。

**它红在哪**（14 处补丁 × 3 条 = 42 条，与本轮任务书点名的三处一一对应）：

| # | 探针原来的判据 | 为什么不成立 |
|---|---|---|
| 1 | 补丁末尾必须是 `0xBF00`（`isNop()`） | `0xBF00` 在 ARMv4T 上是**未定义指令**（§1）⇒ 真机卡死；现行约定是 `0x46C0` |
| 2 | 解引用按**寄存器偏移**位域解码（`0x58xx`） | 正确写法是**立即数偏移** `0x68xx`（imm5=0 ⇒ 读 `*(rD)`）；按 `0x58xx` 解码**永远对不上**（第十八轮修的就是这个坑） |
| 3 | `new_disasm` 与 capstone 原样文本**逐字**比对 | 清单约定 `new_disasm` 是**语义等价的人工可读写法**（解引用写作 `ldr rX, [rX, #0]`，而本机 Capstone 5.0.7 原样打印 `ldr rX, [rX]`）⇒ 逐字比对必然对不上 |

**改法**（只改 `tools/probe_speaker_code_patches.mjs` 这一个文件）：

- **填充指令约定从数据源推导，不写死**：新增 `deriveFillerConvention()`，
  从清单 `conventions.filler` 里读出「固定是 `0x46C0`」与「禁用 `0xBF00`」；
  **读不出来就判红**（不静默回退到写死的值）。
- **新增两条断言**（每处补丁各一条）：
  「末尾不是被禁用的填充指令（ARMv4T 未定义指令 ⇒ 真机异常死循环）」、
  「末尾以清单约定的安全填充指令补齐」。
- **解引用改成立即数偏移**：新增 `decodeLdrImm()`（`0x68xx`，imm5=0），
  断言「新序列含且仅含一条解引用 `ldr rD,[rD,#0]`」；
  并**新增一条反向断言**「不含寄存器偏移 `ldr rD,[rD,rD]`（那是 2×rD，不是 *(rD)）」
  —— 那个 bug 现在会被**明确**判错，而不是「碰巧对不上」。
- **`new_disasm` 改按语义比对**：新增 `semNorm()`（助记符 + 操作数语义归一化：
  立即数统一进制；内存操作数 `[base,#imm]` 在 imm=0 时省略 ⇒ `[r0]` 与 `[r0,#0]` **同义**；
  **寄存器偏移 `[base,reg]` 保持可区分** ⇒ `[r0,r0]` 与 `[r0,#0]` **不同义**）。
  `old_disasm` 仍走**逐字**比对（它才是 capstone 原样文本）。
- 顺带加了 `SPK_MANIFEST` / `SPK_REPORT` 两个环境变量：让探针能读**临时副本**清单、
  写到别处的报告 ⇒ **变异测试不用碰仓库源文件**。

**实测（本轮自己重跑）**：

```powershell
node tools\probe_speaker_code_patches.mjs
#   检查项 261，失败 0
#   全部通过：14 处补丁字节级可核验、长度不变、后续代码未移动。
#   退出码 0
```

**探针有牙齿吗？**（三份**临时副本**清单，仓库源文件零改动；
`SPK_MANIFEST` 让探针读临时副本，`SPK_REPORT` 让报告不覆盖正式报告）：

| 变异 | 期望 | 实测（退出码 / 失败数） |
|---|---|---|
| ① 14 处末尾改回 `00bf`（只改字节，`new_disasm` 不动） | 红 | **exit 1 / 失败 42**（14×「语义一致」+ 14×「不得是被禁用的填充指令」+ 14×「必须是安全填充指令」） |
| ② 第 1 处解引用改成**寄存器偏移**（字节 `0x5800` + `ldr r0, [r0, r0]`） | 红 | **exit 1 / 失败 2**（两条解引用断言各红一条） |
| ③ 清单 `new_disasm` 的解引用写成 `[r0, #4]`（语义写错） | 红 | **exit 1 / 失败 1**（语义比对红） |

> ① 里有个**反直觉**的细节值得记：Capstone 5.0.7 在 Thumb 模式下把 `0xBF00`
> **原样打印成 `nop`** —— 所以「capstone 说是 nop」**不能**当作「ARMv4T 上安全」的证据；
> 真机上的合法性只能按 ISA 版本判定（这正是 §1 的结论，也是本轮新增断言的理由）。
>
> ② 还能看出两条断言的分工：把解引用换成寄存器偏移后，
> 「语义一致」这条**照样绿**（capstone 与清单都写 `ldr r0, [r0,r0]`，语义确实相同），
> 是**专门那两条解引用断言**把它抓住的 ⇒ 它们不是冗余。

---

## 4. 真机验收（动态侧）：`tools/mgba_probe/speaker_acceptance.py`（新建）

参照 `relocation_acceptance.py` / `orphan_acceptance.py` 的写法（`check()` / `head()` /
结果写 `build/*.json` / 退出码 0=过）。

- **A0** 前置条件：14 处补丁末尾都是 `c046`、没有 `00bf`；死断点存在。
- **A1** 用**产品代码**造 ROM：`node tools/build_speaker_test_rom.mjs`
  （id 1「鸣人」→「鸣人测试」）⇒ 触发转换；并核对**产物 ROM 里 14 处补丁逐字节等于清单的 `after_hex`**。
- **A2** **阳性对照**：原版 `rom/base.gba` 同一套按键方案 ⇒ **能跑**（不冻结）。
- **A3** **转换版必须能跑**（不冻结）⇒ 打印结论一句话。
- **A4** **辅助快照（不参与判定）**：在补丁过的读者上挂断点，确认它**真的被执行到**。

**判据（按任务书要求）**
- 只看**画面推进**：每按一次 A 截一张 mGBA 渲染缓冲（`rawshot`），比相邻两张的哈希；
  **最后 3 张相同 ⇒ 卡死**。
- 判定用的运行**只挂一个永不命中的断点** `0x08FFFFFE`
  （快速路径在等输入时会永不返回 —— 那是**宿主**的问题，不是游戏卡死）。
- **没有**用「断点 `0x08097A1C` 命不命中」当判据（那是 mGBA 调试器的假象，原版 ROM 上同样不命中）。
- 辅助断点只用来取快照，**不参与判定**。

**实测输出**（`python tools\mgba_probe\speaker_acceptance.py`，退出码 **0**）：

```
A2) 阳性对照：原版 ROM 用同一套按键方案必须能跑
  [PASS] 原版 ROM：不冻结 — 画面变化 15 步，全程未冻结
A3) 转换版必须能跑（不冻结）
  [PASS] 转换版：不冻结 — 画面变化 15 步，全程未冻结
  结论：转换版能跑 —— 画面推进 15 步（14 次按键全程不冻结）
A4) 辅助快照（不参与判定）
  [PASS] 辅助断点命中过（补丁过的读者不是死代码） — 命中 12 次
```

**顺带记一条方法学**：辅助断点命中时的**寄存器快照不可当判据** ——
mGBA 的断点是**软件断点**（原地改成 `BE00: bkpt`）⇒ Thumb 的 BKPT 走未定义指令异常
⇒ CPU 进 BIOS 异常向量 ⇒ 调试器报出「命中」之后 **CPU 继续跑完这一帧**才被宿主切帧停住
⇒ 快照里的 PC/寄存器**不是那条指令的现场**（实测首个快照 pc = `0x0806112A`，在剧情 VM 里，
不在 `0x08097A14`）。这是**观测假象**（同 §3.1/§3.2），所以验收脚本只把它当**信息**打印。

### 4.1 实测（本轮复测，2026-10-23 晚）

`python tools\mgba_probe\speaker_acceptance.py` ⇒ **退出码 0**，完整输出：

```
A0) 前置条件：补丁末尾的填充指令是安全的那一条
  [PASS] 14 处补丁末尾没有 0xBF00（ARMv4T 未定义指令 ⇒ 卡死）
  [PASS] 14 处补丁末尾都是 0x46C0（mov r8, r8）
  [PASS] 判定用的死断点存在（0x08FFFFFE，永不命中） — 0x8fffffe
A1) 用产品代码造一份「说话人名改长」的 ROM
  [PASS] 转换版 ROM 已生成 — build\speaker-test.gba
  [PASS] 改的是 id 1（鸣人） — 1
  [PASS] 名字确实变长了 — 鸣人 → 鸣人测试
  [PASS] 构建报告里有 1 条转换记录 — [{"table": "speaker_names", "kind": "inline_to_pointer", "base": 5920708, "records": 64}]
  [PASS] 产物 ROM 大小与原版一样 — 6291456 字节
  [PASS] 产物 ROM 里 14 处补丁逐字节等于清单的 after_hex
A2) 阳性对照：原版 ROM 用同一套按键方案必须能跑
  [PASS] 原版 ROM：不冻结 — 画面变化 15 步，全程未冻结
  [PASS] 原版 ROM：画面确实在推进 — 变化 15 步
A3) 转换版必须能跑（不冻结）
  [PASS] 转换版：不冻结 — 画面变化 15 步，全程未冻结
  [PASS] 转换版：画面确实在推进 — 变化 15 步
  结论：转换版能跑 —— 画面推进 15 步（14 次按键全程不冻结）
A4) 辅助快照（**不参与判定**）：被补丁过的取名读者真的被执行到
  [PASS] 辅助断点命中过（补丁过的读者不是死代码） — 命中 12 次
  · 首个命中快照（观测假象，仅供参考）：pc=0x0806112A state=Thumb/System I=0 F=0 r1=0xFFFFFFFF lr=0x080610AB
结论
  说话人名变长化真机验收：全部通过
```

> 本轮在 §4 之后**追加**了 A5「读者覆盖」一节（辅助信息，不参与判定）——
> 见 §5(f)。

### 4.2 本轮（2026-10-23 夜·第二轮）：真机验收**自己重跑**

`python tools\mgba_probe\speaker_acceptance.py` ⇒ **退出码 0**，
输出与 §4.1 **逐行相同**（摘录关键行）：

```
A0) 前置条件：补丁末尾的填充指令是安全的那一条
  [PASS] 14 处补丁末尾没有 0xBF00（ARMv4T 未定义指令 ⇒ 卡死）
  [PASS] 14 处补丁末尾都是 0x46C0（mov r8, r8）
  [PASS] 判定用的死断点存在（0x08FFFFFE，永不命中） — 0x8fffffe
A1) 用产品代码造一份「说话人名改长」的 ROM
  [PASS] 转换版 ROM 已生成 — build\speaker-test.gba
  [PASS] 改的是 id 1（鸣人） — 1
  [PASS] 名字确实变长了 — 鸣人 → 鸣人测试
  [PASS] 构建报告里有 1 条转换记录 — [{"table": "speaker_names", "kind": "inline_to_pointer", "base": 5920708, "records": 64}]
  [PASS] 产物 ROM 大小与原版一样 — 6291456 字节
  [PASS] 产物 ROM 里 14 处补丁逐字节等于清单的 after_hex
A2) 阳性对照：原版 ROM 用同一套按键方案必须能跑
  [PASS] 原版 ROM：不冻结 — 画面变化 15 步，全程未冻结
A3) 转换版必须能跑（不冻结）
  [PASS] 转换版：不冻结 — 画面变化 15 步，全程未冻结
  结论：转换版能跑 —— 画面推进 15 步（14 次按键全程不冻结）
A4) 辅助快照（**不参与判定**）：被补丁过的取名读者真的被执行到
  [PASS] 辅助断点命中过（补丁过的读者不是死代码） — 命中 12 次
  · 首个命中快照（观测假象，仅供参考）：pc=0x0806112A state=Thumb/System I=0 F=0 r1=0xFFFFFFFF lr=0x080610AB
A5) 读者覆盖（**辅助信息，不参与判定**）：14 处读者各自被走到过没有
    …（13 处「未命中」）
    vm_0x08                  filler=0x08097A14  命中 ×12
  [PASS] 覆盖扫描跑起来了（剧情 VM 读者 vm_0x08 被执行到 ⇒ 覆盖机制有效） — vm_0x08 命中 12 次
  [PASS] 至少 1 处读者被剧情路线执行到 — 1/14：vm_0x08
结论
  说话人名变长化真机验收：全部通过
  已写出 build\speaker-acceptance.json
```

⇒ **原版能跑 + 转换版能跑**，退出码 0；A5 的覆盖结论与 §5(f) 一致
（14 处里仍只有 `vm_0x08` 被剧情路线走到）。

---

## 5. 验收结果

### (a) 21 道门禁全绿

```
verify_audio_workbench.mjs             全部通过
verify_battle_map.mjs                  全部通过
verify_battle_story_triggers.mjs      全部通过（82 条断言）
verify_cards.mjs                       全部通过
verify_character_view.mjs              全部通过
verify_dialogue_view.mjs               全部通过（56 条断言）
verify_free_space.mjs                  全部通过（16 条断言）
verify_item_view.mjs                   全部通过
verify_labels.mjs                      全部通过
verify_load_flow.mjs                   全部通过（37 条断言）
verify_pack.mjs                        全部通过
verify_route_workbench.mjs             全部通过
verify_scene_view.mjs                  全部通过
verify_script_relocation.mjs           全部通过（14 条断言）
verify_script_text.mjs                 全部通过
verify_sources.mjs                     全部通过
verify_speaker_conversion.mjs          全部通过（42 条断言）
verify_syntax.mjs                      全部通过（75 个文件）
verify_variable_text.mjs               全部通过（82 条断言）
verify_views.mjs                       全部通过
verify_wording.mjs                     全部通过
```

### (b) 真机验收通过

`python tools\mgba_probe\speaker_acceptance.py` ⇒ **退出码 0**
（原版能跑 + 转换版能跑；见 §4）。

### (c) 没改过的内容包重建仍与原版逐字节相同

`verify_speaker_conversion.mjs` §1/§9：
`[PASS] 逐字节与原版相同 — 6291456 字节全等`、
`[PASS] 重建出来的 ROM 与原版逐字节相同 — 6291456 字节全等`、
`[PASS] 重建没有触发转换（没改过就不转换）`。

### (d) 变异测试：把 `after_hex` 末尾改回 `00bf` ⇒ 门禁必须变红

**做法（仓库源文件零改动）**：Node **loader hook** 把 `node:fs` 换成一个「只改了
`readFileSync`」的替身 —— 路径命中 `tools/data/speaker_name_code_patches.json` 时改读
`$MUTATION_MANIFEST` 指向的**临时副本**（`build/mutation/manifest-with-bf00.json`）。
替身模块用 `createRequire` 拿**真正的** fs（绕过 ESM loader ⇒ 不递归），
所以**仓库里的清单一个字节都没动**。

```powershell
node --import ./build/mutation/register.mjs rom-editor/tools/verify_speaker_conversion.mjs
$env:MUTATION_MANIFEST = '...\build\mutation\manifest-with-bf00.json'
```

**对照组**（挂了 hook 但不替换文件）：**全部通过（42 条断言）**，退出码 0
—— 证明 hook 本身没有把门禁弄坏。

**变异组（清单改回 `00bf` + `nop`）**：**5 项失败**，退出码 1：

| 失败的断言 | 说明 |
|---|---|
| 全部 14 处补丁逐字节落地 | 产物 ROM 里现在是 `00bf`，与内容包的 `c046` 不符 |
| 14 处补丁末尾都没有 0xBF00（**新增**） | 14 处全部命中 `00bf` |
| 14 处补丁末尾的填充指令都是 0x46C0（**新增**） | 14 处全部不是 `c046` |
| `new_disasm` 的最后一条不再是 nop（**新增**） | 14 处全部是 `nop` |
| 清单与内容包的 14 处补丁逐字节一致（**新增**） | 清单 `00bf` / 内容包 `c046` |

**反向变异**（把**内容包**改回 `00bf`，清单不动 ⇒ 模拟「清单改了、内容包没改」的漂移）：
同样 **5 项失败**，其中包括
`清单与内容包的 14 处补丁逐字节一致 — battle_msg_name@0x79086：after_hex 不同（清单 c046 / 内容包 00bf）`
与 `内容包里的 14 处补丁末尾也没有 0xBF00`。

**动态判据的牙齿测试**（`build/mutation/dynamic_teeth_test.py`）：
把**产品造的**转换版 ROM 的 14 处 `c046` 改回 `00bf`，用**验收脚本同一套判据**跑：

```
改了 14 处 0x46C0 -> 0xBF00
判定：卡死（变化 6 步，冻结 6）耗时 2s
最后 3 张画面哈希：62638d1b3442 d4b626347dd1 fa4fd7206ccc
```

⇒ 与上一轮记录（`speaker-name-freeze-trace-20261023.md` §4.0：卡死、变化 6 步、冻结 6、
恒为 `fa4fd7206ccc`）**逐位相同** ⇒ 验收门禁不是空转的：同样的判据在坏 ROM 上会红。

> **本轮复测（2026-10-23 晚）**：上面这段是本轮**自己重跑**的，输出与上一轮**逐位相同**
> （`改了 14 处 0x46C0 -> 0xBF00` / `判定：卡死（变化 6 步，冻结 6）耗时 2s` /
> `最后 3 张画面哈希：62638d1b3442 d4b626347dd1 fa4fd7206ccc`），
> 脚本退出码 **0**（= 成功判定为「卡死」）。
> 做法仍然是**临时副本**（`build/mutation/speaker-test-bf00.gba`），
> **仓库文件零改动**。

### (e) 逐像素名字框核对（「名字显示对了」这一条）

上一节 (b) 只证明「**画面不再冻结**」——**没有**证明「**名字画对了**」。
而后者才是这个功能的**目的**：名字没画出来，画面照样推进、照样不冻结 ⇒ 验收照样全绿。

本轮补上这条，工具是**新建**的 `tools/mgba_probe/speaker_namebox_check.py`
（可复跑，退出码 0）。完整报告见
**`notes/evidence/speaker-name-namebox-verification-20261023.md`**。

做法：原版与转换版用**同一套按键方案**各跑一遍，**每一步**都抓一张 mGBA 渲染缓冲
（`rawshot`），逐像素相减。判据里的量都是**算出来的**，不是写死的：
差分矩形 → 字形格宽（差分宽 ÷ 新增字数 = 16 ÷ 2 = 8 px）→ 原版名字矩形（字数 × 格宽，
右边界紧贴差分矩形左边界）。

实测结果：

| 量 | 值 |
|---|---|
| 差分矩形（转换版多出来的部分） | `x[40,55] × y[105,119]`，**196 个差分像素** |
| 原版名字矩形 | `x[24,39] × y[105,119]`（16×15 px = 2 个字形格） |
| 转换版名字矩形 | `x[24,55] × y[105,119]`（32×15 px = 4 个字形格） |
| 名字墨色 | `(115,33,255)` 洋红 + `(189,173,222)` 淡紫 |
| 名字墨色像素数 | 原版矩形里 **142** → 转换版矩形里 **338** |

四条硬判据：

| 判据 | 实测 | 结论 |
|---|---|---|
| ① 转换版的名字框**确实多出了两个字** | 差分宽 16 px = 2 个 8 px 格；墨色 142 → 338 | **成立** |
| ② 前两个字**仍是「鸣人」**（与原版同位置逐像素相同） | `x[24,39] × y[105,119]` 在两张图里**逐字节相同** | **成立** |
| ③ 名字框**没有溢出** | 196 个差分像素**全部**落在 `x[24,55] × y[105,119]` 内；**框外差分 = 0** | **成立** |
| ④ 对话正文那一行与原版**一致** | `y[120,159] × x[0,239]` 逐字节相同 | **成立** |

> ② 最关键：**原版名字所占的那块像素一个 bit 都没变**，而差分**全部**在它右边
> ⇒ 新名字是**在原名字后面追加**的，不是「重新居中」也不是「重排」。
> 另外：16 帧里**只有 A8/A9/A10 这 3 帧**有差分（名字框出现的那 3 帧），
> 其余 13 帧逐字节相同 ⇒ 这次转换**只动了名字**。

### (f) 其余 11 处读者的覆盖（**未覆盖 + 原因**，如实记录）

14 处补丁里，本轮真机路线（开机 1500 帧 + START + 连按 A ×14）**只走到剧情 VM 的
`vm_0x08`（读者 12）**。其余 13 处（战斗消息 / 命令消息 / 战斗日志 / 名字格数 /
名字长度 / 名字绘制 / `vm_0x0E` 等）**只在战斗与命令场景里才会被执行到**。

本轮做过的覆盖尝试与结果：

| 尝试 | 方法 | 结果 |
|---|---|---|
| ① 剧情路线逐处扫描（**已并进验收脚本 §A5**） | `speaker_acceptance.py` 的 A5：对 14 处读者**逐个**挂一条断点，跑同一条剧情路线 | **14 处里 1 处命中**：`vm_0x08` ×12；其余 13 处**未命中** |
| ② 剧情场景逐场扫（存档状态路线） | `build/l2-states/sweep.ss9` + `poke` 相位，逐场按 A，**一次只挂一条**断点 | 仍然主要是 `vm_0x08`；`name_len` / `name_draw`（读者 8）在**个别场次各命中 1 次**（场景 31 / 43）。⚠️ 这条路线依赖 `story_vm_capture.Probe.send` 的 token 生成方式，**跑到一半会阻塞**（同文件头注释里记的「挂死」）⇒ 没有把它并进验收脚本 |
| ③ 战斗场景 | `l4_battle_matrix` 的 `run_battle` 做法：boot 到状态机 → poke 相位 `0x0110` → 进战斗 | **进得去**（战斗地图、指令菜单、战斗日志都跑起来了，见 `build/battle_shots/`），但 13 处读者**一处都没命中** |
| ④ 战斗里的名字 | 战斗消息框截图里**没有**说话人名字 | 读者 1 `battle_msg_name` 前面有一句 `cmp r7,#0`（`0x08079082`）⇒ **消息没有说话人 id 时这一段根本不执行**；本轮进的那场战斗（1/0）消息都不带说话人，且玩家「没有能使用的术」⇒ 产不出带名字的战斗消息 |

**A5 的实测输出**（`python tools\mgba_probe\speaker_acceptance.py`，退出码 0）：

```
A5) 读者覆盖（**辅助信息，不参与判定**）：14 处读者各自被走到过没有
    battle_msg_name          filler=0x0807908E  未命中
    cmd_msg_name             filler=0x080811D4  未命中
    cmd_msg_name_copy        filler=0x08081240  未命中
    battle_log_name          filler=0x0808604A  未命中
    battle_log_name_2        filler=0x08088816  未命中
    cmd_msg_name_copy_2      filler=0x08088DB4  未命中
    name_cell_count          filler=0x08089364  未命中
    name_len                 filler=0x0808D29C  未命中
    name_draw                filler=0x0808D2BC  未命中
    cmd_msg_name_copy_3      filler=0x08090154  未命中
    battle_msg_name_2        filler=0x08095516  未命中
    cmd_msg_name_append      filler=0x08095CF8  未命中
    vm_0x08                  filler=0x08097A14  命中 ×12
    vm_0x0E_second_name      filler=0x08097A30  未命中
  [PASS] 覆盖扫描跑起来了（剧情 VM 读者 vm_0x08 被执行到 ⇒ 覆盖机制有效） — vm_0x08 命中 12 次
  [PASS] 至少 1 处读者被剧情路线执行到 — 1/14：vm_0x08
```

**为什么判据不能只靠「断点命不命中」**：mGBA 的断点是软件断点（§4 的方法学），
命中次数只是**下界**；而且「没命中」既可能是「这段代码没被执行」，
也可能是「这条路线根本没走到那个场景」。所以上面的表**只用来回答
「有没有被执行到过」**，不用来判「能跑 / 卡死」。

**残余风险的性质**（与 §8.1 呼应，但更精确）：
14 处补丁里的 `0xBF00 → 0x46C0` 是**同一批字节的等长替换**，
`0x46C0`（`mov r8,r8`）**不写标志位、不改任何寄存器** ⇒
**14 处的 CPU 语义完全一致** ⇒ 读者 12 上验过的「不冻结」结论，
在**指令语义层面**可以外推到另外 13 处。
**但**「这段代码在**变长后的表**上算出来的名字对不对」这件事，
在另外 13 处**仍然没有动态证据**（那才是真正需要补的场景）。

> **诚实的结论**：这一轮**没有**把另外 13 处读者跑起来。
> 未覆盖的原因已定位到具体机制（战斗消息需要说话人 id；本轮的战斗产出不了），
> 不是「没试」。

### (g) 本轮（2026-10-23 夜·第二轮）：过期探针修好 + 全部证据**自己重跑**

| 事项 | 命令 | 退出码 | 结果 |
|---|---|---|---|
| **代码补丁探针** | `node tools\probe_speaker_code_patches.mjs` | **0** | 检查项 **261** / 失败 **0**（改前：231 / 失败 42） |
| 探针牙齿 ①（末尾改回 `00bf`） | `SPK_MANIFEST=…` + `SPK_REPORT=…` | **1** | 失败 **42** |
| 探针牙齿 ②（解引用换成**寄存器偏移**） | 同上 | **1** | 失败 **2** |
| 探针牙齿 ③（`new_disasm` 语义写错） | 同上 | **1** | 失败 **1** |
| 21 道门禁 | `rom-editor\tools\verify_*.mjs` | 0 | **全绿**（含 `verify_speaker_conversion.mjs` 42 条断言） |
| 静态门禁**对照组**（挂 hook 不替换文件） | `node --import ./build/mutation/register.mjs rom-editor/tools/verify_speaker_conversion.mjs` | **0** | 全部通过（42 条断言） |
| 静态门禁**变异组**（清单改回 `00bf`） | 同上 + `MUTATION_MANIFEST` | **1** | **5 项失败**（与 §5(d) 逐条相同） |
| 真机验收 | `python tools\mgba_probe\speaker_acceptance.py` | **0** | 全部通过（A0–A5） |
| 逐像素名字框核对 | `python tools\mgba_probe\speaker_namebox_check.py` | **0** | 全部通过（12 条断言；差分 **196 px** / `x[40,55]×y[105,119]` / 墨色 **142→338**） |
| 动态牙齿测试 | `python build\mutation\dynamic_teeth_test.py` | **0** | 判定「**卡死**」（变化 6 步，冻结 6，耗时 2s）；末 3 帧 `62638d1b3442 d4b626347dd1 fa4fd7206ccc`；`illegal_opcode 0x08097A14 / 0x0000BF00` |

> **动态牙齿测试的三个画面哈希与 §5(d) 记录的逐位相同**
> ⇒ 判据不是空转的；本轮**独立复跑**了静态变异与动态变异，**不是抄上一轮的输出**。
>
> 逐像素核对的数字（196 px / 差分矩形 / 142→338 墨色）也与 §5(e) **逐位相同**
> ⇒ 「鸣人」是**原样保留**、「测试」是**追加**上去的，这条结论可重复。

---

## 6. 改动的文件清单

| 文件 | 改了什么 |
|---|---|
| `tools/data/speaker_name_code_patches.json` | 14 处 `after_hex` 末尾 `00bf`→`c046`；14 处 `new_disasm` 末条 `nop`→`mov r8, r8`；14 条 `note` 追加坑的说明；新增 `conventions.filler`；`summary` 追加提醒 |
| `rom-editor/content/pack.json` | **用生成脚本重新导出**（`conversions.speaker_names.code_patches[]` 的 14 条 `after_hex`） |
| `rom-editor/content/pack.min.json.gz` | 同上（确定性 gzip） |
| `rom-editor/tools/verify_speaker_conversion.mjs` | 新增 §10（填充指令白名单，6 条断言）+ §11（清单/内容包同步，3 条断言）+ 文件头说明 |
| `tools/mgba_probe/speaker_acceptance.py` | **新建**：真机验收（4 节，17 条断言）；**本轮追加 §A5「读者覆盖」**（14 处读者逐处命中统计，辅助信息） |
| `tools/mgba_probe/speaker_namebox_check.py` | **新建**（本轮）：逐像素名字框核对（12 条断言） |
| `notes/evidence/speaker-name-namebox-verification-20261023.md` | **新建**（本轮）：逐像素核对的完整报告 |
| `notes/evidence/speaker-name-fix-20261023.md` | **新建**：本文件 |
| `tools/probe_speaker_code_patches.mjs` | **本轮（第二轮）**：修好过期探针（填充指令从清单推导 / 解引用按立即数偏移 / `new_disasm` 按语义比对 / 新增「末尾不得是 0xBF00」断言） |

**没碰**：`rom-editor/js/**`、`docs/**`、其它 `tools/mgba_probe/*`、其它 `notes/evidence/*.md`；
没有 `git commit`。

（本轮第二轮**只**改了上面表里 `tools/probe_speaker_code_patches.mjs` 与本文件两处；
`tools/data/**`、`rom-editor/**` 一个字节都没动 —— 变异测试全部走**临时副本**。）

（`build/` 下的脚本是**一次性核对工具**，不入库：`build/mutation/*`、`build/diff_pack_before_after.py`、
`build/fix_manifest_filler.py`、`build/reword_manifest_note.py`；
本轮新增的一次性探索脚本：`build/_namebox_explore.py`、`build/_namebox_locate.py`、
`build/_namebox_color.py`、`build/_namebox_ink.py`、`build/_reader_cover_explore.py`、
`build/_reader_sweep_all.py`、`build/_reader_clean_sweep.py`、`build/_battle_cover_explore.py`、
`build/_battle_cover2.py`、`build/_battle_shots.py`、`build/_bp_debug.py`、`build/_state_probe.py`。）

---

## 7. 假设

1. **「`0x46C0` 是当前约定」**：按任务书把 `0x46C0`（`mov r8, r8`）写成**白名单**而不是
   「只要不是 `0xBF00` 就行」—— 白名单能挡住「换成别的非法指令」这类回归。
2. **`rom-editor/js/**` 不需要改**：依据是 `rom.js:361` 从内容包读 `after_hex`，
   且全目录 grep `bf00` 零命中（§2.3）。
3. **`docs/sequel-roadmap.md` 本轮没动**：AGENTS.md 规则 6 要求「路线图进展变了要同轮更新」，
   但本轮任务书明确把 `docs/` 列为「不要碰」⇒ 以任务书为准，
   **路线图的进度条目需要下一轮补**（见 §8）。
4. 验收脚本的判据实现**复用** `tools/mgba_probe/speaker_freeze_trace.py` 的 `run_case`
   （只读引用，未修改该文件）—— 判据只有一处实现，避免两处漂移。
5. **本轮新增**：逐像素名字框判据里，「字形格宽」与「原版名字矩形」是**从差分推出来的**
   （差分宽 ÷ 新增字数 = 8 px；原名字数 × 格宽，右边界紧贴差分左边界），
   **不是写死的坐标** ⇒ 换名字、换 id、换场景都仍然成立。
6. **本轮新增**：A5「读者覆盖」用**和 A2/A3 完全同一条路线**（开机 1500 帧 + START + 连按 A ×14），
   所以它**不依赖任何额外的 build 产物**，也不会因为缺存档状态而让验收红掉。
   代价是覆盖面比「存档状态逐场扫」窄（后者在个别场次能额外碰到 `name_len` / `name_draw`）。
7. **本轮（第二轮）新增**：探针里「安全填充指令 / 禁用填充指令」**不写死**，
   而是从清单 `conventions.filler` 的文字里**推导**（取「禁用/禁止/不得/不能」之前的第一个
   `0xXXXX` 作安全值、之后的第一个作禁用值）⇒ 约定改了，探针跟着改；
   **推导不出来就判红**，不静默回退到写死的 `0x46C0`/`0xBF00`。
   代价：约定文字若被改写得太自由（例如不再出现 `0xXXXX`），探针会红 —— 这是**故意的**
   （宁可红，不要默默按旧约定放行）。
8. **本轮（第二轮）新增**：`new_disasm` 的**语义**比对只覆盖这 14 处实际用到的 5 种写法
   （`lsls rX,rX,#imm` / `ldr rX,[pc,#imm]` / `adds rX,rX,rX` / `ldr rX,[rX,#imm]` / `mov rX,rX`）；
   出现**没见过的写法**时，`semNorm()` 会原样保留文本（不猜语义）⇒ 多半会红，
   需要人看一眼 —— 这是**故意**的：宁可红，也不要把没读懂的指令判成「语义一致」。

---

## 8. 剩下的风险 / 没闭合的部分

1. **12 处读者只验了剧情开场那一条路径**：本轮真机验收跑到的是剧情 VM 的 op 0x08
   （读者 12）。证据 §4.3 已经点明：**战斗消息 / 命令消息 / 战斗日志**等场景
   （读者 1/2/3/4/5/6/9/10/11）也会被执行 ⇒ 那些场景要单独验。
   本轮「14 处全部换成 `c046`」是**静态等价**的替换（同一批字节、同样 2 字节），
   但**动态只覆盖了 1 条路径**。
   → **本轮补充**：§5(e) 把「名字显示对了」这条补上了（逐像素）；
   §5(f) 把读者覆盖的**尝试过程与未覆盖原因**写清楚了（A5 表格：14 处里 1 处命中）。
2. **辅助断点命中时的寄存器快照不可信**（§4 末尾）⇒ 想验「r1 是不是解引用后的名字指针」
   这类问题，得换一种观测手段（例如比较 base/转换版两张截图的名字行）。
   → **本轮补充**：§5(e) 就是用这个手段（比两张截图）做的，
   而且**绕开了**寄存器快照 ⇒ 这条风险在「名字对不对」这一问上已经不再是阻碍。
3. **`0xBF00` 的现象在 GBA 硬件上的说明**：本轮全部证据来自 mGBA；
   真机上「无限异常循环 ⇒ 画面冻结」这一段是按 ARMv4T 的异常机制推导的，
   **没有在实机 GBA 上验证**。
4. **`docs/sequel-roadmap.md` 的进度条目待补**（见 §7.3）。
5. **「名字画对了」只在剧情场景验过**：§5(e) 的逐像素核对跑的是**开场剧情**。
   战斗/命令场景里的名字框**没有**用同一套像素判据验过
   （原因同 §5(f)：那些场景本轮没跑起来）。
6. **战斗场景能进，但产不出带名字的消息**：读者 1 前面有 `cmp r7,#0`（`0x08079082`），
   消息没有说话人 id 时那一段根本不执行 ⇒ 「进战斗」不等于「覆盖到战斗消息读者」。

---

## 9. 复现清单

```powershell
cd D:\Github\gba-naruto
# 静态门禁
node rom-editor\tools\verify_speaker_conversion.mjs      # 全部通过（42 条断言）
# 代码补丁字节级探针（本轮修好的那个）
node tools\probe_speaker_code_patches.mjs                # 检查项 261，失败 0（退出码 0）
# 真机验收（原版能跑 + 转换版能跑 + 读者覆盖表，退出码 0）
python tools\mgba_probe\speaker_acceptance.py
# 逐像素名字框核对（「鸣人测试」画对了没有，退出码 0）
python tools\mgba_probe\speaker_namebox_check.py
# 变异测试：把清单末尾改回 00bf ⇒ 门禁必须变红
python build\mutation\make_mutated_manifest.py
$env:MUTATION_MANIFEST = (Resolve-Path 'build\mutation\manifest-with-bf00.json').Path
node --import ./build/mutation/register.mjs rom-editor\tools\verify_speaker_conversion.mjs
# 探针的牙齿测试：三组变异都必须把它打红（仓库源文件零改动）
python build\mutation\make_probe_mutations.py
$env:SPK_MANIFEST = (Resolve-Path 'build\mutation\probe-mut-bf00.json').Path
$env:SPK_REPORT   = (Resolve-Path 'build').Path + '\probe-mut-bf00-report.txt'
node tools\probe_speaker_code_patches.mjs                # 退出码 1（失败 42）
# 动态牙齿测试：坏 ROM 必须被判成「卡死」
python build\mutation\dynamic_teeth_test.py
```

本轮（2026-10-23 夜·第二轮）实际跑过、退出码如实记：

| 命令 | 退出码 | 结果 |
|---|---|---|
| `node tools\probe_speaker_code_patches.mjs` | 0 | 检查项 261，失败 0 |
| `node tools\probe_speaker_code_patches.mjs`（`SPK_MANIFEST`= 末尾 `00bf` 的副本） | **1** | 失败 42 |
| `node tools\probe_speaker_code_patches.mjs`（`SPK_MANIFEST`= 寄存器偏移解引用的副本） | **1** | 失败 2 |
| `node tools\probe_speaker_code_patches.mjs`（`SPK_MANIFEST`= `new_disasm` 语义写错的副本） | **1** | 失败 1 |
| `node rom-editor\tools\verify_speaker_conversion.mjs` | 0 | 全部通过（42 条断言） |
| `node --import ./build/mutation/register.mjs …`（对照组） | 0 | 全部通过（42 条断言）—— hook 本身没把门禁弄坏 |
| `node --import ./build/mutation/register.mjs …`（变异组） | **1** | **5 项失败** |
| `python tools\mgba_probe\speaker_acceptance.py` | 0 | 全部通过（A0–A5） |
| `python tools\mgba_probe\speaker_namebox_check.py` | 0 | 全部通过（12 条断言） |
| `python build\mutation\dynamic_teeth_test.py` | 0 | 判定「卡死」，末 3 帧 `62638d1b3442 d4b626347dd1 fa4fd7206ccc` |
| 21 道 `rom-editor\tools\verify_*.mjs` | 全 0 | 全绿 |
