# W3 —— 黑场收官（接管 Z2）+ 勝利/结算屏画面

> 2026-10-24 · wave 15 · 流 W3 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/Z2-blackfield-final.md`（黑场收尾，**改动已在 ROM 里**）、
> `Y1-stack-fix-and-settlement.md`（结算链运行帧）、`W3-original-truth.md`（黑场真值表）、
> `W2-starfield-vram.md`（VRAM 约束与 hybrid16 解法）
> 本波新建仪器：`tools/s49_victory_align/align_settlement.py`（逐屏差 px）
> 产物：`build/w3/`（`blackfade-pinned.json` / `settlement-align.json` / `chain-pinned/`）
> ⛔ **未改** `battle_runtime_scene.cpp` / `battle_ui_model.h` / `battle_presentation_content.h`
> （W1 独占）、`tools/s49_package/`（W2/W4 独占）；逆向线 **全程只读**；**未提交 git**

---

## 0. 一句话结论

> **黑场：Z2 的修复已在 ROM 里，本波把「剩下的唯一缺口」缩小到一条可判定的结论：
> 生长段 12 级每级 4 帧**不是**遮罩的每精灵开销造成的**（我把每级的 `set_tiles`/`set_position`
> 调用从 2467/级降到 421/级，生长段**一点没变快**）⇒ 瓶颈在别处，
> 下一波请换方向（§2.4 给了两条候选路 + 一张逐级测量表）。
>
> **勝利/結算屏：逐屏差 px 已测出（勝利 37 462 px / 結算 35 859 px / 6 个升級屏 0 px），
> 并且把結算屏的差**定位到三个具体的点**（§3.3）——
> 但**画这两屏的代码在 `battle_runtime_scene.cpp`（W1 独占）**，
> ⇒ 我交出**逐条接线点 + 素材清单**，不改那三个文件（§3.5、§3.6）。

---

## 1. 改动的文件清单

### 1.1 本仓库（`D:\Github\gba-naruto`）

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\notes\s49-fidelity\W3-blackfield-and-screens.md` | **新增** | 本文件。 |
| `D:\Github\gba-naruto\tools\s49_victory_align\align_settlement.py` | **新增** | ⭐ **逐屏差 px 的量器**：把原版真值 9 张与重制侧结算链的运行帧逐像素对拍，给出差 px、差行带、两侧颜色数、逐字节是否相同，并写机读收据 + 人读表。 |

### 1.2 重制线（`D:\Shell\Github\gba-naruto-butano`）

| 文件 | 性质 | 说明 |
|---|---|---|
| `butano-sequel/game/include/konoha/battle_black_field_star_mask.h` | **改后回退** | 见 §2.3：我在这里做了一次优化（跳过未变的 `set_tiles`/`set_position`），**实测没有收益**，**已按 Z2 的基线逐字节回退**（13222 B，sha `d8690a71…`）。 |

### 1.3 **没有**改的

* 重制线其余任何文件：`battle_runtime_scene.cpp` / `battle_ui_model.h` /
  `battle_presentation_content.h` / `battle_result_content.h` / `battle_black_field.h` /
  `battle_black_field_timing.h` / `battle_black_field_star.h` / `battle_black_field_star_table.h` /
  `graphics/*` —— **一个字节都没动**。
* `tools/s49_package/`（W2/W4 独占）：**只读调用**
  （`tools/s49_package/capture_blackfade.py` 是本波唯一用到的包目录仪器）。
* 逆向线 `D:\Shell\Github\gba-naruto-reverse`：**未访问**。
* 共享的 `build/mgba-probe/mgba-probe.exe`：**未动**（本流的探针建在私有的
  `build/mgba-probe-w3/`）。

---

## 2. 任务 A：黑场

### 2.1 Z2 的工作补交（**改动已在 ROM 里，本波不重做**）

**Z2 的笔记在盘上**：`notes/s49-fidelity/Z2-blackfield-final.md`（18:28）。
它做的两件事（**都已进入 wave 14 的 ROM `ec5b5273…`**）：

1. **查实根因**：遮罩的级是在场景 `core::update()` **结束时**才提交上屏的
   ⇒ **一级显示多久 = 那一帧 update 跑多久**；「时间常量不对」被证伪，
   「每级重建遮罩太贵」被证实。
2. **修复**：把「每级销毁+重建全部精灵」改成**复用精灵的池**（单向量、**容量不变 103**）。

**当前状态（同一把尺子 `tools/s49_blackfade/blackfade_report.py`，
重制侧 = wave 14 钉住的 ROM `ec5b5273…`，2402 帧逐帧捕获）**：

| # | 帧号 | 淡出 | 全黑 | 淡入 | 总帧 | 原版 | 判定 |
|---|---|---:|---:|---:|---:|---|---|
| 1 | 27–34 | 0 | 8 | 0 | 8 | 原版**没有**（开机是淡入） | ⛔ 重制侧多出来 |
| 2 | 527–532 | 0 | 6 | 0 | 6 | 原版录不到（进场转场） | ⛔ 重制侧多出来 |
| **3** | **1549–1618** | **24** | 20 | **26** | **70** | **24 / 18 / 24** | ✅ 淡出**逐位等于**原版；持黑 +2；淡入 +2 |
| 4 | 1659–1660 | 0 | 2 | 0 | 2 | 原版**没有** | ⛔ 重制侧多出来 |
| 5 | 2123–2130 | 0 | 8 | 0 | 8 | 原版**没有** | ⛔ 重制侧多出来 |
| **6** | **2171–2250** | **28** | **24** | **28** | **80** | **24 / 24 / 24** | ✅ 持黑**逐位等于**原版；淡出/淡入各 +4 |

* 全黑帧 sha256 两侧相同：`47fbde60709a27683035d7b385f06dd1447f68c6548272758e15a335cf3bc15e`。
* 机读收据：`build/w3/blackfade-pinned.json`（+ `blackfade-pinned.md`）。

⇒ **「重制侧 2 个事件」这条验收**仍不达成：**6 vs 2**，其中 **4 个是重制侧多出来的**（§2.5）。

### 2.2 逐级测量（本波新增，交给下一波的**表**）

Z2 留下的逐级帧数表（`build/s49-z2/level_map2.py` 复跑，本波已复核，**逐值相同**）：

| 级 | 0 | 1–8 | 9–11 | 12(黑) | 13–22 | 23–32 | 33–35 | 36 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 帧数 | 2 | 2 | 2 | 20 | 2 | **4** | 2 | 6 |

⇒ 原版**每级 2 帧**；重制侧 **级 23–32 每级 4 帧** ⇒ **整条入场过渡 110 帧 vs 原版 90 帧**，
⇒ 对白相位晚 20 帧 ⇒ 37 级里**级 29–36 的可见像素差 −139…−477**（Z2 的 V4）。

**本波把「级 23–32 为什么慢」量化到逐级**（从生成的摆放表
`battle_black_field_star_table.h` 直接算，37 级全表）：

