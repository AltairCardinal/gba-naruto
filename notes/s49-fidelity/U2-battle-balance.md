# 流 U2 —— 战斗数值对齐（重制侧 S49 battle-14 能不能打赢）

> 工具：`tools/s49_battle_balance/u2_route_gen.cpp`（离线控制器 + 数值转储）、
> `tools/s49_battle_balance/u2_impact.py`（影响面）、
> `tools/s49_battle_balance/u2_build_and_run.sh` / `u2_ratchet.sh`（复跑）
> 产物：`build/s49-battle-balance/u2/`
> 2026-10-24 · stream U2（wave 10）。**所有数字都是本机实测。**
> 逆向线 `D:\Shell\gba-naruto-reverse` **全程只读**；重制线 **零改动**；**未提交 git**。

---

## 0. 一句话结论

**不该改数值 —— 因为重制侧的 battle-14 数值本来就是对的，而且重制侧 battle-14
本来就能打赢。**

V4（wave 9）判「重制侧 balance 与原版不一致 ⇒ 打不赢」的那个对比**比错了口径**：
原版的 **27** 是**预览总值**（每次防御后伤害 × 命中段数），
重制侧的 **10 / 15 / 6** 是**招式模板威力**（单次数值）。
实测逐项对齐后，两边**完全相同**（HP 138/104/110/40/25、十字手里剑预览 **27**、
命中率 **84%**、蜂打护送 **12**）；而「打不赢」是 **V4 路线生成器的三个驱动器缺陷**
造成的，不是数值缺陷。**改完驱动器（不改任何游戏数值），重制侧 battle-14
打赢：5 回合、5 只蜂全灭、护送 16/40 存活、结算链走到 `complete`。**

⇒ 本流对重制线 **零改动**；单测棘轮 **零回归**。

---

## 1. 改动文件清单

### 1.1 重制线（`D:\Shell\gba-naruto-butano`）—— **只新增一个单测，零逻辑改动**

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\tests\test_battle_s49_balance_truth.cpp` | **新增** | ⭐ **单测棘轮**：把 battle-14 的数值真值（HP/等级/攻防敏、十字手里剑 6×3 段 90% 射程 3、预览 27、命中率 84%、蜂打护送 12）与「十字手里剑比忍者组合拳强」的结论**钉死**，任何人再改数值或再犯 V4 的口径错误都会变红 |

**没有**改 `battle_unit_content.h` / `generated_battle_unit_content.h` /
`battle_conditions.h` / `battle_scenario_content.h` / `battle_ai*.h`
（⇒ 不需要改，见 §4 的影响面评估），
**没有**改 `battle_runtime_scene.cpp` / `battle_black_field*.h` / `graphics/`（U1 独占），
**没有**改 `battle_result*.h`（U3 独占），**没有**改逆向线任何文件。

### 1.2 本仓库（`D:\Github\gba-naruto`）—— 本流新建

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_battle_balance\u2_route_gen.cpp` | **新增** | ⭐ **离线控制器 + 数值转储**：基于 V4 的 `v4_route_gen.cpp`，加了 `--dump`（实测 battle-14 的数值与招式表）与三条驱动器修正 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\u2_replay.py` | **新增** | ⭐ **ROM 回放器**：同 V4 的 `v4_replay.py` 契约（探针 Lua 帧回调、帧精确 PNG），多了 `--capture step`（每步一帧，成本 1/4）与 `--boot` / `--boot-a` / `--boot-hold` |
| `D:\Github\gba-naruto\tools\s49_battle_balance\u2_scale_settle.py` | **新增** | 把键脚本的 `settle` 统一放大（开环回放丢输入时的备用手段） |
| `D:\Github\gba-naruto\tools\s49_battle_balance\u2_impact.py` | **新增** | 影响面评估：解析 `generated_battle_scenario_content.h`，统计 47 场战斗各自用了哪些角色、什么等级 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\u2_build_and_run.sh` | **新增** | 复跑脚本（编译 + 跑两遍 + 比对 sha256） |
| `D:\Github\gba-naruto\tools\s49_battle_balance\u2_ratchet.sh` | **新增** | 单测棘轮（HEAD 基线 vs 工作区，失败集合逐名比对） |
| `D:\Github\gba-naruto\tools\s49_battle_balance\u2_run_twice.sh` | **新增** | 复跑脚本（早期版本，已被 `u2_build_and_run.sh` 取代） |
| `D:\Github\gba-naruto\notes\s49-fidelity\U2-battle-balance.md` | **新增** | 本文件 |
| `D:\Github\gba-naruto\build\s49-battle-balance\u2\**` | 临时产物 | dump / routeA / routeB / 帧录 / 棘轮收据 |

