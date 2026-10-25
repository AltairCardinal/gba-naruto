# Stream B —— 胜利 / 结算序列对照（原版 vs 重制）

> 工具：`tools/s49_victory_compare.py`
> 产物：`build/s49-victory/compare.json`（机器可读）+ `build/s49-victory/compare.md`（对照表）
> 2026-10-23。所有数字都是本机实测，每条都配一条可复跑命令。

## 0. 一句话

**BRIEF §2 的 21k–27k px 残差确实是「配对差」，而且我把它查到了机制级别：
那几帧在原版里是「重制侧根本不会画的东西」（黑场过渡、「開始」书法字、
移动中隐藏 HUD 的过渡帧）或者「重制侧还没走到的那一回合」。
但「重制侧到不了胜利屏」是错的 —— 胜利屏在重制侧的产品代码里已经存在，
只是从来没被录到过。**

同时给出一条**可立刻执行的捷径**：仓里已经躺着一份与原版结算屏
**逐像素只差 532 px（1.4%）**的复刻美术，运行时却没用它。

---

## 1. 幸存的原版胜利/结算帧 —— 到底有几张

BRIEF 只说「790 张原版 PNG 还在，但 25 帧那一组没了」。
本 stream 的任务是把它数清楚。**第一遍数错了两次，两处都记在 §7.2 里。**

| 来源 | 帧数 | 说明 |
|---|---:|---|
| `s49-original-victory-probe-01` … `-22`（顶层） | 137 | 单层 walk 探针，每个目录 2–19 张 |
| `s49-original-victory-probe-20-driver` / `-21-driver`（**嵌套**） | 75 | 14 个 drive 段（`s01-r1-teleport-aim` …），**非递归发现会整段漏掉** |
| `s49-original-victory-20261020-v1` | 398 | 68 个场景目录（`p01…p10` 战后流程 + `r01…r28`/`t01…t21`/`u01…u13` 战斗推进） |
| `s49-original-settlement-20261021-v1`（非 `scratch/`） | 8 | 4 个结算场景 × 2 张 |
| **artifact 侧合计** | **618** | |
| `build/s49-original-walk` | 25 | BRIEF §2 残差基准，单独入表以便闭环 |
| **入表合计** | **643** | **533 张唯一画面**（618 artifact 帧 → 512 张唯一；25 帧 walk → 25 张唯一，其中 **4 张与 artifact 帧内容重合**） |

**独立复核**（不依赖我的工具）：

```powershell
$art='D:\Shell\Github\gba-naruto-butano\artifacts'
(Get-ChildItem $art -Directory -Filter 's49-original-victory-probe-*' | ForEach-Object {
   (Get-ChildItem $_.FullName -Recurse -File -Filter *.png).Count } | Measure-Object -Sum).Sum   # 212
(Get-ChildItem "$art\s49-original-victory-20261020-v1"  -Recurse -File -Filter *.png).Count       # 398
(Get-ChildItem "$art\s49-original-settlement-20261021-v1" -Recurse -File -Filter *.png).Count      #  32
```

⇒ 212 + 398 + (32 − **24 张 `scratch/` 拼版图**) = **618** ✔ 与工具一致。

**`scratch/` 的 24 张不是原始帧**（是 `orig-sheet-*.png` / `rev-sheet-*.png` /
`victory-sheet-*.png` 这类拼版图，其中 `orig-sheet-03.png` 有 2.5 亿像素，
PIL 直接判成 decompression bomb）⇒ 工具按 `scratch` 路径排除，并在
`compare.json` 的 `meta` 里写明。

### 1.1 目录名叫「victory」，里面**没有**胜利屏

`s49-original-victory-probe-01…22` 的 `inputs.json` 标签逐个读出来是：

```
probe01-ninjutsu-list-to-target   probe02-move-left        probe03-move-confirm
probe04-attack-bee                probe05-teleport         probe06-confirm-teleport
probe07/08-teleport-anim          probe09-face-left        probe10-open-ninjutsu-list
probe11-menu-to-ninjutsu          probe12-sakura-command-menu
probe13-naruto-turn1              probe14-teleport-anim-finish
probe15-skip-allies               probe16-skip-sasuke-and-koharu
probe17-after-enemy-phase         probe18-aim-cross-shuriken
probe19-fire-cross-shuriken       probe20-confirm-attack   probe21-attack-executes
probe22-finish-cutin
```

