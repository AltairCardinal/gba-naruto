# W23-F4 —— 結算屏「同前提 ⇒ 数字逐像素为 0」

> 流：**wave 23 / F4** · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 目标：让重制侧結算屏与原版真值在**同一前提**下**逐像素相同**
> 独占：工具 `tools/s49_w23f4/` · 数据 `build/w23-f4/` · 笔记（本文件）
> ⛔ **未改任何产品文件**；⛔ 未改共享树；逆向线只读；未提交 git

---

## 0. 一句话结论

> ⭐⭐⭐ **走的是 (a) 改驱动器（不是 poke）**：用一个**只改打法、不碰产品**的驱动器策略，
> 把重制侧打到与原版真值**完全相同的前提**（回合数 8 ≤ `round_limit`、击杀归属 **2/3/0**），
> ⇒ **結算屏的 9 个数字格逐像素为 0**（`125/125/125`、`100/150/0`、`75/75/75`、`300/350/200`，
> 与真值逐位相同）。
>
> ⭐⭐ **但「結算屏整屏差 = 0 px」没有达成：985 px → 514 px。**
> 剩下的 514 px **不是数字**，而是 **① 結算屏边框装饰 ② 合計行的红色调色板**，
> 且已用「两条重制链互比」证明它们**与前提无关**（渲染差，不是打法差）。
>
> ⇒ **结论的适用范围**：**985 px 不是单一原因** =
> **471 px 前提差（数字取值）+ 514 px 渲染差（边框 + 合計配色）**；
> **前提差已被证明可以在不改产品的前提下归零**，**渲染差需要产品侧修**（新开放项）。

---

## 1. 前提与基线（来自 D2 / D4 / D5 / W22-PARENT）

| 项 | 原版真值 | 重制真实链（D5 修正驱动器） |
|---|---|---|
| 經驗值 | `125 / 125 / 125` | `125 / 125 / 125` ✅ |
| 戰鬥分 | `100 / 150 / 0` | `50 / 200 / 0` |
| 回合分 | `75 / 75 / 75` | `0 / 0 / 0` |
| 合計 | `300 / 350 / 200` | `50 / 200 / 0` |
| 結算屏差 | — | **985 px**（基线）／936 px（D5 修正驱动器） |

真值前提 = **终局回合数 ≤ 8**（`round_limit = 8`）+ **击杀归属 2 / 3 / 0**（鸣人 2 / 佐助 3 / 小樱 0）。

---

## 2. ⭐ 做法：(a) 改驱动器 —— `tools/s49_w23f4/v1_battle_f4.py`

**产品代码、规则、战斗逻辑一律不动**；只改「驱动器选谁出手、打谁」。

### 2.1 三处策略（D5 补丁之上再加三处）

| # | 改动 | 为什么 |
|---|---|---|
| 1 | **击杀配额** `F4_QUOTA = {鸣人: 2, 佐助: 3, 小樱: 0}` | 战闘分行只由「谁杀了谁」决定 ⇒ 直接把打法约束到真值分布 |
| 2 | **目标分配**（min-max 划分）：开局把 5 只蜂切成「鸣人 2 / 佐助 3」，代价 = 两actor到各自蜂的**最大曼哈顿距离之和**取最小（10 种划分穷举） | 少走冤枉路 ⇒ 回合数可控；规则确定 ⇒ 可复现 |
| 3 | **忍具一次性消费**：忍具一旦**出手**（不是被拒绝）就记入 `used_tools`，不再进入候选 | 产品规则「忍具用一次即清空」；D5 的 `persistent_refused` 只在**被拒绝**后才学，导致同一个忍具被反复重挑（基线里 `tool:1` 用了 2 次） |

配额达成后：该角色**本回合不攻击**（小樱全程 0 杀）。

### 2.2 实测（`build/w23-f4/run/battle.json`）

| 项 | 值 | 真值 |
|---|---:|---:|
| `entry.poke` / `poke_commands` | **false / 0** | （必须是真实链） |
| `acceptance.from_real_battle` | **true** | — |
| `errors` | **`[]`** | — |
| `outcome` | **1** | 1 |
| **回合数** | **8** | ≤ 8 ✅ |
| **击杀归属** | **2 / 3 / 0** | 2 / 3 / 0 ✅ |
| **战闘分** | **`100 / 150 / 0`** | `100 / 150 / 0` ✅ |
| **回合分** | **`75 / 75 / 75`** | `75 / 75 / 75` ✅ |
| 經驗值 | `125 / 125 / 125` | `125 / 125 / 125` ✅ |
| **合計** | **`300 / 350 / 200`** | `300 / 350 / 200` ✅ |

