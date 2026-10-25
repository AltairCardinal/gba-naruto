# W2 —— wave 15 棘轮基线修正（仪器缺陷修正）

> 2026-10-24 · 流 W2（wave 15）· 独占文件：`tools/s49_package/run_pipeline.py`、
> `tools/s49_fidelity_report.py` + `tools/s49_fidelity_report/`
> ⛔ **未改** `make_report.py`（W4 独占）、未改重制线任何文件、未改逆向线、未提交 git。

---

## 0. 一句话结论

⭐ **棘轮现在能抓住回归了**：基线从「包目录里的历史参考报告」改成
**「上一波被接受的收据」**（`build/s49-package/baseline-accepted/`），
Z4 漏掉的那次 **+9,359 px（+9.3 %）** 回归现在**必红**；
ROM 变了且残差没变大时报 **「不可比」（退出码 2）**，**不再静默 PASS**。

---

## 1. 问题与修法（Z4 查实的仪器缺陷）

| | wave 14 之前（缺陷） | wave 15 之后（本流） |
|---|---|---|
| 棘轮基线放在哪 | **包目录内** `<package>/baseline/baseline-report.json` | **包目录外** `build/s49-package/baseline-accepted/` |
| 换包目录重跑会怎样 | 基线丢失 ⇒ 从 **wave 4 的参考报告**（168,357 px）起步 | 基线**活着** ⇒ 比的是**上一波被接受的收据**（wave 13：100,210 px） |
| wave 13 → wave 14 的 +9,359 px | **静默 PASS** ❌ | **变红** ✅ |
| ROM 变了 | `changed` 标志只写进收据，**`ok` 不变** ⇒ 照样 PASS | 三态判决：`pass` / `fail` / **`incomparable`**（退出码 0 / 1 / **2**） |

⇒ 根因：**基线跟着包目录一起死**。修法：**基线独立于包目录存在**，
且**只有全绿的收据才能当基线**。

---

## 2. 改了什么

### 2.1 新增：`tools/s49_fidelity_report/accepted.py`（被接受的基线仓库）

* `AcceptedBaseline(root)` —— 仓库：`report.json`（被接受的测量）+ `receipt.json`（接受记录：来源包、ROM sha256、残差摘要、**历史链**）。
* `find_last_accepted_package(build_root)` —— 扫 `build/s49-package*/receipt.json`，
  按 mtime 倒序，取**第一个** `ok is True` **且** `failed_step is None`
  **且** 真的有判定台报告的包。
* `promote_package(package, root)` —— **只接受全绿的包**；不绿 ⇒ **拒绝**。

### 2.2 `tools/s49_fidelity_report/ratchet.py` —— 三态判决

| 状态 | 条件 | 含义 |
|---|---|---|
| `pass` | ROM 相同 **且** 没有指标变差 | 通过 |
| `fail` | **任何指标变差**（**跨 ROM 也算**） | 残差变大了 ⇒ 判红 |
| `incomparable` | ROM 变了 **且** 没有指标变差 | **不可比** ⇒ 明确**不是**通过 |

⚠️ 关键取舍：**ROM 变了不等于免罪**。「残差变大」这句话在两侧都是像素口径，
成立 ⇒ 一律 `fail`。只有「没变大 + ROM 不同」才是 `incomparable`。
（Z4 那次 +9,359 px 正是跨 ROM 的，**必须**能变红。）

### 2.3 `tools/s49_fidelity_report.py` —— 退出码 + 口径说明

* 退出码：**0 = pass / 1 = fail / 2 = incomparable**（三者可区分）。
* markdown 收据新增「口径说明」段：判定台的战场区残差是 **arg-min 对齐残差
  （不带时刻约束）**，**不是**任何「可证像素下界」的下界，两个口径**不许混用**。

### 2.4 `tools/s49_package/run_pipeline.py`

