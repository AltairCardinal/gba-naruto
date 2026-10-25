# wave 12 / X4 —— 出包 + 1:1 报告终审 + 越界复核

> 工具：`tools/s49_package/run_pipeline.py`、`tools/s49_package/make_report.py`、
> `tools/s49_package/verify_terrain_criterion.py`（**本流新增**）
> 产物：`build/s49-package-x4/`（收据 + 包）、
> `docs/s49-fidelity-report-20261024.md`
> 2026-10-24 · 流 X4（wave 12）。**所有数字都是本机实测。**
> 重制线 **零改动**；逆向线 **零改动**；其它流的仪器**一律只读调用**；
> **未提交 git**。

---

## 0. 一句话结论

**12 步流水线 12/12 全绿（收据 `2026-10-24T15:42:17+08:00`）、11 个 selftest 全红、
单测棘轮 117 pass / 20 fail（新失败 0）、判定台连读 3 次读数逐项相同
（残差总和 100,210 px 三次一样）、⭐ 「构建的 sha == 测量/打包的 sha」由构造保证；
上一任（W4）自报的越界（wave 10 / U4 给 `find_overlay_map` 加 terrain 判据）
已由本流**独立复核第二次**，结论仍是「保留、不回退」，
数字是 35 个 walk dump 上 **Q1 0 处不同 / Q1b 0 处不同 / 判据只改 4 个（`0x00800` → `-1`）、
其余 31 个一字未变**，且它让 `grid16-frame-v1` 的残差从 **185 降到 126**（剔掉的是假阳性）。**

⚠️ **但本次运行仍是「wave 12 并行流在飞状态」的读数，不是 wave 12 的终稿基线**：
X1 / X2 / X3 三条流**都没有交付笔记**（X1 只有在飞产物，X2 已改动重制线并让
`movegrid` 的族名不一致从 4 降到 2），详见 §3「未达成项收口」与 §6「卡在哪」。

---

