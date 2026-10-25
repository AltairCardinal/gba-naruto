# W4 —— S49 存档字节 + 边界行为取证 + 出包准备

**日期**：2026-10-24 · 流 W4（wave 4）
**独占**：`tools/s49_save_boundary/`、本文件；重制侧**未改动任何产品代码**
（`battle_campaign_sram.cpp` / `.h` 一字未动 —— 取证结论是「不需要改」）。

---

## 0. 一句话结论

**原版在整场战斗里对 SRAM 的改动是 0 字节（46 个检查点逐字节相同，含「打赢之后的任务菜单」），而重制侧
在战斗结束会自动写盘 —— 两边的存档容器、身份机制、校验算法、槽模型全部不同，
原版 loader 读重制存档接受 0 条记录、重制 loader 读原版存档接受 0 个槽 ⇒ 存档「逐字节一致」在当前设计下
**不可达**，差异表与施工单见 §5；边界行为 12 条对照表见 §6（原版 = 规格，缺陷照抄）。**

---

## 1. 做了什么 / 改了哪些文件

### 1.1 新增（独占目录，本流独占）

| 路径 | 说明 |
|---|---|
| `tools/s49_save_boundary/s49_save_common.py` | 路径 / 常量 / 原版 descriptor 表（内嵌 + 每次跑与逆向线 `bank.json` 交叉核对）/ 探针封装 |
| `tools/s49_save_boundary/s49_save_layout.py` | 两种存档格式的纯字节解码器（原版 10 条记录 / 重制 2 个 `KBCS` 槽）+ 字段表生成 |
| `tools/s49_save_boundary/capture_sram.py` | 用无头 mGBA 探针 `framedump 1 0x0E000000 32768` 抓卡带 SRAM；原版 46 个检查点、重制 16 个检查点 |
| `tools/s49_save_boundary/compare_save_images.py` | 逐字节 diff + 字段级差异表 + 两侧 loader 互相兼容性判定 + Markdown 收据 |
| `tools/s49_save_boundary/run_all.py` | **一条命令**：`--repeat 2` 跑两遍并断言逐字节一致 |
| `notes/s49-fidelity/W4-save-boundary.md` | 本文件 |

### 1.2 没有改的东西

* **重制线任何文件**：一个字节都没动（含本流独占的 `battle_campaign_sram.cpp` / `.h`）。
* `battle_runtime_scene.cpp`（W1 独占）、`battle_range_ui_style.h` / `battle_audio_*.h` /
  `battle_unit_*.h` / `battle_visual_resource_coordinator.h`：未碰。
* 逆向线 `D:\Shell\Github\gba-naruto-reverse`：**全程只读**（只调用了它的
  `verify_save_state_records.py` 做交叉验证，没有写它）。
* `tools/s49_fidelity_report.py`（W2）、`tools/s49_victory_capture/`（W3）、
  `tools/s49_audio_probe/`（J）、`tools/s49_rule_probe/`（F）、`tools/s49_overlay_align/`（G）：未碰。
* **共享探针 `build/mgba-probe/mgba-probe.exe`**：未覆盖（会 LNK1104）。本流另建私有探针
  `build/mgba-probe-w4/mgba-probe.exe`。

### 1.3 私有探针（为什么要自己建）

共享探针的 `framedump` **在本机不可用**：

| 尝试 | 参数 | 结果 |
|---|---|---|
| 共享 exe | `framedump 1 0x0E000000 32768 0x000 <prefix>` | `Parse error` |
| 共享 exe | `framedump 1 0x0E000000 32768 <prefix>` | `Parse error` |
| 共享 exe | `framedump 1 234881024 32768 <prefix> 0x000` | `Parse error` |

共享 exe 的用法行是 `framedump <count> <addr> <len> <prefix> [keymask]`，
而仓内 `tools/mgba_probe/host_main.c` 解析的是 `<count> <addr> <len> <keymask> <prefix>`
⇒ **共享 exe 与仓内源码不是同一版**。本流按仓内源码自建私有探针：

```powershell
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-w4'
python tools/mgba_probe/build.py
```

---

## 2. 跑了哪些验证（命令 + 关键数字）

