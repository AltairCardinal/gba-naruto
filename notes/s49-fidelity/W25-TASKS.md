# W25-TASKS —— wave 25 任务书：开场段解剖 / 入场过渡 / 『請準備』窗 / 4bpp L2

> 2026-10-26 00:30 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`W24-PARENT-wrapup.md`（wave 24 汇总）· `W24-G1-presentation-state.md` · `W24-G2-mask-palette-4bpp.md` ·
> `W24-G3-settlement-frame.md` · `W24-G4-sixty-nine.md` · `W23-PARENT-wrapup.md`
> 仪器：`tools/s49_fidelity_report.py`（判定台，唯一验收仪器）· `tools/s49_wave18/align_capture_steps.py`（25 帧固定偏移）

---

## 0. 目标与现状

| 项 | 值 |
|---|---|
| 目标 | S49「木叶丸 vs 野蜂」战斗**完全复刻**（玩家看得见的画面 + 游戏逻辑状态；不计寄存器） |
| 判定台残差 | **38,047 px**（已接受基线 `build/s49-package/baseline-accepted/report.json`，accepted_at 2026-10-25T22:57:20） |
| 基线 ROM | `b97daa81ca4d90ee36521c042292b5aeeb035fff99b02c50f576d5c3d9c1340a`（12,258,628 B） |
| 25 帧固定偏移残差 | ⭐ **54,959 px**（**已更正**，见下方 §0.0） |
| 棘轮 | 残差**只许变小**；ROM 变了而残差没变大 ⇒ `incomparable`（退出码 2）**不是通过** ⇒ 需显式 `--accept-baseline` |
| 流水线 | `python tools/s49_package/run_pipeline.py --out build/s49-package-w25`（12 步，必须 12/12 全绿） |
| 单测 | `w18-run-all-tests.sh` ⇒ 期望 **pass=119 / fail=20**（lane 无 E2 那条时 118/20），**零新增红** |

### 0.0 ⭐ 更正（2026-10-26 00:45）：**25 帧固定偏移的基线是 54,959 px，不是 53,364 px**

> **53,364 px 是 wave 22 的 `w22-d1` lane 数字。** 已接受基线（共享树）此后有**已归档的 +1,595 px 漂移**，
> **全部落在 `step-24-A`** —— 那一帧对构建/ROM 敏感（见 `W23-F3` §6-5、`W24-G1` §3）。
> wave 24 的 G3 在**当前共享树**上实测：25 帧 = **54,959 px**、判定台 = **38,047 px**（两个口径都正好等于基线）。
>
> ⇒ **判读口径**：你的改动后 25 帧固定偏移残差 **≤ 54,959 px** 才算没变差（不是 ≤ 53,364）。
> **判定台基线仍是 38,047 px**，不变。
> ⇒ 顺带更正：wave 22 之后任何引用「53,364」的地方，**当前共享树口径下应写 54,959**。

### 0.1 ⭐⭐⭐ 本波最重要的新发现：**判定台逐帧残差构成**

父代理用 `tools/s49_w25/baseline_breakdown.py` 拆开已接受基线，得到 **25 帧逐帧**：

| # | 原版帧 | 判定台配对的重制帧 | **战场区残差 px** | 整屏 px | 分类 |
|---:|---|---|---:|---:|---|
| 0 | step-00-base | step-24-A | 1,308 | 1,525 | product_diff |
| 1 | step-01-A | step-05-A | 1,294 | 8,974 | product_diff |
| 2 | step-02-A | step-06-A | 1,680 | 9,360 | product_diff |
| 3 | step-03-A | step-07-A | **2,514** | 10,194 | product_diff |
| 4 | step-04-A | step-08-A | 1,940 | 9,620 | product_diff |
| 5 | step-05-A | step-09-A | 2,057 | 9,737 | product_diff |
| 6 | step-06-A | step-10-A | 1,217 | 8,897 | product_diff |
| 7 | step-07-A | step-11-A | 1,921 | 9,601 | product_diff |
| 8 | step-08-A | step-12-A | 1,026 | 8,706 | product_diff |
| 9 | step-09-A | step-13-A | 759 | 8,439 | product_diff |
| 10 | step-10-A | step-14-A | 278 | 7,958 | product_diff |
| 11 | step-11-A | step-22-A | 305 | 305 | product_diff |
| **12** | **step-12-A** | **step-20-A** | **9,520** | 9,692 | **pairing_diff / moment_mismatch** |
| 13 | step-13-A | step-18-A | 28 | 100 | product_diff |
| 14 | step-14-A | step-18-A | **0** | 0 | identical |
| 15 | step-15-A | step-19-A | **0** | 0 | identical |
| 16 | step-16-A | step-20-A | 43 | 94 | product_diff |
| 17 | step-17-A | step-21-A | **0** | 0 | identical |
| 18 | step-18-A | step-22-A | **0** | 0 | identical |
| 19 | step-19-A | step-23-A | 106 | 106 | product_diff |
| **20** | **step-20-A** | step-24-A | **3,881** | 3,881 | product_diff |
| 21 | step-21-A | step-25-A | 1,535 | 1,899 | product_diff |
| 22 | step-22-A | step-26-A | 2,696 | 10,376 | product_diff（overlay 176） |
| 23 | step-23-A | step-27-A | 1,161 | 1,350 | product_diff（overlay 192） |
| 24 | step-24-A | step-28-A | 2,778 | 2,778 | product_diff（overlay 192） |

