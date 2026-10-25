# W1 —— 集成接线 + 构建打通 + AFTER 复测（wave 4 关键路径）

> 2026-10-24 · stream W1
> 独占改动：`D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_runtime_scene.cpp`
> 仪器（本流新建）：`tools/s49_w1/`
> **未改** wave 3 定稿的任何头文件、**未改**逆向线、**未提交 git**。

---

## 0. 一句话结论

> **接线成功、构建打通、三个门禁全部跑出数字**：
> ① 描边调色板流 + 门控 idle 时钟接上后，**重制侧每帧描边色真的会变**
> （描边色级数 **1 → 11**，连续相同帧对 **3 → 0**，静止帧门禁 **exit 1 → exit 0**）；
> ② 逐格族名对拍的 **AFTER 数字首次测出**（G-H14 关闭）；
> ③ **G-H15 用原版「目标选择阶段」实机帧定论**：原版在目标选择阶段画**绿 `hatch_shift`
> 压住橙 `line_alt`**，而且**完全不画青 `hatch`**；移动阶段则**完全不画绿**
> ⇒ **原版的「移动集」和「目标集」从不同时出现在屏幕上**，
> 所以那 30 处「原版青 / 重制绿」根本不是优先级问题，而是**重制侧在移动阶段就画了目标集**；
> **当前树里这 30 处已经归零**（实测 `hatch → hatch_shift` 转换 **0** 处）。
> ⚠️ 判定台残差：**任务书列的每一个指标完全不变**（min 0 / 中位 1940 / max 27325 / 全 0 帧 3；
> 一致 3 · 产品差 14 · 配对差 8），但**残差总和 +392 px（+0.23 %）**——
> 这 392 px 全部是单位描边像素（像素差 bbox 落在单位轮廓上），
> 原因是**重制侧的描边相位与原版没有建立对应**（见 §6 台账 W1-11）。

---

## 1. 改动的文件

| 路径 | 性质 | 改动 |
|---|---|---|
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_runtime_scene.cpp` | **改（独占）** | H2 调色板流 6-0…6-4 + 门控 idle 时钟 + L 的 3 行音频调用点 |
| `D:\Github\gba-naruto\tools\s49_w1\capture_remake_vram.py` | **新** | 重制侧 VRAM 逐帧抓取（逐格族名对拍的输入） |
| `D:\Github\gba-naruto\tools\s49_w1\capture_original_state.py` | **新** | 原版任意存档态的 BG2/VRAM/IO 抓取（G-H15 的取证） |
| `D:\Github\gba-naruto\tools\s49_w1\overlay_transitions.py` | **新** | 逐格族名转换的**完整**直方图（官方工具只留前 64 条） |
| `D:\Github\gba-naruto\tools\s49_w1\smoke_4096.py` | **新** | 4096 帧无窗口冒烟测试 + 崩溃标记检测 |
| `D:\Github\gba-naruto\notes\s49-fidelity\W1-integration.md` | **新** | 本报告 |

⛔ **没有改**：`battle_unit_palette_stream.h` / `battle_audio_event_trace.h` /
`battle_range_ui_style.h` / `battle_audio_director.h` / `battle_audio_runtime.h` /
`battle_unit_visual_animation.h` / `battle_visual_resource_coordinator.h` /
`battle_runtime_scene.h` / `tools/s49_fidelity_report.py` /
`tools/s49_overlay_align/` / `tools/s49_audio_probe/` / `tools/s49_rule_probe/` /
`tools/s49_victory_capture/` / 逆向线 `D:\Shell\Github\gba-naruto-reverse`。

---

## 2. (a) 构建与冒烟

### 2.1 构建

```powershell
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"
```

| 项 | BEFORE（接线前） | AFTER（接线后） |
|---|---|---|
| `make -j4` | **通过**（`ROM fixed!`，只有 warning） | **通过**（`ROM fixed!`，只有 warning） |
| ROM 路径 | `D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba` | 同左 |
| ROM sha256 | `804dd79384a96a2cc90a44e528277576992868343c087a64d37a27851696eb1d` | **`2de28f164f04de85672d031d4d0bc29e689ff6da7acba82c1ce38678908b98a5`** |
| ROM 字节数 | 11 883 256 | 11 884 684 |

⇒ **构建这一项本来就是绿的**（wave 3 遗留的构建挂已经被别的流修掉）；
本流的工作是**在接上 H2/L 之后仍然保持绿**。

### 2.2 4096 帧冒烟（无窗口探针）

```powershell
python tools/s49_w1/smoke_4096.py --out build/s49-w1/smoke
```

| 跑法 | 帧数 | probe exit | 崩溃行（`Jumped to invalid address` / `Illegal opcode` / `BN_ERROR`） |
|---|---:|---:|---:|
| boot（无输入） | 4096 | 0 | **0** |
| walk（`Down,Down,A ×32`） | 240 + 34×94 | 0 | **0** |

⇒ **不崩**。
中文标题画面正常：`build/s49-w1/smoke/boot-title.png` 显示
「**保护木叶丸不被蜂攻击！**」（S49 标题，中文渲染正确）。

### 2.3 音频运行时回归（用 L 的 trace 工具，只读复用）

```
python tools/s49_audio_l/capture_remake_trace.py --out build/s49-w1/audio-trace ...
→ trace events: 24
   f 15 music 5 / f 884 music 5 / f 1829 sound 126 / f 1829 music 10
   f 1916..2762 sound 102 ×9 / f 2762..3326 sound 105 ×11
