# W19-A —— 「開始」标题卡：改成原版的语义（纯定时 · 无视输入 · 姿态 B）

> 2026-10-25 · A 流（wave 19）· 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 任务书 `notes/s49-fidelity/WAVE19-TASKS.md` §1 ·
> 上游 `notes/s49-fidelity/W18-W5-walk-divergence.md` ·
> `notes/s49-fidelity/W18-PARENT-residual-structure.md`
> 隔离副本：`D:\Github\gba-naruto\build\w19-a\butano-sequel`
> （= `D:\Shell\Github\gba-naruto\build\w19-a\butano-sequel`；**共享产品树
> `D:\Shell\Github\gba-naruto-butano\butano-sequel` 未被改动**）

---

## 0. 一句话结论

> ⭐⭐ **重制侧的「開始」标题卡现在是原版的语义**：纯定时、**完全无视输入**、
> 一次走完（姿态 A → 姿态 B → 自动擦除 → 战斗载入）。
> ⇒ **两条 walk 的步偏移从「第 10 步掉到 +3」变成恒为 +4**（4 对整帧 sha256 相同的帧
> 全部落在 **+4**），**姿态 B 第一次出现在 walk 里**（原版 `step-10` 的残差
> **2 761 → 278 px**），黑场入口对齐（`step-11` **30 418 → 1 212 px**），
> 常数偏移 +4 的残差和 **276 128 → 148 914 px**。
>
> ⇒ **顺带替 B 路落了两条 `.cpp` 接线**（B-1 定位 / B-2 對白页层）：
> **戰後對白 26 819 → 0 px、任務菜單 37 694 → 0 px、結算 2 582 → 684 px**
> （整条結算链 **66 411 px 归零**，实测）。
>
> ⇒ ⛔ **判定台的总残差没降**：那 73 k px 集中在原版 `step-19/21/22`（**战斗段**），
> 重制侧的**战斗首帧画面差 24 460 px**（两侧的「战斗首帧」**时刻是齐的**：都在卡片
> 升起 +1034 GBA 帧）⇒ 那是**战斗场景自己的画面**（相机滚动 / 布景），**不是卡片**。

---

## 1. 改动文件清单（含 sha256）

### 1.1 我独占的两个文件（产品改动）

| 文件 | sha256 | 改了什么 |
|---|---|---|
| `game/include/konoha/battle_opening_title.h` | `e2390e3e9b1c8b6e29d4a98dbd8c17d6f56d47ce69f81d9ab19ccde52e639e23` | ① `phase()` **不再取模**：相位走到最后一个就**保持**；② `phase_frames` 23 → **50**（姿态 A 的时长＝原版的 100 GBA 帧）；③ `on_screen_frames` 48 → **102**（卡片总时长＝原版的 204 GBA 帧）；④ 新增 `finished()`（表演演完的判据） |
| `game/src/battle_runtime_scene.cpp` | `f5cfb5079318a40af3247257c55eb51ba50ed7961f1e191770c0c235f5af7334` | ① **卡片播放期间吞掉按键**（原版无视输入）：A/B 键不再进部署流程；② **卡片的表演结束＝部署的确认**（`deployment.confirm()` 由表演触发，**只被消费一次**）；③ 卡片在表演结束时**先撤**，再走黑场；④ `battle_black_field_event1_lead_frames` 38 → **30**（黑场入口跟着卡片走，见 §4）；⑤ **替 B 路落的两条接线**（见 §7.0） |

### 1.2 ⚠️ 伴随改动（**必须与我这两个文件一起拷回共享树**）

| 文件 | sha256 | 为什么必须一起改 |
|---|---|---|
| `game/tests/test_battle_opening_title.cpp` | `e6b39b55bcd8485da7fea3b0dfd2b78344c1a35b3b2b3bb5793ac6d377891e6e` | 该单测**逐字断言了旧语义**：`assert(on_screen_frames == 48)` 与「**The phases repeat.**」（相位取模回绕）。任务书 §1.3.1 明确要求 `phase()` 不再取模 ⇒ 这两条断言**必然**要跟着改，否则单测会多出 1 项红（违反 A-6 的棘轮）。改法：断言 `on_screen_frames == 102`、`phase()` 走到最后一位**保持**、新增 `finished()` 的断言。**该文件不属于任何一路的独占清单**，我按「语义变更的必要伴随件」处理，在此显式登记，供父代理一并拷回。 |

