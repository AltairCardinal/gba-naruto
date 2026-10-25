# W25-H1 —— 开场 12 帧（判定台 #0–#11）残差解剖

> 2026-10-26 · 流 **H1** · lane `build/w25-h1`
> 任务书：`notes/s49-fidelity/W25-TASKS.md` §3
> 独占文件：`game/include/konoha/battle_scene_presentation.h` · `game/include/konoha/battle_presentation_script.h`
> 仪器：`tools/s49_fidelity_report.py`（arg-min）· `tools/s49_wave18/align_capture_steps.py`（固定偏移 +4）
> 工具：`tools/s49_w25h1/`（本流自写）

---

## 0. ⭐ 结论摘要（给父代理的三行）

1. **12 帧战场区残差 = 16,299 px（42.8 %），不是任务书写的 17,261 px** —— 任务书 §0.1 的**加总**错了 962 px，
   逐帧数值都对。本流归因表逐帧与判定台**逐位一致，误差 0 px**。
2. **不是时序差，是内容差**（全对全匹配：+4 配对最优，次优差 3–22 倍；遥测：重制相位 −2 = 9 帧，原版也是 9 帧）。
   残差三大桶：**A 部署文字叠层 6,315 px（38.7 %）／B 单位精灵 6,403 px（39.3 %）／C 地图标记 1,069 px（6.6 %）／D 其余 2,463 px（15.1 %）**。
3. ⭐ **三个桶的代码落点全部不在本流的两个独占文件里** ⇒ 本流**没有改任何产品文件**（改了也不会动这 16,299 px 的任何一个像素），
   改为给出**逐行改动提案**（§4）。最大的那条是 **R-H1-A**：
   `game/src/battle_runtime_scene.cpp:8213` 的 `generate(-116, 48, detail, sprites)` ⇒ `generate(-116, 56, detail, sprites)`（一行，≈ 1,250 px）；
   再加 `:8162-8164` / `:8166-8183` 两行左上文字只在 `deployment.current_entry() != nullptr` 时画（≈ 6,315 px）。

---

## 0.1 ⭐ 头号更正：**12 帧战场区残差 = 16,299 px，不是 17,261 px**

任务书 §0.1 写「#0–#11 = 17,261 px（45.4 %）」。**逐帧数值本身是对的，加总错了。**

| # | 原版帧 | 判定台配对的重制帧 | 战场区残差 px |
|---:|---|---|---:|
| 0 | step-00-base | step-24-A | 1,308 |
| 1 | step-01-A | step-05-A | 1,294 |
| 2 | step-02-A | step-06-A | 1,680 |
| 3 | step-03-A | step-07-A | 2,514 |
| 4 | step-04-A | step-08-A | 1,940 |
| 5 | step-05-A | step-09-A | 2,057 |
| 6 | step-06-A | step-10-A | 1,217 |
| 7 | step-07-A | step-11-A | 1,921 |
| 8 | step-08-A | step-12-A | 1,026 |
| 9 | step-09-A | step-13-A | 759 |
| 10 | step-10-A | step-14-A | 278 |
| 11 | step-11-A | step-22-A | 305 |
| | | **合计** | **16,299** |

* 16,299 / 38,047 = **42.8 %**（不是 45.4 %）。差额 962 px 就是任务书里的加总误差。
* 校验：`python tools/s49_w25/baseline_breakdown.py build/s49-package/baseline-accepted/report.json`
  ⇒ `# sum(field) = 38047`；逐帧值与本流 `frame_diff_clusters.py` **逐帧完全一致**（1294/1680/2514/1940/2057/1217/1921/1026/759/278/305），
  ⇒ **本流的归因表误差 = 0 px**。
* 25 帧固定偏移基线 = **54,959 px**（父代理 00:45 更正；53,364 是 wave 22 的 `w22-d1` 旧数）。判定台基线 = **38,047 px**。
* ⭐ **25 帧固定偏移口径下，这 12 帧合计 = 18,463 px / 54,959 = 33.6 %**
  （`python tools/s49_wave18/align_capture_steps.py --original build/s49-package-w22/work/s49-report/capture-original --remake build/s49-package-w22/work/s49-report/capture-remake --out build/w25-h1/align-w22.json`
  ⇒ `total field residual at offset +4: 54959`）。
  与判定台的 16,299 差 **2,164 px**，全部来自两处**配对不同**：
  * **#0**：固定偏移配 `step-00-base↔step-04-A`（2,565），判定台配 `step-00-base↔step-24-A`（1,308）⇒ **+1,257**
  * **#11**：固定偏移配 `step-11-A↔step-15-A`（1,212），判定台配 `step-11-A↔step-22-A`（305）⇒ **+907**
  ⇒ **父代理若要改判定台的配对口径，这两帧是最大的两个「配对红利」。**

