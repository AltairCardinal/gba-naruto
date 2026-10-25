# W22-D5 —— 放开 battle 14 普通攻击（一处待裁决的保真度取舍）

> 流：**wave 22 / D5** · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 依据：`notes/s49-fidelity/W22-D2-settlement-premise.md`（接线请求 **R-D2-1**）
> 独占：`game/include/konoha/battle_mission_rules.h`（**仅此一个**）
> lane 副本：`D:\Github\gba-naruto\build\w20-e2\butano-sequel`
> 收据目录：`D:\Github\gba-naruto\build\w22-d5\`
> 新工具：`tools/s49_w22d5/analyze_kills.py` · `tools/s49_w22d5/v1_battle_direct.py`

---

## 0. 一句话结论

> ⭐⭐⭐ **结论三选一 = 「中性」——但归因要修正：**
>
> **放开 battle 14 的普通攻击对产品是零影响（25 帧判定台 Δ = 0 px，真实链行为指纹逐条相同），
> 所以它可以安全接线；但它**不是**解锁「鸣人 2 杀」的那一环 ——
> 真正的卡点是**打法（驱动器）**，不是规则。**
>
> | 读数 | 改前（基线 ROM `5cda0825`） | 改后（D5 ROM `c6514156`） | Δ |
> |---|---:|---:|---:|
> | **25 帧判定台 total（同一 lane、同 ROM 口径）** | **148,914 px** | **148,914 px** | **0 px** |
> | best_offset | +4 | +4 | 0 |
> | 精确字节命中帧 | 4 帧 | 4 帧（同样 4 帧） | 0 |
> | **战闘分（鸣人/佐助/小樱）**〔原版驱动器〕 | `50 / 200 / 0` | **`50 / 200 / 0`** | **0** |
> | 击杀分布〔原版驱动器〕 | 1 / 4 / 0 | 1 / 4 / 0 | 0 |
> | 終局回合数〔原版驱动器〕 | 13 | 13 | 0 |
> | 行为指纹（decisions 摘要 sha256） | `b82bcb82…` | **`b82bcb82…`（逐条相同）** | — |
> | **战闘分〔修正后的驱动器〕** | — | **`100 / 100 / 50`**（鸣人 **2 杀**） | ⭐ **鸣人 100 = 真值 100** |
> | 終局回合数〔修正后的驱动器〕 | — | **9**（真值要 ≤ 8） | −4 回合 |
> | **結算屏差（vs 真值）** | 985 px | **985 px（实测，见 §5）** | 0 |
> | 其余 7 屏（勝利 / 6 張升級 / 忍具一覽） | 逐字节相同 | **逐字节相同（0 px）** | 0 |
> | **結算屏差〔合上 R-D5-4 之后〕** | — | **936 px（−49 px，实测）** | ⭐ 鸣人 100 = 真值 100 |
> | 单测 | pass=119 / fail=20 | **pass=119 / fail=20**（逐名相同） | 0 |

---

## 1. 前提（来自 D2，第一手实测，非猜测）

| 项 | 值 | 出处 |
|---|---|---|
| 原版 battle 14 turn 4 存档态的 2 杀 | **鸣人 1 杀（蜂槽 8）+ 佐助 1 杀（蜂槽 9）** | D2 §1.2（`read_original_pool.py` 读 `.ss9` EWRAM 单位池 `+0xCE`） |
| 真值终局战闘分 | `100/150/0`（鸣人 2 杀 / 佐助 3 杀 / 小樱 0） | 真值結算屏 + E4 公式（每只蜜蜂 50） |
| ⇒ 真值 = turn 4 的 1/1/0 **+** 续打剩下的 3 杀（鸣人 1 + 佐助 2） | — | D2 §1.3 |
| 原版 canonical 路线 | 「**第二回合佐助火遁击倒槽 9；鸣人的普通攻击把槽 8 从 25 打到 9，下一回合完成击倒**」 | 逆向线 `scenario-49-battle-14-runtime-20260720.md:25-37` |
| 重制侧卡点（D2 的判断） | `battle_mission_rules.h:154-155` **禁 battle 14 普通攻击** + `battle_action_system.h:402-404` **忍具用一次清空** ⇒ 鸣人最多 1 杀 | D2 §2.3（P-85） |
| 結算屏差 | **985 px**（全在数字区 行 106–153 × 列 88–235；区外 0 px） | D2 §2.1（`settlement-cell-diff-real.json`） |

### 裁决前提（父代理给定的边界）

* ⛔ 归属规则**不改**（E2 决定性单测已证规则与原版一致）—— **本流未改**
* ⛔ `round_limit` **不改**（8）—— **本流未改**
* ⛔ 忍具「用一次清空」**暂不改** —— **本流未改**
* ✅ **只改一处**：`battle_mission_rules.h:154-155` 的 battle 14 v0 分支 ⇒ 放开 `allow_direct_attack`

---

## 2. 改动（**1 个文件**，只在 lane 副本里）

`D:\Github\gba-naruto\build\w20-e2\butano-sequel\game\include\konoha\battle_mission_rules.h`
（battle 14 v0 分支，`:154-155`）

```cpp
-            result.action_access.allow_direct_attack = false;
-            result.command_access.allow_direct_attack = false;
+            // W22-D5 (2026-10-25) -- the original battle 14 ALLOWS the
+            // normal attack; the remake used to forbid it, ...
+            result.action_access.allow_direct_attack = true;
+            result.command_access.allow_direct_attack = true;
```

* 注释里写清了**为什么**（引用 D2 的实测 + 逆向线 canonical 路线）。
* ⚠️ **只对 battle 14 v0 生效**：battle 15 走同一个 `else if` 分支但
  `allow_direct_attack` 在**内层 `if(battle_id == 14)`** 里 ⇒ battle 15 不受影响；
  battle 9 / battle 41 的禁止逻辑原样保留。
* ⚠️ **共享树未改**（SHA256 `1B612ABCD8D7E549…`，与改前一致）——
  本流只改 lane 副本，接线由父代理做。
* 改后整文件留档：`build/w22-d5/battle_mission_rules.h.d5`

### 2.1 ⚠️ 「只对鸣人放开」在本流做不到（**结构性限制**）

`battle_action_access_policy::allow_direct_attack`（`battle_player_action_flow.h:91`）与
`battle_command_access_policy::allow_direct_attack`（`battle_command_browser.h:24`）
都是**任务级 bool**，`battle_action_access_policy::allows()`（`:93-104`）对
`direct_attack` 这个 kind 直接 return `allow_direct_attack`，**没有按角色的分支**。
⇒ 只改我独占的这一个文件，**无法**做到「只对鸣人放开」；
⇒ 「只对鸣人放开」需要改 `battle_player_action_flow.h` / `battle_action_system.h`
（**非本流独占**）⇒ 见 §7 的接线请求 R-D5-2。
⇒ 本流只能测「整体放开」这一个变体（**唯一在本流所有权内可测的变体**）。

---

## 3. 实测结果

### 3.1 构建（⭐ 本机构建**字节可复现**，与简报 §3.2 的说法相反）

| 源 | ROM sha256 |
|---|---|
| lane 改前（基线） | `5cda0825f4a5937d942a539328b8f020b15e1c4268f8defc743fbcc0ad3eae14` |
| lane 改后（D5） | `c6514156e67dc10f48e19294b58d2c1b55e21a8239947973ce170f555c6f8c2e` |

* ⭐ **基线重建的 sha 与 wave 20 E2 自己那条真实链用的 ROM（`5cda0825…`）一字不差**；
  **D5 重建的 sha 与第一次构建（`c6514156…`）也一字不差**。
* ⇒ **同一 lane、同一源码 ⇒ 字节可复现** ⇒ 下面的 A/B 是**严格同 ROM 口径**
  （只差这一个 flag），满足仪器纪律第 11 条。
* 留档：`build/w22-d5/rom-base.gba`（`5cda0825…`）· `build/w22-d5/rom-d5.gba`（`c6514156…`）

```powershell
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Github/gba-naruto/build/w20-e2/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"
```

### 3.2 ⭐ 真实链（**原版驱动器**，`v1_battle.py --boot --max-turns 400 --use-tools`）

```powershell
python tools/s49_w20/capture_lock.py --run --label D5 -- python tools/s49_battle_balance/v1_battle.py \
  --rom build/w22-d5/rom-d5.gba --out build/w22-d5/run --boot --max-turns 400 --use-tools \
  --exe build/mgba-probe-w22d5/mgba-probe.exe