**没有**改其它流的仪器（`s49_victory_capture/*` **只读调用**，
`v4_replay.py` / `capture_victory_frames.lua` 复用但未改）。

---

## 2. ⭐ 原版数值真值（逆向线，只读）

### 2.1 伤害公式（`notes/battle-damage-hit-bindings-20260723.json`，逆向线已闭合）

```
raw       = floor(power * attack / 10)
factor    = 100 - 5 * isqrt(defense)
per hit   = floor(raw * factor / 100)          # normal_defended
preview   = per hit * hit count                 # ← 屏幕上显示的「伤害」
critical  = floor(150 * raw / 100)              # 四个候选：普通/暴击 × 防御/无视防御
success   = min(99, template + trunc((src_agility - tgt_agility) / 2))
```

### 2.2 原版 battle-14 的单位（`notes/scenario-49-battle-14-runtime-20260720.md`）

> 「玩家槽 1..3 为 Naruto/Sasuke/Sakura，入口等级和 HP 为 `LV5/138`、`LV4/104`、
> `LV5/110`。槽 4 是 character 30、HP 40 的护送单位；
> 槽 5..9 是 character 55、LV5、HP 25 的五名敌人。」

| | 原版 | 出处 |
|---|---|---|
| 鸣人 (char 1) | **LV5 / 138 HP** | 逆向 battle-14 运行时记录 |
| 佐助 (char 2) | **LV4 / 104 HP** | 同上 |
| 小樱 (char 3) | **LV5 / 110 HP** | 同上 |
| 护送木叶丸 (char 30) | **40 HP** | 同上 |
| 蜜蜂 (char 55) | **LV5 / 25 HP** | 同上 |
| 十字手里剑打蜂 | **预览 27 伤害 / 84% 命中** | `notes/s49-fidelity/W4-original-victory-5th.md` §4.3 |
| 蜂打护送 | **12**（40 → 28 → 16） | 逆向记录「护送单位在第二次敌方阶段从 40 HP 降到 28 HP」 |
| 忍者组合拳 / 火遁術 | **10×1 / 98%**、**15×1 / 95%** | W4-R9（读原版自己的信息板） |

### 2.3 ⭐⭐ V4 的对比错在哪（**本流最重要的结论**）

V4 §4 的表格：

| | 原版 | 重制侧 |
|---|---|---|
| 单次伤害（十字手里剑） | **27** | **10 / 15 / 6** |

**这两个数不是同一个量。**

* 原版的 **27** 是**预览总值** = 每次防御后伤害 9 × **3 段** = 27；
* 重制侧的 **10 / 15 / 6** 是**招式模板威力**（`effect.potency`），
  是**单次**的原始值，还没乘段数、还没过防御系数。

⇒ V4 把「预览总值」和「模板威力」放在一张表里比 ⇒ 得出「重制侧伤害低一半」的结论 ⇒
把**驱动器缺陷**误判成**数值缺陷**。

---

## 3. ⭐ 重制侧 battle-14 的实测数值（`u2_route_gen --dump`）

转储命令（只读 include 重制线，不改一个字节）：

```bash
g++ -std=c++23 -O1 -w \
  -I /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel/game/include \
  /mnt/d/Github/gba-naruto/tools/s49_battle_balance/u2_route_gen.cpp \
  -o /tmp/u2_route_gen && /tmp/u2_route_gen --dump
```

### 3.1 单位表（重制侧 battle-14 variant 0）

| id | char | 阵营 | 等级 | HP/最大 | 攻 | 防 | 敏 | 移 | 查克拉 | AI | 位置 |
|---:|---:|---|---:|---|---:|---:|---:|---:|---|---:|---|
| 1 | 1 鸣人 | 我 | 5 | **138/138** | 18 | 17 | 12 | 3 | 5/5 | 1 | (11,6) |
| 2 | 2 佐助 | 我 | 4 | **104/104** | 15 | 11 | 15 | 3 | 4/4 | 1 | (10,14) |
| 3 | 3 小樱 | 我 | 5 | **110/110** | 11 | 11 | 14 | 3 | 3/3 | 1 | (8,14) |
| 4 | 30 护送 | 我 | 3 | **40/40** | 8 | 8 | 8 | 2 | 2/2 | 2 | (8,7) |
| 5–9 | 55 蜜蜂 | 敌 | 5 | **25/25** | 14 | **6** | **24** | 3 | 0/0 | 4 | (3,4)(4,8)(3,11)(6,6)(5,13) |