| 级 | 精灵 | 块 | 单元 | 新图块集 | 换级峰值(图块) | 与上一级同位置的单元 | 池增减 | 帧数 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 22 | 76 | 27 | 49 | 1 | 88 | 15 | 0 | 2 |
| 23 | 76 | 26 | 50 | 13 | 88 | 25 | 0 | **4** |
| 24 | 84 | 23 | 61 | 11 | 108 | 20 | +8 | **4** |
| 25 | 103 | 15 | 88 | 7 | 84 | 41 | +19 | **4** |
| 26 | 96 | 15 | 81 | 1 | 44 | 74 | −7 | **4** |
| 27 | 92 | 15 | 77 | 5 | 36 | 69 | −4 | **4** |
| 28 | 94 | 12 | 82 | 3 | 44 | 65 | +2 | **4** |
| 29 | 101 | 7 | 94 | 3 | 36 | 74 | +7 | **4** |
| 30 | 95 | 7 | 88 | 1 | 28 | 84 | −6 | **4** |
| 31 | 89 | 6 | 83 | 3 | 28 | 79 | −6 | **4** |
| 32 | 89 | 4 | 85 | 3 | 36 | 75 | 0 | **4** |
| 33 | 89 | 3 | 86 | 5 | 44 | 73 | 0 | 2 |
| 34 | 86 | 2 | 84 | 7 | 60 | 64 | −3 | 2 |
| 35 | 88 | 0 | 88 | 9 | 76 | 63 | +2 | 2 |
| 36 | 85 | 0 | 85 | 4 | 64 | 68 | −3 | 6 |

⭐ **这张表里三个「反例」是下一波的钥匙**（它们把三个常见猜想全部证伪）：

| 猜想 | 反例 | 结论 |
|---|---|---|
| 「慢是因为精灵多（OAM/句柄重建贵）」 | **级 22 与 23 都是 76 个精灵，一个 2 帧一个 4 帧**；级 33 有 **89** 个精灵反而是 **2 帧** | **不成立** |
| 「慢是因为图块/VRAM 顶到上限」 | 换级峰值最大 **108 块**（级 24），预算 404 ⇒ **只用了 27 %** | **不成立** |
| 「慢是因为精灵的创建/销毁（池增减）」 | 级 26/30/31/32 的池增减是 **−7 / −6 / −6 / 0**，却都是 4 帧；级 33 增减 0 且 2 帧 | **不成立** |

⇒ **剩下的差别只有「洞里露出多少画面」**（级 22 = 3980 px、级 23 = 5561 px、级 33 = 27291 px）
与 **update 本身要画的场景内容**。

### 2.3 ⭐ 实验：**遮罩的每精灵开销不是瓶颈**（是/否题，答案是「不是」）

**假设**：生长段每级 4 帧，是因为 `battle_black_field_star_mask::set_level()`
对**每一个**单元都调 `set_tiles()` + `set_position()`：
* `set_tiles()` 要在 Butano 的图块分配器里查一次表并改引用计数；
* `set_position()` 会把精灵的 OAM 属性标记成「变了」⇒ 触发
  `sprites_manager` 的**整块 OAM 重建 + 提交**（`check_items_on_screen` +
  `rebuild_handles` + `hw::sprites::commit`）。

**改法（一次只改一处）**：在 `set_level()` 里，把池条目与**它上一级实际持有的那个单元**比较
（⭐ **池条目的旧单元下标是 `index - previous_block_count`，不是 `index - block_count`** ——
块数逐级会变，这是第一次尝试踩的坑，见台账 W3-3），
位置与图号都没变就**跳过** `set_tiles()` 与 `set_position()`。

**量到的效果**（从摆放表精确算出，不是估计）：

| | 一次完整过渡（37 级）的 `set_tiles` 次数 | 生长段每一级的 `set_position` 次数 |
|---|---:|---:|
| 改前 | **2 467** | 85–96（每个单元一次） |
| 改后 | **421**（−83 %） | **4–38** |

**实测结果（ROM `1d7d8c9c…`，2402 帧逐帧捕获）**：

| 项 | Z2 的 ROM `ec5b5273…` | 改后 |
|---|---:|---:|
| 事件 3（入场过渡）总帧 | 70 | 72 |
| 事件 3 的淡出 / 全黑 / 淡入 | 24 / 20 / 26 | 24 / 20 / **28** |
| 事件 6（第二个黑场）总帧 | 80 | 82 |
| 级 23–32 的帧数 | 4 | 4（**没变**） |

⇒ ⭐ **一次尝试回答一个是/否问题：「生长段的额外帧是不是遮罩的每精灵开销造成的？」**
⇒ **答案：不是。** 把每级的 `set_tiles` 砍掉 83 %、`set_position` 砍到 1/20，
**生长段的帧数一个都没少**。

⭐ **逐帧对照（Z2 的捕获 vs 改后的捕获，帧 1540–1679）**：
**108 / 140 帧逐字节相同**，不同的 32 帧**全部从 1615 开始**
（1615 正是级 23 的边界）⇒ **改后只是整体后移了 2 帧，画面本身没有任何变化**
（黑场面积曲线逐值相同：79.417 / 83.003 / 87.917 … 2.156）。

⭐⭐ **那 +2 帧的归因（本波查实）**：`battle_runtime_scene.o` 的 mtime 是 **18:59:18**，
而 W1 改的 `battle_runtime_scene.cpp` 是 **18:57:06** ⇒ **本波的 ROM 确实编进了
W1 18:57 的那处改动** ⇒ **那 +2 帧是 W1 的改动带来的，不是遮罩优化带来的**
⇒ **遮罩优化对时长是中性的**（它把工作量砍了 83 %，但帧数没变 ⇒ 更进一步证明瓶颈不在那里）。

⇒ **但该优化仍已按 Z2 的基线逐字节回退**
（`battle_black_field_star_mask.h` 13222 B，sha `d8690a71418bf57e877bde1a7be1dfa01faef123cc90b4c327ddc27b8636538e`），
**理由**：它**不闭合任何一条验收判据**，而下一波真正的修法必然要改同一个文件
（遮罩的精灵数 / 摆放）⇒ **与其留一个半路改过的版本，不如让下一波在干净的基线上一次改到位**。
**补丁本身是现成的**（§2.3 的三段代码 + §2.2 的「旧单元下标 = `index - previous_block_count`」的坑），
下一波要带的时候直接贴。

### 2.4 生长段：仍未闭合（交给下一波）

**缺口**：级 23–32 每级 **4 帧**（原版 2 帧）⇒ 入场过渡 110 帧 vs 原版 90 帧
⇒ 级 29–36 的可见像素差 −139…−477 未闭合。

**已排除的猜想**（§2.2 的三个反例 + §2.3 的实验）：

