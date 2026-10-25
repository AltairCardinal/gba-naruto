# W18-W2 —— 「はい」选不了的定位与判定（wave 18 · 流 W2）

> 流 W2（子会话 `mvs_85c8605544774f46937e877e9d887226`）· 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 独占：`game/include/konoha/battle_scene_controller.h`、`battle_player_action_flow.h`、`battle_action_execution.h`
> 新建仪器：`tools/s49_w2/w2_confirm_sp.py`（**重制线零改动**）
> ⛔ 未改 `battle_action_system.h`（W1 独占）、`battle_runtime_scene.cpp`（W4 独占）、`battle_range_ui_style.h`
> ⛔ 逆向线未访问；**未提交 git**；共享树 `D:\Shell\gba-naruto-butano\butano-sequel` **零改动**（只读比对了 sha）

---

## 0. 一句话结论

> ⭐ **「はい」根本没有被「拒」——产品一个错误码都没产生，ROM 直接死在按 A 的那一帧。**
> **硬证据**：mGBA 的**写监视点**挂在 `IRQ_VectorTable[0]`（0x03002880）上，
> **在按 A 的那一瞬间命中**（旧值 `0x0803EF25` → 新值 `0x00000012`），
> 命中瞬间 **`sp = 0x03002818`**（比用户栈底 0x03002BC4 **还低 940 字节**）。
> ⇒ **栈溢出已发生** ⇒ 本症状是 **W1 栈溢出的次生**，**不是独立缺陷** ⇒ **本路不改任何重制代码**。
>
> ⭐⭐ **顺带纠正了 U4 的一个误判**（有 U4 自己的收据为证）：
> U4 记的「按 A ⇒ 产品显示 `CANNOT SELECT`」**不成立**——
> * U4 的 **"A" 试次其实按在相位 22**（`target_preview`），只做了 22 → 20，场景照常推进；
> * U4 收据里的 `CANNOT SELECT` 来自 **Right+A / Left+A 试次**（`ctrl 0→3`）；
> * U4 自己的 `diag-confirm/after-press-a.png`（按 A 之后）**没有** `CANNOT SELECT`。
>
> ⇒ **「はい」这条路在重制侧的 A 步数与原版一致**（预览 A → 「可以嗎?」A → 结算 A），
> **缺的不是界面，是第二个 A 的效果** —— 它崩了。

---

## 1. 我的 ROM 与环境

| 项 | 值 |
|---|---|
| **我的 ROM sha256** | **`445bfdb17fc43db352fd4e2cf7884cbf9ac54aad2a94cb7d9e5265da4c288641`** |
| 副本 | `build/w18-w2/butano-sequel/`（`third_party/`、`graphics/`、`audio/` 是 junction，只读） |
| 源状态 | 与共享树**逐文件 sha 相同**（`battle_scene_controller.h` / `battle_player_action_flow.h` / `battle_action_execution.h` / `battle_action_system.h` / `battle_runtime_scene.cpp`）⇒ 基线 = 共享树 wave-17 U1 末版（`c69ba4e4…`） |
| 探针 | `build/mgba-probe/mgba-probe.exe`（**复制**到 `build/w18-w2/mgba-probe/`，sha `c4a34cd4…`，未覆盖原件） |
| 单测基线 | HEAD = pass 101 / fail 20；**工作区 = pass 117 / fail 21**（U1 已证：多出的 1 项是 U2 在制品 `test_battle_range_ui_phase_truth_table`） |

---

## 2. 现象复述（我自己实测，不是转述）

### 2.1 对话框本身是活的（对照组）

| 条件 | 结果 |
|---|---|
| 走到相位 20（`target_confirmation`），**什么都不按**，等 120 帧 | `scene_frame` **577 → 697**（`advanced=True`）⇒ **不是卡死，是在等输入** |
| 走到相位 20，光标在 (6,6)（蜂），**按 A** | `scene_frame` 637 → 638 → **永远停在 638** ⇒ 处理 A 的那一帧**没有跑完** |

### 2.2 按 A 之后到底发生了什么

