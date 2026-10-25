# Wave 10 任务书 —— 接线总装（最后一批）+ 战斗数值 + 结算链缺屏 + 仪器/出包

> 2026-10-24 · 主代理（mvs_4e730a9ded524558a303c115875a9707）
> 前置：wave 9 四路（V1/V2/V3/V4）收口。
> ⭐ **wave 10 的形状**：wave 9 的三路（V1/V2/V3）都交付了「纯逻辑 + 精确接线点」，
> **接线点全部落在 `battle_runtime_scene.cpp`** ⇒ **U1 一次接完**。
> 另两路各解决一个**独立的产品缺口**：战斗数值（打不赢）与结算链缺屏。

---

## 0. wave 9 的结果（**全部已确认，勿重查**）

### 0.1 ⭐ V3：对话「一个字都没画」的真正根因找到了

**不是脚本数据问题**：battle 14 的 3 屏文本、25 个文本页、**862 个码位全部齐备、字体不缺字**。
**真正根因**：`battle_runtime_scene.cpp:8726` 把 `render_script_glyphs()` 关进了
`if(handled || …)` 输入门控，而**打字机推进帧 `handled` 恒为 false** ⇒ 字形精灵永不重建。

**「開始」标题画不出来 = 三个独立缺陷叠加**：
1. **Butano `create_sprite()` 用屏幕中心相对坐标**，运行时传的是**屏幕绝对坐标**
   ⇒ 标题整体偏出 (120, 80)，**完全出屏**；
2. **素材切块上界写反** ⇒ 5 件里 **3 件全透明**；
3. **两个相位按相位主序写进行主序位图** ⇒ 每张位图左右两半都是两相位的行交错。

三个都修好后，投影残差 **5,869 → 264 / 4,725 → 341**（复现 Y2 真值 264/341）。

### 0.2 ⭐ V2：32 px 不是「窗口常量」，差距在**内容**里

* 两种锚定机制查实：原版**内容锚在地图空间 map px (256, 0)、屏幕位置跟相机**
  （`bg2_hoffs=240 == bg_hoffs`、`bg2_voffs=24 == bg_voffs`）；
  重制侧是**内容跟相机滑**。
* ⭐ **窗口搜索放宽到 `[0,480) × [0,256)` ⇒ 没有任何窗口能逐格全等**，
  分数在 224..264 **恒定** ⇒ 32 px 不是一个可调的窗口偏移。
* 已落成可单测的地图空间锚点 API（`battle_map_visual_projection.h`，+101 行），
  并改完 W3 接线点 1（`battle_scene_controller.h` 受阻集 → `terrain.overlay_blocked()`）。
* ⭐ **共享仪器数学上表达不了锚点 256** ⇒ 父代理**授权 U4 直接改**
  `tools/s49_overlay_align/compare_overlay_families.py`（V2 已给现成版
  `tools/s49_v2_anchor/compare_at_anchor.py`）。
* **垂直放置待定**：原版 `bg2_voffs = 24`，重制侧 `248 + camera.y()`，差 **224 px**（= 14 战斗行）。

### 0.3 V1：37 级星光圈资产做出来了，但**没交报告**，且**接线让残差回归**

* 37 级遮罩**逐像素精确**；37 级的 hybrid 布局**超 OAM 预算**（103 精灵 vs 86 空槽）
  ⇒ 改用 cell-only 布局，**图块并集正好 404**（= 余量上限）。
* 接线进 `battle_runtime_scene.cpp` 后**残差回归 109,597 → 159,310**
  ⇒ 生长阶段把**时间轴移位**了 ⇒ V1 把它改成**文档化的开关（默认关）**再重测。
* ⚠️ **`notes/s49-fidelity/V1-star37-wiring.md` 没交**（输出被运行时截断）。
* ⚠️ 「混合 cell 渲染成全黑」这条未查完（怀疑调色板 bank 被运行时覆盖）。