**逐杀明细**（`build/w23-f4/kill-trace-b1.json`）：

| 回合 | 出手 | 战法 | 结果 |
|---:|---|---|---|
| t0 | 鸣人 | `tool:1`（十字手里剑，射程 3） | 杀蜂槽 7 |
| t4 | 佐助 | `active:16`（火遁，射程 2） | 杀蜂槽 8 |
| t6 | 鸣人 | `tool:11`（射程 3） | 杀蜂槽 4 |
| t10 | 佐助 | `active:5`（忍者组合拳，射程 1） | 杀蜂槽 6 |
| t22 | 佐助 | `active:5` | 杀蜂槽 5（**最后一只**） |

* 小樱 23 回合全程不攻击（配额 0）⇒ **0 杀**。
* 护送（木叶丸）40 → 16 HP，存活。

**可复现性**：同参数重跑（`build/w23-f4/run-repeat/battle.json`）⇒
`round=8`、kills `2/3/0`、`assignment`、`used_tools`、`errors=[]` **逐项相同**。

**收据口径的一处修正**：战斗在**最后一回合内**结束 ⇒ 那一回合之后不再有
`select_actor` ⇒ 驾驶员的击杀计数会**漏掉最后一杀**（首版收据里佐助记成 2）。
已在战斗结束后用最终状态对账（`account_kill`），收据现在记 **`kills={1:2, 2:3, 3:0}`**。
（独立工具 `trace_kills.py` 从 roster 快照独立算出的也是 2/3/0 ⇒ 两条独立口径一致。）

---

## 3. ⭐ 对拍结果（`build/w23-f4/align-settlement.json`）

| 屏 | 真值 | 重制 | 差 |
|---|---|---|---:|
| victory | `01-victory.png` | `page-000-outcome.png` | **0 px** |
| **result（結算屏）** | `02-settlement-exp-power-turns.png` | `page-001-result.png` | **514 px**（原 **985 px**） |
| level_up_1..6 | 6 张 | 6 张 | **0 px**（全部） |

⇒ **其余 7 屏仍是逐字节相同**；結算屏 **985 → 514 px（−471 px，−47.7 %）**。

### 3.1 ⭐⭐ 514 px 的成分：**全在数字格之外**

`build/w23-f4/cell-diff.json`：

| 项 | 值 |
|---|---:|
| `total_diff_px` | **514** |
| `diff_row_bands` | `[[106, 153]]` |
| `diff_col_bands` | `[[88, 235]]` |
| 区外差 | **0 px** |

逐行分布：

| 行 | 差 px | 是什么 |
|---|---:|---|
| 106–108 | 92+93+38 = **223** | **上边框装饰**（原版是花纹边框，重制是纯色 + 左上角小方块） |
| 109–138 | 3 / 行 = **90** | 内侧竖线（3 px 宽的边框线） |
| 139–150 | ~17–20 / 行 = **185** | **合計行（红色数字）** |
| 150–153 | 3 / 行 = **11** | 边框线 |

### 3.2 ⭐⭐ 决定性判定：**这 514 px 与前提无关**（渲染差，不是打法差）

把**两条重制链**互比（同一 ROM、同一个产品，只差驱动器）：
`build/w23-f4/cell-diff-vs-d5baseline.json`（F4 链 vs D5 修正驱动链）

| 行带 | F4 vs **原版真值** | F4 vs **D5 链（另一条重制链）** | 结论 |
|---|---:|---:|---|
| **106–108（上边框）** | **223 px** | **0 px** | ⇒ 边框差是**产品渲染差**，与打法无关 |
| 数字/合計行 | 数字 0 px、合計 160 px | 数字有差（前提差） | ⇒ 合計 160 px 也要单独看 |

### 3.3 ⭐ 合計行的 160 px = **红色调色板差**（不是数值差）

`build/w23-f4/numbers/`（两侧数字区裁切，4 倍放大）肉眼：**四个数字完全一致**。

合计行（行 139–150）取色（`tools/s49_w23f4/diff_box.py` + 颜色直方图）：

| 侧 | (231,247,214) 底 | (231,99,66) 浅红 | (231,24,0) 深红 | (231,173,140) 描边 |
|---|---:|---:|---:|---:|
| **原版真值** | 1300 | **160** | **43** | 141 |
| **重制（F4）** | 1300 | **0** | **203** | 141 |

* 红色像素**总数相同（203 = 160 + 43）** ⇒ **字形完全一样**，差的是**配色分层**：
  原版用「浅红 160 px + 深红 43 px」，重制**整行用深红**。
