# U3 —— wave 17：出包 + 1:1 报告定稿（等 U1 / U2 落地后重跑 12 步）

> 工具：`tools/s49_package/make_report.py`（**本流独占**）
> 产物：`build/s49-package-u3-final/`（收据 + 包，**不进 git**）、
> `docs/s49-fidelity-report-20261024.md`
> （**wave 16 的那一版已留档**在 `build/u3-dev/report-wave16.md`，174,753 B）
> 2026-10-24 · 流 U3（wave 17）· 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 任务书：`notes/s49-fidelity/WAVE17-TASKS.md` §3
> 上游：`notes/s49-fidelity/V3-wave16-package.md`（wave 16 的出包波）
> ⛔ **未改**重制线任何文件；⛔ **未改** `run_pipeline.py` /
> `tools/s49_fidelity_report*`；⛔ **未改**其它流的仪器（一律**只读调用**）；
> ⛔ 逆向线全程只读；⛔ **未提交 git**。

---

## 0. 一句话结论

> ⛔ **12 步流水线 = 11 绿 / 第 2 步红**，而**这一红是真阳性**：
> **U2 的产品改动让一个本来通过的单元测试变红**
> （`test_battle_range_ui_phase_truth_table`：
> wave 16 **pass** → wave 17 **fail**；
> 失败断言是 `assert(got != kind::move)`，
> 而 U2 恰恰把「青（可达集）不再被 `move_phase` 锁住」**作为本轮的修复**）
> ⇒ **这一红的归属是 U2**（它独占 `battle_range_ui_style.h` 与测试文件），
> **本流不碰重制线** ⇒ **只能如实报红**。
> 其余 **11 步全绿**，ROM **构建 == 钉住 == 打包 == 实测四个 sha 逐字相同**
> = `16bf746fc254de37cef2fd3c0a29fc843c0fa7bfe064dfc41f30eaf7cea734da`；
> 判定台连读 **3 次 109,569 px** 逐项相同；
> **棘轮判决 = `incomparable`**（基线 ROM `3973adcd…` ≠ 本次 `16bf746f…`
> ⇒ **残差不是同一个测量 ⇒ 这不是通过**；流水线**没有**接受新基线，
> 因为「不是全程绿 ⇒ 不许成为基线」）；
> 可证像素下界为**本包这个 ROM** 重算 = **16,350 px**，
> 同刻可达上界 = **18,909 px** ⇒ **夹逼 [16,350, 18,909]（上下界同一个 ROM）**；
> 1:1 报告 **194,583 B / 1,516 行 / 29 行未达成项（编号 1–26 + 1b/1c/3b）**。
>
> ⛔ **「真实打完仗」仍未达成**：U1 已交付（`notes/s49-fidelity/U1-d4-fix.md`，
> 产品侧也落地了），**U4 在**本次这个 ROM**（`16bf746f…`）上跑了 7 场
> **真实战斗**（`poke_commands = 0`）⇒ **每一场都是
> `outcome = 0` / `battle_decided = False` / `蜂的 HP 下降 = False`**
> ⇒ **D4 仍然没有闭合** ⇒ 报告把「真实战斗链」与「poke 链」**分列**，
> **任何一栏都没有**被写成「真实胜利链」。

---

## 1. 本流改了什么

