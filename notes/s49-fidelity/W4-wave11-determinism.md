# wave 11 / W4 —— 判定台确定性 + 出包 + 1:1 报告终审

> 工具：`tools/s49_fidelity_report.py` + `tools/s49_fidelity_report/`、
> `tools/s49_package/`
> 产物：`build/s49-package/`（收据 + 包）、`docs/s49-fidelity-report-20261024.md`
> 2026-10-24 · 流 W4（wave 11）。**所有数字都是本机实测。**
> 重制线 **零改动**；逆向线 **零改动**；**未提交 git**。

---

## 0. 一句话结论

**判定台的「±9,520 px 抖动」不是仪器抖动 —— 是那两次跑用的 ROM 不是同一个。**
wave 10 / U4 自己留下的两份报告里 `captures.remake.rom_sha256` **不同**
（`249217d7…` vs `73b74587…`）⇒ 差的那 9,520 px 属于**产品改动**。
本波在同一 ROM（sha256 钉住）上连读 **3 次**，残差总和 **100,210 px**、
中位 **1,323**、峰值 **27,325**、全 0 帧 **5**、归因 **5·17·3**、
配对差三桶 **0·0·3**、覆盖层残差总和 **857 px** —— **三次逐项完全相同**，
**每张采集 PNG 的 sha256 也逐张相同**。
⇒ **判定台的判定语义（`product_diff` / `pairing_diff` / 三桶）一个字没改**；
改的是**仪器现在能自证这件事**。

---

## 1. 根因：不是 tie-break，也不是 capture 抖动

| 候选根因 | 判定方法 | 结果 | 状态 |
|---|---|---|---|
| 配对搜索的并列最优没有稳定 tie-break | 读判定台的配对代码 | **已证伪**：`sorted(matrix.items(), key=lambda kv: (kv[1], kv[0]))` —— 残差相同按**帧名**排 ⇒ tie-break 本来就是稳定的 | 已证伪 |
| capture 的帧序 / settle 抖动 | 同 ROM 连跑 3 次，比对每张采集 PNG 的 sha256 | **已证伪**：3 次采集的 PNG **逐张逐字节相同**（摘要 `af722772d492d293…`） | 已证伪 |
| ⭐ **两次跑用的 ROM 不是同一个** | 读 wave 10 / U4 留下的两份报告的 `captures.remake.rom_sha256` | **已确认**：`249217d7f59a2199…`（11:15:03，残差 168,816，`step-12-A` → `step-19-A`）vs `73b74587595d4581…`（11:27:10，残差 104,784，`step-12-A` → `step-16-A`）⇒ **ROM 变了** | **已确认（根因）** |

> ⚠️ wave 10 的终审报告 `docs/s49-fidelity-report-20261024.md` 把这个结论
> 写成了「判定台读数不确定 ⇒ 棘轮门禁天然带 ±9,520 px 的抖动」
> （台账 U4-7「已证伪（读数不确定）」）⇒ **本波已更正**。

---

## 2. 改了什么（**判定语义不动**）

| 文件 | 改动 | 语义影响 |
|---|---|---|
| `tools/s49_fidelity_report/determinism.py` | **新增**：把 N 次读数逐项比对（残差摘要 / 归因 / 三桶 / 逐帧配对 / 每张 PNG 的 sha256），并**把 ROM 变了这件事单独报出来**（⇒ 比较作废，不是「失败」） | 无 |
| `tools/s49_fidelity_report.py` | **新增 `--repeat N`**（连读 N 次）、**`--original-rom` / `--remake-rom`**（把 ROM 钉住）；主流程拆成 `_measure()` 一次读数 | 无 |
| `tools/s49_fidelity_report/ratchet.py` | 棘轮结果里带上**基线与候选两侧的 ROM sha256** 与 `changed` 标志（**不改变 `ok`**：棘轮本来就要跨 ROM 比较） | 无 |
| `tools/s49_fidelity_report.py`（capture 侧） | ⭐ **修了一个会误导人的 bug**：重制侧采集的 audit 里 `rom_sha256` 填的是**原版** ROM 的摘要（`MGBA_BOOT_SEQUENCE_ROM_SHA256` 被填成 `ORIGINAL_ROM_SHA256`）⇒ 现在填重制侧 ROM 自己的摘要 | 无（收据字段修正） |
| `tools/s49_package/run_pipeline.py` | 步骤 5 现在**连读 3 次**（`--repeat 3`，可用 `--judgment-repeat` 调），读数不一致 ⇒ 步骤 5 变红；收据里带上确定性结论与两侧 ROM sha256 | 无（门禁加强） |
| `tools/s49_package/run_pipeline.py` / `s49_fidelity_report.py` | ⭐ **修了一个会把绿灯变红的坑**：控制台是 **GBK**，`⇒` / `⭐` 这类字符会抛 `UnicodeEncodeError`（**在测量全部完成之后**抛 ⇒ 步骤 5 明明 PASS 却 exit 1）。现在 stdout/stderr 用 `errors="replace"` | 无 |

