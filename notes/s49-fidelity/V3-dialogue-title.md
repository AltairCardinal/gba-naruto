# V3 —— 开场对话文字 + 「開始」标题屏

> 2026-10-24 · wave 9 · 流 V3
> 上游：`notes/s49-fidelity/WAVE9-TASKS.md` §3、
> `Z3-dialogue-box.md`（对话框遮罩表 / 打字机时序）、
> `W1-blackfield-timeline.md`、`Y2-opening-title-blackfade.md`（标题真值）
> 工具（本流新建，全部在 `tools/s49_v3_dialogue/`）：
> `regenerate_title_assets.py`（修好的素材生成器，**只写 staging**）、
> `check_title_asset_pixels.py`（素材 ↔ 原图的逐像素校验）、
> `compare_title_assets.py`（staging ↔ graphics/ 差分）、
> `verify_title_placement.py`（放置 ↔ 原版帧的残差）、
> `scan_title_beat.py`（标题节拍定位）、
> `dump_battle14.py` / `check_glyph_coverage.py`（脚本与字体覆盖）
> ⛔ **未改** `game/src/battle_runtime_scene.cpp`（V1 独占）⇒ 接线点写成清单交给父代理
> ⛔ **未改** `graphics/`（V1 独占）⇒ 修好的 5 个 BMP 写到 `build/s49-v3/title-assets/`，
> 附一行 copy 命令
> ⛔ 逆向线 `D:\Shell\gba-naruto-reverse` 全程只读；⛔ **未提交 git**

---

## 0. 一句话结论

> **任务 A（开场对话文字）**：重制侧**一个字都没画出来**。根因**不在**脚本数据 ——
> battle 14 的 3 屏文本、25 个文本页、862 个码位全部齐备、字体不缺字 ——
> 而在 `battle_runtime_scene.cpp:8726` 的**渲染门控**：`render_script_glyphs()` 被关在
> `if(handled || …)` 里，而打字机推进帧**没有** `handled`（`handled` 只在按键时置位，
> 且脚本确认被 `! typewriter_active` 挡住），所以字形精灵**永远不会被重建**。
> 修复点落在 V1 独占文件 ⇒ §4 接线点 ①；我已交付脚本侧 API + 单测。
>
> **任务 B（「開始」标题屏）**：画不出来是**三个互相独立的缺陷叠加**，不是一个：
> ① **坐标体系错** —— Butano 的 `create_sprite()` 用**相对屏幕中心**的坐标，
> 运行时传的是**屏幕绝对坐标** ⇒ 整个标题偏出 (120,80)，完全出屏；
> ② **素材切块上界写反** ⇒ 5 件素材里有 **3 件全透明**（shipped `shi_right` /
> `shi_bottom` / `shi_corner` 的 ink 恒为 0）；
> ③ **相位打包顺序错** —— 位图是**行主序**，生成器却按**相位主序**写 ⇒ 每张位图
> 左右两半都是两个相位的**行交错**，第 2 相位根本不是第 2 相位。
> 三个都修好之后，投影残差 **5,869 → 264 / 4,725 → 341**（Y2 的真值 264 / 341 完全复现）。
> ①②的修复点落在 V1 独占文件 ⇒ §4 接线点 ②③；③ 需要的 5 个 BMP 我已生成到 staging。

---

## 1. 交付物

