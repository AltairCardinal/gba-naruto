# W20-E1 —— Butano 调色板修法接线 + 結算屏残差修复 + 黑场 B2/B3/B4

> 2026-10-25 20:35 起 · 流：E1 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> lane 副本：`D:\Github\gba-naruto\build\w20-e1\butano-sequel`（**唯一改动地**）
> 共享树 `D:\Shell\Github\gba-naruto-butano\butano-sequel`：**未改**（父代理接线）
> 上游：`notes/s49-fidelity/W20-EXEC-BRIEF.md` · `notes/s49-fidelity/W20-RECOVER-lanes.md` · `notes/s49-fidelity/W20-PARENT-wrapup.md` §8.3–8.6

---

## 0. 一句话结论

> ⭐⭐ **任务 1 完成并实测通过：結算屏的 35 k px 残差不是「底板与森林抢槽位」，而是「結算底板与勝利屏背景
> **共用调色板槽 0**」——Butano 的 `create_bpp_8()` 在 `bpp_8_slots_count(16) >= required(2)` 时
> 走 `++first_pal.usages; return 0;` 分支（共用槽 0 且**不上传新调色板**），于是結算底板被画成
> 勝利屏（= 战场画面）的 256 色。**
>
> **修法只有一处**：建結算底板之前先释放 `_victory_background`
> （`game/src/battle_runtime_scene.cpp`，+13 行注释 + 1 行代码）。
> ⇒ 結算屏 **35,016 px → 985 px**；用 poked 链做同战斗状态的对照 ⇒ **684 px（与已接受 ROM 逐字节相同）**。
> 真实链那多出的 301 px 全部落在「戰鬥分 / 合計」数字行 ⇒ **E2 的种子数据缺口，不是 E1 的回归**。
>
> ⏳ **任务 2（黑场 B2/B3/B4 + 淡入 28→24）与任务 3（时间线偏移）未完成**：
> 两者都给出了**带文件行号的根因**与**可执行的判定方法**。
> 任务 3 的归因**已被实测推翻**：用**没有** E1 补丁的已接受 ROM `e2182fff9…` 重录黑场，
> 5 个事件的帧号与 wave20-E1 ROM **逐个相同** ⇒ **那 +90/+94 的偏移不是 E1 的补丁造成的**
> （是 wave19-C 路旧 ROM ↔ 当前共享树的差）。详见 §6。

---

## 1. 三项验收判定

| # | 判据 | 结果 | 状态 |
|---|---|---|---|
| A | 真实战斗打完仗，結算链 7 段全部录到 | **48 页 / `final_phase=task_menu` / 相位 `outcome,result,level_up,training,post_battle_dialogue,task_menu` 全走到** | ✅ **已确认** |
| B | 結算屏与原版真值的差 ≤ 684 px | **985 px**（> 684） | ⚠️ **渲染部分已达 684 px**；残差全在 E2 的「戰鬥分」数字行 |
| C | 不再出现 Butano 错误屏 | **无错误屏**；`stderr.txt` 只有 probe 的 8 行启动日志；`palette_status` 不 present | ✅ **已确认** |

> ⚠️ **B 项的口径说明（不要误判为回归）**：
> 判据里的 684 px 是**在 poked 链**（战斗状态被 poke 成与原版一致）上量到的。
> **真实链的战斗结果不同 ⇒ 戰鬥分/合計两行的数字不同 ⇒ 差值必然 > 684。**
> 本流用 **poked 链做同状态对照**（§1.3）证明渲染部分已经**逐字节回到已接受 ROM**。

### 1.1 数字（精确）

| 项 | 值 |
|---|---|
| 本流新 ROM sha256 | `bf2c2e6e6eb03d4e1dcc876f939bd1d8cb9629c9ac6c10822d6a2c638c35826a` |
| wave20-E1 旧 ROM sha256 | `150dacf876ab3fc385826533a104a70bc5d141a42d1799f03595e1445a488749` |
| 真实链 `entry.poke` / `poke_commands` | `false` / **0**（`probe_commands` 4,602） |
| 真实链 `outcome` / `round` / `frames_run` | **1** / 13 / 25,848 |
| 真实链 `errors` | `[]` |
| 真实链 蜂 HP `start → end` | 5 只 **25 → 0**（`bee_hp_dropped=true`，`escort_alive=true`） |
| 結算链 | **48 页**，`final_phase=task_menu` |
| 单测 | **pass=118 / fail=20**（= 预存债，逐名相同 ⇒ **零回归**） |

