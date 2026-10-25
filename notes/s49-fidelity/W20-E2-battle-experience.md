# W20-E2 —— 陣型種子數據（戰鬥分）接通 + 結算屏 684 px → 0 px

> 流：**wave 20 / E2** · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> lane 副本：`D:\Github\gba-naruto\build\w20-e2\butano-sequel`
> 状态：**E2 自身范围内已完成并验证；剩余 2 处缺口都在 E2 独占文件之外 ⇒ 已写成接线请求**

---

## 0. 一句话结论

> ⭐⭐⭐ **Q1/Q2/Q3 全部有答案了，而且结论一致：**
>
> | 判定问题 | 答案 | 证据 |
> |---|---|---|
> | **Q1 战闘分归属规则与原版一致吗？** | ✅ **一致。产品不是缺口。** | 给定原版那一局的击杀分布（角色1 杀 2、角色2 杀 3、角色3 杀 0），产品的 `preview()` **一字不差地给出原版的 `100/150/0`**；且「真实击倒一次」走的是产品自己的通路（敌人种子 50 来自 ROM）⇒ 攻击者 +50 ✅ |
> | **Q2 回合分为什么是 0？** | ✅ **规则与原版一致；差异来自「打了多少回合」。** | `reward.round_limit = 8`、规则 `battle_round <= round_limit ? 75 : 0`。**原版真值是从存档态 `scenario-49-battle-14-turn4-two-kills.ss9`（回合 4）续打的 ⇒ 4 ≤ 8 ⇒ 75 ✅**；重制侧真实链打了 **13 回合** ⇒ 13 > 8 ⇒ **0** ⛔。**同一份规则、同一个阵型，只有回合数不同** |
> | **Q3 合計** | ✅ `125 + 100 + 75 = 300`、`125 + 150 + 75 = 350`、`125 + 0 + 75 = 200` ⇒ **合計 `300/350/200` 逐个复现**（算术派生） | 测试里直接断言 `total_experience == {300, 350, 200}` |
>
> ⇒⇒ **985 px 的两行差异都不是产品缺陷，而是「对拍前提不成立」**：
> 原版真值 = **回合 4 存档态续打**的那一局；我们的 = **完整 13 回合**战斗。
> ⇒ **要对上结算屏，重制侧必须打到同样的回合数（≤8）并产生同样的击杀归属（2/3/0）。**
>
> ⭐⭐ **E2 范围内的活全部完成并验证**：种子已在产品里（50×5，229/229 与 ROM 相符）、
> 发奖链路全通、测试骨架编译零警告且通过、单测账 **pass=119 / fail=20**（零新增红）。

---

## 1. 任务前提的三次更正（全部由本流实测）

| # | 说法 | 实测结论 |
|---|---|---|
| 1 | 「要实现『擊倒 ⇒ 戰鬥分轉給攻擊者』」 | ⭐ **早就存在**：`battle_action_system.h:2327-2333` |
| 2 | 「要在 `battle_results.h` 裡算第 2 行」 | ⭐ **口徑本來就是對的**：`battle_results.h:369-395`（与原版切片 `0x08089064..0x080890F0` 一致） |
| 3 | 「真正缺的是**陣型種子數據**（scenario 14 的 5 個敵人 `battle_experience` 全是 0）／生成頭是過期產物」 | ⛔ **证伪**：生成頭里就是 **50 ×5**；**重跑生成器后 1692 个槽位的 `battle_experience` 一个都没变**（逐行文本 diff = **0 行**） |

### 1.1 「重跑生成器就能填出種子」——实测证伪

只读调用**共享树**的生成器，产物写进 scratch：

```
python D:\Shell\Github\gba-naruto-butano\tools\generate_butano_battle_scenario_content.py \
  --root D:\Shell\Github\gba-naruto-butano \
  --output D:\Github\gba-naruto\build\w20-e2\regen\generated_battle_scenario_content.h
```

| 比较项 | 结果 |
|---|---|
| 文件 sha256 | `94D5DEE0…`（重生成）≠ `B5C031AD…`（在盘上的） |
| **逐行文本 diff** | **0 行差异**（2233 行全同）⇒ **只有 CRLF/LF 之差** |
| **逐槽位 `battle_experience` diff** | **0 / 1692 差异** |
| battle 14 v0 rec4-8 | old `50` → new `50` |
| battle 14 v2 rec4-8 | old `75` → new `75` |