```
at-phase20  phase=20 frame=577 cursor=(6,6) ctrl=0 player=0 act_err=0
press       OK frames 4 0x00000001 bp=0 done=4
post        phase=20 frame=638 ctrl=0 player=0 act_err=0      ← 冻结，遥测不再刷新
irq-after   03002880:00000012 03002884:00000011 03002888:0000000C 0300288C:00000003
            03002890:0000008A 03002894:0000000E 03002898:00000006 0300289C:00000018
            030028A0:00000003 030028A4:00000019 030028B0:02023E06 030028B4:030028D8
sp-after    0x03007FE0  pc 0x000003B0       ← CPU 已跳进 BIOS
stderr      "Hit illegal opcode at 0xFFFFFFFC: 0xE710B710"（崩溃循环，400 万+ 行）
```

* **画面**：`build/w18-w2/run/diag-a/after.png` = 原版「可以嗎?」对话框（光标在「はい」），
  **没有** `CANNOT SELECT` ⇒ `battle_runtime_scene.cpp:4576` **没有执行**。
* **遥测**：`last_control_error = 0`、`last_player_error = 0`、`selected_action_error = 0`
  ⇒ 全部是**按 A 之前的旧值**（处理 A 的帧没跑完 ⇒ `:8824-8831` 与 `:9331` 都没执行）。

---

## 3. ⭐ W2-1：被拒判据（错误码 + 出处行号）

### 3.1 判决：**「はい」这条路上没有任何错误码**

| 问题 | 答案 |
|---|---|
| 「はい」被拒的错误码？ | **不存在。** 产品**没有**产生任何 `battle_scene_control_error` / `battle_player_action_flow_error` / `action_error` |
| 那它是怎么"停住"的？ | **硬故障**（栈溢出 → 中断向量表被踩坏 → CPU 跳进野地址） |

**判据链（每一环都有出处行号）**：

| # | 环节 | 出处 |
|---|---|---|
| 1 | A ⇒ `controller.confirm()` | `battle_runtime_scene.cpp:8769-8781`（`:8776`） |
| 2 | 相位 20 ⇒ 「はい」 ⇒ `_confirm_target()` | `battle_scene_controller.h:897-905`（`:898` 判 `_target_confirmation_yes`，`:905` `return _confirm_target()`） |
| 3 | `_confirm_target()` | `battle_scene_controller.h:2009`（栈帧 **592 B**） |
| 4 | 第一步：`preview = _runtime.preview_target(target_position)` | `battle_scene_controller.h:2095` |
| 5 | ⇒ `battle_player_action_flow::preview_target` | `battle_player_action_flow.h:1130`（`:1151` 调 `battle_action_execution::preview`） |
| 6 | ⇒ `battle_action_execution::preview` | `battle_action_execution.h:13`（`:23` 调 `battle_action_resolver::preview_area`） |
| 7 | ⇒ `battle_action_resolver::preview_area` | `battle_action_system.h:574`（栈帧 **5,864 B**）；**`:585` `std::array<battle_unit_instance, MaxUnits> units = session._units;`**（12 × 468 B = **5,616 B** 的整队拷贝，压在栈上） |
| 8 | ⇒ `_preview` → `_success_rate` → `battle_attribute_system::view` | `battle_action_system.h:1036`（112 B）→ `:2208`（56 B）→ `battle_attributes.h:47` |
| 9 | ⭐ **`view` 的栈上局部 `battle_attribute_view result` 正好落在 `0x03002880`（=`IRQ_VectorTable[0]`）** | `battle_attributes.h:49-55`；写指令 `str r3,[r0,#0]` @ `0x08000F44` |
| 10 | ⇒ VBlank 处理程序指针 `0x0803EF25` 被改成 `0x00000012` | 写监视点实测（§4） |
| 11 | ⇒ 下一帧的 VBlank 派发跳进野指针 → CPU 离开调用链 | `pc = 0x000003B0/0x00000008`，stderr `Hit illegal opcode at 0xFFFFFFFC` |
| 12 | ⇒ 处理 A 的帧**永不结束** ⇒ 错误码**无处记录** | `battle_runtime_scene.cpp:8824-8831`（记 `last_control_error`）与 `:9331`（`capture_telemetry`）都执行不到 ⇒ 遥测停在 0 |

