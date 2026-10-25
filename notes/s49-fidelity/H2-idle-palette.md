# H2 — idle 相位（状态机门控）+ 逐帧 OBJ 调色板改写

**stream**：H2（idle 相位 + 逐帧 OBJ 调色板改写）
**日期**：2026-10-24
**任务**：`notes/s49-fidelity/WAVE3-TASKS.md` §2
**上游**：`notes/s49-fidelity/H-idle.md`（wave 2 的 H 流）
**独占文件**：`butano-sequel/game/include/konoha/battle_unit_visual_animation.h`、
`butano-sequel/game/include/konoha/battle_visual_resource_coordinator.h`、
**新** `butano-sequel/game/include/konoha/battle_unit_palette_stream.h`、
`butano-sequel/game/tests/test_battle_unit_visual_animation.cpp`、
`butano-sequel/game/tests/test_battle_visual_resource_coordinator.cpp`、
**新** `butano-sequel/game/tests/test_battle_unit_palette_stream.cpp`、
`tools/s49_idle_frame_repeat.py`、**新** `tools/s49_idle_outline_colours.py`、
本报告。

⛔ **没有改** `game/src/battle_runtime_scene.cpp`（G 流独占）。
⛔ **没有改**逆向线 `D:\Shell\Github\gba-naruto-reverse`（全程只读）。
⛔ **没有提交 git**（两棵树都只有工作区改动）。

---

## 0. 一句话结论

> **纯逻辑模块已交付**：`battle_unit_palette_stream.h` 提供**状态机门控的 idle 相位**
> 与**逐帧 OBJ 调色板改写决策**，三个单元测试全绿；
> **描边波形与原版逐帧一致（200/200）且 C++ 实现与门禁脚本的公式逐值相同**；
> ⭐ **并且查实了一条对父代理新门禁的重要修正：原版自己也会「连续两帧完全相同」** ——
> 每 100 个 GBA 帧有 **4 次**，且**恰好落在波形量化后的波谷（相位 9→10）与波峰（25→26）**，
> 所以那条门禁的正确判据不是「绝不允许相同」，而是「**只允许在波形的平点处相同**」。
> 接线点清单见 §6（`battle_runtime_scene.cpp` 的 4 处，G 流照做即可）。

---

## 1. 交付的东西

### 1.1 契约函数（签名与 `WAVE3-TASKS.md` §2.3 逐字一致）

```cpp
// game/include/konoha/battle_unit_palette_stream.h
namespace konoha {

struct battle_unit_palette_rgb5 { int red = 0; int green = 0; int blue = 0; };

struct battle_unit_palette_write {
    bool        valid = false;      // false = 本帧不写
    int         palette_index = 0;  // 目标调色板槽位（原版用 OBJ 调色板 index 15）
    int         color_index = 0;    // 0..15
    battle_unit_palette_rgb5 color{};
};

[[nodiscard]] int battle_unit_idle_cycle_frames(int unit_id);
[[nodiscard]] int battle_unit_idle_phase_frames(int unit_id, unsigned state_frame);
[[nodiscard]] battle_unit_palette_write
battle_unit_palette_write_for_frame(int unit_id,
                                    unsigned state_frame,
                                    unsigned scene_frame);
}
```

**颜色结构自己定义**（`battle_unit_palette_rgb5`），**没有** include
`battle_range_ui_style.h` ⇒ 与 G 流零编译耦合 ✓。
只 include `konoha/battle_unit_visual_animation.h`（本流独占），
不依赖 butano、不依赖 G 流的任何文件 ⇒ **主机可编译**（三个测试就是主机编译的）。

### 1.2 状态机门控的 idle 相位

**核心改动**：idle 相位不再由自由运行的 `scene_frame` 决定，而由一个
**门控时钟（gated idle clock）**决定 —— 只在「场景状态机允许原版 idle 动画推进」
的帧上前进。

| 构件 | 作用 |
|---|---|
| `battle_unit_idle_gate_state` | 场景状态枚举：`field_idle` / `command_menu` / `dialogue` / `banner` / `unit_presentation` / `combat_presentation` |
| `battle_unit_idle_gate_open(state)` | 该状态下原版的 idle 动画**是否推进**（纯函数） |
| `battle_unit_idle_advance(gated_frame, state)` | 推进一帧（推进则 +1，否则不变） |
| `battle_unit_idle_clock` | 场景持有的时钟对象：`advance(state)` / `advance_by(n)` / `reset()` / `frames()` |
| `battle_unit_idle_phase_frames(unit_id, state_frame)` | 相位 = `(state_frame + 单位半周期偏移) mod 32` |

