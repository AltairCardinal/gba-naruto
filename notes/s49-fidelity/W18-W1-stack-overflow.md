# W18-W1 —— 攻击确认链的 IWRAM 栈溢出（wave 18 · 流 W1）

> 2026-10-25 · 流 W1（`mvs_e474fc5073184557a00f3303c4602e51`）· 父代理
> `mvs_4e730a9ded524558a303c115875a9707`
> 任务书：`notes/s49-fidelity/WAVE18-TASKS.md` §1 · 上游：`notes/s49-fidelity/U1-d4-fix.md`
> · `notes/s49-fidelity/U4-real-victory-verify.md` · `notes/s49-fidelity/W18-W2-confirm-yes-unselectable.md`
> 独占文件（只能改这些）：
> `game/include/konoha/battle_action_system.h`、
> `game/include/konoha/battle_encounter_runtime.h`、
> `game/include/konoha/battle_action_combinations.h`、
> **（父代理追加）`game/include/konoha/battle_turn_flow.h`**
> 隔离副本：`build/w18-w1/butano-sequel`（`third_party/`、`graphics/`、`audio/` 只读）
> ⛔ 未提交 git（两个仓都没有 `git add/commit`）；逆向线未访问；孤儿 `mgba-probe.exe` **0 个**

---

## 0. 一句话结论

> **根因 = 4 个「整份会话 / 整份单位数组」的栈拷贝把 IWRAM 用户栈撑爆**
> （最深一次实测 `sp = 0x03002818`，比用户栈底 `0x03002BC4` 还低 **940 字节**，
> 于是踩坏 devkitARM 的 `IRQ_VectorTable`（`0x03002880`）⇒ 中断风暴 ⇒ 场景帧停死）。
> **本流把 4 处拷贝全部移出栈**（会话拷贝 → EWRAM 可嵌套槽位池；单位数组拷贝 → 只拷 source 单体），
> ⇒ **从场景根出发的最坏栈深 26 888 B → 14 944 B（≤ 21 308 B，裕量 6 364 B）**，
> ⇒ **真实战斗首次打赢**：`outcome=1`、蜂 HP **25 → 0**、`errors: []`（无 `rom-frozen`）、
> **「はい」按 A 后相位 20 → 9**（战斗演出真的跑起来了）、**IRQ 向量表写监视点全程未命中**。

---

## 1. 改动文件清单

### 1.1 重制线（**只在我的隔离副本里**：`build/w18-w1/butano-sequel`）

| 文件 | 改动摘要 | sha256 |
|---|---|---|
| `game/include/konoha/battle_action_system.h` | ① 新增 `battle_action_transaction_pool<MaxUnits>`（**EWRAM、深度 2 的 LIFO 槽位池**）+ `battle_action_transaction<MaxUnits>`（RAII 句柄）；② `resolve_battlefield_object_event` / `resolve_area_draft` / `resolve_draft` 的 `battle_session next = session;`（8 052 B）改为走池；③ `preview_area` 的 `std::array<battle_unit_instance, MaxUnits> units = session._units;`（5 616 B）改为**只拷 source 单体**（468 B）+ 新增 `battle_action_targeting::collect_preview()`（source 自身条目用 `source.position`） | `CA450296FBE73379B6D5C6BCC60DD962EAF5540BE778B4EDAEA3215C3AF16873` |
| `game/include/konoha/battle_turn_flow.h` | 5 处 `battle_session next = session;`（`advance_empty_side` / `complete_non_target_action` / `after_effects` / `complete_defense` ×2）全部改走同一个 EWRAM 槽位池 | `581F3408E891DB0D8EDE22463FF5E56F88134D45E0ADB287E9C5CCC475A96129` |
| `game/include/konoha/battle_action_combinations.h` | `resolve()` 的 `battle_session next = session;`（8 052 B）改走同一个 EWRAM 槽位池 | `B90B4EEA56AB1E471B2DB2809BA63D8750DB5355FFC98B536034625F263F7C90` |
| `game/include/konoha/battle_encounter_runtime.h` | **未改**（sha `AA1A58FBA680DCD5A8C29051D3CB6FAF3D3C0694372C5546F4F14B3EEE5F69A2`，与共享树相同）—— 它已有的 `_transaction_session()` 工作区**没有被本流占用**，本流的新池是**独立对象**（见 §3.4） | 同左 |

### 1.2 本仓库（`D:\Github\gba-naruto`）