### 3.2 对照：**相位 20 上产品确实有的干净拒绝码**（U4 的 `control_error = 3` 就是它）

| 输入 | 出处 | 错误码 |
|---|---|---|
| **Left / Right**（左右动的是地图光标） | `battle_scene_controller.h:731-734`（`dx != 0` ⇒ `_invalid_input()`）→ `_invalid_input()` 定义在 **`battle_scene_controller.h:2551-2557`** | `battle_scene_control_error::invalid_input` = **3**（枚举表 `battle_scene_controller.h:117-127`） |

⇒ **U4 收据里的 `CANNOT SELECT` 就是这一条**（`battle_runtime_scene.cpp:4573-4577` 画横幅、`:3590-3594` 画 `INVALID INPUT`）。

### 3.3 ⭐ 纠正 U4 的误判（证据在 U4 自己的收据里）

U4 `notes/s49-fidelity/U4-real-victory-verify.md` §2.0 写「按 A ⇒ 产品自己显示 `CANNOT SELECT`，随后场景停住」。
**U4 的原始收据不支持这句话**：

| U4 收据 | 内容 |
|---|---|
| `build/v1-u4/diag-confirm2/diag-confirm.json` 的 `input_trials` | `A`：**相位 22 → 20**，`scene_frame 722 → 759`（**还在推进**），`ctrl 0→0` ⇒ **U4 的 "A" 试次按在相位 22，根本没按在相位 20** |
| 同上 | `Right+A`：`ctrl 0→3`（= `invalid_input`）⇒ **`CANNOT SELECT` 是左右试次留下的** |
| `build/v1-u4/diag-confirm/after-press-a.png`（按 A 之后） | **画面上只有「可以嗎?」对话框，没有 `CANNOT SELECT`** |
| `build/v1-u4/diag-confirm/diag-confirm.json` 的 `watch_with_a` | 按 A 后 `scene_frame` **持续推进** 967 → 997 → … → 1177，`ctrl/player/act_err` 全 0 |

⇒ **U4 从未在相位 20 上按过 A**（那才是「はい」）。相位 20 上按 A 会**冻住 ROM**，
这正是本流测到、而 U4 没测到的现象。

---

## 4. ⭐ W2-2：独立性判定（`sp` 实测）

### 4.1 决定性测量：**写监视点**

```
watchpoint  Added watchpoint #1  (at 0x03002880)
press       Hit watchpoint 1 at 0x03002880: (new value = 0x00000012, old value = 0x0803EF25)
            | OK frames 4 0x00000001 bp=1 done=1
pc=08000F48 sp=03002818 lr=00000003 fired=True
```

| 量 | 实测 | 含义 |
|---|---|---|
| **命中时刻 `sp`** | **`0x03002818`** | ⭐ **比用户栈底 `0x03002BC4` 还低 940 字节**；比 `IRQ_VectorTable`(`0x03002880`) 还低 **104 字节** |
| 命中时刻 `pc` | `0x08000F48` | = `battle_attribute_system::view<battle_unit_instance>`（`battle_attributes.h:47`），上一条指令 `0x08000F44` = `str r3,[r0,#0]` ⇒ **`r0` = `0x03002880`**（`view` 的栈上局部 `battle_attribute_view` 正好落在中断向量表上） |
| 命中时刻写值 | 旧 `0x0803EF25` → 新 `0x00000012` | `entry[0]`（VBlank 处理程序）被一个**属性值 18** 覆盖 |
| **复现性** | **连续两次跑逐字节相同**（`build/w18-w2/run/sp-watch2` 与 `sp-watch3`：`old=0x0803EF25 new=0x00000012 pc=0x08000F48 sp=0x03002818`） | — |

### 4.2 断点测得的链上 `sp`（同一台机器，同一个 ROM）