### 1.2 結算屏逐屏差表（`tools/s49_victory_align/align_settlement.py`，真值=原版 9 张图）

| 原版真值 | 本流页 | 差 | 差带（行） |
|---|---|---:|---|
| `01-victory.png` | `page-000-outcome.png` | **0 px** | — |
| `02-settlement-exp-power-turns.png` | `page-001-result.png` | **985 px** (2.6 %) | `[[106,153]]` |
| `03-levelup-naruto.png` | `page-002-level_up.png` | **0 px** | — |
| `05-levelup-sasuke-jutsu-name.png` | `page-003-level_up.png` | **0 px** | — |
| `04-levelup-konohamaru.png` | `page-004-level_up.png` | **0 px** | — |
| `05-levelup-sasuke.png` | `page-005-level_up.png` | **0 px** | — |
| `06-levelup-sakura.png` | `page-006-level_up.png` | **0 px** | — |
| `07-ninja-tool-list.png` | `page-007-level_up.png` | **0 px** | — |

收据：`build/w20-e1/align-fix2.json` / `align-fix2.md`（另有 `build/w20-e1/chain-fix2/shots/` 48 张）。

### 1.3 985 px 的精确分解（关键）

| 对照 | 差值 |
|---|---:|
| 旧 E1 ROM `150dacf8…` 結算屏 vs 真值 | **35,016 px** |
| **新 ROM `bf2c2e6e…` 結算屏 vs 真值（真实链）** | **985 px** |
| 新 ROM 結算屏 vs 已接受 ROM 結算屏（真实链 vs poked 链） | 577 px |
| **新 ROM 結算屏 vs 已接受 ROM 結算屏（poked 链，同战斗状态）** | **0 px（sha256 逐字节相同 `bc6501b111ad9bfd…`）** |
| 已接受 ROM（poked 链）結算屏 vs 真值 | 684 px |

* 577 px 的差**全部落在第 121–149 行**（= 「戰鬥分 / 回合數 / 合計」三行数字）；
  第 106–120 行（背景 / tab 栏 / 三个角色）与已接受 ROM **逐字节相同**
  ⇒ **渲染路径（调色板 / 底板 / 精灵）已经修对**。
* 数字不同是**战斗结果不同**：

  | | 戰鬥分 | 合計 |
  |---|---|---|
  | 原版真值 | `100/150/0` | `300/350/200` |
  | 已接受 ROM（poked） | `0/0/0` | `200/200/200` |
  | 本流（**真实战斗**） | `50/200/0` | `175/325/125` |

  ⇒ 「戰鬥分」种子数据缺口 = **E2 的活**（`W20-RECOVER-lanes.md` §5.2 / §7 的 E2 行：阵型表的 `battle_experience` 全是 0）。

---

## 2. 任务 1：调色板修法接线 + 残差修复（**已完成**）

### 2.1 接线情况

`build/w20-e1/butano-sequel/game/src/battle_runtime_scene.cpp` **已经含 wave20-E1 的 +35 行调色板修法**
（lane sha `cf628049d22bb5b7` vs 共享树 `f5cfb5079318a40a`；补丁 `build/w20-verify/e1-palette-fix.patch` 已重放比对）。
⇒ **本流不需要重新 apply 补丁**，只加残差修复。

### 2.2 残差的真根因（**推翻了父代理的猜测**）

父代理猜的是「結算底板（8bpp/32，2 槽）与勝利屏背景（8bpp/256，16 槽）同时被申请」。
**实测与源码都不支持这个猜测**：

* 三张图的 BPP / 颜色数（读 `build/w20-e1/butano-sequel/build/bn_regular_bg_items_*.h`）：

  | 资产 | BPP | 颜色数 | 槽位 |
  |---|---|---:|---:|
  | `scenario_41_victory_bg`（勝利屏） | BPP_8 | 256 | **16（占满整个 bank）** |
  | `battle_ui_result_plate`（結算底板） | BPP_8 | 32 | 2 |
  | `battle_duel_forest`（决斗森林） | BPP_4 | 32 | 2 |

