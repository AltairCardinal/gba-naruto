# Wave 3 任务书 —— 产品侧对齐（三路并行 + 真值补齐）

> ⚠️ **2026-10-24 订正（wave 3 收工时回填）**：本任务书 **§1.2 第 2 条**
> 「**一格 = 16×16 px（2×2 图砖），`tiles_per_cell_x` 4→2**」**前提错误，被 G 流证伪** ——
> 16×16 px 是 **F 流的分析单位（逻辑格）**，**原版的战斗格 = 32×16 px**
> （三条独立证据：格线间距实测竖 32 px / 横 16 px、`movegrid` 青区按 32 px 合并后 =
> **曼哈顿半径 3 菱形**、ROM 碰撞网格 `width_tiles>>2`）。
> ⇒ **1 战斗列 = 2 逻辑列，1 战斗行 = 1 逻辑行**；
> ⇒ 照本任务书改会把 **32 px 格线画成 16 px（错的）**。
> G 流已按正确口径实现，见 `notes/s49-fidelity/G-overlay-alignment.md`。
>
> 同批订正：
> * **「多画 310–420 格 / 缺 96–129 格」口径作废**（拿地图空间缓冲去减屏幕空间图层）
>   ⇒ 换算后实为**多画 42 / 缺 24**。
> * **「坐标对应未建立」已关闭**：battle-14 = 逆向线 map id 14（15×19 战斗格，
>   可走 147 / 不可走 138），坐标 `(bx,by)` = 碰撞网格列行、**无偏移**。
>
> 本文件是 wave 3 的**历史任务书**，其余部分保持原样。

> 2026-10-24 · 主代理（mvs_4e730a9ded524558a303c115875a9707）
> 前置：wave 1（A/B/C/E）与 wave 2（F/H/J/K）全部交付，结论已落盘于本目录。
> **wave 3 的目标：把 wave 1/2 查出来的「产品差」逐条改掉，同时补齐缺失的地面真值。**

---

## 0. 所有子代理必读（共享事实，勿重复调查）

### 0.1 口径两条（用户原话，不可改写）

1. **「完全一致」只算玩家看得见的画面 + 游戏逻辑状态**；寄存器不关心。
2. **音频按事件级交付**；逐采样明确排除（要复现 MP2K 合成器，80–120 h）。

### 0.2 三棵树

| 树 | 路径 | 本轮权限 |
|---|---|---|
| master（证据/工具/文档） | `D:\Github\gba-naruto` | 可写（**但只写自己独占的那部分**） |
| 重制线（产品代码） | `D:\Shell\Github\gba-naruto-butano` | 可写，**仅限自己独占的文件** |
| 逆向线 | `D:\Shell\Github\gba-naruto-reverse` | **全程只读** |

### 0.3 仓库纪律（`AGENTS.md`，硬要求）

* 发现必须落盘到仓内文件；**聊天记录不算记忆**。
* **一次只改一处，跑一次，记一行。** 结论落进**假设台账**
  （一行一个假设：判定方法 / 结果 / 状态 = 未验·已证伪·已确认）。
* **连续 3 次同样结果 ⇒ 停**，换方法，把「这条路走不通」写进台账。
* 一次尝试必须能回答一个**是/否问题**；「还是卡」是噪音。
* 新写文件一律 **LF、无 BOM**（换行符一改就毁掉 SHA-256 证据身份）。
* `core.autocrlf` 必须是 `false`。
* 不提交（除非父代理另行指示）。

### 0.4 环境与工具

```powershell
# 私有探针（**不要**覆盖共享的 build/mgba-probe/mgba-probe.exe，会 LNK1104）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-<你的流>'
python tools/mgba_probe/build.py

# 构建重制 ROM（WSL；必须显式导出 LIBBUTANOABS）
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 判定台（唯一验收仪器）
python tools/s49_fidelity_report.py --out build/s49-report/report.json
```

### 0.5 关键路径

