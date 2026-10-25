# W20-E1 —— 相机摇镜（任务 A）+ 重制侧多画的 3 样东西（任务 B）

> 2026-10-25 20:57 起 · 流：E1 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> lane 副本：`D:\Github\gba-naruto\build\w20-e1\butano-sequel`（**唯一改动地**）
> 共享树：**未改**（父代理整体重接）
> 上游：`notes/s49-fidelity/W20-E1-palette-blackfade.md`（任务 1/2/3）·
> `build/w20-e3/original-camera-curve.json`（E3 的相机曲线）· `build/w20-e3/dense/`（E3 的逐帧图）

---

## 0. 状态

> ⭐ **任务 A 的根因已定位，且我从 E3 的逐帧图里读出了「相机摇镜的语义锚点」**（这一条改写了
> 「相机跟单位」的假设）⇒ **改法定型，补丁已写好**（`build/w20-e1/camera-pan-r1.patch`），
> 但**相位锚点还没验证** ⇒ 本轮**没有**把未验证的相机改动接进 lane 的产品文件。
> 任务 B / C 未做。

## 1. 一句话结论

> ⭐⭐ **原版的相机不是「跟着单位跑」，而是一段「脚本化的摇镜」**：
> **11 帧 × 8 px/帧左摇（−88 px）→ 停 20 帧（移动格线在场）→ 7 帧 ease-back 右摇（+32 px）**。
> **摇镜的锚点 = 移动格线出现/消失的时刻，不是单位的跑步动画**（读 E3 的逐帧图得到，见 §3.1）。
> ⇒ 重制侧要复现的是「**格点 + 逐帧像素位移**」，且**必须复现相位**
> （walk 的 `step-21-A` 截图落在左摇的第 6 帧上）。
> ⇒ 补丁已写好（`build/w20-e1/camera-pan-r1.patch`）：**改完能编过，但相位锚点需要先量出
> 重制侧的逐帧曲线**（§3.4 的三步），否则 `step-21` 那一帧对不上。

## 2. 验收判定

| # | 判据 | 结果 | 状态 |
|---|---|---|---|
| A | `step-21` / `step-22` 的 field px 从 ~28 k 降到 ~6 k 量级 | **补丁已写好，未实测**（相位锚点未验证） | ❌ 未验 |
| A' | 另外 20 帧没有变差 | 未实测 | ❌ 未验 |
| B | 重制侧多画的 3 样东西 | 未做（§4） | ❌ 未验 |
| C | 黑场 B2/B3/B4 + 淡入 28→24 | 未做（`W20-E1-palette-blackfade.md` §5） | ❌ 未验 |

---

## 3. 任务 A：相机（**根因 + 改法定型 + 补丁；未实测**）

### 3.1 ⭐⭐ 我读 E3 的逐帧图得到的**语义锚点**（新增，关键）

E3 的逐帧图 `build/w20-e3/dense/step-20-to-21/`（91 帧）我拼了一张接触表
（`build/w20-e1/dense-pan-sheet.png`，取帧 36/39/42/43/45/48/49/52/60/69/71/74/76/80/86/90），逐段读出来：

| 帧段 | 画面 | 相机 |
|---|---|---|
| f036 | **「開始 預備...」消息框**在场，无格线 | 静止 |
| f038 → f049 | 消息框消失 | **左摇 −88,+9（11 帧 × 8 px）** |
| f049 → f069 | **移动格线**（青/黄/橙的格子）在场 | 静止 |
| f069 → f076 | 格线消失 | **ease-back +32,0（7 帧）** |
| f080 → f090 | **单位在跑** | 静止 |

⇒ ⭐ **摇镜发生在「消息框关闭 → 格线出现」之间，ease-back 发生在「格线消失」的那一刻，
而单位的跑步动画在更后面。**
⇒ **「相机跟单位跑」的假设不成立** ⇒ 重制侧不能把像素位移挂在 `map_movement`（跑步动画）上，
必须挂在**格线（range overlay）出现/消失**这个相位上。
⇒ 这同时解释了任务 B：**重制侧的格线画得比原版早** ⇒ 摇镜的锚点也就对不上。

