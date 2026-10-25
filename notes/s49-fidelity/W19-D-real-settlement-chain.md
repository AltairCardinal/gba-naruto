# W19-D —— 真实战斗打完仗后的结算链：采集、逐屏对照、684 px 根因

> 流：D（驾驶/仪器侧）· wave 19 · 2026-10-25
> 上游：`notes/s49-fidelity/WAVE19-TASKS.md` §4 · `U4-real-victory-verify.md` §2.2/§2.3 ·
> `V1-real-victory.md` · `notes/s49-fidelity/W18-W1-stack-overflow.md`（D4 已闭合）
> 独占：`tools/s49_w19d/**`（新仪器）· 本文件
> ⛔ **重制线零改动**（`D:\Shell\Github\gba-naruto-butano\**` 全程只读）；
> **逆向线只读**；**未提交 git**；**未覆盖共享的 `build/mgba-probe/mgba-probe.exe`**
> （用的是私有副本 `build/w19-d/probe/mgba-probe.exe`，sha `c4a34cd4…`）。

---

## 0. 一句话结论

**「真打赢仗」成立，但「打完仗再走结算链」走不完** ——

1. ⭐ **真实胜利已达成**（D4 修好的直接证据）：
   `from_real_battle: true`、`poke_commands: 0`、`bee_hp_dropped: true`、
   `outcome: 1`、`escort_alive: true`（ROM sha `db676a63…`）。
2. ⭐⭐ **但结算链只录到 1 页就死了**：真实战斗一结束，**Butano 的调色板分配失败**
   （`BPP4 palette create failed. Colors count: 32 / There are no more available colors.`）
   ⇒ 游戏停在 Butano 错误屏、**相位冻结在 13（outcome）** ⇒
   「勝利 / 結算 / 6 張升級屏 / 忍具一覽 / 戰後對白 / 任務菜單」**一段都进不去**。
   ⇒ **D-2 的「真实链逐屏差表」在本 ROM 上不可得**（链条根本没开始）；
   本流给出的是**分列**的「真实链（1 页，错误屏）」+「工具自检链（48 页）」两张表。
3. ⭐ **684 px 的根因查清了**（与真值逐像素对齐后精确复现）：
   那 684 px **全部**是結算屏的**四行数值区**（y 104–160），
   差异只在**第二行「戰鬥分」**（原版 100/150/0 vs 重制侧 0/0/0 ⇒ 合計 300/350/200 vs 200/200/200）。
   根因：**重制侧从来不给「击倒敌人」发战鬥分** ——
   `carried_experience` 全工程只有两个写点（场景种子 + 阵亡时的**零和**转移），
   **没有任何「击倒 ⇒ 获得战鬥分」的规则** ⇒ 真实战斗里它必然还是 0。
   ⇒ **这不是工具自检链的假象，是产品缺口**（代码行 + 修法见 §5）。

---

## 1. 产物与 ROM 绑定

| 项 | 值 |
|---|---|
| 测量的 ROM | `D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba` |
| **ROM sha256** | **`db676a638acd15d07b66f447750a873ee98ae32fa5bf5cedc0c20ecb9fd69438`** |
| 钉住的副本 | `build/w19-d/rom-pinned.gba`（sha 同上） |
| 私有探针 | `build/w19-d/probe/mgba-probe.exe`（sha `c4a34cd47bac3a56ddaa3b1c3cfdb4a809e926477fd3209e6aed1450ccf713e4`，**共享那个没动**） |
| 原版真值目录 | `build/s49-victory-capture/w4/settlement-truth/` |
| **真值收据 sha256** | **`9a60a89bc1330773080e7416a420254bde2c23cb647bd1adfc5c7324a89769aa`**（= 任务书给的 `9a60a89b…`） |
| 真值 ROM | `D:\Shell\gba-naruto-butano\rom\base.gba` sha `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b` |

> ⚠️ 本机构建非字节可复现 ⇒ **本笔记的每一个数字都绑定上面那个 sha**。

### 新工具（`tools/s49_w19d/`）

| 文件 | 作用 |
|---|---|
| `w19d_real_chain.py` | ⭐ 录**两条**链并**分列**归档：①「真实战斗链」（只按键，`v1_battle.py` 不带 `--poke-settlement`）②「工具自检链」（`--poke-settlement`）；同一 ROM、同一探针 ⇒ 直接可比。顺带抽 Butano 的调色板状态（stderr 里的 `log_status()`）。收据 `build/w19-d/chain/w19d-chain.json`。 |
| `w19d_diff.py` | ⭐ 逐屏对照：sha256 优先配对 + 相位顺序兜底（相位顺序**从真值收据自己的文件顺序推导**，不写死表），逐屏给 差 px / 差 bbox / 行带分解，并把結算屏残差**劈成「肖像带 / 数值带」**；另附**升級屏独立复核**块。 |