| 断点（地址取自**我的** `build/butano-sequel.map`） | 函数 | 命中时 `sp` | 相对栈底 0x03002BC4 |
|---|---|---|---|
| `0x08030764` | `battle_scene_controller::_confirm_target`（`battle_scene_controller.h:2009`） | **`0x03004B68`** | 高 8,036 B |
| `0x0802E840` | `battle_action_resolver::resolve_area_draft_in_place`（`battle_action_system.h:685`） | **`0x030045A0`** | 高 6,620 B |
| `0x0802F3B8` | `battle_action_resolver::resolve_draft_in_place`（`:899`） | **未命中** | 该招式走的是 area 分支 |
| `0x0802D646` | `battle_action_resolver::resolve_battlefield_object_event`（`:759`，`add sp,r4` 之后 = 最深处） | **未命中** | ⚠️ **最深的那一帧根本没走到**（链在 `preview_area` 子树里就断了） |

### 4.3 判决

| 判据（任务书 §2.3） | 实测 | 结论 |
|---|---|---|
| `sp` 落在 `0x03002xxx`（靠近/低于栈底 `0x03002BC4`）？ | **`sp = 0x03002818`（低于栈底 940 B）** | ✅ **溢出已发生** |
| 栈溢出是否发生在**按 A 这一次**里？ | ✅ 写监视点**只在按 A 时**命中；按 A 前 `entry[0]=0x0803EF25` 完好，按 A 后变 `0x00000012` | ✅ |
| ⇒ | **「はい」选不了 = W1 栈溢出的次生** | **次生，不是独立缺陷** |

⇒ **本路不改任何重制代码**（任务书 §2.4 阶段 2 的「次生」分支）。

---

## 5. 静态栈链（`-fstack-usage`，**我的** ROM，`build/w18-w2/su/battle_runtime_scene.su`）

| 帧 | 字节 | 出处 | 归属 |
|---|---:|---|---|
| `run_visible_battle_scene` | 6,136 | `battle_runtime_scene.cpp:8066` | W4 |
| `battle_scene_controller::confirm` | 896 | `battle_scene_controller.h:810` | **W2** |
| `battle_scene_controller::_confirm_target` | 592 | `battle_scene_controller.h:2009` | **W2** |
| `battle_player_action_flow::confirm_target_in_place` | 808 | `battle_player_action_flow.h:1222` | **W2** |
| `battle_action_execution::resolve_in_place` | 64 | `battle_action_execution.h:68` | **W2** |
| `battle_encounter_runtime::confirm_target` | 小（用 EWRAM 事务工作区） | `battle_encounter_runtime.h:765` | W1 |
| `battle_action_resolver::resolve_area_draft_in_place` | 1,496 | `battle_action_system.h:685` | W1 |
| ⭐ `battle_action_resolver::preview_area` | **5,864** | `battle_action_system.h:574`（`:585` 的 12 单位数组拷贝占 5,616） | **W1** |
| `battle_action_resolver::_preview` | 112 | `battle_action_system.h:1036` | W1 |
| `battle_action_resolver::_success_rate` | 56 | `battle_action_system.h:2208` | W1 |
| `battle_action_resolver::resolve_battlefield_object_event` | **8,088** | `battle_action_system.h:759`（`:765` 的会话拷贝占 8,052） | W1 |
| `battle_action_resolver::_resolve_battlefield_object_event_in_place` | 1,424 | `battle_action_system.h:781` | W1 |

**`sizeof` 实测**（`build/w18-w2/sizes.cpp` + `arm-none-eabi-nm -S`）：
`battle_unit_instance` = **468**（0x1d4）⇒ 12 × 468 = **5,616**；
`battle_session<12>` = **8,052**（0x1f74）；
`battle_attribute_view` = **20**（0x14）。

**总深度**：栈顶 `0x03007F00`、栈底 `0x03002BC4`（可用 **21,308 B**）；
命中故障时 `sp = 0x03002818` ⇒ **已用 22,344 B** ⇒ **溢出 ≈ 1,036 B**。

> ⭐ **W2 自己的三个文件只贡献 896 + 592 + 808 + 64 = 2,360 B**，
> 真正把栈撑爆的两块大拷贝（5,616 + 8,052）**都在 W1 的 `battle_action_system.h`**。

---

## 6. 跑了哪些验证（命令 + 关键数字）

