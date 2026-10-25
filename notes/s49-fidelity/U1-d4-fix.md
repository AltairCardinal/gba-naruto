# U1 —— D4 必修 + 黑场收尾（wave 17 · 流 U1）

> 2026-10-24 · 流 U1（mvs_00ef4080c1654a0a886acaf72f4af019）· 父代理
> `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/WAVE17-TASKS.md` §0.2/§1 ·
> `notes/s49-fidelity/V1-real-victory.md` · `notes/s49-fidelity/V2-pixel-fixes.md`
> 本流新建仪器：`tools/s49_u1_d4/u1_diag.py`（**U1 自己的**诊断器，
> 不动 U4 的 `tools/s49_battle_balance/`）
> 产物（不进 git）：`build/u1/**`（诊断收据、崩溃转储、构建日志、栈报告）
> ⛔ **未改** `battle_range_ui_style.h` / `battle_result_content.h` / `graphics\`
> ⛔ 逆向线 `D:\Shell\gba-naruto-reverse` **全程只读**；**未提交 git**

---

## 0. 一句话结论

> **D4 没有完全修好，但已经从「不可诊断」推进到「根因已用硬证据闭合」**：
> ⭐ **根因 = 攻击确认链把 IWRAM 用户栈撑爆了**（实测：链深 21,772 字节 vs
> 可用 21,308 字节 ⇒ 溢出约 464–2,200 字节 ⇒ **踩坏 devkitARM 的
> `IRQ_VectorTable`（0x03002880，只比栈底低 832 字节）** ⇒ VBlank 的处理程序
> 指针变成 `0x0000000C` ⇒ **中断风暴** ⇒ 场景帧停死）。
> ⇒ **V1 猜的「战斗演出不结束」被实测否掉**（冻结点上 `presentation_busy = 0`、
> `combat_stage = complete`，演出根本没开始）。
> ⭐ 本流已把**第一个症状修掉**：场景栈帧 7136 → **6144 → 6136**，动作选择不再冻住，
> 驱动器收据里**第一次出现 `target-accepted`**（忍具与普通招式各一次）。
> ⛔ **第二个症状仍在**：目标确认（相位 20）处仍冻住 ⇒ 伤害结算跑不完
> ⇒ **蜂的 HP 还没下降过** ⇒ **`outcome=1` 仍未达成**。


---

## 1. 改动文件清单

### 1.1 重制线（`D:\Shell\Github\gba-naruto-butano\butano-sequel`）—— U1 独占文件

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_runtime_scene.cpp` | **改** | ⭐ **(a)** 把 `run_visible_battle_scene()` 的重量级局部对象从**栈**迁到 **EWRAM 静态**：9 个 `bn::sprite_text_generator`、4 个演出渲染器（`portrait_renderer` / `message_window_renderer` / `dialogue_background_renderer` / `combat_stage_renderer`）、`battle_black_field_star_mask star_mask`、2 个 `bn::vector<bn::sprite_ptr, N>`（`map_scenery_sprite` / `pickup_text_sprites`）。沿用该文件已有的 `BN_DATA_EWRAM static` / `BN_DATA_EWRAM_BSS static` 模式；新静态对象在场景入口显式 `reset()`。**实测该函数栈帧 7136 → 6144 字节（−992）**。<br>⭐ **(b)** 用 `[[gnu::noinline]]` 包装器（`take_battle_scene_snapshot` / `take_battle_scene_object_snapshot` / `take_battle_training_snapshot`）与给 `capture_telemetry` 加 `[[gnu::noinline]]`，把**只在渲染期用**的大临时量挪出场景栈帧（实测只省 **8 字节** ⇒ 那几个临时量本来就不在场景帧里 ⇒ **这一步没有行为变化**，保留是因为它把「场景帧 = 攻击确认链的根」这件事写进了代码）。 |