## 1. 改动文件清单（本流新建 / 修改）

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_package\verify_terrain_criterion.py` | **新增** | ⭐ **越界复核的独立仪器**：把 wave 10 / U4 改前的候选扫描**在本流重新实现**一遍，在同一份 dump 上做「带 / 不带 terrain」的 A/B；再把共享工具 `compare_overlay_families.py` 的 `main()` 端到端跑两遍（**只在本进程里替换函数，不动共享文件**）。收据落 `evidence/overlay/terrain-review.json`。 |
| `D:\Github\gba-naruto\tools\s49_package\run_pipeline.py` | **修改** | ① **步骤 6 现在顺带跑越界复核**（同一份 35 个 dump ⇒ 复核数字与步骤 6 的数字同源、可追到同一次运行）；② ⭐ **ROM 钉住**（见 §2.5）：步骤 1 构建完立刻把 ROM **拷贝一份**钉在包内 `work/pinned-rom/measured.gba`，此后**所有测量步骤与随包发布的 ROM 都是这一份拷贝** ⇒ 并行流在本轮运行期间重建同一个 ROM 也换不掉本轮的读数；③ **`MANIFEST_EXCLUDED_PARTS` 加 `selftest-scratch`**（见 §4 的 X4-9：wave 11 的 U4 包因此把清单从 122 个文件膨胀到 714 个）。**判定语义一个字未改。** |
| `D:\Github\gba-naruto\tools\s49_package\make_report.py` | **修改** | ① 报告标题与页首改成 **wave 12**；② 新增 **§16 越界复核**（数字全部来自收据）；③ **§3.2** 改成指向 §16（不再与 wave 11 的旧结论并列）；④ 新增 **§14.6 wave 12 X4 的台账**；⑤ 新增 `x_status()` / `x1_status()` / `x1_inflight()`：**wave-12 三流的状态一律从收据或磁盘读**，没有交付就不写成已达成。 |
| `D:\Github\gba-naruto\docs\s49-fidelity-report-20261024.md` | **重写** | wave 12 终审稿（由收据生成）。 |
| `D:\Github\gba-naruto\notes\s49-fidelity\W4-wave12-package-review.md` | **新增** | 本文件。 |

**没有**改重制线任何文件、逆向线任何文件、其它流的仪器
（`s49_fidelity_report*` / `s49_overlay_align` / `s49_blackfade` /
`s49_save_boundary` / `s49_audio_l` / `s49_audio_probe` / `s49_idle_*.py` /
`s49_orig_map` / `s49_pairing` / `s49_starfield` / `s49_v2_anchor` /
`s49_v3_dialogue` / `s49_x3_boundary` / `s49_opening_title` /
`s49_battle_balance` / `s49_victory_capture` / `s49_u3_settlement`
一律**只读调用**）。

---

## 2. 跑了哪些验证（命令 + 关键数字）

### 2.1 12 步流水线（`python tools/s49_package/run_pipeline.py --out build/s49-package-x4`）

收据 `build/s49-package-x4/receipt.json`
（`generated_at` = **2026-10-24T15:42:17+08:00**，`ok: true`，
`failed_step: null`）⇒ **12/12 全绿**。
⭐ **本次 ROM 已钉住**：构建 / 测量 / 打包三处都是同一份拷贝
`sha256 = 3f1e9caa11805b5e53bc053f2840d0a5d8f94d33f53956554675c8c305ccdde3`。

| 步 | 名称 | 结果 | 关键数字 |
|---:|---|---|---|
| 1 | build | 🟢 | ROM sha256 `3f1e9caa11805b5e…`；**已钉住**到 `work/pinned-rom/measured.gba` |
| 2 | unit-tests | 🟢 | HEAD **101 pass / 20 fail**；工作区 **117 pass / 20 fail**；**新失败 0** |
| 3 | smoke | 🟢 | 4096 帧不崩 + 中文标题画面 |
| 4 | headless | 🟢 | 无窗口无声 |
| 5 | judgment | 🟢 | **连读 3 次，读数逐项相同**；残差总和 **100,210 px**；`rom_changed: false` |
| 6 | overlay | 🟢 | 逐格对拍走整条 walk 的 **35** 个 dump；**顺带跑越界复核** |
| 7 | idle-frames | 🟢 | 静态帧门禁 |
| 8 | outline-wave | 🟢 | 200/200 |
| 9 | blackfade | 🟢 | 原版 **1881 帧 / 2 个事件**；重制侧 **2402 帧 / 6 个事件**（ROM `3f1e9caa…`） |
| 10 | audio | 🟢 | 事件级对照 |
| 11 | save-boundary | 🟢 | `--repeat 2` |
| 12 | package | 🟢 | **73 个文件**；**打包的 sha == 构建的 sha** |

⭐ **X2 的在飞改动在本轮读数里看得见**：`movegrid-frame-v1` 的族名不一致
从 **4 → 2**（残差 **52 → 50**），其余三个时刻一字未变
⇒ **残差只许变小的棘轮没有报警**，与「X2 在归零覆盖层族名」一致。

### 2.2 11 个 selftest（`powershell -File tools/s49_package/run_selftests.ps1 -PackageDir build\s49-package-x4`）

**11 red, 0 not red**（收据：`build/s49-package-x4/evidence/selftest-break.txt`；
报告 §13.1 逐条列出了 11 行的退出码，全部非 0）
⇒ 11 个步骤的判据都**真的**会被触发。
（这一轮是在**改过流水线之后**重跑的 —— 流水线本轮加了「钉住 ROM」，
所以必须重验一遍判据没有被动过。）

### 2.3 判定台 3 次读数一致性（步骤 5 内建）

同一个 ROM 连读 3 次：

| 读数 | 战场区残差总和 | 中位 | 峰值 | 全 0 帧 | 归因 | 三桶 | 覆盖层残差 |
|---|---:|---:|---:|---:|---|---|---:|
| 1 | 100,210 | 1,323 | 27,325 | 5 | 5·17·3 | 0·0·3 | 857 |
| 2 | 100,210 | 1,323 | 27,325 | 5 | 5·17·3 | 0·0·3 | 857 |
| 3 | 100,210 | 1,323 | 27,325 | 5 | 5·17·3 | 0·0·3 | 857 |

⇒ **三次逐项完全相同**（`determinism.identical = true`、`rom_changed = false`）。

### 2.4 越界复核（`python tools/s49_package/verify_terrain_criterion.py`）

| 复核项 | 方法 | 数字 |
|---|---|---|
| **Q1** 「不带 terrain」的路径与改前**逐字节**相同吗 | 把改前的候选扫描（`max(candidates)[1]`）**独立重写**一遍，在 35 个 dump 上对照 | **35 个 dump / 0 处不同** |
| **Q1b** 判定台自己的覆盖层读数被影响了吗 | 直接调 `tools/s49_fidelity_report/overlay.py::remake_grid`，把它报的 `overlay_map` 与改前的实现对照 | **35 个 dump / 0 处不同** |
| **Q2** 判据改了哪几个 dump | 同一份 dump 带 / 不带 terrain 各跑一遍 | **改 4 个**（`step-00-base` / `step-01-Down` / `step-02-Down` / `step-03-A`：`0x00800` → `-1`）、**31 个一字未变** |
| **Q3** 端到端对共享工具数字的影响 | 共享工具的 `main()` 跑两遍（一遍换回改前的实现） | **4 个 dump** 选到不同窗口；`grid16-frame-v1` 残差 **185 → 126**（多画 **103 → 39**）；`field` / `movegrid` 数字**一字未变**；`banner` 只换取帧（数字全 0） |

35 个 dump 的分类（改前口径）：**无候选 24 / 假窗口 `0x00800`（1024 个非零 entry）4 /
真覆盖层 `0x09800`（768 个非零 entry）7 / 其它 0**。

⇒ **结论：保留，不回退。**
⚠️ **循环论证的风险必须写明**：terrain 来自**重制线自己的生成头**
`generated_battle_map_content.h` ⇒ 该判据只保证「覆盖层与**产品自己用的**地图一致」，
**不是**独立于产品的绝对真值；绝对真值仍是原版导出的
`s49-original-movegrid-tilemap-v1`。

### 2.5 ⭐ 本波抓到的真问题：**收据里的 ROM 与包里的 ROM 不是同一个**

**第一跑（收据 `generated_at` = 2026-10-24T15:21:30+08:00，`ok: true`）里：**

| 项 | sha256 | 含义 |
|---|---|---|
| 步骤 1 构建的 ROM | `b6c2a05fa50e2861…` | **步骤 3 / 5 / 9 / 10 / 11 测的都是它** |
| 步骤 12 打包时盘上的 ROM | `196417ca5ab4478e…` | **包里随包发布的是它** |

⇒ **本收据里的每一个测量数字都属于前者，而包里发布的是后者 —— 后者没有被测过。**
⇒ **这一份收据不能作为发布基线。**

**根因**：X1 在本轮运行**期间**重建了同一个 `butano-sequel.gba`
（重制线 `game/src/battle_runtime_scene.cpp` 的 mtime 从 13:37 变成 **15:27:18**，
ROM 随之在 15:21:45 与 15:26:32 / 15:28:10 之间被换掉）。
⇒ 这是**并行流的环境**造成的，**不是**任何一步的判据失灵。

**修法（在本流的流水线里，判据一个字没改）**：
步骤 1 构建完立刻把 ROM **拷贝一份**钉在
`<包>/work/pinned-rom/measured.gba`（拷贝后核对 sha256，对不上就重试 5 次），
此后 `ctx.rom` 指向这份拷贝 ⇒
**步骤 3 / 5 / 9 / 10 / 11 测它、步骤 12 打包它**
⇒ **「构建的 sha == 打包的 sha」由构造保证**，不再依赖并行流的手脚。

**判据的正确形状**：包里的 ROM 必须是**被测过的那一份**，
而不是「打包那一刻盘上恰好是谁」。

---

## 3. 报告终审：未达成项收口情况

| 未达成项 | wave 12 的状态 |
|---|---|
| ⭐ 原版 S49 结算屏真值 | **已闭合**（wave 8 的 W4）⇒ 写进正文 §15，**不是**未达成项 |
| 结算链运行帧对照（X1） | ⛔ **仍未达成**：X1 **没有交付笔记**；原版真值 9 张里，重制侧仍有 5 张没有对应运行帧。⚠️ X1 的**在飞**产物已能走到 `outcome=1`（见 §7），但**不写成已达成** |
| 残差归零的可达性 | ⛔ **归零在当前录制上不可达**：可证像素**下界 ≈ 23,700**（当前 ROM 23,753 / 上一版 23,697） |
| 存档逐字节一致 | ⛔ **按用户口径排除**（两侧 loader 互不兼容） |
| 音频逐采样一致 | ⛔ **排除**（80–120 h 量级） |
| 20 项单测在 HEAD 即为红 | ✅ **已确认是预存债，本次零回归**（新失败 0） |
| 判定台抖动 | ✅ **已查清并闭合**：不是仪器，是 wave 10 那两次跑**ROM 不同** |
| 覆盖层逐格族名（X2） | ⛔ **未归零**（X2 未交付）：field 168/24/24/**50**、movegrid 168/24/24/**2**（本轮比上一轮 4 降了 2 ⇒ X2 的在飞改动已经见效）、grid16 153/22/39/**65**、banner **0/0/0/0 exact ✔** |
| 黑场事件数/时长（X3） | ⛔ **未对齐**（X3 未交付）：原版 **2 个**事件（24/18/24、24/24/24）；重制侧 **6 个**（4 个是硬切，带渐变的只有 2 个） |
| 对话框斜切展开 | ⛔ **单列**：实测那**不是对话框动画，是入场转场**（BG 图块表全程逐字节不变 ⇒ 遮罩来自 OBJ）⇒ 逐帧遮罩表已做成模型交给素材 / 摆放两流，**像素级复现仍未达成** |
| 本机构建非字节可复现 | ✅ **随包带 ROM + 重录命令**（§12），复现需先建私有探针 |

---

## 4. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **X4-1** | wave 10 / U4 给 `find_overlay_map` 加的 terrain 判据该不该回退 | 把改前的候选扫描**独立重写**；同一份 35 个 dump 带 / 不带 terrain 各跑一遍；共享工具的 `main()` 端到端跑两遍 | **不该回退**：判据只改 **4/35** 个 dump（`0x00800` → `-1`），**31 个一字未变**；端到端 `grid16` 残差 **185 → 126**（剔掉假阳性），`field` / `movegrid` 数字不变 | **已确认（保留）** |
| **X4-2** | 「不带 terrain」的路径与改前**逐字节**相同 | 独立重写改前实现，35 个 dump 对照 | **是**：**0 处不同** ⇒ `terrain` 是新增可选参数、默认 `None` | **已确认** |
| **X4-3** | terrain 判据会打断判定台（步骤 5） | 直接调判定台自己的 `remake_grid`，对照改前的实现 | **不会**：**0 处不同**。判定台调 `find_overlay_map(vram, 77)`，**第二个位置参数是 `tile_max`**，terrain 走默认值 | **已确认** |
| **X4-4** | 判定台的覆盖层残差（857 px）会不会因这处越界而变过 | Q1b 的推论（输入逐个相同 ⇒ 输出必然相同） | **不会** | **已确认** |
| **X4-5** | wave 11 的「±9,520 px 抖动」是判定台的仪器抖动 | 同一个 ROM 连读 3 次，逐帧对照残差、配对与每张采集 PNG 的 sha256 | **已证伪**：wave 10 那两次跑的 **ROM sha256 不同**（`249217d7…` vs `73b74587…`）⇒ 差值属于**产品改动**；本波复现：**3 次读数完全相同** | **已证伪（根因不是仪器）** |
| **X4-6** | X1 / X2 / X3 落地后重跑流水线能全绿 | 跑流水线 + 查三条流的交付物 | **未能验证**：三流**都没交付笔记**（X1 只有在飞产物）⇒ 本波是「在飞状态」的基线；**不许当成 wave 12 终稿基线** | **未验（流未交付）** |
| **X4-7** | 单测棘轮的失败集合与 HEAD 基线**逐名相同** | 步骤 2 收据 | **是**：HEAD 101/20、工作区 117/20、**新失败 0** ⇒ 20 项预存债、零回归 | **已确认** |
| **X4-8** | 「故意破坏 ⇒ 变红」的 11 个 selftest 仍全红 | `run_selftests.ps1` 逐个 `--selftest-break` | **是**：**11 red, 0 not red** | **已确认** |
| **X4-9** | 包清单会把 selftest 的临时目录算进去 | 读 wave 11 两个包的 `packaged_files`（122 vs 714） | **会**（多算 592 个）⇒ **已修**：`MANIFEST_EXCLUDED_PARTS` 加 `selftest-scratch` | **已确认（已修）** |
| **X4-10** | wave 9 的「重制侧 battle-14 打不赢」还成立 | 读 X1 在飞产物 `build/s49-battle-balance/u2/route*.err` 的最后两行 | **已过期**：已能走到 `outcome=1` ⇒ 能打赢不再是障碍；但 X1 未交付 ⇒ **本波仍无逐屏运行帧对照数字** | **已证伪（结论过期；达成状态未验）** |
| **X4-11** | 「12 步全绿」的收据一定是一份**自洽**的包 | 把步骤 1 构建的 ROM 的 sha256 与步骤 12 实际打包的 ROM 的 sha256 对照 | **不是**：第一跑里两者**不同**（构建 `b6c2a05f…` vs 打包 `196417ca…`）⇒ 收据里的数字属于前者、包里发布的是后者 ⇒ **那份收据不能作为发布基线**。根因是**并行流在本轮运行期间重建了同一个 ROM**，不是任何一步的判据失灵 | **已证伪（已修）** |
| **X4-12** | 把 ROM 钉住就能让「构建的 sha == 打包的 sha」由构造保证 | 步骤 1 构建完把 ROM 拷贝一份钉在包内 `work/pinned-rom/measured.gba`（拷贝后核对 sha256，对不上重试 5 次），此后 `ctx.rom` 指向这份拷贝；步骤 5 额外传 `--remake-rom <钉住的拷贝>` | **是**：钉住的拷贝与构建产物的 sha256 **逐字节相同**，步骤 3 / 5 / 9 / 10 / 11 测它、步骤 12 打包它 ⇒ **并行流再怎么重建也换不掉本轮的读数** | **已确认** |
| **X4-13** | 钉住的 ROM 路径可以用相对路径 | 把 `--out` 写成相对路径再跑一遍流水线 | **不行**：步骤 10（音频）在 **0.2 s** 内就红了 —— `ERR cannot open build\s49-package-x4\work\pinned-rom\measured.gba`：**探针进程在自己的工作目录里跑，相对路径打不开**（步骤 3 / 5 / 9 用的是绝对路径，没受影响）⇒ **钉住路径必须是绝对路径** ⇒ **已修**（`pinned_rom` 用 `os.path.abspath` 构造） | **已证伪（已修）** |

---

## 5. 报告各表数字摘要

| 表 | 数字 |
|---|---|
| §0 一句话结论 | 残差 min 0 / 中位 **1,323** / max **27,325** / 全 0 帧 **5**（25 帧）；归因 **5·17·3**；三桶 **0·0·3** |
| §2.0b 读数确定性 | 连读 **3** 次，残差总和 **100,210 px** 三次相同；采集摘要逐张相同 |
| §3 覆盖层逐格族名 | field **168/24/24/50**（残差 98）、movegrid **168/24/24/2**（50）、grid16 **153/22/39/65**（126）、banner **0/0/0/0 exact ✔** |
| §4 音频事件级 | 19 个配对时刻、5 类判定 |
| §7 黑场真值 | 原版 **1881 帧 / 2 个事件**（24/18/24、24/24/24）；重制侧 **2402 帧 / 6 个事件**（4 个硬切） |
| §11 未达成项 | **22 条**（1 / 1b / 1c / 2 … 20） |
| §13 流水线收据 | **12/12 全绿**；**构建 sha == 钉住 sha == 打包 sha**（`3f1e9caa…`）；§13.1 的 selftest **11 red / 0 not red** |
| §15 结算链 | 结构 7 段已映射；**运行帧逐屏对照本波没有数字** |
| §16 越界复核 | Q1 **0** / Q1b **0** / 判据改 **4/35**（31 不变）/ `grid16` 残差 **185 → 126** |
| 报告文件 | `docs/s49-fidelity-report-20261024.md` = **755 行 / 96,482 B**（wave 11 那份是 734 行 / 82,954 B） |

---

## 6. 卡在哪

* ⛔ **X1 / X2 / X3 三条流都没有交付笔记**（本波 15:00–15:48 之间连查四遍：
  `notes/s49-fidelity/` 里没有 `X1-*.md`；`X2-pairing.md` / `X3-boundary-fixes.md`
  是 **wave 6** 的旧笔记，不是 wave 12 的交付）⇒ **本波跑的是「在飞状态」的基线**。
* ⏳ **X1 在飞**：`build/s49-battle-balance/u2/routeY.err`（15:12:11）的最后两行
  是 `after the battle: phase=13 round=5 outcome=1 enemies=0` /
  `after the settlement: phase=24` ⇒ **战斗已经能打赢**（wave 9 的
  「打不赢」结论已过期），但结算链**还没走到 `complete`**，而且**运行帧还没录下来**。
  ⏳ X1 在 15:27:18 改了 `battle_runtime_scene.cpp`、在 15:36:25 重建了 ROM
  （新 sha `3f1e9caa…`）⇒ **本轮的收据已经测的是 X1 修过之后的 ROM**。
* ⏳ **X2 在飞**：`battle_range_ui_style.h`（15:31:42）+ 两个新单测
  （`test_battle_range_ui_overlay_rules.cpp` 15:31:49、
  `test_battle_range_ui_style.cpp` 15:36:07）⇒
  本轮读数里 `movegrid-frame-v1` 的族名不一致 **4 → 2**（残差 52 → 50），
  **X2 的改动已经进 ROM 并被本轮测到**。
* ⏳ **X3 尚未见动静**：黑场仍是原版 **2 个**事件 / 重制侧 **6 个**事件。
* ⚠️ **并行构建碰撞**：本波步骤 1 的 `make` 报 `is up to date` 或正常重编
  （没撞上 objcopy 碰撞），但同一时刻只允许一路做构建这条硬约束仍然有效；
  **正因如此才必须钉住 ROM**（§2.5）。

---

## 7. 复现命令

```powershell
cd D:\Github\gba-naruto