| 文件 | 性质 | 说明 |
|---|---|---|
| `notes/s49-fidelity/W18-W1-stack-overflow.md` | **新增** | 本文件（LF、无 BOM）。 |
| `build/w18-w1/gen_su.sh` | 新增 | **重建** `-fstack-usage` 报告（照 `build/u1/gen_su.sh`，ROOT 指向本 lane，输出 `build/w18-w1/su/`）。⚠️ `build/*.su` 是陈旧产物，正式构建不写 `.su`。 |
| `build/w18-w1/chain.py` / `paths.py` / `deepest.py` | 新增 | **调用图 + 栈深仪器**：把 `.su` 的帧大小和 ELF 反汇编的 `bl` 边合成真实调用图，枚举**从场景根出发的所有简单路径**并求最大帧和。`deepest.py` 带 `COMPLETE / CAP HIT` 标记（本次搜索 **COMPLETE**，994 141 条路径，未截断）。 |
| `build/w18-w1/build.sh` / `check_host.sh` | 新增 | 构建 / 宿主机单测编译快查。 |
| `build/w18-w1/mgba-probe.exe` | **复制** | 共享探针的副本（**没有覆盖** `build/mgba-probe/mgba-probe.exe`）。 |
| `build/w18-w1/**` | 产物 | `su/`（栈报告）、`run-a-tools/`、`run-b-notools/`、`diag-confirm/`、`sp-verify/`、`report.json`、`report.md`、`fid-work/`。 |

### 1.3 没有改的

* `battle_encounter_runtime.h`（我的独占文件，但**不需要改**）；
* `battle_scene_controller.h` / `battle_player_action_flow.h` / `battle_action_execution.h`（W2 独占）、`battle_runtime_scene.cpp`（W4 独占）、`battle_black_field*.h`、`src/main.cpp`、`battle_preparation_scene.cpp`：**一个字节没动**；
* `graphics/`、`audio/`、`third_party/`：**只读**（副本里是指向共享树的链接）；
* `tools/s49_battle_balance/`、`tools/s49_u1_d4/`、`tools/s49_w2/`、`tools/s49_fidelity_report.py`：**只读调用**；
* 逆向线 `D:\Shell\Github\gba-naruto-reverse`：**未访问**。

---

## 2. 根因（实测，不是猜的）

### 2.1 W2 的写监视点实测（决定性证据，已采信）

在 `IRQ_VectorTable[0]`（`0x03002880`）挂**写监视点**后按 A：

| | 改前（W2 的 ROM） | **改后（本流 ROM）** |
|---|---|---|
| 写监视点 | **命中**：`0x0803EF25` → `0x00000012` | ⭐ **未命中**（`fired=False`） |
| 命中/采样时的 `sp` | `0x03002818`（**比栈底低 940 B** ⇒ 已溢出） | ⭐ `0x03004D68`（**离栈顶 12 680 B**，离栈底还有 7 092 B 裕量） |
| `IRQ_VectorTable` 按 A 前后 | entry[0] 被写成野指针 | ⭐ **逐字节相同**（`0803EB6D / 03000EB8 / 00000000 / …` 前后一致） |
| 相位 | 20 卡住 | ⭐ **20 → 9**（`facing_selection`），`ctrl=player=act_err=0` |

⇒ **栈溢出被彻底消除**，不是「没触发」而是「不会再触发」。

### 2.2 ⭐ 溢出点是 **4 处「整份拷贝」**，不是 1 处

`.su`（本流重建）+ ELF 调用图实测：

| # | 站点 | 拷贝内容 | 改前栈帧 |
|---:|---|---|---:|
| **R1** | `battle_action_system.h:765` `resolve_battlefield_object_event` | `battle_session<12>`（8 052 B） | **8 088** |
| **R2** | `battle_turn_flow.h:53` `advance_empty_side` | `battle_session<12>`（8 052 B） | **16 880** |
| **R3** | `battle_action_combinations.h:320` `resolve` | `battle_session<12>`（8 052 B） | **9 504** |
| **R4** | `battle_action_system.h:585` `preview_area` | `std::array<battle_unit_instance,12>`（5 616 B） | **5 864** |

> ⚠️ **U1 §2.2 的「21 304 B 栈链算术」不成立**：那张表把
> `resolve_draft_in_place` / `resolve_area_draft_in_place` /
> `_resolve_battlefield_object_event_in_place` / `resolve_battlefield_object_event`
> 串成了一条链，但源码上它们**互不调用**（`resolve_battlefield_object_event`
> 的唯一调用点是 `battle_turn_flow.h:481`）⇒ 那张表是**几条互斥路径的并集**，
> 「21 304 ≈ 实测 21 772」是数值巧合。
> ⭐ **真实的最坏路径必须用调用图算**（本流的 `deepest.py`）。

---

## 3. 逐帧栈表（**改后**，全部来自本 lane 自己重建的 `.su`）

### 3.1 关键帧：改前 → 改后