| 路径 | 性质 | 说明 |
|---|---|---|
| `…/butano-sequel/game/include/konoha/battle_opening_title.h` | **改** | 放置表重写：Butano 屏幕中心相对坐标 + 切块偏移语义统一 + 真实 tile 数（416 / 208） |
| `…/butano-sequel/game/include/konoha/battle_presentation_script.h` | **改** | 新增 `battle_presentation_glyph_render_key` / `battle_presentation_glyph_render_state`：告诉渲染器"这一帧要不要重画字形" |
| `…/butano-sequel/game/tests/test_battle_opening_title_s49.cpp` | **新** | 标题几何单测：5 个放置值 + 屏幕框回推 + 回归护栏（不得等于旧的绝对坐标） |
| `…/butano-sequel/game/tests/test_battle_presentation_s49_dialogue.cpp` | **改** | 加 `check_render_state()`：打字机每次露字都要重画、其余帧不重画 |
| `tools/s49_v3_dialogue/regenerate_title_assets.py` | **新** | 修好的素材生成器（切块上界 + 相位行主序打包），**只写 staging**，附 copy 命令 |
| `tools/s49_v3_dialogue/check_title_asset_pixels.py` | **新** | staging 里的 10 个（件 × 相位）格子 ↔ 原图逐像素校验（必须 0 差异） |
| `tools/s49_v3_dialogue/compare_title_assets.py` | **新** | staging ↔ `graphics/` 差分（哪几件变了、变了多少像素） |
| `tools/s49_v3_dialogue/verify_title_placement.py` | **新** | 按头的放置表合成标题 → 与原版帧比残差（判决仪器） |
| `tools/s49_v3_dialogue/scan_title_beat.py` | **新** | 定位原版标题节拍、对比重制侧部署文字区 |
| `tools/s49_v3_dialogue/{dump_battle14,check_glyph_coverage,find_box_frames,count_dialogue_screens,render_text_band,stack_text_bands,list_dialogue_frames,probe_title_region,probe_title_anywhere,probe_title_placement,measure_title_ink,render_title_ink,verify_title_offset,measure_title_art,read_deployment_text}.py` | **新** | 本流的调查探针（对话屏 / 标题 / 脚本数据 / 字体覆盖） |
| `build/s49-v3/title-assets/` | **产物** | 修好的 5 个 BMP + 5 个 json + `manifest.json` + `pixel-check.json` + `placement.json` |
| `notes/s49-fidelity/V3-dialogue-title.md` | **新** | 本报告 |

---

## 2. 任务 A：开场对话文字

### 2.1 脚本数据是齐的 —— 「补 3 屏文字」这条路走不通

任务书假设脚本里缺内容。实测**不缺**：

| 项 | 实测 |
|---|---|
| battle 14（scenario 49 的战斗，`battle_campaign_route.h` 的 `{49, 14, 0, 50, …}`） | definition `{14, 629, 629, 46, 139, 11}` |
| case `sel=1`（入场选择器选中的那条） | **3 个 `render_text` 页**，offset/length = `18006/57`、`18063/32`、`18095/61` |
| battle 14 全部文本页 | 25 页 |
| 码位覆盖 | battle 14 全部 25 页用到的码位 **missing = 0**（`generated_battle_presentation_glyph_content.h` 862 个码位，已排序，`battle_presentation_glyph_index` 的二分查找前提成立） |
| 字体图集 | `battle_presentation_glyphs.bmp` 8×13792、P 模式 16 色，索引 0 = (255,0,255) 透明 |

⇒ **文本、内容、字体三者都齐**，缺的是"把字画到屏幕上"这一步。

### 2.2 真正的根因：字形渲染被关在输入门控里

`battle_runtime_scene.cpp` 的两处 `render_script_glyphs()` 调用：

* **8076**（首帧渲染路径）
* **8836**（**在 8726 的门控块内**）

```cpp
// battle_runtime_scene.cpp:8726
if(handled || rejection_changed ||
        presentation_frame ||
        map_movement_frame || map_movement.busy() ||
        presentation.busy())
{
    …
    if(presentation.busy()) { script_glyph_sprites.clear(); }
    else { render_script_glyphs(state, story_text_generator, script_glyph_sprites); }   // 8836
    …
}
```

而 `handled` 的全部赋值点（8193 声明）**全在按键分支里**：

* `8193` `bool handled = false;`
* `8227` 脚本确认被 `! state.script.typewriter_active` 挡住 ⇒ **打字机期间不可能置位**
* 其余 `handled = true` 都在 `a_pressed / b_pressed / l_pressed / …` 分支里

打字机本身每帧都在推进（`8437-8438`，一场景帧推进两次，因为重制侧一场景帧 = 2 GBA 帧），
**但推进帧不是输入帧** ⇒ 门控的六个条件一个都不成立 ⇒ `render_script_glyphs()` 从不被调用
⇒ `script_glyph_sprites` 永远是空的 ⇒ **对话框有纸、有头像、没有一个字**。

`render_script_glyphs()`（4472）本身是对的：它读 `state.script.visible_glyph_count`，
逐字形 `create_sprite(-92 + column*8, row*16 + 48, graphics_index)`。

### 2.3 像素证据