* **步骤 5**：棘轮基线 = `ctx.accepted.report_path`（包目录外）；
  仓库为空 ⇒ 自动认领盘上**最近一次全绿的收据**；盘上也没有 ⇒ 回落到
  wave-4 参考报告并在 notes 里**明写「这不是上一波」**。
* **步骤 1**：新增**前置等待** —— 「ROM 文件连续 150 s 不变 + 没有
  `mgba-probe.exe` 在跑」⇒ 再构建、再钉（Z4 跑了三次才绿的教训）。
* 流水线**尾部**：只有**全绿**的跑法才会把本次测量提升为「被接受的基线」；
  不绿的跑法 ⇒ **拒绝提升**（并在控制台明写）。
* 收据新增顶层字段：`ratchet`（判决 + 两侧 ROM sha + 逐项对照）、
  `accepted_baseline`（下一波的比较对象）、`accepted_baseline_promoted`、`notes`（口径说明）。
* `receipt.md` 新增「棘轮基线」「被接受的基线」两节。
* 新增 CLI：`--accept-baseline`、`--accepted-baseline`、`--rom-settle-seconds`、
  `--rom-settle-max-seconds`。

---

## 3. 跑了哪些验证

### 3.1 ⭐ 判据 A：**残差变大 ⇒ 流水线变红**

**坏样例 = 真回归本身**：wave 13 的收据（`build/s49-package-y4-final`，`ok:true`，
残差 **100,210 px**，ROM `2c2b48d9…`）当基线，wave 14 的收据
（`build/s49-package-z4-final3`，`ok:true`，残差 **109,569 px**，ROM `ec5b5273…`）当候选。

```
python tools/s49_fidelity_report/ratchet_check.py \
    build/s49-package-y4-final/work/s49-report/report.json \
    build/s49-package-z4-final3/work/s49-report/report.json
→ RATCHET FAIL，exit 1
   战场区残差总和 100210 -> 109569   ❌
   战场区残差中位   1323 -> 1372     ❌
   战场区全 0 帧数    5 -> 4         ❌
   整屏残差总和   197875 -> 207478   ❌
```

**端到端（真跑流水线）**：被接受的基线 = wave 14（109,569 px），
本次实测 **109,629 px**（ROM `1d7d8c9c…`）⇒

```
python tools/s49_package/run_pipeline.py --only 5 --judgment-repeat 1 \
    --out build/s49-package-w2-final1
--- step 5 judgment: FAIL (10.9s)
    ! the judgment bench failed: the ratchet broke on 战场区残差总和: 109569 -> 109629;
      战场区残差中位: 1372 -> 1432; 整屏残差总和: 207478 -> 207538
pipeline: FAIL     first failing step: 5     exit=1
```

⇒ **这正是 Z4 漏掉的那一类回归**（跨 ROM 的残差变大）现在**必红**。

⚠️ Z4 留的两个坏样例 `build/s49-package-z4-final` / `-final2` **已被并发的 W4 流删掉**
（本会话 18:11/18:19 还在，18:45 已不在）⇒ 改用上面**更硬的真回归**验；
「拒绝不绿的包」另用盘上还在的 `build/s49-package-selftest`（`ok:false`，`failed_step:11`）验。

### 3.2 ⭐ 判据 B：**ROM 变了 ⇒ 报「不可比」，不许静默 PASS**

基线 = wave-4 参考报告（**168,357 px**，ROM `2de28f16…`），本次 = **109,629 px**
（ROM `1d7d8c9c…`）⇒ 残差**没变大**但 ROM 不同：

```
python tools/s49_package/run_pipeline.py --only 5 --judgment-repeat 1 \
    --out build/s49-package-w2-final2 --accepted-baseline build/w2-dev/accepted-w4
--- step 5 judgment: PASS (11.2s)
    . the ratchet verdict is INCOMPARABLE: the baseline ROM differs from this run's ROM
      => the residual numbers are not the same measurement => this is NOT a pass
    . the judgment bench reported INCOMPARABLE (exit code 2)
pipeline: PASS  (⚠ 棘轮**不可比** —— 这不是棘轮通过)
⚠ RATCHET INCOMPARABLE: the baseline ROM (2de28f16…) differs from this run's ROM
   (1d7d8c9c…) => the residual numbers are NOT comparable => this is not a pass
exit=0
```

