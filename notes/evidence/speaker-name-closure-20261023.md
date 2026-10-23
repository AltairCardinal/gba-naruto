# 说话人名表变长化：**这一轮的收口**（2026-10-23 最后一段）

> **本篇是「收口」那一段的工作记录**：把这一轮新闭合的 **5 项**回填进项目记忆，
> 顺手修掉两处遗留的**过时说明**。
> 改了什么、为什么这么改、复验结果，逐条写在这里（报告边查边写，不攒到最后）。
>
> **本轮允许动的文件**（只有这些 + 新建本篇）：
> `rom-editor/js/modules/common.js` · `rom-editor/js/modules/story.js` ·
> `notes/evidence/speaker-names-hypothesis-ledger.md` ·
> `notes/evidence/speaker-name-round-summary-20261023.md` ·
> `notes/evidence/speaker-name-fix-20261023.md` ·
> `docs/sequel-roadmap.md` · `docs/handoff-20261023-speaker-names-conversion.md`
>
> **没有 `git commit`** —— 工作树里还有别的会话的在制品，提交由上级逐一核对后做。
> **没有碰** `rom-editor/js/rom.js`、`rom-editor/js/editors.js`、`rom-editor/content/**`、
> `rom-editor/tools/**`、`tools/**`、`notes/evidence/consumer-evidence.json`。

---

## 0. 一句话

> **5 项闭合全部回填进台账 / roadmap / 总览 / 交接文档；两处过时说明改成与真实内容包一致的说法；
> 21 道门禁复验全绿；逐字节不变式仍然成立（6,291,456 字节全等）；没有 `git commit`。**

---

## 1. 改了什么（逐文件）

### 1.1 `rom-editor/js/modules/common.js` —— 过时说明（一）

**原来**（`lengthStrategyLabel()` 上面的注释）：

> 11 张表里 9 张是**指针表驱动**的 …；`speaker_names` 是**定长内联槽**、
> `battle_objectives` 是**绝对地址引用** —— 这两张**结构上就变不了**。

**两处都过时了**：

| 说法 | 实际（数过的） |
|---|---|
| 11 张表 | **13 张** |
| 9 张指针表 | **10 张**指针表 + **1 张**可转换 + **2 张**定长内联槽 |
| `battle_objectives` 是绝对地址引用 | 它**早就是指针表驱动**了（`relocatable=true`、`pointer_offset=5851180`、19 B × 219 条） |
| `speaker_names` 是定长内联槽（结构上变不了） | 它是**定长内联槽但可转换**（`convert='speaker_names'`）⇒ 能变长 |

**改后**：13 张表里 10 张指针表驱动；`speaker_names` 定长内联槽**但可转换**；
`speaker_full_names`（说话人全名表）与 `location_names`（地点名表）是
**定长内联槽且不可转换** —— 这两张结构上就变不了。

**数字是怎么数的**（不是照抄任务书）：读 `rom-editor/content/pack.json` 的 `texts[]`，
按 `rom-editor/js/pack.js::textSlotKind()` 的判定顺序（`convert` → `pointer_offset`
→ `raw` 长度 == `capacity` → `absolute`）逐张分类：

```
character_names  pointer | training_names  pointer | jutsu_names      pointer
ninjutsu_names   pointer | material_names  pointer | mission_titles   pointer
mission_descriptions pointer | mission_hints pointer | dialogue_slots  pointer
battle_objectives pointer          ← 10 张指针表
speaker_names      convertible      ← 1 张可转换（19? 不，12 B × 64 条）
speaker_full_names fixed 19 B × 64  ← 2 张定长内联槽
location_names     fixed 18 B × 55
```

### 1.2 `rom-editor/js/modules/story.js` —— 过时说明（二）+ 两张新表的归属

**引言（`intro`）**原来写「指针表驱动的文本（对白槽位表、任务表、**名字表**）…；
定长内联槽（**说话人名表**）与被代码用**绝对地址引用**的文本只能等长改写」——
两处不准（`speaker_names` 不是指针表驱动、它**可转换**；「绝对地址引用」那张表
早就改成指针表了）。改成与内容包一致的说法。