⚠️ **没有**改 `product_diff` / `pairing_diff` / 三桶分类的任何判据。

---

## 3. 验收：同一 ROM 连跑 3 次

```powershell
# 0) 把 ROM 钉住（避免并行流在跑之间重建 ROM）
Copy-Item 'D:\Shell\gba-naruto-butano\butano-sequel\butano-sequel.gba' `
          'D:\Github\gba-naruto\build\w4-det\pinned\butano-sequel.gba' -Force

# 1) 一次进程内连读 3 次（步骤 5 现在默认就这样跑）
python tools/s49_fidelity_report.py --out build/w4-det/rep/report.json `
    --work-dir build/w4-det/rep --remake-rom build/w4-det/pinned/butano-sequel.gba `
    --repeat 3

# 2) 三个独立进程各读一次，跨进程再比一遍
foreach ($i in 1..3) {
  python tools/s49_fidelity_report.py --out "build/w4-det/proc$i/report.json" `
      --work-dir "build/w4-det/proc$i" `
      --remake-rom build/w4-det/pinned/butano-sequel.gba" --quiet
}
python build/w4-det/compare_runs.py build/w4-det/proc1/report.json `
    build/w4-det/proc2/report.json build/w4-det/proc3/report.json
```

实测（重制侧 ROM sha256 `b6c2a05fa50e28613ec8ab35de5306ef635819ab87917756537b248ba061c2cb`，
流水线步骤 5 的收据里就是这三行）：

| 读数 | 战场区残差总和 | 中位 | 峰值 | 全 0 帧 | 归因 | 三桶 | 采集摘要 |
|---|---:|---:|---:|---:|---|---|---|
| 1 | 100,210 | 1,323 | 27,325 | 5 | 5·17·3 | 0·0·3 | `af722772d492d293…` |
| 2 | 100,210 | 1,323 | 27,325 | 5 | 5·17·3 | 0·0·3 | `af722772d492d293…` |
| 3 | 100,210 | 1,323 | 27,325 | 5 | 5·17·3 | 0·0·3 | `af722772d492d293…` |

⇒ **三次完全相同**；逐帧配对**逐项相同**；采集 PNG **逐张逐字节相同**；
三个独立进程的结果也**完全相同**（`build/w4-det/proc{1,2,3}/report.json`）。
其它读数：整屏残差总和 **197,875**（中位 8,706、峰值 35,005）、
覆盖层残差总和 **857**（峰值 192、全 0 帧 17/25）、
全 0 的战场帧 = `step-12-A` / `step-13-A` / `step-14-A` / `step-15-A` / `step-17-A`。

---

## 4. 越界复核：wave 10 / U4 给 `find_overlay_map` 加的 terrain 判据

wave 10 的 U4 流**自报了一处越界**：它在**别的流**的仪器
（`tools/s49_overlay_align/compare_overlay_families.py`）里给
`find_overlay_map` 加了 **terrain 判据**（「solid 必须落在受阻地形上」），
超出「只授权改锚点」的范围。**本波复核结论：保留，不回退。**

| 复核项 | 结论 |
|---|---|
| 是不是真越界 | **是**（改了别的流的仪器文件，且改的是**判据**） |
| 向后兼容吗 | ✅ **是**：`terrain` 是**新增的可选参数**，默认 `None` ⇒ 走原路径（`if terrain is None: return max(candidates)[1]`）⇒ 判定台自己的 `overlay.py`（只按 VRAM 读）**行为一字未变** |
| 不改它会不会测出假窗口 | ⛔ **会**。在 wave 10 的 35 个 walk dump 上实测：**不带** terrain 时 `step-00-base` / `step-01-Down` / `step-02-Down` / `step-03-A` 四个 dump 返回**假窗口 `0x00800`**（图块数据）；**带** terrain 时这四个返回 `-1`（正确地「没有覆盖层」）；**其余 31 个 dump 一字未变** ⇒ **判据窄且可证** |
| 有没有循环论证 | ⚠️ **有，必须写明**：terrain 来自**重制线自己的生成头** `generated_battle_map_content.h` ⇒ 该判据只保证「覆盖层与**产品自己用的**地图一致」，**不是**独立于产品的绝对真值。绝对真值仍是原版导出的 `s49-original-movegrid-tilemap-v1` |

⇒ **本流（只读调用方）没有改它，也没有回退它**；
`tools/s49_overlay_align/` 在 wave 11 归 **W2** 流所有，
W2 若要动这个文件，应把这条判据**收编进自己的版本**并复核一次。

