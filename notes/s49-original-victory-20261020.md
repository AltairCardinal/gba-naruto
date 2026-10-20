# 原版 S49「打到胜利」录制（2026-10-20）

> 本文件是本轮实测记录。所有结论都带**输入哈希**与**帧证据**；
> 没有复现成功的地方一律写「未复现」+ 阻塞点，不做推测性断言。

## 0. 一句话结论

- **屏③（战后状态页，原版显示 `EXP 100/325` 的那一页）已经录到**，
  并且同一屏的三名队员版本（鸣人 `100/325`、佐助 `35/255`、小樱 `180/225`）都录到了，
  PNG 与按键序列见 §2。
- **屏①（战斗结算页）与屏②（升级画面）本轮没有录到**。阻塞点是**两个硬约束同时卡住**：
  1. **回合上限**：原版奖励记录 battle 14 的 `round_limit = 8`
     （`sequel/content/battle-results/bank.json` record 39：`mission_experience 125`、
     `round_bonus_experience 75`、`round_limit 8`），回合奖励只在 `current_round <= 8` 时发放；
     本轮接手时已在第 4 回合。
  2. **护送单位余量**：木叶丸在第 5 回合的敌方阶段后只剩 **4 HP**
     （蜜蜂全部围到了他旁边），再挨一个敌方阶段就归零 ⇒ 任务失败，连结算页都不会出现。
  ⇒ 下一轮必须**先清掉护送单位旁边的蜜蜂**，而不是先追杀远处的蜜蜂；
     而且每个玩家单位**每回合只有 1 次行动**（详见 §3、§6）。
- 本轮同时把**原版战斗的完整输入契约**测出来了（§3），并用**只读**方式从 savestate 里
  读出单位池/HP/携带经验/阵亡标记（§4）。这两项是下一轮直接复现的输入。

---

## 1. 使用的输入（全部哈希钉死）

| 输入 | SHA-256 | 用途 |
| --- | --- | --- |
| `rom/base.gba` | `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b` | 原版 ROM |
| `artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9` | `a3628723ac595f41b87d329f49d5422a7b9b397a8491379abb8c9620568a0aa1` | battle 14 入口（任务指定的起点） |
| `artifacts/runtime-checkpoints/scenario-49-battle-14-turn4-two-kills.ss9` | `e8b2a5ee0cc4dfbcf89086c8a5fd8fb2bc9e38b9a7bec83cfcb2e3e2a44de350` | 第 4 回合、已 2 杀（canonical 中途点） |
| `artifacts/runtime-checkpoints/scenario-49-battle-14-postbattle-task-menu.ss9` | `8dfca22976fdb741bf8d2521aab8f03e067781c9c2284d003f8bfe6893f76484` | 战后（battle 15 入口），**屏③ 的入口** |
| `build/macos-mgba/build/qt/mGBA.app/Contents/MacOS/mGBA` | `2cc5c36d620d5350c377d1e4fede68726c93b57a7d4e5f98f98fd293eb267393` | 模拟器（0.10.5 + Qt script 回移补丁） |

`rom/base.sav`（SRAM 边车）全程只读，未改动。

---

## 2. 已录到的屏：屏③（战后状态页）

**屏③ = 鸣人的人物信息页**，原版显示 `经验值 100/325`、`体力 152/152`、`查克拉 5/5`，
与仓库既有事实一致（`notes/scenario-49-battle-14-runtime-20260720.md:41-44`：
战后 Naruto `LV5 -> LV6`、体力 `+14`、状态页 `EXP 100/325`、`HP 152/152`）。

| 屏 | 目录 | step | PNG SHA-256 | 画面 |
| --- | --- | --- | --- | --- |
| ③ 战后状态页（鸣人） | `artifacts/s49-original-victory-20261020-v1/p04-naruto-character-info/` | `step-01-A.png` | `ef63bb0e2babf7f81a1a9c623a7aeb6ea202913239a748cf6ba213dfbbb3e26e` | 「人物信息 / 漩涡鸣人 LV 6 / 经验值 100/325 / 体力 152/152±0 / 查克拉 5/5±0 / 忍具数 1/5±0 / 攻击力 19±0 / 防御力 18±0 / 敏捷度 13±0 / 移动力 3±0 / 印 15±0」 |

