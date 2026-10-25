# W24-G1 —— 「呈现状态」对齐（wave 24 / G1 流）

> 2026-10-25 23:40 – 2026-10-26 01:2x · wave 24 / G1 流 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`W20-EXEC-BRIEF.md` · `W23-F3-step12-residual.md`（直接上游）· `W23-F2-prepare-box.md` · `W23-PARENT-wrapup.md` §1
> lane 副本：`D:\Github\gba-naruto\build\w20-e1\butano-sequel`（含 D1 的过场实现）
> 独占：`game/include/konoha/battle_presentation_script.h` · `game/src/battle_runtime_scene.cpp` · `graphics/battle_ui_prepare_box.{bmp,json}`
> ⛔ 未改：`battle_black_field_star_mask.h` · `battle_result_content.h` · `battle_ui_model.h` · `battle_presentation_content.h` · `battle_scene_controller.h`
> 本流新增工具：`tools/s49_w24g1/`（`script_telemetry.py` · `apply_g1_edits.py`）

---

## 0. 一句话结论

> ⭐⭐⭐ **F3 的根因诊断成立（缺的是「呈现状态」），但它给的两个「修法」都用错了底图，而且真正的阻塞在别处：**
>
> 1. 原版 `step-12-A` 的背景**不是** `remake-17` 的对白背景，而是重制侧**已经有的**另一张资产
>    —— **`graphics/scenario_41_tutorial_bg.bmp`（y8..95 带逐像素 0 px 命中）**。
>    ⇒ 「背景落位」这一半的修法是**切到入场背景**；用错底图会白留 **9,954 px**。
> 2. ⭐⭐⭐ **脚本侧不缺「空框」状态**：battle 14 / selector 1 的脚本第一条指令就是
>    `render_encoded_text`（**没有 `wait_frames`**）⇒ `begin()` 之后 `message_window_visible` 立即为真。
> 3. ⭐⭐⭐ **真正的阻塞 = 过场入场过渡（黑场 + 星形遮罩）的时机晚了一拍**：
>    重制侧 walk 的落点（`remake-16`）**落在 90 帧入场淡入的里面**（遥测 `render_stage = 100`），
>    所以那一拍画面必然是「地图 + 过渡」；而原版的 `orig-12` 已经在过渡之后（场景 + 空框）。
>    ⇒ **单靠呈现状态的改动改不动 `step-12-A`**，必须先让入场过渡早一拍收尾
>    （**`battle_black_field_star_mask.h` = wave 24 另一路的文件**）。
>
> ⭐ 本流已实现「入场背景 + 空框」的**全部管线**（中性，实测无回归），并把改动的**精确依赖条件**测了出来。

---

## 1. ⭐ 新证据（本流实测，全部可复算）

### 1.1 ⭐⭐⭐ 原版 `step-12-A` 的背景 = 重制侧的 `scenario_41_tutorial_bg`（**0 px**）

把重制侧 `graphics/` 里**所有 256×256 的 BG 资产**逐个与原版 `step-12-A.png` 的
`y8..95` 带（森林 + 草地，20,880 px）比对：

| 资产 | 与 orig-12 的 y8..95 带差 |
|---|---:|
| ⭐ **`scenario_41_tutorial_bg.bmp`** | **0 px** ⭐ |
| `scenario_41_postbattle_dialogue_1_bottom.bmp` | 4,524 px |
| `scenario_41_postbattle_dialogue_page_1.bmp` | 4,795 px |
| `battle_ui_dialogue_background.bmp`（= 原版 step-13 的背景） | 9,954 px |

⇒ **原版的「过场开场」底图在重制侧是现成的资产**，`battle_ui_dialogue_background` 是**另一张**图
（sha256 `37db2388…` vs `a615ba10…`）。

**并且这两张图不是同一张图的平移**：

