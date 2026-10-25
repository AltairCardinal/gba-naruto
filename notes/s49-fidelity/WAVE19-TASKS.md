# WAVE19-TASKS —— wave 19 任务书（四路并行）

> 创建：2026-10-25 00:55 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/W18-W1-stack-overflow.md`（⭐ D4 已闭合）·
> `W18-W2-confirm-yes-unselectable.md` · `W18-W3-black-fade.md` ·
> `W18-W4-settlement-tail.md`（**该笔记缺失，见 §0.4 的交接**）·
> `W18-W5-walk-divergence.md` ·
> `W18-PARENT-residual-structure.md` · `W18-PARENT-stack-copies.md` ·
> `W18-PARENT-ratchet-red.md`
> 上一波任务书：`notes/s49-fidelity/WAVE18-TASKS.md`

---

## 0. 本波目标

### 0.1 ⭐⭐ wave 18 已经拿下的东西（**已接线进共享树并已验证**）

| 项 | 结果 |
|---|---|
| ⭐ **D4（栈溢出）** | **真打赢仗了**：`v1_battle.py --use-tools` ⇒ `bee_hp_dropped: true`（5 只蜂各掉 25 HP）、`escort_hp 40→40`、`from_real_battle: true`、**`poke_commands: 0`**、已进入结算链 |
| ⭐ 栈深 | 最坏 **26,888 → 14,944 B ≤ 21,308 B**（裕量 6,364）；`resolve_battlefield_object_event` 无独立帧；`advance_empty_side` 16,880 → **120**；`combinations::resolve` 9,504 → **1,456**；`preview_area` 5,864 → **720** |
| ⭐ 写监视点自证 | `IRQ_VectorTable[0]` **未命中**，IRQ 表前后逐字节相同，`sp=0x03004D68`（原来低 940 B） |
| ⭐ 黑场 B1 | 开机纯黑 **8 → 2 帧**，整条 walk 帧号**零漂移** |
| ⭐ 棘轮 | 父代理已回退 U2 的错误规则 ⇒ **pass=118 / fail=20**，零新增红 |
| 共享树 ROM | sha `db676a638acd15d07b66f447750a873ee98ae32fa5bf5cedc0c20ecb9fd69438`（2026-10-25 00:49 构建） |

### 0.2 ⭐ 本波要打的四个目标

| 流 | 主题 | 为什么是它 |
|---|---|---|
| **A** | ⭐⭐ **「開始」标题卡语义** | **判定台残差的 75.4 %（82,571 px）卡在这里**（W5 已定位） |
| **B** | ⭐ **結算链后半段**（戰後對白 26,819 + 任務菜單 37,694 + 人物 1,898） | 直接像素残差 |
| **C** | ⭐ **黑场 B2/B3/B4 + 开机纯白 + 事件 6 淡入** | 玩家看得见的画面 |
| **D** | ⭐⭐ **真实打完仗的结算链采集与逐屏对照** | wave 17 起 1:1 报告一直缺「真实战斗链」；**现在能真打赢仗了** |

### 0.3 文件归属（互斥，越界 = 违规 ⇒ 写「接线请求」交父代理）

| 流 | 独占文件 |
|---|---|
| **A** | `game/include/konoha/battle_opening_title.h`、`game/src/battle_runtime_scene.cpp` |
| **B** | `game/include/konoha/battle_result_content.h`、`battle_presentation_content.h`、`battle_ui_model.h`、`graphics/**`（**真实目录**）、`tools/s49_w19b/**` |
| **C** | `game/include/konoha/battle_visual_resource_coordinator.h`、`battle_black_field_star_mask.h`、`battle_black_field_timing.h`、`battle_black_field.h`、`game/src/battle_preparation_scene.cpp`、`src/main.cpp`、`tools/s49_w19c/**` |
| **D** | `tools/s49_w19d/**`（**只做仪器，不改任何重制线产品文件**） |

> ⚠️ **`game/src/battle_runtime_scene.cpp` 归 A 独占。**
> B 与 C 若需要改它 ⇒ **不要改**，写进笔记的「接线请求」一节
> （要改哪个文件的哪一行、改成什么、为什么），由父代理转交 A 执行。
> ⚠️ `battle_black_field.h` **归 C**（wave 18 的 W3 改过它，已接线进共享树）。

### 0.4 W4 的交接（**它的笔记没写成，这是父代理转述的原始日志**）

W4 在 wave 18 末被截断，**没写笔记、没改代码**，但它的分析日志里有**可用的根因**：

> 1. ⭐ **「every working screen-sized layer in this codebase is created at `(8, 48)`,
>    but the settlement renderer uses `(0, 0)`」** ⇒ 結算/对白屏的 26,819 px **很可能是纯定位错**。
> 2. 原版对白屏 = **3 层 BG**：`_bottom` = 森林+肖像 行 8–87、`_middle` = 空、`_top` = 框+文字 行 96–159。
> 3. 重制侧 `graphics/` 里的对白资产是 **256×256 的 8bpp 图层**；
>    **assets 3/4/5 的场景层与原版第 2 页 0 px 精确匹配** ⇒ 资产本身大部分是对的。
> 4. 重制侧的 `dialogue_1` 资产画的是**卡卡西**，而原版真值是**鸣人** ⇒ **页选错了**。
> 5. 项目**没有 `.butt` 文件**，图形走**自定义 loader** ⇒ 资产格式要照现有 240×160 8bpp 资产对齐。
> 6. 任務菜單：原版侧是**自上而下的地图 + 两个文字面板**；重制侧地图资源**已被释放**
>    （`bn::core::update()`），W4 已存 `map-bottom.json` / `orig-taskmenu-timeline.txt` / `orig-pages/`。

⇒ B 路**直接用上面 6 条**，不要从零重查。

### 0.5 隔离副本（各路只在自己的副本里改和构建）

| 流 | 副本根 |
|---|---|
| A | `D:\Github\gba-naruto\build\w19-a\butano-sequel` |
| B | `D:\Github\gba-naruto\build\w19-b\butano-sequel`（`graphics/` 是**真实目录**） |
| C | `D:\Github\gba-naruto\build\w19-c\butano-sequel` |
| D | `D:\Github\gba-naruto\build\w19-d\butano-sequel`（**只构建，不改源码**） |

构建命令（把 `w19-x` 换成你的流）：
```
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Github/gba-naruto/build/w19-x/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"
```
⚠️ **本机构建非字节可复现** ⇒ 一切测量绑定**你自己那份 ROM 的 sha**。
⚠️ **禁止**在共享树 `D:\Shell\Github\gba-naruto-butano\butano-sequel` 里改文件或构建。

### 0.6 全波共同纪律

1. **一次只改一处，跑一次，记一行。**
2. **一次尝试必须能回答一个「是/否」问题。**
3. **连续 3 次同样结果 ⇒ 停**，写进台账，换方法。
4. **结论落进假设台账**（假设 / 判定方法 / 结果 / 状态=未验·已证伪·已确认）。
5. **新写文件一律 LF、无 BOM**；**不提交 git**。
6. **逆向线 `D:\Shell\Github\gba-naruto-reverse` 全程只读。**
7. ⛔ **改含中文的源文件一律用 `edit`/`write` 工具**，**不要用 PowerShell 的 `Set-Content` / `-replace`**。
8. ⚠️ **内存**：RAM 32.5 GB、总空闲约 10 GB；`mgba-probe` 长录制吃 7–8 GB 且泄漏
   ⇒ **全机同一时刻最多 1 路跑长录制（>60 s）**；跑完检查孤儿进程。
9. 单测：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/w19-x/butano-sequel`
   ⇒ 已知基线 **pass=118 / fail=20**（20 项预存债）⇒ **多出任何一项 ⇒ 你引入的回归**。

---

## 1. ⭐⭐ A 流 —— 「開始」标题卡语义（**本波最高优先级**）

### 1.1 W5 已经量到的事实（不用重做）

| | 原版 | 重制侧 |
|---|---|---|
| 卡片是否看输入 | ⛔ **完全无视**：按 A / 不按 A 的 **300 帧运行逐像素完全相同** | ⛔ **按 A 会被冻住**（冻在判定台 `step-13-A.png` 那一帧，**整帧 0 px 差**）；**不按则 A↔B 无限循环**（+390 帧仍在卡上） |
| EWRAM 状态差 | 08→09 变 **3 字**；**09→10 只变 1 字**（30 Hz 计时器）；10→11 变 408 字 | 重制侧「 noisier」 |
| 画面 | `step-09` = 姿态 A；`step-10` = **姿态 B**（整帧差 **2,247 px，全在字形区**；背景 / 状态栏 / `bg_hofs` 全同） | `step-13` = 姿态 A（759 px）；`step-14` = 黑场大绿星 |

⇒ **原版的卡片是「纯定时、完全无视输入」的一次性演出：姿态 A → 姿态 B → 自动擦除。**
⇒ **重制侧缺的是标题卡语义**，**不是缺确认框**（父代理已证伪「A 被拒」那条线）。

### 1.2 代码机制（父代理已核实，可直接用）

`game/src/battle_runtime_scene.cpp:7984-8006`：
```cpp
const bool title_visible = deployment.phase() ==
        battle_deployment_phase::start_confirmation;
if(title_visible != title.visible()) { … title.begin(); … / title.finish(); … }
if(title.visible()) { title.advance(); title_view.set_phase(title.phase()); }
```
`game/include/konoha/battle_opening_title.h`：
```cpp
static constexpr int phase_frames = 23;
[[nodiscard]] int phase() const { return (_frame / phase_frames) % phase_count; }  // ← 取模 ⇒ 无限循环
void advance()  { if(_stage == stage::showing) { ++_frame; } }
void finish()   { _stage = stage::idle; _frame = 0; }
```

⇒ **两个缺陷**：
1. `phase()` 取模 ⇒ 卡片**永远转不完**（姿态 A↔B 循环）。
2. 卡片**只在 `deployment.phase()` 离开 `start_confirmation` 时消失**
   ⇒ 而那需要一次**输入** ⇒ **A 键被卡片「吃掉」却没让部署相位前进**
   ⇒ 表现为「按 A 冻在原帧」。

### 1.3 你的任务（照原版语义改，不要凭感觉）

1. **卡片一次性走完**：`phase()` 不再取模循环；走完最后一个相位后**保持**（或按原版语义自动收尾）。
2. **卡片不吃输入**：按 A **不得**让卡片停在原地；卡片要么无视输入自然走完，
   要么让那次 A 正常传给部署场景（**不要让同一个 A 被消费两次**）。
3. **渲染姿态 B**：重制侧现在只画得出姿态 A ⇒ 补上姿态 B（资产侧如果缺，
   在笔记里写清楚需要什么资源，**不要自己去改 `graphics/`** —— 那是 B 路的）。
4. ⚠️ **一次只改一处**：先改 1（一次性走完）→ 测 → 再改 2（不吃输入）→ 测 → 再改 3。

### 1.4 ⭐ 判定问题（是/否）

> **「修好后，判定台的两条 walk 的步偏移是否恒为 +4（不再在原版第 9→10 步之间从 +4 掉到 +3）？」**

工具（父代理的，**只读调用**）：
```powershell
python tools/s49_wave18/align_capture_steps.py `
    --original <原版捕获目录> --remake <重制侧捕获目录>
```
原版捕获目录用 `build/s49-package-u3-final/work/s49-report/capture-original`；
重制侧捕获目录**要你自己重录**（见 §1.5）。

### 1.5 ⭐ 怎么录一条新的重制侧 walk（你的硬指标）

判定台的捕获脚本是 `D:\Shell\Github\gba-naruto-butano\tools\butano\mgba_boot_input_sequence.lua`
（键序列 `Down,Down` + `A`×32，`HOLD_FRAMES=4`、`SETTLE_FRAMES=90`、`ZERO_INPUT_FRAMES=240`）。
**你要用同样的机制重录一条**，把产物放到**你自己的目录**
（例如 `build/w19-a/capture-remake/`），并让 `align_capture_steps.py` 能读它。

⚠️ 录制时：
* 探针 exe 用 `D:\Github\gba-naruto\build\mgba-probe\mgba-probe.exe` 的**副本**
  （**不要覆盖**它；重建探针用 `$env:KONOHA_PROBE_OUT` 指向自己的目录）；
* **长录制全机只允许 1 路** ⇒ 先用短录制自检，等 D 路或别人不在跑时再录完整条；
* 录完**必须**检查 `Get-Process -Name 'mgba-probe' -ErrorAction SilentlyContinue`。

### 1.6 验收

| # | 项 | 判据 |
|---|---|---|
| A-1 | 卡片一次性走完 | 卡片不再 A↔B 循环（实测：不按输入，+N 帧后卡片已到最终相位） |
| A-2 | 卡片不吃输入 | 按 A 的那一帧，卡片**不冻结**；且那次 A **正常传给部署场景** |
| A-3 | 姿态 B | 能画出原版的姿态 B（整帧 2,247 px 字形差那一版） |
| **A-4** | ⭐ **步偏移恒为 +4** | `align_capture_steps.py` 的偏移剖面**全程 +4**，不再在第 10 步掉到 +3 |
| **A-5** | ⭐ **那 4 帧配对成功** | 原版 `step-12/19/21/22` 在重制侧**能配到帧**（偏移 ±1…±6 全列不再 ≥10k）⇒ **判定台残差应从 109,569 掉到 ≈27,000**（预言 P-7 / P-15） |
| A-6 | 单测 | pass=118/fail=20，零新增红 |
| A-7 | 接线请求 | B/C 两路若有 `.cpp` 需求 ⇒ 父代理转给你，请**一并实现** |

---

## 2. B 流 —— 結算链后半段（戰後對白 + 任務菜單 + 人物）

### 2.1 残差真值（sha256 配对后，U4 实测）

| remake 链页 | 相位 | 原版真值 | 原版 sha256（前 16） | 重制侧 sha256（前 16） | 差 px | 差 bbox |
|---|---|---|---|---|---:|---|
| `page-014-post_battle_dialogue.png` | post_battle_dialogue | `08-postbattle-dialogue-1.png` | `2741dbc3fbf6e838` | `5fece4f6952f78b0` | **26,819** | `[0,0,240,160]` |
| `page-021-task_menu.png` | task_menu | `09-task-menu-map.png` | `cda07a18be60a1ea` | `3814df2825813f89` | **37,694** | `[0,0,240,160]` |
| （結算屏人物） | result | — | — | — | **1,898** | 人物区 |

**同链已闭合**（不要重复劳动）：勝利 **0 px**、結算 **2,582 px**（= 684 px 真实战果数据 + 1,898 px 人物）、
6 张升級屏 **0/6 px**。

**真值图目录**：`D:\Github\gba-naruto\build\s49-victory-capture\w4\settlement-truth\`
（`08-postbattle-dialogue-1.png`、`09-task-menu-map.png`，收据 sha `9a60a89b…`）

### 2.2 ⭐ 先做的事（按顺序）

1. **定位错**：把結算/对白相关 BG 层的创建定位从 `(0, 0)` 改成 `(8, 48)`
   ⇒ **这是 `.cpp`（A 路独占）** ⇒ **写「接线请求」交父代理**，**不要自己改**。
   ⇒ 但**你可以先在笔记里给出精确到行的改法 + 预期残差下降量**（用你算出的几何差推算）。
2. **页选错**：`dialogue_1` 资产画的是卡卡西，真值是鸣人 ⇒ 找到正确的资产页。
   ⇒ 资产侧在**你的** `graphics/`（真实目录）里改 ⇒ **这是你的活**。
3. **缺图层**：原版对白屏是 3 层 BG（`_bottom` 行 8–87 / `_middle` 空 / `_top` 行 96–159）
   ⇒ 确认重制侧是不是少了 `_middle` 或用了错的层。
4. **任務菜單**：地图资源被释放（`bn::core::update()`）⇒ 查清原版的地图资产与重制侧差在哪
   （W4 已存 `map-bottom.json` / `orig-taskmenu-timeline.txt` / `orig-pages/`，
   在 `build/w18-w4/` 下，**只读复用**）。
5. **結算屏人物 1,898 px**：U2 的结论 —— 逐人 8bpp 不可能（硬件只有一套 8bpp OBJ 调色板），
   可行方案是「三个立绘合成一张 8bpp 图集 + 共用一套 8bpp OBJ 调色板」⇒ **本波要实现它**。

### 2.3 ⭐ 判定问题（是/否）

> **「戰後對白 与 任務菜單 两屏的残差能否降到 0？若不能，可证下界是多少？」**

### 2.4 验收

| # | 项 | 判据 |
|---|---|---|
| B-1 | 戰後對白 | 残差降到 0，或给出可证下界 + 硬证据 |
| B-2 | 任務菜單 | 同上 |
| B-3 | 結算屏人物 | 1,898 px → 0，且**参与者仍然动态**（每个战斗换一张图集） |
| B-4 | 逐屏对照 | 用 `tools/s49_victory_align/align_settlement.py`（**只读**）给出**整链**逐屏差表 |
| B-5 | 接线请求 | 所有 `.cpp` 改动写成可执行的请求（文件 + 行 + 改成什么 + 为什么） |
| B-6 | 资产交付 | 新增/修改的资产：**路径 + sha256 + 它对应哪个相位/页**（父代理接线时要一并拷） |
| B-7 | 单测 | pass=118/fail=20 |

---

## 3. C 流 —— 黑场 B2/B3/B4 + 开机纯白 + 事件 6 淡入

### 3.1 待收的硬切（W3 已定位到代码行）

| # | 事件 | 帧号 | 根因位置 | 修法 |
|---|---|---|---|---|
| **B2** | 准备场景 → 战斗 **6 帧纯黑** | 527–532 | `battle_runtime_scene.cpp:8152`（**A 路独占**） | 战斗场景第一帧就画背景；⚠️ **但被 64 KB BG 图块区卡死**（准备背景 32 KB + 部署地图 64 KB 无法共存 ⇒ **到 0 帧不可能**）⇒ 给出**可达到的最小帧数 + 硬证据** |
| **B3** | 生长段 → 对白 **2 帧纯黑** | 1657–1658 | `battle_runtime_scene.cpp:5066-5067` 的 `map.reset(); bn::core::update();`（**A 路独占**） | 把这次交接**挪进遮罩还盖着屏幕的持黑段**（顺带把事件 3 的淡入 28→24） |
| **B4** | 对白段内部 **8 帧纯黑** | 2123–2130 | `battle_runtime_scene.cpp:6497-6514` + `battle_visual_resource_coordinator.h:119-131`（**前者 A 路、后者你的**） | 把交换**推迟到事件 2 淡出的末几级** |
| **B5** | 事件 6 淡出/淡入 **28 ≠ 24** | — | `battle_black_field_star_mask.h`（**你的**） | 对齐原版 24/24/24 |
| **B6** | ⭐ **开机 26 帧纯白**（原版 2 帧） | — | W3 定位到根因在 butano（`core::init()` 清了强制空白） | 比那 2 帧黑**更大** ⇒ 优先收 |

### 3.2 ⭐ 判定问题（是/否）

> **「黑场事件集合能否从 6 个收敛到 2 个（与原版同形），且『淡出/持黑/淡入』帧数 = 24/18/24 与 24/24/24？」**
> **若某一项在硬件/内存约束下不可达，请给出「可达到的最小值 + 硬证据」**（B2 就是这种情况）。

### 3.3 验收

| # | 项 | 判据 |
|---|---|---|
| C-1 | 黑场事件清单 | 你的 ROM 上实测的**事件数 + 帧号 + 每段帧数 + 是否渐变**，与原版逐项对齐 |
| C-2 | B5 / B6 | 在**你的独占文件**里修好并复测 |
| C-3 | B2 / B3 / B4 | 定位 + 精确到行的接线请求（交父代理转 A 路） |
| C-4 | 仪器 | `tools/s49_blackfade/`（**只读**）；需新仪器就建 `tools/s49_w19c/` |
| C-5 | 单测 | pass=118/fail=20 |

---

## 4. ⭐⭐ D 流 —— 真实打完仗的结算链采集与逐屏对照（**只做仪器**）

### 4.1 为什么这一路现在才做得成

wave 17 起，1:1 报告里一直缺「**真实战斗链**」——
之前的结算链对照用的是**工具自检链**（`play_settlement_chain()`：只按键、不 poke），
**报告里已分列标注**。
⇒ **D4 修好后，重制侧能真打赢仗了** ⇒ 现在可以录到**真实**的结算链。

### 4.2 任务

1. **真实战斗 + 真实结算链**：
   用 `tools/s49_battle_balance/v1_battle.py`（**只读**）打出真实胜利
   （`bee_hp_dropped: true`、`from_real_battle: true`、`poke_commands: 0`），
   **接着把结算链走完并逐页录帧**（胜利 / 結算 / 6 张升級屏 / 忍具一覽 / 戰後對白 / 任務菜單）。
2. **逐屏对照**：与 `build/s49-victory-capture/w4/settlement-truth/` 的原版真值
   **按 sha256 配对**（U4 修过的配对方式）逐屏对差，给出**整链**差表。
3. ⭐ **核对那 684 px 的「真实战果数值」**：
   結算屏残差 2,582 px 里，**684 px 是真实战果数据**（原版 100/150/0 与 300/350/200
   vs 重制侧 0/0/0 与 200/200/200）⇒ 现在真打完仗了，**查清重制侧的数值为什么是 0/0/0**，
   并给出修法（写接线请求，**不要改产品代码**）。
4. **升級屏 6/6 = 0 px 的复核**：U4 用 sha256 配对后已得 0 px ⇒ 你要**独立复核**（不是照抄）。

### 4.3 ⭐ 判定问题（是/否）

> **「真实战斗走完的结算链，与原版真值逐屏一致吗？差在哪、为什么？」**

### 4.4 验收

| # | 项 | 判据 |
|---|---|---|
| D-1 | 真实链 | 收据证明：`from_real_battle: true`、`poke_commands: 0`、`bee_hp_dropped: true`、结算链 7 段都录到 |
| D-2 | 逐屏差表 | 整链逐屏（原版页 ↔ 重制页，sha256 配对）+ 差 px + 差 bbox |
| D-3 | ⭐ 684 px 根因 | 「真实战果数值」为什么是 0/0/0 ⇒ 具体到代码行 + 修法（接线请求） |
| D-4 | 升級屏复核 | 独立复核 6/6 = 0 px（不是照抄 U4） |
| D-5 | 仪器 | 新工具放 `tools/s49_w19d/`；**只读调用** `tools/s49_victory_align/`、`tools/s49_battle_balance/` |

> ⚠️ **D 路不改任何重制线产品文件**（`D:\Shell\Github\gba-naruto-butano\**` 只读）。
> ⇒ 「修法」一律写成**接线请求**（文件 + 行 + 改成什么 + 为什么）。

---

## 5. 波末验收（父代理执行）

| # | 项 | 判据 |
|---|---|---|
| 1 | 接线 | 四路的独占文件拷回共享树（`tools/s49_wave18/integrate.py --apply`）+ 接线请求逐条处理 |
| 2 | 统一构建 | `ROM fixed!`，sha 记录 |
| 3 | ⭐ **判定台残差** | 新 ROM 上重跑 ⇒ **是否从 109,569 掉到 ≈27,000**（预言 P-7/P-15 的判决书） |
| 4 | 真实战斗 | `outcome=1` / `bee_hp_dropped` / `poke_commands: 0` |
| 5 | 黑场 | 事件集合与帧数对齐原版 |
| 6 | 結算链 | 真实链逐屏差表 |
| 7 | 棘轮 | 单测 pass=118/fail=20 |
| 8 | 12 步流水线 | `python tools/s49_package/run_pipeline.py --out build/s49-package-w19` |
| 9 | 路线图 | `docs/sequel-roadmap.md` 回填 wave 19 里程碑 |