**通向屏③ 的按键序列**（从 `scenario-49-battle-14-postbattle-task-menu.ss9` 起算，
每一步都是一次独立的 `tools/butano/capture_s49_advance.py` 录制，
`inputs.json`/`steps.json` 都在目录里）：

| 段目录 | `--state` | `--keys` | 屏幕 |
| --- | --- | --- | --- |
| `p01-postbattle-menu/` | `artifacts/runtime-checkpoints/scenario-49-battle-14-postbattle-task-menu.ss9` | `L` | 任务说明页（胜利条件原文，见 §5） |
| `p02-postbattle-next/` | `p01-postbattle-menu/step-01-L.ss9` | `A,A` | 队伍・装备页（鸣人 LV6 体力152 / 佐助 LV6 体力134 / 小樱 LV6 体力125） |
| `p03-naruto-status-exp/` | `p02-postbattle-next/step-02-A.ss9` | `A` | 鸣人的子菜单（人物信息／未列表／装备） |
| `p04-naruto-character-info/` | `p03-naruto-status-exp/step-01-A.ss9` | `A` | **屏③（`EXP 100/325`）** |

**同一次录制的另两名队员状态页**（同一屏的三份实例，重制侧要一起对齐）：

| 屏 | 目录 | step | PNG SHA-256 | 画面读数 |
| --- | --- | --- | --- | --- |
| ③ 之二 佐助 | `artifacts/s49-original-victory-20261020-v1/p07-sasuke-info2/` | `step-03-A.png` | `048b342d00f43c513908abf570976614cc909d55118451d33f4816560736bcfa` | 宇智波佐助 LV6 / 经验值 **35/255** / 体力 134/134 / 查克拉 4/4 / 忍具数 0/5 / 攻17 防13 敏17 移3 印12 |
| ③ 之三 小樱 | `artifacts/s49-original-victory-20261020-v1/p10-sakura-info4/` | `step-04-A.png` | `fee8e4480533a7b05f3f4b09c3bfdeba5a3cbd69599ddd325b932457bf67b967` | 春野樱 LV6 / 经验值 **180/225** / 体力 125/125 / 查克拉 3/3 / 忍具数 0/6 / 攻12 防12 敏15 移3 印6 |

三份读数与 `notes/scenario-49-battle-14-runtime-20260720.md:41-44` 记的
「鸣人 `EXP 100/325` `HP 152/152`、佐助 `LV6/35`、小樱 `LV6/180`」**逐位对上**，
说明这三条链走到的确实是 canonical 战后状态。

其它同源帧（可作为对照）：
`p02-postbattle-next/step-02-A.png` = `5aa1e3783047aa140bb9eeb7ca298941f193deec11f762d6241efb8b54e1c609`（队伍・装备页：鸣人 LV6 体力152 查克拉5 / 佐助 LV6 体力134 查克拉4 / 小樱 LV6 体力125 查克拉3），
`p03-naruto-status-exp/step-01-A.png` = `a7f78cd4fda01289d969a66722344cd520eb937e05238130caef235e94bef919`（鸣人的子菜单），
`p05-sasuke-character-info/step-05-A.png` = `b0d2706749d333393748824439b82ef992a3eb29b1b5b0714a111b2f3178f4e0`，
`p01-postbattle-menu/step-01-L.png` = `3aadee4689b841e777b7b05c2a4ac663897487b86a72778468966cc521742a15`（胜利条件页）。

**选人的按键**：`队伍・装备` 页上用 `Right` / `Right*2` 切到 佐助 / 小樱，
再 `A`（子菜单：人物信息／未列表／装备）、`A`（人物信息）。
`B` 逐层退回。

复现命令（`/usr/local/bin/python3`，`--out-dir` 必须是新目录）：