| 帧 | 改前 | **改后** | 说明 |
|---|---:|---:|---|
| `battle_action_resolver::resolve_battlefield_object_event` | 8 088 | ⭐ **无独立帧**（被内联进 `_resolve_battlefield_objects`，其帧 **712 B 未变**） | 8 052 B 会话拷贝已消失 |
| `battle_turn_flow::advance_empty_side` | 16 880 | ⭐ **120** | 只剩 `battle_turn_flow_result` / `battle_condition_result` 局部量 |
| `battle_action_combinations::resolve` | 9 504 | ⭐ **1 456** | 只剩组合体 / preview 局部量 |
| `battle_action_resolver::preview_area` | 5 864 | ⭐ **720** | 只剩 source 单体（468 B）+ target set + preview |
| `battle_action_resolver::resolve_area_draft_in_place` | 1 496 | 1 496 | 未动 |
| `battle_action_resolver::_resolve_battlefield_object_event_in_place` | 1 424 | 1 424 | 未动 |
| `battle_action_combinations::_resolve_sequence` | 1 392 | 1 392 | 未动 |
| `battle_turn_flow::_resolve_battlefield_objects` | 712 | 712 | 未动 |
| `run_visible_battle_scene` | 6 136 | 6 136 | 未动（W4 独占文件） |
| `battle_scene_controller::tick` | 2 432 | 2 432 | 未动（W2 独占文件） |
| `battle_condition_interpreter::evaluate_session` | 6 192 | 6 192 | 未动（**改后链上的最大单帧**） |

> ✅ **游戏构建的 `.su` 里已没有任何 8 052 B 级的会话副本**（最大的剩余帧是
> `battle_campaign_scene_progression::commit` 9 736 B，它是战役状态提交、不是会话拷贝、
> 且不在战斗链上）。

### 3.2 链 A（攻击确认链）—— 逐帧表

**A-1 单招式路径**（驱动器的实际路径：忍具 1 / 普通招式 5）：

| # | 帧 | 字节 | 累计 |
|---:|---|---:|---:|
| 1 | `run_visible_battle_scene` | 6 136 | 6 136 |
| 2 | `battle_scene_controller::confirm` | 896 | 7 032 |
| 3 | `battle_scene_controller::_confirm_target` | 592 | 7 624 |
| 4 | `battle_player_action_flow::confirm_target_in_place` | 808 | 8 432 |
| 5 | `battle_action_execution::resolve_in_place` | 64 | 8 496 |
| 6 | `battle_action_resolver::resolve_area_draft_in_place` | 1 496 | 9 992 |
| 7 | `battle_action_resolver::preview_area` | **720** | **10 712** |
| 8 | `battle_action_resolver::_preview` | 112 | 10 824 |
| 9 | `battle_action_resolver::_success_rate` | 56 | 10 880 |
| 10 | `battle_attribute_system::view` | 72 | **10 952** |

**A-2 组合技路径**（`_state.combination_component_count == 2` ⇒ 走 `battle_action_combinations::resolve`）：

| # | 帧 | 字节 | 累计 |
|---:|---|---:|---:|
| 1 | `run_visible_battle_scene` | 6 136 | 6 136 |
| 2 | `battle_scene_controller::confirm` | 896 | 7 032 |
| 3 | `battle_scene_controller::_confirm_target` | 592 | 7 624 |
| 4 | `battle_player_action_flow::confirm_target_in_place` | 808 | 8 432 |
| 5 | `battle_action_combinations::resolve` | **1 456** | 9 888 |
| 6 | `battle_action_combinations::_resolve_sequence` | 1 392 | 11 280 |
| 7 | `battle_action_execution::resolve_in_place` | 64 | 11 344 |
| 8 | `battle_action_resolver::resolve_area_draft_in_place` | 1 496 | 12 840 |
| 9 | `battle_action_resolver::preview_area` | **720** | **13 560** |

### 3.3 链 B（胜利收尾链）—— 逐帧表

| # | 帧 | 字节 | 累计 |
|---:|---|---:|---:|
| 1 | `run_visible_battle_scene` | 6 136 | 6 136 |
| 2 | `battle_scene_controller::tick` | 2 432 | 8 568 |
| 3 | `battle_turn_flow::advance_empty_side` | **120** | 8 688 |
| 4 | `battle_turn_flow::_resolve_battlefield_objects` | 712 | 9 400 |
| 5 | `battle_action_resolver::_resolve_battlefield_object_event_in_place` | 1 424 | **10 824** |

### 3.4 ⭐ 全局最坏路径（两条链合起来的**上界**）

用 `deepest.py` 枚举**从 `run_visible_battle_scene` 出发的所有简单调用路径**
（994 141 条，**搜索 COMPLETE，未截断**）：

| # | 帧 | 字节 | 累计 |
|---:|---|---:|---:|
| 1 | `run_visible_battle_scene` | 6 136 | 6 136 |
| 2 | `battle_scene_controller::tick` | 2 432 | 8 568 |
| 3 | `battle_turn_flow::advance_empty_side` | 120 | 8 688 |
| 4 | `battle_condition_interpreter::evaluate_session` | 6 192 | 14 880 |
| 5 | `battle_condition_interpreter::_first_match` | 64 | **14 944** |

