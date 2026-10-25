# W21-C1 —— 相机摇镜复现（wave 21 / C1 流）

> 2026-10-25 21:2x 起 · 流：C1（相机摇镜）· 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> lane 副本：`D:\Github\gba-naruto\build\w20-e1\butano-sequel`
> 上游：`W20-EXEC-BRIEF.md` · `W20-E3-camera-mapping.md` · `W20-E3-camera-curve.md` · `W20-E1-camera.md`
> · `W20-PARENT-round2.md` §4 · C2 的 `build/w21-c2/press-phase-table.json` · C4 的 `build/w21-c4/c4-presentation-timing.patch`
> 产物：`tools/s49_w21c1/{capture_remake_walk,match_dense,telemetry_frames}.py`
> · `build/w20-e1/{align-before.json,align-after.json,align-after2.json,align-after3.json}`
> · `build/w20-e1/{dense-remake,dense-remake-after,dense-remake-after2,telemetry-remake,telemetry-remake-after,telemetry-remake-after2}/`
> · `build/w20-e1/camera-pan-r2.patch`（相机实现的完整补丁，**未接线**）

---

## 0. 状态（收口版）

> ⭐⭐⭐ **本流的结论是「负」的，但有三条可复用的硬结论**：
> ① ⭐⭐ **摇镜曲线的形状可以逐帧复现**（11 + 20 + 7，密集帧实测）；
> ② ⭐⭐ **E3 的曲线汇总表有两处错**（垂直总量 `+9` 应为 `+16`；相机符号反了）；
> ③ ⭐⭐⭐ **重制侧没有「相机落位」那个相位** ⇒ **摇镜无处可挂** ⇒ 直接挂到重制侧自己的相位上
> **必然摇歪一批本来对齐的帧**（实测：25 帧合计 148,914 → 186,279，**净回归 +37,365**）。
>
> ⇒ **本流的 lane 已回退到「共享树 + 调色板修法」的验收基线**（`battle_runtime_scene.cpp` 与共享树**逐字节相同**，
> sha `b01dcd08618688e3`）⇒ **父代理接线时不会误合回归**。
> ⭐ **回退已实测**：重新录 walk + 对拍 ⇒ **148,914 px / best_offset +4**，与基线**逐帧相同**
> （`build/w20-e1/align-reverted.json`）⇒ **lane 回到验收基线，可用可交**。
> ⇒ 相机实现完整保存在 **`build/w20-e1/camera-pan-r2.patch`（11,794 B / 6 hunk）**，**等过场补上后再挂**。

---

## 1. 一句话结论

> ⭐⭐⭐ **原版的相机摇镜可以在重制侧逐帧复现（曲线、形状、相位都能对上），**
> **但重制侧没有原版那个「相机落位」的过场相位，所以摇镜挂不上去** ——
> 硬挂到重制侧自己的相位上，会把一批本来逐像素对齐的帧摇歪（`step-23`：2,306 → 28,331 px）。
> ⇒ **必须先补过场（C4 的 R-C4-4），再挂摇镜**；本流已把两条实测结论和补丁交出去。

---

## 2. 验收判定表（逐帧 field px，战场区 0,0,240,128，偏移固定 +4）