| 猜想 | 判定 |
|---|---|
| 时间常量（`frames_per_level`）不对 | **已证伪**（Z2） |
| 每级重建遮罩太贵 | **已证伪**（Z2：池化后降到 2 帧） |
| 遮罩的每精灵开销（`set_tiles`/`set_position`） | **已证伪**（本波：砍 83 % 后帧数不变） |
| 精灵数 / OAM 压力 | **已证伪**（级 22 vs 23 同为 76 个精灵，2 帧 vs 4 帧） |
| 图块 / VRAM 预算 | **已证伪**（峰值 108 / 404 块） |
| 精灵创建/销毁（池增减） | **已证伪**（级 26/30/31/32 增减各不相同却都是 4 帧） |

**下一波的两条候选路**（本波没做，按反循环守则留给下一波一次改一处）：

1. **⭐ 「洞里露出的场景」这条线**（本波的新发现）：级 22（3980 px）2 帧、级 23（5561 px）4 帧、
   级 33（27291 px）2 帧 ⇒ **不是「露得多就慢」**（级 33 露得最多反而快）。
   ⇒ 但**级 23–32 恰好是「洞里第一次露出对话框/场景内容」的区间**
   ⇒ 下一波该查的是：**洞里露出的那部分场景，每帧要画多少**（地图 BG 的大地图提交？
   对话框的图块提交？）。**判据**：把战斗场景在黑场期间**只画地图 BG**（不画单位/对话框），
   看级 23–32 会不会掉到 2 帧。
2. **「update 越过一帧预算」这条线**：Z2 已证「一级显示多久 = 那一帧 update 跑多久」，
   而 Butano 的 `core::update()` 在**末尾**提交 ⇒ 若某一级的 update 超过了一个
   16.78 ms 的帧预算，那一级就多显示一帧。
   ⇒ 下一波该做的是**在 ROM 内量每一级的 update 耗时**
   （不是量精灵数）：读 Butano 的 `hw::core` 计时器或 `data.last_ticks`
   （`bn_core.cpp:464` `data.last_ticks = update_impl();`），
   **判据**：拿到 37 级的逐级耗时表，就能知道级 23–32 到底超了预算多少、
   差多少才能压回 16.78 ms。

**可复用件（下一波直接带上）**：
* §2.3 的 `set_tiles`/`set_position` 跳过补丁（像素与 Z2 的捕获逐帧相同，已实测；
  ⭐ **踩过的坑**：池条目的「旧单元下标」是 `index - previous_block_count`，
  不是 `index - block_count` —— 块数逐级会变，用错了会**画错画面**）；
* §2.2 的逐级测量表（37 级的精灵/块/单元/图块/峰值/同位置单元数/池增减）；
* `build/s49-z2/level_map2.py`（帧 → 级）与 `build/s49-z2/compare_levels.py`（37 级对拍）；
* ⭐ **「update 越过一帧预算」这条线的量法**（下一波第一步）：
  读 Butano 的 `data.last_ticks`（`bn_core.cpp:464`），**逐级**记录 update 的耗时，
  就能知道级 23–32 超了 16.78 ms 的预算多少。

### 2.5 ⭐ 「4 个硬切」的接线点清单（**交给 W1 / 父代理，不由本流改**）

Z2 已实测确认这 4 个**原版都没有**（原版上电是淡入且从不纯黑；原版 1881 帧里
对白段与入场过渡内部都没有黑场）。⇒ 它们**不该算成「原版的黑场事件」**，
而且**不在黑场的三个文件里** ⇒ 只能由 W1 / 父代理在场景侧修。

**逐条清单**（帧号 = wave 14 钉住 ROM `ec5b5273…` 的 2402 帧捕获）：

| # | 帧号 | 帧数 | 相位边界 | 前一帧 / 后一帧 | 性质 | 建议的修法 |
|---|---|---:|---|---|---|---|
| **1** | 27–34 | 8 | **上电 → 标题** | 前 26 = 纯白 `(255,255,255)`（开机白闪）／后 35 = 标题 | 硬切 | 原版的开机是**淡入**（帧 3–4 标志 48.26 → 15+ 40.94），**全程没有一帧纯黑** ⇒ 开机白闪应当**淡出**到标题，而不是先切成 8 帧纯黑。⚠️ 这一段**不在** `battle_runtime_scene.cpp`，在开机/标题路径（`src/main.cpp` + 标题场景）⇒ **需要父代理指定归属** |
| **2** | 527–532 | 6 | **准备场景 → 战斗** | 前 526 = 准备场景 `(206,230,188)`／后 533 = 战斗 `(138,158,57)` | 硬切 | 场景交接的**黑缝**：战斗场景的第一帧之前，屏上什么都没有 ⇒ 让战斗场景在**第一帧**就画出背景（或交接时不清屏）。在 `battle_runtime_scene.cpp` 的准备场景→战斗交接处 |
| **3** | 1659–1660 | 2 | **入场过渡的生长段结束 → 战斗场景** | 前 1658 = 遮罩盖住 85 %／后 1661 = 战斗场景 | 硬切 | `battle_runtime_scene.cpp:8179-8180` 的 `star_mask.clear(); battle_black_field::clear();` 与战斗场景自己画出第一批精灵之间有 **2 帧空档** ⇒ **先画场景的内容再清遮罩**（或把清遮罩推迟到场景第一帧之后） |
| **4** | 2123–2130 | 8 | **战前对白的中段**（不是对白→黑场的边界） | 前 2122 = 对白 `(130,142,98)`／后 2131 = 对白 `(145,129,167)` | 硬切 | ⭐ **注意**：这一处**在对白段内部**，前后的画面都是对白 ⇒ 是**对白脚本自己的一次「清屏重画」** ⇒ 查对白/对话框渲染器在某页切换时有没有把屏幕清成黑（`battle_presentation_*` / 对话框渲染路径） |

⚠️ **Z2 笔记 §8 提到的 `event1_hold_frames` 7 → 6**：那是**另一个**量
（事件 3 的持黑段 20 帧 vs 原版 18 帧，差 2 帧 = 场景交接多 2 帧），
**与这 4 个硬切无关**。改动点在 `battle_runtime_scene.cpp:199`
（`battle_black_field_event1_hold_frames = 7`）与
`battle_black_field_timing.h`（`event1_hold_frames = 7`，**本流独占**）：
**要一起改，否则断言与接线点会不一致**（`game/tests/test_battle_black_field.cpp` 里有断言）。

---

## 3. 任务 B：勝利屏 + 結算屏

### 3.1 逐屏差 px（**实测**，原版真值 vs 重制侧运行帧）

* 原版真值：`build/s49-victory-capture/w4/settlement-truth/`（9 张 + 收据 `9a60a89b…`）
* 重制侧运行帧：`build/w3/chain-pinned/shots/`（**wave 14 钉住的 ROM `ec5b5273…`**，
  用 `tools/s49_battle_balance/z1_settlement_chain.py` 闭环录出）