⇒ ⭐ **三个战场区大户**：
* **#0–#11「开场 12 帧」= 17,261 px（45.4 %）** —— **前 24 波从未有人碰过这一段**
  ⛔ **更正（wave 25 / H1 实测）**：**加总错了 962 px**，真值 **16,299 px = 42.8 %**（逐帧值全对）。
  校验：`python tools/s49_w25/baseline_breakdown.py` ⇒ `# sum(field) = 38047`。
* **#12 = 9,520 px（25.0 %）** —— 入场过渡晚一拍（G1 的 R-G1-A/B/C）
* **#20 = 3,881 px（10.2 %）** —— 『請準備...』窗没画（F2 的资产已有，缺接线）

### 0.2 战场区的定义

`tools/s49_fidelity_report/paths.py:30` ⇒ **`FIELD_AREA = (0, 0, 240, 128)`**（屏幕顶部 128 行）。
⇒ **底部 32 行的 HUD 面板差异不计入残差**；计入的是战场区内的相位标签、单位站位、红箭头等。

### 0.3 父代理已目视确认的开场段差异（`build/w25-montage/intro.png`）

| 现象 | 原版 | 重制侧 |
|---|---|---|
| 相位标签 | `step-03-A` 无标签 | `step-07-A` 顶部有「S DEPLOY / UNIT」 |
| 单位站位 | 鸣人站在上方中间 | 鸣人站在右边 |
| 红箭头标记 | 在上方单位上 | 位置不同 |
| 底部 HUD | 有完整状态面板（名字 + HP + 忍数） | **空黑条**（不计入残差） |
| **黑场星形**（帧 #11） | **橄榄黄**星 | **红色**星（305 px） |

⇒ 假说：**开场是「相位时序错位」**（重制侧还在 DEPLOY UNIT 相位时原版已经进入下一相位），
外加**星形遮罩颜色错误**这一处小而精确的资产缺陷。

---

## 1. 通用纪律（**所有流必读，违反即作废**）

1. **一次只改一处，跑一次，记一行。** 结论落进**假设台账**（一行一个假设：判定方法 / 结果 / 状态 = 未验·已证伪·已确认）。
2. **连续 3 次同样结果 ⇒ 停**，把「这条路走不通」写进台账，换方法。
3. **⛔ 先写笔记骨架，再写代码。** 第一件事就是建 `notes/s49-fidelity/W25-<流>.md` 并写好标题结构，结论**增量更新**进去。
   （wave 18/19/20 有多路子代理在写完代码前被额度截断，结论只存在于对话里。）
4. **共享树 `D:\Shell\Github\gba-naruto-butano\butano-sequel` 全程只读。** 只在 lane 副本里改。
5. **lane 的 `graphics/` 是真实目录**（`tools/s49_w25/setup_lanes.py` 建的就是真实副本）⇒ 在 lane 里改资产**安全**。
   但注意：**改完 lane 的资产不会自动进共享树**，父代理收口时统一拷。