* Butano 的 bank 语义（`third_party/butano/butano/src/bn_palettes_bank.cpp.h`）：
  * BPP8 调色板**固定占槽 0**，占 `slots_count` 个槽；
  * `create_bpp_8()`：若 `bpp_8_slots_count >= required_slots_count` ⇒ **走 `++first_pal.usages; return 0;`**
    —— **共用槽 0，且 `_set_colors_bpp_impl()` 根本不会被调用 ⇒ 新调色板的颜色从未上传**。
* ⇒ **結算底板不是在跟森林抢槽位，而是在跟勝利屏共用槽 0**：
  底板拿到的是**勝利屏那 256 色的调色板** ⇒ 整屏偏绿（勝利屏 = 战场画面 ⇒ 绿）。

* **像素证据**（`build/w20-e1/chain-fix1/real/shots/page-001-result.png`）：
  它的 54 个颜色里 **46 个 ∈ `scenario_41_victory_bg` 的调色板**，只有 **5 个 ∈ 結算底板自己的调色板**。

* **时序**（为什么底板正好撞上）：主循环里
  `ui_renderer.update()`（输入门 `if(handled || rejection_changed || ui_layer_changed)` 之内，**先**）
  → `ui_renderer.update_victory_background(phase == outcome)`（**每帧**、**后**）。
  相位从 `outcome` 变成 `result` 的那一帧，門开了 ⇒ `ui_renderer.update()` 先建了結算底板，
  而勝利屏背景要等到同一帧**后面**的 `update_victory_background(false)` 才被释放
  ⇒ 底板创建时胜利屏还活着 ⇒ 共用槽 0。

### 2.3 修法（唯一改动，1 行代码）

`game/src/battle_runtime_scene.cpp`，`battle_ui_runtime_renderer::update()` 的結算分支：

```cpp
        if(model.show_result_panel &&
                state.phase == battle_scene_phase::result)
        {
            // The victory picture's palette is a BPP8 palette with 256
            // colours, so it owns the whole BG palette bank (all 16 slots).
            // Butano shares bank slot 0 between two BPP8 palettes whose slot
            // counts fit into the first one instead of allocating a second
            // slot range, and it does not upload the second palette's
            // colours when it shares the slot.  The settlement plate is a
            // BPP8 palette with 32 colours, so a plate created while the
            // victory picture is still alive borrows the victory picture's
            // colours: the settlement screen then comes out green instead of
            // grey (notes/s49-fidelity/W20-E1-palette-blackfade.md §2).
            // The victory picture is released first, so the settlement plate
            // gets the bank slot and its own 32 colours.
            _victory_background.reset();
            _add_result_background();
            _update_result_participants(result);
            return;
        }
```

**为什么这是最小且安全的改动**：
* 释放的时机正确 —— 相位已经是 `result`，勝利屏画面本来就该退场；
* 释放后 `create_bpp_8()` 走**完整分配路径**（`first_pal.usages == 0` ⇒ `bpp_8_slots_count == 0`
  ⇒ `2 <= _first_bpp_4_palette_index()`（= 16，战斗 cohort 已释放）⇒ 分配槽 0 + 上传 32 色）；
* **没有「少建一个背景」**：底板照建、胜利屏照画（只在建底板的那一刻先让位），
  画面与真值逐像素比对证明没牺牲正确性。

---

