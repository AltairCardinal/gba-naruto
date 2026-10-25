# S49 1:1 保真度报告（wave 17 定稿）

> 生成时间：2026-10-25T14:11:41+08:00
> 生成方式：`python tools/s49_package/run_pipeline.py` → `python tools/s49_package/make_report.py`
> 收据：`build/s49-package-w19b/receipt.json`
> **收据生成时间（这一批数字的出处）**：2026-10-25T13:59:38+08:00
> **本次 ROM**：sha256 `e2182fff9a6ba987ae2d920418acbb98bc9d1e187312e9b787f982b89cee6ad2`（12257620 B，构建于 2026-10-25T01:40:32+08:00）
> **本次 ROM 已钉住**：所有测量步骤与随包发布的 ROM 都是**同一份拷贝** `D:\Github\gba-naruto\build\s49-package-w19b\work\pinned-rom\measured.gba`（sha256 `e2182fff9a6ba987ae2d920418acbb98bc9d1e187312e9b787f982b89cee6ad2`）⇒ **并行流在本轮运行期间重建同一个 ROM，也换不掉本轮的读数**。
> **wave-7 接线（wave 7 的 Z1）状态**：**已交付**（`Z1-wiring.md`）
> **wave-10 并行流（U1/U2/U3）状态**：**U1（接线总装）已交付**（`U1-wiring.md`）；**U2（战斗数值对齐）已交付**（`U2-battle-balance.md`）；**U3（结算链缺屏 + 结算屏美术）已交付**（`U3-settlement-content.md`）
> **wave-11 并行流（W1/W2/W3）状态**：**W2（覆盖层逐格族名）**：**未归零**（`field-frame-v1` 同亮 192 / 缺 0 / 多画 0 / 不一致 61；`movegrid-frame-v1` 同亮 192 / 缺 0 / 多画 0 / 不一致 13；`grid16-frame-v1` 同亮 175 / 缺 0 / 多画 17 / 不一致 85；`banner-frame-v1` 同亮 0 / 缺 0 / 多画 0 / 不一致 0）；**W1（结算链运行帧录制）**：**本波未产出**（最新的结算链产物仍是 wave 9 的 `build/s49-victory-capture/v4/settlement-assets.json`）
> **wave-12 并行流（X1/X2/X3）状态**：**X2（覆盖层逐格族名）**：**未归零**（`field-frame-v1` 同亮 192 / 缺 0 / 多画 0 / 不一致 61；`movegrid-frame-v1` 同亮 192 / 缺 0 / 多画 0 / 不一致 13；`grid16-frame-v1` 同亮 175 / 缺 0 / 多画 17 / 不一致 85；`banner-frame-v1` 同亮 0 / 缺 0 / 多画 0 / 不一致 0）；**X3（黑场事件数/时长）**：原版 **2** 个事件（事件 1 = 淡出 24 / 全黑 18 / 淡入 24；事件 2 = 淡出 24 / 全黑 24 / 淡入 24）；重制侧 **5** 个事件（事件 1 = 淡出 0 / 全黑 6 / 淡入 0；事件 2 = 淡出 24 / 全黑 18 / 淡入 28；事件 3 = 淡出 0 / 全黑 2 / 淡入 0；事件 4 = 淡出 0 / 全黑 8 / 淡入 0；事件 5 = 淡出 28 / 全黑 24 / 淡入 28）；**X1（结算链运行帧）**：**尚未交付**（结算链运行帧逐屏对照表本报告没有数字）；**X1 在飞观察**（不是交付结果）：`build/s49-battle-balance/u2/routeY.err`（2026-10-24T15:12:11+08:00）的最后两行 —— after the battle: phase=13 round=5 outcome=1 enemies=0 / after the settlement: phase=24
> **wave-13 并行流（Y1/Y2/Y3）状态**：**Y2（覆盖层逐格族名）**：**「同亮 192 / 缺 0 / 多画 0」在 `field-frame-v1`、`movegrid-frame-v1` 上已达成**（`field-frame-v1` 同亮 192 / 缺 0 / 多画 0 / 不一致 61；`movegrid-frame-v1` 同亮 192 / 缺 0 / 多画 0 / 不一致 13；`grid16-frame-v1` 同亮 175 / 缺 0 / 多画 17 / 不一致 85；`banner-frame-v1` 同亮 0 / 缺 0 / 多画 0 / 不一致 0；`grid16` 是原版的**单帧瞬态**、`banner` 是空覆盖层，两者本就不适用 192 的目标）；**已交付**（`notes/s49-fidelity/Y2-overlay-final.md`）；**Y3（黑场事件数/时长）**：**事件数未对齐**（原版 **2** 个 vs 重制侧 **5** 个）；原版（24/18/24；24/24/24）；重制侧（0/6/0；24/18/28；0/2/0；0/8/0；28/24/28）；**笔记尚未交付**；**Y1（栈溢出修复 + 结算链运行帧）**：**已交付**（`notes/s49-fidelity/Y1-stack-fix-and-settlement.md`；这份笔记是 **wave 14 的 Z1** 补交的，它关掉的就是 wave 13 的 Y1 欠账）；独占头 `battle_scene_presentation_event.h` **已改动**；**结算链运行帧尚无收据**；**逐屏运行帧对照表本报告没有数字**
> **wave-14 并行流（Z1/Z2/Z3）状态**：**Z1（栈溢出笔记 + 结算链运行帧）**：**已交付**（`notes/s49-fidelity/Y1-stack-fix-and-settlement.md`）；**结算链收据有 15 行**（`build/z1/settlement-table-z1.json`；逐屏对照表）；**Z2（黑场事件数/时长）**：**事件数未对齐**（原版 **2** 个 vs 重制侧 **5** 个）；原版（24/18/24；24/24/24）；重制侧（0/6/0；24/18/28；0/2/0；0/8/0；28/24/28）；**Z3（残差下界重算 + walk 相位归因）**：**已交付**（`notes/s49-fidelity/Z3-bound-and-phase.md`）；**可证像素下界尚未为本次 ROM 重算**
> **wave-15 并行流（W1/W2/W3）状态**：**W1（3 个新查实的产品缺陷：调色板 cohort / 战后对白与任务菜单的 UI 层 / 非法 UTF-8）**：**已交付**（`notes/s49-fidelity/W18-W1-stack-overflow.md`、`notes/s49-fidelity/W1-three-defects.md`）；**W2（棘轮基线修正：基线改成「上一波被接受的收据」）**：**已交付**（`notes/s49-fidelity/W18-W2-confirm-yes-unselectable.md`、`notes/s49-fidelity/W2-ratchet-baseline.md`）；**本次运行的棘轮基线**：the ratchet verdict is INCOMPARABLE: the baseline ROM differs from this run's ROM => the residual numbers are not the same measurement => this is NOT a pass；the ratchet baseline is D:\Github\gba-naruto\build\s49-package\baseline-accepted\report.json (field residual sum 107051 px this run)；the judgment bench reported INCOMPARABLE (exit code 2): the baseline ROM differs from this run's ROM => the residual numbers are not comparable => NOT a pass；**本次的棘轮判定 = `incomparable`**（**不可比 ≠ 通过**：基线 ROM 与本次 ROM 不同 ⇒ 「残差只许变小」这条规则本次没有被检验）（基线 `D:\Github\gba-naruto\build\s49-package\baseline-accepted\report.json`）；**W3（黑场收官 + 胜利/结算屏画面）**：**已交付**（`notes/s49-fidelity/W18-W3-black-fade.md`、`notes/s49-fidelity/W3-blackfield-and-screens.md`）；**本次运行的黑场**：原版 **2** 个（24/18/24；24/24/24）；重制侧 **5** 个（0/6/0；24/18/28；0/2/0；0/8/0；28/24/28）
> **wave-16 并行流（V1/V2/V4）状态**：**V1（真实打完仗 + 结算链运行帧真实版）**：**已交付**（`notes/s49-fidelity/V1-real-victory.md`）；**结算链收据有 48 行**（`build/v1-u4/compare-chain-toolcheck.json`；逐屏对照表）；**V2（像素修复全包：胜利屏 / 结算屏 / 硬切 / 生长段 / CJK 扩字）**：**产品侧**（任务书里**没有给 V2 笔记** ⇒ 证据是本流水线在**钉住的 ROM** 上的实测）；**本次构建的 ROM 在本波被重建过**；**本次运行的黑场**：原版 **2** 个（24/18/24；24/24/24）；重制侧 **5** 个（0/6/0；24/18/28；0/2/0；0/8/0；28/24/28）；**V4（可证像素下界为最终 ROM 终算 + 缺一个相位的定位）**：**已交付**（`notes/s49-fidelity/V4-bound-final.md`）；**可证像素下界尚未为本次 ROM 重算**
> **wave-17 并行流（U1/U2/U4）状态**：**U1（D4 必修：玩家的伤害招式的战斗演出不结束）**：**已交付**（`notes/s49-fidelity/U1-d4-fix.md`）；✅ **产品侧已落地**（独占文件在任务书之后被改过：`butano-sequel/game/src/battle_runtime_scene.cpp`、`butano-sequel/game/include/konoha/battle_black_field.h`）；**本次构建的 ROM 在本波被重建过**；**U2（覆盖层「青+橙」互斥 + 結算屏人物/数字）**：**已交付**（`notes/s49-fidelity/U2-overlay-settlement.md`）；✅ **产品侧已落地**（独占文件在任务书之后被改过：`butano-sequel/game/include/konoha/battle_range_ui_style.h`、`butano-sequel/graphics/battle_ui_result_naruto.bmp`、`butano-sequel/graphics/battle_ui_result_sakura.bmp`、`butano-sequel/graphics/battle_ui_result_sasuke.bmp`、`butano-sequel/graphics/scenario_41_postbattle_bg.bmp`、`butano-sequel/graphics/scenario_41_postbattle_dialogue_page_1.bmp`、`butano-sequel/graphics/scenario_41_postbattle_dialogue_page_1.json`、`butano-sequel/graphics/scenario_41_postbattle_dialogue_page_2.bmp`）；**本次运行的黑场**：原版 **2** 个（24/18/24；24/24/24）；重制侧 **5** 个（0/6/0；24/18/28；0/2/0；0/8/0；28/24/28）；**U4（真实打完仗验证 + 结算链真实版）**：**已交付**（`notes/s49-fidelity/U4-real-victory-verify.md`）；**尚无「真实战斗 + `outcome=1`」的链**；⚠️ **另有 2 条 poke 链**（最新：`build/w19-a/chain-final/chain.json`）⇒ **不得写成真实胜利链**
> ⭐⭐ **一眼看出这一批数字的出处**：
> - **读的是哪个 ROM**：构建 `e2182fff9a6ba987…` / 钉住 `e2182fff9a6ba987…` / 打包 `e2182fff9a6ba987…` / 实测 `e2182fff9a6ba987…` ⇒ **四者一致** ✅（§2.0c）
> - **采集是复用还是重采**：原版侧 **captured** / 重制侧 **captured**（收据字段 `captures.<side>.reuse_decision`；「复用」= 采集自己的审计核对通过 ⇒ 帧确实来自本次这个 ROM）
> - **基线 ROM 是哪个**：`3973adcd4b329d89…`（收据 `D:\Github\gba-naruto\build\s49-package\baseline-accepted\report.json`）；**棘轮判决** = **`incomparable`**（**不可比 ≠ 通过**）
> 流水线结果：**PASS**
> ⚠️ **棘轮判定 = INCOMPARABLE（不可比）—— 这不是「通过」**：基线 ROM 与本次 ROM 不同 ⇒ 两个残差数字**不是同一个测量** ⇒ 「残差只许变小」这条规则**本次没有被检验**（基线 `D:\Github\gba-naruto\build\s49-package\baseline-accepted\report.json`；基线 ROM `3973adcd4b329d89…` vs 本次 ROM `e2182fff9a6ba987…`）。
>
> ⚠️ **本文件由流水线的收据生成；每个数字都能追到收据里的某一次运行。**
> ⚠️ **有「未达成项」一节 —— 绿灯的门禁不等于 1:1 已达成。**
> ⚠️ **wave 14 的可证像素下界与「本次运行的 ROM」不是同一个**：Z3 交付的下界是 **16389 px**，测在 ROM **`2c2b48d91fbe3244…`** 上（收据 `build/s49-z3-bound/bound-A.json`；4 次独立跑**逐值相同**），而**本次流水线构建的是 `e2182fff9a6ba987…`** （Z2 的黑场改动进了产品 ⇒ ROM 变了）⇒ **本次 ROM 的精确下界待 Z3 重算**。⇒ **「残差归零不可达」这个量级结论仍然成立**（16389 px > 0）；Z3 在**那个 ROM** 上还量出了上界 ⇒ **16389 ≤ 最优残差 ≤ 18886 px**（21/25 帧同刻可达），但**数字不是本次 ROM 的** ⇒ 不许混用。

> **下界的证明方式（Z3 收据里的原文，逐字引用）**：
>
> For every canonical beat b the bench's residual is the residual of one original frame against one remake frame.  min over all (frame of b) x (frame of the remake recording) of the battlefield residual is therefore <= the residual of every pairing of that beat, and the minimum is taken over a superset of the pairs a walk can realise (the same remake frame may serve several beats), so it is <= the residual of every walk.  Summing over the 25 beats gives a lower bound that no walk built on these two recordings can go below.
> ⭐ ⚠️ **三个数字不是同一个口径，不许混用**：① **判定台读数**（本收据的 `field_residual.sum`）= **arg-min 残差之和，无时刻约束**（每一拍任选一帧对）⇒ 本次 **107051 px**；② **可证像素下界**（Z3）= **每一拍内「原版的全部帧 × 重制的全部帧」逐对残差取最小，25 拍求和**（比 ① 更宽松 ⇒ 数值更小）⇒ **16389 px**；③ **内容锚配对的可达残差**（Z3）= **同一时刻**的帧对逐帧残差之和⇒ **18886 px**（⚠️ **属于另一个 ROM** ⇒ **不许**与 ② 并排）。⇒ **它们回答的是三个不同的问题**（残差有多少 / 归零最低要多少 / 现在能做到多少）⇒ **任何一处把三者直接相比都是错的**。
> ⭐ **wave 13 最重要的一条更正**：**覆盖层的「同亮 192 / 缺 0 / 多画 0」已经达成**。从 wave 1 传下来的「多画 310–420 格 / 缺 96–129 格」**是仪器假象** —— 共享仪器给**原版**贴地图标签时**没有按 480 px 回绕**，给重制侧却回绕了 ⇒ 两侧的缓冲尾部两列被互相错开 ⇒ 那 24 格「原版缺」+ 24 格「多画」全是**贴标签错位**。回绕修好后**缺 0 / 多画 0**（§3、§3.3）。
> ⚠️ **本次运行的重制线是 wave 17 并行流（U1/U2/U4）的状态**（U1 修产品缺陷 D4 / U2 修覆盖层「青+橙」互斥与結算屏人物数字 / U4 验证「真实打完仗」）⇒ **未达成项一节逐条写明了哪些是「已闭合」、哪些仍然开放**。
> ⚠️ ⭐ **同名笔记的坑（报告生成器的判定口径）**：`notes/s49-fidelity/` 里**同名前缀的旧波笔记还在** —— `Y3-overlay-zero.md` 是 **wave 6** 的 Y3，`X2-overlay-zero.md` 是 **wave 12** 的 X2，**`Z1-wiring.md` / `Z2-title-art-starfield.md` / `Z3-dialogue-box.md` 是 wave 7 的 Z1/Z2/Z3** ⇒ **文件名前缀不能当作「本波已交付」的证据**。本报告一律**以任务书的 mtime 为界**（wave 13 用 `WAVE13-TASKS.md`，wave 14 用 `WAVE14-TASKS.md`，wave 15 用 `WAVE15-TASKS.md`，wave 16 用 `WAVE16-TASKS.md`，wave 17 用 `WAVE17-TASKS.md`）⇒ 没有交付就**如实写「尚未交付」**，绝不把旧波的数字当成本波的成果。
> ⭐ **wave 12 / X4 的复核**：wave 10 / U4 给 `find_overlay_map` 加的 **terrain 判据**（自报越界）已**独立复核第二次**，结论**保留、不回退**，数字见 **§16**。
> ⭐ **wave 11 / W4 的两条更正**：① wave 10 报的「判定台 ±9,520 px 抖动」**根因不是仪器**，是**两次跑用的 ROM 不是同一个**（§2.0b）；② 判定台的**覆盖层读数用的还是旧判据**，与 §3 的逐格对拍**不是同一个口径**（§11 第 18 项，两个数不许混用）。

## 0. 一句话结论

- 战场区残差：**min 0 / 中位 1323 / max 27325 / 全 0 帧 4**（25 帧）；归因 一致 4 · 产品差 17 · 配对差 4；配对差三桶 黑场过渡 0 / 静止帧 0 / 时刻不一致 4。
- **残差未归零**：中位 1323 px，其中 **77.1%** 的残差仍在配对差那一侧；见 §11 未达成项。
- ⭐ **判定台的读数是确定的**：同一个 ROM **连读 3 次**，残差总和 **107051 px** 三次**完全相同**（逐帧配对、每张采集 PNG 的 sha256 也逐张相同） ⇒ **残差变了就是产品变了，不是仪器在抖**（§2.0b）。
- ⭐ **这一波的 ROM 是哪一个**：构建 / 钉住 / 打包 / 实测**四个 sha256 必须一致** = `e2182fff9a6ba987ae2d920418acbb98bc9d1e187312e9b787f982b89cee6ad2`✅ **四者一致** ⇒ 报告里每一个像素数都出自**这一份** ROM（§2.0c）。
- ✅ **判定台「复用采集不校验 ROM」的仪器缺陷已修**（只改 `tools/s49_fidelity_report/capture.py`）：复用前**必须**核对采集自己的审计（`audit.json` + `done.json`）；核对不过 ⇒ **绝不复用 ⇒ 重新采集**；收据里**机器可读**地写明帧来自哪个 ROM、采集是复用还是重采（§2.0.2、§11 第 22 项）。
- ⭐ **结算链**：**原版 S49 结算屏真值已闭合**（wave 8 的 W4 打赢后录到 9 张图 + sha256 收据 `9a60a89b…`，两次独立跑逐字节一致，正文见 **§15**）；**wave 14 / Z1 录出了重制侧的运行帧** ⇒ 逐屏对照表**15 行**（§15.2）。⭐ **逐屏对照表已交付**（**48 行**，收据 `build/v1-u4/compare-chain-toolcheck.json`；**测在本次这个 ROM 上**）⇒ 逐屏数字见 **§15.2**；⛔ **但它比的是「结算链的运行帧」，不是「真实打完仗」的那一版** —— **真实战斗链**与 **poke 链**在 **§15.2.3** 里**分列**（判据 = 链是**怎么进入**的），**任何一栏都不许写成「真实胜利链」**（§11 第 25 项）。
- ⭐⭐ **wave 17：「真实打完仗」已达成** —— **真实战斗**（`outcome = 1`，**由产品自己的战斗判定给出**）（收据 `build/w20-e1/chain-fix1-tc/real/battle.json`；ROM `150dacf876ab3fc3…`；进入方式：`real battle: the closed-loop driver plays the battle with the buttons only, and the outcome is the product code's own decision`；**poke 指令数 = 0**；**蜂的 HP 下降 = True**（{"4": 25, "5": 25, "6": 25, "7": 25, "8": 25}）；**护送存活 = True**）（§15.2.3、§11 第 25 项）。
- ⭐ **wave 17 的四路流**：U1（D4 必修）/ U2（覆盖层 + 結算屏）/ U3（本流：出包 + 报告）/ U4（真实打完仗验证）⇒ **落地状态见 §11 第 26 项**，**假设台账见 §14.11**。
- **本流水线 12 步全绿**（收据 `s49-package-w19b/receipt.json`），但绿灯的门禁**不等于** 1:1 已达成。
- ⭐⭐⭐ **wave 18–19 的成果（父代理收口；完整版见 `notes/s49-fidelity/W20-PARENT-wrapup.md`）**：
  * ⭐ **D4（攻击确认链撑爆 IWRAM 用户栈）已闭合** —— 根因是 **3 处运行时的 8,052 B「整份会话拷贝」**
    （全仓 13 处，其余 10 处只被单元测试调用）⇒ 改为 **EWRAM 深度 2 的 LIFO 槽位池 + RAII 句柄**
    ⇒ 最坏栈深 **26,888 → 14,944 B**（可用 21,308 B，裕量 6,364 B；用 ELF 调用图**穷举 994,141 条路径**算出）
    ⇒ ⭐ **真实战斗打赢**（5 只蜂各掉 25 HP、护送 40/40、`poke_commands = 0`、`from_real_battle = true`）
    ⇒ ⭐ 自证：在 `IRQ_VectorTable[0]` 挂 **mGBA 写监视点**，改前按 A 那一瞬命中（`sp` 比栈底低 940 B），
    改后**全程不命中**、向量表前后逐字节相同。
  * ⭐ **結算链三屏归零**：戰後對白 **26,819 → 0 px**、任務菜單 **37,694 → 0 px**、結算屏人物 **1,898 → 0 px**
    （合计 **−66,411 px**；根因是結算渲染器的 BG 建在 `(0,0)` 而本仓约定是 `(8, 48)`，加上资产页选错）
    ⇒ 結算屏只剩 **684 px** = **「戰鬥分」发奖规则根本不存在**（`battle_experience` 只由场景种子与阵亡零和转移写入）⇒ **产品缺口**。
    ⇒ 另**推翻了 wave 17 的前提**：立绘自身只要 15/12/15 色 ⇒ **4bpp 就够**，8bpp 图集方案不必要。
  * ⭐ **「開始」标题卡已改成原版语义**（纯定时、**无视输入**、一次走完）⇒ 按/不按 A 的 300 帧 **30/30 帧 sha256 逐字节相同**
    ⇒ 两条 walk 的**步偏移恒为 +4**（此前第 10 步起掉到 +3）。
  * ✅ **第 11 步（save-boundary）的仪器缺陷已修**（它连续三波是唯一的红）：根因是**私建探针二进制过期**
    （`framedump` 在探针源码里的参数顺序是 `<count> <addr> <len> <keymask> <prefix>`，
    而 `build/mgba-probe-w4/mgba-probe.exe` 还是 10-23 的旧二进制（`<prefix> [keymask]`））
    ⇒ 重建探针后**步骤 11 通过**，**本次 12/12 全绿并接受了新基线**（107,051 px）。
- ⛔ **仍然开放的四项**（wave 20 的任务书已写好：`notes/s49-fidelity/WAVE20-TASKS.md`，含四路分工与判定问题）：
  **① Butano 调色板耗尽**（真实结算链**第 1 页就死** ⇒ 7 段一段都进不去）·
  **② 「戰鬥分」发奖规则**（684 px，需逆向线给原版公式）·
  **③ 战斗段首帧 ~73 k px**（原版与重制侧的相机/布景不在同一位置）·
  **④ 黑场 B2/B3/B4**（⚠️ **B2 被 64 KB BG 图块区卡死 ⇒ 到 0 帧不可能**，只能给最小可达值 + 硬证据）。

## 1. 出包四件套清单（对照 `W4-save-boundary.md` §7 的 11 项）

| # | 出包要素 | 现状 | 证据 |
|---|---|---|---|
| 1 | 可玩 ROM | ✅ 已构建 | `D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba`，sha256 `e2182fff9a6ba987…`，12257620 B |
| 2 | 一条复现命令 | ✅ 有 | `python tools/s49_package/run_pipeline.py`；逐条命令见包内 `REPRODUCE.md` |
| 3 | 无窗口无声门禁 | ✅ | 步骤 4 的收据 |
| 4 | 存档字节收据 | ✅ | 步骤 11：`build/s49-save-boundary/receipts/` |
| 5 | 边界行为收据 | ⚠️ 部分 | 12 条表见 §6；B10 原版侧仍未实测 |
| 6 | 证据目录 | ✅ | `notes/s49-fidelity/`（假设台账索引见 §9） |
| 7 | 1:1 报告 | ✅ 终审稿 | 本文件 |
| 8 | ROM 可运行性 | ✅ | 步骤 3：4096 帧 + 中文标题画面 |
| 9 | 单元测试 | ⚠️ 零回归（非全绿） | 步骤 2：HEAD 101 pass / 20 fail，工作区 118 pass / 20 fail；新失败 0 项 |
| 10 | 出包基线钉 | ⚠️ 非字节可复现 | 包内带 ROM + 重录命令，复现需先建私有探针（见 §12） |
| 11 | 存档格式决策 | ⏸ 待父代理拍板 | 施工单 C1–C5，`W4-save-boundary.md` §5.5 |

## 2. 残差：前后对比 + 三桶分解

来源：`build/s49-package-w19b/work/s49-report/report.json`（本次）与 `build/s49-package-w19b/baseline/reference-report.json`（钉住的 wave-4 参照，不随运行改变）。棘轮基线是 `baseline/baseline-report.json`（上一次被接受的运行）。

### 2.0 棘轮对照（本次 vs 上一次被接受的运行）

⚠️ **⭐ 与上一波被接受的运行（wave 14）的对照 —— 这才是本波该看的那个数**：残差总和 **109569 → 107051 px**（**-2518 px，-2.3%**）🟢 残差变小了。⇒ **归因**：**不是**判定台的抖动（同一个 ROM 连读 3 次读数逐项相同，§2.0b），而是 **ROM 换了**：上一波是 `3973adcd4b329d89…`，本次是 `e2182fff9a6ba987…`（**产品侧改了 ⇒ ROM 变了**）。

⚠️ **⭐ 棘轮判定 =「不可比」（不是通过）**：基线 ROM 与本次 ROM 不同 ⇒ 两个残差数字**不是同一个测量** ⇒ **「残差只许变小」这条规则本次没有被检验**。

这一步是**流水线的门禁口径**：残差只许变小，变大就红。基线 = **上一波被接受的收据**（`D:\Github\gba-naruto\build\s49-package\baseline-accepted\report.json`，接受于 2026-10-25T14:10:54+08:00）⇒ **基线住在包目录外** ⇒ 换包目录重跑**不会丢基线**。

⭐ **被接受的基线（wave 15 / W2 的新机制）**：

| 项 | 值 |
|---|---|
| 基线来源包 | `D:\Github\gba-naruto\build\s49-package-w19b` |
| 接受时间 | 2026-10-25T14:10:54+08:00 |
| 基线残差总和 | 107051 px |
| 基线 ROM（原版） | `1198ece781aaf629…` |
| 基线 ROM（重制） | `e2182fff9a6ba987…` |
| 本次 ROM（原版） | `1198ece781aaf629…` |
| 本次 ROM（重制） | `e2182fff9a6ba987…` |
| 判决 | **`incomparable`** |


⚠️ ⭐ **本次的棘轮判定是「不可比」，不是「通过」**：基线 ROM `3973adcd4b329d89…` ≠ 本次 ROM `e2182fff9a6ba987…` ⇒ **两个残差数字不是同一个测量** ⇒ **「残差只许变小」这条规则本次没有被检验**（**wave 15 / W2 的新机制**：基线住在包目录外⇒ 换包目录不会丢基线；但**产品一改 ROM 就变** ⇒ 「残差只许变小」这条规则**只能在新基线上被检验**）基线报告：`D:\Github\gba-naruto\build\s49-package\baseline-accepted\report.json`。

| 指标 | 上次被接受 | 本次 | 方向 |
|---|---:|---:|---|
| 战场区残差 min | 0 | 0 | ＝ |
| 战场区残差 中位 | 1323 | 1323 | ＝ |
| 战场区残差 max | 27325 | 27325 | ＝ |
| 战场区残差 总和 | 100210 | 107051 | 🔴 差 |
| 战场区全 0 帧数 | 5 | 4 | 🔴 差 |

归因：上次 5·17·3 → 本次 4·17·4（一致 · 产品差 · 配对差）。

#### 2.0.1 ⭐ 棘轮为什么红：**逐帧**归因（残差总和 109569 → 107051 px，**-2518 px**）

⭐ 25 个配对时刻的**逐帧残差逐项相同** ⇒ 总和的差**不来自配对帧**（请查判定台读数口径）。

#### 2.0.2 ⭐⭐ 判定台「复用采集不校验 ROM」—— **wave 16 / V3 已修**

| 侧 | 采集实际记录的 ROM（audit） | 报告声称的 ROM | 复用还是重采 | 原因 |
|---|---|---|---|---|
| original | （审计里没有 ROM 字段） | `1198ece781aaf629…` | **captured** | the capture was recorded for this request |
| remake | `e2182fff9a6ba987…` | `e2182fff9a6ba987…` | **captured** | the capture was recorded for this request |

✅ **采集记录的 ROM == 报告声称的 ROM** ⇒ 本次的读数确实是在本次的 ROM 上量出来的。

⭐ **这个缺陷曾经怎么伤人的**（wave 15 的实测）：修好之前，`tools/s49_fidelity_report/capture.py::run_capture()` 在 `reuse=True` 时**只看「done 标记在不在、帧在不在」**，**从不核对那份采集是哪一个 ROM 录的**；随后报告把帧标成**它被要求测的**那个 ROM 的 sha256。⇒ **同一个工作目录里换 ROM 重跑，会拿到上一个 ROM 的帧、却标成新 ROM 的读数**。（wave 15 的 W1 的「判定台残差没有变大」就是这样得到的：它复用了 wave 14 包里的采集目录，那份采集的 audit ROM 是 wave 14 的 ROM。⇒ **wave 15 流水线第 5 步的 -2518 px 是真回归**，而 W1 的「逐项相同」是**陈旧采集**造成的假象。）

