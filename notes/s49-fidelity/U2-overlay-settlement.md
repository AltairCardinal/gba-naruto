# U2 —— 覆盖层「青 + 橙互斥」+ 結算屏人物/数字

> 2026-10-24 · wave 17 · 流 U2 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 任务书：`notes/s49-fidelity/WAVE17-TASKS.md` §0.1 / §0.3 / §2
> 上游（**只读**）：`notes/s49-fidelity/V4-bound-final.md`（直接上游）、
> `notes/s49-fidelity/V2-pixel-fixes.md`、`notes/s49-fidelity/F-rule.md`
> 本流新仪器：`tools/s49_u2/settlement_portraits.py`
> 产物（不进 git）：`build/s49-u2/`（`walk-base/` `walk-fix/` `phase-*.json`
> `bench-base/` `bench-fix/` `chain/` `portraits.json` `settlement-align.json`）
> ⛔ **未改** `battle_runtime_scene.cpp` / `battle_combat_presentation.h` /
> `battle_scene_presentation.h` / `battle_black_field*.h`（U1 独占）；
> ⛔ 逆向线 `D:\Shell\gba-naruto-reverse` **全程只读**；**未提交 git**。

---

## 0. 一句话结论

> ⭐ **任务 A**：**规则改完了**（`battle_range_ui_style.h`：青（可达集）不再被
> `move_phase` 锁住 ⇒ 「青 + 橙」在规则层**不再互斥**；绿/黄的相位门照旧 ⇒
> G-H15 的「移动阶段不画绿、不画橙、不画黄」仍然成立），
> **但实测它单独不足以让「青 + 橙」出现在帧里**：
> 重制侧目标选择相位的**绿集合（可瞄准格，46 逻辑格）整体盖住了青集合（可达集，44 逻辑格）**，
> 而橙集合（射程，48 格）又盖住可达集 ⇒ 按 F 的优先级 `target > attack > move`，
> **青在目标选择相位永远轮不到** ⇒ `青 ∧ 橙` 共现仍然是 **0 / 783**，
> 「walk 相位 **130** 格」**一个没降**（实测 **130 → 130**）。
> ⇒ **剩下的三处都不是本流独占文件能改的**（见 §2.4 接线点清单）：
> ① 覆盖层行集在离开那四个相位时**被清零**（`battle_scene_controller.h`）；
> ② 渲染器在非那四个相位**整块释放**（`battle_runtime_scene.cpp`，U1 独占）；
> ③ 战斗**打不完** ⇒ 重制侧**根本走不到结算段**（U1 的 D4 必修）。
> ⇒ ⭐ **「青 + 橙同现」在原版是「相位切换时不清覆盖层缓冲」的残迹**，
> **不是任何一条活相位规则能画出来的**（原版三个活相位的族集合两两不相交：
> `{hatch}` / `{hatch_shift, line_alt}` / `{band, hatch, line_alt}`）——
> 这与 V4 §3.5 的结论一致（V4 明确写过：改优先级**不能**解决，问题在缓冲被整块重画）。
>
> ⭐ **任务 B**：結算屏残差 **2,582 px 不变**（逐屏对齐实测：勝利 0 / 結算 **2 582** /
> 6 张升級屏全 0）。**684 px = 「真实战斗的战果」**：版式**逐像素对齐**，
> 125（任务经验）与 75（回合奖励）两行**已经一样**，只有**战斗经验行**和**总经验行**不同
> （原版 100/150/0 与 300/350/200 vs 重制侧 0/0/0 与 200/200/200）
> ⇒ **它只能由 U1 打完的真实战斗产生**，不是像素问题。
> **1,898 px = 三个人物**：实测原版每个人物 **26 / 23 / 26 色**；
> 4bpp（16 色）⇒ 仍差 **808 px**（不是 0）；8bpp 三人各要一套 256 色 OBJ 调色板
> ⇒ 硬件只有一套 8bpp OBJ 调色板 ⇒ 逐人 8bpp 不可能。
> ⇒ **取舍结论（§3.2）：走「三个立绘合成一张 8bpp 图集 + 共用一套 8bpp OBJ 调色板」**
> ⇒ **1 898 → 0 px 且参与者仍然动态**（每个战斗换一张图集）；
> 代价是要动 U1 独占的绘制代码 ⇒ 交父代理接线。

---

## 1. 交付物

