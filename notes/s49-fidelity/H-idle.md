# H — idle 节奏与相位

**stream**：H（idle 节奏与相位）
**日期**：2026-10-24
**任务**：`notes/s49-fidelity/WAVE2-TASKS.md` §3
**独占文件**：`butano-sequel/game/include/konoha/battle_unit_visual_animation.h`、
`butano-sequel/game/include/konoha/battle_scene_controller.h`（本流实测该文件**没有任何 idle 相关段落**，
`idle`/`visual`/`sprite`/`palette` 关键词命中数均为 **0** ⇒ 无可改之处）、
`notes/s49-fidelity/H-idle.md`、`tools/s49_idle_cadence.py`、`tools/s49_idle_outline_wave.py`、
`build/s49-idle/`

---

## 0. 一句话结论

> **「重制侧 32 帧周期只有 3 张图」的根因不是图集、不是状态机、不是相位，而是重制侧只实现了 ROM 的
> *帧序表*，没有实现 ROM 的 *逐帧调色板改写*。**
> 原版每个 GBA 帧都重写一次单位 OBJ 调色板 index 15（1 px 描边，32 帧三角波），所以它一个周期显示
> **32 张**不同的图；重制侧的描边色是死的 `(0,8,8)`，所以只有 **3 张**。
> **姿态节奏两侧已经完全一致**（每 8 GBA 帧换一次姿态、帧序 9→10→11→10、周期 32）——**这一项不需要改**。
> 而「idle 相位差 1 帧」**在本机是反的**（原版 011 / 重制 010，macOS 记录是原版 010 / 重制 011），
> 且用精确仪器量出来**相位差在相邻配对点不重叠 ⇒ 常量偏移在数学上不可能成立**（第 26 轮的结论在本机复现）。

---

## 1. 最重要的发现：「本机模拟器慢一倍」是**采集重复**，不是模拟器慢

`docs/s49-three-day-plan.md`、`BRIEF.md` §2、`WAVE2-TASKS.md` §3 都把
「本机模拟器把游戏动画推进放慢了一倍（PRAM 每 2 帧改一次调色板）」当成事实，并据此要求
「一律按相对节奏判」。**这条前提是错的。**

### 1.1 实测

探针（`tools/mgba_probe/host_main.c`）的帧推进是 `core->runFrame()` **一次 = 一个 GBA 帧**，
但它的 Lua "frame" 回调被触发**两次**（mGBA 内部的帧事件 + 探针在 `runFrame()` 之后补发的
`_scriptFireFrame()`），所以采集脚本每张 GBA 帧写了两遍 PNG：

```powershell
python - <<'PY'
from pathlib import Path; from PIL import Image; import hashlib
d = Path(r"D:\Github\gba-naruto\build\s49-logic\original-idle-sweep")
h = [hashlib.sha256(Image.open(p).convert("RGB").tobytes()).hexdigest()
     for p in sorted(d.glob("frame-*.png"))[:24]]
print("identical even/odd pairs:",
      sum(1 for i in range(0, 23, 2) if h[i] == h[i+1]), "of 12")
PY
```

| 录像 | 偶/奇相邻帧**逐字节相同**的对数 |
|---|---|
| 原版 idle sweep（`build/s49-logic/original-idle-sweep`，前 24 帧） | **12 / 12** |
| 重制侧 field sweep（`build/s49-idle/remake-field-sweep`，200 帧） | **100 / 100** |
| 重制侧 dialogue sweep（`build/s49-idle/remake-idle-sweep`，200 帧） | **100 / 100** |

⇒ **2 张采集帧 = 1 个 GBA 帧。**

### 1.2 后果：macOS 与本机的数字本来就能直接换算

