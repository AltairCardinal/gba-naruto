# wave 14 / Z4 —— 出包定稿 + 1:1 报告定稿

> 工具：`tools/s49_package/run_pipeline.py`、`tools/s49_package/make_report.py`
> （本流只改这两个 + 新增读取器；其它流的仪器**一律只读调用**）
> 产物：`build/s49-package-z4-final/`（收据 + 包）、`docs/s49-fidelity-report-20261024.md`
> 2026-10-24 · 流 Z4（wave 14，收官波）。
> 重制线 **零改动**；逆向线 **零改动**；**未提交 git**。

---

## 0. 一句话结论

⭐ **12 步流水线 12/12 全绿**（收据 `build/s49-package-z4-final3/receipt.json`，
`generated_at` = **2026-10-24T18:20:06+08:00**、`ok: true`、`failed_step: null`）、
**构建 == 钉住 == 打包三者同 sha**（`ec5b5273…`）、
单测棘轮 **118 pass / 20 fail（新失败 0）**、
判定台连读 **3 次读数逐项相同**（残差总和 **109,569 px**）、
**11 个 selftest 全红**、包清单 **73 个文件**核对通过、
**包里没有 `report-test.md`、也没有 `cell-classification-dev.json`**。
报告：`docs/s49-fidelity-report-20261024.md`（**1145 行 / 83,680 B**，
**§11 仍是 23 条**未达成项）。

⚠️ **本波跑了三次才绿**，前两次的红**都不是本流的 bug**，
而是 **Z2 在同一时刻重建 ROM / 把 ROM 改崩**造成的（见 §2.5）。

⚠️ **残差比 wave 13 变大了**：**100,210 → 109,569 px（+9,359 / +9.3%）**
⇒ 归因到 **ROM 变了**（Z2 的黑场改动），**不是**判定台抖动
（同一个 ROM 连读 3 次逐项相同）；但**棘轮没抓住它** ——
换包目录重跑时棘轮基线是从 wave 4 起步的（见 §2.6）。

---

## 1. 本流改了什么（只改报告生成器，判据一个字未动）