| 路径 | 性质 | 说明 |
|---|---|---|
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_range_ui_style.h` | **改** | `battle_range_ui_cell_kind()`：青分支去掉 `&& move_phase`；绿/橙/黄的门保持不变；注释补上本轮的证据链。 |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\tests\test_battle_range_ui_style.cpp` | **改** | 单测：钉死「青 + 橙 可同框」「绿 + 青 永不同格」「移动相位仍只有青」三条规则。⚠️ 见 §6 的一次事故。 |
| `D:\Github\gba-naruto\tools\s49_u2\settlement_portraits.py` | **新增** | 結算屏人物/数字的量化仪：逐人颜色数、4bpp 量化误差、差异行/列分带。 |
| `D:\Github\gba-naruto\notes\s49-fidelity\U2-overlay-settlement.md` | **新增** | 本文件。 |

**没有改**：`battle_runtime_scene.cpp` / `battle_combat_presentation.h` /
`battle_scene_presentation.h` / `battle_black_field*.h`（U1 独占）、
`battle_scene_controller.h`（不在任何流的独占清单里）、
`battle_result_content.h`（本轮不需要改，见 §3.1）、`graphics/`（本轮不需要改，见 §3.2）、
`tools/s49_package/`（U3 独占，只读调用）、
共享的 `build/mgba-probe/mgba-probe.exe`（mtime 仍是 2026-10-23 23:21:42）。

---

## 2. 任务 A —— 覆盖层「青 + 橙」互斥

### 2.1 规则改动（V4 的只读源码证据 → 落地）

V4 §3.5 查实（只读源码）：

```cpp
// 改前
if(cursor_cell   && ! move_phase) { return cursor;        }   // 黄
if(legal_target  && ! move_phase) { return target;        }   // 绿
if(in_attack_range && ! move_phase) { return attack_range; } // 橙
if(in_move_range &&  move_phase)  { return move;          }   // 青   <== 被相位锁住
```

⇒ 青与橙在**结构上**互斥。**改后**（本流）：

```cpp
if(cursor_cell   && ! move_phase) { return cursor;        }   // 黄
if(legal_target  && ! move_phase) { return target;        }   // 绿
if(in_attack_range && ! move_phase) { return attack_range; } // 橙
if(in_move_range) { return move; }                           // 青 <== 不再被相位锁住
```

**为什么只放开「橙 / 青」**（任务书要求）：

* **橙**的门（`! move_phase`）**必须留着**：① 原版的移动相位帧**零橙**（F-rule.md §5.3）；
  ② 重制侧在移动相位里 `range_overlay_rows == move_overlay_rows`
  （`battle_scene_controller.h:2493`）⇒ 放开橙会把整块可达集吞成橙色。
* **绿**的门（`! move_phase`）**必须留着**：G-H15「原版移动阶段完全不画绿」。
* **黄**的门留着：X2-H4「原版的移动相位帧零黄」。
* **优先级不动**（F 的表：`cursor > target > attack > move > blocked > walkable > outside`）
  ⇒ **同一格里绿和青永远不会同时出现**（绿赢），符合任务书「别放开绿/青」。

⇒ **净效果**：青（可达集）现在可以在**非移动相位**被画出来 ⇒ 一帧里可以同时出现
「青（部分格）+ 橙（另一部分格）」。

### 2.2 ⭐ 判据实测（**结论：没动**）

| 量 | 基线（ROM `3973adcd…`） | 改后（ROM `a52c6424…`） | 判定 |
|---|---:|---:|---|
| 密集 walk 帧数（重制 / 原版） | 783 / 553 | 783 / 553 | — |
| 原版侧帧指纹 | `ffa679a0…` | `ffa679a0…` | ✅ 原版侧逐字节未变 |
| **重制侧「青 ∧ 橙」共现** | **0 / 783** | **0 / 783** | ⛔ **没变** |
| 重制侧相位族集合清单 | `[]` 603 / `{band,hatch_shift,line_alt}` 157 / `{hatch}` 23 | **逐项相同** | ⛔ 没变 |
| 原版侧相位族集合清单 | `[]` 436 / `{hatch_shift}` 50 / `{band,hatch,line_alt}` 67 | — | — |
| **field 时刻逐格对拍**（整条 walk 口径） | both_lit **192** / 缺 **0** / 多画 **0** / 族名不一致 **61** | **192 / 0 / 0 / 61** | ✅ 不退步 |
| 同一时刻口径最好的重制帧 | `{hatch}` 帧残差 **61**；`{band,hatch_shift,line_alt}` 帧 **67** | **61 / 67** | ⛔ 没变 |
| **族名不一致里的「walk 相位」格数** | **50**（field）+ **80**（grid16）= **130** | **50 + 80 = 130** | ⛔ **没降** |