> ⭐ **14 944 B ≤ 21 308 B ⇒ 判定问题 = 「是」**（裕量 **6 364 B**，30 %）。
> 这是**任何运行时路径的上界**（不是抽样），所以它比「跑一次没炸」更强。
>
> 改前同一口径的最坏路径是 **26 888 B**
> （`scene 6 136 + tick 2 432 + combinations::resolve 9 504 + _resolve_sequence 1 392
>   + resolve_in_place 64 + resolve_area_draft_in_place 1 496 + preview_area 5 864`），
> **超预算 5 580 B**。

### 3.5 `preview_area` 等价性论证（W1-1d 的依据）

原实现把**整个单位数组**拷到栈上，**只为了把 source 那一格的 `position` 临时改成预览位置**。
新实现只拷 **source 单体**（468 B），等价性逐点核对：

| 原实现读到的值 | 新实现 | 一致？ |
|---|---|---|
| `collect()` 里每个 candidate 的 `position` | `collect_preview()`：candidate 是 source 自身 ⇒ 用 `source.position`（= 预览位置）；否则用 `candidate.position` | ✅ 与原「拷贝数组」完全相同 |
| `collect()` 里 `_matches_policy(source, candidate, policy)` | 该函数**只用** `candidate.id` / `candidate.side` / `source.id` / `source.side`，**不碰位置** | ✅ 行为不变 |
| `_preview(source, target, …)` 的 source | source 单体副本（位置 = 预览位置） | ✅ |
| `_preview(…, target->position)` | target 是 source 自身 ⇒ 取 source 副本（位置 = 预览位置）；否则取会话里的原值 | ✅ 与原「同一对象」情形相同 |
| `aggregate` 里 heal 的 `target->max_hp / target->hp` | 同上 | ✅ |

⇒ **`collect()` 本身一个字没改**（它还有 `battle_ai.h` 与 `test_battle_target_set.cpp` 两个调用点，
改了会影响它们）⇒ 新增 `collect_preview()` 而不是改 `collect()`。

### 3.6 EWRAM 事务池（可嵌套性）

```
battle_action_transaction_pool<MaxUnits>       // EWRAM, section ".ewram.w1"
  depth = 2 槽位（每个 = sizeof(battle_session<MaxUnits>) = 8 052 B）
  acquire(): LIFO 取一个槽位（绝不取模轮换 —— 嵌套的释放顺序不保证）
  release(): 归还（RAII 句柄 battle_action_transaction 在作用域结束时归还）
```

* ⭐ **为什么必须是 ≥2 槽位**：`advance_empty_side`（槽 0）持有副本 1 期间，
  `_resolve_battlefield_objects` → `resolve_battlefield_object_event`（槽 1）又拷一份
  ⇒ **两份同时存活**（父代理 §二 指出的陷阱）。**单例缓冲会被内层覆盖 ⇒ 回滚错对象。**
  槽位耗尽时 `acquire()` 退化为「就地操作调用方会话」（只丢事务、不污染别人的事务），
  属**不可达**分支（调用图已核对最深 = 2）。
* ⭐ **与 `battle_encounter_runtime::_transaction_workspace.session` 是不同对象** ⇒ 不会撞车
  （父代理 §四 的要求）。
* **新 EWRAM 常驻 = 2 × 8 052 = 16 104 B**（`.ewram` 18 728 → 34 836）；
  EWRAM 堆 71 696 → 55 592 B。
  ⚠️ 若要再省 8 KB：把 `advance_empty_side` 改成 `in_place` 变体 + 调用方用
  `_transaction_session()`（父代理 §三 方案 A）—— 但那样 `battle_turn_flow.h` 里
  其余 4 处拷贝版与 `resolve_battlefield_object_event` 的嵌套深度不变 ⇒ **池深度仍是 2** ⇒
  **省不了**，除非把 `_resolve_battlefield_objects` 改成调 `in_place` 变体（改动更大、风险更高）。
  ⇒ **本流选择保留 16 104 B**，理由：语义零风险 + `.su` 里「无 8 052 B 会话副本」这一条更干净。

---