```

| 项 | D5（放开） | 基线（E2 lane，改前） |
|---|---:|---:|
| `outcome` / `battle_decided` | **1** / true | 1 / true |
| `round` | **13** | 13 |
| `frames_run` / `keys_pressed` | **60,518** / 669 | 60,518 / 669 |
| `errors` | **`[]`** | `[]` |
| `entry.poke_commands` | **0** | 0 |
| 蜂 HP 起→止 | **25 → 0（5 只全灭）** | 25 → 0 |
| 护送 HP | 40 → 40（存活） | 40 → 40 |
| **击杀分布（鸣人/佐助/小樱）** | **1 / 4 / 0** | 1 / 4 / 0 |
| **战闘分** | **`50 / 200 / 0`** | `50 / 200 / 0` |
| **行为指纹** | `b82bcb82b321075e5bcda77403e632cdbb236b785559d0aec953ef5c33665149` | **完全相同** |
| 直接攻撃（`direct_attack` 命令）的使用次数 | **0** | 0 |

⇒ **行为指纹逐条相同** ⇒ 放开普通攻击**没有改变这一局的任何一步**。

### 3.3 ⭐⭐ 25 帧判定台（**严格同 lane、同 ROM 口径**）

```powershell
python tools/s49_w21c1/capture_remake_walk.py --rom build/w22-d5/rom-base.gba \
  --exe build/mgba-probe-w22d5/mgba-probe.exe --out-dir build/w22-d5/capture-remake-base