| 观测 | 原版 | 重制侧 |
|---|---|---|
| 判定台 bench2 对话区 ink | step-12 = 0（空框）→ 13 = 1265、14 = 1365、15 = 781、16 = 635、17 = 1449、18 = 0 | 只有 step-15 = 0、step-20 = 0 两屏，且都是空的 |
| 密集 walk 对话区 | `step-0267..0271` 斜切遮罩（paper 0.776→0.983、text 1025→125）、`0272..0283` 空框、`0284..0322` 第一行渐增 32→1163、`0324..0359` 第二行 110→599、`0360..0400` 第三行 39→2236 | `step-0336..0437` 共 **102 帧全是 `paper=1.000 / text=0`** |
| 判定台残差（`build/s49-w1/bench2/report.json`） | `field_residual.sum=109597`、`median=1432`、`max=27325`、**`zero_frames=2`（基线 4）** | 逐帧 delta：step-13 **+646**、14 **+702**、15 **+417**、16 **+68**、17 **+756**；残差正落在 y105–148 的文字区 |

⇒ 验收口径「判定台全 0 帧 ≥ 4」当前是 **2**。这 2 帧正是"有框无字"的对话屏；
接线点 ① 落地后这 5 屏（13/14/15/16/17）会各自带上文字，全 0 帧数应当 ≥ 4。

### 2.4 我落地的部分：脚本侧 API（`battle_presentation_script.h`）

V1 的改动越少越好，所以我把"这一帧要不要重画字形"这条规则放进了**我独占的**脚本头：

```cpp
struct battle_presentation_glyph_render_key
{
    battle_presentation_script_phase phase = …idle;
    std::uint16_t text_offset = 0;
    std::uint8_t text_length = 0;
    std::uint8_t visible_glyph_count = 0;
    std::uint8_t speaker = 0;
    bool typewriter_active = false;
    constexpr bool operator==(const battle_presentation_glyph_render_key&) const = default;
};

class battle_presentation_glyph_render_state
{
public:
    // 第一次调用恒为 true（还没画过）；之后只在"这一行变了"时为 true。
    [[nodiscard]] bool needs_render(const battle_presentation_script_snapshot&);
    [[nodiscard]] static battle_presentation_glyph_render_key key_of(const battle_presentation_script_snapshot&);
private:
    battle_presentation_glyph_render_key _key = {};
    bool _drawn = false;
};
```

单测 `test_battle_presentation_s49_dialogue.cpp::check_render_state()` 已经锁住语义：
空框的 51 帧**不**要重画、露第 1 个字**要**重画、之后的 3 帧**不**要重画、露第 2 个字**要**重画、
换行（新的 text_offset）**要**重画。

### 2.5 附带接线点：对话框的斜切展开整段缺失

Z3 §4 的 W1.1 / W1.2 要求 `update_script_message_window` 接收 box_opening 状态。
实测**整条线都没接**：

* `battle_presentation_box_opening`（`battle_presentation_text_layout.h`，我独占）+ 48 项
  `battle_presentation_box_opening_mask` 表（`battle_presentation_content.h`）**都齐了**；
* `battle_presentation_script.h` 的 `_advance_box_opening()` 也在推进，
  快照里的 `box_opening_active` / `box_opening_frame` 一直在变；
* 但 `grep box_opening` 在 `battle_runtime_scene.cpp` 里**零命中** ——
  `battle_presentation_message_window_runtime_renderer::update(bool visible)`（4979）
  只收一个 `visible`，`update_script_message_window`（6033）也只传 `visible`。

⇒ 原版的「斜切展开」在重制侧完全没有：原版 `step-0267..0271` 的遮罩残差
（paper 0.776→0.983）在重制侧变成 `paper=1.000` 一步到位。

---

## 3. 任务 B：「開始」标题屏

### 3.1 缺陷 ①：Butano 坐标体系用错了（标题整体出屏）

Butano 的 `create_sprite(x, y)` 用的是**相对屏幕中心**的坐标：精灵格子的中心落在
`(120 + x, 80 + y)`。运行时传的却是**屏幕绝对坐标**：

```cpp
// battle_runtime_scene.cpp:7209（V1 独占）
_kai       = …battle_opening_title_kai      .create_sprite(73, 81,  phase);
_shi_top   = …battle_opening_title_shi_top  .create_sprite(167, 74, phase);
_shi_right = …battle_opening_title_shi_right.create_sprite(215, 74, phase);
_shi_bottom= …battle_opening_title_shi_bottom.create_sprite(167,122,phase);
_shi_corner= …battle_opening_title_shi_corner.create_sprite(215,122,phase);
```

