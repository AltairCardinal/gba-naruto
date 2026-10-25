# V3 —— wave 16：出包 + 1:1 报告定稿 + 判定台「复用采集不校验 ROM」的仪器修复

> 工具：`tools/s49_package/make_report.py`（**本流独占**）、
> `tools/s49_fidelity_report/capture.py`（**父代理追加的独占权**，只这一个文件）
> 产物：`build/s49-package-v3-final/`（收据 + 包，**不进 git**）、
> `docs/s49-fidelity-report-20261024.md`
> （**wave 15 的那一版已留档**在 `build/v3-dev/report-wave15.md`，
>  148,667 B / 1,251 行 / 25 条未达成项）
> 2026-10-24 · 流 V3（wave 16）· 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 任务书：`notes/s49-fidelity/WAVE16-TASKS.md` §3
> 上游：`notes/s49-fidelity/W4-wave15-package-final.md`（wave 15 的出包波）、
> `notes/s49-fidelity/W2-ratchet-baseline.md`（wave 15 的棘轮基线修正）
> ⛔ **未改**重制线任何文件；⛔ **未改** `run_pipeline.py` / `tools/s49_fidelity_report*`
> 的其余文件（wave 15 的 W2 成果）；⛔ **未改**其它流的仪器（一律**只读调用**）；
> ⛔ 逆向线全程只读；⛔ **未提交 git**。

---

## 0. 一句话结论

> ⭐⭐ **12 步流水线 12/12 全绿**（收据 `build/s49-package-v3-final/receipt.json`，
> `generated_at` = **2026-10-24T21:56:47+08:00**、`ok: true`、`failed_step: null`、
> 总耗时 **545 s**）；
> **构建 == 钉住 == 打包 == 实测**四个 sha **逐字相同** =
> `3973adcd4b329d89030603acbedf05cecbf468c21ec496cce441c144da1b6445`；
> 判定台连读 **3 次 109,569 px 逐项相同**；
> 单测棘轮 **118 pass / 20 fail（新失败 0 项）**；
> 包清单 **69 个文件**核对通过。
>
> ⭐⭐ **本波修掉了一个「会让报告说谎」的仪器缺陷**：
> 判定台 `tools/s49_fidelity_report/capture.py` 的**复用采集不校验 ROM**
> —— 复用条件只有「done 标记在不在、帧在不在」，**从不核对那份采集是哪一个 ROM 录的**
> ⇒ **可以报告一个它没测过的 ROM 的读数**（wave 15 的 W1「残差没变大」就是这样得到的假象）。
> ⇒ **已修**：复用前必须核对采集自己的审计（`audit.json` **和** `done.json`），
> 核对不过 ⇒ **绝不复用 ⇒ 重新采集**；收据里**机器可读**地写明帧来自哪个 ROM。
> ⇒ **两条判据都跑过**（§3）。
>
> ⭐ **残差 109,569 px**（wave 15 是 **109,629** ⇒ **−60 px**，wave 15 的真回归**已修掉**）；
> **棘轮判决 =「不可比」**（基线 ROM `ec5b5273…` ≠ 本次 `3973adcd…`
> ⇒ 两个数**不是同一个测量** ⇒ **这不是通过**；流水线**显式接受**了新的基线）。
>
> ⭐ **可证像素下界（为**本包这个 ROM** 重算）= 16,813 px**
> （收据 `build/v3-dev/v4-bound/bound-final.json`；交叉核对 `agrees=True`）。
>
> ⭐ **1:1 报告定稿**：`docs/s49-fidelity-report-20261024.md`
> （**未达成项逐条收口**，含「这一波的 ROM 是哪一个」的四个 sha 对照、
> **判定台「复用 vs 重采」**、**残差归零不可达的下界**、**V4 的同刻相位归因**、
> **结算链的「poke 版 vs 真实战斗版」分列**）。
>
> ⛔ **「真实打完仗」仍未达成**：V1 查实了**产品缺陷 D4**
> （玩家的攻击一旦射程内有活敌人，战斗场景就废了 ⇒ `outcome=1` 不可达）；
> 而 V2 在新 ROM 上的 20 页链是 **`controller state poke`** 出来的
> ⇒ **两版都不是「真实战斗打出来的胜利链」** ⇒ 报告**分别标注**，不许混用。

---

## 1. 本流改了什么