⇒ **22 个探针全部是战斗过程的探针，没有一个探到结算屏。**
目录名里的 "victory" 是「朝胜利方向的探针」，不是「探到了胜利屏」。

---

## 2. 做了什么 / 改了什么

### 2.1 改动的文件（**只动了本 stream 独占的 3 个**）

| 文件 | 性质 | 说明 |
|---|---|---|
| `tools/s49_victory_compare.py` | **新增**（唯一交付物） | 交叉对齐 + 对照表 + 判定 |
| `notes/s49-fidelity/B-victory-settlement.md` | **新增**（本文件） | 报告 |
| `build/s49-victory/*` | 临时产物 | 对照表 / 接触印相 / 差分图 |

**没有**改重制线、逆向线或 master 仓的任何其他文件。重制线的产品代码
**只读**（读 `battle_ui_model.h` / `battle_runtime_scene.cpp` / `graphics/*.bmp`）。

### 2.2 工具做什么

1. 从 `--artifacts-root` 递归发现 618 张幸存的原版胜利/结算侧帧 + 25 帧 walk；
2. 从 18 个目录收 **385 张重制帧**（129 张唯一画面）作候选；
3. **逐张**做交叉对齐（不按序号配对），战场区与整屏残差各算一次；
4. 给每一行一个**画面内容描述**和一个**判定**。

### 2.3 差分的定义（必须与 BRIEF 的数字可比）

`diff_pixels()` 用 `ImageChops.difference` + `lighter` 折叠三通道，
统计「RGB 三元组不同」的像素数 —— 与 `tools/compare_frame_dirs.py` **同一条规则**。

**用现成工具交叉验证**（不是自说自话）：

```powershell
python tools\compare_frame_dirs.py build\s49-original-walk build\s49-remake --field-area 0 0 240 128
```

| 原版帧 | `compare_frame_dirs.py` | 本工具 | BRIEF §2 |
|---|---:|---:|---:|
| step-14-A | 0 | 0 | 0 |
| step-15-A | 0 | 0 | 0 |
| step-16-A | 344 | 344 | 344 |
| step-08-A | （按序号配对 28,026） | 1,026（交叉对齐） | 1,026 |
| step-13-A | （按序号配对 29,884） | 28（交叉对齐） | 28 |

⇒ 同一批文件、同一套规则，**逐项复现 BRIEF 的 0 / 0 / 344 / 1,026 / 28**。

---

## 3. 跑了什么验收

| # | 命令 | 结果 |
|---|---|---|
| A1 | `python tools/s49_victory_compare.py --out build/s49-victory/compare.json` | **exit 0**，33 s |
| A2 | `python tools\compare_frame_dirs.py build\s49-original-walk build\s49-remake --field-area 0 0 240 128` | exit 0，逐帧数字与本工具一致（§2.3） |
| A3 | PowerShell 独立递归计数（§1） | 618 ✔ |
| A4 | `python build\s49-victory\_pair_test.py`（10 组指定配对） | 见 §4.4 |
| A5 | `python build\s49-victory\_hud_check.py`（385 帧底带扫描） | 见 §4.3 |
| A6 | `python build\s49-victory\_s41_layers_cmp.py` / `_s41_runtime_cmp.py` | 见 §5 |
| A7 | 新写文件 BOM/行尾检查 | 全部 LF、无 BOM（§7.3） |

产物：`build/s49-victory/compare.json`（1.25 MB，含 643 行逐帧数据）、
`compare.md`（651 行对照表）、以及接触印相图（§7.1）。

---

## 4. 观察到什么

### 4.1 对照表的规模与分布

643 行（原版帧 → 最佳重制帧 → 战场区残差 → 整屏残差 → 画面内容 → 判定）：

| 画面类别 | 帧数 | 战场区残差 min | 战场区残差 max |
|---|---:|---:|---:|
| `battle-field` | 591 | **0** | 29,333 |
| `postbattle-ui`（S49 战后流程 p01–p10） | 40 | **2,206** | 23,846 |
| `settlement-panel`（s41/s46 结算屏） | 8 | **10,417** | 22,578 |
| `transition-black` | 4 | 25,179 | 25,460 |