### 3.2 重制侧相机为什么不动（代码链）

| 位置 | 现状 |
|---|---|
| `battle_runtime_scene.cpp:8914` | `camera_focus = presentation_event.origin;`（焦点是**格子点**） |
| `battle_runtime_scene.cpp:9431-9434` | `camera.set_x(camera_x(camera_focus, config)); camera.set_y(...)` |
| `battle_runtime_scene.cpp:1089-1107` | `camera_x/camera_y` → `clamp_camera(world_x(point), ...)` |
| `battle_runtime_scene.cpp:1052-1062` | `world_x/world_y` = `point.x*32+16−map_center_x` / `point.y*16+8−map_center_y` ⇒ **只能取格子中心** |
| `battle_runtime_scene.cpp:9444` | `if(! map_movement.busy()) { update_range_overlay(...); }` ⇒ **格线在移动动画期间不画** |

* 移动期间光标格不变 ⇒ 相机不动（实测：重制侧那两步的相机位移 = **(0,0)**）。
* 原版跟的是**脚本化的摇镜**（§3.1）⇒ 那 28 k px 全部来自「重制侧根本没有摇镜」。

### 3.3 ⭐ 补丁（**已写好，未接线**）

`build/w20-e1/camera-pan-r1.patch`（6,657 B，4 个 hunk，**全部在 `battle_runtime_scene.cpp`**）：

| hunk | 位置 | 改什么 |
|---|---|---|
| 1 | `:1049` 之后 | 新增 `class battle_camera_pan`：`out_frames=11 / hold_frames=20 / back_frames=7`、`out_step=8`、`back_steps={8,6,6,5,3,2,2}`、`out_pixels_y=9`；`offset_x()/offset_y()` 给出逐帧偏移 |
| 2 | `:1052-1062` | `world_x/world_y` 加 `pixel_offset_x/y` 参数（**放开 32/16 px 量化**） |
| 3 | `:1089-1107` | `camera_x/camera_y` 加 `pixel_offset_x/y` 参数，**在 clamp 之后叠加**（原版的相机确实会超出落点 88 px） |
| 4 | `:8438` / `:8886` / `:9431` | 加 `battle_camera_pan camera_pan;` 成员、`advance()`、锚点 `begin()`，以及相机调用点叠加偏移 |

**设计要点**：
* 摇镜是**原始滚动偏移**（在 clamp 之后叠加），这样才能复现「先超出 88 px 再回来」。
* 曲线常量全部来自 E3 的 `build/w20-e3/original-camera-curve.json`，**没有自己发明曲线**。
* 偏移在**摇镜不活跃时恒为 0** ⇒ **摇镜窗口之外的每一帧逐字节不变**
  （这是「20 帧不许变差」的结构性保证）。

### 3.4 ⚠️ 唯一剩下的未知：**相位锚点**

补丁里锚点写的是「**移动格线出现的时刻**」（对应 `battle_scene_phase::move_selection` 首次进入），
并留了一个 `battle_camera_pan_anchor_delay` 常量待调。**这个锚点必须实测**：

```powershell
# 1) 量出重制侧自己的逐帧相机曲线（E3 的工具，capture + analyze 两段）
python tools/s49_w20e/dense_camera_curve.py --help
#    → 对 build/w20-e1/butano-sequel/butano-sequel.gba 跑

# 2) 对比重制侧的「格线出现帧」与原版的「摇镜起始帧 38」
#    原版：摇镜起于 f038，walk 截图落在 f043（左摇第 6 帧，净 (−40,+7)）
#    重制侧：必须让截图落在自己的摇镜的第 6 帧上 ⇒ 调 battle_camera_pan_anchor_delay

# 3) 整条 walk 对拍（判定台）
python tools/s49_fidelity_report.py --out build/w20-e1/report-fix1.json \
  --butano-root build/w20-e1/butano-sequel \
  --remake-rom build/w20-e1/butano-sequel/butano-sequel.gba
python tools/s49_w20e/shift_probe.py \
  --original build/s49-package-w18/work/s49-report/capture-original \
  --remake  build/w20-e1/capture-remake-fix1 \
  --offset 4 --radius 32 --out build/w20-e1/shift-fix1.json
```