---

## 5. 出包（12 步流水线）

`python tools/s49_package/run_pipeline.py` → 收据 `build/s49-package/receipt.json`
（`generated_at` = **2026-10-24T13:48:50+08:00**，`ok: true`，`failed_step: null`）。

| 步 | 名称 | 结果 | 耗时(s) | 关键数字 |
|---:|---|---|---:|---|
| 1 | build | 🟢 | 25.3 | ROM sha256 `b6c2a05fa50e2861…` |
| 2 | unit-tests | 🟢 | 246.8 | HEAD 101 pass / 20 fail；工作区 **117 pass / 20 fail**；**新失败 0** |
| 3 | smoke | 🟢 | 0.7 | 4096 帧不崩 + 中文标题 |
| 4 | headless | 🟢 | 0.2 | 无窗口无声 |
| 5 | judgment | 🟢 | 35.9 | **连读 3 次，读数相同**；残差总和 100,210 px |
| 6 | overlay | 🟢 | 0.9 | 逐格对拍走整条 walk（见 §6b） |
| 7 | idle-frames | 🟢 | 0.2 | 静态帧门禁 |
| 8 | outline-wave | 🟢 | 0.3 | 200/200 |
| 9 | blackfade | 🟢 | 50.2 | 原版 1881 帧 / 重制侧 2402 帧 |
| 10 | audio | 🟢 | 13.0 | 事件级对照 |
| 11 | save-boundary | 🟢 | 15.7 | `--repeat 2` |
| 12 | package | 🟢 | 3.7 | 清单 **122 个文件**核对一致 |

⇒ **12/12 全绿。**

⚠️ **本波踩到的一个环境坑（不是代码缺陷）**：第 13:36 那一跑里步骤 1 红了
—— W1 正在重建同一个 ROM，**5 次 objcopy 碰撞重试（每次等 60 s）全部撞上**
⇒ 「同时只允许一路做构建」这条规矩在并行流密集时是硬约束；
等 W1 那一轮构建结束后重跑就绿了。

---

## 6. 单测棘轮：20 项预存债，**零回归**

| | HEAD 基线 | 工作区 |
|---|---:|---:|
| 测试数 | 121 | 136（**+15 个新测试**，W2/W3 加的，**全部通过**） |
| pass | 101 | **117** |
| **fail** | **20** | **20** |
| **新失败** | — | **0** |

⇒ **失败集合与 HEAD 基线逐名相同**（20 项预存债，名单见
`notes/s49-fidelity/Q-unit-test-baseline.md` §2.1）⇒ **本次零回归**。
⚠️ **不许写成「单测全绿」**。

### 6b. 在飞过程中踩到的两个真实回归（都已由 W3 自己修掉）

第一次跑（12:49）步骤 2 有 **9 项新红**，第二次跑（13:03）还有 **5 项新红**：
全部在**编译期**挂在 W3 独占的
`butano-sequel/game/include/konoha/battle_scene_controller.h` 的 `static_assert`
（"the phase enum and the generated binding table disagree"）
—— W3 给 `battle_scene_phase` 加了 `post_battle_dialogue` 与 `task_menu`
两个相，**24 行的生成表 `battle_scene_phase_origins` 没同步**。
这正是 `WAVE11-TASKS.md` §3.2 预先警告过的那一处：

> ⚠️ **`battle_scene_phase_origins` 是 24 行生成表，`static_assert == 24` 会失配**
> ⇒ 改的时候一起处理那个表。

⇒ **重制线是本流的禁区**，本流**没有改**这一行；
W3 同步生成表之后，失败集合就回到 HEAD 的 20 项。

---

## 6c. 覆盖层逐格族名（步骤 6，**整条 walk 口径**）

| 时刻 | 同亮 | 原版缺 | 重制多画 | 族名不一致 | 残差 | exact |
|---|---:|---:|---:|---:|---:|---|
| `field-frame-v1` | 168 | 24 | 24 | 50 | 98 | 否 |
| `movegrid-frame-v1` | 168 | 24 | 24 | 4 | 52 | 否 |
| `grid16-frame-v1` | 153 | 22 | 39 | 65 | 126 | 否 |
| `banner-frame-v1` | 0 | 0 | 0 | 0 | **0** | **是** |