| 量 | macOS（1:1 采集） | 本机（2:1 采集） | 换算后 |
|---|---|---|---|
| 帧间变化次数 | 183 / 191 | 96 / 199 | 本机 96 ≈ macOS 96（每 GBA 帧算一次） |
| 32 帧内不同图像数 | 30 | 16 | 本机 16 张 = **16 个 GBA 帧**；macOS 30 张 = 30 个 GBA 帧 ⇒ **每 GBA 帧换一次** |

⇒ **两边其实是同一件事**；本机只是把每张画面写了两遍。
⇒ 「绝对计数不能跨模拟器比」这条顾虑因此**不成立**（对本项而言）：只要把本机的采集帧数 ÷2，
两边就能直接比。**本报告后面所有数字都按 GBA 帧给。**

---

## 2. 相对节奏的量化对照（原版 vs 重制）

两侧用**同一台机器、同一套探针、同一份脚本**（`mgba_original_input_frame_sequence.lua`，
record-all 模式，200 帧）采集。

| 量（单位 = GBA 帧） | **原版** | **重制** | 判定 |
|---|---|---|---|
| 姿态每 N 帧换一次 | **8** | **8** | ✅ 一致 |
| 姿态帧序 | 9→10→11→10（ROM `animations[3]`） | 9→10→11→10 | ✅ 一致 |
| 一个 32 帧周期内的不同姿态 | 3 | 3 | ✅ 一致 |
| 描边色（OBJ 调色板 index 15）每 N 帧改写一次 | **1** | **从不**（恒为 `(0,8,8)`） | ❌ **这就是差距** |
| 描边色取值 | `(0,g,g)`，g = 1,3,…,31（16 级，每级一周期出现 2 次） | — | ❌ |
| **一个 32 帧周期内单位显示几张不同图** | **32** | **3** | ❌ |
| 32 张采集帧内画面全图不同图数 | 16 | 5（含另一个单位与覆盖层也在动） | ❌ |
| 画面变化集中在哪个单位 | **只有被选中那个**（变化包围盒 `(109,32,147,91)`） | 两个单位都在动（`(82,32,147,98)`） | ❌ 次要项 |

### 2.1 逐项怎么量的

* **姿态帧号**：用逆向树导出的帧美术在**调色板索引空间**里比对，候选帧必须
  `true mismatch = 0` 才算命中（沿用 `tools/butano/measure_s49_selected_unit_frame.py` 的判据）。
  本机原版 idle sweep **200/200 帧全部命中**，帧序
  `11×6, 10×16, 9×16, 10×16, 11×16, 10×16, 9×16, …`（采集帧；÷2 即 GBA 帧 ⇒ 每姿态 8 帧）。
* **重制侧**同法：field sweep **200/200 命中**，帧序 `10×8, 11×16, 10×16, 9×16, 10×16, 11×16, …`
  ⇒ **与原版同周期、同帧序、同保持时长**。
* **描边色**：从单位自己那 32×64 像素里取形如 `(0,g,g)` 的颜色，反解 5 bit 绿值
  （`(v<<3)|(v>>2)`），再反推三角波的相位。

---

## 3. 描边色波形：已逐帧对原版验证通过

### 3.1 公式（已写进产品代码 `battle_unit_visual_animation.h`）

```
pose_cycle_position = 姿态时钟在 32 帧周期里的位置（0..31）
wave  = (pose_cycle_position + 23) mod 32
step  = clamp(min(wave - 1, 32 - wave), 0, 15)
green = 1 + 2 * step                 # 5 bit 绿，1,3,…,31
```

物理含义：波谷（最暗的 `(0,1,1)`）落在**姿态周期位置 9**；波在 0..15 / 15..0 之间走，
所以 16 级色在一个 32 帧周期里**各出现两次**。

### 3.2 验证（可复跑）

```powershell
python tools/s49_idle_outline_wave.py --out build/s49-idle/outline-wave-check.json
```

实测：**200 / 200 帧一致，0 不一致，退出码 0**（收据 `build/s49-idle/outline-wave-check.json`）。