```

⇒ 与 L 流的 24 条基线**逐条相同** ⇒ 本流的音频改动**没有回归**。

---

## 3. (b) H2 调色板流的接线

### 3.1 照 H2 §6 的清单逐条落地

| H2 清单 | 落地位置 | 说明 |
|---|---|---|
| **6-0** 每单位一份运行时 OBJ 调色板 | `battle_runtime_scene.cpp:6569` `unit_palette_slot()` | 从单位自己的 `item->palette_item()` **new** 一份（`create_new_palette()`），不用共享 item |
| **6-1** 每帧写描边色 | `battle_runtime_scene.cpp:6883-6902` | `battle_unit_palette_write_for_frame(unit.id, idle_clock.frames(), scene_frame)` → `set_color(outline.color_index, bn::color(r,g,b))` |
| **6-2** 时钟来源换门控时钟 | `battle_runtime_scene.cpp:6197-6211` + `6624-6627` | `unit_visual_sample()` 的 `scene_frame & 0x7FFFFFFFU` → `idle_frame`（`:6211`）；`update_unit_sprites()`（`:6624`）多收 `const battle_unit_idle_clock&` |
| **6-3** 门控时钟的存放与推进 | 部署场景 `:7258` / 战斗场景 `:7568` | `battle_unit_idle_clock idle_clock;` 与 `scene_frame` 同处、**同源从 0 起算**；`idle_clock.advance(...)` 紧挨 `++scene_frame`（`:7372` / `:8255`） |
| **6-4** 只给行动中的单位写描边色 | `battle_runtime_scene.cpp:6902` `else if(acting_unit)` | 见 §3.2 |

### 3.2 三个坑的处理（逐条对照任务书）

| 坑 | 处理 |
|---|---|
| `bn::color` 收 **5 bit 分量**，**不要乘 8** | `outline.color.green` 直接传（模块给的就是 5 bit 值）。**没有**乘 8 |
| 槽位用 `color_index`(=15)，不是 `palette_index` | `set_color(outline.color_index, …)` |
| `\|\| binding_changed` **不可省** | 写成 `if(outline.valid \|\| palette_content_changed \|\| ! sprite_state.outline_palette)`；`palette_content_changed` 覆盖「重新绑定 + 换了 sprite item」两种会把槽位 15 复位的情况 |
| 原版只有**未被灰度**的那个单位在动 | 描边色**只写给 `acting_unit`**（`state.selected_unit == unit.id`）。其余单位继续用共享的 `item->palette_item()`（槽位 15 保持静态色 1），⇒ 残差里不会出现「另一个单位也在动」 |
| 灰度单位用的是**共享** `dimmed_unit_palette()` | 描边色**不写进**那份共享调色板（`dimmed` 分支直接 `set_palette(dimmed_unit_palette())`） |

### 3.3 ⚠️ 一处**有意**的偏离（必须交代）：「每单位一份」→ 「行动单位一份」

H2 §6-0 的字面要求是「每单位一份运行时 OBJ 调色板」。
**实测 Butano 的硬件限制**：`third_party/butano/butano/src/bn_palettes_bank.h:256`
的 `palette _palettes[hw::palettes::count()]` —— **硬件只有 16 个 sprite 调色板 bank**，
`create_bpp_4()` 找不到空位就 `BN_ERROR("There are no more available colors.")` 直接挂。

⇒ 若真的给 9~12 个单位各留一份常驻调色板，和场景里已有的 UI 调色板（字体 / 面板 /
提示 / 对白 / 结果页 …）相加会**越过 16 个 bank 的上限 ⇒ ROM 崩**。

⇒ 本流的做法：**运行时调色板跟着「行动中的单位」走**——
行动的单位拿到自己的副本，单位不再行动时**立刻归还**（`palette_slot.reset()`），
所以常驻的运行时调色板**最多 1 份**。
这同时满足 H2 §6-4 的语义（只有行动的单位在动），
而且**不影响判据**：非行动单位的槽位 15 仍是它自己的静态色 ⇒ 渲染结果与改动前逐像素相同。

**验证**：4096 帧冒烟 + 34 步走位全程 **0 条崩溃行**，且 walk 期间渲染正常
（逐格族名对拍、判定台、静止帧门禁三张收据都拿到了数字）。

### 3.4 门控表（`battle_unit_idle_gate_state_for`）

| 场景状态 | 门 | 依据 |
|---|---|---|
| 地图/移动/敌回合等（无菜单） | `field_idle`（**推进**） | H2 §1.2 实测项 |
| 命令菜单 / 行动菜单 / 目标选择 / 确认 / 防御菜单 / 结果页 | `command_menu`（**推进**） | H2 §1.2 实测项 |
| 演出中（`presentation.busy()`） | `combat_presentation`（**暂停**） | H2 §1.2 未实测项 |
| 回合计（`turn_banner`） | `banner`（**暂停**） | H2 §1.2 未实测项 |
| 脚本对白（`script_blocked`） | `dialogue`（**暂停**） | H2 §1.2 未实测项 |

⚠️ 后三项是 H2 的**机制**不是**测量**（H2 台账 H2-6），本流照抄。
⇒ 一旦门停过，`state_frame != scene_frame`，模块就**一律报写**（H2 §1.3 的「安全但退化」分支），
功能正确，只是少了「跳过平点那一次写」的优化。

---

## 4. (c) L 的 3 行调用点

| cue | 事件 | 调用点 | 触发条件 |
|---:|---|---|---|
| **8** | `battle_audio_event::postbattle_dialogue_opened` | `battle_runtime_scene.cpp:8093`（战斗场景 `state.phase == complete` 的**交接处**，边沿触发） | 原版战后对白场景有自己的 BGM；重制侧还没有独立的对白页 ⇒ 打在「战斗交给战役流程」的那一刻 |
| **146** | `battle_audio_event::tool_group17_activated` | `battle_runtime_scene.cpp:267` `dispatch_battlefield_object_audio()`（`:246` 定义），由 `:8248` 在**演出第 0 帧**调用 | 忍具的战场物件 `type_1_due`（到期生效）且其 payload（忍具 id）属于原版「组 17」。原版 cue 普查把这个状态命名为 `scenario-49-battle-14-tool37-group17-active.ss9` ⇒ **组 17 的忍具 id = 37**（`battle_ninja_tool_is_group17()`） |
| **152** | `battle_audio_event::tool_expiry_reached` | 同上，`:273` 的 `type_2_expired` 分支 | 忍具效果到期（对应 `update_battlefield_object_expiry_sprite()` 画的那段到期演出） |

**口径诚实说明**：这三个时刻 **S49 的 `Down,Down,A ×32` 走位都到不了**
⇒ 它们**有调用点、有运行时派发路径，但没有本次采集的运行时证据**。
本次采集的 trace 仍是 24 条（与 L 的基线逐条相同），**没有多出**这三条
—— 这既证明没误触发，也证明没被触达。

---

## 5. (d) G-H15：30 处「原版青 / 重制绿」的定论

### 5.1 取证方法（不猜）

用**原版自己的目标选择阶段存档态**实机抓帧：

```powershell
python tools/s49_w1/capture_original_state.py `
  --state D:/Shell/Github/gba-naruto-butano/artifacts/runtime-checkpoints/scenario-41-target-select.ss9 `
  --out build/s49-w1/original-target-select