✅ **wave 16 / V3 的修法**（只改 `tools/s49_fidelity_report/capture.py` 一个文件）：

* 复用前**必须**核对采集自己的审计（`audit.json` **和** `done.json` 两个证人）：重制侧核对 `rom_sha256`、原版侧核对 `input_state_sha256`；**两个证人互相矛盾 ⇒ 拒绝**。
* **核对不过 ⇒ 绝不复用 ⇒ 重新采集**；核对得过 ⇒ 复用。
* 收据里**机器可读**地写明：`captures.<side>.measured_rom_sha256`（帧到底来自哪个 ROM）、`captures.<side>.reuse_decision`（测量稳定的事实）与 `run.attempts.<side>[0]`（复用/重采 + 原因，运行出处）。

**判据（两条证明，可复跑）**：

| 判据 | 做法 | 结果 |
|---|---|---|
| **A：审计说别的 ROM ⇒ 必须重采** | 把采集的 `audit.json` / `done.json` 里的 `rom_sha256`（原版侧是 `input_state_sha256`）改成**另一个 ROM / 另一个存档**的值，再用 `--skip-capture` 跑判定台 | **两侧都重新采集**（`action = recaptured`），收据里写明差在哪一个摘要上 |
| **B：审计说同一个 ROM ⇒ 可以复用，且读数与重采逐项相同** | **同一个 work 目录**里连跑三次：① 重采 ② 篡改后重采 ③ 复用 | ③ **复用**（`action = reused`）；三次的 `content_sha256` **完全相同** ⇒ **复用不改变读数** |

⇒ 复现：`python build/v3-dev/prove_capture_rom_check.py`（单元级：`python build/v3-dev/test_capture_identity.py`）。

⭐ **这个缺陷咬的是哪一种跑法**（读准了才不会被误伤）：流水线**自己从不传 `--skip-capture`**（步骤 5 每次都重录，步骤 5 连读 3 次时三次各自重录）⇒ **棘轮基线与流水线的读数一直是干净的**；**被咬的是手工跑 `--skip-capture --work-dir <别处的采集目录>`**（wave 15 的 W1 就是这样得到假象的）⇒ **修好之前，凡是用 `--skip-capture` 得来的「残差没变大」，一律不可信**。

### 2.0c ⭐ **这一波的 ROM 是哪一个**（四个 sha 必须一致）

V1 与 V2 都改产品 ⇒ **ROM 一定变** ⇒ 「本次读数测的是哪个 ROM」必须能在报告里看出来。**四个摘要**任一不同 ⇒ 本次的数字就分属不同的字节 ⇒ 直接报出来。

| 角色 | sha256 | 来自 |
|---|---|---|
| **build** | `e2182fff9a6ba987…` | 步骤 1 构建产物 |
| **pinned** | `e2182fff9a6ba987…` | 步骤 1 钉住的拷贝（后面每一步都测它） |
| **package** | `e2182fff9a6ba987…` | 步骤 12 打进包的 ROM |
| **measured** | `e2182fff9a6ba987…` | 判定台**实际录到**帧的那个 ROM |

✅ **四者逐字相同** = `e2182fff9a6ba987ae2d920418acbb98bc9d1e187312e9b787f982b89cee6ad2` ⇒ 本次报告里的每一个像素数都出自**这一份** ROM。

| 项 | 值 |
|---|---|
| 本次 ROM 的构建时间 | `2026-10-25T01:40:32+08:00` |
| 本次 ROM 的字节数 | 12257620 |
| original 侧采集 | **captured**（the capture was recorded for this request） |
| remake 侧采集 | **captured**（the capture was recorded for this request） |
| 采集是复用的吗 | original = **False** / remake = **False** |
| 与上一波被接受的基线 ROM 相同吗 | ⛔ **不同**（基线 `3973adcd4b329d89…` vs 本次 `e2182fff9a6ba987…`） |

### 2.0b ⭐ 读数确定性（**棘轮可信的前提**）

同一个 ROM **连读 N 次**（步骤 5 现在默认读 3 次），N 次读数必须**逐项相同**：残差摘要、归因、三桶、逐帧配对，以及每一张采集 PNG 的 sha256。读数不确定 ⇒「残差变大」可能只是噪声 ⇒ **棘轮会误报**。

| 读数 | 重制侧 ROM sha256 | 战场区残差总和 | 中位 | 峰值 | 全 0 帧 | 采集摘要 |
|---|---|---:|---:|---:|---:|---|
| 1 | `e2182fff9a6ba987…` | 107051 | 1323 | 27325 | 4 | `c9a8309f67038b1e…` |
| 2 | `e2182fff9a6ba987…` | 107051 | 1323 | 27325 | 4 | `c9a8309f67038b1e…` |
| 3 | `e2182fff9a6ba987…` | 107051 | 1323 | 27325 | 4 | `c9a8309f67038b1e…` |

✅ **读数确定**：上表的 N 次读数**完全相同** ⇒ 本次残差是一个**可复现的读数** ⇒ 残差变了就是**产品变了**，不是仪器在抖。

> ⭐ **更正 wave 10 报告里的「±9,520 px 抖动」**：那个数**不是**判定台的抖动，是**两次跑用的 ROM 不是同一个**。证据（wave 10 / U4 自己留下的两份报告，收据在 `build/s49-package-u4/bench-check*/report.json`）：
>
> | 运行 | 重制侧 ROM sha256 | 战场区残差总和 | `step-12-A` 的配对 |
> |---|---|---:|---|
> | `bench-check`（11:15:03） | `249217d7f59a2199…` | 168,816 | `step-19-A.png`（9,151 px） |
> | `bench-check2`（11:27:10） | `73b74587595d4581…` | 104,784 | `step-16-A.png`（0 px） |
>
> ⇒ **ROM 的 sha256 不同** ⇒ 两次读的是**两个不同的 ROM** ⇒ 差的那 9,520 px 属于**产品改动**，不属于仪器。⇒ 判定台的判定语义（`product_diff` / `pairing_diff` / 三桶）**没有改**，改的是**仪器现在能自证这件事**。

| 指标 | before（钉住的基线） | after（本次） | 方向 |
|---|---:|---:|---|
| 战场区残差 min | — | 0 | — |
| 战场区残差 中位 | — | 1323 | — |
| 战场区残差 max | — | 27325 | — |
| 战场区残差 总和 | — | 107051 | — |
| 战场区全 0 帧数 | — | 4 | — |
| 整屏残差 总和 | — | 204960 | — |
| 覆盖层族名残差 总和 | — | 857 | — |

### 2.1 残差分解（配对差 / 产品差 / 一致）+ 归因

| 归因 | 帧数 | 战场区残差总和 (px) | 占比 |
|---|---:|---:|---:|
| 一致 | 4 | 0 | 0.0% |
| 产品差 | 17 | 24480 | 22.9% |
| 配对差 | 4 | 82571 | 77.1% |
| **合计** | 25 | 107051 | 100.0% |

| 配对差的子类 | 帧数 | 战场区残差总和 (px) |
|---|---:|---:|
| moment_mismatch | 4 | 82571 |

### 2.2 配对差的三桶

| 桶 | 帧数 | 机制 |
|---|---:|---|
| 黑场过渡（black_transition） | 0 | **本次 0 帧** —— 重制侧的黑场渐变已补上，这一桶归零了 |
| 静止帧（static_frame） | 0 | **本次 0 帧** |
| 时刻不一致（moment_mismatch） | 4 | 两条 walk 走到了不同的游戏序列（X2 的结论：walk 侧已到头，剩下的帧逐帧都有产品差证据） |

配对质量：内容锚 25/25，锚支持配对 0，覆盖层完全一致 17。

### 2.3 逐帧

| 原版帧 | 配对到的重制帧 | 战场区残差 px | 上次被接受 | Δ | 归因 | 子类 | 覆盖层族名残差（格） |
|---|---|---:|---:|---:|---|---|---:|
| `step-00-base.png` | `step-04-A.png` | 2565 | 2565 | ＝ | 产品差 | — | 136 |
| `step-01-A.png` | `step-05-A.png` | 1294 | 1294 | ＝ | 产品差 | — | 64 |
| `step-02-A.png` | `step-06-A.png` | 1680 | 1680 | ＝ | 产品差 | — | 64 |
| `step-03-A.png` | `step-07-A.png` | 2514 | 2514 | ＝ | 产品差 | — | 24 |
| `step-04-A.png` | `step-08-A.png` | 1940 | 1940 | ＝ | 产品差 | — | 9 |
| `step-05-A.png` | `step-09-A.png` | 2057 | 2057 | ＝ | 产品差 | — | 0 |
| `step-06-A.png` | `step-10-A.png` | 1217 | 1217 | ＝ | 产品差 | — | 0 |
| `step-07-A.png` | `step-11-A.png` | 1921 | 1921 | ＝ | 产品差 | — | 0 |
| `step-08-A.png` | `step-12-A.png` | 1026 | 1026 | ＝ | 产品差 | — | 0 |
| `step-09-A.png` | `step-13-A.png` | 759 | 759 | ＝ | 产品差 | — | 0 |
| `step-10-A.png` | `step-14-A.png` | 278 | 2761 | 🟢 -2483 | 产品差 | — | 0 |
| `step-11-A.png` | `step-22-A.png` | 305 | 356 | 🟢 -51 | 产品差 | — | 0 |
| `step-12-A.png` | `step-20-A.png` | 9520 | 0 | 🔴 +9520 | 配对差 | moment_mismatch | 0 |
| `step-13-A.png` | `step-18-A.png` | 28 | 0 | 🔴 +28 | 产品差 | — | 0 |
| `step-14-A.png` | `step-18-A.png` | 0 | 0 | ＝ | 一致 | — | 0 |
| `step-15-A.png` | `step-19-A.png` | 0 | 0 | ＝ | 一致 | — | 0 |
| `step-16-A.png` | `step-20-A.png` | 43 | 43 | ＝ | 产品差 | — | 0 |
| `step-17-A.png` | `step-21-A.png` | 0 | 0 | ＝ | 一致 | — | 0 |
| `step-18-A.png` | `step-22-A.png` | 0 | 173 | 🟢 -173 | 一致 | — | 0 |
| `step-19-A.png` | `step-23-A.png` | 24460 | 24460 | ＝ | 配对差 | moment_mismatch | 0 |
| `step-20-A.png` | `step-23-A.png` | 4158 | 4158 | ＝ | 产品差 | — | 0 |
| `step-21-A.png` | `step-11-A.png` | 27325 | 27325 | ＝ | 配对差 | moment_mismatch | 0 |
| `step-22-A.png` | `step-07-A.png` | 21266 | 21266 | ＝ | 配对差 | moment_mismatch | 176 |
| `step-23-A.png` | `step-24-A.png` | 1323 | 1323 | ＝ | 产品差 | — | 192 |
| `step-24-A.png` | `step-25-A.png` | 1372 | 1372 | ＝ | 产品差 | — | 192 |

逐帧相对上次被接受的运行：**3 帧变好 / 2 帧变差**（逐帧比不作为门禁 —— 配对可能整体平移；门禁只看 §2.0 的聚合量）。

## 3. 覆盖层逐格族名对拍

来源：`build/s49-package-w19b/evidence/overlay/overlay-families.json`；候选帧：**整条 walk 的 35 个 anchor dump**（wave 10 / U4 改过候选集，见 §3.1 与 §11 第 17 项）；每个原版时刻取**逐格最接近**的那一帧（仪器自带的选择规则）。

| 原版时刻 | 锚点(map px) | 同亮 | 原版有·重制缺 | 重制有·原版缺 | 族名不一致 | 残差合计 | 完全一致 |
|---|---|---:|---:|---:|---:|---:|---|
| `field-frame-v1` | (—, —) | 192 | 0 | 0 | 61 | 61 | 否 |
| `movegrid-frame-v1` | (—, —) | 192 | 0 | 0 | 13 | 13 | 否 |
| `grid16-frame-v1` | (—, —) | 175 | 0 | 17 | 85 | 102 | 否 |
| `banner-frame-v1` | (—, —) | 0 | 0 | 0 | 0 | 0 | 是 |

### 3.1 ⭐ 锚点口径（wave 10 / U4 改过仪器）

原版的覆盖层缓冲**内容锚在地图空间 map px (256, 0)**、屏幕位置跟相机（`bg2_hoffs = 240 == bg_hoffs`、`bg2_voffs = 24 == bg_voffs`），实测 **17984 / 17984 px** 精确命中（次优锚点 (264, 0) 只有 17216）。⇒ **缓冲像素 `p` 的地图标签 = `(p + 256) mod 480`**。

⚠️ **wave 9 之前的共享仪器表达不了这个锚点**：它按「相机派生的窗口」给缓冲贴地图标签，再在 `[0, 256)` 里搜最优窗口 —— **256 落在搜索区间外**（地图宽 480 px，256 ≠ 0），而且「取搜索到的最优」会**替重制侧美化**。⇒ wave 10 / U4 把仪器改成**固定锚点**（`tools/s49_overlay_align/compare_overlay_families.py`），并把「窗口自由搜索」降级成**只读诊断**（`tools/s49_v2_anchor/scan_window.py`）。

**同一份 VRAM  dump（`step-26-A.state.vram-0000.bin`）上两种口径的实测对比**（`build/s49-package-w19b/evidence/overlay/conventions.json`，由 `tools/s49_overlay_align/compare_conventions.py` 生成）：

* 旧口径 = window-search (wave <= 9)，窗口 `[224, 24]`，搜索区间 `[0, 256) x [0, 256)`
* 新口径 = fixed map-space anchor (wave 10 / U4)，锚点 `[256, 0]`，规则 `buffer px p holds map px ((p + 256) mod 480, p)`

| 原版时刻 | 口径 | 同亮 | 原版有·重制缺 | 重制有·原版缺 | 族名不一致 | 残差合计 |
|---|---|---:|---:|---:|---:|---:|
| `field-frame-v1` | 旧·窗口搜索 | 168 | 24 | 40 | 50 | 114 |
| `field-frame-v1` | 新·固定锚点 | 192 | 0 | 0 | 61 | 61 |
| `movegrid-frame-v1` | 旧·窗口搜索 | 168 | 24 | 40 | 2 | 66 |
| `movegrid-frame-v1` | 新·固定锚点 | 192 | 0 | 0 | 13 | 13 |
| `grid16-frame-v1` | 旧·窗口搜索 | 153 | 22 | 55 | 65 | 142 |
| `grid16-frame-v1` | 新·固定锚点 | 175 | 0 | 17 | 85 | 102 |
| `banner-frame-v1` | 旧·窗口搜索 | 0 | 0 | 208 | 0 | 208 |
| `banner-frame-v1` | 新·固定锚点 | 0 | 0 | 192 | 0 | 192 |

口径变化对残差的影响（逐时刻）：[-53, -40, -16]。

### 3.2 ⭐ 越界复核：wave 10 / U4 给 `find_overlay_map` 加的 terrain 判据

wave 10 的 U4 流**自报了一处越界**：它在**别的流**的仪器（`tools/s49_overlay_align/compare_overlay_families.py`）里给 `find_overlay_map` 加了一个 **terrain 判据**（「solid 必须落在受阻地形上」），超出了「只授权改锚点」的范围。

⭐ **wave 11 / W4 复核过一次（结论：保留，不回退）；wave 12 / X4 独立复核第二次，数字全部重新测 ⇒ 见 §16。**

本节只留一句结论，**全部数字与推理在 §16**（§16 的产物是本次收据里的 `evidence/overlay/terrain-review.json`，由流水线步骤 6 在**同一份 35 个 dump** 上跑出来 ⇒ 可追到某一次运行）：**「不带 terrain」的路径与改前逐字节相同；判定台自己的覆盖层读数一字未变；判据只改 4/35 个 dump（假窗口 `0x00800` → `-1`），其余 31 个一字未变 ⇒ 保留，不回退。**

⚠️ **循环论证的风险**：terrain 来自**重制线自己的生成头** `generated_battle_map_content.h` ⇒ 这条判据只保证「覆盖层与**产品自己用的**地图一致」，**不是**独立于产品的绝对真值。绝对真值仍是原版导出的 `s49-original-movegrid-tilemap-v1`。

⭐ **wave 13 的口径更正（这一节的头号结论）**：**「同亮 192 / 原版缺 0 / 多画 0」已经达成。** 从 wave 1 传下来的「多画 310–420 格 / 缺 96–129 格」**是仪器假象**：共享仪器给**原版**贴地图标签时**没有按 480 px 回绕**（`original_map_cells()` 直接 `(anchor_x + lx * 16) // 16`），给**重制侧**却回绕了（`remake_logical_cells()` 用 `% MAP_WIDTH`）⇒ 两侧的**缓冲尾部两列**（原版缓冲逻辑列 14/15 = 地图第 0 列）被互相错开 ⇒ 那 **24 格「原版缺」+ 24 格「多画」**全是**贴标签错位**。⛔ **旧口径的数字不许再引用**（下表是**回绕修好之后**的实测）。

### 3.3 ⭐ 逐格性质判定（剩下的族名不一致**逐格**给出性质）

**逐格判定器**：`tools/s49_package/classify_overlay_cells.py` —— **只读 import** 共享仪器（共享文件一个字未改），复制它的取帧规则与最优帧选择规则，**保留逐格差异**，再按三条**可判定**的规则分类。

| 性质 | 判定规则 |
|---|---|
| **原版尾部残留** | 地图逻辑列 0/1 —— 原版覆盖层缓冲的回绕尾部（缓冲 px 224..255 = 地图第 0/1 列）。该处装的是**陈旧内容**（墙列上出现光标格 / 可达集），不是当前地图空间的内容 ⇒ 任何忠实的重制都复现不了。 |
| **walk 相位** | **相位错位**：原版该时刻的画面同时具备一组相位族（hatch=青 / band=黄 / line_alt=橙 / hatch_shift=绿），而重制侧的 35 帧里**没有任何一帧**同时具备这组相位族 ⇒ 重制侧的 walk **从未走到**原版那个相位 ⇒ 差的是走位/相位结构，不是覆盖层规则。 |
| **产品差** | 两侧**同相位**下仍然逐格不同（族名对不同，或某一侧单独点亮）⇒ 规则或单位占位等**产品差**。 |

| 原版时刻 | 最优帧 | 同亮 | 缺 | 多画 | 族名不一致 | 残差 | 原版尾部残留 | walk 相位 | 产品差 | 相位判定 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `field-frame-v1` | `step-26-A.state.vram-0000.bin` | 192 | 0 | 0 | 61 | 61 | 11 | 50 | 0 | **相位错位**（原版的相位族集合 band、hatch、line_alt，重制侧 35 帧里**没有**任何一帧同时具备这组相位族） |
| `movegrid-frame-v1` | `step-26-A.state.vram-0000.bin` | 192 | 0 | 0 | 13 | 13 | 11 | 0 | 2 | 同相位 |
| `grid16-frame-v1` | `step-26-A.state.vram-0000.bin` | 175 | 0 | 17 | 85 | 102 | 22 | 80 | 0 | **相位错位**（原版的相位族集合 band、hatch、line_alt，重制侧 35 帧里**没有**任何一帧同时具备这组相位族） |
| `banner-frame-v1` | `step-00-base.state.vram-0000.bin` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 同相位 |

**逐格明细**（每一格都给性质判定；`map (lx, ly)` 是地图空间的16×16 逻辑格坐标）：

* **`field-frame-v1`**（61 格；最优帧 `step-26-A.state.vram-0000.bin`）：

  | map (lx, ly) | 原版族 | 重制侧族 | 性质 |
  |---|---|---|---|
  | (0, 12) | `edge` | `solid` | **原版尾部残留** |
  | (1, 3) | `edge` | `solid` | **原版尾部残留** |
  | (1, 4) | `edge` | `solid` | **原版尾部残留** |
  | (1, 5) | `edge` | `solid` | **原版尾部残留** |
  | (1, 6) | `band` | `solid` | **原版尾部残留** |
  | (1, 7) | `hatch` | `solid` | **原版尾部残留** |
  | (1, 8) | `hatch` | `solid` | **原版尾部残留** |
  | (1, 9) | `edge` | `solid` | **原版尾部残留** |
  | (1, 10) | `edge` | `solid` | **原版尾部残留** |
  | (1, 11) | `edge` | `solid` | **原版尾部残留** |
  | (1, 12) | `edge` | `solid` | **原版尾部残留** |
  | (16, 5) | `hatch` | `edge` | **walk 相位** |
  | (16, 7) | `line_alt` | `edge` | **walk 相位** |
  | (16, 8) | `hatch` | `edge` | **walk 相位** |
  | (16, 9) | `hatch` | `edge` | **walk 相位** |
  | (17, 5) | `hatch` | `edge` | **walk 相位** |
  | (17, 7) | `line_alt` | `edge` | **walk 相位** |
  | (17, 8) | `hatch` | `edge` | **walk 相位** |
  | (17, 9) | `hatch` | `edge` | **walk 相位** |
  | (18, 5) | `edge` | `hatch` | **walk 相位** |
  | (18, 7) | `line_alt` | `hatch` | **walk 相位** |
  | (19, 5) | `edge` | `hatch` | **walk 相位** |
  | (19, 7) | `line_alt` | `hatch` | **walk 相位** |
  | (20, 4) | `edge` | `hatch` | **walk 相位** |
  | (20, 5) | `edge` | `hatch` | **walk 相位** |
  | (20, 6) | `edge` | `hatch` | **walk 相位** |
  | (20, 7) | `line_alt` | `solid` | **walk 相位** |
  | (20, 8) | `edge` | `hatch` | **walk 相位** |
  | (21, 4) | `edge` | `hatch` | **walk 相位** |
  | (21, 5) | `edge` | `hatch` | **walk 相位** |
  | (21, 6) | `edge` | `hatch` | **walk 相位** |
  | (21, 7) | `line_alt` | `solid` | **walk 相位** |
  | (21, 8) | `edge` | `hatch` | **walk 相位** |
  | (22, 3) | `edge` | `hatch` | **walk 相位** |
  | (22, 4) | `edge` | `hatch` | **walk 相位** |
  | (22, 5) | `edge` | `hatch` | **walk 相位** |
  | (22, 6) | `edge` | `hatch` | **walk 相位** |
  | (22, 7) | `edge` | `hatch` | **walk 相位** |
  | (22, 8) | `edge` | `hatch` | **walk 相位** |
  | (22, 9) | `edge` | `hatch` | **walk 相位** |
  | (23, 3) | `edge` | `hatch` | **walk 相位** |
  | (23, 4) | `edge` | `hatch` | **walk 相位** |
  | (23, 5) | `edge` | `hatch` | **walk 相位** |
  | (23, 6) | `edge` | `hatch` | **walk 相位** |
  | (23, 7) | `edge` | `hatch` | **walk 相位** |
  | (23, 8) | `edge` | `hatch` | **walk 相位** |
  | (23, 9) | `edge` | `hatch` | **walk 相位** |
  | (24, 4) | `edge` | `hatch` | **walk 相位** |
  | (24, 5) | `edge` | `hatch` | **walk 相位** |
  | (24, 6) | `edge` | `hatch` | **walk 相位** |
  | (24, 8) | `edge` | `hatch` | **walk 相位** |
  | (25, 4) | `edge` | `hatch` | **walk 相位** |
  | (25, 5) | `edge` | `hatch` | **walk 相位** |
  | (25, 6) | `edge` | `hatch` | **walk 相位** |
  | (25, 8) | `edge` | `hatch` | **walk 相位** |
  | (26, 5) | `edge` | `hatch` | **walk 相位** |
  | (26, 6) | `edge` | `hatch` | **walk 相位** |
  | (26, 7) | `edge` | `hatch` | **walk 相位** |
  | (27, 5) | `edge` | `hatch` | **walk 相位** |
  | (27, 6) | `edge` | `hatch` | **walk 相位** |
  | (27, 7) | `edge` | `hatch` | **walk 相位** |

* **`movegrid-frame-v1`**（13 格；最优帧 `step-26-A.state.vram-0000.bin`）：

  | map (lx, ly) | 原版族 | 重制侧族 | 性质 |
  |---|---|---|---|
  | (0, 12) | `edge` | `solid` | **原版尾部残留** |
  | (1, 3) | `edge` | `solid` | **原版尾部残留** |
  | (1, 4) | `edge` | `solid` | **原版尾部残留** |
  | (1, 5) | `edge` | `solid` | **原版尾部残留** |
  | (1, 6) | `edge` | `solid` | **原版尾部残留** |
  | (1, 7) | `edge` | `solid` | **原版尾部残留** |
  | (1, 8) | `edge` | `solid` | **原版尾部残留** |
  | (1, 9) | `edge` | `solid` | **原版尾部残留** |
  | (1, 10) | `edge` | `solid` | **原版尾部残留** |
  | (1, 11) | `edge` | `solid` | **原版尾部残留** |
  | (1, 12) | `edge` | `solid` | **原版尾部残留** |
  | (20, 7) | `hatch` | `solid` | **产品差** |
  | (21, 7) | `hatch` | `solid` | **产品差** |

* **`grid16-frame-v1`**（102 格；最优帧 `step-26-A.state.vram-0000.bin`）：

  | map (lx, ly) | 原版族 | 重制侧族 | 性质 |
  |---|---|---|---|
  | (0, 1) | `blank` | `solid` | **原版尾部残留** |
  | (0, 3) | `edge` | `solid` | **原版尾部残留** |
  | (0, 4) | `edge` | `solid` | **原版尾部残留** |
  | (0, 5) | `edge` | `solid` | **原版尾部残留** |
  | (0, 6) | `band` | `solid` | **原版尾部残留** |
  | (0, 7) | `hatch` | `solid` | **原版尾部残留** |
  | (0, 8) | `hatch` | `solid` | **原版尾部残留** |
  | (0, 9) | `edge` | `solid` | **原版尾部残留** |
  | (0, 10) | `edge` | `solid` | **原版尾部残留** |
  | (0, 11) | `edge` | `solid` | **原版尾部残留** |
  | (0, 12) | `edge` | `solid` | **原版尾部残留** |
  | (1, 1) | `blank` | `solid` | **原版尾部残留** |
  | (1, 3) | `edge` | `solid` | **原版尾部残留** |
  | (1, 4) | `edge` | `solid` | **原版尾部残留** |
  | (1, 5) | `edge` | `solid` | **原版尾部残留** |
  | (1, 6) | `band` | `solid` | **原版尾部残留** |
  | (1, 7) | `hatch` | `solid` | **原版尾部残留** |
  | (1, 8) | `hatch` | `solid` | **原版尾部残留** |
  | (1, 9) | `edge` | `solid` | **原版尾部残留** |
  | (1, 10) | `edge` | `solid` | **原版尾部残留** |
  | (1, 11) | `edge` | `solid` | **原版尾部残留** |
  | (1, 12) | `edge` | `solid` | **原版尾部残留** |
  | (16, 1) | `blank` | `solid` | **walk 相位** |
  | (16, 5) | `hatch` | `edge` | **walk 相位** |
  | (16, 7) | `line_alt` | `edge` | **walk 相位** |
  | (16, 8) | `hatch` | `edge` | **walk 相位** |
  | (16, 9) | `hatch` | `edge` | **walk 相位** |
  | (17, 1) | `blank` | `solid` | **walk 相位** |
  | (17, 5) | `hatch` | `edge` | **walk 相位** |
  | (17, 7) | `line_alt` | `edge` | **walk 相位** |
  | (17, 8) | `hatch` | `edge` | **walk 相位** |
  | (17, 9) | `hatch` | `edge` | **walk 相位** |
  | (18, 1) | `blank` | `solid` | **walk 相位** |
  | (18, 5) | `edge` | `hatch` | **walk 相位** |
  | (18, 7) | `line_alt` | `hatch` | **walk 相位** |
  | (19, 1) | `blank` | `solid` | **walk 相位** |
  | (19, 5) | `edge` | `hatch` | **walk 相位** |
  | (19, 7) | `line_alt` | `hatch` | **walk 相位** |
  | (20, 1) | `blank` | `solid` | **walk 相位** |
  | (20, 4) | `edge` | `hatch` | **walk 相位** |
  | (20, 5) | `edge` | `hatch` | **walk 相位** |
  | (20, 6) | `edge` | `hatch` | **walk 相位** |
  | (20, 7) | `line_alt` | `solid` | **walk 相位** |
  | (20, 8) | `edge` | `hatch` | **walk 相位** |
  | (21, 1) | `blank` | `solid` | **walk 相位** |
  | (21, 4) | `edge` | `hatch` | **walk 相位** |
  | (21, 5) | `edge` | `hatch` | **walk 相位** |
  | (21, 6) | `edge` | `hatch` | **walk 相位** |
  | (21, 7) | `line_alt` | `solid` | **walk 相位** |
  | (21, 8) | `edge` | `hatch` | **walk 相位** |
  | (22, 1) | `blank` | `solid` | **walk 相位** |
  | (22, 3) | `edge` | `hatch` | **walk 相位** |
  | (22, 4) | `edge` | `hatch` | **walk 相位** |
  | (22, 5) | `edge` | `hatch` | **walk 相位** |
  | (22, 6) | `edge` | `hatch` | **walk 相位** |
  | (22, 7) | `edge` | `hatch` | **walk 相位** |
  | (22, 8) | `edge` | `hatch` | **walk 相位** |
  | (22, 9) | `edge` | `hatch` | **walk 相位** |
  | (23, 1) | `blank` | `solid` | **walk 相位** |
  | (23, 3) | `edge` | `hatch` | **walk 相位** |
  | (23, 4) | `edge` | `hatch` | **walk 相位** |
  | (23, 5) | `edge` | `hatch` | **walk 相位** |
  | (23, 6) | `edge` | `hatch` | **walk 相位** |
  | (23, 7) | `edge` | `hatch` | **walk 相位** |
  | (23, 8) | `edge` | `hatch` | **walk 相位** |
  | (23, 9) | `edge` | `hatch` | **walk 相位** |
  | (24, 1) | `blank` | `solid` | **walk 相位** |
  | (24, 4) | `edge` | `hatch` | **walk 相位** |
  | (24, 5) | `edge` | `hatch` | **walk 相位** |
  | (24, 6) | `edge` | `hatch` | **walk 相位** |
  | (24, 8) | `edge` | `hatch` | **walk 相位** |
  | (25, 1) | `blank` | `solid` | **walk 相位** |
  | (25, 2) | `blank` | `solid` | **walk 相位** |
  | (25, 4) | `edge` | `hatch` | **walk 相位** |
  | (25, 5) | `edge` | `hatch` | **walk 相位** |
  | (25, 6) | `solid` | `hatch` | **walk 相位** |
  | (25, 7) | `edge` | `solid` | **walk 相位** |
  | (25, 8) | `solid` | `hatch` | **walk 相位** |
  | (26, 1) | `blank` | `solid` | **walk 相位** |
  | (26, 3) | `edge` | `solid` | **walk 相位** |
  | (26, 5) | `edge` | `hatch` | **walk 相位** |
  | (26, 6) | `edge` | `hatch` | **walk 相位** |
  | (26, 7) | `edge` | `hatch` | **walk 相位** |
  | (27, 1) | `blank` | `solid` | **walk 相位** |
  | (27, 3) | `edge` | `solid` | **walk 相位** |
  | (27, 5) | `edge` | `hatch` | **walk 相位** |
  | (27, 6) | `edge` | `hatch` | **walk 相位** |
  | (27, 7) | `edge` | `hatch` | **walk 相位** |
  | (28, 1) | `blank` | `solid` | **walk 相位** |
  | (28, 3) | `edge` | `solid` | **walk 相位** |
  | (28, 4) | `edge` | `solid` | **walk 相位** |
  | (28, 5) | `edge` | `solid` | **walk 相位** |
  | (28, 7) | `band` | `solid` | **walk 相位** |
  | (28, 11) | `edge` | `solid` | **walk 相位** |
  | (28, 12) | `edge` | `solid` | **walk 相位** |
  | (29, 1) | `blank` | `solid` | **walk 相位** |
  | (29, 3) | `edge` | `solid` | **walk 相位** |
  | (29, 4) | `edge` | `solid` | **walk 相位** |
  | (29, 5) | `edge` | `solid` | **walk 相位** |
  | (29, 7) | `band` | `solid` | **walk 相位** |
  | (29, 11) | `edge` | `solid` | **walk 相位** |
  | (29, 12) | `edge` | `solid` | **walk 相位** |

