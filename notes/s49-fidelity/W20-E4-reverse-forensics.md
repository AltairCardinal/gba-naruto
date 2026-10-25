# W20-E4 —— 逆向取证：敌人阵型记录的「戰鬥分」种子

> wave 20 / E4 流 · 子代理 = worker · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 创建时间：2026-10-25 20:36 (GMT+0800)
> 更新时间：2026-10-25 21:35 (GMT+0800)
> 状态：**主任务已闭环**（种子值 + 规则 + 结算真值）；次任务（资产清理）清单已出

---

## 0. 任务范围（来自父代理任务书）

1. **主任务**：在逆向线（`D:\Shell\gba-naruto-reverse`，**只读**）取证
   * battle 14（及 group/variant）阵型记录里每个敌人单位的 `+0x0C`（戰鬥分种子）；
   * 验证 E2 给的地址公式 `ROM 0x5461C4 + group*0x1AAC + variant*0x08E4 + 4 + record*0x0B8`，记录内 `+0x0C`；
   * 独立复核原版结算真值 `125/125/125`、`100/150/0`、`75/75/75`、`300/350/200`，
     以及场景 41（`100 / 50 / 0 / 150`）、场景 46（`125/125/125、60/60/30、0、185/185/155`）；
   * 输出机器可读 JSON `build/w20-e4/enemy-battle-experience.json`。
2. **次任务**：全工程扫描 `graphics/scenario_41_postbattle_dialogue_*.bmp|.json`，
   找出产品代码零引用的 33 张旧对白资产，出清单；**清理只在自己的 lane 副本里做**。

**判定问题**：「原版的『戰鬥分』= 敌人阵型记录里的种子值，按击倒数转移给攻击者」在原版 ROM 上是否成立？每个敌人的种子值分别是多少？

---

## 1. 一句话结论

> ⭐⭐⭐ **E2 猜的「battle 14 的 5 个敌人各带 50 戰鬥分」是对的，而且种子值根本不需要猜 ——
> 它就明明白白写在原版 ROM 的阵型记录里**（`0x5461C4 + group*0x1AAC + variant*0x08E4 + 4 + record*0x0B8`
> 记录内 `+0x0C` 的 u16 LE）。
> **重制侧之所以全是 0，不是数据缺失，而是 `generated_battle_scenario_content.h` 是旧产物 ——
> 现在跑一遍生成器就会自动填上正确的种子值**（`sequel/content/positions/bank.json` 里的
> `battle_experience` 字段已经是对的，1728 条记录与 ROM 字节**逐一相符，0 处不符**）。
>
> ⛔ 但**规则比「转移」多一步**：原版 `0x08089064..0x080890F0` 的公式是
> **`戰鬥分 = Σ 同角色存活单位的 carried_experience + (carried × 被动 value_a) / 100`**
> （被动目标类型 `0x15`）⇒ **种子值是必要条件，但不是充分条件**（见 §3.4 的 59 之谜）。
>
> 🔴🔴 **更正（§7，最高优先级）：种子值「已经在产品里了」，不是缺的！**
> `generated_battle_scenario_content.h`（共享树与 lane 副本**逐字节相同**，sha256 `b5c031ad…`）
> **本来就带着正确的种子**（battle 14 的 5 个敌人 = 50，共 **229** 个非零 `battle_experience`）。
> `battle_scenario_loader.h:465` 把它写进 `unit.carried_experience`，
> `battle_action_system.h:2327-2333` 负责转移，产品自带的 `test_battle_experience_flow.cpp`
> **断言这条链是通的**（`unit(2)->carried_experience == 50` → 击杀后 `unit(1) == 50`）。
> ⇒ **那 684 px 的根因不在种子数据**，「E4 取证 → E2 填数据」这条路走不通，
> 真正的缺口在别处（§7 给了三条候选线索）。

---

