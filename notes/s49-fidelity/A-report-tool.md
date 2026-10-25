# A — 判定台（fidelity report）

**stream**：A（判定台）
**日期**：2026-10-23
**目标**（`docs/s49-three-day-plan.md` D1 0–2 h）：把「重录原版 25 帧 + 重录重制 35 帧 + 交叉对齐 + 战场区残差 + 残差归因」固化成**一条命令**的可复跑收据。

---

## 1. 做了什么

### 1.1 交付的工具

`tools/s49_fidelity_report.py`（36 KB，LF，无 BOM）。一条命令出 JSON + Markdown 两份收据：

```
python tools/s49_fidelity_report.py --out build/s49-report/report.json
```

一条命令内部依次完成：

1. **重录原版 25 帧**（从 savestate 起步）——
   脚本 `…/tools/butano/mgba_original_s49_ui_boundaries.lua`，
   env `MGBA_ORIGINAL_S49_*`：`INPUT_STATE` / `INPUT_STATE_SHA256` / `OUTPUT_DIR` /
   `DONE_MARKER` / `KEY_SEQUENCE="A"×24` / `ZERO_INPUT_FRAMES=90` / `SETTLE_FRAMES=90` /
   `HOLD_FRAMES=4`。
2. **重制 35 帧**（从上电起步）——
   脚本 `…/tools/butano/mgba_boot_input_sequence.lua`，
   env `MGBA_BOOT_SEQUENCE_*`：`OUTPUT_DIR` / `DONE_MARKER` / `ROM_SHA256` /
   `KEY_SEQUENCE="Down,Down,A"×32` / `ZERO_INPUT_FRAMES=240` / `SETTLE_FRAMES=90` /
   `HOLD_FRAMES=4`。
   两侧都通过 `tools/mgba_probe/probe_client.py` 调 `build/mgba-probe/mgba-probe.exe`。
3. **交叉对齐** —— 像素语义与 `tools/compare_frame_dirs.py` 完全一致
   （任一通道不同即算 1 px 差），匹配语义与 `tools/align_frame_dirs.py` 一致
   （在完整距离矩阵上取 arg-min），最佳匹配按战场区 `(0,0,240,128)` 选。
4. **残差归因分类** —— 见 §1.3。
5. **出收据** —— JSON（含 `content_sha256`）+ Markdown 逐帧表。

### 1.2 CLI

| 参数 | 默认 | 说明 |
|---|---|---|
| `--out` | `build/s49-report/report.json` | JSON 报告路径（相对路径按仓库根解析，与 cwd 无关） |
| `--work-dir` | `<--out 所在目录>` | 重录产物目录（`capture-original/`、`capture-remake/`） |
| `--markdown` | `<--out>.md` | Markdown 收据路径 |
| `--butano-root` | 自动探测 | 重制线根目录 |
| `--bios` | 关（HLE） | 显式切到真 BIOS；见 §4.2 |
| `--field-area` | `0 0 240 128` | 战场区；非默认值时报告里会给出「阈值是在 240×128 上标定的」告警 |
| `--skip-capture` | 关 | 复用 `--work-dir` 里已有的重录，只重算报告 |
| `--compare PATH` | — | 与另一份报告比对；**退出码 0 = 测量结果一致** |

### 1.3 残差归因（本 stream 的核心价值）

**不做「只给一个数」**。每一帧给三个内容信号 + 投票 + 裕度 + 置信度 + 判据文字：

| 信号 | 定义 | 阈值 |
|---|---|---|
| `structure_match` | 战场区切成 16×16 块，块**均色**逐通道差 ≤8 的块占比 | ≥0.70 判「同」 |
| `diff_block_occupancy` | 含 ≥1 个差异像素的 16×16 块占比 | ≤0.40 判「同」 |
| `diff_row_spread` | 含 ≥1 个差异像素的行占比 | ≤0.85 判「同」 |

三个信号各给一个**带符号裕度**（正 = 判「同」，负 = 判「不同」）；
**≥2/3 判同 ⇒ 同一游戏时刻**。

* 战场区残差 = 0 ⇒ **`一致`**（产品差 = 0 px）
* 同一游戏时刻 且残差 > 0 ⇒ **`产品差`** ⇒ **要改产品代码**
* 不同游戏时刻 ⇒ **`配对差`** ⇒ **不要改代码**，是对齐问题

置信度：`high` = 3/3 一致且支撑裕度 ≥0.20；`medium` = 3/3 但裕度偏小，或 2:1 且异议裕度 ≥0.10；
`low` = 其余（提示人工复核）。

报告里每一帧都带 `criteria` 文字判据 + `signal_detail`（三信号原值/阈值/裕度），
**任何人都能自己复算，不必信本工具的自述**。