# 1) 12 步流水线（私有输出目录，避免撞上其它流的包）
python tools/s49_package/run_pipeline.py --out build/s49-package-x4

# 2) 11 个 selftest（每个步骤故意破坏 ⇒ 必须全红）
powershell -NoProfile -ExecutionPolicy Bypass `
    -File tools/s49_package/run_selftests.ps1 `
    -PackageDir 'build\s49-package-x4'

# 3) 越界复核（单独跑）
python tools/s49_package/verify_terrain_criterion.py `
    --vram-dir build/s49-package-x4/evidence/overlay/vram `
    --out build/s49-package-x4/evidence/terrain-review.json

# 4) 报告
python tools/s49_package/make_report.py `
    --receipt build/s49-package-x4/receipt.json `
    --out docs/s49-fidelity-report-20261024.md
```

---

## 8. 确认

* **新文件全部 LF、无 BOM**（`verify_terrain_criterion.py`、本笔记、
  报告生成器与流水线的改动均为 LF）。
* **未提交 git**。
* **未改重制线任何文件**（`D:\Shell\gba-naruto-butano` 只读使用）。
* **未改逆向线任何文件**（`D:\Shell\gba-naruto-reverse` 只读）。
* **未改其它流的仪器**（§1 列出的全部仪器一律只读调用）。
* **没有伪造任何帧**：所有数字来自收据 / 证据文件。