* 全屏平移探针 ±8×±8（森林带）：最佳 = `dx=0, dy=0`（4,992 px）⇒ 平移救不回来；
* 资产对资产：`tutorial_bg` 与 `dialogue_background` 在 ±120×±40 的粗网格里无命中（最优 16,961 px）。

### 1.2 ⭐⭐ `orig-12` 与 `orig-13` 的背景差**不是**调色板、淡入或平移

| 检验 | 方法 | 结果 |
|---|---|---|
| 换调色板？ | 把 o13 的每个颜色映到 o12 的颜色，看是否一一对应 | ⛔ **否**：135 个 o13 颜色里 **106 个**对应多个 o12 值 |
| 整体变暗（淡入）？ | 逐像素试 `k/16` 缩放 | ⛔ **否**：9,474 px 既不是黑也不是 o13 的缩放 |
| 平移？ | ±8×±8 逐像素 | ⛔ **否**：最佳 `(0,0)` 仍是 4,992 px |

⇒ **两张不同的图**（森林 + 草地两带分别差 4,992 / 4,962 px）。

### 1.3 ⭐⭐ 重制侧 `step-16-A` 画的是**战斗地图**，不是「另一个过场场景」

`build/w22-d1/capture-remake-v4/step-16-A.png` = 亮绿灌木 + 草地 + 2 块岩石 + **左右黑楔**
（相机已越过地图边缘 ⇒ 处在过场机位）。
`step-17-A` 才是过场背景（= 原版 `step-13` 的底图，森林 + 草地 **0 px** 差）。

⇒ F3 §1 的「亮绿灌木 / 另一处场景」就是**战斗地图本身**，不是过场背景的另一版。

### 1.4 ⭐⭐ 脚本侧**不缺**「空框」状态

解析 `generated_battle_presentation_content.h`：
battle 14 的定义 = `battle_presentation_definition{ 14, 629, 629, 46, 139, 11 }`
⇒ case 区 = 139..149，selector 1 的 case = `command_offset 1235, command_count 9`：

| # | opcode | 含义 |
|---|---|---|
| 0 | `0x12` | `initialize_portrait_pair` |
| 1 | `0x08` | `select_message_speaker` |
| 2 | `0x01` | **`render_encoded_text`** ← 第一条就是文字 |
| 3 | `0x08` | `select_message_speaker` |
| 4 | `0x01` | `render_encoded_text` |
| 5 | `0x02` | `render_parameterized_encoded_text` |
| 6 | `0x08` | `select_message_speaker` |
| 7 | `0x01` | `render_encoded_text` |
| 8 | `0x00` | `end` |

⇒ **没有 `wait_frames`（`0x0F`）** ⇒ `battle_presentation_script::begin()` → `_advance_to_block()`
在第一次循环就走到 `render_encoded_text` ⇒ `_state.message_window_visible = true`。
⇒ **「空框」在脚本里天然存在**（`battle_presentation_typewriter_start_delay` 的 52 帧空框延迟也在）。
⇒ **缺的只是「过场入场那一拍」**：脚本/对白背景比原版晚一拍。

### 1.5 两个 gate（决定了那一拍画什么）

| 位置 | 条件 | 后果 |
|---|---|---|
| `battle_runtime_scene.cpp` `update_script_message_window()` | `phase == script_blocked && !presentation_busy && script.message_window_visible` | 过场入场演出未结束时**空框也不画** |
| `battle_runtime_scene.cpp` `dialogue_background_requested` | `battle_id == 14 && phase == script_blocked && script.selector == 1 && !presentation.busy()` | 同上 ⇒ **地图留在屏上** |

⇒ 两处都指向 **wave 24 另一路的 `battle_black_field_star_mask.h`**（黑场 + 星形遮罩的时长）。

### 1.6 ⭐⭐⭐ 决定性证据：重制侧 `step-16-A` 的落点**落在 90 帧入场淡入的里面**