### 1.3 产物

| 产物 | sha256 / 路径 |
|---|---|
| ROM（**最终**，卡片 + lead=30 + B 路接线 + B 路资产） | `7e4c158109ff1830d3d7ba4a934eb45fd9475a8a56d66802fb2480a2c1708119` · `build/w19-a/butano-sequel/butano-sequel.gba` |
| ROM（卡片 + lead=30，未接 B 路） | `00e2e4a169638b464f95408ee107868878454dc3e0dd633c150140d3ac74ff20` |
| ROM（卡片，lead=38 的中间版） | `a0e88e812dde62892da221f9b4d910ff3b49e7e3f054c0cafce7351176f2abba`（**不要用它下结论**） |
| 探针 exe（副本，**未覆盖**共享的那个） | `build/w19-a/probe/mgba-probe.exe` · sha `c4a34cd47bac3a56ddaa3b1c3cfdb4a809e926477fd3209e6aed1450ccf713e4` |
| 重制侧 walk 捕获（最终） | `build/w19-a/capture-remake-final/`（35/35 帧 + `receipt.json`） |
| 结算链捕获 | `build/w19-a/chain-final/`（48 屏 / 5 620 帧 / 1.9 s，`outcome=1`，末相位 `task_menu`） |
| 卡片 watch（不按 A / 按 A） | `build/w19-a/watch-none/` · `build/w19-a/watch-pressa/` |
| 仪器（本流新增） | `build/w19-a/tools/pose_timeline.py` · `anchors.py` · `capture_remake.py` · `stage_b_assets.sh` · `stage_b_portraits.sh` · `build_w19a.sh` |
| 暂存的 B 路资产 | `build/w19-a/butano-sequel/graphics-local/`（共享 graphics ＋ B 路 9 张结算资产 ＋ 3 张立绘；**共享树只读**） |

---

## 2. ⭐ 判定问题的答案

> **「修好后，判定台两条 walk 的步偏移是否恒为 +4（不再在原版第 9→10 步之间从 +4 掉到 +3）？」**

### **是 —— 但只在卡片所在的段落上。**

`align_capture_steps.py` 的**整帧 sha256 精确匹配**（唯一可靠的偏移证据）：

| | 原版 | 重制侧 | 偏移 |
|---|---|---|---|
| **改前** | `step-14-A` / `step-15-A` / `step-17-A` / `step-18-A` | `step-17-A` / `step-18-A` / `step-20-A` / `step-21-A` | **+3**（偏移集合 = {+3}） |
| **改后** | `step-14-A` / `step-15-A` / `step-17-A` / `step-18-A` | `step-18-A` / `step-19-A` / `step-21-A` / `step-22-A` | **+4**（偏移集合 = {+4}） |

⇒ ⭐ **偏移集合从 {+3} 变成 {+4}**：卡片那一段的偏移不再掉 1。
⇒ ⭐ 顺带修好了黑场段的偏移（原来 14–18 步是 +3，现在是 +4）。

---

## 3. ⭐ 偏移剖面改前 / 改后对照（每帧最优偏移与残差，战场区 240×128）