| # | 命令 | 关键数字 |
|---|---|---|
| V1 | `python tools/s49_save_boundary/run_all.py --repeat 2` | 两次跑共 **62 张 SRAM 镜像 sha256 全同**；`identical_across_runs = true`；exit 0 |
| V2 | 同上，单跑 | 原版 **46 个检查点 / 只有 1 种镜像**；战前→战后差 **0 字节**；重制 erased→save1 **4020 B**、save1→save2 **4020 B**、save2→战斗中 **0 B**；跨格式 **3856 B** 不同 |
| V3 | `python tools/s49_save_boundary/compare_save_images.py` | 产出 `build/s49-save-boundary/receipts/save_compare.{json,md}` |
| V4 | 逆向线独立验证器：`python D:\Shell\Github\gba-naruto-reverse\tools\verify_save_state_records.py --bank .../bank.json --sram-dump <我抓的镜像> --json` | `bank_validation.ok = true`、`sram_validation.ok = true`、`issues = []`；记录 0 校验 `0xF7`、记录 2 `0xE3` —— **与我的解码器逐项一致** |
| V5 | 我的镜像 vs 逆向线已认证的原版存档 `artifacts/runtime-checkpoints/tutorial-ui-save.sav` | sha256 **完全相同**（`9fedf6bf1c43ad08…`）⇒ 抓取方法本身被认证 |
| V6 | `python tools/mgba_probe/verify_headless_recording.py` | `OK: the recording chain is headless and silent.`，exit 0 |
| V7 | `python tools/s49_fidelity_report.py --out build/s49-report/report-w4.json` | exit 0；`field px: min 0 / median 1940 / max 27325 / zeros 3/25`；`attribution: identical 3 / product_diff 14 / pairing_diff 8`；`subclasses: black_transition 2 / static_frame 3 / moment_mismatch 3`；`overlay px: sum 1060 / max 187`；`anchors: ok/ok`，配对质量 6/25 |
| V8 | 扫重制侧 `graphics/battle_unit_visual_catalog.json` 全部 **2674** 帧 | 非法终止符**只有 1 帧**：角色 26 / 视觉槽 2 / 帧 2，`frame_trailer_raw_hex = fffb0000`、`frame_trailer_signed_value = -1025`、`renderer_terminator = false`、`frame_pointer = 0x0825A8D0` |
| V9 | 读重制侧运行期数据模型 `generated_battle_unit_visual_content.h` | `battle_unit_visual_frame::components[5]`（定长 5 槽，每项带 `visible` 标志）⇒ **运行期只画列出的 component，不越界** |