⇒ 判定台本体退出码 **2**（与「通过 0」「失败 1」可区分）；
收据顶层 `ratchet.status = "incomparable"`、`comparable = false`、两侧 ROM sha 齐全；
控制台有 ⚠ 横幅；`receipt.md` 有「不可比」一节。**不是静默 PASS。**
（判定台本体：`ratchet_check.py` 对 wave 14 基线 / wave 13 候选 ⇒ `RATCHET INCOMPARABLE`，exit 2。）

### 3.3 基线仓库的三条判据

| 问 | 判定方法 | 结果 |
|---|---|---|
| Q1 能不能找到**最近一次全绿**的收据 | `find_last_accepted_package(build)` | ✅ `build/s49-package-z4-final3`（109,569 px，ROM `ec5b5273…`）—— **不是** wave 4 |
| Q2 会不会接受**不绿**的包 | `promote_package(build/s49-package-selftest)` | ✅ **拒绝**：「ok=False, failed_step=11 ⇒ 不得成为棘轮基线」 |
| Q3 CLI 会不会接受不绿的包 | `run_pipeline.py --accept-baseline --out build/s49-package-selftest` | ✅ **exit 1**，拒绝 |

### 3.4 步骤 1 的前置等待（3 条判据，无构建）

| 问 | 判定方法 | 结果 |
|---|---|---|
| Q1 ROM 一直在变时会不会等 | 造一个每 0.5 s 被改写的 ROM，`stable_s=3, max_wait_s=5` | ✅ **等了 5.2 s 后才放弃**（`gave_up=True`） |
| Q2 盘上没有 ROM 时会不会白等 | 不存在的 ROM，`stable_s=150` | ✅ **0.0 s** 返回（「nothing to settle」） |
| Q3 能不能看见在跑的探针 | 用 `ping.exe` 改名成 `mgba-probe.exe` 当替身（**不碰共享探针**） | ✅ 看见了 `"mgba-probe.exe","26108",…`；结束后又看不见了 |

### 3.5 ⭐ 判据 C：**12 步判据除两处外一字未改**

判据是各步骤函数里的字面量，wave 14 的收据记下了**改动前**的每一条 ⇒ 可机检：

```
python build/w2-dev/verify_criteria.py
build            CHANGED   （第 1 步：新增前置等待 —— 任务书允许）
judgment         CHANGED   （第 5 步：棘轮基线来源 —— 任务书允许）
unit-tests / smoke / headless / overlay / idle-frames /
outline-wave / blackfade / audio / save-boundary / package   unchanged
changed outside the two allowed steps: none
```

⇒ **其余 10 步的判据逐字相同**。

### 3.6 其它

* 步骤 5 的自检仍会变红：`--selftest-break judgment` ⇒
  「the judgment bench's own ratchet rejected a regressed report (exit 1)」。
* 同一个 ROM 连读 2 次（18:53 / 18:54，ROM `ec5b5273…`）⇒ 残差**两次都是 109,569**，逐项相同 ⇒ 测量可复现。
* `content_sha256` **不含** `ratchet` 块 ⇒ 本改动**没有**改变报告的测量指纹口径。
* **清单不会把基线仓库打包进去**（默认布局下基线仓库就在包目录里）：
  `write_manifest(package, exclude_roots=(accepted_root,))` ⇒
  临时目录实测：列出的文件只有 `rom.gba`，`baseline-accepted/*` **未入清单**，
  清单与磁盘一致（`verify_manifest` 通过）。

---

## 4. 交父代理的接线清单

### 4.1 ⛔ `make_report.py` 要改的地方（**W4 独占，本流没动**）

请 W4 在 `make_report.py` 里处理这三处：