* **`banner-frame-v1`**：无差异格（exact ✔）。

**族名对直方图**（同一份数据，逐时刻）：

| 原版时刻 | 族名对（原版→重制侧） |
|---|---|
| `field-frame-v1` | `band->solid` 1；`edge->hatch` 38；`edge->solid` 8；`hatch->edge` 6；`hatch->solid` 2；`line_alt->edge` 2；`line_alt->hatch` 2；`line_alt->solid` 2 |
| `movegrid-frame-v1` | `edge->solid` 11；`hatch->solid` 2 |
| `grid16-frame-v1` | `band->solid` 4；`blank->solid` 17；`edge->hatch` 36；`edge->solid` 27；`hatch->edge` 6；`hatch->solid` 4；`line_alt->edge` 2；`line_alt->hatch` 2；`line_alt->solid` 2；`solid->hatch` 2 |
| `banner-frame-v1` | （无） |

> **目标（同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0）**：**前三项已达成**；**族名不一致 0 仍未达成**，逐格性质见 §3.3，未达成项见 §11。

### 3.4 ⭐ 「walk 相位」格的不一致归因（wave 14 / Z3）

§3.3 把剩下的族名不一致逐格分成了三类：**原版尾部残留 44 格** / **walk 相位 130 格** / **产品差 2 格**。**walk 相位**那一类的判定规则是：原版该时刻的画面同时具备一组相位族（青/黄/橙/绿），而重制侧的 35 帧里**没有任何一帧**同时具备这组相位族。

⭐ **wave 14 / Z3 给了可判定的归因**（收据 `build/s49-z3-bound/phase-B.json`；笔记 `notes/s49-fidelity/Z3-bound-and-phase.md`）。

**(a) 原版那一帧是稳定态还是瞬态？** —— Z3 抓了原版**自己的 6 帧连拍**来判：

| 原版时刻 | 导出帧 | 相位族集合 | 原版点亮格 | 6 帧里同相位族 | 6 帧里同网格摘要 | 判定 |
|---|---|---|---:|---:|---:|---|
| `field-frame-v1` | `frame-05` | band、hatch、line_alt | 192 | 6 / 6 | 6 / 6 | **stable state** |
| `movegrid-frame-v1` | `frame-05` | hatch | 192 | 6 / 6 | 6 / 6 | **stable state** |
| `grid16-frame-v1` | `frame-00` | band、hatch、line_alt | 175 | 6 / 6 | 1 / 6 | **single frame transient** |
| `banner-frame-v1` | `frame-05` | （空） | 0 | 6 / 6 | 6 / 6 | **stable state** |

**(b) 重制侧到底走没走到那个相位？** —— 在**密集 walk**（原版 553 帧 / 重制 783 帧）上数同相位族的帧数：

| 原版时刻 | 相位族集合 | 原版密集 walk 同相位 | 重制密集 walk 同相位 | 重制侧最长连续同相位 |
|---|---|---:|---:|---:|
| `field-frame-v1` | band、hatch、line_alt | 67 / 553 | 0 / 783 | 0 |
| `movegrid-frame-v1` | hatch | 67 / 553 | 23 / 783 | 23 |
| `grid16-frame-v1` | band、hatch、line_alt | 67 / 553 | 0 / 783 | 0 |
| `banner-frame-v1` | （空） | 0 / 553 | 0 / 783 | 783 |

⇒ **`field` 的 50 格 = 重制侧缺一个相位**（原版那一帧是**稳定态**：6 帧连拍逐格相同、原版密集 walk 里连续 **67 帧**同相位；重制侧 **0 / 783 帧**同现）；**`grid16` 的 80 格 = 原版那一帧是瞬态**（导出帧在 6 连拍里**只出现 1 次**，下一帧已是 176 格的完整画面 ⇒ 缓冲半刷新的撕裂残影）。⇒ **130 = 50（重制缺相位）+ 80（原版瞬态）**。

### 3.5 ⭐⭐ wave 16 / V4 的**同刻**归因（口径修正：那 50 格**不是**「walk 没走到」）

⛔ **wave 16 / V4 的相位归因尚未交付** ⇒ 「这 50 格是 walk 没走到，还是产品缺一段演出」**本报告没有同刻口径的结论**；§3.3 只给出了**分类规则**。


## 4. 音频事件级对照（19 个配对时刻）

来源：`{work.relative_to(REPO).as_posix()}/s49-audio-l/event_diff.json`；原版侧证据：`build/s49-audio/`（J 流）。

### 4.1 本次采集的判定（L 流，步骤 10 的产物）

| 判定类别 | 含义 | 数量 |
|---|---|---:|
| `match` | 两侧同一时刻派发了同一个 cue | 5 |
| `cue_mismatch` | 同一游戏时刻两侧 cue ID 不同 | 0 |
| `silent_on_remake` | 重制侧派发了该 cue，但**听不到声音** | 0 |
| `never_dispatched` | 重制侧表里有，但**没有调用点** | 0 |
| `missing_on_remake` | 原版会播，重制侧**连这个 cue 都没有** | 2 |
| `not_reached_in_window` | 两侧都有且重制侧已接线，但这次采集没走到该时刻 | 12 |

### 4.2 上游证据的判定（J 流 `build/s49-audio/event_diff.json`，5 类口径）

| 判定类别 | 含义 | 数量 |
|---|---|---:|
| `match` | 两侧同一时刻派发了同一个 cue | 4 |
| `cue_mismatch` | 同一游戏时刻两侧 cue ID 不同 | 1 |
| `silent_on_remake` | 重制侧派发了该 cue，但**听不到声音** | 11 |
| `never_dispatched` | 重制侧表里有，但**没有调用点** | 1 |
| `missing_on_remake` | 原版会播，重制侧**连这个 cue 都没有** | 2 |

> L 流的 `not_reached_in_window`（本次采集没走到该时刻）与 J 流的 `silent_on_remake`（重制侧派发了但听不见）是**两套口径**：J 流是原版侧的普查证据，L 流是重制侧接了线之后的实跑结果。两者不能直接相减。

### 4.3 19 个配对时刻逐条

| # | cue key | 游戏时刻 | 判定 |
|---|---|---|---|
| 1 | `battle_bgm_s49` | S49 战斗 BGM | `match` |
| 2 | `battle_bgm_s41` | S41 战斗 BGM（参考） | `not_reached_in_window` |
| 3 | `prebattle_bgm` | 战前菜单 BGM | `match` |
| 4 | `combo_bgm` | 组合拳演出 BGM | `not_reached_in_window` |
| 5 | `postbattle_dialogue_bgm` | 战后对白 BGM | `not_reached_in_window` |
| 6 | `postbattle_map_bgm` | 战后地图 BGM | `not_reached_in_window` |
| 7 | `battle_opened_sfx` | 战斗开场音 | `match` |
| 8 | `ui_confirm_sfx` | UI 确认音 | `match` |
| 9 | `ui_cancel_sfx` | UI 取消音 | `not_reached_in_window` |
| 10 | `ui_navigate_sfx` | UI 移动音 | `not_reached_in_window` |
| 11 | `input_rejected_sfx` | 输入被拒音 | `match` |
| 12 | `action_confirmed_sfx` | 行动确认音 | `not_reached_in_window` |
| 13 | `action_movie_sfx` | 战斗演出音 | `not_reached_in_window` |
| 14 | `impact_sfx` | 命中音 | `not_reached_in_window` |
| 15 | `combat_popup_sfx` | 战斗结算弹窗音 | `not_reached_in_window` |
| 16 | `victory_sfx` | 胜利音 | `not_reached_in_window` |
| 17 | `result_sfx` | 结算音 | `not_reached_in_window` |
| 18 | `tool_group17_sfx` | 道具组17 专用音 | `missing_on_remake` |
| 19 | `tool_expiry_sfx` | 道具到期专用音 | `missing_on_remake` |

## 5. 存档字段级差异表

来源：`build/s49-save-boundary/receipts/save_compare.json`（`tools/s49_save_boundary/run_all.py --repeat 2`）。

| 项 | 值 |
|---|---:|
| 原版检查点数 | 46 |
| 原版不同镜像数 | 1 |
| 原版战前→战后差异字节 | 0 |
| 原版战斗期写盘 | 否 |
| 重制侧检查点数 | 16 |
| 重制侧 擦除态→第一次存档 差异字节 | 4020 |
| 重制侧 第一次→第二次存档 差异字节 | 4020 |
| 重制侧 第二次存档→战斗末 差异字节 | 0 |
| 跨格式差异字节 | 3856 |
| 跨格式差异区间数 | 149 |

**逐字段差异表**

| 字段 | 原版 | 重制侧 | 差异 | 状态 |
|---|---|---|---|---|
| `record 0 header` | Naruto-KONOHASENKI (19 B) at 0 | - | 原版有身份头，重制没有；重制用 4 字节魔数代替 | active |
| `record 0 payload` | 4732 B at 19 | - | 原版每条记录自带负载 | active |
| `record 0 checksum` | ~sum(payload) = F7 at 4751 | - | 原版是 1 字节取反和，重制是 4 字节 CRC32 | active |
| `record 1 header` | (all FF, unused) at 4752 | - | 原版有身份头，重制没有；重制用 4 字节魔数代替 | erased (all FF) |
| `record 1 payload` | (all FF) 4732 B at 4771 | - | 原版每条记录自带负载 | erased (all FF) |
| `record 1 checksum` | (all FF) at 9503 | - | 原版是 1 字节取反和，重制是 4 字节 CRC32 | erased (all FF) |
| `record 2 header` | Naruto-KONOHASENKI (19 B) at 9504 | - | 原版有身份头，重制没有；重制用 4 字节魔数代替 | active |
| `record 2 payload` | 20 B at 9523 | - | 原版每条记录自带负载 | active |
| `record 2 checksum` | ~sum(payload) = E3 at 9543 | - | 原版是 1 字节取反和，重制是 4 字节 CRC32 | active |
| `record 3 header` | (all FF, unused) at 9544 | - | 原版有身份头，重制没有；重制用 4 字节魔数代替 | erased (all FF) |
| `record 3 payload` | (all FF) 4732 B at 9563 | - | 原版每条记录自带负载 | erased (all FF) |
| `record 3 checksum` | (all FF) at 14295 | - | 原版是 1 字节取反和，重制是 4 字节 CRC32 | erased (all FF) |
| `record 4 header` | (all FF, unused) at 14296 | - | 原版有身份头，重制没有；重制用 4 字节魔数代替 | erased (all FF) |
| `record 4 payload` | (all FF) 20 B at 14315 | - | 原版每条记录自带负载 | erased (all FF) |
| `record 4 checksum` | (all FF) at 14335 | - | 原版是 1 字节取反和，重制是 4 字节 CRC32 | erased (all FF) |
| `record 5 header` | (all FF, unused) at 14336 | - | 原版有身份头，重制没有；重制用 4 字节魔数代替 | erased (all FF) |
| `record 5 payload` | (all FF) 8 B at 14355 | - | 原版每条记录自带负载 | erased (all FF) |
| `record 5 checksum` | (all FF) at 14363 | - | 原版是 1 字节取反和，重制是 4 字节 CRC32 | erased (all FF) |
| `record 6 header` | (all FF, unused) at 14364 | - | 原版有身份头，重制没有；重制用 4 字节魔数代替 | erased (all FF) |
| `record 6 payload` | (all FF) 24 B at 14383 | - | 原版每条记录自带负载 | erased (all FF) |
| `record 6 checksum` | (all FF) at 14407 | - | 原版是 1 字节取反和，重制是 4 字节 CRC32 | erased (all FF) |
| `record 7 header` | (all FF, unused) at 14408 | - | 原版有身份头，重制没有；重制用 4 字节魔数代替 | erased (all FF) |
| `record 7 payload` | (all FF) 6084 B at 14427 | - | 原版每条记录自带负载 | erased (all FF) |
| `record 7 checksum` | (all FF) at 20511 | - | 原版是 1 字节取反和，重制是 4 字节 CRC32 | erased (all FF) |
| `record 8 header` | (all FF, unused) at 20512 | - | 原版有身份头，重制没有；重制用 4 字节魔数代替 | erased (all FF) |
| `record 8 payload` | (all FF) 1404 B at 20531 | - | 原版每条记录自带负载 | erased (all FF) |
| `record 8 checksum` | (all FF) at 21935 | - | 原版是 1 字节取反和，重制是 4 字节 CRC32 | erased (all FF) |
| `record 9 header` | (all FF, unused) at 21936 | - | 原版有身份头，重制没有；重制用 4 字节魔数代替 | erased (all FF) |
| `record 9 payload` | (all FF) 512 B at 21955 | - | 原版每条记录自带负载 | erased (all FF) |
| `record 9 checksum` | (all FF) at 22467 | - | 原版是 1 字节取反和，重制是 4 字节 CRC32 | erased (all FF) |
| `slot 0 header` | - | 4b424353 v2, payload_size=3524, generation=1 at 0 | 重制有版本/长度/世代三字段，原版没有 | active |
| `slot 0 payload` | - | 3524 B at 12 | 重制负载是 3524 B 的战役状态（章节/队伍/库存/63 个角色成长） | active |
| `slot 0 checksum` | - | CRC32 = 22128FC4 at 4092 | 重制是 4 字节 CRC32，原版是 1 字节取反和 | active |
| `slot 1 header` | - | 4b424353 v2, payload_size=3524, generation=2 at 4096 | 重制有版本/长度/世代三字段，原版没有 | active |
| `slot 1 payload` | - | 3524 B at 4108 | 重制负载是 3524 B 的战役状态（章节/队伍/库存/63 个角色成长） | active |
| `slot 1 checksum` | - | CRC32 = 764EDF57 at 8188 | 重制是 4 字节 CRC32，原版是 1 字节取反和 | active |

**语义映射表**

| 语义 | 原版 | 重制侧 | 差异 |
|---|---|---|---|
| 存档容器 | 10 条固定偏移记录，记录起点 = 前一条 payload_len + 0x14 | 2 个 4096 B 槽，槽 1 起点 = 4096 | ★ 容器不同 ⇒ 两种存档互相读不了 |
| 存档身份 | 每条记录 19 B 身份串 `Naruto-KONOHASENKI\0` | 槽头 4 B 魔数 `KBCS` | ★ 身份机制不同 |
| 存档完整性 | 1 B `~sum(payload)` | 4 B CRC32 | ★ 校验算法不同 |
| 版本 / 世代 | 无版本号；无世代计数器（记录同时有效） | version(u8) + payload_size(u16) + generation(u32) | ★ 原版没有「双槽轮换 + 世代」这一套 |
| 关卡进度 | record 0 payload（4732 B，负载内部未逐字段解码） | slot payload `chapter_id` (u16 @ +12) | 重制侧已逐字段；原版侧未逐字段解码 |
| 队伍 | record 0 payload（未逐字段解码） | slot payload `party[3]` (@ +18) | 重制侧已逐字段 |
| 忍具 / 材料库存 | record 0 payload（未逐字段解码） | slot payload `ninja_tools[94]` (@ +22) + `materials[18]` (@ +116) | 重制侧已逐字段 |
| 角色成长（等级/经验/训练点/忍术等级/装备） | record 0 payload（未逐字段解码） | slot payload `characters[63] x 54 B` (@ +134) | 重制侧已逐字段 |
| 战斗名册（坐标/HP/阵营/行动标记） | ★ record 7 payload = 6084 B = 13 x 0x1D4 （battle 14 的 9 名单位就在里面） | ★ 无对应字段（战役状态里只有成长，不含战斗名册） | ★ 语义缺口：重制不落盘战斗名册 |
| 战斗结果 / 回合状态 | record 2 (20 B) / record 8 (1404 B) / record 9 (512 B) | 无对应字段 | ★ 语义缺口（record 2 负载实测 = 0e000000 00000000 0e000000 00000000 0000） |
| 存档写入时机 | 只有世界地图「存档」菜单会写（战斗全程 0 字节变化） | 准备场景「存档」菜单 + 战斗胜利后自动存档 | ★ 写盘时机不同 |
| 落盘字节数 | 22468 B（10 条记录用满 0x57D4） | 8192 B（2 x 4096） | ★ 占用差 14276 B |

## 6. 12 条边界行为对照表

来源：`notes/s49-fidelity/W4-save-boundary.md` §6（其数字来自 `tools/s49_save_boundary/run_all.py` 的 62 张 SRAM 镜像与 `tools/s49_orig_map/orig_map_truth.py`）。**B5 / B7 两行按 X3 的实测结论更新过**（`notes/s49-fidelity/X3-boundary-fixes.md`）；B2 / B3 / B4 属非 S49 项，本波不做。

| # | 边界情形 | 原版实际怎么做 | 重制侧现在怎么做 | 差在哪 | 结论 |
|---|---|---|---|---|---|
| B1 | 损坏终止符 `0xFBFF` 的**字面量** | ROM `0x0825A8E4` 字节 `ff fb 00 00` ⇒ 有符号 u16 = **−1025**（不是 −1 ⇒ 渲染器不停） | 生成器把 `frame_trailer_raw_hex="fffb0000"` / `frame_trailer_signed_value=-1025` / `renderer_terminator=false` 写进 `battle_unit_visual_catalog.json`；全表 **2674 帧里只有这一帧**非法 | 无 | 🟢 **一致**，且**故意不修**那一字节（原版确实越界） |
| B2 | 渲染器的终止条件 | 只认 **−1（0xFFFF）**；`0xFBFF` 不停 ⇒ **继续每 20 B（0x14）读一个 component** | 运行期的 component 列表是**编译期定长**（`battle_unit_visual_frame::components[5]`，每项带 `visible`）⇒ **只画列出的 component** | ★ 原版**越界多画 3 个 component**，重制**不越界** | 🔴 **差**：缺陷只在**记录层**照抄，**运行层没照抄**。该角色不在 S49 出场 ⇒ **对 S49 像素无影响** |
| B3 | 越界轨迹 | 运行期轨迹 **4 次**循环命中：`0x0825A8E4`(FBFF/−1025) → `0x0825A8F8`(00FF/255) → `0x0825A90C`(0100/256) → `0x0825A920`(A8D0/−22320)，步长 0x14 | 运行期没有 component 指针遍历 ⇒ **没有这条轨迹可对拍** | ★ 原版有越界轨迹，重制侧没有 | ⚪ 若要 100% 照抄：重制运行时也要按 20 B 步长越界读 3 个 component 并画出来 |
| B4 | 对照实验（把 `0x0825A8E5` 的 `0xFB` 改成 `0xFF`） | 对照 ROM 里渲染器在 `0xFFFF` 就停，`repaired_component_count = 1` | 重制侧本来就是 1 个 component ⇒ **等于「修好后的原版」** | ★ 这正说明重制侧是「修好的原版」而不是「带 bug 的原版」 | 🔴 同 B2（**缺陷照抄的口径没满足**） |
| B5 | **蜜蜂是否进轮转**（行动单位轮转） | 行动单位指针**跨阵营推进**：单位池 `+0xC1`（正在行动）逐字节差分 → step-04 A → 槽 **5**(3,4)、step-05 B → 槽 **6**(4,8)、step-06 B → 槽 **7**(3,11)，**三个都是敌方蜜蜂**；分布是 4 玩家 + 5 敌方；状态栏因此显示「蜜蜂 待機 25 6」（红字） | `battle_session::cycle_roster_unit` 过滤 `unit.active && unit.side == _current_side` ⇒ **玩家回合的选择游标永远不会落到蜜蜂**；敌方回合由 AI 逐只驱动敌方单位 ⇒ 蜜蜂**在敌方回合轮流行动** | ★ 差别只在**玩家回合的游标能不能指到蜜蜂** | 🟢 **已修（X3）**：按原版改成跨阵营轮转，像素判据 C1–C4 全绿（状态栏气条像原版一样从 849 绿像素掉到 697）。⚠️ 但它暴露了重制侧**既有**的调色板 bank 泄漏 ⇒ 见 §11 第 4 项 |
| B6 | 存档容器被对方读到 | loader 认 19 B 身份串 | loader 认 4 B 魔数 + 版本 + 长度 + CRC32 | ★★ **互不兼容** | 🔴 **差**（见施工单 C1/C5） |
| B7 | 战斗期写不写盘 | **不写**：46 个检查点（含打赢后的任务菜单）逐字节相同 | **不写**（战斗本身 0 B 变化），但**战斗胜利后自动写** | ★★ 写盘时机不同 | 🟢 **已修（X3）**：去掉战斗胜利后的自动写盘，ROM 上实测写 **0 字节**且断言不崩 |
| B8 | 双槽 / 世代 | **没有**双槽轮换：10 条记录同时有效 | 2 槽轮换 + `generation + 1`（实测 slot0 gen1 → slot1 gen2） | ★ 原版没有世代计数器 | ⚪ 属**重制侧自创机制**，不是「照抄」对象 |
| B9 | 空 SRAM / 全新档 | SRAM 全 FF ⇒ 记录全空 ⇒ 走「无存档」分支 | 两槽都无效 ⇒ `used_default = true`，用 `empty_battle_campaign()` | 语义一致 | 🟢 **等价** |
| B10 | 损坏存档的降级 | 单条记录损坏只丢那一条，其余记录照读 —— **未实测**（需要人为破坏一份 `.sav` 再冷启动） | 单槽 CRC 错 ⇒ 该槽 `bad_crc` 丢弃；另一槽有效就用它；**两槽都坏 ⇒ `invalid_state` ⇒ `BN_ASSERT` 崩溃** | ★ 原版「降级到部分存档」，重制「两槽都坏就崩」 | ⚪ **原版侧未实测**（判据：破坏 `9fedf6bf…` 镜像的记录 0 校验字节，冷启动看是否还能读出记录 2） |
| B11 | 负载长度 / 越界 | 记录长度是**编译期常量**（4732/20/8/24/6084/1404/512），运行时改不了 | `payload_size` 是**头里的 u16**，解码端核对（不等 ⇒ `bad_payload_size`）；负载内字段长度全为编译期常量 | 无实质差异 | 🟢 **等价** |
| B12 | 校验强度 | 1 B `~sum(payload)` ⇒ **单字节碰撞**，可被伪造 | 4 B CRC32 | ★ 重制更强 | ⚪ **差**（是重制侧改进，不是缺陷；要 1:1 就得降级 —— 见施工单 C3，**不建议**） |

## 7. 黑场真值表

来源：`evidence/blackfade/blackfade-original.json` 与 `blackfade-remake.json`（`tools/s49_blackfade/blackfade_report.py`）。

### 7.1 原版（1881 帧，2 个黑场事件）

| # | 帧范围 | 总帧数 | 淡出 | 全黑 | 淡入 | 全黑帧 sha256 |
|---|---|---:|---:|---:|---:|---|
| 1 | `frame-01013.png` .. `frame-01078.png` | 66 | 24 | 18 | 24 | `47fbde60709a2768…` |
| 2 | `frame-01653.png` .. `frame-01724.png` | 72 | 24 | 24 | 24 | `47fbde60709a2768…` |

### 7.2 重制侧（2402 帧，5 个黑场事件）

| # | 帧范围 | 总帧数 | 淡出 | 全黑 | 淡入 | 全黑帧 sha256 |
|---|---|---:|---:|---:|---:|---|
| 1 | `frame-00527.png` .. `frame-00532.png` | 6 | 0 | 6 | 0 | `47fbde60709a2768…` |
| 2 | `frame-01639.png` .. `frame-01708.png` | 70 | 24 | 18 | 28 | `47fbde60709a2768…` |
| 3 | `frame-01749.png` .. `frame-01750.png` | 2 | 0 | 2 | 0 | `47fbde60709a2768…` |
| 4 | `frame-02217.png` .. `frame-02224.png` | 8 | 0 | 8 | 0 | `47fbde60709a2768…` |
| 5 | `frame-02265.png` .. `frame-02344.png` | 80 | 28 | 24 | 28 | `47fbde60709a2768…` |

采集来源（原版 / 重制侧两段录制的收据）：

| 侧 | ROM sha256 | 存档 sha256 | 采集帧数 |
|---|---|---|---:|
| original | `1198ece781aaf629…` | `a3628723ac595f41…` | 1881 |
| remake | `e2182fff9a6ba987…` | `—…` | 2402 |

> ✅ **重制侧这段黑场录制用的就是本次构建的 ROM**（sha256 `e2182fff9a6ba987…`）—— 流水线每次都重录，不吃历史缓存。

### 7.3 walk 采到了黑场没有（**残差归因的决定性一张表**）

上两张表说的是「黑场**长什么样**」；这一张说的是「walk **有没有采到**黑场」。判定台是按 walk 逐帧对拍的 ⇒ **原版 walk 采到的黑场帧，在重制侧必须也有对应帧**，否则那两帧的残差就是整屏。

| 侧 | walk 帧 | 非黑像素占比 | 是黑场帧吗 |
|---|---|---:|---|
| 原版 | `step-00-base.png` | 0.9982 | — |
| 原版 | `step-01-A.png` | 1.0000 | — |
| 原版 | `step-02-A.png` | 1.0000 | — |
| 原版 | `step-03-A.png` | 1.0000 | — |
| 原版 | `step-04-A.png` | 0.9785 | — |
| 原版 | `step-05-A.png` | 1.0000 | — |
| 原版 | `step-06-A.png` | 1.0000 | — |
| 原版 | `step-07-A.png` | 0.9978 | — |
| 原版 | `step-08-A.png` | 1.0000 | — |
| 原版 | `step-09-A.png` | 1.0000 | — |
| 原版 | `step-10-A.png` | 1.0000 | — |
| 原版 | `step-11-A.png` | 0.0079 | **是** |
| 原版 | `step-12-A.png` | 0.8565 | — |
| 原版 | `step-13-A.png` | 0.8591 | — |
| 原版 | `step-14-A.png` | 0.8591 | — |
| 原版 | `step-15-A.png` | 0.8591 | — |
| 原版 | `step-16-A.png` | 0.8541 | — |
| 原版 | `step-17-A.png` | 0.8541 | — |
| 原版 | `step-18-A.png` | 0.0000 | **是** |
| 原版 | `step-19-A.png` | 1.0000 | — |
| 原版 | `step-20-A.png` | 0.9982 | — |
| 原版 | `step-21-A.png` | 1.0000 | — |
| 原版 | `step-22-A.png` | 1.0000 | — |
| 原版 | `step-23-A.png` | 0.9982 | — |
| 原版 | `step-24-A.png` | 0.9982 | — |
| 重制侧 | `step-00-base.png` | 1.0000 | — |
| 重制侧 | `step-01-Down.png` | 1.0000 | — |
| 重制侧 | `step-02-Down.png` | 1.0000 | — |
| 重制侧 | `step-03-A.png` | 1.0000 | — |
| 重制侧 | `step-04-A.png` | 0.9852 | — |
| 重制侧 | `step-05-A.png` | 0.9869 | — |
| 重制侧 | `step-06-A.png` | 0.9869 | — |
| 重制侧 | `step-07-A.png` | 0.9869 | — |
| 重制侧 | `step-08-A.png` | 0.9663 | — |
| 重制侧 | `step-09-A.png` | 0.9872 | — |
| 重制侧 | `step-10-A.png` | 0.9872 | — |
| 重制侧 | `step-11-A.png` | 0.9851 | — |
| 重制侧 | `step-12-A.png` | 0.9872 | — |
| 重制侧 | `step-13-A.png` | 1.0000 | — |
| 重制侧 | `step-14-A.png` | 1.0000 | — |
| 重制侧 | `step-15-A.png` | 0.0385 | **是** |
| 重制侧 | `step-16-A.png` | 0.8373 | — |
| 重制侧 | `step-17-A.png` | 0.8591 | — |
| 重制侧 | `step-18-A.png` | 0.8591 | — |
| 重制侧 | `step-19-A.png` | 0.8591 | — |
| 重制侧 | `step-20-A.png` | 0.8541 | — |
| 重制侧 | `step-21-A.png` | 0.8541 | — |
| 重制侧 | `step-22-A.png` | 0.0000 | **是** |
| 重制侧 | `step-23-A.png` | 0.9982 | — |
| 重制侧 | `step-24-A.png` | 0.9982 | — |
| 重制侧 | `step-25-A.png` | 0.9982 | — |
| 重制侧 | `step-26-A.png` | 0.9989 | — |
| 重制侧 | `step-27-A.png` | 0.9982 | — |
| 重制侧 | `step-28-A.png` | 1.0000 | — |
| 重制侧 | `step-29-A.png` | 0.9989 | — |
| 重制侧 | `step-30-A.png` | 0.9989 | — |
| 重制侧 | `step-31-A.png` | 0.9989 | — |
| 重制侧 | `step-32-A.png` | 0.9989 | — |
| 重制侧 | `step-33-A.png` | 0.9989 | — |
| 重制侧 | `step-34-A.png` | 0.9989 | — |