⇒ **描边波形是姿态周期的纯函数**，不需要第二个时钟 ⇒ 渲染路径只要每帧写一次调色板 index 15 即可。

---

## 4. 相位：为什么「整体平移 N 帧」第二次被证伪（本机实测）

### 4.1 本机锚点与 macOS 记录**方向相反**

| | 原版 | 重制 |
|---|---|---|
| macOS（`notes/s49-selected-unit-idle-phase-20261020.md`，命令菜单打开那一刻） | slot 0 **frame 010** | slot 0 **frame 011** |
| **本机**（命令菜单打开那一刻 = 原版 `step-24-A` ↔ 重制 `step-19-A`，按判定台的内容配对） | slot 0 **frame 011** @ `(112,24)`，`true mismatch = 0` | slot 0 **frame 010** @ `(112,24)`，`true mismatch = 0` |

⇒ **「010 vs 011」不是稳定的产品属性**，它取决于两侧录像各自的帧预算（本机 walk 每步 47 GBA 帧，
macOS 每步 184 GBA 帧），**不是**产品代码里的常量。

### 4.2 精确仪器：描边色可以读出原版在周期里的位置

描边色有 16 级 ⇒ 可以把原版的姿态周期位置定到 **±2 帧**。用它读两个配对点：

| 配对（原版 ↔ 重制） | 原版姿态 | 原版周期位置（由描边色反解） | 重制姿态 | 重制周期位置 | 相位差区间 |
|---|---|---|---|---|---|
| `step-23-A` ↔ `step-18-A` | 9 | **2** | 11 | 16..23 | 重制**超前** 14..21 帧 |
| `step-24-A` ↔ `step-19-A` | 11 | **18** | 10 | 8..15 | 重制**落后** 3..10 帧 |

⇒ 两个区间**不重叠** ⇒ **不存在任何常量偏移能同时满足这两帧** ⇒
**「整体平移 N 帧」这条路在数学上就不成立**（第 26 轮的结论在本机复现，且现在有精确区间而不是定性描述）。

### 4.3 为什么相位关系会漂：原版的 idle 时钟**受场景状态机门控**

两份 walk 脚本（`mgba_original_s49_ui_boundaries.lua` 与 `mgba_boot_input_sequence.lua`）
用的是同一种 "frame" 回调计数 ⇒ 每步的间隔相同（94 次回调 = **47 个 GBA 帧**）。
一个自由的 8 帧一步的时钟，每步应推进 `47 mod 32 = 15` 帧。实测**原版**的推进量：

| walk 步 | 00→01 | 01→02 | 02→03 | … | 22→23 | 23→24 |
|---|---|---|---|---|---|---|
| 原版描边相位推进 | 29 | 6 | 23 | … | 6 | **16** |

⇒ **不是恒定的 15** ⇒ 原版的 idle 时钟**不是自由运行计数器**，它被场景状态机门控
（过场、对话、開始横幅期间不走）。重制侧用的是自由运行的 `scene_frame` ⇒ **两侧的时钟来源不同**。

⇒ **⇒⇒ 要对齐相位，必须改 idle 时钟的「来源」，不能改它的「初相位」。**
而改来源要动 `battle_runtime_scene.cpp` 里那行
`result.elapsed_frames = scene_frame + idle_phase_offset(unit.id);`（`battle_runtime_scene.cpp:6141`），
**那不是本流独占的文件**（见 §7）。

---

## 5. 改了哪些文件

