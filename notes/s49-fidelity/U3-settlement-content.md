# 流 U3 —— 结算链缺屏 + 结算屏美术

> 工具：`tools/s49_u3_settlement/u3_*.py`（本流新建）
> 产物：`build/s49-u3-settlement/`
> 2026-10-24 · stream U3（wave 10）。**所有数字都是本机实测。**
> 逆向线 `D:\Shell\Github\gba-naruto-reverse` **全程只读**；
> 重制线**只改了 U3 的独占头文件 + 一个新单测**；**未提交 git**。

---

## 0. 一句话结论

**原版結算链是 7 段、重制侧是 5 段（差 2 段：戰後對白 / 任務菜單）**；
本流把这两段的**内容与状态迁移**落进了 U3 独占头文件（新增 `battle_settlement_stage`
七段枚举 + `battle_settlement_chain` 状态机 + 7 页戰後對白文本 + 逐人升級页枚举），
并用新单测锁住；**结算屏美术（S4）实测可把资产级差 px 从 12,798 降到 1,636**（−87.2%），
但**换层必须按「index 0 = 透明」的 alpha 合成**（按 V4 工具的 opaque paste 口径反而更差）——
**这是本次交付里最容易被误做的一处，已在 §5 写清**。

⚠️ **本流实测推翻了任务书里的两个前提**（§2 / §3）：

1. **原版的升級屏是 3 个人（鸣人/佐助/小樱）× 2 页 = 6 个子页，不是「四人各一张」**；
2. **W4 真值目录里那 4 个升級屏文件名是按帧号猜的，与像素内容对不上** ——
   `04-levelup-konohamaru.png` 里画的是**佐助**，护送木叶丸**根本没有升級屏**。

---

