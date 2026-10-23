# W4 第 1 片：三个 `-ab-v1` 族接进导入器载体（2026-10-22）

日期：2026-10-22
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
逆向树 `/Users/altair/github/gba-naruto-reverse`，commit `821d0937e058245aa7e6d29f23f96c7fc78e7375`
配套：`docs/butano-wiring-roadmap.md`（W4）、`notes/butano-usable-backlog-20261022.md`（§4 的分组）、
`docs/butano-reverse-gap-roadmap.md` §8.6

## 0. 结论

**W4 的 71 族不是一刀切不可脚本化的——像素 A/B 这一片可以，而且接进了 3 族。**

| 项 | 前 | **现在** |
| --- | ---: | ---: |
| 带声明的接线 | 66 | **69** |
| `on-shelf`（已闭合带 payload、无人接） | 71 | **68** |
| 导入器载体族数 | 54 | **57** |
| 覆盖率断言（审计器可见 − 矩阵数出） | 0 | **0** ✅ |

接进的三族：

| 族 | 编辑对象 | 验收方式 |
| --- | --- | --- |
| `cutscene-obj-id1-primary-ptr-ab-v1` | 一处指针 | **像素差分**（4032 像素，原有规则） |
| `levels-status-per-level-ab-v1` | ROM **数据字节**（`0x545BE4` 表第 21 条，偏移 5528266） | **内容等价**（base ROM 该字节 = 1） |
| `sappy-engine-master-enable-ab-v1` | ROM **代码半字**（`0x0809AE76`，偏移 634486） | **内容等价**（base ROM 该半字 = `0x208F`） |

## 1. 为什么这一片可脚本化

W4 的大部分族「每一族都是设计判断，脚本做不了」——但**像素 A/B 族是例外**：
载体（`tools/butano/import_rom_pixel_ab_baselines.py` 的 `PIXEL_AB_FAMILIES`）现成，
门禁现成，验收规则现成（无容差、逐通道取最大值再二值化）。

⇒ 接一族的动作 = **在常量里加一行「族 + manifest SHA-256」**，然后跑导入器。
声明由**导入器自己的合同**承载（运行期回查 manifest、逐文件复哈希、复制进复刻树），
不需要新建载体，也不需要手写声明。

## 2. ⚠️ 货架笔记的「同一形态」判断错了两族

`notes/butano-usable-backlog-20261022.md` §4 写：

> 像素基准（A/B）| `levels-status-per-level-ab-v1`、`cutscene-obj-id1-primary-ptr-ab-v1`、
> `sappy-engine-master-enable-ab-v1` | `baseline.png` + `candidate.png`，
> **与已导入的 32 个 pixel-A/B 族同一形态**，导入器现成

**文件布局确实一样**（`baseline.png` + `candidate.png` + `evidence.json` + `raw.tar`），
**但「编辑的是什么」不一样**：

| 族 | 逆向侧记录 | 像素期望 |
| --- | --- | --- |
| `cutscene-obj-id1-primary-ptr-ab-v1` | `pixels.changed_pixel_count = 4032` | 有 |
| `levels-status-per-level-ab-v1` | `edit.baseline = 1`，`edit.changed_rom_offsets = [5528266]`，`field = per_level_a` | **无** |
| `sappy-engine-master-enable-ab-v1` | `edit.before_halfword = 0x208F`，`changed_rom_offsets = [634486]`，`instruction_address = 0x0809AE76` | **无** |

⇒ **这两族根本不是像素族**。硬塞进像素载体会有两个后果：
① 门禁读不到 `changed_pixel_count`（要么红、要么被跳过）；
② 更糟的是**像素门禁静默失效**——「跳过」看起来像「通过」。

### 2.1 处置：载体自己声明「我没有像素期望」，并给出另一种验收

导入器新增两件事：

- `extract_expectation()` 额外提取 **`rom_anchor`**：记录这次 A/B 改的是 ROM 的哪个字节/半字、
  以及**基线 ROM 在那里应该是什么值**（`edit.baseline` / `edit.before_halfword`）；