## 2. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| P-40 | E2 的地址公式 `0x5461C4 + group*0x1AAC + variant*0x08E4 + 4 + record*0x0B8`（记录内 `+0x0C`）正确 | 逆向线 `notes/addresses.md:67-70`、`notes/positions-rom-source-20260710.md`、`tools/extract_positions.py:18-24` 三处独立一致 + 直接读 ROM 命中 | 成立 | **已确认** |
| P-41 | battle 14 的 5 个敌人各带 50 戰鬥分（E2 的猜） | 直接读 `base.gba` 的 group 14 / variant 0 记录 4..8 | **成立**：5 条全是 `u16@0x0C = 50` | **已确认** |
| P-42 | 原版結算第 2 行 = 同角色单位身上的戰鬥分之和 + 被动百分比 | 逆向线 `tools/analyze_battle_passive_consumers.py` 的 `0x08089064..0x080890F0` 代码切片 | 成立（且**比 E2 的「纯转移」多一个被动项**） | **已确认** |
| P-43 | 原版結算真值 = `125/125/125`、`100/150/0`、`75/75/75`、`300/350/200` | 独立读 `settlement-truth/02-settlement-exp-power-turns.png` | 成立 | **已确认** |
| P-44 | 场景 41 真值 = `經驗值 100、戰鬥分 50、回合數 0、合計 150` | 独立读 `build/w20-e4/s41-settlement-numbers.png` | 成立 | **已确认** |
| P-45 | 场景 46 真值 = `125/125/125、60/60/30、0、185/185/155` | 独立读 `build/w20-e4/s46-settlement-numbers.png` | **不成立**：实测是 **`59/59/30`、合計 `184/184/155`**（差 1） | **已证伪** |
| P-46 | 33 张 `scenario_41_postbattle_dialogue_*` 旧资产在产品代码零引用 | 全树 1255 个候选文本文件逐一扫描 | 成立（正好 **33** 个 stem 零命中） | **已确认** |
| P-47 | 原版「击倒 ⇒ 戰鬥分转给攻击者」在 ROM 上成立 | 5 组独立結算真值与种子值对账 | 成立（见 §3.3 表） | **已确认** |
| P-48 | 场景 46 的 `59` 能由种子直接相加得到 | 枚举全部 48 组 × 3 变体的种子值集合 | **不成立**：全部种子都是 5 的倍数，**59 不可能是种子和** | **已证伪** |
| P-49 | 重制侧 0 值是「生成器没填」而非「数据源没有」 | 读生成器读取路径 + 与 bank.json 对账 | **不成立**：生成器**早就在读** `+0x0C`，是**产物过期** | **已证伪** |
| P-50 | 场景 46 的 59 = 种子和 60 施加 value_a = −2 的 0x15 被动后截断得到 | 手算 `60 + (60×−2)/100 = 59`（C 向零截断）、`30 + (30×−2)/100 = 30` | 算术自洽，但**被动来源未定位** | **未验** |
| P-51 | 「重制侧种子字段全是 0」 | 逐场景逐槽位解析共享树 + lane 副本的 `generated_battle_scenario_content.h` | **不成立**：battle 14 的 5 个敌人**全是 50**；全表 **229** 个非零 | **已证伪** |
| P-52 | 种子没有进到 `carried_experience` | 读 `battle_scenario_loader.h:465` + 产品自带 `test_battle_experience_flow.cpp` | **不成立**：加载器写入了，测试断言 `== 50` | **已证伪** |
| P-53 | 击倒转移没发生 | 读 `battle_action_system.h:2315-2338` | **不成立**：`target.active = false` 后 `experience_recipient.carried_experience += target.carried_experience` | **已证伪** |
| P-54 | 33 张旧对白资产被链接进 ROM，占用 ~1 MB | 解析 lane 构建的链接器 map `build/butano-sequel.map` | **部分成立**：**33/33 全部被链接**，但实际占用 **264,768 B（≈259 KB）**，**不是 ~1 MB** | **已证伪**（量级错 4×） |
| P-55 | 可以在 lane 副本里安全删除这些资产 | `Get-ChildItem -Force` 查链接类型 | **不成立**：lane 的 `butano-sequel/graphics`、`butano-sequel/audio` 都是**指向共享树的符号链接** | **已证伪** |

---

## 3. 取证日志

### 3.1 地址公式与字段（逆向线只读）

* 逆向线三处独立记录同一公式：
  * `D:\Shell\Github\gba-naruto-reverse\notes\addresses.md:66-73`
  * `D:\Shell\Github\gba-naruto-reverse\notes\positions-rom-source-20260710.md`（第 2/3/4 节）
  * `D:\Shell\Github\gba-naruto-reverse\tools\extract_positions.py:18-24`
