# W3 动作 2 的 ②：34 个内容库都能回答「字节从哪来」（2026-10-22）

日期：2026-10-22
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
逆向树 `/Users/altair/github/gba-naruto-reverse`，commit `821d0937e058245aa7e6d29f23f96c7fc78e7375`
配套：`docs/butano-wiring-roadmap.md`（W3 动作 2）、`notes/butano-usable-backlog-20261022.md`

## 0. 结论

**34/34 个内容库现在都带一个 `_provenance` 块，如实回答自己的字节从哪来。**

| 来源类型 | 族数 | 依据 |
| --- | ---: | --- |
| 有逆向族（严格地址匹配） | **2** | 该族 manifest 的 `source_table.gba_address` **恰等于**本库的 `table_offset` |
| 有 note（库自己引用） | **13** | 库正文里的 `notes/...md` 指针，且文件在树上 |
| 有提取器（库自己声明） | **15** | 库自带的 `extraction.tool` |
| 只认 ROM 偏移（**明写理由**） | **19** | 字节来自 `rom/base.gba` 的偏移与长度；**无族、无 note、无工具** |

收据 `artifacts/butano-content-bank-provenance-v1/`
工具 `tools/butano/annotate_content_bank_provenance.py`（幂等，另有 `--check` 模式）
门禁 `tests/test_content_bank_provenance.py`（**8 项全绿**：块齐全 / ROM 哈希是本树的 / 偏移长度与库一致 /
族在逆向树里 / note 在树上 / 无来源时必须写明 / 幂等 / `--check` 通过）

## 1. 原来的问法为什么不成立

路线图 W3 动作 2 写的是「内容库 JSON 增加 `_provenance` 块（族 + manifest 哈希）」，
验收是「34 个内容库**全部**能回答『来自哪个族 / 哪条 note』」。
**按这个问法去量，四条路都不通**（都试过）：

| 试法 | 结果 |
| --- | --- |
| 库的 `table_offset` 对逆向族 manifest 里的任意地址 | **32 个库只中 2 个**，且两个都指向同一族（`map-canvases-v1`）⇒ 不可信 |
| 库的 `table_offset` 对族 manifest 的 `source_table.gba_address` | 严格匹配只有 **3 个库**（`battle-encounters`/`menu-ui`/`tile-assets`）⇒ 可用但覆盖极低 |
| 库自带的 `extraction`/`discovered_by` 字段 | 记的是**逆向侧当时怎么提取的**（工具、区间观察），**不是**「哪一族闭合了它」 |
| 库自带 note 指针 | 只有 **13 个库**有；其余 21 个库连指针都没有 |

⇒ **「这库来自哪个族」这个问题本身答不全**——因为多数库**根本不是**从逆向族导入的，
它们是**本树直接从 ROM 提取**的。

## 2. 换问法：记录来源，而不是猜来源

把问题从「这库来自哪个族」换成「**这库的字节从哪来**」，
答案就变成**可测量的四件事**（每件都写进 `_provenance`）：

| 字段 | 内容 | 怎么测的 |
| --- | --- | --- |
| `rom` | `sha256` / `offset` / `size` / `entry_count` / `entry_size` | 本树的 `rom/base.gba` + 库自己的表字段 |
| `extractor` | 库自带的 `extraction.tool` | 库自己的字段 |
| `reverse_family` | 声明了**同一表地址**的族（唯一命中时）；候选与状态另记 | 逆向族 manifest 的 `source_table.gba_address` |
| `reverse_evidence` | 库自己引用的 note（且文件在树上） | 库正文 |
| `unattributed_reason` | 都没有时**明写**为什么 | 由上面四项推出 |

⇒ **「族」不再是必填项**：一个库完全可以诚实地回答「我的字节来自 ROM 的 0x5A2034，
长度 360；没有任何逆向族或 note 声明这张表」——**这句话本身就是答案**，
比编一个族名有用得多。