> **`state_frame` 的定义（接线时必须一致）**：`state_frame` = **门控时钟的值**，
> 也就是「该单位的 field idle 动画已经推进了多少帧」，**不是**全局场景帧号。
> 调用方每渲染一帧调用一次 `battle_unit_idle_clock::advance(当前场景状态)`。

**门控表是机制，不是已完成的测量**（诚实标注，见 §5 台账 H2-6）：
`field_idle` 与 `command_menu` 是**实测**的（见 §3 的门禁与 §4 的波形验证）；
其余四项（dialogue / banner / unit_presentation / combat_presentation）按
「原版在该状态下不推进 idle 动画」处理，**未逐状态实测**。
调用方若知道得更多，可以直接用 `advance_by()` 驱动时钟，绕过这张表。

### 1.3 逐帧 OBJ 调色板改写决策

* 原版的描边色 = OBJ 调色板**槽位 15**，颜色 = **(0, g, g)**，`g` 是 5 bit 绿
  （1, 3, …, 31）。原版的 PRAM 写链是 `0x05000200 + bank * 32 + 0x1E`，
  `0x1E` = 槽位 15 ✓。
* `palette_index` 与 `color_index` **都填 15**：
  按任务书 §2.3 的字面（「目标调色板**槽位**（原版用 OBJ 调色板 index 15）」）
  `palette_index` 就是槽位；而 `color_index` 是「调色板内的颜色号」，同样是 15。
  这样**两种读法都不会写错槽位**。
  **调色板 bank（16 个硬件 OBJ 调色板里的哪一个）不是决策的一部分**，
  由调用方拥有；模块提供规范映射 `battle_unit_palette_bank_for_unit(unit_id)`
  = `(unit_id - 1) & 0x0F`（单位槽位顺序，1 号单位 → bank 0）。
* `valid` 的判据：
  * `unit_id <= 0` ⇒ `valid = false`（未知单位）；
  * **门控时钟与场景帧同步时**（`state_frame == scene_frame`），
    上一帧的颜色是**已知**的（= 上一相位的颜色），
    因此只有**颜色真的变了**才报写 ⇒ 波形的**唯一平点**（相位 9→10，
    最暗的色跨两个相位）会被跳过 —— **这与原版行为一致**（§4 证明）；
  * **一旦门控让时钟停过**（两个计数器不再相等），上一帧的颜色未知 ⇒ 一律报写，
    让调用方刷新槽位（保守、安全）；
  * `scene_frame == 0`（场景第一帧）⇒ 一律报写。
* ⚠️ **调用方在重新绑定调色板之后必须无条件写一次**：重新绑定会把槽位 15
  恢复成调色板 item 的静态颜色，模块看不到这件事。接线清单 §6-2 已写明。

---

## 2. 改了哪些文件