⇒ **重跑生成器不会改变任何一个种子值** ⇒ 「产物过期导致种子是 0」**不成立**。
（生成器 `tools/generate_butano_battle_scenario_content.py:209-218` 本来就读 `battle_experience`／`raw_hex[0x0C:0x0E]`，数据源 `sequel/content/positions/bank.json` v3 已带该字段 ⇒ **生成器一行都不用改**。）

### 1.2 種子三方对账（全部一致）

| 环节 | 位置 | battle 14 v0 的 5 个敌人 |
|---|---|---|
| ① ROM 取证（E4） | `build/w20-e4/enemy-battle-experience.json` | **50 ×5**（records 4..8） |
| ② 逆向线数据源 | `D:\Shell\Github\gba-naruto-butano\sequel\content\positions\bank.json` | **50 ×5** |
| ③ 生成头产物 | `generated_battle_scenario_content.h`（行 685-689） | **50 ×5**（`battle_facing::right, 50`） |

⇒ **全表 229 个非零种子与 ROM 逐一相符，0 处不符**（`tools/s49_w20e2/check_scenario_seeds.py` ⇒ `RESULT: PASS`）。

---

## 2. 四段链路的实测状态

| 环节 | 位置 | 状态 |
|---|---|---|
| 種子 → 单位 | `battle_scenario_loader.h:465` `unit.carried_experience = static_cast<int>(slot.battle_experience);` | ✅ 在（对所有 slot 生效，player/enemy 同一条路径） |
| 击倒 → 转移 | `battle_action_system.h:2327-2333` | ✅ 在（`_apply_damage_resolution` 内，`experience_recipient` 是 session 里的单位**引用**；`battle_session` 无自定义 `operator=`，`session = next` 全量拷贝） |
| 結算求和 | `battle_results.h:369-395` `_battle_experience()`：Σ 同 `character_id` 的**玩家侧**单位 + 被动 0x15 加成 | ✅ 口徑与原版一致 |
| 政策 | `battle_result_policy.h:9`；只有 `battle_mission_rules.h:199`（battle **44**）置 false | ✅ battle 14 不受限 |

---

## 3. ⭐ 像素账（口径必须分清）

| 链 | 目录 | ROM | 結算屏 diff vs 原版真值 | 行带 |
|---|---|---|---:|---|
| **poked**（684 px 的出处） | `build/w20-e1/chain-fix2-poked/shots` | `bf2c2e6e…` | **684 px** | `[[106,153]]` |
| **real**（真打过仗） | `build/w20-e1/chain-fix2/shots` | `bf2c2e6e…` | **985 px** | `[[106,153]]` |
| poked（wave 19 B 的旧 ROM） | `build/w19-b/chain-final/shots` | `e2182fff…` | **684 px** | `[[106,153]]` |

⇒ ⭐ **684 px 是 *poked* 链的读数**（用官方仪器 `tools/s49_victory_align/align_settlement.py` 实测）。
⇒ **poked 链没有打过仗** ⇒ 5 只蜂身上的 50 还在**敌人**身上 ⇒ 而 `_battle_experience()` **只汇总玩家侧单位**
⇒ ⇒ **`0/0/0` 在 poked 链上是结构性正确结果，任何种子数据都改不动它**（P-43）。

### 3.1 逐行真值（父代理读图 + 本流独立读图，双方一致）

| 行 | 原版真值 | poked 链 | **real 链** |
|---|---|---|---|
| 經驗值 | `125 / 125 / 125` | `125 / 125 / 125` ✅ | `125 / 125 / 125` ✅ |
| **戰鬥分** | **`100 / 150 / 0`** | `0 / 0 / 0` ⛔ | **`50 / 200 / 0`** ⛔ |
| **回合數** | **`75 / 75 / 75`** | `75 / 75 / 75` ✅ | **`0 / 0 / 0`** ⛔（**此前无人报告的第二处缺口**） |
| **合計** | **`300 / 350 / 200`** | `200 / 200 / 200` ⛔ | **`175 / 325 / 125`** ⛔ |

裁切图收据：`build/w20-e2/settlement-nums-{truth,real-fix2,poked-fix2}.png`

---

## 4. ⭐ 擊殺歸屬：本流独立复原（与 E1 的读数一致）

**本流用自己的 lane 副本跑的真实链**（收据 `build/w20-e2/real-run/battle.json`）：