### 0.4 ⭐ V4：重制侧 battle-14 **打不赢** ⇒ 结算链的运行帧没录到

* **根因是数值不是驱动器**：护送 40 HP、蜜蜂每回合 12、单次伤害 10
  ⇒ 4 轮最多 12 次攻击 < 13 次需求。
  ⚠️ **伤害口径也不同**：原版十字手里剑 **27** 伤 vs 重制侧 10/15/6。
* ⇒ 结算链只能从**敗北**的 `outcome` 进 ⇒「勝利」屏与结算屏的**运行帧**没录到。
* ⭐ **结算链结构差查清了**：

| | 原版 | 重制侧 |
|---|---|---|
| 链 | 勝利→结算屏→**四人升级屏**→忍具一览→**对白**→**任务菜单** | `outcome`→`result`→`level_up`→`training`→`complete` |
| 缺 | — | **没有逐人升级页、没有战后对白、没有任务菜单** |

* **资产级（静态图层）对照**：
  | 屏 | 差 px | 占比 |
  |---|---:|---:|
  | 结算屏 | 12,798 / 38,400 | 33.3 % |
  | 升级屏 | 7,681 / 38,400 | 20.0 % |
  | 训练页 | 8,483 / 38,400 | 22.1 % |
* **施工单 S1–S5**（在 `V4-settlement-compare.md` 里）。
* 流水线 **9/12 绿**（首个失败步骤 5）、**11 个 selftest 全红**、单测棘轮**零回归**。

---

## 1. 流 U1 —— ⭐ 接线总装（**关键路径**）

### 1.1 独占文件