* 量器：`tools/s49_victory_align/align_settlement.py`
  （逐像素口径：任一通道不同即算不同；整屏 240×160 = 38 400 px）
* 收据：`build/w3/settlement-align.json` / `build/w3/settlement-align.md`

| 重制侧运行帧 | 阶段 | 原版真值 | **差 px** | 占比 | 差行带 | 逐字节相同 |
|---|---|---|---:|---:|---|---|
| `page-000-outcome.png` | **勝利** | `01-victory.png` | **37 462** | 97.6 % | 全屏 `[0,159]` | ❌（重制侧**全黑**） |
| `page-001-result.png` | **結算** | `02-settlement-exp-power-turns.png` | **35 859** | 93.4 % | 全屏 `[0,159]` | ❌（版式不同） |
| `page-002-level_up.png` | 升級 1/6 | `03-levelup-naruto.png` | **0** | 0 % | — | ✅ **是** |
| `page-003-level_up.png` | 升級 2/6 | `05-levelup-sasuke-jutsu-name.png` | **0** | 0 % | — | ✅ **是** |
| `page-004-level_up.png` | 升級 3/6 | `04-levelup-konohamaru.png` | **0** | 0 % | — | ✅ **是** |
| `page-005-level_up.png` | 升級 4/6 | `05-levelup-sasuke.png` | **0** | 0 % | — | ✅ **是** |
| `page-006-level_up.png` | 升級 5/6 | `06-levelup-sakura.png` | **0** | 0 % | — | ✅ **是** |
| `page-007-level_up.png` | 升級 6/6（忍具一覽） | `07-ninja-tool-list.png` | **0** | 0 % | — | ✅ **是** |
| `page-008..014-*.png` | 訓練 6 頁 + 崩潰屏 | — | — | — | — | 重制侧独有 |
| （無） | 戰後對白 | `08-postbattle-dialogue-1.png` | — | — | — | ⛔ 不可達（Z1 的 D2+D3） |
| （無） | 任務菜單 | `09-task-menu-map.png` | — | — | — | ⛔ 不可達（Z1 的 D2+D3） |

* ⭐ **录制可复现**：本波这一跑与 Z1 的 `chain-e` **15/15 个文件逐字节相同，不同帧 0 个**
  ⇒ 这是**第三次**独立复现（Z1 的 chain-e / chain-f + 本波）。
* ⚠️ 屏上的数值是**空战果**（`result_total_experience = 200`、`participant_count = 3`，
  是 poke 进来的默认值）⇒ 本波对齐的是**版式**，不是数值。

### 3.2 ⭐ 結算屏：**底板已经对到 88 %**（本波的新发现）

重制侧的結算屏底板是 `graphics/battle_ui_result_plate.bmp`（256×256 的 8bpp regular_bg）。
把它和原版真值逐像素对拍：

| 对比 | 差 px | 差行带 |
|---|---:|---|
| 原版 `02-settlement-exp-power-turns.png` vs **底板** | **4 562** | `[9,23]`（tab 行）、`[49,100]`（肖像）、`[106,153]`（数字） |

⇒ ⭐ **底板已经把 tab 框、行标「経験値/戦闘力/回合数」、红色的「合計」、渐变中板
全部烘焙对了** ⇒ **要补的只有三处**（§3.3）。

### 3.3 ⭐ 結算屏的**三个**具体差异（逐条可判定）

| # | 差异 | 证据 | 怎么修 |
|---|---|---|---|
| **B-1** | ⭐ **底板的下半屏没画出来**（第 105–159 行是**纯黑** `(0,0,0)`，而底板那里是浅色 `(231,247,214)`） | 真值 `(130,115)` = `(231,247,214)`、底板同点同值、**重制侧渲染出来是 `(0,0,0)`**；底板 BMP 的调色板 24 项（索引 0–23）**都在 `colors_count: 24` 之内**，素材本身没问题 | ⭐ **不是素材的问题，是渲染路径的问题**：底板是 8bpp regular_bg，渲染出来只有前 104 行 ⇒ 请 W1 查**结算屏那张 BG 的提交**（BG 优先级 / BG 调色板 cohort / 大地图提交）——⚠️ **W1 正在修的「OBJ 调色板 cohort」与这个高度相关**（底板是 8bpp BG，8bpp BG 的调色板是 **BG 调色板**，不是 OBJ 调色板） |
| **B-2** | ⭐ **三个人名画在了错的位置**：真值是**顶栏的第 2/3/4 个 tab**（第 9–23 行），重制侧画在**右上角**（屏幕 x ≈ 96 / 152 / 208，y = 16） | 真值的 tab 1 = 「経験値」、tab 2 = 「鳴人」（**都在底板里**），tab 3/4 = 「佐助」「小桜」（**底板里是空的**） | 把三个名字从右上角挪到 tab 2/3/4；**tab 3/4 的「佐助」「小桜」要新画**（底板是空的）；tab 2 的「鳴人」**已经在底板里，不要再画** |
| **B-3** | ⭐ **四行数字的版式其实是对的**（列右边界 117 / 173 / 229，行 113 / 121 / 129 / 139，前三行黑、第四行红） | 真值与重制侧的数字列**逐像素对得上**（只有数值不同：真值 125/190/75/300、125/150/50/350、125/150/50/200，重制侧是空战果） | **不用改版式**；只要 B-1 修好、值填对，結算屏的差就只剩数值 ⇒ **目标是「版式 0 px + 数值差」** |

⇒ **結算屏要闭合，接线点是 3 条**（B-1 / B-2 / B-3 的 B-2 一半）。

### 3.4 ⭐ 勝利屏为什么**全黑**（查实）

重制侧的勝利屏（相位 `outcome`）是 **38 400 px 全 (0,0,0)**。查实链路：

1. `battle_ui_model.h:294-301`：`outcome` / `result` / `complete` 三个相位的 UI 层都是
   `battle_ui_layer::result`，且 `show_result_panel = true`。
2. `battle_runtime_scene.cpp:1321-1322`：
   ```cpp
   if(model.show_result_panel && state.phase == battle_scene_phase::result)
   { _add_result_background(); _update_result_participants(result); return; }
   ```
   ⇒ **結算底板只给 `result` 相位画，`outcome`（勝利）相位没有底板**。
3. `battle_runtime_scene.cpp:8765-8788`：`battle_phase_uses_full_screen_result(state.phase)`
   为真 ⇒ **地图、地图单位、光标、场景装饰全部被释放** ⇒ 屏幕上什么都不剩。
4. 勝利屏应该画的两个大字「勝利」**在仓里已经有 1:1 的素材**（§3.5），
   但**没有任何代码去摆它们** ⇒ 连 `battle_runtime_scene.cpp:4344-4352` 的
   `"BATTLE COMPLETE"` / `"MISSION CLEARED"` 文本也没出现在屏上
   ⇒ **除了「没有底板」，還有「文字也没画出来」**（这一条更像是
   W1 正在查的调色板 cohort 问题：文字精灵的调色板在地图 cohort 被释放时一起没了）。