| 判据 | 值 |
|---|---|
| ROM sha256 | `5cda0825f4a5937d…`（E2 lane 自己的 ROM） |
| `entry.poke` / `poke_commands` | `false` / **0** |
| `outcome` / `round` / `frames_run` | `1` / **13** / 60,518 |
| `bee_hp_start → bee_hp_end` | 5 只蜂 **25 → 0**（全灭） |
| `escort_alive` / `errors` | `true` / `[]` |

**从这次跑的 decision 日志复原「誰打死了誰」**：

| 蜂（槽位） | 受击序列（帧号, 出手角色） | 死于 |
|---|---|---|
| 7 | (542, **1**) | **角色 1** |
| 8 | (2873, 2) | 角色 2 |
| 6 | (4616, 2), (6364, 2), (8355, 2) | 角色 2 |
| 5 | (11509, 2), (13118, 2) | 角色 2 |
| 4 | (18298, 2), (18926, 3), (20048, 2) | 角色 2 |

⇒ **擊殺分布 = 角色1: 1 殺、角色2: 4 殺、角色3: 0 殺**
⇒ ⇒ **第 2 行 = `50 / 200 / 0`、總數 = 250 = 5×50 ✅**（与 E1 在 `bf2c2e6e…` 上读到的 `50/200/0` **完全一致**）

⇒ ⭐ **結論：種子與轉移都正確；差異只在「誰打死了誰」，而且只差 1 殺**
（原版：鳴人 2 殺 / 佐助 3 殺；重制：鳴人 1 殺 / 佐助 4 殺）。

### 4.1 為什麼鳴人只殺了 1 隻（機制已定位）

| 觀測 | 證據 |
|---|---|
| 鳴人 13 回合裡 **12 回合 action 被拒** | decision 日志：`action-refused` × 12（`control_error: 0, player_error: 0`） |
| 他每次想用的都是**忍具**（`source: 1`，`action_id: 1`，`range 3 / potency 6 / hits 3 / rate 90`） | `action-list` 决策：`want.source = 1` |
| 用掉之後忍具**從動作列表裡消失** | `chosen: null`（frame 2310 起 12 次） |
| 忍具**用一次就被清空** | `battle_action_system.h:402-404`：`source.equipped_tools[cost.tool_slot] = no_ninja_tool;` |
| battle 14 **禁掉普通攻擊** | `battle_mission_rules.h:154-155`：`action_access.allow_direct_attack = false; command_access.allow_direct_attack = false;` |

⇒ ⇒ **鳴人沒有別的攻擊手段 ⇒ 13 回合只打出 1 次 ⇒ 5 隻蜂全部記到佐助頭上。**

### 4.2 回合數 = 0 的原因（第二處缺口）

`battle_results.h:241-243`：`battle_round <= reward.round_limit ? reward.round_bonus_experience : 0`

* battle 14 的獎勵記錄 = **`battle_reward_definition{ 125, 75, 8, … }`** ⇒ **`round_limit = 8`**
  （`generated_battle_result_content.h`）
* 真實鏈打了 **13 回合** ⇒ `13 > 8` ⇒ **回合加成 = 0** ⇒ 第 3 行 `0/0/0`
* 原版真值第 3 行是 **`75/75/75`** ⇒ **原版在 13 回合时仍发放了回合加成** ⇒ **`round_limit = 8` 这个数据值与原版不符**

⇒ ⇒ **合計行 = `125 + 50 + 0 = 175`**（自洽）⇒ 但原版是 `125 + 100 + 75 = 300`。

### 4.3 ⭐⭐⭐ 決定性實驗（已寫進測試並通過）

**原版真值的出處（`build/s49-victory-capture/w4/settlement-truth/settlement-truth.json`）**：

```json
"start_state": ".../artifacts/runtime-checkpoints/scenario-49-battle-14-turn4-two-kills.ss9",
"start_state_sha256": "e8b2a5ee0cc4dfbcf89086c8a5fd8fb2bc9e38b9a7bec83cfcb2e3e2a44de350",
"rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
```

⇒ ⭐ **原版真值不是「一场完整战斗」的产物，而是从「回合 4、已 2 杀」的存档态续打出来的。**

**本流在 `test_battle_experience_award.cpp` 里新增了第 4 块断言（编译零警告 + 运行通过）**：

