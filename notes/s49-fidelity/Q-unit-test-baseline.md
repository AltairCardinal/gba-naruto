# Q 流 · 重制线单元测试基线 —— 20 项失败是**预存债**，wave 3/4 零回归

> 2026-10-24 · 主代理（mvs_4e730a9ded524558a303c115875a9707）
> 实验脚本：`build/run-baseline-tests.sh`（HEAD 基线）、`build/w1-run-all-tests.sh`（工作区）、
> `build/size_probe.cpp`（结构体尺寸探针）。
> **未改动**任何产品代码、任何已有测试、逆向线。

---

## 0. 一句话结论

**20 个单元测试失败在重制线 HEAD 就已经红了** ⇒ **预存债**，不是 wave 3/4 引入的回归。
⇒ 出包门禁必须是**棘轮式**（失败集合逐名相同），不是「全绿」。

---

## 1. 实验设计（是/否问题）

> **问题**：wave 3/4 的产品改动有没有把原本绿的测试改红？

方法：用 `git archive HEAD` 把重制线 **HEAD 快照**抽到 `build/head-baseline/`
（**只抽 `butano-sequel/game`**，单测只需要 `game/include` + `game/tests`，不依赖 butano 运行时），
对 HEAD 与当前工作区跑**完全相同**的单测（同样的 g++ 旗标、同样的用例目录）。

```powershell
git -C 'D:\Shell\Github\gba-naruto-butano' archive --output=...tar HEAD butano-sequel/game
tar -xf ...tar -C 'D:\Github\gba-naruto\build\head-baseline'
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh   # HEAD
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh     # 工作区
```

⚠️ **不用 `git stash`**：wave 5 的四个子代理正在并行改同一棵树，stash 会毁掉它们的在途改动。
`git archive` 对仓库**只读**。

---

## 2. 结果

| | HEAD 基线 | 当前工作区（wave 3/4 之后） |
|---|---:|---:|
| 头文件数 | 137 | 139（wave 3 新增 2） |
| 测试数 | 121 | 123（wave 3 新增 2） |
| **pass** | **101** | **103** |
| **fail** | **20** | **20** |
| 失败集合 | — | **逐名完全相同** |

⇒ **wave 3 新增的 2 个测试全部通过**；
⇒ **没有任何既有测试从绿变红** ⇒ **零回归**。

### 2.1 20 个失败（HEAD 与工作区一模一样）

```
test_battle_all_scenario_runtime
test_battle_campaign_route
test_battle_campaign_save
test_battle_campaign_scenario_42
test_battle_campaign_scenario_43
test_battle_campaign_scenario_44
test_battle_campaign_scenario_45
test_battle_campaign_scenario_46
test_battle_campaign_scenario_47
test_battle_campaign_scenario_49
test_battle_dynamic_deployment_turn
test_battle_material_pickups
test_battle_presentation_controller
test_battle_runtime_scene_gate
test_battle_s49_input_flow
test_battle_s49_opening
test_battle_scene_character_actions
test_battle_scene_controller
test_battle_scene_multi_unit
test_battle_scene_results
```

失败形态：
* 19 个是 `controller.tick().success()` / `move_cursor(...).success()` / `phase == ...` 的
  **断言失败**（`Aborted (core dumped)`）；
* 1 个是 `test_battle_runtime_scene_gate` 的**编译期静态断言**：
  ```
  sizeof(battle_scene_snapshot<12>) <= 1120   ->  实际 1672
  sizeof(battle_runtime_scene_telemetry) == 824 ->  实际 868
  ```

---

## 3. 根因：尺寸门禁在 HEAD 就已经漂了

结构体尺寸探针（`build/size_probe.cpp`，两侧各编译一次）：