> 只读调用：`tools/s49_battle_balance/v1_battle.py`、`tools/s49_battle_balance/v1_compare.py`
> （后者仅作交叉验证，差表以 `w19d_diff.py` 的独立实现为准）。

---

## 2. D-1 —— 真实链的收据（`from_real_battle: true`）

`build/w19-d/chain/w19d-chain.json` → `real_chain` 块（ROM `db676a63…`）：

```
kind                real battle (buttons only)
from_real_battle    True
poke_commands       0
bee_hp_dropped      True
outcome             1          (胜利)
escort_hp_start/end 40 / 40   (escort_alive = True)
battle_decided      True
round               13
frames_run          60518
keys_pressed        669
chain pages         1
chain phases        ['outcome']
chain final         outcome      ← 相位冻结在 13
butano error        True
```

蜂的 HP：`25/25 ×5 → 0/0/0/0/0`（**5 只全灭**，各掉 25 HP）。

⇒ **D4 确实闭合了**：玩家的攻击真打中了（`bee_hp_dropped`），结局由产品代码判定（`outcome=1`），
**没有 poke 过一个字节**（`poke_commands: 0`）。
**这是 wave 17/18 的 1:1 报告里一直缺的那份「真实战斗链」证据。**

---

## 3. ⭐⭐ 新发现：真实链被 **Butano 调色板预算**挡住（链一段都进不去）

### 3.1 现象

真实链的第 1 页（`build/w19-d/run-a/shots/page-000-outcome.png`）**不是勝利屏**，
而是 Butano 的错误屏：

```
ERROR in bn_palettes_bank.cpp.h
create_bpp_4:176
BPP4 palette create failed. Colors count: 32
There are no more available colors.
Palettes manager status has been logged.
```

它是「结局相位」的**第一帧**，也就是**结算链的第一段还没画出来**就炸了。
⇒ 之后按 A / B / Right / Down / Left / Up 共 6 次按键，**相位始终停在 13（outcome）**。

### 3.2 ⭐ A/B 对照（同一 ROM、同一探针）—— 证明是「真实战斗的状态」造成的

| 跑法 | 收据 | 链 | Butano 错误 |
|---|---|---|---|
| **真实战斗**（`--use-tools`，胜利） | `from_real_battle: true`、`poke_commands: 0` | **1 页**，final `outcome` | ✅ **有** |
| **真实战斗**（默认不用忍具，败北） | `bee_hp_dropped: true`、`outcome: 2` | **1 页**，final `outcome` | ✅ **有** |
| **工具自检链**（`--poke-settlement`） | `poke_commands: 35`、`from_real_battle: false` | **48 页**，6 个相位全走完，final `task_menu` | ❌ **无** |

⇒ **不是忍具的问题**（用不用忍具都一样炸），**也不是胜负的问题**；
⇒ **是「真打过一场」之后调色板预算被吃光** —— poke 进链时战斗没跑过，预算还有余。

### 3.3 ⭐ Butano 侧的硬证据（探针 stderr 里 Butano 自己打的调色板状态）

只有**失败**的两跑才有这段（`log_status()` 只在失败分支被调用）：

```
[mgba] palettes: 16
[mgba] [
[mgba] bpp_8 - slot_index: 0 - slots_count: 16 - colors_count: 256 - usages: 1
[mgba] ]
```

读法（Butano `third_party/butano/butano/src/bn_palettes_bank.cpp.h`）：

* `hw::palettes::count() == 16`，`colors_per_palette() == 16`
  ⇒ 调色板 bank 一共 **16 槽 × 16 色 = 256 色**；
* `create_bpp_4()`（同文件 **133–186 行**）从槽 15 往下找**连续**的空闲槽，
  `required_slots_count = colors_count / 16`；
  **32 色 ⇒ 需要 2 个连续空槽**；找不到就 `BN_ERROR`（**176 行**）⇒ **致命**；
* 上面那段状态说明：**失败时整个 bank 里只剩 1 个调色板**
  —— 一个 **8bpp、256 色、占满 16 槽**的调色板（`slot_index 0 / slots_count 16 / usages 1`）
  ⇒ **4bpp 区（槽 16..15）一个空槽都没有** ⇒ 32 色的 4bpp 调色板**必然创建失败**。

### 3.4 ⭐ 根因代码行（重制线，只读定位）

