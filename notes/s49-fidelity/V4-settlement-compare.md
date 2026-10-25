# 流 V4 —— 结算链对照（原版真值 vs 重制侧）

> 工具：`tools/s49_victory_capture/v4_*.py`、`tools/s49_victory_capture/v4_route_gen.cpp`
> 产物：`build/s49-victory-capture/v4/`
> 2026-10-24 · stream V4（wave 9）。**所有数字都是本机实测。**
> 逆向线 `D:\Shell\gba-naruto-reverse` **全程只读**；重制线 **零改动**；**未提交 git**。

---

## 0. 一句话结论

**结算链的「结构差」查清了，但「运行帧逐屏对照」本波没做成。**
重制侧的结算链**在产品代码里是完整的**（`outcome → result → level_up → training → complete`
五段全在 `battle_scene_controller.h` 里），原版的真值（wave 8 的 W4 打赢后录到的
9 张图 + sha256 收据）也可用；
**两边的链子不是同一条**：原版是「勝利 → 结算屏 → 四人升级屏 → 忍具表 → 对白 → 任务菜单」，
重制侧是「outcome → 结算屏 → 升级页 → 训练/装备页 → complete」——
**重制侧没有「四人升级屏」那样的逐人升级页，升级信息被并进结算屏与训练页**，
**也没有「战后对白」与「任务菜单」两屏**，
**「忍具表」对应的是重制侧的 `training` 段**（实测录到了
「NO AVAILABLE TOOL」「AVAILABLE TOOL」「EQUIP COMPLETE」「隊員一覧表」四张屏）。
⚠️ **重制侧的「勝利」屏与结算屏没有录到**：battle-14 在重制侧**打不赢**（见 §4 的实测），
结算链只能从**败北**的 outcome 进去 ⇒ 逐屏**运行帧**对照表**本波未达成**；
本波只交付了**资产级（静态图层）对照**：结算屏 **12,798 / 38,400 px（33.3%）**、
升级屏 **7,681（20.0%）**、训练页 **8,483（22.1%）**。

---