| 结构体 | HEAD 基线 | 当前工作区 |
|---|---:|---:|
| `battle_scene_snapshot<12>` | **1672** | **1672** |
| `battle_runtime_scene_telemetry` | **868** | **868** |
| `battle_scene_unit_view` | 56 | 56 |
| `battle_player_action_flow_snapshot` | 360 | 360 |
| `battle_presentation_script_snapshot` | 48 | 48 |

⇒ **两侧逐项相同** ⇒ 这**不是** wave 3/4 的锅。
⇒ `battle_scene_controller.h` / `battle_runtime_scene.h`（两个结构体的宿主头）**根本没被 wave 3/4 改过**
（`git diff HEAD -- butano-sequel/game` 显示改动只有 5 个头 + 1 个 cpp + 4 个测试 + 2 个新头 + 2 个新测试）。
⇒ **预存债**：有人给 snapshot / telemetry 加了字段，却没更新尺寸门禁。

**顺带排除过一个错误假设**：我一度怀疑是 H2 往 `battle_unit_visual_animation.h` 加了数据成员撑大的
⇒ **不是**：H2 加的全是 `static constexpr` 成员函数，**没有新数据成员**
（见 `git diff HEAD -- battle_unit_visual_animation.h`）。

---

## 4. 对出包门禁的影响（**口径已改**）

| 原口径 | 新口径 |
|---|---|
| 「`battle/tests/` 全绿」 | ❌ 做不到（预存债 20 项红） |
| — | ✅ **棘轮式**：当前工作区的**单测失败集合**必须与 HEAD 基线**逐名相同**；<br>多出任何一项 ⇒ exit≠0；少掉任何一项 ⇒ **算改进，不判红** |

⇒ 出包清单第 9 项「单元测试全绿」改写为「**单元测试零回归（与 HEAD 基线对照）**」。
⇒ 1:1 报告里必须写「**20 项单测在 HEAD 即为红（预存债），本次零回归**」，
**不许**写成「单测全绿」，也**不许**把它算成本次的成果。

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Q1 | 20 个失败是 wave 3/4 引入的回归 | `git archive HEAD` 抽基线 + 同套单测对照 | HEAD 也是 20 个，**逐名相同** | **已证伪** |
| Q2 | wave 3 新增的 2 个测试是红的 | 工作区 pass=103 = HEAD pass=101 + 2 | 2 个新测试**都通过** | **已证伪** |
| Q3 | 尺寸膨胀来自 wave 3/4 改过的头 | 结构体尺寸探针两侧对照 | 1672 / 868 **两侧完全相同** | **已证伪** |
| Q4 | 是 H2 往 `battle_unit_visual_animation.h` 加数据成员撑大的 | 看 diff：全是 `static constexpr` 函数 | 无新数据成员 | **已证伪** |
| Q5 | 宿主头 `battle_scene_controller.h` / `battle_runtime_scene.h` 被改过 | `git diff HEAD -- butano-sequel/game` | 两者都**未出现在改动列表** | **已确认** |
| Q6 | 出包门禁可以用「全绿」 | HEAD 自身就红 20 项 | 不可用 | **已证伪**（改棘轮式） |

---

## 6. 复跑命令

```powershell
# 1) 抽 HEAD 基线
$dst = 'D:\Github\gba-naruto\build\head-baseline'
git -C 'D:\Shell\Github\gba-naruto-butano' archive --output="$dst.tar" HEAD butano-sequel/game
tar -xf "$dst.tar" -C $dst

# 2) HEAD 基线单测
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh

# 3) 当前工作区单测
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh

# 4) 结构体尺寸对照
wsl -d Ubuntu-24.04 -- bash -lc "g++ -std=c++23 -I /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel/game/include /mnt/d/Github/gba-naruto/build/size_probe.cpp -o /tmp/a && /tmp/a"
wsl -d Ubuntu-24.04 -- bash -lc "g++ -std=c++23 -I /mnt/d/Github/gba-naruto/build/head-baseline/butano-sequel/game/include /mnt/d/Github/gba-naruto/build/size_probe.cpp -o /tmp/b && /tmp/b"
```