⇒ 目标（同亮 192 / 缺 0 / 多画 0 / 不一致 0）**仍未达成** ⇒ **W2 在飞**。

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| W4-1 | 判定台的残差读数是逐次确定的（同 ROM 两跑读数相同） | 同一个 ROM（sha256 钉住）连跑 3 次判定台，逐帧对照残差与配对 | **是**：3 次读数完全相同（100,210 / 1,323 / 27,325 / 5 / 5·17·3 / 0·0·3 / 857），逐帧配对相同，每张 PNG 的 sha256 相同 | **已确认** |
| W4-2 | wave 10 报的「同一个 ROM 两跑，残差 9,520 → 0、总和 114,304 → 104,784」是判定台的抖动 | 读 wave 10 / U4 留下的两份报告的 `captures.remake.rom_sha256` | **已证伪**：那两次跑的 ROM 不是同一个（`249217d7…` vs `73b74587…`）⇒ 差值属于产品改动 | **已证伪（根因不是仪器）** |
| W4-3 | 配对搜索有并列最优、没有稳定 tie-break | 读判定台的配对代码 | **已证伪**：`sorted(..., key=lambda kv: (kv[1], kv[0]))` —— 残差相同按帧名排 | **已证伪** |
| W4-4 | capture 的帧序 / settle 会抖 | 同 ROM 连跑 3 次，比对每一张采集 PNG 的 sha256 | **已证伪**：3 次采集逐张逐字节相同 | **已证伪** |
| W4-5 | 判定台可以**不改语义**就自证读数确定性 | 加 `--repeat N`（连读 N 次并逐项比对），判据不动 | **是**：只加 ① `--repeat N` ② 棘轮收据带两侧 ROM sha256（不改 `ok`） | **已确认** |
| W4-6 | 判定台自己报出的 ROM 身份是对的 | 读收据里 `captures.remake.audit.rom_sha256` | **原来不对**（填的是原版 ROM 的摘要）⇒ **已修** | **已确认（已修）** |
| W4-7 | wave 10 / U4 给 `find_overlay_map` 加的 terrain 判据该不该回退 | 35 个 walk dump 上带 / 不带 terrain 各跑一遍 | **不该回退**：不带时 4 个 dump 返回假窗口 `0x00800`，带时返回 `-1`，其余 31 个一字未变；且默认 `None` ⇒ 判定台不受影响 | **已确认（保留）** |
| W4-8 | 判定台的 `⇒` 打印会把绿灯变红 | 步骤 5 的日志 | **已确认**：GBK 控制台抛 `UnicodeEncodeError`（在棘轮 PASS **之后**）⇒ exit 1 ⇒ **已修**（`errors="replace"` + ASCII 箭头） | **已确认（已修）** |
| W4-9 | 步骤 2 的 5 项新红是本流造成的 | 读失败详情 + `git diff HEAD --stat`（重制线） | **已证伪**：5 项全部挂在 **W3 独占**的 `battle_scene_controller.h` 的 `static_assert`（生成表 24 行 vs 26 相）；本流**零改动**重制线 | **已证伪（是 W3 在飞）** |
| W4-10 | W1/W2/W3 落地后重跑流水线能全绿 | 跑 `run_pipeline.py` | **11/12 绿**；步骤 2 的红项全部指向 W3 的在飞改动（§6）⇒ **本波不能签「12/12 全绿」** | **部分确认** |

---

## 8. 复现命令

```powershell
cd D:\Github\gba-naruto

# 1) 判定台（连读 3 次，ROM 钉住）
Copy-Item 'D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba' `
          'D:\Github\gba-naruto\build\w4-det\pinned\butano-sequel.gba' -Force
python tools/s49_fidelity_report.py --out build/w4-det/rep/report.json `
    --work-dir build/w4-det/rep --remake-rom build/w4-det/pinned/butano-sequel.gba `
    --repeat 3

# 2) 12 步流水线
python tools/s49_package/run_pipeline.py

# 3) 报告
python tools/s49_package/make_report.py --receipt build/s49-package/receipt.json `
    --out docs/s49-fidelity-report-20261024.md

# 4) 11 个 selftest（每个步骤故意破坏 ⇒ 必须全红）
powershell -NoProfile -ExecutionPolicy Bypass -File tools/s49_package/run_selftests.ps1
```

---

## 9. 确认

* **新文件全部 LF、无 BOM**（`determinism.py`、本笔记）。
* **未提交 git**。
* **未改重制线任何文件**（`D:\Shell\gba-naruto-butano` 只读使用）。
* **未改逆向线任何文件**（`D:\Shell\gba-naruto-reverse` 只读）。
* **未改其它流的仪器**（`s49_overlay_align` / `s49_blackfade` / `s49_audio_l` /
  `s49_save_boundary` / `s49_idle_*.py` / `s49_orig_map` / `s49_pairing` /
  `s49_starfield` / `s49_v2_anchor` / `s49_v3_dialogue` / `s49_x3_boundary` /
  `s49_opening_title` / `s49_battle_balance` / `s49_victory_capture` /
  `s49_u3_settlement` 一律只读调用）。