```

抓到的三块：BG2/BG3 tilemap（`0x06001000`）、整块 VRAM（`0x06000000`）、
IO 寄存器（`0x04000000`）。
解码用的是 G 的只读解码器（`tools/s49_rule_probe/overlay_ground_truth.py` 的
`TILE_FAMILY`：256-281 → blank/edge/hatch/line_alt/band/hatch_shift/solid）。

### 5.2 原版目标选择帧的族直方图（1024 个 tilemap 项）

| 族 | 项数 | 含义 |
|---|---:|---|
| `edge` | 291 | 可走格边框 |
| `blank` | 173 | 空 |
| `solid` | 8 | 受阻（1 个战斗格） |
| `line_alt` | 32 | **橙：攻击范围** |
| **`hatch_shift`** | **8** | **绿：合法目标**（1 个战斗格 = 2 逻辑列 × 2 逻辑行） |
| **`hatch`（青）** | **0** | **移动可达区：一张都没有** |

### 5.3 三条由此得出的事实

1. **原版的绿 = 合法目标，且压在橙上面。**
   绿块（tilemap col 24-27 × row 24-25）被橙块（col 20-31 × row 22-27）包着，
   绿所在的位置橙被**替换**掉了 ⇒ **优先级 `target > attack`**（与 F 的书面顺序一致）。
2. **原版在目标选择阶段完全不画青（移动可达区）。**
3. **原版在移动阶段完全不画绿。**
   G 报告的四个导出时刻（field / movegrid / grid16 / banner）里 **`hatch_shift` 出现 0 次**
   ⇒ 移动阶段目标集根本没有激活。

⇒ **原版的「移动集」和「目标集」从不同时出现在屏幕上。**
⇒ **那 30 处「原版青 / 重制绿」根本不是 `move > target` 还是 `target > move` 的优先级问题**，
而是**重制侧在移动阶段就画了自己的目标集（绿）**，而原版那个时刻画的是移动集（青）。

### 5.4 当前树里这 30 处已经归零（实测）

用 `tools/s49_w1/overlay_transitions.py`（完整直方图，官方工具只留前 64 条差异）：

| 树 | 帧 | 偏移 | `hatch → hatch_shift` | 其它主要转换 |
|---|---|---|---:|---|
| **G 改动前**（`build/s49-overlay-g/remake`） | step-23-A | [2,0] | **42** | `blank→solid 22`, `solid→edge 18`, `edge→blank 11`, `hatch→band 2`, `hatch→line_alt 2`, `solid→hatch_shift 4` |
| **G 改动后（= 本流 BEFORE）** | step-23-A | [0,0] | **0** | `blank→solid 20`, `solid→blank 49`, `edge→blank 31`, `hatch→blank 22`, `hatch→band 2` |
| **本流 AFTER** | step-20-A | [0,0] | **0** | 同上 |

⇒ **G-H15 关闭**：差异是「G 改动前重制侧在移动阶段画了目标集」造成的；
G 的族判定顺序 + 地图空间锚定已经把这件事消掉了。
**本流的接线没有碰覆盖层，所以 BEFORE / AFTER 的逐格数字完全相同。**

---

## 6. 三个门禁的数字

### 6.1 门禁①逐格族名对拍（G 的 #14 未验项 → 关闭）

```powershell
python tools/s49_overlay_align/scan_remake_frames.py --vram-dir build/s49-w1/vram-after --out build/s49-w1/scan-after.json
```

**AFTER 数字（本流交付，G-H14 关闭）**

| 原版时刻 | 最佳重制帧 | 偏移 | 同亮 | 原版有·重制缺 | 重制多画 | 族名不一致 |
|---|---|---|---:|---:|---:|---:|
| `field-frame-v1` | `step-00-base` | [0,0] | 192 | 0 | 64 | 102 |
| **`movegrid-frame-v1`** | `step-00-base` | [0,0] | **192** | **0** | **64** | **129** |
| `grid16-frame-v1` | `step-00-base` | [0,0] | 175 | 0 | 81 | 68 |
| `banner-frame-v1` | `step-22-A` | [0,0] | 0 | 0 | 0 | **0（逐格全等）** |

**同一时刻自己的帧（`step-20-A`，movegrid 那一帧）**：同亮 **90** · 原版缺 **102** ·
多画 **40** · 族名不一致 **32**（偏移 [0,0]）。

**前后对比（本流接线前 → 后）**

| 帧 | 口径 | 前 | 后 | 变化 |
|---|---|---:|---:|---|
| step-20-A | 同亮 / 缺 / 多画 / 不一致 | 90 / 102 / 40 / 32 | 90 / 102 / 40 / 32 | **完全相同**（本流不碰覆盖层） |
| step-23-A | 同亮 / 缺 / 多画 / 不一致 | 90 / 102 / 40 / 44 | 90 / 102 / 40 / 44 | **完全相同** |
| 全扫最佳帧 | movegrid | 192 / 0 / 64 / 129 | 192 / 0 / 64 / 129 | **完全相同** |

**与 G 报告基线的对比（⚠️ 有出入，必须交代）**

| 来源 | 帧 | 偏移 | 同亮 | 原版缺 | 多画 | 族名不一致 |
|---|---|---|---:|---:|---:|---:|
| G 报告文字（改动前） | step-20-A | [2,0] | 168 | 24 | 42 | **24** |
| **G 自己的 `scan.json`** | step-20-A | [0,5] | 136 | 56 | 12 | **124** |
| **G 自己的 `scan.json`** | step-23-A | [2,0] | 168 | 24 | 42 | **68** |
| 本流 AFTER（= G 改动后） | step-20-A | [0,0] | 90 | 102 | 40 | 32 |
| 本流 AFTER（= G 改动后） | step-23-A | [0,0] | 90 | 102 | 40 | 44 |

⚠️ **任务书给的基线「同亮 168 · 原版缺 24 · 多画 42 · 族名不一致 24」是把两个数字混在了一起**：
`168 / 24 / 42` 来自 **step-23-A**，而 step-23-A 的族名不一致是 **68**（不是 24）；
那个 **24** 其实是 step-23-A 的「原版有·重制缺」。
用 G 自己的 `build/s49-overlay-g/scan.json` 复算**逐值对得上**（本流已复现），
⇒ **G 报告 §5.1 表格的最后一列写错了**（把 step-20-A 的 24 和 step-23-A 的 68 对调了）。

⚠️ **另一条必须交代的事实**：G 的「地图空间锚定」改动落地后，
逐格口径**同亮从 136/168 掉到 90、原版缺从 56/24 涨到 102**，
只有**族名不一致**从 124/68 降到 32/44。
⇒ **族名更对了，但覆盖面变差了**（原版画了的 102 格重制侧没画）。
这是 G 流的地盘，本流只如实报数，**没有改动** `battle_range_ui_style.h`。

### 6.2 门禁②判定台残差（棘轮）

```powershell
python tools/s49_fidelity_report.py --out build/s49-report/report-w1-after.json --work-dir build/s49-report/w1-after
# BEFORE 用同一版工具、复用同一批采集重跑（可比）：
python tools/s49_fidelity_report.py --out build/s49-report/report-w1-before-v2.json --work-dir build/s49-report/w1-before --skip-capture
```

> ⚠️ **踩到的坑**：W2 流在本流进行期间升级了 `tools/s49_fidelity_report.py`
> （新增 `pairing_diff_subclasses` / `overlay_residual` / `pairing_quality`）。
> 最开始我跑的 BEFORE（`report-w1-before.json`，`content_sha d6980bca…`）是**旧工具**，
> AFTER（`content_sha 041c756e…`）是**新工具** ⇒ 两者不可比。
> ⇒ 改成用**同一版工具**、复用 BEFORE 的采集重跑（`report-w1-before-v2.json`，
> `content_sha 6543bb3f…`），下面所有数字都是这一对。

| 指标 | BEFORE | AFTER | 结论 |
|---|---:|---:|---|
| 战场区残差 min | 0 | 0 | **不变** |
| 战场区残差 中位 | 1940 | 1940 | **不变** |
| 战场区残差 max | 27325 | 27325 | **不变** |
| 全 0 帧 | 3 / 25 | 3 / 25 | **不变** |
| 归因 一致 | 3 | 3 | **不变** |
| 归因 产品差 | 14 | 14 | **不变** |
| 归因 配对差 | 8 | 8 | **不变** |
| 覆盖层残差 sum / max | 1060 / 187 | 1060 / 187 | **不变**（本流不碰覆盖层） |
| 配对质量 | 6/25 | 6/25 | 不变 |
| **战场区残差 sum** | **167 965** | **168 357** | **+392 px（+0.23 %）** ⚠️ |
| **整屏残差 sum** | **281 299** | **281 691** | **+392 px** ⚠️ |

**逐帧前后对比表**（Δ = AFTER − BEFORE，战场区 px）

| 原版帧 | 最佳重制帧 | 前 field px | 后 field px | Δ | 前归因 | 后归因 |
|---|---|---:|---:|---:|---|---|
| `step-00-base` | `step-04-A` | 2565 | 2565 | 0 | product_diff | product_diff |
| `step-01-A` | `step-05-A` | 1294 | 1294 | 0 | product_diff | product_diff |
| `step-02-A` | `step-06-A` | 1680 | 1680 | 0 | product_diff | product_diff |
| `step-03-A` | `step-07-A` | 2514 | 2514 | 0 | product_diff | product_diff |
| `step-04-A` | `step-08-A` | 1940 | 1940 | 0 | product_diff | product_diff |
| `step-05-A` | `step-09-A` | 2057 | 2057 | 0 | product_diff | product_diff |
| `step-06-A` | `step-10-A` | 1217 | 1217 | 0 | product_diff | product_diff |
| `step-07-A` | `step-11-A` | 1921 | 1921 | 0 | product_diff | product_diff |
| `step-08-A` | `step-12-A` | 1026 | 1026 | 0 | product_diff | product_diff |
| `step-09-A` | `step-12-A` | 6064 | 6064 | 0 | pairing_diff | pairing_diff |
| `step-10-A` | `step-12-A` | 4990 | 4990 | 0 | pairing_diff | pairing_diff |
| `step-11-A` | `step-16-A` | 25447 | 25447 | 0 | pairing_diff | pairing_diff |
| `step-12-A` | `step-16-A` | 9907 | 9907 | 0 | pairing_diff | pairing_diff |
| `step-13-A` | `step-14-A` | 28 | 28 | 0 | product_diff | product_diff |
| `step-14-A` | `step-14-A` | 0 | 0 | 0 | identical | identical |
| `step-15-A` | `step-15-A` | 0 | 0 | 0 | identical | identical |
| `step-16-A` | `step-16-A` | 344 | 344 | 0 | product_diff | product_diff |
| `step-17-A` | `step-16-A` | 0 | 0 | 0 | identical | identical |
| `step-18-A` | `step-16-A` | 25459 | 25459 | 0 | pairing_diff | pairing_diff |
| `step-19-A` | `step-17-A` | 24461 | 24460 | **−1** | pairing_diff | pairing_diff |
| `step-20-A` | `step-17-A` | 4014 | 4158 | **+144** | product_diff | product_diff |
| `step-21-A` | `step-11-A` | 27325 | 27325 | 0 | pairing_diff | pairing_diff |
| `step-22-A` | `step-07-A` | 21266 | 21266 | 0 | pairing_diff | pairing_diff |
| `step-23-A` | `step-18-A` | 1323 | 1323 | 0 | product_diff | product_diff |
| `step-24-A` | `step-19-A` | 1123 | 1372 | **+249** | product_diff | product_diff |

**那 +392 px 是什么？**（已定位，不是猜测）
重制侧 BEFORE/AFTER 的逐帧 PNG 像素差：

| 帧 | 变化像素数（战场区） | 变化 bbox |
|---|---:|---|
| `step-19-A` | 1056 | (82, 32, 143, 98) |
| `step-20-A` | 125 | (117, 34, 142, 86) |
| `step-24-A` | 134 | (117, 34, 142, 86) |
| `step-30-A` | 324 | (109, 34, 145, 89) |

⇒ 变化**全部落在单位的描边轮廓上**（x≈109-145 / y≈32-98 就是单位所在的位置）。
⇒ 残差变大是因为**描边现在会动了，而重制侧的描边相位与原版没有建立对应**（台账 W1-11）。

### 6.3 门禁③静止帧（用 H2 收紧后的判据）

```powershell
python tools/s49_idle_frame_repeat.py \
  --original build/s49-report/w1-after/capture-original \
  --remake   build/s49-report/w1-after/capture-remake \
  --out build/s49-idle/frame-repeat-w1-after.json