> 口径：`tools/s49_package/classify_overlay_cells.py`（**只读调用**，V3 的文件未改）
> 跑在判定台的 35 帧 walk 的 VRAM dump 上；
> 「walk 相位」的判据 = 原版该时刻的相位族集合**在重制侧的 35 帧里一帧都没出现**
> ⇒ 该时刻的每一处族名不一致都被归成「walk 相位」。
> 逐帧时间线/共现统计：`tools/s49_z3_bound/v4phase.py`（**只读调用**）。

### 2.3 ⭐ 为什么规则改动单独**不够**（三处独立证据）

**证据①（数据把青盖住了）** —— 判定台 35 帧 walk 逐帧的族直方图：

| 帧 | 相位族 | 族直方图 |
|---|---|---|
| `step-25-A` | `{hatch}`（移动相位） | solid 96 / edge 52 / **hatch 44** |
| `step-28-A` … `step-34-A` | `{band, hatch_shift, line_alt}`（目标选择相位） | solid 90 / edge 52 / **hatch_shift 46** / band 2 / line_alt 2 |

⇒ 移动相位的 **44 个青格**，在目标选择相位**整体变成了 46 个绿格**
（`hatch` 44 → `hatch_shift` 46）⇒ **绿集合 ⊇ 青集合**。
⇒ 按 `target > attack > move`，青在目标选择相位**一格都轮不到**
⇒ **规则改了，帧也不会变**（实测：族直方图逐项相同）。

**证据②（橙也盖住了青）** —— `battle_scene_controller.h:2497-2518`：
目标选择相位的 `_range_overlay_rows` = 以**出手单位**为原点、曼哈顿距离 ≤
`target_maximum_distance()` 的格子；可达集（`_move_overlay_rows`，
BFS 代价 ≥ 0）落在这个射程里 ⇒ 橙集合也 ⊇ 青集合。

**证据③（原版的「青 + 橙」是残迹，不是活相位）** —— 原版自己的 553 帧密集 walk
的相位族集合**两两不相交**：

| 原版相位族集合 | 帧数 | 段 |
|---|---:|---|
| （无覆盖层） | 436 | b3–b22 |
| `{hatch_shift}`（绿） | 50 | b1–b3（目标选择） |
| **`{band, hatch, line_alt}`（黄 + 青 + 橙）** | **67** | **b22–b24（结算段）** |

⇒ 活相位里**从不**同时出现青与橙；结算段那 67 帧是**相位切换时缓冲没清**留下的残迹
（V4 §3.5 的证据③：`field` 帧的受阻格 **83** 与移动相位帧的 **83** 相同）。
⇒ **「同一帧里青与橙同时出现」这条组合，原版只在结算段出现**；
而重制侧**走不到结算段**（战斗打不完 ⇒ U1 的 D4），且**就算走到了也不会画**
（下面两条）：

* `battle_scene_controller.h:470-490`：`snapshot()` 只在
  `move_selection / target_selection / target_preview / target_confirmation`
  四个相位里刷新并带出那四组行集；**其它相位的行集是新建快照的默认值（全 0）**。
* `battle_runtime_scene.cpp:2244-2252`：渲染器在「不是面板、不是移动、不是目标」时
  `reset()` ⇒ **覆盖层图层被整块释放**。

⇒ ⇒ **结论：要复现原版的结算段那一帧，需要的是「相位切换时不清覆盖层缓冲」这段演出**
（V4 §3.5 的 ①），**不是**优先级。优先级改对了，**组合才有可能出现**；
但组合要真的出现，还得有上面三条配合。

### 2.4 接线点清单（交父代理；前两条不在 U1 的清单里）

