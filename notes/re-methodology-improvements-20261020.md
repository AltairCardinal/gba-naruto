# 方法论增量：从对方的测试与构建脚本里还能学什么（2026-10-20）

**触发问题**: 对方"木叶工房"包的逆向成果已全部合入（见
`notes/external-konoha-workshop-gap-20261020.md` §12），
`notes/why-external-editor-shipped-20261020.md` §4 也已总结 L1–L7 七条教训。
**还能从他们的"做法"里学到什么？**

**结论**：从他们的**测试套件与构建脚本**（而非结论本身）里，还能挖出
6 条我们尚未吸收的具体做法。其中 **2 条能直接缓解我们当前的阻塞**，
1 条能当场防住我们上一轮已经踩过的坑。

---

## 0. 先说清楚：他们的验证套件长什么样

`third_party/konoha-workshop/源码/editor/tests_features.js` 的 8 项检查
（每项都产出 evidence JSON）：

| # | 检查 | 技术要点 |
|---|---|---|
| 1 | no-edit exact byte identity | `build()` 无改动时必须与 baseline **逐字节相同** |
| 2 | all 46 native maps decode and render | 全部地图能解码并渲染，尺寸/像素数断言 |
| 3 | LZ literal encoder matches native resource decoder | `decompress(compressLiteral(x)) == x` —— **用游戏自己的解压器验证我们的编码器** |
| 4 | map stamping without changing shared source blocks | 改一个格子后，**共享源块字节不变**；新指针必须 ≥ baseline 长度（即追加而非覆写） |
| 5 | map edits undo and invalid coordinates roll back | undo 生效；非法坐标抛错且**不留残留改动** |
| 6 | new events compile to native scripts | 新事件编译成原生脚本后，`reopen` 的 `issues` 必须为空 |
| 7 | reopened event ROM unchanged project keeps exact bytes | build→reopen→build **字节恒等**（不动点） |
| 8 | native event slots stay intact | 加新事件后，原版事件槽字节与原 ROM **逐字节相同** |

`源码/editor/build_sample.js` 更进一步：**从零合成一个 ROM** ——
手写一段剧情字节码 → 挂到四张根表 → 导出 → **重新打开并统计对白条数**，
再在 manifest 里诚实写 `runtime: 'not_run'`。

---

## 1. 六条可吸收的做法

### M1｜合成夹具往返：不用模拟器也能证明"格式对不对" ★最高价值

**他们的做法**：写一段**已知内容**的表 → 挂指针 → 用自己的解码器读回 → 比对。

**为什么对我们特别重要**：我们有一批表"能读出字节但说不清语义"。
按常规做法只能等动态验证；而**格式正确性**这件事，用合成夹具就能自证：

> 把一段我们完全知道内容的表写进 ROM 空闲区并改指针，
> 用我们的解码器读回来 == 我们写进去的内容 → **格式假设被证明**。

这不依赖游戏运行时，所以能立刻把一批表从"静态自洽"提升到"读写闭环"。

**我们的现成条件**：
- 写侧已有：`tools/import_dialogue_var.py`（写空闲区 `0x5DFBEC`）
  与 `build_mod.py` 的 `pointer_redirect`；
- 读侧已有：VM 解码器、战斗表提取器、奖励表/物件表/头像/positions 提取器。

**诚实的限定**：夹具证明的是**格式**，不是**游戏如何使用该字段**。
按本仓库新引入的四级证据分级（`notes/runtime-verification-gates-20260710.md`），
它落在 **L1（工具产出通过）**，**不构成 L2/L3**。不要拿它当"已验证语义"。

### M2｜无改动构建的字节恒等门禁

**他们的做法**：无改动时 `build()` 必须与 baseline 逐字节相同（检查 #1、#7）。

**我们为什么需要**：**上一轮已经踩过这个坑**——
`tools/automated_test.py` 的构建用例会重写 `build/naruto-sequel-dev.gba`，
而本机缺 `sequel/editor.db`（被 gitignore），重建后产物从
2443 条补丁掉到 5 条，等于**悄悄换掉了一份已跟踪的产物**。
当时是靠人工比对补丁计数才发现的。

**建议**：把"manifest-only 构建产物 == 已提交产物"做成一条自动断言，
并在构建报告里加一节 **changed byte ranges vs base**（本次构建改了哪几段）。

### M3｜原生数据不回归断言（变更半径）