⇒ **勝利屏的两个接线点**（都在 W1 的文件里）：

* **V-1**：给 `outcome` 相位**画底板**（胜利屏要的是**战斗场景那张图**，不是結算底板）；
* **V-2**：把「勝利」两个大字摆上去（素材已就位，**不需要新素材、不占 OAM 槽**）。

### 3.5 ⭐ 素材清单（**仓里已有，不需要新素材**）

| 要画的东西 | 素材（绝对路径） | 尺寸/类型 | 备注 |
|---|---|---|---|
| 勝利屏的背景 | `D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics\scenario_41_victory_bg.bmp` | 256×256 8bpp regular_bg | 与真值的战斗场景同构（森林+草地+左下角那块石头） |
| 勝利屏的「勝利」 | `…\graphics\scenario_41_victory_title.bmp` | 256×256 8bpp regular_bg | 「勝」在第 35–95 列 / 45–115 行，「利」在第 140–200 列 / 45–115 行 |
| 勝利屏的人物 | `…\graphics\scenario_41_victory_actor.bmp` | 256×256 8bpp regular_bg | 鸣人 |
| 結算屏的底板 | `…\graphics\battle_ui_result_plate.bmp` | 256×256 8bpp regular_bg（24 色） | **已经对到 88 %**（§3.2） |
| 結算屏的三个人物 | `…\graphics\battle_ui_result_{naruto,sasuke,sakura}.bmp` | 16×16 sprite item | 重制侧已经在画（位置要往原版对） |
| 結算屏的 tab 3/4 文字 | ⭐ **需要 CJK 字形** | — | 仓里已有 `battle_settlement_font`（16×16 CJK 字体，`game/include/konoha/battle_settlement_font_content.h` 里有 90 个字，**但「佐」「助」「小」「桜」不在里面** ⇒ 要么扩字表，要么用 `battle_ui_font` 的 ASCII 之外的办法） |

⚠️ **OAM 预算**：84 个星星 + 42 个场景 = 126 / 128 ⇒ **胜利屏的两个 BG 用 regular_bg 画，
不占 OAM 槽**（三张 victory 素材本来就是 regular_bg ⇒ 天然合规）。

### 3.5.1 ⭐ 可直接贴的文案常量（本流**没有**写进 `battle_result_content.h`）

⚠️ **`battle_result_content.h` 在 WAVE15 任务书里同时列在 W1（§1.1）与 W3（§3.1）的独占清单里**
⇒ **本流不写它**（避免与 W1 打架），把内容放在这里，W1 / 下一波直接贴：

```cpp
// 結算屏顶栏的四个 tab（真值 02-settlement-exp-power-turns.png 的第 4–23 行）。
// ⚠️ battle_ui_result_plate.bmp 已经烘焙了前两个（tab 1「経験値」、tab 2「鳴人」），
//    后两个（tab 3「佐助」、tab 4「小桜」）是空的 ⇒ 重制侧要画的是后两个。
inline constexpr std::array<const char*, 4>
        battle_settlement_s49_result_tab_labels = {{ "経験値", "鳴人", "佐助", "小桜" }};
inline constexpr std::array<int, 2>
        battle_settlement_s49_result_missing_tab_indices = {{ 2, 3 }};

// 結算屏底部的行标（真值第 112–135 行的左侧）+ 合计行（第 137–150 行，红色的「合計」）。
// ⭐ 这三行 + 「合計」**已经在底板里** ⇒ 接线的人不要重复画。
inline constexpr std::array<const char*, 3>
        battle_settlement_s49_result_row_labels = {{ "経験値", "戦闘力", "回合数" }};
inline constexpr const char* battle_settlement_s49_result_total_label = "合計";

// 勝利屏的标题（真值 01-victory.png 的两个大字）。
// ⭐ 素材已有：graphics/scenario_41_victory_title.bmp（256×256 的 8bpp regular_bg），
//    「勝」在第 35–95 列 / 45–115 行，「利」在第 140–200 列 / 45–115 行。
inline constexpr const char* battle_settlement_s49_victory_title = "勝利";
```

⚠️ **「佐」「助」「小」「桜」四个 CJK 字形不在**
`game/include/konoha/battle_settlement_font_content.h` 的 90 字表里
（该表由 `tools/butano/generate_battle_settlement_font.py` 生成）
⇒ 要画 tab 3/4 的名字，**得先扩字表（改生成器）或换画法**。

### 3.6 結算屏的「三行数字布局」：**版式已经是对的**

原版真值（`02-settlement-exp-power-turns.png`）的数字版式（本波逐像素量出来的）：

| 行 | 行标（底板里有） | 列 1（鳴人） | 列 2（佐助） | 列 3（小桜） | 颜色 |
|---|---|---|---|---|---|
| 113–119 | 経験値 | 125 | 125 | 125 | 黑 |
| 121–127 | 戦闘力 | 190 | 150 | 150 | 黑 |
| 129–135 | 回合数 | 75 | 50 | 50 | 黑 |
| 139–148 | 合計（红） | 300 | 350 | 200 | **红** |

* 三列的数字**右边界**在 **x = 117 / 173 / 229**（间距 56），
  四行的**上边界**在 **y = 113 / 121 / 129 / 139**。
* 重制侧现在画的位置**正是这四个行、四列右边界** ⇒ **版式不用改**（见 B-3）。
* 重制侧的**行标**（左下角）**已经在底板里** ⇒ **不要重复画**。

### 3.7 ⭐ 結算链入口是 poke（复述 Z1，附本波复核）

* 本波的闭环驱动器（`z1_settlement_chain.py`）把控制器状态 poke 进 `outcome`，
  读回验证 `phase = 13` / `outcome = 1`，**20 次按键**后停在 `phase = 19`（訓練段崩潰屏，
  Z1 的 D3：战后对白文本有非法 UTF-8）。
* ⇒ 屏上的数值是**空战果**（`result_total_experience = 200`、`participant_count = 3`），
  **本波对齐的是版式，不是数值**。

---

## 4. 跑了哪些验证（命令 + 关键数字）

> ⭐ **口径**：本波所有「重制侧」测量都跑在**同一个 ROM** 上：
> **`ec5b527373b5c85774fcaf283789d93450dcf9c747e076db595343c2f47e4031`**
> （= wave 14 的钉住 ROM `build/s49-package-z4-final3/work/pinned-rom/measured.gba`，
> 2026-10-24 18:20:16）——**与 Z2 的黑场捕获用的是同一份字节** ⇒ 可比。