用本流私建探针读**新录制**的 `.ss9` 里的遥测（`tools/s49_w24g1/script_telemetry.py`，
遥测地址 `0x0202A570`）：

| 遥测字段 | `remake step-15-A` | ⭐ `remake step-16-A` | `remake step-17-A` |
|---|---:|---:|---:|
| `phase` | 4294967293（部署） | **18 = `script_blocked`** | 18 |
| `scene_frame` | 559 | **0** | 42 |
| `script_phase` / `script_selector` | 0 / 0 | **1 / 1** | 1 / 1 |
| `script_command_index` | 0 | **2**（= 第一条 `render_encoded_text`） | 2 |
| `script_message_window_visible` | 0 | **1** | 1 |
| `script_portrait_0_visible` / `_1_visible` | 0 / 0 | **1 / 1** | 1 / 1 |
| `presentation_busy` | 0 | **0** | 0 |
| ⭐ `render_stage` | 0 | **100** | 7 |

`render_stage = 100` 只在 `battle_runtime_scene.cpp:8861` 被写一次 ——
**紧跟在场景建立时创建地图 BG 的那一行之后、90 帧黑场淡入循环（`:8869-8894`）之前**。

⇒ ⭐⭐⭐ **落点那一帧还在场景建立的淡入循环里** ⇒ 屏上必然是「场景建立时创建的**地图**」
（过场机位 ⇒ 左右黑楔）⇒ **和呈现状态无关**。
⇒ 同时说明：**脚本的第一行是在淡入里打完的**（淡入 90 帧 > 首行延迟 52 帧），
所以「空框」状态**不可能**出现在可见帧上。

### 1.7 ⭐⭐ 原版的同一拍**已经过了过渡**

原版 `orig-11` = 黑场 + 星形（过渡中），`orig-12` = 场景 + 空框（过渡**已结束**）；
重制侧 `remake-15` = 黑场，`remake-16` = **仍在过渡里**。
⇒ **重制侧的入场过渡比原版晚一拍收尾** ⇒ 这是 `step-12-A` 的真正阻塞。

---

## 2. 改动（lane 副本 `build/w20-e1/butano-sequel`）

### 2.1 `game/src/battle_runtime_scene.cpp`（本流独占，7 处编辑 + 1 处 include）

| # | 改什么 | 为什么 |
|---|---|---|
| 1 | 新增 `battle_cutscene_entry_background(state, battle_id)`：**battle 14 且相位 = `script_blocked` 且脚本还没说过话**（`!state.script.portraits_revealed`）⇒ 「过场入场背景」 | `portraits_revealed` 是运行时自己的「脚本说过话」标志（第一个字形时置真、脚本运行期间不再清）⇒ 稳定、不会在换行时闪 |
| 2 | `battle_dialogue_background_runtime_renderer` 支持**两张**背景：入场 = `scenario_41_tutorial_bg`，对白 = `battle_ui_dialogue_background`；切换时先释放旧的（并像原来一样先 `map.reset()` 释放地图 BG，因为两张都是 8bpp 全屏 BG） | §1.1：入场底图 = `scenario_41_tutorial_bg`（0 px 命中） |
| 3 | `dialogue_background_requested`：**入场那一拍不再被 `!presentation.busy()` 挡住** | 原版在场景落位时就已经有底图 |
| 4 | `update_script_message_window()`：新增 `cutscene_entry` 入参；**入场那一拍画空对话框**（不再要求脚本已经到达文字指令） | §1.4：脚本第一条就是文字，但脚本晚一拍 ⇒ 空框状态在那一拍取不到 |
| 5 | `#include "bn_regular_bg_items_scenario_41_tutorial_bg.h"`（Butano 为每个资产生成一个头文件，**没有**聚合头） | 编译错误 `not a member of 'bn::regular_bg_items'` 的修法 |