**他们的做法**：加新事件后，原版事件槽字节与原 ROM 逐字节相同（检查 #8）；
改一个格子后共享源块不变（检查 #4）。

**我们的现状**：`tools/patch_safety.py` 已有**重叠检测**
（`conflicting patch overlap` / `idempotent_duplicate`），
但只覆盖"两个补丁互相冲突"，**不覆盖"补丁改了不该改的字节"**。

**建议**：每条补丁记录它"声称"要改的字段区间；构建后做一次全 ROM 差分，
任何落在声明区间之外的改动都判失败。这是把 L1 的"写回模型"
（复制原生条目 + 只改已知字段）变成**可执行的约束**，而不是口头纪律。

### M4｜基址只从 ROM 取，不信项目文件

**他们的做法**（`features.js` 原注释）：
> "Base pointers come from the ROM's own catalogue, never from untrusted project JSON."

并且有**投毒测试**：把项目 JSON 里的 `features.bases[1].logic` 改成 0，
构建结果仍必须与投毒前**字节相同**。

**我们为什么需要**：我们已经吃过一次亏 ——
`notes/u32-pointer-real-writeback-20260710.md` 记录
"陈旧 `_rom_offset`，现已拒绝回写"。他们把这条做成了**设计不变量 + 测试**，
我们只是**事后补救**。值得固化成同样的不变量。

### M5｜负向测试：工具必须能拒绝

**他们的做法**（检查 #5、#8）：非法坐标抛错、超额事件抛错、空对白抛错，
且抛错后**不留残留改动**。

**我们的现状**：`tests/test_unsafe_legacy_patches.py`、
`tests/test_unsafe_unit_patch.py` 已经在做这件事。方向一致，可继续加强。

### M6｜产物自陈运行时等级

**他们的做法**：manifest 里显式写 `runtime: 'not_run'`。

**我们已吸收**：上一轮的 L1–L4 四级证据分级
（`notes/runtime-verification-gates-20260710.md`），更严格。无需再动。

---

## 2. 对我们当前阻塞的映射

| 我们的阻塞 | 对方做法能否缓解 | 怎么用 |
|---|---|---|
| 大量表停在 static/code 验证，动态验证受限于没有模拟器 | ✅ **M1** | 合成夹具往返：把每张表做成"写→读回→相等"的证明 |
| 产物可能被无声改坏（editor.db 缺失那次） | ✅ **M2** | 无改动构建字节恒等断言 + 全 ROM 差分报告 |
| 写回只改了"该改的字段"目前靠自觉 | ✅ **M3** | 补丁声明字段区间 + 构建后全 ROM 差分核对 |
| 陈旧 `_rom_offset` 已伤过一次 | ✅ **M4** | 基址只从 ROM 取，做成不变量 + 投毒测试 |
| 全部 L2/L3 动态证据缺口 | ❌ | 仍需 mGBA C API 探针（`notes/mgba-c-api-probe-plan-20261020.md`） |

> **M1 不能替代动态验证**：它证明"我们的读写器自洽"，不证明"游戏这样用字段"。
> 把 M1 的结果写成 L1，别写成 L2/L3。

---

## 3. 建议落地顺序

1. **M2 + 差分报告**（成本最低，收益立竿见影）：
   `tools/build_mod.py` 输出"本次构建改动的字节区间"，
   并加一条"无改动构建 == 已提交产物"的断言。
   —— 上一轮那份被无声替换的产物，正是这条门禁该拦下的。
2. **M1 合成夹具**（收益最大）：
   先挑一张已经能用字形码解出来的表（剧情 VM 的 `before` 根表最适合）
   做端到端夹具：合成 → 写空闲区 → 改指针 → 解码 → 比对。
   跑通后这套框架可复制到战斗表、奖励表、物件表。
3. **M4 基址不变量 + 投毒测试**（半小时，堵住已知伤疤）。
4. **M3 变更半径断言**（依赖 1 的差分报告，顺手做）。

---

## 4. 落地情况（2026-10-20 第三轮）