| 路径 | 性质 | 说明 |
|---|---|---|
| `butano-sequel/game/include/konoha/battle_unit_visual_animation.h` | **改** | 新增 `idle_cycle_frames()`（= 32）、`idle_outline_green(int pose_cycle_position)`（§3.1 的波形，已逐帧验证）；把本轮实测写进 `idle_phase_offset()` 的注释（说明常量偏移为何第二次被证伪）。**行为中立**：新增的两个函数当前无人调用 ⇒ 链接后被去重，**ROM 逐字节未变**。 |
| `butano-sequel/game/include/konoha/battle_scene_controller.h` | **未改** | 实测该文件无 idle 相关内容（关键词命中 0），无可改之处。 |
| `notes/s49-fidelity/H-idle.md` | **新增** | 本文件。 |
| `tools/s49_idle_cadence.py` | **新增** | 相对节奏测量器（原版/重制两侧的重复帧数、每窗口不同图数、描边相位与推进量、姿态帧序）。 |
| `tools/s49_idle_outline_wave.py` | **新增** | 波形验证器：把原版 idle sweep 的姿态位置与描边色逐帧对公式，退出码 0 = 一致。 |
| `build/s49-idle/` | 临时产物 | 两份 sweep、接触表、各分析脚本与收据。 |

**没有动** `battle_runtime_scene.cpp`、逆向线、master 仓其他文件。
（`git status --short` 见 §6.4。）

---

## 6. 跑了什么验收

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| H1 | `python tools/s49_idle_outline_wave.py --out build/s49-idle/outline-wave-check.json` | 波形与原版逐帧一致 | **200/200 一致，0 不一致，退出码 0** |
| H2 | `python tools/s49_fidelity_report.py --out build/s49-report/report-h.json --compare build/s49-report/report.json` | 残差不变（棘轮） | `measurement: IDENTICAL`，`content_sha256` 同为 `a5cdf0d8…`；`REPRODUCIBLE: byte-identical`；**退出码 0**；战场区残差 min 0 / 中位 1940 / max 27325 / 全 0 帧 3；归因 一致 3 · 产品差 14 · 配对差 8（与基线逐项相同） |
| H3 | WSL 重建 ROM | 编译通过、ROM 逐字节不变（新增函数是死代码） | 编译通过（只有既有告警）；ROM sha256 仍为 `488a3bc8a44eb4770312be536c34389fdc953790fa7a6cc3ffe07459f3433b94`，与基线报告里记录的一致 |
| H4 | `python tools/s49_idle_cadence.py --compare build/s49-logic/original-idle-sweep build/s49-idle/remake-field-sweep` | 两侧相对节奏可比 | 原版：重复对 100/100（2 采集帧 = 1 GBA 帧）、描边相位每 GBA 帧 +1；重制：重复对 100/100、描边相位恒为 0（无波形） |
| H5 | 文件编码检查 | 新写文件 LF、无 BOM | `battle_unit_visual_animation.h`：0 CRLF、无 BOM；两个新工具 LF、无 BOM |

### 6.1 验收里**没有**达到的那一条（硬性验收的第 1 条）

> **「该帧逐像素 0 px 差」未达成。**

原因不是没做，而是**做不了**：本机锚点帧（原版 `step-24-A` ↔ 重制 `step-19-A`）的残差 **1123 px**，
逐块定位显示它由三部分叠加而成：

| 差异块 | 像素 | 归属 |
|---|---:|---|
| x112..143, y32..95（单位本体） | ≈ 900 | **idle 流**：姿态 011↔010 + 描边色 `(0,140,140)`↔`(0,8,8)` |
| x82..111, y48..95（另一个单位） | ≈ 200 | **idle 流**：重制侧两个单位都在动，原版只动被选中的那个 |
| 其它 | ≈ 20 | 覆盖层 / 状态栏（别的 stream） |

