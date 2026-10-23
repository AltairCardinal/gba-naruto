# 说话人全名表 + 地点名表进内容包（N2 的「内容包」那一半） — 2026-10-23

> 承接 `notes/evidence/speaker-names-hypothesis-ledger.md` 的 **N2**：
> 「地点名表与说话人全名表都还没登记进 `tools/table_registry.py` **和内容包**」。
> **登记表那一半**已由另一条支线做完（`notes/evidence/speaker-name-registry-20261023.md`）。
> **本文件负责内容包这一半。**
>
> 本文件是**增量写**的：每查完一条就写一条。

---

## 0. 结论摘要

| 问 | 答 |
|---|---|
| 两张表进内容包了吗？ | **进了**。`rom-editor/content/pack.json` 的 `texts[]` 从 **11 张变 13 张** |
| 逐字节不变式还成立吗？ | **成立**。独立重建一次：**6,291,456 字节全等**，sha256 = `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b` |
| 生成器确定性 | **两次生成逐字节相同**（`pack.json` / `pack.min.json.gz` / `text-index.json.gz` 三个文件都是） |
| 21 道门禁 | **全部「全部通过」**（另加一道新写的独立逐字节验收脚本） |
| 「定长内联槽」这条分支 | 第一次被**真实表格**走到；**写回路径有缺口，已补**（见 §2.3） |
| 地址别名 | **如实建模**（`aliased_with` + `writable_bytes`），改一处会影响另一处的后果**写进了内容包、界面与本文件** |

---

## 1. 要加的两张表

| 表 | 内容包 id | 基址 | 步长 | 条数 | 范围 |
|---|---|---|---|---|---|
| 说话人**全名表** | `speaker_full_names` | `0x5A5AB8` | **19** | **64**（id 0..63） | `0x5A5AB8..0x5A5F77` |
| **地点名表** | `location_names` | `0x5A5F65` | **18** | **55**（id 0..54） | `0x5A5F65..0x5A5F76`（表尾 `0x5A5F77` 与全名表 id 63 的末字节重叠，见 §2.2） |

两张都是**定长内联槽**（`fixed`）：`pointer_offset = null`、`capacity` = 步长、`raw` = 整槽字节。

---

## 2. 第 1 步：先摸清「定长内联槽」这条路径在产品里到底通不通

### 2.1 四种形态的判定（`rom-editor/js/pack.js::textSlotKind()`）

```js
export function textSlotKind(table, record) {
  if (table && table.convert) return 'convertible';
  if (record.pointer_offset !== null && record.pointer_offset !== undefined) return 'pointer';
  const rawLength = record.raw ? base64ToBytes(record.raw).length : -1;
  if (rawLength >= 0 && rawLength === record.capacity) return 'fixed';
  return 'absolute';
}
```

判定顺序：`convert` → `pointer_offset` 有值 → `raw` 长度 == `capacity` → `absolute`。

⇒ **新表落在 `fixed` 上** ✓（`pointer_offset = null`、`raw` 长度 = 步长 = `capacity`）。

### 2.2 两个新发现（比 `speaker-name-id63-20261023.md` 更细）

直读 `rom/base.gba`：

```
=== 说话人全名表 0x5A5AB8 步长 19
  id  0 @ 0x5A5AB8  92599a9a000000000000000000000000000000     ← 「没有」
  id  1 @ 0x5A5ACB  996897cd929894c80000000000000000000000     ← 漩涡鸣人
  id 63 @ 0x5A5F65  92599a9a00000000000000000000000000008a     ← 「没有」+ **末字节 0x8a**
=== 地点名表 0x5A5F65 步长 18
  id  0 @ 0x5A5F65  92599a9a0000000000000000000000000000       ← 「没有」
  id  1 @ 0x5A5F77  8ae2897e8b62954b91740000000000000000       ← 村边的森林（**首字节 0x8a**）
=== 说话人简称表 0x5A57C4 步长 12
  id 63 @ 0x5A5AB8  92599a9a0000000000000000                   ← 「没有」
```

