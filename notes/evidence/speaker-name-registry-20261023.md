# 说话人名表登记表闭合 + 保护区扩到「两张表」 — 2026-10-23

**范围**：台账 `notes/evidence/speaker-names-hypothesis-ledger.md` 的
**N1（保护区）** 与 **N2（登记表）**的「登记表」那一半。
**ROM**：`rom/base.gba`（SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`，6 MiB）
**ROM 地址 = 文件偏移 + 0x08000000**
**上游考证**：`notes/evidence/speaker-name-id63-20261023.md`（id 63 与三处「没有」）、`notes/evidence/speaker-name-table-20261023.md`（12 个取名读者）

**改动文件**（共 5 个，全部在本任务所有权内）：

| 文件 | 改了什么 |
|---|---|
| `tools/table_registry.py` | 修正 `0x5A57C4` 的**误分类登记**、新增两张表、两条地址别名的 `CONFLICTS` 裁决 |
| `tools/data/speaker_name_code_patches.json` | `table` 段的保护区从「全名表」扩到「全名表 + 地点名表」（只改保护区字段与 note） |
| `rom-editor/tools/verify_speaker_conversion.mjs` | 第 5 段的保护区断言扩成「两张表合起来逐字节未动」+ 有牙齿的变异对照 |
| `tools/consumer_locate.py` | `AUDIT_TABLES` 里旧名改成规范名，并补两张新表 |
| `tools/probe_orphan_bytes.mjs` | 报告里引用的旧名改成规范名 |

---

## 0. 结论摘要

| 问 | 答 |
|---|---|
| 登记表里 `0x5A57C4` 的旧登记（「调色板源表」）对吗？ | **错**。它是**说话人简称表**（每条 12 字节的字形码串）。旧名保留成**别名条目**（`verified=False`），说明里写清它其实是简称表 |
| 全名表 / 地点名表登记了吗？ | **登记了**：`speaker_full_name_table` (0x5A5AB8)、`location_name_table` (0x5A5F65)，均 `verified=True` |
| 地址别名被藏起来了吗？ | **没有**。两条别名写进 `CONFLICTS`（`0x5a5ab8` / `0x5a5f65`），判据由 `tools/alias_audit.py` **从 ROM 重新推导**，5 条检查全 PASS |
| 保护区覆盖到地点名表了吗？ | **覆盖了**：`0x085A5AB8..0x085A5F78` → `0x085A5AB8..0x085A6343`（= 两张表的**并集**，2187 字节） |
| 保护区断言有牙齿吗？ | **有**。清单侧、门禁侧各做一次「写小一个字节」的变异 → **都变红**（§5.3） |
| 21 道门禁还全绿吗？ | **全绿**（§5.2） |

---

## 1. 三张表的事实（本次**从 ROM 重新核对**，不照抄上游笔记）

| 表 | 基址（文件偏移） | 步长 | 条数 | 占的字节 | 原生读者 |
|---|---|---|---|---|---|
| 说话人**简称**表 | `0x5A57C4` | 12 | **63**（id 0..62） | `0x5A57C4..0x5A5AB7` | **12**（全是取名读者） |
| 说话人**全名**表 | `0x5A5AB8` | 19 | **64**（id 0..63） | `0x5A5AB8..0x5A5F77` | 3（`0x08077EE2` / `0x0808B036` / `0x080939D6`） |
| **地点**名表 | `0x5A5F65` | 18 | **55**（id 0..54） | `0x5A5F65..0x5A6342` | 1（`0x0808CD8E`） |

核对方法（可复跑）：

```powershell
python tools\consumer_locate.py rom/base.gba --target 0x085A5AB8   # 3 个读者，步长 19
python tools\consumer_locate.py rom/base.gba --target 0x085A5F65   # 1 个读者，步长 18
python tools\consumer_locate.py rom/base.gba --target 0x085A57C4   # 12 个读者，步长 12
python tools\probe_speaker_id63.py --section b                     # 两张表逐条解码 + 别名判定
```

字节级核对（本次用一次性 Python 片段做的，结果已写进 §2/§3 的说明里）：

```
loc id 0  @0x5A5F65  92 59 9a 9a 00 00 …        '没有'
loc id 54 @0x5A6331  99 e3 90 d3 90 aa 92 85 00 …  ← 末字节 0x5A6342
0x5A6343 起                00 32 00 38 50 0d …  ← 已是指针数据，不是名字
full id 63 @0x5A5F65  92 59 9a 9a 00 … 00 8a    ← 末字节 0x8a = 地点名 id 1「村」的首字形
```

⇒ **地点名表的最后一个字节是 `0x5A6342`**（id 54 的填充），**表尾（不含端）是 `0x5A6343`**。
全名表：64 × 19 = 1216 字节 ⇒ `0x5A5AB8..0x5A5F77`，**表尾 `0x5A5F78`**。

---

## 2. 登记表改动（`tools/table_registry.py`）

### 2.1 修正误分类（`0x5A57C4`）

**旧**（错）：

```python
"palette_source_table": (0x5A57C4, True,
                         "调色板源表 12 字节/条（每条 = 一个 u32 色值 + 8 字节 0）；"
                         "12 个原生读者；正好接在头像表 0x5A4DEC + 63*40 之后"),