⇒ **HP 与等级逐项等于原版**（138 / 104 / 110 / 40 / 25，5 / 4 / 5 / 3 / 5）。

### 3.2 招式表与「原版公式」重算（重制侧自己的数据）

| 招式 | 模板 | 威力 | 段数 | 命中率 | 射程 | 对蜂**预览** | 对蜂**命中率** |
|---|---|---:|---:|---:|---:|---:|---:|
| **十字手里剑（忍具 1）** | `ninja_tool_action_definitions[1]` | 6 | **3** | 90 % | 3 | **27** | **84 %** |
| 忍者组合拳（active 5） | `active_action_definitions[5]` | 10 | 1 | 98 % | 1 | 16 | 92 % |
| 火遁術（active 16，佐助） | `active_action_definitions[16]` | 15 | 1 | 95 % | 2 | 19 | 91 % |
| 蜜蜂攻击（active 86） | `active_action_definitions[86]` | 10 | 1 | 95 % | 1 | 对护送 **12** | — |

重算（用逆向线已闭合的原版公式）：

```
十字手里剑：per hit = floor(6 * 18 / 10) = 10
              factor  = 100 - 5 * isqrt(6)   = 90
              per hit = floor(10 * 90 / 100) = 9
              预览     = 9 * 3               = 27      ← 原版实测 27 ✔
              命中率   = min(99, 90 + trunc((12 - 24) / 2)) = 84  ← 原版实测 84% ✔
蜂打护送  ：per hit = floor(10 * 14 / 10) = 14
              factor  = 100 - 5 * isqrt(8)  = 90
              per hit = floor(14 * 90 / 100) = 12      ← 原版实测 12 ✔
```

⭐ **三个「原版实测值」全部被重制侧自己的数据精确复现** ⇒
**重制侧 battle-14 的数值与原版一致，V4 的「数值不一致」结论不成立。**

### 3.3 数值是从原版 ROM 生成来的（不是重制线自己拍脑袋定的）

| 表 | 出处 | 逆向线的 provenance 记录 |
|---|---|---|
| 招式表 | `generated_battle_action_content.h` | `reverse-source-rom: 0x545BE4+1504` |
| 单位模板表（攻/防/敏/移/查克拉/最大 HP） | `generated_battle_unit_content.h` | `reverse-source-rom: 0x54241C+11340`（`sequel/content/units/bank.json`） |
| 等级成长表 | `generated_battle_result_content.h` | `reverse-source-rom: 0x545068+1008`（U3 独占文件） |
| 伤害公式 | `battle_action_system.h:2307-2328` | 与 `analyze_battle_damage_hit_formula.py` 的绑定逐项一致 |

成长公式（`battle_progression.h:262-296`）：
`value(level) = base + growth_per_100 * (level - 1) / 100`
⇒ 鸣人 `80 + 1450*4/100 = 138` ✔、佐助 `60 + 1480*3/100 = 104` ✔、
小樱 `50 + 1500*4/100 = 110` ✔、护送 `10 + 1500*2/100 = 40` ✔、
蜂 `5 + 500*4/100 = 25` ✔ —— **全部等于原版**。

---

## 4. ⭐ 影响面评估（`tools/s49_battle_balance/u2_impact.py`）

`generated_battle_scenario_content.h` 里 47 场战斗 × 3 个 variant 的角色使用统计：

| 角色 | 用到它的战斗数 | 战斗 id |
|---|---:|---|
| 1 鸣人 | **36 / 47** | 1,2,3,4,5,6,7,9,10,11,12,13,**14**,15,16,17,18,19,20,21,22,23,24,25,26,27,28,30,39,40,41,42,43,44,45,46 |
| 2 佐助 | **31 / 47** | 1,2,3,4,6,7,9,11,12,13,**14**,15,16,… |
| 3 小樱 | **30 / 47** | 1,2,3,4,6,9,11,12,13,**14**,15,16,… |
| 30 护送木叶丸 | **3 / 47** | **14**(LV3)、15(LV3)、41(LV1) |
| 55 蜜蜂 | **1 / 47** | **14**(LV5) |

**同时用到 1/2/3/30/55 的战斗只有 battle 14 一场。**

### 4.1 如果要改，改哪里、波及多少