## 3. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| P-40 | lane 副本已含 wave20-E1 的调色板修法（不必重新 apply 补丁） | lane vs 共享树 `battle_runtime_scene.cpp` sha256 + 补丁重放比对 | lane `cf628049d22bb5b7` ≠ 共享树 `f5cfb5079318a40a`；补丁 +35 行已在 lane 里 | **已确认** |
| P-41 | 結算屏偏绿的根因是「結算底板与勝利屏背景**共用调色板槽 0**」 | 读 Butano `bn_palettes_bank.cpp.h::create_bpp_8` + 取色包含关系 | 成立：`bpp_8_slots_count(16) >= required(2)` ⇒ 走 `++first_pal.usages; return 0;`，**不上传新调色板** | **已确认** |
| P-42 | E1 結算屏的颜色来自 `scenario_41_victory_bg` 的调色板 | E1 結算屏 54 色 vs 三张图的调色板集合 | 46/54 ∈ 勝利屏；5/54 ∈ 結算底板 | **已确认** |
| P-43 | 修好调色板后結算屏应回到「已接受 ROM」水平（684 px） | 已接受 ROM poked 链 `page-001-result.png` vs 真值 | 684 px | **已确认** |
| P-44 | 真实链与 poked 链的結算屏数字相同 | 读 E1 真实链 `page-001-result.png` | ❌ **证伪**：戰鬥分 `50/200/0` vs `0/0/0`、合計 `175/325/125` vs `200/200/200`；回合數都是 75 | **已证伪** |
| P-45 | 「先释放勝利屏背景再建結算底板」能修好残差 | lane 新 ROM `bf2c2e6e…` 真实链 + poked 链 | 成立：35,016 → **985 px**（真实链）/ **684 px**（poked 同状态，与已接受 ROM 逐字节相同）；无错误屏 | **已确认** |
| P-46 | 真实链多出的 301 px 是 E1 引入的 | 逐行差带定位（121–149 行）+ poked 同状态对照 0 px | ❌ **证伪**：残差是**战斗结果不同**（E2 的種子数据缺口） | **已证伪** |
| P-47 | 父代理猜的「底板与胜利屏同时申请槽位」是根因 | 读 Butano bank 源码 | ❌ **证伪**：两者**从不同时申请**；是**共用槽 0 且不上传颜色** | **已证伪** |
| P-48 | 本流改动引入了单测回归 | `build/w18-run-all-tests.sh` 跑 lane | **不成立**：pass=118 / fail=20（= 预存债，逐名相同） | **已证伪** |
| P-49 | 黑场淡入 28 帧是「淡出渐变多算了 2 级」 | 逐帧 `mean_sequence` 拆解 | ❌ **证伪**：淡出**正好 12 级 × 2 帧 = 24**；淡入也是 **12 级**，但**最后两级各被拖成 4 帧** ⇒ 10×2 + 4 + 4 = 28 | **已证伪** |
| P-50 | 淡入多出的 4 帧来自 `growth` 段 | 逐帧 `mean_sequence` + `alpha()` 的 stage 映射 | ❌ **证伪**：`growth` 段的 alpha = 0 ⇒ 画面满亮度 ⇒ mean ≥ 40，**不计入**「暗帧」；多出的 4 帧在 fade_in 段**内部** | **已证伪** |
| P-51 | 「淡入 28 → 24」= 少画 2 级 | 源码 `fade_in_alphas` 有 12 项、`fade_frames = 12` | ❌ **证伪**：级数**已经是对的 12 级**；问题是**最后两级每级占 2 个场景帧**（`core::update()` 一帧装不下）⇒ 是**性能问题**，不是级数问题 | **已证伪** |
| P-52 | **+90 / +94 的时间线偏移是 E1 的补丁造成的** | 同探针同参数对**已接受 ROM `e2182fff9…`（无 E1 补丁）**重录黑场 | ❌ **证伪**：无补丁的已接受 ROM 的 5 个事件帧号与 wave20-E1 ROM **完全相同**（00527 / 01639 / 01749 / 02217 / 02265）⇒ 偏移来自 C 路旧 ROM ↔ 共享树，与 E1 无关 | **已证伪** |

---

## 4. 改动清单

| 文件 | 改动 | 行数 |
|---|---|---|
| `build/w20-e1/butano-sequel/game/src/battle_runtime_scene.cpp` | ① `battle_ui_runtime_renderer::update()` 的結算分支：**建底板前先 `_victory_background.reset()`**（本流新增）<br>② `battle_combat_stage_runtime_renderer::update()` 开头：`battle_phase_uses_full_screen_result()` 时释放决斗森林/HUD 并 `return`（**wave20-E1 已有**，本流未动） | 本流 +13 行（含注释），有效代码 **+1 行** |
| `build/w20-e1/butano-sequel/game/include/konoha/battle_visual_resource_coordinator.h` | **未动**（E1 独占文件，本流不需要） | 0 |