| 原版帧 | 重制帧 | **改前（基线）** | 改后 v1（锚 41 + 渲染条件） | 改后 v2（锚 38 + 帧率修好） | 判定 |
|---|---|---:|---:|---:|---|
| `step-00-base` | `step-04-A` | 2,565 | 2,565 | 2,565 | 不变 ✔ |
| `step-01-A` | `step-05-A` | 1,294 | 1,294 | 1,294 | 不变 ✔ |
| `step-02-A` | `step-06-A` | 1,680 | 1,680 | 1,680 | 不变 ✔ |
| `step-03-A` | `step-07-A` | 2,514 | 2,514 | 2,514 | 不变 ✔ |
| `step-04-A` | `step-08-A` | 1,940 | 1,940 | 1,940 | 不变 ✔ |
| `step-05-A` | `step-09-A` | 2,057 | 2,057 | 2,057 | 不变 ✔ |
| `step-06-A` | `step-10-A` | 1,217 | 1,217 | 1,217 | 不变 ✔ |
| `step-07-A` | `step-11-A` | 1,921 | 1,921 | 1,921 | 不变 ✔ |
| `step-08-A` | `step-12-A` | 1,026 | 1,026 | 1,026 | 不变 ✔ |
| `step-09-A` | `step-13-A` | 759 | 759 | 759 | 不变 ✔ |
| `step-10-A` | `step-14-A` | 278 | 278 | 278 | 不变 ✔ |
| `step-11-A` | `step-15-A` | 1,212 | 1,212 | 1,212 | 不变 ✔ |
| **`step-12-A`** | `step-16-A` | **24,101** | 24,101 | 24,101 | 不变（流程分叉） |
| `step-13-A` | `step-17-A` | 195 | 195 | 195 | 不变 ✔ |
| `step-14-A` | `step-18-A` | 0 | 0 | 0 | 不变 ✔ |
| `step-15-A` | `step-19-A` | 0 | 0 | 0 | 不变 ✔ |
| `step-16-A` | `step-20-A` | 43 | 43 | 43 | 不变 ✔ |
| `step-17-A` | `step-21-A` | 0 | 0 | 0 | 不变 ✔ |
| `step-18-A` | `step-22-A` | 0 | 0 | 0 | 不变 ✔ |
| **`step-19-A`** | `step-23-A` | **24,460** | 24,460 | 24,460 | 不变（流程分叉，C2） |
| `step-20-A` | `step-24-A` | 4,835 | 4,835 | 4,835 | 不变 ✔ |
| **`step-21-A`** | `step-25-A` | **28,390** | 28,626 | **28,908** | ⛔ 目标未达成 |
| **`step-22-A`** | `step-26-A` | **27,946** | 28,728 | **28,791** | ⛔ 目标未达成 |
| **`step-23-A`** | `step-27-A` | **2,306** | 28,331 | **28,336** | ⛔ **回归 +26,030** |
| **`step-24-A`** | `step-28-A` | **18,175** | 28,497 | **28,599** | ⛔ **回归 +10,424** |
| **合计** | | **148,914** | **175,343** | **186,279** | ⛔ **净回归 +37,365** |

> ⚠️ **口径**：全部绑在**同一个原版采集**（`build/s49-package-w18/work/s49-report/capture-original`）上，
> 重制侧是**本 lane 自己的 ROM**（`build/w20-e1/butano-sequel/butano-sequel.gba`）。
> 基线 148,914 px 与 E3 的 `align-e3.json` **逐帧相同** ⇒ 基线可信。

### 2.1 回归模式说明什么（⭐ 最值钱的诊断）

* `step-21`/`step-22`（本来就差 ~28 k）**几乎没变**（+236 / +782）
  ⇒ **摇镜对那两帧基本没起作用**（相机偏移没有落在那两帧上）。
* 而 `step-23`（**本来只有 2,306 px = 几乎完全对齐**）**炸到 28,336**
  ⇒ **摇镜被加到了「原版本来不摇」的帧上**。

⇒ ⭐⭐⭐ **结论：重制侧根本没有原版那个「相机落位」的过场相位。**
原版的过场是 `回合横幅 →『請準備...』→ 相机落位 → unit_selection`（**原版多消耗 2–3 次 A**），
摇镜属于**「相机落位」那一拍**；重制侧从横幅直接进 `unit_selection`
⇒ **重制侧没有可以挂摇镜的相位** ⇒ 硬挂 ⇒ 摇歪一批本来对齐的帧。
⇒ ⇒ **必须先补过场（C4 的 R-C4-4），摇镜才有地方挂**（与 C4 的结论完全吻合）。

---

## 3. 第 1 步：⭐⭐ 相位锚点的实测

### 3.1 仪器