```

| | BEFORE | AFTER |
|---|---:|---:|
| 原版连续相同帧对 / 异常对 | 0 / 0 | 0 / 0 |
| **重制侧连续相同帧对** | **3** | **0** |
| **重制侧异常对** | **3** | **0** |
| 重制侧描边色级数（5 bit） | `[1]` | **`[1,3,5,7,13,15,17,19,23,29,31]`** |
| 描边波是否在动 | `false` | **`true`** |
| **退出码** | **1（FAIL）** | **0（PASS，OK: every repeated frame is a wave flat spot）** |

⇒ **门禁③通过**。原来那 3 对（`24-25` / `30-31` / `32-33`）**全部消失**。

---

## 7. 单元测试

```bash
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh
# 逐个 g++ -std=c++23 -Wall -Wextra -Werror -pedantic -I game/include game/tests/test_*.cpp
```

| 范围 | 结果 |
|---|---|
| **本流接线直接相关的 7 个**（`test_battle_unit_palette_stream` / `_unit_visual_animation` / `_visual_resource_coordinator` / `_range_ui_style` / `_range_ui_original_alignment` / `_audio_director` / `_ui_model`） | **7/7 PASS** |
| `game/tests/` 全量（123 个） | **103 PASS / 20 FAIL** |

⚠️ **那 20 个失败不是本流造成的**，证据：
1. 本流**只改了 `battle_runtime_scene.cpp` 一个 `.cpp`**；
2. 这 20 个测试都是**主机侧头文件测试**，只 `#include` 头文件
   （`battle_runtime_scene.h` / `battle_scene_controller.h` / …），**不编译 `battle_runtime_scene.cpp`**；