```sh
cd /Users/altair/github/gba-naruto
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
D=artifacts/s49-original-victory-20261020-v1
/usr/local/bin/python3 tools/butano/capture_s49_advance.py --out-dir $D/p01-postbattle-menu \
  --rom rom/base.gba --state artifacts/runtime-checkpoints/scenario-49-battle-14-postbattle-task-menu.ss9 \
  --keys "L" --zero-input-frames 90 --settle-frames 300 --hold-frames 4
/usr/local/bin/python3 tools/butano/capture_s49_advance.py --out-dir $D/p02-postbattle-next \
  --rom rom/base.gba --state $D/p01-postbattle-menu/step-01-L.ss9 \
  --keys "A,A" --zero-input-frames 90 --settle-frames 300 --hold-frames 4
/usr/local/bin/python3 tools/butano/capture_s49_advance.py --out-dir $D/p03-naruto-status-exp \
  --rom rom/base.gba --state $D/p02-postbattle-next/step-02-A.ss9 \
  --keys "A" --zero-input-frames 90 --settle-frames 300 --hold-frames 4
/usr/local/bin/python3 tools/butano/capture_s49_advance.py --out-dir $D/p04-naruto-character-info \
  --rom rom/base.gba --state $D/p03-naruto-status-exp/step-01-A.ss9 \
  --keys "A" --zero-input-frames 90 --settle-frames 300 --hold-frames 4
```

> 注意：屏①（战斗结算页）与屏②（升级画面）**只出现在战斗结束的那一瞬间**，
> 战后 checkpoint 已经在它们之后（state `+0x16` = 15 = 下一个任务），
> 因此这两屏**无法**从 post-battle checkpoint 回放出来，只能靠真的把 battle 14 打赢。

---

## 3. 原版战斗的完整输入契约（本轮实测，可直接照抄）

所有序列都用 `tools/butano/capture_s49_advance.py` 的 `--keys` 语法
（逗号分隔，`A*3` 表示重复三次）。每条都注明了证据目录。

### 3.1 回合入口 → 命令菜单

| 动作 | 按键 | 说明 | 证据 |
| --- | --- | --- | --- |
| 回合入口（轮到某单位） | 画面是地图，光标在**该单位**上 | 相机跟随当前单位 | `u07-dialog-end/step-02-A.png` |
| 打开命令菜单 | `A` | 光标在友方单位上时按 A | `t20-cursor-back-to-naruto`、`u08-skip-naruto-r5/step-01-A.png` |
| 命令菜单 5 项 | `移動 / 本・忍具 / 查克拉 / 休息 / 行動結束` | **第 3 项是「查克拉」**（补查克拉），不是「查敵拉」 | `t02-turn4-backout/step-01-B.png`（放大截图见本轮临时渲染） |
| 查克拉 | `Down*3`（选中）`A` → 弹「可以嗎?」→ 再 `A` | 查克拉 0 的单位用它补满，**消耗整个回合** | `u02-sasuke-chakra/`、`u03-sasuke-chakra-confirm/` |

### 3.2 攻击（以鸣人的「十字手里剑」为例，本轮实测打中过）

| 步骤 | 按键 | 证据 |
| --- | --- | --- |
| 命令菜单 → 忍法列表 | `Down`（本・忍具）`A` | `p11-sasuke-action-menu3/step-03-A.png`（佐助版），鸣人版 `r08-aim-bee-r2` |
| 选技能 | 忍法列表用 `Down` 移动（鸣人：瞬身术 / 影分身术 / 忍者组合拳 / **十字手里剑**） | 同上 |
| 进入目标选择 | `A` | `r08-aim-bee-r2/step-08-Down.png` |
| 移动光标 | 方向键，每次 1 格（`Left*5` / `Down` 等） | `probe-02`/`r08` |
| 伤害预览 | `A`（出现「損傷 … 成功率 …%」两行） | `r09` 前一帧 `probe-19/step-01-A.png` |
| 「可以嗎?」确认 | `A` | `probe-20/step-01-A.png` |
| 执行攻击 | `A`（播切镜动画） | `probe-21/step-01-A.png`（十字手里剑切镜） |
| 回合结束 | 切镜文字页 `A`（可能 1～2 页）→ 面向方向 `A` → 「使用防禦・回避系的木・忍具嗎?」`A`（选**否**） | `probe-22/step-0{1,2,3}-A.png` |