**没有动共享树，没有动别的流的独占文件，没有提交 git。**

---

## 5. 任务 2：黑场 B2 / B3 / B4 + 淡入 28 → 24（**未完成，给出根因**）

> ⚠️ **本节只交付「根因 + 判定方法」，代码没动。** 理由见 §5.5。

### 5.1 基线（`build/w20-e1/blackfade-fix1/blackfade.json`，ROM `150dacf8…`，2402 帧，5 事件）

| 事件 | 帧段 | 总帧 | 纯黑 | 淡出 | 淡入 | 场景 | 判定 |
|---|---|---:|---:|---:|---:|---|---|
| 1 | 00527–00532 | 6 | 6 | 0 | 0 | 准备 → 部署地图 | **B2 未修** |
| 2 | 01639–01708 | 70 | 18 | 24 | **28** | 「開始」卡入场转场 | **淡入 28 → 应 24** |
| 3 | 01749–01750 | 2 | 2 | 0 | 0 | 地图 → 对白背景交接 | **B3 未修** |
| 4 | 02217–02224 | 8 | 8 | 0 | 0 | 对白内部 | **B4 未修** |
| 5 | 02265–02344 | 80 | 24 | 28 | **28** | 对白 → 战斗（回合 1） | **淡入 28 → 应 24** |

### 5.2 B2（准备 → 战斗，6 帧纯黑）—— 根因与「不可能到 0」

* 代码位置：准备场景 → 战斗场景的交接。
* 硬约束（任务书已给）：**BG 图块区只有 96 KB**（`bn::bg_tiles`），
  准备背景占 **32 KB**、部署地图占 **64 KB** ⇒ **两者不能共存** ⇒ 交接那几帧屏幕上必然没有背景。
* ⇒ **0 帧不可达**。可交付的最小值 = **交接必须占的帧数**（= 释放 + 1 次 `bn::core::update()` + 提交），
  要压到最小只能靠**把交接挪进已经有黑场的帧**（即借用遮罩/淡出段），而不是「少建一个背景」。
* ⚠️ **本流没有量出这个最小值**（需要一次 2402 帧重录 + 对比，见 §5.5）。

### 5.3 B3（生长 → 对白，2 帧纯黑）—— 根因已定位到行

* 代码位置：`battle_runtime_scene.cpp:5101-5137`
  `battle_dialogue_background_runtime_renderer::update()`：

  ```cpp
  map.reset();          // 5121
  bn::core::update();   // 5122
  _background = bn::regular_bg_items::battle_ui_dialogue_background.create_bg(0, 0);
  ```

* 机制：对白背景是 **BPP_8 / 256 色**（占满 16 槽），必须先把地图（BPP_8，8bpp 调色板）
  释放并 `core::update()` 提交，再分配对白背景
  ⇒ **这 2 帧屏上什么都没有 = 纯黑**（与 `V2-pixel-fixes.md` V2-11 的结论一致）。
* 修法方向（任务书指定）：**把这次交接挪进遮罩还盖着屏幕的持黑段**
  —— 即在对白背景真正需要出现之前、**星空遮罩（star mask）仍然全黑的那几帧**里完成
  `map.reset() + core::update() + create_bg()`。
  ⇒ 需要一个「遮罩仍然盖住屏幕」的判据（`battle_black_field::star_mask_level()` 仍 ≥ `black_level`），
  以及在那个窗口里**延后**对白背景的创建。

### 5.4 B4（对白内部 8 帧纯黑）—— 根因已定位到行

* 代码位置：`game/include/konoha/battle_visual_resource_coordinator.h:113-133`
  `battle_visual_resource_coordinator::transition_to()` 的 `case battle_visual_resource_cohort::map: result.release_map = true;`
  ⇒ 消费方 `battle_runtime_scene.cpp:9204-9217` `apply_visual_resource_transition(...)` 释放地图 cohort。
* 机制：`map → script_dialogue` 的 cohort 交换发生在**遮罩没盖住屏幕**的时候
  ⇒ 释放地图、还没建好对白背景 ⇒ **8 帧纯黑**。
* 修法方向（任务书指定）：**把交换推迟到事件 2 淡出的末几级**
  —— 即在 `battle_phase_uses_full_screen_result()` / 遮罩仍然全黑的那几帧里完成 cohort 交换。
