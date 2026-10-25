# W20-RECOVER —— wave 20 四路的**产物回收**（E1 的调色板修法被找到并复核）

> 2026-10-25 14:5x · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 背景：wave 20 的 E1–E4 在 2026-10-25 01:48–01:51 被额度中断，
> **没有写出笔记**（`notes/s49-fidelity/W20-E1-*.md` 不存在）。
> 但按 AGENTS.md 的纪律「lost ≠ 没干活」，本次收口巡检**按文件系统把四路的产物翻了一遍**，
> **捞回了 E1 的一份完整且已验证的修法**。
> 依据：`notes/s49-fidelity/INCIDENT-wave5-task-loss-20261024.md` §3 的接管流程。

---

## 0. 一句话结论

> ⭐⭐ **wave 20 的 E1 实际上已经做完了「Butano 调色板耗尽」的修法，并且验证过：
> 真实战斗打完仗后，结算链 7 段**全部录到**（48 页、`final_phase = task_menu`、无错误屏）。**
>
> ⇒ 收口笔记里写的「阻塞 #1 仍然开放」**只对 `e2182fff9…` 这一个 ROM 成立**；
> **修法本身已经在盘上**，只是没被接线回共享树、也没有笔记。
>
> ⛔ 但同时查出一件事：**E1 的修法让結算屏多了一处新的画面差**（35,006 px，见 §3）
> ⇒ **不能直接照搬**，必须连同那处一起修。

---

## 1. E1 的修法（唯一改动的文件：`battle_runtime_scene.cpp`）

### 1.1 树对比（穷举，不是抽样）

对 `build/w20-e1/butano-sequel` 与共享树 `butano-sequel/` 做**全文件 sha256 对比**：

```
identical files: 304
DIFFERENT: ['butano-sequel.elf', 'butano-sequel.gba',
            'game\\src\\battle_runtime_scene.cpp']
lane-only (excl .gba): []   count 0
```

⇒ **E1 的副本 = 共享树 + 只改了 `battle_runtime_scene.cpp` 一个文件**（+ 它的构建产物）
⇒ **这个修法可以直接搬进共享树**，不需要移植别的改动。
（`graphics/` 1852 个资产文件**逐一相同**，说明 E1 没有偷改资产。）

### 1.2 改的是哪一行

在 `battle_runtime_scene.cpp` 的 `update(...)`（背景绑定函数，L5509 起）**函数体最前面**插入：

```cpp
if(battle_phase_uses_full_screen_result(state.phase))
{
    // ... 注释说明 8bpp/256 色胜利屏背景要吃满 16 槽，
    //     4bpp/32 色的决斗森林要 2 个连续槽，两者无法共存 ...
    if(_duel_background_bound || _movie_background_bound ||
            _cutin_background_bound || _duel_hud_background)
    {
        _release_resources();
        _duel_background_bound = false;
        _movie_background_bound = false;
        _cutin_background_bound = false;
    }
    return;
}
```

**思路**：进入 `outcome` / `result` 这类**全屏结算相位**时，
**先把决斗森林（4bpp/32 色）与决斗 HUD 释放掉**，再让 8bpp/256 色的胜利屏背景进来
⇒ 16 槽 bank 不再被两个屏幕尺寸的背景同时占。

⚠️ 注释里明确写了**故意不做 `bn::core::update()`**：core update 要等垂直消隐，
多加一次会把整个场景往后推 2 个 GBA 帧。

### 1.3 补丁文件（已落盘）

```
build/w20-verify/e1-palette-fix.patch      2,532 B / 50 行 diff / +35 行
```

（`difflib.unified_diff` 生成，`n=6` 上下文；可 `git apply` 到共享树。）

---

## 2. ⭐ E1 的验证证据（三份收据，链式可追）

### 2.1 E1 lane 的三跑对比（同一 ROM `150dacf8…`）