python tools/s49_w21c1/capture_remake_walk.py --rom build/w22-d5/rom-d5.gba \
  --exe build/mgba-probe-w22d5/mgba-probe.exe --out-dir build/w22-d5/capture-remake-d5
python tools/s49_wave18/align_capture_steps.py \
  --original build/s49-package-w18/work/s49-report/capture-original \
  --remake build/w22-d5/capture-remake-base --out build/w22-d5/align-base.json
python tools/s49_wave18/align_capture_steps.py \
  --original build/s49-package-w18/work/s49-report/capture-original \
  --remake build/w22-d5/capture-remake-d5 --out build/w22-d5/align-d5.json
```

| offset | 基线（`align-base.json`） | D5（`align-d5.json`） | Δ |
|---:|---:|---:|---:|
| +0 | 648,356 | 648,356 | 0 |
| +1 | 608,490 | 610,085 | +1,595 |
| +2 | 575,690 | 575,690 | 0 |
| +3 | 475,324 | 475,324 | 0 |
| **+4（best）** | **148,914** | **148,914** | **0** |
| +5 | 475,610 | 475,608 | −2 |
| +6 | 535,424 | 535,424 | 0 |

* 精确字节命中帧：**两侧完全相同**（`step-14/15/17/18-A` ↔ `step-18/19/21/22-A`，offset +4）。
* ⚠️ 非物理 offset（+1/+5/+8）有 ±几十到 1595 px 的抖动 ⇒ 那是**配错帧**的伪差，
  **物理 offset（+4）上 Δ = 0**。
* ⇒ **25 帧 total：改前 148,914 px → 改后 148,914 px，Δ = 0 px。**
  （与 E3 的 `build/w20-e3/align-e3.json` 基线也完全一致。）

### 3.4 ⭐ 单测

```powershell
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh \
  /mnt/d/Github/gba-naruto/build/w20-e2/butano-sequel
```

* ⇒ **`w18-all-tests(...): pass=119 fail=20 status=1`**
* 与 wave 20 E2 lane 的基线（`build/w20-e2/unit-tests-lane.txt`：**pass=119 fail=20**）
  **逐名相同**（20 个失败项：`test_battle_all_scenario_runtime`、
  `test_battle_campaign_route`、`test_battle_campaign_save`、
  `test_battle_campaign_scenario_42…47`、`test_battle_campaign_scenario_49`、
  `test_battle_dynamic_deployment_turn`、`test_battle_material_pickups`、
  `test_battle_presentation_controller`、`test_battle_runtime_scene_gate`、
  `test_battle_s49_input_flow`、`test_battle_s49_opening`、
  `test_battle_scene_character_actions`、`test_battle_scene_controller`、
  `test_battle_scene_multi_unit`、`test_battle_scene_results` 等）
  ⇒ **零回归**。

### 3.5 ⭐⭐⭐ 关键实验：**让真实链真的用上普通攻击**（`tools/s49_w22d5/v1_battle_direct.py`）

**问题**：`v1_battle.py` 的静态动作目录里**没有 `direct_attack` 这一项**
（`character_attacks()`，`:474-508`，目录来源 `actor_stats(...)[“actions”]`），
⇒ 驱动器**永远不会**把「直接攻撃」命令选进计划
⇒ §3.2 的 `direct_attack_uses = 0` 不是偶然，是**结构性的**。

**做法**（本流自带的驱动器副本 `tools/s49_w22d5/v1_battle_direct.py`，**3 处补丁**）：

1. `character_attacks()` 末尾追加「直接攻撃」选项
   （`source = direct_attack`、`action_id = 0xFE`、range 1、potency 10、1 hit、98 %、
   目标 = 对手单位）—— 数值全部取自产品自己的
   `game/include/konoha/battle_direct_attack.h`；
2. `do_command()` 在计划选中「直接攻撃」时走 `COMMAND_DIRECT_ATTACK`（命令表第 3 项）；
3. ⭐ **学会「被拒绝的攻击不再选」**（`persistent_refused`）：
   `v1_battle.py` 每回合都会 `self.refused = set()`，所以**鸣人每回合都重挑那个
   已经被用掉的忍具**（range 3 ⇒ 在排序里赢过 range 1 的普通攻击），
   每次都被 ROM 拒绝 ⇒ **整回合被浪费掉**。
   本流把拒绝**累积**（不每回合清空）⇒ 鸣人第 2 回合起改用**普通攻击**。

```powershell
python tools/s49_w20/capture_lock.py --run --label D5-direct-play2 -- python tools/s49_w22d5/v1_battle_direct.py \
  --rom build/w22-d5/rom-d5.gba --out build/w22-d5/run-direct2 --boot --max-turns 400 --use-tools \
  --exe build/mgba-probe-w22d5/mgba-probe.exe