| 路径 | 性质 | 说明 |
|---|---|---|
| `butano-sequel/game/include/konoha/battle_unit_palette_stream.h` | **新** | 纯逻辑模块：契约三函数 + 门控枚举/谓词/时钟 + bank 映射 + 描边色。**无 butano 依赖**、不 include G 流文件。 |
| `butano-sequel/game/include/konoha/battle_unit_visual_animation.h` | **改** | 新增 `idle_pose_cycle_position(int)`（姿态时钟在 32 帧周期里的位置，姿态与描边**读同一个数**，不会漂）；`idle_outline_green()` 改为复用它（**数值不变**）；`idle_phase_offset()` 的注释补上「时钟的来源在 `battle_unit_palette_stream.h`」。 |
| `butano-sequel/game/include/konoha/battle_visual_resource_coordinator.h` | **改** | `battle_visual_resource_contract` 新增 `bool unit_outline_palette`：**把单位放上地图的 cohort（`deployment` / `map`）拥有单位 OBJ 调色板**，而那些调色板每帧被描边流改写 ⇒ 供调用方判断「这批单位要走描边流」。 |
| `butano-sequel/game/tests/test_battle_unit_palette_stream.cpp` | **新** | 契约三函数 + 门控 + 波形 + 决策的单元测试（196 行）。 |
| `butano-sequel/game/tests/test_battle_unit_visual_animation.cpp` | **改** | 追加 `idle_pose_cycle_position` 与 `idle_outline_green` 的断言（含 32 值波形全表、16 级各出现 2 次、波谷在相位 9/10）。 |
| `butano-sequel/game/tests/test_battle_visual_resource_coordinator.cpp` | **改** | 追加 `unit_outline_palette` 的 4 条 `static_assert`。 |
| `tools/s49_idle_frame_repeat.py` | **新** | 门禁：**连续两帧完全相同**。支持 `--stride`（本机探针 2:1 采集）与 `--pose`（用姿态图把「相同帧」分类为「波形平点」或「异常」）。 |
| `tools/s49_idle_outline_colours.py` | **新** | 诊断：列出每次采样里单位区域出现过的描边色（8 bit → 5 bit）。**原版 7 级、重制 1 级**。 |
| `notes/s49-fidelity/H2-idle-palette.md` | **新** | 本报告。 |
| `build/h2-run-tests.sh`、`build/h2-wave-probe.cpp`、`build/h2_wave_diff.py`、`build/h2-arm-check.cpp`、`build/s49-idle/original_repeat_probe.py`、`build/s49-idle/outline_colour_probe.py`、`build/h2-rom-build.log` | 临时 | 一次性探针与构建日志（`build/` 被 gitignore，结论已落进本报告与 `tools/`）。 |

**没有动**：`game/src/battle_runtime_scene.cpp`、逆向线、master 仓其它文件。
（`git status --short` 见 §7.3。）

---

## 3. 跑了哪些验证

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| H2-1 | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/h2-run-tests.sh`（= `g++ -std=c++23 -Wall -Wextra -Werror -pedantic -I game/include` 逐个编译并运行三个测试） | 三个测试都编译干净并通过 | **3/3 PASS，退出码 0**（`test_battle_unit_palette_stream` / `test_battle_unit_visual_animation` / `test_battle_visual_resource_coordinator`） |
| H2-2 | `python tools/s49_idle_outline_wave.py --out build/s49-idle/outline-wave-check.json` | 波形与原版逐帧一致 | **frames 200 / matched 200 / mismatched 0 / skipped 0，退出码 0**（收据 `build/s49-idle/outline-wave-check.json`） |
| H2-3 | `python build/h2_wave_diff.py`（比较**出货的 C++** 与门禁脚本的 Python 公式） | 两者逐值相同 | **identical: True**，各 32 个值：`19 17 15 13 11 9 7 5 3 1 1 3 5 7 9 11 13 15 17 19 21 23 25 27 29 31 31 29 27 25 23 21` |
| H2-4 | `python tools/s49_idle_frame_repeat.py --out build/s49-idle/frame-repeat-check.json` | 两侧都无「连续两帧相同」 | **原版 25 帧 / 0 对；重制侧 35 帧 / 3 对且 3 对都异常**（`step-24-A == step-25-A`、`step-30-A == step-31-A`、`step-32-A == step-33-A`）⇒ **退出码 1**（门禁在当前基线上如实失败） |
| H2-5 | `python tools/s49_idle_frame_repeat.py --dir build/s49-logic/original-idle-sweep --glob 'frame-*.png' --stride 2 --pose build/s49-idle/original-sweep-pose.json --out build/s49-idle/original-repeat-check.json` | 原版的「相同帧」只出现在波形平点 | **100 个 GBA 帧 / 4 对相同 / 0 对异常**，4 对全部落在相位 **9→10** 与 **25→26** ⇒ **退出码 0** |
| H2-6 | `python tools/s49_idle_outline_colours.py` | 原版描边色逐帧变、重制侧不变 | **原版 7 个 5 bit 描边色 `[1, 5, 11, 13, 17, 23, 27]`；重制侧只有 1 个 `[1]`** |
| H2-7 | devkitARM：`arm-none-eabi-g++ -c -mcpu=arm7tdmi -mtune=arm7tdmi -O2 -fno-exceptions -fno-rtti -std=c++20 -Wall -Wextra -I game/include build/h2-arm-check.cpp` | 三个头在 ROM 工具链下可编译 | **ARM_COMPILE_OK**（text 400 B） |
| H2-8 | WSL 重建 ROM（§0.4 的命令） | 编译通过 | ❌ **失败，但与本流无关**：4 个 error **全部**在 `game/include/konoha/battle_audio_runtime.h`（L 流的独占文件，改到一半：`battle_audio_event_trace` 未声明、`bn::music_items::sound_010` 不存在）。**整份构建日志里没有出现过本流的三个文件**（收据 `build/h2-rom-build.log`） |

### 3.1 没做到的那一条

**「重制 ROM 构建通过」未达成**，原因在 L 流（见 H2-8），不是本流。
本流的三个头已用 devkitARM 单独编译验证（H2-7）。

---

## 4. ⭐ 对父代理新门禁的修正：原版自己也会「连续两帧完全相同」

父代理给的判据是：「重制侧任意两次连续采样之间，**不得**出现完全相同的整帧；
原版基线 0/24，重制侧当前 3/35」。

**这条判据的原版基线「0」是采样运气，不是规律。** 实测：

```
$ python tools/s49_idle_frame_repeat.py --dir build/s49-logic/original-idle-sweep \
      --glob 'frame-*.png' --stride 2 --pose build/s49-idle/original-sweep-pose.json