| 跑 | ROM sha | 结算链页数 | final_phase | stuck_at | Butano 错误屏 | palette_status |
|---|---|---:|---|---|---|---|
| `chain-base`（**修前**） | `1107c1f9…` | **1** | `outcome` | 6 | ✅ **true** | `present: true`（bank 只剩 1 个 8bpp/256） |
| `chain-fix1`（**修后**） | `150dacf8…` | **48** | `task_menu` | — | ❌ **false** | `present: false` |
| `chain-fix1-tc`（**修后 + 重跑**） | `150dacf8…` | **48** | `task_menu` | — | ❌ **false** | `present: false` |

⇒ **修法确实解掉了调色板阻塞**（`chain-base` → `chain-fix1` 就是 A/B 对照，同一 lane、同一探针）。

### 2.2 真实战斗（**不是 poke**）

`build/w20-e1/chain-fix1-tc/real/battle.json`：

| 判据 | 值 |
|---|---|
| `entry.method` | 「real battle: the closed-loop driver plays the battle with the buttons only, and the outcome is the product code's own decision」 |
| `entry.poke` | `false` |
| `entry.poke_commands` | **0**（`probe_commands` 4,602） |
| `outcome` / `round` | **1** / 13 |
| `frames_run` | 25,848 |
| `errors` | `[]` |
| `bee_hp_start → bee_hp_end` | 5 只蜂 **25 → 0** |
| `bee_hp_dropped` / `escort_alive` | `true` / `true` |
| `from_real_battle` | `true` |
| 结算链 | **48 页**，`phases_seen` = `outcome, result, level_up, training, post_battle_dialogue, task_menu`（**7 段的相位全走到了**） |

### 2.3 ⭐ 真实链里 **9 帧与原版真值逐字节相同**（sha256 精确匹配）

原版真值目录：`build/s49-victory-capture/w4/settlement-truth/`（9 张图）

| 真实链页 | 原版真值 | 匹配 |
|---|---|---|
| `page-000-outcome.png` | `01-victory.png` | ✅ sha 相同 |
| `page-002-level_up.png` | `04-levelup-sasuke.png` | ✅ |
| `page-003-level_up.png` | `05-levelup-sasuke-jutsu-name.png` | ✅ |
| `page-004-level_up.png` | `04-levelup-konohamaru.png` | ✅ |
| `page-005-level_up.png` | `05-levelup-sasuke.png` | ✅ |
| `page-006-level_up.png` | `06-levelup-sakura.png` | ✅ |
| `page-007-level_up.png` | `07-ninja-tool-list.png` | ✅ |
| `page-014-post_battle_dialogue.png` | `08-postbattle-dialogue-1.png` | ✅ |
| `page-021-task_menu.png` | `09-task-menu-map.png` | ✅ |

⇒ **「真实战斗打完仗后結算链能走完 7 段」这句话，第一次被实测证明了。**
（此前只有 *poked* 链的 48 页对照表，见 `W20-PARENT-wrapup.md` §8.2 的口径澄清。）

---

## 3. ⛔ 但 E1 的修法**引入了新的画面差**：結算屏 +35,006 px

### 3.1 复现（不需要重建）

| 画面 | 结算屏（`page-001-result.png`） |
|---|---|
| **原版真值** `02-settlement-exp-power-turns.png` | — |
| **已接受 ROM `e2182fff9…`（无 E1 修法，poked 链）** | 与真值差 **684 px**（就是「戰鬥分」那一行） |
| **E1 lane `150dacf8…`（有 E1 修法，真实链）** | 与真值差 **35,016 px**；与「已接受 ROM 的結算屏」差 **35,006 px** |

### 3.2 机制：**背景层被放掉了，結算屏画在了错误的地板上**

逐像素取色对比（結算屏上边条与中部）：

| 位置 | 已接受 ROM | E1 lane |
|---|---|---|
| 顶栏主色 | `(99,189,115)` 灰绿 | `(33,33,33)` 深灰 |
| 顶栏副色 | `(231,247,214)` 米白 | `(173,173,49)` 橄榄 |
| 中部背景 | `(107,107,107)` 灰 | `(66,99,16)` **草绿** |
| 中部背景 2 | `(99,99,99)` 灰 | `(8,41,0)` **深绿** |

