# Y2 —— 「開始」标题屏 + 黑场渐变补全

> 2026-10-24 · wave 6 · 流 Y2 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/WAVE6-TASKS.md` §3、`W3-original-truth.md`（黑场真值表）、
> `X2-pairing.md`（配对表）、`Q-unit-test-baseline.md`（单测基线）
> 工具：`tools/s49_opening_title/project_title_residual.py`（新）、
> `tools/s49_blackfade/blackfade_report.py`（只读复用）、
> `tools/s49_package/capture_blackfade.py`（只读复用）
> ⛔ **未改** `game/src/battle_runtime_scene.cpp`（Y1 独占）⇒ 接线点写成清单交给父代理
> ⛔ 逆向线 `D:\Shell\Github\gba-naruto-reverse` 全程只读；⛔ **未提交 git**

---

## 0. 一句话结论

> **黑场：重制侧现在有「淡出 / 全黑 / 淡入」三段，单侧渐变实测 24 帧 = 12 级 × 2 GBA 帧，
> 与原版完全一致，全黑帧 sha256 仍是 `47fbde60…`；但验收口径只差一处 —— 跨场景交接还留
> 2 帧亮缝（原版是一个连续事件），需要 Y1 把战斗场景的淡入提前到场景首帧。
> 标题屏：把原版的「開始」书法字真值（两枚字 + 4 级灰阶 + 精确坐标）抽了出来，
> **投影残差 5,869 → 264、4,699 → 333（降 95.5 % / 92.9 %）**，
> 但画面尚未接进重制侧（接线点在 Y1 的文件里）。
> ⭐ 顺带修正一条上游前提：原版的「淡出/淡入」**不是亮度渐变，是四角星形状的光圈收缩/扩张**
> （见 §2.1），所以「只要补渐变段、颜色不用改」这句前提不成立。**

---

## 1. 交付物

| 路径 | 性质 | 说明 |
|---|---|---|
| `butano-sequel/game/include/konoha/battle_black_field_timing.h` | **新** | 黑场状态机（无引擎依赖，主机单测可测）：12 级梯、每级 1 场景帧、跨场景交接的 `black` 阶段 |
| `butano-sequel/game/include/konoha/battle_black_field.h` | **改** | X1r 的稿子重写：接上 timing、调色板侧、交接期间**不释放**淡出 |
| `butano-sequel/game/include/konoha/battle_opening_title.h` | **新** | 「開始」标题屏规格（字形坐标 / 4 级灰阶 / 相位机） |
| `butano-sequel/game/tests/test_battle_black_field.cpp` | **新** | 黑场时序单测（24 帧渐变 / 18 帧全黑 / 交接不释放） |
| `butano-sequel/game/tests/test_battle_opening_title.cpp` | **新** | 标题屏规格单测 |
| `tools/s49_opening_title/project_title_residual.py` | **新** | 从原版帧里抽标题真值 + **投影残差**（判决仪器） |
| `tools/s49_opening_title/{kai,shi,kai-phase1,shi-phase1}.png` | **新** | 抽出的字形美术（RGBA，4 灰阶 + 透明） |
| `notes/s49-fidelity/Y2-opening-title-blackfade.md` | **新** | 本报告 |

---

## 2. 任务 B：黑场（G6）

### 2.1 ⭐ 真相修正：原版的「淡出/淡入」是**四角星光圈**，不是亮度渐变

W3 §3.2 把原版的两段记成「淡出 24 帧 / 全黑 18–24 帧 / 淡入 24 帧」，
并给出了逐帧均值。任务书据此推论「只要补渐变段，**颜色不用改**」。
**本流实测：颜色必须改 —— 原版根本没有亮度渐变。**

证据（`build/s49-blackfade/original-entry-v2/frames/`）：

| 帧 | 画面 |
|---|---|
| `frame-01012.png` | 一个**很大的四角星窗口**，窗口里是全亮的战场（绿草地），窗口外全黑 |
| `frame-01013.png` | 星窗口**缩小**一档 |
| `frame-01021.png` | 星窗口只剩中间一小块 |
| `frame-01037.png … 01054.png` | 纯黑（唯一色 `(0,0,0)`） |
| `frame-01065.png` | 淡入侧：星窗口**重新变大** |

⇒ **原版的黑场 = 一个四角星光圈的收缩（12 级 × 2 帧）→ 全黑（9/12 级）→ 扩张（12 级 × 2 帧）**。
窗口里的画面**始终是全亮的**（窗口内的像素与标题屏同亮度），
逐帧均值下降只是因为**可见面积**在缩小。
W3 §3.4 那句「黑帧里有一颗黄色四角星闪光」说的也是同一个四角星。

⇒ 后果：
* 重制侧**不可能**用调色板淡出复现原版的逐帧均值曲线
  （原版曲线是 `33.3, 27.8, 19.9, 15.9, 9.2, 6.5, 4.0, 2.9, 1.2, 0.6, 0.3, 0.1`，
  是**面积**函数；GBA 的 32 级线性调色板淡出在 32 步里只剩 7 级可区分的暗阶）。
* 真正的 1:1 复现需要**星形遮罩**（BG 覆盖层 + 对角边 tile 集，或多枚 sprite 拼角），
  这是一个独立的图形子任务，**本流没有做**（见 §6）。
* 本流交付的是**结构等价**的版本：调色板淡出，12 级 × 2 GBA 帧 = 24 帧渐变，
  全黑帧仍是纯黑。判决表的三段结构、级数、每级帧数全部对齐。

### 2.2 改了什么

X1r 的稿子（`battle_black_field.h`，5,799 B，未验证）实测有 **4 个问题**：

| # | 问题 | 实测证据 | 修法 |
|---|---|---|---|
| B1 | **渐变被压成 5 级** | 旧的 alpha 梯 `{5,9,15,18,22,24,26,27,28,29,29,29}` 里 `29` 重复 3 次 | 换成 12 级单调梯（`25…31`），相邻级可区分 |
| B2 | **每级 4 GBA 帧**（应为 2） | 旧的可见级在 `1471,1475,1479,…`（4 帧一跳） | `frames_per_level` 2 → 1 ⇒ 可见级在 `1471,1473,1475,…`（2 帧一跳） |
| B3 | **淡出/淡入被拆成两个事件**（中间 4 帧亮屏） | 旧捕获：事件 3 = `1479…1518`，事件 4 = `1547…1578`，中间 `1519…1546` 是亮屏 | `clear()` 不再释放淡出；交接期间画面保持全黑 |
| B4 | **全黑段过长**（48 帧，原版 24） | 旧捕获：事件 6 = 28 / 48 / 14 | 持黑帧数改到 12 场景帧 = 24 GBA 帧（**待 Y1 改常量**） |

新捕获（`build/s49-blackfade/remake-entry-y2b/blackfade.json`）：

| 事件 | 淡出 | 全黑 | 淡入 | 全黑帧 sha256 | 原版对应 |
|---|---:|---:|---:|---|---|
| 3（部署 → 战斗） | **24** | 26 | — | `47fbde60…` | 原版事件 1：24 / 18 / 24 |
| 4（战斗场景首帧） | — | 8 | **24** | `47fbde60…` | 同上（**仍被 2 帧亮缝切开**） |
| 5（对白 → 回合 1） | — | 56 | **24** | `47fbde60…` | 原版事件 2：24 / 24 / 24 |

* 淡出段实测级位置：`1471, 1473, 1475, 1477, 1479, 1481, 1483, 1485, 1487, 1489, 1491, 1493`
  ⇒ **12 级 × 2 GBA 帧 = 24 帧**，与原版逐项一致 ✔
* 淡入段同样 24 帧 ✔
* **全黑帧 sha256 两侧完全相同**：`47fbde60709a27683035d7b385f06dd1447f68c6548272758e15a335cf3bc15e` ✔
* 淡出/淡入的**绝对亮度**现在也对齐了原版的首级（原版首级均值 33.3，重制首级 33.5）：
  梯首从 alpha 10 改成 **25**（原来 10 → 105.2，落在判决工具「暗帧」阈值 40 之上，
  工具会把前 5 级**当正常帧丢掉**，于是报告只数出 14 帧而不是 24 帧）。

### 2.3 还没做到的

* **事件 3/4 仍然是两个事件**（中间 2 帧亮屏 `1521…1522`）。
  原因**不是** `clear()`（已改成不释放）：实测证明**场景交接时调色板被重新提交，
  全局淡出会被丢掉** —— 淡出必须每帧 `apply()` 才活着。
  ⇒ 修法在 Y1 的文件里：把战斗场景的淡入块**挪到场景第一帧之前**（见 §5 接线点 3）。
* 全黑段仍是 26 / 56 帧（原版 18 / 24），因为持黑常量还在 Y1 的文件里（§5 接线点 1、2）。
* 真正的**四角星光圈**未实现（§6）。

---

## 3. 任务 A：「開始」标题屏（G2）

### 3.1 原版真值（抽出来的）

`tools/s49_opening_title/project_title_residual.py` 从原版密集 walk 帧里抽：

| 项 | 真值 |
|---|---|
| 绘制方式 | **OBJ sprite**（标题拍与前一拍的 `DISPCNT=0x1940`、`bg_cnt=[9,7,514,56]`、相机完全相同 ⇒ 背景没变，标题是叠在战场上的 sprite） |
| 「開」 | 屏幕框 **(41, 49) 59×62** |
| 「始」 | 屏幕框 **(135, 42) 63×70** |
| 调色板 | **4 个不透明色，全是灰阶**：RGB5 `4 / 13 / 22 / 31`（8 位展开后正好是 `33 / 107 / 181 / 255`） |
| 在场时间 | 密集 walk 的 **帧 185 … 232**（48 GBA 帧），到玩家确认为止（walk 的下一次确认正好落在 232） |
| 动画 | 「開」在 185→189 之间长出来后**保持不变**；「始」**持续微闪**（细于密集 walk 的 4 帧采样 ⇒ 要 1:1 需要逐帧重抓原版） |

### 3.2 投影残差（判决仪器）

`python tools/s49_opening_title/project_title_residual.py --original-dir build/s49-pairing/walk5/dense-original --remake-dir build/s49-pairing/walk5/dense-remake --out build/s49-opening-title`

| 量 | 像素 |
|---|---:|
| 原版标题屏 vs 重制侧同相位画面（现状） | **5,869** |
| 原版**无标题**帧 vs 重制侧同相位画面 | 1,104 |
| **投影：把抽出的字画到重制侧战场上的同一位置后** | **264** |
| 投影：第二个动画相位 | **333** |
| 原版标题拍 vs 下一拍（标题自身的动画量） | 2,247 |

⇒ **把标题画对，残差从 5,869 / 4,699 降到 264 / 333（−95.5 % / −92.9 %）。**
剩下的 ~300 px 是**重制侧战场自身的差**（小鸟的动画帧 + 约 225 px 其它差），
不是标题造成的 —— 也就是说 **0 附近是可达的**，但需要逐帧对齐小鸟动画。

### 3.3 还没做到的

* **画面还没接进重制侧**：素材还没转成 Butano sprite item，
  `battle_runtime_scene.cpp` 又归 Y1 ⇒ 接线点见 §5。
* 素材**没有**放进 `graphics/`：那会改变 ROM 的 VRAM 占用，
  一旦爆掉会把 **Y1 的构建一起弄挂**，本流不敢赌 ⇒ 素材先放
  `tools/s49_opening_title/*.png`，由 §5 接线点 4 的生成步骤落到 `graphics/`。
* 「始」的微闪相位只有 2 帧被抽到（密集 walk 4 帧采样）⇒ 需要逐帧重抓原版。

---

## 4. 跑了哪些验证

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| Y2-V1 | `python tools/s49_blackfade/blackfade_report.py --frames build/s49-blackfade/remake-entry-y2b/frames …` | 三段 + 级数 + 每级帧数 | 事件 3 = **24 / 26 / —**、事件 4 = **— / 8 / 24**、事件 5 = **— / 56 / 24**；淡出级在 `1471,1473,…,1493`（**12 级 × 2 帧**） |
| Y2-V2 | 同上，看全黑帧 sha256 | 两侧相同 | `47fbde60709a27683035d7b385f06dd1447f68c6548272758e15a335cf3bc15e` ✔ |
| Y2-V3 | `python tools/s49_opening_title/project_title_residual.py …` | 残差从 5,869 / 4,699 降 | **264 / 333**（−95.5 % / −92.9 %） |
| Y2-V4 | WSL 构建（`make -j4`，显式 `LIBBUTANOABS`） | 构建通过 | **ROM fixed!**（exit 0） |
| Y2-V5 | `g++ -std=c++23 -Wall -Wextra -Werror -pedantic` 跑两个新单测 | 通过 | `TEST-BLACK-FIELD: PASS`、`TEST-OPENING-TITLE: PASS` |
| Y2-V6 | `bash build/run-baseline-tests.sh`（HEAD 基线） | 20 项预存债 | `pass=101 fail=20`，失败名单见 §4.1 |
| Y2-V7 | `bash build/w1-run-all-tests.sh`（工作区） | 失败集合与基线**逐名相同** | 见 §4.1 |
| Y2-V8 | `python tools/s49_blackfade/blackfade_report.py` 对**原版**捕获复核 | 真值表不变 | 原版仍是 24/18/24 与 24/24/24 ✔ |
| Y2-V9 | 孤儿进程检查 | 0 个 | `Win32_Process` → `mgba-probe.exe` **count=0** |
| Y2-V10 | 编码自检 | 新文件 LF、无 BOM | 6 个新文件全部 `BOM=False CRLF=0`（见 §7） |
| Y2-V11 | `git status --short`（重制线） | 未提交、不碰 Y1 的文件 | 见 §7 |

### 4.1 单测棘轮（**当前是红的，但红的不是 Y2**）

**HEAD 基线（`build/run-baseline-tests.sh`）**：`pass=101 fail=20`，失败名单：

```
test_battle_all_scenario_runtime      test_battle_campaign_route
test_battle_campaign_save             test_battle_campaign_scenario_42
test_battle_campaign_scenario_43       test_battle_campaign_scenario_44
test_battle_campaign_scenario_45       test_battle_campaign_scenario_46
test_battle_campaign_scenario_47       test_battle_campaign_scenario_49
test_battle_dynamic_deployment_turn    test_battle_material_pickups
test_battle_presentation_controller    test_battle_runtime_scene_gate
test_battle_s49_input_flow             test_battle_s49_opening
test_battle_scene_character_actions    test_battle_scene_controller
test_battle_scene_multi_unit           test_battle_scene_results
```

**工作区（`build/w1-run-all-tests.sh`）**：`pass=104 fail=24`，
多出的 **4 项**是：

```
test_battle_map_loader        test_battle_runtime_grid
test_battle_terrain_traversal test_production_primitives
```

⚠️ **这 4 项不是 Y2 造成的**（两条独立证据）：

1. **包含图证据**：Y2 的三个头文件
   （`battle_black_field.h` / `battle_black_field_timing.h` / `battle_opening_title.h`）
   **只被** `game/src/battle_runtime_scene.cpp`（GBA 构建）和 Y2 自己的两个单测包含；
   那 4 个单测包含的是 `grid_pathfinder.h` / `battle_map_loader.h` /
   `battle_terrain_traversal.h` / `battle_action_system.h`，**一个 Y2 文件都不碰**。
2. **diff 证据**：工作区里 `game/include/konoha/grid_pathfinder.h` 被**并行流**改过
   （`cost()` 现在对非 plain 地形类返回 0 ⇒ 可达集变了 ⇒ 那 4 个网格/地形单测全红）；
   `test_battle_runtime_scene_gate` 的编译失败则是 Y1 改 `battle_session.h`
   导致 `sizeof(battle_scene_snapshot<12>)` 从 ≤1120 涨到 1672。

⇒ **Y2 的净贡献 = 0 项新增失败**，新增的 2 个单测
（`test_battle_black_field`、`test_battle_opening_title`）**通过**。
⇒ 但按验收口径「失败集合与 HEAD 基线逐名相同」，**当前棘轮是红的**，
需要 Y1/Y3 落地后**重跑一次**棘轮再判定。

⚠️ **ROM 口径**：本报告的黑场数字绑定在 **ROM sha `68d74179…`**（本流 07:05 构建、
07:12 捕获）。**Y1 在 07:17:57 又重建了一次**（ROM sha `a7d903d7…`），
所以**合并后必须按 §8 重录一次**再取数。黑场逻辑本身在 Y2 独占的头文件里，
不受 `.cpp` 的并行改动影响，但帧号会整体平移。

⇒ **孤儿进程**：本流结束时 `Win32_Process` 里查出 **1 个残留 `mgba-probe.exe`**
（探针客户端被杀后子进程继续吃 CPU，W3 §1.1 的老坑），已清掉，复查为 **0 个**。



---

## 5. 接线点清单（交给父代理串行合进 `battle_runtime_scene.cpp`）

> 行号基于 **2026-10-24 07:08:30** 的 `battle_runtime_scene.cpp`（Y1 可能还在改，请按符号名定位）。
> ⚠️ `battle_black_field.h` / `battle_opening_title.h` 已就位，**只需接线**。

### 接线点 1 —— 黑场事件 1 的持黑帧数（**必做**）

* 位置：`battle_runtime_scene.cpp:189`
  `constexpr int battle_black_field_event1_hold_frames = 10;`
* 改成 **7**（或直接用 `battle_black_field::event1_hold_frames`）。
* 理由：原版事件 1 的全黑段是 **18 GBA 帧 = 9 场景帧**；
  部署场景持黑 7 场景帧 + 场景交接的 2 场景帧 = 9 场景帧 = 18 GBA 帧。
* 现在的实测值：全黑 26 帧（原版 18）。

### 接线点 2 —— 黑场事件 2 的持黑帧数（**必做**）

* 位置：`battle_runtime_scene.cpp:190`
  `constexpr int battle_black_field_event2_hold_frames = 24;`
* 改成 **12**（或直接用 `battle_black_field::event2_hold_frames`）。
* 理由：原版事件 2 的全黑段是 **24 GBA 帧 = 12 场景帧**。
* 现在的实测值：全黑 56 帧（原版 24）。

### 接线点 3 —— 战斗场景的淡入必须从**场景第一帧**开始（**必做，消掉 2 帧亮缝**）

* 位置：`battle_runtime_scene.cpp:7935-7943`（`battle_black_field fade_in; … begin_fade_in(); …`）
* 改法：把这个块**上移**到战斗场景 `bn::core::update()` 第一次出现之前
  （当前在场景搭建里的 `bn::core::update()` 之前的那段，见 `battle_runtime_scene.cpp:7713` 附近）。
* 理由（实测）：**场景交接时调色板会被重新提交，全局淡出会被丢掉** ——
  淡出只有每帧 `apply()` 才活着。所以淡入块必须覆盖场景搭建的头几帧，
  否则 `1521…1522` 会露出全亮的战场，把一个黑场事件切成两个。
* 备选（不改位置）：让部署场景在交接期间**每帧**重新 `apply()` 一次全黑（需要交接钩子，改动更大）。

### 接线点 4 —— 「開始」标题屏（任务 A）

* 新增文件已在位：`game/include/konoha/battle_opening_title.h`
  （`battle_opening_title::glyphs` = 两枚字的屏幕框，`outline_shades` = 4 级灰阶，
  `on_screen_frames = 48`，`phase_count = 2`）。
* 素材在 `tools/s49_opening_title/{kai,shi,kai-phase1,shi-phase1}.png`（RGBA，4 灰阶 + 透明）。
* 步骤：
  1. 用 `tools/s49_opening_title/project_title_residual.py` 产出的 PNG 转成 Butano sprite 资源
     （`graphics/battle_opening_title_kai.bmp` + `.json`，`.json` 形如 `{"type":"sprite","height":64}`；
     「始」高 70 > 64，**要拆成两枚 64 高 + 一枚余条**）。
  2. **先确认 VRAM 余量**再放进 `graphics/`（本流故意没放，怕把构建弄挂）。
  3. 在部署场景里：`deployment.complete()` 成立时，**不要**画 READY 文本，
     改画标题 sprite（`battle_opening_title::glyphs` 的坐标），等玩家按 A；
     玩家确认后再走 `battle_black_field` 的黑场。
* 位置：`battle_runtime_scene.cpp:7107` 的 `render_deployment_text()`
  （标题期间要跳过 `… DEPLOY` / `START` / `READY` / `A:OK B:BACK` 四行 ——
  原版那个位置**没有文字**，投影里就是靠抹掉这 631 px 才把残差压到 264 的）；
  以及 `battle_runtime_scene.cpp:7361` 附近的 `deployment.complete()` 分支
  （标题 → 玩家确认 → 黑场）。
* 判据：重录后判定台 step-09 / step-10 的残差应降到 **≈264 / ≈333**（投影值）。

### 接线点 5 —— （可选）四角星光圈

* 见 §2.1：真正的 1:1 需要星形遮罩，不是调色板淡出。
* 本流**没有**实现；如果要做，需要新开一个图形子任务（BG 覆盖层 + 对角边 tile 集）。

---

## 6. 卡在哪 / 遗留风险

1. **⭐ 原版的黑场是四角星光圈，不是亮度渐变**（§2.1）。
   本流交付的是**结构等价**（三段 / 12 级 / 每级 2 GBA 帧 / 全黑帧 sha256 相同），
   **逐帧均值曲线与原版不同**。要 1:1 必须实现星形遮罩 ⇒ 独立的图形子任务。
2. **跨场景交接仍有 2 帧亮缝**（§2.3）⇒ 需要接线点 3。
3. **全黑段长度仍不对**（26 / 56 vs 原版 18 / 24）⇒ 需要接线点 1、2。
4. **标题屏没有接进重制侧**（§3.3）⇒ 需要接线点 4；素材的 Butano 转换与 VRAM 余量未验证。
5. **「始」的微闪只有 2 个相位被抽到**（密集 walk 4 帧采样）⇒ 1:1 需要逐帧重抓原版；
   `tools/s49_package/capture_blackfade.py` 的只读 Lua 可以干这件事（`MGBA_W3_CAPTURE=all`）。
6. **判决工具的「暗帧」阈值（均值 < 40）是绝对亮度** ⇒ 淡出梯首被钉在 alpha 25，
   这是为了让 12 级全部落在阈值下；如果重制侧该相位的画面整体变亮，梯首要重新校准。
7. **X1r 的 `battle_runtime_scene.cpp` 接线我一行没改**（Y1 独占）；
   本流只改了 `battle_black_field.h`（自己独占），并把需要改的地方写成清单。
8. **本流期间 Y1 在并行改 `battle_runtime_scene.cpp`（07:08:30 还在动）** ⇒
   §5 的行号可能漂移，按符号名定位。

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Y2-1 | X1r 的 `battle_black_field.h`（5,799 B）已成稿且可用 | 读代码 + 构建 + 逐帧捕获 | 稿子能编译能跑，但**有 4 个问题**（B1 渐变被压成 5 级、B2 每级 4 帧、B3 拆成两个事件、B4 全黑段过长） | **已证伪（已修）** |
| Y2-2 | 黑场的 12 级是**亮度**台阶 | 把原版捕获的每一帧当图看 | 原版是**四角星光圈**收缩/扩张，窗口内亮度不变 | **已证伪（真相修正）** |
| Y2-3 | 1 个黑场场景帧 = 2 个 GBA 帧 | 逐帧比对亮度台阶的位置 | 旧码 4 帧一跳 ⇒ 2:1；改 `frames_per_level` 1 后变 2 帧一跳 ⇒ **2:1 确认** | **已确认** |
| Y2-4 | 淡出/淡入各 24 GBA 帧（12 级 × 2） | 捕获后看报告的 `fade_out_frames` | 24 ✔（改梯首前只有 14，因为前 5 级落在「暗帧」阈值之上） | **已确认** |
| Y2-5 | 全黑帧两侧 sha256 相同 | 读报告的 `first_black_sha256` | `47fbde60…`，与原版逐字节相同 ✔ | **已确认** |
| Y2-6 | 交接处的 4 帧亮缝是 `clear()` 造成的 | 把 `clear()` 改成不释放 → 重录 | **仍然有 2 帧亮缝** ⇒ 真正原因是**场景交接时调色板被重新提交，全局淡出丢失** | **已证伪（已定位）** |
| Y2-7 | 「開始」标题是 **sprite**（不是 BG） | 比对标题拍与前一拍的 `DISPCNT` / `bg_cnt` / 相机 | 全部相同 ⇒ 背景没变，标题是叠上去的 OBJ | **已确认** |
| Y2-8 | 标题屏的残差可以靠「画对字」消掉 | 投影：把抽出的字画到重制侧战场同位置 | 5,869 → **264**、4,699 → **333** ⇒ **可以消掉 93–96 %** | **已确认** |
| Y2-9 | 标题在等玩家确认 | 密集 walk 里标题的起止帧 vs 确认键的拍点 | 标题在帧 185…232，下一次确认正好落在 232 ⇒ 等确认 | **已确认（旁证）** |
| Y2-10 | 重制侧该相位的画面除标题外与原版一致 | 原版无标题帧 vs 重制侧同相位 | 差 1,104 px，其中 631 px 是重制侧自己的 `DEPLOY/START` 文字、248 px 是小鸟动画帧 | **已确认** |
| Y2-11 | 素材进 `graphics/` 不会撑爆 VRAM | — | **没验**：本流故意没放素材进 `graphics/`，怕把 Y1 的构建一起弄挂 | **未验（交给接线点 4）** |
| Y2-12 | 单测棘轮不多不少 | HEAD 基线 vs 工作区 | 基线 20 失败；工作区 24 失败，**多出的 4 项全是网格/地形族**（`map_loader` / `runtime_grid` / `terrain_traversal` / `production_primitives`），根因是并行流改的 `grid_pathfinder.h`（Y2 的头文件只被 `battle_runtime_scene.cpp` 和 Y2 自己的单测包含）⇒ **Y2 净贡献 0 项**，但棘轮当前为红 | **已确认（归因清楚，棘轮待 Y1/Y3 落地后重跑）** |
| Y2-13 | 本流的 ROM 口径还成立吗 | 捕获收据的 `rom_sha256` vs 当前 ROM | **不成立**：捕获绑 `68d74179…`，Y1 在 07:17:57 重建成了 `a7d903d7…` ⇒ 合并后要重录 | **已确认（已写进报告口径）** |

---

## 8. 复跑命令

```powershell
# 0) 私有探针（不要覆盖共享的 build/mgba-probe/mgba-probe.exe）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-y2'
python tools/mgba_probe/build.py

# 1) 构建（WSL，必须显式导出 LIBBUTANOABS）
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 2) 逐帧捕获重制侧黑场
python tools/s49_package/capture_blackfade.py \
  --rom D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba \
  --out build/s49-blackfade/remake-entry-y2b \
  --keys "Down,Down,A*22" --zero-frames 240 --hold-frames 4 --settle-frames 90 --frames 2552 \
  --probe D:\Github\gba-naruto\build\mgba-probe-y2\mgba-probe.exe

# 3) 黑场真值表
python tools/s49_blackfade/blackfade_report.py \
  --frames build/s49-blackfade/remake-entry-y2b/frames \
  --out build/s49-blackfade/remake-entry-y2b/blackfade.json \
  --markdown build/s49-blackfade/remake-entry-y2b/blackfade.md

# 4) 标题屏投影残差
python tools/s49_opening_title/project_title_residual.py \
  --original-dir build/s49-pairing/walk5/dense-original \
  --remake-dir build/s49-pairing/walk5/dense-remake \
  --out build/s49-opening-title

# 5) 单测棘轮
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh
```