| # | 验证 | 命令 | 结果 |
|---|---|---|---|
| **V1** | ⭐ **黑场真值表**（重制侧 = 钉住 ROM） | `python tools/s49_blackfade/blackfade_report.py --frames build/s49-z2/pool-frames --out build/w3/blackfade-pinned.json --markdown build/w3/blackfade-pinned.md` | **2402 帧 / 6 个事件**；事件 3 = **24/20/26**（原版 24/18/24）、事件 6 = **28/24/28**（原版 24/24/24）；全黑帧 sha `47fbde60709a2768…` 两侧相同 |
| **V2** | ⭐ **逐级帧数复核** | `python build/s49-z2/level_map2.py --frames build/s49-z2/pool-frames --low 1400 --high 1750` | 级 0–22 = **2 帧**、级 23–32 = **4 帧**、级 33–35 = **2 帧**、级 36 = **6 帧**；持黑 20 帧 ⇒ **与 Z2 的表逐值相同** |
| **V3** | ⭐ **逐级开销表**（本流新算） | 从 `battle_black_field_star_table.h` 解析 37 级的块/单元/图号，算出精灵数、换级峰值、同位置单元数、池增减 | §2.2 的表；**三个反例**（精灵数 / VRAM / 池增减 全部被证伪） |
| **V4** | ⭐ **实验：跳过未变的 `set_tiles`/`set_position`** | 改 `battle_black_field_star_mask.h` → 构建（ROM `d8b84d67…` / `1d7d8c9c…`）→ `capture_blackfade.py` → `blackfade_report.py` + `level_map2.py` | `set_tiles` 2467 → **421**（−83 %）、生长段 `set_position` 85–96 → **4–38**；**事件 3 70 → 72 帧、事件 6 80 → 82 帧、级 23–32 仍是 4 帧 ⇒ 遮罩的每精灵开销不是瓶颈**；逐帧对照 **108/140 逐字节相同**（差异从级 23 的边界起 ⇒ 只是后移 2 帧）；⭐ **那 +2 帧已归因给 W1 的 18:57 改动**（`.o` 18:59:18 > `.cpp` 18:57:06）⇒ **已回退到 Z2 基线**（13222 B / sha `d8690a71…`） |
| **V5** | ⭐ **逐屏差 px**（勝利 + 結算 + 6 个升級屏） | `python tools/s49_victory_align/align_settlement.py --truth build/s49-victory-capture/w4/settlement-truth --remake build/w3/chain-pinned/shots --out build/w3/settlement-align.json --markdown build/w3/settlement-align.md` | 勝利 **37 462 px**、結算 **35 859 px**、6 个升級屏 **0 px**；收据 `build/w3/settlement-align.json` |
| **V6** | ⭐ **結算底板 vs 真值** | `battle_ui_result_plate.bmp` 逐像素对拍 | **4 562 px**，差行带 `[9,23]` / `[49,100]` / `[106,153]` ⇒ 底板已对到 **88 %** |
| **V7** | ⭐ **結算屏的下半屏为什么是黑的** | 取 `(130,115)` 三方取色 | 真值 `(231,247,214)`、底板 `(231,247,214)`、**重制侧渲染 `(0,0,0)`**；底板 BMP 的调色板索引只用 0–23（`colors_count: 24` 内）⇒ **不是素材问题** |
| **V8** | ⭐ **結算鏈錄製可复现** | 本波 `build/w3/chain-pinned/shots` vs Z1 `build/z1/chain-e/shots` | **15/15 文件逐字节相同，不同帧 0 个** ⇒ 第三次独立复现 |
| **V9** | **私有探针** | `$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-w3'; python tools/mgba_probe/build.py` | 建在私有目录；**共享的 `build/mgba-probe/mgba-probe.exe` 未动** |
| **V10** | **單测棘轮** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh`（HEAD 快照）<br>`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh`（工作区） | HEAD **101 pass / 20 fail**、工作区 **118 pass / 20 fail**，失败名单**逐名相同** ⇒ **新失败 0**（§7.2） |
| **V11** | **判定台残余**（同 ROM） | `python tools/s49_fidelity_report.py --out build/w3/judgment-report.json --work-dir build/s49-package-z4-final3/work/s49-report --skip-capture --remake-rom build/s49-package-z4-final3/work/pinned-rom/measured.gba --repeat 3 --quiet` | ROM sha **`ec5b5273…`**；残差总和 **109 569** / 中位 **1 372** / max 27 325 / 全 0 帧 **4**；连读 3 次 `identical = true`、`rom_changed = false` ⇒ **与基线逐项相同（不变）** |
| **V12** | **孤儿进程** | `Get-CimInstance Win32_Process -Filter "Name='mgba-probe.exe'"` | **count = 0** ✔（本流的探针建在私有的 `build/mgba-probe-w3/`，共享的 `build/mgba-probe/mgba-probe.exe` 未动） |
| **V13** | **编码自检** | 逐个读字节核对 BOM / CRLF | 见 §9 |

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **W3-1** | Z2 的黑场改动**没有**进 wave 14 的 ROM | 比对 Z2 的捕获收据与 wave 14 钉住 ROM 的 sha | Z2 的捕获用的就是 `ec5b5273…`，与钉住 ROM **逐字节相同** ⇒ 改动**在** ROM 里 | **已证伪** |
| **W3-2** | Z2 未交笔记 | 看 `notes/s49-fidelity/` | `Z2-blackfield-final.md`（18:28）**在盘上**，内容完整（根因 + 修法 + 逐级表 + 台账）⇒ 本波**补交了引用**，没有重做 | **已证伪** |
| **W3-3** | 生长段每级 4 帧是**遮罩的每精灵开销**（`set_tiles`/`set_position`）造成的 | 改 `set_level`：池条目与**它上一级实际持有的那个单元**比较（`index - previous_block_count`），没变就跳过；`set_tiles` 2467 → 421、生长段 `set_position` 85–96 → 4–38；重建 + 逐帧捕获 | ⭐ **不成立**：级 23–32 **仍然是 4 帧**（事件 3 70 → 72 帧）；逐帧对照 108/140 逐字节相同、差异从级 23 的边界起 ⇒ 只是整体后移 2 帧；⭐ **那 +2 帧已归因给 W1 的 18:57 改动**（`battle_runtime_scene.o` 18:59:18 > `.cpp` 18:57:06 ⇒ 本波 ROM 编进了它）⇒ **遮罩优化对时长中性，对工作量 −83 %** ⇒ **已证伪（已回退到 Z2 基线，补丁留给下一波）** | **已证伪（已回退到 Z2 基线）** |
| **W3-4** | 生长段慢是因为**精灵多**（OAM / 句柄重建贵） | 从摆放表算 37 级的精灵数 | ⭐ **不成立**：级 22 与 23 **都是 76 个精灵**，一个 2 帧一个 4 帧；级 33 有 **89** 个精灵反而 2 帧 | **已证伪** |
| **W3-5** | 生长段慢是因为**图块 / VRAM 顶到上限** | 从摆放表算每级的图块与换级峰值 | ⭐ **不成立**：换级峰值最大 **108 块**（预算 404 ⇒ 27 %）；`battle_black_field_star.h` 里那个 404 是**旧表**的数字 | **已证伪** |
| **W3-6** | 生长段慢是因为**精灵的创建/销毁**（池增减） | 同上，算逐级池增减 | ⭐ **不成立**：级 26/30/31/32 的池增减是 −7/−6/−6/**0**，却都是 4 帧；级 33 增减 0 且 2 帧 | **已证伪** |
| **W3-7** | 那 4 个硬切事件**原版也有** | Z2 已实测（原版上电重录 95 帧 + 原版 1881 帧真值）；本波复核重制侧的 6 个事件表 | ⭐ **不成立**：4 个全是重制侧多出来的；且**其中 1 个（事件 4，帧 2123–2130）在对白段内部**，不在黑场边界上 ⇒ **要分类修，不能当「黑场事件」修** | **已证伪** |
| **W3-8** | 勝利屏全黑是**素材缺失** | 看仓里的 victory 素材 | ⭐ **不成立**：`scenario_41_victory_{bg,title,actor}.bmp` 三张 1:1 素材**都在**（且已经是 Butano 的 regular_bg item：`bn_regular_bg_items_scenario_41_victory_title.h` 存在）⇒ **是接线缺失** | **已证伪** |
| **W3-9** | 結算屏差 35 859 px 是**底板不对** | 底板 vs 真值逐像素 | ⭐ **不成立**：底板只差 **4 562 px**（88 % 已对）⇒ 差主要来自**渲染**（下半屏是黑的）与**人名画错位置** | **已证伪** |
| **W3-10** | 結算屏的下半屏是黑的，是因为**素材的调色板不够**（`colors_count: 24`） | 读底板 BMP 的原始调色板索引 | ⭐ **不成立**：底板用到的索引只有 **1–7、22、23**，全在 24 项之内，且 PIL 解析出来的颜色与真值**逐像素相同** ⇒ **不是素材问题**（⇒ 是渲染路径，§3.3 B-1） | **已证伪** |
| **W3-11** | 結算屏的**三行数字版式**不对 | 逐像素量真值的列右边界与行上边界 | ⭐ **不成立**：真值 3 列右边界 **117/173/229**、4 行上边界 **113/121/129/139**，重制侧**正是这四个位置** ⇒ **版式已经是对的**，只需修下半屏与人名 | **已证伪** |
| **W3-12** | 結算鏈的運行帧不可复现 | 本波重录 vs Z1 的 chain-e | ⭐ **不成立**：15/15 文件**逐字节相同**，不同帧 0 个 | **已证伪** |

---

## 6. 卡在哪 / 没关掉的

1. ⛔ **「重制侧 2 个黑场事件」仍不达成**（6 vs 2）：
   * **4 个硬切**在场景侧（开机 / 准备→战斗 / 生长段结束的交接 / 对白段内部），
     **接线点清单已在 §2.5 交给 W1 / 父代理**，本流不改那三个文件；
   * **事件 3 与事件 6 的时长**还比原版各多 2 帧（持黑 20 vs 18、淡出/淡入 28/26 vs 24），
     `event1_hold_frames` 7 → 6 的改动点也已指出（**两个文件要一起改**）。
2. ⛔ **生长段 12 级仍是 4 帧/级**（原版 2 帧）⇒ 入场过渡 110 帧 vs 原版 90 帧
   ⇒ **级 29–36 的可见像素差 −139…−477 未闭合**。
   本波排除了 5 个猜想（§2.4），下一波的两条候选路与判据已写好（§2.4）。
   ⭐ **本波最硬的一条新知识**：**遮罩的每精灵开销不是瓶颈**（砍 83 % 后帧数不变）。
3. ⛔ **勝利屏仍是全黑**（37 462 px）：
   * 两个接线点已定位（§3.4 的 V-1/V-2），**但画它的代码在 `battle_runtime_scene.cpp`（W1 独占）**；
   * ⭐ **推测它与 W1 正在修的「OBJ 调色板 cohort 耗尽」是同一个根因**
     （`outcome` 相位会释放地图 cohort 的调色板，而胜利屏的文字精灵用的是同一套）——
     ⇒ **请 W1 在修 cohort 时一并看 `outcome` 相位**。
4. ⛔ **結算屏仍差 35 859 px**，差在三个点（§3.3）：B-1（底板下半屏是黑的）、
   B-2（人名画在右上角而不是 tab 里，tab 3/4 的「佐助」「小桜」缺字形）、
   B-3（不用改）。
   ⇒ **B-1 与 B-2 的接线都在 `battle_runtime_scene.cpp`（W1 独占）**；
   ⇒ **B-2 还需要 CJK 字形**：「佐」「助」「小」「桜」**不在**
   `battle_settlement_font_content.h` 的 90 字表里 ⇒ 要么扩字表（**字表是本流的独占文件
   `battle_settlement_font_content.h`，但它由 `tools/butano/generate_battle_settlement_font.py`
   生成 ⇒ 要改生成器**），要么用别的方式画这两个名字。
5. ⚠️ **测量环境**：W1 在 18:54–18:57 改了 `battle_ui_model.h` 与
   `battle_runtime_scene.cpp`。本波**一次**构建（18:57–18:59）**编进了**那处改动
   （`battle_runtime_scene.o` 18:59:18 > `.cpp` 18:57:06）
   ⇒ 那次实验的 **+2 帧已归因给 W1**（§2.3）。
   ⇒ **本波最终的所有数字都改用「钉住 ROM `ec5b5273…`」重新测**
   （V1 / V2 / V5 / V6 / V8）⇒ **与 Z2 的黑场捕获是同一份字节，可比**。
6. ⚠️ **残余基线的可比性**：本波**没有改任何产品代码**（遮罩的改动已回退），
   ⇒ 判定台残差**不变**（同 ROM `ec5b5273…`，总和 **109 569** / 中位 **1 372** /
   全 0 帧 **4**），见 §7.1。

---

## 7. 残余与棘轮

### 7.1 判定台残余（**同 ROM**）

命令：

```powershell
python tools/s49_fidelity_report.py --out build/w3/judgment-report.json `
  --work-dir build/s49-package-z4-final3/work/s49-report --skip-capture `
  --remake-rom build/s49-package-z4-final3/work/pinned-rom/measured.gba `
  --repeat 3 --quiet
```