6. **改含中文的文件一律用 `edit`/`write` 工具**，不要用 PowerShell `Set-Content`/`-replace`（PS 5.1 按 GBK 读入会毁 UTF-8）。
7. **新写文件一律 LF、无 BOM。**
8. **本机构建非字节可复现** ⇒ 一切读数必须**绑定自己那份 ROM 的 sha256**；**不得跨 ROM 比较残差**。
9. **判定台读数必须同 ROM 比**。ROM 变了 ⇒ 旧读数作废。
10. **⚠️ 录像锁**：全机同一时刻**只允许一路跑长录制**（>60 s）。
    `python tools/s49_w20/capture_lock.py --run --label <流> -- <命令>` / `--status`。
    跑完查孤儿进程：`Get-Process mgba-probe -ErrorAction SilentlyContinue`。
11. **⚠️ 探针 exe 会被占用** ⇒ 用 `$env:KONOHA_PROBE_OUT` 另建副本，**不得**覆盖共享的 `build/mgba-probe/mgba-probe.exe`。
12. **⚠️ 共享 `probe.py` 每行一个读线程会死锁** ⇒ 长录制用 `tools/s49_battle_balance/w1_probe.py`。
13. **不要把「画面会变的帧」加进「有变化才重画」的判定**（AGENTS.md 仪器纪律第 12 条）。
14. **仪器读出的「寄存器」要先证明它真的是那个寄存器**（第 13 条：GBA IO 是 **2 字节步长**）。
15. **判定台残差对「帧号位移/画面冻结」和「渲染」一样敏感**（第 15 条）⇒ 改任何时序都要同时看
    `s49_fidelity_report.py`（arg-min）与 `align_capture_steps.py`（固定偏移）**两个仪器**。

### 1.1 构建命令（WSL，必须导出 LIBBUTANOABS）

```powershell
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Github/gba-naruto/build/<lane>/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"
```
> ⚠️ `make -j4` 必须在**你自己的 lane 目录**里跑。**不要** `cd` 到共享树去构建。
> ⚠️ 若报 `objcopy: Invalid argument` ⇒ 等 60 s 重试（最多 5 次），多半是并发写同一个输出。

### 1.2 单测棘轮

```powershell
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/<lane>/butano-sequel
```
⇒ 期望 **pass=119 / fail=20**（lane 缺 E2 那条时 118/20），**零新增红**。

### 1.3 判定台 + 25 帧固定偏移

```powershell
# 只重录重制侧；原版侧从 w22 出包复制
python tools/s49_w24g1/capture_remake.py --rom <lane ROM> --work-dir build/<流>/work --original build/s49-package-w22/work/s49-report/capture-original

python tools/s49_wave18/align_capture_steps.py --original build/<流>/work/capture-original --remake build/<流>/work/capture-remake --out build/<流>/align.json

python tools/s49_fidelity_report.py --out build/<流>/report.json --work-dir build/<流>/work --remake-rom <lane ROM> --skip-capture
```

### 1.4 lane 合并（父代理收口时做，流不用管）

`tools/s49_wave18/integrate.py` 是**整文件覆盖**，同一文件被两路改就会丢工作。
wave 25 里 **H2 / H3 / H4 都改 `game/src/battle_runtime_scene.cpp`** ⇒ 父代理用
`python tools/s49_w25/merge_lanes.py --file game/src/battle_runtime_scene.cpp --lane w25-h2 --lane w25-h3 --lane w25-h4 --apply`
做**真三方合并**（`git merge-file`）。
⇒ **所以你在 `battle_runtime_scene.cpp` 里只准改属于自己那一段的代码**，不要重排、不要格式化、不要动别人的区段。

---

## 2. 四路分工

| 流 | 主题 | 目标残差 | lane | 独占文件 |
|---|---|---:|---|---|
| **H1** | ⭐⭐⭐ **开场 12 帧解剖**（#0–#11，17,261 px） | ≤ 17,261 | `build/w25-h1` | `game/include/konoha/battle_scene_presentation.h` · `game/include/konoha/battle_presentation_script.h` |
| **H2** | ⭐⭐⭐ **入场过渡早一拍**（#12，9,520 px） | ≤ 9,520 | `build/w25-h2` | `game/include/konoha/battle_black_field_star_mask.h` · `game/include/konoha/battle_black_field_timing.h` · `game/include/konoha/battle_presentation_content.h` · `game/src/battle_runtime_scene.cpp`（仅「入场背景/空框」区段） |
| **H3** | ⭐⭐ **『請準備...』窗接线**（#20，3,881 px） | ≤ 3,881 | `build/w25-h3` | `graphics/battle_ui_prepare_box.bmp` · `graphics/battle_ui_prepare_box.json` · `game/src/battle_runtime_scene.cpp`（仅「prepare box」区段） |
| **H4** | ⭐⭐ **4bpp L2：overlay 与调色板解耦** | 解锁 | `build/w25-h4` | `game/include/konoha/battle_range_ui_style.h` · `game/src/battle_runtime_scene.cpp`（仅「overlay」区段） · `graphics/**`（4bpp 资产集） |