> ⛔ **本流没有改 `battle_presentation_script.h`**：§1.4 证明脚本侧**已经**有「空框」状态，
> 改那里是多余的（父代理的 R-F3-1 的一半前提需要更正）。
>
> ⚠️ **本改动实测中性**（§3）：入场背景的判定条件 `!portraits_revealed` 在 battle 14 的这一拍
> **为假**（遥测：两个肖像都已可见，因为第一行在淡入里就打完了）⇒ 入场背景**从未被选中**。
> ⇒ **它要在 R-G1-A（黑场早一拍收尾）+ R-G1-B（首行延迟 ≥ 90）落地后才会真正生效**。

### 2.2 应用方式

`python tools/s49_w24g1/apply_g1_edits.py`（7 处替换，每处都断言「恰好命中一次」，
UTF-8 / LF / 无 BOM）⇒ 已在 lane 副本生效。

---

## 3. 验证（**全部实测**）

| 仪器 | 改前 | **改后** | Δ | 判读 |
|---|---:|---:|---:|---|
| ⭐ **25 帧合计（固定偏移 +4，`align_capture_steps.py`）** | **53,364 px** | **53,408 px** | **+44** | ⭐ **中性**：+44 全部落在 `step-13-A`，原因是**打字机落点抖动**（新录制的 `scene_frame` = 42，旧录制 = 44 ⇒ 少打 2 个字形）⇒ **与本流改动无关** |
| ⭐ **`step-12-A`（目标帧）** | **24,101 px** | **24,101 px** | **0** | ⛔ **未改善** —— §1.6/§1.7：那一拍**还在 90 帧入场淡入里面**（`render_stage = 100`）⇒ 呈现状态的改动够不着它 |
| ⭐ **判定台（arg-min，`s49_fidelity_report.py`）** | **38,047 px** | **36,452 px** | **−1,595** | ⭐ **中性**：−1,595 **全部落在 `step-24-A`**（w22 出包 2,778 px vs D1 lane 1,183 px）⇒ 正是 F3 §6-5 记的「那一帧对构建/ROM 敏感」，**不是本流的效果** |
| **黑场（纯黑帧）** | 58 帧 | ⛔ **未跑成** | — | 探针只落了 **334 / ~2,400 帧**（`frames_run 2480, frames_captured 334`）⇒ 无法与基线对比（见 §5 U-G1-8） |
| **单测** | pass=119 / fail=20 | 见 §3.4 | — | |
| **ROM 体积** | 12,258,628 B | **12,267,064 B** | **+8,436 B** | = 入场背景 `scenario_41_tutorial_bg` 的 8bpp 图块+调色板（89 tiles + 256 色 + tilemap） |
| **lane ROM sha256** | `40c41df98464da19…` | **`eb86122da316b5b4…`** | — | 本机构建非字节可复现 ⇒ 一切读数绑定本 sha |

### 3.1 ⭐ 25 帧逐帧 field px（**改前 → 改后**，`offset +4`）