| 项 | 本波（wave 15 的基线） | 任务书给的基线 | 判定 |
|---|---:|---:|---|
| **ROM sha256** | **`ec5b527373b5c85774fcaf283789d93450dcf9c747e076db595343c2f47e4031`** | 与 wave 14 的钉住 ROM **同一份** | ✅ 可比 |
| **残差总和** | **109 569** | 109 569 | ✅ **不变**（本波没改产品代码） |
| **残差中位** | **1 372** | 1 372 | ✅ 不变 |
| 残差 max | 27 325 | — | — |
| **全 0 帧** | **4** | 4 | ✅ 不变 |
| 连读次数 / 逐项相同 | 3 / `identical = true` | — | ✅ |
| `rom_changed` | `false` | — | ✅ |
| `content_sha256` | `fb4459830c38470e57091aeffc81cfe172645c3286ec74454bb62a4a9bc8e37e` | — | — |

⇒ **残余「只许变小」这条满足：不变**（本波**没有留下任何产品代码改动** ——
遮罩的实验已回退，见 §2.3）。

### 7.2 单测棘轮

| | pass | fail |
|---|---:|---:|
| HEAD 基线（`build/run-baseline-tests.sh`，`git archive HEAD` 快照） | **101** | **20** |
| 工作区（`build/w1-run-all-tests.sh`） | **118** | **20** |