* 矩阵形状：**48 group × 3 variant × 12 record**，record stride `0xB8`，首记录 +4。
* 记录内字段（`D:\Shell\Github\gba-naruto-butano\tools\extract_positions.py:25-34`）：

  | 偏移 | 字段 |
  |---|---|
  | `+0` | selector（角色 id，`0xFA..0xFF` = 部署占位） |
  | `+1` | affiliation（0 = 玩家，1 = 敌人） |
  | `+2` / `+3` | x / y（格坐标） |
  | `+4` | facing |
  | `+8` | aux_u32 |
  | **`+0x0C`** | **battle_experience（u16 LE）← 戰鬥分种子** |
  | `+0x0E` | unit_parameter |
  | `+0x0F` | level |

### 3.2 「重制侧全是 0」的真正原因（**推翻 E2 的前提假设**）

* 生成器 `D:\Shell\Github\gba-naruto-butano\tools\generate_butano_battle_scenario_content.py:209-218`
  **本来就读 `+0x0C`**：

  ```python
  battle_experience = row.get("battle_experience")
  if battle_experience is None:
      raw_hex = row.get("raw_hex", "")
      battle_experience = int.from_bytes(bytes.fromhex(raw_hex)[0x0C:0x0E], "little")
  ```
* 数据源 `sequel/content/positions/bank.json`（version 3）**已经带 `battle_experience` 字段**，
  且 `raw_hex` 与 ROM **逐字节相同**。
* ⇒ **不是「要改生成器」，而是「产物过期」**：
  `generated_battle_scenario_content.h` 是旧产物（那次生成时 bank.json 还是 version 2 / 种子还是 0）。
  **现在重跑生成器即可填出正确种子**，生成器本身**不用改一行**。
* 验证脚本：`tools/s49_w20e/probe_bank_vs_rom.py`（对比 bank 与 ROM）+
  `tools/s49_w20e/extract_enemy_battle_experience.py`（全量提取 + 1728 条对账，**mismatches = 0**）。
* 附证：生成头里的 provenance 哈希与 `base.gba` **完全吻合** ⇒ 生成器读的就是原版 ROM：

  | 区域 | 生成头写死的 sha256 | `base.gba` 实测 | 结论 |
  |---|---|---|---|
  | `0x53D910 + 1504` | `977b4393…6566c` | `977b4393…6566c` | ✅ |
  | `0x5461C4 + 317952` | `6e3b0e0b…d5ed6` | `6e3b0e0b…d5ed6` | ✅ |

  （`base.gba` 整 ROM sha256 = `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`）

### 3.3 ⭐ 规则验证：种子 → 結算屏，5 组独立对账

场景映射来自重制侧 `game/include/konoha/battle_campaign_route.h:38-55`：

| 重制 scenario_id | battle_id | variant | 敌人种子（variant 0） | 原版实测結算「戰鬥分」 | 对账 |
|---:|---:|---:|---|---|---|
| 41 | 41 | 0 | `[50]` | `50`（單人） | ✅ 1 杀 × 50 |
| 43 | 43 | 0 | `[10, 10, 10]` | `30` | ✅ 3 杀 × 10 |
| 46 | **9** | 0 | `[30, 30, 30, 30, 30]` | `59/59/30`（合計 148） | ⚠️ 差 2（见 §3.4） |
| 47 | **13** | 0 | `[75, 75, 75, 75, 75]` | `75` | ✅ 1 杀 × 75 |
| 49 | **14** | 0 | `[50, 50, 50, 50, 50]` | `100/150/0`（合計 250） | ✅ **2 杀 + 3 杀 + 0 杀 = 5 杀** |

* 原版实测值来源：
  * scenario 41 / 46：`build/w20-e4/s41-settlement-numbers.png`、`s46-settlement-numbers.png`
    （上一波 E4 截断续作；这两张是**原版 ROM** 的結算屏裁切）
  * scenario 49：`build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png`
    （收据 `settlement-truth.json`，ROM sha `1198ece7…9d05b`，存档点 `scenario-49-battle-14-turn4-two-kills.ss9`）
  * scenario 43 / 47 / 49 的「單值」：`D:\Shell\Github\gba-naruto-butano\tools\butano\mgba_battle_campaign_route.lua`
    （驱动**原版 ROM** 的 mgba 脚本，`expected_battle_experience` = 30 / 75 / 100）