| 原版帧 | 重制侧帧 | 改前 | **改后** | Δ |
|---|---|---:|---:|---:|
| `step-00-base` | `step-04-A` | 2,565 | 2,565 | 0 |
| `step-01-A` | `step-05-A` | 1,294 | 1,294 | 0 |
| `step-02-A` | `step-06-A` | 1,680 | 1,680 | 0 |
| `step-03-A` | `step-07-A` | 2,514 | 2,514 | 0 |
| `step-04-A` | `step-08-A` | 1,940 | 1,940 | 0 |
| `step-05-A` | `step-09-A` | 2,057 | 2,057 | 0 |
| `step-06-A` | `step-10-A` | 1,217 | 1,217 | 0 |
| `step-07-A` | `step-11-A` | 1,921 | 1,921 | 0 |
| `step-08-A` | `step-12-A` | 1,026 | 1,026 | 0 |
| `step-09-A` | `step-13-A` | 759 | 759 | 0 |
| `step-10-A` | `step-14-A` | 278 | 278 | 0 |
| `step-11-A` | `step-15-A` | 1,212 | 1,212 | 0 |
| ⭐ **`step-12-A`** | ⭐ **`step-16-A`** | ⭐ **24,101** | ⭐ **24,101** | **0** ⛔ |
| `step-13-A` | `step-17-A` | 195 | **239** | **+44**（打字机抖动） |
| `step-14-A` | `step-18-A` | 0 | 0 | 0 |
| `step-15-A` | `step-19-A` | 0 | 0 | 0 |
| `step-16-A` | `step-20-A` | 43 | 43 | 0 |
| `step-17-A` | `step-21-A` | 0 | 0 | 0 |
| `step-18-A` | `step-22-A` | 0 | 0 | 0 |
| `step-19-A` | `step-23-A` | 106 | 106 | 0 |
| `step-20-A` | `step-24-A` | 3,881 | 3,881 | 0 |
| `step-21-A` | `step-25-A` | 1,535 | 1,535 | 0 |
| `step-22-A` | `step-26-A` | 2,696 | 2,696 | 0 |
| `step-23-A` | `step-27-A` | 1,161 | 1,161 | 0 |
| `step-24-A` | `step-28-A` | 1,183 | 1,183 | 0 |
| **合计** | | **53,364** | **53,408** | **+44** |

> ⭐ **偏移仍是 +4**（未漂移），**没有一帧变差**（+44 是打字机抖动，两侧口径可解释）。
> ⭐ **逐帧 sha256**：只有 `step-17-A` 变了（打字机抖动），其余 24 帧**逐字节相同**。

### 3.2 判定台（arg-min 口径，`build/w24-g1/report.json`）

| 项 | 值 |
|---|---|
| field residual | min 0 / median 1,183 / max 9,520 / **sum 36,452** / zero 4 / 25 |
| full residual | sum **121,997** |
| attribution | identical 4 · product_diff 20 · pairing_diff 1（moment_mismatch 1） |
| content_sha256 | `fd6aecb4fd2b12c5…` |

### 3.3 复现命令

```powershell
# 录制（只重录重制侧；原版侧从 w22 出包复制）
python tools/s49_w24g1/capture_remake.py \
    --rom build/w20-e1/butano-sequel/butano-sequel.gba \
    --work-dir build/w24-g1/work \
    --original build/s49-package-w22/work/s49-report/capture-original

# 25 帧固定偏移对齐
python tools/s49_wave18/align_capture_steps.py \
    --original build/w24-g1/work/capture-original \
    --remake   build/w24-g1/work/capture-remake \
    --out      build/w24-g1/align-after.json

# 判定台
python tools/s49_fidelity_report.py --out build/w24-g1/report.json \
    --work-dir build/w24-g1/work \
    --remake-rom build/w20-e1/butano-sequel/butano-sequel.gba --skip-capture

# 遥测（本流新增）
python tools/s49_w24g1/script_telemetry.py \
    --remake-dir build/w24-g1/work/capture-remake \
    --rom build/w20-e1/butano-sequel/butano-sequel.gba \
    --exe build/mgba-probe-w24g1/mgba-probe.exe --steps 14,15,16,17,18
```

### 3.4 单测

`w18-run-all-tests.sh` ⇒ **pass=118 / fail=20**
⇒ **与 lane 的改前基线逐名相同**（D1 的 lane 基线就是 118/20，见 `W22-D1-transition.md` §8.1；
共享树的 119/20 与 lane 的 118/20 的那 1 项差是**改前就有的**，不是本流造成的）
⇒ **零新增失败**。

---

