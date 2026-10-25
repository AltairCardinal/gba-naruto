# Z3 —— 对话框展开动画 + 换行等待参数

> 2026-10-24 · Z3 流（wave 7）· 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/WAVE7-TASKS.md` §0 / §3、`notes/s49-fidelity/Y4-dialogue-typewriter.md`
> 仪器（只读复用）：`tools/s49_pairing/`（密集 walk + 内容锚）
> 本流新增仪器：`tools/s49_z3_dialogue/`（**每帧一采的原版录制器** + 逐帧测量）
> 独占文件：`battle_presentation_text_layout.h` / `battle_presentation_script.h` /
> `battle_presentation_content.h` + 2 个单元测试
> ⛔ **未改动** `battle_runtime_scene.cpp` / `battle_scene_controller.h`（Z1 独占）、
> `battle_black_field*.h` / `battle_opening_title.h` / `graphics/`（Z2 独占）；
> ⛔ 逆向线全程只读；⛔ **未提交 git**。

---

## 0. 一句话结论

> **换行等待参数取到了真值**：原版的「换行等待」**不是脚本参数**（3213 条命令里只有 1 条
> `wait_frames`），而是**「按 A 之后到下一行第一个字出现」之间的帧数**，而且**分两种**：
> 脚本没有换头像时 **7 帧**，脚本换了头像时 **63 帧**（差的 56 帧是原版等头像替换动画走完）。
> 两个数都是**每帧一采**实测出来的（原版自己的时间轴：第 1406 帧按 A → 第 1413 帧出字；
> 第 1500 帧按 A → 第 1563 帧出字），已在重制侧实现并单测。
> **「对话框斜切展开」不是对话框动画，是入场转场**：原版那一段是**一层纯黑遮罩**在
> **已经画完的场景**上被斜切成碎片擦掉（已逐像素证明），BG 图块表在整个过程里**逐字节不变**
> ⇒ 遮罩来自 OBJ ⇒ **像素级复现需要原版的碎片素材 + 运行期的精灵摆放（Z2 素材 + Z1 运行期）**，
> 不是对话脚本能管的事；本流把**逐帧遮罩表**（实测）做成了模型交给 Z1/Z2。

---

## 1. 交付物

| 路径 | 性质 | 说明 |
|---|---|---|
| `butano-sequel/game/include/konoha/battle_presentation_content.h` | **改** | +2 个实测等待常量（7 / 63）+ 对话框展开常量 + **48 项实测遮罩表** |
| `butano-sequel/game/include/konoha/battle_presentation_text_layout.h` | **改** | +`battle_presentation_box_opening`（对话框展开模型：步进 / 覆盖查询 / 可见跨度） |
| `butano-sequel/game/include/konoha/battle_presentation_script.h` | **改** | 换行等待逻辑（按「有没有换头像」选 7 / 63）+ 快照新增 `box_opening_active` / `box_opening_frame` |
| `butano-sequel/game/tests/test_battle_presentation_line_wait.cpp` | **新** | Z3 单测（换行等待 7/63、展开模型、脚本武装） |
| `butano-sequel/game/tests/test_battle_presentation_typewriter.cpp` | **改** | Y4 的「换行 1 帧」断言改成「换行等 7 帧」（**否则变红**） |
| `tools/s49_z3_dialogue/lua/record_fine.lua` | **新** | **每帧一采**的原版录制器（不存存档，快 10 倍） |
| `tools/s49_z3_dialogue/record_fine_original.py` | **新** | 上面那个录制器的驱动器 |
| `tools/s49_z3_dialogue/measure_fine.py` | **新** | 1 帧分辨率的对白事件测量 |
| `tools/s49_z3_dialogue/make_mask_table.py` | **新** | 生成实测遮罩表 |
| `tools/s49_z3_dialogue/sync_mask_table.py` | **新** | 把实测遮罩表**回写**进重制侧的头文件（表永远不是手打的） |
| `tools/s49_z3_dialogue/*.py`（其余 8 个） | **新** | 逐帧残差 / 遮罩几何 / 切线表 / 脚本转储 等探针 |
| `tools/s49_z3_dialogue/README.md` | **新** | 这批探针的用法（每个探针回答什么问题） |
| `notes/s49-fidelity/Z3-dialogue-box.md` | **新** | 本报告 |

---

## 2. 任务 B：换行等待参数（**实测真值**）

### 2.1 ⭐ 先证伪：等待不是脚本参数

把重制侧生成出来的脚本数据全量转储（`tools/s49_z3_dialogue/scratch_script_dump.py`，
3213 条命令）：

```
opcode 0x00 end                  count=400
opcode 0x01 render_text          count=1074
opcode 0x02 show_portrait        count=140
opcode 0x03 hide_portrait        count=3
opcode 0x04 update_portrait      count=163
opcode 0x08 select_speaker       count=1030
opcode 0x0f wait_frames          count=1      ← 全库只有 1 条
opcode 0x11 set_portrait_focus   count=37
opcode 0x12 init_portrait_pair   count=317
opcode 0x17 animate_portrait     count=4
opcode 0x20 render_param_text    count=44
wait_frames commands: 1
   {'source': '0x08050B57U', 'opcode': 15, 'operands': [30, 0, 0, 0], ...}
```

⇒ **原版的逐行等待不在脚本里**；逆向线里也没有（`notes/evidence/rom-display-text-*`
那批是**固定文本消费者**，不是战斗对白引擎）。
⇒ 只能**从原版帧号反推**（任务书给的第二条路）。

### 2.2 ⭐ 测量方法：把原版**每帧一采**重录一遍

密集 walk 是**每 4 GBA 帧采 1 张**（`tools/s49_pairing/walkspec.py: CAPTURE_STRIDE = 4`），
4 帧的分辨率**测不出**「按键 → 出字」的精确帧数。

⇒ 本流新增了 `tools/s49_z3_dialogue/lua/record_fine.lua`：**每帧采 1 张、不存存档**
（原版 ROM / 原版存档全程只读），跑的是**同一份语义脚本**（24 次 A，hold 4 / settle 90）。
采集窗口 1100–1800 帧，共 **701 张**。

帧号口径（来自录制器自己的 lua）：基线帧 = 90，第 b 拍按 A 的帧 = `90 + 94*(b-1)`，
内层采样帧 = 按下 + 8 … 按下 + 90。

```powershell
python tools/s49_z3_dialogue/record_fine_original.py `
    --out build/s49-z3/fine-original --from 1100 --to 1800
# => {"frames": 701, "exit_code": 0, ...}
```

### 2.3 ⭐ 真值表（原版自己的时间轴，1 帧分辨率）

`tools/s49_z3_dialogue/measure_fine.py` 的输出（`build/s49-z3/fine-original`）：

| 事件 | 第 1 行 | 第 2 行 | 第 3 行 |
|---|---|---|---|
| 第一个字出现在屏幕上 | f=**1255** | f=**1413** | f=**1563** |
| 最后一个字 | f=1311 | f=1449 | f=1631 |
| 字数（(末-首)/4+1） | **15** | **10** | **18** |
| 推进图标出现 | f=1367 | f=1477 | f=1683 |
| **按 A（确认键按下）** | f=**1312**（打字中，**被忽略**） | f=**1406** | f=**1500** |
| 推进图标消失 | — | f=1409 | f=1503 |
| 旧行被擦掉 | — | f=1411 | f=1561 |
| **下一行第一个字** | — | f=**1413** | f=**1563** |
| ⇒ **按 A → 出字 = 等待** | — | **7 帧** | **63 帧** |

**逐帧差分**（`tools/s49_z3_dialogue/scratch_frame_diff.py`）解释了那 56 帧的去处：

```
第 1→2 行（脚本只跑了 select_speaker）：
  f=1409  头像区 x17..95 变 + 图标消失
  f=1411  头像区 x148..219 变 + 旧行被擦掉
  f=1413  新行第一个字出现（x27..30，14 px）
  ⇒ 没有肖像动画，等待 = 7 帧

第 2→3 行（脚本跑了 show_portrait）：
  f=1503  图标消失
  f=1505..1528  旧肖像**向右滑出**（每 2 帧 8 px）
  f=1533  说话人标签变
  f=1535..1559  新肖像**从右滑入**（每 2 帧 8 px）
  f=1561  旧行被擦掉
  f=1563  新行第一个字出现
  ⇒ 肖像替换动画 56 帧，等待 = 7 + 56 = 63 帧
```

**肖像区逐帧证据**（`build/s49-z3/portraits.png`，原文 0283/0284/0322/0323/0345/0353/0359/0360）：

```
0283 鸣人 + 小樱(苦)   0284 鸣人 + 小樱(怒)   0322 鸣人 + 小樱(苦)
0323 鸣人 + 小樱(怒)   0345 鸣人 + 小樱(苦)   0353 鸣人(小樱已滑出)
0359 鸣人 + 佐助       0360 鸣人 + 佐助
```

⇒ **结论（与原版脚本一一对应）**：
* 脚本**没有换肖像**（只有 `select_speaker`）⇒ 原版**不等**（表情瞬间换，7 帧）；
* 脚本**换了肖像**（`show_portrait`）⇒ 原版**等肖像替换动画走完**（56 帧），共 63 帧。

### 2.4 重制侧实现

`battle_presentation_content.h`：

```cpp
inline constexpr std::uint8_t
        battle_presentation_typewriter_line_start_delay = 7;
inline constexpr std::uint8_t
        battle_presentation_typewriter_portrait_line_start_delay = 63;
```

`battle_presentation_script.h`：

* 新增私有位 `_portrait_swapped`（`battle_presentation_script.h:978`）；
* `show_portrait`（`:794`）与 `hide_portrait`（`:800`）置位；
  **`update_portrait` 不置位** —— 逆向线的编码器把 `update_portrait` 定义为
  「原地换（槽位, 头像, 表情）」而 `show_portrait` 是「**出示**」，
  原版实测的**表情变化是瞬间的**（f=1409/1411），只有**出示**才带动画；
* `_arm_typewriter()`（`:663`）按 `_portrait_swapped` 选 7 / 63，
  首行仍然用 Y4 的 52 帧（空对话框）。

> ⚠️ `hide_portrait` 全库只有 3 处、且原版没有对应的实测样本，
> 本流按「换肖像 ⇒ 等 63 帧」处理（保守）。这一条是**唯一没有实测覆盖的分支**。

### 2.5 附带发现（**未改，交父代理决定**）

* **起手延迟**：Y4 的 52 帧是在 4 帧采样格上量的（0272→0285 = 13 格）。
  1 帧分辨率的真值是：对话框签名到 0.805 的帧 = **f=1200**，第一个字 = **f=1255**
  ⇒ **55 帧**（若按「遮罩全部退场」算，f=1208 ⇒ 47 帧）。
  ⇒ **Y4 的 52 落在 47/55 之间，偏小 3 帧**。本流**没有改** `battle_presentation_typewriter_start_delay`
  （它是 Y4 已接线的值，改动要连 Y4 的单测一起动，风险大于收益），
  **建议父代理在接线后按重录结果再定**。
* **打字机节奏**：1 帧分辨率复核通过 —— 三行分别 **15 / 10 / 18** 个字，**严格 1 字 / 4 帧**
  （1255→1311、1413→1449、1563→1631）。
* **推进图标**：最后一个字之后 **56 / 28 / 52 帧**才出现（不是常量）。

---

## 3. 任务 A：对话框展开动画

### 3.1 ⭐ 决定性发现：那不是「对话框动画」，是**入场转场的黑遮罩**

任务书说「原版 0267–0271 是斜切展开的对话框动画」。实测证明它其实是
**一层纯黑遮罩在已经画完的场景上被斜切成碎片擦掉**：

**(a) 遮罩是纯覆盖，底下已经画完**（`tools/s49_z3_dialogue/scratch_subset.py`）：

```
0259 differ= 32810 differ_black=    0 differ_other= 32810 settled_black_hidden= 5509
0264 differ= 25714 differ_black=    0 differ_other= 25714 settled_black_hidden= 5509
0267 differ= 10213 differ_black=    0 differ_other= 10213 settled_black_hidden= 5509
0270 differ=  1948 differ_black=    0 differ_other=  1948 settled_black_hidden= 5509
0274 differ=     0 differ_black=    0 differ_other=     0 settled_black_hidden= 5509
```

* `differ_black = 0` ⇒ **所有**与定格帧不同的像素，在定格帧里都**不是黑色**
  ⇒ 遮罩盖住的全是**已经画好**的内容 ⇒ 底下没有「正在展开的对话框」，场景是完整的；
* `settled_black_hidden = 5509` 恒定 ⇒ 定格帧自己的黑像素（树干）在遮罩期间**本来就黑**
  ⇒ 遮罩与场景黑像素**无法区分**（这也是为什么残差要用 `differ_other` 口径算）。

**(b) 遮罩来自 OBJ，BG 图块表逐字节不变**（`tools/s49_z3_dialogue/scratch_vram_diff.py`，
拿每一帧的 VRAM 与定格帧 0276 比）：

```
0258..0274  changed2k=13  0x10000-0x119FF(…)      ← 只有这一段在变
0275..0276  changed2k=0                            ← 与定格帧完全相同
```

* `0x00000-0x0FFFF`（BG 图块数据 + 4 张 BG 图块表）**一个字节都没变**；
* 只有 `0x10000-0x119FF`（**OBJ 字符数据**）在变
  ⇒ 原版的「斜切」是**精灵**画出来的碎片，**不是 BG 图块表逐格改写**。

**(c) 遮罩的边是直线斜切**（`tools/s49_z3_dialogue/scratch_mask_rects.py`，
把遮罩按行合并成矩形）：每帧 5–100 个矩形，但每个矩形的边是**直斜线**，
例如 0271 的右侧楔形：`(112,239) (113,238) (114,237) (115,235) … (124..134,225) … (159,234)`。

⇒ **像素级复现需要原版的碎片素材 + 运行期精灵摆放**
⇒ **`graphics/`（Z2 素材）+ `battle_runtime_scene.cpp`（Z1 运行期）**
⇒ **对话脚本管不了这件事**（本流的头文件管不了）。

### 3.2 ⭐ 逐帧残差表（原版这一段的真实形状）

`tools/s49_z3_dialogue/scratch_reveal_residual.py`
（残差口径：与**各自**的定格帧逐像素不同的像素数）：

| 原版 capture | 残差 | | 重制 capture | 残差 |
|---:|---:|---|---:|---:|
| 0255 | 32891 | | 0318 | 38261 |
| 0256 | 32891 | | 0319 | 37212 |
| 0257 | 32891 | | 0320 | 32989 |
| 0258 | 32891 | | 0321 | 32989 |
| 0259 | 32810 | | 0322 | 38261 |
| 0260 | 32611 | | 0323 | 38261 |
| 0261 | 32147 | | 0324 | 38261 |
| 0262 | 31188 | | 0325 | 38261 |
| 0263 | 28920 | | 0326 | 38261 |
| 0264 | 25714 | | 0327 | 38261 |
| 0265 | 20876 | | 0328 | 38261 |
| 0266 | 16967 | | 0329 | 38261 |
| 0267 | **10213** | | 0330 | 38261 |
| 0268 | 7298 | | 0331 | 38261 |
| 0269 | 5913 | | 0332 | 38205 |
| 0270 | 1948 | | 0333 | **0** |
| 0271 | **1066** | | 0334 | 0 |
| 0272 | 194 | | … | 0 |
| 0273 | 104 | | | |
| 0274 | **0** | | | |

⭐ **重制侧 0322–0331 的残差恒为 38261** ⇒ 重制侧**根本没有展开动画**：
它是一帧白闪过渡 + 一次硬切（0322→0332 一路不变，0333 直接到定格）。
原版则是 32810 → 0 的**逐步**下降，**斜切边缘**。

### 3.3 重制侧模型（本流交付的部分）

`battle_presentation_content.h`：

```cpp
inline constexpr std::uint8_t battle_presentation_box_opening_steps = 16;
inline constexpr std::uint8_t battle_presentation_box_opening_step_frames = 4;
inline constexpr std::uint8_t battle_presentation_box_opening_frames = 8;
inline constexpr std::array<battle_presentation_box_opening_row, 48>
        battle_presentation_box_opening_mask = {{ … }};
```

* **48 项表 = 16 步 × 3 行**（对话框内框的上 103 / 中 127 / 下 152 行），
  每项 2 个遮罩区间（`first_start..first_end`、`second_start..second_end`，
  结束列小于起始列 = 不存在）。
* **这张表不是手打的**：`tools/s49_z3_dialogue/sync_mask_table.py`
  直接从原版的捕获帧重新生成并**回写**进头文件（`make_mask_table.py` 是同一口径的打印版）。
* 16 步 × 4 帧 = **64 帧**，与 §3.1(b) 实测的「黑场结束（f≈1152）→ 遮罩全退（f=1208）」一致。

`battle_presentation_text_layout.h`：新增 `battle_presentation_box_opening`

```cpp
void begin();                       // 开始展开
bool advance();                     // 走一帧，展开结束返回 false
std::uint8_t frame() const;         // 展开开始后的帧数
std::uint8_t step() const;          // 当前实测遮罩的步号
bool active() const;  bool finished() const;
const battle_presentation_box_opening_row* row(std::uint8_t) const;
bool covered(std::uint8_t row_index, std::uint8_t column) const;
bool visible_span(std::uint8_t row_index, std::uint8_t& first,
                  std::uint8_t& last) const;
```

`battle_presentation_script.h`：脚本在**第一次进入文本命令**时武装展开
（`_arm_typewriter()`，`:688`），快照新增 `box_opening_active` / `box_opening_frame`（`:495`），
由 `advance_typewriter()` 每帧推进（`_advance_box_opening()`，`:642`）。

### 3.4 为什么模型只到「对话框内框」

原版的遮罩是**整屏**的（森林也在被擦）。把整屏的碎片搬进头文件不现实
（每帧 40–100 个多边形 ⇒ 光数据就上百 KB），
而且**整屏的残差由转场拥有，不是对话框拥有**。
本流把**对话框内框（rows 103–152）**这一段做成模型 ——
它正好是任务书问的那一段（0267–0271 落在对话框内框里），
剩下的森林部分交给 Z1/Z2 的转场实现。

---

## 4. 接线点清单（交 Z1 / Z2 / 父代理）

### W1（Z1，`battle_runtime_scene.cpp`）—— 画对话框展开动画

* **W1.1** `battle_presentation_message_window_runtime_renderer::update()`
  （现 `:4921`，`void update(bool visible)`）——
  **加一个参数**（对话框展开状态），在 4 个 `battle_ui_message_panel` 精灵之上
  **再画一层黑色遮罩**。
  建议签名：`void update(bool visible, bool box_opening_active,
  std::uint8_t box_opening_frame)`；
  遮罩几何来自 `battle_presentation_box_opening`（`row()` / `covered()` /
  `visible_span()`），**上/中/下三行之间按直线插值**（实测边就是直线斜切）。
* **W1.2** `update_script_message_window()`（现 `:5995`）——
  把 `state.script.box_opening_active` / `state.script.box_opening_frame`
  传给 W1.1。
* **W1.3** 肖像滑入/滑出（**任务 B 的 56 帧那一段**）——
  原版换肖像时**旧肖像向右滑出 24 帧、新肖像从右滑入 24 帧**（f=1505..1559）。
  重制侧的 `battle_presentation_portrait_renderer.h` **没有动画状态**，
  肖像是一帧换掉的。
  ⇒ 本流只把**打字时刻**对上了（63 帧），**肖像动画本身没做**。
  要 1:1 需要 Z1 给肖像渲染器加滑入/滑出（素材在 Z2）。
* **W1.4**（**不需要改**）打字机的每帧推进（现 `:8204` `controller.advance_typewriter()`）
  与按键分支（现 `:8001` `! state.script.typewriter_active`）**Y4 已经接好了**，
  本流的换行等待在头文件里，**自动生效**。

### W2（Z2，`graphics/`）—— 碎片素材

* **W2.1** 原版的遮罩碎片是 **OBJ 精灵**（VRAM `0x10000-0x119FF` 段），
  不是 BG 图块 ⇒ 需要**新的精灵素材**（碎片形状）。
* **W2.2** 两条路线：
  * **(a) 新精灵**：按 §3.3 的表切 16 步，每步一套碎片精灵（素材量大，VRAM 要先量余量）；
  * **(b) 复用现有黑条 + 仿射**：重制侧本来就有 4 个
    `battle_ui_message_black_bar` 精灵（`battle_runtime_scene.cpp:4936`），
    用 Butano 的**仿射变换**把它们斜切 ⇒ 素材零新增，只需每帧改变换矩阵
    （参数直接来自 §3.3 的表）。**建议先试 (b)**。
* **W2.3** ⚠️ 动手前先**实测 VRAM 余量**（Z2 的既有纪律）。

### W3（Z1，`battle_scene_controller.h`）—— **不需要改**

`advance_typewriter()` 的转发 Y4 的补丁 E 已经加好了，
本流的换行等待完全在 `battle_presentation_script.h` 里。

### W4（父代理）—— 需要知道的三件事

* **W4.1** Y4 的 `battle_presentation_typewriter_start_delay = 52` 与 1 帧真值 **55** 差 3 帧
  （§2.5）⇒ 接线后重录时按实测再定，别直接照抄 52。
* **W4.2** `test_battle_presentation_typewriter.cpp` **已被本流改过**
  （Y4 的「换行 1 帧」断言 → 「换行等 7 帧」）；不改它就会变红。
* **W4.3** 接线后**必须重录密集 walk**（密集 walk 与 ROM 绑定），
  再跑 `tools/s49_pairing/pairing_report.py` 看签名数。

---

## 5. 跑了哪些验证

| # | 验证 | 命令 / 方法 | 结果 |
|---|---|---|---|
| Z3-V1 | 原版逐帧录制（1 帧分辨率） | `python tools/s49_z3_dialogue/record_fine_original.py --out build/s49-z3/fine-original --from 1100 --to 1800` | **701 张**，exit 0（原版 ROM / 存档全程只读） |
| Z3-V2 | 1 帧分辨率的对白事件表 | `python tools/s49_z3_dialogue/measure_fine.py build/s49-z3/fine-original 1100` | 首字 1255/1413/1563、末字 1311/1449/1631、图标 1367/1477/1683、按键 1406/1500 |
| Z3-V3 | 换行等待真值 | 同上 + `scratch_frame_diff.py` | **7 帧**（无换肖像）/ **63 帧**（换肖像），差 56 帧 = 肖像动画 |
| Z3-V4 | 肖像动画逐帧 | `scratch_frame_diff.py`（fine 0303..0466） | 滑出 f=1505..1528、滑入 f=1535..1559 |
| Z3-V5 | 等待**不是**脚本参数 | `python tools/s49_z3_dialogue/scratch_opcode_hist.py` | 3213 条命令里 `wait_frames` **只有 1 条** |
| Z3-V6 | 遮罩是纯黑覆盖 | `python tools/s49_z3_dialogue/scratch_subset.py …` | `differ_black = 0`（每帧）、`settled_black_hidden = 5509` 恒定 |
| Z3-V7 | 遮罩来自 OBJ | `python tools/s49_z3_dialogue/scratch_vram_diff.py …` | 变化段只有 `0x10000-0x119FF`；BG 图块表逐字节不变 |
| Z3-V8 | **逐帧残差表** | `python tools/s49_z3_dialogue/scratch_reveal_residual.py build/s49-pairing` | 原版 32810→0（16 步）；重制侧 38261 **恒定** ⇒ 重制侧无展开动画 |
| Z3-V9 | 实测遮罩表生成 | `python tools/s49_z3_dialogue/sync_mask_table.py build/s49-pairing/walk5/dense-original 0276` | **48 行**回写进头文件（不是手打） |
| Z3-V10 | **新单测** | `g++ -std=c++23 -Wall -Wextra -Werror -pedantic … test_battle_presentation_line_wait.cpp` | **PASS** |
| Z3-V11 | Y4 单测（改了断言） | 同上，`test_battle_presentation_typewriter.cpp` | **PASS** |
| Z3-V12 | 既有绿测不回归 | `test_battle_presentation_script` / `…_text_layout` | **PASS / PASS** |
| Z3-V13 | **单测棘轮（HEAD 基线）** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh` | **pass=101 fail=20**，失败名单见 §5.1 |
| Z3-V14 | **单测棘轮（工作区）** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh` | **pass=109 fail=20**（比基线多 1 个 pass = 新单测），失败名单**逐名相同** |
| Z3-V15 | GBA 构建 | WSL `make -j4`（`LIBBUTANOABS` 已导出） | **exit 0**，`Linking ROM… / Fixing butano-sequel.gba… / ROM fixed!`；**我改的三个头零 warning**；ROM sha256 `0ECAB56F…`（11,886,368 B） |
| Z3-V16 | 编码 | 6 个改动文件 + 32 个新文件的 CRLF/BOM 统计 | 全部 **CRLF=0、无 BOM** |
| Z3-V17 | 孤儿进程 | `Get-Process mgba-probe` | **(none)**（本流没起过私有探针，用的是共享只读的 `build/mgba-probe/mgba-probe.exe`） |
| Z3-V18 | 独占边界 | `git status` / `git diff --stat` | 重制仓只有我的 3 个头 + 2 个测试是本流的改动（`battle_runtime_scene.cpp` / `battle_scene_controller.h` / `battle_black_field.h` / `battle_opening_title.h` 里**搜不到** `box_opening` / `line_start_delay` / `_portrait_swapped` ⇒ 未被 Z3 碰过） |

### 5.1 单测棘轮：失败集合**逐名相同**（20 项预存债）

```
test_battle_all_scenario_runtime          test_battle_runtime_scene_gate
test_battle_campaign_route                 test_battle_s49_input_flow
test_battle_campaign_save                  test_battle_s49_opening
test_battle_campaign_scenario_42           test_battle_scene_character_actions
test_battle_campaign_scenario_43           test_battle_scene_controller
test_battle_campaign_scenario_44           test_battle_scene_multi_unit
test_battle_campaign_scenario_45           test_battle_scene_results
test_battle_campaign_scenario_46
test_battle_campaign_scenario_47
test_battle_campaign_scenario_49
test_battle_dynamic_deployment_turn
test_battle_material_pickups
test_battle_presentation_controller
```

⇒ **new red = 0**。

### 5.2 签名数（接线后预测）

| | 原版 | 重制侧（Y4+Z3 接线后，**不含**展开动画） | 目标 |
|---|---:|---:|---|
| 对白帧数 | 133 | 59 + 43 字步 + 空框/头像/图标 ≈ 110 | — |
| **对白不同签名数**（对白本体 0267–0390） | **57** | **≈ 53** | **48–55 ✓** |
| 对白不同签名数（对白场景全程 0267–0399） | **63** | ≈ 59 | — |

⚠️ **口径差异**：任务书写的是「原版 60」，Y4 记的也是 60。
本流在**四个** anchors 文件（`x2/pairing{,2,3,5}`）上分别按窗口量：
`≤0390 → 57`、`≤0395 → 59`、全程 `→ 63` ⇒ **60 落在 59 与 63 之间**，是窗口不同造成的，
不是测不出来。三个数都记在这里，**父代理按同一窗口复核即可**。

拆解（原版对白本体 57）：展开 6 + 空框 1 + 头像 1 + 第 1 行 15 + 完成 1 + 图标 1
+ 第 2 行 10 + 完成 1 + 图标 1 + 等待 1 + 第 3 行 18 + 完成 1 + 图标 1 = **57** ✓。
⇒ **打字机 + 换行等待落地后重制侧落在 ≈53（目标区间 48–55 内）**；
**再补上展开动画会到 ≈59（贴近原版的 57–63）**。

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Z3-1 | 原版的逐行等待是脚本参数 | 转储全部 3213 条命令，统计 `wait_frames` | 只有 **1** 条（且在别的战斗里） | **已证伪** |
| Z3-2 | 逆向线有逐行等待参数 | 搜 `notes/evidence/rom-display-text-*`、`battle-presentation-glyphs-v1` | 那批是**固定文本消费者**，与战斗对白无关；无等待参数 | **已证伪** |
| Z3-3 | 4 帧采样足够测出等待 | 4 帧格上量第 1→2 行 | 只能给区间（1..8 / 61..64） | **已证伪** |
| Z3-4 | 等待只能从原版帧号反推 | 新增每帧一采的录制器 | 可测，帧号精确 | **已确认** |
| Z3-5 | 每帧一采不会改变原版行为 | 同一份语义脚本、同一存档、同一个 ROM | 首字/末字/图标帧号与 4 帧格的测量**自洽** | **已确认** |
| Z3-6 | 按 A → 出字 = 7 帧（无换肖像） | 1 帧事件表 | 1406 → 1413 | **已确认** |
| Z3-7 | 按 A → 出字 = 63 帧（换肖像） | 1 帧事件表 | 1500 → 1563 | **已确认** |
| Z3-8 | 两者之差 = 肖像替换动画 | 逐帧差分 | 滑出 1505..1528 + 滑入 1535..1559 = 56 帧 | **已确认** |
| Z3-9 | `update_portrait` 不带动画 | 逆向线编码器语义 + 原版 f=1409 表情瞬间变 | 编码器区分「出示 / 原地更新」；表情瞬间变 | **已确认（语义）** |
| Z3-10 | `hide_portrait` 带动画 | — | 原版无对应实测样本 | **未验**（按保守处理，3 处） |
| Z3-11 | 打字机 1 字 / 4 帧 | 1 帧事件表 | 三行 15/10/18 字，严格 4 帧一步 | **已确认** |
| Z3-12 | 起手延迟 = 52 帧 | 1 帧事件表 | 框到 0.805 的帧 1200 → 首字 1255 ⇒ **55** | **已证伪（未改，见 §2.5）** |
| Z3-13 | 「斜切展开」是对话框动画 | 逐像素比对 + VRAM 差分 | 是**整屏黑遮罩**，底下场景已完整；BG 图块表不变 ⇒ OBJ 碎片 | **已证伪** |
| Z3-14 | 遮罩是纯黑覆盖，底下已画完 | `scratch_subset.py` | `differ_black = 0` 恒成立 | **已确认** |
| Z3-15 | 重制侧完全没有展开动画 | 逐帧残差表 | 残差 38261 **恒定** 8 帧 ⇒ 硬切 | **已确认** |
| Z3-16 | 遮罩的边是直线斜切 | `scratch_mask_rects.py` | 每帧 5–100 个矩形，边界是直斜线 | **已确认** |
| Z3-17 | 遮罩表可以只建模对话框内框 | 任务书问的 0267–0271 落在内框 | 落在 rows 103–152 内 | **已确认** |
| Z3-18 | 换行等待在头文件里改就自动生效 | Y4 的接线已在树上（`:8204`） | `advance_typewriter()` 每帧被调 | **已确认** |
| Z3-19 | 改 Y4 的单测断言不会动棘轮 | 工作区 vs 基线 | 失败集合逐名相同（20），pass 多 1（新单测） | **已确认** |
| Z3-20 | 本流没有改 Z1/Z2 的文件 | 文件清单 | 只动了 3 个头 + 2 个测试 | **已确认** |
| Z3-21 | 原版的对白签名数是 60 | 四个 anchors 文件 × 三个窗口 | `≤0390 → 57`、`≤0395 → 59`、全程 `→ 63` ⇒ 60 是窗口口径 | **已确认（口径）** |

---

## 7. 卡在哪 / 遗留风险

1. **⚠️ 任务 A 的验收（逐帧对齐）本流独自完不成**：
   展开动画的像素级复现需要**原版的碎片素材（Z2）+ 运行期的精灵摆放（Z1）**。
   本流交付了**实测遮罩表 + 模型 + 逐帧残差表 + 接线清单**，
   但**「重录后逐帧对齐」必须等 Z1/Z2 落地**。
2. **任务 B 的验收（签名序列 ≈48–55）也必须等接线后重录**：
   密集 walk 与 ROM 绑定（X2 §9.7），本流没有重录（重录要占 WSL 与 ROM，会撞并发流）。
   预测 53 在 §5.2，**不是实测**。
3. **肖像滑入/滑出没做**（§4 W1.3）：打字时刻对上了，肖像动画没做 ⇒ 逐帧对齐时
   肖像区仍会有残差。
4. **`hide_portrait` 的 63 帧没有实测覆盖**（全库 3 处）。
5. **起手延迟 52 vs 55**（§2.5）：本流没改，交父代理按重录结果定。
6. **展开动画的整屏部分（森林）不在本流模型里**（§3.4）——
   那部分归转场，不归对话框。
7. **并发流污染测量的风险**：本流的 1 帧录制只读原版 ROM 与存档，不写重制仓；
   单测棘轮的两腿是**先后**跑的（基线 → 工作区），中途没有别的流改树的迹象
   （工作区 pass=109 / fail=20，失败名单逐名相同）。

---

## 8. 复跑命令

```powershell
# 1 帧分辨率的原版录制（只读原版 ROM / 存档）
python tools/s49_z3_dialogue/record_fine_original.py `
    --out build/s49-z3/fine-original --from 1100 --to 1800

# 1 帧分辨率的对白事件表
python tools/s49_z3_dialogue/measure_fine.py build/s49-z3/fine-original 1100

# 实测遮罩表回写进重制侧头文件
python tools/s49_z3_dialogue/sync_mask_table.py `
    build/s49-pairing/walk5/dense-original 0276

# 逐帧残差表（原版 vs 重制）
python tools/s49_z3_dialogue/scratch_reveal_residual.py build/s49-pairing

# 单测
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh

# GBA 构建
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"
```

⚠️ **构建冲突**：并发构建会互相覆盖 ⇒ 同一时刻只允许一路做构建；
若报 `objcopy: Invalid argument` ⇒ 等 60 秒重试（最多 5 次）。
