# W4 —— wave 15：出包定稿 + 1:1 报告定稿

> 工具：`tools/s49_package/make_report.py`（**本流独占**）
> 产物：`build/s49-package-w4-final/`（收据 + 包，**不进 git**）、
> `docs/s49-fidelity-report-20261024.md`
> 2026-10-24 · 流 W4（wave 15，收官波）· 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 任务书：`notes/s49-fidelity/WAVE15-TASKS.md` §4
> 上游：`notes/s49-fidelity/W4-wave14-package-final.md`（wave 14 的 Z4 出包波）
> ⛔ **未改**重制线任何文件；⛔ **未改** `run_pipeline.py` / `tools/s49_fidelity_report*`
> （W2 独占）；⛔ **未改**其它流的仪器（一律**只读调用**）；⛔ 逆向线全程只读；
> ⛔ **未提交 git**。

---

## 0. 一句话结论

> ⭐ **12 步流水线跑了 12 步，第 5 步（判定台）红，其余 11 步全绿** ——
> 收据 `build/s49-package-w4-final/receipt.json`
> （`generated_at` = **2026-10-24T20:00:13+08:00**、`ok: false`、
> `failed_step: 5`）；ROM **构建 == 钉住 == 打包三者同 sha `fb9d2dbd…`**；
> 单测棘轮 **118 pass / 20 fail（新失败 0）**；
> 判定台连读 **3 次 109,629 px 逐项相同**；
> **棘轮基线没有被提升**（不绿的包不许当基线 —— 这正是 W2 的新机制）。
>
> ⭐⭐ **但这次的红是「真阳性」**：棘轮基线 = **wave 14 被接受的收据**
> （109,569 px / ROM `ec5b5273…`），本次 = **109,629 px / ROM `fb9d2dbd…`**
> ⇒ **+60 px**。逐帧归因：**25 个配对时刻里只有 `step-24-A.png` 一帧变了**
> （1,372 → 1,432 px，判定类别 **产品差**），其余 24 帧**逐像素相同**。
> ⇒ **产品侧确实退步了 60 px**，而 W1 自己报的「判定台残差没有变大」是
> **陈旧采集造成的假象**（见 §2.5）。
>
> ⚠️ **本波没有拿到 12/12 全绿的包**，原因是**产品侧的 +60 px 回归**，
> **不是**出包流程的问题（11 个 selftest 仍全部能把对应的步骤打红）。
>
> ⭐ **报告**：`docs/s49-fidelity-report-20261024.md`
> （**§2.0.1** 逐帧归因 / **§2.0.2** 判定台的采集复用缺陷 /
> **§10** 新增两条明确排除项 / **§11** 25 条未达成项 / **§13.1** 11 个 selftest 全红 /
> **§14.9** 本波台账）。

---

## 1. 本流改了什么

