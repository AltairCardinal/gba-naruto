# Wave 4 任务书 —— 集成接线 + 仪器升级 + 真值补齐（四路并行）

> 2026-10-24 · 主代理（mvs_4e730a9ded524558a303c115875a9707）
> 前置：wave 3 四路（G / H2 / L / M）**全部交付**。本波把它们的成果**接起来、测出来、补齐剩下的真值**。

---

## 0. wave 3 交回了什么（**全部已确认，勿重查**）

| 流 | 交付 | ⭐ 关键结论 |
|---|---|---|
| **G 覆盖层** | `battle_range_ui_style.h` 族判定顺序 + `blocked` 50% 网点 + `battle_runtime_scene.cpp` 地图空间锚定；新仪器 `tools/s49_overlay_align/`（9 个脚本）；报告 `G-overlay-alignment.md` | ⭐ **证伪了任务书里「一格改 16 px、`tiles_per_cell_x` 4→2」的前提** —— 那是 **F 流的分析单位**，不是游戏格。**战斗格 = 32×16 px**（三条独立证据：格线间距 / 青区形状 / ROM 碰撞网格 `width_tiles>>2`）。**1 战斗列 = 2 逻辑列，1 战斗行 = 1 逻辑行**。<br>⭐ **wave 1 的「多画 310–420 格」口径也是错的**（拿原版的地图空间缓冲去减重制的屏幕空间图层）⇒ 换算后实为**多画 42 / 缺 24**。<br>⭐ **坐标对应已建立**（F-2 关闭）：256×256 px 地图空间缓冲，滚动量 = 相机。<br>⚠️ **AFTER 数字未测**（构建被打挂）。<br>⚠️ **30 处「原版青 / 重制绿」** ⇒ `hatch_shift` 优先级或合法目标集有问题（G-H15 **未验**）。 |
| **H2 idle+调色板** | 新文件 `battle_unit_palette_stream.h`（纯逻辑、无 butano 依赖）+ `battle_unit_visual_animation.h` 加 `idle_pose_cycle_position()` + `battle_visual_resource_coordinator.h` 加 `unit_outline_palette` + 3 个测试；工具 `tools/s49_idle_frame_repeat.py`、`tools/s49_idle_outline_colours.py`；报告 `H2-idle-palette.md` | ⭐ **描边色：原版 7 级 5bit `[1,5,11,13,17,23,27]`，重制侧 1 级 `[1]`** ⇒ 根因确认。<br>⭐ **证伪了父代理下发的「不得出现连续两帧相同」门禁** —— 原版自己**每 100 GBA 帧也有 4 对**相同，且**恰好落在波形平点**（相位 9→10、25→26）⇒ 正确判据是「**只允许在波形平点处相同**」。<br>⭐ 描边波形 **200/200** 与原版一致；**接线点清单 6-0…6-4 已给出**（见 §1.3）。 |
| **L 音频** | 战斗 BGM → **sound 10**（新增 `audio/sound_010.s3m`，54.565 s，与原版逐帧相等）；12 个音效 cue 真正出声；**cue 146/152 资产入库**（PCM 与逆向线 ground truth **逐字节相同**）；新建 `battle_audio_event_trace.h`（运行时 `(kind,cue,frame,handle)` trace，**放 EWRAM 固定窗口**）；工具 `tools/s49_audio_l/`（10 个脚本）；报告 `L-audio-wiring.md` | ⭐ 运行时口径 19 个配对时刻：**`cue_mismatch` 1→0、`silent_on_remake` 11→0**、`match` 4→5。<br>⭐ **崩溃已修**：trace 占 IWRAM 撞栈 ⇒ 改放 EWRAM 后 4096 帧跑完（L-12 已确认）。<br>⚠️ **cue 8 / 146 / 152 还缺 3 行调用点**（在 `battle_runtime_scene.cpp`，G 流独占 ⇒ 现在归 W1）。<br>⚠️ **口径诚实说明**：J 的 `compare_events.py:228-245` 里 `remake_kind=="sound"` 分支在 `match` 之前 ⇒ **结构上永远不可能给音效行判 `match`** ⇒ 「重跑 J 的管线把 `silent_on_remake` 压到 0」在不改动 J 工具（只读）的前提下**不可达成**；L 达成的是**运行时口径**。 |
| **M 原版真值** | ⭐ **原版 battle-14 地图/地形/通行成本真值**：`tools/s49_orig_map/battle-14-map-truth.json` + `artifacts/map-14-atlas.png`（sha256 `5beffb4e…`，与逆向线源一致）+ `map-14-tilemap-u16le.bin`（`2bbab081…`）；报告 `M-original-victory-truth.md` | ⭐ **battle-14 = 逆向线 map id 14**：15×19 战斗格 ×32×16 px；**可走 147 / 不可走 138**（`0 plain` 144 可走、`1 river` 10、`3 ground_patch` 3 可走、`7 rock` 8、`15 wall` 120）；**9/9 单位初始坐标全落在可走格**；坐标对应 `(bx,by) = (碰撞网格列,行)`，**无偏移**。<br>⭐ **移动范围 = 曼哈顿半径 3**（3 格接受、4 格拒绝；`(10,8)` 接受、`(10,9)` 拒绝 ⇒ 曼哈顿非切比雪夫）—— 与 G 的独立结论**互相印证**。<br>⚠️ **还是没打成**（`victory: False`）。卡点：探针**每条命令让模拟游戏前进一帧** ⇒ 跨命令像素判定慢一帧。修法见 §3。 |

