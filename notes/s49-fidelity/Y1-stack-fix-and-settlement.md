# Y1 —— 栈溢出修复（尺寸中性）补交笔记 + 结算链运行帧

> 工具：`tools/s49_battle_balance/y1_{size_check.sh,size_probe.cpp,stack_watch.py,addr2line.sh,big_bss.sh,play.py,phase_offset.sh,settlement_table.py}`、
> `w1_{probe,boot,record,drive,verify,settlement_table,brightness,diag}.py`、
> `x1_{telemetry,settlement,play}.py`、
> **本波新增**：`z1_{dialogue_probe.py,settlement_chain.py,controller_offsets.cpp}`
> 产物：`build/z1/`（`chain-e` / `chain-f` 两跑 + `settlement-table-z1.json` + `judgment-report.json`）
> 2026-10-24 · 流 Z1（wave 14，补 wave 13 的 Y1 欠账）。**所有数字都是本机实测。**
> 重制线 **零改动**（ROM 保持 `2c2b48d9…` 逐字节不变）；逆向线 **零改动**；**未提交 git**。

---

## 0. 一句话结论

**Y1 的栈溢出修复是真的落地了（`sizeof(battle_scene_presentation_event)` = **148**，与 HEAD **逐字节相同**，
只有两个 `bool` 换了位置；构建**没有新增** stack-usage 警告），但它的第三个判据「当前 ROM 上打完仗」
**被另外两个产品缺陷挡死**：**第 2 回合对白时 OBJ 调色板耗尽**（Butano 致命错误，ROM 停机），
**战后对白段没有 UI 层 + 文本里有非法 UTF-8**（⇒ 结算链永远走不到 `complete`）。
⇒ **结算链运行帧已录出**：**15 屏、两次独立跑逐字节一致**，其中 **原版 9 张真值里的 6 张
（6 个升级屏 + 忍具一览）逐像素完全相同（差 px = 0）**。

---

## 1. 改动文件清单

### 1.1 本仓库（`D:\Github\gba-naruto`）

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\notes\s49-fidelity\Y1-stack-fix-and-settlement.md` | **新增** | 本文件。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\z1_settlement_chain.py` | **新增** | ⭐ **结算链闭环驱动器**：闭环开机 → 把控制器状态 poke 进 `outcome`（读回验证）→ **按画面闭环走完结算链**（读渲染帧 → 决策 → 按键；一个键不改变画面就换下一个键）→ 每屏 PNG + sha256 收据。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\z1_dialogue_probe.py` | **新增** | ⭐ **卡死诊断器**：在指定的一次按键上做「画面还在动吗 + 四种按法哪种能推进」的判定，并存盘卡死点的 savestate。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\z1_controller_offsets.cpp` | **新增** | 控制器的成员偏移探针（`#define private public` + `offsetof`）。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\x1_telemetry.py` | **修改** | ⭐ **修掉一个把整个闭环读数错位一格的仪器 bug**（见 §4.1）。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\y1_play.py` | **修改** | ⭐ 修掉「按住不放被场景的闩锁吞掉」的按法（见 §4.2）。 |

### 1.2 没有改的

**重制线任何文件一个字未改**；逆向线任何文件未改；其它流的仪器（`s49_victory_capture` /
`s49_package` / `s49_fidelity_report` / `mgba_probe` / `s49_overlay_align` …）一律**只读调用**。
共享的 `build/mgba-probe/mgba-probe.exe` **未动**（私有探针建在 `build/mgba-probe-z1/`）。

⚠️ **ROM 身份（重要）**：本流**所有测量**都跑在 **W4 钉住的那一份拷贝**上：

```
build/s49-package-y4-final/work/pinned-rom/measured.gba
sha256 = 2c2b48d91fbe32447845a7ddf683b29badefd30202e14c230efc98640a72fca0   (mtime 16:10:32)
```

⇒ **与残差基线用的 ROM 逐字节相同**（「必须同 ROM 比」这条满足）。
⚠️ 但**工作树里的 `butano-sequel/butano-sequel.gba` 在本流跑到一半时被 Z2 重建了**
（17:45:05 ⇒ sha `a1637e67…`）⇒ **本流没有用它做测量**，也没有碰它；
`battle_scene_presentation_event.h`（16:08:09）与 `battle_runtime_scene.cpp`（16:19:06）
的 mtime 都早于本流开始（17:19）⇒ **重制线的源码我一行没动**。

---

## 2. 任务 A：栈溢出修复（尺寸中性）——**手法 + 证据**

### 2.1 手法：把新增字段塞进**原有的对齐空隙**