| 要改的数 | 位置 | 作用域 | 波及场景数 | 本流是否改 |
|---|---|---|---:|---|
| 蜜蜂 (char 55) 的攻防敏 / 等级 | `battle_scenario_definitions[14]`（场景表，战斗专属） | **S49 专属** | 1 | **否** |
| 护送 (char 30) 的等级 3 | `battle_scenario_definitions[14]` + `battle_mission_rules_for(14,0)`（把 char 30 标成 allied AI） | 14 / 15 / 41 | 3 | **否** |
| 十字手里剑 / 忍者组合拳 / 火遁術 的威力、段数、射程 | `generated_battle_action_content.h`（**全局表**） | **全局** | 最多 **36** | **否** |
| 鸣人/佐助/小樱 的攻防敏 / 最大 HP | `generated_battle_unit_content.h` + `character_growth_definitions`（**全局表**） | **全局** | 最多 **36** | **否** |
| 蜜蜂每回合伤害 | `active_action_definitions[86]`（**全局表**） | **全局** | 所有用 char 55 的场景 | **否** |
| 伤害公式 | `battle_action_system.h`（**全局**） | **全局** | 全部 | **否** |

### 4.2 结论

* **改全局表 ⇒ 最多波及 36 场战斗**（其中 battle 15、41 也用护送木叶丸），
  且会把**已经与原版一致**的数值改歪 ⇒ **零收益**。
* **改 S49 专属值 ⇒ 只波及 1–3 场**，但同样**零收益**（数值本来就对）。
* ⇒ **本流不改任何数值**；影响面 = **0**。

### 4.3 怎么验（回归保护）

| 场景 | 怎么验 | 期望 |
|---|---|---|
| battle 14 | `u2_route_gen`（离线控制器跑完整场仗） | `outcome=1`（胜利）、`enemies=0`、护送 **16/40**、结算链到 `complete` |
| battle 14 数值 | `test_battle_s49_balance_truth.cpp` | 通过；任何数值改动 ⇒ 红 |
| 其它 46 场 | 数值表零改动 ⇒ **无需回归**（无改动即无影响） | — |
| 全局单测 | `build/run-baseline-tests.sh` vs `build/w1-run-all-tests.sh` | 失败集合**逐名相同**（20 项预存债） |

---

## 5. ⭐ 那为什么 V4 打不赢？—— 三个驱动器缺陷（不是数值）

V4 的 `v4_route_gen.cpp` 路线**逐字节复现**（stderr 完全一致）：
5 轮 / **0 命中** / 5 只蜂全活 / `outcome=2`（败北）/ 护送 40 → 0。

本流把重制侧的离线控制器**当产品代码**审了一遍，找到三个**与数值无关**的缺陷：

| # | 缺陷 | 证据 | 修法 |
|---|---|---|---|
| **R1** | **招式按模板威力排序**，不是按**有效伤害**排序 ⇒ 忍者组合拳（模板 10）赢过十字手里剑（模板 6），而后者实际是 **27** | V4 的 `attack_option::potency` 直接抄 `effect.potency` | 按「威力 × 段数 × 防御系数」排序 |
| **R2** | **移动用 `planned_move()`**：它找的是「到目标的曼哈顿距离 == 目标距离」的**任意**格（**不要求同行/同列**），再沿路径回退直到移动力用完 ⇒ 角色**永远站不到攻击线上**，每回合都放弃攻击 | 转储显示每回合 Naruto 都找到目标，但 `move_position` 与目标的距离 > 攻击距离 ⇒ 走 `end_action` 分支 | 改用 `find_attack_cell()` **已经验证过**的那一格（同行/同列 + 距离对 + 在移动范围内） |
| **R3** | **防御决定（defense_decision）没回答** ⇒ 流程卡死 | 107 条 `WARN confirm failed: error=4 player=9`（`player_flow_failed` / `defense_rejected`） | 上下键切换「是/否」，选**否**= 承受伤害（V4 的 `finish_turn` 其实做对了，本流一开始改错后又改回） |
| **R4** | **够不到蜂时去「守护送」而不是「追最近的蜂」** ⇒ 最后一只蜂永远够不到 | 第 5 轮：蜂 (5,3)、Naruto (10,7)，距离 9 | 改成追最近的蜂 |

### 5.1 修完之后

```
after the battle: phase=13 round=5 outcome=1 enemies=0
after the settlement: phase=16          # complete
```