---

## 1. 流 W1 —— 集成接线 + 构建打通 + AFTER 复测（**关键路径**）

### 1.1 独占文件（**只能改这一���**）

* `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_runtime_scene.cpp`

⛔ **其它三个流都不许碰这个文件**（W2/W3/W4 只读）。
⛔ 不要改 `battle_unit_palette_stream.h` / `battle_audio_event_trace.h` /
`battle_range_ui_style.h` / `battle_audio_director.h` / `battle_audio_runtime.h`
（wave 3 已定稿，只**调用**它们）。

### 1.2 任务

**(a) 构建打通。** wave 3 结束时构建是被各流在途改动打挂的。
**第一步就是让 `make -j4` 干净通过**，并且 ROM 能跑完 4096 帧不崩。
（wave 3 已知的两个坑：trace 撞 IWRAM 栈 → 已改 EWRAM；G 的在途改动 → 已收工。）

**(b) 接线 H2 的调色板流**（照 H2 报告 §6 的清单，一字不差地做）：

* **6-0 先决**：每单位一份**运行时** OBJ 调色板
  （`bn::sprite_palette_items::X.create_palette()` + `set_colors(item->palette_item())`）。
  现 `item->palette_item()` 是共享 item，直接写会串色；
  `dimmed_unit_palette()`（约 L6479）是共享灰度，**不要往里写**。
* **6-1 每帧写描边色**：在 `update_unit_sprites()` 的调色板绑定处 **L6742 之后**
  （现有 `set_palette` 在 L6735 / L6740）插入
  ```cpp
  const battle_unit_palette_write outline =
      battle_unit_palette_write_for_frame(unit.id, idle_clock.frames(), scene_frame);
  if(outline.valid || binding_changed)
      unit_palette(unit.id)->set_color(outline.color_index,
          bn::color(outline.color.red, outline.color.green, outline.color.blue));
  ```
  ⚠️ `bn::color` 收 **5 bit 分量(0..31)**，`color.green` **直接传，不要乘 8**；
  槽位用 `color_index`(=15)；`|| binding_changed` **不可省**（重绑会把槽位 15 复位）。
* **6-2 时钟来源换门控时钟**：`unit_visual_sample()` **L6141–L6145** 的
  `scene_frame & 0x7FFFFFFFU + idle_phase_offset(...)` 改成 `idle_frame + idle_phase_offset(...)`；
  `unit_visual_sample()`（L6132 签名）与 `update_unit_sprites()`（L6487 签名）各加一个门控时钟参数，
  **L6573** 调用处传 `idle_clock.frames()`。