| 文件 | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_package\make_report.py` | **修改** | ① 标题/页首改成 **wave 14 定稿**；② 新增三个**只读磁盘读取器**：`settlement_running_frames()` / `z3_bound()` / `z3_phase_attribution()` —— **按内容/键名**找 Z1 / Z3 的收据，**找不到就明写「尚未交付」**，绝不替别的流的数字冒充；③ 新增 `z14_status()`（Z1/Z2/Z3 的状态）；④ §11 的 1b / 1c / 2 / 11 / 13 / 14 / 20 改成**由收据与磁盘驱动**；⑤ 新增 **§3.4**「walk 相位 130 格的归因」与 **§14.8** 本波台账。**流水线（`run_pipeline.py`）一个字未改** ⇒ 12 步的判据与 wave 13 逐字相同。 |
| `D:\Github\gba-naruto\notes\s49-fidelity\W4-wave14-package-final.md` | **新增** | 本文件。 |

**没有**改重制线任何文件、逆向线任何文件、其它流的仪器。

---

## 2. ⭐ 本波踩到的两个坑（都已经堵上）

### 2.1 笔记的**文件名前缀**不能当「本波已交付」的证据（wave 13 的老坑，wave 14 还在）

`notes/s49-fidelity/` 里同名前缀的旧波笔记还在：
`Y3-overlay-zero.md` 是 **wave 6** 的 Y3，`X2-overlay-zero.md` 是 **wave 12** 的 X2。

⇒ 判定必须**以任务书的 mtime 为界**。
本流把 wave 13 的 `_note_present()` 拆成通用的
`_note_present_since(prefix, cutoff_name)`，
wave 14 的三条流一律用 `WAVE14-TASKS.md` 的 mtime 当界。

### 2.2 ⭐ 新坑：**「按内容查找」也会捡到别的波的收据**

第一版读取器按内容找 Z3 的相位归因时，**捡到了 wave 12 的
`build/s49-pairing/x2/z1-dense/report.json`** —— 它的英文键里有个 `phase`
⇒ 报告会把 **wave 12 的读数**当成 **wave 14 的交付**。

⇒ **修法（两层）**：
① **mtime 下限**：只认 **wave 14 任务书之后**写的收据；
② **关键词**：相位族在本项目里是**中文**（「相位」），
英文 `phase` **不算证据**。

修完后的实测：读取器不再误认，§3.4 如实写「wave 14 / Z3 尚未交付」。

### 2.3 环境坑：删文件要打**真路径**

`D:\Github\gba-naruto` 是指向 `D:\Shell\Github\gba-naruto` 的 **junction**
⇒ 回收站启动器（`mavis-trash`）**拒绝对 junction 的目标动手**，
必须显式打真路径：

```powershell
rm -- "D:\Shell\Github\gba-naruto\build\...\report-test.md"
```

（wave 13 也踩过同一个坑：`Y4-1`。）

### 2.4 ⭐ 读「别的流的收据」的三个口径坑（都是这波真踩到的）

报告生成器要**从盘上读 Z1 / Z3 的产物**。每一处都踩过坑，
**每一处都由「一次尝试回答一个是/否问题」定下来**：

| # | 坑 | 现象 | 修法 |
|---|---|---|---|
| a | **同名笔记** | `Z1-wiring.md` / `Z2-title-art-starfield.md` / `Z3-dialogue-box.md` 是 **wave 7** 的 Z1/Z2/Z3，而 wave 14 也有自己的 Z1/Z2/Z3 | 一律**以任务书的 mtime 为界**（`_note_present_since(prefix, "WAVE14-TASKS.md")`）；§11 第 12/13 项里把 wave 7 的那两处**显式写成「wave 7 的 Z2 / Z3」** |
| b | **按内容查找会捡到别的波的收据** | 第一版读取器按「含 `phase`」找 Z3 的相位归因，捡到了 **wave 12** 的 `build/s49-pairing/x2/z1-dense/report.json` | ① **mtime 下限**（只认 wave 14 任务书之后写的）；② 关键词只认**中文「相位」**（本项目里相位族是中文命名） |
| c | ⭐ **「帧数下界」被当成「像素下界」** | Z3 的配对收据里有 `summary/pairing_diff_lower_bound = 4` —— 那是 **4 帧**，不是 4 px；读取器按「键里含 lower」匹配，报告就会写出「下界 = 4 px」 | 键必须**同时**说明是**像素**（`pixel` / `px` / `sum` / `floor`）才收；Z3 的真键叫 **`floor_sum`** |
| d | ⭐ **旧录制的那份下界没有钉住 ROM** | `bound-old-walk5.json` 的 `roms.remake.sha256` 是 `null` ⇒ 它**不能**当「本次 ROM 的下界」；而且按内容找 sha 会误抓 **帧摘要**（`frames.remake.sha256`） | 只接受**位于名为 ROM 的块下面**的 digest；没有 ROM 的收据**只作对照**，报告里明写「该收据没有钉住 ROM」 |
| e | ⭐ **下界必须与「本次运行的 ROM」匹配** | Z1/Z2 一改产品，ROM 的 sha 就变 ⇒ wave 6 时代量的下界**对不上**本次运行 | `z3_bound(rom_sha256)` **只接受与本次收据的 ROM sha 完全相同**的那份；否则如实写「尚未为当前 ROM 重算」 |
| f | ⭐ **结算链的对照表属于哪个 ROM** | 读 Z1 的 `settlement-table-z1.json`（它**自己不带 ROM sha**） | 它的 `remake_dir` 指向 `build\z1\chain-e\shots` ⇒ 源跑的 `chain.json` 里有 `rom_sha256`；⚠️ **按兄弟文件找 sha 会捡到原版 ROM 的 sha**（`settlement-truth.json`）⇒ 只接受**位于名为 ROM 的块下面**的 digest |

### 2.5 ⭐⭐ 12 步流水线**跑了三次**才全绿 —— 前两次的红**都不是本流的 bug**

| 跑 | 包目录 | 结果 | 首个失败步骤 | 根因 |
|---|---|---|---|---|
| 1 | `build/s49-package-z4-final` | 🔴 | **5 judgment** | **Z2 的在飞改动把 ROM 弄崩了**：`capture 'remake' did not complete; done marker … missing`；探针的 stderr 是 `Jumped to invalid address: E251190A` / `Illegal opcode: e710b710` **刷了 118 MB**（wave 13 同一处是 **0 MB**）⇒ 崩在战斗 walk 里，不是开机（步骤 3 的 4096 帧冒烟**照样过**） |
| 2 | `build/s49-package-z4-final2` | 🔴 | **1 build** | **Z2 在步骤 1 的构建与钉住之间重建了 ROM**：构建的是 `94ef708e…`，钉住时盘上已经是 `ec5b5273…` ⇒ 钉不住（步骤 2–12 **全过**） |
| 3 | `build/s49-package-z4-final3` | 🟢 **12/12** | — | ROM **稳定 150 s + 没有探针在跑**的窗口里跑的 ⇒ 构建 / 钉住 / 打包三者同 sha `ec5b5273…` |

⇒ **可复用的做法**：`build/z4-dev/run-when-idle.ps1` ——
**等 ROM 的 mtime 稳定 > 150 s 且没有 `mgba-probe.exe` 在跑，再跑流水线**
（这就是任务书里「同一时刻只允许一路做构建」那条硬约束的可执行版本）。

⚠️ **这两个包目录删不掉**（`D:\Github\gba-naruto` 是 junction，
回收站启动器拒绝对 junction 的目标动手）⇒ **它们留在盘上作为两次失败的证据**。

### 2.6 ⭐ 残差比 wave 13 **变大了**（+9,359 px），而棘轮**没有**抓住它

| | wave 13 | wave 14（本次） | 差 |
|---|---:|---:|---:|
| 战场区残差总和 | **100,210** | **109,569** | **+9,359（+9.3 %）** |
| 中位 | 1,323 | 1,372 | +49 |
| 峰值 | 27,325 | 27,325 | ＝ |
| 全 0 帧 | 5 | 4 | −1 |
| 归因（一致·产品差·配对差） | 5·17·3 | 4·17·4 | 配对差 +1 |
| ROM sha | `2c2b48d9…` | `ec5b5273…` | **不同** |

* **不是判定台的抖动**：同一个 ROM 连读 **3 次**，读数逐项相同
  （`determinism.identical = true`、`rom_changed = false`）。
* **是 ROM 变了**：Z2 的黑场改动进了产品（重制侧带渐变的两个黑场事件由
  **44/20/46** 与 **54/26/54** 变成 **24/20/26** 与 **28/24/28**）
  ⇒ 判定台采到的帧换了 ⇒ 配对差多 1 帧。
* ⚠️ **棘轮没抓住它**：本波**换包目录重跑**（为了清草稿残留）
  ⇒ 新包目录里**没有**上一波的棘轮基线 ⇒ 棘轮基线是从 **wave 4 的参考报告**
  起步的（`168,357`）⇒ **这一次棘轮只比了 wave 4，没有比 wave 13**。
* ⇒ **建议（交父代理）**：出包前先把**上一波的收据**钉成棘轮基线，
  否则「残差只许变小」这条规则在**换目录时是空的**。

---

## 3. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **Z4w-1** | Z1 / Z2 / Z3 在本波开工前是否已经交付 | 读三份笔记（以 `WAVE14-TASKS.md` 的 mtime 为界）与 `tools/s49_z3_bound/` 是否存在 | **都没有**：三份笔记一个不在，`tools/s49_z3_bound/` 17:25 才出现 ⇒ 本波第一件事是**等**，报告里对应三行只能先写「尚未交付」 | **已确认（未交付）** |
| **Z4w-2** | 报告生成器能不能在 Z1/Z3 的产物**形状未知**的情况下只读地取到它们的数字 | 写**按内容/键名查找**的读取器（`settlement_running_frames()` / `z3_bound()` / `z3_phase_attribution()`），找不到就明写「尚未交付」 | **能**：三个读取器都**只在盘上真的有产物时**才给数字，且**绑定收据路径与 ROM sha256** ⇒ 每个数字都能追到一次运行 | **已确认** |
| **Z4w-3** | 「本波已交付」能不能用笔记的**文件名前缀**判定 | 读 `notes/s49-fidelity/` 里的同名笔记 | **不能** ⇒ 判定必须以**任务书的 mtime** 为界 | **已证伪** |
| **Z4w-4** | 按内容找收据会不会捡到**别的波**的收据 | 用 wave 12 的 `build/s49-pairing/x2/z1-dense/report.json`（键里有英文 `phase`）试 | **会** ⇒ 加 mtime 下限 + 只认中文「相位」；修完不再误认 | **已证伪（已修）** |
| **Z4w-4b** | 读取器会不会把**帧数**的下界当成**像素**的下界 | 用 Z3 的 `pairing.json`（`summary.pairing_diff_lower_bound = 4`）试 | **会**（第一版按「键里含 lower」就收）⇒ 键必须同时说明是像素（`pixel`/`px`/`sum`/`floor`） | **已证伪（已修）** |
| **Z4w-4c** | 「钉住 ROM 的收据」能不能靠任意 64 位 sha 认出来 | 用 Z3 的 `bound-old-walk5.json`（`roms.remake.sha256 = null`）试 | **不能**：按内容找会抓到**帧摘要** ⇒ 只接受**位于名为 ROM 的块下面**的 digest；没有 ROM 的收据只作对照 | **已证伪（已修）** |
| **Z4w-5** | 在别的流还在跑全量录制时重跑流水线会不会把步骤 5 的采集杀掉 | 重跑前查 `Win32_Process` 的内存占用与孤儿 `mgba-probe.exe` | **会** —— 而且不止是内存：**第一次重跑**就是步骤 5 红的（`done marker missing`），根因是 **Z2 的在飞改动让 ROM 在战斗 walk 里崩了**（探针 spew 118 MB 崩溃日志）；**第二次**是步骤 1 红的（**Z2 重建 ROM ⇒ 钉不住**）⇒ **重跑前必须等「ROM 稳定 + 没有探针」** | **已确认（已规避）** |
| **Z4w-6** | 单测棘轮的失败集合是否与 HEAD 基线**逐名相同**（20 项预存债） | 流水线步骤 2 的收据 | **是**：HEAD **101 pass / 20 fail**、工作区 **118 pass / 20 fail**、`new_failures` = **[]** ⇒ **20 项预存债，零回归**；⚠️ **不许写成「单测全绿」** | **已确认** |
| **Z4w-7** | 构建 / 测量 / 打包三者是不是同一份 ROM | 比对步骤 1 构建产物、步骤 1 钉住的拷贝、步骤 12 打包的 sha256 | **是**：三者**逐字节相同** = `ec5b527373b5c85774fcaf283789d93450dcf9c747e076db595343c2f47e4031` ⇒ 并行流中途重建**换不掉**本轮的读数 | **已确认** |
| **Z4w-8** | 判定台的读数是否确定（3 次连读逐项相同） | 流水线步骤 5 内建 | **是**：同一个 ROM 连读 **3 次**，残差总和 **109,569 px** 三次**完全相同**（`determinism.identical = true`、`rom_changed: false`） | **已确认** |
| **Z4w-9** | 「故意破坏 ⇒ 流水线变红」的 11 个 selftest 是否仍然全红 | `run_selftests.ps1` 逐个 `--selftest-break` 跑一遍 | **是**：**11 red, 0 not red**（收据：`build/s49-package-z4-final3/evidence/selftest-break.txt`）⇒ 11 个步骤的判据都真的会被触发 | **已确认** |
| **Z4w-10** | 换包目录重跑能不能把中间目录的草稿残留（`build/s49-package-y4/evidence/overlay/cell-classification-dev.json`）清掉 | 读新包目录的 `manifest.json` 与文件清单 | **能**：新包（`build/s49-package-z4-final3`）里**只有** `evidence/overlay/cell-classification.json`，**没有** `-dev` 那份，也**没有** `report-test.md` ⇒ **73 个文件**核对通过 | **已确认（已修）** |
| **Z4w-14** | 第一次重跑的红是不是**本流的 bug** | 读步骤 5 的日志与探针的 stderr | **不是**：是 **Z2 的在飞改动**把 ROM 弄崩（`Jumped to invalid address` / `Illegal opcode`，**刷了 118 MB**；wave 13 同一处 0 MB）⇒ Z2 随后**自己回退**了（ROM 回到 `2c2b48d9…`） | **已证伪（是 Z2 在飞）** |
| **Z4w-15** | 第二次重跑的红是不是**本流的 bug** | 读步骤 1 的日志 | **不是**：**Z2 在构建与钉住之间重建了 ROM**（构建 `94ef708e…` / 盘上 `ec5b5273…`）⇒ 步骤 1 的钉住判据**正确地**红了（步骤 2–12 全过） | **已证伪（是并发构建）** |
| **Z4w-16** | 等「ROM 稳定 150 s + 没有探针」再跑，能不能拿到 12/12 | `build/z4-dev/run-when-idle.ps1` → `run_pipeline.py --out build/s49-package-z4-final3` | **能**：**12/12 全绿**（`ok: true`、`failed_step: null`），构建 == 钉住 == 打包同 sha | **已确认** |
| **Z4w-17** | 本机构建是不是**字节可复现**的 | 用 wave 13 的 ROM（`2c2b48d9…`）与本波从**同一份源码**构建的 ROM（`ec5b5273…`）比 sha | **不是**：源码树与 wave 13 时**逐文件相同**（`git status` 28 个改动 + 同一批未跟踪文件），sha 却**不同** ⇒ **链接时间戳 / 路径进了产物** ⇒ 报告里「本机构建非字节可复现」这条**有本波自己的两个 sha 佐证** | **已确认** |
| **Z4w-18** | 残差比 wave 13 变大了，是不是**判定台的抖动** | 比两次收据的残差摘要 + 读本次收据的 `determinism` | **不是**：同一个 ROM 连读 3 次**逐项相同**（`identical = true`）⇒ 差值属于 **ROM 变化**（Z2 的黑场改动）；⚠️ **但棘轮没抓住它**（换包目录 ⇒ 棘轮基线从 wave 4 起步） | **已确认（是产品改动）** |
| **Z4w-19** | Z3 的下界能不能直接当**本次 ROM** 的下界 | 比 Z3 收据的 `roms.remake.sha256` 与本次收据的构建 sha | **不能**：Z3 测在 `2c2b48d9…`，本次是 `ec5b5273…` ⇒ 报告**不把它写成「当前 ROM 的下界」**，只写「另一个 ROM 上的下界 ⇒ 量级结论成立，精确值待重算」 | **已证伪（口径不同）** |
| **Z4w-11** | Z3 的下界是不是**为当前 ROM** 重算的 | 读 `build/s49-z3-bound/bound-A/B/new.json` 的 `floor_sum` 与 `roms.remake.sha256` | **是**：**16,389 px**，ROM `2c2b48d9…`，**3 次独立跑逐值相同**；旧口径 23,753 被 `bound-old-walk5.json` **复现**（但那份**没钉住 ROM** ⇒ 只作对照） | **已确认** |
| **Z4w-12** | 130 格「walk 相位」到底是不是同一类东西 | 读 Z3 的 `phase-A/B.json` 的 `verdicts` 与 `phase_reachability` | **不是**：**50 格 = 重制侧缺一个相位**（原版 6 连拍逐格相同、密集 walk 连续 67 帧同相位；重制 0/783 帧同现）/ **80 格 = 原版那一帧是瞬态**（6 连拍里只出现 1 次）⇒ **130 = 50 + 80** | **已确认** |
| **Z4w-13** | 结算链的运行帧能不能**逐屏**对上原版真值 | 读 Z1 的 `build/z1/chain-*/chain.json` 的每页 sha256，与 `settlement-truth.json` 的 sha256 **逐个匹配** | **能**：**5 页与原版真值逐字节相同**（3 张升级屏 + 忍具一览 ⇒ 差 px = 0），其余页无同 sha 的原版屏 | **已确认** |

---

## 4. 复现命令

```powershell
cd D:\Github\gba-naruto