**关键量纲（全部来自原版画面，不是推测）**：

| 单位 | 技能 | 消耗查克拉 | 攻擊力 | 距離 | 範圍 | 成功率 |
| --- | --- | --- | --- | --- | --- | --- |
| 鸣人 | 瞬身术（瞬移） | 1 | — | 3 | 1 | 100% |
| 鸣人 | 影分身术 | — | — | 2 | 1 | 100% |
| 鸣人 | 忍者组合拳 | — | 10×1 | 1 | 1 | — |
| 鸣人 | **十字手里剑** | — | 6×3 | 3 直 | 1 | 90% |
| 佐助 | **火遁术**（带「連」标记） | 2 | 15×1 | 2 直 | 1 | 95% |
| 佐助 | 瞬身术 | — | — | 3 | 1 | — |
| 佐助 | 忍者组合拳 | — | — | 1 | 1 | — |
| 小樱 | 瞬身术 / 分身术 / 忍者组合拳 | 1 | — | 3 / — / 1 | 1 | 100% |

**实测伤害**：十字手里剑对蜜蜂（攻14/防6 一类）预览 `損傷 27`，**实际只打 18**（6×3）——
`probe-21` → `probe-22/step-01-A.ss9` 的 HP 从 25 → 7 逐位对上。
**预览值不能当击杀证据，必须回读 HP**（与 `notes/scenario-49-battle-14-runtime-20260720.md`
里「预览 27 实际 18」的原记录一致，本轮独立复现）。

### 3.3 敌方阶段 / 回合跳过

| 动作 | 按键 | 说明 |
| --- | --- | --- |
| 敌方阶段 | 用一个**无副作用**的键占位（本轮用 `L`），并把 `--settle-frames` 给到 2400 | 敌方阶段会播移动/攻击动画，时间长；用 `A` 会在光标不在单位上时误开系统菜单（回合菜单） |
| 敌方阶段的反应对白 | 若干次 `A`（页数不固定，本轮见过 2 页、4 页） | 对白结束后若 A 键多按了，会把下一单位的命令菜单也打开 |
| 跳过某单位回合 | `A`（开命令菜单）`Down*4`（行動結束）`A`（可以嗎?）`A`（面向）`A`（忍具問→否）`A`（回合结束） | 9 键；证据 `u01-skip-naruto-canonical/`、`u08-skip-naruto-r5/` |

### 3.4 战斗外（战后）

见 §2 的四段序列。

---

## 4. 只读地读原版战斗状态（不需要跑模拟器）

本轮用 `tools/butano/read_rom_unit_pool.py` 的 savestate 解析器（`tools/inspect_mgba_savestate.py`）
确认了下面的字段偏移。**这是只读观测，不改任何内存**。

单位池：`0x020240C0 + slot*0x1D4`（slot 1..9）：

| 偏移 | 含义 | 证据 |
| --- | --- | --- |
| `+0x00` | 角色 ID，**0 = 该槽已阵亡**（1=鸣人 2=佐助 3=小樱 30=木叶丸 55=蜜蜂） | 入口态 5 只蜜蜂 ID 全为 55；阵亡后归 0 |
| `+0x0C` | 当前 HP | 入口态 = 138/104/110/40/25×5 |
| `+0xC4/+0xC5` | 地图坐标 (x,y) | 入口态鸣人 (11,6)、蜜蜂 (3,4)(4,8)(3,11)(6,6)(5,13) |
| `+0xC1` | 「该单位正在行动/被选中」标记 | 跟随光标移动 |
| `+0xCE` | 携带经验 | 阵亡单位的携带经验会转到击杀者身上 |