* **6-3 门控时钟的存放与推进**：场景帧计数器 **L7042** `std::uint32_t scene_frame = 0;` 旁新增
  `battle_unit_idle_clock idle_clock;`，每帧在 `++scene_frame;`（**L7154 / L8006**）旁
  `idle_clock.advance(<当前场景状态>)`。
  **门控时钟须与 `scene_frame` 同源起算（都从 0 开始）**，否则模块一律报写（安全但退化）。
* **6-4 提醒**：原版只有**未被灰度**的那个单位在动；若给所有单位都写描边色，
  残差里会出现「另一个单位也在动」。

**(c) 接线 L 的 3 行调用点**（cue 8 / 146 / 152）。签名见 L 报告 §6。

**(d) 修 G-H15 的 30 处「原版青 / 重制绿」。**
原版 `hatch_shift`（绿，合法目标）与 `hatch`（青，移动可达）的实际优先级**与书面顺序相反**
（对拍出现 30 处「原版青 / 重制绿」）。
⇒ 用**原版目标选择阶段的实机帧**定论，别猜。

**(e) AFTER 复测**（**这是本波的核心验收**）：
* 逐格族名对拍：`python tools/s49_overlay_align/compare_overlay_families.py`
  （G 已建）。目标 **BEFORE → AFTER 明显下降**；
  BEFORE 基线见 G 报告：`movegrid` 同亮 168·原版缺 24·多画 42·族名不一致 24。
* 判定台：`python tools/s49_fidelity_report.py --out build/s49-report/report.json`
  基线：战场区残差 **min 0 / 中位 1940 / max 27325 / 全 0 帧 3**；
  归因 **一致 3 · 产品差 14 · 配对差 8**。
  ⇒ **残差只许变小**（棘轮语义）。
* 静止帧门禁：`python tools/s49_idle_frame_repeat.py`
  ⚠️ 用 H2 收紧后的判据（**只允许在波形平点处相同**），不是父代理最初下发的绝对判据。

### 1.3 验收

* `make -j4` 干净通过，ROM sha256 更新并记录。
* ROM 用无窗口探针跑完 4096 帧**不崩**，中文标题画面正常。
* 逐格族名对拍**AFTER 数字**（G 的 #14 未验项必须给出数字）。
* 判定台残差**不高于**基线（最好给出逐帧前后对比表）。
* 单元测试（`battle/tests/` 的既有跑法）全绿。

### 1.4 交付物

* `notes/s49-fidelity/W1-integration.md` —— 报告 + 假设台账 + **接线前后对比表**。

---

## 2. 流 W2 —— 判定台升级（把「配对差」变成可操作的对象）

### 2.1 独占文件

* `D:\Github\gba-naruto\tools\s49_fidelity_report.py`
* `D:\Github\gba-naruto\tools\s49_fidelity_report\`（新目录，放模块化后的代码）
* `D:\Github\gba-naruto\tools\s49_idle_frame_repeat.py`（H2 已建，wave 3 结束 ⇒ 现在归 W2）
* `D:\Github\gba-naruto\tools\s49_overlay_align\`（G 已建，**只读复用**；要加东西先问父代理）

⛔ 逆向线只读；⛔ 不改重制线任何文件。

### 2.2 任务

**(a) 配对基准从「帧序号」换成「内容锚」。**
P 流已查实（`notes/s49-fidelity/P-pairing-decomposition.md`）：
`best_match` 的偏移从 **+4 漂到 −15** 且在 `#21/#22` 反向跳回 ⇒
两条 walk 走过了**不同的游戏序列**。
⇒ 判「同一游戏时刻」要改用**内容锚**：
名册 HP 集合、菜单开合状态、相机滚动位置、覆盖层格集合、回合横幅相位。
**锚点要能被机器读出，不能靠人眼。**