`battle_scene_presentation_event` 是**按值**在场景函数里到处复制的栈上局部变量
（wave 11 的 W3 在 `battle_scene_snapshot` 上踩过同一个坑：1672 → 1676 ⇒ ROM 跑出 `Illegal opcode`）。
wave 11/12 的结算链往这个结构体里加了
`struct battle_settlement_presentation`（4 字节）+ `bool has_settlement`（1 字节）。

**HEAD 的内存布局**（`y1_size_check.sh` 的逐字段偏移实测）：

```
111 has_resource            1
112 resource_type           1
113..115  ← 3 字节对齐空隙（resource_amount 是 int，4 字节对齐）
116 resource_amount         4
...
138 passive_secondary_status_applied  1
139 special_combination     1
140 direct_attack           1
141..143  ← 3 字节对齐空隙（capture_count 是 int，4 字节对齐）
144 capture_count           4
                              ⇒ 148 字节
```

**Y1 的修法**：把两个 `bool`（`special_combination` / `direct_attack`）**搬进 113 那个 3 字节空隙**
（还剩 1 字节空隙在 115），于是 139..143 空出**连续 5 字节**，正好放下
`has_settlement`（1）+ `settlement`（4）。

**为什么正好放得下**：`battle_settlement_stage` 是 `enum class : std::uint8_t`
⇒ `battle_settlement_presentation` = 1(`stage`) + 1(`page`) + 1(`page_count`) + 1(`character_id`)
= **4 字节，align 1** ⇒ 不需要任何额外填充。
文件末尾还加了两条 `static_assert` 把这个不变量钉死：

```cpp
static_assert(sizeof(battle_scene_presentation_event) == 148, ...);
static_assert(sizeof(battle_settlement_presentation) == 4, ...);
```

### 2.2 ⭐ 证据：`sizeof` 与 HEAD **逐字节相同**

命令：

```powershell
powershell -File tools\s49_battle_balance\y1_dump_head.ps1
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/tools/s49_battle_balance/y1_size_check.sh
```

`y1_dump_head.ps1` 的输出：**`MATCH: build/head-baseline == git HEAD`**（HEAD 快照是 `git show HEAD:` 的原文）。

| 项 | HEAD | 工作区 |
|---|---:|---:|
| `sizeof(battle_scene_presentation_event)` | **148** | **148** |
| `alignof(battle_scene_presentation_event)` | 4 | 4 |
| `sizeof(battle_settlement_presentation)` | n/a（HEAD 没有） | 4（align 1） |
| `sizeof(battle_scene_snapshot<12>)` | **1672** | **1672** |
| `sizeof(battle_scene_control_result)` | 212 | 212 |
| `sizeof(battle_player_action_flow_result)` | 56 | 56 |
| `sizeof(battle_scene_unit_view)` | 56 | 56 |

**逐字段偏移 diff**（`build/y1-size/head.txt` vs `cur.txt`）——**只有两行不同**：

```
-special_combination                       139    1
-direct_attack                             140    1
+special_combination                       113    1
+direct_attack                             114    1
 capture_count                             144    4      ← 两边都在 144
```

⇒ **结构体大小 148 = 148，`capture_count` 的偏移 144 = 144，其余每一个字段的偏移逐个相同**
⇒ 这就是「与 HEAD **逐字节相同**」的可判定证据。

### 2.3 三个判据的达成情况

| 判据（WAVE13-TASKS §1.2） | 结果 | 证据 |
|---|---|---|
| ① `sizeof(battle_scene_presentation_event)` **与 HEAD 完全相同** | ✅ **达成** | 148 = 148；逐字段偏移 diff 只有两个 `bool` 换了位置（§2.2） |
| ② 构建**不再出现该结构的 stack-usage 警告** | ✅ **达成** | 见下 |
| ③ ⭐ **当前 ROM 上同一脚本必须打完仗**（`outcome=1`） | ❌ **未达成**（被另外两个缺陷挡死） | 见 §3.3 / §5 |

**判据 ② 的证据**（Y1 自己留下的构建日志，都在盘上）：

| 日志 | 时间 | `-Wstack-usage=` 命中 | 内容 |
|---|---|---:|---|
| `build/y1-build-before.log`（修复前） | 16:03:56 | **1** | `battle_turn_flow.h:48:5: warning: stack usage is 16880 bytes [-Wstack-usage=]` |
| `build/y1-build-after.log`（修复后） | 16:09:19 | **1** | **同一行**（`advance_empty_side`） |
| `build/y1-build-su.log`（`-Wstack-usage` 全量重建） | 16:19:43 | **1** | **同一行** |

⇒ 修复**前后完全一样**：只剩 wave 11 之前就存在的那一条（`battle_turn_flow.h:48`
`advance_empty_side`，16880 字节），**该结构体没有引入任何新的 stack-usage 警告**。