| 文件 | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_package\make_report.py` | **修改** | ① 标题改成 **wave 15 定稿**；② 新增 **wave 15 的三路交付读取器**（`wave15_cutoff_mtime()` / `wave15_notes()` / `wave15_streams()` / `w15_status()`）—— 「本波已交付」**一律以 `WAVE15-TASKS.md` 的 mtime 为界**（**同名笔记坑**）；③ **§10 明确排除项**新增两行：**`grid16-frame-v1` 的 80 格**（原版缓冲的**单帧撕裂瞬态**）+ **44 格原版尾部残留**，并从 §11 第 3 项里指向它们；④ **黑场判定改成数据驱动**（逐段差由收据算出，不再写死 wave 14 的数字）；⑤ **§0 与 §11 第 2 项新增「三个数不是同一个口径」的警告**（判定台 arg-min / 可证像素下界 / 内容锚可达数）；⑥ 新增 **§11 第 21 项**（wave 15 三路的落地状态）与 **§14.9 wave 15 台账**；⑦ ⭐ **新收据字段**：`ratchet_verdict()`（三态判决）、`accepted_receipts()`（从盘上**独立重推**「上一波被接受的运行」）、`criteria_diff()`（**机检** 12 步判据有没有变）、`ratchet_baseline_info()`；⑧ ⭐ **§2.0.1 逐帧归因**（`ratchet_frame_diff()`）+ **§2.0.2 采集复用缺陷**（`capture_rom_mismatch()`：把「采集实际记录的 ROM」与「报告声称的 ROM」并排写出来）；⑨ ⭐ **§15.2.1 / §15.2.2**（W3 的结算屏收据 + 本流**独立重算**的交叉核对）；⑩ **§11 第 22 项**（判定台复用采集不校验 ROM）。 |
| `D:\Github\gba-naruto\notes\s49-fidelity\W4-wave15-package-final.md` | **新增** | 本文件。 |
| `D:\Github\gba-naruto\build\w4-dev\run-when-idle.ps1` | **新增**（`build/` 不进仓） | 跑流水线前的**闸门**：等 W1/W2/W3 三路都交付 + ROM 的 mtime 稳定 ≥ 150 s + 没有 `mgba-probe.exe` / `wsl` / `make` 在跑。 |
| `D:\Github\gba-naruto\build\w4-dev\check-syntax.ps1` | **新增**（`build/` 不进仓） | 闸门脚本的**语法自检**（PowerShell AST 解析），避免"直接跑一遍才发现脚本写错"。 |

**没有**改重制线任何文件、逆向线任何文件、其它流的仪器。

⚠️ **但 `run_pipeline.py` 本波被 W2 改了**（W2 独占）——**不是本流改的**：
W2 改了 **2 处**（第 1 步加 150 s 前置等待、第 5 步改棘轮基线来源 + 三态判决），
**其余 10 步的判据逐字未改**（W2 的机检 `build/w2-dev/verify_criteria.py`）。
⇒ 本流在报告生成器里加了一条**自己的机检**：
`criteria_diff()` 直接比较**两份收据里 12 条判据的字面量**
（判据是流水线里的字符串，收据原样记着 ⇒ 「判据没改」是**可机检的**，
不是一句承诺）⇒ 报告里会写明「12 步的判据变了 N 处 / 逐字相同」。

---

## 2. ⭐ 本波踩到的坑

### 2.0 三路交付的时间线（**以任务书 mtime 为界**）

| 时刻 | 事件 |
|---|---|
| `18:40:33` | **wave 15 任务书**落盘（本流的「本波已交付」分界线） |
| `18:54:02` | 重制线开始被改（`battle_black_field_star_mask.h`）⇒ W3 开工 |
| `18:54:49` / `18:55:39` | `battle_ui_model.h` / `battle_runtime_scene.cpp` ⇒ W1 开工 |
| `18:56:40` | 盘上的 ROM 被重建（⇒ 并行流在改产品，**此时跑流水线必然红**） |
| `19:02:36` | **W2 交付**（`W2-ratchet-baseline.md`）—— 仪器缺陷修好了 |
| `19:10:08` | **W3 交付**（`W3-blackfield-and-screens.md`） |
| `19:35:47` | **W1 交付**（`W1-three-defects.md`） |
| `19:36` 起 | 闸门满足条件 ⇒ 12 步流水线开跑 |

⚠️ **旧波笔记的坑比任务书说的更宽**：不止 wave 7 有 `Z1/Z2/Z3`，
**wave 5/6/8 也有 `W1-blackfield-timeline.md` / `W2-starfield-vram.md` /
`W3-overlay-dialogue.md`** ⇒ 判定「本波已交付」**只能**用任务书的 mtime。

### 2.1 ⭐ 同名笔记坑：**wave 5 / 6 / 8 也有 W1/W2/W3 命名的笔记**

任务书只提醒了「wave 7 也有 Z1/Z2/Z3 命名的笔记」，实测发现**更宽**：

```
notes/s49-fidelity/W1-blackfield-timeline.md   ← 旧波
notes/s49-fidelity/W2-starfield-vram.md        ← 旧波
notes/s49-fidelity/W3-overlay-dialogue.md      ← 旧波
notes/s49-fidelity/W1-integration.md           ← 旧波
notes/s49-fidelity/W2-judgment-bench-v2.md     ← 旧波
notes/s49-fidelity/W3-settlement-wiring.md     ← 旧波
```

⇒ 「本波已交付」**不能**用文件名前缀判定，
**一律以任务书的 mtime 为界**（`WAVE15-TASKS.md`）。
**实测证明**：把 cutoff 设成 0 时，上面的旧笔记会被误认成 wave 15 的交付
（`W1: [W1-blackfield-timeline.md, W1-integration.md]` …）；
用真实 cutoff 时读到的集合是**空集**（wave 15 还没人交付）⇒ 判据有效。

### 2.2 删除失败包目录：**必须打真路径**

`D:\Github\gba-naruto` 是指向 `D:\Shell\Github\gba-naruto` 的 **junction**
⇒ 回收站启动器**拒绝对 junction 的目标动手**。

实测（两个失败的包目录 `build\s49-package-z4-final`（步骤 5 红）
与 `build\s49-package-z4-final2`（步骤 1 红），共 422 MB）：

```powershell
# 打 junction 路径 ⇒ 被拒
rm -- "D:\Shell\Github\gba-naruto\build\s49-package-z4-final" "..."   # "requires the targets-only trash marker"
# 打真路径 ⇒ 成功
& 'D:\minimax\.minimax\bin\mavis-trash.cmd' -- "D:\Shell\Github\gba-naruto\build\s49-package-z4-final" "D:\Shell\Github\gba-naruto\build\s49-package-z4-final2"
# ⇒ mavis-trash: moved to trash: ... (exit 0)
```

⇒ **两个失败的包目录已清掉**（回收站里可恢复），
`build\s49-package-z4-final3`（wave 14 的**绿包**）**保留** ——
它是 W2 的棘轮基线的来源，**不能删**。

### 2.3 ⭐ wave 15 的棘轮语义变了：**「不可比」不等于「通过」**

W2 已经在 `run_pipeline.py` 里落了新语义（**W2 独占，本流只读**）。
在 W2 的测试包 `build/s49-package-w2-test2/receipt.json` 里实测到：

```
ratchet.status = "incomparable"
ratchet.comparable = false
ratchet.note = "the baseline ROM differs from this run's ROM => the two residual
                numbers are not the same measurement => NOT comparable, and
                therefore NOT a pass"