* **outcome = 1（勝利）**，5 回合，**5 只蜂全灭**；
* 护送木叶丸 **16/40 存活** —— 与原版 W4 打赢时**同一个 16/40**；
* 结算链走完 `outcome → result → level_up → training → complete`；
* 两次独立跑 ⇒ 键脚本**逐字节一致**：
  `sha256 = 197b164f26cc64af28f6974250152ac3edf6f014caa1e12f4be4bf4280223790`（300 步）。

> 对照原版（W4）：7 回合 / 7 次行动 / 5 次命中 / 护送 16 HP。
> 重制侧：5 回合 / 全部 5 蜂灭掉 / 护送 16 HP。**结果一致**。

---

## 6. 跑了哪些验证（命令 + 关键数字）

| # | 命令 | 关键数字 |
|---|---|---|
| **V1** | `u2_route_gen --dump` | 单位表：138/104/110/**40**/25 HP，等级 5/4/5/**3**/5；蜂攻 14 防 **6** 敏 **24**；鸣人攻 18 敏 12 |
| **V2** | 同上（招式表） | 忍具 1 = 威力 6 × **3** 段 / 90 % / 射程 3；active 5 = 10×1/98 %；active 16 = 15×1/95 %；active 86 = 10×1 |
| **V3** | 用逆向线公式重算 | 十字手里剑对蜂**预览 27**、**命中率 84 %**；蜂打护送 **12** —— 与原版实测逐项相同 |
| **V4** | 复现 V4 的路线（改动前的同一份代码） | 5 轮 / **0 命中** / 5 蜂全活 / `outcome=2` ⇒ 与 V4 的 stderr **逐字节一致** |
| **V5** | 修完路线后 `u2_build_and_run.sh` | `after the battle: phase=13 round=5 outcome=1 enemies=0`；`after the settlement: phase=16`；**exit 0** |
| **V6** | 同上跑两遍比 sha256 | `197b164f26cc64af28f6974250152ac3edf6f014caa1e12f4be4bf4280223790`（两次**完全相同**） |
| **V7** | `u2_impact.py` | 47 场；char1 36 场、char2 31、char3 30、char30 3 场(14/15/41)、char55 **1 场(14)**；同时用全 5 个角色的只有 battle 14 |
| **V8** | `g++ -Wall -Wextra -Werror -pedantic` 编译并运行 `test_battle_s49_balance_truth.cpp` | 编译 0 warning、运行 exit 0 |
| **V9** | `build/run-baseline-tests.sh`（HEAD 基线） | **pass=101 fail=20** |
| **V10** | `build/w1-run-all-tests.sh`（工作区） | **pass=115 fail=20**；**新失败 = 空**、**被修好的 = 空** ⇒ 失败集合逐名相同 |
| **V11** | `g++ -Wall -Wextra -Werror -pedantic` 编译并运行新单测 | 0 warning、exit 0 |
| **V12** | ROM 回放 6 次变体（见 §8.1） | 离线胜利已达成；**ROM 录制未达成**，卡点定位在**开机流程**（不是数值、不是战斗） |
| **V13** | `Get-CimInstance Win32_Process -Filter "Name='mgba-probe.exe'"` | **0 个孤儿进程** |
| **V14** | LF / BOM 扫描（§12） | 9 个新文件全部 `bom=False, crlf_pairs=0` |
| **V15** | `git status --porcelain`（两个仓） | 本流文件全部 `??`（未跟踪）；重制线只有 `?? butano-sequel/game/tests/test_battle_s49_balance_truth.cpp` |

---

## 7. 单测棘轮（`tools/s49_battle_balance/u2_ratchet.sh`）

| | 命令 | 结果 |
|---|---|---|
| HEAD 基线 | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh` | **pass=101 fail=20**（20 项预存债，逐名见下） |
| 工作区 | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh` | **pass=115 fail=20** |

⭐ **失败集合逐名相同**：

```
baseline failures: 20
workspace failures: 20
--- new failures (must be empty) ---      ← 空
--- fixed failures (informational) ---     ← 空
```

HEAD 基线的 20 项预存债：
`test_battle_all_scenario_runtime`、`test_battle_campaign_route`、
`test_battle_campaign_save`、`test_battle_campaign_scenario_42`、
`…_43`、`…_44`、`…_45`、`…_46`、`…_47`、`…_49`、
`test_battle_dynamic_deployment_turn`、`test_battle_material_pickups`、
`test_battle_presentation_controller`、`test_battle_runtime_scene_gate`、
`test_battle_s49_input_flow`、`test_battle_s49_opening`、
`test_battle_scene_character_actions`、`test_battle_scene_controller`、
`test_battle_scene_multi_unit`、`test_battle_scene_results`。