这 5 个数是**屏幕绝对**的格子中心（`kai` 的格子中心 = 41 + 32 = 73、49 + 32 = 81），
但 Butano 会再加一次 (120, 80) ⇒ 「開」实际落 screen **(193, 161)** —— 屏幕是 240×160，
**整个标题出屏**。

对照证据（说明 Butano 确实是中心相对）：消息窗黑条 `create_sprite(-90 + index*60, 12)`
正好铺满全屏宽（屏幕 x 从 -90+120 = 30 起）；推进图标 `create_sprite(105, 67)`
对应实测屏框 (217,139)-(231,148)，其格子中心 225,147 = 120+105, 80+67。

### 3.2 缺陷 ②：素材切块的上界写反 ⇒ 3/5 件全透明

`tools/s49_opening_title/make_title_assets.py` 的 `frame_cell()`：

```python
for y in range(min(height, cell_h - offset_y)):      # 应为 min(height - offset_y, cell_h)
    for x in range(min(width, cell_w - offset_x)):    # 应为 min(width - offset_x, cell_w)
```

`shi_right` 的 `offset_x = 64`、`cell_w = 32` ⇒ `cell_w - offset_x = -32` ⇒ 循环体为空；
`shi_bottom` 的 `offset_y = 64`、`cell_h = 32` 同理；`shi_corner` 两个都是 ⇒ 全空。
`kai` / `shi_top` 的偏移是 0，侥幸逃过。

实测 shipped 素材（`graphics/`）：

| 文件 | 尺寸 | 墨迹 |
|---|---|---|
| `battle_opening_title_kai.bmp` | 128×64 | 3 264 |
| `battle_opening_title_shi_top.bmp` | 128×64 | 5 196 |
| `battle_opening_title_shi_right.bmp` | 64×64 | **0** |
| `battle_opening_title_shi_bottom.bmp` | 128×32 | **0** |
| `battle_opening_title_shi_corner.bmp` | 64×32 | **0** |

⇒ 「始」字缺了最后 6 列和最后 6 行。

### 3.3 缺陷 ③：两个相位被打包成交错的行

位图是**行主序**（`write_4bpp_bmp` 写的是 `pixels[y * width + x]`），但生成器把两个相位
**按相位主序**拼进去：

```python
pixels = []
for frame in range(phase_count):
    pixels.extend(cells[frame])          # ← 相位主序
write_4bpp_bmp(bmp_path, cell_w * phase_count, cell_h, pixels, palette)
```

⇒ 位图左半（第 0 相位那一格）里装的是**第 0 相位的偶数行 + 第 1 相位的偶数行**，
右半装的是两个相位的**奇数行**。逐像素实测（`check_title_asset_pixels.py` 在修复前）：

```
battle_opening_title_kai  相位 0: expected_ink 1632 / actual 1644 / differing 1559
                           相位 1: expected_ink 1632 / actual 1620 / differing 1544
```

Butano 侧确认了"横向排帧"这个约定本身是对的：
`butano_graphics_tool.py:201` 写明帧数 = `bmp.width / item_width * bmp.height / item_height`，
`:340` 把 `-Mw width/8 -Mh height/8`（**单帧**的 tile 尺寸）交给 GRIT ⇒
64×64 单帧的 metatile 是 8×8 tile，于是 128×64 位图的 16×8 tile 被读成两个 8×8 block，
左半 = 第 0 相位、右半 = 第 1 相位。**错的只是写进去的像素顺序。**

### 3.4 三个缺陷修好之后的残差

`tools/s49_v3_dialogue/verify_title_placement.py`（按**头的放置表**合成标题，再贴到重制侧
自己的战场帧上，与原版 `step-0207-beat` / `step-0230-beat` 比）：

| 相位 | 不放标题 | **用新的放置表 + 修好的素材** | 用旧的绝对坐标 |
|---|---|---|---|
| 0 | 5 869 | **264** | 5 238 |
| 1 | 4 725 | **341** | 4 094 |

264 / 341 与 Y2 的真值（264 / 333 量级）完全对上 ⇒ 剩下的残差是重制侧自己的鸟动画，
不是标题。合成标题的墨迹框 = **(41, 42)-(205, 112)**，与原版标题框一致。