| 东西 | 路径 | sha256 / 备注 |
|---|---|---|
| 原版存档 | `D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints\scenario-49-battle-14-entry.ss9` | `a3628723…` |
| 原版 ROM | `D:\Shell\Github\gba-naruto-butano\rom\base.gba` | `1198ece7…` |
| 真 BIOS | `D:\Github\gba-naruto\recomp\bios\gba_bios.bin` | **录制时不要加 `--bios`** |
| 重制 ROM | `D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba` | 构建后更新 |
| 覆盖层地面真相 | `D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1\` | `field/movegrid/grid16/banner-frame-v1.bg2-tilemap.json` 等 |
| 原版地图图集 | `D:\Shell\Github\gba-naruto-reverse\artifacts\map-canvases-v1\canvases\map-*.png` | **只读** |

### 0.6 已确认的硬事实（wave 1/2 结论，不要重查）

* **mGBA 探针**：`d8bad14b`，GBA 存档版本 `0x0000000A`。
* **基线基线坑**：基线 savestate 用的是 **HLE BIOS**，不是真 BIOS；本机构建 ROM 的 sha
  ≠ 基线钉的 `02bf3573…` ⇒ **基线 savestate load 不了**。
* **录制参数**：`ZERO_INPUT_FRAMES=600`。
* **探针坑**：`dump` 地址按**十进制**解析；`framedump`/`keyseq` 吃 `0x` 字面量。
* mGBA Lua `emu.memory["vram"]` 在游戏开始渲染后抛 `Invalid object` ⇒ VRAM 只能用总线读。
* **读 I/O 块会扰动模拟**（VCOUNT 有清标志副作用）⇒ VRAM 与 I/O 必须分两次运行。
* **「本机慢一倍」是采集重复**（探针 Lua `frame` 回调每 GBA 帧触发两次）⇒
  **跨模拟器绝对计数现在可以直接比（÷2 即可）**。
  ⚠️ 此前提「慢一倍 ⇒ 绝对计数不可跨模拟器比」**已被证伪**，
  `docs/s49-three-day-plan.md` / `docs/sequel-roadmap.md` / `BRIEF.md` 里的这条口径由父代理删除。
* **所有判据按内容定位，不按帧序号**（`grid16` 是 1 帧瞬态）。

### 0.7 wave 2 的四份报告（必读）

| 流 | 文件 | 一句话结论 |
|---|---|---|
| F | `notes/s49-fidelity/F-rule.md` | **原版点亮的是「可达范围高亮」**，不是不可达压暗 |
| H | `notes/s49-fidelity/H-idle.md` | 姿态节奏两侧一致；相位差来自**状态机门控** vs 自由运行 `scene_frame`；**原版每帧改 OBJ 调色板 index 15，重制从不改** |
| J | `notes/s49-fidelity/J-audio.md` | 战斗 BGM **ID 错**（原版 sound 10，重制 sound 14）；12 个音效 cue **全静音**；素材本身是对的 |
| K | `notes/s49-fidelity/K-original-victory.md` | **原版 S49 结算屏真值仍不存在**；但打出了真实伤害（bee-8 `25→7`） |

---

## 1. 流 G —— 覆盖层形状对齐（**关键路径**）

### 1.1 独占文件（**只能改这些**）

* `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_runtime_scene.cpp`
  （覆盖层渲染在 **L2060–L2218**，调色板在 **L2220–L2560**）
* `…\game\include\konoha\battle_range_ui_style.h`
* `…\game\include\konoha\grid_pathfinder.h`
* `…\game\include\konoha\generated_battle_movegrid_overlay_content.h`
* `…\game\include\konoha\generated_battle_battlefield_overlay_content.h`
* 新文件随意（命名空间 `konoha`），但**不要改** `battle_unit_visual_animation.h` /
  `battle_visual_resource_coordinator.h` / `battle_unit_palette_stream.h`（H2 独占）

### 1.2 施工要点（抄 F 的 §8 + §0）

1. **族词表照抄原版**：`blank / edge / hatch / line_alt / band / solid`
   （外加 `hatch_shift`=绿「合法目标」，这四个时刻没用过，但图砖在原版 tile 集里）。
2. **一格 = 16×16 px（2×2 个 8×8 tilemap 项）**，不是现在的 32×16。
   ⇒ `battle_range_ui_tiles_per_cell_x` 4→**2**，`tiles_per_cell_y` 2→2。
   ⇒ `battle_range_ui_pixel_index` 的边界判据 `cell_x == 31 || cell_y == 15` → `cell_x == 15 || cell_y == 15`。
3. **判定顺序**：`cursor(band) > target(hatch_shift) > attack(line_alt) > move(hatch) > blocked(solid) > walkable(edge) > outside(blank)`。
   现在的 `battle_range_ui_cell_kind` 里 `move_phase` 特判要按上面这条重排。
4. **只在战场范围内画**。原版**不在**整张地图上铺覆盖层；重制侧当前「多画 310–420 格」
   的根因就在这里。
5. **画法必须逐像素对得上**：
   * `edge` = **1 px 细格线**（不是整格着色）；
   * `hatch` / `line_alt` / `band` = **实心填充**（边界用次色）；
   * `solid` = **50% 灰网点**（不是实心）；
   * `blank` = 全透明。
   原版的 32 块图砖像素在
   `D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1\bg2-tiles-4bpp.bin`
   （**32 块 × 32 B，4bpp**；按 16 B 步长读会得到「edge 族全是空白」的假象）。
6. **调色板**：11 个已占用槽位 = 重制侧 **225–235**，与原版 bank 12 的 1–11 **逐项 RGB5 相同**
   （wave 1 E 流已验）。要确认地图背景**没有占用** 224–239。
7. **可达集来源**：用重制侧 `grid_pathfinder.h` / `battle_map_movement.h` 算，
   目标形状（`movegrid` 时刻，青区逐行宽度 **12 / 10 / 6 / 2**，关于第 6 行对称，
   左右边界不同步：左边界每行 +2、右边界 −2，并在 (8,7)、(9,7) 被占格挖空）。
   ⚠️ **坐标对应尚未建立**：原版覆盖层是 16×16 逻辑格（256×256 px，锚在**地图空间**，
   F 的 H5 已证），重制侧 battle-14 地图是 **15×19** 格。
   ⇒ 你必须自己建立这个对应（可用逆向线 `map-canvases-v1` 的原版地图图集 + 原版运行中的
   BG1/tilemap dump + 重制侧 `battle_map_content.h`）。

### 1.3 验收门禁

* **原版侧**：F 的四条 sha256 必须能在本机重抓命中（2048 B BG2 tilemap 逐字节）——
  ```
  field    ce5dd2917f062e5ef8f868898c8f3f7aa70e49cbd93cf50eaec274755efd487e
  movegrid 72dbe5858aa2fb5e8cf09208a61b26f788d8bd785a640035532f4396ed5ea230
  grid16   c1236fbbb8047a571f4685b252cc3e0721cab8e903698d535a61279b56a3fa3e
  banner   193aa2d94d7f3f161c06614a2e0a573820866b5b9874c441ee6314adda38ed18
  ```
  复现命令：`python tools/s49_rule_probe/capture_original.py --out build/s49-rule/capture`
  与 `python tools/s49_rule_probe/verify_moments.py --out build/s49-rule/verify-moments.json`（须 exit 0）。
* **重制侧**：**逐格族名对拍**（不是逐字节 tilemap 对拍——两侧 tile 编号不同、
  原版 4bpp / 重制 8bpp，字节不可比）。用
  `tools/s49_rule_probe/overlay_ground_truth.py` 读原版四时刻的地面真相，
  与重制侧同一游戏时刻的覆盖层按 **16×16 逻辑格**比「族名」，
  目标：`original-only = 0`、`remake-only = 0`、**族名逐格 0 处不一致**。
  重制侧当前基线（wave 1 逐格差分）：

  | 原版时刻 | 原版亮 | 重制亮 | 重合 | 重制多画 | 原版有/重制缺 |
  |---|---:|---:|---:|---:|---|
  | field | 598 | 821 | 482 | 339 | 116（edge 53·solid 49·hatch 14） |
  | movegrid | 640 | 821 | 511 | 310 | 129（solid 49·hatch 42·edge 38） |
  | grid16 | 497 | 821 | 401 | 420 | 96（edge 58·solid 23·hatch 14·band 1） |
  | banner | 1 | 821 | 1 | 820 | 0 |

  ⇒ **「受阻区漏画 2,304 px」的说法不准确**：真相是**多画 310–420 格 + 缺 96–129 格**。
* **判定台残差必须下降**（棘轮语义：残差只许变小）：
  `python tools/s49_fidelity_report.py --out build/s49-report/report.json`
  基线：战场区残差 **min 0 / 中位 1940 / max 27325 / 全 0 帧 3**；
  归因 **一致 3 · 产品差 14 · 配对差 8**。
* **重制 ROM 必须能构建**（WSL 命令见 §0.4），并用无窗口探针跑通中文标题画面。

### 1.4 交付物

* `notes/s49-fidelity/G-overlay-alignment.md` —— 报告（含假设台账、逐格差分前后对比表）。
* 重制线代码改动（上面独占清单内）+ 新增单元测试。
* `tools/` 下新增的对拍脚本（放 `tools/s49_rule_probe/` 或自建目录，**不覆盖** F 的文件）。

### 1.5 已知未解项（允许未验，但必须写进台账）

* F-3：原版「单位坐标 + 地形 → 可达集合」这一步**没在原版侧落地**（原版可达集不在
  EWRAM/IWRAM 里以逐格数组存在）；原版的青区形状**非朴素菱形也非欧氏圆**。
* F-2：坐标对应未建立（见 §1.2.7）。

---

## 2. 流 H2 —— idle 相位 + 逐帧 OBJ 调色板改写

### 2.1 独占文件（**只能改这些**）

* `…\game\include\konoha\battle_unit_visual_animation.h`（H 流已改过它）
* `…\game\include\konoha\battle_visual_resource_coordinator.h`
* **新文件** `…\game\include\konoha\battle_unit_palette_stream.h`
* `…\game\tests\test_battle_unit_visual_animation.cpp`
* `…\game\tests\test_battle_visual_resource_coordinator.cpp`

⛔ **禁止改 `game/src/battle_runtime_scene.cpp`**（G 流独占）。你只提供**纯逻辑模块**，
由 G 流负责接线。你必须在报告里写清「接线点：在 `battle_runtime_scene.cpp` 的哪一行、
调哪个函数」，G 会照做。

### 2.2 任务

1. **idle 时钟改为状态机门控**。现状：`elapsed_frames = scene_frame + idle_phase_offset(unit.id)`
   —— `scene_frame` 是自由运行的，**原版的 idle 时钟受状态机门控**。
   H 流已证：两侧姿态节奏**完全一致**（每 8 帧换一次，9→10→11→10/32），
   但**相位差不存在常量偏移**（区间不重叠）⇒ 必须是**状态机事件驱动**的时钟，
   不是 `scene_frame + offset`。
2. **逐帧 OBJ 调色板改写**。原版**每 1 帧**改 OBJ 调色板 **index 15**（描边色），
   重制侧**从不改** ⇒ 这就是 wave 1 的「重制 3 张图 vs 原版 16/30 张」的根因之一
   （另一半根因是重制侧只实现了 ROM 的帧序表、没实现逐帧调色板改写）。
   H 流已写 `idle_outline_green()`；你把它整理成**每帧决策函数**。
3. 两条都要有**单元测试**（`battle/tests/` 下）。

### 2.3 必须提供的接口契约（G 会按这个接线）

```cpp
// game/include/konoha/battle_unit_palette_stream.h
#ifndef KONOHA_BATTLE_UNIT_PALETTE_STREAM_H
#define KONOHA_BATTLE_UNIT_PALETTE_STREAM_H
#include <cstdint>
namespace konoha {

struct battle_unit_palette_rgb5 { int red = 0; int green = 0; int blue = 0; };

// 本帧要不要改 OBJ 调色板槽位 index 15；改的话写什么颜色。
struct battle_unit_palette_write {
    bool        valid = false;      // false = 本帧不写
    int         palette_index = 0;  // 目标调色板槽位（原版用 OBJ 调色板 index 15）
    int         color_index = 0;    // 0..15
    battle_unit_palette_rgb5 color{};
};

// idle 周期（帧）：同一单位下一次换姿态的间隔。
[[nodiscard]] int battle_unit_idle_cycle_frames(int unit_id);

// 该单位当前 idle 相位（帧），**状态机门控**。
[[nodiscard]] int battle_unit_idle_phase_frames(int unit_id, unsigned state_frame);

// 逐帧 OBJ 调色板改写决策（纯函数，无副作用）。
[[nodiscard]] battle_unit_palette_write
battle_unit_palette_write_for_frame(int unit_id,
                                    unsigned state_frame,
                                    unsigned scene_frame);
}
#endif
```

⚠️ 颜色结构**必须自己定义**（不要 include `battle_range_ui_style.h`，
那个文件 G 流在改，会造成编译耦合）。

### 2.4 验收

* 新单元测试通过（`battle/tests/` 的既有跑法）。
* 报告里给出：**200/200 帧描边波一致**的门禁复跑命令
  （`python tools/s49_idle_outline_wave.py`）。
* **不得**改 ROM 行为以外的东西；**不得**改 `battle_runtime_scene.cpp`。

### 2.5 交付物

* `notes/s49-fidelity/H2-idle-palette.md` —— 报告 + 假设台账 + **接线点清单**。
* `battle_unit_palette_stream.h` + 测试 + 对两个既有头的改动。

---

## 3. 流 L —— 音频接线修复

### 3.1 独占文件（**只能改这些**）

* `…\game\include\konoha\battle_audio_director.h`
* `…\game\include\konoha\battle_audio_runtime.h`
* `…\game\include\konoha\battle_scenario_content.h`（若 BGM 选择在这里）
* 音频资产目录（**只新增**，不改既有资产字节）
* `…\game\tests\test_battle_audio_director.cpp`

⛔ **禁止改 `game/src/battle_runtime_scene.cpp`**（G 流独占）。若发现必须改它，
写进报告交给父代理，不要自己改。

### 3.2 三个具体缺陷（J 流查实）

| | 原版 | 重制侧 | 修法 |
|---|---|---|---|
| 战斗 BGM | MP2K **sound 10** | **sound 14**（= S41 的战斗曲） | 把 S49 的战斗 BGM 改成 **sound 10** |
| 12 个音效 cue | 会播 | `play_battle_sound()` 是 `(void) cue;` → **全静音** | 接通：把 cue 映射到已有资产并真正播放 |
| cue 8 / 146 / 152 | 会播 | cue 8 无调用点；146/152 **连资产都没有** | cue 8 补调用点；146/152 资产需从原版 ROM 提取（若成本过高，写进台账标为**未验**） |

### 3.3 关键事实

* **素材是对的**：两侧共有的 17 个 cue **时长差全部 0.000 s**
  （原版 PCM_RATE = 15768）⇒ 坏的是**接线**，不是素材。
* 原版这场仗会响的 9 个 cue，重制侧「ID 正确且能出声」= **0 个**。
* 重制侧 BGM 资产是**录制的 PCM 以 S3M 回放**，不是 MP2K 合成 ⇒
  **逐采样一致做不到**（要复现 MP2K 合成器，80–120 h）。**本流不做逐采样**。
* 事件次序语义两侧一致 ⇒ **不要改顺序**，只改 ID 与接线。
* J 流的工具链在 `tools/s49_audio_probe/`，**只读复用，不要改**。

### 3.4 验收

* 修完后重跑 J 的对照管线（`tools/s49_audio_probe/run_all.py`），
  产出新的 `event_diff`：19 个配对时刻里
  `match 4 / cue_mismatch 1 / silent_on_remake 11 / never_dispatched 1 / missing_on_remake 2`
  ⇒ 目标是把 `silent_on_remake` 与 `cue_mismatch` **压到 0**。
* **两次独立全流程跑，产物逐字节一致**（J 的既有验收口径）。
* 新单元测试通过。
* 你的改动必须能被 `tools/s49_audio_probe/extract_remake.py` 观测到
  ⇒ **需要给重制侧加一个 build 开关**，把 `(kind, cue, frame)` 写进固定 IWRAM 环形缓冲
  （J 流的卡点 #1，报告 §8 已写）。**这是产品代码改动，允许你做。**

### 3.5 交付物

* `notes/s49-fidelity/L-audio-wiring.md` —— 报告 + 假设台账 + 前后 `event_diff` 对比。

---

## 4. 流 M —— 原版 battle-14 打到胜利 + 结算屏真值

### 4.1 独占文件（**只能改这些**）

* `D:\Github\gba-naruto\tools\s49_victory_capture\`（K 流建的，你接着做）
* `D:\Github\gba-naruto\build\s49-victory-capture\`（临时产物）
* 新目录 `D:\Github\gba-naruto\tools\s49_orig_map\`（次要交付用）

### 4.2 目标

**原版 S49 结算屏真值现在不存在**（B 流查实）。你的任务是把它**录出来**：
从 `scenario-49-battle-14-entry.ss9` 起，打赢木叶丸 vs 野蜂这仗，
录到胜利演出 + 结算屏，导出像素帧与游戏逻辑状态。

### 4.3 K 流已经解决的（别重做）

* 行动菜单 5 项、忍术列表 4 项、瞄准/距离规则、`可以嗎?` 确认框、
  敌方「蜂刺」远程不打位移、玩家操作全部 4 名同伴、**忍术列表按角色不同**。
* 攻击链已稳定命中：bee-8 `25→7`、bee-4 `25→3`、bee-5 `25→7`。
* 采集流水线两次连跑 **21 427 个文件逐字节一致**。
* 通关路线（已实跑命中）：
  ```
  A×21   开场演出+对白+回合横幅+移动阶段
  Left×3 移动游标 (11,6)→(8,6)
  A      确认移动 → 紧凑菜单(术·忍具/行動結束)
  A      术·忍具 → 忍术列表
  Down×3 十字手里剑
  A      选中 → 瞄准模式
  Left×2 瞄准游标 → 蜜蜂(6,6)
  A      开火 → 伤害预测 → 可以嗎?
  A×6    是 → 演出 → 结果   ⇒ 蜜蜂8号 HP 25→7
  ```

### 4.4 当前卡点（你的主攻方向）

**距离/地形，不是机制**：第 2 个单位（小樱 (8,14)）的移动落点**全部非法**
（底边地形阻挡），该回合既没动也没打，回合不推进，耗尽回合预算；变身术落点同样被地形挡。

**K 流建议的下一步（优先照做）**：
> 不要用坐标猜落点 —— 移动/传送阶段都把**合法格**画成**青/橙色**、游标画成**绿色框**，
> 在屏幕上读橙色格，再用像素差换算 D-pad 次数。
> 一次就能消掉「非法落点→错误框→卡死」和「落点不落地」两类问题。

⚠️ 注意：G 流正在改重制侧的覆盖层渲染，**原版侧**的青/橙/绿画法由 F 流查实为
`hatch`=青(移动可达)、`line_alt`=橙(攻击范围/落点)、`band`=黄(光标)、
`hatch_shift`=绿(合法目标)。K 流报告里说的「绿色框」与 F 的「黄=光标」有出入，
**以 F 的 `notes/s49-fidelity/F-rule.md` 为准**（F 是机器读出的像素级结论）。

### 4.5 次要交付（原版地图/地形真值，给 G 流用）

G 流卡在「坐标对应未建立」。你能顺手交付：

* 原版 battle-14 **地图图集 + 地形类别 + 通行成本**（格数、哪些格不可进入）。
* 参考：逆向线 `artifacts/map-canvases-v1/canvases/map-*.png`（**只读**）与
  `artifacts/bg-resource-canvases-v1/entry-*/tilemap-u16le.bin`。
* 交付到 `tools/s49_orig_map/` + 报告里的一节。

### 4.6 验收

* **原版胜利帧 + 结算屏帧**落盘（PNG），并有 sha256 收据。
* 两次独立跑 **逐字节一致**（K 流的 `verify_capture.py` 口径）。
* 结算屏若是多帧演出，给出**全部关键帧**与帧间状态差分。
* 若**仍没打成**：不要死磕。交出「打到第 N 回合、最远进度、卡住的具体原因」，
  并在台账里标状态。

### 4.7 交付物

* `notes/s49-fidelity/M-original-victory-truth.md` —— 报告 + 假设台账。

---

## 5. 父代理（我）同时做的事

* 回填被 wave 2 推翻的口径（删「本机慢一倍 ⇒ 绝对计数不可跨模拟器比」）。
* 更新 `docs/sequel-roadmap.md`、`docs/s49-three-day-plan.md`、
  `docs/butano-fidelity-roadmap.md`。
* 维护判定台棘轮：任何流声称「残差下降」都要用判定台独立复跑确认。
* 监视四路进度、估算剩余耗时、动态调任务。

---

## 6. 交回格式（每个子代理的最终回复）

1. **一句话结论**。
2. **改动的文件**（完整绝对路径列表）。
3. **跑了哪些验证**（命令 + 关键数字）。
4. **假设台账**（表格：# / 假设 / 判定方法 / 结果 / 状态）。
5. **卡在哪**（若没完成，说清卡在第几步、缺什么）。
6. **新文件一律 LF、无 BOM**；**不提交**。

---

## 7. 反循环守则（复述，因为本轮特别容易踩）

* 一次尝试回答一个是/否问题。**「还是卡」不是结果。**
* 一次只改一处，跑一次，记一行。
* 连续 3 次同样结果 ⇒ **停**，换方法，写进台账。
* 陷住了**换方法/换会话**，不要靠续跑硬扛 —— 续跑提示会逐字重复，
  只会把同一个状态再喂一遍。
* 自检：`python tools/loop_guard.py <会话的 messages.jsonl>` ——
  命中就是「真的在打转」，不要继续往下想。