**判据**：
* `step-21-A`（↔ 重制 `step-25-A`）与 `step-22-A`（↔ 重制 `step-26-A`）的 field px **≤ ~8 k**
  （当前 28,390 / 27,946）；
* **另外 20 帧的 field px 不得上升**（当前 25 帧合计 **148,914 px**，best_offset=4）；
* 重制侧的 `camera_delta` 必须在 `step-24→25` 给出 **(−40,+7)**、`step-25→26` 给出 **(−16,+9)**。

### 3.5 为什么本轮没有把补丁接进 lane 的产品文件

* **相位锚点没验证** ⇒ 摇镜会整体错位 ⇒ `step-21`/`step-22` 可能反而变差；
  虽然偏移在摇镜窗口外恒为 0（结构上不影响别的帧的**内容**），但**帧的对应关系**会变
  （重制侧的画面会整体位移）⇒ 有把 20 帧弄坏的风险。
* 父代理的验收是「**三者同时成立**」；**未经实测的相机改动 = 不达标**。
* ⇒ **本轮交付「根因 + 语义锚点 + 完整补丁 + 判定步骤」，不交未经实测的改动。**
  补丁文件独立存在，lane 的产品文件仍只有已验证的调色板两处改动 ⇒ **父代理重接是安全的**。

---

## 4. 任务 B：重制侧多画的 3 样东西（格线 / 红色指示箭头 / 「SELECT 详细」HUD）

* **未做**，但 §3.1 的逐帧读图已经把**移动格线**的时机钉死了：
  * 原版：格线在 **f049…f069**（摇镜结束时出现，格线消失时 ease-back 开始）；
  * 重制侧：`battle_runtime_scene.cpp:9444` 的 `if(! map_movement.busy())`
    ⇒ 格线在**移动动画期间不画**，且格线的出现相位与原版不同。
  ⇒ **格线的绘制时刻要改到「摇镜结束」那一刻** ⇒ 与相机锚点是**同一个相位** ⇒ 一起改。
* **红色指示箭头**：`battle_facing_indicator_graphics_index`
  （`battle_presentation_projection.h:77-91`）在移动相位被画；原版 `step-21/22` 没有
  ⇒ 让它**只在确认目的地之后**画。⚠️ 原版到底哪个相位才有，**E3 尚未取证**
  ⇒ 需要 E3 先取证（该文件也是 E3 的独占文件）。
* **「SELECT 详细」HUD**：UI 层分派，`battle_runtime_scene.cpp` 内可改。

---

## 5. 任务 C：黑场（未做）