| 文件 | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_fidelity_report\capture.py` | **改** | ⭐ **父代理追加的任务**：复用采集必须核对 ROM。① 新增 `read_audit()` / `expected_identity()` / `verify_capture_identity()`；② `run_capture()` 的复用分支**先核对审计**（重制侧 `rom_sha256`、原版侧 `input_state_sha256`，**两个证人互相矛盾 ⇒ 拒绝**），核对不过 ⇒ **重新采集**；③ 收据新增 `measured_rom_sha256` / `measured_rom_sha256_source` / `reuse_decision`（**测量稳定**）与 `attempts[0]`（`kind = "reuse-decision"`，**运行出处** ⇒ 随 `attempts` 一起移出测量摘要）。 |
| `D:\Github\gba-naruto\tools\s49_package\make_report.py` | **改** | ① 标题改成 **wave 16 定稿**；② 新增 wave 16 的读取器（`wave16_cutoff_mtime()` / `wave16_notes()` / `wave16_streams()` / `wave16_settlement_rows()` / `wave16_bounds()` / `wave16_bound()` / `wave16_phase_attribution()` / `rom_identity()` / `w16_status()`）；③ 新增 **§2.0c「这一波的 ROM 是哪一个」**（构建 / 钉住 / 打包 / 实测**四个 sha**）；④ **§2.0.2** 改成「已修 + 两条判据」；⑤ **§11 第 22 项**改成「已修」；⑥ **§11 新增第 23 项**（wave 16 的交付状态）与**第 24 项**（wave 15 的 **+60 px 真回归**）；⑦ **§15.2.3**（V1 的**真实版**逐屏对照表）；⑧ **§14.10** wave 16 的台账；⑨ §0 加两条摘要；⑩ 新增 **§3.5**（V4 的**同刻**归因：那 50 格**不是**「walk 没走到」，而是「**产品缺一段演出**」）与 §11 第 3 项里的口径提醒。 |
| `D:\Github\gba-naruto\notes\s49-fidelity\V3-wave16-package.md` | **新增** | 本文件。 |
| `D:\Github\gba-naruto\docs\s49-fidelity-report-20261024.md` | **改** | 1:1 报告定稿（wave 15 的那一版留档在 `build/v3-dev/report-wave15.md`）。 |

**没有**改重制线任何文件、逆向线任何文件、其它流的仪器。
⛔ **`run_pipeline.py` 一个字未改**；⛔ **`tools/s49_fidelity_report/` 里除 `capture.py` 外的
文件一个字未改**（wave 15 的 W2 成果）；⛔ **12 步的判据一个字未改**。

---

## 2. ⭐ 仪器缺陷：复用采集不校验 ROM（父代理追加）

### 2.1 缺陷（wave 15 / W4 查实）

```python
# 修之前（tools/s49_fidelity_report/capture.py::run_capture）
if reuse and done_marker.exists() and sorted(out_dir.glob("step-*.png")):
    reused = True          # ← 从不核对那份采集是哪一个 ROM 录的