### 0.2 本流的 lane ROM（供父代理收口时对照）

| 项 | 值 |
|---|---|
| lane | `build/w25-h1/butano-sequel` |
| ROM | `build/w25-h1/butano-sequel/butano-sequel.gba` |
| sha256 | `7048410d95abb2414f7b38db61a02a5840039490319ca80928e5f3093237d593` |
| 字节数 | 12,258,372 |
| 构建 | ✅ `make -j4` 通过（WSL Ubuntu-24.04 + devkitARM + `LIBBUTANOABS`） |
| 产品文件改动 | **0 个**（本流没有改任何产品文件，见 §5.1） |

> ⚠️ lane ROM 的 sha 与已接受基线 `b97daa81…`（12,258,628 B）不同 —— 共享树在基线之后有漂移，
> 本流 lane 是从**当前共享树**重建的。**本笔记里所有像素读数都绑定 w22 出包的 ROM
> `b97daa81…`（判定台基线那份）**，跨 ROM 不得比较（AGENTS.md 仪器纪律第 8 条）。

---

## 1. 判定：**这不是时序差，是内容差**

`tools/s49_w25h1/all_vs_all.py`（原版 25 帧 × 重制 35 帧，**战场区**全对全匹配）：

| 原版帧 | 最佳重制帧 | 残差 | 次佳 | 次佳残差 | 倍数 |
|---|---|---:|---|---:|---:|
| step-01-A | step-05-A | 1,294 | step-06-A | 16,315 | 12.6× |
| step-02-A | step-06-A | 1,680 | step-05-A | 16,315 | 9.7× |
| step-03-A | step-07-A | 2,514 | step-26-A | 20,458 | 8.1× |
| step-04-A | step-08-A | 1,940 | step-16-A | 6,225 | 3.2× |
| step-05-A | step-09-A | 2,057 | step-07-A | 24,575 | 11.9× |
| step-06-A | step-10-A | 1,217 | step-09-A | 26,910 | 22.1× |
| step-07-A | step-11-A | 1,921 | step-12-A | 24,929 | 13.0× |
| step-08-A | step-12-A | 1,026 | step-14-A | 4,164 | 4.1× |
| step-09-A | step-13-A | 759 | step-14-A | 2,250 | 3.0× |
| step-10-A | step-14-A | 278 | step-13-A | 2,761 | 9.9× |
| step-11-A | step-22-A | 305 | step-15-A | 1,212 | 4.0× |

⇒ **+4 配对是最优解，且次优解差 3–22 倍** ⇒ **相位时长没有问题**，不是「时序错位」。
⇒ 原版侧唯一的例外：`step-00-base` 的 arg-min 是 `step-24-A`（1,308），固定偏移的 `step-04-A` 是 2,565。
  **这是真的**：原版 `step-00-base` 是「忍者乱入」时刻（底部 HUD 有「忍者乱入」+ 体力 13 / 查克拉 8），
  重制侧这个时刻在 `step-24-A`（有同样的 HUD）；`step-04-A` 是重制侧的**部署选人**画面。
  ⇒ **「原版 step-00-base ↔ 重制 step-24-A」是正确的配对，固定偏移 +4 对 #0 是错的。**
  （这条影响 25 帧固定偏移仪器：它在 #0 上多算了 1,257 px。）

### 1.1 遥测（重制侧，`tools/s49_w25h1/remake_telemetry.py`）

| 重制帧 | `phase` | `scene_frame` | `render_stage` | `script_phase` | 画面 |
|---|---|---:|---:|---:|---|
| step-03-A | —（遥测尚未存在） | — | — | — | 部署选人 |
| step-04-A … step-12-A | **-2 (0xFFFFFFFE)** | 43…419（Δ47） | 0 | 0 | 战场 + **部署文字叠层** |
| step-13-A … step-15-A | **-3 (0xFFFFFFFD)** | 466…559 | 0 | 0 | 「開始」标题 + 黑场 |
| step-16-A 起 | 18 `script_blocked` | 0 | 100 | 1 | 战斗 |