## 1. 改动文件清单（全部是本流独占目录 / 本流新建）

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_victory_capture\v4_route_gen.cpp` | **新增** | ⭐ **离线按键脚本生成器**：用重制侧自己的 `battle_scene_controller`（**只读** include）跑一遍 S49，把每一次 controller 调用记成对应的按键（重制侧的输入分派是统一的：A→confirm、B→cancel、四方向→move_cursor、L/R→cycle_unit） |
| `D:\Github\gba-naruto\tools\s49_victory_capture\v4_replay.py` | **新增** | 在 ROM 上重放按键脚本并逐帧录下（Lua 帧回调，帧精确） |
| `D:\Github\gba-naruto\tools\s49_victory_capture\v4_remake_boot.py` | **新增** | 重制侧开机 + 按键序列的逐帧录制（诊断用） |
| `D:\Github\gba-naruto\tools\s49_victory_capture\v4_frame_runs.py` | **新增** | 把帧目录聚成「像素相同的连续屏」 |
| `D:\Github\gba-naruto\tools\s49_victory_capture\v4_settlement_compare.py` | **新增** | ⭐ **逐屏对照表**：重制侧每一屏 × 原版真值每一图 ⇒ sha256 / 差 px / 差 bbox |
| `D:\Github\gba-naruto\tools\s49_victory_capture\v4_settlement_assets.py` | **新增** | ⭐ **资产级（静态图层）对照**：重制侧 `battle_ui_result_*` / `battle_ui_level_up_panel` / `battle_ui_training_panel` 按场景层次叠放后与原版真值逐像素比 ⇒ sha256 / 差 px / 差 bbox |
| `D:\Github\gba-naruto\tools\s49_victory_capture\capture_victory_frames.lua` | **改** | 扩展：按键 token 支持 `key:settle:hold` 与纯等待 `:settle`（**向后兼容**，W4 的原版驱动器不受影响） |
| `D:\Github\gba-naruto\tools\s49_package\make_report.py` | **改** | 加 §15「结算链对照」一节 |
| `D:\Github\gba-naruto\build\s49-victory-capture\v4\**` | 临时产物 | 脚本、收据、逐帧录下、联络表 |

**没有**改重制线任何文件、逆向线任何文件、其它流的任何仪器
（`s49_pairing` / `s49_blackfade` / `s49_overlay_align` / `s49_fidelity_report*` /
`s49_save_boundary` / `s49_audio_l` / `s49_idle_*.py` / `s49_orig_map` /
`s49_starfield` / `s49_w3_dialogue` / `s49_x3_boundary` / `s49_opening_title`
一律只读调用）。

---

## 2. 方法：为什么「离线算按键、机器上回放」可行

重制侧的输入分派是**统一的**（`battle_runtime_scene.cpp:8264-8336`）：

| 键 | controller 调用 |
|---|---|
| A | `controller.confirm()` |
| B | `controller.cancel()` |
| ← → ↑ ↓ | `controller.move_cursor(±1, 0 / 0, ±1)` |
| L / R | `controller.cycle_unit(∓1)` |

⇒ **每个键恰好对应一次 controller 调用** ⇒ 可以**离线**用重制侧自己的控制器
把整场仗跑一遍，把每一次调用记成按键，再在 ROM 上回放。

`v4_route_gen.cpp` 因此是**重制侧自己的场景 49 单测**（`test_battle_campaign_scenario_49.cpp`）
套一层「按键记录器」：**路线逻辑是那条被测过的路线**，只补了单测缺的两样东西：

1. **回合横幅**（`battle_mission_rules.show_turn_banner = true`，battle-14）：
   横幅吃掉一次按键 ⇒ 单测里没有它（**这条正是 `test_battle_campaign_scenario_49`
   在 HEAD 即为红的原因之一**）。
2. **战役背包**（`campaign.inventory` + `apply_battle_campaign_scene_policy`）：
   不传就没有忍具（`ninja_tool_action_definitions` 一条都不进列表）。

---

## 3. 实测到的重制侧战斗规则（全部来自重制侧自己的数据）

| 项 | 实测值 | 出处 |
|---|---|---|
| 重制侧的战役起点 | **49**（`battle_campaign_route_initial_scenario = 49`）⇒ **开机就在 S49 battle-14**，不用先打通 41–48 | `battle_campaign_route.h:14` |
| 战斗初始站位 | 鸣人 (11,6) / 佐助 (10,14) / 小樱 (8,14) / 护送木叶丸 (10,7) / 五只蜂 (3,4)(4,8)(3,11)(6,6)(5,13) | 本流离线控制器 |
| 鸣人可用招式 | 变身术(2, 范围 3, **打空格**) / 影分身(7, 范围 2, 打空格) / **忍者组合拳(5, 范围 1, 威力 10, 打敌方)** / 忍具 1（范围 3, 威力 6, 打敌方）/ 忍具 11（范围 3, 威力 6, 打敌方）/ 忍具 37（范围 2, 打自己） | 重制侧 `active_action_definitions` / `ninja_tool_action_definitions` |
| 佐助可用招式 | 影分身(2, 范围 3, 打空格) / **火遁术(16, 范围 2, 威力 15, 打敌方)** / 忍者组合拳(5, 范围 1, 威力 10) | 同上 |
| 小樱可用招式 | 影分身(1, 范围 2, 打空格) / 影分身(2, 范围 3, 打空格) / 忍者组合拳(5, 范围 1, 威力 10) | 同上 |
| ⭐ **攻击必须是直线** | 目标格必须与敌人**同行或同列**；否则 `action_error::occupied_target_tile`（= 8） | `battle_action_system.h:1148` |
| ⭐ **打空格不能打单位** | `target_policy_kind::empty_tile` 的招式打有人的格子会被拒 ⇒ **只有 `opponent_unit` / `occupied_unit` 的招式能打人** | 同上 |
| ⭐ **忍术列表只有走完移动才非空** | 在单位选择阶段打开「術・忍具」列表是 **0 条**；移动确认之后才有条目 | 本流实测（`player.action_count`） |
| 护送木叶丸的血量 | **40**，每回合掉 **12**（40 → 28 → 16 → 4 → 0，第 5 轮死） | 本流离线控制器逐轮打印 |
| 蜜蜂的行为 | **会逃**：追击策略下五轮内一次都进不了近战范围（距离始终 ≥ 2） | 本流离线控制器（五种策略对比） |

---

## 4. ⭐ 重制侧 S49 battle-14 打不赢（实测，5 种策略）

| 策略 | 结果 |
|---|---|
| ① 单测原版路线（追最弱的蜂） | 五轮 **0 命中**（蜜蜂一直逃，距离 2–8）；护送 4 轮掉光 ⇒ 败北 |
| ② 追「离护送最近」的蜂 | 命中 7 次 / 打死 2 只；护送 40 → 16 ⇒ 败北 |
| ③ 守护护送（站到护送旁边） | 0 命中 |
| ④ 用忍具（范围 3）远程打 | 0 命中 |
| ⑤ 站到护送旁边 + 优先打贴着护送的蜂 | 命中 7 次 / 打死 2 只；护送 40 → 16 ⇒ 败北 |

⇒ **两条硬约束**（都来自重制侧自己的数据）：

* **护送 40 HP，蜜蜂每回合打 12 ⇒ 最多活 4 轮**；
* **玩家每回合最多 3 次攻击、单次伤害 10（原版的十字手里剑是 27）** ⇒
  打死五只蜂（5 × 25 = 125 HP）**至少要 13 次命中**，
  而 4 轮只有 12 次 ⇒ **打不完**。

⇒ ⚠️ **这是「重制侧 balance 与原版不一致」的直接证据**，
不是一个驱动器的缺陷：原版靠十字手里剑（27 伤害 / 距离 3）7 回合打死 5 只蜂，
重制侧没有这一招 ⇒ **要么补忍具伤害，要么把护送血量/蜜蜂伤害调回原版。**
（施工单见 §6。）

---

## 5. 结算链：两边的结构差

| 段 | 原版（wave 8 的 W4 真值） | 重制侧（wave 9 的 V4 实测） |
|---|---|---|
| 1 | 「勝利」屏 | `outcome` 段（**本波录到的是敗北版**） |
| 2 | 结算屏（经验值/战力/回合数） | `result` 段 |
| 3 | **四人升级屏**（鸣人/木叶丸/佐助/小樱，各一张） | `level_up` 段（**逐人升级页，并入升级信息**） |
| 4 | **忍具一览** | ⭐ **`training` 段**（对应物）：实测录到「AVAILABLE TOOL」「NO AVAILABLE TOOL」「EQUIP COMPLETE」「隊員一覧表」 |
| 5 | 战后对白 | — |
| 6 | 任务菜单（术之里地图） | — |

### 5.1 ⭐ 资产级（静态图层）对照

⚠️ **口径**：重制侧运行时把文字与数字画成 **sprite**
（`battle_result_sprite_font` / `battle_result_compact_sprite_font`），
所以下面比的是**静态 BG 图层**（`battle_ui_result_background`（优先级 2）
+ `battle_ui_result_panel`（优先级 1，在前）按场景的层次叠放后裁成 240×160）。
**这不是运行帧的残差**，只说明**底板结构**的差
（与 B 流 §5.2 对 scenario-41 的同一口径）。

| 屏 | 重制侧图层 | 对照的原版真值 | 差 px | 占比 | 差 bbox |
|---|---|---|---:|---:|---|
| 结算屏 | `battle_ui_result_background.bmp` + `battle_ui_result_panel.bmp` | `02-settlement-exp-power-turns.png` | **12,798** / 38,400 | **33.3%** | `[0, 0, 240, 160]` |
| 升级屏 | `battle_ui_level_up_panel.bmp` | `03-levelup-naruto.png` | **7,681** / 38,400 | **20.0%** | `[0, 0, 240, 160]` |
| 训练页 | `battle_ui_training_panel.bmp` | `07-ninja-tool-list.png` | **8,483** / 38,400 | **22.1%** | `[1, 1, 240, 160]` |

⇒ **差 bbox 覆盖整屏** ⇒ 不是「少画一个元素」，是**底板排布整体不同**
（与 B 流 §5.1 查到的「整体下移 48 px、数字面板出屏」一致）。

---

## 6. 施工单（交父代理）

| # | 事项 | 证据 | 归谁 |
|---|---|---|---|
| **S1** | ⭐ **结算链缺「战后对白 + 任务菜单」两屏** | 重制侧 `battle_scene_phase` 枚举里**没有**战后对白/任务菜单；`complete` 之后直接交还战役场景 | 重制线（新增两屏） |
| **S2** | ⭐ **重制侧 battle-14 的 balance 与原版不一致 ⇒ 打不赢** | 护送 40 HP / 蜜蜂每回合 12 / 单次伤害 10 ⇒ 4 轮最多 12 次攻击，打不死 5 只蜂（需 13 次） | 重制线（数值）或「照抄原版数值」 |
| **S3** | 重制侧**没有「四人升级屏」那样的逐人升级页** | 原版 4 张（`03..06-levelup-*.png`）vs 重制侧升级信息并进 `result` / `training` | 重制线 |
| **S4** | ⭐ **结算屏的美术仍是 `battle_ui_result_*`（B 流 §5.2：整体下移 48 px、数字面板出屏）** | B 流 `notes/s49-fidelity/B-victory-settlement.md` §5；仓里已有 1:1 的 `scenario_41_result_*` 但运行时 0 引用 | 重制线（切资产或上移 48 px） |
| **S5** | 本波**未录到重制侧的「勝利」屏** | 打不赢（§4）⇒ 结算链只能从敗北的 outcome 进 | 依赖 S2 |

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| V4-1 | 重制侧开机就能进 S49 battle-14 | 读 `battle_campaign_route.h` 的 `battle_campaign_route_initial_scenario` | **49** ⇒ 开机即在 S49（**不需要**先打通 41–48） | **已确认** |
| V4-2 | 重制侧的结算链在产品代码里是完整的 | 读 `battle_scene_controller.h` 的 phase 迁移 + 在 ROM 上录 | `outcome → result → level_up → training → complete` 五段全在代码里 | **已确认** |
| V4-3 | 重制侧的输入分派是「一键一调用」，所以可以离线生成按键脚本 | 读 `battle_runtime_scene.cpp` 的输入分派 | A→confirm / B→cancel / 四方向→move_cursor / L,R→cycle_unit | **已确认** |
| V4-4 | 重制侧的「忍术列表」在移动之前是空的 | 离线控制器在单位选择阶段打开列表 | `player.action_count == 0`；移动确认后才有条目 | **已确认** |
| V4-5 | 重制侧的打人招式必须是直线、且不能是「打空格」型 | 离线控制器读 `target_policy` / `range` 并实测被拒 | 目标必须同行/同列；`empty_tile` 型打有人的格子被拒（`occupied_target_tile`） | **已确认** |
| V4-6 | 重制侧 battle-14 可以打赢 | 五种策略各跑一次离线控制器 | **五种全部败北**：追击 0 命中；守护命中但护送 40→16；护送每回合掉 12 | **已证伪**（这条路走不通） |
| V4-7 | 原版的单次伤害口径能套到重制侧 | 读两边的招式定义 | 原版十字手里剑 27 / 重制侧忍者组合拳 10、火遁术 15、忍具 6 | **已确认**（口径不同） |
| V4-8 | 从上电到进战斗需要多少次 A | 两轮对比：boot-a=3 vs boot-a=32 | **3 次停在战前简报/队伍一览表**（预置场景的队伍/装备页，**根本没进战斗**）；**32 次才进战斗** | **已确认** |
| V4-9 | 重制侧的结算链在 ROM 上真的能走出来 | 在 ROM 上录到的帧 | 录到「AVAILABLE TOOL」「NO AVAILABLE TOOL」「EQUIP COMPLETE」「隊員一覧表」四张屏 | **已确认** |
| V4-10 | 重制侧的「忍具一览」对应原版的「忍具一览」 | 比两边的段落内容 | 重制侧 `training` 段有「AVAILABLE TOOL / NO AVAILABLE TOOL / EQUIP COMPLETE」，**位置与用途对得上** | **已确认** |
| V4-11 | 重制侧 ROM 上跑离线脚本会同步 | 在 ROM 上回放按键脚本 | **短等待会让 ROM 跑在脚本前面 ⇒ 输入被丢**（录到「可以嗎？」对话框上「否」高亮后 33,839 帧不动）⇒ 等待必须放大 | **已证伪**（等待不足） |
| V4-12 | 原版 S49 结算屏真值还不存在 | 读 `notes/s49-fidelity/W4-original-victory-5th.md` §4 | **存在**：wave 8 的 W4 打赢后录到 9 张图 + sha256 收据 `9a60a89b…` | **已证伪**（已闭合） |
| V4-13 | 用「按键洪水」能让 ROM 自己把战斗打完 | 三轮：A/B 交错（200 轮）、A/B 交错 + 单位轮转键 R（120 轮）、开机 A×32 + 洪水 | 前一轮**停在战前简报**（开机 A 不够）；后两轮**都进了战斗但战斗没结束**（最后一次录到 25,132 帧，末帧仍是战斗中的单位选择）⇒ **洪水打法也走不通** | **已证伪** |

---

## 8. 复现命令

```powershell
cd D:\Github\gba-naruto