| 判定 | 帧数 | 含义 |
|---|---:|---|
| `content-difference` | 390 | 重制侧**没有**这一时刻的帧 ⇒ 配对/覆盖问题，**不许改代码** |
| `rendering-difference` | 241 | 同一时刻画法不同 ⇒ **真产品差，要改代码** |
| `identical` | 7 | 逐像素相同 |
| `missing-in-remake` | 5 | 原版有的元素重制侧从不画 |

### 4.2 三个问题的答案

#### Q1「重制侧的胜利/结算屏与原版差多少？」

**差「整个屏」。** 48 张结算/战后帧里，**没有任何一张**能被重制侧的某一帧对上：

* 战场区最小残差 **2,206 px**（= 战场区 30,720 px 的 **7.2%**），
  最大 **23,846 px**（**77.6%**）；
* 整屏残差最高 **29,892 / 38,400 px（77.9%）**；
* **0 px 的结算帧：0 张。**

而且 48 张结算/战后帧的最佳匹配**全部落在重制的「战前简报对话框」**
（`step-00-base` / `step-01-Down` / `step-02-Down` / `step-03-A`，共 47/48），
另 1 张落在对话演出。
⇒ **重制侧的语料里一张结算屏都没有，最像的那张是战前简报。**

#### Q2「差在哪（文字？数值？布局？）」

**这三个都不是差因 —— 因为没有可比的帧。** 差异的性质是
**「重制侧尚未产出过结算屏」，不是「结算屏画错了」**。

但布局层面能给出确切的数（§5）：重制运行时那套结算屏美术
**整体比原版下移 48 px**，数字面板框几乎整块出屏。

#### Q3「重制侧根本到不了胜利屏？」

**分两层，答案相反：**

* **录到的帧里到不了。** 385 张重制帧（18 个目录，含 10 个不同构建变体）
  里没有一张结算屏；`build/s49-remake` 的 **step-23…step-34 共 12 张**
  停在同一句 `CANNOT SELECT`（彼此差 0–1,763 px，只是 idle 动画在动），
  之后再按 A 键也不推进。
* **产品代码里到得了。**
  * `butano-sequel/game/include/konoha/battle_ui_model.h:294-313`：
    `battle_scene_phase::result / outcome / complete / level_up / training`
    → `result.show_result_panel = true`
  * `butano-sequel/game/src/battle_runtime_scene.cpp:1387-1405`：
    建 `battle_ui_result_background` + `battle_ui_result_panel`（`create_bg(0, 0)`，**无滚动**）
  * 同文件 `1407-1456`：三名角色 sprite，x = −20 / 36 / 92，y = −8
  * `battle_result_sprite_font` / `battle_result_compact_sprite_font` 画文字与数字
  * `battle_ui_result_total_palette.bmp` 调色板

⇒ **缺的不是功能，是「把游戏打到胜利并把它录下来」这件事。**
⇒ D2/D3 的动作应该是**补路线/补录制**，不是补渲染。

### 4.3 BRIEF 的 21k–27k 到底是什么（机制级）

原版 25 帧 walk 的逐帧结果（最佳重制帧取自 385 张候选）：

| 原版帧 | 最佳重制帧 | 战场区残差 | 判定 | 机制 |
|---|---|---:|---|---|
| step-14-A | step-14-A | **0** | identical | 对话演出 |
| step-15-A | step-15-A | **0** | identical | 对话演出 |
| step-17-A | step-16-A | **0** | identical | 对话演出 |
| step-13-A | step-14-A | 28 | rendering-difference | 同一句台词，差一个滚动箭头 |
| step-16-A | step-16-A | 344 | rendering-difference | 同一句台词，描边粒度 |
| step-08/09/10-A | step-12/13-A | 1,026 / 6,064 / 4,990 | **missing-in-remake** | 原版有「**開始**」书法字，重制侧**从不画**（重制侧在 HUD 区写 `START` 文本） |
| step-11-A | step-16-A | 25,447 | **missing-in-remake** | 原版有**黑场过渡**，重制侧**从不画** |
| step-18-A | step-16-A | 25,459 | **missing-in-remake** | 同上 |
| step-19-A | step-17-A | 24,460 | content-difference | 同为「回合 1 玩家 的行動」提示框，但**回合/战场状态不同** |
| step-20-A | step-17-A | 4,014 | content-difference | 回合提示 vs 回合横幅，不同瞬间 |
| step-21-A | step-11-A | 27,322 | content-difference | 原版「单位移动到位」，重制侧对应帧还在部署阶段 |
| **step-22-A** | step-07-A | **21,260** | content-difference | 原版是**移动中 HUD 隐藏**的过渡帧 |
| step-23-A | step-18-A | **1,323** | rendering-difference | 同一时刻（卡卡西+鸣人重叠 + 「SELECT 詳細」+ HUD） |
| step-24-A | step-19-A | 1,123 | rendering-difference | 同一个行动菜单 |