directory: 100 frames, 4 consecutive identical pairs, 0 unexpected
  frame-040.png == frame-042.png (5e34e539) flat spot
  frame-072.png == frame-074.png (b53dd3c2) flat spot
  frame-104.png == frame-106.png (ed698181) flat spot
  frame-136.png == frame-138.png (2b7dc3cf) flat spot
```

* 原版的 200 帧 idle sweep 里，**每 100 个 GBA 帧有 4 次「连续两帧完全相同」**；
* 这 4 次**恰好**落在波形量化后的两个**平点**：
  * **相位 9→10**：最暗的色（5 bit 绿 = 1）在相邻两个相位上重复；
  * **相位 25→26**：最亮的色（5 bit 绿 = 31）同理；
* 其余 96 个相位上，原版**每一帧都变**。

⇒ **正确的判据是**：

> 连续两帧完全相同 **只允许** 出现在描边波形的平点处（相位 9→10 与 25→26）；
> 其它任何相位上出现 ⇒ 是缺陷。

这同时给 H 流 H8「波形是姿态周期的纯函数」提供了**一条独立的交叉验证**：
公式预测的两个平点（9/10 与 25/26）与原版实际出现重复帧的位置**逐个对上**
—— 公式若在任何地方偏一位，这个对合就不成立。

**对 G 流的直接影响**：模块的 `valid` 在相位 10 会返回 `false`（跳过这一次写）。
**这不是 bug，是与原版一致的行为**：原版在那个相位上颜色也没变，整帧就是重复的。
所以 G 接线后，**walk 捕获（每 47 GBA 帧一次采样）应当降到 0 对重复**，
而**逐帧密集捕获**应当是 **每 32 个 GBA 帧 2 对**（两个平点）。

### 4.1 顺带确认的根因（一行）

| | 单位区域出现的 5 bit 描边色 |
|---|---|
| **原版** | `[1, 5, 11, 13, 17, 23, 27]` —— **7 个，逐帧在变** |
| **重制侧** | `[1]` —— **只有 1 个，永远不变** |

⇒ 「重制 32 帧周期只有 3 张图 vs 原版 16/30 张」与「连续两帧完全相同」
**是同一个根因**：重制侧从不改 OBJ 调色板槽位 15。

### 4.2 关于黑场（父代理的第二条，**未下结论**）

父代理观察到「原版有 2 帧黑场过渡，重制侧 35 帧里一帧黑帧都没有」。
本流用 `build/s49-report/inspect_brightness.py` 复核，**数据一致**：

| 帧 | 非黑 % | 唯一色数 | |
|---|---:|---:|---|
| 原版 `step-11-A.png` | **0.8** | 16 | 近黑过渡帧 |
| 原版 `step-18-A.png` | **0.0** | **1** | 全黑帧 |
| 重制侧 35 帧 | — | — | **没有黑帧** |

⇒ 黑场是**场景切换的淡入淡出**，不是 idle 相位问题；重制侧的 walk 没走到同样的
切换点，**无法区分**「没实现该特性」与「这次没走到那个相位」。
**本流不处理，移交 wave 4**（台账 H2-8，状态 = 未验）。
本流在 idle 相位上**没有**观察到「重制侧某个相位缺一次画面切换」。

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| H2-1 | 描边波形是姿态周期的纯函数（上游 H8） | `python tools/s49_idle_outline_wave.py` | **200/200 一致，0 不一致，退出码 0** | **已确认**（本机复现） |
| H2-2 | 出货的 C++ 实现与门禁脚本的公式不会漂 | C++ 探针输出 vs `s49_idle_outline_wave.py::idle_outline_green`，32 值逐个比 | **identical: True** | **已确认** |
| H2-3 | 原版**只在**波形的平点处出现「连续两帧完全相同」 | 原版 200 帧 idle sweep 按 GBA 帧（stride 2）+ 姿态图定位相位 | **100 帧 / 4 对相同 / 0 对异常**，全部落在相位 9→10 与 25→26 | **已确认** |
| H2-4 | 「重制侧不得出现连续两帧完全相同」是**绝对**规律 | 同 H2-3 | 原版自己每 100 GBA 帧就有 4 对 ⇒ 该判据的「原版基线 0」是采样运气 | **已证伪**（判据需按 §4 收紧为「只允许在平点处」） |
| H2-5 | 重制侧的重复帧源于「从不改 OBJ 调色板槽位 15」 | 统计两侧每次采样里单位区域出现的 5 bit 描边色 | 原版 **7 级**、重制侧 **1 级** | **已确认** |
| H2-6 | 哪些场景状态让原版的 idle 时钟推进 | 只有 `field_idle` / `command_menu` 有实测依据；其余四项按「该状态下不推进」处理 | **dialogue / banner / unit_presentation / combat_presentation 四项未实测** | **未验**（机制已交付，表可由调用方覆盖） |
| H2-7 | 原版的 idle 时钟受场景状态机门控（上游 H11） | 上游 H 流实测：每 walk 步推进 29/6/23/…/11/19/6/2，不是恒定的 15 | 与本流的门控模型一致 | **已确认**（上游结论，本流继承） |
| H2-8 | 重制侧缺黑场是「没实现淡出黑场特性」 | 复核亮度表 | 原版 2 帧黑场、重制 0 帧；**无法区分**「没实现」与「没走到该相位」 | **未验**（移交 wave 4） |
| H2-9 | 单位的半周期相位偏移（奇数单位 +16）仍然正确 | 继承上游，未改动 `idle_phase_offset()` | — | **未验**（沿用，不在本流射程） |
| H2-10 | 模块「跳过平点那一次写」与原版一致 | H2-3 的 4 对重复帧位置 = 公式预测的平点 | 逐个对上 | **已确认** |
| H2-11 | ROM 构建失败与本流无关 | 完整构建日志里 grep 本流的三个文件 | **4 个 error 全在 `battle_audio_runtime.h`（L 流）；日志里没有本流文件** | **已确认** |

---

## 6. 接线点清单（G 流照做）

> 目标文件：`butano-sequel/game/src/battle_runtime_scene.cpp`
> 行号基于 **2026-10-24 本流提交前**的文件状态；G 流并行改动后请按**函数名**定位。

### 6-0 先决条件：每个单位要有一份**自己的**运行时 OBJ 调色板

原版每个单位一个 OBJ 调色板 bank（描边色互不干扰）。
重制侧现在的 `item->palette_item()` 是**共享 item** ⇒ 直接往里写槽位 15 会
**同时改掉所有用这个 item 的单位**。

**做法**（butano 已有现成 API）：
```cpp
// 每个单位一份运行时调色板，seed 自该单位的调色板 item
auto palette = bn::sprite_palette_items::<unit_palette_item>
        .create_palette();               // bn::sprite_palette_ptr