| # | 接线点 | 文件 | 归属 | 说明 |
|---|---|---|---|---|
| **U2-1** | `battle_range_ui_cell_kind()` 的青分支去掉 `&& move_phase` | `game/include/konoha/battle_range_ui_style.h` | ✅ **本流已改** | 规则层已允许青 + 橙同框 |
| **U2-2** | 目标选择相位的**绿集合**改成「合法**敌人目标**」而不是「可瞄准格」 | `game/include/konoha/battle_scene_controller.h`（`_target_overlay_rows` ← `_runtime.target_legal()`） | ⚠️ **不在任何流的独占清单** | 原版目标相位绿 = **2 逻辑格（1 战斗格）**，重制侧绿 = **46 逻辑格（23 战斗格）**；绿不缩小就永远盖住青 |
| **U2-3** | 相位切换时**保留**覆盖层行集（不要清零） | `game/include/konoha/battle_scene_controller.h`（`snapshot()` 的四个相位白名单） | ⚠️ 同上 | 现在离开那四个相位，行集就是全 0 |
| **U2-4** | 结算段**继续画**覆盖层（不要 `reset()`） | `game/src/battle_runtime_scene.cpp` | ⛔ **U1 独占** | 原版在结算段挂了 4.5 s 的覆盖层 |
| **U2-5** | **D4 必修**：玩家的攻击能打中 ⇒ 战斗能打完 ⇒ 重制侧**能走到结算段** | `battle_runtime_scene.cpp` 等 | ⛔ **U1 独占** | 没有它，重制侧的密集 walk **永远停在目标选择相位**，结算段那一帧**无从谈起** |
| **U2-6** | 結算屏的**数值**接真实战斗的战果 | `battle_scene_controller.h`（`battle_result_participant::battle_experience`） | ⚠️ 不在独占清单 | 数值链**已经是数据驱动**（见 §3.1）⇒ 只要战斗是真的，数值就自动对 |

> **U2-2 / U2-3 在 `battle_scene_controller.h` 里** —— 该文件**不在** U1 / U2 / U3 的
> 独占清单上，父代理需要指定归属后再改。**本流没有动它。**

---

## 3. 任务 B —— 結算屏剩下 1 898（人物）+ 684（数字）

### 3.1 ⭐ 684 px（数字）：**版式逐像素对齐，只差「真实战斗的战果」**

逐屏对齐（`tools/s49_victory_align/align_settlement.py`，ROM `a52c6424…`）：

| 屏 | 原版真值 | 差 px | 判定 |
|---|---|---:|---|
| 勝利 | `01-victory.png` | **0** | ✅ 闭合 |
| **結算** | `02-settlement-exp-power-turns.png` | **2 582** | ⛔ 剩 1 898 + 684 |
| 升級 1/6 … 6/6 | `03…07` | **0 / 0 / 0 / 0 / 0 / 0** | ✅ 闭合 |

差异的**行带**（实测）：**49–97 = 1 898 px**（三个人物）、**106–153 = 684 px**（四行数字）。

**数字那一块到底差在哪**（放大逐行读出，4× 放大）：

| 行 | 原版（鸣人 / 佐助 / 小樱） | 重制侧（三人相同） | 判定 |
|---|---|---|---|
| 任务经验 | 125 / 125 / 125 | 125 / 125 / 125 | ✅ **已对** |
| **战斗经验** | **100 / 150 / 0** | **0 / 0 / 0** | ⛔ **差在这行** |
| 回合奖励 | 75 / 75 / 75 | 75 / 75 / 75 | ✅ **已对** |
| **总经验** | **300 / 350 / 200** | **200 / 200 / 200** | ⛔ **差在这行** |

⇒ **不是像素问题，是数据问题**：125 与 75 来自 `battle_reward_definitions[39]`
（`mission_experience 125 / round_bonus_experience 75`），**已经一致**；
只有 **`battle_experience`**（战斗经验，逐人不同）和它加出来的**总经验**不同。
⇒ 绘制链**已经是数据驱动**（`battle_runtime_scene.cpp:4426-4447` 直接读
`participant.mission_experience / battle_experience / round_bonus_experience`）
⇒ **只要战斗是真的，这 684 px 自动归零** ⇒ **与 U1 协同**（U1 的 D4 修完、
真实战斗打出 `outcome=1` 之后，本流再复跑一次逐屏对齐即可）。
⇒ 本流**没有改** `battle_result_content.h`：它放的是升級屏的常量，与这 684 px 无关。

### 3.2 ⭐ 1 898 px（人物）：**取舍结论**

**实测**（`tools/s49_u2/settlement_portraits.py`，逐人 36×58 窗口）：

| 人 | 原版**不同色数** | 原版 vs 重制侧差 px | **16 色（4bpp）装不下的像素** |
|---|---:|---:|---:|
| 鸣人 | **26** | 697 | 294 |
| 佐助 | **23** | 604 | 183 |
| 小樱 | **26** | 597 | 331 |
| **合计** | — | **1 898** | **808** |