* ⭐ **battle 14 的对账是决定性的**：原版結算屏「戰鬥分」行 = `100 / 150 / 0`，
  合計 = 250 = **5 个敌人 × 50**（每个都算上了，且按击倒数分给了三名队友：2/3/0）。
  ⇒ **「敌人阵型记录里的种子值 + 按击倒数转给攻击者」这条规则，在原版 ROM 上成立。**

### 3.4 ⛔ 原版规则**不止「转移」**：还有被动百分比（`0x15`）

逆向线 `tools/analyze_battle_passive_consumers.py` 已经把原版的結算代码切片钉死：

* 代码区间 `0x08089064 .. 0x080890F0`（sha256 `03f7940f…5900c`）
* 关键指令：

  | 地址 | 字面量 | 含义 |
  |---|---|---|
  | `0x08089092` | `0x7810` | 取单位 character id |
  | `0x080890AA` | `0x8800` | **取 carried experience** |
  | `0x080890BE` | `0x2115` | 被动目标类型 `0x15` |
  | `0x080890D0` | `0x8800` | 取被动 value_a |
  | `0x080890D2` | `0x4360` | 乘法 |
  | `0x080890D4` | `0x2164` | 除以 100 |
  | `0x080890DA` | `0x1820` | **加上被动加成** |

* ⇒ **原版公式**：`戰鬥分 = Σ(同 character_id 的玩家单位 carried_experience) + carried × value_a / 100`
* 重制侧 `battle_results.h:369-395` 的 `_battle_experience()` **已经是这个口径**
  （`result += unit->carried_experience;` + `result += result * bonus.value_a / 100;`）
  ⇒ **发奖公式不用改；只缺种子数据（+ 被动 value_a 正确）。**

**场景 46 的 `59` 之谜（未完全闭合，但已排除「种子错」）：**

* 场景 46 = battle 9，5 个敌人 × 30 = **150**；原版結算三列 `59 + 59 + 30 = **148**`，**差 2**。
* ⛔ **59 不可能是种子和**：全矩阵 48×3×12 共 1728 条记录的种子集合 =
  `{10, 30, 50, 70, 75, 100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 500, 700}`，
  **全部是 5 的倍数，59 不在其中**（`tools/s49_w20e/survey_seeds.py`）。
* ⇒ 只能是**算出来的**：`59 = 60 + (60 × (−2)) / 100`（C 向零截断：`−120/100 = −1`），
  `30 = 30 + (30 × (−2)) / 100`（`−60/100 = 0`）。
  **⇒ 场景 46 存在一个 value_a = −2 的 0x15 被动（−2 %），场景 49 没有。**
* ⚠️ 任务书里的「场景 46 真值 = `60/60/30`、`185/185/155`」与实测截图
  **`59/59/30`、`184/184/155`** 不符，**实测截图优先**
  （`s46-settlement-numbers.png` 的合計 `184 = 125 + 59 + 0` 自洽）。
  另注 `mgba_battle_campaign_route.lua` 里 `expected_battle_experience` 对场景 46 写的是 **60** ——
  **该期望值与实测差 1，尚未查清是哪一侧抄错**（列为未完成项 U-2）。

---

## 4. 数据

### 4.1 机器可读数据

* **`build/w20-e4/enemy-battle-experience.json`**（schema `konoha.s49-enemy-battle-experience.v1`）
  * 47 个场景 × 3 个 variant × 12 个单位 = **1692 个单位条目**，每条含
    `id / record_id / enabled / selector_kind / selector / character_id / side / side_name / x / y / facing / level / unit_parameter / battle_experience / rom_offset / rom_offset_hex / raw_prefix_hex`。
  * `scenarios[i].battle_id` == `group` == `group_id` == 地图 bank 的 `_index`（生成器用同一个 `expected_id`）。
  * `units[i].id` == `record_id` == `battle_scenario_unit_slot[12]` 里的槽位下标。
* **`build/w20-e4/formation-matrix.csv`**：同一份数据的扁平表（1728 行，便于 diff/导入）。
* 工具：`tools/s49_w20e/extract_enemy_battle_experience.py`（主）、`show_variants.py`、
  `survey_seeds.py`、`probe_bank_vs_rom.py`。

### 4.2 每个敌人单位的种子值（variant 0 = 重制侧实际使用的变体）