```

**新**（规范名 + 正确的说明）：

```python
"speaker_short_name_table": (0x5A57C4, True,
    "说话人简称表 12 字节/条（每条 = 最多 5 个双字节字形码 + NUL + 填充）；"
    "ROM 里实存 63 条（id 0..62）；id 63 那一格没有自己的字节，"
    "它借用全名表 id 0 的存储（0x5A57C4 + 63*12 = 0x5A5AB8，"
    "见 CONFLICTS['0x5a5ab8']）；12 个原生读者全是取名读者（…12 个地址…，步长 12，机器验证）；"
    "正好接在头像表 0x5A4DEC + 63*40 之后"),
```

顺带修正 `portrait_table` 说明里同一张表的旧数字：「最多 **3** 个双字节字形码」→「最多 **5** 个」
（12 字节槽装得下 5 个双字节字形码 = 10 字节 + NUL + 1 字节填充；ROM 上 `大蛇　头` 就是 5 个），
并在同一条说明里点明「那张表的规范名是 `speaker_short_name_table`，它不是『调色板源表』」。

### 2.2 新登记的两张表

```python
"speaker_full_name_table": (0x5A5AB8, True, "…19 字节/条，64 条（id 0..63），占 0x5A5AB8..0x5A5F77…"
                             "**地址别名**：id 0 与说话人简称表 id 63 同址（0x5A5AB8）；"
                             "id 63 与地点名表 id 0 同址（0x5A5F65）"),
"location_name_table": (0x5A5F65, True, "…18 字节/条，55 条（id 0..54），占 0x5A5F65..0x5A6342…"
                         "**地址别名**：id 0 与说话人全名表 id 63 同址（0x5A5F65）"),
```

两条说明里都写明了**与别的表地址重叠**这件事，并指向对应的 `CONFLICTS` 键。

### 2.3 旧名保留成**别名条目**（不是删掉）

历史文档（`notes/evidence/content-pack-export-20261021.md` 等）和外部引用都还写着
`palette_source_table`；直接删掉会让这些引用悬空。因此在「adjudicated legacy banks」段里保留：

```python
"palette_source_table": (0x5A57C4, False,
    "已裁决（2026-10-23）：**别名**，不是调色板源表。0x5A57C4 起是『说话人简称表』—— "
    "每条 12 字节的字形码串（最多 5 个双字节字形码 + NUL + 填充），"
    "**不是**「一个 u32 色值 + 8 字节 0」；那 12 个原生读者**全是取名读者**。"
    "规范名见 speaker_short_name_table；依据 notes/evidence/speaker-name-table-20261023.md"),