⇒ E1 的結算屏**整块偏绿** ⇒ 它画在**决斗森林的调色板**上，而不是結算屏自己的底板。

**根因（从代码读出来）**：E1 在 `battle_phase_uses_full_screen_result()` 为真时
`return` 掉了 —— 但**它 return 掉的是「背景绑定」这条路**，
而結算屏自己的底板（`battle_ui_result_plate`，8bpp/32 色，2 槽）
在另一条路上建（`battle_runtime_scene.cpp:1364-1388` 的 UI 层分派）。
⇒ **8bpp/256 色的胜利屏背景 + 8bpp/32 色的結算底板 + 决斗森林的 4bpp 槽位**
三者仍会在某一帧同时被申请 ⇒ 调色板不再报错，但**畫面落在了错的调色板/错的 BG 层上**。

⚠️ **这不是 E1 的错，是它被截断造成的**（它没写笔记 ⇒ 没走完"重测 + 修残差"这一步）。
⇒ **wave 20 复开的人必须把这一处一起修**，否则「修好调色板 ⇒ 結算屏反而差 35 k px」。

### 3.3 判定

| 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|
| P-30 E1 的修法解掉了调色板阻塞 | 同 lane、同探针，`chain-base` vs `chain-fix1` | 成立（1 页 → 48 页，错误屏消失） | **已确认** |
| P-31 E1 的修法只改了 `battle_runtime_scene.cpp` 一个文件 | 全树 sha256 对比（304 相同 / 1 不同 / 0 lane-only） | 成立 | **已确认** |
| P-32 E1 的修法让結算屏变差 | 像素差 + 取色对比（灰 → 草绿） | 成立（+35,006 px） | **已确认** |
| P-33 E1 的修法可原样搬进共享树 | 只改一个文件 ⇒ 可直接 `git apply`；但**必须先修 §3.2** | **不成立**（会带着 +35 k px 回归） | **已证伪** |

---

## 4. E1 的黑场产物：**没做完，但拿到了基线**

`build/w20-e1/blackfade-fix1/blackfade.json`（ROM `150dacf8…`，2402 帧，5 个事件）：

| 事件 | 帧段 | 总帧 | 纯黑 | 淡出 | 淡入 | 对照 C 路基线 |
|---|---|---:|---:|---:|---:|---|
| 1 | 00527–00532 | 6 | **6** | 0 | 0 | **B2 未修**（与 C 路同） |
| 2 | 01639–01708 | 70 | 18 | 24 | **28** | 淡入 28（应 24）⇒ **未修** |
| 3 | 01749–01750 | 2 | **2** | 0 | 0 | **B3 未修** |
| 4 | 02217–02224 | 8 | **8** | 0 | 0 | **B4 未修** |
| 5 | 02265–02344 | 80 | 24 | 28 | **28** | 淡入 28（应 24）⇒ **未修** |

⚠️ 注意**帧号整体后移**（事件 2 从 01549 → 01639，事件 4 从 02123 → 02217）
⇒ **E1 的修法本身把场景时间线往后推了** ⇒ 与 §3.2 的「多等一个 core update / 释放时机」一致。

⇒ **黑场 B2/B3/B4 E1 一件都没做完**，只剩这份基线表可用。

---

## 5. E2 的产物：**测试骨架写好了，但没改产品代码**

| 文件 | 状态 | 内容 |
|---|---|---|
| `build/w20-e2/butano-sequel/game/tests/test_battle_experience_award.cpp` | ✅ 写完（177 行） | 锁「戰鬥分」三条规则（见 §5.1） |
| `build/w20-e2/butano-sequel/game/tests/e2_dbg.cpp` | ✅ 写完 | 打印各场景的 enemy 种子与 reward record |
| 产品代码 | ❌ **一行没改** | `battle_action_system.h` / `battle_results.h` 未动 |

### 5.1 E2 写下的**规则假设**（父代理已只读复核，见 §5.2）

> **阵型种子**：battle 14 的 5 个敌人**各带 50 戰鬥分**，玩家单位不带 0。
> **发奖**：敌人被击倒 ⇒ 它的戰鬥分**转给攻击者**，敌人自己清零。
> **结算**：結算屏第 2 行「戰鬥分」= 该角色所有存活单位身上的戰鬥分之和（+ 被动 0x15 百分比）。