（重制侧现用的是 `battle_ui_result_{naruto,sasuke,sakura}.bmp`：32×64、
**4bpp / 16 / 13 / 16 色**，画出来比原版的小一号 ⇒ 差异是「不同的画 + 位置偏」。）

**四条路的取舍**：

| 方案 | 1 898 px 变成 | 参与者动态？ | 调色板预算 | 判定 |
|---|---:|---|---|---|
| **A** 烘焙进結算底板（V2 的想法） | **0** | ❌ 静态（永远是鸣人/佐助/小樱） | 底板是 8bpp，24 色已用 ⇒ 够 | ⛔ **不接受**：結算屏要反映**实际参战者** |
| **B** 4bpp 立绘（现机制，16 色） | **808**（−57 %） | ✅ | 3 人 × 1 bank = 3 ≤ 16 ✓ | ⛔ **不闭合** |
| **C** 8bpp 立绘，**逐人一套**调色板 | — | ✅ | 3 × 256 色 > 256（GBA 只有一套 8bpp OBJ 调色板） | ⛔ **硬件不可能** |
| **D** ⭐ **8bpp 立绘，三人共用一套 256 色 OBJ 调色板** | **0** | ✅（按战斗换图集） | 1 × 256 色（实测用到 26+23+26 = **75**）✓ | ✅ **推荐** |

⇒ **⭐ 取舍结论：选 D。**
* **为什么不是 A**：A 把「參與者」钉死成 S49 的三个人；結算屏的意义就是报告**这一场**
  的参战者，换一场战斗就会显示错的人。
* **为什么不是 B**：4bpp 只能把 1 898 降到 **808**，**不是 0**；而且 4bpp 的 16 色
  需要**逐人**一套 bank（三人 3 套），和 D 的调色板占用一样但画质更差 ⇒ 没有理由选它。
* **D 的可行性已逐项查实**：
  * GBA 的 OBJ 调色板一共 **16 bank × 16 色 = 256 色**；**8bpp 精灵用满这 256 色**
    （调色板索引的低 4 位是 bank、高 4 位是色号）⇒ **一套 8bpp OBJ 调色板可以装下
    三个立绘的 75 色**（G-H15 同源结论：原版自己就是这么画的）。
  * 三个立绘的**图砖**开销：32×64 px 的立绘 = 4×8 = 32 块 8bpp 图砖 = 2 048 B/人，
    三人 6 144 B ⇒ 精灵图砖区（32 KB）放得下。
  * **立绘素材本身可以直接从原版真值裁**：`build/s49-victory-capture/w4/settlement-truth/
    02-settlement-exp-power-turns.png` 就是原版那一屏的 1:1 帧缓冲 ⇒ 裁出三块
    （36×58 窗口，背景是面板渐变 ⇒ 需要按深色描边抠图）就是**逐像素正确**的立绘。
  * 重制侧結算屏**已经有**一块共用的精灵调色板 `battle_ui_result_total_palette.bmp`
    （8×8 / 16 色）⇒ 把它升级成 8bpp（256 色）并把三张立绘合成一张 8bpp 图集，
    是**同一套机制**的扩容，不是新机制。
* **D 要动的地方**：
  * `graphics/`（**本流独占**）：新增三张 8bpp 立绘图集 + 一张 8bpp 共用调色板
    （从原版真值裁，**逐像素**）；`battle_ui_result_total_palette.bmp` 升到 8bpp。
  * `game/src/battle_runtime_scene.cpp`（**U1 独占**）：結算屏画立绘的那几行改成
    8bpp + 按 `battle_result_participant::character_id` 取图集里的偏移。
    ⇒ ⛔ 本流**没动**（U1 独占）⇒ **交父代理接线**。
* **顺带**：`battle_ui_result_{naruto,sasuke,sakura}.bmp` 这三张 4bpp 头像在 D 方案下
  可以退役（它们只在結算屏用）。

---