| 资产 | 格式 | 需要的槽数 |
|---|---|---|
| `bn::regular_bg_items::scenario_41_victory_bg`（勝利屏背景） | tiles **BPP_8** + 调色板 **256 色** | **16 槽（整个 BG bank）** |
| `bn::regular_bg_items::battle_duel_forest`（战斗森林背景） | tiles **BPP_4** + 调色板 **32 色** | **2 槽** ← 失败的那次请求 |

| 位置 | 代码 | 说明 |
|---|---|---|
| `game/src/battle_runtime_scene.cpp:1605-1624` | `_add_victory_background()` → `bn::regular_bg_items::scenario_41_victory_bg.create_bg(8, 48)` | 创建**吃满 16 槽**的 8bpp 勝利屏背景，**没有先释放 4bpp 的战斗/决斗背景** |
| `game/src/battle_runtime_scene.cpp:5516-5526` | `_release_background_before_bpp_transition()` | **已有的正确做法**：`_duel_hud_background.reset(); map.reset(); bn::core::update();`（注释里就写着「BPP8 palettes require the full BG palette bank」） |
| `game/src/battle_runtime_scene.cpp:5528-5545` | `_bind_duel_background()` → `battle_duel_forest.create_bg(8, 80)`（**4bpp / 32 色**） | 创建 4bpp 森林背景；它会先调 `_release_background_before_bpp_transition()`，**但那只释放 map，不释放勝利屏背景** |
| `game/src/battle_runtime_scene.cpp:9296-9299` | `update_victory_background(state.phase == outcome)` | 结局相位每帧创建勝利屏背景；注释写「the settlement screen's own layer needs the background palette」——**作者知道预算有限，但释放顺序没对** |
| `game/src/battle_runtime_scene.cpp:1364-1388` | UI 层分派：`result` 相位 → `_add_result_background()`；`outcome` 相位 → `_add_victory_background()` | 結算屏的底板 `battle_ui_result_plate`（**8bpp / 32 色**）也是 2 槽 |

⇒ **两个屏幕尺寸的背景（8bpp 256 色 与 4bpp 32 色）必须同时活在同一个 BG 调色板 bank 里，
而 bank 只有 16 槽** ⇒ 后创建的那个必炸。

**先后顺序由测量确定**：失败时 bank 里**只剩那个 8bpp/256 色的调色板**（`slot_index 0 /
slots_count 16 / usages 1`）⇒ **4bpp/32 色的那次请求是后到的** ⇒
「勝利屏背景（8bpp/256 色，占满 16 槽）」先建好，
「战斗/决斗森林背景（4bpp/32 色，要 2 槽）」后建 ⇒ **后者的
`create_bpp_4` 必然 `BN_ERROR`**。
（重制线自己的注释 `battle_runtime_scene.cpp:9296-9297`
「the settlement screen's own layer needs the background palette」说明作者已知预算有限。）

---

## 4. D-2 —— 整链逐屏差表（**两条链分列**）

### 4.1 ⛔ 真实链（真实战斗打完仗）—— **只有 1 页**

| 重制页 | 相位 | 原版真值 | 差 px | 差 bbox |
|---|---|---|---:|---|
| `page-000-outcome.png` | outcome | `01-victory.png` | **37 441** | `[0,0,240,160]` |

> 这 37 441 px **不是产品残差**：这一帧是 **Butano 错误屏**，结算链根本没开始。
> （⇒ 真实链的「7 段」在本 ROM 上**不可得**；这是 §3 的产品缺陷，不是仪器缺陷。）

### 4.2 ✅ 工具自检链（poked，48 页）—— 同一 ROM 的对照基线

配对方式：sha256 优先，配不上的按相位顺序（相位顺序**由真值收据的文件顺序推导**）。

