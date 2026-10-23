# W4 第 2 片：52 族逐文件哈希族接进载体，`on-shelf` 归零（2026-10-22）

日期：2026-10-22
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
逆向树 `/Users/altair/github/gba-naruto-reverse`，commit `821d0937e058245aa7e6d29f23f96c7fc78e7375`
配套：`docs/butano-wiring-roadmap.md`（W4）、`notes/butano-w4-pixel-ab-20261022.md`（第 1 片）

## 0. 结论

**W4 的验收分母达成：货架 `on-shelf` 归零。**

| 项 | 前 | **现在** |
| --- | ---: | ---: |
| 带声明的接线 | 69 | **109** |
| `on-shelf`（已闭合带 payload、无人接） | 68 | **0** ✅ |
| 本片接进的族 | — | **52**（794 文件） |
| 导入校验 | — | **794 文件、0 问题** |

导入器 `tools/butano/import_rom_shelf_families.py`，
收据 `artifacts/butano-reverse-m3-import-v1/shelf/families.json`，
门禁 `tests/test_rom_shelf_family_import.py`（**4 项全绿**）。

## 1. 为什么第 1 片只能接 3 族

第 1 片用的是**像素 A/B 导入器**，它要求族里有 `baseline.png` + `candidate.png`。
实测货架上**这类形态只有 3 族**（`levels-status-per-level-ab-v1`、
`cutscene-obj-id1-primary-ptr-ab-v1`、`sappy-engine-master-enable-ab-v1`）⇒ 接完就没了。

⇒ 剩下 64 族是**另一种形态**：manifest **逐文件记了 SHA-256**。
这类族的验收不是像素差分，而是**内容等价**：
「复制进来的每个文件，其 SHA-256 等于逆向侧 manifest 记下的那个」。

⇒ ⇒ **同一个载体合同（族 + manifest 哈希钉死 + 逐文件复核）套另一种载荷形态**，
就得到第 2 片。

## 2. 15 族**不导入**——逆向侧的晋升有缺陷

逐文件复核时发现 **15 族自己的 manifest 与自己的文件不一致**：

| 族 | 不一致的文件 |
| --- | --- |
| `rom-animation-descriptor-pool-v2` | `rom-animation-descriptor-pool-v2.json` |
| `rom-boot-copy-sources-v1` | `rom-boot-copy-sources.json` |
| `rom-bounded-index-u16-pair-table-v1` | `rom-bounded-index-u16-pair-table.json` |
| `rom-cfg-proven-roots-v14` | `rom-cfg-proven-roots-v14.json` |
| `rom-directsound-pitch-lookup-v1` | `rom-directsound-pitch-lookup.bin` + `.json` |
| `rom-display-text-delta-v1` | `rom-display-text-delta.json` |
| `rom-fixed-animation-descriptor-groups-v1` | `rom-fixed-animation-descriptor-groups.json` |
| `rom-fixed-index-u8-tail-v1` | `rom-fixed-index-u8-tail.json` |
| `rom-fixed-pair-tables-v1` | `rom-fixed-pair-tables.json` |
| `rom-fixed-renderer-script-records-v1` | `rom-fixed-renderer-script-records.json` |
| `rom-low-script-delta-v1` | `rom-low-script-delta.json` |
| `rom-psg-frequency-lookup-v1` | `rom-psg-frequency-lookup.json` |
| `rom-renderer-records-delta-v1` | `rom-renderer-records-delta.json` |
| `rom-renderer-script-pointer-pool-records-v1` | `rom-renderer-script-pointer-pool-records.json` |
| `rom-u8-indexed-u8-triplet-lookup-v1` | `rom-u8-indexed-u8-triplet-lookup.json` |

⇒ **不导入**：导入器若把它们拷过来，就是**替逆向侧掩盖一个晋升缺陷**
（manifest 记的哈希与它自己的文件对不上）。
⇒ 它们在接线矩阵里被如实标成 `local-derivation-missing`
（构建链引用了它们、本树没有副本、逆向侧副本自相矛盾）⇒ **缺口可见**。

## 3. 一次撞上的约定坑：`*_FAMILIES` 后缀

审计器读导入器载体时，约定是「常量名以 `_FAMILIES` 结尾 ⇒ 它是 `(族, manifest 哈希)` 的表」。
我最初把「不导入的族」也起名 `INCONSISTENT_FAMILIES` ⇒ **被当成族表解包，报
`too many values to unpack`**。

⇒ 改名 `SHELF_FAMILIES_NOT_IMPORTED`（不再以 `_FAMILIES` 结尾）⇒ 恢复正常。
⇒ **教训：加入导入器载体时，模块里任何以 `_FAMILIES` 结尾的常量都会被当成族表**。

## 4. 边界声明

- 本片接进的是**验收基准**（族与证据的本地副本 + 逐文件哈希复核），
  **不改变重制侧的任何一帧画面**。
- 52 族的验收是**内容等价**（字节级），**不是**像素等价；它们的用途是
  「原版的捕获/清单在本地可读且未被篡改」。
- **15 族仍未接**（逆向侧 manifest 自相矛盾）⇒ 需要逆向侧重新晋升，不是本图的工作。
- 本轮**没有改任何 C++ 代码**。

## 5. 相关

- `docs/butano-wiring-roadmap.md`（W4：on-shelf = 0）
- `tools/butano/import_rom_shelf_families.py`、
  `tests/test_rom_shelf_family_import.py`、
  `artifacts/butano-reverse-m3-import-v1/shelf/`
- `notes/butano-w4-pixel-ab-20261022.md`（第 1 片：3 个像素 A/B 族）
- `notes/butano-wiring-carriers-20261022.md`（两套载体与覆盖率断言）