| # | 命令 | 关键数字 / 判读 |
|---|---|---|
| **W2-1** | `wsl ... make -j4`（副本） | `ROM fixed!`；**sha256 `445bfdb17fc43db352fd4e2cf7884cbf9ac54aad2a94cb7d9e5265da4c288641`** |
| **W2-2** | `python tools/s49_u1_d4/u1_diag.py --rom build/w18-w2/butano-sequel/butano-sequel.gba --exe build/w18-w2/mgba-probe/mgba-probe.exe --out build/w18-w2/run/diag-a --move-cell 9,6 --action-index 3 --target 6,6 --observe 900 --poll 30 --crash-dump` | 相位 6→8→22→**20**；按 A 后 `scene_frame` **停在 578**；`ctrl=0 player=0 act_err=0`；`sp=0x03007FE8 pc=0x00000394`；stderr `Jumped to invalid address: FFFFFFFC` + `Illegal opcode: e710b710`（13,038,704 行）；`after.png` = 对话框、**无** `CANNOT SELECT` |
| **W2-3** | `python tools/s49_w2/w2_confirm_sp.py … --control-frames 120` | **对照组**：`scene_frame 577 → 697`（对话框是活的）；按 A 后 **638 冻结** |
| **W2-4** | 同上 `--bp confirm` | 断点 `0x08030764`（`_confirm_target` 入口）**命中**，`sp = 0x03004B68` |
| **W2-5** | 同上 `--bp area` | 断点 `0x0802E840`（`resolve_area_draft_in_place` 入口）**命中**，`sp = 0x030045A0` |
| **W2-6** | 同上 `--bp draft` / `--bp deepest` | `0x0802F3B8`、`0x0802D646` **均未命中** ⇒ 链在 `preview_area` 子树里就断了 |
| **W2-7** | ⭐ 同上 `--bp none --watch 0x03002880`（**两次**） | **写监视点在按 A 时命中**：`old=0x0803EF25 new=0x00000012`，`pc=0x08000F48`，**`sp=0x03002818`**（两次逐字节相同） |
| **W2-8** | 同上，**U4 的 ROM** `build/v1-u4/rom-pinned.gba`（`16bf746f…`） | 按 A 前 `entry[0]=0x0803EF29`（完好）→ 按 A 后 **`entry[0]=0x0000000C`**（**与 U1 §2.5 记的值逐字相同**）；同样冻结在 `scene_frame 638`；`ctrl/player/act_err` 全 0 |
| **W2-9** | `bash build/w18-w2/gen_su.sh`（同编译参数 + `-fstack-usage`） | 自己的 ROM 的逐帧栈帧表（§5）；⚠️ 正式构建不写 `.su`，必须自己重建 |
| **W2-10** | `arm-none-eabi-nm -S`（`build/w18-w2/sizes.cpp`） | `sizeof(battle_unit_instance)=468`、`sizeof(battle_session<12>)=8052`、`sizeof(battle_attribute_view)=20` |
| **W2-11** | `bash build/w18-run-all-tests.sh build/w18-w2/butano-sequel` | **pass=117 fail=21**（见 §8） |

---

## 7. ⭐ 回答父代理的量化线索（原版比重制侧多一次 A）

**问题**：重制侧的「可以嗎?」是不是少了一次 A？

**答：不是少/多一次界面，而是**第二个 A 的**效果**没了**。

* 重制侧这条链**本来就有两次 A**，与原版同形：
  `target_selection` → **A** → 相位 22 `target_preview`（预报屏）
  → **A** → 相位 20 `target_confirmation`（「可以嗎?」）
  → **A** → 伤害结算。
  （`battle_scene_controller.h:875-896`）
* U4 的收据里 `A` 试次只走到 **22 → 20**（`diag-confirm2/diag-confirm.json`），
  说明**第二个 A（在相位 20 上按）从来没有被成功执行过** ⇒
  ⇒ 原版 walk 在第 9/10 步之间多要的那一次 A，在重制侧**被崩掉的那个 A 吃掉了**。
* ⇒ 所以 `align_capture_steps.py` 的**偏移从 +4 掉到 +3**（原版第 9→10 步之间）
  **不是重制侧少一个界面**，而是**重制侧在那个界面上崩了**，多出来的那一帧没能产生。