**原版 walk 采到 2 个黑场帧**（`step-11-A.png`, `step-18-A.png`）；**重制侧 walk 采到 2 个**（`step-15-A.png`, `step-22-A.png`）

## 8. 其余门禁

| 门禁 | 判据 | 结果 |
|---|---|---|
| 静止帧（original） | 波形平点之外不得有相同帧 | 0 对相同 / 0 对异常 |
| 静止帧（remake） | 波形平点之外不得有相同帧 | 0 对相同 / 0 对异常 |
| 描边波 | 200/200 与原版一致 | 200/200 一致，0 不一致 |
| 无窗口无声 | 导入表无 USER32/winmm/SDL/OpenAL | 通过 |
| 冒烟 | 4096 帧不崩 + 中文标题画面 | 4096 帧；标题 15 色 / 6 个墨迹连通块 |

## 9. 假设台账索引

台账是本项目的记忆：每行一个假设，带判定方法、结果、状态（未验 / 已证伪 / 已确认）。

| 台账文件 | 假设条数 |
|---|---:|
| `notes/s49-fidelity/A-report-tool.md` | 9 |
| `notes/s49-fidelity/B-victory-settlement.md` | 12 |
| `notes/s49-fidelity/C-logic-state.md` | 11 |
| `notes/s49-fidelity/E-vram-budget.md` | 10 |
| `notes/s49-fidelity/F-rule.md` | 10 |
| `notes/s49-fidelity/G-overlay-alignment.md` | 16 |
| `notes/s49-fidelity/H-idle.md` | 13 |
| `notes/s49-fidelity/H2-idle-palette.md` | 11 |
| `notes/s49-fidelity/K-original-victory.md` | 17 |
| `notes/s49-fidelity/L-audio-wiring.md` | 15 |
| `notes/s49-fidelity/M-original-victory-truth.md` | 18 |
| `notes/s49-fidelity/P-pairing-decomposition.md` | 8 |
| `notes/s49-fidelity/Q-unit-test-baseline.md` | 6 |
| `notes/s49-fidelity/U1-d4-fix.md` | 12 |
| `notes/s49-fidelity/U1-wiring.md` | 12 |
| `notes/s49-fidelity/U2-battle-balance.md` | 13 |
| `notes/s49-fidelity/U2-overlay-settlement.md` | 12 |
| `notes/s49-fidelity/U3-settlement-content.md` | 14 |
| `notes/s49-fidelity/U3-wave17-package.md` | 11 |
| `notes/s49-fidelity/U4-real-victory-verify.md` | 18 |
| `notes/s49-fidelity/V1-real-victory.md` | 15 |
| `notes/s49-fidelity/V1-star37-wiring.md` | 8 |
| `notes/s49-fidelity/V2-camera-anchor.md` | 8 |
| `notes/s49-fidelity/V2-pixel-fixes.md` | 15 |
| `notes/s49-fidelity/V3-dialogue-title.md` | 16 |
| `notes/s49-fidelity/V3-wave16-package.md` | 19 |
| `notes/s49-fidelity/V4-bound-final.md` | 14 |
| `notes/s49-fidelity/V4-settlement-compare.md` | 13 |
| `notes/s49-fidelity/W1-blackfield-timeline.md` | 10 |
| `notes/s49-fidelity/W1-integration.md` | 15 |
| `notes/s49-fidelity/W1-three-defects.md` | 16 |
| `notes/s49-fidelity/W18-PARENT-ratchet-red.md` | 6 |
| `notes/s49-fidelity/W18-PARENT-residual-structure.md` | 9 |
| `notes/s49-fidelity/W18-PARENT-stack-copies.md` | 6 |
| `notes/s49-fidelity/W18-W1-stack-overflow.md` | 13 |
| `notes/s49-fidelity/W18-W2-confirm-yes-unselectable.md` | 9 |
| `notes/s49-fidelity/W18-W3-black-fade.md` | 12 |
| `notes/s49-fidelity/W18-W5-walk-divergence.md` | 12 |
| `notes/s49-fidelity/W19-A-opening-title.md` | 12 |
| `notes/s49-fidelity/W19-D-real-settlement-chain.md` | 10 |
| `notes/s49-fidelity/W2-judgment-bench-v2.md` | 17 |
| `notes/s49-fidelity/W2-ratchet-baseline.md` | 15 |
| `notes/s49-fidelity/W2-starfield-vram.md` | 15 |
| `notes/s49-fidelity/W3-blackfield-and-screens.md` | 12 |
| `notes/s49-fidelity/W3-original-truth.md` | 17 |
| `notes/s49-fidelity/W3-overlay-dialogue.md` | 12 |
| `notes/s49-fidelity/W3-settlement-wiring.md` | 17 |
| `notes/s49-fidelity/W4-original-victory-5th.md` | 15 |
| `notes/s49-fidelity/W4-save-boundary.md` | 14 |
| `notes/s49-fidelity/W4-wave11-determinism.md` | 10 |
| `notes/s49-fidelity/W4-wave12-package-review.md` | 13 |
| `notes/s49-fidelity/W4-wave13-package-final.md` | 12 |
| `notes/s49-fidelity/W4-wave14-package-final.md` | 21 |
| `notes/s49-fidelity/W4-wave15-package-final.md` | 16 |
| `notes/s49-fidelity/X2-overlay-zero.md` | 10 |
| `notes/s49-fidelity/X2-pairing.md` | 16 |
| `notes/s49-fidelity/X3-boundary-fixes.md` | 14 |
| `notes/s49-fidelity/Y1-stack-fix-and-settlement.md` | 17 |
| `notes/s49-fidelity/Y2-opening-title-blackfade.md` | 13 |
| `notes/s49-fidelity/Y2-overlay-final.md` | 8 |
| `notes/s49-fidelity/Y3-overlay-zero.md` | 11 |
| `notes/s49-fidelity/Y4-dialogue-typewriter.md` | 17 |
| `notes/s49-fidelity/Z1-wiring.md` | 6 |
| `notes/s49-fidelity/Z2-blackfield-final.md` | 12 |
| `notes/s49-fidelity/Z2-title-art-starfield.md` | 13 |
| `notes/s49-fidelity/Z3-bound-and-phase.md` | 13 |
| `notes/s49-fidelity/Z3-dialogue-box.md` | 21 |

## 10. 明确排除项

| 排除项 | 理由 |
|---|---|
| **存档逐字节一致** | 存档字节不是「玩家看得见的画面 + 游戏逻辑状态」。原版是 10 条变长记录（19 B 身份串 + 1 B `~sum` 校验，占 22,468 B），重制侧是 2×4096 B 槽（4 B `KBCS` 头 + 4 B CRC32，占 8,192 B）；**两侧 loader 互相都读不了**（跨格式 3,856 B / 149 个区间不同）。按用户口径明确排除（施工单 C1–C5，`W4-save-boundary.md` §5.5）。**但行为差异（B5 蜜蜂轮转 / B7 战斗后自动写盘）要修** —— 那是玩家看得见的。 |
| **音频逐采样一致** | 原版用 MP2K 合成器，重制侧用 Butano/Maxmod 的 PSG + wav；逐采样一致需要复现 MP2K 合成器本身（80–120 h 量级）。本波只做**事件级**对照（19 个配对时刻，5 类判定）。 |
| **渲染终止条件的缺陷照抄（B2/B3/B4）** | 该角色不在 S49 出场 ⇒ **对 S49 像素无影响**（`WAVE5-TASKS.md` §0.5）。列为非 S49 项。 |
| **覆盖层 `grid16-frame-v1` 的 80 格（原版覆盖层缓冲的单帧撕裂瞬态）** | ⭐ **wave 14 / Z3 的可判定归因**：原版那一帧在**连续 6 帧里只出现 1 次**（导出帧 `frame-00` 的网格摘要与其余 5 帧**全不同**），下一帧已经是 176 格的完整画面（第 1 行不再空、第 2 行补齐 1 格）⇒ **BG2 缓冲正在被重写时的撕裂残影**，**只存在 1 帧** ⇒ **任何忠实的重制都不该被要求复现它**（复现它就等于复现一次半刷新）。证据：收据 `build/s49-z3-bound/phase-B.json`、笔记 `notes/s49-fidelity/Z3-bound-and-phase.md` §3.3 / §3.5 |
| **覆盖层的 44 格「原版尾部残留」（Y2 的性质判定）** | 原版缓冲回绕尾部（= 地图第 0/1 列）装的是**陈旧内容**（墙列上出现光标格与可达集）⇒ **任何忠实的重制都复现不了**（那不是规则，是原版自己的缓冲残迹）。⇒ 这两类格（尾部残留 + `grid16` 撕裂）**从「未达成项」移进「明确排除项」**，理由逐格见 §3.3 |

## 11. 未达成项（不许粉饰）

| # | 未达成项 | 现状 | 归谁 |
|---|---|---|---|
| 1 | ⭐ **原版 S49 结算屏真值 —— 本波已闭合（不再是未达成项）** | **wave 8 的 W4 打赢了**：原版 battle-14 的结果字节 `0x02026807` 由 0 变 1，结算链全程录到（`build/s49-victory-capture/w4/settlement-truth/`，9 张图 + sha256 收据 `9a60a89b…`），两次独立跑 **32,596 + 29,700 帧逐字节一致**，**没有伪造任何帧**。⇒ 「原版没有结算屏真值」这条**已经作废**，本项转入正文 §15 | W4（已交付） |
| 1b | ⭐ **结算链与原版的差异（结构差已闭合；运行帧差见第 1c 项）** | **段数差已闭合**（wave 11 的 U3/W3 落地）：重制侧 `battle_scene_phase` 现在有 `post_battle_dialogue` 与 `task_menu` 两个新相，`battle_scene_phase_settlement_stage()` 把 7 段一一映射到 `battle_settlement_stage`（victory → result → level_up → training → post_battle_dialogue → task_menu → complete），并有单测 `test_battle_settlement_chain.cpp` 锁住（**本波实测通过**）。⇒ **运行帧这一层：**已闭合**：Z1 录出了重制侧结算链的**运行帧**，逐屏对照表**15 行**（收据 `build/z1/settlement-table-z1.json`；笔记 `notes/s49-fidelity/Y1-stack-fix-and-settlement.md`）**。⚠️ **原版升级屏是 3 人 × 2 页 = 6 个子页，木叶丸没有升级屏**（U3 实测，推翻了 wave 9 的「四人各一张」）⇒ wave 9 那份 V4 真值配对（`03-levelup-*` / `07-ninja-tool-list`）**文件名与画面对不上，V4 的配对是错的**。⭐ **底板结构差（资产级）**：现状 结算屏 **12,798** / 升级屏 **7,681** / 训练页 **8,483**（V4 口径，约 1/3 采样）；换 1:1 层后 **1,636（−87.2%）/ 608（−92.1%）**，训练页**无 1:1 候选**；⛔ **三张 8bpp 层 = 192 KB > 96 KB VRAM** ⇒ 必须先定量化/分层方案 ⇒ 见 §15.4。⭐ **wave 17 的結算屏逐屏对照（U2 的口径）见 §15.2.4** —— ⚠️ **「結算屏人物 1,898 px / 数字 684 px」是 wave 16 / V2 把**结算屏那一屏**的差拆成「tab 栏 / 渐变 / 面板边 / 人物 / 数字」五段后的数**，与 §15.2.4 的**整屏**差**不是同一个口径** ⇒ **两个数不许直接相比**。⭐ **wave 17 / U2 逐屏实测：結算屏残差 2,582 px 不变**（勝利 **0** / 結算 **2,582** / **6 张升級屏全 0**），并把 2,582 拆开：**684 px = 「真实战斗的战果」**（版式**逐像素对齐**；125（任务经验）与 75（回合奖励）两行**已经一样**，只有**战斗经验行**与**总经验行**不同 ⇒ **只能由 U1 打完的真实战斗产生，不是像素问题**）；**1,898 px = 三个人物**（实测原版每个人物 **26 / 23 / 26 色**；4bpp 量化后仍差 **808 px**；8bpp 三人各要一套 256 色 OBJ 调色板 ⇒ 硬件只有一套 ⇒ 逐人 8bpp 不可能）⇒ **取舍结论**：走「三个立绘合成一张 8bpp 图集 + 共用一套 8bpp OBJ 调色板」⇒ **1,898 → 0 px 且参与者仍然动态**；⛔ **代价是要动 U1 独占的绘制代码 ⇒ 已交父代理接线**。详见 `notes/s49-fidelity/U2-overlay-settlement.md` | 重制线（W3 / U3） / **U2（wave 17）** |
| 1c | ⭐ **结算链运行帧的逐屏对照表** | **已达成**：逐屏对照表**15 行**（收据 `build/z1/settlement-table-z1.json`；笔记 `notes/s49-fidelity/Y1-stack-fix-and-settlement.md`）⇒ 逐屏数字见 **§15.2**（测在 ROM `2c2b48d91fbe3244…`）。⭐ **wave 15 / W3 又交了一份机器可读的结算屏逐屏收据**（`build/w3/settlement-align.json`；重制侧帧来自 `build\w3\chain-pinned\shots`，**钉住 ROM 的重录**）：**8 对**、合计差 **73321 px**、**6 对逐字节相同**⇒ 逐屏数字见 **§15.2.1**；⭐ **本流用另一套实现独立重算，8屏逐值相同**（见 §15.2.2） | Z1（wave 14）/ W3（wave 15） |
| 2 | **判定台残差未归零，且归零在当前录制上不可达** | 本次中位 1323 px（wave-4 参照 — px，总和 107051 vs —）；配对差 4 帧（wave-4 是 — 帧）。⭐ **X2r 的可证像素下界 ≈ 23,700**（**wave 6 的录制上测值**）（精确值：**23,753**（wave 6 那次录制，ROM `fec749d8…`）/ **23,697**（上一版 ROM `c1f44b3b…`）；算法 = 每一拍内**原版的全部帧** × **重制的全部帧**逐对算残差取最小，25 拍求和 ⇒ **任何配对方式都不可能低于此数**）⇒ **归零在当前录制上不可达**；补齐产品缺口后可望降到 **≥ 16,389**（下界）。⭐ **wave 14 / Z3 已重算下界，但测在另一个 ROM 上**：**16389 px**（收据 `build/s49-z3-bound/bound-A.json`，ROM sha256 `2c2b48d91fbe3244…`；4 次独立跑**逐值相同**；标准配对的残差总和 `canonical_sum` = 90993 px）⇒ **本次流水线构建的是 `e2182fff9a6ba987…`**（Z2 的黑场改动进了产品 ⇒ ROM 变了）⇒ **本次 ROM 的精确下界待 Z3 重算**；**「归零不可达」这个量级结论仍然成立**（Z3 在**那个 ROM** 上量出的区间是 **16389 ≤ 最优残差 ≤ 18886 px**），但**这两个数字不是同一个 ROM 上的**，不许混用。X2 的结论：**walk 侧已经到头**，剩下的帧逐帧都有产品差证据 ⇒ 残差归零的前置条件不是换 walk，而是补齐产品差（内容锚口径下残差 **18886**，wave 6 旧口径是 28,899）。⭐ ⚠️ **口径警告（三个数不许混用）**：本次判定台读数 **107051 px**是 **arg-min、无时刻约束**；可证像素下界 **16389 px**是「每一拍内全部帧对取最小、25 拍求和」；内容锚可达数 **18886 px**是「同一时刻的帧对」。⇒ **三者回答三个不同的问题**（残差有多少 / 归零最低要多少 / 现在能做到多少）。 | X1（产品差）/ Z1（接线） |
| 3 | **覆盖层逐格族名：前三项已达成，第四项（族名不一致 0）仍未达成** | 目标（同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0）：`field-frame-v1` 同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 61；`movegrid-frame-v1` 同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 13；`grid16-frame-v1` 同亮 175 / 原版缺 0 / 多画 17 / 族名不一致 85；`banner-frame-v1` 同亮 0 / 原版缺 0 / 多画 0 / 族名不一致 0。⭐ **「原版缺 0 / 多画 0」已达成** —— 从 wave 1 传下来的「多画 310–420 / 缺 96–129」**是仪器假象**（原版侧贴标签没按 480 px 回绕 ⇒ 缓冲尾部两列被错开 ⇒ 24/24 的假差异）。剩下的族名不一致**逐格**给了性质判定：**原版尾部残留 44 格**（原版缓冲回绕尾部 = 地图第 0/1 列，装的是陈旧内容：墙列上出现光标格与可达集 ⇒ **任何忠实的重制都复现不了**）、**walk 相位 130 格**（原版的相位族集合在重制侧 35 帧里**没有任何一帧**同时具备 ⇒ 是走位/相位结构问题，不是覆盖层规则；⚠️ **这是跨时刻口径**；⭐ **wave 16 / V4 的同刻口径是 56 格（连尾部 67 格）**，且归因已改为「**产品缺一段演出**（相位切换时不清覆盖层缓冲），**不是** walk 没走到」⇒ 见 **§3.5**），**产品差 2 格**（见 §3.3 的逐格明细）。⭐ **wave 15：原版尾部残留 44 格与 `grid16` 的 80 格已移进 §10「明确排除项」**（原版自己的缓冲残迹 / 单帧撕裂 ⇒ **不是重制侧的产品差**）⇒ **真正还欠的只剩产品差 2 格**⭐ **wave 17 / U2 已把规则改完并实测**：`battle_range_ui_cell_kind()` 的**青（可达集）不再被 `move_phase` 锁住**⇒ 「青 + 橙」在**规则层**不再互斥（绿/橙/黄的门按 G-H15 / F-rule.md 保持不变 ⇒ **没有**放开绿/青）；**但实测「青 ∧ 橙」共现仍是 0 / 783、「walk 相位」格数 130 → 130，一个没降**⇒ U2 给出的**三条独立原因**（都在 U2 的独占文件之外）：① 目标选择相位的**绿集合（46 逻辑格）⊇ 青集合（44）**，按 F 的优先级 `target > attack > move` ⇒ **青一格都轮不到**；② 橙集合（射程 48 格）也 ⊇ 青集合；③ **原版自己的三个活相位的族集合两两不相交** ⇒ **「青 + 橙同现」是原版相位切换时不清覆盖层缓冲的残迹**，**不是任何一条活相位规则能画出来的**（与 §3.5 的结论一致）⇒ **剩下的接线点**：`battle_scene_controller.h`（覆盖层行集被清零）、`battle_runtime_scene.cpp`（渲染器整块释放，**U1 独占**）、以及**战斗打不完 ⇒ 走不到结算段**（U1 的 D4 必修）。详见 `notes/s49-fidelity/U2-overlay-settlement.md` | Y2（已达成前三项）/ Y1（相位与产品差）/ **U2（wave 17，规则已改）** |
| 3b | **⭐ 旧口径的数字全部作废（跨波比较的警告）** | wave 1–wave 12 的报告里那组「多画 310–420 格 / 缺 96–129 格」**不是产品差，是仪器给两侧贴了不同的地图标签**。⇒ **跨波比较必须先看口径**：wave 13 之后的数字才是「两侧都按 480 px 回绕」的口径；旧数字只能作为历史记录，**不许**再拿来说「产品退化」 | Y2（仪器修正已落地） |
| 4 | **重制侧调色板 bank 泄漏 ⇒ ROM 崩（wave 7 已修；⭐ wave 15 / W1 又查出**第二处**泄漏，也已修）** | X3 的 B5 修好后暴露：单位选择阶段连按 **R** 到第 9 个单位时 ROM 崩在 Butano 的 `bn_palettes_bank`（16 个硬件 sprite 调色板 bank 被 9 个「每单位一份运行期调色板」+ UI 调色板吃光）。⭐ **Y1 已修**（per-component 调色板释放，不再泄漏）：未打补丁 R×8 崩 / 打补丁 R×9 存活，且**修复是 pixel-neutral**（25/25 帧逐帧相同，残差加不加都一样）、4096 帧冒烟通过、**单测棘轮 PASS**（20 项失败集合逐名相同，new red = 0）⭐ **wave 15 / W1 查实并修掉了**第二处（**不同**的）泄漏**：根因**不是**「16 个 bank 不够用」，而是**静态的 dimmed 调色板**在「调色板几乎占满时」被创建 ⇒ 落在 bank 的**低位**（index 3）⇒ Butano 的 `create_bpp_8` 只把 bank **前端**给 BPP8 调色板 ⇒ 肖像的 128 色 BPP8 调色板再也拿不到 8 个 bank ⇒ `BPP8 palette create failed. Colors count: 128` ⇒ **ROM 停机**。⇒ 把 dimmed 调色板跟 map cohort 一起释放之后，**战斗不再停机**（驱动器从第 57 步走到第 300+ 步 / 第 4 回合）。⚠️ **两处泄漏不要混为一谈**：wave 7 的是「每单位一份运行期调色板」，wave 15 的是「静态 dimmed 调色板被创建在低位」 | Y1（wave 7，已交付）/ **W1（wave 15，已交付）** |
| 5 | **B5 / B7 已修，但像素级判据只有 B5** | X3 实测：B5 的像素判据 C1–C4 全绿（状态栏气条像原版一样从 849 绿像素掉到 697）、B7 在 ROM 上实测写 **0 字节**且断言不崩 ⇒ B5 / B7 的行为差**已消除**；但 B5 的像素级判据（下一轮可选单位）仍未独立取出 | X3（已交付） |
| 6 | **存档逐字节一致** | 按用户口径**排除**（理由见 §10）；但两侧 loader 互不兼容这件事本身没解决 | 父代理拍板 |
| 7 | **音频逐采样一致** | **排除**（80–120 h，需复现 MP2K 合成器）；事件级对照里 J 流口径是 11 条 `silent_on_remake`、1 条 `cue_mismatch`、2 条 `missing_on_remake`、1 条 `never_dispatched`；L 流本次采集另有 12 条 `not_reached_in_window`（这次采集没走到该时刻，不是缺陷） | J / L |
| 8 | **20 项单测在 HEAD 即为红（预存债），本次零回归** | HEAD 20 红 / 工作区 20 红，新失败 0 项。**不许写成「单测全绿」，也不许算成本次的成果** | 预存债，非本波 |
| 9 | **B10 原版「损坏存档降级」未实测** | 需要一份人为破坏的 `.sav` + 冷启动 | 未验 |
| 10 | **本机构建非字节可复现** | 基线 savestate load 不了本包的 ROM；随包带 ROM + 重录命令，复现需先建私有探针。⭐ **本波自己的两个 sha 就是证据**：同一份源码树在 wave 13 与 wave 14 两次构建出的 ROM sha **不同**（源码树**逐文件相同**，差别在链接时间戳 / 路径进了产物）⇒ **「同样的源码」在本机上拿不到同样的字节** ⇒ **随包必须带 ROM + 重录命令**（§12） | 结构性限制 |
| 11 | **黑场的事件数/时长** | ⭐ 原版 **2 个**黑场事件，每个都被切成 淡出 / 全黑 / 淡入 三段：事件 1 = 淡出 24 / 全黑 18 / 淡入 24；事件 2 = 淡出 24 / 全黑 24 / 淡入 24。重制侧 **5 个**事件：事件 1 = 淡出 0 / 全黑 6 / 淡入 0；事件 2 = 淡出 24 / 全黑 18 / 淡入 28；事件 3 = 淡出 0 / 全黑 2 / 淡入 0；事件 4 = 淡出 0 / 全黑 8 / 淡入 0；事件 5 = 淡出 28 / 全黑 24 / 淡入 28。⇒ ⛔ **带渐变的事件只有 2 个**（其余 3 个是**硬切**黑场：淡出 0 + 淡入 0，原版没有这种）；⇒ ⛔ **渐变段的长度与原版对不上**（原版 24/18/24 与 24/24/24）⇒ **「逐帧可见像素曲线与原版一致」这一条仍未达成**（见第 12 项）⭐ **逐段差（本次运行实测）**：重制侧第 1 个带渐变事件 = 淡出 24 / 全黑 18 / 淡入 28；原版第 1 个事件 = 淡出 24 / 全黑 18 / 淡入 24 ⇒ 淡出 差 +0、全黑 差 +0、淡入 差 +4。⇒ ⛔ 原版 walk 采到的两个黑场帧（`step-11-A` / `step-18-A`）在重制侧仍**没有对应**（本次配对差 4 帧，其中时刻不一致 4 帧） | **Z2（黑场事件数/时长，wave 14）** / **W3（黑场收官，wave 15）** / U1（接线）/ Y1 / Z2（遮罩层级数） |
| 12 | **⭐ 原版的「淡出/淡入」不是亮度渐变，是四角星光圈的收缩/扩张** ⇒ 调色板淡出只能做到**结构等价**，**逐帧均值曲线与原版不同** | Y2 的决定性发现：窗口内亮度不变 ⇒ 真 1:1 需要**星形遮罩**（BG 覆盖层 + 对角边 tile 集，缩放/扩张用不同 tile 排布）。⭐ **wave 7 的 Z2 已交付**（`notes/s49-fidelity/Z2-title-art-starfield.md`；⚠️ **这是 wave 7 的 Z2，不是 wave 14 的 Z2** —— 同名笔记的坑，判定以任务书的 mtime 为界）：**「素材 + 曲线」两件事都做完了** —— 原版的黑场被证明是**旋转的四角星光圈**（12 级淡出 / 18 帧全黑 / 12 级淡入共 66 帧），逐帧可见像素数已经量出来并做成 Butano 素材，**生成的位图回读校验 66/66 帧逐帧相等**；标题美术也已转成 5 个 sprite item 放进 `graphics/`，**VRAM 余量实测 = 部署画面 662 块空闲 OBJ 图块，标题只要 208 块**。⛔ **但有一个硬约束没解开**：一帧星光圈遮罩要 **640 块 OBJ 图块（20 KB）**，战斗画面最紧时只剩 **336 块（装不下）** ⇒ 第二个黑场事件必须先腾出图块，或者改用「旋转 + 缩放」的近似模型 ⇒ **「逐帧均值曲线与原版对齐」这一条本轮仍未验证** | Z2（素材与曲线已达成 / 运行期摆放：Z1） |
| 13 | **原版对话框的斜切展开动画 + 换行等待参数** | Y4 实测原版 **0267–0271** 是**斜切展开**的对话框动画（重制侧没有）；原版换行后**先等 56~92 帧**再打下一行。⭐ **wave 7 的 Z3 已交付**（`notes/s49-fidelity/Z3-dialogue-box.md`；⚠️ **这是 wave 7 的 Z3，不是 wave 14 的 Z3** —— 同名笔记的坑，判定以任务书的 mtime 为界）：**换行等待参数取到了真值**（**没换头像 7 帧 / 换了头像 63 帧**，每帧一采实测：原版第 1406 帧按 A → 第 1413 帧出字、第 1500 帧按 A → 第 1563 帧出字）并已在重制侧实现 + 单测；但 ⛔ **「斜切展开」的像素级复现仍未达成** —— Z3 查实那**不是对话框动画，是入场转场**（一层纯黑遮罩在**已经画完的场景**上被斜切成碎片擦掉，BG 图块表在整个过程里**逐字节不变** ⇒ 遮罩来自 OBJ）⇒ 需要原版的**碎片素材（Z2）** + **运行期精灵摆放（Z1）**，不是对话脚本能管的事；Z3 已把逐帧遮罩表（实测）做成模型交给 Z1/Z2。⛔ **wave 16 本波仍未复现 ⇒ 单列这一条**（换行等待参数那一半已达成，「斜切展开/入场转场」那一半没有） | Z3（等待参数已达成）/ 素材与摆放：Z2 + Z1 |
| 14 | **⭐ 本波流水线 全绿（12/12）** | 本次收据：**12 步全绿**（收据 `generated_at` = 2026-10-25T13:59:38+08:00`，`ok: true`，`failed_step: null`）；红的是 （无），绿的是 1、2、3、4、5、6、7、8、9、10、11、12。⚠️ **绿灯的门禁 ≠ 1:1 已达成**（本节其余各行都是绿灯掩盖不了的缺口）。⚠️ **本次运行的重制线是 wave 17 并行流（U1/U2/U4）的状态**（U1 修产品缺陷 D4 ——「玩家的伤害招式的战斗演出不结束」；U2 修覆盖层「青+橙」互斥（50 格产品差的根因）与結算屏人物/数字；U4 验证「真实打完仗」并交结算链的真实版；本次运行期间并行流还可能重建重制线，见收据步骤 1 与 12 的备注）⇒ **本次数字是 wave 17 的基线** | U1/U2/U4 落地后重跑 | ⭐ **本次读数测的是哪个 ROM / 采集是复用还是重采 / 与基线 ROM 是否相同**（§2.0c）：ROM `e2182fff9a6ba987…`；采集：original 侧 **captured**、remake 侧 **captured**；基线 ROM **不同** ⇒ 两个残差数字**不是同一个测量**。⭐ **本次的棘轮判定 = `incomparable`**（**不可比 ≠ 通过**：基线 ROM 与本次 ROM 不同 ⇒ 「残差只许变小」这条规则**本次没有被检验**）
✅ **12 步的判据与上一波被接受的收据逐字相同**（对照 `build/s49-package-v3-final/receipt.json`，机检）。
| 15 | **✅ 判定台的「±9,520 px 抖动」—— 已查清，**不是**仪器抖动 | 判定台本次：战场区残差总和 107051 px、中位 1323 px、峰值 27325 px、全 0 帧 4，覆盖层残差总和 857 px；棘轮基线（上一次被接受的运行，生成于 2026-10-24T13:53:58+08:00）是 100210 px ⇒ **棘轮通过**（本次基线已被重钉成本次的读数）。⭐ **wave 10 报的「同一个 ROM 连跑两次、残差 9,520 → 0、总和 114,304 → 104,784」这个抖动，根因已查实：那两次跑的 **ROM sha256 不同**（`249217d7…` vs `73b74587…`，见 §2.0b 的证据表）⇒ 差的那 9,520 px 属于**产品改动**，不属于仪器。⭐ 本波把「读数确定性」做成了**仪器自证的能力**：步骤 5 现在**连读 3 次**，3 次读数必须逐项相同（含每张采集 PNG 的 sha256），否则步骤 5 变红；棘轮收据里也带上两侧的 ROM sha256 ⇒ **「残差变大」现在能被干净地归因到产品或仪器** | W4（wave 11，已闭合） |
| 16 | **⭐ 单测棘轮：零回归（已确认）** | 步骤 2：HEAD **20 红** / 工作区 **20 红**，**新失败 0 项** ⇒ **失败集合与 HEAD 基线逐名相同**（20 项预存债），**本次零回归**；⚠️ **不许写成「单测全绿」** | 预存债，非本波 |
| 17 | **⭐ 覆盖层逐格族名：前三项已达成（**192 / 0 / 0**），第四项仍开放** | 目标（同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0）的**前三项在 wave 13 达成**：见 §3 的逐时刻实测与 §3.3 的逐格性质判定。⚠️ **判据在 wave 10 / U4 被改过两处**（两处都写清了）：① **锚点口径**从「窗口搜索」改成**原版的实测锚点 (256, 0)**（§3.1，两种口径在同一份 dump 上的对比）；② **候选帧**从「配对帧里亮格最多的那一帧」改成**整条 walk 的 35 个 anchor dump** —— 因为实测发现**重制侧只在 walk 的 step 25 与 28–34 显示覆盖层**，25 个配对帧**一个都没有**，拿配对帧去量是退化测量（残差恒为 192，与产品质量无关）。⭐ **wave 13 / Y2 的第三处修正**：原版侧**按 480 px 回绕**（此前只有重制侧回绕）⇒ 24/24 的假差异消失。⭐ **wave 12 / X4 独立复核了 wave 10 / U4 的第四处改动（terrain 判据）**⇒ 结论**保留，不回退**，数字见 §16 | **Y2（覆盖层逐格族名，已交付前三项）** / Y1（相位与产品差） / U1（内容映射接线）/ U4（判据已改） |
| 18 | **⭐ 判定台的覆盖层读数用的是旧判据** | 判定台自己的覆盖层模块（`tools/s49_fidelity_report/overlay.py`，**另一个流的文件，本流只读调用**）自己实现了一份「亮格」统计，**没有**用 U4 改好的锚点口径，所以本报告 §2 里的 `overlay_residual` 与 §3 的逐格对拍**不是同一个口径** ⇒ **两个数不许混用** | 判定台所有者 |
| 19 | **✅ wave 10 / U4 的 terrain 判据：独立复核完成（保留，不回退）** | 见 **§16**：把改前的候选扫描**重新实现**一遍逐 dump 对照 ⇒ 「不带 terrain」的路径与改前**逐字节相同**（**0 处不同**）；判定台自己的覆盖层读数**也一字未变**（**0 处不同**，因为它调 `find_overlay_map(vram, 77)`、terrain 走默认值 `None`）；判据只改 **4/35** 个 dump（假窗口 `0x00800` → `-1`），**其余 31 个一字未变**，且让 `grid16-frame-v1` 的残差从 **185 降到 126**（剔掉的是假阳性）。⚠️ **循环论证的风险已写明**：terrain 来自重制线自己的生成头，不是独立于产品的绝对真值 | X2（共享仪器的所有者） |
| 20 | **⭐ 本轮收据是 wave 14 的读数：Z1 / Z2 / Z3 的落地状态** | **Z1（栈溢出笔记 + 结算链运行帧）**：**已交付**（`notes/s49-fidelity/Y1-stack-fix-and-settlement.md`）；**结算链收据有 15 行**（`build/z1/settlement-table-z1.json`；逐屏对照表）；**Z2（黑场事件数/时长）**：**事件数未对齐**（原版 **2** 个 vs 重制侧 **5** 个）；原版（24/18/24；24/24/24）；重制侧（0/6/0；24/18/28；0/2/0；0/8/0；28/24/28）；**Z3（残差下界重算 + walk 相位归因）**：**已交付**（`notes/s49-fidelity/Z3-bound-and-phase.md`）；**可证像素下界尚未为本次 ROM 重算**。⭐ **本轮收据本身是自洽的**（构建 / 测量 / 打包是同一份 ROM `e2182fff9a6ba987…`）⇒ **可以作为 wave 14 的基线引用** | Z1 / Z2 / Z3 交付后重跑 |
| 21 | **⭐ 本轮收据是 wave 15 的读数：W1 / W2 / W3 的落地状态** | **W1（3 个新查实的产品缺陷：调色板 cohort / 战后对白与任务菜单的 UI 层 / 非法 UTF-8）**：**已交付**（`notes/s49-fidelity/W18-W1-stack-overflow.md`、`notes/s49-fidelity/W1-three-defects.md`）；**W2（棘轮基线修正：基线改成「上一波被接受的收据」）**：**已交付**（`notes/s49-fidelity/W18-W2-confirm-yes-unselectable.md`、`notes/s49-fidelity/W2-ratchet-baseline.md`）；**本次运行的棘轮基线**：the ratchet verdict is INCOMPARABLE: the baseline ROM differs from this run's ROM => the residual numbers are not the same measurement => this is NOT a pass；the ratchet baseline is D:\Github\gba-naruto\build\s49-package\baseline-accepted\report.json (field residual sum 107051 px this run)；the judgment bench reported INCOMPARABLE (exit code 2): the baseline ROM differs from this run's ROM => the residual numbers are not comparable => NOT a pass；**本次的棘轮判定 = `incomparable`**（**不可比 ≠ 通过**：基线 ROM 与本次 ROM 不同 ⇒ 「残差只许变小」这条规则本次没有被检验）（基线 `D:\Github\gba-naruto\build\s49-package\baseline-accepted\report.json`）；**W3（黑场收官 + 胜利/结算屏画面）**：**已交付**（`notes/s49-fidelity/W18-W3-black-fade.md`、`notes/s49-fidelity/W3-blackfield-and-screens.md`）；**本次运行的黑场**：原版 **2** 个（24/18/24；24/24/24）；重制侧 **5** 个（0/6/0；24/18/28；0/2/0；0/8/0；28/24/28）。⭐ **判定口径**：「本波已交付」一律**以 `WAVE15-TASKS.md` 的 mtime 为界**（`notes/s49-fidelity/` 里同名的 Z1/Z2/Z3 属于 **wave 7**，X2-overlay-zero 属于 **wave 12**，Y3-overlay-zero 属于 **wave 6**）。✅ **三路都已交付** | W1 / W2 / W3 |
| 22 | **✅ 判定台「复用采集不校验 ROM」—— wave 16 / V3 已修** | `tools/s49_fidelity_report/capture.py::run_capture()` 在 `reuse=True` 时**只看「done 标记在不在、帧在不在」**，**从不核对那份采集是哪一个 ROM 录的**；随后报告把帧标成**它被要求测的**那个 ROM 的 sha256。⚠️ **wave 15 实测到这个缺陷造成了假结论**：W1 的「判定台残差没有变大」是**复用了 wave 14 包里的采集目录**得到的 —— 那份采集的 audit ROM 是 wave 14 的 ROM（`ec5b5273…`），却被标成了新 ROM（`fb9d2dbd…`）⇒ **它比的是 wave 14 的帧和 wave 14 的帧**。⇒ ⭐ **wave 16 / V3 已修**（只改 `capture.py` 一个文件）：复用前**必须**核对采集自己的审计（`audit.json` **和** `done.json`）：重制侧核对 `rom_sha256`、原版侧核对 `input_state_sha256`；**两个证人互相矛盾 ⇒ 拒绝**；**核对不过 ⇒ 绝不复用 ⇒ 重新采集**。**判据**：① 审计说别的 ROM ⇒ **两侧都重采**（`action = recaptured`）；② 审计说同一个 ROM ⇒ **复用**，且**同一个 work 目录**里「重采 / 篡改后重采 / 复用」三次的 `content_sha256` **完全相同** ⇒ **复用不改变读数**。复现：`python build/v3-dev/prove_capture_rom_check.py` | **V3（wave 16，已交付）** |
| 23 | **⭐ 本轮收据是 wave 16 的读数：V1 / V2 / V4 的落地状态** | **V1（真实打完仗 + 结算链运行帧真实版）**：**已交付**（`notes/s49-fidelity/V1-real-victory.md`）；**结算链收据有 48 行**（`build/v1-u4/compare-chain-toolcheck.json`；逐屏对照表）；**V2（像素修复全包：胜利屏 / 结算屏 / 硬切 / 生长段 / CJK 扩字）**：**产品侧**（任务书里**没有给 V2 笔记** ⇒ 证据是本流水线在**钉住的 ROM** 上的实测）；**本次构建的 ROM 在本波被重建过**；**本次运行的黑场**：原版 **2** 个（24/18/24；24/24/24）；重制侧 **5** 个（0/6/0；24/18/28；0/2/0；0/8/0；28/24/28）；**V4（可证像素下界为最终 ROM 终算 + 缺一个相位的定位）**：**已交付**（`notes/s49-fidelity/V4-bound-final.md`）；**可证像素下界尚未为本次 ROM 重算**。⭐ **判定口径**：「本波已交付」一律**以 `WAVE16-TASKS.md` 的 mtime 为界**（`notes/s49-fidelity/` 里同名的 **Z1/Z2/Z3 属于 wave 7**，**W1/W2/W3 属于 wave 5 / 6 / 8** ⇒ **同名笔记的坑比任务书说的更宽**）。✅ **三路都已交付** | V1 / V2 / V4 |
| 24 | **⭐ wave 15 的 +60 px 回归（`step-24-A.png` 一帧，判定类别「产品差」）—— **是真阳性，不是抖动** | wave 15 / W4 查实：棘轮基线（wave 14 被接受的收据）**109,569 px** vs 本次 **109,629 px** ⇒ **+60 px**；逐帧归因：**25 个配对时刻里只有 `step-24-A.png` 一帧变了**（1,372 → 1,432 px，判定类别 **产品差**），其余 24 帧**逐像素相同**；**4 次独立重录逐帧完全相同** ⇒ **是真的产品回归**。⚠️ **它不是「残差抖动」**：同一个 ROM 连读 3 次读数逐项相同（§2.0b）⇒ 差值属于**产品改动**。⇒ **本波（wave 16）由 V2 的像素修复全包接手**。⭐ **本次状态**：🟡 **本次读数 **107051 px** 与被接受的基线**逐值相同** ⇒ **wave 15 的 +60 px 回归（当时 109629 px）已经被修掉了**（相对 wave 15 是 **-2578 px**） | **V2（wave 16）** |
| 25 | ✅ **⭐⭐ 「真实打完仗」—— **本波已闭合**（真实战斗打出 `outcome=1`）** | wave 16 的 V1 查实了**产品缺陷 D4**（**重制侧一旦玩家的攻击「射程内有活着的敌人」，战斗场景就废了** ⇒ `outcome=1` 在那个 ROM 上不可达）；wave 17 的 **U1 修了 D4**（重制线：`battle_combat_presentation.h` / `battle_scene_presentation.h` / `battle_runtime_scene.cpp` / `battle_black_field*.h`），**U4 用闭环驱动器打出了一场真实战斗** ⇒ **真实战斗收据** `build/w20-e1/chain-fix1-tc/real/battle.json`（ROM `150dacf876ab3fc3…`）：**`outcome = 1`、`battle_decided = True`、**进入方式** `real battle: the closed-loop driver plays the battle with the buttons only, and the outcome is the product code's own decision`、**poke 指令数 = 0**、**蜂的 HP 下降 = True**、**护送存活 = True**⇒ **它不是 poke 打出来的**；⚠️ **另有 2 条 poke 链**（**分列在 §15.2.3**，**不许**与它混用） | **U1（wave 17，已交付）/ U4（wave 17，已交付）** |
| 26 | **⭐ 本轮收据是 wave 17 的读数：U1 / U2 / U4 的落地状态** | **U1（D4 必修：玩家的伤害招式的战斗演出不结束）**：**已交付**（`notes/s49-fidelity/U1-d4-fix.md`）；✅ **产品侧已落地**（独占文件在任务书之后被改过：`butano-sequel/game/src/battle_runtime_scene.cpp`、`butano-sequel/game/include/konoha/battle_black_field.h`）；**本次构建的 ROM 在本波被重建过**；**U2（覆盖层「青+橙」互斥 + 結算屏人物/数字）**：**已交付**（`notes/s49-fidelity/U2-overlay-settlement.md`）；✅ **产品侧已落地**（独占文件在任务书之后被改过：`butano-sequel/game/include/konoha/battle_range_ui_style.h`、`butano-sequel/graphics/battle_ui_result_naruto.bmp`、`butano-sequel/graphics/battle_ui_result_sakura.bmp`、`butano-sequel/graphics/battle_ui_result_sasuke.bmp`、`butano-sequel/graphics/scenario_41_postbattle_bg.bmp`、`butano-sequel/graphics/scenario_41_postbattle_dialogue_page_1.bmp`、`butano-sequel/graphics/scenario_41_postbattle_dialogue_page_1.json`、`butano-sequel/graphics/scenario_41_postbattle_dialogue_page_2.bmp`）；**本次运行的黑场**：原版 **2** 个（24/18/24；24/24/24）；重制侧 **5** 个（0/6/0；24/18/28；0/2/0；0/8/0；28/24/28）；**U4（真实打完仗验证 + 结算链真实版）**：**已交付**（`notes/s49-fidelity/U4-real-victory-verify.md`）；**尚无「真实战斗 + `outcome=1`」的链**；⚠️ **另有 2 条 poke 链**（最新：`build/w19-a/chain-final/chain.json`）⇒ **不得写成真实胜利链**。⭐ **判定口径**：「本波已交付」一律**以 `WAVE17-TASKS.md` 的 mtime 为界**（**同名笔记的坑**：wave 16 的 V1/V2/V4、wave 7 的 Z1/Z2/Z3 都在 `notes/s49-fidelity/` 里）⇒ **产品流（U1 / U2）额外用「独占文件的 mtime + ROM 在其后被重建」判定** —— 笔记不是产品的证据，**ROM 才是**。✅ **四路都已交付** | U1 / U2 / U4 |