```

**实测结果**（`build/w22-d5/run-direct2/battle.json`）：

| 项 | 值 |
|---|---|
| `outcome` / `errors` / `poke_commands` | **1** / `[]` / **0** |
| **回合数** | **9**（原版驱动器 13 ⇒ **−4 回合**） |
| **击杀分布** | **鸣人 2 / 佐助 2 / 小樱 1** |
| **战闘分** | **`100 / 100 / 50`** |
| ⭐ **鸣人的战闘分** | **100** = **真值的 100**（鸣人 2 杀）✅ |
| 护送 HP | 40 → **14**（存活） |
| 鸣人的普通攻击 | **3 次**（frame 7770 / 9372 / 11074），`active:5`、range 1、potency 10 |
| ⭐ **普通攻击的实际伤害** | **16**（蜂 HP **25 → 9**，frame 8210）⇒ **与原版 canonical 路线的「25 打到 9」一字不差** |
|  Behaviour fingerprint | `e95ff64d87137019f1a248b77718bf90`（与原版驱动器不同 ⇒ 战斗确实变了） |

---

## 4. ⭐ 必查的边界：「鸣人的普通攻击能不能打到蜂？」—— **答案：能，而且伤害与原版一致**

| 问题 | 答案 | 依据 |
|---|---|---|
| 重制侧鸣人有「忍者组合拳」吗？ | ⭐ **有，而且是普通的主动技 `active:5`**（不是 `direct_attack` 命令！） | 角色目录 `build/v1/battle-truth.json` 的 `roster["1"].actions = ["active:2","active:7","active:5","tool:1","tool:11","tool:37"]` |
| 它能打到蜂吗？ | ⭐ **能**：射程 1（相邻）、目标 = 对手单位、命中 98 % | `battle_direct_attack.h`（`range_shape{1,1}`、`target_policy{opponent_unit}`）；产品自带单测 `test_battle_direct_attack.cpp:49-79` 已证普通攻击能命中相邻敌人并掉血 |
| **伤害是多少？打的是哪个槽位？** | ⭐ **16 点**（蜂 HP **25 → 9**），打的是**蜂槽 4**（frame 7770 出招、8210 记到 9 HP）；第 2、3 次分别收掉槽 4 与槽 5/6 | 实测 `build/w22-d5/run-direct2/battle.json` 的 `roster_series` |
| **与原版一致吗？** | ⭐ **一致**：原版 canonical 路线「鳴人的普通攻撃把槽 8 从 **25 打到 9**」 | 逆向线 `scenario-49-battle-14-runtime-20260720.md:25-37` |
| 那为什么 D2 说「鸣人最多 1 杀」？ | ⭐ **因为驱动器每回合都重挑被用掉的忍具**（range 3 赢过 range 1 的普通攻击），每回合都被拒绝 ⇒ 鸣人**一次普通攻击都没出手** | §3.5 第 3 条补丁；修正驱动器的拒绝策略后，鸣人 3 次普通攻击、2 杀 |

> ⚠️ **修正 D2 的 P-85**：真值前提不可达的**根因不是**「battle 14 禁普通攻击」。
> `allow_direct_attack` 管的是**「直接攻撃」这个通用命令**（ability id `0xFE`），
> **不是**鸣人的「忍者组合拳」（`active:5`）——后者**一直可用**。
> ⇒ **真正的开关是打法的「拒绝学习」**（§7 R-D5-4）。

---

## 5. 結算屏差 = **985 px（实测）**

> ⭐ **本项已从「推定」升级为「实测」**：父代理在 22:43 把各 lane 集成回共享树并于 22:47
> 构建 ⇒ 共享树 ROM（`b97daa81ca4d90ee…`）里**已经含本流的改动**（`battle_mission_rules.h`
> 与本流 lane 副本**逐字节相同**）**和** E1 的调色板修复 ⇒ 結算链可以跑完（48 页，
> `final_phase = task_menu`）⇒ 可以直接对拍真值。

```powershell
python tools/s49_w20/capture_lock.py --run --label D5-shared -- python tools/s49_battle_balance/v1_battle.py \
  --rom "D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba" \
  --out build/w22-d5/run-shared --boot --max-turns 400 --use-tools \
  --exe build/mgba-probe-w22d5/mgba-probe.exe

python tools/s49_victory_align/align_settlement.py \
  --truth build/s49-victory-capture/w4/settlement-truth \
  --remake build/w22-d5/run-shared/shots --out build/w22-d5/align-settlement-shared.json
python tools/s49_w22d2/settlement_cell_diff.py \
  --truth build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png \
  --remake build/w22-d5/run-shared/shots/page-001-result.png \
  --out build/w22-d5/cell-diff-shared.json