根因、修法、判定方法见 `notes/s49-fidelity/W20-E1-palette-blackfade.md` §5（N-1/N-2/N-3/N-4）。

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| P-60 | lane 副本仍含 wave20-E1 的调色板修法 + 本流的結算底板修法 | lane vs 共享树全树 sha256 | 304 相同 / 1 不同（`battle_runtime_scene.cpp`）/ 0 lane-only | **已确认** |
| P-61 | 父代理转述的「原版相机 (−40,+7)/(−16,+9)」可在本地复现 | `camera_delta.py --mode consecutive`（原版侧） | 复现：两条都在原版侧，结构分 0.6548 / 0.8061 | **已确认** |
| P-62 | **重制侧那两步的相机位移是 (0,0)（相机冻结）** | 同上（重制侧，offset 4） | 成立：`step-24→25` 与 `step-25→26` 均为 (0,0) | **已确认** |
| P-63 | 父代理猜的「重制侧相机只由格子坐标算出 ⇒ 量化 32/16 px」是那 28 k px 的根因 | 对比两侧同一步的位移 | ❌ **证伪（部分）**：重制侧那两步是 **0,0**，不是「量化后跳 (−64,+16)」；真正的差别是**相机在移动期间根本不动** | **已证伪（部分修正）** |
| P-64 | 原版的相机**跟着单位的跑步动画**走 | 读 E3 的逐帧图 `dense/step-20-to-21/`（接触表 `build/w20-e1/dense-pan-sheet.png`） | ❌ **证伪**：摇镜在 **f038→f049**（消息框关闭时），格线在 f049→f069，ease-back 在 f069→f076，**单位 f080 才开始跑** ⇒ 摇镜与跑步动画**不同步** | **已证伪** |
| P-65 | 原版的摇镜锚点是**移动格线的出现/消失** | 同上（逐帧读图） | 成立：摇镜结束（f049）＝格线出现；格线消失（f069）＝ease-back 开始 | **已确认** |
| P-66 | 摇镜的曲线常量可直接取自 E3 的 JSON | `build/w20-e3/original-camera-curve.json` 的 `dense_points` | 成立：11 帧 (−8,+1/+2)、停 20 帧、7 帧 (8,6,6,5,3,2,2) | **已确认** |
| P-67 | 未经相位验证的相机改动可以安全接线 | — | ❌ **不成立**：相位错位会整体移动画面，可能破坏 20 帧已 0 px 的画面 | **已证伪** |
| P-68 | 重制侧的「逐帧像素位移」可以直接挂在 `map_movement`（跑步动画）上 | 同 P-64 | ❌ **证伪**：锚点是格线相位，不是跑步动画 | **已证伪** |

---

## 7. 收据

| 收据 | 路径 |
|---|---|
| ⭐ **相机摇镜补丁（本流写）** | `build/w20-e1/camera-pan-r1.patch`（6,657 B，4 hunk） |
| ⭐ **原版逐帧图接触表（本流拼）** | `build/w20-e1/dense-pan-sheet.png`（16 帧：36/39/42/43/45/48/49/52/60/69/71/74/76/80/86/90） |
| 原版逐帧图（E3 录） | `build/w20-e3/dense/step-20-to-21/`（91 帧） |
| 相机逐帧曲线（E3 出） | `build/w20-e3/original-camera-curve.json` |
| 相机连续位移（E3 出 / 本流交叉核对） | `build/w20-e3/camera-delta-consecutive.json` |
| 跨侧最佳平移 | `build/w20-e3/shift-probe.json` / `shift-probe-wide.json` / `camera-delta-cross.json` |
| 对齐表（25 帧 field px） | `build/w20-e3/align-e3.json`（best_offset 4，total **148,914 px**） |

---

## 8. 未完成项 / 接线请求

| # | 项 | 状态 | 接线请求 |
|---|---|---|---|
| N-7 | 相机摇镜（任务 A） | **根因 + 语义锚点 + 完整补丁；未实测** | **R-E3-7**：`battle_runtime_scene.cpp` —— 补丁 `build/w20-e1/camera-pan-r1.patch`（4 hunk，全在本文件）。⚠️ **接线前必须先定相位锚点**（§3.4 的三步） |
| N-8 | 重制侧多画的 3 样东西（任务 B） | 未做 | **移动格线**在 `battle_runtime_scene.cpp`（`:9444` 的 `! map_movement.busy()` 门）——**与 N-7 是同一个相位，一起改**；**红箭头**在 `battle_map_visual_projection.h` / `battle_presentation_projection.h`（**E3 独占**）——需父代理转交 E3，且**原版的相位 E3 还没取证**；**SELECT HUD** 在本流可改 |
| N-9 | 黑场 B2/B3/B4 + 淡入 28→24（任务 C） | 未做 | 见 `W20-E1-palette-blackfade.md` §5 |

**本流本轮（相机任务）没有改动 lane 里的任何产品文件** ⇒
lane 仍是「共享树 + 调色板修法 + 結算底板修法」，父代理重接时**只需重接 `battle_runtime_scene.cpp` 的那两处**。