---

## 3. H1 —— ⭐⭐⭐ 开场 12 帧残差解剖（`W25-H1-intro.md`）

### 3.1 目标

**把 #0–#11 的 17,261 px 拆到「可修的具体原因」为止，并至少实现 + 验证其中最大的一个。**

### 3.2 已知事实

* 战场区残差逐帧：1,308 / 1,294 / 1,680 / **2,514** / 1,940 / 2,057 / 1,217 / 1,921 / 1,026 / 759 / 278 / 305
* 判定台配对（arg-min）与 25 帧固定偏移配对（offset +4）**一致**（见 `build/w22-d1/align-v4.json`）：
  `step-00-base↔step-04-A`、`step-01-A↔step-05-A`、`step-02-A↔step-06-A`、`step-03-A↔step-07-A`、
  `step-04-A↔step-08-A`、`step-05-A↔step-09-A`、`step-06-A↔step-10-A`、`step-07-A↔step-11-A`、
  `step-08-A↔step-12-A`、`step-09-A↔step-13-A`、`step-10-A↔step-14-A`、`step-11-A↔step-15-A`
* 帧 PNG 在 `build/s49-package-w22/work/s49-report/capture-{original,remake}/`
* 父代理的目视结论见 §0.3（相位标签、单位站位、红箭头、黑场星形颜色）

### 3.3 方法建议

1. 用 `tools/s49_w25/montage.py` 逐帧出「原版 | 重制 | 差分热图」三联图。
2. 差分按**连通块/颜色**聚类，区分：
   * 「相位标签」类（原版没有、重制有 ⇒ 重制还在上一相位）
   * 「单位/OBJ」类（站位或朝向不同）
   * 「标记」类（红箭头）
   * 「调色板/黑场」类（整帧染色）
3. **先判定「这是时序差还是内容差」**：
   * 用原版的 `.ss9`（存档态）+ 探针读遥测，看原版在 `step-0X` 这一刻处于哪个相位；
   * 再看重制侧对应帧的遥测（`tools/s49_w24g1/script_telemetry.py` 读遥测地址 `0x0202A570`）。
   * ⇒ 若相位相同 ⇒ 内容差（资产/坐标/颜色）；若相位不同 ⇒ **时序差**（各相位时长不同）。
4. 相位时序差若是主因 ⇒ 找「相位时长表」在哪张表里（可能在
   `game/include/konoha/battle_scene_presentation.h` / `battle_scene_controller.h` / `battle_presentation_content.h`）。
   ⚠️ **后两个文件不是你的独占** ⇒ 若是「只确认修法、但文件归属冲突」，**停下来把结论写进笔记**，
   并在笔记里给出**精确的改动提案（文件 + 行 + 前后值）**，由父代理在 wave 26 接线。**不要越界改。**
5. **星形遮罩颜色**（帧 #11，原版橄榄黄 vs 重制红色，305 px）是一个**小而精确**的候选：
   它在 `battle_black_field_star_mask.h`（**H2 的独占**）⇒ 若是它，**写进笔记交给 H2/父代理**，不要改。

### 3.4 交付物

* `notes/s49-fidelity/W25-H1-intro.md`：逐帧解剖表 + 假设台账 + 接线请求
* `tools/s49_w25h1/`：你写的工具（逐帧差分聚类、遥测读取等）
* 若在**你的独占文件**里实现了一个修法 ⇒ 在 lane `build/w25-h1` 里改好 + 构建 + 录制 + 测量，
  给出「改前/改后」两个仪器的逐帧表。

### 3.5 验收