⇒ **重制侧开场 = 相位 −2 持续 9 个 capture step（04–12），随后相位 −3 三步（開始 + 黑场）。**
⇒ **原版结构完全一样**：frames 00–08 = 9 帧「单位就位」，frame 09 = 「開始」标题。
⇒ ⭐ **相位时长一致 ⇒ 重制侧的 9 帧里画了原版没有的东西**（下面的 A 桶）。

---

## 2. 逐帧解剖（战场区 = 屏幕顶部 128 行，`FIELD_AREA = (0,0,240,128)`）

按**互不重叠**的矩形区域归因（`tools/s49_w25h1/attribute_regions.py`）：

| 桶 | 区域 | #0 | #1 | #2 | #3 | #4 | #5 | #6 | #7 | #8 | #9 | #10 | #11 | **合计** | % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **A** 部署文字叠层 | `deploy_hdr` (0,0,80,16) | 0 | 420 | 421 | 425 | 410 | 418 | 417 | 482 | 465 | 80 | 37 | 0 | **3,575** | 21.9 % |
| | `unit_line` (0,16,45,26) | 0 | 180 | 197 | 236 | 182 | 187 | 178 | 190 | 182 | 0 | 0 | 0 | **1,532** | 9.4 % |
| | `this_player` (0,116,100,128) | 0 | 204 | 158 | 200 | 126 | 126 | 126 | 184 | 126 | 0 | 0 | 0 | **1,250** | 7.7 % |
| | *A 小计* | 0 | 804 | 776 | 861 | 718 | 731 | 721 | 856 | 773 | 80 | 37 | 0 | **6,357** | **39.0 %** |
| **B** 单位精灵 | `konohamaru` (100,42,140,92) | 641 | 130 | 215 | 576 | 311 | 197 | 97 | 167 | 33 | 147 | 149 | 292 | **2,955** | 18.1 % |
| | `unit_left` (2,14,48,92) | 445 | 255 | 330 | 271 | 199 | 207 | 196 | 347 | 207 | 0 | 0 | 0 | **2,457** | 15.1 % |
| | `unit_right` (200,12,234,70) | 0 | 0 | 0 | 727 | 106 | 0 | 0 | 0 | 0 | 158 | 0 | 0 | **991** | 6.1 % |
| | *B 小计* | 1,086 | 385 | 545 | 1,574 | 616 | 404 | 293 | 514 | 240 | 305 | 149 | 292 | **6,403** | **39.3 %** |
| **C** 地图标记 | `marker_left` (108,25,128,36) | 42 | 0 | 0 | 95 | 127 | 93 | 83 | 88 | 88 | 29 | 44 | 0 | **689** | 4.2 % |
| | `marker_right` (128,34,140,45) | 105 | 0 | 0 | 68 | 0 | 68 | 10 | 68 | 68 | 0 | 0 | 0 | **387** | 2.4 % |
| | *C 小计* | 147 | 0 | 0 | 163 | 127 | 161 | 93 | 156 | 156 | 29 | 44 | 0 | **1,076** | **6.6 %** |
| **D** 其余（未归入上列矩形） | | 75 | 105 | 359 | 17 | 479 | 761 | 110 | 395 | 57 | 345 | 48 | 13 | **2,463** | 15.1 % |
| | **合计** | 1,308 | 1,294 | 1,680 | 2,514 | 1,940 | 2,057 | 1,217 | 1,921 | 1,026 | 759 | 278 | 305 | **16,299** | 100 % |

### 2.1 A 桶 —— 部署文字叠层（区域计数 6,357 px / 虚拟改图实测收益 6,315 px，最大单桶）

**现象**：重制侧在相位 −2 的 9 帧里，左上角画着白字黑框的 **「S DEPLOY」**（行 5–11）
和 **「UNIT」**（行 17–23），左下角画着 **「<名字> PLAYER」**（行 121–127，在战场区内）。
原版这 9 帧对应位置**全是草地**，一个字都没有。