| 原版步 | 改前 最优偏移 (px) | 改后 最优偏移 (px) | Δ px | 说明 |
|---|---|---|---:|---|
| `step-00-base` | +4 (2 565) | +4 (2 565) | 0 | |
| `step-01` | +4 (1 294) | +4 (1 294) | 0 | |
| `step-02` | +4 (1 680) | +4 (1 680) | 0 | |
| `step-03` | +4 (2 514) | +4 (2 514) | 0 | |
| `step-04` | +4 (1 940) | +4 (1 940) | 0 | |
| `step-05` | +4 (2 057) | +4 (2 057) | 0 | |
| `step-06` | +4 (1 217) | +4 (1 217) | 0 | |
| `step-07` | +4 (1 921) | +4 (1 921) | 0 | |
| `step-08` | +4 (1 026) | +4 (1 026) | 0 | |
| `step-09`（姿态 A） | +4 (759) | +4 (759) | 0 | 姿态 A 仍对得上 |
| **`step-10`（姿态 B）** | **+3 (2 761)** | **+4 (278)** | **−2 483** | ⭐ **姿态 B 第一次出现** |
| **`step-11`（黑场入口）** | +3 (3 368) | **+4 (1 212)** | **−2 156** | ⭐ 黑场入口跟上了（lead 30） |
| `step-12` | +6 (10 371) | +5 (10 433) | +62 | 过渡的淡入级差（C 的文件，见 §7.2） |
| `step-13` | +4 (28) | +5 (28) | 0 | 偏移 +4→+5，同上一行 |
| `step-14` | +3 (**0**) | +4 (**0**) | 0 | ⭐ 偏移 +3→+4 |
| `step-15` | +3 (**0**) | +4 (**0**) | 0 | ⭐ |
| `step-16` | +3 (43) | +4 (43) | 0 | ⭐ |
| `step-17` | +3 (**0**) | +4 (**0**) | 0 | ⭐ |
| `step-18` | +3 (**0**) | +4 (**0**) | 0 | ⭐ |
| `step-19` | 全列 ≥24 460 | +4 (24 460) | 0 | ⛔ 战斗首帧的**画面**差（时刻是齐的） |
| `step-20` | +2 (4 158) | +3 (4 158) | 0 | ⛔ 战斗段的拍子消耗不同 |
| `step-21` | 全列 ≥27 798 | +3 (27 800) | 0 | ⛔ 同上 |
| `step-22` | 全列 ≥27 639 | +2 (27 643) | 0 | ⛔ 同上 |
| `step-23` | +3 (2 306) | +1 (1 323) | −983 | ⛔ 同上 |
| `step-24` | +2 (5 608) | +1 (1 372) | −4 236 | ⛔ 同上 |

**总账（战场区 240×128）**

| 口径 | 改前 | 改后 | Δ |
|---|---:|---:|---:|
| **常数偏移 +4 的逐帧残差和** | 276 128 | **148 914** | **−127 214** |
| 每帧最优偏移（±1…±6）之和 | 125 513 | **115 723** | −9 790 |
| 全局最优配对之和（判定台口径） | 106 924 | 107 051 | +127 |

> ⚠️ **诚实说明**：判定台口径（全局最优配对）**几乎没动**，因为它给每一帧挑的是
> 「碰巧长得像」的**任意**重制侧帧 ⇒ 卡片修好的 2 483 + 2 156 px 被配对噪声盖住了。
> ⇒ **「残差掉到 ≈27 000」这条（P-7/P-15）还差战斗段那三帧**（原版 `step-19/21/22`
> = **73 051 px**，见 §7.1），**不是卡片能解决的**。
> ⇒ 真正落在本波账上的增量在**结算链**（§7.0：**66 411 px 归零**）。

---

## 4. 原版的卡片时间线（本流实测，直接当规格用）

仪器：`build/w19-a/tools/pose_timeline.py`（给 watch 帧逐帧定姿）
⇒ `build/s49-wave18/w5/watch-original`（原版）与 `build/w19-a/watch-none/watch-remake`（修好的重制侧）。

| 量（从**卡片升起**算起） | 原版 | 重制侧（改后） | 备注 |
|---|---:|---:|---|
| 卡片升起 | 0 | 0 | 原版＝按下那一次 A（press#9）；重制侧＝部署相位进入 `start_confirmation` 的那一帧 |
| 姿态 A 结束（翻到姿态 B） | **+98 GBA 帧** | **+100 GBA 帧** | `phase_frames = 50` 场景帧 × 2 |
| 姿态 B 保持到 | +194…+204 | +194…+204 | ⭐ **不再 A↔B 循环**（改前 300 帧后仍在循环） |
| 卡片消失（画面回到战场） | **+204** | **+204** | ⭐ 两侧**完全一致** |
| 黑场淡出开始 | +266（U1 笔记的 frame 1108） | +266 | ⇒ `lead_frames` 38 → **30** |
| 全黑 | +284…+294 | +284…+294 | |