**本流新增的 `test_battle_s49_balance_truth` 在工作区里通过**（`-Wall -Wextra -Werror
-pedantic` 0 warning，exit 0）⇒ **零回归**。

---

## 8. 判据 A：ROM 上录「勝利」屏与结算屏 —— **未达成，卡在开战前的流程**

### 8.1 做了什么

| 尝试 | 改动 | 结果 |
|---|---|---|
| **R1** | `v4_replay.py` + `--capture all` + `boot-a 3` | 录到 115,469 帧（2.3 GB），但 ROM **停在了战斗里**（末帧仍是战斗指令菜单），结算链没出现 |
| **R2** | 新写 `u2_replay.py`（`--capture step`，每步一帧，成本 1/4） + `boot-a 32` | 335 张抽样帧：ROM 在**部署画面**（"CANNOT SELECT"），战斗在 idx≈130 才开始 ⇒ **脚本的前 100 步被开机流程吃掉了** |
| **R3** | `boot-a 64` | 367 张抽样帧：仍在部署画面 ⇒ **A 键数量不是瓶颈** |
| **R4** | `boot-a 48` + 开机 A **按住 120 帧** | 351 张抽样帧：仍在部署画面 ⇒ **A 键的「按住」也不是瓶颈** |
| **R5** | **开机前缀改成 `Down,Down,A,Down,Down,Down,A×10,Down,A`**（用 step 采样逐帧反查出来的） | ⭐ **开机流程被走通了**：ROM 从标题 → 剧情 → 部署 → **战斗的开场对白** |
| **R6** | 用 R5 的前缀 + 完整胜利键脚本（step 采样） | 318 张抽样帧：ROM 在**部署/对白**里来回，**战斗始终没拿到输入** ⇒ **脚本仍被开机流程吃掉** |

### 8.2 ⭐ 结论：**卡点不是数值、也不是战斗，是「开机流程」**

* 离线控制器**从战斗场景开始**（`battle_scene_controller::load()` 直接装载场景）；
  ROM 却要从**上电**开始走：
  `标题 → 剧情对白 → 战前简报 → **部署画面**（要选 3 个队员，菜单是
  [PLAYER / ENEMY] + [OK / BACK]，选错会出「CANNOT SELECT」）→ 队伍一览表 → 战斗开场对白 → 战斗`。
* 这段流程**是交互式的**（要移动光标、要回答「使用忍具？」的是/否），
  **离线控制器完全没建模它** ⇒ 键脚本的按键落在这些画面上，战斗永远拿不到输入。
* ⇒ **这是 U1 的范围**（`battle_runtime_scene.cpp` 是 U1 独占文件，
  部署/准备流程的输入分派在那里）。

### 8.3 可复跑的录制方案（交给 U1/U3/U4）

**已验证可复用的零件**：

| 零件 | 内容 |
|---|---|
| **胜利键脚本** | `build/s49-battle-balance/u2/routeA.json`（300 步，sha256 `197b164f…3790`，**两次跑逐字节一致**） |
| **离线胜利证明** | `tools/s49_battle_balance/u2_build_and_run.sh` ⇒ `outcome=1`、5 蜂全灭、护送 16/40、结算链到 `complete` |
| **回放器** | `tools/s49_battle_balance/u2_replay.py`（`--capture step` 抽样便宜 4 倍；`--boot` / `--boot-a` / `--boot-hold` 可调） |
| **开机前缀** | `Down,Down,A,Down,Down,Down,A×10,Down,A` ⇒ **能走到战斗的开场对白**（R5 实测） |

**下一步（两步，各 4 分钟）**：

1. **把开机前缀补到「战斗指令菜单」**：
   用 `u2_replay.py --capture step` + 一条更长的开机前缀，
   看抽样帧停在哪个画面（部署 → 队伍一览 → 战斗指令菜单），
   把 prefix 补到**战斗指令菜单**为止。
2. **前缀对齐后直接全量录**：
   `u2_replay.py --capture all --boot "<前缀>"`，
   两次独立跑 ⇒ `w4_verify.py` 比帧级 sha256。

**闭环替代方案**（如果开环仍不同步）：
探针的 Lua 帧回调**可以读 ROM 内存**（`probe.py` 的 `dump`），
把重制侧 `battle_scene_controller` 的状态（`_phase` / `_cursor` / `_selected_unit`）
在 EWRAM 里的地址定出来，就能做「读状态 → 决策 → 按键」的闭环驱动，
彻底摆脱开环计时。**这需要 U1 提供状态布局**（`_runtime` 是 `battle_scene_controller`
的私有成员，地址未导出）。