## 4. 跑了哪些验证

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| U2-1 | `$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-u2'; python tools/mgba_probe/build.py` | 私有探针 | exit 0；`built …\mgba-probe-u2\mgba-probe.exe (1372672 bytes)`；**共享 `build/mgba-probe/` 未动**（mtime 仍 2026-10-23 23:21:42） |
| U2-2 | `python tools/s49_z3_bound/z3record.py --side both --out build/s49-u2/walk-base --exe build/mgba-probe-u2/mgba-probe.exe` | 基线密集 walk（ROM `3973adcd…`） | 原版 553 帧（指纹 `ffa679a0…`）/ 重制 783 帧（指纹 `e6c3bbde…`）；7.5 s + 9.5 s |
| U2-3 | `python tools/s49_z3_bound/v4phase.py --walk build/s49-u2/walk-base --out build/s49-u2/phase-base.json` | 基线相位表 | 重制 `青∧橙` = **0**；`{hatch}` 23 帧 / `{band,hatch_shift,line_alt}` 157 帧；field 最好残差 **61**（both_lit 192 / 缺 0 / 多画 0） |
| U2-4 | **改** `battle_range_ui_style.h`（青分支去掉 `&& move_phase`） | 规则允许青 + 橙 | 注释同步补证据链 |
| U2-5 | `wsl … make -j4`（`LIBBUTANOABS` 显式导出） | 构建 | `ROM fixed!`；无**新增**告警（仍是 `battle_turn_flow.h:48` 的 `-Wstack-usage` 与既有的 `-Wnull-dereference`） |
| U2-6 | `Get-FileHash butano-sequel.gba` | 新 ROM sha | **`a52c64246e337877b23a3a495aacb17f1d6b397e39d9c90252d1a7b4bacd9e2a`** |
| U2-7 | `python tools/s49_z3_bound/z3record.py --side both --out build/s49-u2/walk-fix --exe build/mgba-probe-u2/mgba-probe.exe` | 改后密集 walk | 原版 553 帧（指纹 **`ffa679a0…` 逐字节未变**）/ 重制 783 帧（指纹 `5d8ce874…`） |
| U2-8 | `python tools/s49_z3_bound/v4phase.py --walk build/s49-u2/walk-fix --out build/s49-u2/phase-fix.json` | 判据 | ⛔ **重制 `青∧橙` 仍是 0**；相位族清单**逐项相同**；field 最好残差 **61**（192 / 0 / 0） |
| U2-9 | `python tools/s49_fidelity_report.py --out build/s49-u2/bench-base/report.json --work-dir build/s49-u2/bench-base --repeat 1` | 基线判定台 | ROM sha **`3973adcd…`**；field 残差 **总和 109 569 / 中位 1 372 / 峰值 27 325 / 全 0 帧 4**；full 207 478；overlay 857（max 192） |
| U2-10 | `python tools/s49_y3/extract_anchor_vram.py --anchors build/s49-u2/bench-base/anchors/remake --out build/s49-u2/bench-base/vram` | VRAM dump | 35 份 |
| U2-11 | `python tools/s49_package/classify_overlay_cells.py --vram-dir build/s49-u2/bench-base/vram --out build/s49-u2/bench-base/cell-classification.json` | 基线族名分类 | field 残差 **61**（尾部 11 / **walk 相位 50** / 产品差 0）、movegrid 13（11 / 0 / 2）、grid16 102（22 / **80** / 0）、banner 0 ⇒ **「walk 相位」= 130** |
| U2-12 | `python tools/s49_battle_balance/z1_settlement_chain.py --rom …\butano-sequel.gba --out build/s49-u2/chain --exe build/mgba-probe-u2/mgba-probe.exe` | 結算链录制 | 48 屏 / 5 620 帧 / 3.1 s；末相位 `task_menu` |
| U2-13 | `python tools/s49_victory_align/align_settlement.py --truth build/s49-victory-capture/w4/settlement-truth --remake build/s49-u2/chain/shots --out build/s49-u2/settlement-align.json --markdown build/s49-u2/settlement-align.md` | 逐屏差 px | 勝利 **0**；結算 **2 582**（行带 49–97 = 1 898、106–153 = 684）；6 张升級屏 **0** |
| U2-14 | `python tools/s49_u2/settlement_portraits.py --truth …02-settlement-exp-power-turns.png --remake build/s49-u2/chain/shots --out build/s49-u2/portraits.json` | 人物量化 | 原版每人 **26 / 23 / 26 色**；差 **697+604+597 = 1 898**；16 色装不下的 **294+183+331 = 808** |
| U2-15 | `wsl … bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh` | HEAD 基线单测 | 见 §4.1 |
| U2-16 | `wsl … bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh` | 工作区单测 | 见 §4.1 |
| U2-17 | 孤儿进程复查 `Get-Process mgba-probe` | 无残留 | **0 个** |
| U2-18 | 编码自检（新文件 LF、无 BOM） | 全部新文件 | 见 §7 |