| 重制页 | 相位 | 原版真值 | 原版 sha256（前 16） | 重制侧 sha256（前 16） | 差 px | 差 bbox |
|---|---|---|---|---|---:|---|
| `page-000-outcome.png` | outcome | `01-victory.png` | `d60a1d35e45736db` | `d60a1d35e45736db` | **0** | — |
| `page-001-result.png` | result | `02-settlement-exp-power-turns.png` | `e34e116c7ed3a55e` | `337661386808ba99` | **2 582** | `[84,49,236,154]` |
| `page-002-level_up.png` | level_up | `03-levelup-naruto.png` | `a876f32dbe100a65` | `a876f32dbe100a65` | **0** | — |
| `page-003-level_up.png` | level_up | `05-levelup-sasuke-jutsu-name.png` | `daac884a6415577b` | `daac884a6415577b` | **0** | — |
| `page-004-level_up.png` | level_up | `04-levelup-konohamaru.png` | `ef0808aea763ff31` | `ef0808aea763ff31` | **0** | — |
| `page-005-level_up.png` | level_up | `05-levelup-sasuke.png` | `c5a8440b451ef6a1` | `c5a8440b451ef6a1` | **0** | — |
| `page-006-level_up.png` | level_up | `06-levelup-sakura.png` | `a0db87e9fd8ec358` | `a0db87e9fd8ec358` | **0** | — |
| `page-007-level_up.png` | level_up | `07-ninja-tool-list.png` | `455acc43c9ace553` | `455acc43c9ace553` | **0** | — |
| `page-008…013-training.png` ×6 | training | **真值无对应帧** | — | — | — | — |
| `page-014-post_battle_dialogue.png` | post_battle_dialogue | `08-postbattle-dialogue-1.png` | `2741dbc3fbf6e838` | `5fece4f6952f78b0` | **26 819** | `[0,0,240,160]` |
| `page-015…020-post_battle_dialogue.png` ×6 | post_battle_dialogue | 真值只有 1 帧 | — | — | — | — |
| `page-021-task_menu.png` | task_menu | `09-task-menu-map.png` | `cda07a18be60a1ea` | `3814df2825813f89` | **37 694** | `[0,0,240,160]` |
| `page-022…047-task_menu.png` ×26 | task_menu | 真值只有 1 帧 | — | — | — | — |

> ✅ **与 U4 §2.3 的数字逐项相同** ⇒ 仪器一致。
> ⚠️ **这一张表是「工具自检链」，不是「真实战斗链」** —— 真实链被 §3 挡住，只录到 1 页错误屏。
> 26 819 / 37 694 两项归 **B 路**（`battle_result_content.h` / `battle_presentation_content.h` / `battle_ui_model.h`）。

### 4.3 結算屏残差的**行带分解**（2 582 px 的归属，可复核）

`w19d_diff.py --remake build/w19-d/run-poked/shots` → `screens[].row_bands`：

| 行带 | 差 px | 归属 |
|---|---:|---|
| y 48–56 | 186 | 肖像 |
| y 56–64 | 258 | 肖像 |
| y 64–72 | 345 | 肖像 |
| y 72–80 | 385 | 肖像 |
| y 80–88 | 455 | 肖像 |
| y 88–96 | 259 | 肖像 |
| y 96–104 | 10 | 肖像 |
| **y 0–104 小计** | **1 898** | **三张人物立绘**（归 B 路） |
| y 104–112 | 229 | 数值 |
| y 112–120 | 24 | 数值 |
| y 120–128 | 137 | 数值 |
| y 128–136 | 24 | 数值 |
| y 136–144 | 122 | 数值 |
| y 144–152 | 143 | 数值 |
| y 152–160 | 5 | 数值 |
| **y 104–160 小计** | **684** | **四行数值区**（本流 D-3 的对象） |

⇒ **2 582 = 1 898（立绘） + 684（数值）** —— 与任务书给的口径**逐像素吻合**。

---

## 5. ⭐ D-3 —— 684 px 的根因（真实战果数值为什么是 0/0/0）

### 5.1 数值区逐字读数（真值 8× 放大 vs 重制侧 5× 放大，文件见 `build/w19-d/`）

原版 `02-settlement-exp-power-turns.png` 的行标题（放大后逐字读）：
**經驗分 / 戰鬥分 / 回合分 / 合計**（合計是红字）。

| | 經驗分 | **戰鬥分** | 回合分 | 合計 |
|---|---|---|---|---|
| **原版 鸣人** | 125 | **100** | 75 | **300** |
| **原版 佐助** | 125 | **150** | 75 | **350** |
| **原版 小樱** | 125 | **0** | 75 | **200** |
| **重制侧 三人** | 125 | **0** | 75 | **200** |

⇒ **只有「戰鬥分」这一行不同**；經驗分 125 与 回合分 75 **逐像素相同**；
合計随之变成 200/200/200（原版 300/350/200）⇒ **684 px 全部来自这一行 + 合计行的联动**。

### 5.2 ⭐ 运行时读数（不是猜的）

工具自检链的結算屏那一页的 ROM 遥测（`build/w19-d/run-poked/battle.json`）：

```json
{"file": "page-001-result.png", "phase": 14, "phase_name": "result",
 "outcome": 1, "result_participant_count": 3, "result_total_experience": 200}
```

⇒ **产品自己算出来的合計就是 200 = 125 + 0 + 75** ⇒ 「戰鬥分 = 0」是**产品算出来的**，
不是画面画错的。

### 5.3 ⭐ 根因代码行（重制线，只读定位）

