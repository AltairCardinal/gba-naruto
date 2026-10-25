# X3 —— 边界产品差：蜜蜂跨阵营轮转（B5）+ 战斗期不写盘（B7）

> 2026-10-24 · wave 5 · 流 X3（**接管**：上一任在 05:41 被运行时中断，改动全部未经验证）
> 独占：`battle_session.h` / `battle_campaign_sram.{h,cpp}` / `src/main.cpp` / 3 个单测 /
> `tools/s49_x3_boundary/`
> 逆向线 `D:\Shell\Github\gba-naruto-reverse`：**全程只读**

---

## 0. 一句话结论

**上一任的 B5 与 B7 改动经实测都是对的（B5 的像素判据 C1–C4 全绿：重制侧的状态栏气条像原版一样从 849 绿像素掉到 697；B7 在 ROM 上实测写 0 字节且断言不崩），单测棘轮零回归、构建干净、W4 存档门禁 exit 0；
但 B5 会触发一个重制侧**既有**的调色板 bank 泄漏 —— 玩家在单位选择阶段连按 R 到第 9 个单位时 ROM 崩在 Butano 的 `bn_palettes_bank`（16 个硬件 sprite 调色板 bank 被 9 个「每单位一份运行期调色板」+ UI 调色板吃光），
⇒ 这个崩点的修复点在 `battle_runtime_scene.cpp`（**X1 流独占，本流不许改**），已升级给父代理；B5 本身按「原版行为 = 规格」保留。**

---

## 1. 上一任留下的东西：逐条核查结果

| # | 上一任的改动 | 核查方法 | 结果 |
|---|---|---|---|
| 1 | `battle_session.h::cycle_roster_unit()` 去掉 `unit.side == _current_side` | 新单测 + 像素判据 + 两个 ROM 的 A/B 走位 | ✅ **对**：轮转指针能落到敌方蜜蜂槽 5/6/7；像素上重制侧与原版**同一组数值**（气条 849 → 697） |
| 2 | `battle_campaign_sram.h` 加 `battle_campaign_save_trigger` 枚举 + `suppressed` 标志 | 编译 + 单测 + ROM 实测 | ✅ **对**：战斗结果这一路不写盘，0 字节 |
| 3 | `battle_campaign_sram.{h,cpp}`：保存流程抽成可插拔 storage 的模板 | 编译 + 单测（host 上跑同一段流程） | ✅ **对**：`save_battle_campaign_to_slots()` 的 suppressed 分支在碰 storage 之前就返回 |
| 4 | `src/main.cpp` 战斗结果那条路传 `battle_result` trigger，断言改成 `saved.success() && saved.suppressed` | **探针 ROM 实测**（上电就调用这一路 + 同一个断言） | ✅ **对**：不崩，且 SRAM 与出厂 ROM **逐字节相同** ⇒ 运行时写 0 字节 |
| 5 | `game/tests/test_battle_roster_cross_side.cpp`（新） | 单测棘轮 | ✅ 绿 |
| 6 | `game/tests/test_battle_campaign_sram_trigger.cpp`（新） | 单测棘轮 | ✅ 绿 |
| 7 | `game/tests/test_battle_roster_scheduler.cpp`（改 5 行） | 单测棘轮 | ✅ 绿 |
| 8 | `tools/s49_x3_boundary/check_b5_rotation.py` | 跑 | ⚠️ **上一任自己写的判据是红的**（C3 FAIL：判据写错了 —— 它把整条走位的气条数值集合当成判据，而走位里有标题画面/准备场景的 0 与 510）。**本流重写了它**（按「轮转步」判据 + 加了不带 B5 的对照），现在 C1–C4 全绿 |

---

## 2. 前后对照表

### 2.1 B5 —— 蜜蜂进轮转