```

* 收据里**多了三个顶层键**：`ratchet` / `accepted_baseline` /
  `accepted_baseline_promoted` ⇒ **报告生成器必须能读新收据的形状**
  （旧的 wave 14 收据没有这些键 ⇒ 两边都要支持）。
* 步骤 5 在「不可比」时**不是红的**（退出码 2），但收据**明写「NOT a pass」**，
  流水线末尾也打印「⚠ RATCHET INCOMPARABLE … this is not a pass」。

⇒ **对 wave 15 本次运行的直接后果**：W1/W3 改了产品 ⇒ **ROM 必然变** ⇒
**本次的棘轮判定几乎一定是 `incomparable` 而不是 `pass`** ⇒
**「残差只许变小」这条规则本次并没有被检验**。
⇒ 报告**不许**把它写成「棘轮通过」，必须写「**不可比 ⇒ 这条门禁本次没被检验**」。

⇒ 本流因此在报告生成器里加了一个**独立于流水线**的复核：
`accepted_receipts()` 自己从盘上的收据里重新推导「上一波被接受的运行」
（按 `generated_at` 排序、`ok == true`、**跑满 12 步**、排除本次自己的包目录），
再把**它**和流水线自己的基线对照 ⇒ 棘轮是否带牙齿**从外面可验证**。

> ⚠️ **踩坑**：第一版 `accepted_receipts()` 没有要求「跑满 12 步」⇒
> 它把 W2 的 **`--only 5` 测试包**（`build/s49-package-w2-test2`）
> 当成了「上一波被接受的运行」⇒ 报告里出现 **109 629 px** 这个**不存在的数**
> （真正的上一波是 **100 210 px**）。
> ⇒ **修法**：只认 `len(steps) == 12` 的收据。
> ⇒ **验证**：修完后本报告从盘上独立算出 wave 13 → wave 14 的
> **+9,359 px（+9.3 %）** —— 与 Z4 笔记里的数字**逐值相同** ⇒
> 这条复核链路是可信的。

### 2.4 ⭐ W3 的结算屏收据与本流的**独立重算逐值相同**

W3 交了机器可读收据 `build/w3/settlement-align.json`
（重制侧帧来自 `build/w3/chain-pinned/shots`，**钉住 ROM 的重录**）。
本流另起一个实现（报告生成器里的 `_diff_pixels()`，PIL + 项目像素口径）
在盘上的 PNG 上重算 ⇒ **8 / 8 屏逐值相同**：

| 原版真值 | 重制侧 | 差 px | 逐字节相同 |
|---|---|---:|---|
| `01-victory.png` | `page-000-outcome.png` | 37 462 | ❌（重制侧**全黑**：原版 83 色 vs 重制侧 **1 色**） |
| `02-settlement-exp-power-turns.png` | `page-001-result.png` | 35 859 | ❌（版式不同） |
| `03-levelup-naruto.png` | `page-002-level_up.png` | 0 | ✅ |
| `05-levelup-sasuke-jutsu-name.png` | `page-003-level_up.png` | 0 | ✅ |
| `04-levelup-konohamaru.png` | `page-004-level_up.png` | 0 | ✅ |
| `05-levelup-sasuke.png` | `page-005-level_up.png` | 0 | ✅ |
| `06-levelup-sakura.png` | `page-006-level_up.png` | 0 | ✅ |
| `07-ninja-tool-list.png` | `page-007-level_up.png` | 0 | ✅ |

⇒ **6 / 8 有语义对应的屏差 0 px**（记在 15 屏的运行帧记录里 = **6 / 15**），
与 Z1 笔记 §3.3 的数字**逐值相同** ⇒ **三个来源（Z1 笔记 / W3 收据 / 本流重算）互证**。

### 2.5 ⭐⭐⭐ 本波最重要的发现：**判定台复用采集时不校验 ROM** ⇒ 假结论

**现象**：W1 交的笔记里写着「判定台残差没有变大（同口径、同帧集：
总和 109,569 / 中位 1,372 / 全 0 帧 4，**与基线 ROM 逐项相同**）」，
但本流的流水线在**同一个 ROM** 上量到 **109,629（+60）**。

**定位（一次一个是否问题，逐步收敛）**：

| # | 问题 | 判定方法 | 结果 |
|---|---|---|---|
| 1 | 是不是 W1 的改动让残差变大了？ | 比 W1 的 `build/w1/judgment-{base,w1}.json` | **两份的 `run.reused` 都是 `true`** ⇒ **两次跑都没有重录**，比的是**同一份采集** ⇒ 「逐项相同」是**必然的**，不是证据 |
| 2 | 那份被复用的采集是哪一个 ROM 录的？ | 读 `captures.remake.audit.rom_sha256` vs `captures.remake.rom_sha256` | ⚠️ **audit = `ec5b5273…`（wave 14 的 ROM），声称 = `fb9d2dbd…`（新 ROM）** ⇒ **它拿的是 wave 14 的帧，却标成新 ROM 的读数** |
| 3 | 采集目录在哪？ | 读 `captures.remake.output_dir` | **`build/s49-package-z4-final3/work/s49-report/capture-remake`** ⇒ **wave 14 包里的采集目录** ⇒ W1 的命令复用了它 |
| 4 | 采集程序为什么不报错？ | 读 `tools/s49_fidelity_report/capture.py::run_capture()` | `if reuse and done_marker.exists() and sorted(out_dir.glob("step-*.png")): reused = True` ⇒ **只看「标记在不在、帧在不在」，从不核对 ROM**；而报告里的 `rom_sha256` 是**它被要求测的那个 ROM** 的 sha ⇒ **报告可以声称一个它没测过的 ROM** |
| 5 | 那 +60 px 到底是真的吗？ | 在**同一个钉住的 ROM** 上**独立重录 4 次**（流水线那次 + 本流 3 次：20:11:20 / 20:11:36 / 20:12（并行探针负载下）） | **4 次逐帧完全相同**（重制侧 35 帧 **0 处不同**）⇒ 读数 **109,629 / 中位 1,432** ⇒ **+60 px 是真的** |
| 6 | 是主机负载造成的吗？ | 第三次重录时**并行跑一个探针** | 与空闲时的重录 **0 处不同** ⇒ **负载不是机制** |
| 7 | 是判定台代码变了吗？ | 比 `tools/s49_fidelity_report*` 的 mtime | 最后一次改动 **18:49** ⇒ **在两次跑（19:33 / 20:07）之前** ⇒ 代码没变 |
| 8 | 是 ROM 变了吗？ | 比 sha | 采集的是**同一份** `fb9d2dbd…`（`build/w1/rom-w1b.gba` 与流水线的 `pinned-rom/measured.gba` **逐字节相同**）⇒ 不是 |

⇒ **结论**：**+60 px 是真回归**（第 5 问的 4 次独立重录互证），
**W1 的「逐项相同」是陈旧采集造成的假象**（第 1–4 问）。
⇒ **根因是一个真仪器缺陷**：`capture.py` 复用采集时不校验 ROM
⇒ 报告生成器因此新增了 `capture_rom_mismatch()`，
**在报告里把「采集实际记录的 ROM」和「报告声称的 ROM」并排写出来**，
**下一次谁复用采集，报告自己就会指出它读的是哪个 ROM**。
⇒ **交给判定台的所有者**：复用前必须核对
`audit.rom_sha256 == 本次要求的 ROM`，否则**拒绝复用**。

---

## 3. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **W4w-1** | W1 / W2 / W3 在本波开工前是否已经交付 | 读 `notes/s49-fidelity/` 里**在 `WAVE15-TASKS.md` 之后**写的笔记 + 查重制线源码在任务书之后有没有被改过 | **都没有**：任务书 `18:40:33` 写完时，目录里最新的笔记是 wave 14 的 `Z2-blackfield-final.md`（`18:28:08`）、重制线源码最后一次改动是 `18:13:22`、盘上的 ROM 是 `ec5b5273…`（`18:14:04`）⇒ 本流第一件事是**等** | **已确认（未交付）** |
| **W4w-2** | 「本波已交付」能不能用笔记的**文件名前缀**判定 | 读 `notes/s49-fidelity/` 里的同名笔记（`Z1-wiring.md` / `Z2-title-art-starfield.md` / `Z3-dialogue-box.md` 是 **wave 7** 的；`W1-blackfield-timeline.md` / `W2-starfield-vram.md` / `W3-overlay-dialogue.md` 等是**更早的波**的） | **不能** ⇒ 判定必须**以任务书的 mtime 为界**；报告生成器里由 `wave15_notes()` / `wave15_streams()` 实现；**实测**：cutoff=0 时会误认旧笔记，真实 cutoff 时读到的集合是空集 | **已证伪** |
| **W4w-3** | 报告生成器能不能在 W1/W2/W3 的产物**形状未知**的情况下只读地取到它们的数字 | 按**笔记标题**里的流编号（W1/W2/W3）分类；数字只从**本次收据**里取 | **能**：笔记只用来判定「交付与否」，**所有数字都来自收据**（黑场事件数、棘轮基线、单测棘轮、残差）⇒ 每个数字都能追到一次运行 | **已确认** |
| **W4w-4** | 两个失败的包目录能不能删掉 | 先 `rm --`，再打**真路径**调 `mavis-trash.cmd` | **能**：必须打真路径；打 junction 路径会被回收站启动器拒掉 | **已确认（已清理）** |
| **W4w-5** | 残差归零到底可不可达 | 读 Z3 的下界收据（`floor_sum`）+ 它的证明方式；**并把判定台的读数与下界分成两个口径** | **不可达**：下界 **16,389 px**（测在 ROM `2c2b48d9…`）、内容锚可达数 **18,886 px** ⇒ 区间 **[16,389, 18,886]**；⚠️ **判定台读数是另一个口径**（arg-min 无时刻约束）⇒ 两个数**不许混用** | **已确认** |
| **W4w-6** | 覆盖层剩下的 176 格能不能算作「覆盖层规则的产品差」 | 读 Z3 的相位归因收据（6 帧连拍 + 密集 walk 逐帧对齐） | **不能**：130 格 = **50 格重制侧缺一个相位**（原版稳定态，连续 67 帧）+ **80 格原版那一帧是瞬态**（6 连拍只现 1 次 ⇒ 缓冲撕裂）；⇒ `grid16` 的 80 格 + 44 格尾部残留进**「明确排除项」** | **已确认** |
| **W4w-7** | 结算链的「语义对照」能不能从盘上**重算**，而不是抄笔记里的数 | 用报告生成器新写的 `_diff_pixels()` 在 `build/z1/chain-e/shots/` 与 `build/s49-victory-capture/w4/settlement-truth/` 两组 PNG 上重算 | **能**：重算得 **37,462 / 35,859 / 0×6**，与 Z1 笔记 §3.3 记的 **37,462 / 35,859 / 0×6** **逐值相同** ⇒ 口径（三通道任一不同即算不同、bbox 上界开区间）正确 | **已确认** |
| **W4w-8** | wave 15 的棘轮判定会是什么 | 读 W2 的测试包 `build/s49-package-w2-test2/receipt.json` 的顶层 `ratchet` | **预测「incomparable（不可比）」**（W1/W3 改了产品 ⇒ ROM 变 ⇒ 残差不变）⇒ **已证伪**：实际是 **`fail`** —— 残差**变大**了 **+60 px**，按 W2 的三态规则「ROM 变了 **且** 残差变大 ⇒ **FAIL（红）**」⇒ **本次的红是「真阳性」** | **已证伪（预测错了）** |
| **W4w-9** | 报告能不能在**新旧两种收据形状**下都工作 | ① 用 wave 14 的旧收据跑一遍；② 读 W2 测试包的新收据字段 | **能**：`ratchet_verdict()` 优先读新的顶层 `ratchet`；旧收据没有 ⇒ 由 `ratchet_rom.changed` 推出状态，并**明写「本收据早于 wave 15 的判定字段」** | **已确认** |
| **W4w-10** | wave 15 的 12 步能不能全绿 | `build/w4-dev/run-when-idle.ps1` → `run_pipeline.py --out build/s49-package-w4-final` | **不能**：**11 绿、第 5 步红** —— 棘轮判定 **FAIL**（残差 **109,569 → 109,629，+60 px**）⇒ **不是**出包流程的问题，是**产品侧的回归被新棘轮抓住了** | **已确认（红）** |
| **W4w-11** | 那 +60 px 是**真的产品回归**还是**仪器抖动** | 在**同一份钉住的 ROM** 上**独立重录 4 次**（流水线 + 本流 3 次，含一次并行探针负载下） | **是真的**：4 次**逐帧完全相同**（重制侧 35 帧 **0 处不同**）⇒ 读数恒为 **109,629 / 中位 1,432** ⇒ **+60 px 稳定可复现** | **已确认（真回归）** |
| **W4w-12** | W1 报的「残差没有变大」为什么和流水线差 60 px | 读 W1 收据的 `run.reused` / `captures.*.audit.rom_sha256` / `output_dir` | **因为 W1 复用了 wave 14 包里的采集目录**（`reused: true`、`audit ROM = ec5b5273…`、目录在 `build/s49-package-z4-final3/work/…`）⇒ **它比的是 wave 14 的帧，却标成新 ROM 的读数** ⇒ 「逐项相同」是**必然的**，不是证据 | **已确认（假象）** |
| **W4w-13** | 采集复用的根因在哪 | 读 `tools/s49_fidelity_report/capture.py::run_capture()` | `if reuse and done_marker.exists() and sorted(out_dir.glob("step-*.png")): reused = True` ⇒ **从不核对 ROM**；报告里的 `rom_sha256` 是**它被要求测的**那个 ROM ⇒ **可以声称一个没测过的 ROM** | **已确认（仪器缺陷）** |
| **W4w-14** | 主机负载会不会改变采集 | 第三次重录时**并行跑一个私有探针**（`build/mgba-probe-w4`） | **不会**：与空闲时的重录**逐帧相同**（0 处不同）⇒ 负载不是机制 | **已证伪** |
| **W4w-15** | 判定台代码在两次跑之间变过吗 | 比 `tools/s49_fidelity_report*` 的 mtime | **没变**：最后一次改动 **18:49**，早于两次跑（19:33 / 20:07） | **已证伪** |
| **W4w-16** | 判定台代码改动会不会改判据 | 比两份收据里 12 条判据的字面量（`criteria_diff()`） | wave 15 改了 **2 处**（第 1 步加 150 s 前置等待、第 5 步改棘轮基线来源 + 三态判决），**其余 10 步逐字未改** —— 与 W2 的机检 `build/w2-dev/verify_criteria.py` **一致** | **已确认** |

---

## 4. 复现命令

```powershell
cd D:\Github\gba-naruto