## 4. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **G1-H1** | 原版 `step-12-A` 的背景 = 重制侧的 `scenario_41_tutorial_bg` | 重制侧全部 256×256 BG 资产 × 原版 `step-12-A` 的 y8..95 带 | ⭐ **成立**：**0 px**（其它资产 ≥ 4,524 px） | **已确认** |
| **G1-H2** | 原版 `step-12` ↔ `step-13` 的背景差是「换调色板 / 淡入 / 平移」 | 调色板映射检验 + 缩放检验 + ±8 平移探针 | ⛔ **全部证伪** ⇒ **两张不同的图** | **已证伪** |
| **G1-H3** | 重制侧 `step-16-A` 画的是过场背景的另一版 | 目视 + 与地图/各资产比对 | ⛔ **证伪**：那是**战斗地图**（过场机位，左右黑楔） | **已证伪** |
| **G1-H4** | 脚本侧缺「空框」状态（F3 的 R-F3-1 前提） | 解析 battle 14 / selector 1 的 9 条指令 | ⛔ **证伪**：第一条就是 `render_encoded_text`，**无 `wait_frames`** ⇒ `begin()` 后 `message_window_visible` 立即为真 | **已证伪** |
| **G1-H5** | 那一拍没有对话框 / 没有对白底图，是因为 `!presentation_busy` / `!presentation.busy()` 两个 gate | 读 `update_script_message_window()` 与 `dialogue_background_requested` | ⛔ **部分证伪**：遥测显示 `presentation_busy = 0`、`message_window_visible = 1`、`selector = 1` ⇒ **两个 gate 都没有挡住**；真正的原因是**那一帧还在入场淡入里**（`render_stage = 100`） | **已证伪（被 G1-H7 取代）** |
| **G1-H6** | 切到 `scenario_41_tutorial_bg` + 空框 ⇒ `step-12-A` ≈ 195 px | 由 G1-H1（底图 0 px）+ 原版空框面积推得 | ⭐ **仍成立，但被前置条件卡住**：落点那一帧还在淡入里 ⇒ **必须先让入场过渡早一拍收尾**（G1-H7），否则改不动 | **已确认（附前置条件）** |
| **G1-H7** | ⭐⭐⭐ **重制侧 walk 的落点（`remake-16`）落在 90 帧入场淡入里面** ⇒ 那一拍必然显示「地图 + 过渡」，与呈现状态无关 | 读 `.ss9` 遥测的 `render_stage`（= 100，只能在场景建立 + 地图 BG 创建之后、淡入循环之前被写）+ 代码 `battle_runtime_scene.cpp:8861` / `:8869-8894` | ⭐ **成立** | **已确认** |
| **G1-H8** | ⭐⭐ **原版的同一拍已经过了过渡**（`orig-11` = 黑场+星形，`orig-12` = 场景+空框） | 原版 4 帧对照图 `build/w24-g1-orig-strip.png` + 原版逐帧结构表 | ⭐ **成立** ⇒ **重制侧的入场过渡比原版晚一拍收尾** | **已确认** |
| **G1-H9** | ⭐⭐ **脚本的第一行是在淡入里打完的**（淡入 90 帧 > 首行延迟 52 帧）⇒ 「空框」不可能出现在可见帧 | 遥测 `script_portrait_0_visible = 1` / `_1_visible = 1`（落点那一帧两个肖像都已可见）+ `battle_presentation_content.h:184`（`start_delay = 52`） | ⭐ **成立** | **已确认** |
| **G1-H10** | 本流改动是**中性**的（两个口径的 Δ 都能被已知的抖动解释） | 25 帧逐帧 sha256 + 两个口径的逐帧 Δ | ⭐ **成立**：+44 = `step-13-A` 的打字机落点抖动（`scene_frame` 44→42）；判定台 −1,595 = `step-24-A` 的构建敏感（F3 §6-5） | **已确认** |

---

## 5. 未完成项 / 接线请求

### 5.1 ⭐⭐⭐ 接线请求（按优先级）