| 项 | 改前 | 改后 | 证据 |
|---|---|---|---|
| `cycle_roster_unit()` 的过滤 | `unit.active && unit.side == _current_side` | `unit.active`（**跨阵营**） | `battle_session.h:530-540` |
| 玩家游标能否落到敌方蜜蜂 | **不能** | **能**（槽 5/6/7/8/9） | `test_battle_roster_cross_side.cpp`（绿） |
| 轮转时状态栏气条的绿像素数 | **恒 849**（永远是玩家） | **849 → 697**（697 = 原版蜜蜂行的数值） | `check_b5_rotation.py` C3/C4 |
| 原版同一条曲线 | 849（我方 4 个）→ 697（敌方 6 个） | — | `check_b5_rotation.py` C2 |
| 单测断言 | `cycle_roster_unit(3,1)->id == 1` | `== 4` / `== 5` / `== 1` | `test_battle_roster_scheduler.cpp:48-53`（绿） |
| **ROM 实测：规范走位** `Down,Down,A×32` | — | **33 帧，无错误屏** | `smoke-canonA.json` |
| **ROM 实测：轮转走位** `Down,Down,A×16,R×8` | 26 帧，**不崩** | 27 帧，**第 8 次 R 崩** | `smoke-romB-nob5.json` vs `remake-walk-312dfc97` |
| 轮转走位崩溃阈值 | 不可达（游标到不了蜜蜂） | R×4 / R×6 / R×7 **不崩**，**R×8 崩** | `smoke-romA-r4/r6/r7.json` |

### 2.2 B7 —— 战斗期不写盘

| 项 | 改前 | 改后 | 证据 |
|---|---|---|---|
| 战斗胜利后的写盘 | **自动写盘**（4020 B / 槽轮换 + 世代 +1） | **suppress（0 字节）** | `test_battle_campaign_sram_trigger.cpp`（绿） |
| 写盘入口 | `save_battle_campaign_to_sram(campaign, ws)` | 同上 + `battle_campaign_save_trigger::battle_result` | `main.cpp:184-195` |
| 断言 | `saved.success() && saved.verified` | `saved.success() && saved.suppressed` | 同上 |
| 准备场景的「存档」菜单 | 写盘 | **仍然写盘**（未改） | 单测 ①③；W4 实测 4020 B |
| **ROM 实测**（探针 ROM：上电就调用这一路 + 同一个断言） | — | **不崩**；SRAM sha256 `2d864c0b789a4321…` 与出厂 ROM **完全相同** ⇒ 运行时写 **0 字节** | `b7_runtime.json` |
| W4 存档门禁 | `remake_save2_to_battle = 0 B` | **仍是 0 B**，两次跑 62 张镜像逐字节一致，exit 0 | `run_all.json` |
| 原版对照 | 46 个检查点（含打赢后的任务菜单）只有 1 种镜像 ⇒ 战前→战后 **0 字节** | — | W4 §4.1（未改动 W4 的工具） |

---

## 3. 跑了哪些验证