3. `git status` 显示 `battle_runtime_scene.h` **未被本流改动**；
4. 失败内容全是**别的流在途改动**造成的样子：
   `sizeof(battle_scene_snapshot<12>)` 变成 1672（门禁要求 ≤ 1120）、
   `sizeof(battle_runtime_scene_telemetry)` 变成 868（门禁要求 == 824）、
   以及一批 `controller.tick().success()` / `move_cursor(...).success()` 的相位断言。

⇒ **这些失败是共享树当前的既有状态，本流无法在只改一个 `.cpp` 的前提下修掉。**
⚠️ 也就是说「单测全绿」这条验收在**当前共享树上不成立**，本流把它如实记下来。

---

## 8. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **W1-1** | wave 3 遗留的构建挂已经修好，接线后仍能绿 | `make -j4`（WSL） | `ROM fixed!`，只有 warning；ROM sha `2de28f16…` | **已确认** |
| **W1-2** | 接线后的 ROM 跑完 4096 帧不崩 | `tools/s49_w1/smoke_4096.py`（boot + walk 两条） | 0 条崩溃行，probe exit 0 | **已确认** |
| **W1-3** | 中文标题画面正常 | 读 `build/s49-w1/smoke/boot-title.png` | 「保护木叶丸不被蜂攻击！」渲染正确 | **已确认** |
| **W1-4** | `item->palette_item()` 会被同角色的其它单位共享，所以描边色不能写进去 | 读 butano `sprite_ptr::set_palette(sprite_palette_item)` → `find_palette()` 按颜色复用 | 确认共享 ⇒ 必须用运行时副本 | **已确认** |
| **W1-5** | 一个单位的多个 body part 共享同一份 16 色 | 解 62 个单位 slot 的图砖调色板 | 同一 slot 的 part_0/1/2 调色板**逐字节相同** ⇒ **一单位一调色板**成立 | **已确认** |
| **W1-6** | Butano 只有 16 个硬件 sprite 调色板 bank，给每个单位常驻一份会崩 | 读 `bn_palettes_bank.h:256` + `create_bpp_4()` 的 `BN_ERROR` 分支 | 16 个上限确认 ⇒ **改成「行动单位一份、用完归还」** | **已确认** |
| **W1-7** | 门控时钟与 `scene_frame` 同源起算 ⇒ 模块能识别「平点」并跳过那一次写 | 两处都从 0 起算，`advance()` 紧挨 `++scene_frame` | 是 ⇒ 门禁③从 3 对降到 0 对 | **已确认** |
| **W1-8** | 原版的目标选择阶段用绿（`hatch_shift`）画合法目标 | 抓 `scenario-41-target-select.ss9` 的 BG3 tilemap 并按 `TILE_FAMILY` 解码 | `hatch_shift` 8 项、`line_alt` 32 项、**`hatch` 0 项** | **已确认** |
| **W1-9** | 原版的绿**压**橙（target > attack） | 看目标选择帧里绿块与橙块的相对位置 | 绿块（col 24-27 × row 24-25）**替换**了橙块 ⇒ target > attack | **已确认** |
| **W1-10** | 原版在移动阶段不画绿、在目标阶段不画青 ⇒ 两集从不同屏 ⇒ 30 处差异不是优先级问题 | 四个导出时刻 `hatch_shift` 计数 0；目标选择帧 `hatch` 计数 0 | 两个「从不出现」都成立 ⇒ **G-H15 关闭** | **已确认** |
| **W1-11** | 重制侧描边相位与原版存在一个**常数**偏移，可以调出来让残差下降 | 用 `s49_idle_outline_colours.py` 取两侧逐帧描边色，按报告的配对把 shade 反解成相位，求三对公共偏移 | 三对的候选偏移集合交集为**空** ⇒ **不存在常数偏移**（配对质量只有 6/25） | **已证伪** |
| **W1-12** | 接线后残差只会变小 | 判定台逐帧对比 | 任务书列的 7 个指标**全部不变**；**sum +392 px（+0.23 %）**，全部是描边像素 | **部分成立**（见 §6.2） |
| **W1-13** | 逐格族名对拍的 AFTER 数字可以复现 | 用 G 自己的 `build/s49-overlay-g/scan.json` 复算 | 逐值复现 ⇒ 发现 **G 报告 §5.1 的最后一列写错了**（24 实为 orig-only，step-23-A 的 mismatch 是 68） | **已确认（并纠正上游）** |
| **W1-14** | cue 8 / 146 / 152 的调用点能在 S49 走位里被触达 | 跑 L 的 trace 采集 | trace 仍是 24 条 ⇒ **都到不了**（有调用点，无运行时证据） | **未验**（走位不够，非缺陷） |
| **W1-15** | 20 个单测失败是本流造成的 | 失败测试只 include 头文件；`battle_runtime_scene.h` 未被本流改 | 本流只改 `.cpp` ⇒ **与本流无关**（共享树的既有状态） | **已证伪** |