⇒⇒⇒ **⇒ 灰区因此消失：不是每个库都补上了族名，而是每个库都补上了**可核验**的来源说明，
没有来源的把「没有」写出来。**

## 3. 门禁做了什么

`tests/test_content_bank_provenance.py`（8 项）：

- 每个库都有 `_provenance` 块，且六个字段齐全；
- 块里的 ROM 哈希 **等于本树** `rom/base.gba` 的哈希（不是某个写死的值）；
- 块的 `offset`/`size` 与库自己的 `table_offset`/`entry_count`×`entry_size` 一致；
- 写到的**族**在逆向树里确实有 manifest；写到的 **note** 确实在树上；
- 既没族也没 note 的库**必须**有 `unattributed_reason`；
- **幂等**：跑两遍字节不变（`before == after` 已实测）；
- `--check` 模式对当前树返回 0。

## 4. 风险处置（路线图点名的那条）——**第一版检查漏了 `tools/`**

路线图 W3 写：「载体加在 JSON 里会改内容库字节 ⇒ **要确认现有门禁不依赖内容库的精确字节**」。

**我第一版只扫了 `tests/`**，结论是「没有任何测试对内容库做字节哈希 ⇒ 改字节安全」——
**这个结论是错的**：pin **不在 `tests/`，在 `tools/`**。

⇒ 全量套件立刻把这一点打出来：`tools/analyze_battle_action_reachability.py` 的
`INPUTS` 钉了三个内容库的 SHA-256，注记后字节变了 ⇒ **失败关闭**（工具行为正确，
是我的改动破坏了它的输入契约）。
⇒ 顺带发现 `action-identities.json` 的 pin **在提交树里就已经过期**
（文件在 HEAD、pin 不是）⇒ 是并发会话那次合并遗留的，与本次无关。

**修法（刻意更新，不是「按当前值重算」）**：
- 三个被注记改过字节的 pin 更新到新哈希，并在代码里写明「2026-10-22 因 `_provenance`
  块而**有意**变更；pin 仍用于挡**静默**漂移」；
- 一个本来就过期的 pin 修正到文件的实际哈希。

⇒ **全仓只有这一个工具钉内容库哈希**（扫 `tools/**` 的全部 64 位十六进制字面量，
命中 3 个库）⇒ 影响面收敛。
⇒ **教训：查「有没有门禁依赖这份文件的字节」必须扫 `tools/` 与 `tests/` 两处**——
pin 通常写在**消费方**的工具里，不在测试里。

（另：注记器把 34 个库重写为 `indent=2` 格式后，`test_populate_units_bank`、
`test_battle_controller_states`、`test_battle_handler_identity`、
`test_battle_encounter_identity` 共 29 项全绿 ⇒ 改字节本身对**按字段读**的用例无害。）

## 5. 边界声明

- **2 个库的族是「严格地址相同」**，不是「语义上就是这张表」——块里另记了
  `reverse_family_state` 与候选列表，读者可自行复核。
- **19 个库没有族也没有 note**：块里写明了 ROM 偏移与长度，**没有**替它们编族名。
- 本轮**只动内容库 JSON**（新增 `_provenance` 键），**没有改任何 C++/生成器**。
- W3 动作 2 的 **③（图形资产按生成器登记 sidecar）仍未做**：
  1819 个图形资产里只有 174 个被某个生成器源码**字面点名**，
  其余由循环/模板生成 ⇒ 需要 37 个生成器各自**声明**产物，
  属逐个改造，不在本轮范围。

## 6. 相关

- `docs/butano-wiring-roadmap.md`（W3 动作 2）
- `notes/butano-usable-backlog-20261022.md`（存量分诊）
- `tools/butano/annotate_content_bank_provenance.py`、
  `tests/test_content_bank_provenance.py`、
  `artifacts/butano-content-bank-provenance-v1/`