### 3.5 标题节拍：重制侧**确实走到了**

有人会怀疑"重制侧根本没进 `start_confirmation`"。实测**进了**：

* `battle_deployment_flow.h:114-129`：每按一次 A 确认一个单位，`_current_index >= _entry_count`
  ⇒ phase 变成 `start_confirmation`；再按一次 A 才是 `complete`。
* `battle_runtime_scene.cpp:7508-7512` 部署场景里 `a_pressed` ⇒ `deployment.confirm()`。
* `battle_runtime_scene.cpp:7585-7593`：`title_visible = deployment.phase() == start_confirmation`
  ⇒ `title.begin()` + `title_view.create(title.phase())`。
* 原版节拍（`scan_title_beat.py`，walk5 原版）：`step-0185-in` 标题区灰阶 4 109 →
  `step-0205-in` 峰值 8 027 → 之后稳定在 ~4 078（标题的相位 1 形态）。

⇒ 部署流程不用改，**只改坐标和素材**，标题就会出现在原版对应的那一拍。

---

## 4. 接线点清单（全部落在 `battle_runtime_scene.cpp` / `graphics/`，V1 独占）

### ① 任务 A —— 把字形渲染移出输入门控

文件：`…/butano-sequel/game/src/battle_runtime_scene.cpp`

1. 在 `script_glyph_sprites` 旁边加一个成员：
   `battle_presentation_glyph_render_state script_glyph_render_state;`
2. 把 **8830-8840** 这一段从 8726 的门控块里**移到门控块之外**（每场景帧执行）：

```cpp
// 现在（在 8726 的 if(handled || …) 块内）——删掉
//     if(presentation.busy()) { script_glyph_sprites.clear(); }
//     else { render_script_glyphs(state, story_text_generator, script_glyph_sprites); }

// 改成（放在门控块结束之后、每帧都跑）
if(presentation.busy())
{
    script_glyph_sprites.clear();
}
else if(script_glyph_render_state.needs_render(state.script))
{
    render_script_glyphs(state, story_text_generator, script_glyph_sprites);
}
```

`battle_presentation_glyph_render_state` 在我改过的 `battle_presentation_script.h` 里，
语义已被 `test_battle_presentation_s49_dialogue.cpp` 锁住。
（`state.script` 是 `battle_presentation_script_snapshot`，其 `phase` / `text_offset` /
`text_length` / `visible_glyph_count` / `speaker` / `typewriter_active` 齐了。）

### ② 任务 B —— 标题的 5 个坐标改成 Butano 中心相对坐标

文件：同上，`battle_opening_title_view::create()`（**7209-7228**）

```cpp
_kai        = …battle_opening_title_kai      .create_sprite(-47,  1, phase);
_shi_top    = …battle_opening_title_shi_top  .create_sprite( 47, -6, phase);
_shi_right  = …battle_opening_title_shi_right.create_sprite( 95, -6, phase);
_shi_bottom = …battle_opening_title_shi_bottom.create_sprite( 47, 42, phase);
_shi_corner = …battle_opening_title_shi_corner.create_sprite( 95, 42, phase);
```

或者更稳（别再手写常数）——直接用我放在 `battle_opening_title.h` 里的表：

```cpp
constexpr std::array<battle_opening_title_placement, 5> placements;  // 顺序 = pieces
_kai = …battle_opening_title_kai.create_sprite(
        battle_opening_title::placements[0].x,
        battle_opening_title::placements[0].y, phase);
```

（`set_phase()`（7230）不用改，它只换 tile，不动位置。）

### ③ 任务 B —— 换掉 5 个素材（3 件全透明 + 2 件相位错乱）

目录：`…/butano-sequel/graphics/`（V1 独占）

修好的 5 个 BMP + 5 个 json 已生成在 `build/s49-v3/title-assets/`：

```
Copy-Item "D:\Github\gba-naruto\build\s49-v3\title-assets\*.bmp","D:\Github\gba-naruto\build\s49-v3\title-assets\*.json" "D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics"
```

落地前请先跑一次校验（必须 10 个格子全部 `differing_pixels = 0`）：

```
python tools/s49_v3_dialogue/check_title_asset_pixels.py --staged build/s49-v3/title-assets
```

`manifest.json` 里有每件的 sha256、tile 数（合计 416 tile，每相位 208）。