* 12 帧逐帧给出「残差 px 的归因」，总和 = 17,261（误差 ≤ 100 px 要能解释）
* 至少给出 **1 个**可接线、修法明确的结论；**若归因指向别的流独占的文件**，给出精确改动提案
* 若动了独占文件 ⇒ 25 帧固定偏移残差**不得上升**，单测零新增红

---

## 4. H2 —— ⭐⭐⭐ 入场过渡早一拍（`W25-H2-entry-transition.md`）

### 4.1 目标

**让重制侧的入场过渡比原版早一拍收尾**，使 `step-12-A`（判定台 #12，**9,520 px**）掉到 ≈ 200–1,000 px。

### 4.2 已知事实（wave 24 / G1 的实测结论，**不要再重做**）

* 原版：`orig-11` = 黑场 + 星形（过渡中）；`orig-12` = 场景 + **空对话框**（过渡**已结束**）。
* 重制侧：`remake-15` = 黑场；`remake-16` = **仍在过渡里** ⇒ **晚一拍收尾**。
* `remake-16` 的遥测：`phase = 18 (script_blocked)`、`scene_frame = 0`、`script_command_index = 2`、
  `script_message_window_visible = 1`、两个肖像都可见、⭐ `render_stage = 100`。
* `render_stage = 100` 只在 `battle_runtime_scene.cpp:8861` 被写 —— 紧跟「场景建立时创建地图 BG」之后、
  **90 帧黑场淡入循环（`:8869-8894`）之前** ⇒ **落点那一帧还在淡入里** ⇒ 屏上必然是「地图 + 过渡」。
* G1 已实现但**因为前置条件未满足而未生效**的 **R-G1-C**（在 `build/w20-e1` lane 与
  `tools/s49_w24g1/apply_g1_edits.py` 里）：
  * `battle_cutscene_entry_background(state, battle_id)`：battle 14 且 `phase == script_blocked` 且
    **脚本还没说过话**（`!state.script.portraits_revealed`）⇒ 用**入场背景**
  * ⭐ 入场底图 = **`graphics/scenario_41_tutorial_bg.bmp`**（与原版 `step-12-A` 的 y8..95 带 **0 px** 命中；
    `battle_ui_dialogue_background` 是另一张图，会白留 **9,954 px**）
  * `battle_dialogue_background_runtime_renderer` 支持两张背景，切换时先释放旧的（先 `map.reset()`）
  * `dialogue_background_requested`：入场那一拍不再被 `!presentation.busy()` 挡住
  * `update_script_message_window()`：新增 `cutscene_entry` 入参；入场那一拍画**空对话框**
  * `#include "bn_regular_bg_items_scenario_41_tutorial_bg.h"`
* **R-G1-B**：`battle_presentation_typewriter_start_delay = 52` ⇒ 需 **≥ 90**（覆盖 90 帧入场淡入），
  否则第一行在淡入里就打完了 ⇒ 「空框 + 无肖像」永远不会被渲染成可见帧。
  ⚠️ **R-G1-B 必须与 R-G1-A 同轮落地**（G1 明确警告：单独改会让 `step-13/14/15` 少 40 帧文字而变差）。
* **R-G1-A**（你的主线）：**黑场 + 星形遮罩的结束时机**。

### 4.3 方法

1. **先做 R-G1-A 的取证**（不要先改）：
   * 原版：`orig-11`（过渡中）→ `orig-12`（过渡完）之间隔几帧？
   * 重制侧：`remake-15` → `remake-16` 之间隔几帧？淡入循环在 `:8869-8894`，**90 帧**是硬编码还是表驱动？
   * 查 `battle_black_field_timing.h` / `battle_black_field_star_mask.h` / `battle_black_field.h`：
     **黑场淡入/淡出的时长与星形遮罩的帧数**分别在哪一行？
   * 读 `battle_runtime_scene.cpp:8861-8900` 附近的淡入循环，确认 `render_stage` 的语义。
2. **量化目标**：让重制侧的「过渡结束帧」落在原版「过渡结束帧」的**同一拍**（或更早 1 拍）。
   ⇒ **一次只改一个时长常数**，每改一次跑一次测量，记一行。
3. **R-G1-A 落地后**再上 **R-G1-B**，然后把 **R-G1-C**（G1 的实现）接进来。
4. ⚠️ **黑场淡入是 `bn::bg_palettes::set_fade()` 整盘淡入**（`battle_black_field.h::apply()` 是空函数），
   **不是**逐槽写回 ⇒ 别去找「逐槽调色板写回」。