HP 数组：`0x020242A0 + (slot-1)*0x1D4`（与单位池同 stride，**索引比 slot 小 1**）。
入口态读出 `138/104/110/40/25/25/25/25/25`，与 `notes/` 记的四个友方上限完全一致。

**未闭合**：真正的「查克拉」字段没有定位。`+0xC0` 在执行「查克拉」命令后由 0 变 32，
但下一回合又归 0（`u03` → `u05` 的对比），所以 `+0xC0` 更像是临时/动画字段；
查克拉的真实读数只能从画面右下角的 `查克拉` 数字读（`+0xC0` 之外的候选未逐一排除）。

---

## 5. 胜利条件（原版规则页实拍）

`p01-postbattle-menu/step-01-L.png` 是原版的任务说明页，原文：

> 保护木叶丸不被敌人哥攻击！
> 保护木叶丸不受後备人员攻击。木叶丸不会攻击，所以不赶快去救他就很危险。
> 保护木叶丸的同时把所有的後备人员都赶去任务算结束

⇒ **胜利条件 = 5 只蜜蜂（后备人员）全灭，且木叶丸（护送单位）存活**，
与本任务给的前提一致。**战后奖励记录**（`sequel/content/battle-results/bank.json`，
battle 14 → record 39）：`mission_experience 125`、`round_bonus_experience 75`、
**`round_limit 8`** ⇒ 回合奖励只在 `current_round <= 8` 时发放。

---

## 6. 屏①/屏② 为什么本轮没录到（阻塞点 + 证据）

1. **回合数不够**。canonical 战斗在第 6 回合结束（`scenario-49-battle-14-postbattle-task-menu.ss9`
   的 `0x0202680C = 6`）。本轮接手的是第 4 回合中途点
   （`scenario-49-battle-14-turn4-two-kills.ss9`，`0x0202680C = 4`），
   而原版每个玩家单位**每回合只有 1 次行动**（命令菜单里「移動」和「本・忍具」是二选一；
   只有走「移動 → 确认落点」这条路才会接着弹忍法列表，等于「移动 + 行动」同回合，
   但**仍然只有 1 次攻击**）。
   5 只蜜蜂 × 2 击（十字手里剑 18 伤害 vs 25 HP）= 至少 5 次攻击，
   分摊到 4 个单位、且每单位每回合 1 次行动 ⇒ 需要 ≥2～3 个回合；
   而 `round_limit = 8` 意味着**必须在第 8 回合内结束**。
   本轮实测推进到第 5 回合时，双方状态是：
   `鸣人 76/5、佐助 104/?、小樱 110/3、木叶丸 28/0`，
   蜜蜂 3 只（25 / 25 / 12 HP）分别站在 (11,4)、(9,5)、(8,6)，
   佐助在 (7,10)。**佐助的火遁术「距離 2 直」够不到任何一只蜜蜂**
   （最近的 (8,6) 距离 4），而移动后再攻击要再花一个回合。
2. **经验分布一改就废**。战后结算页显示每名队员的经验，经验 = 125 + 75 + 该角色的携带经验。
   canonical 的携带经验是 **鸣人 50 / 佐助 200 / 小樱 0 / 木叶丸 0**
   （`postbattle-task-menu` 的 `+0xCE` 实测），对应鸣人 `EXP 100/325`、佐助 `LV6/35`、
   小樱 `LV6/180`。本轮中途试打时曾让鸣人多杀一只（携带经验变成 鸣人 100），
   那样结算页/状态页的数字都会和原版不同 —— 所以本轮把那一段**弃用**，
   改从 canonical 的第 4 回合中途点重新打（`u01-…` 之后那一串），
   以保证「鸣人 1 杀、佐助 3 杀」的分摊。