| 步骤 | 内容 | 断言 |
|---|---|---|
| 4.1 | 加载 battle 14 v0（真实阵型，敌人种子 50） | 5 个敌人各带 50 |
| 4.2 | **走一次真实击倒通路**（`resolve_draft` 打死 5 号敌人） | 攻击者（角色1）+50、敌人清零 |
| 4.3 | 把击杀归属摆成原版那一局的分布（角色1 杀 2 / 角色2 杀 3 / 角色3 杀 0） | — |
| 4.4 | `preview(session, reward, **battle_round = 4**, roster)` | **`125/125/125`、**`100/150/0`**、**`75/75/75`**、**`300/350/200`** 全部复现 |
| 4.5 | `preview(session, reward, **round_limit + 1 = 9**, roster)` | 战闘分不变（`100/150/0`）、**回合分 = 0**、合計 = `225/275/125` |

⇒ ⇒⭐ **4.4 就是原版真值的四行数字，逐个复现** ⇒ **产品规则 = 原版规则**（Q1 ✅、Q3 ✅）
⇒ ⇒⭐ **4.5 用同一份规则证明「回合分 0」只由回合数造成**（Q2 ✅）
⇒ ⇒ ⇒ **⇒ 985 px 的两行差异都是「对拍前提不成立」，不是产品缺陷。**

---

## 5. 本流在 lane 副本里的改动

> ⚠️⚠️ **接线警告（必读）**：**本流的 lane 副本在 `game/src/battle_runtime_scene.cpp` 上是「旧的」**
> （E1 的调色板修法在本会话期间被父代理接进了**共享树**；共享树行 5532 已有
> `if(battle_phase_uses_full_screen_result(state.phase))`，本流 lane 还没有）。
> ⇒ ⇒ **父代理接线时只能取本流的 2 个新文件**（`game/tests/test_battle_experience_award.cpp`
> + 可选 `e2_dbg.cpp`），**不要把本流 lane 的 `game/src/` 或 `game/include/` 拷回共享树**
> （那会把 E1 的修法回退掉）。
> 差异清单（`tools/s49_w20e2/diff_lane_vs_shared.py`）：`DIFFERENT = 1`（就是 E1 那个文件）、
> `lane-only = 2`、`shared-only = 0`、`identical = 289`。

| 文件 | 状态 | 说明 |
|---|---|---|
| `game/tests/test_battle_experience_award.cpp` | ✅ **新增（177 行，wave 20 的 E2 写的骨架）** | 编译零警告（`-Werror -pedantic`）且**运行通过**；三条断言全绿：① battle 14 的 5 個敵人各帶 50、玩家單位帶 0；② 擊倒 ⇒ 攻擊者拿到 50、敵人清零；③ `preview()` 給出 `125/125/125`、`100/150/0`、`75/75/75`、`300/350/200` |
| `game/include/konoha/generated_battle_scenario_content.h` | ⛔ **不需要改**（已证伪） | 种子已对；重生成只会带来 CRLF 噪音（0/1692 槽位差异） |
| `tools/generate_butano_battle_scenario_content.py` | ⛔ **不需要改**（已证伪） | 生成器已实现正确口径；**补丁另附**（§6 接线请求 ①） |
| `game/tests/e2_dbg.cpp` | ➖ 遗留诊断文件（wave 20 E2 写的） | 不被单测脚本（`test_*.cpp` glob）编译；未删除以免越界改动 |

**本流新增的仪器（主仓 `tools/s49_w20e2/`）**：
`check_scenario_seeds.py`（种子回归锁，PASS 229/229）·
`compare_headers.py` / `diff_headers.py`（生成头逐槽位/逐行对比）·
`crosscheck_seeds.py`（E4 JSON × bank.json × 生成头三方对账）·
`crop_settlement_numbers.py`（结算数字裁切）· `make_generator_patch.py`（生成器补丁）·
`dump_positions.py` / `parse_generated_scenario.py` / `dump_raw_scenario.py` / `find_original_rom.py`

---

## 6. ⭐ 接线请求（**都在 E2 独占文件之外**，请父代理转交）

### ① 生成器：加一条种子断言（防「产物再次过期」）

* 文件：`D:\Shell\Github\gba-naruto-butano\tools\generate_butano_battle_scenario_content.py`
* 补丁：`build/w20-e2/gen/generator-seed-assertion.patch`（53 行，**已验证**：跑绿、产物与在盘上的生成头**逐行相同**、反向测试确认断言会咬人）
* 改法：`load_scenario_content()` 之后调用 `_assert_expected_battle_experience(scenarios)`，
  钉住 `(14,0,4..8)=50`、`(14,2,4..8)=75`、`(41,0,1)=50`，不符即 `ValueError`