取证：
* `tools/s49_w25h1/white_row_profile.py` ⇒ 重制侧独有的纯白像素：
  `y5..y11`（DEPLOY）173 px/帧、`y17..y23`（UNIT）108 px/帧、`y121..y127`（THIS PLAYER）95–128 px/帧。
* 放大图 `build/w25-h1/remake_topleft.png` 肉眼可见「S DEPLOY」+「UNIT」；
  `build/w25-h1/remake_bottomleft.png` 可见「… PLAYER」。
* 来源：`game/src/battle_runtime_scene.cpp:8150 render_deployment_text()`
  * `:8162-8164` `header = config.title + " DEPLOY"`，`generate(-116, -72, …)` ⇒ 屏幕 (4, 8)，字高 8 ⇒ 行 4–11 ✓
  * `:8166-8183` `progress = "UNIT n/m"`，`generate(-116, -60, …)` ⇒ 屏幕 (4, 20) ⇒ 行 16–23 ✓
  * `:8205-8213` `detail = <display_name> + " PLAYER"`，`generate(-116, 48, …)` ⇒ 行 121–127 ✓（**落在战场区内**）
  * 调用点：`:8349`（进入部署场景）与 `:8536`（循环内每帧，条件 `! title.visible()`）
* ⭐ **原版的对应文字在屏幕底部 128 行以下（战场区外）**，所以原版战场区没有它。

### 2.2 B 桶 —— 单位精灵（6,403 px）

两个**互相独立**的子因：

**B-1 站位 y 偏 2 px**（`unit_right` / `unit_left` 为主）
`tools/s49_w25h1/region_dump.py` 对 `step-03-A` vs `step-07-A` 的 (200,10)-(233,40) 逐像素对比：
原版那个右侧单位的白色特征像素在行 29–39，重制侧在行 31–40 ⇒ **重制侧整体下移 2 px**。
（行 31/32/33/34/35/36/37/38/39 vs 29/31/33/34/35/37/38/39）

**B-2 调色板差**（`konohamaru` 区域）
同一对比里，原版鸣人帽/发色是 **(0,41,41) 亮青**，重制侧是 **(0,8,8) 暗青**
（原版 `t`=teal(0,41,41) 109 px，重制侧 `T`=darkteal(0,8,8) 115 px，位置完全重合）⇒ **同一张精灵、同一位置、调色板不同**。

### 2.3 C 桶 —— 地图标记（1,076 px）

`region_dump.py`（104,22)-(142,48) 对比 `step-03-A` vs `step-07-A`：

| | 原版 | 重制侧 |
|---|---|---|
| 左标记（114–127, 28–35） | **蓝色**下行三角（11 px 宽，6 行） | **红色**下行三角（9 px 宽，6 行，高 2 px） |
| 右标记（129–137, 36–42） | **红色** 6×6 头 + 灰边（24 px 红） | **蓝色**同形 |

⇒ **地图光标与「红 facing indicator」两者的颜色被调换了**（且左标记差 2 px y）。
⇒ 原版的红 facing indicator 规格在 `battle_scene_presentation.h:519-525`
（24 px / 6×6 / RGB(255,0,0)）——**该组常量目前是死代码**（见 §3 P-7）。
⇒ 重制侧两处都用同一个 tileset `scenario_41_cursor`：
* 光标：`battle_runtime_scene.cpp:8332-8336`（`create_sprite(world_x, world_y - 24)`，**默认 tile 0**）
* facing indicator：`battle_runtime_scene.cpp:9716-9722`（`battle_facing_indicator_graphics_index(facing, scene_frame)`，tile 0..11）

### 2.4 D 桶（2,463 px）—— 未完全归因

主要集中在 #4/#5/#7（479 / 761 / 395 px），是精灵边缘的亚像素/调色板残差与散点；
**未验**：D 桶是否可完全拆成 B-1/B-2 的延伸（逐帧缺 100 px 的解释额度已满足，
但精确拆分需要再做一次按颜色的聚类，**本轮未做**）。

---