**(b) 把「配对差 8 帧」的三桶拆解做成判定台的一等公民。**
当前一个标签混了三种机制：
* **2 帧**（原版 #11 近黑 / #18 全黑）= 原版**黑场过渡**；
* **3 帧** = 重制侧**连续静止帧**（原版 0 处 / 重制侧 3 处）；
* **3 帧** = 两侧处在不同游戏时刻。
⇒ 判定台应分别报 `black_transition` / `static_frame` / `moment_mismatch`。

**(c) 静止帧判据收紧。**
H2 已证伪绝对判据：**原版自己每 100 GBA 帧就有 4 对连续相同帧**，
且**恰好落在波形平点**（相位 9→10、25→26）。
⇒ 判据 =「**只允许在波形平点处出现连续相同帧**」。

**(d) 把 G 的逐格族名对拍并进判定台**（作为「覆盖层残差」的一等指标），
让「残差」同时包含**整帧 px** 和**逐格族名**两个维度。

**(e) 棘轮门禁**：判定台要能对比两次运行的残差，**残差只许变小**；
变大 ⇒ exit≠0。

### 2.3 验收

* 判定台仍 **exit 0**，两次连跑 **byte-identical**。
* 归因分类**新增**上述三类，且原版 #11/#18 能被自动识别成黑场过渡。
* 静止帧判据能区分「波谷平点处的重复」与「异常重复」。
* 报告里给出**配对质量指标**（例如：多少帧找到内容锚）。

### 2.4 交付物

* `notes/s49-fidelity/W2-judgment-bench-v2.md` —— 报告 + 假设台账 + 前后分类对比。

---

## 3. 流 W3 —— 原版真值补齐：结算屏 + 黑场过渡

### 3.1 独占文件