---

## 3. 任务 B：结算链运行帧

### 3.1 方法（**不是**伪造帧）

1. **闭环开机**（`w1_boot.Boot`）：13 次 A 见到黑场（黑场是唯一的相位标记）→ 等黑场结束 →
   等画面连续 30 帧不变（打字机跑完）→ 停在战斗开场对白第 1 页。
2. **把控制器状态 poke 进 `outcome`**：
   * 控制器是战斗运行时场景里的 `BN_DATA_EWRAM_BSS static`，**每次构建地址都会动**
     （X1 记的 `0x02023C40` 已经过期 ⇒ 本波实测是 **`0x02023C30`**）。
     ⇒ `z1_settlement_chain.py` **按效果找它**：把窗口里每个等于当前相位的字节都 poke 成 13，
     再用 ROM 自己的 telemetry 读回来，**telemetry 跟着变的那一个就是 `_phase`**（71 个候选，1 个命中）。
   * `_outcome` 在 `battle_scene_controller<12,23,32>` 里比 `_phase` 靠后 `0x228` 字节 ⇒
     `0x02023C30 + 0x228 = 0x02023E58`。
   * poke 之后**读回验证**：`phase = 13`、`condition_outcome = 1`（收据里有）。
3. **闭环走链**：**读渲染帧 → 决策 → 按键**。
   按钮 A 不改变画面就换 B / → / ↓ / ← / ↑（训练段最后一页吞 A，就是这样过去的）。
   走链的判据是**渲染帧的 sha256**，不是硬编码的按键序列 ⇒ 同一相位下的多页（训练段 6 页）也一页一页走。
4. **每一帧都是产品代码画出来的运行帧**（探针的 `shot` 截的是 mGBA 的帧缓冲），工具**不画任何东西**。

### 3.2 结果

* **15 屏**（`build/z1/chain-e/shots/`）：`outcome` 1 + `result` 1 + `level_up` 6 + `training` 7。
* **两次独立跑逐字节一致**：`chain-e` 与 `chain-f` 各 15 个文件，**文件名相同、逐文件 sha256 相同、
  不同帧 0 个**。
* **原版 9 张真值里的 6 张被逐像素复现（差 px = 0）**（§3.3）。
* 收据：`build/z1/chain-e/chain.json`（ROM sha、poke 地址与来源、每屏的 sha256、按键数）。

### 3.3 ⭐ 结算链逐屏运行帧对照表

原版真值：`build/s49-victory-capture/w4/settlement-truth/`（9 张，W4 wave 8）。
差 px 口径：**逐像素**（任一通道不同即算不同），整屏 240×160 = 38 400 px。

| 重制侧运行帧 | 阶段 | 原版真值 | 原版 sha256 | 重制侧 sha256 | 差 px | 差 bbox | 逐字节相同 |
|---|---|---|---|---|---:|---|---|
| `page-000-outcome.png` | outcome（勝利 / BATTLE COMPLETE） | `01-victory.png` | `d60a1d35e45736db` | `47fbde60709a2768` | **37 462** | `[0, 0, 240, 160]` | ❌（重制侧**全黑**） |
| `page-001-result.png` | result（结算屏） | `02-settlement-exp-power-turns.png` | `e34e116c7ed3a55e` | `0027e9cf95129b6a` | **35 859** | `[0, 0, 240, 160]` | ❌（版式不同） |
| `page-002-level_up.png` | level_up 1/6 | `03-levelup-naruto.png` | `a876f32dbe100a65` | `a876f32dbe100a65` | **0** | — | ✅ **是** |
| `page-003-level_up.png` | level_up 2/6 | `05-levelup-sasuke-jutsu-name.png` | `daac884a6415577b` | `daac884a6415577b` | **0** | — | ✅ **是** |
| `page-004-level_up.png` | level_up 3/6 | `04-levelup-konohamaru.png` | `ef0808aea763ff31` | `ef0808aea763ff31` | **0** | — | ✅ **是** |
| `page-005-level_up.png` | level_up 4/6 | `05-levelup-sasuke.png` | `c5a8440b451ef6a1` | `c5a8440b451ef6a1` | **0** | — | ✅ **是** |
| `page-006-level_up.png` | level_up 5/6 | `06-levelup-sakura.png` | `a0db87e9fd8ec358` | `a0db87e9fd8ec358` | **0** | — | ✅ **是** |
| `page-007-level_up.png` | level_up 6/6（忍具一览） | `07-ninja-tool-list.png` | `455acc43c9ace553` | `455acc43c9ace553` | **0** | — | ✅ **是** |
| `page-008-training.png` | training 1/6（忍具一览·重制版式） | — | — | `b012f6051307b51c` | — | — | 重制侧独有 |
| `page-009-training.png` | training 2/6 | — | — | `8b8ee8663e3aaaa7` | — | — | 重制侧独有 |
| `page-010-training.png` | training 3/6 | — | — | `b2fd1061cdd41a73` | — | — | 重制侧独有 |
| `page-011-training.png` | training 4/6 | — | — | `2a7fdabad4931059` | — | — | 重制侧独有 |
| `page-012-training.png` | training 5/6 | — | — | `4112cebb52f60b23` | — | — | 重制侧独有 |
| `page-013-training.png` | training 6/6 | — | — | `53c2bf0e33cf6375` | — | — | 重制侧独有 |
| `page-014-training.png` | **崩溃屏**（非法 UTF-8，见 §5 D3） | — | — | `20c1161209417dda` | — | — | — |
| （无） | post_battle_dialogue | `08-postbattle-dialogue-1.png` | `2741dbc3fbf6e838` | — | — | — | ⛔ **不可达** |
| （无） | task_menu | `09-task-menu-map.png` | `cda07a18be60a1ea` | — | — | — | ⛔ **不可达** |