1. **口径澄清（任务 C）**：报告里**不许**把 Z3 的下界 **16,389 px** 说成
   「判定台的下界」。判定台的读数是 **arg-min 对齐残差（不带时刻约束）**，
   与下界**不是同一口径**，两个数**不许混用、不许互相换算**。
   （判定台侧的口径说明已写进 `tools/s49_fidelity_report/report.py` 的 markdown
   收据与流水线收据的 `notes`；**报告正文仍需 W4 改**。）
2. **棘轮基线来源**：报告的「棘轮」一节现在应写
   **「与上一波被接受的收据对照」**，并给出被接受基线的
   来源包 / 接受时间 / 残差总和 / 两侧 ROM sha256
   （收据顶层 `accepted_baseline` + `ratchet` 两个字段就是这些数字）。
3. **三态判决**：报告要区分 `pass` / `fail` / **`incomparable`**；
   `incomparable` 必须写成「**基线 ROM 不同 ⇒ 残差不可比 ⇒ 不是通过**」，
   不许写成「棘轮通过」。

### 4.2 出包流程的新规矩（W4 要知道）

* 棘轮基线在 **`build/s49-package/baseline-accepted/`**（不在包目录里 ⇒ 换包目录不会丢）。
* 全绿的跑法**自动**把本次测量提升为新的被接受基线；
  不绿的跑法**拒绝提升**（收据里有 `accepted_baseline_promoted`）。
* **ROM 变了**时：残差变大 ⇒ **红**；残差没变大 ⇒ **「不可比」**（绿但有 ⚠ 横幅，
  `receipt.json` 顶层 `ratchet.status = "incomparable"`）。
  ⇒ 出包前请确认这一项：**要么残差没变大（可接受），
  要么人工接受新基线**：
  `python tools/s49_package/run_pipeline.py --accept-baseline --out <包目录>`
  （该命令**拒绝**不绿的包）。