# 0) 跑流水线前：等「W1/W2/W3 都交付 + ROM 稳定 150 s + 没有探针/构建在跑」
powershell -NoProfile -ExecutionPolicy Bypass -File build\w4-dev\run-when-idle.ps1

# 1) 12 步流水线（**换包目录** ⇒ 草稿残留自动清掉）
python tools/s49_package\run_pipeline.py --out build/s49-package-w4-final

# 2) 11 个 selftest（每个步骤故意破坏 ⇒ 必须全红）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\s49_package\run_selftests.ps1 `
    -PackageDir 'build\s49-package-w4-final'

# 3) selftest 把证据写进包里之后，重写并核对包清单
python tools\s49_package\run_pipeline.py --out build/s49-package-w4-final --verify-manifest

# 4) 报告
python tools\s49_package\make_report.py `
    --receipt build/s49-package-w4-final/receipt.json `
    --out docs/s49-fidelity-report-20261024.md
```

---

## 4. ⭐ 本波跑了哪些验证（命令 + 关键数字）

| # | 验证 | 命令 | 结果 |
|---|---|---|---|
| 1 | **12 步流水线** | `python tools/s49_package/run_pipeline.py --out build/s49-package-w4-final` | **12 步跑完，11 绿、第 5 步红**（收据 `generated_at` = **2026-10-24T20:00:13+08:00**、`ok: false`、`failed_step: 5`） |
| 2 | **ROM 一致性** | 比步骤 1 构建产物 / 钉住的拷贝 / 步骤 12 打包的 / 包里 `rom/butano-sequel.gba` 的 sha256 | **四者逐字节相同** = `fb9d2dbd8e35b8101b96f6df133b03073a144e8f84ae124fbc1812d47fd93384` |
| 3 | **单测棘轮** | 步骤 2 | HEAD **101 pass / 20 fail**、工作区 **118 pass / 20 fail** ⇒ **新失败 0 项**（20 项预存债，**零回归**） |
| 4 | **判定台 3 次读数一致性** | 步骤 5（`--repeat 3`） | `determinism.identical = true` ⇒ 连读 3 次 **109,629 px** 逐项相同 |
| 5 | **棘轮判决** | 收据顶层 `ratchet` | **FAIL**：基线（wave 14 被接受的收据）**109,569** vs 本次 **109,629** ⇒ **+60 px**；`accepted_baseline_promoted` = **否**（不绿的包不许当基线） |
| 6 | **+60 px 的逐帧归因** | 比较基线报告与本次报告的 25 个配对时刻 | **只有 `step-24-A.png` 一帧变了**（1,372 → 1,432 px，判定类别 **产品差**），其余 24 帧逐像素相同 |
| 7 | **+60 px 是不是仪器抖动** | 在**同一份钉住的 ROM** 上**独立重录 4 次** | **4 次逐帧完全相同**（重制侧 35 帧 **0 处不同**）⇒ **是真的** |
| 8 | **是不是主机负载** | 第三次重录时并行跑私有探针 `build/mgba-probe-w4` | 与空闲时**逐帧相同** ⇒ **负载不是机制** |
| 9 | **覆盖层逐格** | 步骤 6 | 同亮 **192 / 缺 0 / 多画 0**（field、movegrid）；`grid16` 175/0/17；逐格性质 **尾部残留 44 / walk 相位 130 / 产品差 2** |
| 10 | **黑场** | 步骤 9 | 原版 **2** 个事件（24/18/24、24/24/24）；重制侧 **6** 个（**4 个仍是硬切**；两个带渐变的是 24/20/28、28/24/28） |
| 11 | **结算屏逐屏对照** | 读 W3 的收据 + 本流独立重算 | W3 收据 **8 对**、合计差 **73,321 px**、**6 对逐字节相同**；本流重算与它 **8/8 逐值相同** |
| 12 | **11 个 selftest** | `build/w4-dev/run-selftests-percase.ps1`（见 §4.1） | **11 red, 0 not red** ⇒ **11 个步骤的判据都真的会被触发**（证据 `build/s49-package-w4-final/evidence/selftest-break.txt`） |
| 13 | **包清单** | `run_pipeline.py --out build/s49-package-w4-final --verify-manifest` | **the manifest matches the package (198 files)** ⇒ 清单与磁盘一致 |

### 4.1 ⭐ 11 个 selftest 的一个**环境坑**（wave 15 新增）

wave 15 的流水线**在第 1 步之前会先等 150 s**（W2 的新 settle 门禁：
「ROM 不变 150 s + 没有 `mgba-probe.exe` 在跑」）。
⇒ 当**别的流还举着探针**时，`--selftest-break build` 这一案会**一直等**，
把**整个 selftest 队列**堵住（wave 14 的 `run_selftests.ps1` 是串行队列 ⇒ 第一案堵 ⇒ 全堵）。
⇒ **本流的做法**：用 `build/w4-dev/run-selftests-percase.ps1`
—— **每案一个自己的 scratch 目录**，并且**把 build 那一案放到最后**跑
⇒ 其它 10 案的判决不再被那一案的等待拖累。
⇒ **实测**：**11 red, 0 not red**（build 那一案在 settle 窗口
「900 s 上限放弃」之后自己跑完了，也是红的）。

---

## 4.2 ⭐ 产物清单

| 产物 | 路径 |
|---|---|
| 包 + 收据 | `D:\Github\gba-naruto\build\s49-package-w4-final\`（**不进 git**） |
| 报告 | `D:\Github\gba-naruto\docs\s49-fidelity-report-20261024.md`（**1251 行 / 148,667 B**） |
| 本笔记 | `D:\Github\gba-naruto\notes\s49-fidelity\W4-wave15-package-final.md` |
| 改动的工具 | `D:\Github\gba-naruto\tools\s49_package\make_report.py` |
| 本流的工作脚本（`build/` 不进仓） | `build\w4-dev\run-when-idle.ps1`（闸门）、`run-selftests-percase.ps1`（逐案 selftest）、`verify.ps1`（包的事实）、`check-syntax.ps1`、`check-report.py` |

---

## 5. 确认

* **未提交 git**（`git log -1` 仍是 `4d247e8c`；本流的文件都是未跟踪状态）。
* **未改 `run_pipeline.py`**、未改 `tools/s49_fidelity_report*`（W2 独占）。
  ⚠️ 本波 `run_pipeline.py` 被 **W2** 改了（12 步判据改了 **2 处**：第 1 步加前置等待、
  第 5 步改棘轮基线来源 + 三态判决）—— **不是本流改的**，
  本流用 `criteria_diff()` 独立机检过：**其余 10 步的判据逐字未改**。
* **未改重制线任何文件**、未改逆向线任何文件、**未改其它流的仪器**。
* **没有伪造任何帧**：所有数字来自收据 / 证据文件。
* **新文件全部 LF、无 BOM**（实测 `CRLF=0`、无 BOM）。
* **本波没有拿到 12/12 全绿的包**：卡点是**产品侧的 +60 px 回归**（第 5 步红），
  **不是**出包流程的问题。
