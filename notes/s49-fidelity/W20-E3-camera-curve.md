# W20-E3 —— 原版移动相位的**逐帧**相机位移曲线

> 2026-10-25 · wave 20 / E3 流（第二轮）· 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/W20-E3-camera-mapping.md`（本流第一轮）
> 产物：`build/w20-e3/original-camera-curve.json`（机器可读曲线）
>      `build/w20-e3/dense/{step-19-to-20,step-20-to-21,step-21-to-22}/`（逐帧 PNG，91 帧/窗口）
>      `tools/s49_w20e/dense_camera_curve.py`（采集 + 分析）

---

## 0. 一句话结论

> ⭐⭐⭐ **原版的相机在移动相位里不是「平滑滚动」，而是「一段 8 px/帧的快速左摇（11 帧，−88 px）＋ 停顿 ＋ 一段 ease-back 右摇（7 帧，+32 px）」。**
> ⭐⭐ **而且 walk 的 `step-21-A` 截图恰好落在这段快速左摇的**中间**（第 43 帧 / 摇镜第 6 帧）**
> ⇒ **原版在截图那一刻相机还在动** ⇒ E1 要复现的不是「净值」也不是「终点」，而是**这条曲线 + 它的相位**。
> ⭐ **这条曲线的逐步增量可机读**：`build/w20-e3/original-camera-curve.json`（schema `konoha.s49-original-camera-curve.v1`）。

---

## 1. 采集方法（可复现）

| 项 | 值 |
|---|---|
| 原版 ROM | `D:\Shell\Github\gba-naruto-butano\rom\base.gba` |
| 起点 | walk 的存档态 `capture-original/step-20-A.ss9`（**1 帧比 walk 的截图早**） |
| 输入 | 与原版 lua 脚本同参：**A 按住 4 帧** → **静置 90 帧**（`HOLD_FRAMES=4`、`SETTLE_FRAMES=90`） |
| 逐帧 | 探针 `shot`（`mCoreTakeScreenshotVF`，不推进帧）⇒ 每帧一张 PNG |
| 探针 | `build/mgba-probe-w20e3/mgba-probe.exe`（自建） |
| 分析 | 相邻两帧在战场区 (240×128) 上搜整数平移（半径 12），目标 = 差异像素数 |

```powershell
python tools/s49_w20e/dense_camera_curve.py capture --state <walk>/step-20-A.ss9 --rom <base.gba> --exe build/mgba-probe-w20e3/mgba-probe.exe --out-dir build/w20-e3/dense/step-20-to-21
python tools/s49_w20e/dense_camera_curve.py analyze --dense build/w20-e3/dense --out build/w20-e3/dense-camera-curve.json --radius 12
```

### 1.1 ⭐ 采集的**正确性验证**（不是「看起来对」）

| 窗口 | walk 端点帧 | 密集帧 | 像素差 |
|---|---|---|---:|
| `step-20-to-21` | `step-21-A.png` | `f043.png` | **0**（逐字节相同） |
| `step-21-to-22` | `step-22-A.png` | `f043.png` | **0** |
| `step-19-to-20` | `step-20-A.png` | `f043.png` | **0** |

⇒ **回放严格复现了原版**（不是近似）。

---

## 2. ⭐ 逐帧曲线（`step-20 → step-21` 窗口，**起点已验证**）

> 判别口径：只有「重叠区不匹配率 < 5 %」的平移才算数；`f000→f001` 的 (−12,−12) 不匹配率 0.998
> ⇒ **是整屏切换帧，不是相机运动，必须剔除**。

| 帧段 | 帧数 | 每帧增量 | 段位移 | 说明 |
|---|---:|---|---:|---|
| `f001` → `f038` | 37 | **(0, 0)** | 0 | 相机静止 |
| `f038` → `f049` | **11** | **(−8, +1/+2)** | **(−88, +9)** | ⭐ **快速左摇，8 px/帧** |
| `f049` → `f069` | 20 | (0, 0) | 0 | 停顿 |
| `f069` → `f076` | **7** | (+8,0), (+6,0)×2, (+5,0), (+3,0), (+2,0)×2 | **(+32, 0)** | ⭐ **ease-back 右摇**（逐步减速） |
| `f076` → `f090` | 15 | (0, 0) | 0 | 静止 |

### 2.1 ⭐ 关键：walk 截图落在**摇镜中间**

* `f001`（≈ `step-20-A.png`）→ `f043`（= `step-21-A.png`，**0 px**）的净位移 = **(−40, +7)**
  ⇒ **与 `camera-delta-consecutive.json` 的净值 (−40, +7) 完全一致** ⇒ 曲线自洽 ✔
* 而 `f043` 处在「11 帧快速左摇」的第 6 帧 ⇒ **原版在 walk 截图那一刻相机还在以 8 px/帧移动。**
  ⇒ ⚠️ **E1 若只把相机放到终点（净位移），`step-21` 这一帧仍然对不上** —— 必须复现**曲线 + 相位**。
* 摇镜在 `f049` 结束、`f069` 才开始 ease-back ⇒ **中间有 20 帧静止**，ease-back 是在**另一个事件**（不是同一个摇镜的回弹）。

### 2.2 其余两个窗口（**未通过起点验证，如实标注**）

| 窗口 | 起点 | 起点匹配 | 截图区间净位移 | 判定 |
|---|---|---:|---:|---|
| `step-21-to-22` | `step-21-A.png` | **27,476 px（对不上）** | (+24, +2) | ⚠️ **`step-21-A.ss9` 与 `step-21-A.png` 不对应**（walk 的存档态与截图不同步）⇒ 区间数值**不可用** |
| `step-19-to-20` | `step-19-A.png` | **23,309 px（对不上）** | (+128, −78) | ⚠️ 同上，**不可用** |

⇒ ⚠️ **只有 `step-20-to-21` 窗口是端点双验证过的。**
⇒ ⭐ 但 `step-21-to-22` 窗口**内部**的增量仍然自洽且有参考价值：
`f001→f002` (−8,+2)；`f022→f029` 有一段 **(+8,0),(+6,0)×2,(+5,0),(+3,0),(+2,0)×2 = +32 px 的 ease-back**；
`f057→f061` 4 帧 (+8,0)；`f079→f082` 3 帧 (+8,−5)/(+8,−6)。

### 2.3 ⚠️ 两条**必须随数据一起交付**的告警

1. **8 px 混叠**：地图草地纹理以 **8 px 为周期** ⇒ 平移搜索能过「整 8 px」对齐，
   所以测到的增量是**8 px 对齐下的最佳拟合**，**绝对相位只能观测到模 8 px**。
   ⇒ 曲线里的 (−8,+1) 真实含义是「**向左 ≈8 px（误差 < 8 px）**」。
2. **`f000→f001` 是整屏切换**（不匹配率 0.998）⇒ **不是相机运动**，任何求和都必须剔除它，
   否则净位移会凭空多出 (−12,−12)。

---

## 3. 机器可读曲线

`build/w20-e3/original-camera-curve.json`（schema `konoha.s49-original-camera-curve.v1`）：

```json
{"schema":"konoha.s49-original-camera-curve.v1","unit":"pixel",
 "points":[{"from":"step-20-A","to":"step-21-A","dx":-40,"dy":7,"struct":0.6548},
           {"from":"step-21-A","to":"step-22-A","dx":-16,"dy":9,"struct":0.8061}],
 "dense_points":[{"window":"step-20-to-21","from":"f038.png","to":"f040.png",
                  "dx":-8,"dy":1,"repeat":2}, ...],
 "windows":[{"window":"step-20-to-21",
             "settled_endpoint":"step-21-A.png","endpoint_frame":"f043.png",
             "endpoint_match_px":0,
             "verified_displacement_over_screenshot_interval":{"from":"f001.png","to":"f043.png","dx":-40,"dy":7},
             "runs":[...]}]}