* **步骤 1 现在会先等 150 s**（ROM 不变 + 没有探针在跑）⇒ 全量跑会多花约 2.5 分钟，
  这是 Z4「跑三次才绿」的根治。

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **W2-1** | 棘轮基线丢了是因为它住在**包目录**里 | 读 `step_judgment`：基线 = `ctx.baseline/"baseline-report.json"`，而 `ctx.baseline = ctx.out/"baseline"` | **是** ⇒ 换包目录 ⇒ 基线从头播种（wave 4 的 168,357 px） | **已确认** |
| **W2-2** | wave 14 的 +9,359 px 真的会被新基线抓住吗 | 把 wave 13 的收据（100,210 px）当基线、wave 14 的收据（109,569 px）当候选跑 `ratchet_check.py` | **会**：4 项指标变差 ⇒ `RATCHET FAIL` exit 1 | **已确认** |
| **W2-3** | 流水线（不只是判定台）会因此变红吗 | `run_pipeline.py --only 5`，基线 = wave 14（109,569），本次 109,629 | **会**：步骤 5 FAIL、`first failing step: 5`、exit 1 | **已确认** |
| **W2-4** | ROM 变了会不会静默 PASS | 基线 = wave-4 参考（168,357，ROM `2de28f16…`），本次 109,629（ROM `1d7d8c9c…`） | **不会**：判定台 exit **2**、判决 `incomparable`、控制台 ⚠ 横幅、收据顶层 `comparable=false` | **已确认** |
| **W2-5** | 「残差变大」跨 ROM 时还算不算失败 | 读 `ratchet.py`：ROM 变化**不**关掉指标比较 | **算** ⇒ `fail` ⇒ 红（这正是 Z4 漏掉的那一类） | **已确认** |
| **W2-6** | 不绿的包会不会被提升成基线 | `promote_package(build/s49-package-selftest)`（ok=false, failed_step=11） | **不会** ⇒ 拒绝并说明原因 | **已确认** |
| **W2-7** | 基线仓库能不能自己找到「上一波被接受的收据」 | `find_last_accepted_package(build)` | **能** ⇒ `s49-package-z4-final3`（最近的全绿包，109,569 px） | **已确认** |
| **W2-8** | 步骤 1 的等待会不会被一个不停变的 ROM 骗过 | 造一个每 0.5 s 被改写的 ROM，`stable_s=3/max_wait_s=5` | **不会** ⇒ 改了签名就重新计时，5.2 s 后放弃并记录 `gave_up=true` | **已确认** |
| **W2-9** | 盘上没有 ROM 时会不会白等 150 s | 不存在的 ROM | **不会** ⇒ 0.0 s 返回 | **已确认** |
| **W2-10** | 等待能不能看见别的流正在跑的探针 | 用改名成 `mgba-probe.exe` 的替身进程（不碰共享探针） | **能** ⇒ 看见了 `"mgba-probe.exe","26108",…` | **已确认** |
| **W2-11** | 改基线来源会不会动到别的步骤的判据 | 把源码里的判据字面量与 wave 14 收据里记录的判据逐条比对 | **不会** ⇒ 只有 `build` 与 `judgment` 变了，其余 10 步逐字相同 | **已确认** |
| **W2-12** | 判定台的读数在同一 ROM 上可复现吗 | 18:53 与 18:54 两次跑（ROM `ec5b5273…`） | **是** ⇒ 两次都是 109,569 px | **已确认** |
| **W2-13** | 本机重建同一份源码会不会给出不同的残差 | ROM `d8b84d67…` 与 `1d7d8c9c…`（sha 不同，W1/W3 在飞）两次测量 | **残差相同**（都是 109,629 px）⇒ 差的是**字节**不是**画面**（印证 Z4 的「非字节可复现」） | **已确认** |
| **W2-14** | Z4 留的两个坏样例还在吗 | 18:45 列 `build/` | **不在了** ⇒ 被并发的 W4 流删掉（`s49-package-z4-final` / `-final2`）⇒ 改用真回归 + `s49-package-selftest` 验 | **已证伪（样例已被删）** |
| **W2-15** | 本流的四个临时包目录能删掉吗 | `rm -- build/s49-package-w2-*` | **不能** ⇒ 回收站启动器拒绝对 junction 目标动手（打真路径又被判「在工作区外」）⇒ **留在盘上**（都是红的，不影响基线认领） | **已证伪（删不掉）** |

---

## 6. 改动清单（完整绝对路径）

| 文件 | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_package\run_pipeline.py` | **改** | 棘轮基线改「上一波被接受的收据」；步骤 1 前置等待；三态判决；收据顶层 `ratchet` / `accepted_baseline`；`--accept-baseline` 等 4 个新参数；清单排除基线仓库 |
| `D:\Github\gba-naruto\tools\s49_fidelity_report\accepted.py` | **新增** | 被接受基线仓库（读 / 提升 / 找最近一次全绿 / 拒绝不绿的包） |
| `D:\Github\gba-naruto\tools\s49_fidelity_report\ratchet.py` | **改** | 三态判决（`pass`/`fail`/`incomparable`）+ `comparable` + `note`；指标比较**不**因 ROM 变化而关闭 |
| `D:\Github\gba-naruto\tools\s49_fidelity_report.py` | **改** | 退出码 0/1/2；判决打印；文档段 |
| `D:\Github\gba-naruto\tools\s49_fidelity_report\ratchet_check.py` | **改** | 打印并返回三态（2 = 不可比） |
| `D:\Github\gba-naruto\tools\s49_fidelity_report\report.py` | **改** | markdown 收据：棘轮三态 + ROM 变化提示 + 「口径说明」段 |
| `D:\Github\gba-naruto\notes\s49-fidelity\W2-ratchet-baseline.md` | **新增** | 本文件 |

**没有**改：`tools/s49_package/make_report.py`（W4 独占）、
重制线任何文件、逆向线任何文件、其它流的任何仪器。

---

## 7. 复现命令

```powershell
cd D:\Github\gba-naruto