* **机械最优匹配表**（`build/z1/settlement-table-z1.json`，由 `y1_settlement_table.py` 生成）
  在 `build/z1/settlement-table-z1.json` 里；**上面这张表是语义对应**（机械最优对重制侧的绿框面板
  全部落到同一张原版图上，没有语义意义）。
* ⭐ **结论**：**结算链的 8 屏可达**（`outcome` / `result` / 6 个升级屏），
  其中 **6 屏与原版逐字节相同**；**`outcome` 屏重制侧全黑**（§5 D4），
  **`result` 屏版式不同**（重制侧画的是「鸣人/佐助/小樱 + 经验/战力」，
  原版是「经验/战力/回合数」三栏）；
  **最后 2 屏（战后对白 / 任务菜单）不可达**（§5 D2+D3）。

### 3.4 「旧链 8 次 A，新链要 16 次」的核对

WAVE13 §1.3 的口径在实测里对上了：

| | 段 | 按 A 次数 |
|---|---|---|
| **旧链**（`u2_route_gen.cpp` 生成时的控制器） | outcome 1 + result 1 + level_up 6 | **8** |
| **新链**（现在的控制器，多了战后对白 7 页 + 任务菜单 1 页） | 8 + 7 + 1 | **16** |

⇒ U2 的 `routeY.json` 的结算段是 **14 次 A**（8 + 训练段 6），
**不够走到 `complete`** ⇒ 需要**补 8 次 A**（把训练段的 6 次换成战后对白 7 次 + 任务菜单 1 次）。
⇒ 本波用**闭环**（读画面 → 决策）代替了这个硬编码计数，
但**训练段第 7 屏会崩**（§5 D3）⇒ **实测只能走到第 8 屏（`training` 的 6 页 + 崩溃屏）**。

---

## 4. ⭐ 本波查实并修掉的**仪器 bug**（都不在产品代码里）

### 4.1 `x1_telemetry.py` 的字段表少了一个字段 ⇒ **第 70 个字段之后全部错位一格**

`x1_telemetry.py` 的 `FIELDS` 表是遥测结构体 `battle_runtime_scene_telemetry`
（`game/include/konoha/battle_runtime_scene.h`）的**手工镜像**。实测对照：

```
struct members=217  telemetry FIELDS=216
MISMATCH at 70: struct=presentation_passive_status_applied telemetry=battlefield_object_count
⇒ 从索引 70 起，x1_telemetry.py 少了一个字段 presentation_passive_status_applied
⇒ 之后的每一个字段都被读早了 1 个字（32 位）
```

⇒ **被读错的东西包括**：`unit_x[12]` / `unit_y[12]` / `unit_hp[12]` / `unit_chakra[12]` /
`unit_side[12]` / `unit_control[12]`（**闭环驱动器选目标用的就是这些**）、
`condition_outcome`、`training_detail_page`、`map_movement_*`、`move_preview_*` 等。

⇒ **两个直接后果**：
1. X1 的 `x1_settlement.py` 里 `condition_outcome` 一直读成 **0**，
   看起来像「poke 了 outcome 也没生效」，其实 **outcome 一直是 win**
   （收据里 `outcome_byte_after_poke = 1` 就是证据）；
2. 闭环驱动器的目标选择读的是错位的单位坐标。

⇒ **本波已修**：补上 `presentation_passive_status_applied` ⇒
**217 / 217，0 处不一致**（`struct` 与 `FIELDS` 逐名逐序相同）。