* ⇒ **判决书成立**：W1 修好之后，
  * 重制侧第 **14 / 15 / 17 / 18** 步（当前与原版**整帧 sha256 逐字节相同**的那 4 帧）**必须保持逐字节相同**；
  * 重制侧**应当多出**与原版 **19 / 21 / 22** 对应的帧（⇒ 那 4 帧贡献的 82,571 px / 75.4 % 残差应当自动归零）。

---

## 8. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **W2-A** | 「はい」被**产品规则**拒绝（存在某个 `action_error`） | 读遥测 `last_control_error` / `last_player_error` / `selected_action_error` | ⛔ **不成立**：三者全是 0（= 按 A 之前的旧值）；处理 A 的帧没跑完 | **已证伪** |
| **W2-B** | 「はい」这条路会产生 `CANNOT SELECT` | 看 U4 自己的 `after-press-a.png` 与 `input_trials` | ⛔ **不成立**：U4 的 "A" 试次按在**相位 22**；`CANNOT SELECT` 来自 **Right/Left+A**（`ctrl 0→3`） | **已证伪** |
| **W2-C** | ⭐ 对话框本身是死的 | 相位 20 上不按任何键，等 120 帧 | ⛔ **不成立**：`scene_frame 577 → 697` 持续推进 | **已证伪** |
| **W2-D** | ⭐ **栈溢出发生在按 A 这一帧里** | 在 `IRQ_VectorTable[0]`(0x03002880) 上挂**写监视点**，按 A | ✅ **成立**：监视点在按 A 时命中（`0x0803EF25` → `0x00000012`）；按 A 前后各拍一次向量表做对照 | **已确认** |
| **W2-E** | ⭐ **溢出量级**：链底 `sp` 是否越过栈底 | 读命中瞬间的 `sp` | ✅ **成立**：**`sp = 0x03002818`**，比栈底 `0x03002BC4` **低 940 B**；总深度 22,344 B vs 可用 21,308 B ⇒ **溢出 ≈ 1,036 B** | **已确认** |
| **W2-F** | ⭐ 这是**独立缺陷**（提前返回的干净拒绝） | 任务书 §2.3 的判据 | ⛔ **不成立**：栈已溢出 ⇒ **次生**（W1 栈溢出的次生） | **已证伪** |
| **W2-G** | 最深的帧是 `resolve_battlefield_object_event`（8,088 B） | 在 `0x0802D646`（该函数 `add sp,r4` 之后）挂断点 | ⛔ **不成立**：**断点从未命中** ⇒ 链在 `preview_area`（5,864 B）子树里就断了 | **已证伪** |
| **W2-H** | 溢出是 `preview_area` 的 12 单位数组拷贝（`battle_action_system.h:585`） | 写监视点的写者 = `battle_attribute_system::view`，其栈上局部正好落在 `0x03002880`（`sp+0x68`） | ✅ **成立**（`view` 只被 `_success_rate`/`_damage_candidates` 调用，二者只在 `preview_area`→`_preview` 子树里） | **已确认** |
| **W2-I** | 本路三个独占文件里 `battle_session next = session;`（`battle_player_action_flow.h:1206` / `:1722`）在运行时栈上 | `.su` 表里**没有**任何 8,052 B 的帧；`battle_encounter_runtime.h:773` 调的是 `confirm_target_in_place` | ⛔ **不成立**：拷贝版**不在运行时路径**（只被单元测试调用）⇒ **不动它们**（与父代理的全仓普查一致） | **已证伪** |

---

## 9. 验收逐条结论