### 5.2 父代理的只读复核（结论：方向对，但**两处前提在当前代码里不成立**）

| E2 的断言 | 复核 | 结论 |
|---|---|---|
| 「敌人被击倒 ⇒ 戰鬥分转给攻击者」 | `battle_action_system.h:2327-2333` **已经有这个逻辑**（`target.active = false` 之后 `experience_recipient.carried_experience += target.carried_experience; target.carried_experience = 0;`） | ✅ **已存在** ⇒ E2 不用实现它 |
| 「battle 14 的 5 个敌人各带 50 戰鬥分」 | 读 `generated_battle_scenario_content.h` 的 **scenario 14**（`battle_scenario_definition{ 14, 15, 19, 1U, ...}`）：9 个有效 slot 的 `battle_experience` 字段**全是 0**（`battle_scenario_unit_slot{ true, ..., 55, battle_side::enemy, grid_point{ 3, 4 }, battle_facing::up, 0, ... }` —— 第 7 个参数就是 `battle_experience`） | ⛔ **前提不成立** ⇒ 要么**生成器没填这个字段**（要改 `tools/generate_butano_battle_scenario_content.py` + 重新生成），要么 **50 这个数来自别处** |
| 「`battle_scenario_loader.h:465` 会把种子搬进 `carried_experience`」 | 复核：**成立**（`unit.carried_experience = static_cast<int>(slot.battle_experience);`） | ✅ 通路在，**只差数据** |
| 「結算第 2 行 = 存活单位身上之和」 | `battle_results.h:369-395` 的 `_battle_experience()` **正是这个口径** | ✅ 口径本来就对 |
| 「原版真值：S49 經驗值 125/125/125、戰鬥分 100/150/0、回合數 75/75/75、合計 300/350/200」 | ⭐ **父代理独立读图确认**：真值 `02-settlement-exp-power-turns.png` 的四行数字 = `125/125/125`、`100/150/0`、`75/75/75`、`300/350/200`；重制侧 = `125/125/125`、**`0/0/0`**、`75/75/75`、`200/200/200` | ✅ **真值成立**；差 **684 px** 就是第 2 行 `100/150/0` vs `0/0/0` + 第 4 行 `300/350/200` vs `200/200/200` |

⇒ 🎯 **E2 真正缺的不是「发奖规则」（那已经有了），而是「阵型表里的种子数据」**
⇒ 归到 **E4**（逆向取证：battle 14 的敌人在 ROM 阵型记录里到底带多少戰鬥分）
⇒ **E2 的测试文件可以直接复用**（它已经是可编译的断言骨架）。

⚠️ 另注：E2 的注释写「阵型记录 +0x0C」（ROM `0x5461C4 + group*0x1AAC + variant*0x08E4 + 4 + record*0x0B8`）
⇒ 与生成头里的 provenance 一致（`reverse-source-rom: 0x5461C4+317952`）
⇒ **这条取证路径是可信的**，但 E2 没跑出数字（它的 `e2_dbg.cpp` 只打印本仓数据，不读 ROM）。

---

## 6. E3 / E4 的产物

| 流 | 产物 | 结论 |
|---|---|---|
| **E3** | `build/w20-e3/{align-e3.json, orig-bg.json, remake-bg.json}` + `capture-remake/` | ✅ **有实质进展**：步偏移扫描出 **best_offset = 4**（total 648,356 → **148,914 px**）；`exact_matches` 3 对（`step-14/15/17-A` ↔ `step-18/19/21-A`，offset 4）。**产品代码 0 行改动**（E3 的 4 个独占文件一个没动） |
| **E4** | `build/w20-e4/`（`orig-step-*.png`、`scenario-46-lineup-pool.bin`） | 有原版取证素材，但**没有笔记、没有清单**；33 张无人引用的旧对白资产**未清理** |

---

## 7. 给 wave 20 复开者的执行顺序（已按「依赖」重排）