```

**逐屏对照（`align_settlement.py`，真值 8 屏）**：

| 屏 | 真值 | 重制 | 差 |
|---|---|---|---:|
| victory | `01-victory.png` | `page-000-outcome.png` | **0 px** |
| **result（結算屏）** | `02-settlement-exp-power-turns.png` | `page-001-result.png` | **985 px**（band `[[106,153]]`） |
| level_up_1 | `03-levelup-naruto.png` | `page-002-level_up.png` | **0 px** |
| level_up_2 | `05-levelup-sasuke-jutsu-name.png` | `page-003-level_up.png` | **0 px** |
| level_up_3 | `04-levelup-konohamaru.png` | `page-004-level_up.png` | **0 px** |
| level_up_4 | `05-levelup-sasuke.png` | `page-005-level_up.png` | **0 px** |
| level_up_5 | `06-levelup-sakura.png` | `page-006-level_up.png` | **0 px** |
| level_up_6 | `07-ninja-tool-list.png` | `page-007-level_up.png` | **0 px** |

⇒ **8 屏里 7 屏逐字节相同，只有結算屏差 985 px** ⇒ 与 D2 的实测**完全一致**
⇒ **本改动没有改变結算屏**。

**985 px 的结构分解（`settlement_cell_diff.py`，`build/w22-d5/cell-diff-shared.json`）**：

| 项 | 值 |
|---|---:|
| `total_diff_px` | **985** |
| `diff_row_bands` | `[[106, 153]]` |
| `diff_col_bands` | `[[88, 235]]` |
| `diff_px_outside_row_band` | **0** |
| `diff_px_outside_col_bands` | **0** |

⇒ 差**全部**落在 9 个数字格上（战闘分 3 + 回合分 3 + 合計 3）。

**该 ROM 上的战斗结果**（`build/w22-d5/run-shared/battle.json`）：
`outcome = 1`、`round = 13`、`errors = []`、`poke_commands = 0`、
**击杀 1/4/0 ⇒ 战闘分 `50/200/0`**、**回合分 0**（13 > 8）、合計 `50/200/0`
⇒ 与真值 `100/150/0` + 回合分 `75/75/75` 差 **985 px**。

⚠️ **注意**：这条实测链用的是**原版驱动器**（`v1_battle.py`）⇒ 鸣人仍然只有 1 杀
（§4：驱动器每回合重挑被用掉的忍具）⇒ **要让結算屏真正变化，得先合 R-D5-4**。

### 5.1 ⭐⭐ **合上 R-D5-4 之后的結算屏差 = 936 px（实测，少 49 px）**

```powershell
python tools/s49_w20/capture_lock.py --run --label D5-shared-direct -- python tools/s49_w22d5/v1_battle_direct.py \
  --rom "D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba" \
  --out build/w22-d5/run-shared-direct --boot --max-turns 400 --use-tools \
  --exe build/mgba-probe-w22d5/mgba-probe.exe