| 工具 | 作用 |
|---|---|
| `tools/s49_w21c1/capture_remake_walk.py` | 用**私建探针**（`build/mgba-probe-w20e1/mgba-probe.exe`）录重制侧 walk（35 帧） |
| `tools/s49_w21c1/match_dense.py` | 把 walk 截图与密集窗口的每一帧对拍，找**逐字节相同**的那一帧 |
| `tools/s49_w21c1/telemetry_frames.py` | 密集回放里**逐帧 dump 遥测**（相位/光标/移动动画/帧率） |
| `tools/s49_w20e/dense_camera_curve.py`（E3，**只读复用**） | 密集采集（capture/analyze） |

### 3.2 ⭐ 实测：两侧的 walk 截图都逐字节命中 `f043`

| 侧 | 起点存档态 | walk 截图落在密集帧 | 证据 |
|---|---|---|---|
| 原版 | `capture-original/step-20-A.ss9` | **f043** | `build/w20-e1/dense-match-orig-step21.json`：**0 px** |
| 重制侧 | `capture-remake-before/step-24-A.ss9` | **f043** | `build/w20-e1/dense-match-remake-step25.json`：**0 px** |

⇒ ✅ **相位锚点 = `f043`**（两侧都成立、逐字节验证）。
⇒ ⭐ ⇒ 原版的摇镜在 `f038→f049`（11 帧）起，walk 截图 = **第 5 个增量** = 净 **(−40,+7)**。

> ⚠️ **但这条对「重制侧」只说明「画面内容落在同一帧」**：
> 重制侧那一段画面本来是静止的 ⇒ 0 px 命中**不能**证明重制侧也有那次「相机落位」。
> ⇒ **这正是回归的根源**（见 §2.1）。

### 3.3 重制侧的相位时间线（逐帧遥测）

* 遥测结构在 EWRAM `0x0202A56C`（按 magic `0x4B42544C` 定位）。
* `step-24-A.ss9` 之后按 A：**f001 起相位就是 `command_selection`**；
  `map_movement_active` **恒为 0**、`cursor=(11,6)` **全程不动**
  ⇒ 重制侧**既没有跑步动画、也没有镜头移动**。
* 重制侧相位链（C2 的表 + 本流复核）：
  `turn_banner(22/23) → unit_selection(24) → command_selection(25) → move_selection(26) → command_selection(27) → action_selection(28) → target_selection(29…)`
  ⇒ **没有「請準備...」框、没有「相机落位」相位**。

---

## 4. ⭐⭐ 曲线的两处更正（E3 的汇总表有错）

### 4.1 垂直总量是 **+16**，不是 +9

E3 的 `original-camera-curve.json` 的 `runs` 给出 11 个增量：

```
f038→f039 (−8,+1)  f039→f040 (−8,+1)  f040→f041 (−8,+2)  f041→f042 (−8,+1)
f042→f043 (−8,+2)  f043→f044 (−8,+1)  f044→f045 (−8,+2)  f045→f046 (−8,+1)
f046→f047 (−8,+2)  f047→f048 (−8,+1)  f048→f049 (−8,+2)
```

* 前 5 个增量和 = **(−40, +7)** ⇒ 与原版「step-20→21 净位移 (−40,+7)」**完全一致** ✔
* 11 个增量总和 = **(−88, +16)**（1,1,2,1,2,1,2,1,2,1,2，和为 16）
  ⇒ E3 汇总表里的「(−88,+9)」**是错的**（+9 不可能是 11 个 {1,2} 之和）。
* ease-back 7 步 (+8,+6,+6,+5,+3,+2,+2) = **+32, 0** ⇒ 整段净 **(−56, +16)**
  ⇒ 与原版「step-20→22 净位移 (−56,+16)」**完全一致** ✔（= (−40,+7) + (−16,+9)）。

**累积垂直值** = 1,2,4,5,7,8,10,11,13,14,16 ⇒ 整数斜坡 `16 * step / 11` **逐项相等**
⇒ 实现只要 `out_pixels_y = 16` + 斜坡（E1 旧补丁写的是 `9` ⇒ 错）。