**step-22 的「重制侧没有对应帧」是实测的，不是推的**：

```
$ python build\s49-victory\_hud_check.py
remake frames scanned: 385
step-22-A.png: bottom band (240x32) best remake match = 5265 px  (s49-remake/step-07-A.png)
step-23-A.png: bottom band (240x32) best remake match = 0 px    (s49-remake/step-17-A.png)
distinct remake bottom bands: 23
   187 frames share this bottom band   e.g. s49-remake/step-17-A.png
```

* 385 张重制帧的底部 32 行**只有 23 种**，其中 187 张共享同一条（标准 HUD）；
* 原版 step-22 的底带（HUD 隐藏）**最小残差 5,265 px** ⇒ **一张都没有**；
* 顺带：原版 step-23 的底带与重制 step-17 的底带 **0 px** ⇒ HUD 带本身逐像素相同。

### 4.4 ⚠️ 对 BRIEF §2 的一处订正

BRIEF §2 那行写的是「**step-22/23 → 21k–27k px**」。本机逐帧复现后：

* BRIEF 的**其它每一个数字都复现了**（0 / 0 / 0 / 28 / 344 / 1,026）；
* 但 **step-23-A 实测是 1,323 px，不是 27k**；
* ≥21k 的那一族其实是 **step-11（25,447）/ step-18（25,459）/ step-19（24,460）
  / step-21（27,322）/ step-22（21,260）**。

⇒ **BRIEF 把 step-22/23 这一行的帧号写错了。** 影响是实的：
D1 的「22–24 h 配对差归零」如果按 BRIEF 的帧号去做，
会拿 step-23（一个 1.3k 的**真产品差**）当成配对差去消，
反而漏掉真正没有对应帧的 step-19/21/22。

### 4.5 BRIEF 之外的新 0 px 配对

7 张 0 px 帧里有 **4 张是新的**，而且指向一件好事：

| 原版帧 | 重制帧 | 战场区 | 整屏 | 内容 |
|---|---|---:|---:|---|
| `r01-intro/step-11-A.png` | step-14-A | 0 | **0** | 对话演出：鸣人 + 小樱头像，小樱台词 |
| `r01-intro/step-12-A.png` | step-15-A | 0 | **0** | 对话演出：鸣人 + 小樱 + 佐助头像 |
| `r01-intro/step-13-A.png` | step-16-A | 0 | **0** | 对话演出：佐助台词 |
| `probe-13/step-02-A.png` | step-22-A | 0 | **0** | **忍术列表菜单**（替身术/影分身/忍术组合/十字手里剑 + 查克拉 3 / 范围 1 / 成功率 100%） |

⇒ **重制侧的对话演出（头像 + 对话框 + 文字）和忍术列表菜单已经逐像素一致。**
这对 D2「过场与演出整条序列 0 px」是现成的正面证据。

---

## 5. 结算屏的资产级对照（顺带查出来的一件事）

因为重制侧没有结算帧可对，改从**美术资产**层面对照
（原版 `s41-result` 是 scenario-41 的结算屏，仓里有它的复刻资产）。

### 5.1 运行时用的那套 vs 原版

`butano-sequel/graphics/battle_ui_result_background.bmp` + `battle_ui_result_panel.bmp`
（各 256×256 8bpp BG 层）按 scroll (0,0) 合成后与原版 `s41-result/step-00-base.png` 比：
**38,152 / 38,400 px 不同（99.4%）**。

⚠️ **这个 99.4% 不能当渲染差读**：重制侧面板里的文字和数字是
**运行时用 sprite 画**的（`battle_result_sprite_font`），
静态 BG 只提供边框 ⇒ 拿静态 BG 去比渲染帧是错配。