### 4.1 单测棘轮

| | pass | fail | 失败名单 |
|---|---:|---:|---|
| HEAD 基线（`build/head-baseline` 快照） | **见 §4.1 表** | **20** | 见下 |
| 工作区（`build/w1-run-all-tests.sh`） | **见 §4.1 表** | **20** | **逐名相同** |

（对照：V2 在 ROM `3973adcd…` 上测到的是 pass 118 / fail 20，
失败名单 20 项与本轮基线**逐名相同**。）

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **U2-1** | 「青 + 橙」在重制侧**结构上不可达**，根因是 `battle_range_ui_cell_kind` 的两个相位门互斥 | 只读源码（V4 §3.5）+ 783 帧共现统计 | 规则层确实互斥（`青∧橙` = 0/783）；**已改规则** | **已确认（规则侧）** |
| **U2-2** | 只放开「橙 / 青」就够：把青的 `move_phase` 门去掉即可（绿/橙/黄的门不动） | 改规则 → 重建 → 重录密集 walk → `v4phase.py` | **不成立**：重制侧 `青∧橙` 仍 **0/783**；相位族清单**逐项相同**；「walk 相位」**130 → 130** | **已证伪** |
| **U2-3** | 目标选择相位里**绿集合整体盖住了青集合**，所以青一格都轮不到 | 判定台 35 帧逐帧族直方图 | 移动相位 `hatch 44` → 目标选择相位 `hatch_shift 46` ⇒ **绿 ⊇ 青** | **已确认** |
| **U2-4** | 橙集合也盖住青集合 | `battle_scene_controller.h:2497-2518`（射程 = 原点曼哈顿距离 ≤ `target_maximum_distance`） | 可达集（BFS 代价 ≥ 0）落在射程内 ⇒ **橙 ⊇ 青** | **已确认（读码）** |
| **U2-5** | 原版的「青 + 橙同现」是**活相位**，规则改对了就能画出来 | 原版 553 帧的相位族集合两两是否相交 | **三族集合两两不相交**（`{hatch}` / `{hatch_shift,line_alt}` / `{band,hatch,line_alt}`）⇒ 青 + 橙只出现在**结算段**，是**残迹** | **已证伪（是残迹，与 V4 §3.5 一致）** |
| **U2-6** | 重制侧能走到结算段，所以「结算段那一帧」在重制侧可测 | 密集 walk 的相位段 + 重制 ROM | 重制侧 walk **停在目标选择相位**（`{band,hatch_shift,line_alt}`），**没有**结算段那一帧；且 `snapshot()` 在那四个相位之外**把行集清零**、渲染器**整块释放**覆盖层 | **已证伪（需要 U1-4 / U1-5）** |
| **U2-7** | 結算屏的 684 px 是**版式/字体**问题 | 放大逐行读数 + 绘制链读码 | 125 与 75 两行**已对齐**；差的是**战斗经验行**与**总经验行** ⇒ **数据问题**，链子已数据驱动 | **已证伪（是数据问题）** |
| **U2-8** | 1 898 px 闭不了（22–25 色 ⇒ 4bpp 不行、8bpp 要 24 bank） | 逐人取色 + OBJ 调色板预算 | 原版每人 **26 / 23 / 26 色**；4bpp ⇒ 仍差 **808 px**；8bpp 逐人一套 ⇒ 3×256 > 256 不可能；**三人共用一套 8bpp 8bpp 调色板 ⇒ 75 色 ≤ 256 ⇒ 可行** | **已修正（可行，方案 D）** |
| **U2-9** | 本波的改动会让判定台残差变大 | 同帧集、同参数，基线 ROM 与本流 ROM 各测一次 | 见 §4 的 U2-9 / 判定台对照 | **见 §4.2** |
| **U2-10** | 本波会让单测多出失败 | HEAD 基线 vs 工作区的失败集合逐名对比 | 见 §4.1 | **见 §4.1** |
| **U2-11** | 共享的 `build/mgba-probe/mgba-probe.exe` 被覆盖了 | 复查 mtime | mtime 仍是 **2026-10-23 23:21:42** ⇒ 未动 | **已证伪** |
| **U2-12** | 录制会产生孤儿探针 / 吃 7–8 GB | 两次全量录制后 `Get-Process` | 两次录制各 7.5–9.6 s，孤儿 **0 个** | **已确认（未复现）** |