* `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_runtime_scene.cpp`
* `…\game\include\konoha\battle_black_field.h` / `battle_black_field_timing.h`
* `…\graphics\`（标题素材 + 星光圈素材）

⛔ **不要改** `battle_map_visual_projection.h` / `battle_scene_controller.h`（V2 已改完，属它）、
`battle_presentation_*.h` / `battle_opening_title.h`（V3 已改完，属它）、
`battle_result*.h` / `battle_runtime_result.h` / `generated_battle_result_content.h`（U3 独占）。
⛔ 逆向线只读。

### 1.2 要接的线（**逐条照抄**，都在 `battle_runtime_scene.cpp`）

**① ⭐⭐ 对话字形渲染移出输入门控（对话的唯一根因）**
V3 报告 §5 的接线点 ①：
* 成员区加 `battle_presentation_glyph_render_state script_glyph_render_state;`
* 把 **8830–8840** 整段从 **8726** 的门控块**移到门控块之外**：
```cpp
if(presentation.busy()) { script_glyph_sprites.clear(); }
else if(script_glyph_render_state.needs_render(state.script))
{ render_script_glyphs(state, story_text_generator, script_glyph_sprites); }
```

**② ⭐⭐ 标题 5 个坐标改成 Butano 中心相对**
`battle_opening_title_view::create()`（**7209–7228**）⇒
`(-47,1) (47,-6) (95,-6) (47,42) (95,42)`，
或直接用 V3 放在 `battle_opening_title.h` 里的 `battle_opening_title::placements[0..4]`。
`set_phase()` 不用改。

**③ ⭐ 换掉 5 个标题素材**
从 `D:\Github\gba-naruto\build\s49-v3\title-assets\` 拷到 `…\butano-sequel\graphics\`。
落地前先跑 `python tools/s49_v3_dialogue/check_title_asset_pixels.py --staged build/s49-v3/title-assets`
⇒ 必须 **10 格全 0 差异**。

**④ ⭐ 覆盖层锚点接线（V2）**
`battle_runtime_scene.cpp` **2221–2266**：
```cpp
map_px_x = battle_map_overlay_map_x(layer_px_x);
cell_x   = battle_map_overlay_cell_x(layer_px_x);
map_px_y = battle_map_overlay_map_y(layer_px_y);
cell_y   = battle_map_overlay_cell_y(layer_px_y);
```
`tile_x/tile_y` 仍由 `map_px - cell*size` 推；
`_bg->set_position(-window_x, -window_y)` **不动**；
`cell_x ∈ {0, 8..14}` ⇒ 宽度钳位不用放宽，回绕段自动映到地形列 0。

**⑤ ⭐ 星光圈 37 级接线（V1）**
* include `konoha/battle_black_field_star_mask.h`（自带两个 item 头）；
* 场景加 `battle_black_field_star_mask` 成员；
* **每推进一级调 `set_level(level)`，必须在场景精灵画完之后**（否则被压住）；
* 黑场结束 `clear()`；
* ⚠️ **星光圈与调色板淡出二选一**（原版是「洞」不是「变暗」）⇒ `battle_black_field.h` 的调色板淡出要**关掉**；
* 素材「已转换、**未链接**」⇒ include 后才进 ROM（自查：`nm | grep star_mask`）。
* ⚠️ **V1 接线后残差回归 109,597 → 159,310**（生长阶段移位了时间轴）
  ⇒ 先把扩展做成**开关（默认关）**，确认回归消失；再定位时间轴并**打开**。
  **不许**用「默认关」当作最终交付——最终必须是**打开且残差不回归**。

**⑥ 对话框斜切展开（可选，最后做）**
`update_script_message_window`（6033）要把 `box_opening_active/frame` 传给渲染器；
`battle_presentation_message_window_runtime_renderer::update`（4979）现在只收 `bool visible`。
Z3 的展开模型（`battle_presentation_box_opening` 的 `step()/covered()/visible_span()`，
采样行 103/127/152）已齐。⚠️ **建议单独排一轮**，不要和标题补丁混做。

### 1.3 补交 V1 的报告

`notes/s49-fidelity/V1-star37-wiring.md`（**V1 至今未交**）：
从 `git diff HEAD -- butano-sequel/game` 反推它到底接了什么，
把接线点逐条标注「已接 / 未接 / 为什么」+ 台账 + 前后对比表。

### 1.4 验收

* **构建干净通过**；**ROM 4096 帧冒烟不崩**；**R×9 不崩**。
* ⭐ **重录密集 walk** ⇒ 判定台残差总和 **< 109,597**，**全 0 帧 ≥ 4**（现在 2）。
* **判定台 12 步流水线全绿**（含棘轮）。
* 逐格族名对拍（**用 U4 改好的锚点版仪器**）⇒ 目标 **同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0**。
* 黑场真值：`python tools/s49_blackfade/blackfade_report.py` ⇒ 重制侧 **37 级**逐帧可见像素与原版一致。
* 对话：判定台**全 0 帧 ≥ 4**（对话那 3 帧补上）。
* 标题：原版 step-09 / step-10 对应时刻**重制侧有同相位标题屏**，残差 → 0 附近（投影 264/341）。
* **单测棘轮**：失败集合与 HEAD 基线**逐名相同** ⇒ 多出任何一项 ⇒ 变红。
  HEAD 基线：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh`
  工作区：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh`
* ⚠️ **并发构建会互相覆盖** ⇒ `objcopy: Invalid argument` ⇒ 等 60 s 重试（最多 5 次）。

---

## 2. 流 U2 —— ⭐ 战斗数值对齐（让重制侧 battle-14 能打赢）

### 2.1 独占文件

* `…\game\include\konoha\battle_unit_content.h` / `generated_battle_unit_content.h`
* `…\game\include\konoha\battle_condition*.h` / `battle_scenario_content.h`
* `…\game\include\konoha\battle_ai*.h`
* 新单元测试

⛔ **不要改** `game\src\battle_runtime_scene.cpp` / `battle_black_field*.h` / `graphics/`（U1 独占）、
`battle_result*.h`（U3 独占）。
⛔ 逆向线 **全程只读**。

### 2.2 问题（一句话）

**重制侧 S49 battle-14 打不赢** ⇒ 结算链只能从**敗北**的 `outcome` 进
⇒ 「勝利」屏与结算屏的**运行帧**没录到 ⇒ V4 的结算链逐屏对照做不了。

**已测到的数值差**（V4）：
| | 原版 | 重制侧 |
|---|---|---|
| 护送 HP | 40 | 40 |
| 蜜蜂每回合伤害 | 12 | 12 |
| 单次伤害（十字手里剑） | **27** | **10 / 15 / 6**（三个招式） |
| 打 5 只蜂需要的攻击次数 | 13 | 4 轮最多 12 ⇒ **不够** |

### 2.3 要做的

1. **先取原版数值真值**（逆向线只读；W4 已解出原版单位记录布局：
   `+0x00` 角色 ID / `+0x07` 查克拉 / `+0x0C` HP / `+0x0E` 最大 HP；
   战斗结果字节 `0x02026807`）。
   ⇒ 逐项对齐：**伤害、HP、攻击频率、招式表**。
2. **评估影响面**：改数值会影响其它 46 个场景 ⇒ 先做**影响面评估**（哪些场景共用这些数值），
   再决定改法（改 S49 专用值 vs 改全局表）。
3. ⚠️ **决策点**：如果「原版与重制侧的 balance 差异」是**有意的**（重制线自己的设计），
   ⇒ **不要改数值**，改用「让结算链在敗北后也能录」的方案
   （V4 的 `training` 段已经录到了「忍具一览」）。
   ⇒ 两种结论都要有**证据**。

### 2.4 验收

* **判据 A（若判定「该对齐」）**：重制侧 battle-14 **能打赢** ⇒
  用 V4 的驱动器 `tools/s49_victory_capture/v4_route_gen.cpp` + `v4_replay.py`
  把「勝利」屏与结算屏**运行帧**录出来（两次独立跑逐字节一致）。
* **判据 B（若判定「不该改」）**：给出**证据**说明差异是有意的 +
  给出「敗北后结算链」的可复跑录制方案。
* **单测棘轮**（同 §1.4）。

### 2.5 交付物

* `notes/s49-fidelity/U2-battle-balance.md`。

---

## 3. 流 U3 —— 结算链缺屏 + 结算屏美术

### 3.1 独占文件

* `…\game\include\konoha\battle_results.h` / `battle_result_content.h`
* `…\game\include\konoha\battle_runtime_result.h`
* `…\game\include\konoha\generated_battle_result_content.h`
* `…\game\include\konoha\battle_scene_presentation_event.h`
* 新单元测试

⛔ **不要改** `game\src\battle_runtime_scene.cpp` / `battle_black_field*.h` / `graphics/`（U1 独占）。
⇒ 接线点写清单交父代理。
⛔ 逆向线只读。

### 3.2 任务

**S1 · 缺战后对白 + 任务菜单两屏**
原版链：勝利→结算屏→四人升级屏→忍具一览→**对白**→**任务菜单**；
重制侧：`outcome`→`result`→`level_up`→`training`→`complete` ⇒ 这两屏**完全没有**。

**S3 · 无逐人升级页**
原版有**四人**逐人升级屏；重制侧只有一个 `level_up`。

**S4 · 结算屏美术仍是 `battle_ui_result_*`**
⚠️ 仓里**已有 1:1 的 `scenario_41_result_*`**，但**运行时 0 引用** ⇒ 换过去。

### 3.3 验收

* 资产级对照的差 px 下降（结算屏 12,798 / 升级屏 7,681 / 训练页 8,483）。
* **单测棘轮**（同 §1.4）。
* 接线点清单。

### 3.4 交付物

* `notes/s49-fidelity/U3-settlement-content.md`。

---

## 4. 流 U4 —— 仪器锚点修正 + 出包 + 报告终审

### 4.1 独占文件

* `D:\Github\gba-naruto\tools\s49_overlay_align\compare_overlay_families.py`
  （**父代理授权**：V2 申请改这个共享仪器，V2 判它「数学上表达不了锚点 256」）
* `D:\Github\gba-naruto\tools\s49_package\`（流水线 + 打包）
* `D:\Github\gba-naruto\docs\s49-fidelity-report-2026xxxx.md`（报告）

⛔ 不改重制线任何文件；⛔ 不改其它流的仪器（**只读调用**）；⛔ 逆向线只读。

### 4.2 任务

**(a) 仪器锚点修正。**
把 `compare_overlay_families.py` 的 `remake_logical_cells` 改成
「缓冲 px `p` 的地图标签 = `(p + 256) mod 480`」，
`best_window` 改为**固定锚点**或放宽到 `[0, 480)`。
⇒ V2 已给**现成版本**：`tools/s49_v2_anchor/compare_at_anchor.py`（**照抄，别重写**）。

**(b) 12 步流水线复跑 + 出包。**
* 等 U1/U2/U3 落地后重跑 `python tools/s49_package/run_pipeline.py`。
* ⚠️ 第 2 步单测棘轮：失败集合必须与 HEAD 基线**逐名相同**（20 项预存债）。
* ⚠️ 构建碰撞重试已在流水线里（5 次 / 60 s / 只认 `objcopy` 碰撞）。
* 产物 `build/s49-package/`（**不进 git**）。

**(c) 1:1 报告终审。**
残差前后对比、逐格族名、**结算链对照表**、音频 event_diff、存档字段表、12 条边界表、
黑场真值表、假设台账索引、**未达成项**（**不许粉饰**）。
**未达成项**至少包含：
* ⭐ **原版 S49 结算屏真值 —— 已闭合**（写进正文）；
* **残差归零的可达性**：可证像素**下界 ≈ 23,700** ⇒ 归零在当前录制上**不可达**；
* 存档**逐字节一致按用户口径排除**；音频**逐采样一致排除**（80–120 h）；
* **20 项单测在 HEAD 即为红（预存债），本次零回归**；
* 四角星光圈 / 对话框斜切展开若未补齐要单列；
* 本机构建非字节可复现 ⇒ 随包带 ROM + 重录命令。

### 4.3 验收

* 12 步流水线**全绿**，收据 JSON 完整；11 个 selftest 仍全红。
* 报告里每个数字能追到某次运行。

### 4.4 交付物

* `tools/s49_overlay_align/`（改） + `tools/s49_package/` + `docs/s49-fidelity-report-2026xxxx.md`（终稿）。

---

## 5. 父代理（我）做的事

* **串行接线兜底**（U2/U3 的接线点由我合进 `battle_runtime_scene.cpp`）。
* 残差棘轮监督：任何流声称「残差下降」都要用判定台独立复跑确认。
* 同步 `docs/sequel-roadmap.md` / `docs/s49-three-day-plan.md` / `docs/butano-fidelity-roadmap.md`。

---

## 6. 交回格式

1. **一句话结论**。
2. **改动的文件**（完整绝对路径）。
3. **跑了哪些验证**（命令 + 关键数字）。
4. **假设台账**（表格）。
5. **接线点清单**。
6. **卡在哪**。
7. **新文件一律 LF、无 BOM**；**不提交 git**。

---

## 7. 反循环守则（复述）

* 一次尝试回答一个**是/否问题**；**「还是卡」不是结果**。
* 一次只改一处，跑一次，记一行；结论落进**假设台账**。
* **连续 3 次同样结果 ⇒ 停**，换方法，写进台账。
* 陷住了**换方法/换会话**，不要靠续跑硬扛。
* ⚠️ **并发构建会互相覆盖** ⇒ **同一时刻只允许一路做构建**。
* ⚠️ **子代理被运行时中断时，产物在盘上但未经验证** ⇒ 接管方必须**重新验证**
  （见 `notes/s49-fidelity/INCIDENT-wave5-task-loss-20261024.md`）。