| 文件 | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_package\make_report.py` | **改** | ① 新增 wave 17 的读取器（`wave17_cutoff_mtime()` / `wave17_notes()` / `wave17_streams()` / `wave17_chains()` / `wave17_chain_verdict()` / `wave17_battles()` / `wave17_battle_verdict()` / `wave17_real_victory()` / `wave17_real_victory_chain()` / `wave17_settlement_align()` / `_remake_rom_of_align()` / `wave17_product_state()` / `wave17_bound()` / `w17_status()`）；② **§15.2.3 拆成「真实战斗链」与「poke 链」两栏**（新增 **§15.2.3.1** / **§15.2.3.2**），新增 **§15.2.4**（結算屏逐屏对照的最新一次测量）；③ **§0** 与页首新增**「一眼看出这一批数字的出处」**（四个 sha / 复用还是重采 / 基线 ROM / 棘轮判决）；④ **§11 第 25 项**（真实打完仗）改成**数据驱动**（战斗收据的三条判据）；⑤ **§11 新增第 26 项**（wave 17 四路流的落地状态，产品流按**独占文件的 mtime** 判交付）；⑥ **§11 第 1b / 第 3 项**补上 **U2 的结论与接线点**；⑦ **§14.11** wave 17 的台账；⑧ 修三个读取器缺陷 + 给 `_scan_json` 加缓存（报告生成 90 s → 23 s）。 |
| `D:\Github\gba-naruto\notes\s49-fidelity\U3-wave17-package.md` | **新增** | 本文件。 |
| `D:\Github\gba-naruto\docs\s49-fidelity-report-20261024.md` | **改** | 1:1 报告定稿（wave 16 的那一版留档在 `build/u3-dev/report-wave16.md`）。 |

**没有**改重制线任何文件、逆向线任何文件、其它流的仪器。
⛔ **`run_pipeline.py` 一个字未改**；⛔ **`tools/s49_fidelity_report/` 一个字未改**
（wave 16 的 V3 成果）；⛔ **12 步的判据一个字未改**（收据里的判据字面量可机检）。

---

## 2. ⭐ 本波的关键设计：「真实战斗链」与「poke 链」的**机器可判**分栏

### 2.1 判据

| 证据 | 判读 |
|---|---|
| `entry.method` 里含 `poke` | ⛔ **poke 链** |
| `outcome_byte_before_poke != outcome_byte_after_poke` | ⛔ **poke 链** |
| `entry.method` 明确**不是** poke，且链上 `outcome == 1` | ✅ **真实胜利链** |
| `entry.method` 明确**不是** poke，且 `outcome != 1` | ✅ **真实战斗链（败北）** |
| 两者都没有（进入方式未记录） | ⚠️ **进入方式未记录** ⇒ **不许**当成真实链 |

### 2.2 战斗收据（U4 的闭环驱动器）额外给三条判据

| 字段 | 含义 |
|---|---|
| `entry.method` / `entry.poke` / `acceptance.poke_commands` | 是不是**真打的**（U4 记了每一条发往探针的命令 ⇒ `poke_commands` 可自证） |
| `battle_decided` | 是不是**产品判的**（`False` ⇒ 这一局没打完） |
| `acceptance.bee_hp_dropped` | **蜂的 HP 有没有掉**（`False` ⇒ 玩家的攻击仍然打不中 ⇒ D4 还在） |
| `acceptance.escort_alive` | 护送（木叶丸）有没有活下来 |

⇒ **「真实打完仗」= 三条同时成立**。报告 §15.2.3.1 把这几张收据**逐条列出来**，
⛔ **任何一栏都不许写成对方的名字**。

---

## 3. 本波修掉的三个读取器缺陷（都在本流独占的 `make_report.py` 里）

| # | 缺陷 | 症状 | 修法 |
|---|---|---|---|
| **U3w-A** | 「逐屏对照表」被当成「结算链」 | `wave17_chains()` 的行判据里有 `row.get("phase")` ⇒ **逐屏对照表**（每行带 `phase` 字符串）被当成链记录塞进链清单 | 链记录**必须不是**对照表 ⇒ 加 `if _is_comparison(rows): continue` |
| **U3w-B** | 「逐屏对照表」的 ROM 过滤只做了一半 | `wave16_settlement_rows()` 的**第一遍**不过滤 ROM ⇒ U4 的新收据（测在另一个 ROM 上）会顶掉 wave 16 / V1 的对照表 | 第一遍也加 `prefer_sha` 过滤 ⇒ **与本次 ROM 不同就不引用** |
| **U3w-C** | 产品流「是否交付」只看笔记 | U2 **没有**写笔记（它的独占文件全在重制线）⇒ 报告会说「U2 尚未交付」，而**它的产品明明进了 ROM** | 新增 `wave17_product_state()`：**独占文件的 mtime > 任务书 mtime** ⇒ 产品侧已落地；两条证据**分开写**（笔记 / 产品） |

---

## 4. 12 步流水线

| 项 | 值 |
|---|---|
| 收据 | `build/s49-package-u3-final/receipt.json`（`generated_at` = **2026-10-24T23:11:04+08:00`，**`ok: false`**，`failed_step: **2**`） |
| 步骤 | **11 / 12 绿**（第 2 步红，见 §4.1） |
| **ROM（四个 sha）** | 构建 / 钉住 / 打包 / 实测 **逐字相同** = `16bf746fc254de37cef2fd3c0a29fc843c0fa7bfe064dfc41f30eaf7cea734da`（步骤 1 等了 **152 s** 的 ROM 稳定窗口；钉住的拷贝 `work/pinned-rom/measured.gba`） |
| 采集 | 步骤 5 的判定台在**同一个 ROM 上连读 3 次**，残差总和 **109,569 px** 逐项相同 |
| **棘轮判决** | **`incomparable`**（基线 ROM `3973adcd…` ≠ 本次 `16bf746f…` ⇒ **残差不是同一个测量 ⇒ 这不是通过**）；**基线未被接受**（`the accepted ratchet baseline was NOT updated: this run is not green all the way`） |
| 单测棘轮 | HEAD **101 pass / 20 fail** / 工作区 **117 pass / 21 fail** ⇒ **新红 1 项**：`test_battle_range_ui_phase_truth_table` |
| 黑场 | 步骤 9：原版 **1,881 帧**（ROM `1198ece7…`）；重制侧 **2,402 帧**（ROM `16bf746f…`）；事件数 **6 vs 2**（原版 24/18/24、24/24/24；重制侧 0/8/0、0/6/0、**24/18/28**、0/2/0、0/8/0、28/24/28）⇒ ⭐ **第三个事件的淡入 26 → 28**（wave 16 是 24/18/**26**）|
| 包清单 | **69 个文件**核对通过（`the manifest matches the package (69 files)`）；selftest 写完证据后重写清单 = **198 个文件**，再核对一次仍通过 |
| 11 个 selftest | **11 red, 0 not red**（证据 `build/s49-package-u3-final/evidence/selftest-break.txt`） |
| 1:1 报告 | `docs/s49-fidelity-report-20261024.md` —— **194,583 B / 1,516 行 / 29 行未达成项** |

### 4.1 ⛔ 第 2 步的红是**真阳性**：U2 的产品改动打破了一个本来通过的测试

| 证据 | 结果 |
|---|---|
| wave 16 的工作区收据 `build/s49-package-v3-final/baseline/unit-tests-workspace.tsv` | `test_battle_range_ui_phase_truth_table` = **pass** |
| wave 17 的工作区收据 `build/s49-package-u3-final/baseline/unit-tests-workspace.tsv` | 同名测试 = **fail** |
| 失败断言 | `Assertion 'got != kind::move' failed` —— 位于 `butano-sequel/game/tests/test_battle_range_ui_phase_truth_table.cpp:100`，注释写着「**Outside the move phase the cyan reach set is not painted**」 |
| U2 的产品改动 | `battle_range_ui_cell_kind()`：**青（可达集）不再被 `move_phase` 锁住** ⇒「青 + 橙」在规则层不再互斥 |
| ⇒ | **测试编码的是**改规则**之前**的语义 ⇒ U2 改了产品却**没有同步更新**这份既有的真值表测试 ⇒ 棘轮正确地变红 |
| 该测试的来历 | `git status` = **未跟踪**（不在 HEAD 里）、mtime **2026-10-24 16:11:54** ⇒ **wave 13 / G 流留下的**，**不是** U2 新写的文件 |
| U2 笔记 §4.1 的说法 | 「失败名单 20 项与基线**逐名相同**」⇒ **与本次实测不符**（实测 21 项）⇒ 它的棘轮跑在**产品改动落地前**或**另一份树状态**上 |

⇒ **归属 U2**（它独占 `battle_range_ui_style.h` 与 `game/tests/`）；
⛔ **重制线是本流的禁区** ⇒ 本流**只如实报红**，**不改那一行断言**。
⚠️ **修法（一行）**：把 `test_battle_range_ui_phase_truth_table.cpp:99-100`
那句「非移动相位不画青」的断言改成**新语义**（非移动相位**可以**画青），
并同步检查同一文件里其余依赖「青只在移动相位」的断言。

---

## 5. 可证像素下界 / 上界（**为本包这个 ROM 重算**）

| 项 | 值 |
|---|---|
| 下界（可证像素） | **16,350 px**（收据 `build/u3-dev/bound/bound-final.json`；`canonical_sum` = 91,249；重制侧 783 帧 / 392 张去重；**与 `pair.beat_floor` 交叉核对 `agrees=True`**） |
| 上界（同刻可达） | **18,909 px**（收据 `build/u3-dev/bound/pairing/pairing.json`；25 个原版帧 / 783 个重制帧；同刻命中 21 帧 = 84 %） |
| **夹逼** | **16,350 ≤ 最优残差 ≤ 18,909 px**（**上下界是同一个 ROM** `16bf746f…`） |
| 原版侧重录 | 553 帧，指纹 `ffa679a0…` —— **与 wave 16 的逐字节相同** ⇒ **录制是确定的** |
| 重制侧指纹 | `758d7fc6…`（wave 16 是 `e6c3bbde…`）⇒ **差来自 ROM** |

⚠️ **三个数不许混用**：判定台读数 **109,569 px**（arg-min、无时刻约束）
／ 可证像素下界 **16,350 px**（每一拍内全部帧对取最小）／
内容锚可达数 **18,909 px**（同一时刻的帧对）。

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **U3w-1** | U1 / U2 在本波开工前是否已经交付 | 读 `notes/s49-fidelity/` 里**在 `WAVE17-TASKS.md` 之后**写的笔记，**并**查重制线里 U1 / U2 独占文件的 mtime | 开工时（22:27）**两路都没有交付**；22:34 **U2 落地**（`battle_range_ui_style.h`）；22:43 **U4 交付**；**23:04 U1 落地**（父代理把接线点合进 `battle_runtime_scene.cpp`）；**23:08 ROM 重建** ⇒ 闸门 23:10 打开 | **已确认** |
| **U3w-2** | 「本波已交付」能不能用笔记的**文件名前缀**判定 | 读 `notes/s49-fidelity/` 里的同名笔记 | **不能** ⇒ 判定必须**以任务书的 mtime 为界**；**并且**产品流（U1 / U2）额外用「独占文件的 mtime + ROM 在其后被重建」判定 —— **笔记不是产品的证据，ROM 才是** | **已证伪** |
| **U3w-3** | 报告生成器能不能在 U1 / U2 / U4 的产物**形状未知**的情况下只读地取到它们的数字 | 按**内容/键名**查找（`wave17_chains()` / `wave17_battles()` / `wave17_settlement_align()`） | **能**（三个读取器都只在盘上真的有产物时才给出数字，且**绑定收据的路径与 ROM sha256**） | **已确认** |
| **U3w-4** | 「真实战斗链」与「poke 链」能不能被**机器**分开 | 读链收据的 `entry.method` 与 outcome 字节 | **能**（判据见 §2.1）⇒ 报告 §15.2.3 **分列** | **已确认** |
| **U3w-5** | 第 2 步的红是**仪器假象**还是**真阳性** | 比 wave 16 与 wave 17 两份工作区单测收据里同名测试的结论 | **真阳性**：wave 16 **pass** → wave 17 **fail**；失败断言是 `assert(got != kind::move)`，与 U2 的产品改动**直接冲突** | **已确认（真阳性）** |
| **U3w-6** | 构建 / 钉住 / 打包 / 实测四个 sha 是不是同一份 ROM | 比步骤 1 / 步骤 12 / 判定台收据里的摘要 | **是**（`16bf746f…` 四个逐字相同，§2.0c） | **已确认** |
| **U3w-7** | 判定台的读数在同一个 ROM 上确定吗 | 步骤 5 连读 3 次 | **是**（109,569 px 三次逐项相同） | **已确认** |
| **U3w-8** | 可证像素下界能不能为**本包这个 ROM** 重算 | 只读调用 V4 的工具 `tools/s49_z3_bound/` | **能**（16,350 px，`agrees=True`；原版侧指纹与 wave 16 逐字节相同 ⇒ 录制确定） | **已确认** |
| **U3w-9** | 棘轮判决会是什么 | 步骤 5 | **`incomparable`**（基线 ROM 不同 ⇒ **残差不是同一个测量 ⇒ 这不是通过**）；**基线没有被接受**（不是全程绿） | **已确认** |
| **U3w-10** | 11 个 selftest 是不是仍然全部能把对应的步骤打红 | `build/u3-dev/run-selftests-percase.ps1` | **11 red, 0 not red** | **已确认** |
| **U3w-11** | 报告生成器能不能在**新旧两种收据形状**下都工作 | 拿 wave 16 的收据跑一遍 | **能**（旧收据没有 wave 17 的产物 ⇒ 对应处显示「尚未交付」；新收据有 ⇒ 显示真实数字） | **已确认** |

---

## 7. 复现命令

```powershell
cd D:\Github\gba-naruto

# 0) 跑流水线前：等「U1 / U2 的独占文件在任务书之后被改过 + ROM 在其后被重建
#    + ROM/源码安静 150 s + 没有探针/构建在跑 + 内存 > 4 GB」
powershell -NoProfile -ExecutionPolicy Bypass -File build\u3-dev\run-when-idle.ps1 -NoRun

# 1) 12 步流水线（**换包目录** ⇒ 草稿残留自动清掉）
python tools\s49_package\run_pipeline.py --out build\s49-package-u3-final

# 2) 跑完之后的一切：下界重算 + 上界 + 11 个 selftest + 包清单 + 报告 + 编码自检
powershell -NoProfile -ExecutionPolicy Bypass -File build\u3-dev\finish.ps1 `
    -PackageDir 'build\s49-package-u3-final' `
    -Report 'docs\s49-fidelity-report-20261024.md'
```

---

## 8. 卡在哪 / 遗留风险

1. ⛔ **第 2 步的 1 项新红是 U2 的**（`test_battle_range_ui_phase_truth_table`，
   §4.1）⇒ **12/12 全绿的验收差这一条**。
   **修法在 U2 的文件里**（把「非移动相位不画青」的断言改成新语义），
   ⛔ **重制线是本流的禁区** ⇒ 本流不碰。
   ⇒ **U2 修好并重建之后重跑一次 `run_pipeline.py`（约 10 min）+ 一次
   `finish.ps1`（约 20 min）即可 12/12**；**报告生成器是数据驱动的**，
   只重跑 `make_report.py`（约 25 s）就能把新数字写进报告。
2. ⛔ **「真实打完仗」仍未达成**：U1 已交付（`notes/s49-fidelity/U1-d4-fix.md`），
   **但 U4 在**本次这个 ROM**（`16bf746f…`）上跑了 7 场**真实战斗**
   （`poke_commands = 0`）⇒ **每一场都是 `outcome = 0`、
   `battle_decided = False`、蜂的 HP 下降 = False**
   ⇒ **D4 仍然没有闭合** ⇒ `outcome=1` 仍不可达
   ⇒ 报告里只有「真实战斗链（未判定）」与「poke 链」，**没有**「真实胜利链」。
   ⇒ **归属 U1**（重制线的 D4 必修）。
   ⚠️ **U1 与 U4 在本流跑完后仍在跑诊断**（`build/u1/diag-irq*`、
   `build/v1-u4/diag-confirm*`，23:43 前后）⇒ **D4 的收尾还在路上**；
   **本包的产品状态是 23:14:24 那次重建**（此后重制线**一个字节都没改**
   ⇒ 本包**就是**当前源码树的状态）。
3. ⚠️ **覆盖层的「walk 相位 130 格」一个没降**（U2 实测 **130 → 130**）：
   规则改完了（青不再被相位锁住），**但**绿集合 ⊇ 青集合、橙集合 ⊇ 青集合
   ⇒ 青在目标选择相位一格都轮不到 ⇒ 剩下三处接线点
   （`battle_scene_controller.h` / `battle_runtime_scene.cpp` / D4）
   **都不在 U2 的独占文件里**。
4. ⚠️ **結算屏的 2,582 px 不变**：**684 px = 真实战斗的战果**（只能由 U1 打完的
   真实战斗产生）；**1,898 px = 三个人物**（要一张 8bpp 图集 + 共用一套 8bpp OBJ
   调色板 ⇒ 要动 U1 独占的绘制代码）⇒ **两件都卡在 U1**。
5. ⚠️ **黑场剩下的 4 个硬切 + 生长段**（事件 1 / 2 / 4 / 5）在
   `battle_preparation_scene.cpp` / 对白渲染路径 / 开机标题路径 ⇒ **U1**。
6. ⚠️ **本机构建非字节可复现** ⇒ 随包带 ROM + 重录命令（报告 §12）；
   复现要**先建私有探针**（`KONOHA_PROBE_OUT` 指到私有目录，
   **不要覆盖共享的 `build/mgba-probe/mgba-probe.exe`**，会 LNK1104）。
   本流用的是私有探针 `build/mgba-probe-u3/`
   （共享探针 mtime 仍是 **2026-10-23 23:21:42**，**未动**）。
7. ⚠️ **不要在别的流还在跑录制时重跑流水线**：全量录制吃 7–8 GB 且持续泄漏
   ⇒ 步骤 5 的采集会被杀 ⇒ **同一时刻只允许一路做构建**。
8. ⚠️ **棘轮判决是「不可比」而不是「通过」** ⇒ 「残差只许变小」这条规则
   **本波没有被检验**（基线 ROM 与本次 ROM 不同）。