---

## 9. 复现命令清单

```powershell
cd D:\Github\gba-naruto

# (a) 构建
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# (a) 私有探针
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-w1'
python tools/mgba_probe/build.py

# (a) 4096 帧冒烟
python tools/s49_w1/smoke_4096.py --out build/s49-w1/smoke

# 门禁②判定台（BEFORE 用同一版工具复用采集）
python tools/s49_fidelity_report.py --out build/s49-report/report-w1-before-v2.json `
  --work-dir build/s49-report/w1-before --skip-capture
python tools/s49_fidelity_report.py --out build/s49-report/report-w1-after.json `
  --work-dir build/s49-report/w1-after

# 门禁③静止帧
python tools/s49_idle_frame_repeat.py --original build/s49-report/w1-after/capture-original `
  --remake build/s49-report/w1-after/capture-remake --out build/s49-idle/frame-repeat-w1-after.json

# 门禁①逐格族名
python tools/s49_w1/capture_remake_vram.py --capture-dir build/s49-report/w1-after/capture-remake `
  --out-dir build/s49-w1/vram-after
python tools/s49_overlay_align/scan_remake_frames.py --vram-dir build/s49-w1/vram-after `
  --out build/s49-w1/scan-after.json
python tools/s49_overlay_align/compare_overlay_families.py --vram build/s49-w1/vram-after/step-20-A.vram-0000.bin \
  --moments movegrid-frame-v1 --out build/s49-w1/compare-after-step20.json