## 1. 改动文件清单

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_result_content.h` | **改** | 新增 `battle_settlement_stage`（7 段枚举）、`battle_settlement_stages`（顺序表）、`battle_settlement_missing_stages`（缺的那 2 段）、`battle_settlement_stage_next()`；逐人升級的**人/页/行序/实测成长值/抬头**；S49 的 **7 页戰後對白**文本 |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_results.h` | **改** | 新增 `battle_result_level_up_page`（升級屏的一个子页）、`battle_result_level_up_pages()`（**按原版顺序枚举 6 个子页**）、`battle_result_level_up_page_total()` |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_runtime_result.h` | **改** | 新增 `battle_settlement_progress`、`battle_settlement_stage_page_count()`、`battle_settlement_chain`（**结算链状态机**：先推进段内页、段内走完才进下一段） |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_scene_presentation_event.h` | **改** | 新增 `battle_settlement_presentation`（段 + 段内页 + 当前人）与事件里的 `has_settlement` / `settlement` 字段 |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\tests\test_battle_settlement_chain.cpp` | **新增** | 新单测：7 段链 / 缺 2 段 / 状态机推进 / 7 页对白 / 6 个升級子页顺序与成长值 / 事件载荷 |
| `D:\Github\gba-naruto\tools\s49_u3_settlement\u3_*.py`（24 个） | **新增** | 本流仪器（见 §8） |
| `D:\Github\gba-naruto\build\s49-u3-settlement\*` | 临时产物 | 测量收据 |

**没有**改 `battle_runtime_scene.cpp` / `battle_black_field*.h` / `graphics/`（U1 独占）、
`battle_unit_content.h` / `battle_condition*.h` / `battle_ai*.h`（U2 独占）、
`battle_scene_controller.h`（父代理串行接线）、逆向线任何文件。

---

## 2. ⭐ 纠正一：升級屏是 **3 个人 × 2 页**，不是「四人各一张」

### 2.1 实测方法

`tools/s49_u3_settlement/u3_stable_screens.py` 把 W4 录制的 29,700 帧按像素哈希聚成
**27 个稳定屏**（min-run 200 帧），再对每个升級屏的**肖像区域**（16,24)-(112,120)）
单独取哈希 ⇒ 同一个人的两页肖像哈希相同。

### 2.2 实测结果

| 稳定屏 | 帧区间 | 肖像指纹 | 抬头（实测） | 含义 |
|---|---|---|---|---|
| #1 | 1705..2542 | `53bf94c0…` | **漩涡鸣人的LV升到6级了** | 鸣人 第 1 页（属性成长表） |
| #2 | 2591..3512 | `53bf94c0…`（同上） | **螺旋丸的现在可以修炼了** | 鸣人 第 2 页（忍術解锁） |
| #3 | 3651..4482 | `64e93e74…` | **宁智波佐助的LV升到5级了** | 佐助 第 1 页 |
| #4 | 4531..5452 | `64e93e74…`（同上） | **动作训练班可以修炼了** | 佐助 第 2 页 |
| #5 | 5583..6422 | `0034ee53…` | **春野樱的LV升到6级了** | 小樱 第 1 页 |
| #6 | 6471..7392 | `0034ee53…`（同上） | **忍者知识现在可以修炼了** | 小樱 第 2 页 |

⇒ **升級屏 = 3 个人 × 2 页 = 6 个子页**（`u3_level_up_portraits.py` 打印
`distinct portraits: 3`）。

### 2.3 ⭐ W4 真值的文件名与像素对不上

`build/s49-victory-capture/w4/settlement-truth/` 里有 **11 张 PNG**，
但收据 `settlement-truth.json` 只列 **9 张**（多的 2 张是 `04-levelup-sasuke.png`
和 `05-levelup-sasuke-jutsu-name.png`，收据里没有 ⇒ **它们是上一轮实验的残留**）。

把收据里的 9 张与稳定屏对齐（`u3_map` 见 §8 的 `u3_stable_screens.py`）：

| 真值文件 | 收据里的源帧 | **实测落在哪个稳定屏** | 文件名对吗 |
|---|---|---|---|
| `03-levelup-naruto.png` | frame-01801 | #1（鸣人第 1 页） | ✅ |
| `04-levelup-konohamaru.png` | frame-04201 | **#3（佐助第 1 页）** | ❌ **里面画的是佐助** |
| `05-levelup-sasuke.png` | frame-04801 | **#4（佐助第 2 页）** | ❌ **里面是「動作訓練班」页** |
| `06-levelup-sakura.png` | frame-06001 | #5（小樱第 1 页） | ✅ |
| `07-ninja-tool-list.png` | frame-07201 | **#6（小樱第 2 页）** | ❌ **里面不是忍具一览** |

⇒ **「四人逐人升級屏」这个前提不成立**：
护送木叶丸（character_id 30）**没有升級屏**，
原版的升級屏是**鸣人/佐助/小樱**这 3 个人（与重制侧 `battle_result.participants`
的 3 个槽位**正好对上**）。

⚠️ 连带影响：`04-levelup-konohamaru` / `07-ninja-tool-list` 这两张被 V4 拿去当
「升级屏 / 训练页」的真值，**这两张其实都不是那两屏** ⇒ V4 报告里
「升级屏 7,681 / 训练页 8,483」这两个数的**真值配对是错的**（见 §5.3）。

### 2.4 逐人升級的实测内容（已落进 `battle_result_content.h`）

属性成长（第 1 页，7 行，行序 = 原版行序 = `character_stat_values` 字段序）：

| 人 | 体力 | 查克拉 | 攻擊力 | 防禦力 | 敏捷度 | 移動力 | 忍具数 | 升到 |
|---|---|---|---|---|---|---|---|---|
| 鸣人 | **+14** | ±0 | +1 | +1 | +1 | ±0 | ±0 | 6 |
| 佐助 | **+15** | ±0 | +1 | +1 | +1 | ±0 | ±0 | 5 |
| 小樱 | **+15** | ±0 | +1 | +1 | +1 | ±0 | ±0 | 6 |

第 2 页的抬头分别是「螺旋丸的现在可以修炼了」/「动作训练班可以修炼了」/
「忍者知识现在可以修炼了」。

---

## 3. ⭐ 纠正二：W4 真值里**没有**逐人升級页的「4 人」

见 §2.3。W4 的文件名是**按帧号猜的**（抽帧间隔 2400 帧），
抽到的第 2/4/5 张其实分别是**佐助第 1 页 / 佐助第 2 页 / 小樱第 2 页**。

⇒ **原版升級屏的实际结构**：3 人 × 2 页 = 6 个子页，**按 A 逐页推进**。

---

## 4. S1 · 战后对白 + 任务菜单（内容 + 状态迁移）

### 4.1 结算链的段数对齐

`battle_result_content.h` 里的 `battle_settlement_stage` 就是这条链的 7 段：

| # | 段 | 重制侧现状 |
|---|---|---|
| 1 | `victory` | 有（`battle_scene_phase::outcome`） |
| 2 | `result` | 有（`result`） |
| 3 | `level_up` | 有（`level_up`），**但只有 1 屏**（S3 补逐人子页） |
| 4 | `training` | 有（`training`） |
| 5 | **`post_battle_dialogue`** | **缺（S1 补）** |
| 6 | **`task_menu`** | **缺（S1 补）** |
| 7 | `complete` | 有 |

`battle_settlement_missing_stages` 把缺的那 2 段显式列出来，
`battle_settlement_stage_is_missing()` 可以直接查。

### 4.2 战后对白的 7 页（逐字转写）

来自 `build/s49-victory-capture/w4/settlementA/frames` 的稳定屏 #21..#27
（`u3_dialogue_zoom.py` 放大 6–8 倍后逐字读）：

| 页 | 帧 | 说话人 | 台词 |
|---|---|---|---|
| 1 | 21107 | 鸣人 | 跟你説已經没事了吧！ |
| 2 | 22049 | 木叶丸 | 嗚哇！別过来呀！！ |
| 3 | 23081 | 小樱 | 没关系了啦，已经没有蜜蜂了！不要害怕了！！ |
| 4 | 23923 | 木叶丸 | 嗚哇！！！ |
| 5 | 25091 | 鸣人 | 木叶丸！！ |
| 6 | 25949 | 佐助 | 喂，他跑到森林的深处了！ |
| 7 | 26993 | 卡卡西 | 不好，看样子那家伙快不行了……你们快去把他追回来。 |

⚠️ **这 7 页不在逆向线的 dialogue bank 里**
（`u3_find_dialogue_bytes.py`：309 条对白，**命中 0 条**）
⇒ 只能从原版帧读，**已落进 `battle_result_content.h`**。

### 4.3 状态迁移（`battle_runtime_result.h`）

`battle_settlement_chain` 是**纯逻辑**的状态机（不碰 Butano、不碰渲染）：

* `advance()`：**先推进段内页**，段内走完才进下一段；
* 每段的子页数由 `battle_settlement_stage_page_count()` 给
  （升級屏 6 页、戰後對白 7 页、其余 1 页）；
* 忍具一覽那种页数不定的段用 `enter(stage, page_count)` 覆盖；
* `battle_settlement_chain_may_finish()` 只在 `complete` 段为真
  ⇒ **重制侧现在在 `training` 之后就 `complete` 交还战役，改完后要多走两段**。

⚠️ **「勝利」屏不会自己推进**（W4-H13：连录 18,000 帧不变）⇒ 每段都要按 A。

---

## 5. S4 · 结算屏美术：差 px 实测下降

### 5.1 ⭐ 两个口径的坑（本次交付最关键的一条）

1. **合成规则**：`scenario_41_result_*` 是 Butano `bpp_8` regular BG，**index 0 是透明色**。
   正确的合成是**最上面的非透明像素获胜**（GBA 的行为），
   **不是** wave 9 的 V4 工具用的 opaque paste。
2. **V4 的计数器每 3 个像素采 1 个**：它把 merged 图建成 `L` 模式（每像素 1 字节），
   然后按 3 字节一组走 ⇒ 报出来的数约为**真值的 1/3**。

⇒ 两个口径都报（`u3_s4_asset_swap.py`），以便和已记录的数对得上。

### 5.2 实测（`u3_s4_asset_swap.py`）

结算屏（真值 = `02-settlement-exp-power-turns.png`）：

| 图层栈 | 合成规则 | V4 口径 | **真值 px** | 差 bbox |
|---|---|---:|---:|---|
| 现状 `battle_ui_result_background` + `battle_ui_result_panel` | opaque paste | 12,798 | 38,152 | (0,0,240,160) |
| 现状同上 | alpha（index 0 透明） | 12,798 | 38,152 | (0,0,240,160) |
| **S4 候选 `scenario_41_result_bottom`+`middle`+`top`** | alpha | **1,636** | **3,769** | (84,9,231,150) |
| S4 候选 | opaque paste | 12,800 | 38,400 | (0,0,240,160) |

⭐ **对 `ref-scenario-41-result/screen.png`（原版自己的结算屏）：S4 候选 alpha 合成
= 0 差 px（逐像素全等）** ⇒ **这三个图层就是原版结算屏的 1:1 底板**。

升级屏（真值 = `03-levelup-naruto.png`）：

| 图层栈 | 合成规则 | V4 口径 | **真值 px** |
|---|---|---:|---:|
| 现状 `battle_ui_level_up_panel` | 两者相同 | 7,681 | 21,247 |
| **S4 候选 `scenario_41_level_up_1_bottom`+`middle`+`top`** | alpha | **608** | **1,629** |
| S4 候选 | opaque paste | 11,249 | 33,532 |

对 `ref-scenario-41-level-up-1/screen.png`：alpha **595** 差 px，
bbox **(16,40,96,120)** ⇒ 差的就是**头像那一块**（原版的头像是 OAM sprite，
不在 BG 层里）⇒ **除头像外逐像素全等**。

### 5.3 差 px 下降的实测结论

| 屏 | 现状（V4 口径） | S4 后（V4 口径） | 变化 |
|---|---:|---:|---|
| 结算屏 | 12,798 | **1,636** | **−87.2%** |
| 升级屏 | 7,681 | **608** | **−92.1%** |

⚠️ **口径提醒**（§5.1）：V4 口径下**必须用 alpha 合成**；
若沿用 V4 工具的 opaque paste，结算屏会从 12,798 变成 12,800（**更差**）。

⚠️ **训练页没有 1:1 候选**：仓里**没有** `scenario_41_training_*`。
且 V4 用作「训练页真值」的 `07-ninja-tool-list.png` **实际是小樱升級第 2 页**（§2.3）
⇒ **训练页的 8,483 这个数本身配对错了**，S4 只能覆盖结算屏与升级屏两屏。

### 5.4 VRAM 预算（接线前必须确认）

`scenario_41_*` 是 `bpp_8` 256×256 ⇒ **每层 64 KB VRAM**，
三层叠放 = **192 KB > GBA 的 96 KB（`VRAM_SIZE 0x18000`）**。
⇒ **三张 8bpp 层不可能同时驻留 VRAM**。
Butano 会在运行时按需换入/换出，但**结算屏必须同时显示多层** ⇒
**要么改成 4bpp 量化、要么只留 1 层 + 其它层改用 sprite**。
**这条必须由父代理/U1 在接线时定夺**，本流只提供数据与测量。

---

## 6. 跑了哪些验证

| # | 命令 | 关键数字 |
|---|---|---|
| **V1** | `python tools/s49_u3_settlement/u3_stable_screens.py --frames build/s49-victory-capture/w4/settlementA/frames` | 29,700 帧 → **1,229 个连续 run** → **27 个稳定屏**（min-run 200） |
| **V2** | `python tools/s49_u3_settlement/u3_level_up_portraits.py` | 稳定屏 #1..#6 → **3 个肖像指纹** ⇒ **3 人 × 2 页** |
| **V3** | `python tools/s49_u3_settlement/u3_dialogue_zoom.py` | 战后对白 7 页的放大图（逐字转写用） |
| **V4** | `python tools/s49_u3_settlement/u3_decisive_checks.py` | ① 1:1 层 alpha 合成 vs 原版自己的屏 = **0 差 px**；② 转写文本 Shift-JIS 编码后 **44 个码位**不在重制侧 862 码的 presentation 字体里 |
| **V4b** | `python tools/s49_u3_settlement/u3_font_gap.py` | `battle_result_font` 缺 **42 字**；presentation 字体缺 **44 码** |
| **V5** | `python tools/s49_u3_settlement/u3_s4_asset_swap.py` | 结算屏 **12,798 → 1,636**（V4 口径）/ 38,152 → 3,769（真值）；升级屏 **7,681 → 608** / 21,247 → 1,629 |
| **V6** | `python tools/s49_victory_capture/v4_settlement_assets.py` | 基线复核：12,798 / 7,681 / 8,483（与 V4 报告记录**逐数一致**） |
| **V7** | `g++ … test_battle_settlement_chain.cpp && /tmp/test_u3_chain` | **TEST PASS** |
| **V8** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh` | HEAD 基线：**pass=101 fail=20**，失败名 20 个 |
| **V9** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh` | 工作区：**pass=116 fail=20**，失败名 **与基线逐名相同** |
| **V10** | 头文件尺寸探针（当前树 vs `build/head-baseline`） | `battle_scene_snapshot<12>` 1672=1672、`battle_runtime_scene_telemetry` 868=868（**未变**）；`battle_scene_control_result` **212 ≤ 256**（门限内）；`battle_scene_presentation_event` 148→**156**（+8） |
| **V11** | `make -j4`（WSL，导出 `LIBBUTANOABS`） | **ROM 构建通过**：`butano-sequel.gba` 12,020,952 字节 |
| **V12** | `Get-CimInstance Win32_Process -Filter "Name='mgba-probe.exe'"` | **0 个孤儿进程** |
| **V13** | BOM/CRLF 扫描（5 个改动文件） | 全部 **bom=False, crlf_pairs=0** |

### 6.1 ⭐ 单测棘轮

**基线（HEAD）失败 20 项**：
`test_battle_all_scenario_runtime`、`test_battle_campaign_route`、
`test_battle_campaign_save`、`test_battle_campaign_scenario_42`…`_49`（8 项）、
`test_battle_dynamic_deployment_turn`、`test_battle_material_pickups`、
`test_battle_presentation_controller`、`test_battle_runtime_scene_gate`、
`test_battle_s49_input_flow`、`test_battle_s49_opening`、
`test_battle_scene_character_actions`、`test_battle_scene_controller`、
`test_battle_scene_multi_unit`、`test_battle_scene_results`。

**工作区失败 20 项，名字与基线逐名相同 ⇒ 零回归**（pass 101 → 116）。
⚠️ **pass 增量不是本流独占的**：基线快照有 121 个测试文件、工作区有 **136** 个
（多出的 15 个是各流陆续加的新单测，本流只占其中 **1** 个：
`test_battle_settlement_chain.cpp`）。

⚠️ `test_battle_runtime_scene_gate` 的**编译失败是预存债**：
基线与工作区**同一处** `static_assert`（`sizeof(battle_scene_snapshot<12>) <= 1120`
实测 1672），**不是本流引入**（V10 已逐项对比结构体尺寸）。

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| U3-1 | 原版結算链是 7 段、重制侧 5 段 | 读 W4 真值链序 + 对照 `battle_scene_phase` | 原版 7（含**戰後對白**/**任務菜單**）、重制侧 5 | **已确认** |
| U3-2 | 升級屏是「四人各一张」 | 肖像区域哈希 + 抬头逐字读 | **3 人 × 2 页 = 6 子页**；木叶丸**没有**升級屏 | **已证伪**（前提错误） |
| U3-3 | W4 真值文件名可信 | 把 9 张真值与 27 个稳定屏逐一对齐 | 5 张里 **3 张与内容对不上**（`04-konohamaru`=佐助、`05-sasuke`=佐助第2页、`07-ninja-tool-list`=小樱第2页） | **已证伪** |
| U3-4 | 战后对白有 7 页 | 稳定屏 #21..#27 逐字读 | **7 页**，说话人 鸣人/木叶丸/小樱/木叶丸/鸣人/佐助/卡卡西 | **已确认** |
| U3-5 | 战后对白的文本在逆向线的 dialogue bank 里 | 309 条对白按 gbk/cp932/big5 三种编码搜 7 句 | **命中 0 条** ⇒ 只能从帧读 | **已证伪** |
| U3-6 | `scenario_41_result_*` 是原版结算屏的 1:1 底板 | alpha 合成（index 0 透明）后与 `ref-scenario-41-result/screen.png` 逐像素比 | **0 差 px**（全等） | **已确认** |
| U3-7 | V4 工具的 opaque paste 口径适合 8bpp 图层 | 同一栈用两种合成规则各测一次 | opaque paste 下结算屏 **12,798 → 12,800（更差）**；alpha 下 **→ 1,636** | **已证伪**（V4 口径用错合成规则） |
| U3-8 | V4 的差 px 计数是真值 | 读 V4 计数器实现 | `L` 模式 + 每 3 字节一组 ⇒ **约 1/3 采样**（12,798 对应真值 38,152） | **已证伪**（口径需标注） |
| U3-9 | 训练页有 1:1 候选图层 | 扫 `graphics/` | **没有** `scenario_41_training_*` | **已证伪**（这条路走不通） |
| U3-10 | 三张 8bpp 层能同时驻留 VRAM | 算 VRAM：3 × 64 KB vs GBA `VRAM_SIZE 0x18000` = 96 KB | **192 KB > 96 KB** ⇒ 不可能 | **已证伪**（S4 接线的前置约束） |
| U3-11 | 转写的对白能被重制侧现有字体直接渲染 | 对**两个**候选字体各查一次（`u3_font_gap.py`） | `battle_result_font`（UTF-8，401 字形）缺 **42 个字**；presentation 字体（Shift-JIS，862 码）缺 **44 个码** | **已证伪**（两种字体都要扩，⇒ 交接） |
| U3-12 | 本流改头文件会撑爆快照/遥测的门限 | 当前树 vs `build/head-baseline` 逐结构体测尺寸 | 1672=1672、868=868 **未变**；`battle_scene_control_result` 212 ≤ 256 | **已确认** |
| U3-13 | 本流新单测与工作区全量测试不引入新失败 | 跑基线 + 工作区，比失败名集合 | 20 vs 20，**逐名相同** | **已确认** |
| U3-14 | 原版結算屏列 3 个人 | 读 `02-settlement-exp-power-turns.png` 抬头 | 经验值/鸣人/佐助/小樱 = **3 人** | **已确认** |

---

## 8. 接线点清单（交父代理 / U1）

> ⚠️ 下面每条都**没有**由本流实施（相关文件不属于 U3 独占）。

### 8.1 结算链补 2 段（S1）— `battle_scene_controller.h` + `battle_runtime_scene.cpp`

1. **`battle_scene_controller.h` 的 `battle_scene_phase` 枚举**：加
   `post_battle_dialogue`、`task_menu` 两个相位
   （**注意** `battle_scene_phase_origins` 是 24 行的生成表，`static_assert
   battle_scene_phase_count == 24` 会随之失配 ⇒ 要么同步
   `battle_original_states.h` 的生成源，要么把新相位标成 `remake_only`）。
2. **`_advance_level_up()` 之后**：`training` 结束不要直接 `complete`，
   先进 `post_battle_dialogue`。
3. **`post_battle_dialogue` 相位**：按 A 推进 7 页，页文本用
   `battle_settlement_s49_dialogue`（说话人 `character_id` + 台词）。
4. **`task_menu` 相位**：按 A 离开结算链，回到战役场景。
5. **`battle_runtime_scene.cpp`**：画战后对白屏（对话框 + 说话人标签 + 台词）与
   任務菜單屏。⚠️ **台词的两种字体都缺字**（U3-11）：
   * `battle_result_font`（结算屏自己的 UTF-8 精灵字体，401 字形）缺 **42 个字**：
     `56LV…了事们伙作你修关別升呀哇啦喂嗚在好家已怕来林样深炼现班知經级螺説训识跟追那`；
   * presentation 字体（原版自己的 Shift-JIS 对白字体，862 码）缺 **44 个码**
     （0x88C8=以、0x89C6=家、0x8A90=叶、0x8ADB=丸、0x9BDF=已、0xE353=經、0xE6EE=跟 …）。

   ⇒ 要么扩 `battle_result_font.bmp` + `battle_result_sprite_font.h`，
   要么扩 presentation 字体（生成源在
   `D:\Shell\Github\gba-naruto-butano\tools\export_battle_presentation_glyphs.py`）。
6. **`battle_runtime_scene.cpp` 的 `_add_result_background()` / 升级屏 UI**：
   按 §5 换成 `scenario_41_result_*` / `scenario_41_level_up_1_*`（**alpha 合成**），
   并先解决 §5.4 的 **VRAM 预算**。

### 8.2 逐人升級（S3）

7. **`battle_scene_controller.h` 的 `_advance_level_up()`**：改成按
   `battle_result_level_up_pages(result)` 枚举 **6 个子页**
   （原版顺序：鸣人 2 页 → 佐助 2 页 → 小樱 2 页），而不是现在
   「只有升级了的人才出现、且每人固定 2 页」的近似。
8. **`battle_runtime_scene.cpp` 的 `_add_level_up_ui()`**：
   用 `state.level_up_detail_page` 取 `battle_result_level_up_pages()` 的对应页；
   抬头用 `battle_settlement_s49_level_up_headers` /
   `battle_settlement_s49_level_up_technique_headers`（或扩 title 精灵图）。

### 8.3 接线后要复跑的验证

9. `python tools/s49_u3_settlement/u3_s4_asset_swap.py`（确认差 px 真的降）
10. `wsl … run-baseline-tests.sh` 与 `w1-run-all-tests.sh`（失败名集合不变）
11. ROM 冒烟：战后对白 7 页能翻页、任務菜單能退出结算链。

---

## 9. 确认

* **新文件全部 LF、无 BOM**（24 个 `tools/s49_u3_settlement/*.py` + 1 个新单测
  + 本报告）；改动的 4 个头文件也扫过：**bom=False, crlf_pairs=0**。
* **未提交 git**（本流文件在工作区里是未跟踪/未提交状态）。
* **未改** `battle_runtime_scene.cpp` / `battle_black_field*.h` / `graphics/`（U1 独占）、
  `battle_unit_content.h` / `battle_condition*.h` / `battle_ai*.h`（U2 独占）。
* **逆向线全程只读**（读了 `sequel/content/story/bank.json`、
  `sequel/content/text/dialogue-bank-full.json`、`sequel/content/fonts/bank.json`、
  `artifacts/rom-chapter-script-inventory-v1/*`；**一个字节都没写**）。
* **孤儿进程检查通过**：`mgba-probe.exe` 残留 **0** 个。
* **路线图同步留给父代理**（WAVE10-TASKS §5 规定由父代理串行接线与同步）。
* ⚠️ **本流没有在 ROM 上录到重制侧的结算链运行帧** ——
  V4-H6 已证重制侧 battle-14 打不赢（U2 的数值域），所以运行帧对照本流做不了；
  本流交付的是**内容 + 状态机 + 资产级测量**，运行帧对照留待 U2 数值落地后。