## 3. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| P-1 | 「开场 12 帧是相位时序错位（各相位时长不同）」 | `all_vs_all.py`：原版 25 帧 × 重制 35 帧全对全战场区匹配 | **证伪**：+4 配对是最优解，次优解差 3–22 倍 | **已证伪** |
| P-2 | 「残差主要来自相位标签 / 部署文字叠层」 | 逐帧白像素行剖面 + 区域归因 | **确认**：A 桶 6,357 px（39.0 %） | **已确认** |
| P-3 | 「底部 HUD 面板差异计入残差」 | `paths.py:30 FIELD_AREA=(0,0,240,128)` + 行剖面 | **证伪**：HUD 在 y≥128，不计；计的是部署文字落到 121–127 行 | **已证伪** |
| P-4 | 「重制侧的单位站位与原版差很多（大位移）」 | `region_dump.py` 逐像素 | **证伪**：只是 **y 方向 2 px** 的下移，x 不变 | **已证伪** |
| P-5 | 「鸣人单位残差是精灵画错」 | 同上 | **证伪**：是**调色板差**（0,41,41 vs 0,8,8），位置一致 | **已证伪** |
| P-6 | 「地图光标与红 facing indicator 只是画反了朝向」 | 同上 | **证伪**：形状相同、**颜色互换**（红↔蓝） | **已证伪** |
| P-7 | 「`battle_scene_presentation.h` 里的 C4 呈现时刻表已接线」 | 全 `game/` 树 grep `battle_presentation_moment` / `battle_presentation_overlays_of` | **证伪**：**只有头文件自身命中 ⇒ 整张表 + `battle_presentation_facing_indicator_*` 常量全是死代码** | **已证伪** |
| P-8 | 「重制侧开场相位时长与原版不同」 | 重制侧遥测（相位 −2 持续 9 个 capture step）+ 原版帧结构 | **证伪**：原版也是 9 帧（00–08）后接「開始」(09) ⇒ 时长一致 | **已证伪** |
| P-9 | 「#0（step-00-base）的正确配对是 step-24-A」 | all-vs-all + 画面内容（「忍者乱入」HUD 两侧一致） | **确认**：arg-min 1308 < 固定偏移 2565 ⇒ **固定偏移仪器在 #0 上多算 1,257 px** | **已确认** |
| P-10 | 「帧 #11 的 305 px 是黑场星形颜色（原版橄榄黄 vs 重制红）」 | `attribute_regions.py`：#11 的 292 px 落在 `konohamaru` 区域 | **未验**：需单独 dump 星形遮罩才能确认（H2 的 `battle_black_field_star_mask.h`） | **未验** |

**台账统计：已确认 2 条，已证伪 7 条，未验 1 条。**

---

## 4. 接线请求（**三个桶都不在本流的独占文件里 ⇒ 只给提案，不越界改**）

> 归属说明：`battle_runtime_scene.cpp` = H2/H3/H4 的独占（父代理用 `merge_lanes.py` 三方合并）；
> `battle_presentation_content.h` = H2 的独占；`graphics/**` = H4 的独占；
> `battle_presentation_projection.h` / `battle_map_visual_projection.h` = 未分配（共享树）。

### 4.1 ⭐ R-H1-A（最大，6,315 px / 38.7 %）：部署文字叠层不该出现在战场区

**归属**：`game/src/battle_runtime_scene.cpp`（H2/H3/H4 的独占）。

**A-1（最小可行版，一行，收益 ≈ 1,250 px）** —— 把底部「<名字> PLAYER」推出战场区：

```diff
--- a/game/src/battle_runtime_scene.cpp
+++ b/game/src/battle_runtime_scene.cpp
@@ battle_runtime_scene.cpp:8213 (render_deployment_text)
-    generator.generate(-116, 48, detail, sprites);
+    // The original's deployment detail line sits **below** the field area
+    // (y >= 128); at 48 it bled into rows 121-127 and cost ~1,250 px.
+    generator.generate(-116, 56, detail, sprites);
```

（同一处 `battle_runtime_scene.cpp:3930` 的 `render_text()` 也有 `generate(-116, 48, detail, sprites)`
—— 战斗相位的 HUD 明细行同理落在 121–127 行，**建议一并改成 56**，但它不在本流的 12 帧里。）

**A-2 + A-3（完整版，收益 ≈ 6,315 px）** —— 把左上角两行文字限制到真正的部署选人相位：