# (d) G-H15 取证
python tools/s49_w1/capture_original_state.py --state `
  D:/Shell/Github/gba-naruto-butano/artifacts/runtime-checkpoints/scenario-41-target-select.ss9 `
  --out build/s49-w1/original-target-select
python tools/s49_w1/overlay_transitions.py --vram-dir build/s49-w1/vram-after \
  --moment movegrid-frame-v1 --frame step-20-A.vram-0000.bin

# 单测
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh
```

---

## 10. 卡在哪 / 剩余风险

| # | 事项 | 状态 | 谁来解 |
|---|---|---|---|
| 1 | **残差总和 +392 px（+0.23 %）** | 任务书列的 7 个指标全部不变，但 sum 变大。根因是**描边相位与原版没有对应**（W1-11 证明不存在常数偏移） | 需要**内容锚**级别的配对（W2 流）才能把相位对齐；本流无法在只改一个 `.cpp` 的前提下解决 |
| 2 | **G 的地图空间锚定让覆盖面变差** | 同亮 136/168 → 90、原版缺 56/24 → 102（只有族名不一致 124/68 → 32/44 变好） | **G 流**（`battle_range_ui_style.h` 不在本流权限内）。本流如实报数 |
| 3 | **G 报告 §5.1 的族名不一致数字写错了** | 报告写 24，其自己的 `scan.json` 是 68（24 是 orig-only）。本流已复现并纠正 | 回填上游报告（父代理） |
| 4 | **门控表有 3 项未实测** | `dialogue` / `banner` / `unit_presentation` / `combat_presentation` 按「不推进」处理（H2-6） | 需要原版在这些状态下的实机帧 |
| 5 | **cue 8 / 146 / 152 没有运行时证据** | S49 走位到不了这三个时刻 | 需要更长的走位（K/M 流在做原版路线） |
| 6 | **单测 20 个失败** | 共享树既有状态（别的流在途改头文件），本流改不到 | 各流收工后重跑 |
| 7 | **运行时调色板只给行动单位** | 有意偏离 H2 的「每单位一份」字面（16 bank 上限，见 W1-6） | 已在本报告记录 |
| 8 | **相位偏移 `idle_phase_offset` 仍是未验项** | H2-9 沿用，本流没动 | 需要原版 idle sweep 的相位锚 |

---

## 11. 编码检查

本流新建/改动的 6 个文件全部 **LF、无 BOM**（`crlf=0`、`bom=False`）✓
**没有提交 git**（两棵树都只有工作区改动）✓