> ⭐ 两侧的「卡片升起 → 卡片消失」窗口**逐帧同长（204 GBA 帧）**。

---

## 5. ⭐ 验收逐条结论

| # | 项 | 判据 | 结论 | 证据 |
|---|---|---|---|---|
| **A-1** | 卡片一次性走完 | 不按输入，+N 帧后卡片已到最终相位（不再 A↔B 循环） | ✅ **成立** | 修好的重制侧 watch：`f0010…f0110` 全部是**姿态 B**（对原版 `step-10-A` 残差 278…789 px，对姿态 A 残差 2 250…2 740 px）⇒ **无回绕**；`f0120` 起卡片已消失（对原版 `step-08-A` 残差 811 px ＝ 战场） |
| **A-2** | 卡片不吃输入 | 按 A 那一帧卡片**不冻结**，且那次 A **只被消费一次** | ✅ **成立** | ⭐ **按 A / 不按 A 的 300 帧 watch 逐帧 sha256 完全相同（30/30 帧，0 帧不同）** ⇒ 与原版「按不按 A 逐像素相同」的定义性质完全一致；卡片期间 A/B 键不进部署流程，部署的确认由**表演结束**触发（`deployment.confirm()` 只调用一次） |
| **A-3** | 姿态 B | 能画出原版姿态 B | ✅ **成立** | 原版 `step-10-A` ↔ 重制侧 `step-14-A` = **278 px**（改前 2 761 px；姿态 B 的美术本来就在，只是语义错，W5-9） |
| **A-4** | ⭐ 步偏移恒为 +4 | 偏移剖面全程 +4 | ✅ **卡片段成立**（0–11 步、14–19 步 = +4；sha 精确匹配的偏移集合 = {+4}）；⚠️ 12–13 步 = +5（黑场过渡的淡入级差，C 的文件）、20–24 步 = +3…+1（战斗段的拍子消耗，D 路） | §2、§3 |
| **A-5** | ⭐ 那 4 帧配对成功 | 原版 `step-12/19/21/22` 能配到帧，残差 ≈27 000 | ⚠️ **部分**：`step-12` **10 433**（黑场淡入级差，C 的文件）；`step-19/21/22` 24 460 / 27 800 / 27 643（**战斗首帧的画面**差，时刻已齐）⇒ **卡片能做的都做完了，剩下的是战斗场景的内容** | §3、§7.1 |
| **A-6** | 单测 | pass=118 / fail=20，零新增红 | ✅ **成立** | `w18-run-all-tests.sh` ⇒ **pass=118 fail=20**（与基线逐项相同；`test_battle_opening_title` **在 pass 集里**） |
| **A-7** | 接线请求 | B/C 对 `.cpp` 的需求 | ✅ **已实现 B 路的两条**（B-1 / B-2，见 §7.0，实测 **−66 411 px**）；C 路无对本文件的请求 | §7.0 |

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **A-1** | 原版的卡片是**纯定时、无视输入**的一次性演出 | W5 的 EWRAM 逐字差 + 按/不按 A 的 300 帧逐帧定价 | EWRAM 09→10 只变 1 字（30 Hz 计时器）；按 A 与不按 A 的残差表逐格一字不差 | **已确认**（W5-4/5） |
| **A-2** | 原版卡片时间线：姿态 A → 姿态 B → 自动擦除 | `pose_timeline.py` 给 W5 的 watch 帧逐帧定姿 | 姿态 A 到 **+98 帧**、姿态 B 到 **+194…+204**、**+204 卡片消失**、**+214…+224 黑场擦除开始**、**+284 全黑** | **已确认** |
| **A-3** | 重制侧的部署场景逻辑是**半速**（1 场景帧 = 2 GBA 帧） | 重制侧 watch 的 6 个姿态翻转桶 vs `phase_frames=23` | 6 个桶全部落在 23×2 的预测上；60 Hz 预测的另外 6 个桶没有翻转 | **已确认** |
| **A-4** | 重制侧卡片**在按下那一刻升起** | 同上（翻转点相对升起 = 46/92/… GBA 帧） | 成立 | **已确认** |
| **A-5** | 改后重制侧第 94 帧的捕获落在**姿态 A** | 同上 | 修好后：卡片在 +94 仍是姿态 A（759 px 对原版 `step-09`）⇒ 姿态 A 保留、姿态 B 在 +100 起 | **已确认** |
| **A-6** | ⭐ 修好后步偏移恒为 +4 | `align_capture_steps.py` 的 sha 精确匹配 + 偏移剖面 | 偏移集合 {+3} → **{+4}**；0–11 步与 14–19 步 = +4 | **已确认（卡片段）** |
| **A-7** | ⭐ 原版 `step-12/19/21/22` 能配到帧 ⇒ 残差 ≈27 000 | 同上 | `step-12` 10 433（黑场淡入级差）；`step-19/21/22` 24 460/27 800/27 643（战斗首帧的画面差）⇒ **总数降不下来** | **已证伪（不在卡片上）** |
| **A-8** | ⭐ 修好后卡片与输入无关 | 修好的 ROM 上跑 watch（按 A / 不按 A），逐帧 sha256 | **30/30 帧完全相同** | **已确认** |
| **A-9** | 黑场入口必须跟着**卡片的结束**走，不是跟着按键走 | U1 笔记的原版帧号：卡片 1046 消失、淡出 1108 开始 ⇒ 差 62 GBA 帧 = 30 场景帧 + 1 帧等键 | lead 38 → 30 后，原版 `step-11` 的残差 **30 418 → 1 212 px**，且该帧的 `non_black` 从 0.993（画面）变成 **0.048**（近黑 + 小星），与原版 0.010 同形 | **已确认** |
| **A-10** | 两侧「战斗首帧」的**时刻**是对齐的 | 锚点 + 步号推算 | 原版 `step-19` 捕获 = 卡片升起 +1034 帧；重制侧 `step-23` 捕获 = 卡片升起 +1034 帧 ⇒ **时刻齐**，但画面差 24 460 px ⇒ 差在战斗场景的内容（相机/布景） | **已确认** |
| **A-11** | ⭐ 卡片改成原版语义后，**结算链**不受影响 | 修好的 ROM 上跑 `z1_settlement_chain.py` | 48 屏 / 5 620 帧 / 1.9 s，`outcome=1`，末相位 `task_menu` ⇒ **结算链照常跑完** | **已确认** |
| **A-12** | ⭐ B 路的 W19-B-1 / W19-B-2 接线能让兩屏残差归零 | 接线后跑 `classify_settlement.py`（10 对逐屏） | 戰後對白 **26 819 → 0 px**、任務菜單 **37 694 → 0 px**、結算 **2 582 → 684 px**（立绘 1 898 px 由 B 的资产收掉，剩 684 px 是真实战果数据 ⇒ D 路） | **已确认** |