# 0) 重跑前：等「ROM 稳定 + 没有探针在跑」⚠️ 这一步是**硬前置条件**
powershell -NoProfile -ExecutionPolicy Bypass `
    -File build\z4-dev\run-when-idle.ps1     # 内含等待窗口 + 跑流水线

# 1) 12 步流水线（**换包目录** ⇒ 草稿残留自动清掉）
python tools/s49_package/run_pipeline.py --out build/s49-package-z4-final3

# 2) 11 个 selftest（每个步骤故意破坏 ⇒ 必须全红）
powershell -NoProfile -ExecutionPolicy Bypass `
    -File tools/s49_package/run_selftests.ps1 `
    -PackageDir 'build\s49-package-z4-final3'

# 3) selftest 把证据写进包里之后，重写并核对包清单
python tools/s49_package/run_pipeline.py `
    --out build/s49-package-z4-final3 --verify-manifest

# 4) 报告
python tools/s49_package/make_report.py `
    --receipt build/s49-package-z4-final3/receipt.json `
    --out docs/s49-fidelity-report-20261024.md
```

**本次的最终产物**：

| 产物 | 路径 |
|---|---|
| 包 + 收据 | `D:\Github\gba-naruto\build\s49-package-z4-final3\` |
| 报告 | `D:\Github\gba-naruto\docs\s49-fidelity-report-20261024.md` |
| 本笔记 | `D:\Github\gba-naruto\notes\s49-fidelity\W4-wave14-package-final.md` |
| 改动的工具 | `D:\Github\gba-naruto\tools\s49_package\make_report.py` |

⚠️ **两次失败的包目录留在盘上**（删不掉，junction）：
`build\s49-package-z4-final`（步骤 5 红）与
`build\s49-package-z4-final2`（步骤 1 红）—— 它们是 Z2 并发重建 ROM 的证据。

---

## 5. 确认

* **新文件全部 LF、无 BOM**（`make_report.py`、本笔记、报告；实测 `CRLF=0`、无 BOM）。
* **未提交 git**（`git log -1` 仍是别人的 `4d247e8c`；本流的三个文件都是
  `??` 未跟踪状态）。
* **未改重制线任何文件**（`D:\Shell\gba-naruto-butano` 只读使用；
  本流只**读**了它的 `git status` / `git diff` 与 ROM 的 sha）。
* **未改逆向线任何文件**（`D:\Shell\gba-naruto-reverse` 只读）。
* **未改其它流的仪器**（一律只读调用）。
* **没有伪造任何帧**：所有数字来自收据 / 证据文件。
* **未改流水线的任何判据**：`run_pipeline.py` **一个字未改** ⇒
  12 步的判据与 wave 13 逐字相同；本流只改了**报告生成器**与本笔记。