palette.set_colors(item->palette_item());   // 拷贝全部 16 个颜色
```
* VRAM 够：峰值 47,082 / 98,304 B，12 个单位各 32 B = **384 B**（上游 H-idle.md §8.2）。
* 每单位一个 bank ⇒ 硬件 OBJ 调色板 bank 共 16 个，12 个单位够用。
  模块给的规范映射是 `battle_unit_palette_bank_for_unit(unit.id)`（1 号 → bank 0）。
* ⚠️ **被灰度（dimmed）的单位用的是共享的 `dimmed_unit_palette()`（L6479）**
  ⇒ **不要往那份共享调色板里写描边色**，否则所有灰度单位都会变色。
  原版的灰度单位也是静态描边色。

### 6-1 ⭐ 每帧写一次描边调色板（**这才是「3 张图 → 32 张图」「连续两帧相同」的修复**）

**位置**：`update_unit_sprites()` 里的调色板绑定处，现 **L6718–L6742**：

```cpp
            const bool dimmed =
                    dim_inactive_units &&
                    ! acting_unit &&
                    state.phase != battle_scene_phase::unit_selection &&
                    state.phase != battle_scene_phase::move_selection;
            if(dimmed)                                        // L6733
            {
                sprite->set_palette(
                        dimmed_unit_palette());               // L6735
            }
            else if(binding_changed)                          // L6738
            {
                sprite->set_palette(
                        item->palette_item());                // L6740
            }