| # | 命令 | 关键数字 |
|---|---|---|
| V1 | `wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=… && make -j4"` | **`ROM fixed!`**（干净通过）。额外发现：**本机构建对本文件是字节可复现的** —— 撤销 B5 再改回来，两次 ROM 的 sha256 都是 `c1f44b3b5bf603bb…` ⇒ A/B 的两个 ROM 只差那一行 |
| V2 | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/tools/s49_x3_boundary/run_unit_ratchet.sh` | HEAD 基线 `pass=101 fail=20`；工作区 `pass=105 fail=20`；**new red = ∅**；`test_battle_roster_cross_side` / `test_battle_roster_scheduler` / `test_battle_campaign_sram_trigger` **全绿**。失败集合与 `notes/s49-fidelity/Q-unit-test-baseline.md` 的 20 项**逐名相同**。（脚本把输出目录改成 `/tmp/x3-unit-ratchet-$$`：两个 ratchet 并发跑会互相覆盖测试二进制，把结果搞成假红 —— 本流撞过一次，已修。） |
| V3 | `python tools/s49_save_boundary/run_all.py --repeat 2`（**只读复用，未改**） | **exit 0**；`reproducible across 2 runs: True`；原版 46 检查点 / 1 种镜像 / 战前→战后 **0 B**；重制侧 erased→save1 **4020 B**、save1→save2 **4020 B**、**save2→战斗 0 B**；跨格式 3856 B（按用户口径排除） |
| V4 | `python tools/s49_x3_boundary/check_b5_rotation.py` | **C1–C4 全 PASS**：原版 marker 跨阵营（我方 4 步 / 敌方 6 步）；原版气条 我方 849 / 敌方 697；带 B5 的重制侧轮转 849→697（697 出现在第 3 个轮转步）；**不带 B5 的重制侧轮转恒 849** |
| V5 | `python tools/s49_x3_boundary/check_b7_runtime.py` | 探针 ROM **不崩**；探针 SRAM sha256 `2d864c0b789a4321…` == 出厂 ROM 的 ⇒ **运行时 0 字节** |
| V6 | `python tools/s49_x3_boundary/check_rom_smoke.py --label canonA --keys Down,Down,A×32` | **33 帧，无错误屏**（规范 S49 走位不崩） |
| V7 | 同一脚本 `--label romB-nob5 --rom rom-B-no-b5.gba --keys Down,Down,A×16,R×8` | 26 帧，**无错误屏** ⇒ 不带 B5 的重制侧轮转**不崩** |
| V8 | 同一脚本 `--label romA-r4 / r6 / r7`（带 B5） | R×4、R×6、R×7 **都不崩**；**R×8 崩** ⇒ 崩溃需要游标走到**第 9 个单位** |
| V9 | `git -C … diff HEAD -- butano-sequel` | 改动文件集合与本流开工时**逐项一致**（15 个文件 + 5 个未跟踪新文件）；**本流没有新增/删除任何重制线文件**；`battle_runtime_scene.cpp` **未被本流碰过**（它在本流开工前已被改过 386 行，本流收工时是 470 行 —— 那是 **X1 在 05:59 自己改的**，比本流最后一次构建（05:58）晚，所以本流的构建没有覆盖 X1 的在途改动；**树里的 ROM 因此比 X1 的最新源码旧，X1 需要自己重建一次**） |

产物（都在 `D:\Github\gba-naruto\build\s49-x3-boundary\`）：
`receipts/b5_rotation.json`、`receipts/b7_runtime.json`、`receipts/smoke-*.json`、
`roms/rom-A2-with-b5.gba`（sha `c1f44b3b…`）、`roms/rom-B-no-b5.gba`（sha `daf1ffa8…`）、
`roms/rom-probe-b7.gba`（sha `8120ab88…`）、`rotation-with-b5/`、`rotation-without-b5/`、
`b7-probe/`、`b7-shipped/`、`sram/b7-probe.bin`、`sram/b7-shipped.bin`。

---

## 4. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| X3-1 | 上一任的改动编译不过 / 改坏 | `make -j4` | `ROM fixed!`；且改回 B5 后重建的 sha256 与改前相同 ⇒ 改动**可编译且字节可复现** | **已证伪** |
| X3-2 | 上一任新增/修改的 3 个单测是红的 | 单测棘轮 | 三个全绿 | **已证伪** |
| X3-3 | 工作区的失败集合比 HEAD 基线多了东西 | `run_unit_ratchet.sh` | new red = ∅；fail 集合逐名相同（20 = 20） | **已证伪** |
| X3-4 | `BN_ASSERT(saved.success() && saved.suppressed)` 会崩 | 探针 ROM（上电就调用 battle_result 那一路 + 同一个断言）+ 规范走位 | 不崩，35 帧 | **已证伪** |
| X3-5 | 战斗结果这一路在 ROM 上真的写 0 字节 | 探针 ROM 与出厂 ROM 的 SRAM 逐字节比 | sha256 **完全相同**（`2d864c0b789a4321…`） | **已确认** |
| X3-6 | 准备场景的「存档」菜单被 B7 改没了 | 单测 ①③ + W4 的 4020 B | 仍写盘 4020 B | **已证伪** |
| X3-7 | B5 让玩家的轮转游标能落到敌方蜜蜂 | `test_battle_roster_cross_side.cpp` | 能（槽 5/6/7/8/9，character 55） | **已确认** |
| X3-8 | B5 的**像素级**判据成立（重制侧 = 原版） | `check_b5_rotation.py`：状态栏气条绿像素数 | 原版 849→697；带 B5 的重制侧 849→697；不带 B5 恒 849 | **已确认** |
| X3-9 | 去掉阵营过滤会破坏 S49 的正常操作流程 | 规范走位 `Down,Down,A×32` | 33 帧，无错误屏 | **已证伪** |
| X3-10 | 上一任写的 B5 像素判据可用 | 直接跑上一任的脚本 | **C3 FAIL**（判据把整条走位的气条数值集合当判据，走位里有标题/准备场景的 0 与 510） | **已证伪**（本流重写） |
| X3-11 | B5 会引入崩溃 | 同一条轮转走位跑**两个** ROM（只差那一行） | 带 B5：第 8 次 R 崩；不带 B5：26 帧不崩 ⇒ **B5 是触发条件** | **已确认（负面结果）** |
| X3-12 | 崩溃的根因是「每单位一份运行期调色板」把 16 个 bank 吃光 | 代码走查 + R 次数阈值 | `unit_palette_slot(unit.id)` 每单位一个运行期调色板；换人时 `else` 分支只把**第 0 个 component** 的 sprite 换回静态调色板，其余 component 仍持有运行期调色板 ⇒ **每访问一个新单位泄漏一个 bank**；R×7（8 个单位）不崩、R×8（9 个单位）崩 ⇒ 9 个单位调色板 + UI 调色板正好顶到 16 | **已确认**（待 X1 复核） |
| X3-13 | 打赢 S49 才能实测「战斗胜利后不写盘」 | 找 W3 的胜利驱动 | **做不到**：W3 的 `verify-play` 最好成绩是 `victory: false`（2 回合 / 1 命中）⇒ 改用**探针 ROM**（把同一路调用提到上电）实测，得到等价的运行时结论 | **未验（原路径）** / 探针路径**已确认** |
| X3-14 | 单测棘轮脚本可以用固定的 `/tmp` 输出目录 | 并发跑两次 ratchet | **不成立**：两次会互相覆盖测试二进制，把结果搞成假红（new red 出现了一个并不存在的名字）⇒ 脚本改成 `$$` 唯一目录 | **已证伪**（脚本已修） |

---

## 5. 🔴 阻塞项（必须交给 X1 / 父代理）

### 5.1 崩溃：轮转游标走到第 9 个单位时 ROM 崩

* **症状**：Butano 致命错误屏
  `ERROR in bn_palettes_bank.cpp.h / create_bpp_4:176 / BPP4 palette create failed. Colors count: 16 / There are no more available colors.`
* **触发**：单位选择阶段（`SELECT 詳細`）连按 **R** 走位。第 8 次 R（游标落到第 9 个单位）崩；R×4 / R×6 / R×7 都不崩。
* **A/B 证据**（两个 ROM 只差 `battle_session.h` 的那一行，构建字节可复现 ⇒ 不是构建噪声）：

  | ROM | sha256 | 轮转走位结果 |
  |---|---|---|
  | 带 B5 | `c1f44b3b5bf603bb…` | 27 帧，**step-26-R 是错误屏** |
  | 不带 B5 | `daf1ffa868c11ece…` | 26 帧，**无错误屏** |

* **根因**（在 `game/src/battle_runtime_scene.cpp`，**X1 流独占**）：
  * `battle_unit_palette_slot_count = 12`（L6566）+ `unit_palette_slot(unit_id)`（L6568-6580）
    ⇒ **每个单位一个运行期调色板**（`bn::sprite_palette_ptr`，`create_new_palette()`）；
  * L6904-6969：换人时走 `else` 分支，`sprite_state.outline_palette` 是**单位级**标志，
    第 0 个 component 会 `sprite->set_palette(item->palette_item())` 把 sprite 上的运行期调色板引用丢掉，
    **但同一单位的其余 component 的 `had_outline_palette` 已经是 false、`binding_changed` 也是 false
    ⇒ 它们继续持有运行期调色板 ⇒ 调色板不释放**；
  * ⇒ **每访问一个新单位泄漏一个硬件 sprite 调色板 bank**。GBA 只有 16 个 ⇒
    9 个单位调色板 + UI 的调色板（panel / bar / status_panel / dimmed_unit / action icon / turn banner …）
    正好顶到上限 ⇒ `create_bpp_4` 失败。
  * 这也解释了 WAVE5-TASKS §5 里 W1 记的那条「Butano 只有 16 个硬件 sprite 调色板 bank ⇒
    「每单位一份调色板」会崩」：那个既有缺陷一直存在，只是**在 B5 之前玩家的游标到不了蜜蜂**，
    最多只碰 4 个我方单位，撑不满 16 个 bank。
* **建议的修法**（在 X1 的文件里，本流**没有改**）：
  * 方向：让**每个 component** 都把运行期调色板还回去，而不是只让第 0 个 component 还
    （把 `outline_palette` 标志下沉到 `battle_unit_sprite_state::components[]`，或在 `else` 分支里
    无条件 `sprite->set_palette(item->palette_item())`）；
  * 修完的判据：`python tools/s49_x3_boundary/check_rom_smoke.py --label romA-r8 --rom … --keys Down,Down,A×16,R×8`
    ⇒ 必须 `RESULT: no error screen`；
  * 或者：把「每单位一份调色板」改成「**只有行动中的单位**有一份」——注释里原本就是这么设计的
    （L6561-6565「the runtime palette is handed to that unit and taken back from the unit that held it before」），
    现在的 12 槽实现把这个设计做成了「每单位一份」。
* **对出包的影响**：**B5 在这个修好之前不能进包**。规范走位（`Down,Down,A×32`）不崩，
  但玩家按 R 就会崩。

### 5.2 非阻塞的观察（留给 X1 / 父代理，本流未改）

* **重制侧的状态栏没有画蜜蜂的名字**：原版蜜蜂行的名字格是红色的「蜜蜂」（W4 §6 B5），
  重制侧对应的那一行**名字格是空的**（气条 697、平行空、查克拉空、计数 0 —— 其余全对）。
  名字的绘制在 `battle_runtime_scene.cpp` 的状态栏渲染里（X1 的文件）。
* **重制侧的「待機」字颜色**：原版全红；重制侧大多是紫色（`(115,33,255)`），只有一行是红的。

### 5.3 明确不做：B2（渲染终止条件）

* 原版只认 −1 ⇒ 越界多画 3 个 component；重制运行期是编译期定长 5 槽 + `visible` ⇒ 不越界。
* **该角色不在 S49 出场 ⇒ S49 像素无影响** ⇒ 按 WAVE5-TASKS §0.5 列为「非 S49 项」，本波**不做**。
* 备注：若将来要照抄，缺口在 `battle_unit_visual_frame::components[5]` 的运行期数据模型
  （W4 §6 B2/B3），**不在本流独占范围**。

---

## 6. 本流新增 / 改动的文件

### 6.1 重制线

**本流没有留下任何新的重制线改动**：上一任的那几个文件经实测全部保留原样。
唯一的例外是 `battle_session.h` 在 A/B 实验期间被**临时**改过一行（撤销 B5 造 ROM_B），
**已改回并重建**（重建后的 ROM sha256 与改前完全相同 ⇒ 字节可复现）。

| 路径 | 状态 |
|---|---|
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_session.h` | 上一任的改动，**本流验证后保留**（B5 跨阵营） |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_campaign_sram.h` | 上一任的改动，**本流验证后保留** |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_campaign_sram.cpp` | 上一任的改动，**本流验证后保留** |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\src\main.cpp` | 上一任的改动，**本流验证后保留**（本流为探针 ROM 临时加过一段，**已还原**，diff 与上一任完全一致） |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\tests\test_battle_roster_cross_side.cpp` | 上一任的新测试，**绿** |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\tests\test_battle_campaign_sram_trigger.cpp` | 上一任的新测试，**绿** |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\tests\test_battle_roster_scheduler.cpp` | 上一任改的 5 行，**绿** |