### 1.4 可复现性设计

* JSON 顶层有 `content_sha256` = `sha256(canonical_json({config, captures, frames, summary}))`，
  **不含** `generated_at`，也**不含** `run`（运行出处：这次是真重录还是复用）。
  ⇒ 下游 stream 盯这一个数就知道「像素有没有变」。
* `run` 段单独放 `attempts`（烧了几次帧预算、退出码）与 `reused` 标志。
* 两侧重录的每一张 PNG 的 **SHA-256** 都进报告 ⇒ 证据身份钉死。
* 所有写盘文件 UTF-8 无 BOM + LF（仓库用 SHA-256 当证据身份，换行符一改全部钉死失效）。

---

## 2. 改了哪些文件

| 路径 | 性质 | 说明 |
|---|---|---|
| `tools/s49_fidelity_report.py` | **新增** | 判定台本体（36 285 B，831 LF，0 CRLF，无 BOM） |
| `notes/s49-fidelity/A-report-tool.md` | **新增** | 本文件 |
| `build/s49-report/` | 临时产物 | 重录帧、报告、标定脚本、独立验收脚本 |

**没有动**重制线、逆向线，也没有动 master 仓的任何其他文件。
`git status --short` 实测只新增 `tools/s49_fidelity_report.py` 与 `notes/s49-fidelity/`。

`build/s49-report/` 里的可复跑脚本：

| 脚本 | 用途 |
|---|---|
| `_verify.py` | **独立验收脚本**（不依赖工具自己的 `--compare`，自己重算字节一致性） |
| `_probe_align.py` | 标定用：交叉对齐残差表（与 BRIEF §2 对表） |
| `_probe_signals.py` | 标定用：逐帧候选信号表 |
| `_probe_tol.py` | 标定用：块均色容差扫描（阈值是不是刀尖） |
| `exp-orig-bios/` `exp-remake-bios/` `exp-orig-hle/` `exp-remake-hle/` | 真 BIOS vs HLE 的对照重录（§4.2 的证据） |

---