## 4. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **W1-1** | 「攻击确认链里最深的单帧是 `resolve_battlefield_object_event`（8 088 B）」 | ELF 真实调用图（`bl` 边）+ `.su` 帧大小，枚举场景根出发的所有简单路径 | ⛔ **不成立**：它在**防御/非目标行动**链上，不在攻击确认链上；攻击确认链上最深的是 `battle_action_combinations::resolve`（9 504）与 `preview_area`（5 864） | **已证伪** |
| **W1-2** | 「U1 §2.2 的 21 304 B 栈链算术 = 真实同时在栈上的帧」 | 同上 + 读源码调用点 | ⛔ **不成立**：那张表是**几条互斥路径的并集**；「21 304 ≈ 实测 21 772」是巧合 | **已证伪** |
| **W1-3** | 「攻击确认链最坏路径 ≤ 21 308 B ⇒ 不会再溢出」 | 静态：枚举所有简单路径求最大帧和（上界） | ✅ **成立**（改后 14 944 B；改前 26 888 B） | **已确认** |
| **W1-4** | 「会话拷贝搬到 EWRAM ⇒ 事务语义不变（失败时不提交 session、不提交 rng）」 | 单测 + 战斗收据 + `advance_empty_side` 失败路径 | ✅ **成立**：提交点仍在 `if(result.success())` / `if(error == none)` 之后；单测 117/21 与基线逐名相同 | **已确认** |
| **W1-5** | 「EWRAM 静态 ⇒ 残差变大」 | 判定台残差（自己的 ROM `9127915b…` vs 基线 `c69ba4e4…`） | ⛔ **不成立**：**每一个指标逐项相同**（field sum 109 569 / median 1 372 / max 27 325 / zeros 4-25；overlay sum 857；attribution 4/17/4） | **已证伪** |
| **W1-6** | ⭐「**单个**共享 EWRAM 缓冲会被嵌套调用覆盖」 | 读源码：`advance_empty_side` 副本 1 存活期间 `resolve_battlefield_object_event` 又拷一份 | ✅ **成立** ⇒ 工作区必须**可嵌套**（LIFO 槽位池） | **已确认** |
| **W1-7** | ⭐「`preview_area` 的 5 616 B 单位数组拷贝可以只换成 source 单体拷贝，语义不变」 | 逐点核对 `collect` / `_matches_policy` / `_preview` 的位置依赖（§3.5） | ✅ **成立** | **已确认** |
| **W1-8** | 「EWRAM 事务池放不进 `.ewram` / `.sbss`」 | 编译报错：`only zero initializers are allowed in section '.sbss'` + `'roster' causes a section type conflict with 'pool' in section '.ewram'` | ✅ **成立**：`battle_session` 不可平凡默认构造 ⇒ `.sbss` 不行；`.ewram` 与模板 COMDAT 变量同段冲突 ⇒ 改用**独占段名 `.ewram.w1`**（`gba_cart.ld` 用 `*(.ewram*)` 通配 ⇒ 仍落在 EWRAM） | **已确认** |
| **W1-9** | ⭐⭐「**链 B（胜利收尾）**也会溢出」 | `.su`：`advance_empty_side` = 16 880 ⇒ 6 136 + 2 432 + 16 880 = **25 448 > 21 308** | ✅ **成立** | **已确认** |
| **W1-10** | ⭐⭐⭐「**链 A 的溢出点在 `preview_area`**」 | W2 的写监视点实测：`sp = 0x03002818`（比栈底低 940 B），且在 `resolve_battlefield_object_event` 上的断点**从未命中** | ✅ **成立**（采信 W2）⇒ 必须一起修 | **已确认（采信 W2）** |
| **W1-11** | ⭐「改完之后从场景根出发的最坏栈深（攻击确认链 **与** 胜利收尾链）≤ 21 308 B」 | `deepest.py` 穷举（994 141 条路径，COMPLETE） | ✅ **成立**：**14 944 B** | **已确认** |
| **W1-12** | ⭐「改完之后真实战斗能打赢、蜂 HP 会下降」 | `v1_battle.py`（忍具 / 普通招式各一次）+ 写监视点 | ✅ **成立**：忍具路径 `outcome=1`（胜利）、蜂 HP 25→0；普通招式蜂 HP 25→0；写监视点未命中 | **已确认** |
| **W1-13** | ⭐「**「はい」选不了**是栈溢出的次生现象」 | `v1_diag_confirm.py --trials "A"` | ✅ **成立**：改前按 A ⇒ ROM 死在那一帧（`ctrl/player/act_err` 全 0）；改后按 A ⇒ **相位 20 → 9**、战斗演出开跑（`busy=1, combat_stage=2`）、三个错误码全 0 | **已确认** |

---

## 5. 跑过的命令与关键数字