### 8.4 附带发现（对 U1/U3 有用）

* **重制侧的上电流程比 V4 假设的长得多**：V4 的 `--boot-a 3` 只能停在
  「战前简报 / 队伍一览表」（V4-8 已记），实测**再加 64 次 A 也出不了部署画面**；
  必须用 `Down,Down,A,Down,Down,Down,A×10,Down,A` 才走得过去。
* ROM 在录制期间被 U1 重建过（sha256 `73b74587…` → `21650614…`），
  **任何录制收据都必须带 ROM 的 sha256**，否则帧与 ROM 对不上。

### 8.5 ⭐ 判据 B 的备选（如果 ROM 录制短期做不出来）

任务书要求：「若判定『不该改』⇒ 给出『敗北后结算链』的可复跑录制方案」。
本流也把这条备选做成了可复跑的形式：

| 项 | 内容 |
|---|---|
| 敗北路线的键脚本 | V4 的 `build/s49-victory-capture/v4/route.json`（253 步，sha256 `cc599dcb…6be`） |
| 本流的等价物 | `u2_route_gen.cpp` 里只要**不攻击**（`select_best_action` 返回 false 就 `end_action`），立刻得到一条敗北路线，格式与 V4 的 `route.json` 完全一致 ⇒ `v4_replay.py` / `u2_replay.py` 直接吃 |
| 录到的段 | V4 已录到 `training` 段（「AVAILABLE TOOL」「NO AVAILABLE TOOL」「EQUIP COMPLETE」「隊員一覧表」四张屏）⇒ **忍具一览**这一段**已经有运行帧** |
| 缺的段 | 「勝利」屏、结算屏、**逐人升级屏**（原版 4 张）、战后对白、任务菜单 |

⇒ **判据 B 的「敗北后结算链」已有可复跑方案**；
判据 A 的「勝利屏 + 结算屏」需要先解决开机流程（§8.3）。

---

## 9. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **U2-1** | 重制侧 battle-14 的数值与原版不一致 | 逐项对齐 HP / 等级 / 攻防敏 / 招式表 / 伤害公式（`--dump` + 逆向线公式） | HP **138/104/110/40/25**、等级 **5/4/5/3/5** 全部**等于原版**；公式逐项等于逆向线绑定 | **已证伪**（数值本来就一致） |
| **U2-2** | V4 的「原版 27 vs 重制侧 10/15/6」是同一口径 | 查两边的量纲 | 27 = 预览总值（9 × **3** 段）；10/15/6 = 招式模板威力（**单次**） | **已证伪**（量纲不同） |
| **U2-3** | 重制侧 battle-14 打不赢是**数值**问题 | 用重制侧自己的控制器跑一条胜利路线 | `outcome=1`、5 蜂全灭、护送 16/40、结算链到 `complete` | **已证伪**（是驱动器问题） |
| **U2-4** | V4 的路线生成器能复现 V4 的败北 | 改动前跑同一份代码，比 stderr | 5 轮 / 0 命中 / 5 蜂全活 / `outcome=2`，与 V4 的 `route.err` **逐字节一致** | **已确认** |
| **U2-5** | V4 路线「移动到攻击格」的 `planned_move()` 是对的 | 看它返回的格子与目标是否同行/同列、是否在移动范围内 | 返回的格子**不满足**攻击直线条件 ⇒ 每回合放弃攻击 | **已证伪** |
| **U2-6** | 重制侧有十字手里剑（6 × 3 段 / 射程 3）可用 | 读 `ninja_tool_action_definitions[1]` + 转储忍术列表 | 有，且在 Naruto 的列表里 | **已确认** |
| **U2-7** | 用掉忍具后它还在列表里 | 读 `battle_action_cost_policy::commit` | `equipped_tools[slot] = no_ninja_tool` ⇒ **用掉即消失** ⇒ V4 的硬编码选项列表整回合失败 | **已证伪**（会消失） |
| **U2-8** | 防御决定不回答会卡住 | 不回答时的返回码 | 107 次 `player_flow_failed / defense_rejected`（`player=9`）；上下键切换是/否，选「否」= 承受伤害 | **已确认** |
| **U2-9** | 改数值会波及多少场景 | `u2_impact.py` 统计 47 场 | char1 **36** 场、char2 31、char3 30、char30 **3** 场、char55 **1** 场 | **已确认** |
| **U2-10** | 重制侧 battle-14 能打赢 ⇒ 「勝利」屏与结算屏可在 ROM 上录 | 把胜利键脚本在 ROM 上回放 | **离线**已达成（两次跑逐字节一致）；**ROM 上未达成** —— 卡在开机流程（§8） | **部分确认**（ROM 录制未达成） |
| **U2-11** | ROM 回放走不到战斗，是因为键太少 | step 采样逐步看画面 | A 键加到 64 次、加住到 120 帧都出不了部署画面 | **已证伪**（不是键的数量/长度） |
| **U2-12** | ROM 回放走不到战斗，是因为没有方向键 | step 采样逐步看画面 | `Down,Down,A,Down,Down,Down,A×10,Down,A` ⇒ **走到了战斗的开场对白** | **已确认**（方向键才是关键） |
| **U2-13** | 补齐开机前缀后，胜利键脚本就能驱动 ROM 打完这场仗 | 用 R5 的前缀 + 完整脚本 step 采样 | ROM 在部署/对白之间来回，**战斗仍没拿到输入** ⇒ 开机流程还需要更多交互（选队员、回答「使用忍具？」） | **已证伪**（前缀还不够） |