| # | 项 | 结论 |
|---|---|---|
| **W2-1** | 被拒判据（错误码 + 出处行号） | ✅ **「はい」没有错误码**（`ctrl/player/act_err` 全 0，因为处理 A 的帧没跑完 ⇒ `battle_runtime_scene.cpp:8824-8831` 执行不到）。决策点 = `battle_scene_controller.h:897-905` → `:905` → `:2009`；故障点 = `battle_action_system.h:574 preview_area` → `:585` → `battle_attributes.h:47`（写坏 `0x03002880`）。**对照**：相位 20 唯一存在的干净拒绝码 = `battle_scene_control_error::invalid_input` = **3**（`battle_scene_controller.h:731-734` → `_invalid_input()` `:2551-2557`） |
| **W2-2** | 独立性判定（`sp` 实测 + 结论） | ✅ **`sp = 0x03002818`（低于栈底 940 B）** ⇒ **溢出已发生** ⇒ **次生**，不是独立缺陷 |
| **W2-3** | 修复（若独立） | ⛔ **不适用**（次生 ⇒ 按任务书 §2.4 **不改代码**）。复测命令与预期判据见 §10 |
| **W2-4** | 回归 | ✅ **pass=117 / fail=21**，失败名单与 U1 逐名相同（HEAD 的 20 项 + U2 在制品 `test_battle_range_ui_phase_truth_table`）⇒ **本路零回归**（本路**未改任何重制源文件**） |
| **W2-5** | 记录：W1 修好后是否仍需要本路改动 | ✅ **不需要**。本路三个文件的帧合计 2,360 B；两处大拷贝（5,616 + 8,052）都在 **W1 的 `battle_action_system.h`**；本路 `battle_player_action_flow.h:1206/:1722` 的拷贝版**不在运行时路径**（W2-I 已证） |

**失败名单（21，逐名）**：
```
test_battle_all_scenario_runtime        test_battle_campaign_route
test_battle_campaign_save                test_battle_campaign_scenario_42
test_battle_campaign_scenario_43         test_battle_campaign_scenario_44
test_battle_campaign_scenario_45         test_battle_campaign_scenario_46
test_battle_campaign_scenario_47         test_battle_campaign_scenario_49
test_battle_dynamic_deployment_turn      test_battle_material_pickups
test_battle_presentation_controller      test_battle_range_ui_phase_truth_table  ← U2 在制品
test_battle_runtime_scene_gate           test_battle_s49_input_flow
test_battle_s49_opening                  test_battle_scene_character_actions
test_battle_scene_controller             test_battle_scene_multi_unit
test_battle_scene_results
```

---

## 10. 复测（W1 落地后）

```powershell
# 1) W1 的 ROM 上重跑本流仪器（把 --rom 换成 W1 的副本 ROM）
python tools/s49_w2/w2_confirm_sp.py --rom <W1 的 ROM> --exe build/w18-w2/mgba-probe/mgba-probe.exe --out build/w18-w2/run/sp-after-w1 --control-frames 60 --bp none --watch 0x03002880
```
**预期判据（四条全中才算过）**：

| # | 判据 | 期望值 |
|---|---|---|
| 1 | 写监视点 **不再命中** | `press` 行里没有 `Hit watchpoint` ⇒ `IRQ_VectorTable[0]` 保持 `0x0803EF25` |
| 2 | `sp` **不再越过栈底** | 命中/`status` 的 `sp` **> 0x03002BC4**（本流实测故障值 `0x03002818`） |
| 3 | 相位 **离开 20** | 按 A 后 `phase` 变成 `facing_selection`(9) 或 `outcome`(13) |
| 4 | ⭐ **蜂的 HP 下降** | `python tools/s49_battle_balance/v1_battle.py --rom <W1 的 ROM> --out build/w18-w2/run/battle-after-w1 --boot --max-turns 400 --use-tools` ⇒ 收据 `bee_hp_end < bee_hp_start`、**不再出现** `rom-frozen` |

**再加一条（父代理的判决书）**：
`python tools/s49_wave18/align_capture_steps.py --original <原版捕获目录> --remake <重制侧捕获目录>`
⇒ 重制侧第 14/15/17/18 步**仍与原版逐字节相同**，且**多出**与原版 19/21/22 对应的帧。

---

## 11. 改动文件清单