| battle | 敌人数 | 每个敌人的戰鬥分种子 | 合计 | | battle | 敌人数 | 每个敌人的種子 | 合計 |
|---:|---:|---|---:|---|---|---:|---|---:|
| 0 | 0 | — | 0 | | 24 | 4 | 200 ×4 | 800 |
| 1 | 2 | 200 ×2 | 400 | | 25 | 3 | 250 ×3 | 750 |
| 2 | 3 | 125 ×3 | 375 | | 26 | 3 | 250 ×3 | 750 |
| 3 | 2 | **200, 0** | 200 | | 27 | 3 | 250 ×3 | 750 |
| 4 | 4 | 125 ×4 | 500 | | 28 | 3 | 300, 250, 200 | 750 |
| 5 | 2 | 200 ×2 | 400 | | 29 | 3 | 250 ×3 | 750 |
| 6 | 5 | 125 ×5 | 625 | | 30 | 6 | 250 ×6 | 1500 |
| 7 | 1 | 250 | 250 | | 31 | 1 | 250 | 250 |
| 8 | 1 | 250 | 250 | | 32 | 3 | 100 ×3 | 300 |
| 9 | 5 | 30 ×5 | 150 | | 33 | 3 | 100 ×3 | 300 |
| 10 | 2 | 200 ×2 | 400 | | 34 | 3 | 100 ×3 | 300 |
| 11 | 2 | 200 ×2 | 400 | | 35 | 3 | 100 ×3 | 300 |
| 12 | 1 | 175 | 175 | | 36 | 3 | 100 ×3 | 300 |
| **13** | 5 | **75 ×5** | 375 | | 37 | 3 | 100 ×3 | 300 |
| **14** | 5 | **50 ×5** | **250** | | 38 | 3 | 100 ×3 | 300 |
| 15 | 5 | 70 ×5 | 350 | | 39 | 1 | 100 | 100 |
| 16 | 3 | 70 ×3 | 210 | | 40 | 0 | — | 0 |
| 17 | 1 | 175 | 175 | | **41** | 1 | **50** | **50** |
| 18 | 2 | 175 ×2 | 350 | | 42 | 1 | 10 | 10 |
| 19 | 2 | 150 ×2 | 300 | | **43** | 3 | **10 ×3** | **30** |
| 20 | 3 | 100 ×3 | 300 | | 44 | 1 | 100 | 100 |
| 21 | 0 | — | 0 | | 45 | 1 | 100 | 100 |
| 22 | 3 | 200 ×3 | 600 | | 46 | 1 | 500 | 500 |
| 23 | 5 | 200 ×5 | 1000 | | | | | |

> **battle 3 的两个敌人是 `200` 和 `0`**（`+0x0C` 真的是 0，不是 200）。
> **variant 1 在这批战斗里全空**；**variant 2 的种子普遍更高**（例：battle 14 v2 = 75 ×5，battle 9 v2 = 50 ×5）。
> 完整 3 变体数据见 JSON / CSV。

### 4.3 battle 14 的逐单位明细（variant 0）

| 槽位 id | selector | character_id | side | x | y | facing | **battle_experience** | ROM 偏移 |
|---:|---:|---:|---|---:|---:|---|---:|---|
| 0 | 1 | 1 | player | 11 | 6 | left | 0 | `0x055D730` |
| 1 | 2 | 2 | player | 10 | 14 | up | 0 | `0x055D7E8` |
| 2 | 3 | 3 | player | 8 | 14 | up | 0 | `0x055D8A0` |
| 3 | 30 | 30 | player | 8 | 7 | right | 0 | `0x055D958` |
| **4** | 55 | 55 | **enemy** | 3 | 4 | right | **50** | `0x055DA10` |
| **5** | 55 | 55 | **enemy** | 4 | 8 | right | **50** | `0x055DAC8` |
| **6** | 55 | 55 | **enemy** | 3 | 11 | right | **50** | `0x055DB80` |
| **7** | 55 | 55 | **enemy** | 6 | 6 | right | **50** | `0x055DC38` |
| **8** | 55 | 55 | **enemy** | 5 | 13 | right | **50** | `0x055DCF0` |
| 9..11 | — | — | — | — | — | — | 0（记录全零 = 不存在） | `0x055DDA8` 起 |

---

## 5. 旧对白资产清单