正确的比较是**布局**：

| 元素 | 原版 | 重制运行时合成 | 差 |
|---|---|---|---|
| 页签行（绿框） | y **0–31** | y **48–79** | **下移 48 px** |
| 灰色渐变 | y 32–74 | y 80–122 | 下移 48 px |
| 数字面板框 | y 104–159 | y **152–（出屏）** | 240×160 的屏里只剩 **8 行** |

页签行的**美术是同一套**：把重制的 y48–80 与原版的 y0–32 对齐后，
差 **398 / 7,680 px（5.2%）**。
⇒ 结算屏的差异是**垂直布局 + 运行时拼装**，不是文字/数值画错。

### 5.2 ⭐ 仓里已经有一份 1:1 的复刻，但运行时没用

`butano-sequel/graphics/scenario_41_result_{top,middle,bottom}.bmp`
（各 256×256 8bpp BG 层）按 bottom ← middle ← top 合成后：

```
composite vs ORIGINAL s41-result: 532 differing pixels of 38400      # 1.4%
row bands with differences:  y 50-97   532 px                          # 只有角色精灵那一条
```

⇒ **页签行、灰色渐变、数字面板框、全部文字（经验值 / 鸣人 / 经验分 / 面临分 /
回合分 / 合计 150）逐像素相同**；532 px 的差异全部落在 y 50–97 的角色精灵行带。

但是：

```powershell
Select-String -Path 'D:\Shell\Github\gba-naruto-butano\butano-sequel\game\**\*.cpp' `
              -Pattern 'scenario_41_result'