### 4.4 交付物

* `notes/s49-fidelity/W25-H2-entry-transition.md`：R-G1-A 的取证（帧数对照表）+ 三项改动的实现 + 测量
* `build/w25-h2` lane 里改好的代码 + 构建出的 ROM + 测量产物
* 25 帧固定偏移逐帧表（改前 vs 改后）+ 判定台读数

### 4.5 验收

* `step-12-A` 的战场区残差**必须下降**（基线 9,520 px）
* 25 帧固定偏移总残差**不得上升**（基线 **54,959 px**，见 §0.0 更正）
* 单测零新增红（119/20 或 118/20）
* 偏移不得漂移（基线恒为 +4）

---

## 5. H3 —— ⭐⭐ 『請準備...』窗接线（`W25-H3-prepare-box.md`）

### 5.1 目标

**把原版的『請準備...』窗 1:1 画出来**，使 `step-20-A`（判定台 #20，**3,881 px**）掉到 ≈ 809 px。

### 5.2 已知事实（wave 23 / F2 的实测结论）

* ⭐ **原版『請準備...』窗 = 96×32，位于屏幕 (72, 48)**，**7 色全在原版 PRAM bank 14**。
* F2 从原版 VRAM/PRAM **逐层分离**出了这扇窗的 1:1 资产 ⇒ 资产在 **`build/w23-f2/assets/`**。
  （⚠️ `build/w23-f2/butano-sequel/graphics` 是**指向共享树的符号链接**，不要在那里改资产；
  你的 lane `build/w25-h3` 的 `graphics/` 是**真实副本**，安全。）
* ⭐ F2 实测：**贴回原位 = 0 px**；贴到重制侧 = **3,881 → 809 px**。
* ⭐ **z-order 必须低于单位**：原版是**窗压住角色** —— 窗矩形内有 **689 px** 的 OBJ 不透明像素，
  而原版真值帧那一格**一格角色像素都没有**。
  （这**更正**了 wave 22 / D1「窗在角色后面」的说法。）
* 接线参照：`battle_runtime_scene.cpp:2376` 附近的 `_add_turn_banner()`（D1 加的回合横幅）。
* 条件：`phase == turn_banner && turn_banner_stage == prepare_box`（D1 已在
  `battle_scene_controller.h` 里加了 `battle_turn_banner_stage` 四段枚举；**那不是你的文件，不要改**）。

### 5.3 方法

1. 把 F2 的资产**拷进你的 lane**（`build/w25-h3/butano-sequel/graphics/`），改名/登记成 Butano 资源
   （Butano 为每个资产生成 `bn_regular_bg_items_*.h`；**没有聚合头**，要自己 include）。
   ⭐ **先核对 F2 资产的尺寸与格式**（96×32 ⇒ 4bpp 还是 8bpp？调色板表在哪？）
2. 在 `battle_runtime_scene.cpp` 里加 `_add_prepare_box()`，照 `_add_turn_banner()` 的写法：
   * 条件 = `phase == turn_banner && turn_banner_stage == prepare_box`（**其它三段不画**）
   * 位置 **(72, 48)**
   * ⭐ **z_order 低于单位**（窗压住角色）
3. **一次只改一处**：`battle_runtime_scene.cpp` 里只准动「prepare box」相关的新增代码，
   **不许**改 H2（入场背景）和 H4（overlay）要动的区段 ⇒ 父代理要用三方合并。
4. 构建 → 录制 → 两个仪器都测。

### 5.4 交付物

* `notes/s49-fidelity/W25-H3-prepare-box.md`
* lane 里改好的资产 + 代码 + ROM + 测量
* `step-20-A` 改前/改后残差（基线 3,881 px，目标 ≈ 809 px）

### 5.5 验收

* `step-20-A` 战场区残差**必须下降**
* 25 帧固定偏移总残差**不得上升**
* 单测零新增红
* 窗口**压住角色**（z_order 正确）—— 用逐像素验证，不要目测

---

## 6. H4 —— ⭐⭐ 4bpp L2：overlay 与调色板解耦（`W25-H4-4bpp-l2.md`）

### 6.1 目标