> ⚠️ `battle_opening_title_shi_corner` **两相位都是全透明的**（原图那个角落没有墨迹）。
> 它是白占 32 tile + 1 个 OAM 槽；可以删掉这个 item（连带 `graphics/` 里的 BMP/JSON
> 和 `battle_runtime_scene.cpp` 里那一行），但**不是必须**。

### ④ 任务 A 附带 —— 对话框的斜切展开（Z3 §4 W1.1 / W1.2）

文件：同上

* `update_script_message_window`（**6033**）要把 `state.script.box_opening_active` /
  `box_opening_frame` 传给渲染器；
* `battle_presentation_message_window_runtime_renderer::update`（**4979**）目前只收
  `bool visible`，要改成收展开状态；
* 展开的模型已经齐了：`battle_presentation_box_opening`
  （`battle_presentation_text_layout.h`，我独占）提供 `step()` / `covered(row, column)` /
  `visible_span(row, first, last)`，采样行是 `screen_top_row=103` /
  `screen_middle_row=127` / `screen_bottom_row=152`；
* 运行时在展开期间要**在对话框之上**画黑色碎片（Z3 §4）。

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| A1 | 重制侧脚本里缺开场对话的文字 | 解析生成头，列 battle 14 case `sel=1` 的 `render_text` 页 | 3 页（18006/57、18063/32、18095/61），25 页全在 | **已证伪** |
| A2 | 字体缺字位 | battle 14 全部 25 页码位 vs `generated_battle_presentation_glyph_content.h` | missing = 0（862 码位，已排序） | **已证伪** |
| A3 | 字形绘制代码本身有 bug | 读 `render_script_glyphs()`（4472） | 逻辑正确，读 `visible_glyph_count` 逐字建精灵 | **已证伪** |
| A4 | 字形精灵没被重建（渲染门控） | 读 8726 门控 + 8193 `handled` 的全部赋值点 + 8227 `!typewriter_active` | 打字机帧六个条件全不成立 ⇒ 永不调用 | **已确认（根因）** |
| A5 | 判定台全 0 帧只有 2 帧是因为"有框无字" | `bench2/report.json` 的 `zero_frames` + 逐帧 delta + 对话区 ink | zero_frames = 2（基线 4），delta 集中在 step-13..17 | **已确认** |
| A6 | box_opening 模型没被运行时消费 | `grep box_opening` 扫 `battle_runtime_scene.cpp` | 零命中；`update()` 只收 `visible` | **已确认** |
| B1 | 标题素材本身缺内容 | 读 `tools/s49_opening_title/*.png` 的墨迹 | kai 1 632 + shi 3 343（全），素材应当够 | **已证伪** |
| B2 | 标题素材切块有 bug | 读 `frame_cell()` 的上界 + 与原图逐像素对 | `min(height, cell_h - offset_y)` 应为 `min(height - offset_y, cell_h)` | **已确认（缺陷②）** |
| B3 | 标题的 3 件素材全透明 | 读 `graphics/*.bmp` 的调色板索引 | shi_right / shi_bottom / shi_corner 的 ink = 0 | **已确认** |
| B4 | Butano 的 `create_sprite` 用屏幕中心相对坐标 | 对照消息窗黑条（`create_sprite(-90+…, 12)` 铺满全屏宽）与推进图标（105,67 → 屏框 217,139） | 确认中心相对；旧的 5 个坐标整体偏 (120,80) | **已确认（缺陷①）** |
| B5 | 两个相位的打包顺序错 | 位图行主序 vs 生成器相位主序；逐像素对相位 0/1 | 左半 = 相位 0 偶数行 + 相位 1 偶数行 | **已确认（缺陷③）** |
| B6 | Butano 侧"横向排帧"约定成立 | `butano_graphics_tool.py:201` 帧数公式、`:340` 的 `-Mw/-Mh` 用单帧 tile 尺寸 | 成立；错的只是写进去的像素顺序 | **已确认** |
| B7 | 三个缺陷修好后残差能降到 Y2 的真值 | `verify_title_placement.py` | 5 869 → **264**、4 725 → **341** | **已确认** |
| B8 | 重制侧进不了 `start_confirmation`（标题节拍缺失） | 读 `battle_deployment_flow.h:114-129` + `battle_runtime_scene.cpp:7508` / `7585-7593` + 原版节拍扫描 | 部署流程正常，按 A 会走到 `start_confirmation` | **已证伪** |
| B9 | VRAM / OAM 放不下标题 | `build/s49-w1/vram-headroom.json`（部署画面 obj_tiles_free 543~710，峰值 336）+ 生成的 item 头 | 标题合计 416 tile（每相位 208），够；OAM 5 槽，W2 星芒在黑场不同幕 | **已确认（可放下）** |
| B10 | 修好的素材与 shipped 素材的差别只应是那 3 件 | `compare_title_assets.py` | kai / shi_top **总墨迹数相同**（3 264 / 5 196）但 **3 103 / 4 101 个像素位置不同**（相位打包错乱）；shi_right 0 → 156、shi_bottom 0 → 111；shi_corner 两边都是 0 | **已确认** |