```

`verified=False`（沿用仓库对「旧名/错名」的既有惯例：`legacy_menu_ui`、`legacy_resource_pointers` 等
都是 `verified=False` + 裁决说明 + 指向规范名），所以它**不会**被
`build/content_pack_gaps.py` 算成内容包缺口。

### 2.4 全仓库旧名引用的处置（「一处不漏」）

| 位置 | 处置 |
|---|---|
| `tools/table_registry.py` | 规范名 + 别名条目（**故意保留**，见 §2.3） |
| `tools/consumer_locate.py` (`AUDIT_TABLES`) | 改成 `speaker_short_name_table`，并补 `speaker_full_name_table` / `location_name_table` |
| `tools/probe_orphan_bytes.mjs` | 报告里的表名改成 `speaker_short_name_table` |
| `notes/evidence/consumer-evidence.json` | **不动**：它是 `consumer_locate.py` 的**生成产物**（历史快照），本任务不碰 `notes/evidence/*` |
| `notes/evidence/content-pack-export-20261021.md` | **不动**：历史考证记录，且它描述的正是「旧登记是误分类」这件事 |
| `notes/evidence/speaker-name-table-20261023.md` | **不动**：就是指出旧登记错的那份考证 |

---

## 3. 地址别名的裁定（`CONFLICTS`）

**没有藏起来。** 两处别名写进 `tools/table_registry.py::CONFLICTS`：

| 键 | 冲突双方 | 裁定 |
|---|---|---|
| `0x5a5ab8` | `speaker_short_name_table` ↔ `speaker_full_name_table` | `merge` / `base_status=native-reader-alias` / canonical = 全名表 |
| `0x5a5f65` | `speaker_full_name_table` ↔ `location_name_table` | `merge` / `base_status=native-reader-alias` / canonical = 地点名表 |

每条都带 `dispositions`（谁拥有哪些字节）、`evidence`（为什么是别名而不是 bug）、
`falsifiable_test`（什么情况下这条裁决作废）、`checks`（**机器判据**）。

### 3.1 机器判据（由 `tools/alias_audit.py` 从 ROM 重新推导）

```
=== 0x5a5ab8  [merge] banks: speaker_short_name_table, speaker_full_name_table
    消费者 0x5a5ab8     3 个原生读者
        0x08077EE2  fn 0x08077C90  ldr r1, [pc, #0x19c]
        0x0808B036  fn 0x0808AFE0  ldr r1, [pc, #0x4c]
        0x080939D6  fn 0x08093818  ldr r1, [pc, #0x280]
    [PASS] reader 0x5A57C4  0x5A57C4 至少要有 12 个原生读者，实际 12 个
    [PASS] reader 0x5A5AB8  0x0808B036 必须读 0x085A5AB8
    [PASS] reader 0x5A5AB8  0x080939D6 必须读 0x085A5AB8

=== 0x5a5f65  [merge] banks: speaker_full_name_table, location_name_table
    消费者 0x5a5f65     1 个原生读者
        0x0808CD8E  fn 0x0808CD40  ldr r0, [pc, #0xa0]
    [PASS] reader 0x5A5F65  0x0808CD8E 必须读 0x085A5F65
    [PASS] reader 0x5A5AB8  0x085A5AB8 至少要有 3 个原生读者，实际 3 个

未裁决冲突: 0
失败的判死检验: 0
RESULT: OK
```

`alias_audit.py` 会把**不是**同址冲突的 `CONFLICTS` 条目也一并复核（§「非同址冲突…一并复核」），
所以这两条**不会烂掉**：哪个读者不再读那个基址，检查立刻失败。

### 3.2 为什么 `table_registry.py` 自己没报「冲突」

`verify_table_bases()` 的同址冲突是**从 32 个内容 bank 的 `table_offset` 推出来的**，
而**没有任何 bank 声明 0x5A5AB8 / 0x5A5F65 / 0x5A57C4**（`sequel/content/*/bank.json` 里
离这片最近的都在别处）。所以登记表自检**不会**打印这两行 —— 别名不是 bank 之间的碰撞，
而是**三张表之间的存储别名**，它的落点就是 `CONFLICTS`（§3.1 的 5 条机器判据）。
登记表自检输出仍然是 `mismatches: 0`、exit 0。

---

## 4. 保护区扩展（`tools/data/speaker_name_code_patches.json`）

### 4.1 口径：`[start, end)`（不含 end）

旧值 `['0x085A5AB8','0x085A5F78']` 就是这个口径的证据：
`0x5A5AB8 + 64*19 = 0x5A5F78` —— 正好是全名表 64 条的**表尾（不含端）**，
也正好是 `notes/evidence/speaker-name-id63-20261023.md` 里写的「保护区与全名表完全吻合」。

### 4.2 **一处 off-by-one 的更正（与任务书写的数字差 1 字节）**

任务书写的是 `['0x085A5AB8','0x085A6342']`。按上面的 `[start, end)` 口径，
这会**漏掉地点名表 id 54 的最后一个字节**（`0x5A6342`）：

* 地点名表 55 条 × 18 字节 = 990 字节 ⇒ `0x5A5F65..0x5A6342`（**含** `0x5A6342`），
  表尾（不含端）= `0x5A6343`；
* ROM 上 `0x5A6343` 起已经是指针数据（`00 32 00 38 50 0d …`），不是名字 —— 佐证表尾就在这。

⇒ **实际写入清单的值是 `0x085A6343` / `0x5A6343`**，并在 `protected_note` 里把
「地点名表占 `0x085A5F65..0x085A6342`（含末字节）」这句话**原文写出来**，口径差异可查。
保护区的**并集**因此是 `0x085A5AB8..0x085A6342`（含末字节）= **2187 字节**
= 全名表 1216 + 地点名表 990 − 重叠 19。

### 4.3 `protected_note` 写了什么

* 保护区 = **两张表**的并集（原来只覆盖全名表），各自的步长/条数/占位/读者；
* 两张表在 `0x085A5F65..0x085A5F77` 这 **19 字节上重叠**（全名表 id 63 = 地点名表 id 0）；
* **地址别名**关系：简称表 id 63 ≡ 全名表 id 0（`0x085A5AB8`）、全名表 id 63 ≡ 地点名表 id 0（`0x085A5F65`），
  三处「没有」共用同一批字节 `92 59 9a 9a 00` + 零填充；
* 新指针表只占 `0x085A57C4..0x085A58C3`，与保护区不相交（还差 500 字节空隙）；
  14 处代码补丁也都不落在保护区内。

---

## 5. 门禁与变异证据

### 5.1 门禁第 5 段现在断什么

`rom-editor/tools/verify_speaker_conversion.mjs` 第 5 段（**只改这一段**）：

1. **清单里的保护区 = 两张表的并集**（不多不少）—— 清单来自
   `tools/data/speaker_name_code_patches.json`，门禁自己算并集，两边必须完全相等；
2. **两张表合起来（并集，2187 字节）逐字节未动**；
3. **变异对照 ×2**：故意改掉保护区**首字节**、**末字节**，比较必须能发现 ⇒
   证明第 2 条不是空转（转换本来就不写保护区，范围写错它也会绿）；
4. **两端锚点**：首字节必须是「没有」`92 59 9a 9a 00`（全名表 id 0 = 简称表 id 63），
   末字节必须是地点名表 id 54 的填充 `00` ⇒ 保护区边界不是随便一段。

### 5.2 跑出来的结果

```
$ node rom-editor\tools\verify_speaker_conversion.mjs
5) 保护区：**说话人全名表 + 地点名表**两张表合起来逐字节未动
  [PASS] 清单里的保护区 = 两张表的并集（0x5A5AB8..0x5A6343，2187 字节） — 清单 0x5A5AB8..0x5A6343
  [PASS] 0x5A5AB8..0x5A6342（2187 字节）逐字节相同
  [PASS] 变异对照：保护区**首字节**被改 ⇒ 比较能发现（断言不是空转）
  [PASS] 变异对照：保护区**末字节**被改 ⇒ 比较能发现（断言不是空转）
  [PASS] 保护区首字节 = 「没有」（92 59 9a 9a 00）—— 全名表 id 0 = 简称表 id 63 — 92599a9a00
  [PASS] 保护区末字节 = 地点名表 id 54 的填充 0x00 — 00