**让 `battle_range_overlay` 不再依赖「地图调色板顶端 32 个空闲槽的绝对索引 224..255」**，
从而让 4bpp 资产集可用（省 **93,516 B** ROM），并且**两张全屏 BG 能同时在场**（16 槽瓶颈）。

### 6.2 已知事实（wave 23 / F1 与 wave 24 / G2 的实测结论）

* ⭐ **原版本来就是 4bpp**（`BGxCNT` bit14 全 0 + 逐块 PRAM 回查 + 逆向线普查）。
* Butano 自己的 `bpp_4_auto` 量化器对这套资产**像素 0 变化**。
* 槽位：地图 5 槽 + 对白 2 槽 + 准备 1 槽 = **8 ≤ 16** ⇒ 两张全屏 BG 可同时在场。
* F1 的 4bpp 资产集在 `build/w23-f1/...`；⚠️ **G2 更正：F1 交的 `graphics-4bpp/` 只有 100 个文件，
  实际 4bpp 资产是 149 个**（多 49 个 `battle_XX_map_chunks.json` 清单）
  ⇒ 用 **`build/w24-g2/assets-4bpp-full/`**。
* G2 已修 **L1**（`battle_runtime_scene.cpp:2643` 图块 BPP 写死 `BPP_8` ⇒ 改为 `map_bg.palette().bpp()`），
  **8bpp 下 35/35 帧逐字节 no-op、25 帧 = 54,959 = 基线** ⇒ L1 可安全接线。
  （G2 的 lane 是 `build/w23-f1`，它的 L1 修法见 `notes/s49-fidelity/W24-G2-mask-palette-4bpp.md`。）
* ⭐ **L2 未修，是 4bpp 的真阻塞**：
  * `battle_runtime_scene.cpp:2822-2842`：`range_palette_first_color = 224`、`action_palette_first_color = 240`，
    断言 `colors.size() >= 256` ⇒ **4bpp 地图调色板只有 80 项 ⇒ 不存在 ⇒ 崩**
    （Butano 报错「Battle overlays require an 8BPP map palette」）。
  * `game/include/konoha/battle_range_ui_style.h:19-32`：索引**写死 225..235**。
  * 崩溃时刻 = `step-28` = 行动/指令选择层出现的那一刻（overlay 只在
    `action_selection`/`command_selection`/`move`/`target` 相位创建）。
  * G2 的修法设计（**你来实现**）：
    * **L2-a** `:2822-2823`：两个 first_color 从写死改成按 `palette.colors().size()` 现算
      （8bpp ⇒ 224/240，4bpp ⇒ 48/64），`_restore_action_palette` 同步；
    * **L2-b** `battle_range_ui_style.h:19-32` 的 225..235 与 `:3104-3113` 的行动面板索引一起重映射；
    * **L2-c** ⭐ `_prepare_tiles()`（`:3043`）的图块字节排布要按 bpp 分别排（4bpp = 32 B/块、2 B/像素）；
      ⚠️ **改前必须先对着 Butano 的图块布局核实**；
    * **L2-d** `_restore_action_palette()` 还原索引同 L2-a。

### 6.3 方法（**分两步交付，第一步才是本波的目标**）

* **第一步（必须做）**：把 overlay 改成**调色板大小无关**（L2-a / L2-b / L2-d）。
  ⇒ 目标：**8bpp 下 35 帧逐字节 no-op**（= 基线，零回归），**4bpp 下不再崩**（step-28 起能正常跑）。
* **第二步（尽量做）**：接入 4bpp 资产集（`build/w24-g2/assets-4bpp-full/` 的 149 个文件），
  做 **L2-c**（图块排布），目标 ROM 省 ≈ 93 KiB 且 25 帧残差不上升。
  ⇒ 若第二步做不完，**如实说明**，不要交半成品。

### 6.4 交付物

* `notes/s49-fidelity/W25-H4-4bpp-l2.md`
* lane 里改好的代码 + 资产 + ROM + 测量（8bpp no-op 证明 / 4bpp 不崩证明 / ROM 体积对比）
* 单测（`battle_range_ui_style` 的测试在 `game/tests/test_battle_range_ui_style.cpp`）

### 6.5 验收

* **8bpp 下 35 帧逐帧 sha256 与 8bpp 基线逐字节相同**（no-op 证明）
* 4bpp 下 **step-28 之后不再是 Butano 错误屏**
* 25 帧固定偏移残差**不得上升**
* 单测零新增红
* 改动只落在 `battle_runtime_scene.cpp` 的「overlay」区段与 `battle_range_ui_style.h`