⇒ 即使把 idle 的两件事都修对，这一帧也**不会**到 0 px（另一个单位的差异还在）。
⇒ **「0 px」这一条必须在 idle 两件事都修完、且覆盖层/状态栏也归零之后才可能成立。**

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| H1 | 「本机模拟器把游戏动画推进放慢一倍」 | 比对原版 idle sweep 相邻采集帧的像素哈希 | 偶/奇对 **12/12 逐字节相同**（两份重制 sweep 各 100/100）⇒ 是**采集**写了两遍 | **已证伪** |
| H2 | macOS 的 183/191 与本机的 96/199 是不同的现象 | 把本机的采集帧数 ÷2 后换算 | 本机 96 个 GBA 帧级变化 ≈ macOS 96 ⇒ **同一件事** | **已证伪**（不是环境差异） |
| H3 | 重制侧 32 帧周期只出 3 张图是**图集缺帧** | 数导出目录 `battle_unit_visual_catalog.json` 里 slot 0 的帧数与重制侧实际用到的帧号 | 图集有 20 帧，重制侧用的 9/10/11 **与原版逐项相同** | **已证伪** |
| H4 | 同上，是**状态机跳帧**（跳过了中间姿态） | 比对两侧的姿态保持时长与帧序 | 两侧都是**每 8 GBA 帧一步**、帧序 9→10→11→10、周期 32，**逐项相等** | **已证伪** |
| H5 | 同上，是**相位偏移**（图少是因为相位没对上） | 比对两侧在**同一 32 帧窗口**内的姿态数 | 两侧窗口内都是 3 个姿态 ⇒ 姿态数与相位无关 | **已证伪** |
| H6 | 同上，是**重制侧把 32 帧周期实现成了 3 帧** | 同上 + 数描边色 | 重制侧**只有帧序表**那 3 个姿态；原版多出来的图**全部来自描边色逐帧改写**（16 级色 × 姿态 ⇒ 每周期 32 张不同图） | **已确认** |
| H7 | 原版的描边色是 32 帧三角波、每帧改一次 | 从原版 idle sweep 逐帧反解 `(0,g,g)` 的 5 bit 绿值 | 16 级（1,3,…,31），每级一周期出现 2 次，**每 GBA 帧走一步** | **已确认** |
| H8 | 描边波形可以只靠姿态周期位置算出来（不需要第二个时钟） | 把公式套到原版 sweep 的 200 帧上 | **200/200 一致** | **已确认** |
| H9 | 本机锚点处原版画 frame 010、重制画 frame 011 | 用帧美术在索引空间比对本机两侧的锚点帧 | 本机是**原版 011 / 重制 010**，与 macOS 记录**方向相反** | **已证伪**（macOS 那条不是稳定属性） |
| H10 | 用常量偏移可以修好锚点 | 用描边色把两侧的周期位置定到 ±2 帧，比较两个配对点的相位差 | 两个配对点的相位差区间**不重叠**（超前 14..21 vs 落后 3..10）⇒ **不存在这样的常量** | **已证伪**（第 26 轮结论在本机复现，并给出精确区间） |
| H11 | 相位差之所以不是常量，是因为原版的 idle 时钟被门控 | 算 walk 每步的 GBA 帧间隔（47），再看原版描边相位每步推进多少 | 推进量实测 29/6/23/…/11/19/6/2，**不是恒定的 15** ⇒ 原版时钟被场景状态机门控 | **已确认** |
| H12 | 原版只让**被选中**的单位动，重制侧两个单位都在动 | 比对两侧 sweep 的变化包围盒 | 原版 `(109,32,147,91)`（只有一个单位）；重制 `(82,32,147,98)`（两个单位） | **已确认** |
| H13 | 描边波形需要额外的 VRAM | 读 stream E 的实测 | 整片 VRAM 峰值 **47,082 / 98,304 B**（E 的 §5，E7 已证伪计划里的 98,281）⇒ 12 个单位各一个 OBJ 调色板（12×32 B = 384 B）**装得下** | **已确认**（不构成阻塞） |

---

## 8. 剩下什么 / 卡在哪

### 8.1 卡点（精确到行）

两件真正能改像素的事，**都不在本流的独占文件里**：