---

## 7. 接线请求

### 7.0 ⭐ 替 B 路实现的接线（已落地并实测）

B 路的 `notes/s49-fidelity/W19-B-settlement-tail.md` §6 给 A 路两条请求，
**已在 `game/src/battle_runtime_scene.cpp` 实现**：

| 请求 | 内容 | 落点 | 实测 |
|---|---|---|---|
| **W19-B-1** | 结算链的屏幕级图层改用 `create_bg(8, 48)`（butano 把 regular BG 的**中心**放在给定位置 ⇒ `(0,0)` 显示的是 256×256 图的**居中**窗口） | `battle_settlement_screen_runtime_renderer::update()` 的任務菜單分支 | 任務菜單 **37 694 → 0 px** |
| **W19-B-2** | 對白相位改画「對白页层」（原版的框与台词**烘在 BG 层里**），并停掉精灵框与结算字体文本 | 同上 + 新增 `battle_settlement_dialogue_page_item()` 与 `_dialogue` / `_dialogue_page` 成员 | 戰後對白 **26 819 → 0 px** |

⚠️ **我比 B 的原始代码多做了两处**（B 的代码若照抄会漏）：

1. **页切换**：B 的片段是 `if(item && ! _dialogue) { _dialogue = item->create_bg(8, 48); }`
   ⇒ **页码变了也不会重建图层**（第一页会一直显示）⇒ 我加了 `_dialogue_page`，
   页码变了先 `reset()` 再建。