**`texts:` 列表**：`['dialogue_slots', 'speaker_names', 'rom_text_index']`
⇒ **加上 `speaker_full_names` 与 `location_names`**，并在代码注释里写清归属依据（见 §4.1）。

### 1.3 `notes/evidence/speaker-names-hypothesis-ledger.md`

| 位置 | 改动 |
|---|---|
| **F1 / F2 / §1.1 的 ⚠️ 备注** | 「**42** 条断言」→ **47**（本轮由 42 增至 47：新增的是**保护区那 5 条**） |
| **F6** | 保护区从「全名表 `0x085A5AB8..0x085A5F78`」改为**两张表 `0x085A5AB8..0x085A6343`**（2187 字节），并指向 F19 |
| **F18** | 改写为**已闭合**：**A 5 / B 9 / C 0**；14/14 受控触发正确；三条路线 151 / 462 / 59 步都不冻结；144 场战斗全扫。**删掉「未闭合的覆盖缺口」那句** |
| **F18b**（新增） | 如实写清剩下的是**「界面没被打开」**，**不是「代码没验过」**（代码在真实 CPU 上验过了，14/14） |
| **F19 – F23**（新增） | 本轮新增的事实：保护区新范围 + 变异测试 · 两张表进内容包（11→13）· 定长槽写回的三处缺口 · 跨表抢字节检测 · 逐字节不变式 + 生成器确定性 |
| **§6 新事实表** | 加了**状态列**（`已确认` / `已证伪` / `未验`，与 §1/§2 同一口径）；**N5 拆成 N5① / N5② / N5③ 三行**，各自**已确认**并写依据文件 + 关键数字；**N1 / N1b / N2 / N3 / N4 / N6** 也标上状态 |
| **§9 相关文件** | 补上本轮的 5 篇证据笔记 + 3 个探针 + 收口本篇 |

**保留**：全部 15 条「已证伪」（H1–H15）、全部 3 条「被推翻的前提」（P1–P3）、
U1–U5 的判定表、**§7「怎么用这张表」那一节**（原样保留，只在 §9 的表里加了行）。

### 1.4 `notes/evidence/speaker-name-round-summary-20261023.md`

- **§0** 的「剩下的是收口」改成「**这一轮已经收口**」并指向新的 §6；
- **§4.1** 证据笔记从「7 篇」改成两段（**收口那一段的 6 篇** + **前一段的 7 篇**），
  **§4.2** 工具表补上 4 个新探针；
- **§5.1 / §5.2 / §5.3** 改写成「三件都已做 / 别再查 / 原来那 3 件小事全部验完」；
- **新增 §6「这一轮的收尾（最终状态）」**：5 项闭合表 + 顺带修掉的产品缺口 +
  最终状态表 + 还剩什么。

### 1.5 `notes/evidence/speaker-name-fix-20261023.md`

| 位置 | 改动 |
|---|---|
| **§7.3** | 「路线图的进度条目需要下一轮补」⇒ **已补，见 §8.4** |
| **§8.1** | 「12 处读者只验了剧情开场那一条路径」⇒ **已闭合**（受控触发 14/14；A 5 / B 9 / C 0）；同时写清剩下的是**界面没被打开** |
| **§8.4** | 「**`docs/sequel-roadmap.md` 的进度条目待补**」⇒ **✅ 已补**，注明位置 = `docs/sequel-roadmap.md` 的「**2026-10-23｜ROM 编辑器第十八轮**」一节 |
| **§8.5** | 「名字画对了只在剧情场景验过」—— **仍然成立**，补一句「收口那一段也没补」 |
| **§8.6** | 「战斗场景能进，但产不出带名字的消息」⇒ **这条已被推翻**（战斗消息框确实画出了带说话人的「鸣人测试」；它走的是**读者 12 `vm_0x08`**，不是读者 1/10） |

### 1.6 `docs/sequel-roadmap.md`（「2026-10-23｜ROM 编辑器第十八轮」一节）