产物（都在 `D:\Github\gba-naruto\build\s49-save-boundary\`）：

* `sram/original-walk-a02041dc/*.sav`（46 张 32 KiB 镜像）
* `sram/remake-walk-7451892f/*.sav`（16 张 32 KiB 镜像）
* `receipts/capture_sram.json`、`receipts/save_compare.json`、`receipts/save_compare.md`、
  `receipts/run_all.json`

---

## 3. 两侧的存档是怎么工作的（实测）

### 3.1 原版

* SRAM **32 KiB**，卡带头 `0xE2`（ROM+RAM+电池）。
* **10 条固定偏移记录**（逆向线 `sequel/content/save-state/bank.json`，ROM 表在 `0x53D848`）：
  每条 = **19 B 身份串 `Naruto-KONOHASENKI\0`** + `payload_length` 负载 + **1 B 校验 `~sum(payload)`**；
  下一条起点 = 本条 `payload_length + 0x14`。
* 战斗 14 入口时的有效记录：**记录 0**（4732 B，校验 `0xF7`）与 **记录 2**（20 B，校验 `0xE3`）；
  其余 8 条是擦除态（全 FF）。占用 **22468 B**（0x57D4）。
* **记录 7** 的负载长度 **6084 B = 13 × 0x1D4** —— 与 C 流 dump 的「战斗单位池」
  （13 槽 × 468 B）**逐字节对应**，battle 14 的 9 名单位就在这条记录里。
  记录 2 的 20 B 负载实测 = `0e000000 00000000 0e000000 00000000 0000`。
* **写盘时机**：只有世界地图的「存档」菜单会写。**战斗全程 0 字节变化**（§4）。

### 3.2 重制侧

* SRAM **32 KiB**，卡带头 `0x4A`（ROM+RAM+电池，RAM size `0x0A` = 32 KiB）—— 与原版**同样大小**。
* **2 个 4096 B 槽**（槽 0 @ 0，槽 1 @ 4096）：
  `'KBCS'`(4) + `version`(1) + `reserved`(1) + `payload_size`(u16) + `generation`(u32)
  + payload + **CRC32**(4)。
* payload = **3524 B** 的战役状态：
  `chapter_id`(u16) + `flags`(u32) + `party[3]` + 1 保留字节 + `ninja_tools[94]` + `materials[18]`
  + `characters[63] × 54 B`（active/level/experience/training_points/initialized/primary[15]/secondary[24]/tools[9]）。
* 实测（准备场景按一次「存档」）：
  `chapter_id = 49`、`flags = 0`、`party = [1,2,3]`、
  忍具 `{1:1, 11:1, 37:1, 67:1}`、材料 `{6:1}`、
  激活角色 3 个 —— 1(lv5/exp160/tp4, 装备 1/11/37)、2(lv4/exp100/tp3)、3(lv5/exp190/tp4)，其余 60 个未激活。
* **写盘时机**：① 准备场景的「存档」菜单；② **战斗胜利后自动存档**（`main.cpp` 的
  `campaign != campaign_checkpoint` 分支）。
* ⚠️ **重制树里有两套存档 codec**：产品用的是上面的 `KBCS` v2；
  `benchmark/include/konoha_bench/save_codec.h` 是**基准测试用的 32 B `KNSV` v1 桩**，
  跟 SRAM 无关。**别把后者当成产品格式。**

---

## 4. 战斗期写不写盘（核心实测）

### 4.1 原版：**不写**（46 个检查点逐字节相同）

| 检查点 | 来自 | SRAM sha256 |
|---|---|---|
| `original-pre-battle` | `scenario-49-battle-14-entry.ss9`（战斗 14 入口） | `9fedf6bf1c43ad08…` |
| `original-battle-tool67-entry` | 战斗中 | 同 |
| `original-battle-tool67-confirmation` | 战斗中 | 同 |
| `original-battle-tool37-confirmation` | 战斗中 | 同 |
| `original-battle-turn4-two-kills` | 战斗中（回合 4，2 只蜜蜂已死） | 同 |
| **`original-post-battle`** | **`scenario-49-battle-14-postbattle-task-menu.ss9`（打赢之后的任务菜单）** | **同** |
| `original-step-01..40-A` | 40 次 A 的走位（覆盖开场对白、回合横幅、移动范围、命令菜单、忍术列表、瞄准、伤害预测、确认框） | 同 |

⇒ **46 张镜像只有 1 种哈希**。战前 → 战后差 **0 字节**。
⇒ **原版的「战后存档」不是战斗产物**：战斗结束只回到世界地图，存档要玩家在
世界地图的「存档」菜单里手动写。

### 4.2 重制侧：战斗本身不写，但**战斗结束会写**

| 阶段 | 检查点 | SRAM sha256 | 与上一阶段的差 |
|---|---|---|---:|
| 上电（无存档） | step-01..03 | `2d864c0b789a4321…`（全 FF） | — |
| 准备场景按「存档」 | step-04 | `b7ba3497f420f833…`（槽 0 gen 1） | **4020 B** |
| 再按一次「存档」 | step-08 | `642b2d4ff6b384e6…`（槽 0 gen 1 + 槽 1 gen 2） | **4020 B** |
| 战斗中（step-09..16） | 战斗内 | `642b2d4ff6b384e6…`（不变） | **0 B** |

⇒ 4020 B = 4096 B 槽里**值不是 0xFF** 的字节数（负载区 3536 B + 零填充区 556 B 里非 FF 的部分 +
CRC 4 B；负载里有 76 个字节本身就是 `0xFF` —— 那是 `locked_action_level`）。
⇒ **两次存档 ⇒ 槽轮换 + 世代递增**（槽 0 gen 1 → 槽 1 gen 2），两次的 CRC32 都自洽。

---

## 5. 字段级存档差异表

### 5.1 逐字节（跨格式）

| 项 | 数字 |
|---|---:|
| 原版存档镜像（32 KiB） | `9fedf6bf1c43ad08…` |
| 重制存档镜像（32 KiB，含两个槽） | `642b2d4ff6b384e6…` |
| **逐字节不同的位置数** | **3856** |
| 不同的连续区间数 | 149 |

### 5.2 字段级（每条记录 / 每个槽）

| 字段 | 原版 | 重制 | 差异 | 状态 |
|---|---|---|---|---|
| record 0 header | `Naruto-KONOHASENKI` (19 B) @0 | — | 原版有身份头；重制用 4 B 魔数代替 | active |
| record 0 payload | 4732 B @19 | — | 原版每条记录自带负载 | active |
| record 0 checksum | `~sum(payload) = F7` @4751 | — | 原版 1 B 取反和 vs 重制 4 B CRC32 | active |
| record 1 | 全 FF @4752 | — | 未用记录 | erased |
| record 2 header | `Naruto-KONOHASENKI` (19 B) @9504 | — | 同 record 0 | active |
| record 2 payload | 20 B @9523 | — | 负载实测 `0e000000 00000000 0e000000 00000000 0000` | active |
| record 2 checksum | `~sum(payload) = E3` @9543 | — | 同上 | active |
| record 3 / 4 / 5 / 6 | 全 FF | — | 未用记录 | erased |
| record 7 | 全 FF @14408（**负载本应是 6084 B = 13×0x1D4 的战斗单位池**） | — | ⚠️ 这条记录在**这份**存档里是擦除态（战斗名册是战斗期内存，不是存档内容） | erased |
| record 8 / 9 | 全 FF | — | 未用记录 | erased |
| slot 0 header | — | `4b424353` v2, payload_size=3524, generation=1 @0 | 重制有版本/长度/世代三字段，原版没有 | active |
| slot 0 payload | — | 3524 B @12 | 章节/队伍/库存/63 个角色成长 | active |
| slot 0 checksum | — | CRC32 `22128FC4` @4092 | 4 B CRC32 vs 1 B 取反和 | active |
| slot 1 header | — | `4b424353` v2, payload_size=3524, generation=2 @4096 | 同上 | active |
| slot 1 payload | — | 3524 B @4108 | 同上 | active |
| slot 1 checksum | — | CRC32 `764EDF57` @8188 | 同上 | active |

### 5.3 语义映射（游戏状态落在哪）

| 语义 | 原版落在哪 | 重制落在哪 | 差异 |
|---|---|---|---|
| 存档容器 | 10 条固定偏移记录，起点 = 前一条 `payload_len + 0x14` | 2 个 4096 B 槽，槽 1 起点 = 4096 | ★★ 容器不同 ⇒ 互相读不了 |
| 存档身份 | 每条记录 19 B 身份串 | 槽头 4 B 魔数 | ★★ 身份机制不同 |
| 完整性 | 1 B `~sum(payload)` | 4 B CRC32 | ★★ 校验算法不同 |
| 版本 / 世代 | 无版本号；**无世代计数器**，10 条记录同时有效 | version + payload_size + generation，每次写**换槽 + 世代 +1** | ★★ 原版没有「双槽轮换 + 世代」 |
| 关卡进度 | record 0 payload（**负载内部未逐字段解码**） | `chapter_id` (u16 @+12) | 重制侧已逐字段 |
| 队伍 | record 0 payload（未逐字段解码） | `party[3]` @+18 | 重制侧已逐字段 |
| 忍具 / 材料库存 | record 0 payload（未逐字段解码） | `ninja_tools[94]` @+22 + `materials[18]` @+116 | 重制侧已逐字段 |
| 角色成长（等级/经验/训练点/忍术等级/装备） | record 0 payload（未逐字段解码） | `characters[63] × 54 B` @+134 | 重制侧已逐字段 |
| 战斗名册（坐标/HP/阵营/行动标记） | ★ record 7 的负载 6084 B = 13 × 0x1D4（**battle 14 的 9 名单位就在里面**，见 C 流 roster dump） | ★ **无对应字段** | ★★ 语义缺口：重制不落盘战斗名册 |
| 战斗结果 / 回合状态 | record 2 (20 B) / record 8 (1404 B) / record 9 (512 B) | 无对应字段 | ★★ 语义缺口 |
| 存档写入时机 | 只有世界地图「存档」菜单（战斗全程 0 字节变化） | 准备场景「存档」菜单 + **战斗胜利后自动** | ★★ 写盘时机不同 |
| 落盘字节数 | 22468 B（10 条记录用满 0x57D4） | 8192 B（2 × 4096） | ★★ 占用差 14276 B |

### 5.4 互相能不能读（两侧 loader 的头部检查各自重放）

| 读取方 | 读取对象 | 结果 |
|---|---|---|
| 原版 loader | 原版存档 | 接受记录 **[0, 2]** |
| 原版 loader | **重制存档** | 接受记录 **[]** |
| 重制 loader | **原版存档** | 接受槽 **[]** |
| 重制 loader | 重制存档 | 接受槽 **[0, 1]** |

### 5.5 施工单（**本流不执行**，交产品线决策）

| # | 事项 | 影响面 | 备注 |
|---|---|---|---|
| C1 | **存档格式整体对齐原版**（10 条记录 / 19 B 身份串 / 1 B 取反和） | `battle_campaign_save.h` + `battle_campaign_sram.cpp`（本流独占）+ 所有已发存档作废 | 原版**没有版本号** ⇒ 对齐后无法做格式演进；这是**产品决策**，不是缺陷 |
| C2 | 只对齐**写盘时机**（战斗结束不自动存档，改成世界地图菜单写） | `src/main.cpp`（**不在**本流独占） | 会改变玩家可预期的「打完就存」行为 |
| C3 | 只对齐**校验算法**（4 B CRC32 → 1 B `~sum`） | 本流独占 | ⚠️ **降级**：1 B 和校验有单字节碰撞，重制侧更强，不建议为了像而改 |
| C4 | 补**战斗名册落盘**（对齐 record 7 的语义） | 需要新的存档字段（版式变更） | 与 C1 绑定才有意义 |
| C5 | 保留现状（**推荐**） | — | 现有设计文档明确写了「以字节 buffer 模拟 SRAM，**不实现旧 ROM 存档兼容**」；把它当**产品特性**而不是缺陷，并在此处留档 |

---

## 6. 边界行为对照表（原版行为 = 规格）

| # | 边界情形 | 原版实际怎么做 | 重制侧现在怎么做 | 差在哪 | 结论 |
|---|---|---|---|---|---|
| B1 | 损坏终止符 `0xFBFF` 的**字面量** | ROM `0x0825A8E4` 字节 `ff fb 00 00` ⇒ 有符号 u16 = **−1025**（不是 −1 ⇒ 渲染器不停） | 生成器把 `frame_trailer_raw_hex="fffb0000"` / `frame_trailer_signed_value=-1025` / `renderer_terminator=false` 写进 `battle_unit_visual_catalog.json`；全表 **2674 帧里只有这一帧**非法 | 无 | 🟢 **一致**，且**故意不修**那一字节（原版确实越界） |
| B2 | 渲染器的终止条件 | 只认 **−1（0xFFFF）**；`0xFBFF` 不停 ⇒ **继续每 20 B（0x14）读一个 component** | 运行期的 component 列表是**编译期定长**（`battle_unit_visual_frame::components[5]`，每项带 `visible`）⇒ **只画列出的 component** | ★ 原版**越界多画 3 个 component**，重制**不越界** | 🔴 **差**：缺陷只在**记录层**照抄，**运行层没照抄**。该角色不在 S49 出场 ⇒ **对 S49 像素无影响** |
| B3 | 越界轨迹 | 运行期轨迹 **4 次**循环命中：`0x0825A8E4`(FBFF/−1025) → `0x0825A8F8`(00FF/255) → `0x0825A90C`(0100/256) → `0x0825A920`(A8D0/−22320)，步长 0x14 | 运行期没有 component 指针遍历 ⇒ **没有这条轨迹可对拍** | ★ 原版有越界轨迹，重制侧没有 | ⚪ 若要 100% 照抄：重制运行时也要按 20 B 步长越界读 3 个 component 并画出来 |
| B4 | 对照实验（把 `0x0825A8E5` 的 `0xFB` 改成 `0xFF`） | 对照 ROM 里渲染器在 `0xFFFF` 就停，`repaired_component_count = 1` | 重制侧本来就是 1 个 component ⇒ **等于「修好后的原版」** | ★ 这正说明重制侧是「修好的原版」而不是「带 bug 的原版」 | 🔴 同 B2（**缺陷照抄的口径没满足**） |
| B5 | **蜜蜂是否进轮转**（行动单位轮转） | 行动单位指针**跨阵营推进**：单位池 `+0xC1`（正在行动）逐字节差分 → step-04 A → 槽 **5**(3,4)、step-05 B → 槽 **6**(4,8)、step-06 B → 槽 **7**(3,11)，**三个都是敌方蜜蜂**；分布是 4 玩家 + 5 敌方；状态栏因此显示「蜜蜂 待機 25 6」（红字） | `battle_session::cycle_roster_unit` 过滤 `unit.active && unit.side == _current_side` ⇒ **玩家回合的选择游标永远不会落到蜜蜂**；敌方回合由 AI 逐只驱动敌方单位 ⇒ 蜜蜂**在敌方回合轮流行动** | ★ 差别只在**玩家回合的游标能不能指到蜜蜂** | 🔴 **差**：原版能指到（状态栏出现「蜜蜂」），重制不能。像素级判据要取「**下一轮的可选中单位**」（结算面板不足以判定 —— 逆向线 §4.3.50 D2-b） |
| B6 | 存档容器被对方读到 | loader 认 19 B 身份串 | loader 认 4 B 魔数 + 版本 + 长度 + CRC32 | ★★ **互不兼容**（§5.4） | 🔴 **差**（见施工单 C1/C5） |
| B7 | 战斗期写不写盘 | **不写**：46 个检查点（含打赢后的任务菜单）逐字节相同 | **不写**（战斗本身 0 B 变化），但**战斗胜利后自动写** | ★★ 写盘时机不同 | 🔴 **差**（§4） |
| B8 | 双槽 / 世代 | **没有**双槽轮换：10 条记录同时有效 | 2 槽轮换 + `generation + 1`（实测 slot0 gen1 → slot1 gen2） | ★ 原版没有世代计数器 | ⚪ 属**重制侧自创机制**，不是「照抄」对象 |
| B9 | 空 SRAM / 全新档 | SRAM 全 FF ⇒ 记录全空 ⇒ 走「无存档」分支 | 两槽都无效 ⇒ `used_default = true`，用 `empty_battle_campaign()` | 语义一致 | 🟢 **等价** |
| B10 | 损坏存档的降级 | 单条记录损坏只丢那一条，其余记录照读 —— **未实测**（需要人为破坏一份 `.sav` 再冷启动） | 单槽 CRC 错 ⇒ 该槽 `bad_crc` 丢弃；另一槽有效就用它；**两槽都坏 ⇒ `invalid_state` ⇒ `BN_ASSERT` 崩溃** | ★ 原版「降级到部分存档」，重制「两槽都坏就崩」 | ⚪ **原版侧未实测**（判据：破坏 `9fedf6bf…` 镜像的记录 0 校验字节，冷启动看是否还能读出记录 2） |
| B11 | 负载长度 / 越界 | 记录长度是**编译期常量**（4732/20/8/24/6084/1404/512），运行时改不了 | `payload_size` 是**头里的 u16**，解码端核对（不等 ⇒ `bad_payload_size`）；负载内字段长度全为编译期常量 | 无实质差异 | 🟢 **等价** |
| B12 | 校验强度 | 1 B `~sum(payload)` ⇒ **单字节碰撞**，可被伪造 | 4 B CRC32 | ★ 重制更强 | ⚪ **差**（是重制侧改进，不是缺陷；要 1:1 就得降级 —— 见施工单 C3，**不建议**） |

---

## 7. 出包准备清单

「可玩 ROM + 一条复现命令 + 收据 + 1:1 报告」四件套的现状：

| # | 出包要素 | 现状 | 还缺什么 | 归谁 |
|---|---|---|---|---|
| 1 | **可玩 ROM** | `butano-sequel\butano-sequel.gba`，sha256 `804dd79384a96a2cc90a44e528277576992868343c087a64d37a27851696eb1d`（构建于 2026-10-24 02:54:24） | ⚠️ **W1 还要重建**（接线 H2 / L / G 的改动）⇒ **sha256 一定会变**，出包前必须重钉并重跑本流 | **W1** |
| 2 | **一条复现命令（判定台）** | `python tools/s49_fidelity_report.py --out build/s49-report/report.json`；磁盘上的版本**已带 W2 的升级**（`black_transition` / `static_frame` / `moment_mismatch` 三分类 + 内容锚 + overlay px + confidence），本流实测 exit 0 | 出包前必须与 **W2 的最终版本**再对齐一次并重跑（基线：战场区残差 min 0 / 中位 1940 / max 27325 / 全 0 帧 3；归因 一致 3 · 产品差 14 · 配对差 8；overlay px sum 1060） | **W2** |
| 3 | **无窗口无声门禁** | `python tools/mgba_probe/verify_headless_recording.py` → **OK**（本流实测 exit 0） | 无 | ✅ 已完成（W4 实测） |
| 4 | **存档字节收据** | `python tools/s49_save_boundary/run_all.py --repeat 2` → 62 张镜像两次跑**逐字节一致**；`receipts/{capture_sram,save_compare,run_all}.json` | 缺「**原版打赢后回世界地图按存档**」与「**重制侧战斗胜利后自动存档**」两份镜像（都需要打赢 S49） | **W4**（工具就绪）+ **W3/M**（胜利路线） |
| 5 | **边界行为收据** | §6 的 12 条对照表 | B10（原版单记录损坏的降级行为）**未实测**；B5 的**像素级判据**（下一轮可选单位）未取 | **W4**（B10）/ **W1**（B5） |
| 6 | **证据目录** | `notes/s49-fidelity/`：A / B / C / E / F / H / J / K / G / H2 / L / M / P + WAVE2 / WAVE3 / WAVE4 任务书 + **W4** | — | ✅ |
| 7 | **1:1 报告** | **不存在** | `docs/s49-fidelity-report-2026xxxx.md`：要汇总残差数字、逐格族名对拍 AFTER、存档差异表（§5）、边界表（§6） | **父代理**（汇总四路） |
| 8 | ROM 可运行性 | 判定台本次跑完 25 + 35 帧、exit 0 | W1 重建后要重跑 **4096 帧不崩** + 中文标题画面正常 | **W1** |
| 9 | 单元测试 | — | `battle/tests/` 既有跑法全绿（W1 的验收项） | **W1** |
| 10 | 出包基线钉 | BRIEF 订正③：本机构建**非字节可复现** ⇒ 基线 savestate **load 不了** | 出包必须**随包带 ROM + 重录命令**，不能只带 savestate；且本流的私有探针（`build/mgba-probe-w4`）不在仓内 ⇒ 复现命令要先建私有探针 | **父代理** |
| 11 | 存档格式决策 | §5.5 施工单 C1–C5 | 「要不要把重制存档改成原版格式」是**产品决策**，需要父代理拍板 | **父代理** |

---

## 8. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| W4-1 | 探针能读出卡带 SRAM（`0x0E000000`） | 无头 mGBA 探针 `dump 0x0E000000 64` | 擦除态返回 `FFFFFFFF…`；`load` 战斗 14 存档后返回 `4E617275746F2D4B4F4E4F…` | **已确认** |
| W4-2 | 共享探针的 `framedump` 可用 | 三种参数顺序各试一次 | 全部 `Parse error`（共享 exe 与仓内 `host_main.c` 不同版）⇒ 改用自建私有探针 | **已证伪** |
| W4-3 | 原版在战斗期会写 SRAM | 战前 / 4 个战斗中 / **打赢后的任务菜单** / 40 个走位步 = 46 个检查点逐字节比 | 46 张镜像**只有 1 种**（`9fedf6bf…`），战前→战后 **0 字节** | **已证伪**（原版战斗中不写盘） |
| W4-4 | 我抓的 SRAM 与逆向线已认证的原版存档一致 | 与 `artifacts/runtime-checkpoints/tutorial-ui-save.sav` 比 sha256 | `9fedf6bf1c43ad08…` **完全相同** | **已确认** |
| W4-5 | 我的记录解码器与逆向线的独立实现一致 | 逆向线 `verify_save_state_records.py` 验我的镜像 | `bank_validation.ok` / `sram_validation.ok` 均 true，`issues = []`；记录 0 `0xF7`、记录 2 `0xE3` 与我一致 | **已确认** |
| W4-6 | 重制侧在战斗期会写 SRAM | 准备场景存档后连续 12 个检查点 | 战斗中 **0 字节**变化（`642b2d4f…` 连续 9 个检查点不变） | **已证伪**（战斗本身不写） |
| W4-7 | 重制侧每次写盘会换槽并递增世代 | 准备场景连按两次「存档」 | 槽 0 gen 1 → 槽 0 gen 1 + 槽 1 gen 2，两槽 CRC32 均自洽 | **已确认** |
| W4-8 | 两边的存档能互相读 | 两侧 loader 的头部检查各自重放 | 原版 loader 读重制存档接受 **0** 条；重制 loader 读原版存档接受 **0** 个槽 | **已确认**（互不兼容） |
| W4-9 | 重制侧已记录 `0xFBFF` 缺陷，且**运行时不越界** | 扫 catalog 2674 帧 + 读运行期数据结构 | 只有 1 帧非法（角色 26/槽 2/帧 2，`fffb0000`/−1025/`renderer_terminator=false`）；运行期是定长 5 槽 + `visible`，不越界 | **已确认** |
| W4-10 | 蜜蜂在重制侧的轮转里 | 读 `battle_session::cycle_roster_unit` 与敌方回合推进 | 玩家回合游标按 `side == _current_side` 过滤 ⇒ **不会**落到蜜蜂；敌方回合 AI 逐只驱动敌方单位 | **部分确认**（代码级已定，像素级判据未取） |
| W4-11 | 原版「蜜蜂进轮转」的判据 | 逆向线 `+0xC1`（正在行动）逐字节差分 | step-04/05/06 行动槽依次 **5 / 6 / 7**，都是敌方蜜蜂 ⇒ 原版行动指针跨阵营推进 | **已确认** |
| W4-12 | 存档比对可复跑 | `python tools/s49_save_boundary/run_all.py --repeat 2` | 两次跑 62 张镜像 **sha256 全同**，`identical_across_runs = true`，exit 0 | **已确认** |
| W4-13 | 重制侧「战后自动存档」的镜像能拿到 | 打赢 S49 | 未达成：战斗尚未打赢（缺胜利驱动器，属 W3/M 范围） | **未验** |
| W4-14 | 原版单记录损坏时的降级行为 | 破坏一份 `.sav` 再冷启动 | 未做（本流无破坏性测试环境；判据见 §6 B10） | **未验** |

---

## 9. 剩下什么 / 卡在哪

1. **重制侧「战斗胜利后自动存档」的真实镜像没拿到**（W4-13）。
   卡点：需要打赢 S49（3 玩家 vs 5 蜜蜂，十来次十字手里剑），而**胜利驱动器是 W3/M 的活**
   （它们在做原版的胜利路线）。本流已把管道备好：W3/M 的胜利脚本一到位，
   `capture_sram.py` 只要在胜利后加一个检查点就能出镜像。
   ⚠️ 本流**没有**为了拿镜像去改产品代码，也没有伪造。
2. **原版侧「损坏存档降级」未实测**（W4-14，B10）：需要一份人为破坏的 `.sav` + 冷启动，
   本流没有做破坏性实验的环境。
3. **原版 record 0 的 4732 B 负载没有逐字段解码**：只确认了「它是负载、校验是 `~sum`、
   内容是小计数器数组（30 段非 FF 区域）」。要逐字段需要逆向线配合。
4. **蜜蜂轮转的像素级判据**（B5）未取：需要「下一轮的可选中单位」这一帧，属 W1/W3 的录制范围。

---

## 10. 复跑

```powershell
cd D:\Github\gba-naruto
$env:PYTHONIOENCODING='utf-8'

# 0) 私有探针（只建一次；不要覆盖共享的 build/mgba-probe）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-w4'
python tools/mgba_probe/build.py

# 1) 一条命令：抓 SRAM → 解码 → 逐字节 diff → 字段级差异表（跑两遍并断言一致）
python tools/s49_save_boundary/run_all.py --repeat 2

# 2) 只重跑对比（不重抓）
python tools/s49_save_boundary/compare_save_images.py

# 3) 逆向线独立验证器交叉验我的镜像（交叉验证用，退出码 0）
$env:PYTHONUTF8='1'
python D:\Shell\Github\gba-naruto-reverse\tools\verify_save_state_records.py `
    --bank D:\Shell\Github\gba-naruto-reverse\sequel\content\save-state\bank.json `
    --sram-dump build\s49-save-boundary\sram\original-walk-a02041dc\original-pre-battle.sav --json

# 4) 出包门禁（无窗口无声）
python tools/mgba_probe/verify_headless_recording.py

# 5) 判定台（私有输出路径，W2/W1 也在跑）
python tools/s49_fidelity_report.py --out build/s49-report/report-w4.json
```

退出码：`run_all.py` 0 = 全部通过 / 2 = 缺输入 / 3 = 两次跑不一致。

---

## 11. 确认

* 新写文件一律 **LF、无 BOM**（`tools/s49_save_boundary/*.py`、本文件）。
* **未提交 git**（master 仓与重制线都没 `git commit` / `git push`）。
* **未改 `battle_runtime_scene.cpp`**；**未改** `battle_range_ui_style.h` /
  `battle_audio_*.h` / `battle_unit_*.h` / `battle_visual_resource_coordinator.h`；
  **未改** `battle_campaign_sram.cpp` / `.h`（取证结论是不需要改，施工单见 §5.5）；
  逆向线全程只读。
* **未覆盖共享探针** `build/mgba-probe/mgba-probe.exe`（私有探针在 `build/mgba-probe-w4`）。