| # | 要改什么 | 在哪 | 为什么不在本流 |
|---|---|---|---|
| **1** | **每帧写一次描边调色板 index 15** | `butano-sequel/game/src/battle_runtime_scene.cpp`（`update_unit_sprites()`，现只有 `sprite->set_palette(dimmed_unit_palette());` 一处调色板写入，约 L6735） | 本流只准写 `battle_unit_visual_animation.h` 与 `battle_scene_controller.h`；`battle_runtime_scene.cpp` 是 **stream G** 的施工面（`WAVE2-TASKS.md` §1 注「G 与 H 都可能碰 … ⇒ G 必须在 H 之后开」） |
| **2** | **改 idle 时钟的「来源」**（不能只改初相位） | 同上，`battle_runtime_scene.cpp:6141` 的 `result.elapsed_frames = scene_frame + idle_phase_offset(unit.id);` | 同上 |

### 8.2 交给渲染路径 / 逆向侧的**施工说明**（可直接照做）

**渲染路径（`battle_runtime_scene.cpp`）**

1. 为每个单位准备一个运行时 OBJ 调色板（VRAM 够：峰值 47,082/98,304，12×32 B）。
2. 每帧在 `update_unit_sprites()` 里算
   `battle_unit_visual_animation::idle_outline_green(pose_cycle_position)`
   并写进该调色板的 index 15（绿通道 = 该 5 bit 值，红蓝 = 0）。
   `pose_cycle_position` = 该单位姿态时钟在 32 帧周期里的位置
   （= `elapsed_frames mod 32`，与 `frame_at()` 用的是同一个时钟）。
3. 若要连「相位」一起修好，把 `elapsed_frames` 的来源从自由运行的 `scene_frame`
   换成**由场景状态机门控的时钟**（见 8.3）。

**逆向侧（只读线）**

4. 查清原版「idle 动画推进」在**哪些状态**走、**哪些状态**停
   （本轮已量到：每 walk 步推进 29/6/23/…/11/19/6/2，不是恒定的 15）。
   逆向树已有线索：`AGENTS.md` 记录的 PRAM 写入链条
   `0x05000200 + bank*32 + 0x1E`（不在 copy queue 上 ⇒ 直接 `STRH`）。

### 8.3 本流已经做掉、可以直接继承的

* 「3 张 vs 16/30 张」的**根因已定位并被逐帧验证**（§2、§3）；
* 描边波形已写成**产品代码里的一个纯函数**（`idle_outline_green`）并对原版 200/200 验证通过（§3.2）；
* 「常量偏移」这条路**第二次被证伪**，而且现在有精确区间（§4.2）——**不要再试第三次**；
* 「模拟器慢一倍」这个前提**已被证伪**（§1）——**波 2 其它 stream 的结论若依赖它，需要重算**；
* 重制侧姿态节奏**不需要改**（§2）——**不要去动 `frame_at()` 的步长表**。

### 8.4 需要主控拍板的一件事

`docs/s49-three-day-plan.md` 与 `BRIEF.md` 里「本机模拟器慢一倍 ⇒ 不能跨模拟器比绝对计数」
这条前提现在不成立（§1）。若 wave 2 其它 stream（F/G/J/K）的结论建立在它上面，
**请主控决定是否要它们重算**。本流未改这两个文件（不在独占清单内）。

---

## 9. 引用

* 判定台（残差 / 棘轮）：`tools/s49_fidelity_report.py`（stream A）
* 帧号反查工具（沿用）：`butano-sequel/tools/butano/measure_s49_selected_unit_frame.py`
* 导出帧美术 / 调色板：`gba-naruto-reverse/artifacts/character-battle-visuals-v1/`（只读）
* 本轮的采集与收据：`build/s49-idle/`
  * `original-sweep-pose.json`（原版 200 帧的姿态帧号）
  * `remake-field-pose.json`（重制侧 200 帧的姿态帧号）
  * `remake-walk-pose.json`（重制侧 35 个 walk 帧的姿态帧号）
  * `outline-wave-check.json`（波形验证收据）
  * `sheet-original-walk.png` / `sheet-remake-walk.png`（两张 walk 的接触表，用来按内容定位锚点）