- 原来那条「⚠️ **真机验收的覆盖缺口**（只覆盖 1/14 处读者）」⇒ 改成 **✅ 已闭合**，
  写进 **A 5 / B 9 / C 0**、14/14 受控触发、三条路线步数、144 场全扫，
  以及「剩下的是**界面没被打开**，不是**代码没验过**」；
- 补一条「✅ 另外两项待验也闭合了」（逐像素名字框 + 标志位语义）；
- 「**下一步（现在真正剩下的事）**」⇒ 改成「**这一步做完的事**」：
  四条都已做（产品侧落地 / 真机验收 / 收口 / 登记表 + 内容包），
  加上 **门禁 42 → 47**、**内容包 11 → 13**、**逐字节不变式仍成立**、
  以及「还剩下的只是产品体验上的事」。

### 1.7 `docs/handoff-20261023-speaker-names-conversion.md`

- **§5**「下一步该做什么（有序）」⇒ **「本轮已完成什么 / 之后还剩什么」**：
  §5.1 四条已做（含每条的证据与关键数字），§5.2 剩下的三件**产品体验**上的事；
- **§1** 的完成情况表：要求 1 由「**部分**」⇒ **✅ 已闭合**；要求 4 ⇒ **✅ 两张都完成**；
- **§3** 的标题「唯一的未闭合项：…」⇒ 「…—— **已闭合**；下面是当时的症状与排查过程」；
- **§7** 两句话总结 ⇒ 第二句从「只剩三件事」改成「**这一轮已经收口**」；
- **§0** 里那句「11 张文本表里 9 张是指针表驱动」后面补了一句
  「**这是当时的数字**：现在内容包里是 **13 张**表」。

---

## 2. 复验结果（本轮实际跑的，退出码如实记）

### 2.1 21 道门禁 —— 全绿

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
verify_speaker_conversion.mjs          全部通过（47 条断言）   ← 本轮由 42 变 47
verify_syntax.mjs                      全部通过（75 个文件）
verify_variable_text.mjs               全部通过（84 条断言）
verify_views.mjs                       全部通过
verify_wording.mjs                     全部通过
```

> `verify_views.mjs` / `verify_syntax.mjs` 是在**改完 `common.js` 与 `story.js` 之后**跑的
> （那两道门禁会真的把剧情域首页画出来），绿。

### 2.2 逐字节不变式 —— 仍然成立

```
$ node build\verify_byte_identical.mjs
  [PASS] 逐字节比较无差异 — 6,291,456 字节全等
  报告: 文本表 13（改动 0）/ 结构 116（改动 0）/ 补丁 0
  [PASS] sha256 一致 — 重建 1198ece781aaf629… / 原版 1198ece781aaf629…
  [PASS] 说话人全名表（0x5a5ab8 起 1216 字节）逐字节未动
  [PASS] 地点名表（0x5a5f65 起 990 字节）逐字节未动
  [PASS] 说话人简称表（0x085a57c4 起 768 字节）逐字节未动
全部通过   （EXIT=0）
```

### 2.3 登记表 / 别名裁决 / 内容包自检

```
$ python tools\table_registry.py
mismatches: 0 - every content bank agrees with the registry      （EXIT=0）

$ python tools\alias_audit.py rom\base.gba
未裁决冲突: 0
失败的判死检验: 0
RESULT: OK                                                   （EXIT=0）