* `D:\Github\gba-naruto\tools\s49_victory_capture\`（M 流已建）
* `D:\Github\gba-naruto\tools\s49_blackfade\`（新）
* `D:\Github\gba-naruto\notes\s49-fidelity\W3-original-truth.md`

⛔ 不改重制线；⛔ 逆向线只读；⛔ 不改 `tools\s49_audio_probe\` / `tools\s49_rule_probe\` / `tools\s49_overlay_align\`。

### 3.2 任务 A：结算屏真值（续 M 流）

M 流的卡点很明确：**探针每条命令让被模拟的游戏前进一帧**
⇒ 跨命令的「先读寄存器、再截图」判定读到**上一帧**的画面。

**修法（M 报告 §7.3 给的方向，照做）**：
* 用 `framedump` 在**同一帧**里同时取 VRAM + 层级寄存器（不要跨命令）；
* 或**等层级寄存器连续两次读数稳定再判**。

⇒ 目标：**打到胜利**，录到胜利演出 + 结算屏。
**不许伪造任何帧。** 打不成就交出「打到第 N 回合、最远进度、卡点」。

⚠️ 原版的战斗规则已经查清，照着用：
移动范围 = **曼哈顿半径 3**；坐标 `(bx,by)` = 碰撞网格列行、**无偏移**；
合法落点 = 碰撞网格可走格（可走 147 / 不可走 138）；
忍者列表**按角色不同**；`可以嗎?` 确认框比伤害预测**晚一次 A**；
蜜蜂 25 血、十字手里剑一发 **18–22 伤**（⇒ 要两发）；
木叶丸 40 血、**第三回合会死**（输出从 4 人降到 3 人）。

### 3.3 任务 B：黑场过渡真值（**wave 4 的新问题**）

P 流查实：**原版有 2 帧黑场过渡**（step-11 非黑 0.8%、step-18 全黑唯一色 1），
而**重制侧 35 帧里一帧黑帧都没有**。

要回答的问题：
1. 原版**在哪些相位**淡出黑场？（每次 A 之后的回合切换？开场演出？胜利前？）
2. 黑场是**纯黑一帧**还是**渐变多帧**？原版 #11 是近黑（均值 1.2/1.3/0.4、唯一色 16）、
   #18 是全黑（唯一色 1）⇒ 至少有两种黑度 ⇒ **可能是渐变**。
3. 重制侧**需不需要**实现？如果需要，是**产品差**（"玩家看得见的画面"的一部分）；
   如果不需要（因为那次 walk 没走到该相位），要给出**证据**。

⇒ 交付：**黑场相位的真值表**（帧号 / sha256 / 持续帧数 / 前后帧关系）+ 结论。

### 3.4 验收

* 结算屏 PNG + sha256 收据；两次独立跑**逐字节一致**。
  （若没打成：交出最远进度与卡点，**不伪造**。）
* 黑场真值表可复跑（一条命令）。
* 报告里给出「黑场是产品差还是走位没走到」的**判定**，并给证据。

### 3.5 交付物

* `notes/s49-fidelity/W3-original-truth.md`。

---

## 4. 流 W4 —— 存档字节 + 边界行为取证

### 4.1 独占文件

* `D:\Github\gba-naruto-butano\butano-sequel\game\src\battle_campaign_sram.cpp`
* `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_campaign_sram.h`
* `D:\Github\gba-naruto\tools\s49_save_boundary\`（新）
* `D:\Github\gba-naruto\notes\s49-fidelity\W4-save-boundary.md`

⛔ **不改 `battle_runtime_scene.cpp`**（W1 独占）；⛔ 逆向线只读。

### 4.2 任务

**(a) 存档字节一致。**
战前 / 战后 SRAM 与原版**逐字节**对比。
先**取证**：两边各导出一份存档，diff 出**哪些字节不同、每个字节对应哪个字段**，
产出「字段级差异表」+ 施工单。
⚠️ **不要**一上来就改产品代码 —— 先把差异表交出来，
**改动只允许落在 `battle_campaign_sram.cpp` / `.h`**（你独占）。

**(b) 边界行为（含原作 bug）。**
C 流已查实 7 条 `0xFBFF` 损坏终止符缺陷语义（全绿），
另有「蜜蜂是否进轮转」等未判项。
⇒ 对照表：**原版行为 = 规格**（原版越界渲染就让它越界），
列出每条边界情形下**原版实际怎么做**、**重制侧现在怎么做**、**差在哪**。

**(c) 出包准备清单。**
列出「可玩 ROM + 一条复现命令 + 收据 + 1:1 报告」还缺什么。

### 4.3 验收

* 字段级存档差异表（有差异就写清楚；**没差异也要给出比对方法与收据**）。
* 边界行为对照表（每条：原版 / 重制 / 差 / 结论）。
* 存档比对可复跑（一条命令）。

### 4.4 交付物

* `notes/s49-fidelity/W4-save-boundary.md` + `tools/s49_save_boundary/`。

---

## 5. 父代理（我）同时做的事

* **回填被 wave 3 推翻的结论**（AGENTS.md 规则 5）：
  * F 的「一格 = 16×16 px」→ **战斗格 = 32×16 px**（F-2 关闭）；
  * wave 1 的「多画 310–420 格」→ **多画 42 / 缺 24**；
  * H2 的静止帧判据修正（原版自己每 100 帧 4 对，落在波形平点）。
* 同步 `docs/sequel-roadmap.md` / `docs/s49-three-day-plan.md` / `docs/butano-fidelity-roadmap.md`。
* 维护判定台棘轮：任何流声称「残差下降」都要用判定台独立复跑确认。
* 监视四路、估算剩余耗时、动态调任务。

---

## 6. 交回格式

1. **一句话结论**。
2. **改动的文件**（完整绝对路径）。
3. **跑了哪些验证**（命令 + 关键数字）。
4. **假设台账**（表格：# / 假设 / 判定方法 / 结果 / 状态）。
5. **卡在哪**。
6. **新文件一律 LF、无 BOM**；**不提交 git**。

---

## 7. 反循环守则（复述）

* 一次尝试回答一个**是/否问题**；**「还是卡」不是结果**。
* 一次只改一处，跑一次，记一行；结论落进**假设台账**。
* **连续 3 次同样结果 ⇒ 停**，换方法，写进台账。
* 陷住了**换方法/换会话**，不要靠续跑硬扛。
* 自检：`python tools/loop_guard.py <会话的 messages.jsonl>`。