`battle_result_participant::battle_experience`（**就是「戰鬥分」那一行**）的来源：

| 位置 | 代码 | 作用 |
|---|---|---|
| `game/include/konoha/battle_results.h:244-252` | `participant.battle_experience = policy.award_battle_experience ? _battle_experience(session, *unit) : 0;` | 取值入口 |
| `game/include/konoha/battle_results.h:369-395` | `_battle_experience()`：`result += unit->carried_experience;` | **戰鬥分 = 该角色所有单位的 `carried_experience` 之和** |
| `game/include/konoha/battle_action_system.h:2315-2338` | `experience_recipient.carried_experience += target.carried_experience; target.carried_experience = 0;` | **唯一**的「获得」路径：**阵亡时把死者身上的战鬥分零和转移给击杀者** |
| `game/include/konoha/battle_scenario_loader.h:465-466` | `unit.carried_experience = static_cast<int>(slot.battle_experience);` | **唯一**的「初始值」路径：**场景种子** |

⇒ ⭐ **全工程穷举（`grep carried_experience`，排除测试）只有这 4 处**
（另 2 处在 `game/tests/`）⇒ **没有任何一处给 `carried_experience` 增加值**：

* **没有**「击倒敌人 ⇒ 击杀者获得战鬥分」的规则；
* 阵亡转移是**零和**的（总量不变）；
* 场景种子：生成内容里**没有任何一处**给 `battle_experience` 赋值
  （`battle_scenario_content.h:44` 只有默认值 `= 0`；
  `grep battle_experience` 在 `game/**`（排除 tests）里**不命中任何 generated_*.h**）
  ⇒ **场景 49 / 战斗 14 的所有人战鬥分种子都是 0**。

⇒ ⭐ **推论（可判定）**：真实战斗打死了 5 只蜂，但击倒只做「零和转移」，
而蜂身上的战鬥分种子是 0 ⇒ **真实战斗结束时三名角色的 `carried_experience` 仍然是 0**
⇒ **結算屏「戰鬥分」在真实链里也必然是 0/0/0**。

⇒ ⚠️ **这一条是「代码穷举 + 零和不变量 + 场景种子实测为 0」的推断，不是「真实链的屏幕读数」**
—— 因为真实链被 §3 的调色板错误挡住，**根本画不出那一页**。
但它**不是**「poked 链没有战斗所以是 0」那种假象：poked 链与真实链走的是**同一段**
`battle_result_system::preview()` 代码，差别只在**战鬥分有没有被赚到**，
而重制侧**永远赚不到**。

### 5.4 原版的对照数据（逆向线，只读）

* `D:\Shell\Github\gba-naruto-reverse\notes\scenario-46-entry-runtime-20260719.md:291`
  「胜利结算页显示三名角色**本战经验均为 125**，另列 **59/59/30**，合计显示 **184/184/155**」
  （59+125=184 ✓、30+125=155 ✓）
* `D:\Shell\Github\gba-naruto-reverse\notes\scenario-47-entry-runtime-20260720.md:138`
  「结算经验页显示三人**本战基础经验均为 125**」
* 本波真值（战斗 14，`turn4-two-kills` 恢复点）：經驗分 125 / 戰鬥分 **100/150/0** / 回合分 75 / 合計 300/350/200

⇒ **注意**：场景 46 是**捕获**五只猫（没有击倒），戰鬥分却是 59/59/30
⇒ 「戰鬥分」**不是**单纯的「击倒数 × 固定值」，原版的算法更细
⇒ ⚠️ **修法需要原版的战鬥分公式表**，这是逆向线/B 路的活，本流不猜。

### 5.5 修法（**接线请求**，本流不改产品代码）