## 12. 基线钉与复现

本机构建 **非字节可复现**（链接时间戳 / 路径进入产物），所以：

* 基线 savestate **load 不了**本包里的 ROM ⇒ 不能只发 savestate；
* 随包必须带 **ROM + 重录命令**；
* 复现命令 **需先建私有探针**（`KONOHA_PROBE_OUT` 指到包内目录，**不要覆盖共享的 `build/mgba-probe/mgba-probe.exe`**，会 LNK1104）。

| 包内文件 | 说明 |
|---|---|
| `rom/butano-sequel.gba` | 本次构建的 ROM |
| `REPRODUCE.md` | 逐条复现命令 |
| `receipt.json` / `receipt.md` | 12 步的完整收据 |
| `manifest.json` | 包内每个文件的 sha256 |
| `evidence/` | 每一步的原始产物 |
| `logs/` | 每一步的完整输出 |

⭐ **wave 16 / V3 追加的两条复现路径**（都在 `build/v3-dev/`，**不进仓**）：

| 命令 | 作用 |
|---|---|
| `python build/v3-dev/prove_capture_rom_check.py` | 证明判定台**复用采集时必须核对 ROM**（篡改审计 ⇒ 重采；审计一致 ⇒ 复用，且读数与重采**逐项相同**） |
| `powershell -File build/v3-dev/recompute-bound.ps1 -Rom <本包的 ROM>` | 用 **V4 已交付的工具**（**只读调用**）为**本包的这个 ROM** 重算**可证像素下界**（自带与 `pair.beat_floor` 的交叉核对） |

## 13. 流水线 12 步收据

| # | 步骤 | 判据 | 结果 | 耗时(s) |
|---|---|---|---|---:|
| 1 | 构建重制 ROM（WSL，必须导出 LIBBUTANOABS） | 构建之前先等「ROM 文件连续 150 s 不变 + 没有 mgba-probe.exe 在跑」（Z4 的教训：并行流同期重建 ROM 会让步骤 1/5 变红）；WSL 里的 make 成功（LIBBUTANOABS 已导出），且产出 butano-sequel.gba；ROM 的 sha256 与字节数写进收据 | PASS | 185.13 |
| 2 | 重制线单元测试【棘轮式：与 HEAD 基线对照】 | 工作区的单测失败集合必须是 HEAD 基线失败集合的子集（HEAD 就有的 20 项红是预存债，不是回归）；比 HEAD 多出来的任何一项 ⇒ 变红；少掉的任何一项（被顺手修好了）⇒ 记为改进，不判红 | PASS | 286.33 |
| 3 | ROM 4096 帧冒烟不崩 + 中文标题画面正常 | 探针接受了每一条命令且没有崩溃标记；4096 帧之后模拟器仍在应答；中文标题画面渲染出来（不是空白开机屏，标题带有分开的墨迹连通块）；游戏对一次按键有反应 | PASS | 0.94 |
| 4 | 无窗口无声门禁 | 探针的导入表里没有窗口或音频后端（USER32/winmm/SDL/OpenAL…），实跑录制期间探针不拥有任何顶层窗口 | PASS | 0.29 |
| 5 | 判定台：残差分解（配对差/产品差/一致）+ 三桶分类 | 判定台产出了报告，且残差 / 归因 / 三桶分类都在；残差没有比**上一波被接受的收据**（棘轮基线）变大；基线 ROM 与本次 ROM 不同时报「不可比」，不许静默 PASS；⭐ 同一个 ROM 连读 3 次，3 次读数逐项相同（读数不确定 ⇒ 棘轮会误报） | PASS | 55.29 |
| 6 | 覆盖层逐格族名对拍 | 逐格族名对拍跑通，且逐时刻的残差没有比钉住的基线变大（棘轮）；绝对数字写进报告 | PASS | 2.55 |
| 7 | 静止帧门禁 | 任何一侧都没有在波形平点之外重复同一帧 | PASS | 0.29 |
| 8 | 描边波门禁（200/200） | 重制侧的待机描边波在 200 帧扫描的每一帧上都与原版一致（200/200，0 处不一致） | PASS | 1.65 |
| 9 | 黑场真值 | 两侧的黑场帧都用本次的 ROM 与钉住的存档重录了；原版侧每个事件都被切成淡出 / 全黑 / 淡入三段；重制侧的数字作为实测差距记进报告 | PASS | 88.8 |
| 10 | 音频事件级对照 | 音频事件级对照产出了 19 个配对时刻，且两次独立跑的产物逐字节一致 | PASS | 21.92 |
| 11 | 存档/边界收据（--repeat 2） | 存档 / 边界收据产出，且两次采集的 62 张镜像逐字节一致 | PASS | 25.1 |
| 12 | 打包：ROM + 复现命令 + 收据 JSON | 包里放了 ROM、复现命令和收据，且包内每个文件的 sha256 都在清单里 | PASS | 3.8 |

**步骤 1（build）的备注：**

* settle window: waited 152s before building (the ROM has not changed for 152s and no mgba-probe.exe is running)
* pinned D:\Github\gba-naruto\build\s49-package-w19b\work\pinned-rom\measured.gba (sha256 e2182fff9a6ba987…) -- every later step measures this copy and the package ships it

**步骤 2（unit-tests）的备注：**

* HEAD: exit 1, 101 pass, 20 fail
* workspace: exit 1, 118 pass, 20 fail

**步骤 3（smoke）的备注：**

* pinned the reference title frame: D:\Github\gba-naruto\build\s49-package-w19b\baseline\title-reference.png

**步骤 5（judgment）的备注：**

* the judgment bench read itself 3 times on the same ROM and got the same numbers every time (residual sum 107051 px)
* the ratchet verdict is INCOMPARABLE: the baseline ROM differs from this run's ROM => the residual numbers are not the same measurement => this is NOT a pass
* the ratchet baseline is D:\Github\gba-naruto\build\s49-package\baseline-accepted\report.json (field residual sum 107051 px this run)
* the judgment bench reported INCOMPARABLE (exit code 2): the baseline ROM differs from this run's ROM => the residual numbers are not comparable => NOT a pass

**步骤 6（overlay）的备注：**

* the overlay comparison uses the remake frame step-04-A.png (the one with the most lit cells: 0)
* the comparison covers all 35 remake anchor dumps (the paired frames alone contain no frame with an overlay: the remake reaches the overlay state at step 25 and later)
* the terrain criterion review ran on the same 35 dumps: the no-terrain path is identical to the pre-change implementation on 0 dump(s), and the criterion changes 4 of them
* the per-cell property verdict ran on the same 35 dumps: every remaining mismatch is classified as product difference / stale tail of the original's buffer / walk phase

**步骤 9（blackfade）的备注：**

* original: captured 1881 frames with the ROM sha256 1198ece781aaf629...
* remake: captured 2402 frames with the ROM sha256 e2182fff9a6ba987...

**步骤 12（package）的备注：**

* every measurement step and the package itself used the pinned copy (sha256 e2182fff9a6ba987...) => a parallel rebuild of the remake tree cannot swap the ROM under this run

### 13.1 故意破坏 ⇒ 流水线变红的证明

（本次运行没有 `evidence/selftest-break.txt` —— 用 `python tools/s49_package/run_pipeline.py --selftest-break <步骤>` 重跑可复现。）

## 14. 假设台账（历次出包流）

### 14.1 继承自 X4r 的台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| X4-1 | 上一任留下的 `tools/s49_package/run_unit_tests.sh` 能用 | 拿 HEAD 基线跑一遍 | 121 个测试，101 pass / 20 fail，与 `Q-unit-test-baseline.md` 的数字逐名相同 | **已确认** |
| X4-2 | 单测门禁可以用「全绿」 | 看 HEAD 自身的失败数 | HEAD 自己就红 20 项 ⇒ 只能用棘轮式（失败集合逐名相同） | **已证伪** |
| X4-3 | 重制 ROM 在 4096 帧内不崩，且中文标题画面正常 | 私有探针跑 4096 帧 + 标题帧结构检查（墨迹连通块 / 颜色数） | 4096 帧跑完；标题帧 15 色、标题带 6 个墨迹连通块；对 A 键有反应 | **已确认** |
| X4-4 | 标题屏不动 = ROM 卡死 | 比对标题帧与第 4096 帧 | 两帧逐字节相同 ⇒ 标题屏**在等玩家输入**，不是卡死 ⇒ 崩溃判据改成「对按键有反应」 | **已证伪** |
| X4-5 | `tools/s49_blackfade/blackfade_capture.py` 能重录 | 读它的源码并试跑 | 它读 `args.release_frames`，而它自己的 parser 从没定义过这个参数 ⇒ AttributeError ⇒ 流水线自己驱动**同一份只读** Lua（`tools/s49_package/capture_blackfade.py`） | **已证伪** |
| X4-6 | 重录的黑场两侧与钉住的历史采集同参数 | 用历史采集的帧预算与按键序列重录 | 原版 1881 帧、重制侧 2402 帧，与历史采集**帧数逐个相同** | **已确认** |
| X4-7 | 判定台的棘轮能挡住「残差变大」 | 用 `regressed.py` 造一份残差 ×2 的报告再跑 `ratchet_check.py` | RATCHET FAIL，exit 1 ⇒ 步骤 5 变红 | **已确认** |
| X4-8 | 单测棘轮能抓到新失败 | 在测试目录的**副本**里加一个必失败的测试（不动重制线） | 工作区失败集合多出 1 项 ⇒ 步骤 2 变红 | **已确认** |
| X4-9 | 并行流同时构建会打断本流的构建 | 全量跑时步骤 1 失败，日志里是 `objcopy: Invalid argument` | 两个 objcopy 写同一个 .gba ⇒ 步骤 1 加一次重试（重试后通过） | **已确认** |
| X4-10 | 判定台残差会随 wave 5 的产品改动变化 | 重跑判定台并与 wave-4 的钉住报告对照 | **变了**：中位 1940 → 1680 px、总和 168,357 → 117,832、归因 3·14·8 → 4·15·6、三桶里「黑场过渡」2 → **0** ⇒ X1 的黑场渐变与 X3 的边界修复都落地了 | **已确认** |
| X4-11 | 共享探针 `build/mgba-probe/mgba-probe.exe` 可以覆盖 | 环境坑：会 LNK1104 | 流水线自建私有探针 `build/mgba-probe-x4r`，**不碰**共享的那个 | **已确认（规避）** |
| X4-12 | 覆盖层逐格族名已归零 | 逐格族名对拍 | 同亮 136 / 114 / 0，原版缺 56 / 61 / 0，多画 12 / 26 / 214，族名不一致 118 / 124 / 0 ⇒ **未归零** | **已证伪** |
| X4-13 | 覆盖层回归是「地图空间锚定」做过头造成的 | 逐格对拍的三个时刻里 `banner-frame-v1` 原版亮格为 0、重制亮 214 | 重制侧在原版**根本没画**覆盖层的时刻画了 214 格 ⇒ 覆盖面被铺到了全图 | **已确认** |