```

* `points` = 净值（来自 `camera-delta-consecutive.json`，口径：settled frame 之间）
* `dense_points` / `windows[].runs` = **逐帧增量曲线**（已按相同增量合并成 `repeat` 段）
* `caveats` 字段里带着上面两条告警（机器可读）

---

## 4. 任务 B：重制侧相机取值链（定位结论）

### 4.1 取值链（全部在 `game/src/battle_runtime_scene.cpp`，**E1 的文件**）

| 环节 | 位置 | 内容 |
|---|---|---|
| 相机焦点的来源 | `:8866` `camera_focus = presentation_event.origin;` / `:9325` `camera_focus = state.cursor;` | **`camera_focus` 是 `grid_point`（格子坐标）** |
| 格子 → 世界像素 | `:1055-1061` `world_x/world_y` | `point.x*cell_width + cell_width/2 - map_center_x`（水平 32 px 量化、垂直 16 px 量化） |
| 世界像素 → 相机 | `:1089-1107` `camera_x/camera_y` | `clamp(world_x, …)` / `battle_camera_focus_y` |
| 相机 → 背景 | `:9383-9393` `camera.set_x/set_y` + `update_background_stream(next_camera_x, …)` | 背景按相机滚动 |
| 覆盖层 | `:9396-9404` `update_range_overlay(state, …, camera, *map, range_overlay)` | 移动格线按相机画 |

⇒ ⭐ **根因**：**相机焦点的类型是 `grid_point`** ⇒ 光标在移动期间不动 ⇒ 相机不动。
⇒ **原版跟的是单位的像素位置**（上一轮实测：`step-20→21` = (−40,+7)、`step-21→22` = (−16,+9)，都不是 32/16 整数倍）。

### 4.2 要改的话，需要在**哪里**加**什么**字段

| 文件 | 归属 | 需要加什么 | 为什么 |
|---|---|---|---|
| `game/include/konoha/battle_map_movement.h` | ⛔ **不在 E3 独占清单** ⇒ **接线请求** | 移动动画需要一个**逐帧像素位移**（`pixel_offset_x/y`，或 `camera_offset_x/y`）字段 | 现有的 `offset_x/offset_y` 是**整格常量**（单位精灵锚点），**不能动**；相机需要的是**亚格像素位移** |
| `game/src/battle_runtime_scene.cpp` | E1 | 相机焦点的类型从 `grid_point` 改成「格点 + 像素位移」；`camera_x/camera_y` 加一个像素偏移参数 | 见 §4.1 |
| `game/include/konoha/battle_map_visual_projection.h` | ⭐ **E3 独占** | **可加**一个纯函数：`battle_map_camera_pixel_offset(...)`，把「移动进度 → 相机像素偏移」写成可单测的纯算术 | 让 E1 调用它即可，不必把相机算术塞进 `.cpp`；同时我这边可以写单测锁住它 |

---

## 5. 任务 C：红箭头 / 移动格线 / 「SELECT 详细」HUD

### 5.1 定位结果

| 东西 | 实际绘制位置 | 归属 |
|---|---|---|
| 移动格线（range overlay） | `battle_runtime_scene.cpp:9396-9404` `update_range_overlay(…)` | E1 |
| 「SELECT 详细」HUD | `battle_runtime_scene.cpp` 的 UI 分派（`battle_ui_model`） | E1 |
| ⭐ **红色指示箭头** | ⭐ **不在 `battle_map_visual_projection.h`** —— 该文件只有 `battle_map_visual_position/facing/cursor_facing` 等纯函数，**没有任何箭头绘制**；箭头的角度/图元索引在 `battle_presentation_projection.h` 的 `battle_facing_indicator_angle/graphics_index/pulse_phase`，**绘制**在 `battle_runtime_scene.cpp` | **E1**（不是 E3） |

⇒ ⚠️ **「红箭头归 E3」这个前提不成立**：`battle_map_visual_projection.h` 是纯函数文件，无绘制代码。
⇒ 我在 E3 独占文件里能改的是**语义层**（`battle_map_visual_facing` / `battle_map_cursor_facing`），
而**红箭头是 E1 的 `battle_runtime_scene.cpp` 用这些语义去选图元的**。

### 5.2 可直接执行的改法（给 E1）

**红箭头（`battle_runtime_scene.cpp`）**：红箭头 = `battle_facing_indicator_graphics_index(facing, scene_frame)`
（`battle_presentation_projection.h:77-91`）在**移动选择**相位里被画出来。
⇒ **改法**：让它**只在「已确认目的地」之后画**，或**在移动动画期间不画** ——
原版在 `step-21`/`step-22`（移动相位）**没有**红箭头，而是在**更早/更晚**的相位才有。
⚠️ **原版具体是哪个相位才有，尚未取证**（见 §7 第 1 条）。

**移动格线**：原版 `step-22` 有 176 个亮格（W18 §3 锚点：族 = edge/solid/hatch/line_alt/band），
**画面上不是青色细线** ⇒ 重制侧的画法（细线）与原版的**格族画法**不同。
⇒ **改法**：不是「什么时候画」而是「怎么画」⇒ 归 `battle_map_visual_projection.h`（E3）可做：
把 `battle_map_overlay_map_x/y` 的**格族分类**对齐原版的 edge/solid/hatch 家族。
⚠️ 需要原版每格的族名做对拍（`tools/s49_overlay_align/compare_overlay_families.py`）才能定案。

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| P-60 | ⭐ 原版在移动相位里的相机是**连续平滑滚动** | 逐帧密集采集 + 相邻帧平移搜索（91 帧 × 3 窗口） | ⛔ **不成立**：是 **11 帧 × 8 px/帧的阶跃左摇** + 停顿 + **7 帧 ease-back 右摇**（+8,+6,+6,+5,+3,+2,+2） | **已证伪** |
| P-61 | ⭐ 密集采集能严格复现原版 | walk 端点帧 vs 密集帧逐像素比对 | **成立**：3 个窗口的端点都 **0 px**（逐字节相同） | **已确认** |
| P-62 | ⭐ walk 的 `step-21-A` 截图落在相机摇镜的**中间** | `f043` 处在 `f038→f049` 这段 11 帧左摇的第 6 帧；`f001→f043` 净位移 (−40,+7) 与 settled 净值一致 | 成立 | **已确认** |
| P-63 | 逐帧增量会被「草地纹理 8 px 周期」混叠 | 每帧增量都落在 8 的整数倍附近；真实相位只能观测到模 8 px | 成立（**告警已写进 JSON 的 `caveats`**） | **已确认** |
| P-64 | `f000→f001` 的 (−12,−12) 是相机运动 | 重叠区不匹配率 **0.998**（整屏切换） | ⛔ 不成立 ⇒ 求和必须剔除 | **已证伪** |
| P-65 | `step-21-A.ss9` 与 `step-21-A.png` 对应 | 逐像素比对（最佳 27,476 px） | ⛔ **不成立** ⇒ `step-21-to-22` 窗口的区间数值不可用（其端点 `f043` 仍 0 px 匹配） | **已证伪** |
| P-66 | 重制侧相机不动的根因 = 相机焦点的类型是 `grid_point` | 读 `battle_runtime_scene.cpp:8866/9325`（`camera_focus` 是 `grid_point`）与 `:1055-1107`（`world_x/world_y` 的 32/16 px 量化） | 成立 | **已确认** |
| P-67 | 红箭头在 E3 的 `battle_map_visual_projection.h` 里 | 通读该文件（205 行，全是纯函数，无绘制）+ grep `indicator`/`arrow` | ⛔ **不成立**：该文件无绘制代码；箭头图元在 `battle_presentation_projection.h`，绘制在 `battle_runtime_scene.cpp` ⇒ **归 E1** | **已证伪** |

---

## 7. 未完成项

1. ⭐ **原版在哪个相位才画红箭头 / 移动格线 / 「SELECT 详细」HUD，尚未取证**
   ⇒ 需要原版侧**逐帧**抓 25 个 walk 步的**叠加层族名**（`tools/s49_overlay_align/compare_overlay_families.py`）
   或原版存档态的 VRAM 抓取（`tools/s49_w1/capture_original_state.py`）。
2. ⭐ **`step-21-to-22` / `step-19-to-20` 窗口的**起点存档态与 walk 截图不对应**（P-65）
   ⇒ 需要搞清楚 walk 脚本的存档态保存时机，才能拿到这两段的**已验证**曲线。
3. **8 px 混叠**没有完全解开：绝对相机位置只知到模 8 px
   ⇒ 若要精确曲线，需要在**非周期区域**（灌木/水带/木箱）上单独测，或用原版**非 8 px 对齐**的特征点。
4. **E3 没有改产品代码**（相机/箭头/格线都在 E1 的文件里；E3 独占的
   `battle_map_visual_projection.h` 里能加的只是**纯函数**与**格族分类**）。
5. 未跑单测（0 行改动）；未提交 git。