2. **B-2 还需要释放任務菜單的两张层**（8bpp 共用 BG 调色板 bank，优先级相同会打架）
   ⇒ 對白分支里 `_background.reset(); _overlay.reset();`（B 的文字里提到了，
   代码片段里没写全）。

⚠️⭐⭐ **接线与资产是「一个开关」绑在一起的**（为了不让共享树在 B 的资产拷进来之前
构建失败）：

```cpp
#if defined(__has_include)
#  if __has_include("bn_regular_bg_items_scenario_41_postbattle_dialogue_page_1.h")
#    define KONOHA_SETTLEMENT_DIALOGUE_PAGES 1
#  endif
#endif
```

⇒ **B 的 7 张页层资产不在树里 ⇒ 结算链的行为与今天一模一样**（旧的精灵框 + 结算字体），
树照常构建；**资产一拷进来 ⇒ 自动切到新渲染**（對白画页层、任務菜單用 (8,48)）。
⇒ ⇒ **父代理接线时不必担心顺序**，但**要拷 B 的资产**（否则残差不归零）：
`graphics/scenario_41_postbattle_dialogue_page_1..7.bmp(+json)`、
`graphics/scenario_41_postbattle_bg.bmp/json`、
`graphics/scenario_41_postbattle_ui.bmp/json`，
以及结算屏立绘 `graphics/battle_ui_result_{naruto,sasuke,sakura}.bmp`（B 的 §5）。

### 7.1 → **D 路 / 战斗场景**：战斗首帧的画面差 24 460 px（**残差最大的一块：73 k px**）

* **现象**：原版 `step-19-A`（战斗段的第一张可见帧）与重制侧 `step-23-A` 差
  **24 460 px**（战场区的 80 %）；原版 `step-21/22`（移动相位覆盖层，176 个亮格）
  在重制侧的 35 帧里**没有对应帧**（27 800 / 27 643 px）。
* **时刻是齐的**（A-10）：两侧的「战斗首帧」都在**卡片升起 +1034 GBA 帧**，
  所以这**不是**时间问题，是**战斗场景自己的画面**问题。
* **线索**：原版 `step-19` 的 `bg_hofs = [160,261,268]`（地图滚动了 12 px），
  原版 `step-12` 是 `[160,261,256]`；重制侧战斗首帧的 `bg_hofs` **未测**
  （可用 `tools/s49_w5/w5_probe_sanity.py` 读一下）。
* **请求**：在战斗场景里查「战斗开场第一帧的相机滚动位置与布景」，
  使重制侧 `step-23` 能对上原版 `step-19`。**这不在 A 路的文件里。**

### 7.2 → **C 路**：黑场过渡的**淡入级差**（`step-12` 仍差 10 433 px）

* **现象**：黑场段本身已经对齐（原版 `step-13…18` ↔ 重制侧 `step-17…22`，
  逐帧 0/0/43/0/0 px），但**过渡的淡入级差半拍**：
  原版 `step-12` 的 `non_black = 0.832`（画面 83 % 回来），
  重制侧 `step-16` 是 **0.973**（97 % 回来）⇒ 重制侧淡入**早**了半拍。