…
全部通过（47 条断言）
EXIT=0
```

21 道门禁：

```
$ Get-ChildItem 'rom-editor\tools' -Filter 'verify_*.mjs' | ForEach-Object { … }
绿: verify_audio_workbench.mjs :: 全部通过
…（共 21 个，全绿）
红数 = 0
```

### 5.3 变异证据（**「写小一个字节 ⇒ 变红」**）

做法：把门禁**复制**成临时文件（`rom-editor/tools/_tmp_mut{1,2}_verify.mjs`），
在里面改一处，跑完立刻删（**仓库文件零改动**，事后 `git status` 已确认干净）。

| 变异 | 改了什么 | 结果 |
|---|---|---|
| mut1 | **清单**里的保护区写小一个字节（`0x5A6342`） | **EXIT=1**：`[FAIL] 清单里的保护区 = 两张表的并集（0x5A5AB8..0x5A6343，2187 字节） — 清单 0x5A5AB8..0x5A6342` |
| mut2 | 门禁自己的**地点名表范围**写小一个字节（`hi: 0x5a6342`） | **EXIT=1**：`[FAIL] 清单里的保护区 = 两张表的并集（0x5A5AB8..0x5A6342，2186 字节） — 清单 0x5A5AB8..0x5A6343` |

⇒ 保护区范围无论从**清单**侧还是**门禁**侧被写小一个字节，断言立刻变红。

### 5.4 其它受影响的检查（都绿）

```
$ python tools\table_registry.py            → EXIT=0（mismatches: 0）
$ python tools\alias_audit.py rom/base.gba   → EXIT=0（RESULT: OK，失败的判死检验: 0）
$ python tools\completion_audit.py           → EXIT=0
$ python -m unittest tests.test_process_improvements → Ran 14 tests … OK
$ python tools\export_content_pack.py --check → EXIT=0（内容包没被这次改动带偏）
```

---

## 6. 残留 / 移交（不在本任务所有权内）

1. **内容包里的那句话过时了**：`tools/export_content_pack.py` 生成的 `speaker_names` 说明里写着
   「`tools/table_registry.py` 把它登记成『调色板源表』……那一处登记是误分类」。
   登记表现在**已经**改成「说话人简称表」（旧名只作为别名条目留着），所以这句话指向的旧状态不再成立。
   **本任务没有改它**，因为改了生成器就得同步重生成 `rom-editor/content/pack.json`，
   而内容包**不在本任务所有权内**（且 `export_content_pack.py --check` 现在是绿的）。
   ⇒ 交给内容包那一半的负责人：把那句改成「registry 的规范名是 `speaker_short_name_table`」。
2. **内容包缺口**：`build/content_pack_gaps.py` 现在把三张表都报成「VERIFIED registry tables NOT in the pack」
   （`speaker_short_name_table` / `speaker_full_name_table` / `location_name_table`）。
   这是**如实反映**现状 —— 内容包里只有内联形态的 `speaker_names`，全名表与地点名表还没进包（N2 的另一半）。
3. `notes/evidence/consumer-evidence.json` 里的表名仍是旧名：它是 `consumer_locate.py` 的**生成产物**，
   本次没有重生成（重生成会改动 `notes/evidence/*`）。下次重生成时会自动变成规范名。
4. `notes/evidence/speaker-names-hypothesis-ledger.md` 里 N1/N2 的状态**没有改**（本任务不碰台账本身），
   请台账负责人按本文件更新 N1/N2 的「已闭合」标记。