> **接线请求 D-1（戰鬥分规则缺口）**
> **文件**：`game/include/konoha/battle_action_system.h`（战斗结算/伤害判定处）
> **位置**：`battle_action_system.h:2315-2338`（`if(! target.active) { … defeated … }` 段）
> **改成什么**：在**敌人被击倒**的判定里补上**原版的战鬥分发放规则**
> ——即被击倒者应当**带着它自己累计的战鬥分**被转移（现在的转移代码 `2330-2332` 已经有了，
> 缺的是「战鬥分在战斗中是怎么被赚到并挂到单位身上」的那条规则）。
> 参照 `game/tests/test_battle_experience_flow.cpp`（第 18–19、42–43 行）已写明的语义：
> 场景给单位播种战鬥分（`carried_experience`），单位被击倒时该数值转移给击杀者。
> **为什么**：結算屏第 2 行「戰鬥分」= `battle_result_system::_battle_experience()`
> = Σ `unit->carried_experience`（`battle_results.h:369-395`）；
> 现在这个值**永远是 0** ⇒ 結算屏 684 px + 合計 200/200/200。
> **前置**：需要原版的战鬥分公式（逆向线：`notes/scenario-46-entry-runtime-20260719.md:291`
> 的 59/59/30 与本波真值的 100/150/0 是两个锚点）；**不能拍脑袋写常数**。
>
> **接线请求 D-2（调色板预算，挡住真实链）**
> **文件**：`game/src/battle_runtime_scene.cpp`（**A 路独占**）
> **位置**：`1605-1624` `_add_victory_background()` 与 `5528-5545` `_bind_duel_background()`
> **改成什么**：让 **8bpp 256 色的勝利屏背景** 与 **4bpp 32 色的决斗森林背景**
> **永不同时活着**，并且在「释放旧的」与「创建新的」之间插入 `bn::core::update()`
> （`_release_background_before_bpp_transition()` 已经这么做了，只是没管到勝利屏背景）。
> 具体：`_add_victory_background()` 在 `create_bg` 之前先
> `_victory_background.reset()` 之外的 map/duel 释放 + `bn::core::update()`；
> `_bind_duel_background()` 在 `create_bg` 之前先 `_victory_background.reset()`。
> **为什么**：`hw::palettes::count()==16`、`colors_per_palette()==16` ⇒ BG 调色板 bank 只有 16 槽；
> 8bpp 256 色要**吃满 16 槽**，4bpp 32 色要 2 槽 ⇒ 后创建者必然
> `BN_ERROR("BPP4 palette create failed. Colors count: 32 …")`（Butano
> `bn_palettes_bank.cpp.h:176`）⇒ **游戏停在错误屏、结算链一段都进不去**。
> **为什么是这两张图（而不是别的）**：测量到的失败请求是 **BPP4 / 32 色**
> ⇒ 全工程唯一的 4bpp/32 色 BG 资产是 `bn::regular_bg_items::battle_duel_forest`
> （`build/bn_regular_bg_items_battle_duel_forest.h`：tiles `BPP_4` + 调色板 32 色）；
> 而失败时 bank 里唯一的那个调色板是 **8bpp / 256 色** ⇒ 唯一的 8bpp/256 色 BG 资产是
> `bn::regular_bg_items::scenario_41_victory_bg`（tiles `BPP_8` + 调色板 256 色）。
> ⇒ **勝利屏背景先建好、决斗森林后建 ⇒ 后者炸**。
> **最可能的时间点**：`update_victory_background(true)`（9298 行）在**结局相位的每一帧**都建
> 勝利屏背景；若此时**战斗演出还没结束**（战斗演出路径会再调 `_bind_duel_background()`，
> 见 5432 / 5784 行），两张屏幕尺寸的背景就会在同一个 bank 里撞车。
> ⇒ 建议加一道闸：**战斗演出没结束前不要建勝利屏背景**（或建之前先释放 4bpp 背景 + `bn::core::update()`）。
> **预期收益**：真实链能走完 ⇒ 本波的「真实链逐屏差表」才可能产出。
> ⚠️ 上面最后一段（时间点）是**推断**；已**实测**的是「失败时 bank 里只有一个
> 8bpp/256 色调色板」+「失败请求是 BPP4/32 色」+「这两个资产是全工程唯一匹配者」
> —— 这三条足以支撑「两张屏幕尺寸背景互相撞车」的结论。

---

## 6. D-4 —— 升級屏 6/6 = 0 px 的**独立复核**（不照抄 U4）

`w19d_diff.py` 的 `level_up_recheck` 块（`build/w19-d/compare-toolcheck.json`）：

| 重制页 | 配到的真值帧 | 配对方式 | 差 px | bbox |
|---|---|---|---:|---|
| `page-002-level_up.png` | `03-levelup-naruto.png` | **sha256** | **0** | — |
| `page-003-level_up.png` | `05-levelup-sasuke-jutsu-name.png` | **sha256** | **0** | — |
| `page-004-level_up.png` | `04-levelup-konohamaru.png` | **sha256** | **0** | — |
| `page-005-level_up.png` | `05-levelup-sasuke.png` | **sha256** | **0** | — |
| `page-006-level_up.png` | `06-levelup-sakura.png` | **sha256** | **0** | — |
| `page-007-level_up.png` | `07-ninja-tool-list.png` | **sha256** | **0** | — |

复核的**判据**（三条同时成立才算通过）：