失败名单（两边**逐名相同**，共 20 项，**新失败 0**）：

```
test_battle_all_scenario_runtime      test_battle_campaign_route
test_battle_campaign_save             test_battle_campaign_scenario_42
test_battle_campaign_scenario_43      test_battle_campaign_scenario_44
test_battle_campaign_scenario_45      test_battle_campaign_scenario_46
test_battle_campaign_scenario_47      test_battle_campaign_scenario_49
test_battle_dynamic_deployment_turn   test_battle_material_pickups
test_battle_presentation_controller   test_battle_runtime_scene_gate
test_battle_s49_input_flow            test_battle_s49_opening
test_battle_scene_character_actions   test_battle_scene_controller
test_battle_scene_multi_unit          test_battle_scene_results
```

⇒ **这 20 项在 HEAD 即为红（预存债），本流没有新增任何一项。**
⚠️ 工作区的这一次跑**包含 W1 在 18:54–19:00 的在制品**
（`battle_ui_model.h` / `battle_runtime_scene.cpp`），
但**失败集合仍与 HEAD 逐名相同** ⇒ W1 的在制品**没有引入新的单测失败**。

---

## 8. ⭐ 接线点清单（**交父代理串行合并**，本流不改那些文件）

> 全部接线点都在 **W1 独占**的 `battle_runtime_scene.cpp` /
> `battle_ui_model.h` 里（除了标注了「本流独占」的两处）。
> 每条都给了**帧号**（wave 14 钉住 ROM `ec5b5273…` 的 2402 帧捕获）作为判据。

| # | 接线点 | 位置 | 判据（帧号 / 数字） | 优先级 |
|---|---|---|---|---|
| **W-1** | **准备场景 → 战斗的 6 帧黑缝** | `battle_runtime_scene.cpp` 的准备场景→战斗交接 | 帧 **527–532** 应为 0 帧纯黑 | 高 |
| **W-2** | **生长段结束 → 战斗场景的 2 帧黑缝** | `battle_runtime_scene.cpp:8179-8180`（`star_mask.clear(); battle_black_field::clear();`）与战斗场景自己画第一批精灵之间 | 帧 **1659–1660** 应为 0 帧纯黑 ⇒ **先画场景内容再清遮罩** | 高 |
| **W-3** | **战后对白/任务菜单两相位的 UI 层**（Z1 的 D2） | `battle_ui_model.h` 的相位 switch | 结算链能走到 `post_battle_dialogue` 与 `task_menu`，且**有画面** | 高 |
| **W-4** | **战后对白文本的非法 UTF-8**（Z1 的 D3） | 战后对白的文本内容 | 结算链全程**不停机**（`battle_settlement_s49_dialogue` 7 页） | 高 |
| **W-5** | ⭐ **勝利屏的底板** | `battle_runtime_scene.cpp:1321-1322`（`show_result_panel && phase == result` ⇒ **`outcome` 相位没有底板**） | 勝利屏的差 px 从 **37 462** 降到「只剩两个字与人物」 | 高 |
| **W-6** | ⭐ **勝利屏的「勝利」两个大字 + 战斗场景背景** | 同上（`outcome` 相位的绘制分支） | 同上；素材已就位（§3.5），**不占 OAM 槽** | 高 |
| **W-7** | ⭐ **結算屏底板的下半屏为什么是黑的**（第 105–159 行纯黑） | 結算底板那张 8bpp regular_bg 的**提交**路径（BG 优先级 / **BG 调色板** cohort / 大地图提交） | 帧 `page-001-result.png` 的 `(130,115)` 应为 `(231,247,214)` | 高 |
| **W-8** | ⭐ **結算屏的三个人名要挪到顶栏的 tab 里** | `battle_runtime_scene.cpp:4360-4375`（`participant_name_x[] = {-24, 32, 88}`，y = −64） | 名字应在**第 9–23 行**的 tab 2/3/4；tab 2 的「鳴人」**已经在底板里，不要再画** | 中 |
| **W-9** | ⭐ **結算屏 tab 3/4 的「佐助」「小桜」缺 CJK 字形** | `battle_settlement_font_content.h`（**由 `tools/butano/generate_battle_settlement_font.py` 生成** ⇒ 要改生成器） | 90 字的表里没有「佐」「助」「小」「桜」 | 中 |
| **W-10** | **事件 3 的持黑段 20 帧 → 18 帧** | `battle_runtime_scene.cpp:199`（`battle_black_field_event1_hold_frames = 7`）**＋** `battle_black_field_timing.h`（`event1_hold_frames = 7`，**本流独占**） | 事件 3 的持黑 **20 → 18**；⚠️ **两个常量要一起改**，否则 `game/tests/test_battle_black_field.cpp` 的断言与接线点不一致 | 中 |
| **W-11** | **事件 6 的淡出/淡入 28 → 24 帧** | `battle_black_field_timing.h` 的 `frames_per_level` / 淡出淡入的级数 | 事件 6 = **24/24/24**（与原版逐位相同） | 中 |
| **W-12** | **开机 → 标题的 8 帧黑**（**不在 `battle_runtime_scene.cpp`**） | 开机/标题路径（`src/main.cpp` + 标题场景）⇒ **需要父代理指定归属** | 帧 **27–34** 应为 0 帧纯黑（原版的开机是淡入） | 低（不在战斗场景里） |

---

## 9. 边界声明
* 逆向线 `D:\Shell\Github\gba-naruto-reverse`：**全程只读**（本波没有打开它）。
* 重制线的改动：**只有** `battle_black_field_star_mask.h` 的一次**已回退**的实验
  ⇒ **本波结束时重制线与 wave 14 的基线逐字节相同**（该文件 13222 B / sha `d8690a71…`）。
* **未改** `battle_runtime_scene.cpp` / `battle_ui_model.h` / `battle_presentation_content.h`
  （W1 独占）、`tools/s49_package/`（W2/W4 独占）。
* **未提交 git**；新文件一律 **LF、无 BOM**。
* **没有伪造任何帧**：所有 PNG 都是 mGBA 帧缓冲的截图（探针的 Lua 帧回调），
  每一张都能在 `build/w3/chain-pinned/shots/` 里找到原图。
* 孤儿进程：见 §6 最后一行的复查结果。