```

| 项 | 原版驱动器 | **修正后的驱动器** | 真值 |
|---|---:|---:|---:|
| 回合数 | 13 | **9** | ≤ 8 |
| 击杀分布 | 1 / 4 / 0 | **2 / 2 / 1** | 2 / 3 / 0 |
| **战闘分** | `50 / 200 / 0` | **`100 / 100 / 50`** | `100 / 150 / 0` |
| 回合分 | 0 | **0** | `75 / 75 / 75` |
| **結算屏差（实测）** | **985 px** | **936 px（−49 px）** | 0 px |
| 其余 7 屏 | 0 px | **0 px** | 0 px |
| 差的行带 | `[[106,153]]` | `[[106,153]]` | — |
| 区外差 | 0 px | **0 px** | — |

⇒ **鸣人的战闘分从 50 变成 100（= 真值）⇒ 結算屏差从 985 px 降到 936 px。**
⇒ 但**回合分仍是 0**（9 > 8）⇒ 还差 **R-D5-5**（回合数 ≤ 8 + 归属 `100/150/0`）才能到 0 px。
⇒ 收据：`build/w22-d5/align-settlement-shared-direct.json` ·
`build/w22-d5/cell-diff-shared-direct.json` · `build/w22-d5/kill-shared-direct.json`

---

## 7. ⭐ 接线请求（请父代理决策）

### R-D5-1（**建议接线，零回归**）：放开 battle 14 v0 的「直接攻撃」命令

* 文件：`D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_mission_rules.h`
* 行：**154-155**（battle 14 v0 分支）
* 改动：`allow_direct_attack = false` → `true`（两处）
* 理由：
  1. **原版允许**普通攻击（逆向线 canonical 路线）⇒ 重制侧禁掉它是**保真度缺陷**，本流修的是这一条。
  2. **零回归**（本流实测，严格同 ROM 口径）：真实链战闘分 `50/200/0` **不变**、
     行为指纹**逐条相同**、25 帧判定台 total **148,914 px 不变（Δ = 0）**、单测 **119/20 逐名相同**。
  3. 它**不改变**結算屏的 985 px（§5）。
* ⚠️ 但请注意 §4：**它不是解锁「鸣人 2 杀」的那一环**（真正的开关是 R-D5-4）。
  ⇒ 它的价值是**保真度**（原版允许 ⇒ 重制侧也允许），**不是**结算屏。
* 补丁留档：`build/w22-d5/battle_mission_rules.h.d5`（改后整文件）。

### R-D5-2：若要「只对鸣人放开」，需要改**非独占**文件

* 文件：`game/include/konoha/battle_player_action_flow.h`（`battle_action_access_policy`）
  或 `game/include/konoha/battle_action_system.h`
* 为什么必须改那里：`allow_direct_attack` 是**任务级 bool**，
  `battle_action_access_policy::allows()`（`battle_player_action_flow.h:93-104`）
  对 `direct_attack` 直接 return，**没有角色维度**。
* 建议形态：给 `battle_action_access_policy` 加一个
  「允许直接攻击的角色白名单」（或让 `allows()` 接受 actor 的 character_id）。
* ⛔ 本流未改（**非独占文件**）。

### R-D5-3 ✅ **已完成**（父代理 22:43 集成后本流在共享树 ROM 上实测）

* 事实：**E2 lane 缺 E1 的调色板修复** ⇒ 結算链在第 1 页被错误屏顶死 ⇒ 本 lane 测不了。
* ⭐ **父代理于 22:43:20 把各 lane 集成回共享树**（`battle_mission_rules.h` 与本流 lane 副本
  **逐字节相同**，mtime 22:43:20），并于 **22:47** 构建出共享树 ROM（`b97daa81ca4d90ee…`）
  ⇒ **本流的改动已经在共享树里** ⇒ §5 的 **985 px 已是实测**。
* ⇒ R-D5-3 **关闭**（实测收据：`build/w22-d5/align-settlement-shared.json` ·
  `build/w22-d5/cell-diff-shared.json`）。

### R-D5-4 ⭐⭐⭐：**驱动器必须学会「被拒绝的攻击不再选」**（这才是解锁真值前提的开关）

* 文件：`tools/s49_battle_balance/v1_battle.py`（**工具文件，非产品**）
* 位置：`character_attacks()`（`:474-508`）、`do_action()` 的两个拒绝分支
  （`:759`、`:777`）、`select_actor()` 的 `self.refused = set()`（`:538`）
* 机制：`self.refused` **每回合清空** ⇒ 鸣人每回合都重挑那个**已经被用掉的忍具**
  （range 3 ⇒ 在排序里赢过 range 1 的普通攻击），每回合都被 ROM 拒绝
  ⇒ 整回合被浪费 ⇒ **鸣人一次普通攻击都没出手** ⇒ 鸣人只有 1 杀。
* 改法（**本流已实现并实测**，`tools/s49_w22d5/v1_battle_direct.py`）：
  把拒绝**累积**到一个跨回合的 `persistent_refused` 集合里，
  `attack_options()` 同时过滤它。
* **实测收益**（同一 ROM `c6514156…`，只改驱动器）：

  | 项 | 原版驱动器 | **修正后的驱动器** | 真值 |
  |---|---:|---:|---:|
  | 鸣人的杀数 | 1 | **2** | **2** ✅ |
  | **鸣人的战闘分** | 50 | **100** | **100** ✅ |
  | 回合数 | 13 | **9** | ≤ 8（回合分要 75） |
  | 战闘分 | `50/200/0` | **`100/100/50`** | `100/150/0` |
  | 回合分 | 0 | **0** | **75** |
  | 鳴人的普通攻击 | 0 次 | **3 次，每次 16 伤害（25→9，与原版一致）** | 「25 打到 9」✅ |

* ⛔ 本流**未改** `tools/s49_battle_balance/v1_battle.py`（共享工具文件，别的流也在用）
  ⇒ 改动在 `tools/s49_w22d5/v1_battle_direct.py`（副本），请父代理决定是否回合。

### R-D5-5：回合数 9 > `round_limit` 8 ⇒ 回合分仍是 0

* 修正后的驱动器把战斗从 13 回合压到 **9 回合**，但**仍 > 8**
  ⇒ 回合分仍是 `0/0/0`（真值要 `75/75/75`）⇒ **結算屏仍不会是 0 px**。
* ⇒ 要 0 px 还差两件事：**① 归属分布**（`100/150/0`：佐助 3 杀、小樱 0 杀）
  和 **② 回合数 ≤ 8**。两者都是**打法/节奏**问题，不是结算规则问题。
* ⛔ 本流未改 `round_limit`（按父代理裁决）。

---

## 8. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| P-87 | 「lane 副本的 `battle_mission_rules.h` 与共享树一致」 | SHA256 对比 4 份拷贝 | ✅ **一致**（4 份全为 `1B612ABCD8D7E549…`，同 mtime） | **已确认** |
| P-88 | 「放开 battle 14 普通攻击 ⇒ 鸣人能打到蜂并造成伤害」 | 真实链收据 + 产品单测 + 静态定义 | ⚠️ **部分成立**：产品侧**能**打（射程 1、相邻即可命中）；但**原版驱动器从不选它**（`direct_attack_uses = 0`）⇒ 真实链给不出证据 | **部分确认** |
| P-89 | 「放开后真实链战闘分 = `100/150/0`」 | 真实链收据的击杀分布 | ⛔ **证伪**：实测 **`50/200/0`**（1/4/0），与基线**逐项相同** | **已证伪** |
| P-90 | 「放开后結算屏差 → 0 px」 | 对拍真值（共享树集成 ROM） | ⛔ **证伪**：**实测仍是 985 px**（8 屏里 7 屏 0 px；差全在 9 个数字格）⇒ 本改动不改变結算屏 | **已证伪** |
| P-91 | 「放开后 25 帧判定台 total 不上升」 | 同 lane、同 ROM 口径的 `align_capture_steps.py` A/B | ✅ **成立**：**148,914 px → 148,914 px（Δ = 0）**，精确命中帧也相同 | **已确认** |
| P-92 | 「放开后单测仍 pass=119/fail=20」 | `w18-run-all-tests.sh` 对 lane 副本 | ✅ **成立**：**pass=119 / fail=20**，失败项与基线**逐名相同** | **已确认** |
| P-93 | 「放开普通攻击会改变战斗节奏（回合数/击杀归属）」 | 行为指纹对比 | ⛔ **证伪**：指纹 `b82bcb82…` **逐条相同**，回合数 13 不变 | **已证伪** |
| P-94 | 「原版鸣人的普通攻击伤害 = 16，重制 = 10 ⇒ 伤害数值才是真差异」 | 逆向线记录（25→9）vs `battle_direct_attack.h`（`potency = 10`） | ⛔ **证伪**：**实测重制的普通攻击也是 16**（蜂 25 → 9，frame 8210）⇒ `potency` 不是最终伤害 ⇒ **伤害与原版一致** | **已证伪** |
| P-95 ⭐ | 「D2 的 P-85『禁普通攻击 ⇒ 鸣人最多 1 杀』的归因是对的」 | 驱动器拒绝学习实验（§3.5） | ⛔ **证伪**：鸣人的「忍者组合拳」是 **`active:5`（一直可用）**，不是 `direct_attack` 命令；放开 `allow_direct_attack` 对它**毫无影响**。真正卡住的是**驱动器每回合重挑被用掉的忍具** | **已证伪** |
| P-96 ⭐ | 「真值前提（鸣人 2 杀）在真实链上不可达」 | 修正驱动器后的真实链 | ⛔ **证伪**：**鸣人 2 杀达成** ⇒ 战闘分 `100/100/50`，鸣人的 **100 = 真值 100**；回合数 13 → **9**（真值要 ≤ 8） | **已证伪** |
| P-97 ⭐ | 「本机构建非字节可复现」（W20 简报 §3.2 的说法） | 同一 lane 连续两次构建比 sha256 | ⛔ **证伪**：基线重建 = `5cda0825…`（与 wave 20 E2 那条链的 ROM **一字不差**）；D5 重建 = `c6514156…`（与第一次**一字不差**）⇒ **字节可复现** | **已证伪** |

---

## 9. 实测记录（复现）

```powershell
# 1) 构建（lane 副本）
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Github/gba-naruto/build/w20-e2/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 2) 真实链（原版驱动器；长录制必须带全局锁）
python tools/s49_w20/capture_lock.py --run --label D5 -- python tools/s49_battle_balance/v1_battle.py \
  --rom build/w22-d5/rom-d5.gba --out build/w22-d5/run --boot --max-turns 400 --use-tools \
  --exe build/mgba-probe-w22d5/mgba-probe.exe