### 4.2 ⭐ 符号：E3 的 `dx` 是**画面内容**的位移，相机要**反号**

* `overlap_residual()` 的 `best_dx` = 「后一帧的内容相对前一帧的位移」。
  原版 `step-20→21` = **(−40,+7)** ⇒ **内容向左 40、向下 7**。
* 重制侧 `screen_x = world_x − camera_x` ⇒ 相机**右移**才会让内容**左移**
  ⇒ 摇镜期间重制侧的相机必须 **+8/帧（向右）**、**−(1..2)/帧（向上）**。
* E1 的旧补丁把 **−8 加到相机上** ⇒ **两个符号都反** ⇒ 照抄会更差。

---

## 5. 改动（lane 副本）

### 5.1 ⭐ 相机摇镜实现（**已回退，补丁保留**）

补丁：**`build/w20-e1/camera-pan-r2.patch`（11,794 B / 6 hunk）**，全部在 `battle_runtime_scene.cpp`：

| 位置 | 改什么 |
|---|---|
| `world_x` 之前 | 新增 `class battle_camera_pan`（常量全部取自 E3 的 JSON，未自创曲线） |
| `camera_x` / `camera_y` | 加 `pixel_offset_x/y` 参数，**在 clamp 之后叠加** |
| 场景成员 | 加 `battle_camera_pan camera_pan;` |
| 相位更新处 | `unit_selection → command_selection` ⇒ `begin()`；`move_selection → command_selection` ⇒ `begin_return()`；每帧 `advance()` |
| 渲染处 | ⭐ **相机 + 背景流的更新提到「有变化才重画」的条件块之外**（每帧都执行） |

### 5.2 ⭐⭐⭐ 工程教训：**不要把「每帧都要动的帧」加进「有变化才重画」的判定**

第一版把 `camera_pan.busy()` 加进了该判定（`battle_runtime_scene.cpp:9582`）。**实测后果**：

| 遥测 | 改前（旧 ROM） | 改后（第一版） |
|---|---|---|
| `scene_frame` 步进 | 356, 357, 358…（**每帧 +1**） | 355, 356, **356**, 357, **357**…（**每 2 帧 +1**） |
| 摇镜第一次动的帧 | （无摇镜） | **f083**（比应到的 f038 晚 45 帧） |
| 25 帧 field px 合计 | 148,914 | **175,343**（+26,429） |

**根因**：那个判定块里会**重传格线覆盖层 + 文字精灵**；每帧都跑 ⇒ 一帧的活干不完
⇒ **场景的 `scene_frame` 变成每 2 个 GBA 帧才 +1** ⇒ 整条摇镜曲线（和整个场景）都慢了 2 倍。
**修法**：相机与背景流的更新**提到条件块之外**（相机移动很便宜）；条件块里只留格线/文字的重画。

### 5.3 ⭐ 重制侧逐帧实测出的摇镜曲线（**形状 100 % 复现**）

`build/w20-e1/dense-remake-after2/` 与改前的密集窗口逐帧对拍：

| 密集帧 | 与前一帧的差 | 判读 |
|---|---:|---|
| f000–f041 | 0（与改前**逐像素相同**） | 相机未动 ✔ |
| **f042** | **22,284** | ⭐ 摇镜第 1 个增量（锚 41 时） |
| f042–f052 | 每帧 ~19–22 k | ⭐ **左摇 11 帧**（与原版一致） |
| f053–f072 | 0 | ⭐ **停顿 20 帧**（一致） |
| f073–f079 | 每帧 ~16–19 k | ⭐ **ease-back 7 帧**（一致） |
| f080–f090 | 0（整体比改前多 24 k） | 摇镜结束，停在净偏移 (+56,−16) |