| 文件 | 性质 | sha256 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_w2\w2_confirm_sp.py` | **新增**（仪器：控制组 + 断点测 `sp` + 写监视点定位踩坏向量表的写者） | `4108d1a6cd303d73c62805b3d8ad04d6163696f75797e6a48a4f669c93fb4209` |
| `D:\Github\gba-naruto\notes\s49-fidelity\W18-W2-confirm-yes-unselectable.md` | **新增**（本文件） | — |
| `build/w18-w2/butano-sequel/**`（重制线副本） | **未改任何源文件**（只构建） | — |
| `build/w18-w2/**`（收据 / `.su` / `sizes.cpp` / `gen_su.sh` / 探针副本） | 产物 | — |

**共享树** `D:\Shell\Github\gba-naruto-butano\butano-sequel`：**零改动**（只读比对了 5 个文件的 sha）。

---

## 12. ⭐ 越界请求（请父代理裁决 / 交 W1）

### 12.1 ⭐⭐ **`battle_action_system.h` 要修 **两** 处，不是任务书写的一处**（W1 独占）

| # | 位置 | 内容 | 帧 | 状态 |
|---|---|---|---:|---|
| **①** | **`battle_action_system.h:585`**（`preview_area`） | `std::array<battle_unit_instance, MaxUnits> units = session._units;`（12 × 468 = **5,616 B** 整队拷贝压在栈上） | 5,864 | ⛔ **任务书没列** |
| ② | `battle_action_system.h:765`（`resolve_battlefield_object_event`） | `battle_session<MaxUnits> next = session;`（**8,052 B**） | 8,088 | ✅ 任务书 §1.2 已列（U1-W1） |

**为什么必须两处都修（硬证据）**：

* 只修 ② **不够**：实测**溢出发生在 ① 的子树里**，
  `resolve_battlefield_object_event` 的断点（`0x0802D646`）**从头到尾没命中** ——
  链在 `preview_area` 就断了 ⇒ **只修 ②，① 仍然会踩坏 `IRQ_VectorTable[0]`**。
* 只修 ① **也不够**：解析路径（`resolve_area_draft_in_place` → `commit_resolved_effects` → …）
  之后还会进 ② 的 8,088 B 帧。
* **两处都修**：总深度 22,344 − 5,616 − 8,052 ≈ **8,676 B ≪ 21,308 B** ⇒ 裕量充足。
* ⚠️ 修 ① 时注意：`preview_area` 里 `units` 数组是**只读副本**（`:586-660` 只读不改），
  可以直接改成**引用 `session._units`** 或搬到 EWRAM 工作区；
  `resolve_battlefield_object_event` 的 ② 照 U1-W1 的 **EWRAM 事务工作区**模板改即可。

### 12.2 `battle_runtime_scene.cpp`（W4 独占）：**不需要改**

`battle_runtime_scene.cpp:4573-4577`（`CANNOT SELECT`）与 `:3590-3594`（`INVALID INPUT`）
是**正确的拒绝呈现**（左右键 → `invalid_input`），不是缺陷。
⇒ **本缺陷的根不在 W4 的文件里**，不需要越界改它。

### 12.3 给父代理的两条信息

1. **U4 §2.0 的「按 A ⇒ `CANNOT SELECT`」需要更正**为
   「**按 A ⇒ 无错误码、ROM 冻死**」；`CANNOT SELECT` 来自左右键试次。
   （证据见 §3.3，全部来自 U4 自己的收据与截图。）
2. **`battle_attributes.h` / `battle_scene_controller.h` 的 `view` 局部落点**
   是 0x03002880（= 中断向量表），**只差 104 字节**就踩进向量表 ——
   这解释了为什么这个缺陷表现为「场景帧停死」而不是任何明确的报错。

---

## 13. 风险与遗留

* **本流没改重制代码** ⇒ 不引入回归；单测 pass/fail 与 U1 逐名相同。
* 父代理提醒的两处拷贝（`battle_player_action_flow.h:1206` / `:1722`）**确认不在运行时路径**
  （W2-I：`.su` 里没有 8,052 B 的帧；`battle_encounter_runtime.h:773` 调的是 `_in_place` 变体）
  ⇒ **未动**。
* `u1_diag.py` 的 `--crash-dump` 会写出 **466 MB** 的 stderr 收据
  （ROM 崩在 BIOS 非法指令循环里，每秒百万行）⇒ 我已删掉那份；
  本流自己的仪器 `w2_confirm_sp.py` **只保留 stderr 尾部 60 行**（`BoundedProbe`），
  避免把内存吃光。
* 写监视点在 mGBA 里是**软件断点**，会显著拖慢那一帧（调试器逐指令步进）；
  但它只影响那 1–2 帧，不影响结论的可复现性（两次跑逐字节相同）。