* ⇒ **合計行的数值是对的、字形是对的，差的是原版的双色描边/渐变没有复刻**。

---

## 4. ⭐ 结论（适用范围）

| 结论 | 状态 | 适用范围 |
|---|---|---|
| 「同前提 ⇒ 結算屏的数字格逐像素为 0」 | ✅ **已实测**（真实链、非 poke） | **只适用于 9 个数字格**（4 行 × 3 列的取值） |
| 「結算屏整屏差 = 0 px」 | ⛔ **未达成**（514 px） | 剩下的 514 px 是**边框装饰 + 合計行配色**，**产品侧要修** |
| 「985 px 全部是前提/打法差」 | ⛔ **被本流证伪** | 985 px = **471 px 前提差** + **514 px 渲染差** |
| 「结算规则（归属 / round_limit）与原版一致」 | ✅ 仍成立（D4） | 本流不改任何规则 |

⇒ ⭐⭐ **产品侧不需要为「985 px」改规则**；但**需要为「514 px」改渲染**（新开放项，见 §6）。

---

## 5. 收据清单（`build/w23-f4/`）

| 收据 | 内容 |
|---|---|
| ⭐ `run/battle.json` | **真实链收据**：`poke=false`、`poke_commands=0`、`errors=[]`、`round=8`、`f4_policy.kills={1:2,2:3,3:0}`、`battle_score=[100,150,0]`、`round_score=[75,75,75]` |
| `run-repeat/battle.json` | ⭐ **复跑**：round/kills/assignment/used_tools/errors **逐项相同**（可复现） |
| ⭐ `run-shots` | `run/shots/` 48 页結算链（`page-001-result.png` = 514 px 那张） |
| ⭐ `align-settlement.json` | **逐屏对拍**：8 屏里 7 屏 0 px，結算屏 **514 px**（基线 985 px） |
| ⭐ `cell-diff.json` | 514 px 的行/列分解（行带 `[[106,153]]`、区外 0 px）+ 逐行计数 |
| ⭐ `cell-diff-vs-d5baseline.json` | ⭐ **两条重制链互比**：行 106–108 差 **0 px** ⇒ 边框差与前提无关 |
| ⭐ `box-diff-digits.json` | 数字区框 `[95,110]-[232,152]`：差 **160 px**，bbox 落在行 139–150（合計行配色） |
| `box-diff-numbers-band.json` | 整带框 `[88,106]-[235,154]`：**467 px** |
| `kill-trace-b1.json` | **逐杀归因**（5 杀：鸣人 2 / 佐助 3） |
| `decision-chain-baseline-d5direct.json` | D5 基线的决策链（用于对照） |
| `settlement-truth.png` / `settlement-before-985px.png` / `settlement-before-d5direct-936px.png` / `settlement-after-514px.png` | ⭐ **改前 / 改后結算屏图**（985 px → 936 px → **514 px**） |
| `numbers/numbers-truth.png` / `numbers/numbers-remake.png` | 两侧数字区放大裁切（**数字一致**） |

---

## 6. 接线请求 / 开放项

### R-F4-1（**新开放项，产品侧**）：結算屏的**边框装饰**与**合計行双色红**

* **现象**：原版結算屏的数字框有**花纹上边框**（行 106–108，223 px）与**双色红**的合計行
  （原版：浅红 160 px + 深红 43 px；重制：整行深红），重制侧两者都没有复刻。
* **证据**：`build/w23-f4/cell-diff-vs-d5baseline.json`（**行 106–108 在两条重制链之间差 0 px**
  ⇒ 与打法无关，是产品渲染差）+ `build/w23-f4/numbers/` 的取色对比。
* **需要父代理决策**：这是**资产/调色板**问题（结算屏的 frame 资产 + 合計行的字体配色），
  本流**未改任何产品文件**，也**未定位到具体资产**（时间不够）。

### R-F4-2（**工具，可直接回合**）：驱动器的三处策略

* 文件：`tools/s49_w23f4/v1_battle_f4.py`（本流**独占副本**，未改共享的
  `tools/s49_battle_balance/v1_battle.py`）。
* 三处补丁：**击杀配额** / **min-max 目标分配** / **忍具一次性消费**。
* 建议：**不要**回合到共享的 `v1_battle.py`（它会影响别的流的基线）；
  建议在 `tools/s49_battle_balance/` 下另立一个 `v1_battle_f4.py`，并把
  `f4_policy`（配额 / 击杀 / 战闘分 / 回合分 / 分配）作为**一等公民**写进收据
  （这正是 W22-D2 的 **R-D2-2**）。

### R-F4-3（**收据口径**）：`align_settlement.py` 建议增加「数字区 / 边框区」分账