### 4.2 驱动器「按住不放」被场景的闩锁吞掉 ⇒ 改成**点按**

`battle_runtime_scene.cpp` 的对白输入路径：

```cpp
if(! bn::keypad::a_held()) { script_confirmation_latched = false; }   // 只有看到「松开」才解锁
...
if(! state.script.typewriter_active &&
    ! script_confirmation_latched &&
    bn::keypad::a_held()) { script_confirmation_latched = true; controller.confirm(); }
```

而探针的 `frames <count> <mask>` 命令是**「设键 → 跑 N 帧 → 再松键」**：
**松键不产生任何一帧** ⇒ 连续两次按之间**场景从来没看到过「松开」** ⇒ 闩锁永远是锁着的
⇒ **按住只能确认一行，之后就被吞掉**。

⇒ **实测**（`z1_dialogue_probe.py` 的四种按法对照）：
`tap6`（按 6 帧 + 松 6 帧）**能推进**（`command_index` 2 → 4），
`hold240` / `frames240` / `tap5x` 在第 2 回合对白处**全部推不动**
（画面 8 次采样 16 帧间隔只有 **1 个不同的画面** ⇒ 场景是静的）。

⇒ **本波已修**：`y1_play.py` 的 `press()` 先渲染 **1 帧「无键」**，`press_until()` 改成**点按**
（按 4 帧 + 松 2 帧）而不是按住。

### 4.3 控制器的地址会随构建变 ⇒ 改成**按效果找**

X1 记的 `_phase` 地址 `0x02023C40` 在当前 ROM 上**已经失效**（那个字节的值是 1，不是相位 18）。
链接映射（`butano-sequel/build/butano-sequel.map`）给出的是**对象**的窗口
（`battle_runtime_scene.o` 占 `.sbss` 的 `0x0200ab20..0x02025ee8`），不给单个 static 的地址。

⇒ **本波已修**：`z1_settlement_chain.py` 按效果找（poke + 用 ROM 自己的 telemetry 读回），
命中 **`0x02023C30`**（71 个候选里 1 个命中），`_outcome` = `+0x228` = `0x02023E58`。

---

## 5. ⭐⭐ 本波**新查实**的 3 个产品缺陷（重制线，**本波零改动**）

| # | 缺陷 | 现象（截图/收据） | 位置 | 后果 |
|---|---|---|---|---|
| **D1** | **第 2 回合对白时 OBJ 调色板耗尽** | 屏幕上 Butano 致命错误：`ERROR in bn_palettes_bank.cpp.h / create_bpp_8x16 / BPP8 palette create failed. Colors count: 128 / There are no more available colors.` | **待查**：怀疑是对白阶段与战斗阶段的 OBJ 调色板 cohort（`battle_visual_resource_coordinator`）在同一帧里同时占盘；本流**没有逐个统计活着的调色板**（需下一波单独做） | **战斗永远打不完**（Y1 的判据 ③ 卡在这）⇒ `outcome` 只能靠 poke 进 |
| **D2** | **战后对白 / 任务菜单没有 UI 层** | `battle_ui_model.h` 的相位 switch **没有** `post_battle_dialogue` / `task_menu` 的 case ⇒ 落到 `default:` ⇒ `battle_ui_layer::hidden` | `game/include/konoha/battle_ui_model.h`（相位 switch，`:294-321`） | 这两段**画不出东西** |
| **D3** | **战后对白的文本里有非法 UTF-8** | 画面：`ERROR in bn_utf8_character.h / utf8_character:91 / Invalid UTF-8 character` ⇒ ROM 停机 | 战后对白的文本内容（`battle_settlement_s49_dialogue_page_count = 7` 页） | **结算链永远走不到 `complete`**（⇒ `08-postbattle-dialogue-1.png` / `09-task-menu-map.png` 不可达） |
| **D4** | **勝利屏（`outcome`）画出来是全黑** | `page-000-outcome.png` 的 38 400 个像素**全是 (0,0,0)** | `battle_runtime_scene.cpp:4344-4352` 的 `battle_ui_layer::result` 分支（`state.phase == outcome` 时画 "BATTLE COMPLETE" / "MISSION CLEARED"） | `01-victory.png` **对不上**（差 37 462 px） |

> ⭐ **D1 的证据链**（两个不同的驱动器都撞在同一处 ⇒ 与驱动器无关，是 ROM 的问题）：
> Y1 的 `run-tool`（16:44，原版 `y1_play.py`）与本波的 `play-fix1`（17:1x，修完 §4.2 后）
> **都停在路由的第 57 步**（第 2 回合的对白），画面都是同一张 Butano 调色板错误屏。
> `z1_dialogue_probe.py` 的四种按法全部无效、画面 8 次采样完全不变 ⇒ **不是输入问题**。