1. **全名表 id 63 的最后一个字节（`0x5A5F77`）是地点名表 id 1 的第一个字形码（`0x8a` = 「村」）。**
   ⇒ 全名表 id 63 的槽（19 字节）与地点名表 id 0 的槽（18 字节）**完全重合**，
   与地点名表 id 1 的槽**重叠 1 字节**。
2. ⇒ **全名表 id 63 的可写长度只有 18 字节**（第 19 字节归地点名表 id 1）。

### 2.3 三个问题，逐个查清

#### Q1：`rom.js::rebuildTextTable()` 对**非 pointer、非 convertible** 的表怎么写回？

**答**：走 `if (!table.relocatable)` 那一支（改前 `rom-editor/js/rom.js:503-546`）：
`text_offset` 为空 ⇒ 报错；`owned_by` 有值 ⇒ 跳过并警告；
容量判定用 `textContentBytes()`（不带槽填充的内容长度）+ NUL ≤ `capacity`；
写回 = `content` + NUL + **把旧文本多出来的尾巴清零**。

**⇒ 缺口 1（真 bug）**：定长槽写回时把尾巴**清零**，
那不是「整槽原样写回」—— 尾巴里可能有**别的表的内容字节**（本例就有：`0x5A5F77`）。

**⇒ 缺口 2（真 bug）**：容量判定用 `capacity`（槽长），不是**可写长度**。
全名表 id 63 的槽长 19、可写 18 ⇒ 写第 19 个字节就会踩掉地点名表 id 1 的「村」。

**⇒ 缺口 3（隐患）**：「有没有改过」拿「正文 + **零填充**」去比。
全名表 id 63 的填充**不是零**（末字节 `0x8a`）⇒ 一个字都没改也会被误判成「改过」。

#### Q2：`parsepack.js::parseTextTable()` 能不能解析「定长内联槽」？

**答：能，通的**（上一轮修过 `fixedSlot` 判定）。

```js
const fixedSlot = kind === 'fixed' || (kind === 'convertible' && !converted);
...
} else if (fixedSlot) {
  const size = record.capacity || 0;
  bytes = rom.slice(record.text_offset, record.text_offset + size);   // 整槽
  record.pointer = null;
}
```

- `capacity` **不被重算**（保持 = 步长）✓
- `raw` = **整槽**（内容 + NUL + 填充）✓
- `text` 由 `scanTokens(bytes)` 解出 —— `scanTokens` 遇 `0x00` 就停（`textcodec.js:165`）⇒ **填充不会混进文本** ✓

⇒ **解析这条路一个字都没改**（`parsepack.js` 未动）。
证据：`verify_load_flow.mjs` 的「**13 张文本表整表 JSON 相同（解析没有改动任何一格）**」绿。

#### Q3：`editors.js` 里 `fixed` 分支的「写回规则 / 角标 / 超长当场拦」能不能跑？

**答：能跑，但有两处对 `fixed` 不准**：

| 位置 | 现状 | 问题 |
|---|---|---|
| `editors.js` 写回规则 | 「定长内联槽（等长）」 | ✓ 正确（本轮补上「整槽原样」这句） |
| `editors.js` 角标 / 超长当场拦 | 拿 `record.capacity` 判 | ⚠️ 对**别名**记录不准：可写长度可能比槽长短 ⇒ 界面说「放得下」，构建却报错 |
| `editors.js` 角标 | `shared_with`（**同表**共用） | ⚠️ **跨表**共用（同址但不同表）没有标记 ⇒ 用户看不出「改一处会动另一张表」 |

### 2.4 第 1 步的判定

> **「定长内联槽」这条路径：解析通、写回有缺口、界面提示对别名不准。**
>
> ⇒ 本轮补：**整槽原样写回** + **按可写长度判超长** + **别名如实建模** + **跨表抢字节时报错**。

---

## 3. 地址别名：建模方案与「改一处会影响另一处」的后果

### 3.1 别名事实