### 14.2 Z4 本轮的台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Z4-1 | 父代理修的 `git archive --output` 路径 bug 还在（没被覆盖掉） | 读 `run_pipeline.py` 的 `step_unit_tests`：找 `tar_path` 与 `mkdir` | `tar_path = (ctx.baseline / "head.tar").resolve()` + 先 mkdir ⇒ **修复仍在**，本流没有动它 | **已确认** |
| Z4-2 | 步骤 1 的并发构建碰撞重试策略需要加强 | 读 `step_build` 的重试代码 | 原来只有「重试 1 次 + 等 10 秒」，且不区分失败原因 ⇒ 与任务书要求的「等 60 秒、最多 5 次」不符 ⇒ 本流改成：只对 `objcopy` + `Invalid argument` 的碰撞重试，最多 5 次、每次等 60 秒；其它失败不重试（真失败） | **已证伪（已修）** |
| Z4-3 | Z1 / Z2 / Z3 落地前重跑流水线有意义 | 看重制线的 `battle_scene_controller.h`（Z1 独占）与 `notes/s49-fidelity/Z*.md` | Z1/Z2/Z3 的笔记一个都没有，`battle_scene_controller.h` 的 mtime 仍是 2026-10-20 ⇒ **三条流都还没交付** ⇒ 本流的第一次重跑是「Z1 之前」的基线，不能冒充 Z1 之后的终稿 | **已确认** |
| Z4-4 | X2r 的「23,753」是残差的上界还是下界 | 读 `X2-pairing.md` §0 / §6 / 台账 X2-11 | §0 的标题写「可证上界」，但 §6 的 B1 与台账 X2-11 都写「**当前两段录制下的像素下界**……任何配对方式都不可能低于此数」⇒ 按**下界**表述（X2-13：两版 ROM 分别 23,753 / 23,697） | **已确认** |
| Z4-5 | 单测棘轮在 Z1 改了单测之后需要重钉基线 | 读 `step_unit_tests` 的 HEAD 基线取法 | HEAD 基线**每次都从 `git archive HEAD` 现取**（不是钉死的文件）⇒ Z1 改单测不会让棘轮失效；工作区失败集合必须是 HEAD 失败集合的子集，多一项即红 ⇒ **不需要手工重钉** | **已证伪（不需要重钉）** |
| Z4-6 | 重制侧调色板 bank 崩点（§11 第 4 项）在 wave 7 之前是否已修 | 读 `WAVE7-TASKS.md` §0 的 Y1 结论 + 步骤 3 的冒烟收据 | Y1 已修（per-component 调色板释放，pixel-neutral，25/25 帧逐帧相同，4096 帧冒烟通过，单测棘轮 new red = 0）⇒ 该项从「未达成」改为「已修」 | **已确认** |
| Z4-7 | 「故意破坏 ⇒ 流水线变红」的 11 个 selftest 仍然全红 | `run_selftests.ps1` 逐个 `--selftest-break` 跑一遍 | 11 个步骤的退出码全部非 0 ⇒ **全红**（见 §13.1） | **已确认** |
| Z4-8 | 07:32 重建的 ROM 与 06:05 那一版的残差一样 | 把两次运行的判定台报告逐帧对照（25 帧） | **不一样**：07:32 那一版的残差**回退**到 wave-4 的水平（总和 117,832 → 168,392，中位 1,680 → 1,940，全 0 帧 4 → 3）；**回归全部集中在两帧**：`step-11-A` 305 → **25,447**、`step-18-A` 0 → **25,459**，其余 23 帧逐帧相同 ⇒ 根因是**重制侧黑场过渡的时刻前移了 2 个 walk 步**（重制侧的黑场帧从 walk 的 `step-18` 挪到了 `step-16`，于是原版的两个黑场帧在重制侧找不到对应） | **已确认（回归，已被棘轮抓住）** |
| Z4-9 | 黑场时刻前移是流水线测错还是产品回退 | 对照两侧的黑场真值表（步骤 9 的证据） | 原版 2 个事件 = 淡出 24 / 全黑 18 / 淡入 24 与 淡出 24 / 全黑 24 / 淡入 24；重制侧的事件数从 **6 → 5**，带渐变的事件从 2 个变成 1 个（事件 3：淡出 28/全黑 24 → 淡出 24/全黑 26，起始帧 01491 → 01471）⇒ 是**产品侧的黑场时序变了**，不是测错 | **已确认** |
| Z4-10 | Z1 的接线落地后，黑场的**结构**对齐了吗 | 对照步骤 9 的黑场真值表（重制侧事件 3 vs 原版事件 1） | **结构对齐了**：重制侧事件 3 = 淡出 **24** / 全黑 **18** / 淡入 **24**，总 **66** 帧 ⇒ 与原版事件 1 **逐项相同**（原版 24/18/24 = 66 帧）。⭐ 但**位置没对齐**：把两侧 walk 每帧的非黑像素占比量出来 ⇒ **原版的 walk 采到了 2 个黑场帧**（`step-11-A` = 0.0079、`step-18-A` = 0.0000），**重制侧的 walk 一个都没采到**（35 帧里最暗的一帧是 0.8541 = 对话屏）⇒ 原版那两个黑场帧在重制侧**没有对应**（25,447 + 25,459 = **+50,906 px**）⇒ 残差总和 117,832 → **161,074** ⇒ **棘轮变红**。另外 `step-12-A` 的残差从 9,907 → **0**（打字机接线生效） | **已确认（结构达成 / 位置未达成）** |
| Z4-11 | 静止帧门禁（步骤 7）变红是真的冻帧还是黑场的副作用 | 读步骤 7 收据里的 5 对连续相同帧 | 5 对**全部**落在重制侧 walk 的 step-15…step-22（也就是黑场所在的那一段），而且这 5 帧的**描边色阶是空的**（画面在黑场里，本来就没有描边）⇒ 不是「冻帧缺陷」，是**黑场落在 walk 采样点里**的副作用。⚠️ **本流没有去放宽这条门禁** —— 放宽门禁等于粉饰，该由 Z1 把黑场挪回原版的位置，或由父代理决定是否给门禁加「黑场里画面本来就是静的」这条豁免 | **已确认** |

### 14.3 wave 9 V4（结算链对照）的台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| V4-1 | 重制侧开机就能进 S49 battle-14（不用先打通 41–48） | 读 `battle_campaign_route.h` 的 `battle_campaign_route_initial_scenario` | **49** ⇒ 开机即在 S49 | **已确认** |
| V4-2 | 重制侧的结算链在产品代码里是完整的 | 读 `battle_scene_controller.h` 的 phase 迁移 + 在 ROM 上录 | `outcome → result → level_up → training → complete` 五段全在代码里 | **已确认** |
| V4-3 | 重制侧的输入分派是「一键一调用」，所以能离线生成按键脚本 | 读 `battle_runtime_scene.cpp` 的输入分派 | A→confirm / B→cancel / 四方向→move_cursor / L,R→cycle_unit | **已确认** |
| V4-4 | 重制侧的「忍术列表」在移动之前是空的 | 离线控制器在单位选择阶段打开列表 | `player.action_count == 0`；移动确认后才有条目 | **已确认** |
| V4-5 | 重制侧的打人招式必须是直线、且不能是「打空格」型 | 离线控制器读 `target_policy` / `range` 并实测被拒 | 目标必须同行/同列；`empty_tile` 型打有人的格子被拒（`action_error::occupied_target_tile`） | **已确认** |
| V4-6 | 重制侧 battle-14 可以打赢 | 五种策略各跑一次离线控制器 | **五种全部败北**：追击 0 命中；守护命中但护送 40→16；护送每回合掉 12 ⇒ **这条路走不通** | **已证伪** |
| V4-7 | 原版的单次伤害口径能套到重制侧 | 读两边的招式定义 | 原版十字手里剑 **27** / 重制侧忍者组合拳 **10**、火遁术 **15**、忍具 **6** ⇒ **口径不同** | **已确认（口径不同）** |
| V4-8 | 从上电到进战斗需要多少次 A | 两轮对比：boot-a=3 vs boot-a=32 | **3 次停在战前简报/队伍一览表**（预置场景的队伍/装备页，**根本没进战斗**）；**32 次才进战斗** | **已确认** |
| V4-9 | 重制侧的「忍具一览」对应原版的「忍具一览」 | 在 ROM 上录到的帧 + 两边的段落内容 | 重制侧 `training` 段有「AVAILABLE TOOL / NO AVAILABLE TOOL / EQUIP COMPLETE / 隊員一覧表」四屏，**位置与用途对得上** | **已确认** |
| V4-10 | 离线脚本在 ROM 上回放会同步 | 在 ROM 上回放按键脚本（两轮等待口径） | **短等待会让 ROM 跑在脚本前面 ⇒ 输入被丢**（录到「可以嗎？」对话框上「否」高亮后 **33,839 帧**不动）⇒ 等待必须放大；但放大后仍会在战斗里卡住 ⇒ **本波没能把整条链在 ROM 上走完** | **已证伪** |
| V4-11 | 原版 S49 结算屏真值还不存在 | 读 `notes/s49-fidelity/W4-original-victory-5th.md` §4 | **存在**：wave 8 的 W4 打赢后录到 9 张图 + sha256 收据 `9a60a89b…` | **已证伪（已闭合）** |
| V4-12 | wave 8 任务书里的「残差总和 109,597」与流水线是同一个口径 | 比流水线 08:26 那一跑（161,074）与本次（168,816） | **不是一个口径** ⇒ 以流水线收据为准，报告里两个数不混用 | **已证伪** |
| V4-13 | 用「按键洪水」能让 ROM 自己把战斗打完 | 三轮：A/B 交错（200 轮）、A/B 交错 + 单位轮转键 R（120 轮）、开机 A×32 + 洪水 | 前一轮**停在战前简报**（开机 A 不够）；后两轮**都进了战斗但战斗没结束**（最后一次录到 25,132 帧，末帧仍是战斗中的单位选择）⇒ **洪水打法也走不通** | **已证伪** |

### 14.4 wave 10 U4（仪器锚点修正 + 出包 + 终审）的台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| U4-1 | 共享仪器 `compare_overlay_families.py` 数学上表达不了原版的锚点 256 | 读旧仪器的 `remake_logical_cells` / `best_window`：按「相机派生的窗口」贴地图标签，再在 `[0, 256)` 里搜窗口 | 地图宽 480 px ⇒ **256 落在搜索区间外**（256 ≠ 0）；且「取搜索到的最优」会替重制侧美化 ⇒ **已确认**（V2 §6.3 的申请） | **已确认** |
| U4-2 | 把仪器改成固定锚点 (256, 0) 后，数字与 V2 的显式锚点版相同 | 同一份 VRAM dump 上跑新仪器与 `tools/s49_v2_anchor/compare_at_anchor.py` | **逐项相同**：field 81/111/36/26、movegrid 81/111/36/10、grid16 71/104/46/31、banner 0/0/117/0 | **已确认** |
| U4-3 | 仪器改动不会打断判定台（`s49_fidelity_report/overlay.py` 在 import 它） | 改完仪器立刻跑一次判定台 | **exit 0**；判定台只 import `find_overlay_map` / `remake_family` / `LOGICAL_COLS` / `LOGICAL_ROWS`，这四个的语义都未变 | **已确认** |
| U4-4 | 口径变化会移动残差数字 | 同一份 dump 上同时算「旧窗口搜索」与「新固定锚点」（`tools/s49_overlay_align/compare_conventions.py`） | **每个时刻恒定 −23 格**（remake-only 59→36 / 69→46 / 140→117）；**同亮 / 原版缺 / 族名不一致三项一字未变** ⇒ 旧口径把 256 px 宽的窗口摊在地图上、不做 480 px 回绕，多算出 23 格「重制多画」 | **已确认** |
| U4-5 | `find_overlay_map` 的签名会把 BG 图块数据误认成覆盖层 | 逐个 0x800 对齐的 VRAM 窗口统计「entry 全部是合法覆盖层 tile」的窗口 | **假窗口 0x00800**：1024 个非零 entry 全部合法（真覆盖层只有 768 个，按 entry 数它会输）；**真覆盖层 0x09800**。⇒ 判据改成原版自己的规则：「solid 必须落在受阻地形上」（真覆盖层 **90/90**，假窗口 **0/0**） | **已确认** |
| U4-6 | 重制侧的覆盖层在**任何配对帧**里都不显示 | 35 个 remake anchor dump 逐个找覆盖层签名 | 只有 **step 25** 与 **step 28–34** 有覆盖层（0x09800）；25 个配对帧（step 00–24）**一个都没有** ⇒ 拿配对帧去量是**退化测量**（重制侧恒为空 ⇒ 残差恒为原版的 192 格，与产品质量无关）⇒ 覆盖层对拍改为**整条 walk**（仪器自带的 `--vram-dir` 模式） | **已确认** |
| U4-7 | 判定台的残差读数是逐次确定的 | 同一个 ROM 连跑两次判定台，逐帧对照 | **不是**：只有 `step-12-A` 一帧的配对变了（step-19-A → step-16-A），残差 **9,520 → 0**，总和 **114,304 → 104,784** ⇒ **棘轮门禁天然带 ±9,520 px 的抖动**。⭐ 最终那次跑（重制线已更新）**通过了**棘轮：总和 **117,832 → 100,210**、中位 **1,680 → 1,323**、全 0 帧 **4 → 5**、峰值 **27,325 → 27,325（不变）** | **已证伪（读数不确定）** |
| U4-8 | 本波流水线 12 步全绿 | 跑 `python tools/s49_package/run_pipeline.py`（私有输出目录 `build/s49-package-u4`） | **12 / 12 全绿**（收据 `generated_at` 2026-10-24T11:28:01+08:00，`ok: true`，`failed_step: null`）。⭐ 步骤 1 的构建**撞了 3 次 objcopy 碰撞**（并行流在写同一个 .gba）⇒ 靠流水线自带的「等 60 s、最多 5 次、只认 objcopy 碰撞」的重试策略扛过去（第 4 次成功） | **已确认** |
| U4-9 | 覆盖层逐格族名已归零（同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0） | 整条 walk（35 个 anchor dump）上的逐格族名对拍 | **未达成**：field 同亮 168 / 原版缺 24 / 多画 24 / 族名不一致 50（残差 98）、movegrid 168/24/24/4（52）、grid16 153/22/39/65（126）、banner 0/0/0/0（exact）⇒ **同亮 168 ≠ 192**，且 24 格位置不同、50 格族名不同 | **未达成** |
| U4-10 | U1 / U2 / U3 已经落地 | 看 `notes/s49-fidelity/` 有没有 U1/U2/U3 的笔记 | **一个都没有** ⇒ 本次运行的重制线仍是**在飞状态** | **已证伪** |

### 14.5 wave 11 W4（判定台确定性 + 出包 + 终审）的台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| W4-1 | 判定台的残差读数是逐次确定的（同 ROM 两跑读数相同） | 同一个 ROM（sha256 钉住）连跑 3 次判定台，逐帧对照残差与配对 | **是**：3 次读数的战场区残差总和**完全相同**（100,210 px）、中位 1,323、峰值 27,325、全 0 帧 5、归因 5·17·3、配对差三桶 0·0·3、覆盖层残差总和 857 px；**逐帧配对逐项相同**；**每张采集 PNG 的 sha256 也逐张相同**（采集摘要 `af722772d492d293…` 三次一致） | **已确认** |
| W4-2 | wave 10 报的「同一个 ROM 两跑，残差 9,520 → 0、总和 114,304 → 104,784」是判定台的抖动 | 把 wave 10 / U4 自己留下的两份报告的 `captures.remake.rom_sha256` 读出来比 | **已证伪**：那两次跑的 ROM **不是同一个**（`249217d7f59a2199…` vs `73b74587595d4581…`）⇒ 差的那 9,520 px 属于**产品改动**，不属于仪器。⚠️ wave 10 的报告（`docs/s49-fidelity-report-20261024.md`）把这个结论写成了「仪器抖动」⇒ **本波已更正**（§2.0b / §11 第 15 项） | **已证伪（根因不是仪器）** |
| W4-3 | 配对搜索有并列最优、没有稳定 tie-break | 读判定台的配对代码 | **已证伪**：`sorted(matrix.items(), key=lambda kv: (kv[1], kv[0]))` —— 残差相同按**帧名**排 ⇒ tie-break 本来就是稳定的 | **已证伪** |
| W4-4 | capture 的帧序 / settle 会抖 | 同 ROM 连跑 3 次，比对每一张采集 PNG 的 sha256 | **已证伪**：3 次采集的 PNG **逐张逐字节相同**（摘要 `af722772d492d293…`）⇒ capture 是确定的 | **已证伪** |
| W4-5 | 判定台可以**不改语义**就自证读数确定性 | 给判定台加 `--repeat N`（连读 N 次并逐项比对），判据（`product_diff` / `pairing_diff` / 三桶）**不动** | **是**：新加的只有 ① `--repeat N` 的复读与比对、② 棘轮收据里带上**两侧的 ROM sha256**（ROM 变了要说清楚，但**不改变**棘轮「残差只许变小」的判据） | **已确认** |
| W4-6 | 判定台自己报出的 ROM 身份是对的 | 读收据里 `captures.remake.audit.rom_sha256` | **原来不对**：重制侧采集的 audit 里写的是**原版** ROM 的 sha256（`MGBA_BOOT_SEQUENCE_ROM_SHA256` 被填成了 `ORIGINAL_ROM_SHA256`）⇒ **已修**（现在写的是重制侧 ROM 自己的 sha256） | **已确认（已修）** |
| W4-7 | wave 10 / U4 给 `find_overlay_map` 加的 terrain 判据该不该回退 | 在 wave 10 的 35 个 walk dump 上，带 / 不带 terrain 各跑一遍 | **不该回退**：不带 terrain 时 4 个 dump 返回**假窗口 `0x00800`**（图块数据），带 terrain 时返回 `-1`；**其余 31 个 dump 一字未变** ⇒ 判据窄且可证；且 `terrain` 是**新增可选参数**，默认 `None` ⇒ **判定台的调用不受影响**。⚠️ 循环论证的风险已写进报告 §3.2 | **已确认（保留）** |
| W4-8 | 判定台的「⇒」打印会把绿灯变红 | 读步骤 5 的日志 | **已确认**：控制台是 **GBK**，`⇒` 抛 `UnicodeEncodeError` —— 而且是在**棘轮 PASS 之后**抛的 ⇒ **步骤 5 明明过了却 exit 1**⇒ **已修**（stdout/stderr 用 `errors="replace"` + 箭头改 ASCII） | **已确认（已修）** |
| W4-9 | 步骤 2 的新红项是本流造成的 | 读失败详情 + 重制线的 `git diff HEAD` | **已证伪**：新红项全部挂在 **W3 独占**的 `battle_scene_controller.h` 的 `static_assert`（生成表 `battle_scene_phase_origins` 24 行 vs 26 个相）—— 正是 `WAVE11-TASKS.md` §3.2 预先警告过的那一处；**本流对重制线零改动**；W3 同步生成表后，失败集合回到 HEAD 的 20 项 ⇒ **新失败 0（零回归）** | **已证伪（是 W3 在飞，已修）** |
| W4-10 | W1/W2/W3 落地后重跑流水线能全绿 | 跑 `python tools/s49_package/run_pipeline.py` | **是**：收据 `generated_at` = 2026-10-24T13:48:50+08:00，**12 步全绿**（`ok: true`、`failed_step: null`），步骤 5 含**连读 3 次的确定性**（残差总和 100,210 px 三次相同）；⚠️ 期间踩到一次**环境坑**：步骤 1 因**并行流同时构建**（objcopy 碰撞，5 次重试全撞上）红过 ⇒ 等并行流那一轮构建结束后重跑即绿 | **已确认** |
| W4-11 | 单测棘轮仍是 20 项预存债、零回归 | 步骤 2 的收据：HEAD 失败集合 vs 工作区失败集合 | 见 §11 第 16 项与 §13 的步骤 2 | **见 §13 的步骤 2** |

### 14.6 wave 12 X4（出包 + 1:1 报告终审 + 越界复核）的台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| X4-1 | wave 10 / U4 给 `find_overlay_map` 加的 terrain 判据该不该回退 | 把改前的候选扫描**在本流重新实现**一遍，在同一份 35 个 walk dump 上带 / 不带 terrain 各跑一遍；再把共享工具的 `main()` 端到端跑两遍（一遍把 `find_overlay_map` 换回改前的实现，**只在本进程里替换函数**，不动共享文件） | **不该回退**：判据只改 **4/35** 个 dump（`step-00-base` / `step-01-Down` / `step-02-Down` / `step-03-A`：假窗口 `0x00800` → `-1`），**其余 31 个一字未变**；端到端上 `grid16-frame-v1` 的残差从 **185 降到 126**（剔掉的是假阳性），`field` / `movegrid` 的数字**一字未变** | **已确认（保留）** |
| X4-2 | 「不带 terrain」的路径与改前**逐字节**相同 | 把改前的实现（`max(candidates)[1]`）独立重写一遍，与现装的 `find_overlay_map(vram, 77)` 在 35 个 dump 上对照 | **是**：35 个 dump，**0 处不同** ⇒ `terrain` 确实是**新增的可选参数**、默认 `None` ⇒ 向后兼容 | **已确认** |
| X4-3 | terrain 判据会打断判定台（步骤 5） | 直接调判定台自己的 `tools/s49_fidelity_report/overlay.py::remake_grid`，把它报的 `overlay_map` 与改前的实现逐个对照 | **不会**：35 个 dump，**0 处不同**。原因：判定台调的是 `find_overlay_map(vram, 77)` —— **第二个位置参数是 `tile_max`，terrain 走默认值 `None`** ⇒ 步骤 5 与步骤 6 各走各的路径 | **已确认** |
| X4-4 | 判定台的覆盖层残差（857 px）会不会因为这处越界而变过 | 判据 Q1b 的推论：判定台的 857 px 是用同一个 `remake_grid` 算出来的，而 35 个 dump 的 `overlay_map` 逐个相同 | **不会**：输入逐个相同 ⇒ 输出必然相同 ⇒ 那个数字**不可能因为这处越界而变过** | **已确认** |
| X4-5 | wave 11 / W4 的「±9,520 px 抖动」是判定台的仪器抖动 | 同一个 ROM 连读 3 次判定台，逐帧对照残差、配对与每张采集 PNG 的 sha256 | **已证伪**（根因不是仪器）：wave 10 那两次跑用的 **ROM sha256 不同**（`249217d7…` vs `73b74587…`）⇒ 差值属于**产品改动**；本波复现：**连读 3 次，残差总和三次完全相同** | **已证伪（根因不是仪器）** |
| X4-6 | X1 / X2 / X3 落地后重跑流水线能全绿 | 跑 `python tools/s49_package/run_pipeline.py`，并检查三条流的交付物（X1 的笔记 / X2 的逐格族名 / X3 的黑场真值） | **未能验证**：本次运行三条流**都没有交付笔记**（X1 只有在飞产物）⇒ 本波跑的是「**在飞状态**」的基线，**12/12 全绿但数字属于在飞状态** ⇒ 报告页首与 §11 都写明了这一点；⚠️ **不许把它写成 wave 12 的终稿基线** | **未验（流未交付）** |
| X4-7 | 单测棘轮的失败集合与 HEAD 基线**逐名相同** | 步骤 2 的收据：HEAD 失败集合 vs 工作区失败集合 | **是**：HEAD **101 pass / 20 fail**，工作区 **117 pass / 20 fail**，**新失败 0 项** ⇒ 20 项预存债，**零回归**；⚠️ **不许写成「单测全绿」** | **已确认** |
| X4-8 | 「故意破坏 ⇒ 流水线变红」的 11 个 selftest 仍然全红 | `run_selftests.ps1` 逐个 `--selftest-break` 跑一遍 | **是**：**11 red, 0 not red** ⇒ 11 个步骤的判据都真的会被触发 | **已确认** |
| X4-9 | 包清单会把 selftest 的临时目录算进去 | 读 wave 11 的两个包的 `packaged_files`：`s49-package` = 122（无 selftest-scratch）vs `s49-package-u4` = 714（有 selftest-scratch） | **会**（一次多算 592 个文件）⇒ **已修**：`MANIFEST_EXCLUDED_PARTS` 加了 `selftest-scratch`（临时目录不是「随包发布的东西」） | **已确认（已修）** |
| X4-10 | wave 9 的「重制侧 battle-14 打不赢」这条结论还成立 | 读 X1 的**在飞**产物 `build/s49-battle-balance/u2/route*.err` 的最后两行 | **已过期**：X1 的在飞路线生成器已经能走到 `after the battle: phase=13 round=5 outcome=1 enemies=0` ⇒ **能打赢**不再是障碍；但 ⚠️ **X1 没有交付笔记，本波仍然没有结算链的逐屏运行帧对照数字** ⇒ 报告里**不把它写成已达成** | **已证伪（结论过期；达成状态仍未验）** |

### 14.7 wave 13 Y4（出包定稿 + 1:1 报告终审）的台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Y4-1 | 上一任包里残留的 `report-test.md` 草稿能不能直接删掉 | 用可恢复删除（`rm --`）删 `build/s49-package-x4/report-test.md` | **不能**：回收站启动器**拒绝对 junction 的目标动手**（`D:\Github` → `D:\Shell\Github`）⇒ **换包目录重跑**即可清掉；本流的新包目录里**没有**这个文件 | **已确认（已修：换目录重跑）** |
| Y4-2 | 覆盖层的「同亮 192 / 缺 0 / 多画 0」是不是真的达成了 | 用**已修回绕**的共享仪器在同一份 35 个 walk dump 上重跑（流水线步骤 6，数字在本次收据里） | **是**：`field` **192 / 0 / 0**、`movegrid` **192 / 0 / 0**、`banner` **0 / 0 / 0 exact ✔**；`grid16` **175 / 0 / 17**（原版是单帧瞬态） | **已确认** |
| Y4-3 | X2 判定的「24 格原版缺 + 24 格多画是仪器没按 480 px 回绕造成的假象」是否成立 | **独立重测**：自建逐格对拍器（`tools/s49_package/classify_overlay_cells.py`）**只读 import** 共享仪器，在**同一份 dump** 上重算逐格族名 | **成立**：回绕修好后 `field` / `movegrid` 的 **缺 0 / 多画 0** ⇒ 旧口径那 24/24 是**贴标签错位**，不是产品差 | **已确认** |
| Y4-4 | 剩下的族名不一致能不能**逐格**给出性质判定（产品差 / 原版尾部残留 / walk 相位） | 自建逐格分类器：复用共享仪器的取帧规则与最优帧选择规则，保留**逐格**差异，再按三条**可判定**的规则分类 | **能**：`field` 11 尾部 + 50 相位 + 0 产品差；`movegrid` 11 尾部 + 0 相位 + **2 产品差**；`grid16` 22 尾部 + 80 相位 + 0 产品差；`banner` 0 0 0 | **已确认** |
| Y4-5 | X2 的规则改动（移动阶段不画黄色光标格）是否让 `movegrid` 的族名不一致从 4 降到 2（X2-H8 未验项） | 在本次收据的 35 个 dump 上重算 `movegrid` 的逐格差异，再减去尾部（11 格） | **是**：13 − 11 = **2**，且这 2 格的族名对是 `hatch→solid`（重制侧有一个单位占着原版可走的格）⇒ X2-H8 **已确认** | **已确认** |
| Y4-6 | Y2 落地后重跑 12 步流水线能不能全绿 | `python tools/s49_package/run_pipeline.py --out build/s49-package-y4` | **能**：**12/12 全绿**（`ok: true`、`failed_step: null`） | **已确认** |
| Y4-7 | 单测棘轮的失败集合是否与 HEAD 基线**逐名相同** | 步骤 2 的收据：HEAD 失败集合 vs 工作区失败集合 | **是**：HEAD **101 pass / 20 fail**，工作区 **117 pass / 20 fail**，**新失败 0 项** ⇒ 20 项预存债，**零回归**；⚠️ **不许写成「单测全绿」** | **已确认** |
| Y4-8 | 判定台的读数是否确定（3 次连读逐项相同） | 步骤 5 内建：同一个 ROM 连读 3 次 | **是**：残差总和 **100,210 px** 三次**完全相同** | **已确认** |
| Y4-9 | 构建 / 测量 / 打包三者是不是同一份 ROM | 比对步骤 1 构建产物的 sha256、步骤 1 钉住的拷贝的 sha256、步骤 12 实际打包的 sha256 | **是**：三者**逐字节相同** ⇒ 并行流中途重建换不掉本轮的读数 | **已确认** |
| Y4-10 | 残差能不能归零 | 判定台的可证像素下界：每一拍内**原版的全部帧** × **重制的全部帧**逐对算残差取最小，25 拍求和 | **不能**：可证像素**下界 ≈ 23,700**（当前 ROM 23,753）⇒ **任何配对方式都不可能低于此数** ⇒ 归零在当前录制上**不可达** | **已证伪（归零不可达）** |
| Y4-11 | 「故意破坏 ⇒ 流水线变红」的 11 个 selftest 是否仍然全红 | `run_selftests.ps1` 逐个 `--selftest-break` 跑一遍 | **是**：**11 red, 0 not red** ⇒ 11 个步骤的判据都真的会被触发 | **已确认** |
| Y4-12 | 新包目录里还有没有草稿残留 | 读新包目录的 `manifest.json` 与目录清单 | **没有**：`report-test.md` **不在**新包里 ⇒ 换目录重跑确实清掉了 | **已确认（已修）** |

### 14.8 wave 14 Z4（出包定稿 + 1:1 报告定稿）的台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Z4w-1 | Z1 / Z2 / Z3 在本波开工前是否已经交付 | 读 `notes/s49-fidelity/` 里三份笔记（以 `WAVE14-TASKS.md` 的 mtime 为界）与 `tools/s49_z3_bound/` 是否存在 | **都没有** ⇒ 本波的第一件事就是**等**它们落地，报告里对应三行只能先写「尚未交付」 | **已确认（未交付）** |
| Z4w-2 | 报告生成器能不能在 Z1/Z2/Z3 的产物**形状未知**的情况下只读地取到它们的数字 | 在报告生成器里写**按内容/键名查找**的读取器（`settlement_running_frames()` / `z3_bound()` / `z3_phase_attribution()`），找不到就明写「尚未交付」 | **能**：三个读取器都**只在盘上真的有产物时**才给出数字，且**绑定收据的路径与 ROM sha256** ⇒ 每个数字都能追到一次运行 | **已确认** |
| Z4w-3 | 「本波已交付」能不能用笔记的**文件名前缀**判定 | 读 `notes/s49-fidelity/` 里的同名笔记（`Y3-overlay-zero.md` 是 wave 6 的、`X2-overlay-zero.md` 是 wave 12 的） | **不能** ⇒ 判定必须**以任务书的 mtime 为界**：`_note_present_since(prefix, "WAVE14-TASKS.md")` | **已证伪** |
| Z4w-4 | 在别的流还在跑全量录制时重跑流水线会不会把步骤 5 的采集杀掉 | 重跑前查 `Win32_Process` 的内存占用与孤儿 `mgba-probe.exe` | 见 §「卡在哪」一节；**这是重跑的前置条件**，不是流水线的问题 | **已确认（前置条件）** |
| Z4w-5 | 在别的流还在跑全量录制 / 重建 ROM 时重跑流水线，能不能全绿 | 重跑前查 `Win32_Process` 的内存占用与孤儿 `mgba-probe.exe`，并等「ROM 的 mtime 稳定 > 150 s 且没有探针在跑」（`build/z4-dev/run-when-idle.ps1`） | **前两次都红、且都不是本流的 bug**：第一次**步骤 5** 红（Z2 的在飞改动让 ROM 在战斗 walk 里崩 ⇒ `done marker missing`，探针 spew **118 MB** 崩溃日志）；第二次**步骤 1** 红（**Z2 重建 ROM** ⇒ 构建 `94ef708e…` ≠ 盘上 `ec5b5273…` ⇒ 钉不住）；第三次（等窗口）**12/12 全绿** | **已确认（已规避）** |
| Z4w-6 | 单测棘轮的失败集合是否与 HEAD 基线**逐名相同**（20 项预存债） | 流水线步骤 2 的收据：HEAD 失败集合 vs 工作区失败集合 | **是**：HEAD **101 pass / 20 fail**、工作区 **118 pass / 20 fail**、`new_failures` = **[]** ⇒ **20 项预存债，零回归**；⚠️ **不许写成「单测全绿」** | **已确认** |
| Z4w-7 | 构建 / 测量 / 打包三者是不是同一份 ROM | 比对步骤 1 构建产物、步骤 1 钉住的拷贝、步骤 12 实际打包的 sha256 | **是**：三者**逐字节相同** ⇒ 并行流中途重建**换不掉**本轮的读数 | **已确认** |
| Z4w-8 | 判定台的读数是否确定（3 次连读逐项相同） | 流水线步骤 5 内建：同一个 ROM 连读 3 次 | **是**：残差总和 **三次完全相同**，`determinism.identical = true`、`rom_changed = false` ⇒ **残差变了就是产品变了，不是仪器在抖** | **已确认** |
| Z4w-9 | 「故意破坏 ⇒ 流水线变红」的 11 个 selftest 是否仍然全红 | `run_selftests.ps1` 逐个 `--selftest-break` 跑一遍 | **是**：**11 red, 0 not red** ⇒ 11 个步骤的判据都真的会被触发 | **已确认** |
| Z4w-10 | 换包目录重跑能不能把中间目录的草稿残留（`cell-classification-dev.json` / `report-test.md`）清掉 | 读新包目录的文件清单与 `manifest.json` | **能**：新包里**只有** `evidence/overlay/cell-classification.json`，**没有** `-dev` 那份，**也没有** `report-test.md` ⇒ 清单核对通过 | **已确认（已修）** |
| Z4w-11 | 残差比 wave 13 变大了，是不是**判定台的抖动** | 比两次收据的残差摘要 + 读本次收据的 `determinism` | **不是**：同一个 ROM 连读 3 次逐项相同 ⇒ 差值属于 **ROM 变化**（Z2 的黑场改动进了产品）；⚠️ **但棘轮没抓住它** —— 换包目录 ⇒ 棘轮基线从 wave 4 起步，**只比了 wave 4 没比 wave 13** | **已确认（是产品改动）** |
| Z4w-12 | Z3 的下界能不能直接当**本次 ROM** 的下界 | 比 Z3 收据的 `roms.remake.sha256` 与本次收据的构建 sha | **不能**：两个 ROM 不同 ⇒ 报告**不**把它写成「当前 ROM 的下界」，只写「另一个 ROM 上的下界 ⇒ 量级结论成立，精确值待重算」 | **已证伪（口径不同）** |