---

## 6. 验证记录

| 验证 | 命令 | 结果 |
|---|---|---|
| 新单测（标题几何） | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/v3-run-tests.sh` | `PASS test_battle_opening_title_s49` / `PASS test_battle_presentation_s49_dialogue` / `PASS test_battle_opening_title` |
| 单测棘轮（HEAD 基线） | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh` | 20 个失败（`/tmp/head-baseline-fails.txt`） |
| 单测棘轮（工作区） | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/v3-run-all-tests.sh` | 20 个失败，**与基线逐名相同**（`diff` → IDENTICAL）；两个新单测在通过列表里 |
| 素材逐像素校验 | `python tools/s49_v3_dialogue/check_title_asset_pixels.py` | 10 个（件 × 相位）格子 **differing_pixels 全 0** |
| staging ↔ shipped 差分 | `python tools/s49_v3_dialogue/compare_title_assets.py` | kai / shi_top 总墨迹数相同（3 264 / 5 196）但 **3 103 / 4 101 个像素位置不同**（相位打包修好）；shi_right 0 → 156、shi_bottom 0 → 111；shi_corner 两边都是 0 |
| 放置 ↔ 原版帧残差 | `python tools/s49_v3_dialogue/verify_title_placement.py` | 相位 0：**264**（不放标题 5 869，旧坐标 5 238）；相位 1：**341**（4 725 / 4 094） |
| 标题节拍 | `python tools/s49_v3_dialogue/scan_title_beat.py` | 原版 `step-0205-in` 标题区灰阶峰值 8 027；重制侧部署流程走到 `start_confirmation` |
| 脚本 / 字体覆盖 | `python tools/s49_v3_dialogue/dump_battle14.py 14`、`check_glyph_coverage.py 14` | 3 页 / missing = 0 |
| ROM 构建 | `wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=… && make -j4"` | **成功**（`Linking ROM… / Fixing butano-sequel.gba… / ROM fixed!`；`butano-sequel.gba` 12 020 796 B，2026-10-24 11:02:47）。新头文件进得了正式构建；告警全是既有的（`battle_range_ui_style.h` / `battle_audio_director.h` / `battle_scene_controller.h`，都不在本流独占清单） |

---

## 7. 风险与未决

1. **本流没有落地 ① ② ③ ④ 四个接线点**（都在 V1 独占文件 / 目录），
   所以**重录后的验收数字还没有**：判定台全 0 帧数、step-09 / step-10 的标题残差
   要等父代理落地后重录才能给出。本流给出的是**接线前就能验证的等价证明**：
   素材逐像素 0 差异 + 放置残差 264 / 341。
2. **对话框斜切展开（④）缺一整段实现**：模型和掩码表齐了，但运行时怎么把黑色碎片
   画到对话框之上（用哪个精灵 / 哪个 BG / 怎么按 `covered()` 裁）没有先例，
   建议单独排一轮，不要和标题补丁混在一起。
3. **相位 1 的精确形状只有两个采样点**：密集 walk 每 4 帧采样一次，
   所以「始」的相位 1 只知道 2 个相位；`battle_opening_title::phase_frames = 23`
   是按采样推的，要做到逐帧一致需要原版的逐帧录制。
4. **OAM 槽**：W2 记「星芒吃 84 槽，余量只有 2 槽」。标题要 5 槽。
   两者不同幕（标题在部署幕、星芒在黑场幕），实测不冲突，但若以后同幕出现，
   优先删掉全透明的 `shi_corner`（省 1 槽 32 tile）。
5. `build/s49-v3/title-assets/` 是**产物**，不是源码；`graphics/` 的落地要由 V1 执行。