⇒ ⭐⭐ **曲线形状逐帧复现**（11 + 20 + 7）；锚点常量 41 → 38 可把第 1 个增量推到 f039（原版位置）。

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| C1-H1 | ⭐ 相位锚点可由「两侧 walk 截图在密集窗口里的同一帧号」定出 | `match_dense.py` 两侧逐字节对拍 | **成立**：两侧都落在 **f043**（0 px） | **已确认** |
| C1-H2 | ⭐ 原版摇镜的垂直总量是 +9（E3 汇总表） | 从 `original-camera-curve.json` 的 `runs` 逐项求和 | ⛔ **不成立**：11 个 {1,2} 之和 = **+16** | **已证伪** |
| C1-H3 | ⭐ E1 旧补丁的符号（相机 −8）正确 | 由 `overlap_residual` 的定义反推 `dx` 的含义 | ⛔ **不成立**：`dx` 是**内容**位移；相机要 **+8** | **已证伪** |
| C1-H4 | ⭐ 摇镜后相机的偏移是**瞬态**（会回零） | 原版 `step-22→23` 是整屏切换、`step-23→24` 是 (0,0)；跨侧 `step-23↔step-27` 最佳位移 **(0,0)** | **成立** | **已确认** |
| C1-H5 | 重制侧的摇镜锚点可用重制侧自己的相位跃迁表达 | 遥测逐帧 | **成立**（`unit_selection→command_selection`、`move_selection→command_selection` 各一次） | **已确认** |
| C1-H6 | ⭐⭐ 把摇镜帧加进「有变化才重画」的判定是安全的 | 遥测 `scene_frame` 步进 + 密集窗口首动帧 | ⛔ **不成立**：**帧率减半**，曲线错位 45 帧，合计 +26,429 | **已证伪**（已修） |
| C1-H7 | ⭐ 原版 walk 截图 = 密集帧 f043（= 存档态 + 47 帧） | 原版 `step-21-A.png` 与 `dense/step-20-to-21/f043.png` **0 px** | **成立** | **已确认** |
| C1-H8 | ⭐⭐ 摇镜可以挂在**重制侧自己的相位**上 | 改后 25 帧逐帧对拍 | ⛔ **不成立**：净回归 +37,365；`step-23` 从 2,306 → 28,336 ⇒ **摇镜落在原版不摇的帧上** ⇒ **重制侧没有「相机落位」相位** | **已证伪** |

---

## 7. 未完成项 / 接线请求

| # | 项 | 状态 |
|---|---|---|
| N-C1-1 | 相机摇镜实现 | ⭐ **代码已完成并逐帧验证曲线形状**（`build/w20-e1/camera-pan-r2.patch`），⛔ **未接线**（回归，见 §2.1）⇒ **等过场补上后再挂** |
| N-C1-2 | ⭐⭐ **补过场（C4 的 R-C4-4）**：`回合横幅 →『請準備...』框 → 相机落位 → unit_selection`，让重制侧**多消耗 2–3 次 A** | **本流做不了** ⛔ —— 见 §7.1 的阻塞说明 |
| N-C1-3 | 「CANNOT SELECT」的定位 | **已定位**（见 §8） |
| N-C1-4 | 移动格线 / 红箭头 / 「SELECT 详细」HUD 的绘制时机 | 未做（C4 已给出 R-C4-1/2/3 的改法与实测表） |
| N-C1-5 | 相机归零（return）的触发点 | 未解决（原版的相机在 `step-22→23` 之间回地图焦点；重制侧需要更晚的触发点） |

### 7.1 ⛔ 为什么「补过场」本流做不了（给父代理的精确阻塞说明）

* 原版的过场需要**新的相位**（`prepare_box` / `deployment_unit`），
  而 **`enum class battle_scene_phase` 定义在 `game/include/konoha/battle_scene_controller.h:26`**
  ⇒ **不在 C1 的独占文件里** ⇒ 本流**无权**加相位。
* 其余部分（「請準備...」那个蓝边圆角文字窗、让控制器多走 2–3 次 A、
  以及 C4 的 `battle_presentation_moment` 接线）分别在
  `battle_scene_controller.h`（控制流）、`battle_scene_presentation.h`（C4 独占）、
  `battle_runtime_scene.cpp`（C1 独占）⇒ **至少跨 3 个流**。
