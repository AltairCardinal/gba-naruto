# W5 第一步：332 条未转门禁 note 的 ROM 字节钉点（2026-10-22）

日期：2026-10-22
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
配套：`docs/butano-wiring-roadmap.md`（W5）、`artifacts/reverse-notes-index-v1/notes-index.json`

## 0. 结论

**332 条 `needs_guard` note 里引用的 ROM 地址，已经全部变成机器可检的钉点。**

| 项 | 值 |
| --- | ---: |
| 未转门禁的 note | **332** |
| 它们引用的地址 | **2405** |
| **可钉（卡带地址 0x08000000–0x09FFFFFF）** | **1434** |
| **只列不钉（EWRAM/PRAM/IO 等）** | **971** |

收据 `artifacts/butano-note-rom-claims-v1/`
工具 `tools/butano/snapshot_note_rom_claims.py`
门禁 `tests/test_note_rom_claims.py`（**5 项全绿**）

## 1. 为什么不写 332 条语义门禁

W5 写的是「逐条转成**行为**门禁」。每条 note 的**语义**断言各不相同
（「这段代码是 `mov`」「这个表的第 21 条是 1」……），写 332 条要逐条读、逐条判断。

⇒ 但 note 引用的**地址**是它断言的**一部分**：若 note 说「0x0809AE76 处如何如何」，
那么那 4 个字节就该被钉住。于是：

- **可钉** = 卡带窗口内的地址 ⇒ 钉住 base ROM 在那儿的 4 字节；
- **不可钉** = EWRAM/PRAM/IO 地址 ⇒ **只列出来，不钉**（base ROM 里根本没有这些字节，
  钉了就是撒谎）。

⇒ **字节级钉点不证明 note 的解读仍成立**，只证明「它指的那几个字节没变」。
收据与文档都写明了这条边界。

## 2. 提取规则与索引一致

`tools/build_reverse_notes_index.py` 用 `ADDR_RE = 0x[0-9A-Fa-f]{4,}` 数每条 note 的
「ROM 地址」⇒ 快照工具**用同一条正则**重新抽 ⇒ 抽出来的是同一批地址（2405 处，
索引合计 1992 —— 差值来自同一 note 内的重复地址去重口径不同，两边都记在收据里）。

## 3. 门禁做了什么

- 每个钉点都还对得上 base ROM（不��则**点名 note + 地址 + 期望值/实际值**）；
- 快照记录了 base ROM 的哈希 ⇒ ROM 换了快照立刻作废；
- 钉点**只允许在卡带窗口内**（测试钉住）；
- 窗口外的地址**只列不钉**（测试钉住「不钉的不在钉点里」）；
- 快照可复现（同一棵树两次跑结果相同）。

## 4. 边界声明

- **这是字节级门禁，不是语义门禁**：note 说「0x… 是 `mov`」，本轮只保证那儿的字节没变，
  **不保证解读对**。语义门禁仍要逐条写（W5 的下一步）。
- 1434 个钉点**只覆盖 note 正文里的地址**；note 用别的形式表述的断言
  （表结构、消费者链、行为序列）**不在覆盖内**。
- 本轮**没有改任何 note、没有改 ROM**；只新增了收据与门禁。

## 5. 相关

- `docs/butano-wiring-roadmap.md`（W5）
- `tools/butano/snapshot_note_rom_claims.py`、`tests/test_note_rom_claims.py`、
  `artifacts/butano-note-rom-claims-v1/`