```

⇒ 报告随后把帧标成**它被要求测的**那个 ROM 的 sha256
⇒ **同一个工作目录里换 ROM 重跑，会拿到上一个 ROM 的帧、却标成新 ROM 的读数**。
⇒ wave 15 的后果：W1 的「判定台残差没有变大」是**复用 wave 14 包里的采集目录**得到的
（采集的 audit ROM 是 wave 14 的 `ec5b5273…`，却被标成新 ROM `fb9d2dbd…`）
⇒ **它比的是 wave 14 的帧和 wave 14 的帧** ⇒ 「逐项相同」是**必然的**，不是证据。

### 2.2 修法

| 侧 | 采集的审计里有什么 | 核对什么 |
|---|---|---|
| remake | `rom_sha256`（录的时候 boot 的那个 ROM 的摘要） | **必须 == 本次要测的 ROM 的 sha256** |
| original | `input_state_sha256`（boot 用的那个存档的摘要；它的 ROM 是常量） | **必须 == 本次请求的存档摘要** |

* **两个证人**（`audit.json` **和** `done.json`）都读；**互相矛盾 ⇒ 拒绝**。
* **核对不过 ⇒ 绝不复用 ⇒ 重新采集**（收据里写明「ROM 变了，已重采」与差在哪个摘要上）。
* **核对不过、也没有任何可核对的摘要 ⇒ 拒绝**（fail closed）。
* 收据里**机器可读**地写明：`captures.<side>.measured_rom_sha256`（帧到底来自哪个 ROM）、
  `captures.<side>.reuse_decision`（测量稳定的事实）、
  `run.attempts.<side>[0]`（复用/重采 + 原因，运行出处）。

### 2.3 ⭐ 为什么新字段**不会**破坏 `content_sha256` 的可复现承诺

判定台 CLI（**不是本流能改的文件**）在算 `content_sha256` 之前会把
`attempts` 与 `reused` 从 `captures` 里 **pop 出去**（放到 `run`）——
注释明写「Run provenance … is kept out of the measurement digest」。

⇒ 因此：**运行出处**（复用/重采 + 原因）放进 `attempts`（**在摘要外**），
**测量稳定**的事实放进 `reuse_decision`（**在摘要内**）。
⇒ 「重采」与「复用」两次读数的 `content_sha256` **完全相同** —— 实测确认（§3 判据 B）。

---

## 3. ⭐ 两条判据（可复跑）

```powershell
cd D:\Github\gba-naruto
python build\v3-dev\test_capture_identity.py       # 单元级：7/7
python build\v3-dev\prove_capture_rom_check.py     # 端到端：6/6
```

| 判据 | 做法 | 实测结果 |
|---|---|---|
| **A：审计说别的 ROM ⇒ 必须重采** | 把 `audit.json` / `done.json` 里的 `rom_sha256`（原版侧是 `input_state_sha256`）改成**另一个 ROM / 另一个存档**的值，再用 `--skip-capture` 跑判定台 | **两侧都重新采集**（`action = recaptured`）：原版侧的理由是「`input_state_sha256` differs: … 记录的是 `0000…`，本次请求的是 `a3628723…`」；重制侧是「`rom_sha256` differs: … 记录的是 `ec5b5273…`，本次请求的是 `fb9d2dbd…`」 |
| **B：审计说同一个 ROM ⇒ 可以复用，且读数与重采逐项相同** | **同一个 work 目录**里连跑三次：① 重采 ② 篡改后重采 ③ 复用 | ③ **两侧都复用**（`action = reused`）；**三次的 `content_sha256` 完全相同**（`30332e8380fb0776…`）⇒ 残差总和 / 中位 / 归因**逐项相同**（109,629 / 1,432 / 一致 4 · 产品差 17 · 配对差 4）⇒ **复用不改变读数** |

⚠️ **为什么三次必须在同一个 work 目录**：`content_sha256` 覆盖 `captures`，而
`captures.<side>.output_dir` 等字段里是**绝对路径** ⇒ 换目录就换摘要。
（第一版证明脚本用三个目录 ⇒ 摘要只差路径，**测出来的是路径差，不是读数差**；
这本身也说明**复用判定没有污染测量口径**。）

---

## 4. 12 步流水线

### 4.1 ⭐ 为什么**必须等**（wave 14 / wave 15 的教训）

* **wave 14**：Z4 跑了**三次**才全绿，前两次的红**都不是出包流程的 bug** ——
  第一次是并行流把 ROM 弄崩（步骤 5 红），第二次是并行流在「构建」与「钉住」之间
  重建了 ROM（步骤 1 红）。
* **wave 15**：W4 跑了一次，**11 绿 / 第 5 步红** —— 那是**真阳性**
  （残差 109,569 → 109,629，+60 px），只有修好的棘轮才看得见。

⇒ 本流用**闸门脚本** `build/v3-dev/run-when-idle.ps1` 把「等」写成**可执行的**：

| 闸门条件 | 为什么 |
|---|---|
| V1 交付（**以笔记标题认领**，以 `WAVE16-TASKS.md` 的 mtime 为界） | 任务书要求「等 V1/V2 落地后重跑」 |
| **ROM 在本波被重建过**（mtime > 任务书） | V2 的产品修复必须**在**被测的 ROM 里 |
| 重制源码树与 ROM **安静 ≥ 150 s** | 并行流不在半路上改文件 |
| 没有 `mgba-probe*.exe` / `wsl` / `make` 在跑，内存 > 4 GB | 全量录制吃 7–8 GB ⇒ 步骤 5 的采集会被杀 |
| **有一个下界收据是为「这个 ROM」重算的** | 下界是**针对某一份录制**的；换了 ROM 就过期（V4 自己的笔记这么说） |

⚠️ **闸门超时不会跑流水线**（退出码 3）⇒ 不会产出一个「半成品的包」。

### 4.2 ⭐ 本次的跑法与数字

| 项 | 值 |
|---|---|
| 收据 | `build/s49-package-v3-final/receipt.json`（`generated_at` = **2026-10-24T21:56:47+08:00**，`ok: true`，`failed_step: null`） |
| 步骤 | **12 / 12 全绿**（总耗时 **545 s**） |
| **ROM（四个 sha）** | 构建 / 钉住 / 打包 / 实测 **逐字相同** = `3973adcd4b329d89030603acbedf05cecbf468c21ec496cce441c144da1b6445`（12,114,016 B，构建于 21:51:02） |
| 采集 | original / remake **两侧都是 `captured`（新录）**，`identity_verified = True` |
| **残差** | 总和 **109,569 px** / 中位 **1,372** / 峰值 **27,325** / 全 0 帧 **4 / 25**；归因 一致 **4** · 产品差 **17** · 配对差 **4** |
| 读数确定性 | 连读 **3 次** 全是 **109,569 px**，`determinism.identical = true` ⇒ **残差变了就是产品变了** |
| **棘轮判决** | **`incomparable`**（基线 ROM `ec5b5273…` ≠ 本次 `3973adcd…`）⇒ **残差不是同一个测量 ⇒ 这不是通过**；流水线**显式接受**了新基线（`accepted_baseline_promoted.ok = true`） |
| 单测棘轮 | HEAD **101 pass / 20 fail** / 工作区 **118 pass / 20 fail** / `new_failures = []` ⇒ **20 项预存债，零回归** |
| 覆盖层 | `field` / `movegrid` **同亮 192 / 原版缺 0 / 多画 0**（**192/0/0 已达成**）；`grid16` 175 / 0 / 17；`banner` 0 / 0 / 0；剩下的 **176 格** = **原版尾部残留 44 / walk 相位 130 / 产品差 2** |
| 黑场 | 原版 **2** 个（24/18/24；24/24/24）；重制侧 **6** 个（0/8/0；0/6/0；**24/18/26**；0/2/0；0/8/0；28/24/28）⇒ ⭐ wave 15 的第三个事件是 **24/20/28**，**淡入 28 → 26**（更靠近原版的 24） |
| **可证像素下界（为这个 ROM 重算）** | **16,813 px**（收据 `build/v3-dev/v4-bound/bound-final.json`；`canonical_sum` = 91,935；重制侧 783 帧 / 379 张去重；**与 `pair.beat_floor` 交叉核对 `agrees=True`**）⇒ **归零在当前 ROM 上不可达** |
| 包清单 | **69 个文件**核对通过（`the manifest matches the package`） |

### 4.3 产物

| 产物 | 路径 |
|---|---|
| 包 + 收据 | `D:\Github\gba-naruto\build\s49-package-v3-final\`（**不进 git**） |
| 报告 | `D:\Github\gba-naruto\docs\s49-fidelity-report-20261024.md` |
| 本笔记 | `D:\Github\gba-naruto\notes\s49-fidelity\V3-wave16-package.md` |
| 改动的工具 | `D:\Github\gba-naruto\tools\s49_package\make_report.py`、`D:\Github\gba-naruto\tools\s49_fidelity_report\capture.py` |
| 本流的工作脚本（`build/` 不进仓） | `build/v3-dev/`（闸门、selftest 逐案、下界重算、两条判据的证明、编码自检、摘要） |

---

## 5. 报告定稿的「未达成项」收口

| 要求 | 落在报告的哪里 | 状态 |
|---|---|---|
| ⭐ 原版 S49 结算屏真值 —— 已闭合 | §15 / §11 第 1 项 | ✅ wave 8 的 W4 交付，本波沿用 |
| **结算链运行帧对照（V1 的真实版逐屏表）** | **§15.2.3** | ⭐ V1 交付了**逐屏对照表工具 + 90 行表**（`build/v1/compare-real-defeat.json`）⇒ **那是「真实战斗产生的败北屏」**（`outcome=2`）；⛔ **V2 在新 ROM 上的 20 页链（`build/v2/chain-d/chain.json`）是 `controller state poke` 出来的**（`entry.method` 自报）⇒ **屏上战果是空的** ⇒ ⛔ **「真实打完仗」未达成**（§11 第 25 项）。⚠️ **poke 版与真实版不许混用** |
| ⭐ **残差归零不可达**：**为最终 ROM 重算过的**可证像素下界 + 证明方式 | §11 第 2 项 / §14.10 | ⭐ `wave16_bound(本次 ROM 的 sha)` 只接受**与本次 ROM 完全相同**的那份；否则明写「未为当前 ROM 重算」 |
| ⚠️ **判定台的数字与下界不是同一口径，不许混用** | §11 第 2 项末尾的「三个数不许混用」警告 | ✅ 保留并加粗 |
| ⭐ 覆盖层「192/0/0」已达成 | §3 / §11 第 3 项 | ✅ 沿用 wave 13 / Y2 的口径 |
| 剩余 176 格逐格性质（尾部 44 / 相位 130 / 产品差 2） | §3.3 / §11 第 3 项 | ✅ 沿用（逐格明细） |
| ⚠️ **`grid16` 的 80 格进「明确排除项」**（与 Y2 的尾部残留并列） | **§10** | ✅ wave 15 已进；本波保留 |
| 存档逐字节一致按用户口径排除 | §10 / §11 第 6 项 | ✅ |
| 音频逐采样一致排除（80–120 h） | §10 / §11 第 7 项 | ✅ |
| **20 项单测在 HEAD 即为红（预存债），本次零回归** | §11 第 8 项 | ✅ 数据驱动（步骤 2 的收据） |
| 判定台抖动 —— **已查清闭合** | §11 第 15 项 | ✅ wave 11 / W4 查实：wave 10 那两次跑的 **ROM sha256 不同** ⇒ 是产品改动，不是仪器 |
| 黑场事件数/时长（V2 的结果） | §7 / §11 第 11 项 | ✅ **数据驱动**（步骤 9 的收据） |
| 对话框斜切展开（实为入场转场）若未复现要单列 | §11 第 13 项 | ✅ 单列（wave 16 仍未复现） |
| 本机构建**非字节可复现**（同源码两个 sha）⇒ 随包带 ROM + 重录命令 | §11 第 10 项 / §12 | ✅ 写明「同一份源码树两次构建出的 sha 不同」 |
| ⭐ **同名笔记坑** ⇒「本波已交付」以**任务书 mtime** 为界 | §11 第 23 项 / §14.10 | ✅ `wave16_cutoff_mtime()` |
| ⭐ **这一波的 ROM 是哪个**（四个 sha 一致，不一致要报出来） | **§2.0c** / §11 第 14 项 | ✅ 新增 `rom_identity()` |
| ⭐ **「walk 相位 50 格」的同刻归因**（V4 查实：**不是**「walk 没走到」） | **§3.5** | ✅ 新增：同刻逐格对照 + 相位族共现统计 + 「**产品缺一段演出**」的三条可判定证据；⚠️ **跨时刻 130 格与同刻 56 格两个口径不许混用** |

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **V3w-1** | V1 / V2 / V4 在本波开工前是否已经交付 | 读 `notes/s49-fidelity/` 里**在 `WAVE16-TASKS.md` 之后**写的笔记 + 查重制线源码与 ROM 的 mtime | 开工时（21:04）**三路都没有**；21:19 **V4 交付**（`V4-bound-final.md`）；**V1 / V2 未交付** ⇒ 本流第一件事是**等** | **已确认** |
| **V3w-2** | 「本波已交付」能不能用笔记的**文件名前缀**判定 | 读 `notes/s49-fidelity/` 里的同名笔记（wave 7 的 `Z1/Z2/Z3`、wave 5/6/8 的 `W1/W2/W3`） | **不能** ⇒ 判定必须**以任务书的 mtime 为界**（`wave16_cutoff_mtime()` / `wave16_notes()` / `wave16_streams()`） | **已证伪** |
| **V3w-3** | 判定台复用采集时会不会核对 ROM | 读 `tools/s49_fidelity_report/capture.py::run_capture()` 的复用分支 | **不会** —— 复用条件只有「done 标记在不在、帧在不在」，**从不核对那份采集是哪一个 ROM 录的** ⇒ **可以报告一个它没测过的 ROM 的读数** | **已确认（缺陷）** |
| **V3w-4** | 修好之后，复用采集时会不会仍然复用别的 ROM 的采集 | 把采集的 `audit.json` / `done.json` 里的 `rom_sha256`（原版侧是 `input_state_sha256`）改成**另一个 ROM / 另一个存档**的值，再用 `--skip-capture` 跑判定台 | **不会** ⇒ **两侧都重新采集**（`action = recaptured`），收据里写明差在哪个摘要上 | **已确认（已修）** |
| **V3w-5** | ROM 一致时能不能复用，且读数与重采**逐项相同** | **同一个 work 目录**里连跑三次：① 重采 ② 篡改后重采 ③ 复用 | **能** ⇒ 三次的 `content_sha256` **完全相同**（`30332e8380fb0776…`），残差总和 / 中位 / 归因**逐项相同** | **已确认（已修）** |
| **V3w-6** | 收据里新增字段会不会破坏 `content_sha256` 的可复现承诺 | 比「重采」与「复用」两份收据的**逐叶差异** | **不会** —— 差异只剩**绝对路径**；`reuse_decision`（测量稳定）在摘要内、复用/重采 + 原因（运行出处）随 `attempts` 移出摘要 | **已确认** |
| **V3w-7** | 「三次跑」的比较口径对不对 | 第一版证明脚本用**三个不同**的 work 目录 ⇒ 摘要只差**路径** | **不对** ⇒ 改成**同一个** work 目录 ⇒ 摘要才可比（这本身也证明**复用判定没有污染测量口径**） | **已证伪（已修）** |
| **V3w-8** | 报告能不能读出 V4 的收据 | 按**中文「相位」**关键字找（wave 14 的读法） | **不能** —— V4 的收据 `build/s49-v4/phase-v4.json` **通篇是英文键**（`schema = konoha.s49-v4.phase-locate/1`）⇒ 改成**按 schema 认领** | **已证伪（已修）** |
| **V3w-9** | V4 的下界是不是为**最终 ROM** 算的 | 读 V4 的收据 `roms.remake.sha256` 与盘上的 ROM | **不是** —— V4 的 16,350 px 测于 `fb9d2dbd…`（**V1/V2 落地前**的 ROM）；V4 自己的笔记明写「**V1/V2 落地后必须重算**」⇒ 本流**用 V4 的工具只读重算**（`build/v3-dev/recompute-bound.ps1`） | **已确认（是产品改动）** |
| **V3w-10** | V2 有没有笔记可读 | 读任务书 §2.1 的独占文件清单 | **没有** —— V2 的独占文件**全在重制线** ⇒ 「V2 是否交付」**不能**看笔记，只能看**产品**：本流水线在**钉住的 ROM** 上的实测 + ROM 是否在本波被重建过 | **已确认** |
| **V3w-11** | 报告生成器能不能在**新旧两种收据形状**下都工作 | ① 用 wave 15 的旧收据跑一遍；② 读本次收据 | **能**（旧收据没有 `reuse_decision` ⇒ 对应格显示「—」；新收据有 ⇒ 显示 `captured` / `reused`） | **已确认** |
| **V3w-12** | 12 步的判据有没有被本流改掉 | 比两份收据里 12 条判据的字面量（`criteria_diff()`） | **没有** —— 本流只改**报告生成器**与 `capture.py`；**`run_pipeline.py` 一个字未改** | **已确认** |
| **V3w-13** | 「四个 sha 一致」的判据能不能在**四个摘要都相同**时判成一致 | 拿 wave 15 的收据跑一遍 §2.0c | **第一版判错**：四个摘要放进 `set` 之后长度是 **1**（不是 4）⇒ 「凑齐」的判据写成了 `len(values) == 4` ⇒ **一致却报「没有凑齐」** ⇒ 改成「**非空摘要的个数 == 4** 且**去重后 == 1**」 | **已证伪（已修）** |
| **V3w-14** | V1 的逐屏对照表能不能被报告读取器找到 | 读 `build/v1/compare-real-defeat.json` 的形状（`screens` 90 行，列有 `remake_sha256` / `truth_sha256` / `diff_pixels` / `bbox`） | **能** —— 但**文件名不含** `settlement`/`chain` ⇒ 第一遍「按文件名找」**找不到** ⇒ 报告生成器补了**第二遍「按形状找」**（≥3 行、每行带 64 位 sha、带差值）⇒ 找到了 | **已确认** |
| **V3w-15** | 「真实打完仗」能不能在本波达成 | 读 V1 的笔记 §0 + **V2 自己的链收据** `build/v2/chain-d/chain.json` | **不能** —— ① V1 查实了**产品缺陷 D4**（「玩家的攻击一旦射程内有活着的敌人，战斗场景就废了」）⇒ **`outcome=1` 不可达**；② **V2 在新 ROM 上的 20 页链是 `controller state poke` 出来的**（收据里 `entry.method` 自报「controller state poke (phase + outcome)」，`outcome_byte_before_poke = 0` → `after_poke = 1`）⇒ **屏上战果是空的** ⇒ **两版都不是「真实战斗打出来的胜利链」** ⇒ 报告**必须分别标注**，不许混用 | **已确认（未达成）** |
| **V3w-16** | 等到 V1/V2 落地后重跑，能不能 **12/12 全绿** | 闸门 `build/v3-dev/run-when-idle.ps1`（V1 交付 + ROM 在本波被重建 + 源码/ROM 安静 150 s + 无探针/构建）→ `run_pipeline.py --out build/s49-package-v3-final` | **能** —— **12/12 全绿**（`ok: true`、`failed_step: null`、545 s）；⛔ **但棘轮判决是「不可比」而不是「通过」**（基线 ROM 不同 ⇒ 残差不是同一个测量）⇒ 流水线**显式接受**了新基线 | **已确认（绿，但「不可比 ≠ 通过」）** |
| **V3w-17** | 本波残差有没有比 wave 15 变小 | 比两次收据的残差摘要（同一个口径、同一台仪器） | **变小了**：wave 15 **109,629 px** → 本波 **109,569 px**（**−60 px**）⇒ **wave 15 的 +60 px 真回归被修掉了**；⚠️ 但**相对被接受的基线（wave 14 的 109,569）是「相同」**，且 ROM 变了 ⇒ 判决仍是**不可比** | **已确认** |
| **V3w-18** | 可证像素下界能不能为**本包这个 ROM** 重算 | 用 **V4 已交付的工具**（`tools/s49_z3_bound/`，**只读调用**）对**钉住 ROM** 重录重制侧 + 重算 | **能** —— **16,813 px**（`canonical_sum` 91,935；783 帧 / 379 去重；**`pair.beat_floor` 交叉核对 `agrees=True`**）；原版侧重录 **553 帧、指纹 `ffa679a0…` 与 V4 的逐字节相同**（⇒ 录制是确定的）⇒ **重制侧指纹不同**（`e6c3bbde…` vs V4 的 `b91900e7…`）⇒ **差来自 ROM** | **已确认** |
| **V3w-19** | 覆盖层的「192/0/0」与剩余 176 格的逐格性质 | 读步骤 6 的 `cell_classification` | **192/0/0 已达成**；剩下的 **176 格** = **原版尾部残留 44 / walk 相位 130 / 产品差 2**（与 wave 13/14/15 **逐项相同**） | **已确认** |

---

## 7. 复现命令

```powershell
cd D:\Github\gba-naruto