| # | 文件 / 位置 | 改成什么 | 为什么（实测依据） |
|---|---|---|---|
| ⭐⭐⭐ **R-G1-A（**wave 24 另一路**：`battle_black_field_star_mask.h` / 黑场时长）** | 黑场 / 星形遮罩的**结束时机** | ⭐ **让 battle 14 的入场过渡比原版早一拍收尾**（原版：`orig-11` 还在过渡、`orig-12` 已过渡完；重制侧：`remake-16` 还在过渡里） | G1-H7/G1-H8：**这是 `step-12-A` 的真正阻塞** —— 落点那一帧还在 90 帧淡入里面，屏上必然是「地图 + 过渡」。**不解决它，任何呈现状态的改动都够不着那一拍** |
| ⭐⭐ **R-G1-B（`battle_presentation_content.h` = 另一路的文件，或授权本流改）** | `battle_presentation_typewriter_start_delay = 52` | ⭐ **≥ 90**（覆盖入场淡入的 90 帧），或改成「首行等到玩家第一次确认才开打」 | G1-H9：淡入 90 帧 > 首行延迟 52 帧 ⇒ **第一行在淡入里就打完了** ⇒ 「空框 + 无肖像」这个原版状态**永远不会被渲染成一张可见帧**。⚠️ **在 R-G1-A 落地之前不要单独改这一项**：单独改会让 `step-13/14/15`（原版已有文字）少 40 帧的文字 ⇒ 那 3 帧会变差 |
| ⭐ **R-G1-C（本流已实现，**待 R-G1-A/B 落地后即可生效**）** | `battle_runtime_scene.cpp`：`battle_cutscene_entry_background()` + `battle_dialogue_background_runtime_renderer` | ⭐ **已经实现**（§2.1）：入场底图 = `scenario_41_tutorial_bg`；对白底图 = `battle_ui_dialogue_background`；入场那一拍画空框 | G1-H6 + §1.1（底图 0 px 命中）⇒ **R-G1-A 与 R-G1-B 落地后，`step-12-A` 应从 24,101 掉到 ≈ 195 px** |
| ⭐⭐ **R-F2-2 / R-F2-3（『請準備...』窗）** | `battle_runtime_scene.cpp`：照 `:2376` 的 `_add_turn_banner()` 加 `_add_prepare_box()` | 条件 `phase == turn_banner && turn_banner_stage == prepare_box`（其它三段不画）；位置 **(72, 48)**；⭐ **`z_order` 必须低于单位**（原版是**窗压住角色**：窗矩形内有 689 px 的 OBJ 不透明像素，而真值帧那里一格角色像素都没有 ⇒ F2 的 R-F2-3 更正 D1 的说法） | F2 的实测（`build/w23-f2/assets/`，资产已 1:1：贴回原位 0 px；贴到重制侧 3,881 → 809 px） |
| **R-F3-3** | `battle_runtime_scene.cpp`（红箭头绘制处） | **30 px/10×5 只画 2 拍**；原版那 12 拍用 **24 px/6×6**（**重制侧完全没有 24px 款 ⇒ 需要新增资产**） | F3 §2.2 |
| **R-F3-4** | `battle_runtime_scene.cpp`（SELECT 詳細 HUD 绘制条件） | **只在 `unit_selection` 画**（原版 1 拍 `step-23`；重制侧 5 拍 `step-27/29/32/33/34`） | F3 §2.2 |

### 5.2 其余未完成项