```

**做法**：在 `else if(binding_changed)` 分支之后（即 **L6742 之后**）插入：

```cpp
            // 原版每帧重写单位 OBJ 调色板的槽位 15（描边色），
            // 所以它一个周期显示 32 张图，而重制侧原本只有 3 张。
            const battle_unit_palette_write outline =
                    battle_unit_palette_write_for_frame(
                            unit.id,
                            idle_clock.frames(),
                            scene_frame);
            if(outline.valid || binding_changed)
            {
                unit_palette(unit.id)->set_color(
                        outline.color_index,
                        bn::color(outline.color.red,
                                  outline.color.green,
                                  outline.color.blue));
            }
```

**坑（务必照做）**：

1. `bn::color(int red, int green, int blue)` 收的是 **5 bit 分量（0..31）**
   （已核对 `bn_color.h`：`BN_ASSERT(green >= 0 && green <= 31)`）
   ⇒ **模块给的 `color.green` 已经是 5 bit 值，直接传，不要再乘 8**。
2. `set_color(int color_index, bn::color)` 的 `color_index` 是 **0..15**
   ⇒ 用 `outline.color_index`（= 15），不要用 `palette_index`。
3. **`|| binding_changed` 不可省**：重新绑定调色板会把槽位 15 恢复成 item 的
   静态颜色（模块看不到这件事）。
4. `dimmed` 的单位走共享灰度调色板 ⇒ 上面这段要在 `else` 语义下做
   （只有非灰度单位才有自己的描边色）。

### 6-2 ⭐ idle 时钟的来源：换成**门控时钟**（这是「相位差」���修复）

**位置**：`unit_visual_sample()`，现 **L6132–L6145**：

```cpp
[[nodiscard]] battle_unit_visual_sample unit_visual_sample(
        const battle_scene_unit_view& unit,
        const battle_scene_presentation& presentation,
        std::uint32_t scene_frame)        // L6135
{
    ...
    result.elapsed_frames =
            static_cast<int>(
                    scene_frame & 0x7FFFFFFFU) +       // L6143  ← 自由运行
            battle_unit_visual_animation::idle_phase_offset(
                                unit.id);                // L6144
```

**做法**：
1. `unit_visual_sample()` 多收一个参数，例如
   `unsigned idle_frame`（门控时钟的值）；
2. 把 **L6141–L6145** 改成：
```cpp
    result.elapsed_frames =
            static_cast<int>(idle_frame) +
            battle_unit_visual_animation::idle_phase_offset(
                    unit.id);
```
   （`idle_phase_offset` 仍是单位的半周期偏移，**保留**。）
3. `update_unit_sprites()`（**L6487** 的签名）多收一个
   `const battle_unit_idle_clock& idle_clock`，并在 **L6573** 的
   `unit_visual_sample(visual_unit, presentation, scene_frame)` 调用处
   改成传 `idle_clock.frames()`。

### 6-3 门控时钟的存放与推进

**位置**：场景帧计数器旁边，现 **L7042**：`std::uint32_t scene_frame = 0;`

**做法**：
```cpp
    std::uint32_t scene_frame = 0;
    battle_unit_idle_clock idle_clock;   // ← 新增：门控 idle 时钟
```
每渲染一帧（**L7154 / L8006** 的 `++scene_frame;` 旁边，以及
**L7043 / L7155 / L7568 / L8039** 的 `update_unit_sprites(...)` 调用处）
推进一次：
```cpp
    idle_clock.advance(<当前场景状态>);
```
当前场景状态 → `battle_unit_idle_gate_state` 的映射由 G 决定
（`field_idle` / `command_menu` 推进，其余四个状态暂停）。

> **重要**：门控时钟与 `scene_frame` 必须**同源起算**（场景开始时都是 0），
> 否则模块的 `state_frame == scene_frame` 判定永远为假 ⇒ 模块一律报写
> （**安全但退化**：每帧都写，功能正确，只是少了那一次「跳过平点」的优化）。
> 门控表本身**未实测**（台账 H2-6），G 若有更准的信息可改用 `advance_by()`。

### 6-4 灰度单位与描边色的关系（给 G 的提醒，不是必须改）

原版里**只有没被灰度的那个单位**在动（H12：原版只让被选中的单位动）。
⇒ 若 G 接线后残差里出现「另一个单位也在动」，那是**描边流给所有单位都写了颜色**
造成的；原版的其它单位描边色是**静态**的。
若要与原版一致，G 可以只给**当前行动单位**写描边色，其余单位保持静态。

---

## 7. 卡在哪 / 剩下什么

### 7.1 卡点

| # | 事项 | 状态 |
|---|---|---|
| 1 | **ROM 构建通过** | ❌ 被 **L 流**的 `battle_audio_runtime.h`（改到一半）挡住：4 个 error，日志里没有本流文件。本流三个头已用 devkitARM 单独编译通过（H2-7）。 |
| 2 | **门控表** | ⚠️ `dialogue` / `banner` / `unit_presentation` / `combat_presentation` 四项**未实测**（H2-6）。机制已交付，G 可覆盖。 |
| 3 | **重制侧的重复帧降到 0** | ⏳ **要等 G 接线**（§6-1）才能测。本流只能把门禁做好并如实让它在当前基线上失败。 |
| 4 | **黑场** | ⏳ 不在本流射程，移交 wave 4（H2-8）。 |

### 7.2 还没做的（明确排除）

* **没有**改 `battle_runtime_scene.cpp`（按分工）。
* **没有**实现「只让被选中单位动」（那是渲染策略，归 G）。
* **没有**做逐采样音频（明确排除）。
* **没有**提交 git。

### 7.3 工作区状态（两棵树都未提交）

```
=== remake repo (git status --short) ===
 M butano-sequel/game/include/konoha/battle_audio_director.h      ← L 流
 M butano-sequel/game/include/konoha/battle_audio_runtime.h        ← L 流
 M butano-sequel/game/include/konoha/battle_unit_visual_animation.h   ← 本流
 M butano-sequel/game/include/konoha/battle_visual_resource_coordinator.h ← 本流
 M butano-sequel/game/tests/test_battle_unit_visual_animation.cpp      ← 本流
 M butano-sequel/game/tests/test_battle_visual_resource_coordinator.cpp ← 本流
?? butano-sequel/game/include/konoha/battle_audio_event_trace.h     ← L 流
?? butano-sequel/game/include/konoha/battle_unit_palette_stream.h   ← 本流
?? butano-sequel/game/tests/test_battle_unit_palette_stream.cpp     ← 本流
```

master 仓新增：`tools/s49_idle_frame_repeat.py`、`tools/s49_idle_outline_colours.py`、
`notes/s49-fidelity/H2-idle-palette.md`（本报告）。

### 7.4 编码检查

新写/改动的 7 个源文件全部 **LF、无 BOM**（`crlf=0`、`bom=False`）✓

---

## 8. 引用

* 上游：`notes/s49-fidelity/H-idle.md`（H 流）、`notes/s49-fidelity/WAVE3-TASKS.md` §0/§2
* 波形门禁：`tools/s49_idle_outline_wave.py`（H 流，只读复用）
* 重复帧门禁：`tools/s49_idle_frame_repeat.py`（本流新增）
* 描边色诊断：`tools/s49_idle_outline_colours.py`（本流新增）
* 判定台：`tools/s49_fidelity_report.py`（A 流）
* butano API：`third_party/butano/butano/include/bn_sprite_palette_ptr.h`
  （`set_color(int color_index, color color)`）、`bn_color.h`
  （`color(int red, int green, int blue)`，分量 0..31）
* 采集素材：`build/s49-logic/original-idle-sweep`（原版 200 帧）、
  `build/s49-report/capture-original`（25 帧）、
  `build/s49-report/capture-remake`（35 帧）
* 收据：`build/s49-idle/outline-wave-check.json`、
  `build/s49-idle/frame-repeat-check.json`、
  `build/s49-idle/original-repeat-check.json`、`build/h2-rom-build.log`