| # | 命令 | 关键数字 |
|---|---|---|
| **W1-C1** | `bash build/w18-w1/gen_su.sh`（`-fstack-usage` **重建**，不是陈旧的 `build/*.su`） | 252 → 252 个帧；**R1/R2/R3/R4 四个大帧全部消失** |
| **W1-C2** | `python3 build/w18-w1/deepest.py <elf> su run_visible_battle_scene 21308` | **994 141 条路径，COMPLETE（未截断）**，最大 **14 944 B** |
| **W1-C3** | 同上，threshold 40 000 | 最大仍是 14 944 B ⇒ 真实上界 |
| **W1-C4** | `python3 paths.py … 'battle_scene_controller::confirm' 'preview_area'` | 链 A-2 = 7 424（从 `confirm` 起） |
| **W1-C5** | `python3 paths.py … 'battle_turn_flow::advance_empty_side' '_resolve_battlefield_object_event_in_place'` | 链 B = 2 256（从 `advance_empty_side` 起） |
| **W1-C6** | `bash build/w18-w1/build.sh`（`make -j4`） | ✅ **`ROM fixed!`**；**无新增 `-Wstack-usage` 告警**；ROM sha **`9127915ba5bd9acc9ab605b62897aaa47e87a34995183b9071d1e694e686eaba`**；大小 12 130 856（+15 156）；`.ewram` 18 728 → 34 836 |
| **W1-C7** | `python tools/s49_battle_balance/v1_battle.py --rom build/w18-w1/butano-sequel/butano-sequel.gba --out build/w18-w1/run-a-tools --boot --max-turns 400 --use-tools` | ⭐ `errors: []`（**无 `rom-frozen`**）；`outcome: 1`、`outcome_is_victory: true`；`bee_hp_start {4..8: 25}` → `bee_hp_end {4..8: 0}`；`bee_hp_dropped: true`；`poke_commands: 0`；`from_real_battle: true`；`frames_run: 60 518`；`round: 13`；`settlement pages: 1 final: outcome` |
| **W1-C8** | 同上但**不**带 `--use-tools`（`--out build/w18-w1/run-b-notools`） | ⭐ `errors: []`；`bee_hp_end {6,7,8: 0}`（其余 4、5 仍 25）⇒ **`bee_hp_start ≠ bee_hp_end`**；`bee_hp_dropped: true`；`outcome: 2`（护送阵亡，但**攻击确实打中了**）；`poke_commands: 0` |
| **W1-C9** | `python tools/s49_battle_balance/v1_diag_confirm.py --rom … --out build/w18-w1/diag-confirm --move-cell 9,6 --action-index 3 --target 6,6 --trials "A"` | 按 A 前：相位 20、`scene_frame` 640 → 970 **持续推进**；按 A 后：**`phase_moved: true`、`scene_advanced: true`**，相位 **20 → 9**（`facing_selection`），`busy: 1`、`combat_stage: 2`、`combat_frame: 4`，`action_error/control_error/player_error` **全 0** ⇒ **「はい」现在能选了** |
| **W1-C10** | ⭐ `python tools/s49_w2/w2_confirm_sp.py --rom … --exe build/w18-w1/mgba-probe.exe --out build/w18-w1/sp-verify --bp none --watch 0x03002880` | ⭐ **写监视点未命中**（`fired=False`）；按 A 时 `sp = 0x03004D68`（**离栈底还有 7 092 B**）；`IRQ_VectorTable` 按 A 前后**逐字节相同**（`0803EB6D / 03000EB8 / 00000000 / 00000000 / 0804D855 / 00000000`）；相位 20 → 9，三个错误码全 0 |
| **W1-C11** | `python tools/s49_fidelity_report.py --out build/w18-w1/report.json --remake-rom build/w18-w1/butano-sequel/butano-sequel.gba --work-dir build/w18-w1/fid-work` | **本流 ROM `9127915b…`**：`field px` min 0 / median **1 372** / max **27 325** / sum **109 569** / zeros **4-25**；`overlay px` sum **857** / max 192；`attribution` identical **4** / product_diff **17** / pairing_diff **4**；`subclasses` 0/0/**4**；`confidence` high 16 / medium 7 / low 2；`distinct_remake_frames_used` 18；`content_sha 65022ba4…` |
| **W1-C12** | 同上，但**不**带 `--remake-rom`（⇒ 用共享树 ROM `c69ba4e4…`）＝ **基线** | `field px` min 0 / median **1 372** / max **27 325** / sum **109 569** / zeros **4-25**；`overlay px` sum **857**；`attribution` **4 / 17 / 4**；`subclasses` 0/0/**4**；`confidence` 16/7/2；`content_sha 0dcaa18b…`（与本流不同只因报告里嵌了 ROM 路径与 sha） |
| **W1-C13** | `bash build/w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/w18-w1/butano-sequel` | **pass = 117 / fail = 21**（与 W2 的基线 **117/21 逐名相同** ⇒ **零回归**） |
| **W1-C14** | `Get-Process -Name 'mgba-probe'` | 孤儿探针 **0 个**；空闲内存 9.6 GB / 31.8 GB |

---

## 6. 验收清单逐条结论

| # | 项 | 判据 | **结论** |
|---|---|---|---|
| **W1-1** | `resolve_battlefield_object_event` 栈帧 | 8 088 → ≤ 64 B | ✅ **8 088 → 无独立帧**（被内联进 `_resolve_battlefield_objects`，712 B 未变）；8 052 B 会话拷贝已移到 EWRAM |
| **W1-1b** | `battle_turn_flow::advance_empty_side` 栈帧 | 16 880 → ≤ 64 B（或等价小值） | ✅ **16 880 → 120**（`.su` 实测） |
| **W1-1c** | 同文件其余 4 处拷贝 | 同样处理，`.su` 里不再出现 8 052 B 级会话副本 | ✅ **5 处全改**；`.su` 里**已无任何 8 052 B 级会话副本** |
| **W1-1d** | `preview_area` 栈帧 | 5 864 → ≤ 64 B（或等价小值） | ✅ **5 864 → 720**（等价性论证见 §3.5） |
| **W1-2** | 攻击确认链总深 | ≤ 21 308 B，给出逐帧表 | ✅ **链 A-2 = 13 560 B**（逐帧表 §3.2）；**全局最坏 14 944 B**（§3.4，穷举 COMPLETE） |
| **W1-3** | `battle_action_combinations::resolve` | 给出数字；超预算一并处理 | ✅ **9 504 → 1 456** |
| **W1-4** | 重建 ROM | `ROM fixed!` + 记 sha | ✅ `ROM fixed!`；sha **`9127915ba5bd9acc9ab605b62897aaa47e87a34995183b9071d1e694e686eaba`** |
| **W1-4b** | ⭐ 写监视点自证 | 挂在 `IRQ_VectorTable[0]`，按 A 不应命中 | ✅ **未命中**；`sp = 0x03004D68`（离栈底 7 092 B）；IRQ 表前后逐字节相同 |
| **W1-5** | ⭐ 真实战斗（忍具） | 收据无 `rom-frozen` + 蜂 HP 下降 | ✅ `errors: []`；`outcome: 1`（**胜利**）；蜂 HP **25 → 0**；`poke_commands: 0`；`from_real_battle: true` |
| **W1-5b** | ⭐ 真实胜利 | 战斗结束后场景帧继续推进 | ✅ 收据走到 `settlement pages: 1 final: outcome`；战斗 60 518 帧、13 回合全程无冻结 |
| **W1-6** | 普通招式路径 | 同样不冻、同样掉血 | ✅ `errors: []`；蜂 HP **25 → 0**（6/7/8 号）；`bee_hp_dropped: true` |
| **W1-7** | 「はい」联动 | 记录按 A 之后的现象 | ✅ **改前是次生缺陷**：改后按 A ⇒ 相位 **20 → 9**、战斗演出开跑、三个错误码全 0 ⇒ **「はい」现在能选了**（W2 的问题被本流一并闭合） |
| **W1-8** | 判定台残差 | 记录读数；残差变大 ⇒ 换方法 | ✅ **与基线逐项相同**（field sum 109 569 / median 1 372 / max 27 325 / zeros 4-25；overlay 857；attribution 4/17/4）⇒ **EWRAM 排布变化没有改变画面**，**无需换方法** |
| **W1-9** | 单测 | pass/fail + 失败名单 | ✅ **pass = 117 / fail = 21**，与 W2 基线逐名相同 ⇒ **零回归**。失败名单（21 项，**与 U1 的 20 项预存债逐名相同**，多出的 `test_battle_range_ui_phase_truth_table` 是 U2 的在制品、未被 git 跟踪）：`test_battle_all_scenario_runtime` / `test_battle_campaign_route` / `test_battle_campaign_save` / `test_battle_campaign_scenario_42` / `test_battle_campaign_scenario_43` / `test_battle_campaign_scenario_44` / `test_battle_campaign_scenario_45` / `test_battle_campaign_scenario_46` / `test_battle_campaign_scenario_47` / `test_battle_campaign_scenario_49` / `test_battle_dynamic_deployment_turn` / `test_battle_material_pickups` / `test_battle_presentation_controller` / `test_battle_range_ui_phase_truth_table` / `test_battle_runtime_scene_gate` / `test_battle_s49_input_flow` / `test_battle_s49_opening` / `test_battle_scene_character_actions` / `test_battle_scene_controller` / `test_battle_scene_multi_unit` / `test_battle_scene_results` |

---

## 7. 越界请求（需要改别人独占文件的地方）

| # | 文件 / 行 | 要改成什么 | 为什么 |
|---|---|---|---|
| **R-1** | `game/include/konoha/battle_condition_interpreter.h`（`evaluate_session`，**6 192 B**） | 把 `evaluate_session` 的大局部量搬到 EWRAM 静态（照 `BN_DATA_EWRAM static` 模式），可把最坏路径再降 ~6 KB | 它是**改后链上最大的单帧**（14 944 B 里有 6 192 B）。**不是阻塞**（裕量已够），但它属于别家的独占文件 ⇒ 本流**没动** |
| **R-2** | `game/include/konoha/battle_player_action_flow.h`（`preview_move`，**5 992 B**）、`battle_ai.h`（`battle_ai::plan`，**4 360 B**） | 同上（搬到 EWRAM 静态） | 同上：分别是改后第 4、6 大的单帧。**不是阻塞** |
| **R-3** | `game/src/battle_runtime_scene.cpp`（`run_visible_battle_scene`，**6 136 B**） | 把剩下的重量级局部量搬到 EWRAM 静态 | 场景帧是每条链的根；它每省 1 字节，整条链就省 1 字节。**W4 独占 ⇒ 本流没动** |
| **R-4** | `game/include/konoha/battle_scene_controller.h`（`tick`，**2 432 B**） | 同上 | **W2 独占 ⇒ 本流没动** |

> ✅ **本流没有越界改任何别人的文件**；上表只是「还能再省栈」的建议，
> **不是本流的阻塞项**（判定问题已经闭合，裕量 6 364 B）。

---

## 8. 尚未闭合 / 剩余风险

1. ⛔ **判定台残差虽然与基线逐项相同，但 `content_sha` 不同**
   （`0dcaa18b…` vs `65022ba4…`）—— 因为报告 JSON 里嵌了 remake ROM 的路径与 sha256。
   **像素指标完全一致**（field / overlay / attribution / confidence 全部逐项相同）⇒
   画面没变。波末接线后父代理需在**统一构建**的 ROM 上重跑一次判定台做最终基线。
1b. ⚠️⭐⭐ **父代理的「可证伪预言 P-7」没有兑现**：修好 D4 之后残差**没有**从 **109 569**
   掉到 ≈ 27 000 量级，而是**逐项不变**。
   ⇒ **本流已把 D4 侧的前置条件清掉**（真实战斗链现在能打赢：`outcome=1`、蜂 HP 25→0），
   但**判定台的 remake 走的是开机键序**（`Down,Down` + 32×A，见报告的
   `MGBA_BOOT_SEQUENCE_KEY_SEQUENCE`）—— 而真实战斗要打 **13 回合 / 669 次按键**才赢
   ⇒ **那条 walk 根本没打完仗** ⇒ 父代理 §五-1 里那 4 帧
   （战斗打完 → 地图滚动 → 移动相位覆盖层）**仍然走不到**。
   ⇒ ⭐ **P-7 的兑现条件是「键序对齐（父代理 §五-3 / W5）+ 打完仗」，不是单修 D4**
   ⇒ 排期上 **W5 要提前**（否则残差不会因为 D4 修好而自动掉下来）。
2. ⚠️ **结算链仍只走了 1 页**（`settlement pages: 1 final: outcome`）。
   战斗已经能打赢并进入结算相位，但结算链的后半段（戰後對白 / 任務菜單）是 **W4 的活**。
   本流**没有**碰 `battle_runtime_scene.cpp` / `battle_result_content.h`。
3. ⚠️ **W1-6 那次跑 `outcome: 2`（护送阵亡）**：攻击确实命中并掉了血，
   但这一局没有赢。`from_real_battle: false` 是因为收据把「胜利」当作出击链的验收条件。
   ⇒ **W1-5（忍具路径）才是「真实打赢」的那条证据**（`outcome: 1`、蜂 HP 全灭）。
4. ⚠️ **事务池深度 2 是按当前调用图证明的**（`advance_empty_side` → `resolve_battlefield_object_event`）。
   若以后有人在 `advance_empty_side` / `complete_defense` 里再加一层会话拷贝，
   池会耗尽 ⇒ `acquire()` 退化为「就地操作」（丢事务但不污染别人的事务）。
   ⇒ **建议在 `battle_action_transaction_pool` 里加一条注释或断言**（本流已写了注释）。
5. ⚠️ 本机构建**不是字节可复现**的 ⇒ 本笔记的一切数字**只绑定本 lane 的
   ROM `9127915ba5bd9acc9ab605b62897aaa47e87a34995183b9071d1e694e686eaba`**。
   波末父代理统一接线 + 统一构建后**必须重跑** W1-5 / W1-8。

---

## 9. 确认

* 新文件一律 **LF、无 BOM**（`notes/s49-fidelity/W18-W1-stack-overflow.md`、`build/w18-w1/*.sh`、`build/w18-w1/*.py`）；
* **未提交 git**（两个仓都没有 `git add/commit`）；
* 共享的 `build/mgba-probe/mgba-probe.exe`：**未动**（用的是私有副本 `build/w18-w1/mgba-probe.exe`）；
* 孤儿 `mgba-probe.exe`：**0 个**；
* 逆向线 `D:\Shell\gba-naruto-reverse`：**未访问**；
* **没有伪造任何帧**：所有数字都来自本 lane 自己重建的 `.su`、本 lane 的 ELF 调用图、
  本 lane 的 ROM 实跑收据，以及 mGBA 的写监视点现场。