* ⚠️ 与 §5.3 是**同一类问题、同一段代码**：地图→对白背景的 8bpp 调色板交接。
  两处一起改才不会互相打架。

### 5.5 「淡入 28 → 24」的根因（**不是级数问题，是性能问题**）

逐帧拆解事件 2 的淡入（`blackfade.json` 的 `mean_sequence`，帧 01681–01708）：

```
级 1..10 各 2 帧：0.088 0.334 0.671 1.185 2.547 3.192 4.985 7.263 12.019 16.428
级 11   4 帧：22.573   （sha bb4a7d74…）
级 12   4 帧：29.091   （sha e610cd7c…）
                       ⇒ 10×2 + 4 + 4 = 28 帧
```

* 淡出**正好 12 级 × 2 帧 = 24** ✓；淡入**也是 12 级**（`fade_in_alphas` 有 12 项，`fade_frames = 12`），
  但**最后两级每级被拖成 4 帧**。
* 代码里已经写明这个机制（`game/include/konoha/battle_black_field_star_mask.h:146-152`）：
  > 「the scene's core update has to finish before a new level is committed to the screen,
  > so **a level change that does not fit into one frame is visible for two frames instead of one**,
  > and the fade was 28 frames instead of the original's 24」
* ⇒ **修法 = 让星空遮罩的最后两级在 1 个场景帧内完成**（把 `set_level()` 的重建成本压进一帧的
  `core::update()` 预算），**不是**改级数、不是改 `fade_in_alphas`。
* 成本证据（`battle_black_field_star_table.h`，逐级 `block_counts` / `cell_counts`）：
  淡入 13→24 级的**精灵总数** = 43,43,46,49,55,58,64,64,74,76,76,**84**；
  最后一级的 `Δcell = +11`、`Δblock = −3`（= 11 个条目要换 role ⇒ 销毁 + 重建 ⇒ 新 tile 集分配）。
  ⇒ 怀疑点是**最后一级的 cell 艺术（+11 个 16×16 tile 集）超出了一帧的 VRAM 上传预算**。
  **但这一条没有被实测证实**（需要逐级耗时探针）。

### 5.6 为什么本流没有动代码（诚实说明）

1. B3 / B4 要改的是**「什么时候做 8bpp 调色板交接」**，属于**场景边界时序**；
   改错会让对话背景与遮罩不同步，而且**只能靠一次 2402 帧重录**才能判定。
2. 「淡入 28 → 24」要动的是**星空遮罩的重建成本**（`battle_black_field_star_mask.h`），
   属于 **E1 独占文件**但风险最高（遮罩像素错一格 = 整屏错）；
   按 AGENTS.md 的「一次只改一处，跑一次，记一行」，本轮时间不够做完一轮**改 → 编 → 录 → 比**。
3. **保护已验收的成果**：任务 1 的 ROM（`bf2c2e6e…`）已通过三项验收，
   本流**没有**在同一棵树上叠加未验证的黑场改动。
   ⇒ **建议：父代理把本流的任务 1 成果先接线，任务 2 单独开一轮。**

### 5.7 任务 2 的判定方法（下一轮直接用）

```powershell
# 1) 重录黑场（用本流自己的探针）
python tools/s49_package/capture_blackfade.py --rom build/w20-e1/butano-sequel/butano-sequel.gba `
  --out build/w20-e1/blackfade-fix3 --keys "Down,Down,A*21" --zero-frames 240 `
  --hold-frames 4 --settle-frames 90 --frames 2552 --probe build/mgba-probe-w20e1/mgba-probe.exe

# 2) 出表（按**事件序号**对齐，不要按绝对帧号）
python tools/s49_blackfade/blackfade_report.py --frames build/w20-e1/blackfade-fix3/frames `
  --out build/w20-e1/blackfade-fix3/blackfade.json --markdown build/w20-e1/blackfade-fix3/blackfade.md