| 编号 | 做法 | 落地 | 证据 |
|---|---|---|---|
| **M1** | 合成夹具往返 | ✅ `tools/synthetic_fixture.py` | 4 个夹具（story_before / battle_rules / battle_actors / reward_entry）**19 项检查全绿**；夹具 ROM 落在 `build/synthetic-fixtures/`，不碰真实 ROM |
| **M2** | 无改动构建字节恒等 / 变更半径 | ✅ `tools/build_mod.py` | 报告新增 `change_radius` 段；`undeclared_change_count` 必须为 0，否则**构建直接失败** |
| **M3** | 变更半径断言 | ✅ 同上 | 声明区间 = 所有补丁的 `(offset, length)` 并集；全 ROM 差分后做区间减法 |
| **M4** | 基址只从 ROM 取 | ✅ `tools/table_registry.py` | 32 个内容 bank 全部与权威注册表一致（0 mismatch）；**投毒测试**：把 `maps` 的 `table_offset` 改成 `0x123456` 必须被检出 |
| **M5** | 负向测试 | ✅ `tests/test_process_improvements.py` | 14 项，含"未知 opcode 必须报 issue"、"越界空闲区必须被拒"、"投毒基址必须被检出" |
| **M6** | 产物自陈运行时等级 | ✅（上一轮已吸收） | `notes/runtime-verification-gates-20260710.md` §四级证据分级 |

### 4.1 接进标准流程

新增 `process` 套件（`tools/automated_test.py`），**每次跑标准测试都会执行**：

```
python tools/automated_test.py            # 27/28
python tools/automated_test.py --suite process -v
```

套件包含 4 项：合成夹具往返、表基址与注册表一致、构建无声明外改动、报告含变更半径段。

### 4.2 变更半径报告长什么样

```
change_radius:
  changed_bytes            : 127
  changed_range_count      : 9
  declared_range_count     : 5
  undeclared_change_count  : 0
  changed_ranges           : 0x76d..0x76f, 0x459414..0x45943d, ...
```

字节级爆炸半径直接可见：`0x459414` 处只改了 2 字节（其余相同），
`0x459508` 处整 41 字节全改 —— 这在旧的"补丁列表"视角下是看不出来的。

### 4.3 本轮顺手修掉的两个环境问题

- `automated_test.py` 的子进程输出按 **GBK** 解码会抛 `UnicodeDecodeError`
  （子进程输出 UTF-8 中文，父进程用系统 locale 解码）。已固定为
  `encoding="utf-8", errors="replace"`。
- 测试套件的构建用例原本会重写已跟踪的 `build/naruto-sequel-dev.gba`；
  上一轮已改为隔离输出目录（`build/automated-test-build`）。

### 4.4 意外收获：换行符失效是**真的会发生**的

改写 `tools/automated_test.py` 时用了一段 Python 脚本做替换，
结果 `Path.write_text` 在 Windows 上把 `\n` 转成了 `\r\n` ——
**整个文件被改写成 CRLF，而 `git status` 只显示"修改了"，不报换行符问题**。

这正是 `notes/windows-migration-20261020.md` 里那条规则
（"仓库用文件 SHA-256 当证据身份，换行符一改全部钉死失效"）所指的事。
本次共 3 个受版本控制的文件被这样污染：
`tools/automated_test.py`、`sequel/content/text/dialogue-bank.json`、
`sequel/content/text/dialogue-bank-full.json`。

修法分两层：

1. **写入端**：新增 `tools/lib/io.py` 的 `write_text()`（强制 `newline="\n"`），
   把所有写受版本控制文件的工具切过去
   （`extract_dialogue_full` / `migrate_text_bank_to_font` /
   `import_dialogue` / `import_dialogue_var` / `populate_bank_json` /
   `extract_all_structures` / `build_mod` / `audit_re_completion`）。
2. **守卫端**：新增 `tests/test_line_endings.py` ——
   扫全部受版本控制的文本文件，任何 CRLF 立即失败；
   同时断言 `core.autocrlf` 仍为 `false`。

> 这条比对方那套更严：他们的"原字节校验"管的是补丁目标，
> 管不到"工具自己把文件写出 CRLF"这类**元层面**的失效。

### 4.5 仍然没有解决的部分

M1 只证明**格式**，不证明**游戏如何使用字段**。按四级证据分级，
它落在 **L1（工具产出通过）**，不构成 L2/L3。
真正的动态语义验证仍然需要 mGBA C API 探针
（`notes/mgba-c-api-probe-plan-20261020.md`）。

## 5. 复现

对方的验证套件可直接阅读（只读知识库）：

- `third_party/konoha-workshop/源码/editor/tests_features.js`
- `third_party/konoha-workshop/源码/editor/tests_objects.js`
- `third_party/konoha-workshop/源码/editor/tests_core.js`
- `third_party/konoha-workshop/源码/editor/build_sample.js`
- `third_party/konoha-workshop/源码/continuation/tools/check_editor_workflow.js`