### 1.2 本仓库（`D:\Github\gba-naruto`）—— U1 新增

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_u1_d4\u1_diag.py` | **新增** | ⭐ U1 自己的诊断器：走一个回合 → 落到指定招式条目 → 确认 → **逐帧轮询 ROM 自己的遥测**（相位 / 场景帧 / 战斗演出内部状态 / 三个错误码）→ 可选 **mGBA 调试器崩溃现场转储**（寄存器 + IWRAM 窗口 + IO 寄存器 + 反汇编 + stderr）。 |
| `D:\Github\gba-naruto\notes\s49-fidelity\U1-d4-fix.md` | **新增** | 本文件。 |
| `D:\Github\gba-naruto\build\u1\gen_su.sh` / `addr2line.sh` / `find_pc.sh` | 新增（产物目录） | 重建栈报告 / 地址解析 / 查 PC 所属符号。 |
| `D:\Github\gba-naruto\build\u1\**` | 产物 | 诊断收据、崩溃转储、构建日志、私有探针 `build\mgba-probe-u1\mgba-probe.exe`。 |

### 1.3 没有改的

* `battle_combat_presentation.h` / `battle_scene_presentation.h` /
  `battle_black_field.h` / `battle_black_field_timing.h`：**一个字节没动**
  （本波定位到的两个缺陷都不在这四个文件里，见 §6）；
* `battle_range_ui_style.h` / `battle_result_content.h` / `graphics\`：**没动**（U2 独占）；
* `tools/s49_battle_balance/`（U4 独占）：**只读调用**
  （`v1_diag_freeze.py` / `v1_battle.py` 是判据工具）；
* 逆向线 `D:\Shell\gba-naruto-reverse`：**未访问**；
* **未提交 git**（两个仓都没有 `git add/commit`）。

---

## 2. ⭐ D4 的根因（实测，不是猜的）

### 2.1 复现（当前 ROM，sha `16bf746f…`）

`python tools/s49_battle_balance/v1_diag_freeze.py --rom <ROM> --index 3 --cells "9,6"`：

| | 改前（V1 的 ROM `fb9d2dbd…`） | **本流 ROM `16bf746f…`** |
|---|---|---|
| 「离蜂 ≤3 格确认忍具 1」 | ⛔ 冻住，场景帧 499→500 / 508→509 | ✅ **场景帧 511 → 555 继续走** |
| 动作选择后的相位 | 停在 6 | ✅ **6 → 8（target_selection）** |
| 驱动器收据 | 无 `target-accepted` | ✅ **有 `target-accepted`**（`{"do": "target-accepted", "frame": 542, "enemy": 7, "cell": [6, 6], "phase": 22}`） |

### 2.2 ⭐ 第一个缺陷 = **攻击确认链把 IWRAM 栈撑爆**（实测数字）

冻结点的 mGBA 调试器现场（`build/u1/diag-tool3-crash/`）：

| 量 | 实测值 | 含义 |
|---|---:|---|
| `__sp_usr` | `0x03007F00` | 用户栈顶 |
| IWRAM 最低的数据块 | `mm_fetch` @ `0x03002A34`…`0x03002BC4` | ⇒ **可用栈 = 21,308 字节** |
| 崩溃时的 `sp` | **`0x030029F4`** | ⇒ **已用 21,772 字节** ⇒ **越过栈底约 464 字节** |
| 崩溃时的 `pc` | **`0x03001B94`** | **IWRAM 里的数据，不是代码** ⇒ 栈上的返回地址被溢出内容踩坏 |
| 崩溃时的 `lr` | `0x03001F90` | 同上（数据） |
| 遥测结构 | `phase` 被写成 `0x002A05A1` | ⇒ V1 看到的「相位不动 / 错误码 0 / 按键全无效」是**溢出后的次生现象**，不是原因 |

⇒ **V1 的结论「演出不结束所以输入全死」不成立**：演出根本没开始
（`presentation_busy = 0`、`combat_stage = complete`），是 **CPU 跑进了野地址**。

**栈链算术（与实测逐位吻合）**：

| 帧 | 字节 | 出处 |
|---|---:|---|
| `run_visible_battle_scene` | 7136（**改前**） | `battle_runtime_scene.cpp` |
| `battle_scene_controller::confirm()` | 896 | `battle_scene_controller.h:810` |
| `battle_scene_controller::_confirm_target()` | 592 | `battle_scene_controller.h:2009` |
| `battle_player_action_flow::confirm_target_in_place()` | 808 | `battle_player_action_flow.h:1222` |
| `battle_action_execution::resolve_in_place()` | 64 | `battle_action_execution.h:68` |
| `battle_action_resolver::resolve_draft_in_place()` | 800 | `battle_action_system.h:899` |
| `battle_action_resolver::resolve_area_draft_in_place()` | 1496 | `battle_action_system.h:685` |
| `battle_action_resolver::_resolve_battlefield_object_event_in_place()` | 1424 | `battle_action_system.h:781` |
| ⭐ `battle_action_resolver::resolve_battlefield_object_event()` | **8088** | `battle_action_system.h:759` |
| **合计** | **21 304** | ＋每帧 push 寄存器约 460 ⇒ **21 764 ≈ 实测 21 772** ✓ |

⭐ **最深的单帧 `resolve_battlefield_object_event` 的 8052 字节就是
`sizeof(battle_session<12>)`（实测 0x1F74 = 8052）**：
`battle_action_system.h:765` 的 `battle_session<MaxUnits> next = session;`
把**整个战斗会话拷到栈上**。

### 2.3 本流的修复（在我的独占文件里）

场景函数是**这条链的根**：它自己的栈帧（7136）在链的最底下。
把它压小，整条链就整体下移。两步改动见 §1.1：

1. 把重量级局部对象（9 个文本生成器、4 个演出渲染器、遮罩、2 个向量）搬到 EWRAM 静态；
2. ⭐ 把**只在渲染期用**的大临时量（`controller.snapshot()` 的 1656 字节、
   `controller.object_snapshot()` 的 624 字节、`capture_telemetry()`）用
   `[[gnu::noinline]]` 包装器**挪出场景栈帧** ——
   它们只在**输入处理之后**才需要，而攻击确认链正好跑在输入处理里。

| 步骤 | 场景栈帧 |
|---|---:|
| 改前 | 7136 |
| 步骤 1 后 | 6144（−992） |
| **步骤 2 后（最终 ROM `c69ba4e4…`）** | **6136（−8）** ⇒ 步骤 2 **没有行为变化**（那三个临时量本来就不在场景帧里） |

⚠️ **踩过的坑**：`build/*.su` 是 **16:19 的一次性产物**（正式构建只带
`-Wstack-usage=16384` 告警，**不写 `.su`**）⇒ 一开始我读的是**陈旧**数字，
误判「改动没生效」。必须自己重生成（`build/u1/gen_su.sh`）。

### 2.4 ⭐⭐⭐ 第二个症状：**用户栈溢出踩坏了 devkitARM 的中断向量表**

在**动作选择已经修好**之后，冻结点前移到 **相位 20 = target_confirmation**：

```
confirm@22 phase=20 target_confirmation  scene_frame=577
[   60] phase=20 target_confirmation  scene_frame=577   ← 场景帧停死
```

冻结现场（`build/u1/diag-irq2/crash-dump.txt`）：

| 量 | 实测值 | 含义 |
|---|---:|---|
| `pc` | `0x030011E8` | **devkitARM 的 IRQ 派发器** `interrupt_found`（IWRAM 0x03001190） |
| 下一条指令 | `0x030011E4: bx r3` | 派发到处理程序 |
| ⭐ `r3` | **`0x0000000C`** | **野指针** ⇒ 跳进 Thumb 预取异常向量 ⇒ **中断风暴** ⇒ 场景帧停死 |
| `sp` | `0x03007FE8` | **栈没溢出**（离栈顶只有 24 字节）⇒ 是**同一个根因的另一个症状** |
| `0x03007FFC`（用户 IRQ 向量） | `0x030010E4` **完好** | ⇒ 不是栈踩了「用户 IRQ 向量」 |
| IE / IF | `0x0001 / 0x0001` | 只有 VBlank，**正常** ⇒ 不是非法中断 ID |
| 被中断的 PC | `0x08050D0E` = **`VBlankIntrWait`** | ⇒ 打断点是**正常**位置 ⇒ 破坏发生在这之前 |

### 2.5 ⭐⭐⭐⭐ **决定性证据：中断向量表被栈溢出覆盖**

| 符号 | 地址 | 说明 |
|---|---:|---|
| `IRQ_VectorTable` | **`0x03002880`**（14 项 × 4 字节 ⇒ 到 `0x030028B7`） | VBlank 等 14 个中断的处理程序指针 |
| `__sp_usr` | `0x03007F00` | 用户栈顶 |
| IWRAM 最低的数据块 | `mm_fetch` @ `0x03002A34`…`0x03002BC4` | ⇒ **用户栈底 = 0x03002BC4，可用 21,308 字节** |

⇒ **`IRQ_VectorTable`（0x03002880）只比用户栈底低 832 字节** ⇒
**栈只要溢出 832 字节就会踩到中断向量表。**

**实测：攻击前 vs 冻结时的向量表**

| 项 | 攻击前 | 冻结时 |
|---|---:|---:|
| `entry[0]`（VBlank） | `0x0803EF29`（合法 ROM 地址） | ⭐ **`0x0000000C`** ← **被覆盖** |
| `entry[1]` | `0x03000EB8` | `0x00000003` |
| `entry[4]` | `0x0804DC11` | `0x00000006` |
| `entry[7]` | `0x0804DD09` | `0x00000019` |
| `entry[2]/[3]/[5]/[6]` | `0` | `0x8A / 0x0E / 0x18 / 0x03` |
| `entry[10]/[11]/[12]` | `0` | `0x02023E06 / 0x030028D0 / 0x03002998` |

⭐⭐⭐ **`entry[0]` 的 `0x0000000C` 正是派发器 `bx r3` 跳去的地址**
⇒ **闭合**：用户栈溢出 ⇒ 踩坏 VBlank 处理程序指针 ⇒ 每个 VBlank 都跳进
预取异常向量 ⇒ **中断风暴** ⇒ 场景帧停死 ⇒ 「按键全无效 / 相位不动」。

⇒ **两个症状（动作选择处冻住、目标确认处冻住）是同一个根因**：
**攻击确认链把 IWRAM 用户栈撑爆了**；V1 猜的「战斗演出不结束」与实测不符。

---

## 3. 跑了哪些验证（命令 + 关键数字）

| # | 命令 | 关键数字 |
|---|---|---|
| **U1-1** | `python tools/s49_u1_d4/u1_diag.py --rom <ROM> --move-cell 9,6 --action-index 3 --target 6,6 --observe 1200`（**改前 ROM**） | ⛔ `scene_frame` 停死 516；遥测 `phase` 被写成 `0x2A05A1`；`pc=0x03001B94`（IWRAM 数据）；`sp=0x030029F4` ⇒ **栈溢出** |
| **U1-2** | `python tools/s49_battle_balance/v1_diag_freeze.py --rom <ROM> --index 3 --cells "9,6"`（**改后 ROM**） | ✅ `after = {phase: 8, scene_frame_before: 511, scene_frame_after: 555, advanced: True, control_error: 0, player_error: 0}` ⇒ **不再冻住** |
| **U1-3** | `python tools/s49_battle_balance/v1_battle.py --rom <ROM> --out build/u1/run-a-tools --boot --max-turns 400 --use-tools` | ✅ 收据含 **`{"do": "target-accepted", "frame": 542, "enemy": 7, "cell": [6, 6], "phase": 22}`**；⛔ 随后 `{"do": "rom-frozen", "phase": 20, "scene_frame": 583}`（相位 20 = target_confirmation） |
| **U1-4** | 同上（**不用忍具**，普通招式 active 5） | ✅ 同样出现 `target-accepted`（`cell [8,7]`）；⛔ 同样停在相位 20 ⇒ **两个招式同一条深链** |
| **U1-5** | `python tools/s49_u1_d4/u1_diag.py … --crash-dump`（改后 ROM，目标确认处） | `pc=0x030011E8`（IRQ 派发器）、`r3=0x0000000C`、`sp=0x03007FE8`、IRQ 向量完好、IE/IF 正常、被中断 PC = `VBlankIntrWait` |
| **U1-6** | `bash build/u1/gen_su.sh`（同编译参数 + `-fstack-usage`） | ⭐ 场景栈帧 **7136 → 6144**；`resolve_battlefield_object_event` **8088**；`battle_session<12>` = **8052**（`arm-none-eabi-g++` 实测 `sizeof`） |
| **U1-7** | `bash build/u1/addr2line.sh 0x08050D0E 0x080118CB 0x080118CE` | `VBlankIntrWait` / `battle_range_overlay::_restore_action_palette()`（`battle_runtime_scene.cpp:2550`）/ `bn::optional<bn::bg_palette_ptr>::reset()`（同函数 `:2558`） |
| **U1-8** | 构建 `make -j4`（`LIBBUTANOABS` 已导出） | `ROM fixed!`；**ROM sha256 = `c69ba4e4b76e53215215de569688c9afd23fae9f98ad89a92dc33f37ac9a763a`**；无新增告警（仍只有既有的 `battle_turn_flow.h:48` 一条 `-Wstack-usage=16384`） |
| **U1-8b** | 同上（中间那版 ROM `16bf746f…`） | 同样的 `target-accepted` + 同样的相位 20 冻结 ⇒ 步骤 (b) 的 `noinline` 包装器**没有行为变化**（只省 8 字节） |
| **U1-9** | 单测棘轮：HEAD 基线 vs 工作区 | 见 §3.1（**多出的那一项是 U2 的在制品，不是本流引入**） |
| **U1-10** | 判定台残差 | ⛔ **未跑**：残差台要求**同一帧集 + 同一 ROM**，而本流换了 ROM（`3973adcd…` → `c69ba4e4…`）⇒ 判决会是 `incomparable`。**必须由 U3 在新 ROM 上重跑 12 步流水线**（父代理 §3.2）。见 §6 风险。 |
| **U1-11** | `python tools/s49_battle_balance/v1_battle.py --rom c69ba4e4… --out build/u1/run-c-tools --boot --max-turns 400 --use-tools` | ✅ `{"do": "target-accepted", "frame": 542, "enemy": 7, "cell": [6, 6], "phase": 22}`；⛔ `{"do": "rom-frozen", "phase": 20, "scene_frame": 583}` ⇒ **与 16bf746f 版逐项相同** |


### 3.1 单测棘轮（HEAD 基线 vs 工作区）

| | pass | fail |
|---|---:|---:|
| HEAD 基线（`build/run-baseline-tests.sh`，`git archive HEAD` 快照） | **101** | **20** |
| 工作区（`build/w1-run-all-tests.sh`） | **117** | **21** |

失败名单（两边**逐名相同**的 20 项）：

```
test_battle_all_scenario_runtime        test_battle_campaign_route
test_battle_campaign_save                test_battle_campaign_scenario_42
test_battle_campaign_scenario_43         test_battle_campaign_scenario_44
test_battle_campaign_scenario_45         test_battle_campaign_scenario_46
test_battle_campaign_scenario_47         test_battle_campaign_scenario_49
test_battle_dynamic_deployment_turn      test_battle_material_pickups
test_battle_presentation_controller      test_battle_runtime_scene_gate
test_battle_s49_input_flow               test_battle_s49_opening
test_battle_scene_character_actions      test_battle_scene_controller
test_battle_scene_multi_unit             test_battle_scene_results
```

⭐ **多出来的那一项（`test_battle_range_ui_phase_truth_table`）不是本流引入的**，
证据三条：

1. 它**只 `#include "konoha/battle_range_ui_style.h"`** ⇒ 单元测试根本不链接
   `battle_runtime_scene.cpp` ⇒ **本流改的 `.cpp` 不可能影响它**；
2. 它是**未被 git 跟踪的新文件**（`git archive HEAD` 的基线快照里根本没有它，
   基线的 `game/tests/` 只有 `test_battle_range_ui_storage.cpp` 与
   `test_battle_range_ui_style.cpp`）⇒ 它**只可能**在工作区里失败；
3. `battle_range_ui_style.h` / `test_battle_range_ui_style.cpp` 在
   **22:49** 被改过（U2 的独占文件，U2 本波正在改）⇒ 它的红是 **U2 的在制品**。

⇒ **本流没有引入任何单测失败**；但按任务书「多出任何一项 ⇒ 变红」的字面口径，
**棘轮在本波结束时是红的**，变红项归 U2。

---

## 4. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **U1-1** | D4 = 「玩家伤害招式的**特制战斗演出**不结束」⇒ 输入全死（V1 的定位） | 读遥测的 `presentation_busy` / `presentation_combat_stage` / `scene_frame` | ⛔ **不成立**：冻结点上 `presentation_busy = 0`、`combat_stage = complete`（演出**根本没开始**）；`phase` 被写成 `0x2A05A1` ⇒ 是 **CPU 跑进野地址** | **已证伪** |
| **U1-2** | D4 = 「射程内有活敌人」是触发条件 | 同一 ROM 上把鸣人在第 1 回合走到离蜂 3 格 vs 5 格，分别确认忍具 1 | ✅ **成立**（与 V1 一致）：离蜂 3 格 ⇒ 冻；离蜂 5 格 ⇒ 不冻（动作选择正常） | **已确认** |
| **U1-3** | ⭐ 冻结 = **IWRAM 栈溢出**（不是非法指令） | mGBA 调试器读 `sp` / `pc` / `lr`，再与 `__sp_usr`、IWRAM 最低数据块、`.su` 栈链算术对拍 | ✅ **成立**：`sp=0x030029F4` 比可用栈底低 **464 字节**；`pc=0x03001B94` 是 IWRAM **数据**；链算术 21 764 ≈ 实测 21 772 | **已确认** |
| **U1-4** | ⭐ 最深帧 = `resolve_battlefield_object_event` 的 **8052 字节会话拷贝** | 读 `.su`（`-fstack-usage` 重生成）+ `arm-none-eabi-g++` 实测 `sizeof(battle_session<12>)` | ✅ **成立**：`battle_action_system.h:765` 的 `battle_session<MaxUnits> next = session;`，`sizeof` = **8052** | **已确认** |
| **U1-5** | ⭐ 压小场景函数栈帧 ⇒ 冻结消失 | 把 9 个文本生成器 + 4 个渲染器 + 遮罩 + 2 个向量搬到 EWRAM 静态，重建重测 | ✅ **成立**：栈帧 7136 → 6144；「离蜂 ≤3 格确认忍具 1」不再冻住（场景帧 511 → 555） | **已确认（已修）** |
| **U1-6** | ⭐ 动作确认链通了 ⇒ 会出现 `target-accepted` | `v1_battle.py` 进攻模式（忍具 / 普通招式各一次）读收据 | ✅ **成立**：两种招式都出现 `{"do": "target-accepted", ...}` | **已确认** |
| **U1-7** | ⭐ 目标确认处的冻结 = 同一个栈溢出 | 冻结点读 `sp` / `pc` / `r3` + IRQ 帧 | ⛔ **不成立**：`sp=0x03007FE8`（**离栈顶只 24 字节**，没溢出）；`pc` 在 **IRQ 派发器**，`r3=0x0000000C` ⇒ **中断风暴**，与 U1-3 是**两个缺陷** | **已证伪** |
| **U1-8** | IRQ 派发到野指针 = 栈踩了 IRQ 向量 | 读 `0x03007FFC` 与 IE/IF | ⛔ **不成立**：向量 `0x030010E4` **完好**，IE/IF 只有 VBlank 且正常 ⇒ 是**处理程序指针本身**被写坏 | **已证伪** |
| **U1-9** | ⭐ 处理程序指针是被**射程覆盖层的调色板还原**写坏的 | IWRAM 窗口残留返回地址 addr2line | ⛔ **不成立**：真正的元凶是 `IRQ_VectorTable`（0x03002880）被**用户栈溢出**覆盖（`entry[0]` 从 `0x0803EF29` 变成 `0x0000000C`）。覆盖层的调色板还原只是**恰好在附近**跑过 | **已证伪** |
| **U1-10** | 蜂的 HP 会随 `target-accepted` 下降 | 读收据的 `bee_hp_start/end` | ⛔ **不成立**：战斗在目标确认处中断，伤害结算没跑完 ⇒ 蜂 HP 仍是 25/25 | **已证伪** |
| **U1-11** | ⭐ **两个症状是同一个根因**（不是两个缺陷） | 读 devkitARM 的 `IRQ_VectorTable`（0x03002880，14 项）攻击前 vs 冻结时的内容 | ✅ **成立**：冻结时 `entry[0]`（VBlank）由 `0x0803EF29` 变成 **`0x0000000C`** = 派发器 `bx r3` 跳去的地址；而该表**只比用户栈底低 832 字节** ⇒ 栈溢出必然踩到它 | **已确认** |
| **U1-12** | ⭐ 剩余的修复量 = **还需腾出 ≥832 字节**（实测） | 链算术 + `IRQ_VectorTable` 与栈底的距离 | ✅ **成立**：目标确认链的深度 ≈ 23,464（场景 6136 + `confirm` 896 + `_confirm_target` 592 + **`target_legal` 2160** + `confirm_target_in_place` 808 + `resolve_draft_in_place` 800 + `resolve_area_draft_in_place` 1496 + `_resolve_battlefield_object_event_in_place` 1424 + `resolve_battlefield_object_event` 8088）⇒ 比可用栈多约 **2,156 字节** ⇒ **必须改 `battle_action_system.h`（8052 字节会话拷贝）才能真正闭合** | **已确认** |


---

## 5. 接线点清单（交父代理）

### 5.1 ⭐ D4 的**根因修复**（不在 U1 独占文件里 ⇒ 交父代理串行合并）

| # | 接线点 | 文件 / 位置 | 说明 |
|---|---|---|---|
| **U1-W1** | ⭐ **`resolve_battlefield_object_event` 的 8052 字节栈拷贝** | `game/include/konoha/battle_action_system.h:759-776` | `battle_session<MaxUnits> next = session;`（`:765`）把整个会话拷到栈上。**这是栈溢出的根因**。修法：照抄 `battle_encounter_runtime::_transaction_session()`（`battle_encounter_runtime.h:939`）的模式，用 **EWRAM 事务工作区**代替栈拷贝。**改完这一处，攻击确认链整体下移 8052 字节 ⇒ 裕量约 8 KB**，U1 的场景帧压缩就退化为「保险」而非「必需」。 |
| **U1-W2** | ⭐ **目标确认 ⇒ 中断风暴** | `game/src/battle_runtime_scene.cpp`（覆盖层调色板 ↔ 战斗演出的 8bpp cohort 交接） | 冻结点证据见 §2.4。**待查的三个候选**：(a) `battle_range_overlay::_restore_action_palette()`（`:2550/2558`）在地图 8bpp 调色板被释放后仍往里写色；(b) `battle_combat_stage_runtime_renderer::_release_background_before_bpp_transition()`（`:5470` 附近）释放地图 BG/调色板时，覆盖层仍攥着 `bn::bg_palette_ptr`；(c) 战斗演出新建 4bpp 对战背景时与 8bpp 地图的调色板 cohort 冲突。**建议的最小修法**：战斗演出接管屏幕**之前**先让覆盖层**放弃**（而不是还原）它保存的调色板。 |
| **U1-W3** | 判定台残差必须**在��� ROM 上重算** | `tools/s49_package/`（U3 独占） | 本流 ROM 从 `3973adcd…` 变成 `16bf746f…` ⇒ 残差判决必然是 `incomparable`（V3 已修的仪器会显式接受新基线）。**U3 必须重跑 12 步流水线并给出新基线的残差数字。** |

### 5.2 黑场任务 B 的四个硬切（事件 1 / 2 的清单交父代理）

| # | 事件 | 帧号 | 归属 | 接线点清单 |
|---|---|---|---|---|
| **U1-B1** | 事件 1：开机 → 标题多出 8 帧纯黑 | 27–34 | ⛔ **不在 U1 独占文件里** | 开机/标题路径：`game/include/konoha/battle_opening_title.h`（新文件）+ `src/main.cpp` 的开机流程；**黑场常量**在 `battle_runtime_scene.cpp:200`（`battle_black_field_event1_hold_frames = 6`）与 `:238`（`battle_black_field_event1_lead_frames = 38`）。**开机路径自己也要走一遍「淡出→持黑→淡入」**，目前它在标题路径里是**直接黑 8 帧**。请父代理指定归属后由该流改。 |
| **U1-B2** | 事件 2：准备场景 → 战斗多出 6 帧纯黑 | 527–532 | ⛔ **不在 U1 独占文件里** | `game/src/battle_preparation_scene.cpp`（准备场景）与战役路径（`battle_campaign_scene_progression.h`）。**修法**：战斗场景的**第一帧**必须就画出背景（战斗场景在 `battle_runtime_scene.cpp:8248` 建 `map`，但黑场 lead 帧把它盖住了 ⇒ 交接完成前屏上什么都没有）。 |
| **U1-B3** | 事件 4：生长段结束 → 对白 2 帧纯黑 | 1657–1658 | ⚠️ 跨场景 | 根因已由 V2 查实 = **地图 → 对白背景的 8bpp 调色板交接**（释放+提交后再分配）。修法 = 把这次交接**挪进遮罩还盖着屏幕的持黑段**。持有遮罩的是 `battle_runtime_scene.cpp` 的黑场循环（`:8572` `black_field_frame`），而对白背景在 `battle_dialogue_background_runtime_renderer`（同一文件）。**⇒ 两侧都在 `battle_runtime_scene.cpp`，理论上 U1 可做，但需要先复现该帧段（本波预算不够）**。 |
| **U1-B4** | 事件 5：对白段内部 8 帧纯黑 | 2123–2130 | ⛔ 对白渲染路径 | `battle_presentation_*` / 对话框渲染器（V2 §4 第 4 行）。交父代理指定归属。 |

### 5.3 生长段（级 24–31 每级 4 帧、级 36 六帧）

* **Z2 那套 ROM 内逐级耗时探针需要重建**：`rebuild_ticks` / `frame_ticks` / `missed_frames`
  （Z2 放在 `battle_black_field_star.h`，**该文件不在 U1 独占清单里**；若要重建，
  建议改放到 U1 独占的 `battle_black_field.h`，或由父代理指定归属）。
* **符号表里已无那两个数组 ⇒ 地址要重取**（用 `arm-none-eabi-nm` 在**当前 ROM**
  的 ELF 上取，不能用 wave 13/16 的旧地址）。
* **V2 的新线索仍然有效**：级 31 vs 32 只差 2 个块却 4→2 帧 ⇒ **差值不在精灵数/块数**。
* ⭐ **本波顺手拿到的一条硬数据**：重制侧的构建带 `-Wstack-usage=16384`，
  **只报 ≥16 KB 的帧**；Z2 的探针要回答的是「级 24–31 的 update 为什么越过一帧预算」，
  那是**时间**不是**栈**，所以必须重建计时探针（`rebuild_ticks`/`frame_ticks`/`missed_frames`），
  不能靠栈报告。

---

## 6. 卡在哪 / 剩余风险

1. ⛔ **「真实打完仗」仍未达成**：目标确认处的**中断风暴**没修掉，
   ⇒ 伤害结算跑不完 ⇒ 蜂的 HP 没下降过 ⇒ `outcome=1` 不可达 ⇒
   结算链的真实版拿不到。**这是 D4 剩下的唯一阻塞。**
   ⭐ **闭合它必须动 `battle_action_system.h`（U1-W1）**：把
   `resolve_battlefield_object_event` 的 8052 字节会话拷贝换成 EWRAM 事务工作区
   （一次改动就把攻击确认链整体下移 8052 字节 ⇒ 裕量约 8 KB）。
   只在 `battle_runtime_scene.cpp` 里继续压场景帧**不够**：还差约 2,156 字节，
   而场景帧已经只剩 6136 字节（其中绝大部分是**被内联进来的渲染期函数**）。
2. ⛔ **判定台残差未测**：本流换了 ROM，残差必须在**新 ROM** 上重算（U1-W3）。
   ⚠️ **风险**：把 4 个渲染器 / 9 个文本生成器 / 遮罩从栈搬到 EWRAM **静态**会改变
   **EWRAM 堆的排布** ⇒ Butano 的 VRAM/OAM 分配顺序可能变 ⇒ **画面可能变**
   ⇒ 残差可能**变大**。这是本波最需要父代理盯的一条。
   （若残差变大，**优先回退**「4 个渲染器 + 遮罩」这几项，只保留「9 个文本生成器 + 2 个向量」，
   再用别的杠杆补足栈。）
3. ⚠️ **新静态对象的生命周期**：4 个渲染器现在是**函数级静态**，
   场景的 `aborted` 提前返回路径（`:8558` 的 START 退出）**不会**再像局部对象那样
   析构释放 Butano 资源。本波已确认：渲染器在场景入口显式 `reset()`，
   且战斗演出不忙时 `combat_stage_renderer.update()` 自己会释放资源；
   但**这条路径没有被实测覆盖**（本波没跑到 aborted 分支）。
4. ⚠️ **`.su` 栈报告是陈旧的**（16:19 的一次性产物）：任何引用栈数字的结论
   都必须用 `build/u1/gen_su.sh` 重生成。
5. ⚠️ **本波的诊断器只覆盖了忍具 1 与普通招式 active 5** 两条路径；
   `battle_action_combinations::resolve`（9504 B）那条**组合技**链没有实测。
   组合技一旦可达，栈裕量会被再次吃掉 ⇒ **U1-W1 是必须做的**。
6. ⚠️ **单测棘轮在本波结束时是红的**（多出 `test_battle_range_ui_phase_truth_table`），
   但该项**不是本流引入**（§3.1 有三条证据）⇒ 归 U2 的在制品。


---

## 7. 确认

* **新文件一律 LF、无 BOM**：`tools/s49_u1_d4/u1_diag.py`、
  `notes/s49-fidelity/U1-d4-fix.md`、`build/u1/*.sh`；
* **未提交 git**（两个仓都没有 `git add/commit`）；
* **未改** `battle_range_ui_style.h` / `battle_result_content.h` / `graphics\`（U2 独占）；
* **未改** `battle_combat_presentation.h` / `battle_scene_presentation.h` /
  `battle_black_field.h` / `battle_black_field_timing.h`（本波定位到的缺陷都不在这四个文件里）；
* 逆向线 `D:\Shell\gba-naruto-reverse`：**全程只读，本波未访问**；
* 共享的 `build/mgba-probe/mgba-probe.exe`：**未动**（本流探针建在私有的
  `build\mgba-probe-u1\`）；孤儿 `mgba-probe.exe` **0 个**；
* **没有伪造任何帧**：所有数字都来自 ROM 自己的遥测与 mGBA 调试器现场。