| 身份 | 地址 | 槽长 | 内容区（到 NUL 为止） |
|---|---|---|---|
| 说话人**简称**表 id 63 | `0x5A5AB8` | 12 | `[0x5A5AB8, 0x5A5ABD)` |
| 说话人**全名**表 id 0 | `0x5A5AB8` | 19 | `[0x5A5AB8, 0x5A5ABD)` ← **同一段内容** |
| 说话人**全名**表 id 63 | `0x5A5F65` | 19 | `[0x5A5F65, 0x5A5F6A)` |
| **地点名**表 id 0 | `0x5A5F65` | 18 | `[0x5A5F65, 0x5A5F6A)` ← **同一段内容** |
| **地点名**表 id 1 | `0x5A5F77` | 18 | `[0x5A5F77, 0x5A5F81)` ← **落在全名表 id 63 的槽里** |

### 3.2 内容包里的建模（新增两个字段）

| 字段 | 含义 | 实测到的值 |
|---|---|---|
| `aliased_with` | **跨表**共用同一段字节的其它记录（`"表id#记录id"`） | 简称表#63 ≡ 全名表#0；全名表#63 ≡ 地点名表#0 |
| `writable_bytes` | 这条记录**可以写**的字节数（≤ `capacity`）；缺省 = `capacity` | 只有**全名表 id 63** = **18**（槽长 19） |

**为什么 `aliased_with` 要单独一个字段**：`shared_with` 在整个仓库里的语义是
「**本表**内共用同一段字节的记录 id 列表」（`editors.js` 明写「本表 #…」），
格式与用途都不同 ⇒ 不改它，另开一个字段。

### 3.3 「改一处会影响另一处」的后果（**本节就是那条后果**）

| 情形 | 后果 |
|---|---|
| 改**全名表 id 0**（`0x5A5AB8`） | 同一批字节也被**简称表 id 63** 读到 ⇒ **简称表那一格的内容跟着变**（除非简称表被转换走） |
| 改**简称表 id 63**（`0x5A5AB8`） | 简称表一旦被改动就**整张表转换成指针表 + 串池** ⇒ 这一格搬走 ⇒ **与全名表 id 0 解耦**；两处可以各写各的 |
| 改**全名表 id 63** 或**地点名表 id 0**（`0x5A5F65`） | 两者**共用**那段字节 ⇒ **改一个，另一个跟着变**；包里那一格的**值会过期**（门禁 11d 把这条写成了断言） |
| 改**全名表 id 63**（写到第 19 字节） | 会**踩掉地点名表 id 1 的第一个字**（`0x8a` = 「村」）⇒ 用 `writable_bytes = 18` **拦掉**（构建报错，ROM 一个字节都不动） |
| **两处**都改成**不同的**字 | **后写的覆盖先写的 ⇒ 有一处改动凭空消失** ⇒ 本轮新增的**跨表抢字节检查**把它**报出来**（构建报错，不让它悄悄发生） |

---

## 4. 本轮改动清单

### 4.1 生成器（`tools/export_content_pack.py`）

| 改动 | 位置 |
|---|---|
| 新增 6 个常量（两张表的基址/步长/条数）+ 别名说明注释 | `SPEAKER_FULL_NAME_*` / `LOCATION_NAME_*` |
| `build_inline_text_table()` 加 `id_prefix` 参数（原来硬编码「说话人{i}」） | 该函数签名 |
| **新增两张表**（`speaker_full_names` / `location_names`），说明里写清步长、条数、读者、地址别名与「改一处会影响另一处」 | `build_text_tables()` |
| **新增 `annotate_slot_aliases()`**：算出 `aliased_with` 与 `writable_bytes` | 新函数 |
| 调用它（放在 `shared_with` 之后） | `build_pack()` |
| **修过时的登记说明**：不再说 registry「把它登记成『调色板源表』」，改成「规范名是 `speaker_short_name_table`，旧名只作别名条目留着」 | `speaker_names` 的 note |
| **修另一处同类过时说明**：顶层 `notes` 里「文本表分两类」→ 四种形态 | `build_pack()` 的 `notes` |

### 4.2 产品代码