> ⛔ **E1 不再是「从零修调色板」，而是「搬一个已验证的修法 + 修它的残差」。**
> ⛔ **E2 不再是「实现发奖规则」，而是「补阵型种子数据 + 复用已写好的测试」。**

| 优先 | 流 | 做什么 | 判据 |
|---|---|---|---|
| **1** | **E1** | ① `git apply build/w20-verify/e1-palette-fix.patch`；② **修 §3.2 的背景层归属**（結算屏必须画在自己的底板上，而不是森林的调色板）；③ 顺带核对时间线后移（§4） | 真实链 **48 页 + 結算屏 ≤ 684 px + 无 Butano 错误屏**（三者同时成立才算过） |
| **2** | **E4** | 取证 **battle 14 的敌人在 ROM 阵型记录里的戰鬥分种子**（路径见 §5.2：`0x5461C4 + group*0x1AAC + variant*0x08E4 + 4 + record*0x0B8`，记录内 `+0x0C`） | 给出 5 个敌人各自的种子值（E2 猜是 50） |
| **3** | **E2** | ① 把 E4 的种子值填进**生成器**并重新生成 `generated_battle_scenario_content.h`；② 复用 `test_battle_experience_award.cpp`；③ 只在缺失处改 `battle_action_system.h` / `battle_results.h` | 結算屏第 2 行 = `100/150/0`、第 4 行 = `300/350/200` ⇒ **684 px → 0 px** |
| **4** | **E1**（续） | 黑场 **B2 / B3 / B4** + 事件 2/5 淡入 28 → 24（E1 一件都没做完，基线表见 §4） | B2 给出最小可达值 + 硬证据；B3/B4 收掉 |
| **5** | **E3** | 用它已测出的 **best_offset = 4** 作起点，继续拆「相机/布景语义映射」（两侧地图不同 ⇒ 寄存器原值不可直接比大小） | 战斗段首帧的 ~73 k px 下降 |

⚠️ **判据必须是「三者同时成立」**（48 页 ∧ 結算屏 ≤ 684 px ∧ 无错误屏）：
**只满足前者的修法就是 E1 现在这个状态 —— 它会让結算屏差 35 k px。**

---

## 8. 收口笔记的更正

`notes/s49-fidelity/W20-PARENT-wrapup.md` §8.4 写的是
「调色板阻塞在已接受 ROM 上原样存在」⇒ **该结论本身仍然成立**（`e2182fff9…` 确实还在报错），
但**「阻塞 #1 没有解法」这个隐含判断要更正**：**解法已经存在并被验证过，在 `build/w20-e1/` 里。**
⇒ 收口时把 wave 20 说成「四路颗粒无收」是**低估了**：E1 其实交付了核心修法 + 完整验证链，
只是**没有笔记、没有接线回共享树**。

---

## 9. 本节新增假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| P-30 | E1 的修法解掉了调色板阻塞 | 同 lane 同探针 A/B（`chain-base` vs `chain-fix1`） | 成立（1 页 → 48 页） | **已确认** |
| P-31 | E1 只改了一个文件 | 全树 sha256 对比（304 相同 / 1 不同 / 0 lane-only） | 成立 | **已确认** |
| P-32 | E1 的修法让結算屏变差 | 像素差 + 取色对比 | 成立（+35,006 px，灰 → 草绿） | **已确认** |
| P-33 | E1 的修法可原样搬进共享树 | 依赖 §3.2 | **不成立** | **已证伪** |
| P-34 | 「击倒 ⇒ 戰鬥分转给攻击者」需要实现 | 读 `battle_action_system.h:2327-2333` | **证伪**（已有） | **已证伪** |
| P-35 | battle 14 的敌人阵型带 50 戰鬥分 | 读 `generated_battle_scenario_content.h` 的 scenario 14 | **证伪**（种子字段全是 0） | **已证伪** |
| P-36 | 原版結算屏第 2 行 = `100/150/0`、第 4 行 = `300/350/200` | 独立读真值图 + 重制侧图 | 成立（差 684 px 全部在这两行） | **已确认** |