* ⇒ **建议父代理**：把「补过场」单独开成一路（或由 C4 领衔），C1 提供
  **`camera-pan-r2.patch` + §4 的曲线常量 + §5.3 的逐帧实测**，作为挂载点。

---

## 8. 「CANNOT SELECT」的定位（父代理点名）

**一句话**：**A 键在 `target_selection` 相位走 `controller.confirm()`，
而 `confirm()` 先做 `preview_target(_cursor)`；光标还停在单位自己那一格（遥测：cursor=(11,6) 全程不动），
预览判定不合法 ⇒ 返回 `invalid_target` ⇒ 画面打出「CANNOT SELECT」。**

代码链（行号按本 lane 的 `battle_runtime_scene.cpp` / `battle_scene_controller.h`）：

| 位置 | 内容 |
|---|---|
| `game/src/battle_runtime_scene.cpp:9147-9159` | 战斗相位的 A 键 ⇒ `result = controller.confirm();` |
| `game/src/battle_runtime_scene.cpp:9202-9209` + `:9085` | `result.success()` 为假 ⇒ `rejection.update(handled, false)` ⇒ 画面出 **「CANNOT SELECT」**（`:4789`） |
| `game/include/konoha/battle_scene_controller.h:875-890` | `confirm()` 的 `target_selection` 分支 ⇒ `_runtime.preview_target(_cursor)`；失败 ⇒ `_player_result(preview)` |
| `game/include/konoha/battle_player_action_flow.h:1130-1160` | `preview_target()` ⇒ `! target_preview.legal()` ⇒ 错误 `invalid_target` |

**判读**：本 walk 的按键序列是 `Down,Down,A×32` —— **在 `target_selection` 相位里一次方向键都没按**；
遥测显示 `cursor=(11,6)` 全程不动 ⇒ **「CANNOT SELECT」更像「本 walk 的按键方式」而不是产品缺陷**
（原版的 A-only walk 能过 ⇒ 原版要么自动选目标、要么光标初始就落在合法目标上）。
⇒ **给父代理的判定建议**：先在**真实链**里补上方向键再验证；仍失败才是产品缺陷。
⚠️ 本条是**代码路径追踪 + 遥测读数**的推断，**没有做「带方向键的实跑」验证**。

---

## 9. 复现命令

```powershell
# 1) 录重制侧 walk（35 帧）
python tools/s49_w21c1/capture_remake_walk.py \
  --rom build/w20-e1/butano-sequel/butano-sequel.gba \
  --exe build/mgba-probe-w20e1/mgba-probe.exe \
  --out-dir build/w20-e1/capture-remake-before

# 2) 25 帧逐帧 field px（偏移 +4）
python tools/s49_wave18/align_capture_steps.py \
  --original build/s49-package-w18/work/s49-report/capture-original \
  --remake   build/w20-e1/capture-remake-before \
  --out      build/w20-e1/align-before.json

# 3) 密集窗口（相位锚点 + 摇镜曲线逐帧）
python tools/s49_w20e/dense_camera_curve.py capture \
  --state build/w20-e1/capture-remake-before/step-24-A.ss9 \
  --rom   build/w20-e1/butano-sequel/butano-sequel.gba \
  --exe   build/mgba-probe-w20e1/mgba-probe.exe \
  --out-dir build/w20-e1/dense-remake/step-24-to-25
python tools/s49_w21c1/match_dense.py \
  --dense  build/w20-e1/dense-remake/step-24-to-25 \
  --target build/w20-e1/capture-remake-before/step-25-A.png \
  --out    build/w20-e1/dense-match-remake-step25.json

# 4) 逐帧遥测（相位时间线 + 帧率）
python tools/s49_w21c1/telemetry_frames.py \
  --rom build/w20-e1/butano-sequel/butano-sequel.gba \
  --state build/w20-e1/capture-remake-before/step-24-A.ss9 \
  --exe build/mgba-probe-w20e1/mgba-probe.exe \
  --out-dir build/w20-e1/telemetry-remake/step-24-to-25 \
  --out build/w20-e1/telemetry-remake/step-24-to-25.json
```
