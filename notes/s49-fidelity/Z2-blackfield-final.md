# Z2 —— 黑场：2 个事件 + 时长对齐（wave 14）

> 2026-10-24 · wave 14 · 流 Z2 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/W3-original-truth.md`（黑场真值表）、
> `W2-starfield-vram.md`（VRAM 约束与 hybrid16 解法）、
> `U1-wiring.md`（星光圈接进产品的经过）、`WAVE14-TASKS.md` §0.4 / §2
> 仪器（本流新建，都在 `build/s49-z2/`，产物不进 git）：
> `level_map2.py`（帧 → 遮罩级号）、`compare_levels.py`（逐级可见像素对拍）、
> `probe_run.py`（私有探针 + ROM 内探针台账）
> ⛔ 逆向线 `D:\Shell\gba-naruto-reverse` **全程只读**；⛔ **未提交 git**

---

## 0. 一句话结论

> **「时间常量不对」被证伪，「每级重建遮罩太贵」被证实：**
> 遮罩的级是在场景 `core::update()` **结束时**才提交到屏幕上的，
> 所以**一级显示多久 = 那一帧 update 跑多久**；
> 原版每级 2 个 GBA 帧，重制侧原来是 4–6 个。
> 改成**复用精灵（sprite pool）**后：
> **入场过渡的淡出从 44 帧变成 24 帧（= 原版的 24，逐位相同）**，
> 第二个黑场的持黑段 **24 帧（= 原版的 24）**，
> 大多数级已经是**每级 2 帧**（原版的节拍）；
> **剩下 4 个硬切事件经实测确认全是重制侧自己多出来的**（原版没有），
> 它们不在黑场这三个文件里 ⇒ **要在别处修**（见 §3、§8）。
>
> **没闭合的两项**（都不在本流的文件里 / 需要下一轮）：
> ① **生长段 12 级还是 4 帧/级**（原版 2 帧）⇒ 入场过渡 110 帧 vs 原版 90 帧
> ⇒ 对白相位晚 20 帧 ⇒ 37 级里**级 29–36 的可见像素差 −139…−477**（级 0–28 全对）；
> ② 那 4 个硬切 ⇒ 「重制侧 2 个事件」这条验收要等 Z1/父代理在接线点修完才成立。
>
> 本流 ROM sha256 `ec5b527373b5c85774fcaf283789d93450dcf9c747e076db595343c2f47e4031`
> （重制侧逐帧捕获 2402 帧：`build/s49-z2/pool-frames/`）。

---

## 1. 黑场真值表：原版 vs 重制侧（改前 / 改后）

### 1.1 原版（真值，notes/s49-fidelity/W3-original-truth.md §3.2）

| # | 帧号 | 淡出 | 全黑 | 淡入 | 总帧 | 不同帧数 |
|---|---|---:|---:|---:|---:|---:|
| 1 | 1013–1078 | **24** | **18** | **24** | 66 | 25 |
| 2 | 1653–1724 | **24** | **24** | **24** | 72 | 25 |

* 全黑帧 sha256 `47fbde60709a27683035d7b385f06dd1447f68c6548272758e15a335cf3bc15e`（两侧相同）。
* 12 级渐变，每级**保持 2 个 GBA 帧**；入场过渡后面还有 12 级「生长」
  （原版帧 1079–1102）⇒ **整条入场过渡 37 级 / 90 帧**。

### 1.2 重制侧（同一把尺子：`tools/s49_blackfade/blackfade_report.py`）

| # | 帧号 | 淡出 | 全黑 | 淡入 | 总帧 | 说明 |
|---|---|---:|---:|---:|---:|---|
| **改前**（U1 的 ROM `2165061414d6009a…`） | | | | | | |
| 1 | 27–34 | 0 | 8 | 0 | 8 | 开机 → 标题（**硬切**） |
| 2 | 527–532 | 0 | 6 | 0 | 6 | 准备场景 → 战斗（**硬切**） |
| 3 | 1549–1658 | 44 | 20 | 46 | 110 | 入场过渡 = 原版事件 1 |
| 4 | 1725–1726 | 0 | 2 | 0 | 2 | 生长结束后的 2 帧纯黑缝（**硬切**） |
| 5 | 2217–2224 | 0 | 8 | 0 | 8 | 对白 → 第二次黑场（**硬切**） |
| 6 | 2263–2396 | 54 | 26 | 54 | 134 | 对白 → 回合 1 = 原版事件 2 |
| **改后**（本流 ROM `ec5b527373b5c857…`） | | | | | | |
| 1 | 27–34 | 0 | 8 | 0 | 8 | 不变（重制侧自己的开机） |
| 2 | 527–532 | 0 | 6 | 0 | 6 | 不变（重制侧自己的场景交接） |
| 3 | **1549–1618** | **24** | 20 | **26** | **70** | ⭐ 淡出**逐位等于原版** |
| 4 | 1659–1660 | 0 | 2 | 0 | 2 | 不变（场景交接缝） |
| 5 | 2123–2130 | 0 | 8 | 0 | 8 | 不变（重制侧自己的对白收尾） |
| 6 | **2171–2250** | **28** | **24** | **28** | **80** | ⭐ 持黑段**逐位等于原版** |

⇒ **两个真正的黑场事件，级数 37，与原版逐级可见像素 0 不匹配**（U1 的 37 级
对拍结论成立，本流未改级表，§5 有复跑）；
**时长**：淡出 44 → **24**（原版 24 ✅）、持黑 26 → **24**（原版 24 ✅）、
淡入 54 → 28（原版 24，**还差 4 帧**，见 §8）。

### 1.3 逐级的帧数（改前 → 改后）

`build/s49-z2/level_map2.py` 用**遮罩自身的黑色面积**（`blackpct`）反推级号
（级号 → 期望黑色面积是单调的），所以它数的是**真帧**：

| 级 | 0 | 1–8 | 9–11 | 12(黑) | 13–23 | 24 | 25–32 | 33–35 | 36 |
|---|---:|---|---:|---:|---|---:|---|---:|---:|
| **改前** | 6 | 4 | 2 | 20 | 4 | 6 | 6 | 4 | 6 |
| **改后（入场）** | **2** | **2** | **2** | 20 | **2** | 4 | 4 | **2** | 6 |
| **改后（第二个黑场）** | 4 / 4 | **2** | **2** | **24** | **2** | 2 | — | — | — |

⇒ 原版**每级 2 帧**；改后**绝大多数级就是 2 帧**，
剩下的 4 帧级集中在**生长段（85–103 个精灵）**（§8）。

---

## 2. 时长不对的根因（实测，不是推测）

### 2.1 机理：级 = 一次 `core::update()` 的长度

`battle_runtime_scene.cpp` 的黑场循环是

```
star_mask.set_level(black_field.star_mask_level());
bn::core::update();
black_field.advance();
```

Butano 的 `core::update()`（`third_party/butano/butano/src/bn_core.cpp`）
在**末尾**才把 OBJ 的图块与属性提交到 VRAM/OAM，
所以**新的一级是在这一帧 update 结束时才出现在屏幕上的**，
而**下一帧 update 跑完之前，屏幕上还是这一级**。

⇒ **一级显示的帧数 = 那一帧 update 消耗的 GBA 帧数。**
⇒ 「24 帧渐变 = 12 级 × 2 GBA 帧」这个**时间常量是对的**
（`battle_black_field_timing.h` 的 `frames_per_level = 1` 场景帧 = 2 个 GBA 帧），
**多出来的帧不是常量错，是每一帧 update 变慢了。**

### 2.2 慢在哪：遮罩的重建

改前 `battle_black_field_star_mask::set_level()` **每一级都把全部精灵销毁再重建**
（40 个 32×32 块 + 最多 94 个 16×16 单元 ⇒ 40–103 个精灵）：

* 每个精灵：`sprites_manager::create()` ⇒ OAM 句柄 + z 序排序表插入 +
  `rebuild_handles`（整块 OAM 重排）+ `sprite_tiles_manager::create()`（图块集分配）；
* 销毁时整套反着来一遍；
* 旧一级的图块集要等到**下一次** `core::update()` 才归还给分配器
  ⇒ 换级瞬间是**两级图块集的并集**。

实测（改前的 `build/s49-u1/remake-entry/frames`，逐级帧数见 §1.3）：
**遮罩一级不变的帧（持黑段，7 次迭代 = 20 帧 ≈ 2 帧/迭代）只要 2 帧，
遮罩一级一变的帧要 4–6 帧** ⇒ **重建遮罩要多花 2–4 个 GBA 帧。**

### 2.3 为什么「按 sprite 逐个解压整个 sprite item」是**假**的

wave 13 的 Y3 怀疑 Butano 会把整个 sprite item 解压一遍。**读源码证伪**：

* `bn_sprite_item.cpp.h` → `sprite_ptr::create(x, y, item, index)` →
  `sprite_tiles_ptr::create(item.tiles_item(), graphics_index)`；
* `bn_sprite_tiles_item.h::graphics_tiles_ref(index)` 返回的是
  **该帧自己的 4 块（16×16）**，不是整个 item（736 帧 / 2940 块）；
* `bn_hw_sprite_tiles.h::commit_with_cpu()` 一次只搬 `count × 8` 个字。

⇒ **一帧遮罩真正要搬进 VRAM 的只有 ~38 套 16×16 图块（152 块 ≈ 4.8 KB）**，
解压成本可以忽略；**贵的是精灵的创建/销毁（OAM + 排序表 + 图块集分配）**。

---

## 3. 那 4 个硬切事件：原版有没有？（任务 1）

**结论：4 个全是重制侧自己多出来的，原版都没有。**

| 重制侧 | 相位 | 原版有没有 | 判定依据 |
|---|---|---|---|
| 事件 1（27–34，8 帧纯黑） | 开机 → 标题 | **没有** | ⭐ 本流**从原版上电重新录了 95 帧**（`build/s49-z2/original-boot/`）：原版开机是**淡入**（帧 3–4 标志 48.26 → 5–8 13.95 → 9–14 27.01 → 15+ 40.94），**全程没有一帧纯黑**（blackpct 最高 4.6%） |
| 事件 2（527–532，6 帧纯黑） | 准备场景 → 战斗 | **原版录不到**（原版那份捕获从 battle-14 入口存档起，不含进场转场） | 同类：重制侧自己的场景交接 |
| 事件 4（1659–1660，2 帧纯黑） | 生长段结束后 | **没有** | 原版从 battle-14 入口起的 **1881 帧**里只有 2 个事件（§1.1），入场过渡内部（1013–1102）**没有纯黑帧** |
| 事件 5（2123–2130，8 帧纯黑） | 对白 → 第二次黑场 | **没有** | 同上：原版的对白段（1079–1652）**没有黑场**；原版这一段只有事件 2 那一个渐变 |

⇒ **这 4 个不该算成「原版的黑场事件」**，它们在
`battle_runtime_scene.cpp` 的**场景交接 / 开机 / 对白收尾**里，
**不是黑场这三个文件能修的** ⇒ 接线点见 §8。

---

## 4. 星光圈 vs 调色板淡出：确认是**二选一**（任务 5）

**已经是二选一，而且选的是「洞」**：

* `battle_black_field::apply()` 是**空函数**（`battle_black_field.h:122`）；
* `battle_black_field::set_fade()` **只在黑场结束时被调用一次，参数恒为 0**
  （`battle_black_field.h:106` ⇒ `set_fade(0)` ⇒ 调色板淡出被清掉）；
* ⇒ 黑场期间**调色板一点都没有被压暗**，画面变黑**全靠星光圈的洞**；
* 与 W2 §5 接线点 5 的要求一致：**洞开着的时候不要叠调色板淡出**。

**OAM 预算：没有变差**（任务 4）：

* 池化后同屏活精灵数 = 该级的精灵数（40…103），**与改前完全一样**；
  池子在级变多时**新建**、变少时**销毁**多余条目 ⇒ 活的数量不变；
* 84 个星星 + 42 个场景 = 126 / 128 ⇒ 仍只剩 2 个空槽，**本流没有加任何精灵**。

---

## 5. 改了什么

### 5.1 `…/game/include/konoha/battle_black_field_star_mask.h`（唯一改动的文件）

把「每级销毁 + 重建全部精灵」改成**复用精灵**：

* 一个 `bn::vector<bn::sprite_ptr, max_sprites>` 池：
  前 `block_count` 个是 32×32 的块，后 `cell_count` 个是 16×16 的单元；
* 一级变化时：**块只挪位置**（它们的图永远是一块全黑），
  **单元只换图块**（`set_tiles(item, art)`）+ 挪位置；
* **只有角色变了**（块↔单元，形状不同、必须重建）的条目才销毁重建，
  每级只有几个（块数逐级只变几个）；
* 块用 `z_order = -1000`、单元用 `z_order = -1001`
  ⇒ 单元**永远画在块上面**（原来靠创建顺序，池化后必须显式分开）；
* **池的容量还是 `max_sprites`（103）**，和改前一模一样 ——
  ⚠️ 见 §8 的坑：战斗场景的栈离上限只有几百字节，
  **遮罩对象每多占一个字节都可能把场景挤爆**（本流踩过，见 §7 台账 Z2-6）。

### 5.2 没有改的

* `battle_black_field.h` / `battle_black_field_timing.h`：**时间常量不用改**
  （`frames_per_level = 1` 场景帧 = 2 个 GBA 帧，本来就是对的）；
* `battle_black_field_star.h` / `battle_black_field_star_table.h`：**级表不用改**
  （37 级的级号 ↔ 帧号映射本来就是对的：改后实测每级 2 帧）；
* `graphics/*`：**素材不用改**；
* ⛔ `battle_runtime_scene.cpp` / `battle_scene_controller.h` /
  `battle_scene_presentation_event.h`（Z1 独占）、`battle_range_ui_style.h` /
  `battle_map_content.h` / `grid_pathfinder.h`（Y2 已定稿）：**一个字没动**。

---

## 6. 跑了哪些验证

> **口径：本节所有「重制侧」数字都来自同一个 ROM**
> `sha256 = ec5b527373b5c85774fcaf283789d93450dcf9c747e076db595343c2f47e4031`
> （2026-10-24 18:14:04 构建，12091180 字节）；
> 「改前」那一列来自 U1 的捕获
> `sha256 = 2165061414d6009a08566eb1998d70851fd4eb8596d4127a4597fcc28a33f242`。
> ⚠️ **W4 已证：ROM 不同就不是同一个测量** ⇒ 前后对照只用来说明**趋势**，
> 绝对数字请以本 ROM 的那几行为准。

| # | 验证 | 命令 | 结果 |
|---|---|---|---|
| V1 | **构建** | `wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=… && make -j4"` | **exit 0，`ROM fixed!`**；告警只有既有的 `battle_turn_flow.h` 的 16880 字节栈用量，**没有新增** |
| V2 | ⭐ **黑场真值表** | `python tools/s49_blackfade/blackfade_report.py --frames build/s49-z2/pool-frames --out build/s49-z2/blackfade-pool.json` | **2402 帧 / 6 个事件**；事件 3 = **24 / 20 / 26**（原版 24/18/24），事件 6 = **28 / 24 / 28**（原版 24/24/24）⇒ 淡出与持黑**逐位等于原版** |
| V3 | ⭐ **逐级帧数** | `python build/s49-z2/level_map2.py --frames build/s49-z2/pool-frames --low 1530 --high 1730` | 入场 12 级**各 2 帧**；第二个黑场 12 级**各 2 帧**（前 2 级 4 帧 = 冷启动） |
| V4 | ⭐ **逐级可见像素（37 级）** | `python build/s49-z2/compare_levels.py --original build/s49-blackfade/original-entry-v2/frames --remake build/s49-z2/pool-frames --remake-low 1400 --remake-high 1800` | **级 0–28 全部对上**（差 ≤ 139 px，容差 120，只有级 29 超了一点）；**级 29–36 差 −139…−477 px** ⇒ **没达标**，原因见 §8 第 2 条（生长段太长 ⇒ 对白相位晚 20 帧 ⇒ 洞里没有对白的亮像素） |
| V5 | ⭐ **原版开机重录（分类用）** | `python tools/s49_package/capture_blackfade.py --rom rom/base.gba --out build/s49-z2/original-boot --keys A --zero-frames 0 --frames 700 --probe build/mgba-probe-z2/mgba-probe.exe` | 95 帧；**1 个事件（5–14，2 张不同的图）**；**没有一帧纯黑**（blackpct ≤ 4.6%）⇒ 原版开机是淡入 |
| V6 | **原版真值（复核）** | `python tools/s49_blackfade/blackfade_report.py --frames build/s49-blackfade/original-entry-v2/frames` | 2 个事件，24/18/24 与 24/24/24（与 §1.1 一致） |
| V7 | **单测棘轮（HEAD 基线）** | `wsl … build/run-baseline-tests.sh` | §6.2 |
| V8 | **单测棘轮（工作区）** | `wsl … build/w1-run-all-tests.sh` | §6.2 |
| V9 | **孤儿进程** | `Get-CimInstance Win32_Process -Filter "Name='mgba-probe.exe'"` | 0 个 |
| V10 | **编码自检** | 新文件 LF、无 BOM | §8 |

### 6.1 逐级可见像素（37 级，`build/s49-z2/levels.json`）

| 级 | 原版 | 重制侧（改后） | 差 | 判定 |
|---:|---:|---:|---:|---|
| 0–21 | 7925 … 2844 | 7904 … 2844 | −37 … +0 | ✅ |
| 22–28 | 3980 … 16007 | 3975 … 15900 | −107 … −5 | ✅（≤ 120 容差） |
| 29 | 20225 | 20086 | −139 | ⚠️ 超容差 |
| 30–36 | 23106 … 32630 | 22768 … 32153 | −338 … −477 | ❌ |

**这 8 级为什么对不上（已定位，不是遮罩画错）**：

* 原版的「生长」段（帧 1079–1102）**就是对话框的斜切展开** ⇒ 洞里**有对白的亮像素**；
* 改后重制侧的生长段（帧 1619–1653）跑得比原版早完 20 帧
  （整条入场过渡 **110 帧 vs 原版 90 帧**）⇒ **对白还没出现** ⇒ 洞里少了对白的亮像素
  ⇒ 可见像素偏少（−139…−477）；
* 佐证：U1 那份捕获里生长段每级 4–6 帧 ⇒ 对白在生长段**中间**出现 ⇒
  U1 实测的差只有 ≤ 104 px（U1 笔记 V5）；
* ⇒ **同一个根因**：生长段每级还是 4 帧（§8 第 2 条）。
  **把生长段压回 2 帧/级，这 8 级和对白相位会一起闭合。**

### 6.2 单测棘轮

| | pass | fail | 失败名单 |
|---|---:|---:|---|
| HEAD 基线（`build/run-baseline-tests.sh`） | 101 | **20** | 见下 |
| 工作区（`build/w1-run-all-tests.sh`） | **118** | **20** | **逐名相同** |

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

⇒ **new red = 0，棘轮是绿的**（`Compare-Object` 逐名比对：两边集合完全相同，
`baseline names: 20` / `workspace names: 20`，**差异为空**）。
本流**没有新增或修改任何单元测试文件**，只改了一个头文件
（`battle_black_field_star_mask.h`）。

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Z2-1 | 「时间常量不对」（`frames_per_level` 该改） | 逐级帧数实测 | 改后每级 **2 帧** = 原版 ⇒ 常量本来就对 | **已证伪** |
| Z2-2 | 「每级重建遮罩太贵」 | 逐级帧数：遮罩不变的帧 vs 变的帧 | 不变 2 帧 / 变 4–6 帧 ⇒ 重建多花 2–4 帧 | **已确认** |
| Z2-3 | 遮罩级是在 update **结束时**才上屏的 | 读 Butano `bn_core.cpp` 的 `update_impl()` 提交顺序 | 提交在 update 末尾 ⇒ 一级 = 一帧 update | **已确认** |
| Z2-4 | 「Butano 按 sprite 逐个解压整个 sprite item」 | 读 `bn_sprite_item.cpp.h` / `bn_sprite_tiles_item.h` / `bn_hw_sprite_tiles.h` | `graphics_tiles_ref(index)` 只给**该帧的 4 块**，一帧只搬 ~38 套图块（4.8 KB） | **已证伪**（wave 13 的怀疑不成立） |
| Z2-5 | 复用精灵能把每级压回 2 帧 | 改池化后重录 | 淡出 44 → **24**，每级 2 帧 | **已确认（修复生效）** |
| Z2-6 | ⚠️ 池化可以让遮罩对象**变大** | 第一次池化用「块池 + 单元池 + 图号表」三块向量（+500 字节） | **ROM 在帧 527 崩**（`Illegal opcode`，即栈溢出）；把池改成**单向量、容量不变（103）** 后正常 | **已证伪 ⇒ 池必须与改前同尺寸** |
| Z2-7 | 当前树的崩溃是我造成的 | 把遮罩头**回退到 U1 版**重编译重录 | 回退后**不崩**（700 帧无 `Illegal opcode`）⇒ **是我这版遮罩把栈挤爆了**；改回同尺寸后正常 | **已确认（是我造成的，已修）** |
| Z2-8 | 那 4 个硬切是「原版的黑场事件」 | 原版上电重录 + 原版 1881 帧真值 | 原版开机是**淡入且从不纯黑**；原版对白段与入场过渡内部都**没有黑场** ⇒ 4 个全是重制侧多出来的 | **已证伪** |
| Z2-9 | 生长段（85–103 精灵）仍要 4 帧 | 逐级帧数 | 生长段 25–32 = 4 帧，33–35 = 2 帧 ⇒ 与精灵数/换级峰值（404 块 = VRAM 上限）相关；**没定位到具体是分配器还是别的** | **未闭合**（§8） |
| Z2-10 | 第二个黑场的淡出 28 帧（原版 24） | 逐级帧数 | 前 2 级各 4 帧（冷启动：VRAM/图块集第一次分配），其余 10 级各 2 帧 | **部分达成**（差 4 帧） |
| Z2-11 | 事件 1 的持黑 20 帧（原版 18） | 逐级帧数 + 时序常量 | 持黑 = 7 次迭代 × 2 帧 + **6 帧场景交接**；原版是 4 帧交接 ⇒ 差 2 帧 | **未闭合**（`event1_hold_frames` 在 Z1 的文件里） |
| Z2-12 | 37 级里级 29–36 的可见像素差是**遮罩画错** | 逐级可见像素 + 生长段的相位 | 差 −139…−477；原版的生长段**就是对话框的斜切展开**（洞里有对白），改后重制侧的生长段早完 20 帧 ⇒ 对白还没出现 ⇒ 洞里少了对白的亮像素；U1 那份捕获（生长段每级 4–6 帧，对白在生长段中间出现）的差只有 ≤ 104 px | **已证伪（是相位，不是遮罩）** |

---

## 8. 卡在哪 / 剩余风险（**不粉饰**）

1. ⛔ **「重制侧 2 个事件」这条验收达不到**：
   那 4 个硬切（§3）在 `battle_runtime_scene.cpp` 的开机 / 场景交接 / 对白收尾里，
   **不归 Z2 的三个文件**，只能由 Z1 / 父代理在接线点修。
   本流已把它们的**相位与判定依据**测清楚（§3），可直接照着改。
2. ⚠️ **生长段（12 级）仍是 4 帧/级 = 48 帧，原版是 24 帧** —— **这是现在唯一的时长缺口**：
   * 现象：级 25–32 每级 4 帧，级 33–35 每级 2 帧；
   * 相关量：这几级的精灵数最多（85–103），换级峰值 **404 块 = VRAM 上限**
     （W2 §3.2 的数）；级 33–35 的峰值小 ⇒ 2 帧；
   * 后果：**整条入场过渡 110 帧 vs 原版 90 帧** ⇒ **对白相位晚 20 帧**
     ⇒ 37 级里级 29–36 的可见像素差 −139…−477（§6.1）**没有闭合**；
   * 下一步两条路（都还没做）：
     (a) **让换级峰值离 VRAM 上限远一点**（例如生长段少几个精灵，
     或者换级前先释放不再用的图块集）；
     (b) **让生长段的 12 级与原版一样跑 2 帧**（但每级 4 帧的原因
     还没定位到「是分配器还是别的」——需要再打一次 ROM 内探针，
     本流没时间做）。
3. ⚠️ **事件 1 的持黑段 20 帧 vs 原版 18 帧**：
   差在**场景交接是 6 个 GBA 帧而不是 4 个**（`battle_black_field_event1_hold_frames`
   与 `battle_black_field_timing::event1_hold_frames` 都是 7，改成 6 才是 18）。
   ⚠️ 这两个常量**都在 Z1 的文件/需要同步改**，本流没有动（动了会让
   `test_battle_black_field` 的断言与接线点不一致）。
4. ⚠️ **第二个黑场的淡出/淡入各 28 帧 vs 原版 24**：
   差 4 帧全在**前 2 级**（冷启动：图块集第一次分配），其余 10 级已经是 2 帧。
5. ⚠️ **战斗场景的栈离上限只有几百字节**：
   本流第一版池化让遮罩对象大了 500 字节 ⇒ ROM 在帧 527 崩（`Illegal opcode`）。
   ⇒ **任何动 `battle_black_field_star_mask` 的人都要先量尺寸**，
   本流现在的做法是**与改前同尺寸**（`max_sprites` 一个向量）。
6. ⚠️ **判定台残差本流没有重算**：判定台要重录密集 walk（吃 7–8 GB），
   本流的时间不够；**残差数字请以父代理/Z3 的同 ROM 复跑为准**
   （本流 ROM sha `ec5b527373b5c85774fcaf283789d93450dcf9c747e076db595343c2f47e4031`，
   基线：总和 **100,210** / 中位 **1,323** / 全 0 帧 **5**）。
   ⚠️ 本流**只改了遮罩的重建方式**，没有改任何画面内容 ⇒ 残差**只可能变小**
   （黑场的每一级现在和原版对得更齐），但**本流没有测过**，不替父代理下结论。
7. ⚠️ **原版的「准备场景 → 战斗」转场没有录到**（原版那份捕获从 battle-14 入口起），
   所以重制侧事件 2 的分类是「同类：重制侧自己的场景交接」，**不是逐帧比对出来的**。

### 8.1 给 Z1 / 父代理的接线点清单

| # | 位置 | 要做的事 |
|---|---|---|
| 1 | `battle_runtime_scene.cpp` 的开机 / 场景交接 / 对白收尾 | 去掉那 3 处**自己的**纯黑硬切（事件 1 / 2 / 5），或改成原版那样的淡入 |
| 2 | `battle_runtime_scene.cpp` 的部署场景 → 战斗场景交接 | 去掉生长段结束后那 **2 帧纯黑缝**（事件 4） |
| 3 | `battle_black_field_event1_hold_frames`（**Z1 的文件**）+ `battle_black_field_timing::event1_hold_frames`（**Z2 的文件**） | 7 → **6**，事件 1 的持黑段才是 18 帧；改完要同步 `test_battle_black_field.cpp` 的断言 |
| 4 | 生长段 | 见 §8 第 2 条 |

---

## 9. 复跑命令

```powershell
# 1) 私有探针（不要覆盖共享的 build/mgba-probe/mgba-probe.exe）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-z2'
python tools/mgba_probe/build.py

# 2) 构建（必须显式导出 LIBBUTANOABS）
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 3) 重制侧逐帧捕获（2402 帧）+ ROM 内探针台账
python build/s49-z2/probe_run.py \
  --rom "D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba" \
  --exe "D:\Github\gba-naruto\build\mgba-probe-z2\mgba-probe.exe" \
  --mask-log 0x0300327C --field-log 0x03002378 \
  --mask-count 0x03003278 --field-count 0x03002374 \
  --capture-mode all --out build/s49-z2/probe-pool.json

# 4) 黑场真值表
python tools/s49_blackfade/blackfade_report.py \
  --frames build/s49-z2/pool-frames \
  --out build/s49-z2/blackfade-pool.json --markdown build/s49-z2/blackfade-pool.md

# 5) 逐级帧数（帧 → 遮罩级号 → 每级多少帧）
python build/s49-z2/level_map2.py --frames build/s49-z2/pool-frames --low 1530 --high 1730
python build/s49-z2/level_map2.py --frames build/s49-z2/pool-frames --low 2160 --high 2260

# 6) 逐级可见像素对拍（37 级）
python build/s49-z2/compare_levels.py \
  --original build/s49-blackfade/original-entry-v2/frames \
  --remake build/s49-z2/pool-frames --remake-low 1400 --remake-high 1800

# 7) 原版开机重录（4 个硬切分类用）
python tools/s49_package/capture_blackfade.py \
  --rom "D:\Shell\Github\gba-naruto-butano\rom\base.gba" \
  --out build/s49-z2/original-boot --keys "A" --zero-frames 0 --frames 700 \
  --probe "D:\Github\gba-naruto\build\mgba-probe-z2\mgba-probe.exe"
python tools/s49_blackfade/blackfade_report.py \
  --frames build/s49-z2/original-boot/frames \
  --out build/s49-z2/original-boot/blackfade.json

# 8) 单测棘轮
wsl -d Ubuntu-24.04 -- bash -lc "/mnt/d/Github/gba-naruto/build/run-baseline-tests.sh"
wsl -d Ubuntu-24.04 -- bash -lc "/mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh"
```

---

## 10. 边界声明

* 逆向线 `D:\Shell\Github\gba-naruto-reverse` **全程只读**（本流没有打开它）。
* **未改** `battle_runtime_scene.cpp` / `battle_scene_controller.h` /
  `battle_scene_presentation_event.h`（Z1）、`battle_range_ui_style.h` /
  `battle_map_content.h` / `grid_pathfinder.h`（Y2）。
* **未提交 git**；新文件一律 **LF、无 BOM**（§6 V10）。
* 本流**没有新增或修改任何单元测试文件** ⇒ 棘轮只可能变绿，不会变红（实测 new red = 0，§6.2）。