### 6.2 本流新增（都在本流独占目录）

| 路径 | 说明 |
|---|---|
| `D:\Github\gba-naruto\tools\s49_x3_boundary\check_b5_rotation.py` | **重写**：B5 的像素级判据（原版 marker + 双方状态栏气条像素数 + 不带 B5 的对照） |
| `D:\Github\gba-naruto\tools\s49_x3_boundary\walkrec.py` | 走位录制 / 错误屏检测 / 状态栏量测的共用件 |
| `D:\Github\gba-naruto\tools\s49_x3_boundary\check_rom_smoke.py` | ROM 不崩门禁（走位 → 有没有落到 Butano 错误屏） |
| `D:\Github\gba-naruto\tools\s49_x3_boundary\check_b7_runtime.py` | B7 的运行时门禁（探针 ROM vs 出厂 ROM 的 SRAM 逐字节比） |
| `D:\Github\gba-naruto\tools\s49_x3_boundary\run_unit_ratchet.sh` | 单测棘轮（HEAD 基线 vs 工作区，失败集合逐名比） |
| `D:\Github\gba-naruto\tools\s49_x3_boundary\inspect_status_bar.py` | 状态栏条带拼图（人工核对用的小工具） |
| `D:\Github\gba-naruto\notes\s49-fidelity\X3-boundary-fixes.md` | 本文件 |