---

## 6. 跑了哪些验证（命令 + 关键数字）

| # | 命令 | 关键数字 |
|---|---|---|
| **V1** | `powershell -File tools\s49_battle_balance\y1_dump_head.ps1` | `MATCH: build/head-baseline == git HEAD` |
| **V2** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/tools/s49_battle_balance/y1_size_check.sh` | HEAD **148** / 工作区 **148**；逐字段 diff **只有 2 行**（两个 `bool` 换位）；`capture_count` **144 = 144**；`battle_scene_snapshot<12>` **1672 = 1672** |
| **V3** | Y1 的构建日志 `build/y1-build-{before,after,su}.log` | `-Wstack-usage=` 命中 **1 / 1 / 1**，且是**同一条**（`battle_turn_flow.h:48`，16 880 字节）⇒ **零新增** |
| **V4** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh` | HEAD **101 pass / 20 fail**（20 个名字见 §6.1） |
| **V5** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh` | 工作区 **118 pass / 20 fail** ⇒ **失败集合与 HEAD 逐名相同 ⇒ 新失败 0** |
| **V6** | `python tools/s49_battle_balance/y1_play.py --rom <pinned> --route routeY.json --boot`（修完 §4.2 后） | 26785 帧 / 95 键 ⇒ 仍停在**第 57 步**（D1） |
| **V7** | `python tools/s49_battle_balance/z1_dialogue_probe.py --diagnose-call 4` | 71 个候选字节 → `0x02023C30`；四种按法全败；画面 **1 个不同**（静止）⇒ D1 |
| **V8** | `python tools/s49_battle_balance/z1_settlement_chain.py --rom <pinned> --out build/z1/chain-e` | **15 屏**；`phase_after_poke = 13`、`outcome_after_poke = 1`；`stuck_phase = 19`（D3） |
| **V9** | 同上 `--out build/z1/chain-f`（第二次独立跑） | **15 / 15 文件逐字节相同，不同帧 0 个** |
| **V10** | `python tools/s49_battle_balance/y1_settlement_table.py --truth … --remake build/z1/chain-e/shots` | 机械最优表 → `build/z1/settlement-table-z1.json`；语义表见 §3.3（**6 张差 px = 0**） |
| **V11** | `python tools/s49_fidelity_report.py --out build/z1/judgment-report.json --work-dir build/s49-package-y4-final/work/s49-report --skip-capture --remake-rom build/s49-package-y4-final/work/pinned-rom/measured.gba --repeat 3 --quiet` | 判定台**连读 3 次读数逐项相同**：`field_residual` 总和 **100 210** / 中位 **1 323** / max 27 325 / **全 0 帧 5**；`determinism.identical = true`、`rom_changed = false`；**ROM sha `2c2b48d91fbe32447845a7ddf683b29badefd30202e14c230efc98640a72fca0`**（与基线**同一个 ROM**，残差**未变**，即「只许变小」里的**不变**） |
| **V12** | `Get-CimInstance Win32_Process` 收尾复查 | 本流自己的 `mgba-probe.exe` 残留 **0**（盘上现存的 `mgba-probe-z2` 是 Z2 的） |

### 6.1 单测棘轮：失败集合**逐名相同**

| | pass | fail |
|---|---:|---:|
| HEAD 基线（`build/head-baseline`） | 101 | **20** |
| 工作区（`butano-sequel/game`） | 118 | **20** |

**20 个失败名（两边完全相同，顺序也相同）**：

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

⇒ **新失败 0**（这 20 项在 HEAD 即为红，是预存债）。

### 6.2 判定台残差（**同 ROM**）

| 项 | 基线（wave 13 Y4 收据） | 本波复测（`build/z1/judgment-report.json`） |
|---|---:|---:|
| ROM sha256 | `2c2b48d9…` | `2c2b48d9…`（**逐字节相同**） |
| 残差总和 | 100 210 | **100 210** |
| 残差中位 | 1 323 | **1 323** |
| 残差 max | 27 325 | **27 325** |
| 全 0 帧 | 5 | **5** |
| 连读次数 / 逐项相同 | 3 / 是 | **3 / 是**（`identical: true`，`rom_changed = false`） |
| 报告 `content_sha256` | `28ba47bb9717422b6db6c3c97e0bcd6305715c0a65bb0f500100383fc3a4fc70` | **完全相同**（`28ba47bb…`）⇒ 本波复测的报告与 wave 13 的报告**内容逐字节一致** |

⇒ **残差没有变大**（本波**没有改重制线任何文件**，测的就是同一份 ROM 字节）。

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **Z1-1** | 栈溢出的根因是 `battle_scene_presentation_event` 在 wave 11 变大 ⇒ 把结算链的新增字段塞进**原有的对齐空隙**就能把 `sizeof` 压回 HEAD 的值 | `y1_size_check.sh`：HEAD 头文件 vs 工作区头文件各编一个 `offsetof` 探针并逐字段 diff | **成立**：HEAD 148 / 工作区 148，`capture_count` 偏移 144 = 144，**只有两个 `bool` 换了位置** | **已确认** |
| **Z1-2** | 修复会引入新的 stack-usage 警告 | 对比 Y1 的三份构建日志（修复前 16:03:56 / 修复后 16:09:19 / `-Wstack-usage` 全量 16:19:43） | **不成立**：三份日志的 `-Wstack-usage=` 命中都是 **1**，且是**同一条**（`battle_turn_flow.h:48`，16 880 字节） | **已证伪** |
| **Z1-3** | `battle_settlement_presentation` 必须正好 4 字节才能塞进对齐空隙 | 读 `battle_settlement_stage` 的底层类型（`enum class : std::uint8_t`）+ `static_assert` | **成立**：4 字节 / align 1 | **已确认** |
| **Z1-4** | 当前 ROM 上同一脚本能打完仗（`outcome=1`） | 闭环驱动 + `y1_play.py` 回放 `routeY.json`（Y1 的原版与修完 §4.2 的版本各一次） | **不成立**：两次都停在**第 57 步**（第 2 回合对白），画面是 Butano 的**调色板耗尽**致命错误 | **已证伪** |
| **Z1-5** | 第 2 回合对白卡死是**驱动器/输入**的问题 | `z1_dialogue_probe.py`：四种按法（tap6 / hold240 / frames240 / tap5x）× 画面 8 次采样 | **不成立**：四种按法全败，画面 8 次采样**只有 1 个不同的画面**（静止）⇒ 是 ROM 停机了 | **已证伪** |
| **Z1-6** | 第 2 回合的卡死还是 wave 11 那个 `Illegal opcode` 崩溃 | 读卡死点的画面 | **不成立**：画面是 `BPP8 palette create failed. Colors count: 128`（调色板），不是 illegal opcode | **已证伪** |
| **Z1-7** | X1 的 `x1_settlement.py` 里 outcome 的 poke 没生效（`condition_outcome` 一直是 0） | 修好 §4.1 的遥测表后重读 | **不成立**：telemetry 表少一个字段 ⇒ `condition_outcome` 读的是**别的字段**；实际 `outcome_byte_after_poke = 1`、telemetry 读回 **1** | **已证伪（根因是仪器）** |
| **Z1-8** | `x1_telemetry.py` 的字段表与遥测结构体逐名相同 | 把结构体的成员逐个抽出来与 `FIELDS` 对拍 | **不成立**：**217 vs 216**，从索引 70 起整体错位一格（单位坐标/HP/阵营全在里面） | **已证伪（已修）** |
| **Z1-9** | 对白可以用「按住 A」推进 | 对拍「按住」与「点按」两种按法 | **不成立**：场景的闩锁只在**看到松开**的那一帧才解锁，而探针的 `frames` 命令松键**不产生帧** ⇒ 按住只能确认一行 | **已证伪（已修：改成点按）** |
| **Z1-10** | 控制器的 `_phase` 地址是固定的（X1 记的 `0x02023C40`） | 在当前 ROM 上读那个字节 | **不成立**：那个字节的值是 1，不是相位 18；实测 `_phase` 在 **`0x02023C30`**（每次构建都会动） | **已证伪（已改成按效果找）** |
| **Z1-11** | 结算链可以用「一路按 A」走完（任务书：旧链 8 次、新链 16 次） | 闭环走链（读渲染帧 → 决策 → 按键） | **部分成立**：`outcome` + `result` + 6 个升级屏 + 训练段 6 页（**共 14 屏，13 次按键**）都能走；但**战后对白段一进去就崩**（D3）⇒ **走不到 `complete`** | **部分确认** |
| **Z1-12** | 重制侧的 6 个升级屏 + 忍具一览与原版**逐像素**相同 | 逐屏 diff（逐像素口径，240×160） | **成立**：**6 张差 px = 0**（`03-levelup-naruto` / `05-levelup-sasuke-jutsu-name` / `04-levelup-konohamaru` / `05-levelup-sasuke` / `06-levelup-sakura` / `07-ninja-tool-list`） | **已确认** |
| **Z1-13** | 勝利屏（`01-victory.png`）能被复现 | 读 `page-000-outcome.png` 的像素 | **不成立**：重制侧的 `outcome` 屏 **38 400 px 全是 (0,0,0)**（D4）⇒ 差 37 462 px | **已证伪** |
| **Z1-14** | 战后对白 / 任务菜单两屏可达 | 闭环走链 + 强行把相位推进 `post_battle_dialogue` | **不成立**：那一段**没有 UI 层**（D2）且**文本有非法 UTF-8**（D3）⇒ ROM 停机 | **已证伪** |
| **Z1-15** | 结算链的录制是**可复现**的 | 两次独立跑（`chain-e` / `chain-f`）逐文件 sha256 对比 | **成立**：15 / 15 文件**逐字节相同**，不同帧 **0** | **已确认** |
| **Z1-16** | 本波没有引入新的单测失败 | HEAD 基线 vs 工作区的失败集合**逐名**对比 | **成立**：20 = 20，名字完全相同 ⇒ **新失败 0**（118 pass vs HEAD 101 pass） | **已确认** |
| **Z1-17** | 本波没有让判定台残差变大 | 同一个钉住的 ROM（`2c2b48d9…`）连读 3 次判定台 | **成立**：总和 **100 210** / 中位 **1 323** / 全 0 帧 **5**，三次逐项相同，`rom_changed = false` | **已确认** |

---

## 8. 还卡在哪 / 没关掉的

* ⛔ **Y1 的判据 ③「当前 ROM 上打完仗」仍然不达成** —— 但**不是栈溢出**：
  栈溢出（`Illegal opcode`）已经修掉，战斗现在能打到**第 2 回合**；
  挡住它的是 **D1（OBJ 调色板耗尽）**。
  ⇒ 修 D1 需要动重制线的调色板 cohort 预算（`battle_runtime_scene.cpp` / `battle_black_field*`），
  **那会改 ROM** ⇒ 残差基线与 Y4 的钉住包都会失效 ⇒ **本波刻意没做**，留给下一波专修。
* ⛔ **结算链的最后 2 屏（战后对白 / 任务菜单）不可达** —— **D2 + D3**：
  `battle_ui_model.h` 没有这两个相位的 UI 层；战后对白的文本里有非法 UTF-8 字符。
  ⇒ `08-postbattle-dialogue-1.png` / `09-task-menu-map.png` 这两张原版真值**没有对应的重制侧运行帧**。
* ⛔ **`01-victory.png` 对不上** —— 重制侧的 `outcome` 屏全黑（D4）。
* ⛔ **`02-settlement-exp-power-turns.png` 对不上** —— 重制侧的结算屏版式是
  「鸣人/佐助/小樱 + 经验/战力」，原版是「经验/战力/回合数」三栏（差 35 859 px）。
* ⚠️ **结算链的入口是「poke 控制器的状态」**，不是「打完仗自然进入」——
  因为 D1 让战斗打不完。**每一帧仍然是产品代码画出来的运行帧**，但**这场仗不是赢下来的**，
  结算屏上的数值是**空战果**（`result_total_experience = 200`、
  `result_participant_count = 3`，是 poke 进来的默认值，不是打出来的）。
* ⚠️ **判定台复测用的是 `--skip-capture`**（复用 Y4 在**同一个钉住 ROM**上录的帧）。
  因为本波**一个字节都没改 ROM**，这是同一个测量；报告里给了 ROM sha 供核对。

---

## 9. 确认

* **新文件一律 LF、无 BOM**（`Y1-stack-fix-and-settlement.md`、`z1_settlement_chain.py`、
  `z1_dialogue_probe.py`、`z1_controller_offsets.cpp`）。
* **未提交 git**。
* **重制线零改动**（D:\Shell\Github\gba-naruto-butano 只读使用 ⇒ 源码 mtime 全部早于本流开始；
  本流全部测量跑在 W4 钉住的 ROM 2c2b48d9… 上；工作树的 ROM 在本流期间被 Z2 重建过，
  **本流没有用它测量**）。
* **逆向线零改动**（`D:\Shell\Github\gba-naruto-reverse` 未访问）。
* **未改其它流的仪器**（`s49_fidelity_report` / `s49_package` / `s49_victory_capture` /
  `mgba_probe` 一律只读调用；共享的 `build/mgba-probe/mgba-probe.exe` 未动）。
* **没有伪造任何帧**：15 张 PNG 全部是 mGBA 帧缓冲的截图（探针 `shot`），
  每一张都能在 `build/z1/chain-{e,f}/shots/` 里找到原图，收据里有逐文件 sha256。
* **孤儿进程检查**：本流自己的 `mgba-probe.exe` 残留 **0**。