```

判据：B2 纯黑帧数**最小可达值**（并给出 BG 图块区 96 KB 的硬证据）、B3 = 0 帧、
B4 = 0 帧、事件 2/5 的淡入 = **24**、纯黑帧 sha256 仍是 `47fbde60709a2768…`。

---

## 6. 任务 3：时间线偏移（**未消掉，但归因被推翻**）

### 6.1 事实

| 事件 | C 路基线 ROM `4f24810b…` | wave20-E1 ROM `150dacf8…` | 差 |
|---|---:|---:|---:|
| 1 | 00527 | 00527 | **0** |
| 2 | 01549 | 01639 | +90 |
| 3 | 01659 | 01749 | +90 |
| 4 | 02123 | 02217 | +94 |
| 5 | 02171 | 02265 | +94 |

（`build/w19-c/blackfade-b6b/blackfade.json` vs `build/w20-e1/blackfade-fix1/blackfade.json`；
两次都是 2402 帧 / 2575 frames_run / 23 个按键，脚本相同。）

### 6.2 归因：**偏移不是 E1 的修法造成的**（已实测证明）

**决定性实验**：用**同一个探针、同一套参数、同一段按键脚本**（`Down,Down,A*21`，zero 240 / hold 4 / settle 90 / frames 2552）
对**已接受 ROM `e2182fff9…`（= 共享树，**没有** E1 的补丁）**重录黑场**：

```powershell
python tools/s49_package/capture_blackfade.py --rom build/s49-package-w19b/work/pinned-rom/measured.gba `
  --out build/w20-e1/blackfade-accepted --keys "Down,Down,A*21" --zero-frames 240 `
  --hold-frames 4 --settle-frames 90 --frames 2552 --probe build/mgba-probe-w20e1/mgba-probe.exe
python tools/s49_blackfade/blackfade_report.py --frames build/w20-e1/blackfade-accepted/frames `
  --out build/w20-e1/blackfade-accepted/blackfade.json --markdown build/w20-e1/blackfade-accepted/blackfade.md
```

| 事件 | C 路旧基线 ROM `4f24810b…` | **已接受 ROM `e2182fff9…`（无 E1 补丁）** | wave20-E1 ROM `150dacf8…`（有 E1 补丁） | E1 补丁的影响 |
|---|---:|---:|---:|---|
| 1 | 00527 | **00527** | 00527 | **0** |
| 2 | 01549 | **01639** | 01639 | **0** |
| 3 | 01659 | **01749** | 01749 | **0** |
| 4 | 02123 | **02217** | 02217 | **0** |
| 5 | 02171 | **02265** | 02265 | **0** |

⇒ **已接受 ROM（无 E1 补丁）与 wave20-E1 ROM（有 E1 补丁）的黑场表逐事件逐帧号完全相同**
⇒ **E1 的补丁对黑场时间线零影响** ⇒ **那 +90 / +94 的偏移是「wave 19 C 路旧 ROM ↔ 当前共享树」的差，
不是 E1 引入的**（父代理在任务书里的归因「E1 的修法把事件 2 从 01549 推到 01639」**不成立**）。

代码上也自洽：
* E1 的修法**只改 `battle_combat_stage_runtime_renderer::update()` 在
  `battle_phase_uses_full_screen_result(state.phase)` 为真时的行为**，
  而该相位集合是 `outcome / result / level_up / training / post_battle_dialogue / task_menu`
  —— **全部在战斗之后**（`battle_runtime_scene.cpp:295-310`），
  ⇒ **在物理上不可能影响事件 2/3/4/5（全部在战斗之前）的帧号**。
* 真实原因在 wave 19 D 之后进共享树的那批时序改动
  （`battle_black_field_event1_lead_frames = 30`、`battle_black_field_event2_lead_frames = 19`、
  星空遮罩 growth 接线、`battle_opening_title` 的 `lead_frames` 38→30 等）。

⇒ **本流没有消掉这个偏移**：它**不是本流的回归**，也不是 E1 的补丁造成的；
  真要消掉必须与**原版真值**（`notes/s49-fidelity/W3-original-truth.md` §3.2）逐事件对齐，
  属于「判定台对齐」那条线的工作，不在 E1 的所有权范围内。

---

## 7. 收据