| 文件 | 改动 |
|---|---|
| `rom-editor/js/rom.js` | ① 新增 `textContent()`；② 定长槽的「有没有改过」改比**正文**；③ 新增 `inlineWriteClaims()` / `fixedSlotBytes()` —— **整槽原样写回**（填充保留）；④ 容量判定改用 `writable_bytes`；⑤ 新增 `checkTextWriteConflicts()` —— 两张表抢同一段字节且内容不同 ⇒ **构建报错** |
| `rom-editor/js/editors.js` | ① 角标：新增「别名 ×N」（`aliased_with`）；② 详情面板新增「地址别名」说明卡；③ 超长当场拦与角标都改用 `writable_bytes`；④ 「写回规则」补上「整槽原样」 |
| `rom-editor/js/parsepack.js` | **未改**（解析这条路本来就是通的） |

### 4.3 门禁

| 文件 | 改动 |
|---|---|
| `rom-editor/tools/verify_pack.mjs` | **新增第 11 节**（定长内联槽的写回规则，8 条断言 + 1 条变异对照）；§11 引入 `RomBuilder` 与 `textSlotKind` |
| `rom-editor/tools/verify_variable_text.mjs` | §11 的表数 11 → **13**；「没有定长内联槽形态的表了」改成「**2 张**是定长内联槽」；「变长被拒」改成「**放不下**被拒」并让改动**真的放不下**（原来第一条记录只有 4 字节，加两个字反而放得下 ⇒ 测不到超长） |
| `rom-editor/tools/verify_load_flow.mjs` | 文案 11 张 → **13 张**（断言本身是通用的，没改判据） |
| `rom-editor/tools/verify_views.mjs` | 更新注释：内容包里**现在真的有 2 张 `fixed`**（断言没改） |

### 4.4 重新生成的产物

| 文件 | 说明 |
|---|---|
| `rom-editor/content/pack.json` | 13 张文本表（11 → 13） |
| `rom-editor/content/pack.min.json.gz` | 同一个脚本用确定性 gzip（`mtime=0`）写出 |
| `rom-editor/content/text-index.json.gz` | **顺带重生成**（见 §6.1） |
| `notes/evidence/consumer-evidence.json` | 由 `python tools/consumer_locate.py rom/base.gba --all --evidence …` 重新生成：旧名 `palette_source_table` → `speaker_short_name_table`，并新增两张新表（3 个 / 1 个读者） |

**内容包 diff 是最小的**（逐表逐记录对比 `git show HEAD:rom-editor/content/pack.json`）：

```
speaker_names: record 63.aliased_with changed | field note changed
顶层：texts / notes
```

⇒ **其它 10 张表与所有其它记录逐字段完全相同** ✓

---

## 5. 验证结果

### 5.1 21 道门禁全绿

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
verify_speaker_conversion.mjs          全部通过（47 条断言）
verify_syntax.mjs                      全部通过（75 个文件）
verify_variable_text.mjs               全部通过（84 条断言）
verify_views.mjs                       全部通过
verify_wording.mjs                     全部通过
```

### 5.2 逐字节不变式（**独立**验收，`build/verify_byte_identical.mjs`）

```
原版 ROM sha256 : 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b

1) 内容包（13 张文本表，不带全 ROM 文本索引）
  [PASS] 构建无错误 / 长度一致 / sha256 一致 / 逐字节比较无差异 — 6,291,456 字节全等
  报告: 文本表 13（改动 0）/ 结构 116（改动 0）/ 补丁 0
2) 内容包 + 全 ROM 文本索引（14 张文本表）
  [PASS] 构建无错误 / 长度一致 / sha256 一致 / 逐字节比较无差异 — 6,291,456 字节全等
  [PASS] 说话人全名表（0x5a5ab8 起 1216 字节）逐字节未动
  [PASS] 地点名表（0x5a5f65 起 990 字节）逐字节未动
  [PASS] 说话人简称表（0x5a57c4 起 768 字节）逐字节未动