```diff
--- a/game/src/battle_runtime_scene.cpp
+++ b/game/src/battle_runtime_scene.cpp
@@ battle_runtime_scene.cpp:8162-8164 (render_deployment_text)
-    bn::string<48> header = config.title;
-    header += " DEPLOY";
-    generator.generate(-116, -72, header, sprites);
+    bn::string<48> header = config.title;
+    header += " DEPLOY";
+    generator.generate(-116, -72, header, sprites);   // 只有部署选人相位才画
@@ battle_runtime_scene.cpp:8166-8183
-    generator.generate(-116, -60, progress, sprites);
+    generator.generate(-116, -60, progress, sprites);   // 同上
```

⚠️ A-2/A-3 需要一个「当前是不是部署选人相位」的判据。
重制侧遥测显示**整个相位 −2 都是部署场景**（`battle_runtime_scene.cpp:8252 run_deployment_confirmation`），
而**原版这 9 帧的左上角是空的** ⇒ 判据不能是「相位 −2」，必须是
「**当前选中单位的那一帧**」（`deployment.current_entry() != nullptr`，即 `battle_deployment_flow.h:209-218`）。
**⇒ 建议的改法**：把 `render_deployment_text()` 的两行左上文字包在
`deployment.current_entry() != nullptr` 里（并把 `sprites.clear()` 保留），
其余 8 帧只画 A-1 下移后的底部明细行。
**未验**：这样改之后重制侧的部署选人画面（`step-04-A`）会与原版的部署选人画面差多少 —— 原版那一段没被录到，**无法验证**。

| # | 位置 | 改前 | 改后 | 预期收益 |
|---|---|---|---|---:|
| A-1 | `battle_runtime_scene.cpp:8213` | `generate(-116, 48, detail, sprites)` | `generate(-116, 56, detail, sprites)` | ≈ 1,250 px |
| A-2 | `battle_runtime_scene.cpp:8162-8164` | 无条件画 `config.title + " DEPLOY"` | 仅 `deployment.current_entry() != nullptr` 时画 | ≈ 3,575 px |
| A-3 | `battle_runtime_scene.cpp:8166-8183` | 无条件画 `"UNIT n/m"` | 同 A-2 | ≈ 1,532 px |

### ⛔ 父代理更正（2026-10-26 收口时）：**A-2 / A-3 的判据是空操作，不能照此接线**

父代理在收口时逐行核对了 `battle_runtime_scene.cpp` 的实际代码，**A-2/A-3 的门控条件不成立**：

* `battle_deployment_flow.h` 的 `current_entry()`：
  ```cpp
  return _phase == battle_deployment_phase::unit_confirmation &&
         _current_index < _entry_count ? &_entries[_current_index] : nullptr;
  ```
* 而 `progress` 文字的 `if(entry)` 分支画的是 **"UNIT n/m"**，`else` 分支画的是 **"START"**。
* ⭐ **实测帧里画的是 "UNIT n/m"**（`build/w25-montage/topleft.png`：重制侧 `step-05-A` / `step-07-A` 的左上角
  是「S DEPLOY」+「UNIT」，原版 `step-01-A` / `step-03-A` 的同一位置**是空草地**）
  ⇒ 画 "UNIT n/m" 的那些帧**必然满足 `current_entry() != nullptr`**
  ⇒ **把这两行包进 `current_entry() != nullptr` 之后，文字照样会被画出来 ⇒ 收益 = 0。**

⇒ **A-2/A-3 收口时未应用**，留给 wave 26。正确的判据仍然是未定的：
原版的部署选人画面**没有被录到**（重制侧的部署段对应原版的「忍者乱入」段），
所以「原版部署画面到底有没有文字」目前**无法从现有证据判定**，
⇒ **不能用一个猜出来的门控去删掉玩家可见的 UI**。

⇒ **A-1 是收口时唯一应用的一条**（父代理实测核对过）：
`generate(-116, 48, detail, sprites)` ⇒ `generate(-116, 56, detail, sprites)`。
父代理用 `tools/s49_w25/text_row_profile.py` 量了行分布，确认那行文字落在 **row 125–131**，
**跨过了战场区边界（y<128）** ⇒ field 残差确实吃到它；
`:8443` 已改（合并后的行号）。

### 4.2 ⭐ R-H1-B（6,403 px / 39.3 %）：单位精灵