$ python tools\export_content_pack.py --check
OK: 内容包与 ROM 一致                                        （EXIT=0）
```

> ⚠️ 任务书写的是 `node tools/export_content_pack.py --check` —— 那是 **`.py`** 文件，
> 必须用 `python` 跑（用 `node` 会因为语法不对直接报错）。

---

## 3. 判断记录（这一轮做过的判断 + 依据）

### 3.1 两张新表该不该进 story 域的 `texts:` 列表？—— **进**，依据有三条

**不是拍脑袋，也不是照抄任务书**。查下来有三条**互相独立**的依据：

1. **内容包自己就这么标**：两张表在 `rom-editor/content/pack.json` 里的
   `module` 字段**都是 `story`**。而 `common.js::domainTableRows()` 会把
   `module === options.module` 的表**自动追加**到该域的表列表里
   ⇒ 两张表**本来就够得着**（`verify_views.mjs` 第 8 组正是拿这个数做可达性断言）。
   写进 `options.texts` 决定的是**策展顺序**（域自己的清单排在前面，自动追加的排在后面），
   不是可达性。
2. **说话人全名表 = 说话人简称表的邻居**：`speaker_names`（简称，12 B × 64）
   与 `speaker_full_names`（全名，19 B × 64）是**同一批说话人的两种形态**，
   简称表本来就在这一域 ⇒ 全名表是它的邻居，放一起作者不用在两个地方来回找。
3. **地点名表是剧情侧的数据**：它唯一的原生读者 `fn 0x0808CD40`
   是被**剧情状态机** `fn 0x0808F190` 调用的（`0x0808F40C`；
   同一个函数还 `bl 0x0808F4D4` 派发场景）⇒ 它画的是**剧情里显示的地点名**，
   不是战斗 / 地图侧的。

**依据是怎么查出来的**（一次性探针，只读，`build/` 下不入库）：
全 ROM 扫 Thumb `BL` 调用点 → 找 `fn 0x0808CD40` 的调用者 → 往前找最近的
`push {..., lr}` 定位函数入口 → 看它调谁。

```
$ python build\_probe_locname_callers.py
locname_reader 0x0808CD40: 1 BL call sites
    caller 0x0808F40C