```

⇒ **零命中**。运行时用的是 `battle_ui_result_*`，这两套美术**没接上**。

**这是 D2/D3 最便宜的一条路**：要么把运行时切到 `scenario_41_result_*`，
要么把 `battle_ui_result_*` 的布局上移 48 px。前者是现成的。

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| B1 | 幸存的原版胜利/结算侧帧是 543 张 | 工具递归发现 vs PowerShell 递归计数 | 工具 543 vs 独立计数 **618**（差 75 = 两个 `-driver` 目录里的嵌套段） | **已证伪**（第一遍数错） |
| B2 | 幸存的帧是 618 张 | PowerShell 递归计数 + 工具递归发现，两条独立路径 | 两条都给出 **618**（212 + 398 + 8） | **已确认** |
| B3 | `s49-original-victory-probe-*` 里含胜利屏 | 读 22 个 `inputs.json` 的 `label` + 看帧 | 全部是战斗探针（ninjutsu-list / move / attack-bee / teleport / cross-shuriken / skip-allies），**0 个结算屏** | **已证伪** |
| B4 | 21k–27k 那几帧是配对差 | 逐帧交叉对齐 + 与 BRIEF 数字逐项比对 | 是配对差，机制是「黑场 / 開始 书法字 / HUD 隐藏的过渡帧 / 不同回合」 | **已确认** |
| B5 | BRIEF 的「step-22/23 → 21k–27k」帧号正确 | 用同一批文件跑 `compare_frame_dirs.py` + 本工具 | 其它数字全复现，但 **step-23 实测 1,323 px**；≥21k 的是 step-11/18/19/21/22 | **已证伪**（BRIEF 那一行写错） |
| B6 | 原版 step-22 的 HUD 隐藏帧在重制侧不存在 | 扫描全部 385 张重制帧的底部 32 行带 | 385 帧只有 23 种底带，187 帧共享标准 HUD；step-22 底带最小残差 **5,265 px** | **已确认** |
| B7 | 重制侧语料里没有结算屏 | 48 张结算/战后帧逐张交叉对齐，最小残差 2,206 px，0 张为 0 | **0 张** 0 px；最佳匹配全是战前简报框 | **已确认** |
| B8 | 重制侧**没有**胜利屏功能 | grep `show_result_panel` / `battle_ui_result_*` | 产品代码里**有**（`battle_ui_model.h:294-313`、`battle_runtime_scene.cpp:1387-1456`） | **已证伪**（缺的是路线/录制，不是功能） |
| B9 | 结算屏的差异在文字/数值 | 静态 BG vs 渲染帧逐像素比 | **99.4% 不同是错配**（文字数字是运行时 sprite）；真正的布局差是**下移 48 px** | **已证伪**（差因问错了） |
| B10 | 仓里已有 1:1 的结算屏美术但没接上 | `scenario_41_result_*` 三层合成 vs 原版渲染帧；再 grep 运行时引用 | 合成差 **532 / 38,400 px（1.4%）**，差异全在角色精灵行带；运行时 **0 引用** | **已确认** |
| B11 | 重制侧对话演出/忍术菜单还没对齐 | 643 行交叉对齐里找 0 px | 7 张 0 px，其中 **4 张是新的**（对话演出 ×3 + 忍术列表 ×1） | **已证伪**（这些已经一致） |
| B12 | 重制侧 step-23…34 是 12 张完全相同的冻结帧 | 逐对比对 | 彼此差 **0–1,763 px**（idle 动画），不是完全相同 | **已证伪**（冻结但有 idle 动画） |

---

## 7. 给 D2 / D3 的结论与建议

### 7.1 结论

1. **产品差 vs 配对差已经分开，且是判据级的**：
   `compare.json` 里每一行都有 `verdict`。
   390 帧是配对差（不改代码），241 帧是真产品差（改代码），5 帧是重制侧缺元素。
2. **BRIEF 的「21k–27k」那一行帧号要改**（§4.4）。否则 D1 会打错靶子。
3. **「重制侧到不了胜利屏」是错的**：功能在，缺的是**把游戏打到胜利并录下来**。
4. **结算屏的现成捷径存在**：`scenario_41_result_*`（1.4% 差）vs 运行时那套（下移 48 px）。
5. **原版 S49 自己的结算屏从来没被拍到过**，也没有对应 checkpoint（§7.2）。

### 7.2 最大的卡点：原版 S49 的结算屏**没有真值**

`artifacts/runtime-checkpoints/` 里 **153 个 checkpoint 全在**，包括：

```
scenario-49-battle-14-entry.ss9                    90250 B
scenario-49-battle-14-postbattle-task-menu.ss9    65655 B
scenario-49-battle-14-turn4-two-kills.ss9         96196 B
scenario-49-post-training-task-menu.ss9           68243 B
```

但 **没有** `scenario-49-...-victory-reward.ss9` / `-result.ss9`
（对照 scenario-41 有 `scenario-41-victory.ss9` / `scenario-41-result.ss9`，
scenario-46 有 `scenario-46-victory-reward.ss9`）。

⇒ **原版 battle-14 的结算屏既没被拍、也没有存档点。**
`drive_victory.py` 的战斗链只推到第 5 回合（`u13-dialog-r5`），
探针链停在 `probe22-finish-cutin`（十字手里剑演出），**都没打完**。

**D2/D3 的第一个动作应该是这个**（不是改渲染）：
把原版 battle-14 打通到胜利 ⇒ 录到 S49 自己的结算屏真值 ⇒
才有资格谈「重制侧差多少」。否则只能拿 scenario-41/46 的结算屏当替身。

（好消息：`scenario-49-battle-14-postbattle-task-menu.ss9` 在，
⇒ 原版的**战后菜单**可以立刻在本机重录，不用重打。）

### 7.3 建议的排期输入

| 时段 | 建议 | 依据 |
|---|---|---|
| D1 22–24 h（原「配对差归零」） | **改帧号**：目标应是 step-11 / 18 / 19 / 21 / 22；step-23（1,323 px）要当**产品差**处理 | §4.3 / §4.4 |
| D1 内（新增，~1 h） | 决定结算屏走哪条路：切 `scenario_41_result_*`（1.4% 差，已有）还是修 `battle_ui_result_*` 的 48 px 布局 | §5.1 / §5.2 |
| D2 42–48 h（原「过场与演出」） | **对话演出与忍术列表已经 0 px**，别重做；真正要补的是「**開始**」书法字与黑场过渡 | §4.3 / §4.5 |
| D2（前置，可能 4–8 h） | **打通原版 battle-14 到胜利**，录 S49 结算屏真值 | §7.2 |
| D3（前置） | 把重制侧也驱动到 `battle_scene_phase::result` 并录帧；这是判定「重制侧到不到得了」的**唯一**办法 | §4.2 Q3 |

### 7.4 给下游的注意事项

* `compare.json` 的 `rows[]` 每行都带 `path`（绝对路径）、`sha256`、
  `best_remake_path`、`field_px` / `full_px` / `verdict`，
  **可以直接当门禁期望值用**，不用重新跑。
* 候选集比 BRIEF 用的 35 帧大（385 帧 / 129 张唯一画面，跨 10 个重制构建变体），
  所以最小值可能比 BRIEF 更小。
  **本 stream 里最明显的一处不是候选集效应，而是 BRIEF 写错了帧号**
  —— step-23 从 BRIEF 记的 27k 掉到 **1,323 px**（§4.4），
  而 step-08-A（1,026）等其余数字前后一致。
  **建议 D2 统一用 385 帧候选集**，并把 §4.3 的帧号表作为基线，
  否则最小值会被候选集大小左右。

---

## 8. 卡在哪 / 剩余风险

1. **原版 S49 结算屏没有真值**（§7.2）—— 本 stream 无法自解，
   因为它需要「把原版 battle-14 打赢」这件重活。
2. **重制侧的结算屏从未被渲染过**，所以「重制侧结算屏到底长什么样」，
   本 stream 只能从**资产层**推断（§5），不能从**渲染帧**确认。
   一旦有人把重制侧驱动到 result phase，**§5.1 的 48 px 布局结论必须重测**
   （本 stream 的合成用的是 `create_bg(0,0)` 的默认 scroll，
   运行时若另有 scroll 补偿，结论会变）。
3. `scenario_41_result_*` 是 **scenario-41** 的复刻，不是 S49 的。
   它证明「这套做法可行」，**不证明** S49 的结算屏长得一样
   （S49 的参战人数、奖励项可能不同）。
4. **判定阈值 10,000 px** 是从 BRIEF 已有的两个总体（1,000–2,500 vs 21,000–27,000）
   取中间空档，不是统计检验出来的。实测上这个空档确实存在：
   241 行 `rendering-difference` 的战场区残差落在 **28 – 9,969 px**（全部 < 10,000）。
   390 行 `content-difference` 里 **376 行 ≥ 10,000**，另 **14 行 < 10,000**：
   * **12 行**是 `postbattle-ui` 帧（残差 2,206–5,663 px）——
     残差小只是因为**整屏都是绿色面板底**，
     但两侧**根本不是同一种屏**（原版=战后菜单，重制=战前简报）⇒ 按类别判 content；
   * **2 行**是 walk 的 step-12-A（9,907）与 step-20-A（4,014）——
     残差虽小但**画面内容不同**（见 §4.3 的并排图）⇒ 手判 content。
   walk 的 12 行 `rendering-difference` 与 5 行 `missing-in-remake`
   是**逐帧看过并排图手判的**，不是靠阈值自动判的。
5. **我第一遍把帧数数成 543**（漏了 `-driver` 目录的 75 张嵌套帧）。
   修法是让工具递归 + 用 PowerShell 独立复核（§1）。已记在台账 B1/B2。

---

## 附：临时产物清单（`build/s49-victory/`）

| 文件 | 内容 |
|---|---|
| `compare.json` | **主产物**：643 行逐帧对照 + `answers` 块 + 摘要 |
| `compare.md` | 同上的人类可读对照表（651 行） |
| `sheet-orig-walk-25.png` | 原版 25 帧 walk 接触印相 |
| `sheet-remake-35.png` | 重制 35 帧接触印相 |
| `remake-slice-04-16.png` / `remake-slice-17-34.png` | 重制分段印相（带可读书签） |
| `sheet-settle-screens.png` | 原版 4 个结算场景 8 张 |
| `sheet-p-screens.png` | 原版战后流程 p01–p10 全部 40 张 |
| `settlement-vs-best-remake.png` | **48 张结算/战后帧 vs 各自最佳重制帧**并排 |
| `walk-greyzone-pairs.png` | 灰区 9 组配对并排（人工判定依据） |
| `s41-result-layers.png` | 原版结算帧 vs 重制三层美术 |
| `s41-result-composite-vs-original.png` | `scenario_41_result_*` 合成 vs 原版（532 px 差） |
| `s41-runtime-result-vs-original.png` | 运行时那套 vs 原版（99.4%，错配演示） |
| `orig-19-24.png` / `orig-22-24.png` / `remake-17-20.png` | 判定用局部印相 |