# 0) 跑流水线前：等「V1 交付 + ROM 在本波被重建过 + ROM/源码稳定 150 s + 没有探针/构建在跑」
#    并且「有一个下界收据是为**这个** ROM 重算的」
powershell -NoProfile -ExecutionPolicy Bypass -File build\v3-dev\run-when-idle.ps1

# 1) 12 步流水线（**换包目录** ⇒ 草稿残留自动清掉）
python tools/s49_package/run_pipeline.py --out build/s49-package-v3-final

# 2) 11 个 selftest（每个步骤故意破坏 ⇒ 必须全红）
powershell -NoProfile -ExecutionPolicy Bypass -File tools/s49_package/run_selftests.ps1 `
    -PackageDir 'build/s49-package-v3-final'

# 3) selftest 把证据写进包里之后，重写并核对包清单
python tools/s49_package/run_pipeline.py `
    --out build/s49-package-v3-final --verify-manifest

# 4) 报告
python tools/s49_package/make_report.py `
    --receipt build/s49-package-v3-final/receipt.json `
    --out docs/s49-fidelity-report-20261024.md

# 5) 判定台「复用采集必须核对 ROM」的两条判据
python build/v3-dev/test_capture_identity.py
python build/v3-dev/prove_capture_rom_check.py

# 6) 为**最终 ROM** 重算可证像素下界（**只读调用** V4 已交付的工具）
powershell -NoProfile -ExecutionPolicy Bypass -File build\v3-dev\recompute-bound.ps1 `
    -Rom 'build\s49-package-v3-final\work\pinned-rom\measured.gba'

# 7) 同一个 ROM 的**内容锚可达上界**（夹逼的上端；**只读调用**配对流的仪器）
python tools\s49_pairing\pairing_report.py --walk build\v3-dev\v4-bound\walk `
    --out build\v3-dev\v4-bound\pairing --no-floor