* **根因（C 的文件）**：原版的**星形光圈**从「卡片消失」到「闭死」用了约
  **60 GBA 帧**（frame 1046 → 1106/1126），而重制侧的光圈跟着**调色板淡出**
  的 12 个场景帧（24 GBA 帧）走 ⇒ 光圈闭得太早。
* **请求**：在 `battle_black_field_timing.h` / `battle_black_field_star_mask.h`
  里让**光圈的收拢速度**跟原版一致（与调色板淡出**解耦**），
  也就是前 12 个星形级不要挤在 12 个场景帧里。
* ⚠️ **连带**：A 路的 `battle_black_field_event1_lead_frames = 30` 是按
  「光圈在淡出的 12 个场景帧里走完」推出来的；**C 改了光圈速度后，
  这个 30 必须重推**（原版的口径是：淡出比卡片消失晚 **62 GBA 帧**）。

### 7.3 → **父代理（接线清单）**

1. 拷回我独占的两个文件 + **伴随改动的 `game/tests/test_battle_opening_title.cpp`**（§1.2，**漏拷会让单测多 1 项红**）。
2. **B 路的 9 张结算资产 + 3 张立绘**（§7.0 的清单）与我的 `.cpp` 一起拷 ⇒ 结算链的
   **66 411 px** 归零；**顺序无所谓**（接线有 `__has_include` 开关），
   但**资产不拷 ⇒ 结算链残差不归零**。
3. 我在 `battle_runtime_scene.cpp` 里把 `battle_black_field_event1_lead_frames`
   从 38 改成 **30** —— 这是**波 18 W3 调过的常量**，请在合并时确认；
   口径见 §4 与 A-9。
4. 判定台的读数请用**最终 ROM**（`7e4c1581…`）重跑；本文的偏移剖面就是那一版。

---

## 8. 跑过的命令与关键数字

```powershell
# 1) 构建（隔离副本；--shared 可切回共享 graphics）
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w19-a/tools/build_w19a.sh
#    ⇒ "ROM fixed!"  三次：lead=38 / lead=30 / lead=30+B 路接线+B 路资产

# 2) 暂存 B 路资产（共享 graphics 只读地拷进 graphics-local/）
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w19-a/tools/stage_b_assets.sh
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w19-a/tools/stage_b_portraits.sh

# 3) 重录重制侧 walk（35 帧，Down,Down + A×32，HOLD=4 / SETTLE=90 / ZERO=240，HLE BIOS）
python build/w19-a/tools/capture_remake.py --rom build/w19-a/butano-sequel/butano-sequel.gba \
    --out build/w19-a/capture-remake-final --probe build/w19-a/probe/mgba-probe.exe
#    ⇒ exit_code 0, done_marker true, frame_count 35/35
#    录完检查：Get-Process -Name 'mgba-probe' -ErrorAction SilentlyContinue ⇒ 空（无孤儿）

# 4) 偏移剖面（父代理的仪器，只读调用）
python tools/s49_wave18/align_capture_steps.py \
    --original build/s49-package-u3-final/work/s49-report/capture-original \
    --remake   build/w19-a/capture-remake-final --out build/w19-a/align-final.json

# 5) 全 25×35 残差矩阵（全局最优配对）
python tools/s49_w5/w5_walk_align.py --original <同上> --remake build/w19-a/capture-remake-final \
    --out build/w19-a/align-matrix-final.json

# 6) 卡片自跑：按 A / 不按 A（两次 300 帧 watch）
python tools/s49_w5/w5_titlecard_watch.py --remake-rom build/w19-a/butano-sequel/butano-sequel.gba \
    --remake-capture build/w19-a/capture-remake-lead30 --exe build/w19-a/probe/mgba-probe.exe \
    --frames 300 --every 10 --press none --out build/w19-a/watch-none
python tools/s49_w5/w5_titlecard_watch.py … --press A --out build/w19-a/watch-pressa
#    ⇒ 30/30 帧的 sha256 完全相同（0 帧不同）

# 7) 结算链（只读调用 B/D 的仪器）
python tools/s49_battle_balance/z1_settlement_chain.py --rom build/w19-a/butano-sequel/butano-sequel.gba \
    --out build/w19-a/chain-final --exe build/w19-a/probe/mgba-probe.exe
python tools/s49_w4/classify_settlement.py --truth build/s49-victory-capture/w4/settlement-truth \
    --remake build/w19-a/chain-final/shots --out build/w19-a/classify-final.json

# 8) 本流自测仪器
python build/w19-a/tools/pose_timeline.py --watch build/w19-a/watch-none/watch-remake \
    --original build/s49-package-u3-final/work/s49-report/capture-original \
    --remake build/w19-a/capture-remake-lead30
python build/w19-a/tools/anchors.py --original <同上> --remake build/w19-a/capture-remake-final

# 9) 单测
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh \
    /mnt/d/Github/gba-naruto/build/w19-a/butano-sequel
#    ⇒ pass=118 fail=20（基线相同）
```