| # | 项 | 状态 / 最小动作 |
|---|---|---|
| **U-G1-1** | ⭐⭐ **R-G1-A 的依赖方**：本流改动的**效果依赖黑场时机**，所以**本流单独上线不会改善 `step-12-A`** | 父代理排期时请把 R-G1-A（另一路）与 R-G1-B 放在同一轮验证，否则本流的改动看起来像「没效果」 |
| **U-G1-2** | ⭐⭐ **R-F3-2 的底图选择已被本流更正** | 接线时按 §2.1 走；**不要**用 F3 §4 的「落位到 `remake-17` 的背景」（会白留 9,954 px） |
| **U-G1-3** | ⭐ **黑场** | ⛔ **未跑成**：探针只落了 **334 / ~2,400 帧**（`frames_run 2480, frames_captured 334`）⇒ `blackfade_report.py` 报 **0 个黑场事件**，**无法与基线的 58 帧对比**。下一位：`python tools/s49_package/capture_blackfade.py --rom <lane ROM> --out build/w24-g1/blackfade --keys 'Down,Down,A,A,...(21 个 A)' --zero-frames 240 --hold-frames 4 --settle-frames 90`（**`--keys` 不能省**，空串会让 lua 的 `assert` 失败） |
| **U-G1-4** | ⭐⭐ **R-F2-2 / R-F2-3（『請準備...』窗）** | ⛔ **本流没做**（时间不够）。⚠️ lane 的 `graphics/` 是**指向共享树的符号链接** ⇒ 资产不能拷进 lane（会改共享树），要么父代理拷、要么把 lane 的 `graphics/` 换成真目录 |
| **U-G1-5** | **R-F3-3 / R-F3-4** | ⛔ **本流没做**（见 §5.1 的接线请求） |
| **U-G1-6** | **遥测工具** | ✅ **已跑通**：`tools/s49_w24g1/script_telemetry.py`（**注意：必须先 `probe.load(state)` 再 `telemetry.locate()`** —— 遥测结构在 EWRAM，没载入 state 时扫不到） |
| **U-G1-7** | ⭐ **本流改动的取舍** | 本流改动**实测中性**（两个口径的 Δ 都能被已知抖动解释）**且 ROM +8,436 B**（入场背景的 8bpp 图块+调色板）⇒ **父代理可以按 `tools/s49_w24g1/apply_g1_edits.py` 的反向 7 处编辑退回**，或保留它作为 R-G1-C 的管线 |
| **U-G1-8** | git | ⛔ **未提交**（按纪律）；共享树**未改**；本流产物全在 `build/w24-g1/` 与 `build/w20-e1/`（lane 副本） |

---

## 6. 交付物

| 路径 | 内容 |
|---|---|
| ⭐ `notes/s49-fidelity/W24-G1-presentation-state.md` | 本文件 |
| ⭐ `build/w24-g1/align-baseline-w22d1.json` | **改前 25 帧逐帧**（total 53,364 / offset +4） |
| ⭐ `build/w24-g1/align-after.json` | ⭐ **改后 25 帧逐帧**（total 53,408 / offset +4） |
| ⭐ `build/w24-g1/report.json` / `report.md` | ⭐ **判定台收据**（field sum 36,452 / attribution 4·20·1） |
| `build/w24-g1/work/capture-remake/` | 本流新录制的重制侧 35 帧（`.png` + `.ss9`） |
| `build/w24-g1/work/capture-original/` | 从 w22 出包复制的原版侧 25 帧（审计一致 ⇒ 判定台复用） |
| `build/w24-g1/blackfade/` | ⛔ 黑场收据（**只落 334 帧，不可用**，见 U-G1-3） |
| `build/w24-g1-orig-strip.png` | 原版 `step-11/12/13/16` 四帧对照（目视用） |
| `tools/s49_w24g1/script_telemetry.py` | ⭐ 读 `.ss9` 里的脚本遥测（**已跑通**） |
| `tools/s49_w24g1/capture_remake.py` | 只重录重制侧 walk（复用原版侧捕获） |
| `tools/s49_w24g1/apply_g1_edits.py` | 本流 7 处编辑的施加脚本（幂等断言） |
| lane 副本 `build/w20-e1/butano-sequel/game/src/battle_runtime_scene.cpp` | ⭐ 本流的 7 处改动 + 1 处 include |
| `build/mgba-probe-w24g1/mgba-probe.exe` | 本流私建探针 |