## 3. 跑了什么验收

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| A1 | `python tools/s49_fidelity_report.py --out build/s49-report/report.json` | 退出码 0 | 退出码 0 |
| A2 | `python tools/s49_fidelity_report.py --out build/s49-report/report2.json --compare build/s49-report/report.json` | 两次连跑逐字节一致（除时间戳） | `REPRODUCIBLE: byte-identical`，`content_sha256` 同为 `a5cdf0d8957e5d5946ab0e7ee733e01e16f0cae47530137b51deb4b630b8e2eb`；退出码 0 |
| A3 | `python build/s49-report/_verify.py` | 独立复核 23 项全绿 | 23/23 PASS，退出码 0 |
| A4 | `python build/s49-report/_probe_tol.py build/s49-original-walk build/s49-remake` | 阈值不是刀尖 | tol=4..12 全部 0 分类错误，最大 gap 0.183（tol=6） |
| A5 | `_verify.py` 内含：本次重录 vs 基线录像 `build/s49-original-walk` / `build/s49-remake` 逐 PNG SHA-256 | 参数与 BRIEF §1.2 完全一致 | 原版 **25/25**、重制 **35/35** 逐字节相同 |
| A6 | `python tools/s49_fidelity_report.py --out … --skip-capture --compare …` | 复用重录时测量结果仍一致 | `measurement: IDENTICAL`，仅 `run` 段不同，退出码 0 |
| A7 | 从 `D:\` 目录跑相对 `--out` | 与 cwd 无关 | 退出码 0 |
| A8 | 文件编码检查 | 新写文件 LF 无 BOM | `tools/s49_fidelity_report.py`、`report.json`、`report.md` 均 0 CRLF、无 BOM |

A3 的 23 项里，与 BRIEF §2 直接对表的有：
`step-14-A` / `step-15-A` / `step-17-A` = **0 px**（恰好 3 帧）、
`step-13-A` = **28 px**、`step-16-A` = **344 px**、`step-08-A` = **1026 px**、
最小 0 / 中位 1940 / 最大 27325。

---

## 4. 观察到什么

### 4.1 本轮基线（重录后，战场区 240×128）

归因：**一致 3 / 产品差 14 / 配对差 8**；置信度：high 15 / medium 8 / low 2。

| 原版帧 | 最佳重制帧 | 战场区 px | 整屏 px | 归因 | 置信 |
|---|---|---:|---:|---|---|
| step-00-base | step-04-A | 2565 | 10245 | 产品差 | medium |
| step-01-A | step-05-A | 1294 | 8974 | 产品差 | high |
| step-02-A | step-06-A | 1680 | 9360 | 产品差 | **low** |
| step-03-A | step-07-A | 2514 | 10194 | 产品差 | medium |
| step-04-A | step-08-A | 1940 | 9620 | 产品差 | medium |
| step-05-A | step-09-A | 2057 | 9737 | 产品差 | medium |
| step-06-A | step-10-A | 1217 | 8897 | 产品差 | high |
| step-07-A | step-11-A | 1921 | 9601 | 产品差 | medium |
| step-08-A | step-12-A | 1026 | 8706 | 产品差 | high |
| step-09-A | step-12-A | 6064 | 13744 | **配对差** | medium |
| step-10-A | step-12-A | 4990 | 12670 | **配对差** | medium |
| step-11-A | step-16-A | 25447 | 32784 | **配对差** | high |
| step-12-A | step-16-A | 9907 | 10600 | **配对差** | **low** |
| step-13-A | step-14-A | 28 | 100 | 产品差 | high |
| step-14-A | step-14-A | **0** | 0 | **一致** | high |
| step-15-A | step-15-A | **0** | 0 | **一致** | high |
| step-16-A | step-16-A | 344 | 814 | 产品差 | high |
| step-17-A | step-16-A | **0** | 0 | **一致** | high |
| step-18-A | step-16-A | 25459 | 32796 | **配对差** | medium |
| step-19-A | step-17-A | 24461 | 24461 | **配对差** | high |
| step-20-A | step-17-A | 4014 | 4014 | 产品差 | high |
| step-21-A | step-11-A | 27325 | 35005 | **配对差** | high |
| step-22-A | step-07-A | 21266 | 26531 | **配对差** | high |
| step-23-A | step-18-A | 1323 | 1323 | 产品差 | high |
| step-24-A | step-19-A | 1123 | 1123 | 产品差 | high |

**与 BRIEF §2 完全对得上**（3 帧 0 px、28 px、344 px、1026 px、21k–27k），
说明重录参数与 BRIEF §1.2 逐字一致。

### 4.2 新发现 ①：基线录像用的是 **HLE BIOS**，不是真 BIOS

BRIEF §1.2 把真 BIOS 列为可用能力，但**没有**说基线录像用了它。实测（`exp-*` 目录）：

| 重录方式 | 原版 vs 基线 `s49-original-walk` | 重制 vs 基线 `s49-remake` |
|---|---|---|
| 不带 `--bios`（HLE） | **25/25 逐字节相同** | **35/35 逐字节相同** |
| 带 `--bios`（真 BIOS） | 21/25 相同（`step-21..24` 不同） | **0/35 相同** |

⇒ 基线录像 **没带** `--bios`。

更关键：**带真 BIOS 时重制侧的上电流程进不了战斗**。`exp-remake-bios/step-10-A.png`
画面停在「队伍・装备 / DEPLOY」菜单而不是战斗，交叉对齐最小残差 **25998 px**，
**一帧 0 px 都没有**。

⇒ **判定台默认用 HLE**，真 BIOS 只作为 `--bios` 显式开关留档。
⇒ 若项目以后决定为保真度切真 BIOS，**原版基线要重新钉，且重制的上电策略要重做**。

### 4.3 新发现 ②：BRIEF §2 没分类的 4–6k px 段是**配对差**，不是产品差

`step-09/10`（6064 / 4990 px）目视核对：原版是战斗地图上的「開始」覆盖层 + 完整状态栏
（体力/忍力条），重制侧还停在战前 DEPLOY 菜单（带光标框、底部 `ENEMY / AOK BACK`）。
**同一张地图，不同的游戏时刻** ⇒ 配对差，**不许改代码**。

`step-12`（9907 px）同理：原版此时**还没出人物头像**（空消息框），重制 `step-16` 已经出头像 ⇒ 不同时刻。

⇒ BRIEF §2「1,000–2,500 px ＝ 产品差」这条带区间的经验值要补一句：
**残差落在 4–10k 也完全可能是配对差**，必须靠内容判定，不能按数值大小猜。

### 4.4 新发现 ③：`D:\Github\gba-naruto` 是 junction，`Path.resolve()` 会改写路径

`Path(__file__).resolve()` 把脚本路径变成 `D:\Shell\Github\gba-naruto\...`，
报告里所有路径都会跟着变。工具改用 `os.path.abspath`（不解析 junction），
路径按用户实际调用的形式呈现。

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| H1 | BRIEF §2 的基线录像是在**真 BIOS** 下录的 | 用 `--bios` 重录两侧，与 `build/s49-original-walk`、`build/s49-remake` 逐 PNG 比 SHA-256 | 带 `--bios`：原版 21/25、重制 0/35 相同；不带：原版 25/25、重制 35/35 全同 ⇒ 基线是 **HLE** | **已证伪** |
| H2 | 真 BIOS 会让重制侧的上电流程进不了战斗 | 真 BIOS 重录重制，目视 `step-10-A.png` + 交叉对齐 | 落在「队伍・装备 / DEPLOY」菜单，最小残差 25998 px，0 帧 0 px | **已确认** |
| H3 | 按 BRIEF §1.2 参数重录能复现 BRIEF §2 的残差表 | 跑工具，逐帧对表 | 3 帧 0 px / 28 / 344 / 1026 / 最大 27325，全部吻合 | **已确认** |
| H4 | 「同一游戏时刻 vs 不同游戏时刻」可由画面内容判定 | 三内容信号投票 | 25 帧里只有 3/3 或 0/3，**无 1-2 摇摆帧** | **已确认** |
| H5 | 结构阈值 0.70 不是刀尖 | 容差扫描 tol=0..48 | tol 4..12 全部 0 分类错误，gap 0.125–0.183 | **已确认** |
| H6 | 两次连跑的报告逐字节一致 | 连跑两次 + `_verify.py` 独立去时间戳比对 | 45570 B 完全相同，`content_sha256` 相同，只有 `generated_at` 不同 | **已确认** |
| H7 | 4–6k px 段是产品差（按残差大小猜） | 目视核对 `step-09/10/12` 的两侧画面 | 是「開始」覆盖层 vs DEPLOY 菜单、空消息框 vs 有头像 ⇒ 不同游戏时刻 | **已证伪** |
| H8 | `step-02`（产品差, low）与 `step-12`（配对差, low）的归因正确 | 看三信号裕度 | `step-02` 差异行占比 0.812 逼近阈值 0.85；`step-12` 结构 0.467 明显偏低但行占比 0.805 判同 ⇒ 两帧都是**最接近阈值**的帧，建议人工过一眼 | **未验**（待人工） |
| H9 | 换成真 BIOS 后原版 `step-21..24` 的差异是渲染差 | 比对 `exp-orig-bios` 与基线的 4 帧 | 未细查（4 帧落在配对差带内，且真 BIOS 下重制侧根本进不了战斗，单独比较无意义） | **未验** |

---

## 6. 剩下什么

1. **`docs/sequel-roadmap.md` 未同步。** 项目记忆规则第 6 条要求「roadmap 进展变化时同一轮更新
   `docs/sequel-roadmap.md`」，但本 stream 的文件所有权只允许写
   `tools/s49_fidelity_report.py`、`notes/s49-fidelity/A-report-tool.md`、`build/s49-report/`
   三个位置 ⇒ **留给 parent 决定**是否补写 D1「固化判定台」已完成的条目。
2. **`step-09/10/11/12` 这 4 帧要变成产品差，需要重制侧补录 DEPLOY→战斗的过渡帧**
   （现在的 `Down,Down,A×32` 序列在 DEPLOY 菜单就跳过去了）。这是产品代码 stream 的活。
3. **阈值是按当前 25×35 基线标定的。** 重制侧一改代码，帧集合变了，gap 可能移动。
   工具把三信号原值/阈值/裕度全部写进报告，**归因判据是可复核的**，但若出现摇摆帧（1-2 票）
   需要重新标定。
4. **低置信度 2 帧**（`step-02`、`step-12`）建议人工过一眼（见 H8）。
5. 工具目前**不产出逐帧 diff 图**。覆盖层 2304 px 那摊（BRIEF §2）在逐帧归零时会需要
   「差异像素落在哪」的可视化；加一个 `--diff-images` 输出 diff PNG 是低成本的后续增强。
6. **音频不在范围内**（BRIEF §4 的豁免项 A 级）。

---

## 7. 卡在哪

* **本 stream 的交付物没有阻塞。**
* **真正的堵点在跨 stream**：§6.2 —— 配对差要归零，必须是重制侧能录到原版所处的那几个时刻
  （DEPLOY 菜单、「開始」覆盖层、结算屏）。判定台只能**判定**，不能**制造**对侧画面。
* **一个需要 parent 拍板的口径问题**（§4.2）：判定台按「与 BRIEF §2 的数字可比」定在 **HLE BIOS**。
  若项目改主意要切真 BIOS（保真度上更接近真机），则
  (a) 原版 25 帧基线要重钉，
  (b) 重制的上电按键序列要重做（`Down,Down,A×32` 在真 BIOS 下到不了战斗），
  (c) BRIEF §2 与 `docs/s49-three-day-plan.md` §1.3 的所有残差数字要重算。
  在拍板前，**所有 stream 继续用 HLE**，否则数字不可比。