**B-1 y 偏 2 px**（`unit_left` 2,457 + `unit_right` 991 的一部分）
* 归属：`game/src/battle_runtime_scene.cpp` 的 `update_unit_sprites()`（单位精灵的 `set_position` y 锚点）
  或 `battle_map_visual_projection.h` 的 `world_y()`（`:1336-1340`，`point.y * 16 + 8 - map_center_y`）。
* **未验**：到底是精灵锚点常数差 2 px，还是 `world_y()` 的取整差 2 px —— 需要把重制侧的
  `world_y(position)` 与原版同格的 y 逐格比对（**本轮未做**）。
* 建议修法（**待取证后填具体值**）：单位精灵 y 锚点 `-2`（或 `world_y()` 的偏移项改 `-2`）。

**B-2 调色板差**（`konohamaru` 区域 2,955 px）
* 归属：`game/include/konoha/battle_unit_palette_stream.h`（未分配）**或**
  `graphics/` 里该单位的精灵调色板（H4 的独占）。
* 现象：同一张精灵同一位置，原版 (0,41,41) / 重制侧 (0,8,8) ⇒ **单位调色板流的槽位分配与原版不一致**。
* **未验**：是哪一槽（palette bank / color index）错位。

### 4.3 ⭐ R-H1-C（1,076 px / 6.6 %）：地图光标 / facing indicator 颜色互换

**归属**：
* 颜色互换本身 = `graphics/scenario_41_cursor.bmp` + `.json`（**H4 的独占**）——
  原版 tile 0 = 蓝色光标、红 facing indicator 在别的 tile；重制侧反了。
  ⇒ **H4 的 4bpp 资产集要保留这个 tileset 的调色板顺序。**
* y 差 2 px = `battle_runtime_scene.cpp:8332-8336`（`world_y(first->position) - 24` ⇒ 建议 `- 22`）
  与 `:9716-9722`（facing indicator 的 y 锚点）。
* 规格常量已在 **`battle_scene_presentation.h:519-525`（本流独占）**：
  `battle_presentation_facing_indicator_pixels = 24` / `_width = 6` / `_height = 6` /
  `_red = 255` / `_green = 0` / `_blue = 0`
  ⇒ **接线时应把运行时改成读这组常量**，而不是另写一份（目前它们是死代码，见 P-7）。

### 4.4 R-H1-D：帧 #11 的 305 px（星形遮罩颜色）

* 归属：`game/include/konoha/battle_black_field_star_mask.h`（**H2 的独占**）。
* 现象（父代理目视）：原版星形是**橄榄黄**、重制侧是**红色**。
* **未验**：本流未单独 dump 星形区域（`attribute_regions.py` 把它落在 `konohamaru` 矩形 292 px，
  但 #11 是黑场帧 ⇒ 那个矩形里没有鸣人 ⇒ **归属存疑，需 H2 自己 dump**）。

### 4.5 R-H1-E（低优先，但顺手）：把 C4 的死表接上

`battle_scene_presentation.h:454-511` 的 `battle_presentation_moment` /
`battle_presentation_overlay_visibility_table` / `battle_presentation_overlays_of()`，
以及 `:519-532` 的 facing-indicator / SELECT-HUD 常量，**在整棵 `game/` 树里零引用**（P-7）。
`notes/s49-fidelity/W21-C4-original-presentation.md` 记录的 **R-C4-1 接线请求**从未落地。
⇒ 建议 wave 26 由父代理接线（`battle_runtime_scene.cpp`），否则这张表会一直误导后来的人。

---

## 5. 改动记录（改前 / 改后，两个仪器）

### 5.1 本流**没有**改任何产品文件（但 lane 已构建通过）

**理由**：A/B/C 三个桶的代码落点全部在 `battle_runtime_scene.cpp`（H2/H3/H4 的独占）、
`battle_presentation_content.h`（H2）、`graphics/**`（H4）、`battle_unit_palette_stream.h` /
`battle_presentation_projection.h` / `battle_map_visual_projection.h`（未分配）。
**本流的两个独占文件（`battle_scene_presentation.h` / `battle_presentation_script.h`）
在整个开场段（相位 −2）里没有被运行时读到** ——
`battle_scene_presentation` 的常量（`movement_frame_count` / `passive_frame_count` /
`battlefield_object_expiry_*`）只在战斗相位的移动/被动演出里用，
`battle_presentation_script` / `battle_presentation_selector` 只在对白相位用
（开场 9 帧的 `script_phase` 恒为 0 = idle，见 §1.1 遥测）。
⇒ **在独占文件里改任何东西都不会改变这 16,299 px 里的任何一个像素** ⇒ 按「一次只改一处、
跑一次、记一行」的纪律，**不做无谓改动**，避免动基线。