---

## 7. 复跑

```powershell
cd D:\Github\gba-naruto
$env:PYTHONIOENCODING='utf-8'

# 0) 私有探针（不要覆盖共享的 build/mgba-probe）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-x3r'
python tools/mgba_probe/build.py

# 1) 构建（WSL，必须显式导出 LIBBUTANOABS）
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 2) 单测棘轮（需要先抽 HEAD 基线，见 §8）
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/tools/s49_x3_boundary/run_unit_ratchet.sh

# 3) B5 像素判据（会自己录两条轮转走位；--no-record 复用）
python tools/s49_x3_boundary/check_b5_rotation.py

# 4) B7 运行时判据（需要 build/s49-x3-boundary/roms/rom-probe-b7.gba）
python tools/s49_x3_boundary/check_b7_runtime.py

# 5) ROM 不崩门禁
python tools/s49_x3_boundary/check_rom_smoke.py --label canonA --keys "Down,Down,A×32"
python tools/s49_x3_boundary/check_rom_smoke.py --label romA-r8 --rom build/s49-x3-boundary/roms/rom-A2-with-b5.gba --keys "Down,Down,A×16,R×8"

# 6) W4 存档门禁（只读复用，不要改 W4 的工具）
python tools/s49_save_boundary/run_all.py --repeat 2
```

---

## 8. 确认

* 新写文件一律 **LF、无 BOM**（`tools/s49_x3_boundary/*.py`、`*.sh`、本文件）。
* **未提交 git**（master 仓与重制线都没有 `git commit` / `git push`）。
* **未改 `battle_runtime_scene.cpp`**（X1 独占）、**未改** `battle_range_ui_style.h` /
  `battle_map_content.h` / `grid_pathfinder.h` / `battle_unit_palette_stream.h` /
  `battle_unit_visual_animation.h` / `battle_visual_resource_coordinator.h`。
* **未改** `tools/s49_save_boundary/` / `tools/s49_fidelity_report.py` / `tools/s49_logic_checks/`
  / `tools/s49_victory_capture/`（只读复用）。
* **逆向线 `D:\Shell\Github\gba-naruto-reverse` 全程只读**。
* **未覆盖共享探针** `build/mgba-probe/mgba-probe.exe`（本流私有探针在 `build/mgba-probe-x3r`）。
* **没有用 `git stash`**（wave 5 的其它子代理正在同一棵树上工作）；HEAD 基线用
  `git archive HEAD butano-sequel/game` 抽到 `build/head-baseline/`（只读）。