3. **木叶丸的余量**：canonical 打完时木叶丸只剩 16 HP（`28 → 16`，被最后一只 7 HP 的蜜蜂打了一次）。
   本轮把战斗推进到第 5 回合的敌方阶段之后，实测**木叶丸被打到只剩 4 HP**
   （`28 → 4`，`u12-enemy-phase-r5/step-01-L.ss9` 的 `+0x0C` = 4）——
   因为 5 只蜜蜂在敌方阶段全部围到了护送单位旁边（蜜蜂 (10,3)/(11,4)/(9,5) vs 木叶丸 (12,3)）。
   **下一轮的第一优先不是攻击，而是先把护送单位旁边的蜜蜂清掉**；
   否则再打一个敌方阶段护送单位就归零，任务直接失败，连结算页都不会出现。
   本轮 canonical 线的最终实测状态（`u13-dialog-r5/step-04-A.ss9`）：
   `鸣人 65/携带经验50`、`佐助 104/携带经验50`、`小樱 110/携带经验0`、`木叶丸 4/携带经验0`，
   蜜蜂 3 只（25 / 25 / 12 HP）在 (10,3)、(11,4)、(9,5)，佐助在 (7,10)。

**下一轮可以直接照做的最小动作**（全部在本仓库已有 checkpoint 上）：

```sh
# 起点：canonical 第 4 回合中途点（鸣人 1 杀 / 佐助 1 杀，木叶丸 28 HP，蜜蜂 3 只）
/usr/local/bin/python3 tools/butano/capture_s49_advance.py --out-dir <新目录> --rom rom/base.gba \
  --state artifacts/runtime-checkpoints/scenario-49-battle-14-turn4-two-kills.ss9 \
  --keys "B" --zero-input-frames 90 --settle-frames 240 --hold-frames 4      # 退出移动态 → 鸣人命令菜单
# 鸣人：必须「不杀」。用 十字手里剑 打 25 HP 的蜜蜂（18 伤害 → 7 HP），
#       瞄准方向要挑「直线且 ≤3 格」的那只（canonical 就是 Naruto 把槽 5 从 25 打到 7）
# 佐助：Down*3 → 查克拉（补满，消耗整个回合）→ 之后用 火遁术（60 伤害，一击必杀）
#       但 火遁术 距離 2 直 ⇒ 必须先移动到能直线打到蜜蜂的格位
#       （「移動 → 确认落点」之后会接着弹忍法列表 ⇒ 移动+攻击可以同一回合完成）
# 樱：整回合 行動結束 跳过；木叶丸会自动行动（他不会攻击）
# 敌方阶段：用 L 之类的无副作用键 + settle 2400；**每回合都要回读木叶丸的 HP**
```

**两个还差最后一步确认的点**（下一轮第 1 分钟就该验）：

1. 「查克拉」补满的查克拉**能不能跨回合用**。本轮实测：`查克拉` 之后
   单位池 `+0xC0` 由 0 变 32（`u03-sasuke-chakra-confirm/step-01-A.ss9`），
   但下一个敌方阶段后同一字段又变回 0（`u05-enemy-phase-canonical/step-01-L.ss9`）。
   `+0xC0` 是不是查克拉本身没闭合（见 §4），
   所以「查克拉 1 回合 + 火遁术 1 回合」能不能连着打 3 只蜜蜂，**必须实拍一次**。
2. 佐助走到「能直线打到蜜蜂」的位置要走几格。本轮只测到：从 (7,10) 出发，
   走位光标往上按 3 次 `Up` **只移动了 1 格就停住**
   （`t21-sasuke-move/step-05-Up.png`：橙色格 = 当前光标格，白括号在其上，
   可走区域是另一片青色格；`t21-sasuke-move/step-08-A.ss9` 显示佐助没有移动）。
   **停住的原因本轮没有区分开**（是移动范围的边界，还是该格被单位占位），
   所以「往上 1 格就够」还是「往上要 2 回合」两种可能都还在。
   若确实要 2 个回合才能进火遁术射程，3 次击杀会被推到第 8 回合之后，
   **回合计入超过 `round_limit 8`** ⇒ 回合奖励（75 经验）会丢。
   这是下一轮最先要算清楚的数（1 段录制即可判定：读 `step-05-Up.png` 的青色格集合，
   或读单位坐标看光标停在哪一格）。