**lane 状态**：`build/w25-h1` 已 `make -j4` 构建通过，ROM sha256
`7048410d95abb2414f7b38db61a02a5840039490319ca80928e5f3093237d593`（12,258,372 B）。
**产品文件改动数 = 0** ⇒ 父代理收口时**不需要从本 lane 拷任何东西**，直接取笔记与工具即可。

**本流没有产出「改前 / 改后」两个仪器的数字** —— 因为没有产品改动。
§5.2 的数字是**离线虚拟改图的实测上界**（同一批 w22 帧、同一套仪器口径算出来的），
父代理接线后必须重录重制侧再实测。**这一点请勿当成已验证的收益。**

### 5.2 离线虚拟改图量（**实测的预期值，不是产品改动**）

`tools/s49_w25h1/virtual_fix.py`：把重制侧帧的指定矩形**换成原版同位置的像素**，
再按判定台口径重算残差 ⇒ 得到「该桶修好后残差能降到多少」的**上界**。
（12 帧战场区基线 = 16,299 px；12 帧**整屏**基线 = 93,316 px = 判定台 `full_residual` 之和 ✓）

| 模拟修法 | 12 帧战场区残差 | 12 帧整屏残差 | 相对基线 |
|---|---:|---:|---:|
| 基线（不改） | **16,299** | **93,316** | — |
| 只修 **A**（部署文字叠层） | **9,984** | 85,991 | **−6,315** 战场区 / **−7,325** 整屏 |
| 只修 **C**（标记颜色/位置） | 15,230 | 92,247 | −1,069 / −1,069 |
| 修 **A + C** | 8,915 | 84,922 | −7,384 / −8,394 |
| 修 **A + B + C**（全修） | **4,205** | 80,212 | **−12,094** / −13,104 |

逐帧（修 A 后）：1,308 / 493 / 907 / 1,660 / 1,227 / 1,332 / 499 / 1,074 / 259 / 679 / 241 / 305。

⚠️ **两点说明**：
1. 修 A 的**整屏**收益（7,325）比战场区收益（6,315）多 1,010 px ⇒ 那 1,010 px 在**战场区以下**
   （y≥128 的 HUD 带）⇒ **A 桶同时污染了底部 HUD 带**，修完 A 之后底部 HUD 会更接近原版
   （但底部 HUD 不计残差，所以对判定台数字没有额外贡献）。
**⇒ 修 A 后期望：判定台 12 帧 16,299 → ≈ 9,984；25 帧固定偏移 54,959 → ≈ 48,644（−6,315）**。
（A 桶在 #0 / #11 两帧上不产生影响 —— 那两帧配对到的重制帧没有部署叠层。）

---

## 6. 本流的工具（`tools/s49_w25h1/`）

| 工具 | 作用 |
|---|---|
| `all_vs_all.py` | 原版 25 × 重制 35 全对全战场区匹配（判定「时序差 vs 内容差」） |
| `frame_diff_clusters.py` | 逐帧差分连通块聚类 + 两边主色（找「可修的具体原因」） |
| `attribute_regions.py` | 按互不重叠的矩形区域做归因表（本流 §2 的数据源） |
| `white_row_profile.py` | 重制侧独有的纯白像素行剖面（定位部署文字叠层） |
| `region_dump.py` | 任意矩形的两帧并排 ASCII 像素图（读单位位移/调色板/标记颜色） |
| `crop_zoom.py` | 裁剪 + 最近邻放大（肉眼读小字） |
| `remake_telemetry.py` | 修好 `s49_w24g1/script_telemetry.py` 的遥测读取（原版在第一帧就找 struct 会死） |
| `virtual_fix.py` | 离线虚拟改图，估算某个桶修好后的残差上界 |

产物：`build/w25-h1/{intro_clusters.json, all_vs_all.json, remake_topleft.png, remake_bottomleft.png, orig_bottomleft.png}`