| 数字 | 值 |
|---|---|
| 原版 `step-09` → `step-10` 整帧差 | **2 247 px**（全在字形区） |
| 原版 09→10 的 EWRAM 变化 | **1 个字**（30 Hz 计时器） |
| 原版卡片：姿态 A 时长 / 总时长 | **98 / 204 GBA 帧** |
| 重制侧卡片（改后）：姿态 A 时长 / 总时长 | **100 / 204 GBA 帧** |
| 原版 `step-10` ↔ 重制侧 `step-14` | **278 px**（改前 2 761） |
| 原版 `step-11` ↔ 重制侧 `step-15` | **1 212 px**（lead=38 时 30 418） |
| sha 精确匹配的偏移集合 | **{+4}**（改前 {+3}） |
| 常数偏移 +4 的残差和 | **148 914**（改前 276 128） |
| 卡片 watch：按 A vs 不按 A | **30/30 帧逐字节相同** |
| 结算链：戰後對白 / 任務菜單 / 結算 | **0 / 0 / 684 px**（改前 26 819 / 37 694 / 2 582） |
| 结算链整条 | **−66 411 px** |
| 单测 | **pass=118 / fail=20** |
| ROM sha256 | `7e4c158109ff1830d3d7ba4a934eb45fd9475a8a56d66802fb2480a2c1708119` |

---

## 9. 遗留与风险

1. ⛔ **A-5 只部分达成**：判定台的总残差没降，因为 **73 k px 集中在原版
   `step-19/21/22`（战斗段）** ⇒ 战斗场景的**内容**（相机滚动 / 布景）必须先修。
   §7.1 是给 D 路的接线请求。
2. ⚠️ **`battle_black_field_event1_lead_frames` 30 是我推的**：口径＝
   「黑场淡出比卡片消失晚 62 GBA 帧」（原版 frame 1046 → 1108）。
   若 C 改了光圈速度，这个 30 必须重推（§7.2 已写明）。
3. ⚠️ **姿态 A 只差 6 帧的余量**：重制侧第 94 帧的捕获落在姿态 A，
   而姿态 B 在 +100 帧开始 ⇒ 只有 6 GBA 帧的余量。实测余量 6 帧（759 px 命中），
   但**任何让卡片提前 2 帧翻相的改动都会把这一帧打回 2 761 px** ⇒
   `phase_frames = 50` 不要动。
4. ℹ️ **本机构建非字节可复现** ⇒ 一切读数绑定 ROM `7e4c1581…`；
   接入 B 路资产后，图块分配会变（`step-12` 的残差从 28 395 变成 24 101），
   **卡片那一段（`step-09…11`）逐帧不变**。
5. ℹ️ 卡片播放期间 **B 键也被吞掉**（原版在卡片期间无视一切输入）。
   这是照原版语义；若产品上想保留「卡片期间可取消」，需要父代理拍板。
6. ℹ️ 我在自己的副本里另建了 `graphics-local/`（共享 graphics ＋ B 路资产），
   **共享树的 graphics 全程只读**；副本用
   `make GRAPHICS="graphics-local ../third_party/butano/common/graphics"` 构建。