* 现在的对拍只给一个总差（985 → 514），看不出「数字已对齐、边框没对齐」。
* 建议在 `align_settlement.py` 里加两档口径：**数字格**（行 110–152 × 列 95–232）
  与 **边框**（其余），本流的数据可直接作回归基线（数字 0 px / 边框 514 px）。

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| P-100 | 「同前提下結算屏差 = 0 px」 | 配额策略驱动器打同前提后对拍 | ⛔ **部分证伪**：**数字格 = 0 px**，但整屏 **514 px**（边框 + 合計配色） | **部分确认** |
| P-101 | 「真值前提（2/3/0、≤8 回合）在重制侧真实链上可达」 | 真实链收据（`poke=0`） | ✅ **成立**：round **8**、kills **2/3/0**、`from_real_battle=true` | **已确认** |
| P-102 | 「985 px 全部是前提差」 | 两条重制链互比（行 106–108） | ⛔ **证伪**：行 106–108 在两条重制链之间 **0 px** ⇒ 223 px 是**渲染差** | **已证伪** |
| P-103 | 「剩下的 514 px 仍是数字差」 | 数字区裁切肉眼 + 取色直方图 + `diff_box` bbox | ⛔ **证伪**：四个数字**逐位相同**；160 px 是**合計行双色红**、223+90+11 px 是**边框** | **已证伪** |
| P-104 | 「合計行的差是数值差」 | 取色直方图（红色像素总数 203 = 203） | ⛔ **证伪**：字形相同、**配色分层**不同 | **已证伪** |
| P-105 | 「D5 的 `persistent_refused` 会让同一个忍具被重复使用」 | 基线决策链（`tool:1` 在 t0 与 t3 各用一次） | ✅ **成立** ⇒ F4 加了 `used_tools`（出手即消费） | **已确认** |

---

## 8. 复现

```powershell
# 1) 真实链（配额策略 ⇒ 同前提）
python tools/s49_w20/capture_lock.py --run --label F4 -- python tools/s49_w23f4/v1_battle_f4.py \
  --rom "D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba" \
  --out build/w23-f4/run --boot --max-turns 400 --use-tools \
  --exe build/mgba-probe-w23f4/mgba-probe.exe

# 2) 逐屏对拍
python tools/s49_victory_align/align_settlement.py \
  --truth build/s49-victory-capture/w4/settlement-truth \
  --remake build/w23-f4/run/shots --out build/w23-f4/align-settlement.json

# 3) 差的分解 + 「两条重制链互比」
python tools/s49_w22d2/settlement_cell_diff.py \
  --truth build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png \
  --remake build/w23-f4/run/shots/page-001-result.png --out build/w23-f4/cell-diff.json
python tools/s49_w22d2/settlement_cell_diff.py \
  --truth build/w23-f4/run/shots/page-001-result.png \
  --remake build/w22-d5/run-shared-direct/shots/page-001-result.png \
  --out build/w23-f4/cell-diff-vs-d5baseline.json

# 4) 数字区 / 边框区分账
python tools/s49_w23f4/diff_box.py \
  --a build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png \
  --b build/w23-f4/run/shots/page-001-result.png --box 95 110 232 152 \
  --out build/w23-f4/box-diff-digits.json
python tools/s49_w23f4/crop_numbers.py \
  --truth build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png \
  --remake build/w23-f4/run/shots/page-001-result.png --out-dir build/w23-f4/numbers

# 5) 逐杀归因
python tools/s49_w23f4/trace_kills.py --battle build/w23-f4/run/battle.json \
  --out build/w23-f4/kill-trace-b1.json
```

---

## 9. 未完成项

1. ⛔ **「結算屏整屏差 = 0 px」未达成**（514 px 残留：边框装饰 + 合計行双色红）。
   * **本流未定位到具体产品资产**（结算屏 frame 的资产文件 / 合計行字体的调色板）⇒ 时间不够。
2. ⛔ **未做「(b) poke 造等价局面」的实测**（不需要了：(a) 已成功且是更强的证据）。
3. ⛔ **未在其它 ROM 上复跑**（本流只用共享树 ROM `b97daa81ca4d90ee…`）。
4. ⏳ **未验证 battle 15**（策略只作用于 battle 14 的单位配额；F4_QUOTA 是硬编码的角色 id）。
5. ⏳ **未回合任何共享文件**（`tools/s49_battle_balance/v1_battle.py` 未动；见 R-F4-2）。
6. ℹ️ `build/w23-f4/butano-sequel/` 是父代理给的 lane 副本，本流**未在 lane 里构建**（不需要改产品）。