1. 每一页都用 **sha256** 配到真值帧（不是按文件名猜的）⇒ 字节完全相同；
2. 6 页配到 **6 个互不相同**的真值帧（`distinct_truth_frames = 6`）⇒ 没有两页撞同一张；
3. 差 px 由**本工具自己**从像素算出来 = **0**（`all_zero_pixels = true`）。

`verdict` = 「independent re-check: every level-up page is byte identical to a distinct original frame」

⚠️ **范围声明**：这是**工具自检链**的升級屏（真实链被 §3 挡住，压根没到升級屏）。
⇒ 「升級屏 6/6 = 0 px」在**工具自检链**上**独立复核通过**；
真实链上的同一结论**待 §5 的 D-2 接线请求落地后才能验证**。

---

## 7. 跑了哪些验证（命令 + 关键数字）

| # | 命令 | 关键数字 / 判读 |
|---|---|---|
| **D-1** | `python tools/s49_battle_balance/v1_battle.py --rom build/w19-d/rom-pinned.gba --out build/w19-d/run-a --exe build/w19-d/probe/mgba-probe.exe --truth build/v1/battle-truth.json --boot --use-tools --max-turns 400` | ⭐ `from_real_battle: true`、`poke_commands: 0`、`bee_hp_dropped: true`（5×25）、`outcome: 1`、`escort_alive: true`、round 13、60 518 帧、669 键；**链只录到 1 页**（Butano 错误屏） |
| **D-2** | 同上 `--out build/w19-d/run-poked … --poke-settlement` | 工具自检链：**48 页**，6 个相位全走完，final `task_menu`，`poke_commands: 35`，**无 Butano 错误** |
| **D-3** | 同上 `--out build/w19-d/run-notools … --max-turns 1200`（不用忍具） | `bee_hp_dropped: true`、`outcome: 2`（护送阵亡）、**链 1 页 + 同样的 Butano 错误** ⇒ **与忍具无关、与胜负无关** |
| **D-4** | `python tools/s49_w19d/w19d_diff.py --remake build/w19-d/run-poked/shots --out build/w19-d/compare-toolcheck.json` | 勝利 **0**、結算 **2 582** `[84,49,236,154]`、升級屏 **6/6 = 0**、戰後對白 **26 819**、任務菜單 **37 694**；行带分解 1 898 + 684 |
| **D-5** | `python tools/s49_w19d/w19d_diff.py --remake build/w19-d/run-a/shots --out build/w19-d/compare-real.json` | 真实链唯一一页 vs `01-victory.png` = **37 441 px**（是错误屏，不是残差） |
| **D-6** | `python tools/s49_w19d/w19d_real_chain.py --rom build/w19-d/rom-pinned.gba --exe build/w19-d/probe/mgba-probe.exe --out build/w19-d/chain --max-turns 400` | 一条命令出**两条链的对照收据** `build/w19-d/chain/w19d-chain.json`；含 Butano 调色板状态抽取 |
| **D-7** | 只读 `grep carried_experience` / `grep battle_experience`（`game/**`，排除 tests） | `carried_experience` 的写点**只有** `battle_scenario_loader.h:465` 与 `battle_action_system.h:2330-2332`；`battle_experience`（场景种子）**没有任何生成内容赋值** |
| **D-8** | 只读 `grep` Butano `bn_palettes_bank.cpp.h` | `create_bpp_4` 133–186 行；`BN_ERROR` 176 行；`hw::palettes::count()==16`、`colors_per_palette()==16`（`bn_hw_palettes.h:21-29`） |
| **D-9** | 只读扫描 `butano-sequel/build/bn_*palette*.h` / `bn_regular_bg_items_*` | `scenario_41_victory_bg` = **BPP_8 + 256 色**；`battle_duel_forest` = **BPP_4 + 32 色**；`battle_ui_result_plate` = BPP_8 + 32 色 |
| **D-10** | 只读逆向线 `notes/scenario-46-…md:291` / `notes/scenario-47-…md:138` | 原版「本战经验 125 + 另列 59/59/30 = 184/184/155」 |
| **D-11** | ⭐ `python tools/s49_victory_align/align_settlement.py --truth build/s49-victory-capture/w4/settlement-truth --remake build/w19-d/run-poked/shots --out build/w19-d/align-toolcheck.json`（**只读调用**，独立实现） | ⭐ **交叉验证通过**：勝利 **0 px**、結算 **2 582 px**（bands `[[49,97],[106,153]]`）、升級屏 **6/6 = 0 px** —— 与 `w19d_diff.py` 的数字**逐项相同** ⇒ 两套独立实现互证 |

---