---

## 7. 录制链（本轮所有产物都在 `artifacts/s49-original-victory-20261020-v1/`）

| 段 | 内容 |
| --- | --- |
| `r01-intro/` | 从 battle-14 入口按 `A*18` 到命令菜单；**`step-18-A.png` 与 `artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-18-A.png` 逐字节相同**（`bdf92a439df772bc67ccf91999b3d80f617aa6833bf95ffd04607fc19e45aec7`），证明本轮起跑点与既有 walk 记录一致 |
| `r02-teleport-aim/` `r03-teleport-exec/` | 鸣人瞬身术 3 格（11,6）→（8,6），查克拉 5→4 |
| `r04-…-skip-sakura-sasuke/` | 鸣人回合结束 + 跳过小樱/佐助（该段是**回合结束序列的黄金样本**：`A,A,A` 之后 `acting` 从 1 变 3 再变 2） |
| `r05-enemy-phase-r1/` … `r18-enemy-attack-resolve/` | 敌方阶段、反应对白、系统的回合菜单（`回合 3 / 回合結束 / 選擇角色 / 通關條件 / 遊戲中斷`）、`A` 在**空格**上会误开这个菜单（重要陷阱） |
| `r19-…` `r23-…` | 小樱忍法列表实测：瞬身术 / 分身术 / 忍者组合拳 |
| `r26-sasuke-action-menu/` | 佐助忍法列表实测：火遁术 / 瞬身术 / 忍者组合拳 |
| `t01-…` `t21-…` | 从 canonical 第 4 回合中途点接手的一段；`t05` 里 **鸣人的十字手里剑把蜜蜂槽 5 从 25 打到 7**（与 canonical 记录的「槽 5 25→7」逐位一致） |
| `u01-…` … `u13-…` | canonical 线的正式接手：跳过鸣人 → 佐助 `查克拉`（0→32 见 §4）→ 跳过小樱 → 敌方阶段 → 反应对白 |
| `p01-…` … `p04-…` | **屏③ 的四段（见 §2）** |
| `drive_victory.py` | 本轮写的自动驱动器（读 savestate → 决定按键 → 调 `capture_s49_advance.py` 录一段）。**它只跑到第 1 回合就被本轮发现的「敌方阶段不能按 A」和「查克拉 ≠ 查敵拉」两个问题打断**，不是最终可用的成品，保留在此作为可复现脚本的起点 |

每段目录都含 `inputs.json`（含 ROM/快照/脚本/守卫的 SHA-256 与完整按键序列）、
`steps.json`（逐步 PNG+savestate 的 SHA-256）、`guard.json`（守卫收据）。

---

## 8. 已知的坑（下一轮别再踩）

1. **光标不在单位上时按 `A` 会打开系统回合菜单**（`回合結束 / 選擇角色 / 通關條件 / 遊戲中斷`），
   再按 `A` 可能选中「遊戲中斷」直接退出游戏。敌方阶段、对白阶段、目标选择阶段
   都可能出现光标不在单位上的状态。
2. **切镜动画的文字页数不固定**（本轮见过 1 页与 2 页），回合结束的 `A` 次数要按帧核对，
   多按一次会把下一单位的命令菜单也打开（后面再按 `A` 就会误进「移動」）。
3. **查克拉是命令菜单第 3 项**，不是「查敵拉」；它消耗整个回合。
4. **每个 mGBA run 必须 ≤ 约 6000 帧**：`tools/run_guarded.py` 的 idle 超时是 120 s
   （`capture_s49_advance.py` 硬编码 `--idle-timeout-s 120`），
   实测约 52 fps ⇒ 一次 run 最多约 6000 帧；超过就 `exit 124`。
   ⇒ 长战斗必须**分段录制**，用 `--state <上一段的 step-NN-*.ss9>` 串起来。
5. 同一时间可能有别的代理在跑 remake 侧的 capture，**重锁会返回 exit 75**，等一下重试。