# 3) 击杀归属（本流新工具）
python tools/s49_w22d5/analyze_kills.py \
  --battle build/w22-d5/run/battle.json --label D5-open-direct-attack \
  --battle build/w20-e2/real-run/battle.json --label E2-baseline \
  --out build/w22-d5/kill-compare.json

# 4) 25 帧判定台（基线 ROM 与 D5 ROM 各一次，同 probe 同工具）
python tools/s49_w21c1/capture_remake_walk.py --rom build/w22-d5/rom-base.gba \
  --exe build/mgba-probe-w22d5/mgba-probe.exe --out-dir build/w22-d5/capture-remake-base
python tools/s49_w21c1/capture_remake_walk.py --rom build/w22-d5/rom-d5.gba \
  --exe build/mgba-probe-w22d5/mgba-probe.exe --out-dir build/w22-d5/capture-remake-d5
python tools/s49_wave18/align_capture_steps.py \
  --original build/s49-package-w18/work/s49-report/capture-original \
  --remake build/w22-d5/capture-remake-base --out build/w22-d5/align-base.json
python tools/s49_wave18/align_capture_steps.py \
  --original build/s49-package-w18/work/s49-report/capture-original \
  --remake build/w22-d5/capture-remake-d5 --out build/w22-d5/align-d5.json

# 5) ⭐ 让真实链真的用上普通攻击（修正驱动器的拒绝学习）
python tools/s49_w20/capture_lock.py --run --label D5-direct-play2 -- python tools/s49_w22d5/v1_battle_direct.py \
  --rom build/w22-d5/rom-d5.gba --out build/w22-d5/run-direct2 --boot --max-turns 400 --use-tools \
  --exe build/mgba-probe-w22d5/mgba-probe.exe