---

## 7. 父代理收口清单（wave 25 结束后）

1. `python tools/s49_w25/merge_lanes.py --file game/src/battle_runtime_scene.cpp --lane w25-h2 --lane w25-h3 --lane w25-h4 --apply`
   （三方合并；冲突则手工裁决）
2. 把各 lane 的**独占文件**（非 `battle_runtime_scene.cpp`）按 `owned` 清单拷回共享树
3. G3 的 3 个結算资产（`battle_result_font.bmp` / `battle_ui_result_total_palette.bmp` / `battle_ui_result_plate.bmp`）
   拷回共享树（G3 已按字节还原过共享树，父代理在收口时统一拷）
4. 共享树重建 → `python tools/s49_package/run_pipeline.py --out build/s49-package-w25` ⇒ 12/12 全绿
5. 判定台 → 残差与 **38,047 px** 比（棘轮：只许变小）；同 ROM 才可比
6. 单测 119/20，零新增红
7. `docs/sequel-roadmap.md` 回填「七之十三」
8. `notes/s49-fidelity/W25-PARENT-wrapup.md` 写汇总 + 假设台账
9. 改结论的地方**回溯更正**旧笔记（F3/F1/D1 都被更正过，惯例要延续）

---

## 8. wave 26 备料清单（**收口时按实际进展删改**）

| # | 项 | 来源 | 性质 | 预估 |
|---|---|---|---|---|
| **W26-1** | ⭐⭐⭐ **『合計数累加动画』** —— 原版 719→1059 帧把 300/350/200 从 0 滚上去，重制侧**完全没有** | G3 §7.1 | 玩家可见（結算屏） | 中（要动 `battle_runtime_scene.cpp`） |
| **W26-2** | ⭐⭐ **场景 46 的「59」判别** —— 一次「结算瞬间的 EWRAM dump」同时判别 C-1/C-2/C-3：读 `0x020240C0` 起 13 槽的 `+0x00`（character id）/ `+0xC0` / `+0xCE`（carried） | G4 §1.2 | 取证（不改产品） | 中（要跑**原版** battle 9 到结算 ⇒ 长录制） |
| **W26-3** | ⭐⭐ **红箭头 24 px/6×6 款**（原版那 12 拍用，重制侧连画 9 拍 30 px/10×5）+ **SELECT 詳細 HUD 只在 `unit_selection` 画**（原版 1 拍，重制侧 5 拍） | F3 §2.2 | 玩家可见 | 中（要新增资产） |
| **W26-4** | ⭐ **蜜蜂轮转** + **存档写盘时机** —— 用户口径的「游戏逻辑状态」，**不在**判定台的 25 帧里 | 用户口径（wave 20 确认的排除项只有「音频逐采样」「存档逐字节」） | 逻辑 | 中–大 |
| **W26-5** | **旧对白资产清理**（33 stem / 66 文件 / **ROM 实占 264,768 B**）—— 安全脚本 `tools/s49_w24g4/cleanup_unused_dialogue_assets.py` 已备（VERIFY→BACKUP→DELETE→ROLLBACK，dry-run 通过） | G4 §1.4 | 体积 | 小（删完要重建 + 跑一次判定台确认零回归） |
| **W26-6** | ⭐⭐⭐ **H1 的开场段结论落地**（开场 12 帧 = 17,261 px = 45.4 %） | wave 25 / H1 | 玩家可见 | 看 H1 的结论 |
| **W26-7** | **4bpp L2-c**（图块按 bpp 排布）若 wave 25 / H4 没做完 | wave 24 / G2 §2.4 + wave 25 / H4 | 架构 | 中 |
| **W26-8** | **PRAM/VRAM 级机制取证**（原版結算屏的双色红怎么落到 PRAM） | G3 §7.2 | 取证 | 中 |

> **用户口径（不可改写）**：「完全一致」= **玩家看得见的画面 + 游戏逻辑状态**（不计寄存器）；
> **允许重录**。明确排除项只有：**音频逐采样一致**、**存档逐字节一致**。
> ⇒ 但**存档写盘时机**与**蜜蜂轮转**按玩家可见口径**要修**（W26-4）。