```

---

## 8. 卡在哪 / 遗留风险

1. ⛔ **V1（真实打完仗）是本波最长的依赖**。它是**驾驶/仪器**侧，
   **不改产品** ⇒ 本流的**包**不依赖它；但任务书要求「等 V1/V2 落地后重跑」。
   ⇒ 闸门把 V1 做成**软条件**（有自己的截止时间）：截止后流水线照跑，
   报告**如实写「V1 尚未交付」**（§11 第 23 项 + §15.2.3），
   **V1 一落地，重跑一次 `make_report.py`（约 2 分钟，只读）就能补上真实版逐屏表**。
2. ⚠️ **V4 的下界 16,350 px 测于 ROM `fb9d2dbd…`**（V1/V2 落地**前**的 ROM）。
   V4 自己的笔记明写「**产品改动后必须重算**」⇒ 本流**用 V4 已交付的工具只读重算**
   （`build/v3-dev/recompute-bound.ps1`）⇒ 报告里引用的是
   **本包这个 ROM 的**下界（若重算没有跑成，报告会**如实写**
   「未为当前 ROM 重算」）。
3. ⚠️ **本机构建非字节可复现** ⇒ 随包带 ROM + 重录命令（§12）；
   复现要**先建私有探针**（`KONOHA_PROBE_OUT` 指到私有目录，
   **不要覆盖共享的 `build/mgba-probe/mgba-probe.exe`**，会 LNK1104）。
4. ⚠️ **覆盖层的「50 格 → 56 格」口径修正没有落进分类文件**：
   `tools/s49_package/classify_overlay_cells.py` **本流未改**
   ⇒ §3.3 仍是**跨时刻**口径，**§3.5** 是 V4 的**同刻**口径
   ⇒ **两个数不许混用**（V4 笔记 §5 的第 5 条）。
5. ⚠️ **「斜切展开」（实为入场转场）本波仍未复现** ⇒ 单列在 §11 第 13 项。
6. ⚠️ **不要在别的流还在跑录制时重跑流水线**：全量录制吃 7–8 GB 且持续泄漏
   ⇒ 步骤 5 的采集会被杀（wave 14 的第一次红就是这个原因）。
   ⇒ **同一时刻只允许一路做构建**。

---

## 9. ⭐ 本波跑了哪些验证（命令 + 关键数字）

| # | 验证 | 命令 | 结果 |
|---|---|---|---|
| 1 | **12 步流水线** | `build/v3-dev/run-when-idle.ps1` → `run_pipeline.py --out build/s49-package-v3-final` | **12 / 12 全绿**（`ok: true`、`failed_step: null`、545 s） |
| 2 | **ROM 四 sha 一致** | 比步骤 1 的 `rom_sha256` / `pinned_rom_sha256`、步骤 12 的 `rom_sha256`、判定台收据的 `captures.remake.measured_rom_sha256` | **四者逐字相同** = `3973adcd4b329d89030603acbedf05cecbf468c21ec496cce441c144da1b6445`（§2.0c） |
| 3 | **单测棘轮** | 步骤 2 | HEAD **101 pass / 20 fail** / 工作区 **118 pass / 20 fail** / `new_failures = []` ⇒ **20 项预存债，零回归** |
| 4 | **判定台 3 次读数一致性** | 步骤 5（`--repeat 3`） | `determinism.identical = true` ⇒ 连读 3 次 **109,569 px** 逐项相同 |
| 5 | **棘轮判决** | 收据顶层 `ratchet` | **`incomparable`**（基线 ROM `ec5b5273…` ≠ 本次 `3973adcd…`）⇒ **残差不是同一个测量 ⇒ 这不是通过**；流水线**显式接受**了新基线（`accepted_baseline_promoted.ok = true`） |
| 6 | **残差 vs wave 15** | 比两次收据 | **109,629 → 109,569 px（−60）** ⇒ **wave 15 的 +60 px 真回归被修掉了** |
| 7 | **11 个 selftest 全红** | `build/v3-dev/run-selftests-percase.ps1` | **11 red, 0 not red**（证据 `build/s49-package-v3-final/evidence/selftest-break.txt`） |
| 8 | **包清单** | `run_pipeline.py --out build/s49-package-v3-final --verify-manifest` | **the manifest matches the package (198 files)** |
| 9 | **判定台「复用必须核对 ROM」· 单元级** | `python build/v3-dev/test_capture_identity.py` | **7 / 7**（匹配 ⇒ 复用；不匹配 / 缺审计 / 两个证人矛盾 ⇒ 拒绝） |
| 10 | **判定台「复用必须核对 ROM」· 端到端** | `python build/v3-dev/prove_capture_rom_check.py` | **6 / 6**（篡改审计 ⇒ **两侧都重采**；审计一致 ⇒ **复用**；**三次的 `content_sha256` 完全相同** ⇒ 复用不改变读数） |
| 11 | **可证像素下界（为最终 ROM 重算）** | `build/v3-dev/recompute-bound.ps1 -Rom build\s49-package-v3-final\work\pinned-rom\measured.gba` | **16,813 px**（`canonical_sum` 91,935；783 帧 / 379 去重；**交叉核对 `agrees=True`**）；原版侧 553 帧、指纹 `ffa679a0…` **与 V4 的逐字节相同** ⇒ 录制是确定的 |
| 12 | **内容锚可达上界（同一个 ROM）** | `python tools/s49_pairing/pairing_report.py --walk build\v3-dev\v4-bound\walk --out build\v3-dev\v4-bound\pairing --no-floor` | **19,595 px**（同刻 **21 / 25**）⇒ **夹逼 16,813 ≤ opt ≤ 19,595（上下界同一个 ROM）** |
| 13 | **覆盖层逐格** | 步骤 6 | 同亮 **192 / 原版缺 0 / 多画 0**；`grid16` 175/0/17；剩下的 **176 格** = **尾部残留 44 / walk 相位 130 / 产品差 2** |
| 14 | **黑场** | 步骤 9 | 原版 **2** 个（24/18/24；24/24/24）；重制侧 **6** 个（0/8/0；0/6/0；**24/18/26**；0/2/0；0/8/0；28/24/28）⇒ ⭐ wave 15 的 **24/20/28** ⇒ **24/18/26**（淡入 28 → 26） |
| 15 | **编码自检** | `python build/v3-dev/check_encoding.py` | **8 / 8**（全部 **LF、无 BOM**） |
| 16 | **共享探针没被覆盖** | 比 `build/mgba-probe/mgba-probe.exe` 的 mtime | **未动**（仍 2026-10-23 23:21:42）⇒ 本流用的是**私有探针** `build/mgba-probe-v3/` |

---

## 10. 确认

* **新文件全部 LF、无 BOM**（实测 8 / 8：`make_report.py`、`capture.py`、本笔记、报告、`build/v3-dev/*`）。
* **未提交 git**（`git log -1` 仍是 `4d247e8c`；本流的文件全是 `??` 未跟踪状态）。
* **未改 `run_pipeline.py`**（一个字未改 ⇒ **12 步的判据逐字未动**；收据里的判据字面量可机检）。
* **未改 `tools/s49_fidelity_report/` 里除 `capture.py` 外的任何文件**（wave 15 的 W2 成果）。
* **未改重制线任何文件**（`D:\Shell\Github\gba-naruto-butano` **只读使用**：只读了它的
  `git status` / 文件 mtime / ROM 的 sha，**构建由流水线的步骤 1 做**）。
* **未改逆向线任何文件**。
* **未改其它流的仪器**：`tools/s49_z3_bound/`、`tools/s49_pairing/`、
  `tools/s49_battle_balance/` 一律**只读调用**。
* **没有伪造任何帧**：所有数字都来自收据 / 证据文件 / 盘上的产物。
* ⚠️ **只改了两个文件**：`tools/s49_package/make_report.py`（本流独占）、
  `tools/s49_fidelity_report/capture.py`（父代理追加的独占权）。
