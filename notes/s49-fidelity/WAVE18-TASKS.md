# WAVE18-TASKS —— wave 18 任务书（四路并行）

> 创建：2026-10-25 00:0x · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/U1-d4-fix.md` · `U2-overlay-settlement.md` ·
> `U3-wave17-package.md` · `U4-real-victory-verify.md` · `V4-bound-final.md`
> 上一波任务书：`notes/s49-fidelity/WAVE17-TASKS.md`

---

## 0. 本波目标与总原则

### 0.1 一句话目标

> **wave 18 只做两件事**：
> **A. 打通「真实打完仗」**（这是 D4 剩下的唯一阻塞，也是所有结算链真值的前提）；
> **B. 收掉结算链后半段与黑场硬切**（不依赖 A，可并行）。

### 0.2 剩余时间

72 h 窗口：起 2026-10-23 23:13 → 止 2026-10-26 23:13。
wave 18 开火时（2026-10-25 00:0x）**已用约 24.9 h，剩约 47.1 h**。

### 0.3 四路分工与**独占文件**（互斥，越界 = 违规）

| 流 | 主题 | 独占文件（**只能改这些**） |
|---|---|---|
| **W1** | ⭐ D4 根因必修（栈溢出） | `game/include/konoha/battle_action_system.h`、`game/include/konoha/battle_encounter_runtime.h`、`game/include/konoha/battle_action_combinations.h`、**`game/include/konoha/battle_turn_flow.h`**（父代理追加：胜利收尾路径） |
| **W2** | 「はい」/ `CANNOT SELECT` | `game/include/konoha/battle_scene_controller.h`、`game/include/konoha/battle_player_action_flow.h`、`game/include/konoha/battle_action_execution.h` |
| **W3** | 黑场 4 个硬切 | `game/include/konoha/battle_opening_title.h`、**`src/main.cpp`**（顶层 `src/`，不在 `game/src/` 下）、`game/src/battle_preparation_scene.cpp`、`game/include/konoha/battle_black_field.h`、`game/include/konoha/battle_black_field_timing.h`、`game/include/konoha/battle_black_field_star.h` |
| **W4** | 結算链后半段（戰後對白 + 任務菜單） | `game/src/battle_runtime_scene.cpp`、`game/include/konoha/battle_result_content.h`、`game/include/konoha/battle_presentation_content.h`、`game/include/konoha/battle_ui_model.h` |

> ⚠️ **`game/src/battle_runtime_scene.cpp` 归 W4 独占。** W1/W2/W3 **一律不得**改它
> （W1 上游已把它压到 6136 B 栈帧；W3 的事件 4 需要它，只能**报告**给父代理）。
> ⚠️ W1 与 W2 都要读 `battle_action_system.h`，但**只有 W1 能改**。
> 若某路发现必须改别人独占的文件 ⇒ **不要改**，写进笔记的「越界请求」一节，由父代理裁决。

### 0.4 ⭐ 构建隔离（本波新增，各路必须遵守）

并发构建会互相覆盖同一个 `.gba` ⇒ **每路有自己的独立副本**，禁止在共享树上构建。

| 流 | 自己的副本根目录 |
|---|---|
| W1 | `D:\Github\gba-naruto\build\w18-w1\butano-sequel` |
| W2 | `D:\Github\gba-naruto\build\w18-w2\butano-sequel` |
| W3 | `D:\Github\gba-naruto\build\w18-w3\butano-sequel` |
| W4 | `D:\Github\gba-naruto\build\w18-w4\butano-sequel` |

各副本的 `third_party/` 是指向 `D:\Shell\Github\gba-naruto-butano\third_party` 的 junction；
`graphics/`、`audio/` 是指向共享树的符号链接（**只读**）。

* **只在你的副本里改代码、构建、测量。**
* **绝对不要**在共享树 `D:\Shell\Github\gba-naruto-butano\butano-sequel` 里构建或改文件。
* 共享树 `D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba`
  当前 sha = `c69ba4e4b76e53215215de569688c9afd23fae9f98ad89a92dc33f37ac9a763a`
  （wave 17 U1 末版）。**波末由父代理统一接线 + 统一构建。**
* ⚠️ **本机构建不是字节可复现的**：同一份源码两个副本会产出两个 sha
  （已实测：共享树 `c69ba4e4…` vs W1 副本 `94afe9a4…`）。
  ⇒ **一切测量必须绑定自己那一份 ROM 的 sha**；跨 ROM 的数字**不可比**。

### 0.5 构建命令（各路统一）

```powershell
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Github/gba-naruto/build/w18-<流>/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"
```

成功后 `ROM fixed!`，产物 = `build/w18-<流>/butano-sequel/butano-sequel.gba`。
**把自己的 ROM sha 记进笔记的第一行。**

### 0.6 共享的纪律（全部适用）

1. **一次只改一处，跑一次，记一行。**
2. **一次尝试必须能回答一个「是/否」问题。**「还是卡」不是结果。
3. **连续 3 次同样结果 ⇒ 停**，写进台账，换方法。
4. **结论落进假设台账**（表：假设 / 判定方法 / 结果 / 状态）。
5. **新写文件一律 LF、无 BOM**。
6. **不提交 git**（两个仓都不 `git add/commit`）。
7. **逆向线 `D:\Shell\Github\gba-naruto-reverse` 全程只读。**
8. ⛔ **改含中文的源文件一律用 `edit`/`write` 工具**，**不要用 PowerShell `Set-Content` / `-replace`**
   （PS 5.1 按 GBK 读入写回会毁掉 UTF-8）。
9. **探针 exe 只读复用**：用 `D:\Github\gba-naruto\build\mgba-probe\mgba-probe.exe`
   **复制**到自己的目录用，**不要覆盖**它。重建探针时必须用
   `$env:KONOHA_PROBE_OUT` 指向自己的目录。

### 0.7 ⚠️ 资源纪律（全机共享）

* 本机 RAM = **32.5 GB，总空闲仅约 10 GB**；`mgba-probe` 录制进程**吃 7–8 GB 且持续泄漏**（~10 MB/s）。
  ⇒ **全机同一时刻最多 1 路在跑长录制（> 60 s）**。
  其它路用**短录制**（≤ 60 s）或只读收据类工具（`v1_battle.py` / `u1_diag.py` 这类只写收据的）。
* 跑完长录制**必须**检查孤儿进程：
  `Get-Process -Name 'mgba-probe' -ErrorAction SilentlyContinue`
* CPU 长期闲置是本任务的目标状态 ⇒ **各路尽量并行**，不要串行等待。

### 0.8 各路交付物

| # | 交付物 | 位置 |
|---|---|---|
| 1 | 笔记（含假设台账、逐条命令与数字、越界请求） | `D:\Github\gba-naruto\notes\s49-fidelity\W18-<流>-<主题>.md` |
| 2 | 改过的文件**留在自己的副本里** | `build/w18-<流>/butano-sequel/...` |
| 3 | 改动文件清单 + 每个文件的 sha256 | 笔记里的「改动文件清单」表 |
| 4 | 自己的 ROM sha + 测量数字（**绑定自己的 ROM**） | 笔记 |
| 5 | 单测结果（pass/fail + 失败名单） | 笔记 |

父代理在波末做：把各路**独占文件**从副本拷回共享树 → 统一构建 → 跑 12 步流水线 → 出包。

---

## 1. W1 —— ⭐ D4 根因必修（攻击确认链的 IWRAM 栈溢出）

### 1.1 根因（上游 U1 已用硬证据闭合，不需要你重新证明）

| 量 | 值 |
|---|---|
| 用户栈顶 `__sp_usr` | `0x03007F00` |
| 用户栈底（可用 21,308 B） | `0x03002BC4` |
| `IRQ_VectorTable` | `0x03002880`（14 项 × 4 B）**只比栈底低 832 B** |
| 攻击确认链总深 | 场景 6136 + `confirm` 896 + `_confirm_target` 592 + **`target_legal` 2160** + `confirm_target_in_place` 808 + `resolve_draft_in_place` 800 + `resolve_area_draft_in_place` 1496 + `_resolve_battlefield_object_event_in_place` 1424 + **`resolve_battlefield_object_event` 8088** + 每帧压寄存器 ≈ 460 ⇒ **≈ 23,464 B** |
| 结论 | **溢出约 2,156 B ⇒ 踩坏 `IRQ_VectorTable` ⇒ VBlank 派发野指针 `0x0000000C` ⇒ 中断风暴 ⇒ 场景帧停死** |

⭐ **最深的单帧是 `battle_action_system.h:759-776` 的 `resolve_battlefield_object_event`**，
它的 8,088 B 栈帧里 **8,052 B 是 `sizeof(battle_session<12>)`** ——
`battle_action_system.h:765` 的 `battle_session<MaxUnits> next = session;` 把整个会话拷到栈上。

### 1.2 你的任务

**把这份 8,052 B 的会话拷贝从栈上挪走。**

样板在 `game/include/konoha/battle_encounter_runtime.h:939` 的 `_transaction_session()`
（EWRAM 事务工作区）。语义必须保持不变：**事务性**（失败时不提交 `session`、不提交 `rng`）。

可选修法（择一，或给出更好的）：
1. **EWRAM 事务工作区**（照样板）：静态 EWRAM 缓冲（`MaxUnits=12` 时 8,052 B）+ `next_rng` 也放 EWRAM。
   ⚠️ 代价：EWRAM 静态占用 8 KB ⇒ **EWRAM 堆排布变化 ⇒ Butano 的 VRAM/OAM 分配顺序可能变 ⇒ 画面可能变**
   ⇒ 必须在**自己的 ROM** 上跑判定台并和基线比残差（见 §1.4）。
2. **细粒度回滚**：不拷整个会话，只备份 `_resolve_battlefield_object_event_in_place` 实际会改的字段，
   失败时按字段回滚。⚠️ 容易漏字段 ⇒ 必须逐字段核对 `_resolve_battlefield_object_event_in_place` 的写入点。
3. **其它等效方案**（例如把会话移到 EWRAM 常驻、去掉事务性拷贝并改用「先算后提交」的纯函数式写法）。

### 1.3 ⭐ 本路的判定问题（是/否）

> **「修完之后，攻击确认链的栈深是否 ≤ 21,308 B（可用栈）？」**

必须给出**逐帧表**（帧名 + 字节）与**合计**，并用 `-fstack-usage` **重新生成**
（⚠️ `build/*.su` 是陈旧的一次性产物，正式构建不写 `.su` ⇒ 必须自己重建，
参考 `D:\Github\gba-naruto\build\u1\gen_su.sh`）。

### 1.4 验收

| # | 项 | 判据 |
|---|---|---|
| W1-1 | `resolve_battlefield_object_event` 栈帧 | 从 8,088 B 降到 **≤ 64 B** |
| W1-2 | 攻击确认链总深 | **≤ 21,308 B**，给出逐帧表 |
| W1-3 | `battle_action_combinations::resolve`（9,504 B，组合技链） | 也要给出数字；若超预算 ⇒ 一并处理（该文件归你） |
| W1-4 | 重建 ROM | `ROM fixed!`，记下自己的 ROM sha |
| W1-5 | ⭐ 真实战斗 | `python tools/s49_battle_balance/v1_battle.py --rom <你的ROM> --out build/w18-w1/run-a-tools --boot --max-turns 400 --use-tools` ⇒ 收据**不再出现** `rom-frozen`；**出现蜂的 HP 下降**（`bee_hp_start` ≠ `bee_hp_end`） |
| W1-6 | 普通招式路径 | 同上但 `--use-tools` 关掉（active 5）⇒ 同样不冻、同样掉血 |
| W1-7 | 「はい」联动 | 在你的 ROM 上跑 `tools/s49_battle_balance/v1_diag_confirm.py --move-cell 9,6 --action-index 3 --target 6,6 --trials "A"` ⇒ 记录**按 A 之后**的现象（**不要据此改 W2 的文件**，只记录） |
| W1-8 | 判定台残差 | `python tools/s49_fidelity_report.py --out build/w18-w1/report.json`（**必须绑定你自己的 ROM**）⇒ 读数记下来（⚠️ 与基线 ROM 不同 ⇒ 判决大概率是 `incomparable`，**那不是通过**；只报数字） |
| W1-9 | 单测 | `bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/w18-w1/butano-sequel` ⇒ pass/fail + 失败名单 |

> ⚠️ **W1-8 的判读**：EWRAM 排布变化**可能让残差变大**。若确实变大 ⇒
> 优先改用 §1.2 修法 2（不占 EWRAM 静态），或把静态对象挪到 IWRAM 之外的位置重试。**不要**接受「残差变大」。

### 1.5 ⭐⭐⭐ 父代理追加（2026-10-25 01:2x）：胜利收尾链 + 嵌套覆盖陷阱

> 完整依据：`notes/s49-fidelity/W18-PARENT-stack-copies.md`

**(a) 新增独占文件 `game/include/konoha/battle_turn_flow.h`。**

`battle_turn_flow.h:48` 的 `advance_empty_side` 栈帧 **16,880 B**，第 53 行是同一份
8,052 B 会话拷贝；它位于**战斗结束（胜利）**路径上。
⇒ 修前链深 = 场景 6,136 + tick 2,432 + 16,880 + 8,088 = **33,536 > 21,308** ❌
⇒ **只修攻击确认链，战斗打完那一刻照样溢出。**
⇒ 同文件 5 处拷贝（行 53 / 110 / 182 / 243 / 336）全部同样处理。

**(b) ⭐ 陷阱：事务工作区必须可嵌套（≥ 2 个缓冲）。**

`battle_turn_flow.h:66` 的 `_resolve_battlefield_objects(next, …)` 在**外层仍持有
会话副本**时，`:479-485` 又调用 `battle_action_resolver::resolve_battlefield_object_event`，
后者**自己再拷一份会话**。
⇒ **单个共享的 EWRAM 缓冲会被内层覆盖** ⇒ 事务语义被破坏
⇒ 症状 = 「结算结果偶发错乱」，**不崩、不溢出**，最难查的一类 bug。
⇒ ⛔ **切勿用取模轮换省缓冲**（嵌套返回顺序不保证）。

**(c) EWRAM 预算**：2 缓冲 = 16,104 B；3 缓冲 = 24,156 B。EWRAM 仅 256 KB。
⇒ 必须同时盯 W1-8（判定台残差）；**残差变大 ⇒ 换方法，不要接受**。

**(d) 判定问题扩成两条链**：**攻击确认链** 与 **胜利收尾链** 的最坏栈深都要 ≤ 21,308 B。

**(e) 新增验收项 W1-5b**：真实打完仗后，**场景帧必须继续推进**（不许在胜利那一刻停死）。

### 1.6 风险与退路

* 若 EWRAM 静态 8 KB 不可行（爆 EWRAM 或导致残差变大）⇒ 走修法 2，并在笔记里写清取舍。
* 若改完**仍冻住** ⇒ 说明还有第二个溢出点 ⇒ **换方法**（读 `.su` 找下一个最深的帧），
  不要在同一处反复试第 4 次。

---

## 2. W2 —— 「はい」/ `CANNOT SELECT` 的定位与修复

### 2.1 现象（U4 实测，ROM `16bf746f…`）

| 阶段 | 相位 | 现象 |
|---|---|---|
| 招式确认 | 6 → 8 `target_selection` | ✅ 通 |
| 目标确认 | 8 → 22 `target_preview` | ✅ 通（收据有 `target-accepted`，目标格 (6,6)） |
| **「可以嗎?」** | 22 → **20** `target_confirmation` | ⛔ **停在这里** |

* 屏幕上是原版的「可以嗎?」对话框（`はい` / `いいえ`），**光标在「はい」上**，按 A 之前无报错；
* **按 A ⇒ 产品自己显示 `CANNOT SELECT`**（`game/src/battle_runtime_scene.cpp:4576`，由 `rejected` 触发）；
* 不按任何键 ⇒ **场景正常推进**（657 → 709），对话框一直挂着 ⇒ **不是卡死，是等待输入**；
* `Up+A` / `Down+A` ⇒ 回到相位 22（等于取消）；`Left+A` / `Right+A` ⇒ 相位不变、`control_error = 3`
  （左右动的是地图光标，不是对话框光标）；`B` ⇒ 停住。

**驾驶侧已排除**：对话框本身正常、光标在「はい」上、原版按键口径就是按 A。
⇒ **这是产品的缺陷**。

### 2.2 代码线索（已核实）

| 位置 | 内容 |
|---|---|
| `battle_scene_controller.h:731-738` | `target_confirmation` 相位里 `move_cursor` 只接受上下（`dx != 0` ⇒ `_invalid_input()`），上下翻转 `_target_confirmation_yes` |
| `battle_scene_controller.h:897-905` | `confirm()` 在 `target_confirmation`：`_target_confirmation_yes == true`（即「はい」）⇒ 走 `_confirm_target()` |
| `battle_scene_controller.h:2009` | `_confirm_target()`（592 B 帧） |
| `battle_runtime_scene.cpp:8769-8781` | `a_pressed()` ⇒ `controller.confirm()` |
| `battle_runtime_scene.cpp:4573-4577` | `rejected` ⇒ 生成 `CANNOT SELECT` |
| `battle_runtime_scene.cpp:3587-3593` | `rejected` ⇒ 细节区显示 `INVALID INPUT` |

`rejected` 来自 `result.error != 0`（`battle_runtime_scene.cpp:8824-8829`）。

### 2.3 ⭐ 本路的判定问题（是/否）

> **「『はい』被拒的确切判据是哪一个？」** —— 给出**具体的错误码 + 出处行号**。

判定方法（两条都要做）：
1. **读遥测**：用 `tools/s49_u1_d4/u1_diag.py`（只读调用，**不改**它）在你自己的 ROM 上
   跑到相位 20，按 A，读 `ctrl` / `act_err` 两个错误码字段 ⇒ 给出数值与含义
   （错误码表在 `game/include/konoha/battle_action_system.h` 或 action_error 定义处）。
2. **判定「独立缺陷」还是「W1 的栈溢出的次生」**：
   在**冻结/拒绝现场**读 `sp`（用户栈指针）。
   * 若 `sp` 落在 `0x03002xxx`（靠近栈底 0x03002BC4）⇒ **溢出已经发生** ⇒ 本症状是**次生**；
   * 若 `sp` 仍在高位（`0x0300 7xxx`）⇒ 是**提前返回的干净拒绝** ⇒ **独立缺陷**。

### 2.4 任务

* **阶段 1（判定，必须先做）**：完成 §2.3 的两条判定，**此时不要改任何代码**。
* **阶段 2（修复）**：
  * 若判定为**独立缺陷** ⇒ 在你的独占文件里做**最小修复**（不要顺手重构），重建并复测：
    按 A ⇒ 相位离开 20 ⇒ 进入伤害结算 ⇒ 蜂 HP 下降。
  * 若判定为**次生**（栈溢出导致）⇒ **不要改代码**，写明「等 W1 落地后复测」，
    并给出复测命令与预期判据。

### 2.5 验收

| # | 项 | 判据 |
|---|---|---|
| W2-1 | 被拒判据 | 错误码 + 出处行号（硬证据） |
| W2-2 | 独立性判定 | `sp` 实测值 + 结论（独立 / 次生） |
| W2-3 | 修复（若独立） | 重建后按 A ⇒ 相位离开 20 ⇒ 蜂 HP 下降（收据里 `bee_hp_end < bee_hp_start`） |
| W2-4 | 回归 | `test_battle_scene_controller` / `test_battle_s49_input_flow` 等相关单测**不得新增变红** |
| W2-5 | 记录 | 在 W1 修好之后**是否还需要本路改动**（供父代理收口） |

> ⚠️ W2 **不得**改 `battle_action_system.h`（W1 独占）、`battle_runtime_scene.cpp`（W4 独占）。
> 若根因落在 `battle_runtime_scene.cpp` ⇒ 写进「越界请求」。

---

## 3. W3 —— 黑场 4 个硬切（把黑场事件从 6 个收敛到 2 个）

### 3.1 真值

| | 原版 | 重制侧（wave 17 实测） |
|---|---|---|
| 黑场事件数 | **2** | **6** |
| 事件 1 | 24 / 18 / 24（淡出/持黑/淡入） | 24 / 18 / **26** |
| 事件 2 | 24 / 24 / 24 | **28** / 24 / **28** |
| 持黑 18 | — | ✅ **已闭合**（与原版同形） |
| 其余 4 个 | — | ⛔ **硬切未收** |

⇒ **持黑 18 已对**；剩下 4 个是**纯黑硬切**（没有淡出/淡入渐变），需要改成渐变 + 正确帧数。

### 3.2 四个硬切清单（U1 已定位到代码位置）

| # | 事件 | 帧号 | 归属 | 修法线索 |
|---|---|---|---|---|
| **B1** | 事件 1：开机 → 标题**多出 8 帧纯黑** | 27–34 | `battle_opening_title.h` + `src/main.cpp`（**你的**） | 黑场常量在 `battle_runtime_scene.cpp:200`（`battle_black_field_event1_hold_frames = 6`）与 `:238`（`battle_black_field_event1_lead_frames = 38`）——⚠️ 这两个常量在 **W4 独占文件**里 ⇒ **不要改**，把「常量应改成多少」写进越界请求。开机路径现在在标题路径里是**直接黑 8 帧**，要改成「淡出 → 持黑 → 淡入」 |
| **B2** | 事件 2：准备场景 → 战斗**多出 6 帧纯黑** | 527–532 | `battle_preparation_scene.cpp` + 战役路径（**你的**） | 战斗场景第一帧就画出背景；现在黑场 lead 帧把它盖住了 |
| **B3** | 事件 4：生长段结束 → 对白**2 帧纯黑** | 1657–1658 | 根因 = 地图 → 对白背景的 **8bpp 调色板交接**（释放 + 提交后再分配）；持有遮罩的是 `battle_runtime_scene.cpp:8572` 的黑场循环（**W4 独占**） | ⇒ 你只做**定位 + 方案**，把「交接应挪进持黑段」的具体改法写进越界请求 |
| **B4** | 事件 5：对白段内部 **8 帧纯黑** | 2123–2130 | 对白渲染路径（`battle_presentation_*` / 对话框渲染器） | 与 `battle_presentation_content.h`（W4 独占）可能相关 ⇒ 先定位，必要时写越界请求 |

### 3.3 ⭐ 本路的判定问题（是/否）

> **「黑场事件集合能否从 6 个收敛到 2 个，且每个事件的『淡出/持黑/淡入』帧数 =
> 原版的 24/18/24 与 24/24/24？」**

### 3.4 验收

| # | 项 | 判据 |
|---|---|---|
| W3-1 | 黑场事件清单 | 自己的 ROM 上实测的**事件数 + 帧号 + 每段的帧数 + 是否渐变**，与原版逐项对齐 |
| W3-2 | B1 / B2 | 修好并复测（在你的副本里重建） |
| W3-3 | B3 / B4 | 定位到确切代码位置 + 给出可执行的修法（若需改他人独占文件 ⇒ 写越界请求） |
| W3-4 | 仪器 | `tools/s49_blackfade/`（**只读调用**）；若需新仪器，另建 `tools/s49_w3/`，**不改** `tools/s49_blackfade/` |
| W3-5 | 单测 | 同 §1.4 的 W1-9 脚本（换成你的 lane 路径） |

> ⚠️ **黑场是「玩家看得见的画面」** ⇒ 直接计入用户口径。
> 但**残差判定台**是否覆盖黑场事件，要以判定台自己的口径为准（不要自己扩大口径）。

---

## 4. W4 —— 結算链后半段：戰後對白（26,819 px）+ 任務菜單（37,694 px）

### 4.1 残差真值（U4 实测，**poke 链 / 工具自检链**，sha256 配对后）

| remake 链页 | 相位 | 原版真值 | 原版 sha256（前 16） | 重制侧 sha256（前 16） | 差 px | 差 bbox |
|---|---|---|---|---|---:|---|
| `page-014-post_battle_dialogue.png` | post_battle_dialogue | `08-postbattle-dialogue-1.png` | `2741dbc3fbf6e838` | `5fece4f6952f78b0` | **26,819** | `[0,0,240,160]` |
| `page-021-task_menu.png` | task_menu | `09-task-menu-map.png` | `cda07a18be60a1ea` | `3814df2825813f89` | **37,694** | `[0,0,240,160]` |

⇒ 两个残差都是**全屏级**（bbox = 整个 240×160）⇒ 要么重制侧**缺画**，要么原版**多画**。

**已闭合的同链各屏**（不要重复劳动）：
勝利 0 px、結算 2,582 px（= 684 px 真实战果数据 + 1,898 px 三个人物）、6 张升級屏 **0/6 px**。

### 4.2 ⚠️ 口径警告

* 上表是**「工具自检链」**（`play_settlement_chain()`：只按键、不 poke），
  **不是真实战斗链** —— 真实战斗链要等 W1 修好 D4 才有。
* ⇒ 你的任务是把**这两个相位本身**画对；**不要**把「真实战果数据」算进本路。

### 4.3 ⭐ 本路的判定问题（是/否）

> **「这两个全屏残差分别是『重制侧缺画』还是『原版多画』？各占多少 px？」**

判定方法：逐像素分类（缺画 / 多画 / 颜色差 / 结构差），
用 `tools/s49_victory_align/align_settlement.py`（**只读复用**）或自建 `tools/s49_w4/`（**新建，不改** U4 的目录）。

### 4.4 任务

1. **定位**：这两块画面在重制侧由谁画？
   候选：`battle_result_content.h`、`battle_presentation_content.h`、`battle_ui_model.h`（相位 → UI 层 switch）、
   `battle_runtime_scene.cpp`（绘制）。**先确认真值（`build/s49-victory-capture/w4/settlement-truth/`）
   的两张图到底长什么样**，再决定改法。
2. **修复**：把残差降到 0；若**不可归零**，给出**硬证据 + 可证下界**（照 `tools/s49_z3_bound/` 的做法）。
3. ⚠️ 若需要**新增/修改 `graphics/` 里的图**：你副本里的 `graphics/` 是**指向共享树的符号链接** ⇒
   **必须先**把它换成真实目录副本再改（否则会污染共享树 ⇒ 影响其它三路）：
   ```powershell
   python -c "import shutil,os; p=r'D:\Github\gba-naruto\build\w18-w4\butano-sequel\graphics'; t=p+'.link'; os.replace(t,p) if os.path.islink(t) else None; shutil.copytree(r'D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics', p, dirs_exist_ok=True)"
   ```
4. **结算屏人物（1,898 px）**：U2 已给出结论 —— 逐人 8bpp 不可能（硬件只有一套 8bpp OBJ 调色板），
   可行方案是「三个立绘合成一张 8bpp 图集 + 共用一套 8bpp OBJ 调色板」。
   **本波不做**（会与本路主线冲突、且要先等真实战斗链），但**请给出可行性评估与工作量估计**，供 wave 19 排期。

### 4.5 验收

| # | 项 | 判据 |
|---|---|---|
| W4-1 | 残差分类 | 缺画/多画/颜色差 各多少 px（自己的 ROM 上实测） |
| W4-2 | 戰後對白 | 残差降到 0，或给出下界 + 证据 |
| W4-3 | 任務菜單 | 同上 |
| W4-4 | 逐屏对照 | 用 `tools/s49_victory_align/align_settlement.py` 给出**整链**的逐屏差表（不要只报两屏） |
| W4-5 | 结算屏人物评估 | 8bpp 图集方案的可行性 + 工作量估计（不实现） |
| W4-6 | 单测 | 同 §1.4 的 W1-9 脚本（换成你的 lane 路径） |

> ⚠️ **不要改** `battle_range_ui_style.h`（U2 的文件，wave 17 留下一个红测试
> `test_battle_range_ui_phase_truth_table`，见 §5）。

---

## 5. 父代理留给自己的活（各路不要碰）

1. **wave 17 遗留的红测试**：`test_battle_range_ui_phase_truth_table`
   （U2 把「青（可达集）不再被 `move_phase` 锁住」当成本轮修复 ⇒ 与该测试的
   `assert(got != kind::move)` 冲突）。U2 已证明该改动**单独是 no-op**
   （青集合被绿集合盖住 ⇒ `青 ∧ 橙` 共现仍是 0/783，walk 相位 130 格一个没降）。
   ⇒ 父代理会处理：**要么回退 U2 的规则改动（恢复测试绿），要么改测试**。
   各路**不要**动 `battle_range_ui_style.h` 与它的测试。
2. **波末接线**：把四路的独占文件从副本拷回共享树 → 统一构建 → 12 步流水线 → 出包 → 回填
   `docs/sequel-roadmap.md`。
3. **残差下界重算**：新 ROM 上重算（`tools/s49_z3_bound/`）。
4. **1:1 报告定稿**：`docs/s49-fidelity-report-20261024.md`。

---

## 6. 波末验收（父代理执行）

| # | 项 | 判据 |
|---|---|---|
| 1 | 共享树构建 | `ROM fixed!`，sha 记录 |
| 2 | 12 步流水线 | `python tools/s49_package/run_pipeline.py --out build/s49-package-w18` |
| 3 | 棘轮 | 残差**只许变小**；ROM 变了且残差没变大 ⇒ `incomparable`（退出码 2）**不是通过** |
| 4 | 真实战斗 | 收据里出现 `bee_hp_end < bee_hp_start` |
| 5 | 结算链 | 胜利 / 結算 / 升級 / 戰後對白 / 任務菜單 逐屏差表 |
| 6 | 黑场 | 事件集合 = 2 个，帧数与原版一致 |
| 7 | 路线图 | `docs/sequel-roadmap.md` 回填 wave 18 里程碑 |