---

## 10. 卡在哪 / 遗留风险

* **本流的核心结论没有阻塞项**：数值不需要改；胜利路线已跑通并两次逐字节一致。
* **阻塞项（判据 A 的 ROM 录制）**：**重制侧的开机流程**（部署/队伍一览）
  是交互式的，离线控制器没建模 ⇒ 键脚本的按键被这些画面吃掉。
  **归属 U1**（`battle_runtime_scene.cpp` 独占）。方案见 §8.3。
* **遗留风险 1**：本流的新单测只钉住 battle-14 的数值；
  其余 46 场战斗的数值与原版的一致性**本流没有逐场核对**
  （但表本身是 ROM 生成的，且本流**零改动** ⇒ 没有引入任何偏差）。
* **遗留风险 2**：离线控制器与 ROM 的**行为一致性**只在 battle-14 的**离线**侧验证过。
* **遗留风险 3**：录制期间 ROM 被 U1 重建过 ⇒ **最终录制必须重跑**，且收据必须带 ROM sha256。
* **遗留风险 4（磁盘）**：失败的 R1 全量录制留下 **2.3 GB** 帧
  （`build/s49-battle-balance/u2/remake-victory/frames`，gitignored）。
  本机的可恢复删除命令在本次会话里不可用（`rm -- …` 要求一个 trash 标记，未能执行），
  **留给父代理清理**。

---

## 11. 确认

* **新文件一律 LF、无 BOM**（见 §12 的扫描结果）。
* **未提交 git**（本流文件在工作区里是未跟踪状态：`?? tools/s49_battle_balance/`、
  `?? notes/s49-fidelity/`）。
* **未改 `battle_runtime_scene.cpp`**（U1 独占），**未改 `battle_black_field*.h` / `graphics/`**。
* **未改 `battle_result*.h` / `generated_battle_result_content.h`**（U3 独占）。
* **未改 `battle_unit_content.h` / `generated_battle_unit_content.h` /
  `battle_conditions.h` / `battle_scenario_content.h` / `battle_ai*.h`**
  （本流独占，但**不需要改**）。
* **未改逆向线任何文件**（`D:\Shell\gba-naruto-reverse` 只读）。
* **重制线零逻辑改动**，只新增了一个单测文件。
* **没有伪造任何帧**：所有 PNG 都来自探针内 Lua 帧回调的逐帧截图。
* **孤儿进程检查通过**：`mgba-probe.exe` 残留 **0** 个。

---

## 12. LF / BOM 扫描

| 文件 | bom | crlf_pairs |
|---|---|---:|
| `notes/s49-fidelity/U2-battle-balance.md` | False | 0 |
| `tools/s49_battle_balance/u2_route_gen.cpp` | False | 0 |
| `tools/s49_battle_balance/u2_impact.py` | False | 0 |
| `tools/s49_battle_balance/u2_replay.py` | False | 0 |
| `tools/s49_battle_balance/u2_scale_settle.py` | False | 0 |
| `tools/s49_battle_balance/u2_build_and_run.sh` | False | 0 |
| `tools/s49_battle_balance/u2_ratchet.sh` | False | 0 |
| `tools/s49_battle_balance/u2_run_twice.sh` | False | 0 |
| `butano-sequel/game/tests/test_battle_s49_balance_truth.cpp` | False | 0 |