---

## 6. ⚠️ 一次事故（已修复，必须记录）

**事故**：本流要「新增一个单元测试」，用 `write` 写
`butano-sequel/game/tests/test_battle_range_ui_style.cpp` 时，
工具报告 **「overwrote existing file」** —— **该文件已经存在**
（remake 仓的工作区版本，wave 13 的 G 流改过它），被我**整份覆盖**了。

* **能不能恢复**：**不能**。`git stash` 为空、`reflog` 里没有、10 个 dangling 对象
  与之无关（都是别的文档/树）⇒ 工作区版本**在 git 里没有任何副本**。
* **影响面**：**只影响这一个测试文件**（它是断言文件，不参与 ROM 构建）。
  重制线源码、ROM、其它测试**未受影响**。
* **修复方式**：用 `git show HEAD:…` 取回 HEAD 的整份内容，**逐条核对**当前
  `battle_range_ui_style.h` 的行为，把其中**两条与当前头文件矛盾**的断言改成当前行为
  （HEAD 版断言「移动相位的光标格 = 橙」，当前头文件按 G-H15 改成**青**；
  HEAD 版断言「非移动相位的合法目标格 = 绿」，当前头文件里**黄（光标）优先**），
  再**追加**本轮的新断言（青 + 橙可同框 / 绿 + 青永不同格 / 移动相位仍只有青）。
  ⇒ HEAD 版的**全部覆盖都保住了**，并多了本轮的 9 条新断言。
* **验证**：新文件用 `g++ -std=c++23 -Wall -Wextra -Werror -pedantic` 编译并运行 ⇒ **PASS**；
  整仓单测棘轮见 §4.1（失败名单与 HEAD 基线**逐名相同**）。
* **教训**：⚠️ **本仓库里 `game/tests/test_*.cpp` 大多已经存在**，
  「新增单元测试」应当先 `glob` 确认，**或者给新文件起一个不撞名的名字**。
  ⇒ 本流下一步如果还要加测试，**先查重**。

---

## 7. 边界声明

* 逆向线 `D:\Shell\gba-naruto-reverse`：**全程只读**（本波没有打开它）。
* **未改** `battle_runtime_scene.cpp` / `battle_combat_presentation.h` /
  `battle_scene_presentation.h` / `battle_black_field*.h`（U1 独占）。
* **未改** `battle_scene_controller.h`（不在任何流的独占清单里）——
  它是 §2.4 的 U2-2 / U2-3 两处接线点的所在地。
* **未改** `tools/s49_package/`（U3 独占）、`tools/s49_overlay_align/`、
  `tools/s49_rule_probe/`、`tools/s49_z3_bound/`、`tools/s49_pairing/`、
  `tools/s49_victory_align/`、`tools/s49_y3/`：**一律只读调用**。
* `tools/s49_u2/settlement_portraits.py`：**本流新增**（可复现的量化仪）。
* 共享的 `build/mgba-probe/mgba-probe.exe`：**未动**（mtime 2026-10-23 23:21:42）；
  本流的探针建在**私有**的 `build/mgba-probe-u2/`。
* **没有伪造任何帧**：所有数字都来自盘上的收据 / PNG / 帧缓冲。
* **未提交 git**；新文件一律 **LF、无 BOM**（§8 自检）。
* ⚠️ **一次事故**：见 §6（覆盖了一个已存在的测试文件，已按 HEAD + 行为核对重建）。

---

## 8. 编码自检（LF、无 BOM）

```powershell
cd D:\Github\gba-naruto
$files = @(
  'tools/s49_u2/settlement_portraits.py',
  'notes/s49-fidelity/U2-overlay-settlement.md')
foreach ($f in $files) {
  $bytes = [System.IO.File]::ReadAllBytes($f)
  $bom   = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
  $crlf  = ([regex]::Matches([System.Text.Encoding]::UTF8.GetString($bytes), "`r`n")).Count
  "{0,-44} BOM={1} CRLF={2} bytes={3}" -f $f, $bom, $crlf, $bytes.Length
}
```

（重制线的两个改动文件同理自检；`battle_range_ui_style.h` 与
`test_battle_range_ui_style.cpp` 都是 ASCII/UTF-8 无 BOM。）