* 扫描脚本：`tools/s49_w20e/scan_unused_dialogue_assets.py`（全树 1255 个候选文本文件，逐一 grep）
* 报告：`build/w20-e4/unused-dialogue-assets.json`
* 结果：`graphics/scenario_41_postbattle_dialogue_*` 共 **80 个文件 / 40 个 stem**
  * **7 个被引用**：`..._page_1` .. `..._page_7` ⇒ 全部命中 `game/src/battle_runtime_scene.cpp`
    （`#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_page_N.h"` +
    `bn::regular_bg_items::scenario_41_postbattle_dialogue_page_N`）
  * **33 个零引用**（= 任务书说的 33 张）：`..._{1..11}_{top,middle,bottom}`
    ⇒ **grep 全仓 0 命中**（每个 stem 的 `reference_count = 0`，证据在 JSON 的 `reference_evidence` 里）

清单（**每个 stem 一个 `.bmp` + 一个 `.json` = 66 个文件**）：

```
scenario_41_postbattle_dialogue_1_top      scenario_41_postbattle_dialogue_1_middle    scenario_41_postbattle_dialogue_1_bottom
scenario_41_postbattle_dialogue_2_top      scenario_41_postbattle_dialogue_2_middle    scenario_41_postbattle_dialogue_2_bottom
scenario_41_postbattle_dialogue_3_top      scenario_41_postbattle_dialogue_3_middle    scenario_41_postbattle_dialogue_3_bottom
scenario_41_postbattle_dialogue_4_top      scenario_41_postbattle_dialogue_4_middle    scenario_41_postbattle_dialogue_4_bottom
scenario_41_postbattle_dialogue_5_top      scenario_41_postbattle_dialogue_5_middle    scenario_41_postbattle_dialogue_5_bottom
scenario_41_postbattle_dialogue_6_top      scenario_41_postbattle_dialogue_6_middle    scenario_41_postbattle_dialogue_6_bottom
scenario_41_postbattle_dialogue_7_top      scenario_41_postbattle_dialogue_7_middle    scenario_41_postbattle_dialogue_7_bottom
scenario_41_postbattle_dialogue_8_top      scenario_41_postbattle_dialogue_8_middle    scenario_41_postbattle_dialogue_8_bottom
scenario_41_postbattle_dialogue_9_top      scenario_41_postbattle_dialogue_9_middle    scenario_41_postbattle_dialogue_9_bottom
scenario_41_postbattle_dialogue_10_top     scenario_41_postbattle_dialogue_10_middle   scenario_41_postbattle_dialogue_10_bottom
scenario_41_postbattle_dialogue_11_top     scenario_41_postbattle_dialogue_11_middle   scenario_41_postbattle_dialogue_11_bottom
```

* 清理**只能在共享树里做**（⚠️ 见 §7.2：lane 的 `graphics/` 是指向共享树的符号链接），
  **共享树一个字节都没动**（父代理自行判断后再删）。
  ⇒ **E4 没有实际删除任何文件** —— 计划中的删除被安全层拦下，因为那会打到共享树。

### 5.1 ROM 占用（链接器实测，**不是 ~1 MB**）

lane 构建产出的链接器 map：`build/w20-e4/butano-sequel/build/butano-sequel.map`
（工具 `tools/s49_w20e/sum_rom_footprint.py`，报告 `build/w20-e4/dialogue-asset-rom-footprint.json`）。

| 资产 | 链接进 ROM | `.rodata`+`.data` 字节 |
|---|---|---:|
| **33 个无人引用的旧对白** | **33/33 全部被链接**（不是死代码） | **264,768**（≈ 259 KB） |
| 7 个被引用的 `..._page_1..7` | 7/7 | 132,992 |

* 单个资产的典型大小：`_bottom` = `0x4300`（17,152）、`_middle` = `0x0a40`（2,624）、
  `_top` = `0x1280`–`0x1600`（4,736–5,632）。
* ⇒ **实际可回收 ≈ 259 KB，不是任务书说的 ~1 MB**（旧资产是 256×160 對白屏的**三层切片**，
  不是 11 张 256×256 整图 ⇒ 差了约 4 倍）。
* ⚠️ 此数字来自**链接器的 section 大小**（可回收量的直接证据），**未做「删完重建」的第二轮实测**。

---

## 6. 未完成项 / 接线请求