| 收据 | 路径 | 内容 |
|---|---|---|
| 新 ROM | `build/w20-e1/butano-sequel/butano-sequel.gba` | sha256 `bf2c2e6e6eb03d4e1dcc876f939bd1d8cb9629c9ac6c10822d6a2c638c35826a` |
| 真实链（收据） | `build/w20-e1/chain-fix2/battle.json` | `poke=false` / `poke_commands=0` / `outcome=1` / `errors=[]` / 蜂 25→0 |
| 真实链（48 页） | `build/w20-e1/chain-fix2/shots/page-000…047.png` | `final_phase=task_menu` |
| poked 对照链 | `build/w20-e1/chain-fix2-poked/` | 結算屏与已接受 ROM **sha256 逐字节相同** |
| 逐屏差表 | `build/w20-e1/align-fix2.json` / `.md` | 8 屏 0 px，結算屏 985 px |
| 探针（自建） | `build/mgba-probe-w20e1/mgba-probe.exe` | **没用** `build/mgba-probe-w4/`（旧二进制，参数顺序不同） |
| 黑场基线 | `build/w20-e1/blackfade-fix1/`（wave20-E1 原有） | 5 事件表 |

---

## 8. 未完成项 / 接线请求

### 8.1 给父代理的接线请求

| # | 文件 | 改成什么 | 为什么 |
|---|---|---|---|
| **R-1** | `butano-sequel/game/src/battle_runtime_scene.cpp` | ① 应用 wave20-E1 的 +35 行调色板修法（`build/w20-verify/e1-palette-fix.patch`）；② **本流新增**：`battle_ui_runtime_renderer::update()` 的結算分支里，`_add_result_background();` 之前加 `_victory_background.reset();`（+13 行注释） | ① 解 Butano 调色板阻塞；② 解「結算底板共用槽 0 ⇒ 整屏偏绿」的 35 k px 残差。**两处必须一起上**，只上①会带着 +35 k px 回归 |
| **R-2** | — | 接线后**必须重跑 12 步流水线**（ROM 变了 ⇒ 棘轮会报 `incomparable` ⇒ 需要显式 `--accept-baseline`） | `W20-EXEC-BRIEF.md` §10 |

### 8.2 本流明确**没做**的事

| # | 事 | 状态 | 备注 |
|---|---|---|---|
| N-1 | 黑场 **B2**（准备→战斗 6 帧纯黑） | ❌ 未做 | 到 0 帧不可达（96 KB BG 图块区）；最小可达值**未量** |
| N-2 | 黑场 **B3**（生长→对白 2 帧纯黑） | ❌ 未做 | 根因已定位到 `battle_runtime_scene.cpp:5121-5122` |
| N-3 | 黑场 **B4**（对白内部 8 帧纯黑） | ❌ 未做 | 根因已定位到 `battle_visual_resource_coordinator.h:119-121` + `battle_runtime_scene.cpp:9204-9217` |
| N-4 | 事件 2/5 的**淡入 28 → 24** | ❌ 未做 | 根因已定位到 `battle_black_field_star_mask.h:146-152`（最后两级装不进一帧）；**是性能问题不是级数问题** |
| N-5 | **时间线偏移**消掉 | ❌ 未做（且**不该由本流做**） | 偏移来自 C 路旧 ROM ↔ 共享树的差，**不是 E1 补丁**；见 §6.2 |
| N-6 | 結算屏第 2/4 行的数字（`100/150/0`、`300/350/200`） | ❌ 不在 E1 范围 | = **E2/E4** 的阵型种子数据（`battle_experience` 全是 0） |

### 8.3 给下一轮的建议顺序

1. 父代理先接线 **R-1**（两处一起）⇒ 真实链 48 页 + 結算屏 985 px（真实战斗）/ 684 px（poked 同状态）+ 无错误屏。
2. **任务 2 单独开一轮**（E1 仍持有 `battle_runtime_scene.cpp` 与 `battle_visual_resource_coordinator.h`）：
   先做 **N-4**（星空遮罩最后两级的单帧预算，风险最低、收益最直接：直接决定「淡入 28 → 24」），
   再做 **N-2 / N-3**（同一段 8bpp 调色板交接，一起改才不会打架），最后做 **N-1**（最小可达值 + 96 KB 硬证据）。
3. **N-6** 交给 E2/E4：种子数据补上后，真值差应当从 985 → 0（真实链）与 684 → 0（poked 链）。