```

### 5.3 生成器确定性（跑两次，逐字节相同）

```
rom-editor/content/pack.json               IDENTICAL  47738781A6713ECA…
rom-editor/content/pack.min.json.gz        IDENTICAL  5EE50D0873535FA9…
rom-editor/content/text-index.json.gz      IDENTICAL  05BD5EEE45CC7811…
```

`python tools/export_content_pack.py --check --no-rom --no-text-index` ⇒ `OK: 内容包与 ROM 一致`（exit 0）。

### 5.4 新写的门禁（`verify_pack.mjs` 第 11 节）

```
11) 定长内联槽：两张新表进包后的写回规则（整槽原样 / 放不下就拒 / 别名不抢字节）
  [PASS] 说话人全名表在包里（64 条 × 19 字节定长内联槽）
  [PASS] 地点名表在包里（55 条 × 18 字节定长内联槽）
  [PASS] 三处「没有」的地址别名已如实建模（aliased_with）
  [PASS] 全名表 id 63 的第 19 字节是地点名表 id 1 的第一个字形码 — 0x5a5f77 = 0x8a，可写长度 18/19
  [PASS] 定长槽写回是「整槽原样」（填充与别人的字节一个都没动）
  [PASS] 地点名表 id 1 仍读得出「村边的森林」（没被邻居的改动踩坏）
  [PASS] 共用同一段字节的两张表确实一起变了（改一处会影响另一处）
  [PASS] 超过可写长度的改动被构建器拒绝（ROM 一个字节都没动）
  [PASS] 两处别名改成不同的字时构建器报错（不悄悄丢一处）
  [PASS] 变异对照：旧写法（清零尾巴）会抹掉别人的字节 —— 11d 的断言不是空转
```

**变异对照**（证明断言有牙齿）：把 `inlineWriteClaims` 猴补丁成旧行为（清零尾巴），
`0x5A5F77` 立刻变成 `0x00`（原 `0x8a`）⇒ 11d 的断言能发现。

---

## 6. 遗留 / 移交

### 6.1 顺带重生成的文件（超出任务书列的三项）

`rom-editor/content/text-index.json.gz`（全 ROM 文本索引）**也重生成了一���**。

**为什么必须一起重生成**：文本索引给每条字符串标 `owned_by`（这段字节归哪张表），
构建时**跳过**标了 `owned_by` 的记录 ⇒ 「一个字节一个归属」。
两张新表进包之前，`0x5A5ACB`（全名表 id 1）、`0x5A5F65`（地点名表 id 0）这些地址
在文本索引里**没有归属** ⇒ 同一段字节会有**两个可写的主张者**。
重生成之后，119 条新记录全部带上了 `owned_by`
（全名表 64 条 + 地点名表 55 条，逐条核对过）。

### 6.2 不在本任务所有权内、但发现过时的地方（**没改**）

| 位置 | 过时内容 |
|---|---|
| `rom-editor/js/modules/common.js:16` | 「11 张表里 9 张是指针表驱动的」—— 现在是 **13 张 / 10 张**；且「`battle_objectives` 是绝对地址引用」也早已过时（它现在是指针槽） |
| `rom-editor/js/modules/story.js:76,80` | 域首页的说明文字仍写「定长内联槽（说话人名表）……只能等长改写」（说话人名表早已可转换）；`texts:` 列表里**没有**两张新表 |

⇒ 两张新表**在界面里仍然可达**：`app.js` 的「**全部文本表（点击进入编辑）**」
总表列的是 `pack.texts` 全集 ⇒ 概览页点进去就能编辑；
`lengthStrategyLabel()` 会把它们标成「定长内联槽（等长）」。
但「剧情」域首页的说明文字过时、且没把新表列进该域的 `texts:` 清单 ——
那属于 `modules/` 的所有者。

### 6.3 台账

`notes/evidence/speaker-names-hypothesis-ledger.md` 的 **N2** 现在只剩「登记表」那一半
由另一条支线闭合；**「内容包」这一半已闭合**（本文件）。
台账本身按分工**没动**（由台账负责人更新状态）。