$ python build\_probe_enclosing_fn.py
0x0808F40C  ->  fn 0x0808F190  (push {r4, r5, r6, r7, lr})   delta=0x27C
$ python build\_probe_f190.py
HIT 0808F40C -> #0x808cd40     ← 地点名表
HIT 0808F588 -> #0x808f4d4     ← 场景派发
```

> ⚠️ **踩过的坑（记下来给下一个接手的人）**：第一次写这个探针时，Thumb `BL` 的位域
> 解码写错了（把**第一个**半字的 imm10 当成第二个半字读、又用错了 S/J1/J2 的位置）
> ⇒ 结果是「0 个调用点」，差点得出「没有调用者」的错误结论。
> 正确的位域：**半字 1** = `11110 S imm10`；**半字 2** = `11 J1 1 J2 imm11`；
> `I1 = NOT(J1 EOR S)`、`I2 = NOT(J2 EOR S)`，
> `offset = SignExtend(S:I1:I2:imm10:imm11:'0')`，`target = PC + 4 + offset`。

### 3.2 台账 N3 要不要补证据？—— **要**，补的是**机器判据**

N3（「id 63 的地址别名是作者**刻意**的布局，不是 bug」）原来只有考证笔记。
本轮登记表闭合时，那两条别名（`0x5a5ab8` / `0x5a5f65`）写进了
`tools/table_registry.py::CONFLICTS`，并且 `tools/alias_audit.py` 会
**从 ROM 重新推导**判据（哪个读者还在读那个基址）⇒ 不再靠人记住。
本轮复验：**5 条判据全 PASS、未裁决冲突 0、失败的判死检验 0**。
⇒ 台账 N3 行补上了这个机器判据的出处。

### 3.3 N5② 的「名字画得对不对」怎么算「对」？

判据不是「画面没冻结」——那是上一轮的判据，它**测不出名字画错**。
本轮用**逐像素**：同一按键序列下原版与转换版逐帧相减 ⇒
差分矩形 `x[40,55] × y[105,119]`、**196** 个差分像素；
原版名字所占的 `x[24,39] × y[105,119]`（16×15）在两张图里**逐字节相同**
⇒「鸣人」**没被重排**、「测试」是**追加**；**框外差分 0**；正文逐字节相同。

### 3.4 F18 的「未闭合的覆盖缺口」那句话为什么要删、又要补什么？

**删**：因为现在**没有未闭合的覆盖缺口**了 —— 14 处补丁**全部**在真实 CPU 上
受控触发验过（**14/14**），档位 **A 5 / B 9 / C 0**（**C = 0** ⇒ 没有「只有静态判定」的）。

**补**（不许含糊）：9 处 B 档所在的**界面**（战斗日志 / 指令菜单的子界面 /
另一种消息框类型）在本轮三条路线 + **144 场战斗全扫**里**一次都没被打开**
⇒ 那是**「界面没被打开」**，**不是「代码没验过」**（代码在真实 CPU 上验过了）。
要补成 A 档，得先找到打开那些界面的按键 —— 这是**产品体验**上的事，不是正确性问题。

---

## 4. 遗留 / 风险（本轮没有解决，也不该由本轮解决）

1. **9 处 B 档的界面没被打开** —— 缺自然触发的截图，不缺正确性证据（见 §3.4）。
2. **「名字画对了」的逐像素判据只跑过开场剧情** —— 战斗 / 命令场景的名字框没用同一套像素判据验过。
3. **全部证据都在 mGBA 上** —— 没在实机 GBA 上验证过。
4. **工作树里还有别的会话的在制品** —— 本轮**没有 `git commit`**，
   上级提交前请逐一核对（`git status` 里 `rom-editor/content/**`、`rom-editor/js/rom.js`、
   `rom-editor/js/editors.js`、`tools/**` 等都不是本轮动的）。
5. **本轮的一次性探针留在 `build/` 下**（不入库）：`_probe_locname_reader.py`、
   `_probe_locname_callers.py`、`_probe_enclosing_fn.py`、`_probe_f190.py`
   —— 只读 `rom/base.gba`，用来定 §3.1 的归属。

---

## 5. 复现

```powershell
cd D:\Github\gba-naruto

# 21 道门禁
Get-ChildItem 'rom-editor\tools' -Filter 'verify_*.mjs' | Sort-Object Name | ForEach-Object {
  $o = node $_.FullName 2>&1 | Select-String -Pattern '全部通过|项失败' | Select-Object -Last 1
  '{0,-38} {1}' -f $_.Name, $o.Line.Trim()
}

# 逐字节不变式（独立重建比对）
node build\verify_byte_identical.mjs            # 全部通过，6,291,456 字节全等

# 登记表 / 别名裁决 / 内容包
python tools\table_registry.py                   # mismatches: 0
python tools\alias_audit.py rom\base.gba         # RESULT: OK
python tools\export_content_pack.py --check      # OK: 内容包与 ROM 一致

# 这一轮的归属探针（只读）
python build\_probe_locname_callers.py
python build\_probe_enclosing_fn.py
python build\_probe_f190.py
```

---

## 6. 相关文件

| 文件 | 作用 |
|---|---|
| `notes/evidence/speaker-names-hypothesis-ledger.md` | **假设台账**（F18 / F18b / F19–F23 / N1–N6 已回填） |
| `notes/evidence/speaker-name-round-summary-20261023.md` | **本轮总览**（新增 §6「这一轮的收尾」） |
| `notes/evidence/speaker-name-fix-20261023.md` | 产品侧落地（§7.3 / §8.1 / §8.4 / §8.6 已更新） |
| `notes/evidence/speaker-name-reader-coverage-20261023.md` | 读者覆盖取证（N5① / F18） |
| `notes/evidence/speaker-name-namebox-verification-20261023.md` | 逐像素名字框（N5②） |
| `notes/evidence/speaker-name-flag-semantics-20261023.md` | 标志位语义（N5③） |
| `notes/evidence/speaker-name-registry-20261023.md` | 登记表 + 保护区（N1 / N2） |
| `notes/evidence/speaker-name-contentpack-20261023.md` | 两张表进内容包（N2） |
| `docs/sequel-roadmap.md` | 「2026-10-23｜ROM 编辑器第十八轮」一节（已补收尾） |
| `docs/handoff-20261023-speaker-names-conversion.md` | §5 改写成「已完成什么 / 还剩什么」 |