# 0) 看一眼当前的被接受基线
python tools\s49_package\run_pipeline.py --accept-baseline --out build\s49-package-z4-final3

# 1) 证明「残差变大 ⇒ 变红」（用 wave 13 的收据当基线）
python tools\s49_fidelity_report\ratchet_check.py `
    build\s49-package-y4-final\work\s49-report\report.json `
    build\s49-package-z4-final3\work\s49-report\report.json      # -> RATCHET FAIL, exit 1

# 2) 端到端：流水线步骤 5（会真跑一次判定台，约 11 s）
python tools\s49_package\run_pipeline.py --only 5 --judgment-repeat 1 `
    --out build\s49-package-w2-final1                              # -> 步骤 5 FAIL, exit 1

# 3) 端到端：「不可比」（基线换成 wave-4 的参考报告）
python tools\s49_package\run_pipeline.py --only 5 --judgment-repeat 1 `
    --out build\s49-package-w2-final2 --accepted-baseline build\w2-dev\accepted-w4
                                                                       # -> INCOMPARABLE, exit 2, 绿但有横幅

# 4) 拒绝不绿的包
python tools\s49_package\run_pipeline.py --accept-baseline --out build\s49-package-selftest   # -> exit 1

# 5) 判据只改了两步
python build\w2-dev\verify_criteria.py
```

---

## 8. 卡在哪 / 遗留风险

1. **本会话没能跑一次完整 12 步**（步骤 1 的 WSL 构建会与并发的 W1/W3 抢同一个
   `.gba`；且重制线正在被改，ROM 每几分钟就变一次）⇒ **步骤 1 的前置等待只做了
   函数级验证**（§3.4），**没有**在真实构建上端到端跑过。
2. **临时包目录删不掉**：`build/s49-package-w2-test`、`-test2`、`-selftest`、
   `-default`、`-final1`、`-final2` 留在盘上（回收站启动器拒绝对 junction 目标动手，
   打真路径又被判「工作区外」）。它们**都是红的或已被认领过**，不影响基线认领；
   父代理可用真路径清：
   `rm -- "D:\Shell\Github\gba-naruto\build\s49-package-w2-final1" ...`
3. **`build/s49-package-w2-test2` 是绿的**（`ok:true`，109,569 px，ROM `ec5b5273…` ——
   与 wave 14 **同一个 ROM 上的同一次读数**）⇒ 万一父代理删掉
   `build/s49-package/baseline-accepted/`，认领会退回到它，**数字完全一样**，
   只是 `source_package` 指向了一个临时包。请顺手删掉那 6 个临时包目录。
4. **`tools/s49_pairing/run_all.py` 会把判定台的退出码 2 当失败**（`run_all.py`
   对任何非 0 退出码都 `SystemExit`）。该流程两次判定台跑的是同一个 ROM
   ⇒ 实际不会触发「不可比」；但这是**行为变化**，已在此登记。
5. 报告正文（`make_report.py`）的口径澄清**未做** —— W4 独占，见 §4.1。

---

## 9. 确认

* **新文件全部 LF、无 BOM**（实测 `CRLF=0`、无 BOM：`run_pipeline.py`、
  `s49_fidelity_report.py`、`accepted.py`、`ratchet.py`、`ratchet_check.py`、
  `report.py`、本笔记）。
* **未提交 git**（本流所有文件仍是 `??` 未跟踪状态）。
* **未改 `make_report.py`**（它 18:59 的 mtime 来自并发的 W4 流，不是本流）。
* **未改重制线任何文件**（只读用了它的 `git status` 与 ROM 的 sha；
  80 个改动文件全是 W1/W3 的）。
* **未改逆向线、未改其它流的仪器**。
* **没有伪造任何帧**：所有数字都来自收据 / 盘上的报告。
* **12 步判据只有 2 条变了**（第 1 步的前置等待、第 5 步的基线来源），
  其余 10 步逐字未动。