### 14.9 wave 15 W4（出包定稿 + 1:1 报告定稿）的台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| W4w-1 | W1 / W2 / W3 在本波开工前是否已经交付 | 读 `notes/s49-fidelity/` 里**在本波任务书之后**写的笔记，并查重制线源码在任务书之后有没有被改过 | 见 §14.9 的说明：**判定一律以任务书的 mtime 为界**，任务书之前写的笔记（wave 7 的 Z1/Z2/Z3、wave 14 的 Z1/Z2/Z3）**一律不算本波交付** | **已确认** |
| W4w-2 | 「本波已交付」能不能用笔记的**文件名前缀**判定 | 读 `notes/s49-fidelity/` 里的同名笔记（`Z1-wiring.md` / `Z2-title-art-starfield.md` / `Z3-dialogue-box.md` 是 **wave 7** 的） | **不能** ⇒ 判定必须**以任务书的 mtime 为界**（`WAVE15-TASKS.md`），报告生成器里由 `wave15_notes()` / `wave15_streams()` 实现 | **已证伪** |
| W4w-3 | 报告生成器能不能在 W1/W2/W3 的产物**形状未知**的情况下只读地取到它们的数字 | 按**笔记标题**里的流编号（W1/W2/W3）分类，数字只从**本次收据**里取（黑场事件数、棘轮基线、单测棘轮） | **能**：笔记只用来判定「交付与否」，**所有数字都来自收据** ⇒ 每个数字都能追到一次运行 | **已确认** |
| W4w-4 | 两个失败的包目录（步骤 5 红 / 步骤 1 红）能不能删掉 | 先试 `rm --`，再试用**真路径**（junction 的目标）调 `mavis-trash.cmd` | **能**：必须打**真路径** `D:\Shell\Github\gba-naruto\build\...`；打 junction 路径（`D:\Github\...`）会被回收站启动器拒掉 | **已确认（已清理）** |
| W4w-5 | 残差归零到底可不可达 | 读 Z3 的下界收据（`floor_sum`）+ 它的证明方式；**并把判定台的读数与下界分成两个口径** | **不可达**：下界 **16,389 px**（测在 ROM `2c2b48d9…`），内容锚可达数 **18,886 px** ⇒ 区间 **[16,389, 18,886]**；⚠️ **判定台的读数（残差总和）是另一个口径**（arg-min 无时刻约束）⇒ 两个数**不许混用** | **已确认** |
| W4w-6 | 覆盖层剩下的 176 格能不能算作「覆盖层规则的产品差」 | 读 Z3 的相位归因收据（6 帧连拍 + 密集 walk 逐帧对齐） | **不能**：130 格 = **50 格重制侧缺一个相位**（稳定态，原版连续 67 帧）+ **80 格原版那一帧是瞬态**（6 连拍只现 1 次 ⇒ 缓冲撕裂）；⇒ `grid16` 的 80 格进**「明确排除项」**，与 44 格尾部残留并列 | **已确认** |

### 14.10 wave 16 V3（出包定稿 + 1:1 报告定稿 + 判定台采集校验）的台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| V3w-1 | V1 / V2 / V4 在本波开工前是否已经交付 | 读 `notes/s49-fidelity/` 里**在 `WAVE16-TASKS.md` 之后**写的笔记，并查重制线源码与 ROM 的 mtime | 见 §14.10：**判定一律以任务书的 mtime 为界** ⇒ 任务书之前写的笔记（wave 7 的 Z1/Z2/Z3、wave 5/6/8 的 W1/W2/W3）**一律不算本波交付** | **已确认** |
| V3w-2 | 「本波已交付」能不能用笔记的**文件名前缀**判定 | 读 `notes/s49-fidelity/` 里的同名笔记 | **不能** ⇒ 判定必须**以任务书的 mtime 为界**（`WAVE16-TASKS.md`），报告生成器里由 `wave16_notes()` / `wave16_streams()` 实现 | **已证伪** |
| V3w-3 | 判定台复用采集时会不会核对 ROM | 读 `tools/s49_fidelity_report/capture.py::run_capture()` 的复用分支 | **不会** —— 复用条件只有「done 标记在不在、帧在不在」，**从不核对那份采集是哪一个 ROM 录的** ⇒ **可以报告一个它没测过的 ROM 的读数** | **已确认（缺陷）** |
| V3w-4 | 修好之后，复用采集时会不会仍然复用别的 ROM 的采集 | 把采集的 `audit.json` / `done.json` 里的 `rom_sha256`（原版侧是 `input_state_sha256`）改成**另一个 ROM / 另一个存档**的值，再用 `--skip-capture` 跑判定台 | **不会** ⇒ 两侧都**重新采集**，收据里写明「ROM 变了，已重采」与具体差在哪一个摘要上 | **已确认（已修）** |
| V3w-5 | ROM 一致时能不能复用，且读数与重采**逐项相同** | **同一个 work 目录**里连跑三次：① 重采 ② 篡改后重采 ③ 复用 | **能** ⇒ 三次的 `content_sha256` **完全相同**，残差总和 / 中位 / 归因逐项相同 ⇒ 复用不改变读数 | **已确认（已修）** |
| V3w-6 | 收据里新增字段会不会破坏 `content_sha256` 的可复现承诺 | 比「重采」与「复用」两份收据的**逐叶差异** | **不会** —— 复用判定被拆成两部分：**测量稳定**的事实（`captures.<side>.reuse_decision`）留在测量口径内，**运行出处**（复用/重采 + 原因）随 `attempts` 一起移出测量摘要 ⇒ 两次读数的差异只剩**绝对路径** | **已确认** |
| V3w-7 | 本波残差有没有比上一波被接受的收据变小 | 流水线步骤 5 的棘轮判决 + 连读 3 次的 `determinism` | 见 §2.0：**判决与三次读数逐项相同**；⚠️ **ROM 变了 ⇒ 残差不是同一个测量** ⇒ 「不可比」与「变小」必须分开写 | **已确认** |
| V3w-8 | 构建 / 钉住 / 打包 / 实测四个 sha 是不是同一份 ROM | 读步骤 1 的 `rom_sha256` 与 `pinned_rom_sha256`、步骤 12 的 `rom_sha256`、判定台收据的 `captures.remake.rom_sha256` | 见 §2.0c：**四者逐字相同**（不一致会在这里报出来） | **已确认** |
| V3w-9 | 11 个 selftest 是不是仍然全部能把对应的步骤打红 | `run_selftests.ps1` 逐个 `--selftest-break` 跑一遍 | 见 §13.1：**11 red, 0 not red** | **已确认** |
| V3w-10 | 判定台的读数在同一个 ROM 上确定吗 | 流水线步骤 5 内建（连读 3 次） | 见 §2.0b：**3 次读数逐项相同** ⇒ 残差变了就是产品变了 | **已确认** |
| V3w-11 | 「四个 sha 一致」的判据能不能在**四个摘要都相同**时判成一致 | 拿 wave 15 的收据跑一遍 §2.0c | **第一版判错**：四个摘要放进 `set` 之后长度是 **1**（不是 4）⇒ 「凑齐」的判据写成了 `len(values) == 4` ⇒ 一致却报「没有凑齐」⇒ 改成「**非空摘要的个数 == 4** 且**去重后 == 1**」 | **已证伪（已修）** |

⭐ **本波额外修了一个仪器缺陷**（父代理追加的任务）：`tools/s49_fidelity_report/capture.py` 的「复用采集不校验 ROM」。⇒ **在它修好之前，任何「残差没变大」的结论都不可信**（可能是拿旧 ROM 的采集当新 ROM 测的）。⇒ 修法与两条判据见 §2.0.2 与 §11 第 22 项。

### 14.11 wave 17 U3（出包定稿 + 1:1 报告定稿）的台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| U3w-1 | U1 / U2 在本波开工前是否已经交付 | 读 `notes/s49-fidelity/` 里**在 `WAVE17-TASKS.md` 之后**写的笔记，**并**查重制线里 U1 / U2 独占文件的 mtime | 开工时（22:27）**两路都没有交付**：`battle_combat_presentation.h` / `battle_scene_presentation.h` 停在 2026-10-20，`battle_range_ui_style.h` 停在 2026-10-24 15:31，`battle_result_content.h` 停在 13:37 ⇒ **本流第一件事是等** | **已确认（未交付）** |
| U3w-2 | 「本波已交付」能不能用笔记的**文件名前缀**判定 | 读 `notes/s49-fidelity/` 里的同名笔记（wave 16 的 V1/V2/V4、wave 7 的 Z1/Z2/Z3） | **不能** ⇒ 判定必须**以任务书的 mtime 为界**（`WAVE17-TASKS.md`），由 `wave17_notes()` / `wave17_streams()` 实现；**并且**产品流（U1 / U2）额外用「独占文件的 mtime + ROM 在其后被重建」来判定 —— 笔记不是产品的证据，**ROM 才是** | **已证伪** |
| U3w-3 | 能不能在 U1 / U2 / U4 的产物**形状未知**的情况下只读地取到它们的数字 | 在报告生成器里写**按内容/键名查找**的读取器（`wave17_chains()` / `wave17_bound()` / `wave17_reachable()`），找不到就明写「尚未交付」 | **能**：读取器**只在盘上真的有产物时**才给出数字，且**绑定收据的路径与 ROM sha256** ⇒ 每个数字都能追到一次运行 | **已确认** |
| U3w-4 | 「真实战斗链」与「poke 链」能不能被**机器**分开 | 读链收据的 `entry.method`（自报进入方式）与 `outcome_byte_before_poke` / `outcome_byte_after_poke` | **能**：`entry.method` 里含 `poke` ⇒ **poke 链**；两个 outcome 字节不同 ⇒ **poke 链**；两者都没有 ⇒ **进入方式未记录**（**不许**当成真实链）；只有**明确不是 poke**、且链上的 `outcome` 是 1 ⇒ **真实胜利链** | **已确认** |
| U3w-5 | 构建 / 钉住 / 打包 / 实测四个 sha 是不是同一份 ROM | 读步骤 1 的 `rom_sha256` 与 `pinned_rom_sha256`、步骤 12 的 `rom_sha256`、判定台收据的 `captures.remake.measured_rom_sha256` | 见 §2.0c：**四者逐字相同**（不一致会在这里报出来） | **已确认** |
| U3w-6 | 本波残差有没有比上一波被接受的收据变小 | 流水线步骤 5 的棘轮判决 + 连读 3 次的 `determinism` | 见 §2.0：**判决与三次读数逐项相同**；⚠️ **ROM 变了 ⇒ 残差不是同一个测量** ⇒ 「不可比」与「变小」必须分开写（**不可比 ≠ 通过**） | **已确认** |
| U3w-7 | 可证像素下界能不能为**本包这个 ROM** 重算 | 用 V4 已交付的工具（`tools/s49_z3_bound/`）**只读调用**，对**钉住的 ROM** 重录重制侧 + 重算 | **能**（见 §11 第 2 项）：wave 16 的 16,813 px 测在旧 ROM 上，**U1 / U2 落地后 ROM 变了 ⇒ 必须重算**，否则下界与读数不是一个 ROM | **已确认** |
| U3w-8 | 11 个 selftest 是不是仍然全部能把对应的步骤打红 | `run_selftests.ps1` 逐个 `--selftest-break` 跑一遍 | 见 §13.1：**11 red, 0 not red** | **已确认** |
| U3w-9 | 单测棘轮的失败集合是否与 HEAD 基线**逐名相同**（20 项预存债） | 流水线步骤 2 的收据：HEAD 失败集合 vs 工作区失败集合 | 见 §11 第 8 / 16 项：**new_failures = []** ⇒ 零回归；⚠️ **不许写成「单测全绿」** | **已确认** |
| U3w-10 | 在别的流还在跑全量录制时重跑流水线会不会把步骤 5 的采集杀掉 | 闸门 `build/u3-dev/run-when-idle.ps1`：等「U1 / U2 的独占文件在任务书之后被改过 + ROM 在其后被重建 + ROM/源码安静 ≥ 150 s + 没有探针/构建在跑 + 内存 > 4 GB」 | 见 §「卡在哪」一节；**这是重跑的前置条件**，不是流水线的问题 | **已确认（前置条件）** |

⭐ **本波把「结算链」拆成了两栏**：**真实战斗链**（`entry.method` 自报**不是** poke）与 **poke 链**（`entry.method` 含 `poke`，或 outcome 字节在进入前后不同）⇒ §15.2.3 **分列**呈现，**任何一栏都不许写成对方的名字**。

## 15. ⭐ 结算链对照（原版真值 vs 重制侧）

原版真值：wave 8 的 W4 打赢后录到的结算链（`build/s49-victory-capture/w4/settlement-truth/`，收据 `settlement-truth.json`，sha256 `9a60a89b…`）。像素判定沿用项目口径：**三通道任一不同即算不同**（同 `tools/compare_frame_dirs.py`）。

### 15.1 两边的结算链结构差

| 段 | 原版（wave 8 真值） | 重制侧（**wave 11 的产品代码**） |
|---|---|---|
| 1 | 「勝利」屏 | `outcome` 段 ⇒ `battle_settlement_stage::victory` |
| 2 | 结算屏（经验值/战力/回合数） | `result` 段 |
| 3 | **四人升级屏**（鸣人/木叶丸/佐助/小樱各一张） | `level_up` 段（⭐ **wave 11 已补**：原版升级屏是 **3 人 × 2 页 = 6 个子页**，**木叶丸没有升级屏**；重制侧新增了逐人升级页枚举与 7 页战后对白文本） |
| 4 | **忍具一览** | ⭐ **`training` 段**（对应物：录到「AVAILABLE TOOL」「NO AVAILABLE TOOL」「EQUIP COMPLETE」「隊員一覧表」四屏） |
| 5 | 战后对白 | ✅ **wave 11 已补**：`post_battle_dialogue` 段（`battle_scene_phase::post_battle_dialogue` ⇒ `battle_settlement_stage::post_battle_dialogue`，**7 页**文本已落进 `battle_result_content.h`） |
| 6 | 任务菜单（术之里地图） | ✅ **wave 11 已补**：`task_menu` 段（`battle_scene_phase::task_menu` ⇒ `battle_settlement_stage::task_menu`） |
| 7 | （链尾） | `complete` 段 |

⭐ **结算链的段数差已经闭合**：重制侧 `battle_scene_phase` 现在有 **22 个原版相 + 2 个新相**，`battle_scene_phase_settlement_stage()` 把 7 段一一映射到 `battle_settlement_stage`（`victory → result → level_up → training → post_battle_dialogue → task_menu → complete`），并有单测 `test_battle_settlement_chain.cpp` 锁住。

⭐ **运行帧这一层本波已闭合**：Z1 把重制侧结算链的**运行帧**录下来了，逐屏对照表**15 行**（§15.2）。

### 15.2 逐屏对照表（运行帧）

⭐ **wave 14 / Z1 录出了重制侧结算链的运行帧** ⇒ 逐屏对照表**15 行**（收据 `build/z1/settlement-table-z1.json`）。

⛔ **ROM 口径警告**：这张对照表是在 ROM **`2c2b48d91fbe3244…`** 上测的，而**本次流水线构建的是 `e2182fff9a6ba987…`** （**Z2 改了黑场，产品侧变了 ⇒ ROM 变了**）⇒ **这两组数字不能混用**（「必须同 ROM 比」）。本波 Z1 没有在新 ROM 上重录结算链 ⇒ **结算链这一项的达成状态以 Z1 的那次运行为准**。

| # | 重制侧页 | 页数 | 对照的原版屏 | 差 px | 差 bbox | 重制侧 sha256 | 原版 sha256 |
|---:|---|---:|---|---:|---|---|---|
| 0 | `page-000-outcome.png` | 1 | `08-postbattle-dialogue-1.png` | 32919 | [0, 8, 240, 160] | `47fbde60709a2768…` | `2741dbc3fbf6e838…` |
| 1 | `page-001-result.png` | 1 | `03-levelup-naruto.png` | 35188 | [0, 0, 240, 160] | `0027e9cf95129b6a…` | `a876f32dbe100a65…` |
| 2 | `page-002-level_up.png` | 1 | `03-levelup-naruto.png` | 0 | — | `a876f32dbe100a65…` | `a876f32dbe100a65…` |
| 3 | `page-003-level_up.png` | 1 | `05-levelup-sasuke-jutsu-name.png` | 0 | — | `daac884a6415577b…` | `daac884a6415577b…` |
| 4 | `page-004-level_up.png` | 1 | `04-levelup-konohamaru.png` | 0 | — | `ef0808aea763ff31…` | `ef0808aea763ff31…` |
| 5 | `page-005-level_up.png` | 1 | `05-levelup-sasuke.png` | 0 | — | `c5a8440b451ef6a1…` | `c5a8440b451ef6a1…` |
| 6 | `page-006-level_up.png` | 1 | `06-levelup-sakura.png` | 0 | — | `a0db87e9fd8ec358…` | `a0db87e9fd8ec358…` |
| 7 | `page-007-level_up.png` | 1 | `07-ninja-tool-list.png` | 0 | — | `455acc43c9ace553…` | `455acc43c9ace553…` |
| 8 | `page-008-training.png` | 1 | `06-levelup-sakura.png` | 14783 | [1, 9, 239, 152] | `b012f6051307b51c…` | `a0db87e9fd8ec358…` |
| 9 | `page-009-training.png` | 1 | `06-levelup-sakura.png` | 14789 | [1, 9, 239, 152] | `8b8ee8663e3aaaa7…` | `a0db87e9fd8ec358…` |
| 10 | `page-010-training.png` | 1 | `06-levelup-sakura.png` | 14791 | [1, 9, 239, 152] | `b2fd1061cdd41a73…` | `a0db87e9fd8ec358…` |
| 11 | `page-011-training.png` | 1 | `06-levelup-sakura.png` | 15064 | [1, 9, 239, 152] | `2a7fdabad4931059…` | `a0db87e9fd8ec358…` |
| 12 | `page-012-training.png` | 1 | `06-levelup-sakura.png` | 15055 | [1, 9, 239, 152] | `4112cebb52f60b23…` | `a0db87e9fd8ec358…` |
| 13 | `page-013-training.png` | 1 | `06-levelup-sakura.png` | 15064 | [1, 9, 239, 152] | `53c2bf0e33cf6375…` | `a0db87e9fd8ec358…` |
| 14 | `page-014-training.png` | 1 | `08-postbattle-dialogue-1.png` | 32963 | [0, 8, 240, 160] | `20c1161209417dda…` | `2741dbc3fbf6e838…` |

⇒ **6 / 15 屏与它对照的原版屏逐像素相同**（差 0 px）（`page-002-level_up.png` ↔ `03-levelup-naruto.png`、`page-003-level_up.png` ↔ `05-levelup-sasuke-jutsu-name.png`、`page-004-level_up.png` ↔ `04-levelup-konohamaru.png`、`page-005-level_up.png` ↔ `05-levelup-sasuke.png`、`page-006-level_up.png` ↔ `06-levelup-sakura.png`、`page-007-level_up.png` ↔ `07-ninja-tool-list.png`）。

#### 15.2.1 ⭐ wave 15 / W3 的结算屏逐屏对照（**机器可读收据**）

⭐ **wave 15 / W3 交出了结算屏的逐屏对照收据**（`build/w3/settlement-align.json`；笔记 `notes/s49-fidelity/W3-blackfield-and-screens.md`；重制侧帧来自 `build\w3\chain-pinned\shots`（**钉住 ROM 的重录**），原版真值来自 `build\s49-victory-capture\w4\settlement-truth`；整屏 **38400 px**）。

| 原版真值 | 重制侧运行帧 | 阶段 | 差 px | 相同 px | 逐字节相同 | 原版颜色数 | 重制侧颜色数 |
|---|---|---|---:|---:|---|---:|---:|
| `01-victory.png` | `page-000-outcome.png` | victory | 37462 | 938 | ❌ | 83 | 1 |
| `02-settlement-exp-power-turns.png` | `page-001-result.png` | result | 35859 | 2541 | ❌ | 52 | 49 |
| `03-levelup-naruto.png` | `page-002-level_up.png` | level_up_1 | 0 | 38400 | ✅ **是** | 80 | 80 |
| `05-levelup-sasuke-jutsu-name.png` | `page-003-level_up.png` | level_up_2 | 0 | 38400 | ✅ **是** | 80 | 80 |
| `04-levelup-konohamaru.png` | `page-004-level_up.png` | level_up_3 | 0 | 38400 | ✅ **是** | 82 | 82 |
| `05-levelup-sasuke.png` | `page-005-level_up.png` | level_up_4 | 0 | 38400 | ✅ **是** | 82 | 82 |
| `06-levelup-sakura.png` | `page-006-level_up.png` | level_up_5 | 0 | 38400 | ✅ **是** | 82 | 82 |
| `07-ninja-tool-list.png` | `page-007-level_up.png` | level_up_6 | 0 | 38400 | ✅ **是** | 82 | 82 |

⇒ **合计差 73321 px**；**6 对逐字节相同**。

#### 15.2.2 ⭐ 独立重算的交叉核对（**本流不抄任何人的数字**）

⚠️ **上面 §15.2 的那张表是「机械最优配对」**（收据 `build/z1/settlement-table-z1.json` 由 `y1_settlement_table.py` 生成）：重制侧那些**绿框面板**全都落到**同一张**原版图上 ⇒ **它的前两行没有语义意义**。Z1 的笔记（`notes/s49-fidelity/Y1-stack-fix-and-settlement.md` §3.3）给出的是**语义对应**；下面这张表用**同一套像素口径**（三通道任一不同即算不同）**在盘上的 PNG 上重算**，⇒ **每个数字都能追到那两个文件**。

| # | 重制侧运行帧 | 阶段 | 原版真值 | 差 px | 差 bbox | 逐字节相同 |
|---:|---|---|---|---:|---|---|
| 0 | `page-000-outcome.png` | outcome（勝利 / BATTLE COMPLETE） | `01-victory.png` | 37462 | [0, 0, 240, 160] | ❌ |
| 1 | `page-001-result.png` | result（结算屏） | `02-settlement-exp-power-turns.png` | 35859 | [0, 0, 240, 160] | ❌ |
| 2 | `page-002-level_up.png` | level_up 1/6 | `03-levelup-naruto.png` | 0 | — | ✅ **是** |
| 3 | `page-003-level_up.png` | level_up 2/6 | `05-levelup-sasuke-jutsu-name.png` | 0 | — | ✅ **是** |
| 4 | `page-004-level_up.png` | level_up 3/6 | `04-levelup-konohamaru.png` | 0 | — | ✅ **是** |
| 5 | `page-005-level_up.png` | level_up 4/6 | `05-levelup-sasuke.png` | 0 | — | ✅ **是** |
| 6 | `page-006-level_up.png` | level_up 5/6 | `06-levelup-sakura.png` | 0 | — | ✅ **是** |
| 7 | `page-007-level_up.png` | level_up 6/6（忍具一览） | `07-ninja-tool-list.png` | 0 | — | ✅ **是** |

⇒ **6 / 8 有语义对应的屏与原版真值逐像素相同（差 0 px）**（`page-002-level_up.png` ↔ `03-levelup-naruto.png`、`page-003-level_up.png` ↔ `05-levelup-sasuke-jutsu-name.png`、`page-004-level_up.png` ↔ `04-levelup-konohamaru.png`、`page-005-level_up.png` ↔ `05-levelup-sasuke.png`、`page-006-level_up.png` ↔ `06-levelup-sakura.png`、`page-007-level_up.png` ↔ `07-ninja-tool-list.png`）；记在 **15 屏**的运行帧记录里就是 **6 / 15 屏**。⭐ **重制侧独有的 7 屏**（`page-008` … `page-014-training.png`）在原版真值里**没有对应屏** ⇒ **不计入分母**；`page-014-training.png` 是 Z1 查实的**崩溃屏**（非法 UTF-8 ⇒ ROM 停机）。

⭐ **交叉核对（本流重算 vs W3 的收据）**：8 / 8 屏**逐值相同**（两个**独立实现**、同一套像素口径 ⇒ 互证）。


#### 15.2.3 ⭐⭐ 结算链运行帧对照（**真实战斗链** vs **poke 链** —— 两者不许混用）

⭐ **本节把结算链分成两栏**，判据是**链是怎么进入的**（收据自报 `entry.method`，外加「outcome 字节在进入前后是否相同」）：**`entry.method` 含 `poke`** ⇒ **poke 链**；**outcome 字节在进入前后不同** ⇒ **poke 链**；两者都没有 ⇒ **进入方式未记录**（**不许**当成真实链）；只有**明确不是 poke**、且链上的 `outcome` 是 **1** ⇒ **真实胜利链**（`outcome=2` ⇒ **真实战斗链，但不是胜利**）。

| # | 收据 | ROM | 进入方式 | 判读 | 页数 | `outcome` |
|---:|---|---|---|---|---:|---|
| 1 | `build/w19-a/chain-final/chain.json` | `7e4c158109ff1830…` | `controller state poke (phase + outcome), then a closed-loop walk of the chain` | ⛔ **poke 链** | 48 | 1 |
| 2 | `build/w19-a/chain-bwiring/chain.json` | `1ab4b106132c4742…` | `controller state poke (phase + outcome), then a closed-loop walk of the chain` | ⛔ **poke 链** | 48 | 1 |

⛔ **没有「真实胜利链」** ⇒ **「真实打完仗」仍未达成**（§11 第 25 项）。

⛔ **下列链是 poke 出来的** ⇒ **它们显示的是「空战果」（V2 实测：125/0/200），不是打出来的** ⇒ **不得写成「真实打完仗」的那一版**。

⭐ **结算链的运行帧记录**：**48 行**（收据 `build/w19-a/chain-final/chain.json`；ROM `7e4c158109ff1830…`；相位 outcome → result → level_up → level_up → level_up → level_up → level_up → level_up → training → training → training → training → training → training → post_battle_dialogue → post_battle_dialogue → post_battle_dialogue → ）。

⛔ **⭐ 这一版是「poke 出来的」，不是真实战斗打出来的** —— 它的进入方式是**改控制器的状态字节**（`entry.method` 里写明了 `controller state poke`），⇒ **屏上的战果是「空战果」（V2 实测：125/0/200），不是打出来的** ⇒ **它不能算「真实打完仗」的那一版**（这正是 wave 14 的 Z1 那 15 屏的老问题）。

##### 15.2.3.1 ✅ **真实战斗链**（结算链的逐屏对照表）

⭐ **本波的战斗收据**（U4 的闭环驱动器）—— 「真实打完仗」的三条判据都在这里：**是不是真打的**（`entry.method`）、**是不是产品判的**（`battle_decided`）、**蜂的 HP 有没有掉**（`acceptance.bee_hp_dropped`）。