## 8. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **D-1** | D4 修好后能真打赢仗（`from_real_battle`） | `v1_battle.py --use-tools --max-turns 400`，看收据的 `acceptance` 块 | **成立**：`outcome=1`、`bee_hp_dropped`、`poke_commands=0`、`from_real_battle=true` | **已确认** |
| **D-2** | ⭐ 真打赢仗后，结算链能像自检链一样走完 48 页 | 同上，看 `settlement.pages` 与 `final_phase` | **不成立**：只录到 **1 页**，相位冻结在 13；屏幕上��� **Butano 调色板错误屏** | **已证伪** |
| **D-3** | ⭐ 链走不完是**忍具**的锅 | 同一 ROM 不用忍具再跑一场 | **不成立**：不用忍具照样在结局相位炸同一张错误屏 | **已证伪** |
| **D-4** | ⭐ 链走不完是**poke 链特有**的假象 | 同一 ROM 上 poke 链跑满 48 页 | **不成立**：poke 链**正常**走完 ⇒ 差别在「真打过一场」的状态 | **已证伪** |
| **D-5** | ⭐ 调色板错误是「BG 调色板 bank 被 8bpp 背景吃满」 | 读 Butano `create_bpp_4` + 探针 stderr 里 Butano 自己打的 bank 状态 | **成立**：失败时 bank 里只剩 **1 个 8bpp/256 色/16 槽**的调色板 ⇒ 4bpp 区 0 空槽；`battle_duel_forest`（4bpp/32 色）与 `scenario_41_victory_bg`（8bpp/256 色）必有一个失败 | **已确认** |
| **D-6** | ⭐ 結算屏 2 582 px = 1 898（立绘）+ 684（数值） | `w19d_diff.py` 的行带分解 + 数值带/肖像带切分 | **成立**：y 0–104 = 1 898，y 104–160 = 684，合计 2 582 | **已确认** |
| **D-7** | ⭐ 684 px 全部来自「戰鬥分」那一行 | 真值 8× / 重制侧 5× 放大逐字读 + 运行时遥测 `result_total_experience=200` | **成立**：經驗分 125 与 回合分 75 逐像素相同；只有 戰鬥分 100/150/0 vs 0/0/0 ⇒ 合計 300/350/200 vs 200/200/200 | **已确认** |
| **D-8** | ⭐ 「0/0/0」是 poked 链没有战斗造成的假象 | 穷举 `carried_experience` 的全部写点 + 场景种子实测 | **不成立**：写点只有「场景种子」与「阵亡零和转移」；**没有击倒发奖规则**；场景种子实测 0 ⇒ **真实战斗也必然是 0** | **已证伪（是产品缺口）** |
| **D-9** | 升級屏 6/6 = 0 px 是配对错位造出来的假象 | 本工具独立配对（sha256）+ 自算像素差 + 6 页 6 张不同真值帧 | **不成立**：6 页**字节相同**地配到 6 张**互不相同**的真值帧，差 px = 0 | **已证伪（0 px 成立）** |
| **D-10** | 真实链的 7 段差表在当前 ROM 上可产出 | 真实链实跑 | **不成立**：被 D-5 的产品缺陷挡住 ⇒ 需要 D-2 接线请求先落地 | **已证伪（受阻）** |

---

## 9. 限制 / 剩余风险

1. ⛔ **真实链的 7 段逐屏差表在本 ROM 上不可得**（§3）。D-2 的表目前只有
   「真实链 1 页（错误屏）」与「工具自检链 48 页」**两行分列**。
   ⇒ 父代理若落地了接线请求 D-2，**重跑 `w19d_real_chain.py` 即可拿到真表**（命令已写好）。
2. ⚠️ 「真实战斗的戰鬥分也是 0」是**代码穷举 + 零和不变量 + 场景种子实测**的推断，
   **不是**真实链屏幕读数（真实链画不出那一页）。推断链是闭合的，但**没有直接屏幕证据**。
3. ⚠️ 「戰鬥分」的原版公式**未确定**（场景 46 是捕获猫也有 59/59/30 ⇒ 不是「击倒数 × 常数」）。
   本流**不猜**，只给锚点与接线请求。
4. ⚠️ 本波**没有改任何重制线产品文件** ⇒ **单测 pass=118/fail=20 的基线不受影响**（未重跑）。
5. ⚠️ **ROM 会变**（并行流随时会重建共享树）⇒ 本笔记全部数字绑定 sha `db676a63…`；
   `build/w19-d/rom-pinned.gba` 是钉住的副本。
6. ⚠️ 内存纪律：全程**同一时刻只跑 1 路探针**；跑完已检查
   `Get-Process -Name 'mgba-probe'`，**无孤儿进程**。