- `check_rom_anchor(rom, anchor)`：拿**本树的 base ROM** 去核对那个锚点，返回问题清单。

⇒ 验收从「像素差分」变成「**内容等价**」：这对锚点必须仍由**重制侧构建所用的那份 ROM**
持有记录里的基线值。这样 A/B 证据对就**锚在重制侧的 ROM 上**，不会悄悄漂到别的 ROM。

门禁（`tests/test_rom_pixel_ab_baseline_import.py`）相应分叉：

- 有像素期望的族 ⇒ 走原有的**像素差分**规则（无容差、逐通道取最大值再二值化）；
- 没有像素期望的族 ⇒ 走**内容等价**规则，且**必须**有 `rom_anchor`，
  没有锚点就是「这一对没有任何验收」⇒ 失败关闭。

并配一条**变异测试**：把锚点处的一个字节改掉 ⇒ 必须被拒绝。

## 3. 门禁

| 项 | 内容 |
| --- | --- |
| 工具 | `tools/butano/import_rom_pixel_ab_baselines.py`（+`_rom_anchor` / `check_rom_anchor`） |
| 声明载体 | `PIXEL_AB_FAMILIES`（32 → **35**） |
| 门禁 | `tests/test_rom_pixel_ab_baseline_import.py`（16 项，全绿，含一条锚点变异测试） |
| 复现 | `python3 tools/butano/import_rom_pixel_ab_baselines.py import --reverse-root <reverse> --out-dir artifacts/butano-reverse-m3-import-v1/pixel-ab`（`family_count: 35`）<br>`python3 tools/butano/import_rom_pixel_ab_baselines.py verify --reverse-root <reverse> --out-dir artifacts/butano-reverse-m3-import-v1/pixel-ab`（`checked_families: 35`，`problems: []`） |

## 4. 读数变化（当轮收据）

| 测量 | 前 | 现在 |
| --- | ---: | ---: |
| 带声明接线 | 66 | **69** |
| `on-shelf` | 71 | **69** |
| 成果族 `build` | 93/264 = 35.2% | **96/264 = 36.4%** |
| 条目口径 | build 375 / doc 513 / local_artifact 0 / none 1073 / test 246 | **build 377 / doc 510 / local_artifact 0 / none 1073 / test 247** |
| 覆盖率断言差 | 0 | **0** ✅ |

> 四份「当前状态」文档（缺口路线图 §7.7、核验笔记 §11.10、konoha-senki README 索引行、
> sequel-roadmap 指针）已按当次收据刷新读数——`tests/test_gap_denominator_consistency.py`
> 会在这类数字变化时**故意转红**，那是信号不是回归。

## 5. 边界声明

- **这三族不是「接进构建链」**，是「接进**验收基准**」：导入器把族与证据复制进复刻树，
  并由门禁守住。**像素差分/内容等价是验收，不是消费**——
  它们不改变重制侧的任何一帧画面。
- `scope` 仍未闭合：`levels-status-per-level-ab-v1` 与 `sappy-engine-master-enable-ab-v1`
  的 manifest **没有 `scope` 块**（既没有「全闭合」也没有「未闭合声明」）。
  按 W4 的风险条款，**可以接，但不能声称原版一定会走到那里**。
- `sappy-engine-master-enable-ab-v1` 的导入收据写的是
  `applicability: no-local-anchor-in-this-tree`——**它的锚点是 ROM 半字，不是本地文件**，
  这正是内容等价验收要覆盖的情况。
- W4 剩余 68 族仍是逐族设计判断（状态栏/调色板、文本/对白、场景/地图、战斗特效、音频表）。

## 6. 相关

- `docs/butano-wiring-roadmap.md`（W0–W5；W4 第 1 片）
- `docs/butano-reverse-gap-roadmap.md` §8.6（本轮读数与教训）
- `notes/butano-usable-backlog-20261022.md` §4（分组；**「同一形态」的判断已被本轮修正**）
- `notes/butano-wiring-carriers-20261022.md`（两套载体与覆盖率断言）
- `tools/butano/import_rom_pixel_ab_baselines.py`、`tests/test_rom_pixel_ab_baseline_import.py`