# 0) 私有探针（不要覆盖共享的 build/mgba-probe/mgba-probe.exe）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-v4'
python tools/mgba_probe/build.py

# 1) 离线生成按键脚本（重制侧自己的控制器；只读 include 重制线）
wsl -d Ubuntu-24.04 -- bash -lc "g++ -std=c++23 -I /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel/game/include /mnt/d/Github/gba-naruto/tools/s49_victory_capture/v4_route_gen.cpp -o /tmp/v4_route_gen && /tmp/v4_route_gen > /mnt/d/Github/gba-naruto/build/s49-victory-capture/v4/route.json"

# 2) 在 ROM 上回放并逐帧录下
python tools/s49_victory_capture/v4_replay.py `
    --script build/s49-victory-capture/v4/route.json `
    --out build/s49-victory-capture/v4/remake-chain `
    --boot "Down,Down" --boot-a 3 --zero-frames 240

# 3) 聚屏 + 逐屏对照表
python tools/s49_victory_capture/v4_frame_runs.py `
    --frames build/s49-victory-capture/v4/remake-chain/frames --min-run 40
python tools/s49_victory_capture/v4_settlement_compare.py `
    --truth build/s49-victory-capture/w4/settlement-truth `
    --remake build/s49-victory-capture/v4/remake-chain/frames `
    --out build/s49-victory-capture/v4/settlement-compare.json
```

---

## 9. 确认

* **新文件全部 LF、无 BOM**（`v4_route_gen.cpp` / `v4_*.py` / `v4_settlement_compare.py`）。
* **未提交 git**（本流文件在工作区里是未跟踪状态）。
* **未改重制线任何文件**（`D:\Shell\gba-naruto-butano` 只读使用）。
* **未改逆向线任何文件**（`D:\Shell\gba-naruto-reverse` 只读）。
* **未改其它流的工具**（只读调用）。
* 路线图同步留给父代理（WAVE9-TASKS §5 规定由父代理串行接线与同步）。