### 6.1 🔴 最高优先级：种子数据**已经在产品里**，684 px 的根因在别处

| 环节 | 现状 | 证据 |
|---|---|---|
| 阵型种子 | ✅ **已在产品里** | `generated_battle_scenario_content.h`（两棵树 sha256 都是 `b5c031ad…`）：battle 14 的 5 个敌人 = **50**；全表 **229** 个非零 `battle_experience` |
| 写入 `carried_experience` | ✅ 已实现 | `battle_scenario_loader.h:465` `unit.carried_experience = static_cast<int>(slot.battle_experience);` |
| 击倒转移 | ✅ 已实现 | `battle_action_system.h:2327-2333` |
| 結算口径 | ✅ 已实现 | `battle_results.h:369-395` `_battle_experience()` = Σ同角色 carried + 被动百分比 |
| 链路的自测 | ✅ 断言通过 | 产品自带 `game/tests/test_battle_experience_flow.cpp`：加载后 `unit(2)->carried_experience == 50`；一次致命攻击后 `unit(1)->carried_experience == 50`、`unit(2) == 0` |

⇒ **重跑生成器不会有任何变化**（产物已是最新），**E2 的「补种子数据」这条路是空的**。
⇒ 684 px 的三个候选根因（按可能性排序，**留给 E1/E2**）：

1. **結算屏那一行根本没接 `_battle_experience()`**（或接到了另一个字段/另一个单位集合）——
   最可能：`_battle_experience()` 会按 `unit->character_id == passive_source.character_id` 过滤，
   如果結算屏传进去的 `passive_source` 角色对不上，就恒为 0。
2. **結算取的是战前快照**（kills 发生前算的），所以 carried 全是 0。
3. **`experience_recipient` 不是玩家单位**（例如 AI 行动时 recipient 取错），转移没落到玩家身上。
   ⇒ 验证入口：`battle_results.h` 里 `_battle_experience()` 的调用点 + `battle_scene_results` 的组装处。

### 6.2 其它未完成项

* **U-2**：场景 46 的 `59`（vs Lua 期望的 `60`）尚未闭合 —— 需要确认是
  「原版确实有 value_a = −2 的 0x15 被动」还是「某个截断/抄写误差」。
  **E2 接线时不要把场景 46 的結算值硬编码成 60/60/30（合计 185/185/155）。**
* **U-3**：种子数据只覆盖 **battle_id 0..46**（group 47 在 ROM 里存在但没有对应地图，未被使用）。
* **U-4**：被动 `value_a` 的来源（哪个角色 / 哪个等级 / 哪个被动槽）尚未定位。
* **U-5**：variant 2 的种子与 variant 0 不同（更高）；重制侧目前只用 variant 0，
  但 `battle_campaign_route.h` 的 `variant` 字段是可配的，接线时要留意。
* **U-6（资产清理）**：lane 副本的 `butano-sequel/graphics` 与 `butano-sequel/audio`
  都是**指向共享树的符号链接** ⇒ **在 lane 里删 = 在共享树删**。
  ⇒ 要在 lane 里安全实测，必须先把这一个目录**换成真实目录**（1852 个文件，慢），
  否则**只能在共享树里删**（父代理决定）。E4 没有删任何文件。

---

## 7. 更正与追加证据（2026-10-25 21:50）

### 7.1 🔴 种子数据本来就在产品里 —— 回收报告与任务书的这个前提是错的

* 回收报告 `notes/s49-fidelity/W20-RECOVER-lanes.md:212` 写：
  「9 个有效 slot 的 `battle_experience` 字段**全是 0**」；
  父代理任务书也据此把 E4 定义成「补种子数据」。
* **实测（`tools/s49_w20e/compare_trees_experience.py` + `verify_slot_mapping.py`）**：
  * 共享树与 lane 副本的 `generated_battle_scenario_content.h` **逐字节相同**
    （913,522 B，sha256 `b5c031ad9d7ee8318e576cfe37761e321bcfa1023566aaf27cdee98834fa1afc`），
    且**git 里没有未提交改动**（`git status --porcelain` 对该文件为空）。
  * 解析全部 **1692 个槽位**：`selector / side / x / y / battle_experience`
    **与 ROM 提取结果 0 处不符**。
  * **非零 `battle_experience` 共 229 个**；battle 14 v0 的 5 个敌人 = 50、battle 41 的敌人 = 50、
    battle 43 的 3 个敌人 = 10、battle 13 v0 = 75、battle 9 v0 = 30。
  * ⇒ 回收报告那句「全是 0」**与盘上的文件矛盾**（很可能是早期版本或误读了 `_index`/槽位）。