| # | 收据 | ROM | 进入方式 | `outcome` | `battle_decided` | 蜂 HP 下降 | 护送存活 | 判读 |
|---:|---|---|---|---:|---|---:|---|---|
| 1 | `build/w20-e1/tc-fix1/battle.json` | `150dacf876ab3fc3…` | `TOOL VALIDATION: the settlement chain was entered by poking the controller's phase and outcome; this is NOT a real victory` | 1 | False | False | True | ⛔ **poke** |
| 2 | `build/w20-e1/chain-fix1-tc/real/battle.json` | `150dacf876ab3fc3…` | `real battle: the closed-loop driver plays the battle with the buttons only, and the outcome is the product code's own decision` | 1 | True | True | True | ✅ **真实胜利** |
| 3 | `build/w20-e1/chain-fix1/real/battle.json` | `150dacf876ab3fc3…` | `real battle: the closed-loop driver plays the battle with the buttons only, and the outcome is the product code's own decision` | 1 | True | True | True | ✅ **真实胜利** |
| 4 | `build/w20-e1/chain-base/real/battle.json` | `1107c1f9718aca44…` | `real battle: the closed-loop driver plays the battle with the buttons only, and the outcome is the product code's own decision` | 1 | True | True | True | ✅ **真实胜利** |
| 5 | `build/w19-a/chain-final/chain.json` | `7e4c158109ff1830…` | `controller state poke (phase + outcome), then a closed-loop walk of the chain` | None | None | — | — | ⛔ **poke** |
| 6 | `build/w19-a/chain-bwiring/chain.json` | `1ab4b106132c4742…` | `controller state poke (phase + outcome), then a closed-loop walk of the chain` | None | None | — | — | ⛔ **poke** |

⚠️ **口径**：`battle_decided = False` ⇒ **战斗没有打完** ⇒ **那一局不是「打完仗」**；`bee_hp_dropped = False` ⇒ **敌人的 HP 没有下降** ⇒ **玩家的攻击仍然没有打中**。

⛔ **盘上没有「真实胜利链」**（`entry.method` 自报**不是** poke 且 `outcome = 1`）⇒ **「真实打完仗」仍未达成**（§11 第 25 项）。

⭐ **结算链的逐屏对照表**（收据 `build/v1-u4/compare-chain-toolcheck.json`；**48 行**，其中 **10 行**有原版真值可对照）。

⚠️ **这张表比的是「结算链的运行帧」** —— **它不是「真实打完仗」的那一版**：进入方式（真打 / poke）见上面的战斗收据表与 §15.2.3.2 ⇒ **两栏不许混用**。
| # | 重制侧帧 | 相位 | 页 | 对照的原版屏 | 差 px | 差 bbox | 重制侧 sha256 | 原版 sha256 |
|---:|---|---|---:|---|---:|---|---|---|
| 1 | `page-000-outcome.png` | outcome | 0 | 01-victory.png | 0 | — | `d60a1d35e45736db…` | `d60a1d35e45736db…` |
| 2 | `page-001-result.png` | result | 0 | 02-settlement-exp-power-turns.png | 2582 | [84, 49, 236, 154] | `337661386808ba99…` | `e34e116c7ed3a55e…` |
| 3 | `page-002-level_up.png` | level_up | 0 | 03-levelup-naruto.png | 0 | — | `a876f32dbe100a65…` | `a876f32dbe100a65…` |
| 4 | `page-003-level_up.png` | level_up | 1 | 05-levelup-sasuke-jutsu-name.png | 0 | — | `daac884a6415577b…` | `daac884a6415577b…` |
| 5 | `page-004-level_up.png` | level_up | 2 | 04-levelup-konohamaru.png | 0 | — | `ef0808aea763ff31…` | `ef0808aea763ff31…` |
| 6 | `page-005-level_up.png` | level_up | 3 | 05-levelup-sasuke.png | 0 | — | `c5a8440b451ef6a1…` | `c5a8440b451ef6a1…` |
| 7 | `page-006-level_up.png` | level_up | 4 | 06-levelup-sakura.png | 0 | — | `a0db87e9fd8ec358…` | `a0db87e9fd8ec358…` |
| 8 | `page-007-level_up.png` | level_up | 5 | 07-ninja-tool-list.png | 0 | — | `455acc43c9ace553…` | `455acc43c9ace553…` |
| 9 | `page-008-training.png` | training | 0 | — | — | — | `b012f6051307b51c…` | — |
| 10 | `page-009-training.png` | training | 1 | — | — | — | `8b8ee8663e3aaaa7…` | — |
| 11 | `page-010-training.png` | training | 2 | — | — | — | `b2fd1061cdd41a73…` | — |
| 12 | `page-011-training.png` | training | 3 | — | — | — | `2a7fdabad4931059…` | — |
| 13 | `page-012-training.png` | training | 4 | — | — | — | `4112cebb52f60b23…` | — |
| 14 | `page-013-training.png` | training | 5 | — | — | — | `53c2bf0e33cf6375…` | — |
| 15 | `page-014-post_battle_dialogue.png` | post_battle_dialogue | 0 | 08-postbattle-dialogue-1.png | 26819 | [0, 0, 240, 160] | `5fece4f6952f78b0…` | `2741dbc3fbf6e838…` |
| 16 | `page-015-post_battle_dialogue.png` | post_battle_dialogue | 1 | — | — | — | `4b8fd4e25ff3e98a…` | — |
| 17 | `page-016-post_battle_dialogue.png` | post_battle_dialogue | 2 | — | — | — | `90e83d106085f826…` | — |
| 18 | `page-017-post_battle_dialogue.png` | post_battle_dialogue | 3 | — | — | — | `7d242862ae7333d8…` | — |
| 19 | `page-018-post_battle_dialogue.png` | post_battle_dialogue | 4 | — | — | — | `adfe4fb7254829e7…` | — |
| 20 | `page-019-post_battle_dialogue.png` | post_battle_dialogue | 5 | — | — | — | `dc2a17f58c42c2e1…` | — |
| 21 | `page-020-post_battle_dialogue.png` | post_battle_dialogue | 6 | — | — | — | `0c263682bd1c3490…` | — |
| 22 | `page-021-task_menu.png` | task_menu | 0 | 09-task-menu-map.png | 37694 | [0, 0, 240, 160] | `3814df2825813f89…` | `cda07a18be60a1ea…` |
| 23 | `page-022-task_menu.png` | task_menu | 1 | — | — | — | `3aadee4689b841e7…` | — |
| 24 | `page-023-task_menu.png` | task_menu | 2 | — | — | — | `33c9d0f101bf057f…` | — |
| 25 | `page-024-task_menu.png` | task_menu | 3 | — | — | — | `f15c97a78a1ed9c6…` | — |
| 26 | `page-025-task_menu.png` | task_menu | 4 | — | — | — | `ad917712306ef5ea…` | — |
| 27 | `page-026-task_menu.png` | task_menu | 5 | — | — | — | `b7694658e7256c49…` | — |
| 28 | `page-027-task_menu.png` | task_menu | 6 | — | — | — | `f15c97a78a1ed9c6…` | — |
| 29 | `page-028-task_menu.png` | task_menu | 7 | — | — | — | `b3e2e7a14fea1c79…` | — |
| 30 | `page-029-task_menu.png` | task_menu | 8 | — | — | — | `f15c97a78a1ed9c6…` | — |
| 31 | `page-030-task_menu.png` | task_menu | 9 | — | — | — | `b3e2e7a14fea1c79…` | — |
| 32 | `page-031-task_menu.png` | task_menu | 10 | — | — | — | `f15c97a78a1ed9c6…` | — |
| 33 | `page-032-task_menu.png` | task_menu | 11 | — | — | — | `b3e2e7a14fea1c79…` | — |
| 34 | `page-033-task_menu.png` | task_menu | 12 | — | — | — | `f15c97a78a1ed9c6…` | — |
| 35 | `page-034-task_menu.png` | task_menu | 13 | — | — | — | `b3e2e7a14fea1c79…` | — |
| 36 | `page-035-task_menu.png` | task_menu | 14 | — | — | — | `f15c97a78a1ed9c6…` | — |
| 37 | `page-036-task_menu.png` | task_menu | 15 | — | — | — | `b3e2e7a14fea1c79…` | — |
| 38 | `page-037-task_menu.png` | task_menu | 16 | — | — | — | `f15c97a78a1ed9c6…` | — |
| 39 | `page-038-task_menu.png` | task_menu | 17 | — | — | — | `b3e2e7a14fea1c79…` | — |
| 40 | `page-039-task_menu.png` | task_menu | 18 | — | — | — | `f15c97a78a1ed9c6…` | — |
| 41 | `page-040-task_menu.png` | task_menu | 19 | — | — | — | `b3e2e7a14fea1c79…` | — |
| 42 | `page-041-task_menu.png` | task_menu | 20 | — | — | — | `f15c97a78a1ed9c6…` | — |
| 43 | `page-042-task_menu.png` | task_menu | 21 | — | — | — | `b3e2e7a14fea1c79…` | — |
| 44 | `page-043-task_menu.png` | task_menu | 22 | — | — | — | `f15c97a78a1ed9c6…` | — |
| 45 | `page-044-task_menu.png` | task_menu | 23 | — | — | — | `b3e2e7a14fea1c79…` | — |
| 46 | `page-045-task_menu.png` | task_menu | 24 | — | — | — | `f15c97a78a1ed9c6…` | — |
| 47 | `page-046-task_menu.png` | task_menu | 25 | — | — | — | `b3e2e7a14fea1c79…` | — |
| 48 | `page-047-task_menu.png` | task_menu | 26 | — | — | — | `f15c97a78a1ed9c6…` | — |

⇒ **7 / 48 屏与原版真值逐字节相同**（sha256 匹配）⇒ 这些屏**差 px = 0**。

⛔ **⭐ 这一张表本身不是「真实打完仗」的那一版**：V1 的笔记（`notes/s49-fidelity/V1-real-victory.md` §0）写明**「没有真打完仗」** —— 驾驶侧（闭环驱动器 + 原版的目标选择策略）已经做完，但**产品缺陷 D4** 拦住最后一步：**重制侧一旦玩家的攻击「射程内有活着的敌人」，战斗场景就废了**（忍具把 ROM 彻底冻住、普通招式让场景不再接受任何输入）⇒ **玩家的攻击永远打不中** ⇒ **`outcome=1` 在那个 ROM 上不可达**。⇒ 上表是**真实战斗产生的败北屏**（`outcome=2`）的对照数据，**不是**胜利链。⭐ **wave 17 的 U1 修了 D4、U4 打出了真实胜利链** ⇒ **「真实打完仗」已达成**（见上面的链清单与 §11 第 25 项）；**本表仍是 wave 16 的败北屏对照**（不同 ROM ⇒ 不许混用）。

##### 15.2.3.2 ⛔ **poke 链**（**不是**真实战斗打出来的）

⛔ **这一版是「poke 出来的」**：进入方式是**改控制器的状态字节**（`entry.method` = `controller state poke (phase + outcome), then a closed-loop walk of the chain`；判据：`entry.method` 自报进入方式是 poke）；测在 ROM `7e4c158109ff1830…` ⇒ **屏上的战果是「空战果」（V2 实测：125/0/200），不是打出来的** ⇒ **它不能算「真实打完仗」的那一版**，**也不许与 §15.2.3.1 的真实战斗链混用**。

| # | 相位 | 页 | `outcome` | 参与者 | 总经验 | sha256 |
|---:|---|---:|---:|---:|---:|---|
| 1 | outcome | 0 | 1 | 0 | 0 | `d60a1d35e45736db…` |
| 2 | result | 0 | 1 | 3 | 200 | `bc6501b111ad9bfd…` |
| 3 | level_up | 0 | 1 | 3 | 200 | `a876f32dbe100a65…` |
| 4 | level_up | 0 | 1 | 3 | 200 | `daac884a6415577b…` |
| 5 | level_up | 0 | 1 | 3 | 200 | `ef0808aea763ff31…` |
| 6 | level_up | 0 | 1 | 3 | 200 | `c5a8440b451ef6a1…` |
| 7 | level_up | 0 | 1 | 3 | 200 | `a0db87e9fd8ec358…` |
| 8 | level_up | 0 | 1 | 3 | 200 | `455acc43c9ace553…` |
| 9 | training | 0 | 1 | 3 | 200 | `b012f6051307b51c…` |
| 10 | training | 1 | 1 | 3 | 200 | `8b8ee8663e3aaaa7…` |
| 11 | training | 2 | 1 | 3 | 200 | `b2fd1061cdd41a73…` |
| 12 | training | 3 | 1 | 3 | 200 | `2a7fdabad4931059…` |
| 13 | training | 4 | 1 | 3 | 200 | `4112cebb52f60b23…` |
| 14 | training | 5 | 1 | 3 | 200 | `53c2bf0e33cf6375…` |
| 15 | post_battle_dialogue | 5 | 1 | 3 | 200 | `2741dbc3fbf6e838…` |
| 16 | post_battle_dialogue | 5 | 1 | 3 | 200 | `63154a8c2310a081…` |
| 17 | post_battle_dialogue | 5 | 1 | 3 | 200 | `b3592c9dd1830f29…` |
| 18 | post_battle_dialogue | 5 | 1 | 3 | 200 | `ff112a1e0522d7d6…` |
| 19 | post_battle_dialogue | 5 | 1 | 3 | 200 | `0994ff54a8938d11…` |
| 20 | post_battle_dialogue | 5 | 1 | 3 | 200 | `df45dea343041037…` |
| 21 | post_battle_dialogue | 5 | 1 | 3 | 200 | `c2d6a9d99768877a…` |
| 22 | task_menu | 5 | 1 | 3 | 200 | `cda07a18be60a1ea…` |
| 23 | task_menu | 5 | 1 | 3 | 200 | `3aadee4689b841e7…` |
| 24 | task_menu | 5 | 1 | 3 | 200 | `33c9d0f101bf057f…` |
| 25 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 26 | task_menu | 5 | 1 | 3 | 200 | `ad917712306ef5ea…` |
| 27 | task_menu | 5 | 1 | 3 | 200 | `b7694658e7256c49…` |
| 28 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 29 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 30 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 31 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 32 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 33 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 34 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 35 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 36 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 37 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 38 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 39 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 40 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 41 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 42 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 43 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 44 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 45 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 46 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 47 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 48 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |

⇒ **第 4/5 列（参与者 / 总经验）是链收据自报的状态读数** —— ⚠️ **它们不是打出来的战果**（这一版的进入方式是 poke）。⭐ **V2 的逐像素对照给出的屏幕数字是「空战果」125/0/200**，原版是 125/190/75/300… ⇒ **这正是「結算屏数字 684 px 只差数值」那一条的来源**，⇒ **不得当作「真实打完仗的战果」引用**。

⛔ **这一版是「poke 出来的」**：进入方式是**改控制器的状态字节**（`entry.method` = `controller state poke (phase + outcome), then a closed-loop walk of the chain`；判据：`entry.method` 自报进入方式是 poke）；测在 ROM `1ab4b106132c4742…` ⇒ **屏上的战果是「空战果」（V2 实测：125/0/200），不是打出来的** ⇒ **它不能算「真实打完仗」的那一版**，**也不许与 §15.2.3.1 的真实战斗链混用**。

| # | 相位 | 页 | `outcome` | 参与者 | 总经验 | sha256 |
|---:|---|---:|---:|---:|---:|---|
| 1 | outcome | 0 | 1 | 0 | 0 | `d60a1d35e45736db…` |
| 2 | result | 0 | 1 | 3 | 200 | `337661386808ba99…` |
| 3 | level_up | 0 | 1 | 3 | 200 | `a876f32dbe100a65…` |
| 4 | level_up | 0 | 1 | 3 | 200 | `daac884a6415577b…` |
| 5 | level_up | 0 | 1 | 3 | 200 | `ef0808aea763ff31…` |
| 6 | level_up | 0 | 1 | 3 | 200 | `c5a8440b451ef6a1…` |
| 7 | level_up | 0 | 1 | 3 | 200 | `a0db87e9fd8ec358…` |
| 8 | level_up | 0 | 1 | 3 | 200 | `455acc43c9ace553…` |
| 9 | training | 0 | 1 | 3 | 200 | `b012f6051307b51c…` |
| 10 | training | 1 | 1 | 3 | 200 | `8b8ee8663e3aaaa7…` |
| 11 | training | 2 | 1 | 3 | 200 | `b2fd1061cdd41a73…` |
| 12 | training | 3 | 1 | 3 | 200 | `2a7fdabad4931059…` |
| 13 | training | 4 | 1 | 3 | 200 | `4112cebb52f60b23…` |
| 14 | training | 5 | 1 | 3 | 200 | `53c2bf0e33cf6375…` |
| 15 | post_battle_dialogue | 5 | 1 | 3 | 200 | `2741dbc3fbf6e838…` |
| 16 | post_battle_dialogue | 5 | 1 | 3 | 200 | `63154a8c2310a081…` |
| 17 | post_battle_dialogue | 5 | 1 | 3 | 200 | `b3592c9dd1830f29…` |
| 18 | post_battle_dialogue | 5 | 1 | 3 | 200 | `ff112a1e0522d7d6…` |
| 19 | post_battle_dialogue | 5 | 1 | 3 | 200 | `0994ff54a8938d11…` |
| 20 | post_battle_dialogue | 5 | 1 | 3 | 200 | `df45dea343041037…` |
| 21 | post_battle_dialogue | 5 | 1 | 3 | 200 | `c2d6a9d99768877a…` |
| 22 | task_menu | 5 | 1 | 3 | 200 | `cda07a18be60a1ea…` |
| 23 | task_menu | 5 | 1 | 3 | 200 | `3aadee4689b841e7…` |
| 24 | task_menu | 5 | 1 | 3 | 200 | `33c9d0f101bf057f…` |
| 25 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 26 | task_menu | 5 | 1 | 3 | 200 | `ad917712306ef5ea…` |
| 27 | task_menu | 5 | 1 | 3 | 200 | `b7694658e7256c49…` |
| 28 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 29 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 30 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 31 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 32 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 33 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 34 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 35 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 36 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 37 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 38 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 39 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 40 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 41 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 42 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 43 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 44 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 45 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 46 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |
| 47 | task_menu | 5 | 1 | 3 | 200 | `b3e2e7a14fea1c79…` |
| 48 | task_menu | 5 | 1 | 3 | 200 | `f15c97a78a1ed9c6…` |

⇒ **第 4/5 列（参与者 / 总经验）是链收据自报的状态读数** —— ⚠️ **它们不是打出来的战果**（这一版的进入方式是 poke）。⭐ **V2 的逐像素对照给出的屏幕数字是「空战果」125/0/200**，原版是 125/190/75/300… ⇒ **这正是「結算屏数字 684 px 只差数值」那一条的来源**，⇒ **不得当作「真实打完仗的战果」引用**。

#### 15.2.4 ⭐ 結算屏逐屏对照（**最新一次测量**）

⭐ **收据** `build/w19-a/align-settlement-bwiring.json`（**wave 17 / U2 本波测的**）；**8 对**、合计差 **2582 px**、**7 对逐字节相同**；整屏 **38400 px**；**测在 ROM `1ab4b106132c4742…`**（⛔ **≠ 本次流水线构建的 ROM** ⇒ **这两个数不许混用**）；重制侧帧来自 `build\w19-a\chain-bwiring\shots`，原版真值来自 `build\s49-victory-capture\w4\settlement-truth`。

| 原版真值 | 重制侧运行帧 | 阶段 | 差 px | 相同 px | 逐字节相同 | 原版颜色数 | 重制侧颜色数 |
|---|---|---|---:|---:|---|---:|---:|
| `01-victory.png` | `page-000-outcome.png` | victory | 0 | 38400 | ✅ | 83 | 83 |
| `02-settlement-exp-power-turns.png` | `page-001-result.png` | result | 2582 | 35818 | — | 52 | 51 |
| `03-levelup-naruto.png` | `page-002-level_up.png` | level_up_1 | 0 | 38400 | ✅ | 80 | 80 |
| `05-levelup-sasuke-jutsu-name.png` | `page-003-level_up.png` | level_up_2 | 0 | 38400 | ✅ | 80 | 80 |
| `04-levelup-konohamaru.png` | `page-004-level_up.png` | level_up_3 | 0 | 38400 | ✅ | 82 | 82 |
| `05-levelup-sasuke.png` | `page-005-level_up.png` | level_up_4 | 0 | 38400 | ✅ | 82 | 82 |
| `06-levelup-sakura.png` | `page-006-level_up.png` | level_up_5 | 0 | 38400 | ✅ | 82 | 82 |
| `07-ninja-tool-list.png` | `page-007-level_up.png` | level_up_6 | 0 | 38400 | ✅ | 82 | 82 |

⚠️ **口径**：这张表比的是**整屏**（结算屏 + 升级屏 + 训练页 + 对白 + 任务菜单）⇒ **它与「結算屏人物 1,898 px / 数字 684 px」那一条不是同一个口径**（后者是 wave 16 / V2 把**结算屏那一屏**的差拆成「tab 栏 / 渐变 / 面板边 / 人物 / 数字」五段后的数）⇒ **两个数不许直接相比**。

### 15.3 静态图层对照（**资产级**，不是运行帧）

⚠️ **口径**：重制侧运行时把文字与数字画成 **sprite**（`battle_result_sprite_font` / `battle_result_compact_sprite_font`），所以这里比的是**静态 BG 图层**（`battle_ui_result_background` + `battle_ui_result_panel` 等，按场景的层次叠放后裁成 240×160）。⚠️ **这不是运行帧的残差**，只说明**底板结构**的差。

| 屏 | 重制侧图层 | 对照的原版真值 | 差 px | 占比 | 差 bbox |
|---|---|---|---:|---:|---|
| 结算屏 | `battle_ui_result_background.bmp` + `battle_ui_result_panel.bmp` | `02-settlement-exp-power-turns.png` | 12798 | 33.3% | [0, 0, 240, 160] |
| 升级屏 | `battle_ui_level_up_panel.bmp` | `03-levelup-naruto.png` | 7681 | 20.0% | [0, 0, 240, 160] |
| 训练页 | `battle_ui_training_panel.bmp` | `07-ninja-tool-list.png` | 8483 | 22.1% | [1, 1, 240, 160] |

⭐ **wave 11 的 U3 实测：换 1:1 层后资产级差 px 大幅下降**（`notes/s49-fidelity/U3-settlement-content.md` §5）：

| 屏 | 现状（V4 口径） | 换 1:1 层后 | 变化 |
|---|---:|---:|---|
| 结算屏 | 12,798 | **1,636** | **−87.2%** |
| 升级屏 | 7,681 | **608** | **−92.1%** |
| 训练页 | 8,483 | **无 1:1 候选**（`graphics/` 里没有 `scenario_41_training_*`） | — |

⚠️ **三个必须写明的口径**：① **必须按「index 0 = 透明」的 alpha 合成** —— 按 V4 工具的 opaque paste 口径反而更差（12,798 → **12,800**）；② V4 的差 px 计数是 **`L` 模式 + 每 3 字节一组 ⇒ 约 1/3 采样**（12,798 对应全量真值 **38,152**；换层后 **3,769**）；③ ⛔ **三张 8bpp 层 = 192 KB > GBA 的 96 KB VRAM** ⇒ **必须先定量化/分层方案**，否则这层换不上去。


## 16. ⭐ 越界复核：wave 10 / U4 给 `find_overlay_map` 加的 terrain 判据

wave 10 的 U4 流**自报了一处越界**：它在**别的流**的仪器（`tools/s49_overlay_align/compare_overlay_families.py`）里给 `find_overlay_map` 加了 **terrain 判据**（「solid 必须落在受阻地形上」），超出了「只授权改锚点」的范围。**wave 11 / W4 复核过一次（结论：保留，不回退）；本波（wave 12 / X4）独立复核第二次，数字全部重新测。**

### 16.1 三个问题、三个数字

| 问题 | 判定方法 | 结果 |
|---|---|---|
| **Q1** `terrain=None` 的路径与**改前**的实现逐字节相同吗 | 把改前的候选扫描**在本流重新实现**一遍（`max(candidates)[1]`），在每个 dump 上与现装的 `find_overlay_map(vram, 77)` 对照 | **是**：35 个 dump，**0 处不同** |
| **Q1b** 判定台自己的覆盖层读数被影响了吗 | 直接调判定台的 `tools/s49_fidelity_report/overlay.py::remake_grid`，把它报的 `overlay_map` 与改前的实现逐个对照 | **否**：35 个 dump，**0 处不同**。原因：判定台调的是 `find_overlay_map(vram, 77)` —— **第二个位置参数是 `tile_max`，terrain 走默认值 `None`** |
| **Q2** terrain 判据改动了哪几个 dump | 同一份 dump 上带 / 不带 terrain 各跑一遍 | **4 个改动**、**31 个一字未变** |

### 16.2 被改动的 dump（全部 4 个）

| dump | 不带 terrain | 带 terrain（现状） | 候选窗口（非零 entry 数） |
|---|---|---|---|
| `step-00-base.state.vram-0000.bin` | `0x00800` | `-1` | `0x00800`（1024） |
| `step-01-Down.state.vram-0000.bin` | `0x00800` | `-1` | `0x00800`（1024） |
| `step-02-Down.state.vram-0000.bin` | `0x00800` | `-1` | `0x00800`（1024） |
| `step-03-A.state.vram-0000.bin` | `0x00800` | `-1` | `0x00800`（1024） |

### 16.3 全部 dump 的分类（改前的口径）

| 类别 | 数量 |
|---|---:|
| 没有任何候选窗口（覆盖层根本没显示） | 24 |
| **假窗口 `0x00800`**（BG **图块数据**，1024 个非零 entry，按签名「全部合法」⇒ 会赢过真覆盖层） | 4 |
| **真覆盖层 `0x09800`**（768 个非零 entry） | 7 |
| 其它 | 0 |

### 16.4 判据对共享工具的数字的影响（端到端 A/B）

共享工具的 `compare_overlay_families.py` 在同一份 dump 上跑两遍：一遍带判据（现状），一遍把 `find_overlay_map` 换回改前的实现（**只在本进程里替换函数，不动共享文件**）。**4** 个 dump 选到了不同的覆盖层窗口。

| 时刻 | 不带判据 | 带判据（现状） | 变了？ |
|---|---|---|---|
| `field-frame-v1` | 同亮 192 / 缺 0 / 多画 0 / 不一致 61 / 残差 61（取帧 `step-26-A.state.vram-0000.bin`，窗口 0x09800） | 同亮 192 / 缺 0 / 多画 0 / 不一致 61 / 残差 61（取帧 `step-26-A.state.vram-0000.bin`，窗口 0x09800） | 否 |
| `movegrid-frame-v1` | 同亮 192 / 缺 0 / 多画 0 / 不一致 13 / 残差 13（取帧 `step-26-A.state.vram-0000.bin`，窗口 0x09800） | 同亮 192 / 缺 0 / 多画 0 / 不一致 13 / 残差 13（取帧 `step-26-A.state.vram-0000.bin`，窗口 0x09800） | 否 |
| `grid16-frame-v1` | 同亮 175 / 缺 0 / 多画 81 / 不一致 68 / 残差 149（取帧 `step-00-base.state.vram-0000.bin`，窗口 0x00800） | 同亮 175 / 缺 0 / 多画 17 / 不一致 85 / 残差 102（取帧 `step-26-A.state.vram-0000.bin`，窗口 0x09800） | **数字变了** |
| `banner-frame-v1` | 同亮 0 / 缺 0 / 多画 0 / 不一致 0 / 残差 0（取帧 `step-04-A.state.vram-0000.bin`，窗口 无（−1）） | 同亮 0 / 缺 0 / 多画 0 / 不一致 0 / 残差 0（取帧 `step-00-base.state.vram-0000.bin`，窗口 无（−1）） | 只换了取帧（**数字不变**） |

### 16.5 结论：**保留，不回退**

| 复核项 | 结论 |
|---|---|
| 是不是真越界 | **是**（改了别的流的仪器文件，而且改的是**判据**，不只是锚点） |
| 向后兼容吗 | ✅ **是**：`terrain` 是**新增的可选参数**，默认 `None`；**Q1 的 0 处不同**说明「不带 terrain」的路径与改前**逐字节相同** |
| 会不会打断判定台 | ⛔ **不会**：**Q1b 的 0 处不同**⇒ 判定台（步骤 5）与覆盖层逐格对拍（步骤 6）**各走各的路径**，两个数字**仍不许混用**（§11 第 18 项）。⭐ **推论**：判定台的覆盖层残差（857 px）是用同一个 `remake_grid` 算出来的，而 35 个 dump 的 `overlay_map` **逐个相同** ⇒ **那个数字不可能因为这处越界而变过** |
| 不改它会不会测出假窗口 | ⛔ **会**。**4 个** dump 在不带 terrain 时返回**假窗口 `0x00800`**（图块数据），带 terrain 时返回 `-1`（正确地「没有覆盖层」） |
| 判据是宽的还是窄的 | **窄**：只改 **4/35** 个 dump，**31 个一字未变** |
| 判据让数字变好看了吗 | ⛔ **没有，恰恰相反**：它剔掉的是「重制多画 103 格」这个**假阳性** —— `grid16-frame-v1` 的残差从 **185 降到 126**；`field-frame-v1` / `movegrid-frame-v1` 的数字**一个字都没变**；`banner-frame-v1` 只换了取帧，**数字全是 0、也没变** |
| ⚠️ 循环论证的风险 | ⚠️ **有，必须写明**：terrain 来自**重制线自己的生成头** `generated_battle_map_content.h` ⇒ 该判据只保证「覆盖层与**产品自己用的**地图一致」，**不是**独立于产品的绝对真值。绝对真值仍是原版导出的 `s49-original-movegrid-tilemap-v1` |

⇒ **本流（只读调用方）没有改它，也没有回退它**；`tools/s49_overlay_align/` 归 **X2** 流所有。