# 6) 单测
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh \
  /mnt/d/Github/gba-naruto/build/w20-e2/butano-sequel

# 7) ⭐ 結算屏对拍（用父代理 22:43 集成后的共享树 ROM；它含本流的改动 + E1 的调色板修复）
python tools/s49_w20/capture_lock.py --run --label D5-shared -- python tools/s49_battle_balance/v1_battle.py \
  --rom "D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba" \
  --out build/w22-d5/run-shared --boot --max-turns 400 --use-tools \
  --exe build/mgba-probe-w22d5/mgba-probe.exe
python tools/s49_victory_align/align_settlement.py \
  --truth build/s49-victory-capture/w4/settlement-truth \
  --remake build/w22-d5/run-shared/shots --out build/w22-d5/align-settlement-shared.json
python tools/s49_w22d2/settlement_cell_diff.py \
  --truth build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png \
  --remake build/w22-d5/run-shared/shots/page-001-result.png \
  --out build/w22-d5/cell-diff-shared.json
```

### 收据清单（`build/w22-d5/`）

| 收据 | 内容 |
|---|---|
| `rom-d5.gba` / `rom-base.gba` | 两个 ROM 留档（`c6514156…` / `5cda0825…`，**字节可复现**） |
| `battle_mission_rules.h.d5` | 改后的整文件（接线用） |
| `run/battle.json` | ⭐ 真实链收据（放开 + 原版驱动器）：outcome 1、round 13、kills 1/4/0 |
| `run-direct2/battle.json` | ⭐⭐ 真实链收据（放开 + 修正驱动器）：outcome 1、**round 9**、**kills 2/2/1**、鸣人 3 次普通攻击 |
| `kill-compare.json` / `kill-direct.json` | 击杀归属 + 战闘分 + 行为指纹 |
| `capture-remake-base/` · `capture-remake-d5/` | 25 帧重制侧 walk（基线 / D5，各 35 帧，probe = 自建 `mgba-probe-w22d5`） |
| `align-base.json` / `align-d5.json` | ⭐ 25 帧对齐（两侧 best_offset +4，total **148,914 px**，Δ = 0） |
| `run-shared/` | ⭐⭐ **共享树集成 ROM 的真实链**（48 页結算链跑完） |
| `align-settlement-shared.json` | ⭐⭐ **結算链逐屏对照**：8 屏里 **7 屏 0 px**，結算屏 **985 px** |
| `cell-diff-shared.json` | ⭐⭐ 結算屏差的行/列分解：`total_diff_px = 985`、行带 `[[106,153]]`、列带 `[[88,235]]`、**区外 0 px** |
| `kill-shared.json` | 共享树 ROM 上的击杀归属（1/4/0 ⇒ `50/200/0`、round 13） |
| `run-shared-direct/` | ⭐⭐ 共享树 ROM + **修正驱动器**的链（round 9、kills 2/2/1、48 页結算链） |
| `align-settlement-shared-direct.json` · `cell-diff-shared-direct.json` | ⭐⭐ **修正驱动器后的結算屏差 = 936 px** |
| `kill-shared-direct.json` | 修正驱动器后的击杀归属（2/2/1 ⇒ `100/100/50`、round 9） |

---

## 10. 未完成项

1. ✅ **結算屏的像素差已实测**（§5）：**985 px**，8 屏里 7 屏逐字节相同，
   差全在 9 个数字格。收据：`build/w22-d5/align-settlement-shared.json` ·
   `build/w22-d5/cell-diff-shared.json`。
2. ✅ **修正后的驱动器（round 9、2/2/1）的結算屏也已实测**（§5.1）：
   **936 px**（原版驱动器 985 px，**−49 px**），差仍在 9 个数字格内，其余 7 屏 0 px。
   ⇒ 但**回合分仍是 0**（9 > 8）⇒ **不是 0 px**。
3. ⛔ **「只对鸣人放开」没有测**（该变体需要改非独占文件，§2.1 / R-D5-2）。
4. ⏳ **没有实现「回合数 ≤ 8」**：修正后的驱动器是 9 回合，离真值（≤ 8）差 1 回合；
   归属分布也还差（`100/100/50` vs `100/150/0`：佐助 2 杀 vs 3、小樱 1 杀 vs 0）。
   ⇒ 要結算屏 0 px，**还要打法上的两处调整**（R-D5-5）。
5. ⏳ **没有复核 battle 15**（按代码路径 battle 15 不受影响，但没单独跑一条链）。
6. ⏳ **没有把 `tools/s49_w22d5/v1_battle_direct.py` 的 3 处补丁回合到共享的
   `tools/s49_battle_balance/v1_battle.py`**（共享工具文件，别的流也在用 ⇒ 交父代理决定）。
7. ℹ️ **本流没有改共享树**；共享树里 `battle_mission_rules.h` 的改动是
   **父代理 22:43:20 的集成动作**（内容与本流 lane 副本逐字节相同）。