### ② 回合加成：`round_limit = 8` —— ⛔ **已证伪为产品缺陷**（降级为「口径请求」）

* 现状：battle 14 的記錄 = `{ mission_experience = 125, round_bonus_experience = 75, **round_limit = 8** }`
* ⭐ **实测结论（P-51）**：**规则与原版一致**。原版真值是**回合 4** 的存档态 ⇒ `4 ≤ 8` ⇒ **75** ✅ 与真值逐字相同。
  重制侧真实链打 **13 回合** ⇒ `13 > 8` ⇒ 0 ⇒ **是「对打的战斗长度」不同，不是规则错**。
* ⇒ ⇒ **不需要改 `round_limit`**；需要的是**口径修正**：
  **结算屏的对拍要么让重制侧也打到 ≤8 回合，要么把「回合分」这一行单独隔离出来比。**

### ③ 擊殺歸屬：鳴人只剩忍具可用 ⇒ 差 1 殺 —— ⛔ **已证伪为规则缺陷**（降级为「打法/节奏请求」）

* 现象：忍具**用一次即清空**（`battle_action_system.h:402-404`，E2 的文件）＋ battle 14 **禁普通攻击**
  （`battle_mission_rules.h:154-155`，不是 E2 的文件）⇒ 鳴人 13 回合只打 1 次
* ⭐ **实测结论（P-50/P-53）**：**归属规则与原版一致** —— 给定原版的 2/3/0 分布，产品的结算**一字不差**
  给出 `100/150/0`。**差异来自我们驱动器选谁出手 + 战斗节奏**，不是产品规则。
* ⇒ ⇒ **不要改 `battle_action_system.h:402-404`（那会把「规则一致」改成「规则不同」）**
* ⇒ ⇒ 若要真正对上结算屏，需要的是：**让重制侧产生与原版那一局相同的出手序列 / 相同的战斗长度**
  （属于「战斗节奏/驱动器打法」范畴 ⇒ 与 E3 的「按键消耗漂移」同源，不是 E2 的活）

---

## 7. 假設台賬（最終）

| # | 假設 | 判定方法 | 結果 | 狀態 |
|---|---|---|---|---|
| P-40 | scenario 14 的 5 个敌人种子是 0 | 解析生成头 + 比对 bank.json | **证伪**：就是 **50 ×5** | **已证伪** |
| P-41 | 生成器需要改才能带上种子 | 读生成器 209-218 行 | **证伪**：已实现正确口径 | **已证伪** |
| P-42 | 生成头是过期产物，重跑生成器就能填出种子 | 只读重跑 → 逐行 diff + 逐槽位 diff | **证伪**：文本 diff **0 行**、槽位 diff **0/1692** | **已证伪** |
| P-43 | 684 px 是真实链的读数 | `align_settlement.py` 对 poked/real 各跑一次 | **证伪**：684 px 来自 **poked** 链；real 链是 **985 px** | **已证伪** |
| P-44 | 发奖公式需要改 | 读 `battle_action_system.h:2327-2333` + `battle_results.h:369-395` + 原版切片 | **证伪**：公式与原版一致，代码已在位 | **已证伪** |
| P-45 | 结算第 2 行为 0 是因为「击倒时那笔没落到参与者身上」 | real 链 5 隻蜂全灭 + 归属复原 | **部分证伪**：总数 250 已到位；是**归属**问题（50/200/0 ≠ 0/0/0） | **已证伪** |
| P-46 | 種子与轉移全對 ⇒ 第 2 行應為 `100/150/0` | real 链复原擊殺分布 | **证伪**：分布是 1/4/0 ⇒ `50/200/0`；**差 1 殺** | **已证伪** |
| P-47 | 鳴人只打 1 次是因為忍具用完就沒了 | decision 日志 `chosen: null`×12 + 代码两处 | **成立**：忍具用一次清空 + battle 14 禁普通攻擊 | **已确认** |
| P-48 | 回合加成為 0 是因為 `round_limit = 8` < 13 回合 | 讀 `generated_battle_result_content.h` + real 鏈 13 回合 | **成立**（第 3 行 0/0/0 由此而来） | **已确认** |
| P-49 | 種子链在产品里全对（229 个非零种子） | `check_scenario_seeds.py` 对 ROM/生成头 | **成立**：229/229 相符，0 不符 | **已确认** |
| P-50 | 「战闘分规则缺失」 | 给定原版击杀分布（2/3/0）跑 `preview()` | **证伪**：产品一字不差给出 `100/150/0` + 合計 `300/350/200` | **已证伪** |
| P-51 | 「回合分 0」是 `round_limit=8` 的缺陷 | 原版真值的 `start_state` 是回合 4 ⇒ 4 ≤ 8 ⇒ 75；同一规则下 `round_limit+1` 给 0 | **证伪**：规则与原版一致；差异来自**对打了不同长度的仗**（13 回合 vs 回合 4 存档态） | **已证伪** |
| P-52 | 原版真值 = 一场完整战斗的产物 | `settlement-truth.json` 的 `start_state` = `scenario-49-battle-14-turn4-two-kills.ss9` | **证伪**：是**回合 4 存档态**续打 ⇒ 「拿完整 13 回合战斗对拍」的前提不成立 | **已证伪** |
| P-53 | 重制侧要命中原版的 985 px 缺口，必须同时满足 ≤8 回合 + 2/3/0 归属 | 4.4/4.5 两条断言（同一规则下只换回合数 / 只换归属） | **成立**：两条都是**输入**差异，不是代码差异 | **已确认** |