* 结论：**种子不是缺口**。684 px 的根因在 §6.1 的三条候选里。

### 7.2 lane 副本的 `graphics/` / `audio/` 是符号链接（不是真实目录）

```
D:\Github\gba-naruto\build\w20-e4\butano-sequel\audio      -> D:\Shell\Github\gba-naruto-butano\butano-sequel\audio
D:\Github\gba-naruto\build\w20-e4\butano-sequel\graphics   -> D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics
```

* ⚠️ 简报 §1 说「`third_party/` 是真实目录不是符号链接」——**但 `graphics/` 和 `audio/` 是符号链接**。
* ⇒ **E4 在 lane 里执行删除时被 `mavis-trash` 拒绝**（它检测到路径经过 junction，
  会打到共享树）。**拒绝是对的**，E4 因此**没有删除任何文件**。
* ⇒ 父代理要删这 33 个资产，只能**直接在共享树里删**（或先把 lane 的 `graphics/` 换成真实目录再删）。
* ⇒ **共享树目前完好**：33 个 `.bmp` + 33 个 `.json` 一个都没少（清单与 sha256 在
  `build/w20-e4/dialogue-asset-cleanup-manifest.json`）。

### 7.3 ROM 占用实测

* lane 基线构建：**成功**（`build/w20-e4/butano-sequel/butano-sequel.gba`，
  12,257,620 B，sha256 `2B2D5945D5EE31FD064A6FAAC27D587C33949CC4EBBBCECA2C06529C18F1F6B2`）。
* 链接器 map 显示 **33/33 旧资产全部被链接**（不是死代码，链接器不会自动丢弃），
  `.rodata`+`.data` 合计 **264,768 B**；7 个 `page_N` 合计 132,992 B。
* ⇒ **可回收 ≈ 259 KB**，任务书的「~1 MB」高估了约 4 倍。

### 7.4 交付物清单（E4）

| 路径 | 内容 |
|---|---|
| `notes/s49-fidelity/W20-E4-reverse-forensics.md` | 本文件 |
| `build/w20-e4/enemy-battle-experience.json` | **47 场景 × 3 变体 × 12 单位 = 1692 条**种子数据（机器可读） |
| `build/w20-e4/formation-matrix.csv` | 1728 行扁平表 |
| `build/w20-e4/unused-dialogue-assets.json` | 33 个零引用 stem + 逐 stem 引用证据 |
| `build/w20-e4/dialogue-asset-cleanup-manifest.json` | 66 个待删文件的 size + sha256 |
| `build/w20-e4/dialogue-asset-rom-footprint.json` | 链接器实测 ROM 占用 |
| `tools/s49_w20e/extract_enemy_battle_experience.py` | 主提取器（ROM → JSON/CSV） |
| `tools/s49_w20e/probe_bank_vs_rom.py` | bank.json vs ROM 字节对账 |
| `tools/s49_w20e/verify_slot_mapping.py` | 产物 vs ROM 的 1692 槽位一致性 |
| `tools/s49_w20e/compare_trees_experience.py` | 共享树 vs lane 的种子字段对比 |
| `tools/s49_w20e/survey_seeds.py` | 全矩阵种子值集合统计 |
| `tools/s49_w20e/show_variants.py` | 逐 battle/variant 明细表 |
| `tools/s49_w20e/scan_unused_dialogue_assets.py` | 旧对白资产引用扫描 |
| `tools/s49_w20e/make_cleanup_manifest.py` | 清理清单生成 |
| `tools/s49_w20e/sum_rom_footprint.py` | 链接器 map → ROM 占用 |
| `tools/s49_w20e/emit_rm_command.py` | 生成 mavis-trash 目标行 |

> ⚠️ `tools/s49_w20e/` 里另有 **6 个上一波 E4 截断续作留下的脚本**
> （`camera_delta.py` / `capture_io_regs.py` / `residual_cause.py` / `rom_struct_xref.py` /
> `shift_probe.py` / `ss9_wram.py`）—— **不是本次产出**，本次只新增上表列出的 10 个。