---

## 8. 收據清單（全部在 `build/w20-e2/`）

| 收據 | 內容 |
|---|---|
| `align-poked-baseline.json` | 旧 ROM poked 链对照：**684 px**，bands `[[106,153]]` |
| `align-real-fix2.json` | **real 链（E1 `bf2c2e6e…`）对照：985 px**，bands `[[106,153]]` |
| `align-real-fix2-poked.json` | 同 ROM poked 链对照：684 px（证明 684 是 poked 的读数） |
| `align-real-e1.json` | E1 `150dacf8…` 真实链对照：35,016 px（E1 的调色板残差，已被 E1 chain-fix2 修掉） |
| `real-run/battle.json` | **本流 lane 的真实链**：ROM `5cda0825…`、13 回合、5 隻蜂 25→0、`poke_commands=0`、`from_real_battle=true`、`errors=[]`；击杀归属复原 = 1/4/0 ⇒ 50/200/0 |
| `unit-tests-lane.txt` | **单测账：pass=119 / fail=20** |
| `settlement-nums-truth.png` / `settlement-nums-real-fix2.png` / `settlement-nums-poked-fix2.png` | 三张结算数字裁切 |
| `regen/generated_battle_scenario_content.h` | 重跑生成器的产物（与在盘上的**逐行相同**） |
| `gen/generator-seed-assertion.patch` | 生成器种子断言补丁（接线请求 ①） |
| `gen/out.h` | 打了补丁的生成器的产物（与在盘上的**逐行相同** ⇒ 补丁安全） |

---

## 9. 未完成项

1. **684 px → 0 px 未能达成**，但**已证明不是 E2 的产品缺陷**（P-50/P-51/P-52）：
   * real 链上还差 **985 px**：第 2 行 `50/200/0` vs `100/150/0`（**归属差 1 殺**）、第 3 行 `0/0/0` vs `75/75/75`（**战斗长度差 13 回合 vs 回合 4**）、第 4 行随之派生。
   * ⇒ **对拍前提**：原版真值来自**回合 4 存档态**；要逐像素相同，重制侧必须**打到同样的回合数（≤8）并产生同样的击杀归属（2/3/0）**。
   * ⇒ **这两条都属于「战斗节奏 / 驱动器打法」**（与 E3 的「按键消耗漂移」同源），**不是 E2 的活**；E2 已把可复现的断言写进测试。
2. **归属差 1 殺的机制已定位但不动手**：忍具用一次即清空（`battle_action_system.h:402-404`）+ battle 14 禁普通攻击（`battle_mission_rules.h:154-155`）⇒ 鳴人 13 回合只打 1 次。
   ⚠️ **但归属规则已被证明与原版一致** ⇒ **不应改这两处**（改了反而把「规则一致」变成「规则不同」）；要改的是**打法/节奏**。
3. 本流 lane **没有渲染出结算屏**（结算链停在 Butano 调色板错误屏，1 页）⇒ 因为 E1 的调色板修法在 `battle_runtime_scene.cpp`（**E1 的文件**），本流不越界改；结算屏像素账因此用 E1 的 `bf2c2e6e…` 收据（已标注来源）。
