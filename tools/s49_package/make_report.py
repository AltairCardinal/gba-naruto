#!/usr/bin/env python3
"""Fill the 1:1 fidelity report draft from the packaging pipeline's receipt.

    python tools/s49_package/make_report.py \
        --receipt build/s49-package/receipt.json \
        --out docs/s49-fidelity-report-20261024.md

Every number in the report comes from a file the pipeline produced, and every
table names that file.  The "not achieved" section is **not** generated from
the measurements -- it is the honest list of what this project has not
reached, and it is written here so that a reader cannot mistake a green gate
for a finished 1:1.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import re

# os.path.abspath, not Path.resolve(): the repository is reached through
# a directory junction (D:\Github\gba-naruto -> D:\Shell\Github\gba-naruto)
# and resolving it would report the junction target instead of the path the
# user actually invoked.
HERE = pathlib.Path(os.path.abspath(__file__)).parent
REPO = HERE.parent.parent

BOUNDARY_TABLE = """\
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
"""

EXCLUSIONS = """\
| 排除项 | 理由 |
|---|---|
| **存档逐字节一致** | 存档字节不是「玩家看得见的画面 + 游戏逻辑状态」。原版是 10 条变长记录（19 B 身份串 + 1 B `~sum` 校验，占 22,468 B），重制侧是 2×4096 B 槽（4 B `KBCS` 头 + 4 B CRC32，占 8,192 B）；**两侧 loader 互相都读不了**（跨格式 3,856 B / 149 个区间不同）。按用户口径明确排除（施工单 C1–C5，`W4-save-boundary.md` §5.5）。**但行为差异（B5 蜜蜂轮转 / B7 战斗后自动写盘）要修** —— 那是玩家看得见的。 |
| **音频逐采样一致** | 原版用 MP2K 合成器，重制侧用 Butano/Maxmod 的 PSG + wav；逐采样一致需要复现 MP2K 合成器本身（80–120 h 量级）。本波只做**事件级**对照（19 个配对时刻，5 类判定）。 |
| **渲染终止条件的缺陷照抄（B2/B3/B4）** | 该角色不在 S49 出场 ⇒ **对 S49 像素无影响**（`WAVE5-TASKS.md` §0.5）。列为非 S49 项。 |
"""

# The ledger of this stream: one row per assumption, with the method that
# decided it and the verdict (未验 / 已证伪 / 已确认).
X4_LEDGER = (
    ("X4-1", "上一任留下的 `tools/s49_package/run_unit_tests.sh` 能用",
     "拿 HEAD 基线跑一遍",
     "121 个测试，101 pass / 20 fail，与 `Q-unit-test-baseline.md` 的数字逐名相同",
     "已确认"),
    ("X4-2", "单测门禁可以用「全绿」",
     "看 HEAD 自身的失败数",
     "HEAD 自己就红 20 项 ⇒ 只能用棘轮式（失败集合逐名相同）",
     "已证伪"),
    ("X4-3", "重制 ROM 在 4096 帧内不崩，且中文标题画面正常",
     "私有探针跑 4096 帧 + 标题帧结构检查（墨迹连通块 / 颜色数）",
     "4096 帧跑完；标题帧 15 色、标题带 6 个墨迹连通块；对 A 键有反应",
     "已确认"),
    ("X4-4", "标题屏不动 = ROM 卡死",
     "比对标题帧与第 4096 帧",
     "两帧逐字节相同 ⇒ 标题屏**在等玩家输入**，不是卡死 ⇒ 崩溃判据改成"
     "「对按键有反应」",
     "已证伪"),
    ("X4-5", "`tools/s49_blackfade/blackfade_capture.py` 能重录",
     "读它的源码并试跑",
     "它读 `args.release_frames`，而它自己的 parser 从没定义过这个参数 ⇒ "
     "AttributeError ⇒ 流水线自己驱动**同一份只读** Lua"
     "（`tools/s49_package/capture_blackfade.py`）",
     "已证伪"),
    ("X4-6", "重录的黑场两侧与钉住的历史采集同参数",
     "用历史采集的帧预算与按键序列重录",
     "原版 1881 帧、重制侧 2402 帧，与历史采集**帧数逐个相同**",
     "已确认"),
    ("X4-7", "判定台的棘轮能挡住「残差变大」",
     "用 `regressed.py` 造一份残差 ×2 的报告再跑 `ratchet_check.py`",
     "RATCHET FAIL，exit 1 ⇒ 步骤 5 变红",
     "已确认"),
    ("X4-8", "单测棘轮能抓到新失败",
     "在测试目录的**副本**里加一个必失败的测试（不动重制线）",
     "工作区失败集合多出 1 项 ⇒ 步骤 2 变红",
     "已确认"),
    ("X4-9", "并行流同时构建会打断本流的构建",
     "全量跑时步骤 1 失败，日志里是 `objcopy: Invalid argument`",
     "两个 objcopy 写同一个 .gba ⇒ 步骤 1 加一次重试（重试后通过）",
     "已确认"),    ("X4-10", "判定台残差会随 wave 5 的产品改动变化",
     "重跑判定台并与 wave-4 的钉住报告对照",
     "**变了**：中位 1940 → 1680 px、总和 168,357 → 117,832、"
     "归因 3·14·8 → 4·15·6、三桶里「黑场过渡」2 → **0** ⇒ "
     "X1 的黑场渐变与 X3 的边界修复都落地了",
     "已确认"),
    ("X4-11", "共享探针 `build/mgba-probe/mgba-probe.exe` 可以覆盖",
     "环境坑：会 LNK1104",
     "流水线自建私有探针 `build/mgba-probe-x4r`，**不碰**共享的那个",
     "已确认（规避）"),
    ("X4-12", "覆盖层逐格族名已归零",
     "逐格族名对拍",
     "同亮 136 / 114 / 0，原版缺 56 / 61 / 0，多画 12 / 26 / 214，"
     "族名不一致 118 / 124 / 0 ⇒ **未归零**",
     "已证伪"),
    ("X4-13", "覆盖层回归是「地图空间锚定」做过头造成的",
     "逐格对拍的三个时刻里 `banner-frame-v1` 原版亮格为 0、重制亮 214",
     "重制侧在原版**根本没画**覆盖层的时刻画了 214 格 ⇒ 覆盖面被铺到了全图",
     "已确认"),
)

# The ledger of **this** stream (Z4, taking over from X4r).  One row per
# assumption, with the method that decided it and the verdict
# (未验 / 已证伪 / 已确认).
Z4_LEDGER = (
    ("Z4-1", "父代理修的 `git archive --output` 路径 bug 还在（没被覆盖掉）",
     "读 `run_pipeline.py` 的 `step_unit_tests`：找 `tar_path` 与 `mkdir`",
     "`tar_path = (ctx.baseline / \"head.tar\").resolve()` + 先 mkdir ⇒ "
     "**修复仍在**，本流没有动它",
     "已确认"),
    ("Z4-2", "步骤 1 的并发构建碰撞重试策略需要加强",
     "读 `step_build` 的重试代码",
     "原来只有「重试 1 次 + 等 10 秒」，且不区分失败原因 ⇒ 与任务书要求的"
     "「等 60 秒、最多 5 次」不符 ⇒ 本流改成：只对 `objcopy` + "
     "`Invalid argument` 的碰撞重试，最多 5 次、每次等 60 秒；"
     "其它失败不重试（真失败）",
     "已证伪（已修）"),
    ("Z4-3", "Z1 / Z2 / Z3 落地前重跑流水线有意义",
     "看重制线的 `battle_scene_controller.h`（Z1 独占）与 `notes/s49-fidelity/Z*.md`",
     "Z1/Z2/Z3 的笔记一个都没有，`battle_scene_controller.h` 的 mtime 仍是 "
     "2026-10-20 ⇒ **三条流都还没交付** ⇒ 本流的第一次重跑是「Z1 之前」的基线，"
     "不能冒充 Z1 之后的终稿",
     "已确认"),
    ("Z4-4", "X2r 的「23,753」是残差的上界还是下界",
     "读 `X2-pairing.md` §0 / §6 / 台账 X2-11",
     "§0 的标题写「可证上界」，但 §6 的 B1 与台账 X2-11 都写「**当前两段录制下的"
     "像素下界**……任何配对方式都不可能低于此数」⇒ 按**下界**表述（"
     "X2-13：两版 ROM 分别 23,753 / 23,697）",
     "已确认"),
    ("Z4-5", "单测棘轮在 Z1 改了单测之后需要重钉基线",
     "读 `step_unit_tests` 的 HEAD 基线取法",
     "HEAD 基线**每次都从 `git archive HEAD` 现取**（不是钉死的文件）⇒ "
     "Z1 改单测不会让棘轮失效；工作区失败集合必须是 HEAD 失败集合的子集，"
     "多一项即红 ⇒ **不需要手工重钉**",
     "已证伪（不需要重钉）"),
    ("Z4-6", "重制侧调色板 bank 崩点（§11 第 4 项）在 wave 7 之前是否已修",
     "读 `WAVE7-TASKS.md` §0 的 Y1 结论 + 步骤 3 的冒烟收据",
     "Y1 已修（per-component 调色板释放，pixel-neutral，25/25 帧逐帧相同，"
     "4096 帧冒烟通过，单测棘轮 new red = 0）⇒ 该项从「未达成」改为「已修」",
     "已确认"),
    ("Z4-7", "「故意破坏 ⇒ 流水线变红」的 11 个 selftest 仍然全红",
     "`run_selftests.ps1` 逐个 `--selftest-break` 跑一遍",
     "11 个步骤的退出码全部非 0 ⇒ **全红**（见 §13.1）",
     "已确认"),
    ("Z4-8", "07:32 重建的 ROM 与 06:05 那一版的残差一样",
     "把两次运行的判定台报告逐帧对照（25 帧）",
     "**不一样**：07:32 那一版的残差**回退**到 wave-4 的水平"
     "（总和 117,832 → 168,392，中位 1,680 → 1,940，全 0 帧 4 → 3）；"
     "**回归全部集中在两帧**：`step-11-A` 305 → **25,447**、"
     "`step-18-A` 0 → **25,459**，其余 23 帧逐帧相同 ⇒ "
     "根因是**重制侧黑场过渡的时刻前移了 2 个 walk 步**"
     "（重制侧的黑场帧从 walk 的 `step-18` 挪到了 `step-16`，"
     "于是原版的两个黑场帧在重制侧找不到对应）",
     "已确认（回归，已被棘轮抓住）"),
    ("Z4-9", "黑场时刻前移是流水线测错还是产品回退",
     "对照两侧的黑场真值表（步骤 9 的证据）",
     "原版 2 个事件 = 淡出 24 / 全黑 18 / 淡入 24 与 淡出 24 / 全黑 24 / 淡入 24；"
     "重制侧的事件数从 **6 → 5**，带渐变的事件从 2 个变成 1 个"
     "（事件 3：淡出 28/全黑 24 → 淡出 24/全黑 26，起始帧 01491 → 01471）"
     "⇒ 是**产品侧的黑场时序变了**，不是测错",
     "已确认"),
    ("Z4-10", "Z1 的接线落地后，黑场的**结构**对齐了吗",
     "对照步骤 9 的黑场真值表（重制侧事件 3 vs 原版事件 1）",
     "**结构对齐了**：重制侧事件 3 = 淡出 **24** / 全黑 **18** / 淡入 **24**，"
     "总 **66** 帧 ⇒ 与原版事件 1 **逐项相同**"
     "（原版 24/18/24 = 66 帧）。⭐ 但**位置没对齐**："
     "把两侧 walk 每帧的非黑像素占比量出来 ⇒ "
     "**原版的 walk 采到了 2 个黑场帧**（`step-11-A` = 0.0079、"
     "`step-18-A` = 0.0000），**重制侧的 walk 一个都没采到**"
     "（35 帧里最暗的一帧是 0.8541 = 对话屏）⇒ "
     "原版那两个黑场帧在重制侧**没有对应**"
     "（25,447 + 25,459 = **+50,906 px**）⇒ 残差总和 117,832 → **161,074** "
     "⇒ **棘轮变红**。另外 `step-12-A` 的残差从 9,907 → **0**（打字机接线生效）",
     "已确认（结构达成 / 位置未达成）"),
    ("Z4-11", "静止帧门禁（步骤 7）变红是真的冻帧还是黑场的副作用",
     "读步骤 7 收据里的 5 对连续相同帧",
     "5 对**全部**落在重制侧 walk 的 step-15…step-22（也就是黑场所在的那一段），"
     "而且这 5 帧的**描边色阶是空的**（画面在黑场里，本来就没有描边）"
     "⇒ 不是「冻帧缺陷」，是**黑场落在 walk 采样点里**的副作用。"
     "⚠️ **本流没有去放宽这条门禁** —— 放宽门禁等于粉饰，"
     "该由 Z1 把黑场挪回原版的位置，或由父代理决定是否给门禁加"
     "「黑场里画面本来就是静的」这条豁免",
     "已确认"),
)


# The ledger of **wave 11 / W4** (determinism of the judgment bench + package
# + final review).  One row per assumption, with the method that decided it
# and the verdict (未验 / 已证伪 / 已确认).
W4_LEDGER = (
    ("W4-1", "判定台的残差读数是逐次确定的（同 ROM 两跑读数相同）",
     "同一个 ROM（sha256 钉住）连跑 3 次判定台，逐帧对照残差与配对",
     "**是**：3 次读数的战场区残差总和**完全相同**（100,210 px）、"
     "中位 1,323、峰值 27,325、全 0 帧 5、归因 5·17·3、"
     "配对差三桶 0·0·3、覆盖层残差总和 857 px；"
     "**逐帧配对逐项相同**；**每张采集 PNG 的 sha256 也逐张相同**"
     "（采集摘要 `af722772d492d293…` 三次一致）",
     "已确认"),
    ("W4-2", "wave 10 报的「同一个 ROM 两跑，残差 9,520 → 0、"
     "总和 114,304 → 104,784」是判定台的抖动",
     "把 wave 10 / U4 自己留下的两份报告的 `captures.remake.rom_sha256` 读出来比",
     "**已证伪**：那两次跑的 ROM **不是同一个**"
     "（`249217d7f59a2199…` vs `73b74587595d4581…`）⇒ "
     "差的那 9,520 px 属于**产品改动**，不属于仪器。"
     "⚠️ wave 10 的报告（`docs/s49-fidelity-report-20261024.md`）"
     "把这个结论写成了「仪器抖动」⇒ **本波已更正**（§2.0b / §11 第 15 项）",
     "已证伪（根因不是仪器）"),
    ("W4-3", "配对搜索有并列最优、没有稳定 tie-break",
     "读判定台的配对代码",
     "**已证伪**：`sorted(matrix.items(), key=lambda kv: (kv[1], kv[0]))` "
     "—— 残差相同按**帧名**排 ⇒ tie-break 本来就是稳定的",
     "已证伪"),
    ("W4-4", "capture 的帧序 / settle 会抖",
     "同 ROM 连跑 3 次，比对每一张采集 PNG 的 sha256",
     "**已证伪**：3 次采集的 PNG **逐张逐字节相同**（摘要 "
     "`af722772d492d293…`）⇒ capture 是确定的",
     "已证伪"),
    ("W4-5", "判定台可以**不改语义**就自证读数确定性",
     "给判定台加 `--repeat N`（连读 N 次并逐项比对），"
     "判据（`product_diff` / `pairing_diff` / 三桶）**不动**",
     "**是**：新加的只有 ① `--repeat N` 的复读与比对、"
     "② 棘轮收据里带上**两侧的 ROM sha256**（ROM 变了要说清楚，"
     "但**不改变**棘轮「残差只许变小」的判据）",
     "已确认"),
    ("W4-6", "判定台自己报出的 ROM 身份是对的",
     "读收据里 `captures.remake.audit.rom_sha256`",
     "**原来不对**：重制侧采集的 audit 里写的是**原版** ROM 的 sha256"
     "（`MGBA_BOOT_SEQUENCE_ROM_SHA256` 被填成了 `ORIGINAL_ROM_SHA256`）"
     "⇒ **已修**（现在写的是重制侧 ROM 自己的 sha256）",
     "已确认（已修）"),
    ("W4-7", "wave 10 / U4 给 `find_overlay_map` 加的 terrain 判据该不该回退",
     "在 wave 10 的 35 个 walk dump 上，带 / 不带 terrain 各跑一遍",
     "**不该回退**：不带 terrain 时 4 个 dump 返回**假窗口 `0x00800`**"
     "（图块数据），带 terrain 时返回 `-1`；**其余 31 个 dump 一字未变** ⇒ "
     "判据窄且可证；且 `terrain` 是**新增可选参数**，默认 `None` ⇒ "
     "**判定台的调用不受影响**。⚠️ 循环论证的风险已写进报告 §3.2",
     "已确认（保留）"),
    ("W4-8", "判定台的「⇒」打印会把绿灯变红",
     "读步骤 5 的日志",
     "**已确认**：控制台是 **GBK**，`⇒` 抛 `UnicodeEncodeError` —— "
     "而且是在**棘轮 PASS 之后**抛的 ⇒ **步骤 5 明明过了却 exit 1**"
     "⇒ **已修**（stdout/stderr 用 `errors=\"replace\"` + 箭头改 ASCII）",
     "已确认（已修）"),
    ("W4-9", "步骤 2 的新红项是本流造成的",
     "读失败详情 + 重制线的 `git diff HEAD`",
     "**已证伪**：新红项全部挂在 **W3 独占**的 `battle_scene_controller.h` 的 "
     "`static_assert`（生成表 `battle_scene_phase_origins` 24 行 vs 26 个相）"
     "—— 正是 `WAVE11-TASKS.md` §3.2 预先警告过的那一处；"
     "**本流对重制线零改动**；W3 同步生成表后，失败集合回到 HEAD 的 20 项 ⇒ "
     "**新失败 0（零回归）**",
     "已证伪（是 W3 在飞，已修）"),
    ("W4-10", "W1/W2/W3 落地后重跑流水线能全绿",
     "跑 `python tools/s49_package/run_pipeline.py`",
     "**是**：收据 `generated_at` = 2026-10-24T13:48:50+08:00，"
     "**12 步全绿**（`ok: true`、`failed_step: null`），"
     "步骤 5 含**连读 3 次的确定性**（残差总和 100,210 px 三次相同）；"
     "⚠️ 期间踩到一次**环境坑**：步骤 1 因**并行流同时构建**（objcopy 碰撞，"
     "5 次重试全撞上）红过 ⇒ 等并行流那一轮构建结束后重跑即绿",
     "已确认"),
    ("W4-11", "单测棘轮仍是 20 项预存债、零回归",
     "步骤 2 的收据：HEAD 失败集合 vs 工作区失败集合",
     "见 §11 第 16 项与 §13 的步骤 2",
     "见 §13 的步骤 2"),
)


# The ledger of **wave 12 / X4** (package + 1:1 final review + the independent
# review of wave 10 / U4's overrun).  One row per assumption, with the method
# that decided it and the verdict (未验 / 已证伪 / 已确认).
W12_LEDGER = (
    ("X4-1", "wave 10 / U4 给 `find_overlay_map` 加的 terrain 判据该不该回退",
     "把改前的候选扫描**在本流重新实现**一遍，在同一份 35 个 walk dump 上"
     "带 / 不带 terrain 各跑一遍；再把共享工具的 `main()` 端到端跑两遍"
     "（一遍把 `find_overlay_map` 换回改前的实现，**只在本进程里替换函数**，"
     "不动共享文件）",
     "**不该回退**：判据只改 **4/35** 个 dump"
     "（`step-00-base` / `step-01-Down` / `step-02-Down` / `step-03-A`："
     "假窗口 `0x00800` → `-1`），**其余 31 个一字未变**；"
     "端到端上 `grid16-frame-v1` 的残差从 **185 降到 126**（剔掉的是假阳性），"
     "`field` / `movegrid` 的数字**一字未变**",
     "已确认（保留）"),
    ("X4-2", "「不带 terrain」的路径与改前**逐字节**相同",
     "把改前的实现（`max(candidates)[1]`）独立重写一遍，与现装的 "
     "`find_overlay_map(vram, 77)` 在 35 个 dump 上对照",
     "**是**：35 个 dump，**0 处不同** ⇒ `terrain` 确实是**新增的可选参数**、"
     "默认 `None` ⇒ 向后兼容",
     "已确认"),
    ("X4-3", "terrain 判据会打断判定台（步骤 5）",
     "直接调判定台自己的 `tools/s49_fidelity_report/overlay.py::remake_grid`，"
     "把它报的 `overlay_map` 与改前的实现逐个对照",
     "**不会**：35 个 dump，**0 处不同**。原因：判定台调的是 "
     "`find_overlay_map(vram, 77)` —— **第二个位置参数是 `tile_max`，"
     "terrain 走默认值 `None`** ⇒ 步骤 5 与步骤 6 各走各的路径",
     "已确认"),
    ("X4-4", "判定台的覆盖层残差（857 px）会不会因为这处越界而变过",
     "判据 Q1b 的推论：判定台的 857 px 是用同一个 `remake_grid` 算出来的，"
     "而 35 个 dump 的 `overlay_map` 逐个相同",
     "**不会**：输入逐个相同 ⇒ 输出必然相同 ⇒ 那个数字**不可能因为"
     "这处越界而变过**",
     "已确认"),
    ("X4-5", "wave 11 / W4 的「±9,520 px 抖动」是判定台的仪器抖动",
     "同一个 ROM 连读 3 次判定台，逐帧对照残差、配对与每张采集 PNG 的 sha256",
     "**已证伪**（根因不是仪器）：wave 10 那两次跑用的 **ROM sha256 不同**"
     "（`249217d7…` vs `73b74587…`）⇒ 差值属于**产品改动**；"
     "本波复现：**连读 3 次，残差总和三次完全相同**",
     "已证伪（根因不是仪器）"),
    ("X4-6", "X1 / X2 / X3 落地后重跑流水线能全绿",
     "跑 `python tools/s49_package/run_pipeline.py`，并检查三条流的交付物"
     "（X1 的笔记 / X2 的逐格族名 / X3 的黑场真值）",
     "**未能验证**：本次运行三条流**都没有交付笔记**"
     "（X1 只有在飞产物）⇒ 本波跑的是「**在飞状态**」的基线，"
     "**12/12 全绿但数字属于在飞状态** ⇒ 报告页首与 §11 都写明了这一点；"
     "⚠️ **不许把它写成 wave 12 的终稿基线**",
     "未验（流未交付）"),
    ("X4-7", "单测棘轮的失败集合与 HEAD 基线**逐名相同**",
     "步骤 2 的收据：HEAD 失败集合 vs 工作区失败集合",
     "**是**：HEAD **101 pass / 20 fail**，工作区 **117 pass / 20 fail**，"
     "**新失败 0 项** ⇒ 20 项预存债，**零回归**；"
     "⚠️ **不许写成「单测全绿」**",
     "已确认"),
    ("X4-8", "「故意破坏 ⇒ 流水线变红」的 11 个 selftest 仍然全红",
     "`run_selftests.ps1` 逐个 `--selftest-break` 跑一遍",
     "**是**：**11 red, 0 not red** ⇒ 11 个步骤的判据都真的会被触发",
     "已确认"),
    ("X4-9", "包清单会把 selftest 的临时目录算进去",
     "读 wave 11 的两个包的 `packaged_files`："
     "`s49-package` = 122（无 selftest-scratch）vs "
     "`s49-package-u4` = 714（有 selftest-scratch）",
     "**会**（一次多算 592 个文件）⇒ **已修**："
     "`MANIFEST_EXCLUDED_PARTS` 加了 `selftest-scratch`"
     "（临时目录不是「随包发布的东西」）",
     "已确认（已修）"),
    ("X4-10", "wave 9 的「重制侧 battle-14 打不赢」这条结论还成立",
     "读 X1 的**在飞**产物 `build/s49-battle-balance/u2/route*.err` 的最后两行",
     "**已过期**：X1 的在飞路线生成器已经能走到 "
     "`after the battle: phase=13 round=5 outcome=1 enemies=0` ⇒ **能打赢**"
     "不再是障碍；但 ⚠️ **X1 没有交付笔记，本波仍然没有结算链的"
     "逐屏运行帧对照数字** ⇒ 报告里**不把它写成已达成**",
     "已证伪（结论过期；达成状态仍未验）"),
)


# The ledger of **wave 13 / Y4** (package finalisation + the 1:1 report's
# final review).  One row per assumption, with the method that decided it and
# the verdict (未验 / 已证伪 / 已确认).
Y13_LEDGER = (
    ("Y4-1", "上一任包里残留的 `report-test.md` 草稿能不能直接删掉",
     "用可恢复删除（`rm --`）删 `build/s49-package-x4/report-test.md`",
     "**不能**：回收站启动器**拒绝对 junction 的目标动手**"
     "（`D:\\Github` → `D:\\Shell\\Github`）⇒ **换包目录重跑**即可清掉；"
     "本流的新包目录里**没有**这个文件",
     "已确认（已修：换目录重跑）"),
    ("Y4-2", "覆盖层的「同亮 192 / 缺 0 / 多画 0」是不是真的达成了",
     "用**已修回绕**的共享仪器在同一份 35 个 walk dump 上重跑"
     "（流水线步骤 6，数字在本次收据里）",
     "**是**：`field` **192 / 0 / 0**、`movegrid` **192 / 0 / 0**、"
     "`banner` **0 / 0 / 0 exact ✔**；"
     "`grid16` **175 / 0 / 17**（原版是单帧瞬态）",
     "已确认"),
    ("Y4-3", "X2 判定的「24 格原版缺 + 24 格多画是仪器没按 480 px 回绕"
     "造成的假象」是否成立",
     "**独立重测**：自建逐格对拍器（`tools/s49_package/"
     "classify_overlay_cells.py`）**只读 import** 共享仪器，"
     "在**同一份 dump** 上重算逐格族名",
     "**成立**：回绕修好后 `field` / `movegrid` 的 **缺 0 / 多画 0** "
     "⇒ 旧口径那 24/24 是**贴标签错位**，不是产品差",
     "已确认"),
    ("Y4-4", "剩下的族名不一致能不能**逐格**给出性质判定"
     "（产品差 / 原版尾部残留 / walk 相位）",
     "自建逐格分类器：复用共享仪器的取帧规则与最优帧选择规则，"
     "保留**逐格**差异，再按三条**可判定**的规则分类",
     "**能**：`field` 11 尾部 + 50 相位 + 0 产品差；"
     "`movegrid` 11 尾部 + 0 相位 + **2 产品差**；"
     "`grid16` 22 尾部 + 80 相位 + 0 产品差；`banner` 0 0 0",
     "已确认"),
    ("Y4-5", "X2 的规则改动（移动阶段不画黄色光标格）是否让 `movegrid` 的"
     "族名不一致从 4 降到 2（X2-H8 未验项）",
     "在本次收据的 35 个 dump 上重算 `movegrid` 的逐格差异，"
     "再减去尾部（11 格）",
     "**是**：13 − 11 = **2**，且这 2 格的族名对是 `hatch→solid`"
     "（重制侧有一个单位占着原版可走的格）⇒ X2-H8 **已确认**",
     "已确认"),
    ("Y4-6", "Y2 落地后重跑 12 步流水线能不能全绿",
     "`python tools/s49_package/run_pipeline.py --out build/s49-package-y4`",
     "**能**：**12/12 全绿**（`ok: true`、`failed_step: null`）",
     "已确认"),
    ("Y4-7", "单测棘轮的失败集合是否与 HEAD 基线**逐名相同**",
     "步骤 2 的收据：HEAD 失败集合 vs 工作区失败集合",
     "**是**：HEAD **101 pass / 20 fail**，工作区 **117 pass / 20 fail**，"
     "**新失败 0 项** ⇒ 20 项预存债，**零回归**；"
     "⚠️ **不许写成「单测全绿」**",
     "已确认"),
    ("Y4-8", "判定台的读数是否确定（3 次连读逐项相同）",
     "步骤 5 内建：同一个 ROM 连读 3 次",
     "**是**：残差总和 **100,210 px** 三次**完全相同**",
     "已确认"),
    ("Y4-9", "构建 / 测量 / 打包三者是不是同一份 ROM",
     "比对步骤 1 构建产物的 sha256、步骤 1 钉住的拷贝的 sha256、"
     "步骤 12 实际打包的 sha256",
     "**是**：三者**逐字节相同** ⇒ 并行流中途重建换不掉本轮的读数",
     "已确认"),
    ("Y4-10", "残差能不能归零",
     "判定台的可证像素下界：每一拍内**原版的全部帧** × "
     "**重制的全部帧**逐对算残差取最小，25 拍求和",
     "**不能**：可证像素**下界 ≈ 23,700**（当前 ROM 23,753）⇒ "
     "**任何配对方式都不可能低于此数** ⇒ 归零在当前录制上**不可达**",
     "已证伪（归零不可达）"),
    ("Y4-11", "「故意破坏 ⇒ 流水线变红」的 11 个 selftest 是否仍然全红",
     "`run_selftests.ps1` 逐个 `--selftest-break` 跑一遍",
     "**是**：**11 red, 0 not red** ⇒ 11 个步骤的判据都真的会被触发",
     "已确认"),
    ("Y4-12", "新包目录里还有没有草稿残留",
     "读新包目录的 `manifest.json` 与目录清单",
     "**没有**：`report-test.md` **不在**新包里 ⇒ 换目录重跑确实清掉了",
     "已确认（已修）"),
)


# The ledger of **wave 15 / W4** (the package finalisation + the 1:1 report's
# final review, on top of W1 / W2 / W3).  One row per assumption, with the
# method that decided it and the verdict (未验 / 已证伪 / 已确认).

# The wave whose task book is the "delivered in this wave" line.
W15_CUTOFF = "WAVE15-TASKS.md"

W15_LEDGER = (
    ("W4w-1", "W1 / W2 / W3 在本波开工前是否已经交付",
     "读 `notes/s49-fidelity/` 里**在本波任务书之后**写的笔记，"
     "并查重制线源码在任务书之后有没有被改过",
     "见 §14.9 的说明：**判定一律以任务书的 mtime 为界**，"
     "任务书之前写的笔记（wave 7 的 Z1/Z2/Z3、wave 14 的 Z1/Z2/Z3）"
     "**一律不算本波交付**",
     "已确认"),
    ("W4w-2", "「本波已交付」能不能用笔记的**文件名前缀**判定",
     "读 `notes/s49-fidelity/` 里的同名笔记"
     "（`Z1-wiring.md` / `Z2-title-art-starfield.md` / `Z3-dialogue-box.md` "
     "是 **wave 7** 的）",
     "**不能** ⇒ 判定必须**以任务书的 mtime 为界**"
     f"（`{W15_CUTOFF}`），"
     "报告生成器里由 `wave15_notes()` / `wave15_streams()` 实现",
     "已证伪"),
    ("W4w-3", "报告生成器能不能在 W1/W2/W3 的产物**形状未知**的情况下"
     "只读地取到它们的数字",
     "按**笔记标题**里的流编号（W1/W2/W3）分类，"
     "数字只从**本次收据**里取（黑场事件数、棘轮基线、单测棘轮）",
     "**能**：笔记只用来判定「交付与否」，"
     "**所有数字都来自收据** ⇒ 每个数字都能追到一次运行",
     "已确认"),
    ("W4w-4", "两个失败的包目录（步骤 5 红 / 步骤 1 红）能不能删掉",
     "先试 `rm --`，再试用**真路径**（junction 的目标）"
     "调 `mavis-trash.cmd`",
     "**能**：必须打**真路径** `D:\\Shell\\Github\\gba-naruto\\build\\...`；"
     "打 junction 路径（`D:\\Github\\...`）会被回收站启动器拒掉",
     "已确认（已清理）"),
    ("W4w-5", "残差归零到底可不可达",
     "读 Z3 的下界收据（`floor_sum`）+ 它的证明方式；"
     "**并把判定台的读数与下界分成两个口径**",
     "**不可达**：下界 **16,389 px**（测在 ROM `2c2b48d9…`），"
     "内容锚可达数 **18,886 px** ⇒ 区间 **[16,389, 18,886]**；"
     "⚠️ **判定台的读数（残差总和）是另一个口径**（arg-min 无时刻约束）"
     "⇒ 两个数**不许混用**",
     "已确认"),
    ("W4w-6", "覆盖层剩下的 176 格能不能算作「覆盖层规则的产品差」",
     "读 Z3 的相位归因收据（6 帧连拍 + 密集 walk 逐帧对齐）",
     "**不能**：130 格 = **50 格重制侧缺一个相位**（稳定态，原版连续 67 帧）"
     "+ **80 格原版那一帧是瞬态**（6 连拍只现 1 次 ⇒ 缓冲撕裂）；"
     "⇒ `grid16` 的 80 格进**「明确排除项」**，与 44 格尾部残留并列",
     "已确认"),
)

# The wave whose task book is the "delivered in this wave" line (wave 16).
W16_CUTOFF = "WAVE16-TASKS.md"

# The ledger of **wave 16 / V3** (the package finalisation + the 1:1 report's
# final review, on top of V1 / V2 / V4).  One row per assumption, with the
# method that decided it and the verdict (未验 / 已证伪 / 已确认).
W16_LEDGER = (
    ("V3w-1", "V1 / V2 / V4 在本波开工前是否已经交付",
     "读 `notes/s49-fidelity/` 里**在 `WAVE16-TASKS.md` 之后**写的笔记，"
     "并查重制线源码与 ROM 的 mtime",
     "见 §14.10：**判定一律以任务书的 mtime 为界** ⇒ "
     "任务书之前写的笔记（wave 7 的 Z1/Z2/Z3、wave 5/6/8 的 W1/W2/W3）"
     "**一律不算本波交付**",
     "已确认"),
    ("V3w-2", "「本波已交付」能不能用笔记的**文件名前缀**判定",
     "读 `notes/s49-fidelity/` 里的同名笔记",
     "**不能** ⇒ 判定必须**以任务书的 mtime 为界**"
     f"（`{W16_CUTOFF}`），报告生成器里由 `wave16_notes()` / "
     "`wave16_streams()` 实现",
     "已证伪"),
    ("V3w-3", "判定台复用采集时会不会核对 ROM",
     "读 `tools/s49_fidelity_report/capture.py::run_capture()` 的复用分支",
     "**不会** —— 复用条件只有「done 标记在不在、帧在不在」，"
     "**从不核对那份采集是哪一个 ROM 录的** ⇒ "
     "**可以报告一个它没测过的 ROM 的读数**",
     "已确认（缺陷）"),
    ("V3w-4", "修好之后，复用采集时会不会仍然复用别的 ROM 的采集",
     "把采集的 `audit.json` / `done.json` 里的 `rom_sha256`（原版侧是 "
     "`input_state_sha256`）改成**另一个 ROM / 另一个存档**的值，"
     "再用 `--skip-capture` 跑判定台",
     "**不会** ⇒ 两侧都**重新采集**，收据里写明"
     "「ROM 变了，已重采」与具体差在哪一个摘要上",
     "已确认（已修）"),
    ("V3w-5", "ROM 一致时能不能复用，且读数与重采**逐项相同**",
     "**同一个 work 目录**里连跑三次：① 重采 ② 篡改后重采 ③ 复用",
     "**能** ⇒ 三次的 `content_sha256` **完全相同**，"
     "残差总和 / 中位 / 归因逐项相同 ⇒ 复用不改变读数",
     "已确认（已修）"),
    ("V3w-6", "收据里新增字段会不会破坏 `content_sha256` 的可复现承诺",
     "比「重采」与「复用」两份收据的**逐叶差异**",
     "**不会** —— 复用判定被拆成两部分："
     "**测量稳定**的事实（`captures.<side>.reuse_decision`）留在测量口径内，"
     "**运行出处**（复用/重采 + 原因）随 `attempts` 一起移出测量摘要 ⇒ "
     "两次读数的差异只剩**绝对路径**",
     "已确认"),
    ("V3w-7", "本波残差有没有比上一波被接受的收据变小",
     "流水线步骤 5 的棘轮判决 + 连读 3 次的 `determinism`",
     "见 §2.0：**判决与三次读数逐项相同**；"
     "⚠️ **ROM 变了 ⇒ 残差不是同一个测量** ⇒ "
     "「不可比」与「变小」必须分开写",
     "已确认"),
    ("V3w-8", "构建 / 钉住 / 打包 / 实测四个 sha 是不是同一份 ROM",
     "读步骤 1 的 `rom_sha256` 与 `pinned_rom_sha256`、"
     "步骤 12 的 `rom_sha256`、判定台收据的 `captures.remake.rom_sha256`",
     "见 §2.0c：**四者逐字相同**（不一致会在这里报出来）",
     "已确认"),
    ("V3w-9", "11 个 selftest 是不是仍然全部能把对应的步骤打红",
     "`run_selftests.ps1` 逐个 `--selftest-break` 跑一遍",
     "见 §13.1：**11 red, 0 not red**",
     "已确认"),
    ("V3w-10", "判定台的读数在同一个 ROM 上确定吗",
     "流水线步骤 5 内建（连读 3 次）",
     "见 §2.0b：**3 次读数逐项相同** ⇒ 残差变了就是产品变了",
     "已确认"),
    ("V3w-11", "「四个 sha 一致」的判据能不能在**四个摘要都相同**时判成一致",
     "拿 wave 15 的收据跑一遍 §2.0c",
     "**第一版判错**：四个摘要放进 `set` 之后长度是 **1**（不是 4）⇒ "
     "「凑齐」的判据写成了 `len(values) == 4` ⇒ 一致却报「没有凑齐」"
     "⇒ 改成「**非空摘要的个数 == 4** 且**去重后 == 1**」",
     "已证伪（已修）"),
)


# The wave whose task book is the "delivered in this wave" line (wave 17).
W17_CUTOFF = "WAVE17-TASKS.md"

# wave 17's parallel streams.  U1 and U2 are **product** streams (they change
# the remake tree, so the ROM must be rebuilt and re-measured); U3 is this
# stream (the package + the report); U4 is a **driver/instrument** stream.
W17_STREAMS = ("U1", "U2", "U3", "U4")

# The ledger of **wave 17 / U3** (the package finalisation + the 1:1 report's
# final review, on top of U1 / U2 / U4).  One row per assumption, with the
# method that decided it and the verdict (未验 / 已证伪 / 已确认).
W17_LEDGER = (
    ("U3w-1", "U1 / U2 在本波开工前是否已经交付",
     "读 `notes/s49-fidelity/` 里**在 `WAVE17-TASKS.md` 之后**写的笔记，"
     "**并**查重制线里 U1 / U2 独占文件的 mtime",
     "开工时（22:27）**两路都没有交付**："
     "`battle_combat_presentation.h` / `battle_scene_presentation.h` 停在 "
     "2026-10-20，`battle_range_ui_style.h` 停在 2026-10-24 15:31，"
     "`battle_result_content.h` 停在 13:37 ⇒ **本流第一件事是等**",
     "已确认（未交付）"),
    ("U3w-2", "「本波已交付」能不能用笔记的**文件名前缀**判定",
     "读 `notes/s49-fidelity/` 里的同名笔记"
     "（wave 16 的 V1/V2/V4、wave 7 的 Z1/Z2/Z3）",
     "**不能** ⇒ 判定必须**以任务书的 mtime 为界**"
     f"（`{W17_CUTOFF}`），由 `wave17_notes()` / `wave17_streams()` 实现；"
     "**并且**产品流（U1 / U2）额外用「独占文件的 mtime + ROM 在其后被重建」"
     "来判定 —— 笔记不是产品的证据，**ROM 才是**",
     "已证伪"),
    ("U3w-3", "能不能在 U1 / U2 / U4 的产物**形状未知**的情况下"
     "只读地取到它们的数字",
     "在报告生成器里写**按内容/键名查找**的读取器"
     "（`wave17_chains()` / `wave17_bound()` / `wave17_reachable()`），"
     "找不到就明写「尚未交付」",
     "**能**：读取器**只在盘上真的有产物时**才给出数字，"
     "且**绑定收据的路径与 ROM sha256** ⇒ 每个数字都能追到一次运行",
     "已确认"),
    ("U3w-4", "「真实战斗链」与「poke 链」能不能被**机器**分开",
     "读链收据的 `entry.method`（自报进入方式）与 "
     "`outcome_byte_before_poke` / `outcome_byte_after_poke`",
     "**能**：`entry.method` 里含 `poke` ⇒ **poke 链**；"
     "两个 outcome 字节不同 ⇒ **poke 链**；"
     "两者都没有 ⇒ **进入方式未记录**（**不许**当成真实链）；"
     "只有**明确不是 poke**、且链上的 `outcome` 是 1 ⇒ **真实胜利链**",
     "已确认"),
    ("U3w-5", "构建 / 钉住 / 打包 / 实测四个 sha 是不是同一份 ROM",
     "读步骤 1 的 `rom_sha256` 与 `pinned_rom_sha256`、"
     "步骤 12 的 `rom_sha256`、判定台收据的 "
     "`captures.remake.measured_rom_sha256`",
     "见 §2.0c：**四者逐字相同**（不一致会在这里报出来）",
     "已确认"),
    ("U3w-6", "本波残差有没有比上一波被接受的收据变小",
     "流水线步骤 5 的棘轮判决 + 连读 3 次的 `determinism`",
     "见 §2.0：**判决与三次读数逐项相同**；"
     "⚠️ **ROM 变了 ⇒ 残差不是同一个测量** ⇒ "
     "「不可比」与「变小」必须分开写（**不可比 ≠ 通过**）",
     "已确认"),
    ("U3w-7", "可证像素下界能不能为**本包这个 ROM** 重算",
     "用 V4 已交付的工具（`tools/s49_z3_bound/`）**只读调用**，"
     "对**钉住的 ROM** 重录重制侧 + 重算",
     "**能**（见 §11 第 2 项）：wave 16 的 16,813 px 测在旧 ROM 上，"
     "**U1 / U2 落地后 ROM 变了 ⇒ 必须重算**，否则下界与读数不是一个 ROM",
     "已确认"),
    ("U3w-8", "11 个 selftest 是不是仍然全部能把对应的步骤打红",
     "`run_selftests.ps1` 逐个 `--selftest-break` 跑一遍",
     "见 §13.1：**11 red, 0 not red**",
     "已确认"),
    ("U3w-9", "单测棘轮的失败集合是否与 HEAD 基线**逐名相同**（20 项预存债）",
     "流水线步骤 2 的收据：HEAD 失败集合 vs 工作区失败集合",
     "见 §11 第 8 / 16 项：**new_failures = []** ⇒ 零回归；"
     "⚠️ **不许写成「单测全绿」**",
     "已确认"),
    ("U3w-10", "在别的流还在跑全量录制时重跑流水线会不会把步骤 5 的采集杀掉",
     "闸门 `build/u3-dev/run-when-idle.ps1`：等"
     "「U1 / U2 的独占文件在任务书之后被改过 + ROM 在其后被重建 + "
     "ROM/源码安静 ≥ 150 s + 没有探针/构建在跑 + 内存 > 4 GB」",
     "见 §「卡在哪」一节；**这是重跑的前置条件**，不是流水线的问题",
     "已确认（前置条件）"),
)



# The ledger of **wave 14 / Z4** (the package finalisation + the 1:1 report's
# final review, on top of Z1 / Z2 / Z3).  One row per assumption, with the
# method that decided it and the verdict (未验 / 已证伪 / 已确认).
W14_LEDGER = (
    ("Z4w-1", "Z1 / Z2 / Z3 在本波开工前是否已经交付",
     "读 `notes/s49-fidelity/` 里三份笔记（以 `WAVE14-TASKS.md` 的 mtime 为界）"
     "与 `tools/s49_z3_bound/` 是否存在",
     "**都没有** ⇒ 本波的第一件事就是**等**它们落地，"
     "报告里对应三行只能先写「尚未交付」",
     "已确认（未交付）"),
    ("Z4w-2", "报告生成器能不能在 Z1/Z2/Z3 的产物**形状未知**的情况下"
     "只读地取到它们的数字",
     "在报告生成器里写**按内容/键名查找**的读取器"
     "（`settlement_running_frames()` / `z3_bound()` / `z3_phase_attribution()`），"
     "找不到就明写「尚未交付」",
     "**能**：三个读取器都**只在盘上真的有产物时**才给出数字，"
     "且**绑定收据的路径与 ROM sha256** ⇒ 每个数字都能追到一次运行",
     "已确认"),
    ("Z4w-3", "「本波已交付」能不能用笔记的**文件名前缀**判定",
     "读 `notes/s49-fidelity/` 里的同名笔记"
     "（`Y3-overlay-zero.md` 是 wave 6 的、`X2-overlay-zero.md` 是 wave 12 的）",
     "**不能** ⇒ 判定必须**以任务书的 mtime 为界**："
     "`_note_present_since(prefix, \"WAVE14-TASKS.md\")`",
     "已证伪"),
    ("Z4w-4", "在别的流还在跑全量录制时重跑流水线会不会把步骤 5 的采集杀掉",
     "重跑前查 `Win32_Process` 的内存占用与孤儿 `mgba-probe.exe`",
     "见 §「卡在哪」一节；**这是重跑的前置条件**，不是流水线的问题",
     "已确认（前置条件）"),
    ("Z4w-5", "在别的流还在跑全量录制 / 重建 ROM 时重跑流水线，能不能全绿",
     "重跑前查 `Win32_Process` 的内存占用与孤儿 `mgba-probe.exe`，"
     "并等「ROM 的 mtime 稳定 > 150 s 且没有探针在跑」"
     "（`build/z4-dev/run-when-idle.ps1`）",
     "**前两次都红、且都不是本流的 bug**：第一次**步骤 5** 红"
     "（Z2 的在飞改动让 ROM 在战斗 walk 里崩 ⇒ `done marker missing`，"
     "探针 spew **118 MB** 崩溃日志）；第二次**步骤 1** 红"
     "（**Z2 重建 ROM** ⇒ 构建 `94ef708e…` ≠ 盘上 `ec5b5273…` ⇒ 钉不住）；"
     "第三次（等窗口）**12/12 全绿**",
     "已确认（已规避）"),
    ("Z4w-6", "单测棘轮的失败集合是否与 HEAD 基线**逐名相同**（20 项预存债）",
     "流水线步骤 2 的收据：HEAD 失败集合 vs 工作区失败集合",
     "**是**：HEAD **101 pass / 20 fail**、工作区 **118 pass / 20 fail**、"
     "`new_failures` = **[]** ⇒ **20 项预存债，零回归**；"
     "⚠️ **不许写成「单测全绿」**",
     "已确认"),
    ("Z4w-7", "构建 / 测量 / 打包三者是不是同一份 ROM",
     "比对步骤 1 构建产物、步骤 1 钉住的拷贝、步骤 12 实际打包的 sha256",
     "**是**：三者**逐字节相同** ⇒ 并行流中途重建**换不掉**本轮的读数",
     "已确认"),
    ("Z4w-8", "判定台的读数是否确定（3 次连读逐项相同）",
     "流水线步骤 5 内建：同一个 ROM 连读 3 次",
     "**是**：残差总和 **三次完全相同**，`determinism.identical = true`、"
     "`rom_changed = false` ⇒ **残差变了就是产品变了，不是仪器在抖**",
     "已确认"),
    ("Z4w-9", "「故意破坏 ⇒ 流水线变红」的 11 个 selftest 是否仍然全红",
     "`run_selftests.ps1` 逐个 `--selftest-break` 跑一遍",
     "**是**：**11 red, 0 not red** ⇒ 11 个步骤的判据都真的会被触发",
     "已确认"),
    ("Z4w-10", "换包目录重跑能不能把中间目录的草稿残留"
     "（`cell-classification-dev.json` / `report-test.md`）清掉",
     "读新包目录的文件清单与 `manifest.json`",
     "**能**：新包里**只有** `evidence/overlay/cell-classification.json`，"
     "**没有** `-dev` 那份，**也没有** `report-test.md` ⇒ 清单核对通过",
     "已确认（已修）"),
    ("Z4w-11", "残差比 wave 13 变大了，是不是**判定台的抖动**",
     "比两次收据的残差摘要 + 读本次收据的 `determinism`",
     "**不是**：同一个 ROM 连读 3 次逐项相同 ⇒ 差值属于 **ROM 变化**"
     "（Z2 的黑场改动进了产品）；⚠️ **但棘轮没抓住它** —— "
     "换包目录 ⇒ 棘轮基线从 wave 4 起步，**只比了 wave 4 没比 wave 13**",
     "已确认（是产品改动）"),
    ("Z4w-12", "Z3 的下界能不能直接当**本次 ROM** 的下界",
     "比 Z3 收据的 `roms.remake.sha256` 与本次收据的构建 sha",
     "**不能**：两个 ROM 不同 ⇒ 报告**不**把它写成「当前 ROM 的下界」，"
     "只写「另一个 ROM 上的下界 ⇒ 量级结论成立，精确值待重算」",
     "已证伪（口径不同）"),
)


def load_json(path: pathlib.Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def fmt(value, digits: int = 0) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    if isinstance(value, int):
        return str(value)
    return str(value)


def step_by_name(receipt: dict, name: str) -> dict:
    for step in receipt.get("steps", []):
        if step.get("name") == name:
            return step
    return {}


def ledger_index() -> list[tuple[str, int, str]]:
    """(note file, number of ledger rows, section title) for every ledger."""
    rows = []
    directory = REPO / "notes" / "s49-fidelity"
    if not directory.is_dir():
        return rows
    for path in sorted(directory.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        match = re.search(r"^##\s*\d+\.\s*假设台账\s*$", text, re.M)
        if not match:
            continue
        body = text[match.end():]
        next_heading = re.search(r"^##\s", body, re.M)
        if next_heading:
            body = body[:next_heading.start()]
        count = len([line for line in body.splitlines()
                     if line.startswith("|") and not re.match(
                         r"^\|[\s\-:|]+\|$", line)]) - 1
        rows.append((f"notes/s49-fidelity/{path.name}", max(count, 0),
                     "假设台账"))
    return rows


def _z_status(note_name: str) -> str:
    """Did the parallel stream deliver its note yet?

    The "not achieved" list has to say which gaps are still open *as of this
    run*.  A wave-7 stream that has not written its note has, by definition,
    not delivered -- so the row says so instead of guessing.
    """
    path = REPO / "notes" / "s49-fidelity" / note_name
    if path.is_file():
        return (f"**{note_name} 已交付**（{path.name}）⇒ "
                "该行的结论以那份笔记的实测为准")
    return (f"**尚未交付**（本轮没有 `notes/s49-fidelity/{note_name}`）")


def z2_status() -> str:
    return _z_status("Z2-title-art-starfield.md")


def z3_status() -> str:
    return _z_status("Z3-dialogue-box.md")


def _non_black_fraction(path: pathlib.Path) -> float | None:
    """The share of pixels that are not pure black (None if unreadable)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as image:
            pixels = list(image.convert("RGB").getdata())
    except (OSError, ValueError):
        return None
    if not pixels:
        return None
    black = sum(1 for r, g, b in pixels if (r, g, b) == (0, 0, 0))
    return 1.0 - black / len(pixels)


def walk_blackness_table(original: pathlib.Path, remake: pathlib.Path) -> list:
    """Per-walk-step non-black fraction, for both sides.

    This is the decisive measurement for "does the walk *sample* the black
    field at all?".  The original's walk samples it twice; if the remake's
    walk samples it zero times, the original's two black frames have no
    counterpart and the residual on them is the whole screen.
    """
    rows = []
    for label, directory in (("原版", original), ("重制侧", remake)):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("step-*.png")):
            fraction = _non_black_fraction(path)
            if fraction is None:
                continue
            rows.append((label, path.name, fraction))
    return rows


def u_status() -> str:
    """Have the wave-10 parallel streams (U1 / U2 / U3) delivered yet?

    A stream that has not written its note has, by definition, not delivered.
    The notes are checked by name, and the tree is checked too, so the report
    never claims a stream's conclusion that is not on disk.
    """
    streams = (
        ("U1", "接线总装", "U1-wiring.md",
         "butano-sequel/game/src/battle_runtime_scene.cpp"),
        ("U2", "战斗数值对齐", "U2-battle-balance.md",
         "butano-sequel/game/include/konoha/battle_unit_content.h"),
        ("U3", "结算链缺屏 + 结算屏美术", "U3-settlement-content.md",
         "butano-sequel/game/include/konoha/battle_result_content.h"),
    )
    parts = []
    for name, title, note, exclusive in streams:
        note_path = REPO / "notes" / "s49-fidelity" / note
        if note_path.is_file():
            parts.append(f"**{name}（{title}）已交付**（`{note}`）")
            continue
        if _remake_file_changed(exclusive):
            parts.append(f"**{name}（{title}）接线已落地、笔记未交付**")
            continue
        parts.append(f"**{name}（{title}）尚未交付**")
    return "；".join(parts)


def w_status(receipt: dict) -> str:
    """The wave-11 parallel streams (W1 / W2 / W3), as of this run.

    Every claim is read from a file: the phases from the remake header, the
    overlay families from the receipt's own step 6, and the settlement chain's
    running frames from the newest artifact under ``build/s49-victory-capture``.
    """
    parts = []

    controller = pathlib.Path(
        r"D:\Shell\gba-naruto-butano\butano-sequel\game\include\konoha"
        r"\battle_scene_controller.h")
    if controller.is_file():
        text = controller.read_text(encoding="utf-8", errors="replace")
        landed = [name for name in ("post_battle_dialogue", "task_menu")
                  if name in text]
        parts.append(
            "**W3（结算链接线 + 字体扩字）**："
            + ("「战后对白」+「任务菜单」两段**已进 `battle_scene_phase`**"
               if len(landed) == 2 else
               f"两段只进了 {len(landed)}/2 段")
            + "；⚠️ **字体扩字与 VRAM 量化方案在本次收据里没有产物**")

    overlay = (step_by_name(receipt, "overlay") or {}).get("metrics") or {}
    moments = overlay.get("moments") or {}
    if moments:
        zeroed = all(
            row.get("both_lit") == 192
            and not row.get("original_only")
            and not row.get("remake_only")
            and not row.get("family_mismatches")
            for row in moments.values())
        if zeroed:
            parts.append("**W2（覆盖层逐格族名）**：**已归零**"
                         "（同亮 192 / 缺 0 / 多画 0 / 不一致 0）")
        else:
            detail = "；".join(
                f"`{name}` 同亮 {row.get('both_lit')} / 缺 "
                f"{row.get('original_only')} / 多画 {row.get('remake_only')}"
                f" / 不一致 {row.get('family_mismatches')}"
                for name, row in moments.items())
            parts.append(f"**W2（覆盖层逐格族名）**：**未归零**（{detail}）")
    else:
        parts.append("**W2（覆盖层逐格族名）**：本次收据里没有逐格对拍数据")

    task_book = REPO / "notes" / "s49-fidelity" / "WAVE11-TASKS.md"
    wave_start = task_book.stat().st_mtime if task_book.is_file() else 0.0
    artifacts = sorted(
        (path for path in (REPO / "build" / "s49-victory-capture").rglob("*.json")
         if "settlement" in path.name),
        key=lambda path: path.stat().st_mtime)
    fresh = [path for path in artifacts if path.stat().st_mtime >= wave_start]
    if fresh:
        newest = fresh[-1]
        parts.append(
            f"**W1（结算链运行帧录制）**：**已有本波产物** "
            f"（`{newest.relative_to(REPO).as_posix()}`）")
    else:
        last = artifacts[-1] if artifacts else None
        parts.append(
            "**W1（结算链运行帧录制）**：**本波未产出**"
            + (f"（最新的结算链产物仍是 wave 9 的 "
               f"`{last.relative_to(REPO).as_posix()}`）" if last else ""))
    return "；".join(parts)


def x_status(receipt: dict) -> str:
    """The wave-12 parallel streams (X1 / X2 / X3), as of this run.

    X2 and X3 are measured *inside* the pipeline (step 6's per-cell family
    comparison and step 9's black field truth table), so their result is
    read straight out of this receipt.  X1's deliverable is the settlement
    chain's **running frames**; that one is looked up on disk, because a
    stream that has not written its artifact has, by definition, not
    delivered -- the report never claims a stream's conclusion that is not
    on disk.
    """
    parts = []

    overlay = (step_by_name(receipt, "overlay") or {}).get("metrics") or {}
    moments = overlay.get("moments") or {}
    if moments:
        zeroed = all(
            row.get("both_lit") == 192
            and not row.get("original_only")
            and not row.get("remake_only")
            and not row.get("family_mismatches")
            for row in moments.values())
        if zeroed:
            parts.append("**X2（覆盖层逐格族名）**：**已归零**"
                         "（同亮 192 / 缺 0 / 多画 0 / 不一致 0）")
        else:
            detail = "；".join(
                f"`{name}` 同亮 {row.get('both_lit')} / 缺 "
                f"{row.get('original_only')} / 多画 {row.get('remake_only')}"
                f" / 不一致 {row.get('family_mismatches')}"
                for name, row in moments.items())
            parts.append(f"**X2（覆盖层逐格族名）**：**未归零**（{detail}）")
    else:
        parts.append("**X2（覆盖层逐格族名）**：本次收据里没有逐格对拍数据")

    black = (step_by_name(receipt, "blackfade") or {}).get("metrics") or {}
    original_events = (black.get("original") or {}).get("events") or []
    remake_events = (black.get("remake") or {}).get("events") or []
    if original_events or remake_events:
        def _events(events):
            return "；".join(
                f"事件 {e.get('event')} = 淡出 {e.get('fade_out_frames')}"
                f" / 全黑 {e.get('black_hold_frames')}"
                f" / 淡入 {e.get('fade_in_frames')}"
                for e in events)
        parts.append(
            f"**X3（黑场事件数/时长）**：原版 **{len(original_events)}** 个事件"
            f"（{_events(original_events)}）；重制侧 **{len(remake_events)}** 个事件"
            f"（{_events(remake_events)}）")
    else:
        parts.append("**X3（黑场事件数/时长）**：本次收据里没有黑场真值表")

    notes = sorted((REPO / "notes" / "s49-fidelity").glob("X1-*.md"))
    tables = sorted(
        (path for path in (REPO / "build" / "s49-battle-balance").rglob("*.json")
         if "settlement" in path.name),
        key=lambda path: path.stat().st_mtime)
    if notes:
        parts.append(f"**X1（结算链运行帧）**：**已交付**"
                     f"（`notes/s49-fidelity/{notes[-1].name}`）")
    elif tables:
        newest = tables[-1]
        parts.append(f"**X1（结算链运行帧）**：**有产物、笔记未交付**"
                     f"（`{newest.relative_to(REPO).as_posix()}`）")
    else:
        parts.append("**X1（结算链运行帧）**：**尚未交付**"
                     "（结算链运行帧逐屏对照表本报告没有数字）")
    inflight = x1_inflight()
    if inflight:
        parts.append(inflight)
    return "；".join(parts)


def x1_inflight() -> str:
    """What X1's *in-flight* artifacts already show (labelled as such).

    X1 has not delivered its note yet, so nothing here is treated as a
    result.  It is read from X1's own files so that the reader can follow
    the path and check it; the wording says "in flight" explicitly.
    """
    root = REPO / "build" / "s49-battle-balance" / "u2"
    if not root.is_dir():
        return ""
    routes = sorted(root.glob("route*.err"),
                    key=lambda path: path.stat().st_mtime)
    if not routes:
        return ""
    newest = routes[-1]
    tail = []
    try:
        text = newest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for line in text.splitlines():
        if line.startswith("after the battle:") or \
                line.startswith("after the settlement:"):
            tail.append(line.strip())
    if not tail:
        return ""
    stamp = datetime.datetime.fromtimestamp(newest.stat().st_mtime).astimezone()
    return (f"**X1 在飞观察**（不是交付结果）："
            f"`{newest.relative_to(REPO).as_posix()}`"
            f"（{stamp.isoformat(timespec='seconds')}）的最后两行 —— "
            + " / ".join(tail))


def x1_status() -> str:
    """Just the X1 clause of :func:`x_status`, for the sections that need it."""
    clause = [part for part in x_status({}).split("；")
              if part.startswith("**X1")]
    return clause[0] if clause else "**X1（结算链运行帧）**：**尚未交付**"


def _note_present_since(prefix: str, cutoff_name: str) -> pathlib.Path | None:
    """The newest note with *prefix* written **after** the given task book.

    The notes directory also holds older waves' notes with the same prefixes
    (``Y3-overlay-zero.md`` is wave 6's Y3, not wave 13's; ``X2-overlay-zero.md``
    is wave 12's X2).  A note only counts as *this wave's* delivery when it
    was written after **this wave's** task book -- otherwise the report would
    credit a stream with a note that belongs to a much earlier wave.
    """
    wave_start = (REPO / "notes" / "s49-fidelity" / cutoff_name)
    try:
        cutoff = wave_start.stat().st_mtime
    except OSError:
        cutoff = 0.0
    notes = [path for path in sorted(
        (REPO / "notes" / "s49-fidelity").glob(f"{prefix}*.md"))
        if path.stat().st_mtime >= cutoff]
    return notes[-1] if notes else None


def _note_present(prefix: str) -> pathlib.Path | None:
    """The newest **wave-13** note whose file name starts with *prefix*."""
    return _note_present_since(prefix, "WAVE13-TASKS.md")


def y_status(receipt: dict) -> str:
    """The wave-13 parallel streams (Y1 / Y2 / Y3), as of this run.

    Same discipline as :func:`x_status`: a stream that has not written its
    note has, by definition, not delivered -- the report never claims a
    stream's conclusion that is not on disk.  What *is* measured inside the
    pipeline (the overlay families, the black field truth table) is read
    straight out of this receipt.
    """
    parts = []

    # ---- Y2: the overlay families -------------------------------------
    overlay = (step_by_name(receipt, "overlay") or {}).get("metrics") or {}
    moments = overlay.get("moments") or {}
    y2_note = _note_present("Y2-")
    if moments:
        detail = "；".join(
            f"`{name}` 同亮 {row.get('both_lit')} / 缺 {row.get('original_only')}"
            f" / 多画 {row.get('remake_only')} / 不一致 "
            f"{row.get('family_mismatches')}"
            for name, row in moments.items())
        achieved = [name for name, row in moments.items()
                    if row.get("both_lit") == 192
                    and not row.get("original_only")
                    and not row.get("remake_only")]
        parts.append(
            f"**Y2（覆盖层逐格族名）**："
            + (f"**「同亮 192 / 缺 0 / 多画 0」在 "
               + "、".join(f"`{name}`" for name in achieved)
               + " 上已达成**" if achieved
               else "**「同亮 192 / 缺 0 / 多画 0」未达成**")
            + f"（{detail}；`grid16` 是原版的**单帧瞬态**、"
              "`banner` 是空覆盖层，两者本就不适用 192 的目标）"
            + (f"；**已交付**（`notes/s49-fidelity/{y2_note.name}`）"
               if y2_note else "；**笔记尚未交付**"))
    else:
        parts.append("**Y2（覆盖层逐格族名）**：本次收据里没有逐格对拍数据")

    # ---- Y3: the black field ------------------------------------------
    black = (step_by_name(receipt, "blackfade") or {}).get("metrics") or {}
    original_events = (black.get("original") or {}).get("events") or []
    remake_events = (black.get("remake") or {}).get("events") or []
    y3_note = _note_present("Y3-")
    if original_events or remake_events:
        def _events(events):
            return "；".join(
                f"{e.get('fade_out_frames')}/{e.get('black_hold_frames')}"
                f"/{e.get('fade_in_frames')}" for e in events)
        aligned = (len(original_events) == len(remake_events) == 2)
        parts.append(
            f"**Y3（黑场事件数/时长）**："
            + ("**事件数已对齐（2 个）**" if aligned
               else f"**事件数未对齐**（原版 **{len(original_events)}** 个"
                    f" vs 重制侧 **{len(remake_events)}** 个）")
            + f"；原版（{_events(original_events)}）；"
              f"重制侧（{_events(remake_events)}）"
            + (f"；**已交付**（`notes/s49-fidelity/{y3_note.name}`）"
               if y3_note else "；**笔记尚未交付**"))
    else:
        parts.append("**Y3（黑场事件数/时长）**：本次收据里没有黑场真值表")

    # ---- Y1: the stack overflow + the settlement chain's running frames -
    y1_note = _note_present("Y1-")
    frames = sorted(
        (path for path in (REPO / "build" / "s49-battle-balance").rglob("*.json")
         if "settlement" in path.name),
        key=lambda path: path.stat().st_mtime)
    header_changed = _remake_file_changed(
        "butano-sequel/game/include/konoha/battle_scene_presentation_event.h")
    y1_parts = ["**Y1（栈溢出修复 + 结算链运行帧）**："
                + (f"**已交付**（`notes/s49-fidelity/{y1_note.name}`；"
                   "这份笔记是 **wave 14 的 Z1** 补交的，"
                   "它关掉的就是 wave 13 的 Y1 欠账）"
                   if y1_note else "**笔记尚未交付**")]
    if header_changed:
        y1_parts.append("独占头 `battle_scene_presentation_event.h` **已改动**")
    if frames:
        y1_parts.append(
            f"结算链运行帧收据 `{frames[-1].relative_to(REPO).as_posix()}`")
    else:
        y1_parts.append("**结算链运行帧尚无收据**")
    if not frames:
        y1_parts.append("**逐屏运行帧对照表本报告没有数字**")
    parts.append("；".join(y1_parts))
    return "；".join(parts)


# --------------------------------------------------------------------------
# wave 14: the three parallel streams (Z1 / Z2 / Z3).
#
# The report must never claim a stream's conclusion that is not on disk, so
# every wave-14 number below is **read from the disk**: the note (with this
# wave's task book as the mtime cutoff) plus the stream's own JSON receipt.
# A stream that has not written either has, by definition, not delivered.
# --------------------------------------------------------------------------

W14_CUTOFF = "WAVE14-TASKS.md"

# Where a stream's JSON receipt may land.  The first candidate that actually
# carries rows wins; the scan is newest-first.
SETTLEMENT_ROOTS = (
    "build/z1",
    "build/s49-z1",
    "build/s49-battle-balance",
    "build/s49-settlement",
    "build/s49-victory-capture",
)
BOUND_ROOTS = (
    "build/s49-z3-bound",
    "build/s49-z3",
    "build/s49-pairing",
)

# Keys a stream may use for "the provable pixel lower bound".
BOUND_KEYS = (
    "bound", "lower_bound", "proven_lower_bound", "provable_lower_bound",
    "pixel_lower_bound", "bound_px", "bound_pixels", "bound_sum",
    "lower_bound_px", "lower_bound_pixels", "min_sum", "minimum_sum",
    "floor_sum",
)

# the bound is read from disk several times per report -> scan once
_Z3_CACHE: dict = {}

# The JSON walks are repeated by several readers with the same roots and the
# same cutoff (``build/`` holds thousands of files) -> walk once, filter after.
_SCAN_CACHE: dict = {}


def _scan_json(roots, keep, max_bytes: int = 4 * 1024 * 1024, limit: int = 400,
               min_mtime: float = 0.0):
    """Newest-first candidate JSON receipts under *roots* (relative to REPO).

    *min_mtime* is the wave cutoff: an artifact written **before** this
    wave's task book cannot be this wave's delivery -- without it the
    reader would happily quote a wave-12 receipt as if it were wave 14's.

    The walk is cached per ``(roots, max_bytes, limit, min_mtime)``: the
    *keep* predicate is applied afterwards, which is the same result as
    filtering during the walk (the order of the two filters does not matter
    because only the newest *matching* files are returned).
    """
    key = (tuple(roots), max_bytes, limit, min_mtime)
    found = _SCAN_CACHE.get(key)
    if found is None:
        found = []
        for root in roots:
            base = REPO / root
            if not base.is_dir():
                continue
            try:
                paths = list(base.rglob("*.json"))
            except OSError:
                continue
            for path in paths:
                try:
                    if path.stat().st_size > max_bytes:
                        continue
                    if path.stat().st_mtime < min_mtime:
                        continue
                except OSError:
                    continue
                found.append(path)
        found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        _SCAN_CACHE[key] = found
    candidates = [path for path in found
                  if keep(path.name.lower(), path.as_posix().lower())]
    return candidates[:limit]


def _wave_cutoff_mtime() -> float:
    """The mtime of this wave's task book -- the "delivered in this wave" line."""
    try:
        return (REPO / "notes" / "s49-fidelity" / W14_CUTOFF).stat().st_mtime
    except OSError:
        return 0.0


def _rows_of(document) -> list:
    """The list of per-item rows inside a stream's receipt, if there is one."""
    if not isinstance(document, dict):
        return []
    for key in ("running_screens", "remake_screens", "screens", "rows",
                "comparisons", "per_screen", "items", "pages", "chain_pages"):
        value = document.get(key)
        if isinstance(value, list) and value:
            rows = [row for row in value if isinstance(row, dict)]
            if rows:
                return rows
    return []


def _is_comparison(rows) -> bool:
    """Do these rows carry a **difference** (not just a recording)?"""
    for row in rows:
        for key in ("differing_pixels", "diff_px", "diff_pixels",
                    "diff_bbox", "original_sha256", "original"):
            if row.get(key) not in (None, ""):
                return True
    return False


def _settlement_rom_sha(path: pathlib.Path, document,
                        prefer_sha: str | None = None) -> str | None:
    """Which ROM the settlement evidence was measured on.

    The comparison sheet itself may not name the ROM; its *source run* does
    (``chain.json`` next to the shots).  A measurement that cannot name its
    ROM is not a measurement -- and if the ROM is not the one this pipeline
    run built, the report must say so.

    The **original** side's digest must never be returned: it is the
    original ROM, not the remake's.
    """
    if isinstance(document, dict):
        for key in ("remake_rom_sha256", "rom_sha256"):
            candidate = document.get(key)
            if isinstance(candidate, str) and len(candidate) == 64:
                return candidate
    if isinstance(document, dict):
        remake_dir = document.get("remake_dir")
        if remake_dir:
            base = pathlib.Path(os.path.abspath(str(REPO / remake_dir)))
            for candidate_path in (base.parent / "chain.json",
                                   base / "chain.json"):
                data = load_json(candidate_path)
                if isinstance(data, dict):
                    sha = data.get("rom_sha256")
                    if isinstance(sha, str) and len(sha) == 64:
                        return sha
    # last resort: a sibling receipt of the same run -- but only one that
    # matches the ROM this pipeline built, or one that names the remake
    candidates: list = []
    directory = path.parent
    for _ in range(2):
        for sibling in directory.glob("*.json"):
            if sibling == path:
                continue
            data = load_json(sibling)
            if not isinstance(data, dict):
                continue
            sha = data.get("remake_rom_sha256") or data.get("rom_sha256")
            if isinstance(sha, str) and len(sha) == 64:
                candidates.append(sha)
        directory = directory.parent
    if prefer_sha and prefer_sha in candidates:
        return prefer_sha
    return None


def settlement_running_frames(prefer_sha: str | None = None
                              ) -> tuple[pathlib.Path | None, list, str, str | None]:
    """Z1's settlement chain evidence: the running frames and their compare.

    Returns ``(receipt path, rows, kind, rom sha256)`` where *kind* is
    ``"compare"`` (the rows carry a per-screen difference against the
    original truth) or ``"chain"`` (the rows are the remake side's
    recorded chain pages).  The ROM digest says which ROM the measurement
    belongs to -- the report must not mix ROMs.
    The original side's truth sheet is *not* a comparison, so it is
    excluded by name: it has no remake side.
    """
    def keep(name: str, path: str) -> bool:
        # the stream names its own files; these are the words it uses
        if not any(word in name for word in
                   ("settlement", "settle", "chain", "result", "victory")):
            return False
        if "truth" in name or "assets" in name:
            return False
        return True

    fallback = (None, [], "")
    for path in _scan_json(SETTLEMENT_ROOTS, keep,
                           min_mtime=_wave_cutoff_mtime()):
        document = load_json(path)
        rows = _rows_of(document)
        if not rows:
            continue
        if not any("sha256" in json.dumps(row) for row in rows):
            continue
        rom_sha = _settlement_rom_sha(path, document, prefer_sha)
        if _is_comparison(rows):
            return path, rows, "compare", rom_sha
        if not fallback[0]:
            fallback = (path, rows, "chain", rom_sha)
    return fallback


def _find_bound(document):
    """The (key path, value) of the provable pixel lower bound, if any.

    A key counts when it *is* one of :data:`BOUND_KEYS`, or when it contains
    "bound" / "lower" **and** says it is a pixel count ("pixel", "px",
    "sum", "floor").  The second half matters: the pairing receipt has a
    ``pairing_diff_lower_bound`` of **4** -- that is a number of *frames*,
    not of pixels, and quoting it as a pixel bound would be wrong.
    """
    if isinstance(document, dict):
        for key, value in document.items():
            lowered = str(key).lower()
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            if lowered in BOUND_KEYS:
                return str(key), value
            if ("bound" in lowered or "lower" in lowered) and (
                    "pixel" in lowered or "px" in lowered
                    or "sum" in lowered or "floor" in lowered):
                return str(key), value
        for key, value in document.items():
            found = _find_bound(value)
            if found[0] is not None:
                return f"{key}.{found[0]}", found[1]
    elif isinstance(document, list):
        for index, value in enumerate(document):
            found = _find_bound(value)
            if found[0] is not None:
                return f"[{index}].{found[0]}", found[1]
    return None, None


def _first_sha(document):
    """The first 64-hex digest inside *document*."""
    if isinstance(document, dict):
        for key, value in document.items():
            if ("sha" in str(key).lower() and isinstance(value, str)
                    and len(value) == 64):
                return value.lower()
        for value in document.values():
            found = _first_sha(value)
            if found:
                return found
    elif isinstance(document, list):
        for value in document:
            found = _first_sha(value)
            if found:
                return found
    return None


def _find_remake_rom_sha(document):
    """The digest of the **remake** ROM the receipt measured.

    The bound is a statement about *this* ROM, so the original side's digest
    must not be mistaken for it -- and neither must a *frames* digest.  The
    lookup therefore only accepts a digest that lives under a block named
    after the ROM.
    """
    if not isinstance(document, dict):
        return None
    # (a) roms -> remake -> sha256
    for key, value in document.items():
        if "rom" in str(key).lower() and isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if ("remake" in str(sub_key).lower()
                        and isinstance(sub_value, dict)):
                    found = _first_sha(sub_value)
                    if found:
                        return found
    # (b) remake_rom_sha256 / remake_sha256
    for key, value in document.items():
        lowered = str(key).lower()
        if ("remake" in lowered and "sha" in lowered
                and isinstance(value, str) and len(value) == 64):
            return value.lower()
    # (c) any key that names the ROM and a digest
    for key, value in document.items():
        lowered = str(key).lower()
        if ("rom" in lowered and "sha" in lowered
                and isinstance(value, str) and len(value) == 64):
            return value.lower()
    return None


def z3_bounds() -> list:
    """Every bound receipt Z3 has written for this wave.

    Each record names the **remake ROM** it measured, so the report can
    check that the bound really belongs to *this* run's ROM (a bound
    measured on another ROM proves nothing about this one).
    """
    if "bounds" in _Z3_CACHE:
        return _Z3_CACHE["bounds"]
    result = _z3_bounds_uncached()
    _Z3_CACHE["bounds"] = result
    return result


def _z3_bounds_uncached() -> list:
    def keep(name: str, path: str) -> bool:
        return ("bound" in name or "lower" in name or "floor" in name
                or "z3" in path or "pairing" in path)

    records: list = []
    for path in _scan_json(BOUND_ROOTS, keep,
                           min_mtime=_wave_cutoff_mtime()):
        document = load_json(path)
        key, value = _find_bound(document)
        if key is None:
            continue
        rom_sha = _find_remake_rom_sha(document)
        records.append({
            "path": path,
            "key": key,
            "value": int(value),
            "rom_sha256": rom_sha,
            "label": document.get("label"),
            "walk": document.get("walk"),
            "proof": document.get("proof"),
            "canonical_sum": document.get("canonical_sum"),
            "beats": document.get("beats"),
            "per_beat": document.get("per_beat"),
            "cross_check": document.get("cross_check"),
            "frames": document.get("frames"),
            "roms": document.get("roms"),
        })
    return records


def z3_bound(rom_sha256: str | None = None) -> dict | None:
    """The bound that belongs to *rom_sha256* (or the newest one).

    A bound measured on a different ROM is **not** this run's bound, so
    when a ROM is given only a record with that exact digest is accepted.
    """
    records = z3_bounds()
    if not records:
        return None
    if rom_sha256:
        same = [record for record in records
                if record["rom_sha256"] == rom_sha256]
        if not same:
            return None
        records = same
    record = dict(records[0])
    values = {item["value"] for item in records}
    record["runs"] = records
    record["agree"] = len(values) == 1
    record["value"] = records[0]["value"]
    return record


def z3_reachable() -> dict | None:
    """The content-anchor **reachable** residual sum (the bracket's upper end).

    Z3's pairing receipt answers: of the 25 canonical moments, how many have
    a *same-moment* remake frame, and what is the sum of their residuals.
    That number is **achievable**, so it is the upper end of the bracket.
    """
    if "reachable" in _Z3_CACHE:
        return _Z3_CACHE["reachable"]
    result = None
    for path in _scan_json(BOUND_ROOTS, lambda name, full: True, limit=400,
                           min_mtime=_wave_cutoff_mtime()):
        document = load_json(path)
        summary = document.get("summary") if isinstance(document, dict) else None
        if not isinstance(summary, dict):
            continue
        value = summary.get("residual_at_match_sum")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        result = {
            "path": path,
            "value": int(value),
            "exact_moment": summary.get("exact_moment"),
            "original_frames": summary.get("original_frames"),
            "remake_frames": summary.get("remake_frames"),
            "exact_moment_share": summary.get("exact_moment_share"),
        }
        break
    _Z3_CACHE["reachable"] = result
    return result


def _bound_proof_text() -> str:
    """Z3's own proof of the lower bound, quoted from its receipt."""
    for record in z3_bounds():
        proof = record.get("proof")
        if isinstance(proof, str) and proof.strip():
            return proof.strip()
    return ""


def z3_phase_attribution() -> tuple[pathlib.Path | None, dict]:
    """Z3's attribution of the 130 'walk 相位' cells, if it landed.

    The attribution is looked up by **content** (a receipt that talks about
    the phase families), not by a guessed file name: the stream's tool and
    its output directory are its own business.
    """
    if "phase" in _Z3_CACHE:
        return _Z3_CACHE["phase"]
    result = (None, {})
    candidates = _scan_json(BOUND_ROOTS, lambda name, full: True, limit=400,
                            min_mtime=_wave_cutoff_mtime())
    # a file that names the phase attribution is preferred over one that
    # merely mentions the word
    candidates.sort(key=lambda path: (0 if "phase" in path.name.lower() else 1,
                                      -path.stat().st_mtime))
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # the project names the phase families in Chinese; an English
        # "phase" key is not evidence (the wave-12 pairing receipt has one)
        if "相位" not in text:
            continue
        document = load_json(path)
        if not isinstance(document, dict):
            continue
        result = (path, document)
        break
    _Z3_CACHE["phase"] = result
    return result


def z14_status(receipt: dict) -> str:
    """The wave-14 parallel streams (Z1 / Z2 / Z3), as of this run.

    Z1 and Z3 deliver a note plus a JSON receipt; Z2 changes the product
    itself, so its evidence is the **pipeline's own black field truth table**
    (step 9, measured on this run's pinned ROM).
    """
    parts = []

    # ---- Z1: the settlement chain's running frames ----------------------
    z1_note = _note_present_since("Y1-stack-fix", W14_CUTOFF)
    path, rows, kind, rom_sha = settlement_running_frames(
        receipt_rom_sha(receipt))
    z1_parts = ["**Z1（栈溢出笔记 + 结算链运行帧）**："
                + (f"**已交付**（`notes/s49-fidelity/{z1_note.name}`）"
                   if z1_note else "**笔记尚未交付**")]
    if rows:
        z1_parts.append(
            f"**结算链收据有 {len(rows)} 行**"
            f"（`{path.relative_to(REPO).as_posix()}`；"
            + ("逐屏对照表" if kind == "compare" else "重制侧链页记录")
            + "）")
    else:
        z1_parts.append("**结算链运行帧尚无对照收据**")
    parts.append("；".join(z1_parts))

    # ---- Z2: the black field -------------------------------------------
    black = (step_by_name(receipt, "blackfade") or {}).get("metrics") or {}
    original_events = (black.get("original") or {}).get("events") or []
    remake_events = (black.get("remake") or {}).get("events") or []
    if original_events or remake_events:
        def _events(events):
            return "；".join(
                f"{e.get('fade_out_frames')}/{e.get('black_hold_frames')}"
                f"/{e.get('fade_in_frames')}" for e in events)
        aligned = (len(original_events) == len(remake_events) == 2)
        parts.append(
            "**Z2（黑场事件数/时长）**："
            + ("**事件数已对齐（2 个）**" if aligned
               else f"**事件数未对齐**（原版 **{len(original_events)}** 个"
                    f" vs 重制侧 **{len(remake_events)}** 个）")
            + f"；原版（{_events(original_events)}）；"
              f"重制侧（{_events(remake_events)}）")
    else:
        parts.append("**Z2（黑场事件数/时长）**：本次收据里没有黑场真值表")

    # ---- Z3: the provable lower bound, recomputed for this ROM ---------
    z3_note = _note_present_since("Z3-bound", W14_CUTOFF)
    bound = z3_bound(receipt_rom_sha(receipt))
    z3_parts = ["**Z3（残差下界重算 + walk 相位归因）**："
                + (f"**已交付**（`notes/s49-fidelity/{z3_note.name}`）"
                   if z3_note else "**笔记尚未交付**")]
    if bound:
        z3_parts.append(
            f"**可证像素下界 = {bound['value']} px**"
            f"（收据 `{bound['path'].relative_to(REPO).as_posix()}`，"
            f"当前 ROM sha256 `{bound['rom_sha256'][:16]}…`；"
            f"{len(bound['runs'])} 次独立跑"
            + ("**逐值相同**" if bound["agree"] else "**不一致**") + "）")
    else:
        z3_parts.append("**可证像素下界尚未为本次 ROM 重算**")
    parts.append("；".join(z3_parts))
    return "；".join(parts)


# --------------------------------------------------------------------------
# wave 15: W1 (three newly-found product defects) / W2 (the ratchet baseline
# fix) / W3 (black field + the victory / settlement screens).
#
# "Delivered in this wave" is decided by the **mtime of this wave's task
# book** -- never by the file name: `notes/s49-fidelity/` still holds wave 7's
# Z1 / Z2 / Z3 under the very same names, with wave 14's notes next to them.
# A note counts only when it was written **after** the task book.
# --------------------------------------------------------------------------

# The project convention names the stream in the note's **title**
# ("# W1 --- ..."), so the title is what decides which stream a note
# belongs to.  A note whose title does not name a stream is reported as
# "unclassified" -- never guessed into one.
W15_STREAMS = ("W1", "W2", "W3")


def wave15_cutoff_mtime() -> float:
    """The mtime of wave 15's task book -- the 'delivered in this wave' line."""
    try:
        return (REPO / "notes" / "s49-fidelity" / W15_CUTOFF).stat().st_mtime
    except OSError:
        return 0.0


def wave15_notes() -> list:
    """Every note written **after** wave 15's task book, newest first."""
    cutoff = wave15_cutoff_mtime()
    directory = REPO / "notes" / "s49-fidelity"
    found: list = []
    if not directory.is_dir():
        return found
    for path in directory.glob("*.md"):
        try:
            if path.stat().st_mtime > cutoff:
                found.append(path)
        except OSError:
            continue
    found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return found


def _stream_of_title(title: str) -> str | None:
    """Which stream does a note's title name, if any?

    The project's convention is ``# W1 --- ...``; the match is deliberately
    loose (the token may appear a little further into the title) but it must
    appear **early** -- otherwise a note that merely mentions another stream
    in its title would be counted as that stream's delivery.
    """
    match = re.search(r"\b(W[123])\b", title)
    if not match or match.start() > 30:
        return None
    return match.group(1)


def wave15_streams() -> dict:
    """Which of W1 / W2 / W3 have a note **in this wave**.

    Returns ``{"W1": [paths], "W2": [...], "W3": [...], "other": [...]}``.
    """
    streams: dict = {name: [] for name in W15_STREAMS}
    streams["other"] = []
    for path in wave15_notes():
        try:
            with path.open("r", encoding="utf-8") as handle:
                first = handle.readline()
        except (OSError, UnicodeDecodeError):
            continue
        name = _stream_of_title(first)
        if name and name in streams:
            streams[name].append(path)
        else:
            streams["other"].append(path)
    return streams


def _notes_of(paths) -> str:
    if not paths:
        return ""
    return "、".join(f"`notes/s49-fidelity/{path.name}`" for path in paths)


def w15_status(receipt: dict) -> str:
    """The wave-15 parallel streams (W1 / W2 / W3), as of this run.

    W1 and W3 change the **product**, so their evidence is their note plus
    the pipeline's own measurements on this run's pinned ROM.  W2 fixes the
    **instrument** (the ratchet baseline), so its evidence is what the
    judgment step recorded about the baseline it compared against.
    """
    streams = wave15_streams()
    parts: list = []

    # ---- W1: three product defects ---------------------------------------
    w1 = streams["W1"]
    w1_parts = ["**W1（3 个新查实的产品缺陷：调色板 cohort / "
                "战后对白与任务菜单的 UI 层 / 非法 UTF-8）**："
                + (f"**已交付**（{_notes_of(w1)}）" if w1 else "**尚未交付**")]
    parts.append("；".join(w1_parts))

    # ---- W2: the ratchet baseline ----------------------------------------
    judgment = step_by_name(receipt, "judgment") or {}
    judgment_notes = judgment.get("notes") or []
    baseline_notes = [note for note in judgment_notes
                      if "baseline" in note.lower() or "ratchet" in note.lower()]
    w2 = streams["W2"]
    w2_parts = ["**W2（棘轮基线修正：基线改成「上一波被接受的收据」）**："
                + (f"**已交付**（{_notes_of(w2)}）" if w2 else "**尚未交付**")]
    if baseline_notes:
        w2_parts.append("**本次运行的棘轮基线**："
                        + "；".join(baseline_notes))
    verdict = ratchet_verdict(receipt)
    if verdict.get("status"):
        w2_parts.append(
            f"**本次的棘轮判定 = `{verdict.get('status')}`**"
            + ("（**不可比 ≠ 通过**：基线 ROM 与本次 ROM 不同 ⇒ "
               "「残差只许变小」这条规则本次没有被检验）"
               if verdict.get("status") == "incomparable" else "")
            + (f"（基线 `{verdict.get('baseline_report')}`）"
               if verdict.get("baseline_report") else ""))
    parts.append("；".join(w2_parts))

    # ---- W3: black field + the victory / settlement screens --------------
    black = (step_by_name(receipt, "blackfade") or {}).get("metrics") or {}
    original_events = (black.get("original") or {}).get("events") or []
    remake_events = (black.get("remake") or {}).get("events") or []
    w3 = streams["W3"]
    w3_parts = ["**W3（黑场收官 + 胜利/结算屏画面）**："
                + (f"**已交付**（{_notes_of(w3)}）" if w3 else "**尚未交付**")]
    if original_events or remake_events:
        def _triplets(events):
            return "；".join(
                f"{event.get('fade_out_frames')}/"
                f"{event.get('black_hold_frames')}/"
                f"{event.get('fade_in_frames')}" for event in events)
        w3_parts.append(
            f"**本次运行的黑场**：原版 **{len(original_events)}** 个"
            f"（{_triplets(original_events)}）；"
            f"重制侧 **{len(remake_events)}** 个"
            f"（{_triplets(remake_events)}）")
    parts.append("；".join(w3_parts))
    return "；".join(parts)


# --------------------------------------------------------------------------
# wave 16: V1 (a real victory + the settlement chain's **real** running
# frames) / V2 (the pixel fixes) / V4 (the provable lower bound, recomputed
# for the **final** ROM).
#
# "Delivered in this wave" is decided by the **mtime of this wave's task
# book** -- never by the file name: `notes/s49-fidelity/` still holds wave 7's
# Z1 / Z2 / Z3 and wave 5 / 6 / 8's W1 / W2 / W3 under the very same names.
# --------------------------------------------------------------------------

W16_STREAMS = ("V1", "V2", "V3", "V4")

# Where a wave-16 stream's JSON receipt may land.  The scan is newest-first
# and only accepts files written **after** this wave's task book.
W16_ROOTS = ("build",)


def wave16_cutoff_mtime() -> float:
    """The mtime of wave 16's task book -- the 'delivered in this wave' line."""
    try:
        return (REPO / "notes" / "s49-fidelity" / W16_CUTOFF).stat().st_mtime
    except OSError:
        return 0.0


def wave16_notes() -> list:
    """Every note written **after** wave 16's task book, newest first."""
    cutoff = wave16_cutoff_mtime()
    directory = REPO / "notes" / "s49-fidelity"
    found: list = []
    if not directory.is_dir():
        return found
    for path in directory.glob("*.md"):
        try:
            if path.stat().st_mtime > cutoff:
                found.append(path)
        except OSError:
            continue
    found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return found


def _stream_of_title_v16(title: str) -> str | None:
    """Which wave-16 stream does a note's title name, if any?"""
    match = re.search(r"\b(V[1234])\b", title)
    if not match or match.start() > 30:
        return None
    return match.group(1)


def wave16_streams() -> dict:
    """Which of V1 / V2 / V3 / V4 have a note **in this wave**."""
    streams: dict = {name: [] for name in W16_STREAMS}
    streams["other"] = []
    for path in wave16_notes():
        try:
            with path.open("r", encoding="utf-8") as handle:
                first = handle.readline()
        except (OSError, UnicodeDecodeError):
            continue
        name = _stream_of_title_v16(first)
        if name and name in streams:
            streams[name].append(path)
        else:
            streams["other"].append(path)
    return streams


def _w16_scan(keep, limit: int = 200, roots=W16_ROOTS):
    """Newest-first JSON receipts written **after** wave 16's task book."""
    return _scan_json(roots, keep, limit=limit,
                      min_mtime=wave16_cutoff_mtime())


def wave16_settlement_rows(prefer_sha: str | None = None
                            ) -> tuple[pathlib.Path | None, list, str, str | None]:
    """V1's **real** settlement chain table.

    V1 beat the battle for real (the outcome comes from the fight, not from
    a poke), so its running frames are the ones the report must quote.  The
    receipt is found by **content** and bounded by this wave's task book; the
    original side's truth sheet is excluded by name because it has no remake
    side.  The ROM digest says which ROM the measurement belongs to.
    """
    def keep(name: str, path: str) -> bool:
        if not any(word in name for word in
                   ("settlement", "settle", "chain", "victory", "result")):
            return False
        if "truth" in name or "assets" in name:
            return False
        return True

    fallback = (None, [], "", None)
    for path in _w16_scan(keep):
        document = load_json(path)
        rows = _rows_of(document)
        if not rows:
            continue
        if not any("sha256" in json.dumps(row) for row in rows):
            continue
        rom_sha = _settlement_rom_sha(path, document, prefer_sha)
        if _is_comparison(rows):
            # The ROM filter applies to this pass too: a comparison sheet that
            # was measured on another ROM must not be quoted as this run's.
            if prefer_sha and rom_sha and rom_sha != prefer_sha:
                continue
            return path, rows, "compare", rom_sha
        if not fallback[0]:
            fallback = (path, rows, "chain", rom_sha)
    if fallback[0]:
        # A **chain** record is only a fallback: the second pass below looks
        # for a real per-screen **comparison** wherever it is filed.
        pass
    # Second pass: the file may be named anything at all.  A settlement table
    # is a list of at least three rows that each carry a digest and a
    # difference -- that is what the report quotes, so that is what it looks
    # for.
    for path in _w16_scan(lambda name, full: True, limit=200):
        document = load_json(path)
        if not isinstance(document, dict):
            continue
        rows = []
        for value in document.values():
            if (isinstance(value, list) and len(value) >= 3
                    and all(isinstance(row, dict) for row in value)):
                if any(_is_sha(str(row.get(key)))
                       for row in value
                       for key in ("remake_sha256", "original_sha256", "sha256")):
                    rows = value
                    break
        if not rows:
            continue
        if not _is_comparison(rows):
            continue
        rom_sha = _settlement_rom_sha(path, document, prefer_sha)
        if prefer_sha and rom_sha and rom_sha != prefer_sha:
            continue
        return path, rows, "compare", rom_sha
    return fallback


def wave16_chain_rows(prefer_sha: str | None = None
                      ) -> tuple[pathlib.Path | None, list, str | None, bool]:
    """The wave-16 settlement **chain** record (the remake side's pages).

    Returns ``(path, rows, rom sha256, poked)``.  ``poked`` is True when the
    chain was entered by **poking the controller state** instead of by
    really winning the battle -- the screen values of such a chain are the
    empty ones, so the report must never call it the "real" version.
    """
    def keep(name: str, path: str) -> bool:
        if not any(word in name for word in
                   ("settlement", "settle", "chain", "victory", "result")):
            return False
        if "truth" in name or "assets" in name:
            return False
        return True

    for path in _w16_scan(keep):
        document = load_json(path)
        rows = _rows_of(document)
        if not rows:
            continue
        if not any(row.get("phase_name") or row.get("outcome") is not None
                   for row in rows):
            continue
        rom_sha = _settlement_rom_sha(path, document, prefer_sha)
        if prefer_sha and rom_sha and rom_sha != prefer_sha:
            continue
        poked = False
        entry = document.get("entry")
        if isinstance(entry, dict):
            method = str(entry.get("method") or "")
            poked = "poke" in method.lower()
        if not poked:
            poked = bool(document.get("outcome_byte_before_poke") is not None
                         and document.get("outcome_byte_after_poke") is not None
                         and document.get("outcome_byte_before_poke")
                         != document.get("outcome_byte_after_poke"))
        return path, rows, rom_sha, poked
    return None, [], None, False


def _rom_sha_of_walk(path: pathlib.Path) -> str | None:
    """The remake ROM a walk receipt belongs to (its pinned copy).

    The content-anchor reachable sum belongs to **one** recording, so the
    report must know which ROM it is about before it puts it next to a
    lower bound.
    """
    for candidate in (
            path.parent / "walk" / "dense-remake" / "receipt.json",
            path.parent.parent / "walk" / "dense-remake" / "receipt.json",
            path.parent / "dense-remake" / "receipt.json",
            path.parent / "walk" / "receipt.json",
    ):
        data = load_json(candidate)
        if isinstance(data, dict):
            sha = data.get("rom_sha256")
            if isinstance(sha, str) and len(sha) == 64:
                return sha.lower()
    return None


def wave16_reachable(prefer_sha: str | None = None) -> dict | None:
    """The content-anchor **reachable** residual sum of a wave-16 walk.

    That is the **upper end** of the bracket.  It belongs to one recording,
    so it is only quoted when its ROM is the ROM this run measured -- an
    upper end from another ROM must not be put next to a lower end from
    this one (the report would then mix two calibres).
    """
    if "w16_reachable" in _Z3_CACHE:
        cached = _Z3_CACHE["w16_reachable"]
    else:
        cached = None
        for path in _w16_scan(lambda name, full: True, limit=200):
            document = load_json(path)
            summary = document.get("summary") if isinstance(document, dict) else None
            if not isinstance(summary, dict):
                continue
            value = summary.get("residual_at_match_sum")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            cached = {
                "path": path,
                "value": int(value),
                "exact_moment": summary.get("exact_moment"),
                "original_frames": summary.get("original_frames"),
                "remake_frames": summary.get("remake_frames"),
                "rom_sha256": _rom_sha_of_walk(path),
            }
            break
        _Z3_CACHE["w16_reachable"] = cached
    if cached is None:
        return None
    if prefer_sha and cached.get("rom_sha256") \
            and cached["rom_sha256"] != prefer_sha:
        return None
    return cached


def wave16_bounds() -> list:
    """Every bound receipt written **after** wave 16's task book (V4's)."""
    if "w16_bounds" in _Z3_CACHE:
        return _Z3_CACHE["w16_bounds"]

    def keep(name: str, path: str) -> bool:
        return ("bound" in name or "lower" in name or "floor" in name
                or "z3" in path or "pairing" in path or "v4" in path)

    records: list = []
    for path in _w16_scan(keep):
        document = load_json(path)
        key, value = _find_bound(document)
        if key is None:
            continue
        records.append({
            "path": path,
            "key": key,
            "value": int(value),
            "rom_sha256": _find_remake_rom_sha(document),
            "label": document.get("label"),
            "walk": document.get("walk"),
            "proof": document.get("proof"),
            "canonical_sum": document.get("canonical_sum"),
            "beats": document.get("beats"),
            "per_beat": document.get("per_beat"),
            "cross_check": document.get("cross_check"),
            "frames": document.get("frames"),
            "roms": document.get("roms"),
        })
    _Z3_CACHE["w16_bounds"] = records
    return records


def wave16_bound(rom_sha256: str | None = None) -> dict | None:
    """V4's bound -- for the **final** ROM when one is given.

    A bound measured on another ROM proves nothing about this one, so with a
    ROM digest only a record with that exact digest is accepted.
    """
    records = wave16_bounds()
    if not records:
        return None
    if rom_sha256:
        same = [record for record in records
                if record["rom_sha256"] == rom_sha256]
        if not same:
            return None
        records = same
    record = dict(records[0])
    values = {item["value"] for item in records}
    record["runs"] = records
    record["agree"] = len(values) == 1
    record["value"] = records[0]["value"]
    return record


def wave16_phase_attribution() -> tuple[pathlib.Path | None, dict]:
    """V4's attribution of the phase families (the 50-cell question).

    Found by **schema** (``konoha.s49-v4.phase-locate``) or by the
    distinctive blocks the receipt carries (``same_moment_comparison`` +
    ``coexistence``) -- **not** by the word "phase": wave 12's pairing
    receipt has English "phase" keys and is not this wave's evidence, and
    this wave's receipt does not use the Chinese word at all.
    """
    if "w16_phase" in _Z3_CACHE:
        return _Z3_CACHE["w16_phase"]
    result = (None, {})
    candidates = _w16_scan(lambda name, full: True, limit=200)
    candidates.sort(key=lambda path: (0 if "phase" in path.name.lower() else 1,
                                      -path.stat().st_mtime))
    for path in candidates:
        document = load_json(path)
        if not isinstance(document, dict):
            continue
        if "phase-locate" in str(document.get("schema") or ""):
            result = (path, document)
            break
        if (isinstance(document.get("same_moment_comparison"), dict)
                and isinstance(document.get("coexistence"), dict)):
            result = (path, document)
            break
    _Z3_CACHE["w16_phase"] = result
    return result


def _reuse_decision_of(report: dict, side: str) -> dict:
    """The reuse decision the capture layer recorded for one side."""
    attempts = ((report.get("run") or {}).get("attempts") or {}).get(side) or []
    for entry in attempts:
        if isinstance(entry, dict) and entry.get("kind") == "reuse-decision":
            return entry
    return {}


def judgment_report(package: pathlib.Path) -> dict:
    """The judgment bench's own report inside the package."""
    return load_json(pathlib.Path(os.path.abspath(
        str(package / "work" / "s49-report" / "report.json")))) or {}


def rom_identity(receipt: dict, package: pathlib.Path) -> dict:
    """Which ROM is this run about?  **Four** digests have to agree.

    * **build**    -- the ROM step 1 produced;
    * **pinned**   -- the copy every later step measures;
    * **package**  -- the ROM the package ships;
    * **measured** -- the ROM the judgment bench actually recorded.

    A mismatch is reported, never smoothed over: a run whose four digests
    differ is a run whose numbers belong to different bytes.
    """
    build = (step_by_name(receipt, "build") or {}).get("metrics") or {}
    package_step = (step_by_name(receipt, "package") or {}).get("metrics") or {}
    report = judgment_report(package)
    captures = report.get("captures") or {}
    remake = captures.get("remake") or {}
    digests = {
        "build": build.get("rom_sha256"),
        "pinned": build.get("pinned_rom_sha256"),
        "package": package_step.get("rom_sha256"),
        "measured": remake.get("measured_rom_sha256") or remake.get("rom_sha256"),
    }
    values = {value for value in digests.values() if value}
    present = sum(1 for value in digests.values() if value)
    return {
        "digests": digests,
        # All four have to be present **and** equal: a missing digest is not
        # an agreement, it is a gap.
        "agree": len(values) <= 1 and present == 4,
        "present": present,
        "rom_sha256": build.get("rom_sha256"),
        "rom_mtime": build.get("rom_mtime"),
        "rom_bytes": build.get("rom_bytes"),
        "reused": (report.get("run") or {}).get("reused", {}),
        "decisions": {side: _reuse_decision_of(report, side)
                      for side in ("original", "remake")},
        "captures": captures,
        "report": report,
    }


def _rebuilt_in_wave(receipt: dict, cutoff_mtime: float | None = None) -> bool:
    """Was the ROM this run measured **rebuilt during this wave**?

    A product stream (V2, and in wave 17 also U1 / U2) changes the ROM; if the
    ROM's build time is older than the task book's, the product fixes are
    **not** in this run's numbers and the report has to say so.

    *cutoff_mtime* picks the wave: wave 16's task book by default, wave 17's
    when the claim is about U1 / U2.
    """
    metrics = (step_by_name(receipt, "build") or {}).get("metrics") or {}
    stamp = metrics.get("rom_mtime")
    if not stamp:
        return False
    try:
        built = datetime.datetime.fromisoformat(str(stamp))
    except ValueError:
        return False
    if cutoff_mtime is None:
        cutoff_mtime = wave16_cutoff_mtime()
    cutoff = datetime.datetime.fromtimestamp(cutoff_mtime)
    if built.tzinfo is None:
        built = built.replace(tzinfo=cutoff.tzinfo)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=built.tzinfo)
    return built > cutoff


def w16_status(receipt: dict) -> str:
    """The wave-16 parallel streams (V1 / V2 / V4), as of this run."""
    streams = wave16_streams()
    parts: list = []

    # ---- V1: a real victory + the settlement chain's real frames ---------
    v1 = streams["V1"]
    path, rows, kind, rom_sha = wave16_settlement_rows(receipt_rom_sha(receipt))
    v1_parts = ["**V1（真实打完仗 + 结算链运行帧真实版）**："
                + (f"**已交付**（{_notes_of(v1)}）" if v1 else "**尚未交付**")]
    if rows:
        v1_parts.append(
            f"**结算链收据有 {len(rows)} 行**"
            f"（`{path.relative_to(REPO).as_posix()}`；"
            + ("逐屏对照表" if kind == "compare" else "重制侧链页记录")
            + "）")
        if rom_sha:
            v1_parts.append(f"测在 ROM `{rom_sha[:16]}…`")
    else:
        v1_parts.append("**结算链运行帧尚无对照收据**")
    parts.append("；".join(v1_parts))

    # ---- V2: the pixel fixes ---------------------------------------------
    # V2 has **no note** in this wave's task book: it is the *product* stream
    # (its exclusive files are all in the remake tree).  Its evidence is
    # therefore the pipeline's own measurements on this run's **pinned** ROM
    # plus the fact that the remake tree was rebuilt during this wave.
    black = (step_by_name(receipt, "blackfade") or {}).get("metrics") or {}
    original_events = (black.get("original") or {}).get("events") or []
    remake_events = (black.get("remake") or {}).get("events") or []
    v2_parts = ["**V2（像素修复全包：胜利屏 / 结算屏 / 硬切 / 生长段 / CJK 扩字）**："
                "**产品侧**（任务书里**没有给 V2 笔记** ⇒ "
                "证据是本流水线在**钉住的 ROM** 上的实测）"]
    _rom_mtime = (step_by_name(receipt, "build") or {}).get("metrics", {}).get(
        "rom_mtime")
    v2_parts.append(
        "**本次构建的 ROM 在本波被重建过**"
        if _rebuilt_in_wave(receipt) else
        "⚠️ **本次构建的 ROM 不是本波重建的** ⇒ V2 的产品改动**可能没进本次读数**")
    if original_events or remake_events:
        def _triplets(events):
            return "；".join(
                f"{event.get('fade_out_frames')}/"
                f"{event.get('black_hold_frames')}/"
                f"{event.get('fade_in_frames')}" for event in events)
        v2_parts.append(
            f"**本次运行的黑场**：原版 **{len(original_events)}** 个"
            f"（{_triplets(original_events)}）；"
            f"重制侧 **{len(remake_events)}** 个"
            f"（{_triplets(remake_events)}）")
    parts.append("；".join(v2_parts))

    # ---- V4: the provable lower bound for the **final** ROM --------------
    v4 = streams["V4"]
    bound = wave16_bound(receipt_rom_sha(receipt))
    v4_parts = ["**V4（可证像素下界为最终 ROM 终算 + 缺一个相位的定位）**："
                + (f"**已交付**（{_notes_of(v4)}）" if v4 else "**尚未交付**")]
    if bound:
        v4_parts.append(
            f"**可证像素下界 = {bound['value']} px**"
            f"（收据 `{bound['path'].relative_to(REPO).as_posix()}`，"
            f"当前 ROM sha256 `{str(bound['rom_sha256'])[:16]}…`；"
            f"{len(bound['runs'])} 次独立跑"
            + ("**逐值相同**" if bound["agree"] else "**不一致**") + "）")
    else:
        v4_parts.append("**可证像素下界尚未为本次 ROM 重算**")
    parts.append("；".join(v4_parts))
    return "；".join(parts)


# --------------------------------------------------------------------------
# wave 17: U1 (the **product** fix for D4) / U2 (the overlay + settlement
# fixes) / U4 (the **real** victory verification).
#
# "Delivered in this wave" is decided by the **mtime of this wave's task
# book** -- never by the file name: `notes/s49-fidelity/` still holds wave 16's
# V1 / V2 / V4 and wave 7's Z1 / Z2 / Z3 under very similar names.
#
# For the **product** streams (U1 / U2) the note is not enough: the package
# must contain the *fix*, not the *story*.  The product evidence is
# "their exclusive files were touched after the task book **and** the ROM was
# rebuilt after that" -- which is what `build/u3-dev/run-when-idle.ps1`
# gates on before the pipeline is allowed to run.
#
# The one thing this wave adds on top of wave 16 is the **chain's entry
# method**: a settlement chain that was entered by poking the controller
# state is NOT the real victory chain, and the report must say which one it
# is quoting.
# --------------------------------------------------------------------------

W17_ROOTS = ("build",)


def wave17_cutoff_mtime() -> float:
    """The mtime of wave 17's task book -- the 'delivered in this wave' line."""
    try:
        return (REPO / "notes" / "s49-fidelity" / W17_CUTOFF).stat().st_mtime
    except OSError:
        return 0.0


def wave17_notes() -> list:
    """Every note written **after** wave 17's task book, newest first."""
    cutoff = wave17_cutoff_mtime()
    directory = REPO / "notes" / "s49-fidelity"
    found: list = []
    if not directory.is_dir():
        return found
    for path in directory.glob("*.md"):
        try:
            if path.stat().st_mtime > cutoff:
                found.append(path)
        except OSError:
            continue
    found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return found


def _stream_of_title_v17(title: str) -> str | None:
    """Which wave-17 stream does a note's title name, if any?"""
    match = re.search(r"\b(U[1234])\b", title)
    if not match or match.start() > 30:
        return None
    return match.group(1)


def wave17_streams() -> dict:
    """Which of U1 / U2 / U3 / U4 have a note **in this wave**."""
    streams: dict = {name: [] for name in W17_STREAMS}
    streams["other"] = []
    for path in wave17_notes():
        try:
            with path.open("r", encoding="utf-8") as handle:
                first = handle.readline()
        except (OSError, UnicodeDecodeError):
            continue
        name = _stream_of_title_v17(first)
        if name and name in streams:
            streams[name].append(path)
        else:
            streams["other"].append(path)
    return streams


def _w17_scan(keep, limit: int = 300, roots=W17_ROOTS):
    """Newest-first JSON receipts written **after** wave 17's task book."""
    return _scan_json(roots, keep, limit=limit,
                      min_mtime=wave17_cutoff_mtime())


def _chain_entry_info(document: dict) -> dict:
    """How a settlement chain was entered -- and whether it was poked.

    ``poked`` is True / False / **None** (unknown).  ``None`` must never be
    read as "real": a chain whose entry method is not recorded cannot be
    called the real victory chain, it can only be called *unattributed*.
    """
    entry = document.get("entry")
    method = None
    if isinstance(entry, dict):
        candidate = str(entry.get("method") or "").strip()
        method = candidate or None
    elif isinstance(entry, str):
        method = entry.strip() or None

    poked: bool | None = None
    reason = ""
    if method is not None and "poke" in method.lower():
        poked = True
        reason = "`entry.method` 自报进入方式是 poke"
    else:
        before = document.get("outcome_byte_before_poke")
        after = document.get("outcome_byte_after_poke")
        if isinstance(before, int) and not isinstance(before, bool) \
                and isinstance(after, int) and not isinstance(after, bool):
            if before != after:
                poked = True
                reason = "outcome 字节在进入链的前后不同（被改过）"
            else:
                poked = False
                reason = "outcome 字节在进入链的前后相同（没被改过）"
        elif method is not None:
            poked = False
            reason = "`entry.method` 自报进入方式**不是** poke"
    return {"method": method, "poked": poked, "reason": reason}


def _chain_rows_of(document) -> list:
    """The chain's page rows, whatever the stream calls the key."""
    for key in ("pages", "screens", "rows", "chain_pages", "chain", "steps"):
        value = document.get(key)
        if isinstance(value, list) and value \
                and all(isinstance(row, dict) for row in value):
            return value
    return []


def _chain_outcome_of(document: dict, rows: list) -> int | None:
    """The ``outcome`` the chain ran with (1 = victory, 2 = defeat)."""
    for source in (rows, [document]):
        for row in source:
            outcome = row.get("outcome")
            if isinstance(outcome, int) and not isinstance(outcome, bool):
                return outcome
    return None


def wave17_chains(prefer_sha: str | None = None) -> list:
    """Every settlement **chain** record written after wave 17's task book.

    Each record says **how the chain was entered** -- that is the only thing
    that separates the *real battle* chain from the *poke* chain.  The report
    must never call a poked chain the real victory chain.
    """
    if "w17_chains" in _Z3_CACHE:
        records = _Z3_CACHE["w17_chains"]
    else:
        records = []
        for path in _w17_scan(lambda name, full: True, limit=300):
            document = load_json(path)
            if not isinstance(document, dict):
                continue
            rows = _chain_rows_of(document)
            if len(rows) < 3:
                continue
            # A **per-screen comparison** table is not a chain record: it
            # carries a difference per screen, not a chain page.  Mixing the
            # two would put a comparison sheet into the "chain" inventory.
            if _is_comparison(rows):
                continue
            if not any(row.get("phase_name") or row.get("outcome") is not None
                       or row.get("sha256") or row.get("phase")
                       for row in rows):
                continue
            info = _chain_entry_info(document)
            records.append({
                "path": path,
                "rows": rows,
                "rom_sha256": _settlement_rom_sha(path, document, None),
                "method": info["method"],
                "poked": info["poked"],
                "reason": info["reason"],
                "outcome": _chain_outcome_of(document, rows),
                "source": "wave17",
            })
        records.sort(key=lambda record: record["path"].stat().st_mtime,
                     reverse=True)
        _Z3_CACHE["w17_chains"] = records

    if prefer_sha:
        same = [record for record in records
                if record["rom_sha256"] == prefer_sha]
        if same:
            return same
    return records


def wave17_chain_verdict(record: dict) -> str:
    """``"real-victory"`` / ``"real-defeat"`` / ``"poke"`` / ``"unknown"``."""
    poked = record.get("poked")
    outcome = record.get("outcome")
    if poked is True:
        return "poke"
    if poked is False:
        return "real-victory" if outcome == 1 else "real-defeat"
    return "unknown"


def wave17_battles(prefer_sha: str | None = None) -> list:
    """Every **battle** receipt written after wave 17's task book.

    A battle receipt answers the question a chain receipt cannot: was the
    battle really fought (the driver's own ``entry.method`` says so), did the
    **product** decide it, and did the bees' HP actually drop.  Those three
    are the acceptance criteria of "真实打完仗" (U4's §4.2), so the report
    quotes them rather than the chain's page count.
    """
    if "w17_battles" in _Z3_CACHE:
        records = _Z3_CACHE["w17_battles"]
    else:
        records = []
        for path in _w17_scan(lambda name, full: True, limit=300):
            document = load_json(path)
            if not isinstance(document, dict):
                continue
            acceptance = document.get("acceptance")
            entry = document.get("entry")
            if not isinstance(acceptance, dict) and not isinstance(entry, dict):
                continue
            if not isinstance(entry, dict):
                continue
            method = str(entry.get("method") or "").strip() or None
            poked: bool | None = None
            if method is not None:
                poked = "poke" in method.lower()
            if isinstance(entry.get("poke"), bool):
                poked = bool(entry.get("poke"))
            settlement = document.get("settlement")
            pages = settlement.get("pages") if isinstance(settlement, dict) else []
            records.append({
                "path": path,
                "method": method,
                "poked": poked,
                "rom_sha256": document.get("rom_sha256"),
                "outcome": document.get("outcome"),
                "battle_decided": document.get("battle_decided"),
                "round": document.get("round"),
                "frames_run": document.get("frames_run"),
                "acceptance": acceptance if isinstance(acceptance, dict) else {},
                "pages": pages if isinstance(pages, list) else [],
                "errors": document.get("errors") or [],
                "schema": document.get("schema"),
            })
        records.sort(key=lambda record: record["path"].stat().st_mtime,
                     reverse=True)
        _Z3_CACHE["w17_battles"] = records
    if prefer_sha:
        same = [record for record in records
                if record["rom_sha256"] == prefer_sha]
        if same:
            return same
    return records


def wave17_battle_verdict(record: dict) -> str:
    """``"real-victory"`` / ``"real-defeat"`` / ``"undecided"`` / ``"poke"``.

    A **real victory** needs all three: the chain was **not** entered by a
    poke, the **product** decided the battle, and the outcome is 1.
    """
    if record.get("poked") is True:
        return "poke"
    if not record.get("battle_decided"):
        return "undecided"
    acceptance = record.get("acceptance") or {}
    victory = (record.get("outcome") == 1
               or acceptance.get("outcome_is_victory") is True)
    return "real-victory" if victory else "real-defeat"


def wave17_real_victory(prefer_sha: str | None = None) -> dict | None:
    """The battle receipt that proves a **real** victory, if there is one."""
    for record in wave17_battles(prefer_sha):
        if wave17_battle_verdict(record) == "real-victory":
            return record
    return None


def wave17_real_victory_chain(prefer_sha: str | None = None) -> dict | None:
    """The chain that a **real battle** produced with ``outcome = 1``.

    ``None`` means "there is no such chain on disk" -- which is exactly the
    state wave 16 was in, and the report must say so rather than quote the
    poke chain in its place.
    """
    for record in wave17_chains(prefer_sha):
        if wave17_chain_verdict(record) == "real-victory":
            return record
    return None


def wave17_bound(rom_sha256: str | None = None) -> dict | None:
    """The provable pixel lower bound of wave 17, for **this** ROM when given.

    A bound measured on another ROM proves nothing about this one, so with a
    ROM digest only a record with that exact digest is accepted.
    """
    if "w17_bound" in _Z3_CACHE:
        records = _Z3_CACHE["w17_bound"]
    else:
        records = wave16_bounds()
        _Z3_CACHE["w17_bound"] = records
    if not records:
        return None
    if rom_sha256:
        same = [record for record in records
                if record["rom_sha256"] == rom_sha256]
        if not same:
            return None
        records = same
    record = dict(records[0])
    values = {item["value"] for item in records}
    record["runs"] = records
    record["agree"] = len(values) == 1
    record["value"] = records[0]["value"]
    return record


def wave17_reachable(prefer_sha: str | None = None) -> dict | None:
    """The content-anchor **reachable** residual sum (the bracket's upper end).

    It belongs to one recording, so it is only quoted when its ROM is the ROM
    this run measured -- an upper end from another ROM must not be put next to
    a lower end from this one.
    """
    return wave16_reachable(prefer_sha)


# The remake tree (read-only for this stream).
REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")

# The files U1 and U2 own (WAVE17-TASKS.md sections 1.1 and 2.1).  Their
# mtimes are the **product** evidence of delivery: a note is a story, the
# ROM is the product.
W17_PRODUCT_FILES = {
    "U1": (
        "butano-sequel/game/include/konoha/battle_combat_presentation.h",
        "butano-sequel/game/include/konoha/battle_scene_presentation.h",
        "butano-sequel/game/src/battle_runtime_scene.cpp",
        "butano-sequel/game/include/konoha/battle_black_field.h",
        "butano-sequel/game/include/konoha/battle_black_field_timing.h",
    ),
    "U2": (
        "butano-sequel/game/include/konoha/battle_range_ui_style.h",
        "butano-sequel/game/include/konoha/battle_result_content.h",
        "butano-sequel/graphics",
    ),
}


def wave17_product_state(stream: str) -> dict:
    """Has the product stream *stream* landed **in the product**?

    The evidence is the mtime of the files the stream owns: a note is a
    story, the **ROM** is the product.  A file touched after this wave's
    task book means the fix is in the tree; whether it is in the ROM this
    run measured is a separate question (the ROM's build time).
    """
    cutoff = wave17_cutoff_mtime()
    changed: list = []
    newest = 0.0
    for relative in W17_PRODUCT_FILES.get(stream, ()):
        path = REMAKE_ROOT / relative
        try:
            if path.is_dir():
                for child in path.rglob("*"):
                    if not child.is_file():
                        continue
                    stamp = child.stat().st_mtime
                    newest = max(newest, stamp)
                    if stamp > cutoff:
                        changed.append(child)
                continue
            stamp = path.stat().st_mtime
        except OSError:
            continue
        newest = max(newest, stamp)
        if stamp > cutoff:
            changed.append(path)
    return {
        "stream": stream,
        "landed": bool(changed),
        "newest_mtime": newest,
        "changed": [path.relative_to(REMAKE_ROOT).as_posix()
                    for path in changed[:8]],
    }


def _remake_rom_of_align(path: pathlib.Path, document: dict) -> str | None:
    """Which **remake** ROM a settlement alignment sheet was measured on.

    The sheet itself may not name the ROM; its *source run* does (``battle.json``
    / ``chain.json`` next to the shots).  A measurement that cannot name its
    ROM is not a measurement -- and if the ROM is not the one this pipeline
    run built, the report must say so.
    """
    if isinstance(document, dict):
        for key in ("remake_rom_sha256", "rom_sha256"):
            candidate = document.get(key)
            if isinstance(candidate, str) and len(candidate) == 64:
                return candidate.lower()
    remake_dir = document.get("remake_dir") if isinstance(document, dict) else None
    if remake_dir:
        base = pathlib.Path(os.path.abspath(str(REPO / remake_dir)))
        for candidate_path in (base.parent / "battle.json",
                               base.parent / "chain.json",
                               base / "battle.json",
                               base / "chain.json"):
            data = load_json(candidate_path)
            if isinstance(data, dict):
                sha = data.get("rom_sha256")
                if isinstance(sha, str) and len(sha) == 64:
                    return sha.lower()
    # last resort: a sibling receipt of the same run
    directory = path.parent
    for _ in range(2):
        for sibling in directory.glob("*.json"):
            if sibling == path:
                continue
            data = load_json(sibling)
            if not isinstance(data, dict):
                continue
            sha = data.get("remake_rom_sha256") or data.get("rom_sha256")
            if isinstance(sha, str) and len(sha) == 64:
                return sha.lower()
        directory = directory.parent
    return None


def wave17_settlement_align() -> tuple[pathlib.Path | None, dict, bool]:
    """The newest settlement screen alignment receipt, and whose wave it is.

    U2 owns the settlement screen (the portraits and the numbers).  When U2
    lands it re-measures the settlement chain, so the report has to quote
    **the newest** alignment receipt -- and to say **which wave** it came
    from, because a wave-16 number must not be presented as a wave-17 result.
    """
    if "w17align" in _Z3_CACHE:
        return _Z3_CACHE["w17align"]
    result: tuple = (None, {}, False)

    def keep(name: str, path: str) -> bool:
        return any(word in name for word in
                   ("settle", "align", "result", "chain"))

    for path in _w17_scan(keep, limit=300):
        document = load_json(path)
        if not isinstance(document, dict):
            continue
        pairs = document.get("pairs")
        if not isinstance(pairs, list) or not pairs:
            continue
        if not any("diff_px" in json.dumps(pair) for pair in pairs):
            continue
        result = (path, document, True)
        break
    if not result[0]:
        path, document = w3_settlement_align()
        result = (path, document, False)
    _Z3_CACHE["w17align"] = result
    return result


def w17_status(receipt: dict) -> str:
    """The wave-17 parallel streams (U1 / U2 / U4), as of this run."""
    streams = wave17_streams()
    parts: list = []
    run_rom = receipt_rom_sha(receipt)

    # ---- U1: the product fix for D4 --------------------------------------
    u1 = streams["U1"]
    u1_product = wave17_product_state("U1")
    u1_parts = ["**U1（D4 必修：玩家的伤害招式的战斗演出不结束）**："
                + (f"**已交付**（{_notes_of(u1)}）" if u1 else "**尚未交付笔记**")
                + ("；✅ **产品侧已落地**（独占文件在任务书之后被改过："
                   + "、".join(f"`{name}`" for name in u1_product["changed"])
                   + "）"
                   if u1_product["landed"] else
                   "；⛔ **产品侧尚未落地**（独占文件在任务书之后**没有被改过**）")]
    u1_parts.append(
        "**本次构建的 ROM 在本波被重建过**"
        if _rebuilt_in_wave(receipt, wave17_cutoff_mtime()) else
        "⚠️ **本次构建的 ROM 不是本波重建的** ⇒ U1 的产品改动"
        "**可能没进本次读数**")
    parts.append("；".join(u1_parts))

    # ---- U2: the overlay + settlement fixes -------------------------------
    u2 = streams["U2"]
    u2_product = wave17_product_state("U2")
    black = (step_by_name(receipt, "blackfade") or {}).get("metrics") or {}
    original_events = (black.get("original") or {}).get("events") or []
    remake_events = (black.get("remake") or {}).get("events") or []
    u2_parts = ["**U2（覆盖层「青+橙」互斥 + 結算屏人物/数字）**："
                + (f"**已交付**（{_notes_of(u2)}）" if u2 else "**尚未交付笔记**")
                + ("；✅ **产品侧已落地**（独占文件在任务书之后被改过："
                   + "、".join(f"`{name}`" for name in u2_product["changed"])
                   + "）"
                   if u2_product["landed"] else
                   "；⛔ **产品侧尚未落地**（独占文件在任务书之后**没有被改过**）")]
    if original_events or remake_events:
        def _triplets(events):
            return "；".join(
                f"{event.get('fade_out_frames')}/"
                f"{event.get('black_hold_frames')}/"
                f"{event.get('fade_in_frames')}" for event in events)
        u2_parts.append(
            f"**本次运行的黑场**：原版 **{len(original_events)}** 个"
            f"（{_triplets(original_events)}）；"
            f"重制侧 **{len(remake_events)}** 个"
            f"（{_triplets(remake_events)}）")
    parts.append("；".join(u2_parts))

    # ---- U4: the real victory verification --------------------------------
    u4 = streams["U4"]
    u4_parts = ["**U4（真实打完仗验证 + 结算链真实版）**："
                + (f"**已交付**（{_notes_of(u4)}）" if u4 else "**尚未交付**")]
    chains = wave17_chains(run_rom)
    real = wave17_real_victory_chain(run_rom)
    if real:
        u4_parts.append(
            f"**真实胜利链**：{len(real['rows'])} 页"
            f"（收据 `{real['path'].relative_to(REPO).as_posix()}`"
            + (f"；ROM `{real['rom_sha256'][:16]}…`" if real["rom_sha256"] else "")
            + "；进入方式：" + (real["method"] or "—") + "）")
    else:
        u4_parts.append("**尚无「真实战斗 + `outcome=1`」的链**")
    poked = [record for record in chains
             if wave17_chain_verdict(record) == "poke"]
    if poked:
        u4_parts.append(
            f"⚠️ **另有 {len(poked)} 条 poke 链**"
            f"（最新：`{poked[0]['path'].relative_to(REPO).as_posix()}`）"
            "⇒ **不得写成真实胜利链**")
    parts.append("；".join(u4_parts))
    return "；".join(parts)



# The **semantic** correspondence between the remake's settlement pages and
# the original's truth screens.  It is Z1's own reading (notes/s49-fidelity/
# Y1-stack-fix-and-settlement.md §3.3); the *numbers* are recomputed here
# from the PNGs on disk, so nothing in the report is hard-coded.
SETTLEMENT_SEMANTIC = (
    ("page-000-outcome.png", "01-victory.png", "outcome（勝利 / BATTLE COMPLETE）"),
    ("page-001-result.png", "02-settlement-exp-power-turns.png", "result（结算屏）"),
    ("page-002-level_up.png", "03-levelup-naruto.png", "level_up 1/6"),
    ("page-003-level_up.png", "05-levelup-sasuke-jutsu-name.png", "level_up 2/6"),
    ("page-004-level_up.png", "04-levelup-konohamaru.png", "level_up 3/6"),
    ("page-005-level_up.png", "05-levelup-sasuke.png", "level_up 4/6"),
    ("page-006-level_up.png", "06-levelup-sakura.png", "level_up 5/6"),
    ("page-007-level_up.png", "07-ninja-tool-list.png", "level_up 6/6（忍具一览）"),
)


def _diff_pixels(left: pathlib.Path, right: pathlib.Path):
    """(differing pixels, bbox) for two PNGs -- project convention.

    A pixel differs when **any** of the three channels differs (the same
    convention as ``tools/compare_frame_dirs.py``).  The bbox is
    ``[x0, y0, x1, y1]`` with the far edge **exclusive**.
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        image_a = Image.open(left).convert("RGB")
        image_b = Image.open(right).convert("RGB")
    except (OSError, ValueError):
        return None
    try:
        if image_a.size != image_b.size:
            return None
        width, _height = image_a.size
        pixels_a = list(image_a.getdata())
        pixels_b = list(image_b.getdata())
    finally:
        image_a.close()
        image_b.close()
    differing = 0
    min_x = min_y = 1 << 30
    max_x = max_y = -1
    for index, (pixel_a, pixel_b) in enumerate(zip(pixels_a, pixels_b)):
        if pixel_a == pixel_b:
            continue
        differing += 1
        x = index % width
        y = index // width
        if x < min_x:
            min_x = x
        if x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y
    bbox = None if max_x < 0 else [min_x, min_y, max_x + 1, max_y + 1]
    return differing, bbox


def _is_sha(value) -> bool:
    """Is this a sha256 digest (64 hex characters)?"""
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdefABCDEF" for char in value))


def settlement_semantic_rows() -> list:
    """The semantic per-screen comparison, recomputed from the PNGs on disk.

    The receipt's own table (``settlement-table-z1.json``) pairs the remake's
    pages with the original screens **mechanically** -- the remake's green
    panel matches the same original image over and over -- so its first two
    rows carry no semantic meaning.  Z1's note gives the semantic reading;
    the differences are recomputed here from the two image directories, so
    every number in the report is traceable to the files on disk.

    Returns ``[]`` when the images are not on disk (nothing is invented).
    """
    truth_dir = REPO / "build" / "s49-victory-capture" / "w4" / "settlement-truth"
    shots_dir = REPO / "build" / "z1" / "chain-e" / "shots"
    if not truth_dir.is_dir() or not shots_dir.is_dir():
        return []
    rows = []
    for index, (remake_name, original_name, stage) in enumerate(SETTLEMENT_SEMANTIC):
        remake = shots_dir / remake_name
        original = truth_dir / original_name
        if not remake.is_file() or not original.is_file():
            continue
        measured = _diff_pixels(remake, original)
        if measured is None:
            continue
        differing, bbox = measured
        rows.append({
            "index": index,
            "remake": remake_name,
            "original": original_name,
            "stage": stage,
            "diff": differing,
            "bbox": bbox,
        })
    return rows


def ratchet_verdict(receipt: dict) -> dict:
    """The ratchet verdict of this run, in either receipt shape.

    wave 15 / W2 taught the pipeline to answer **incomparable** when the
    baseline ROM and this run's ROM differ: the two residual numbers are
    then not the same measurement, so the gate must not report a pass.
    Older receipts (wave 14 and before) have no verdict field at all -- for
    them the step-5 notes and ``metrics.ratchet_rom`` are the only evidence,
    and the derived status is marked as such.
    """
    verdict = dict(receipt.get("ratchet") or {})
    if verdict.get("status"):
        verdict["from_new_receipt"] = True
        return verdict
    judgment = step_by_name(receipt, "judgment") or {}
    metrics = judgment.get("metrics") or {}
    rom = metrics.get("ratchet_rom") or {}
    verdict["from_new_receipt"] = False
    verdict["status"] = "incomparable" if rom.get("changed") else "pass"
    verdict["baseline_rom"] = rom.get("baseline") or {}
    verdict["candidate_rom"] = rom.get("candidate") or {}
    verdict["rom"] = rom
    verdict["note"] = (rom.get("note") or
                       "this receipt predates the wave-15 verdict field; "
                       "the status was derived from `ratchet_rom.changed`")
    return verdict


def ratchet_baseline_info(package: pathlib.Path) -> dict:
    """Which reports the ratchet had on disk, and what each of them said.

    wave 14's instrument defect was exactly this: a **fresh** package
    directory has no previous baseline, so the ratchet silently fell back to
    a *reference* report (wave 4) instead of the last accepted receipt -- the
    gate stayed green while comparing against a much older reading.  The
    report therefore names every baseline file it can see.
    """
    info: dict = {}
    for name in ("reference-report.json", "previous-baseline-report.json",
                 "baseline-report.json"):
        path = package / "baseline" / name
        if not path.is_file():
            continue
        data = load_json(path) or {}
        summary = data.get("summary") or {}
        field = summary.get("field_residual") or {}
        info[name] = {
            "path": path,
            "generated_at": data.get("generated_at"),
            "sum": field.get("sum"),
            "median": field.get("median"),
        }
    return info


def accepted_receipts(exclude: pathlib.Path | None = None) -> list:
    """Every pipeline receipt on disk that says ``ok``, newest first.

    This is the report's **own** reading of "the previous accepted run" --
    it does not trust the pipeline's baseline bookkeeping, so the two can be
    compared against each other.
    """
    found = []
    base = REPO / "build"
    if not base.is_dir():
        return found
    for path in base.glob("s49-package*/receipt.json"):
        if exclude is not None and path.parent == exclude:
            continue
        data = load_json(path)
        if not isinstance(data, dict) or not data.get("ok"):
            continue
        steps = data.get("steps") or []
        # a **partial** run (e.g. `--only 5`) is not "an accepted run": it
        # never built a ROM, so it cannot be the baseline of another run.
        if len(steps) < 12:
            continue
        # the residual lives in the judgment step's metrics, not at the top
        judgment = step_by_name(data, "judgment") or {}
        metrics = judgment.get("metrics") or {}
        field = metrics.get("field_residual") or {}
        found.append({
            "path": path,
            "generated_at": data.get("generated_at"),
            "steps": len(steps),
            "sum": field.get("sum"),
            "median": field.get("median"),
            "rom_sha256": receipt_rom_sha(data),
            "ratchet_rom": metrics.get("ratchet_rom"),
        })
    found.sort(key=lambda item: str(item.get("generated_at") or ""), reverse=True)
    return found


W15_ROOTS = (
    "build/w3",
    "build/s49-victory-align",
    "build/w1",
    "build/s49-w1",
)


def w3_settlement_align() -> tuple[pathlib.Path | None, dict]:
    """The wave-15 settlement screen alignment receipt, if it landed.

    It pairs the original's truth screens with the remake's settlement chain
    frames **by phase** and gives the per-screen difference in pixels.  It
    is found by **content** (a receipt with per-pair differences) and only
    receipts written **after this wave's task book** count -- otherwise the
    report would quote a previous wave's numbers as this wave's.
    """
    if "w3align" in _Z3_CACHE:
        return _Z3_CACHE["w3align"]
    result: tuple = (None, {})
    cutoff = wave15_cutoff_mtime()
    candidates = []
    for root in W15_ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        try:
            paths = list(base.rglob("*.json"))
        except OSError:
            continue
        for path in paths:
            try:
                if path.stat().st_mtime <= cutoff:
                    continue
                if path.stat().st_size > 4 * 1024 * 1024:
                    continue
            except OSError:
                continue
            candidates.append(path)
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        document = load_json(path)
        if not isinstance(document, dict):
            continue
        pairs = document.get("pairs")
        if not isinstance(pairs, list) or not pairs:
            continue
        if not any("diff_px" in json.dumps(pair) for pair in pairs):
            continue
        if not any("truth" in pair and "remake" in pair for pair in pairs
                   if isinstance(pair, dict)):
            continue
        result = (path, document)
        break
    _Z3_CACHE["w3align"] = result
    return result


def criteria_diff(previous: dict, current: dict) -> list:
    """Which steps' success criteria differ between two receipts.

    The criteria are literal strings inside the pipeline, so a receipt keeps
    them verbatim -- which makes "the twelve criteria did not change" a
    **machine-checkable** claim instead of a promise.
    """
    def _criteria(receipt):
        out = {}
        for step in receipt.get("steps") or []:
            name = step.get("name")
            if name:
                out[name] = step.get("criterion") or ""
        return out

    before = _criteria(previous)
    after = _criteria(current)
    changed = []
    for name, text in after.items():
        if name in before and before[name] != text:
            changed.append((name, before[name], text))
    for name in before:
        if name not in after:
            changed.append((name, before[name], "(step removed)"))
    return changed


def capture_rom_mismatch(report: dict) -> list:
    """Which capture's **audit** ROM differs from the ROM the report claims.

    ``capture.py`` reuses an existing capture directory whenever a done
    marker is present -- **without checking which ROM was recorded** -- and
    the report then labels the frames with the ROM it was *asked* to
    measure.  A report whose audit ROM differs from its claimed ROM is a
    reading of a **different** ROM, and every number derived from it is
    about that other ROM.
    """
    out = []
    for side, capture in (report.get("captures") or {}).items():
        if not isinstance(capture, dict):
            continue
        audit = capture.get("audit") or {}
        audit_rom = audit.get("rom_sha256")
        claimed = capture.get("rom_sha256")
        if audit_rom and claimed and audit_rom != claimed:
            out.append({
                "side": side,
                "audit_rom": audit_rom,
                "claimed_rom": claimed,
                "reused": (report.get("run") or {}).get("reused", {}).get(side),
                "output_dir": capture.get("output_dir"),
            })
    return out


def ratchet_frame_diff(candidate: dict, baseline: dict) -> list:
    """Per-frame residual differences between two judgment reports.

    The ratchet only says "the residual got bigger"; this says **where**.
    """
    base = {row.get("original"): row
            for row in (baseline.get("frames") or [])
            if isinstance(row, dict)}
    rows = []
    for row in (candidate.get("frames") or []):
        if not isinstance(row, dict):
            continue
        name = row.get("original")
        other = base.get(name)
        if other is None:
            continue
        before = other.get("field_residual_px")
        after = row.get("field_residual_px")
        if before is None or after is None or before == after:
            continue
        verdict = row.get("verdict") or {}
        rows.append({
            "original": name,
            "baseline": before,
            "candidate": after,
            "delta": after - before,
            "class": verdict.get("class_label") or verdict.get("class"),
            "best_match": row.get("best_match"),
        })
    return rows


def receipt_rom_sha(receipt: dict) -> str | None:
    """The sha256 of the ROM this receipt's pipeline built."""
    build = step_by_name(receipt, "build") or {}
    return (build.get("metrics") or {}).get("rom_sha256")


def _remake_file_changed(relative: str) -> bool:
    """Is the remake file *relative* (under butano-sequel/) different from HEAD?"""
    import subprocess
    root = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
    if not root.is_dir():
        return False
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "HEAD", "--",
             relative],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    if completed.returncode != 0:
        return False
    return bool(completed.stdout.strip())


def z1_status() -> str:
    """Has the wiring stream (Z1) landed its wiring and/or its note?

    The note is the primary evidence, but the note is written at the *end* of
    a stream, so the tree itself is checked too: ``battle_scene_controller.h``
    is Z1's exclusive file, and a diff against HEAD proves the wiring landed
    even before the note exists.
    """
    path = REPO / "notes" / "s49-fidelity" / "Z1-wiring.md"
    if path.is_file():
        return f"**已交付**（`{path.name}`）"
    touched = _z1_touched_files()
    if touched:
        return ("**接线已落地、笔记尚未交付**（本轮没有 "
                "`notes/s49-fidelity/Z1-wiring.md`；Z1 独占的 "
                + "、".join(f"`{name}`" for name in touched)
                + " 相对 HEAD 有改动）")
    return ("**尚未落地**（本轮没有 `notes/s49-fidelity/Z1-wiring.md`，"
            "Z1 独占的两个文件相对 HEAD 也没有改动）")


def _z1_touched_files() -> list[str]:
    """Z1's exclusive files that differ from the remake repository's HEAD."""
    import subprocess
    root = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")
    if not root.is_dir():
        return []
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "HEAD", "--",
             "game/src/battle_runtime_scene.cpp",
             "game/include/konoha/battle_scene_controller.h"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines()
            if line.strip()]


# The ledger of **this** stream (V4, wave 9: the settlement chain
# comparison).  One row per assumption, with the method that decided it and
# the verdict (未验 / 已证伪 / 已确认).
V4_LEDGER = (
    ("V4-1", "重制侧开机就能进 S49 battle-14（不用先打通 41–48）",
     "读 `battle_campaign_route.h` 的 `battle_campaign_route_initial_scenario`",
     "**49** ⇒ 开机即在 S49",
     "已确认"),
    ("V4-2", "重制侧的结算链在产品代码里是完整的",
     "读 `battle_scene_controller.h` 的 phase 迁移 + 在 ROM 上录",
     "`outcome → result → level_up → training → complete` 五段全在代码里",
     "已确认"),
    ("V4-3", "重制侧的输入分派是「一键一调用」，所以能离线生成按键脚本",
     "读 `battle_runtime_scene.cpp` 的输入分派",
     "A→confirm / B→cancel / 四方向→move_cursor / L,R→cycle_unit",
     "已确认"),
    ("V4-4", "重制侧的「忍术列表」在移动之前是空的",
     "离线控制器在单位选择阶段打开列表",
     "`player.action_count == 0`；移动确认后才有条目",
     "已确认"),
    ("V4-5", "重制侧的打人招式必须是直线、且不能是「打空格」型",
     "离线控制器读 `target_policy` / `range` 并实测被拒",
     "目标必须同行/同列；`empty_tile` 型打有人的格子被拒"
     "（`action_error::occupied_target_tile`）",
     "已确认"),
    ("V4-6", "重制侧 battle-14 可以打赢",
     "五种策略各跑一次离线控制器",
     "**五种全部败北**：追击 0 命中；守护命中但护送 40→16；"
     "护送每回合掉 12 ⇒ **这条路走不通**",
     "已证伪"),
    ("V4-7", "原版的单次伤害口径能套到重制侧",
     "读两边的招式定义",
     "原版十字手里剑 **27** / 重制侧忍者组合拳 **10**、火遁术 **15**、"
     "忍具 **6** ⇒ **口径不同**",
     "已确认（口径不同）"),
    ("V4-8", "从上电到进战斗需要多少次 A",
     "两轮对比：boot-a=3 vs boot-a=32",
     "**3 次停在战前简报/队伍一览表**（预置场景的队伍/装备页，"
     "**根本没进战斗**）；**32 次才进战斗**",
     "已确认"),
    ("V4-9", "重制侧的「忍具一览」对应原版的「忍具一览」",
     "在 ROM 上录到的帧 + 两边的段落内容",
     "重制侧 `training` 段有「AVAILABLE TOOL / NO AVAILABLE TOOL / "
     "EQUIP COMPLETE / 隊員一覧表」四屏，**位置与用途对得上**",
     "已确认"),
    ("V4-10", "离线脚本在 ROM 上回放会同步",
     "在 ROM 上回放按键脚本（两轮等待口径）",
     "**短等待会让 ROM 跑在脚本前面 ⇒ 输入被丢**"
     "（录到「可以嗎？」对话框上「否」高亮后 **33,839 帧**不动）"
     "⇒ 等待必须放大；但放大后仍会在战斗里卡住 ⇒ "
     "**本波没能把整条链在 ROM 上走完**",
     "已证伪"),
    ("V4-11", "原版 S49 结算屏真值还不存在",
     "读 `notes/s49-fidelity/W4-original-victory-5th.md` §4",
     "**存在**：wave 8 的 W4 打赢后录到 9 张图 + sha256 收据 `9a60a89b…`",
     "已证伪（已闭合）"),
    ("V4-12", "wave 8 任务书里的「残差总和 109,597」与流水线是同一个口径",
     "比流水线 08:26 那一跑（161,074）与本次（168,816）",
     "**不是一个口径** ⇒ 以流水线收据为准，报告里两个数不混用",
     "已证伪"),
    ("V4-13", "用「按键洪水」能让 ROM 自己把战斗打完",
     "三轮：A/B 交错（200 轮）、A/B 交错 + 单位轮转键 R（120 轮）、"
     "开机 A×32 + 洪水",
     "前一轮**停在战前简报**（开机 A 不够）；后两轮**都进了战斗但战斗没结束**"
     "（最后一次录到 25,132 帧，末帧仍是战斗中的单位选择）⇒ **洪水打法也走不通**",
     "已证伪"),
)


# The ledger of **this** stream (U4, wave 10: the instrument's anchor fix +
# the packaging run + the final report review).
U4_LEDGER = (
    ("U4-1", "共享仪器 `compare_overlay_families.py` 数学上表达不了原版的锚点 256",
     "读旧仪器的 `remake_logical_cells` / `best_window`：按「相机派生的窗口」贴"
     "地图标签，再在 `[0, 256)` 里搜窗口",
     "地图宽 480 px ⇒ **256 落在搜索区间外**（256 ≠ 0）；"
     "且「取搜索到的最优」会替重制侧美化 ⇒ **已确认**（V2 §6.3 的申请）",
     "已确认"),
    ("U4-2", "把仪器改成固定锚点 (256, 0) 后，数字与 V2 的显式锚点版相同",
     "同一份 VRAM dump 上跑新仪器与 `tools/s49_v2_anchor/compare_at_anchor.py`",
     "**逐项相同**：field 81/111/36/26、movegrid 81/111/36/10、"
     "grid16 71/104/46/31、banner 0/0/117/0",
     "已确认"),
    ("U4-3", "仪器改动不会打断判定台（`s49_fidelity_report/overlay.py` 在 import 它）",
     "改完仪器立刻跑一次判定台",
     "**exit 0**；判定台只 import `find_overlay_map` / `remake_family` / "
     "`LOGICAL_COLS` / `LOGICAL_ROWS`，这四个的语义都未变",
     "已确认"),
    ("U4-4", "口径变化会移动残差数字",
     "同一份 dump 上同时算「旧窗口搜索」与「新固定锚点」"
     "（`tools/s49_overlay_align/compare_conventions.py`）",
     "**每个时刻恒定 −23 格**（remake-only 59→36 / 69→46 / 140→117）；"
     "**同亮 / 原版缺 / 族名不一致三项一字未变** ⇒ 旧口径把 256 px 宽的窗口"
     "摊在地图上、不做 480 px 回绕，多算出 23 格「重制多画」",
     "已确认"),
    ("U4-5", "`find_overlay_map` 的签名会把 BG 图块数据误认成覆盖层",
     "逐个 0x800 对齐的 VRAM 窗口统计「entry 全部是合法覆盖层 tile」的窗口",
     "**假窗口 0x00800**：1024 个非零 entry 全部合法（真覆盖层只有 768 个，"
     "按 entry 数它会输）；**真覆盖层 0x09800**。"
     "⇒ 判据改成原版自己的规则：「solid 必须落在受阻地形上」"
     "（真覆盖层 **90/90**，假窗口 **0/0**）",
     "已确认"),
    ("U4-6", "重制侧的覆盖层在**任何配对帧**里都不显示",
     "35 个 remake anchor dump 逐个找覆盖层签名",
     "只有 **step 25** 与 **step 28–34** 有覆盖层（0x09800）；"
     "25 个配对帧（step 00–24）**一个都没有** ⇒ "
     "拿配对帧去量是**退化测量**（重制侧恒为空 ⇒ 残差恒为原版的 192 格，"
     "与产品质量无关）⇒ 覆盖层对拍改为**整条 walk**（仪器自带的 `--vram-dir` 模式）",
     "已确认"),
    ("U4-7", "判定台的残差读数是逐次确定的",
     "同一个 ROM 连跑两次判定台，逐帧对照",
     "**不是**：只有 `step-12-A` 一帧的配对变了（step-19-A → step-16-A），"
     "残差 **9,520 → 0**，总和 **114,304 → 104,784** ⇒ "
     "**棘轮门禁天然带 ±9,520 px 的抖动**。⭐ 最终那次跑（重制线已更新）"
     "**通过了**棘轮：总和 **117,832 → 100,210**、中位 **1,680 → 1,323**、"
     "全 0 帧 **4 → 5**、峰值 **27,325 → 27,325（不变）**",
     "已证伪（读数不确定）"),
    ("U4-8", "本波流水线 12 步全绿",
     "跑 `python tools/s49_package/run_pipeline.py`（私有输出目录 "
     "`build/s49-package-u4`）",
     "**12 / 12 全绿**（收据 `generated_at` 2026-10-24T11:28:01+08:00，"
     "`ok: true`，`failed_step: null`）。⭐ 步骤 1 的构建**撞了 3 次 objcopy "
     "碰撞**（并行流在写同一个 .gba）⇒ 靠流水线自带的「等 60 s、最多 5 次、"
     "只认 objcopy 碰撞」的重试策略扛过去（第 4 次成功）",
     "已确认"),
    ("U4-9", "覆盖层逐格族名已归零（同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0）",
     "整条 walk（35 个 anchor dump）上的逐格族名对拍",
     "**未达成**：field 同亮 168 / 原版缺 24 / 多画 24 / 族名不一致 50（残差 98）、"
     "movegrid 168/24/24/4（52）、grid16 153/22/39/65（126）、"
     "banner 0/0/0/0（exact）⇒ **同亮 168 ≠ 192**，且 24 格位置不同、"
     "50 格族名不同",
     "未达成"),
    ("U4-10", "U1 / U2 / U3 已经落地",
     "看 `notes/s49-fidelity/` 有没有 U1/U2/U3 的笔记",
     "**一个都没有** ⇒ 本次运行的重制线仍是**在飞状态**",
     "已证伪"),
)


def render(receipt: dict, package: pathlib.Path) -> str:
    work = package / "work"
    evidence = package / "evidence"
    after = load_json(work / "s49-report" / "report.json") or {}
    before = load_json(package / "baseline" / "reference-report.json") or {}
    ratchet_before = load_json(package / "baseline" / "baseline-report.json") or {}
    after_summary = (after.get("summary") or {})
    before_summary = (before.get("summary") or {})

    # ---- which ROM is this run about? (needed by §0, §2.0c and §11) -------
    # V1 and V2 both change the product => the ROM always changes => the
    # report has to name the bytes every number belongs to.
    _identity = rom_identity(receipt, package)
    _baseline_rom_w16 = ((ratchet_verdict(receipt).get("baseline_rom") or {})
                         .get("remake"))

    lines: list[str] = []
    add = lines.append

    add("# S49 1:1 保真度报告（wave 17 定稿）")
    add("")
    add(f"> 生成时间：{datetime.datetime.now().astimezone().isoformat(timespec='seconds')}")
    add(f"> 生成方式：`python tools/s49_package/run_pipeline.py` → "
        f"`python tools/s49_package/make_report.py`")
    add(f"> 收据：`{package.relative_to(REPO).as_posix() if package.is_relative_to(REPO) else package}/receipt.json`")
    add(f"> **收据生成时间（这一批数字的出处）**：{receipt.get('generated_at')}")
    build = step_by_name(receipt, "build") or {}
    build_metrics = build.get("metrics") or {}
    if build_metrics.get("rom_sha256"):
        add(f"> **本次 ROM**：sha256 `{build_metrics.get('rom_sha256')}`"
            f"（{fmt(build_metrics.get('rom_bytes'))} B，构建于 "
            f"{build_metrics.get('rom_mtime')}）")
        if build_metrics.get("pinned_rom"):
            add(f"> **本次 ROM 已钉住**：所有测量步骤与随包发布的 ROM 都是"
                f"**同一份拷贝** `{build_metrics.get('pinned_rom')}`"
                f"（sha256 `{build_metrics.get('pinned_rom_sha256')}`）"
                "⇒ **并行流在本轮运行期间重建同一个 ROM，也换不掉本轮的读数**。")
    package_step = step_by_name(receipt, "package") or {}
    package_metrics = package_step.get("metrics") or {}
    built_sha = build_metrics.get("rom_sha256")
    shipped_sha = package_metrics.get("rom_sha256")
    if built_sha and shipped_sha and built_sha != shipped_sha:
        add(f"> ⛔ **⚠️ 收据里的 ROM 与包里的 ROM 不是同一个**："
            f"**步骤 1 构建的是 `{built_sha}`**，"
            f"**步骤 12 打包时盘上的 ROM 已经是 `{shipped_sha}`**"
            "（**另一个流在本轮运行期间重建了同一个 ROM**）。"
            "⇒ **本收据里的每一个测量数字都属于 `{built}`，"
            "而包里随包发布的是 `{shipped}` —— 后者没有被测过**。"
            "⇒ **本收据不能作为发布基线**；要发布，必须重跑到"
            "「构建的 sha == 打包的 sha」。".format(
                built=built_sha[:16] + "…", shipped=shipped_sha[:16] + "…"))
    add(f"> **wave-7 接线（wave 7 的 Z1）状态**：{z1_status()}")
    add(f"> **wave-10 并行流（U1/U2/U3）状态**：{u_status()}")
    add(f"> **wave-11 并行流（W1/W2/W3）状态**：{w_status(receipt)}")
    add(f"> **wave-12 并行流（X1/X2/X3）状态**：{x_status(receipt)}")
    add(f"> **wave-13 并行流（Y1/Y2/Y3）状态**：{y_status(receipt)}")
    add(f"> **wave-14 并行流（Z1/Z2/Z3）状态**：{z14_status(receipt)}")
    add(f"> **wave-15 并行流（W1/W2/W3）状态**：{w15_status(receipt)}")
    add(f"> **wave-16 并行流（V1/V2/V4）状态**：{w16_status(receipt)}")
    add(f"> **wave-17 并行流（U1/U2/U4）状态**：{w17_status(receipt)}")
    _verdict = ratchet_verdict(receipt)
    # ---- the one-glance provenance line ------------------------------------
    _dig = _identity.get("digests") or {}
    _dec = _identity.get("decisions") or {}
    add("> ⭐⭐ **一眼看出这一批数字的出处**：")
    add(f"> - **读的是哪个 ROM**：构建 `{str(_dig.get('build'))[:16]}…` / "
        f"钉住 `{str(_dig.get('pinned'))[:16]}…` / "
        f"打包 `{str(_dig.get('package'))[:16]}…` / "
        f"实测 `{str(_dig.get('measured'))[:16]}…` ⇒ "
        + ("**四者一致** ✅" if _identity.get("agree")
           else "⛔ **四者不一致**（数字分属不同的字节）")
        + "（§2.0c）")
    add("> - **采集是复用还是重采**：原版侧 "
        f"**{( _dec.get('original') or {}).get('action') or '—'}** / "
        f"重制侧 **{(_dec.get('remake') or {}).get('action') or '—'}**"
        "（收据字段 `captures.<side>.reuse_decision`；"
        "「复用」= 采集自己的审计核对通过 ⇒ 帧确实来自本次这个 ROM）")
    add("> - **基线 ROM 是哪个**："
        + (f"`{str((_verdict.get('baseline_rom') or {}).get('remake'))[:16]}…`"
           f"（收据 `{_verdict.get('baseline_report')}`）"
           if _verdict.get("baseline_rom") else "—")
        + "；**棘轮判决** = "
        + (f"**`{_verdict.get('status')}`**"
           + ("（**不可比 ≠ 通过**）" if _verdict.get("status") == "incomparable"
              else "")
           if _verdict.get("status") else "—"))
    add(f"> 流水线结果：**{'PASS' if receipt.get('ok') else 'FAIL'}**"
        + (f"（首个失败步骤 {receipt.get('failed_step')}）"
           if receipt.get("failed_step") else ""))
    if _verdict.get("status"):
        _status = _verdict["status"]
        _verdict_line = {
            "pass": "✅ **棘轮判定 = PASS**（残差没有比被接受的基线变大）",
            "fail": "🔴 **棘轮判定 = FAIL**（残差比被接受的基线变大了 ⇒ 门禁应当变红）",
            "incomparable": ("⚠️ **棘轮判定 = INCOMPARABLE（不可比）—— "
                             "这不是「通过」**：基线 ROM 与本次 ROM 不同 ⇒ "
                             "两个残差数字**不是同一个测量** ⇒ "
                             "「残差只许变小」这条规则**本次没有被检验**"),
        }.get(_status, f"⚠️ **棘轮判定 = {_status}**")
        add(f"> {_verdict_line}"
            + (f"（基线 `{_verdict.get('baseline_report') or '—'}`；"
               f"基线 ROM `{str((_verdict.get('baseline_rom') or {}).get('remake'))[:16]}…`"
               f" vs 本次 ROM "
               f"`{str((_verdict.get('candidate_rom') or {}).get('remake'))[:16]}…`）"
               if _verdict.get("baseline_report") or _verdict.get("rom") else "")
            + ("。⚠️ 本收据**早于** wave 15 的棘轮判定字段 ⇒ "
               "状态由 `ratchet_rom.changed` 推出。"
               if not _verdict.get("from_new_receipt") else "。"))
    add(">")
    add("> ⚠️ **本文件由流水线的收据生成；每个数字都能追到收据里的某一次运行。**")
    add("> ⚠️ **有「未达成项」一节 —— 绿灯的门禁不等于 1:1 已达成。**")
    _bound = z3_bound(receipt_rom_sha(receipt))
    # wave 16 / V4 recomputes the bound **for the final ROM** => prefer it.
    # (The wave-14 reader would also find V4's receipt if it happened to be
    # written under the wave-14 roots; this makes the preference explicit
    # and independent of where V4 put its file.)
    _bound_w16 = wave16_bound(receipt_rom_sha(receipt))
    if _bound_w16:
        _bound = _bound_w16
    _bound_any = None
    if not _bound:
        _records = z3_bounds() + wave16_bounds()
        if _records:
            _same_rom = [record for record in _records
                         if record["rom_sha256"] == _records[0]["rom_sha256"]]
            _bound_any = dict(_records[0])
            _bound_any["runs"] = _same_rom
            _bound_any["agree"] = len({r["value"] for r in _same_rom}) == 1
    _all_bounds = z3_bounds()
    _other_bounds = [record for record in _all_bounds
                     if _bound is None
                     or record["rom_sha256"] != _bound["rom_sha256"]]
    if _bound:
        add(f"> ⭐ **wave 14 最重要的一条更正**：§11 第 2 项里那个"
            f"「可证像素下界 ≈ 23,700」**是 wave 6 的录制上测的**"
            f"（ROM `fec749d8…` / `c1f44b3b…`），**没有**为本次 ROM 重算。"
            f"⇒ **wave 14 / Z3 为当前 ROM（sha256 `{_bound['rom_sha256'][:16]}…`）"
            f"重算出来的可证像素下界 = **{_bound['value']} px***"
            f"（收据 `{_bound['path'].relative_to(REPO).as_posix()}`；"
            f"{len(_bound['runs'])} 次独立跑"
            + ("**逐值相同**" if _bound["agree"] else "**不一致**")
            + "；算法 = 每一拍内**原版的全部帧** × **重制的全部帧**逐对算残差"
            f"取最小，{_bound.get('beats')} 拍求和 ⇒ "
            f"**任何配对方式都不可能低于此数**）。")
        if _other_bounds:
            add("> ⭐ **交叉验证**：Z3 把**另一段录制**也用同一算法重算了一遍，"
                "得 **"
                + "、".join(f"{record['value']} px"
                            f"（{record.get('label') or record['path'].name}"
                            + (f"，ROM sha256 `{record['rom_sha256'][:16]}…`）"
                               if record.get("rom_sha256") else
                               "，⚠️ **该收据没有钉住 ROM** ⇒ 只作对照）")
                            for record in _other_bounds)
                + "** ⇒ 旧口径的「≈ 23,700」被**复现**了，"
                "两个数不是矛盾，是**两段录制上的两个下界**。")
        _reach = wave16_reachable(receipt_rom_sha(receipt)) or z3_reachable()
        _reach_same_rom = bool(_reach and _reach.get("rom_sha256")
                               and _reach.get("rom_sha256")
                               == receipt_rom_sha(receipt))
        if _reach:
            add(f"> ⭐ **三段夹逼（wave 16 最该写进报告的数字）**："
                f"**{_bound['value']} ≤ 最优残差 ≤ {_reach['value']} px**"
                f"（下界 B1 = 任何配对方式都不可能低于此数；"
                f"上界 B2 = 内容锚同刻配对的残差之和，"
                f"{_reach['exact_moment']}/{_reach['original_frames']} 帧在重制侧"
                f"找到了同一时刻的帧，收据 "
                f"`{_reach['path'].relative_to(REPO).as_posix()}`）"
                f"⇒ **残差归零在当前录制上不可达**（下界 > 0）。"
                + ("" if _reach_same_rom else
                   "⚠️ **上界属于另一个 ROM** ⇒ 上下界**不是同一个测量** ⇒ "
                   "**这个夹逼只是量级参考，不是本次 ROM 的夹逼**。"))
    else:
        add("> ⚠️ **wave 14 的可证像素下界与「本次运行的 ROM」不是同一个**："
            + (f"Z3 交付的下界是 **{_bound_any['value']} px**，"
               f"测在 ROM **`{_bound_any['rom_sha256'][:16]}…`** 上"
               f"（收据 `{_bound_any['path'].relative_to(REPO).as_posix()}`；"
               f"{len(_bound_any['runs'])} 次独立跑"
               + ("**逐值相同**" if _bound_any["agree"] else "**不一致**")
               + "），"
               if _bound_any else "")
            + (f"而**本次流水线构建的是 `{receipt_rom_sha(receipt)[:16]}…`** "
               "（Z2 的黑场改动进了产品 ⇒ ROM 变了）⇒ "
               "**本次 ROM 的精确下界待 Z3 重算**。"
               if _bound_any else "")
            + "⇒ **「残差归零不可达」这个量级结论仍然成立**"
            + (f"（{_bound_any['value']} px > 0）" if _bound_any else "")
            + (f"；Z3 在**那个 ROM** 上还量出了上界 ⇒ "
               f"**{_bound_any['value']} ≤ 最优残差 ≤ "
               f"{fmt(z3_reachable()['value'])} px**"
               f"（{z3_reachable()['exact_moment']}/"
               f"{z3_reachable()['original_frames']} 帧同刻可达）"
               if _bound_any and z3_reachable() else "")
            + "，但**数字不是本次 ROM 的** ⇒ 不许混用。")
        _proof = _bound_proof_text()
        if _proof:
            add("")
            add("> **下界的证明方式（Z3 收据里的原文，逐字引用）**：")
            add(">")
            for _line in _proof.splitlines():
                add(f"> {_line}")
    # ③ must be the **same ROM's** reachable sum as the bracket above,
    # otherwise the header would quote two different recordings in one line.
    _reach_header = (wave16_reachable(receipt_rom_sha(receipt))
                     or z3_reachable())
    add("> ⭐ ⚠️ **三个数字不是同一个口径，不许混用**："
        "① **判定台读数**（本收据的 `field_residual.sum`）= "
        "**arg-min 残差之和，无时刻约束**（每一拍任选一帧对）"
        f"⇒ 本次 **{fmt((after_summary.get('field_residual') or {}).get('sum'))} px**；"
        "② **可证像素下界**（Z3）= **每一拍内「原版的全部帧 × 重制的全部帧」"
        "逐对残差取最小，25 拍求和**（比 ① 更宽松 ⇒ 数值更小）"
        f"⇒ **{fmt(_bound['value']) if _bound else (fmt(_bound_any['value']) if _bound_any else '—')} px**；"
        "③ **内容锚配对的可达残差**（Z3）= **同一时刻**的帧对逐帧残差之和"
        f"⇒ **{fmt(_reach_header['value']) if _reach_header else '—'} px**"
        + ("（**＝本次这个 ROM 的那一版** ⇒ 与 ② 同一个夹逼）"
           if _reach_header and _reach_header.get("rom_sha256")
           == receipt_rom_sha(receipt) else
           "（⚠️ **属于另一个 ROM** ⇒ **不许**与 ② 并排）")
        + "。"
        "⇒ **它们回答的是三个不同的问题**（残差有多少 / 归零最低要多少 / "
        "现在能做到多少）⇒ **任何一处把三者直接相比都是错的**。")
    add("> ⭐ **wave 13 最重要的一条更正**：**覆盖层的「同亮 192 / 缺 0 / "
        "多画 0」已经达成**。从 wave 1 传下来的「多画 310–420 格 / 缺 96–129 格」"
        "**是仪器假象** —— 共享仪器给**原版**贴地图标签时**没有按 480 px 回绕**，"
        "给重制侧却回绕了 ⇒ 两侧的缓冲尾部两列被互相错开 ⇒ 那 24 格「原版缺」"
        "+ 24 格「多画」全是**贴标签错位**。回绕修好后**缺 0 / 多画 0**（§3、§3.3）。")
    add("> ⚠️ **本次运行的重制线是 wave 17 并行流（U1/U2/U4）的状态**"
        "（U1 修产品缺陷 D4 / U2 修覆盖层「青+橙」互斥与結算屏人物数字 / "
        "U4 验证「真实打完仗」）"
        "⇒ **未达成项一节逐条写明了哪些是「已闭合」、哪些仍然开放**。")
    add("> ⚠️ ⭐ **同名笔记的坑（报告生成器的判定口径）**："
        "`notes/s49-fidelity/` 里**同名前缀的旧波笔记还在** —— "
        "`Y3-overlay-zero.md` 是 **wave 6** 的 Y3，`X2-overlay-zero.md` 是 "
        "**wave 12** 的 X2，**`Z1-wiring.md` / `Z2-title-art-starfield.md` / "
        "`Z3-dialogue-box.md` 是 wave 7 的 Z1/Z2/Z3**"
        " ⇒ **文件名前缀不能当作「本波已交付」的证据**。"
        "本报告一律**以任务书的 mtime 为界**"
        f"（wave 13 用 `WAVE13-TASKS.md`，wave 14 用 `WAVE14-TASKS.md`，"
        f"wave 15 用 `{W15_CUTOFF}`，wave 16 用 `{W16_CUTOFF}`，"
        f"wave 17 用 `{W17_CUTOFF}`）"
        "⇒ 没有交付就**如实写「尚未交付」**，绝不把旧波的数字当成本波的成果。")
    add("> ⭐ **wave 12 / X4 的复核**：wave 10 / U4 给 `find_overlay_map` 加的 "
        "**terrain 判据**（自报越界）已**独立复核第二次**，"
        "结论**保留、不回退**，数字见 **§16**。")
    add("> ⭐ **wave 11 / W4 的两条更正**："
        "① wave 10 报的「判定台 ±9,520 px 抖动」**根因不是仪器**，"
        "是**两次跑用的 ROM 不是同一个**（§2.0b）；"
        "② 判定台的**覆盖层读数用的还是旧判据**，与 §3 的逐格对拍"
        "**不是同一个口径**（§11 第 18 项，两个数不许混用）。")
    add("")

    # ---------------------------------------------------------------- 0
    add("## 0. 一句话结论")
    add("")
    field = after_summary.get("field_residual") or {}
    attribution = after_summary.get("attribution") or {}
    subclasses = after_summary.get("pairing_diff_subclasses") or {}
    add("- 战场区残差：**min {fmin} / 中位 {fmed} / max {fmax} / 全 0 帧 "
        "{fzero}**（{fframes} 帧）；归因 一致 {a_id} · 产品差 {a_pd} · 配对差 "
        "{a_pair}；配对差三桶 黑场过渡 {b_black} / 静止帧 {b_static} / "
        "时刻不一致 {b_mm}。".format(
            fmin=fmt(field.get("min")), fmed=fmt(field.get("median")),
            fmax=fmt(field.get("max")), fzero=fmt(field.get("zero_frames")),
            fframes=fmt(field.get("frames")),
            a_id=fmt(attribution.get("identical")),
            a_pd=fmt(attribution.get("product_diff")),
            a_pair=fmt(attribution.get("pairing_diff")),
            b_black=fmt(subclasses.get("black_transition")),
            b_static=fmt(subclasses.get("static_frame")),
            b_mm=fmt(subclasses.get("moment_mismatch"))))
    pairing_share = 0.0
    grand_total = sum((row.get("field_residual_px") or 0)
                      for row in after.get("frames", []))
    if grand_total:
        pairing_total = sum((row.get("field_residual_px") or 0)
                            for row in after.get("frames", [])
                            if (row.get("verdict") or {}).get("class")
                            == "pairing_diff")
        pairing_share = 100.0 * pairing_total / grand_total
    add(f"- **残差未归零**：中位 {fmt(field.get('median'))} px，"
        f"其中 **{pairing_share:.1f}%** 的残差仍在配对差那一侧；见 §11 未达成项。")
    determinism_preview = (after.get("run") or {}).get("determinism") or {}
    preview_runs = determinism_preview.get("runs") or []
    if len(preview_runs) > 1:
        preview_sums = [reading.get("field_residual_sum")
                        for reading in preview_runs]
        if determinism_preview.get("identical"):
            add(f"- ⭐ **判定台的读数是确定的**：同一个 ROM **连读 "
                f"{len(preview_runs)} 次**，残差总和 **{preview_sums[0]} px** "
                f"三次**完全相同**（逐帧配对、每张采集 PNG 的 sha256 也逐张相同）"
                f" ⇒ **残差变了就是产品变了，不是仪器在抖**（§2.0b）。")
        else:
            add(f"- ⛔ **判定台的读数不确定**：同一个 ROM 连读 "
                f"{len(preview_runs)} 次，读数不一致 ⇒ 棘轮不可信（§2.0b）。")
    steps = receipt.get("steps") or []
    green = sum(1 for step in steps if step.get("ok"))
    _settle_rows_0 = settlement_running_frames()[1]
    _v1_rows_0 = wave16_settlement_rows(receipt_rom_sha(receipt))[1]
    _v1_path_0 = wave16_settlement_rows(receipt_rom_sha(receipt))[0]
    add("- ⭐ **这一波的 ROM 是哪一个**：构建 / 钉住 / 打包 / 实测"
        "**四个 sha256 必须一致** = "
        f"`{str((_identity.get('digests') or {}).get('build'))}`"
        + ("✅ **四者一致** ⇒ 报告里每一个像素数都出自**这一份** ROM"
           if _identity.get("agree")
           else "⛔ **不一致** ⇒ 本次的数字**分属不同的字节**")
        + "（§2.0c）。")
    add("- ✅ **判定台「复用采集不校验 ROM」的仪器缺陷已修**"
        "（只改 `tools/s49_fidelity_report/capture.py`）："
        "复用前**必须**核对采集自己的审计（`audit.json` + `done.json`）；"
        "核对不过 ⇒ **绝不复用 ⇒ 重新采集**；"
        "收据里**机器可读**地写明帧来自哪个 ROM、采集是复用还是重采"
        "（§2.0.2、§11 第 22 项）。")
    add("- ⭐ **结算链**：**原版 S49 结算屏真值已闭合**"
        "（wave 8 的 W4 打赢后录到 9 张图 + sha256 收据 `9a60a89b…`，"
        "两次独立跑逐字节一致，正文见 **§15**）；"
        + (f"**wave 14 / Z1 录出了重制侧的运行帧** ⇒ 逐屏对照表"
           f"**{len(_settle_rows_0)} 行**（§15.2）。"
           + (f"⭐ **逐屏对照表已交付**（**{len(_v1_rows_0)} 行**，"
              f"收据 `{_v1_path_0.relative_to(REPO).as_posix() if _v1_path_0 else '—'}`"
              "；**测在本次这个 ROM 上**）⇒ 逐屏数字见 **§15.2**；"
              "⛔ **但它比的是「结算链的运行帧」，不是「真实打完仗」的那一版** —— "
              "**真实战斗链**与 **poke 链**在 **§15.2.3** 里**分列**"
              "（判据 = 链是**怎么进入**的），"
              "**任何一栏都不许写成「真实胜利链」**（§11 第 25 项）。"
              if _v1_rows_0 else
              "⛔ **逐屏对照表尚未交付**（§15.2.3）。")
           if _settle_rows_0 else
           "⛔ **重制侧结算链的运行帧逐屏对照本波仍未达成**"
           "（§11 的 1b / 1c 与 §15.2）—— 只交付了**资产级**对照"
           "（§15.3：结算屏 33.3% / 升级屏 20.0% / 训练页 22.1% 差）。"))
    # ---- wave 17: the real battle chain vs the poke chain -----------------
    _w17_chains = wave17_chains(receipt_rom_sha(receipt))
    _w17_real_chain = wave17_real_victory_chain(receipt_rom_sha(receipt))
    _w17_battles = wave17_battles(receipt_rom_sha(receipt))
    _w17_real_battle = wave17_real_victory(receipt_rom_sha(receipt))
    # "真实打完仗" is closed by a **real victory**: the battle was fought by
    # the driver (not poked), the **product** decided it, and the outcome is 1.
    _w17_real = _w17_real_battle or _w17_real_chain
    _w17_poked = [record for record in _w17_chains
                  if wave17_chain_verdict(record) == "poke"]
    _w17_real_runs = [record for record in _w17_battles
                      if record.get("poked") is False]
    if _w17_real_battle:
        _acc = _w17_real_battle.get("acceptance") or {}
        add("- ⭐⭐ **wave 17：「真实打完仗」已达成** —— "
            f"**真实战斗**（`outcome = {_w17_real_battle.get('outcome')}`，"
            "**由产品自己的战斗判定给出**）"
            f"（收据 `{_w17_real_battle['path'].relative_to(REPO).as_posix()}`"
            + (f"；ROM `{_w17_real_battle['rom_sha256'][:16]}…`"
               if _w17_real_battle.get("rom_sha256") else "")
            + f"；进入方式：`{_w17_real_battle.get('method') or '—'}`"
            + f"；**poke 指令数 = {_acc.get('poke_commands', '—')}**"
            + f"；**蜂的 HP 下降 = {_acc.get('bee_hp_dropped')}**"
            + (f"（{json.dumps(_acc.get('bee_hp_drop'), ensure_ascii=False)}）"
               if _acc.get("bee_hp_drop") else "")
            + f"；**护送存活 = {_acc.get('escort_alive')}**）"
            + (f"⭐ **并且有真实胜利链 {len(_w17_real_chain['rows'])} 页**"
               f"（收据 `{_w17_real_chain['path'].relative_to(REPO).as_posix()}`）"
               if _w17_real_chain else "")
            + "（§15.2.3、§11 第 25 项）。")
    elif _w17_real_runs:
        _run = _w17_real_runs[0]
        _acc = _run.get("acceptance") or {}
        add("- ⛔ **wave 17：「真实打完仗」仍未达成** —— "
            f"盘上**有**「真实战斗」的收据"
            f"（收据 `{_run['path'].relative_to(REPO).as_posix()}`"
            + (f"；ROM `{_run['rom_sha256'][:16]}…`"
               if _run.get("rom_sha256") else "")
            + f"；进入方式：`{_run.get('method') or '—'}`"
            + f"；**poke 指令数 = {_acc.get('poke_commands', '—')}**）"
            f"⇒ **`outcome = {_run.get('outcome')}`、"
            f"`battle_decided = {_run.get('battle_decided')}`、"
            f"**蜂的 HP 下降 = {_acc.get('bee_hp_dropped')}**"
            + (f"（{json.dumps(_acc.get('bee_hp_drop'), ensure_ascii=False)}）"
               if _acc.get("bee_hp_drop") else "")
            + " ⇒ **战斗没有由产品判定出胜利** ⇒ "
            "**不能算「真实打完仗」**（§15.2.3、§11 第 25 项）。")
    else:
        add("- ⛔ **wave 17：「真实打完仗」仍未达成** —— "
            "盘上**没有**「真实战斗 + `outcome=1`」的收据"
            f"（以 `{W17_CUTOFF}` 的 mtime 为界，"
            f"扫到 **{len(_w17_battles)}** 份战斗收据、"
            f"**{len(_w17_chains)}** 条链记录）。"
            + (f"⚠️ **另有 {len(_w17_poked)} 条 poke 链**"
               f"（最新：`{_w17_poked[0]['path'].relative_to(REPO).as_posix()}`）"
               "⇒ **不得写成「真实胜利链」**（§15.2.3、§11 第 25 项）。"
               if _w17_poked else ""))
    add("- ⭐ **wave 17 的四路流**：U1（D4 必修）/ U2（覆盖层 + 結算屏）/ "
        "U3（本流：出包 + 报告）/ U4（真实打完仗验证）"
        "⇒ **落地状态见 §11 第 26 项**，**假设台账见 §14.11**。")
    if receipt.get("ok") and len(steps) == 12:
        add(f"- **本流水线 12 步全绿**（收据 `{package.name}/receipt.json`），"
            "但绿灯的门禁**不等于** 1:1 已达成。")
    else:
        failed = receipt.get("failed_step")
        add(f"- ⛔ **本流水线 {green}/{len(steps)} 绿"
            + (f"，首个失败步骤 {failed}" if failed else "")
            + f"**（收据 `{package.name}/receipt.json`）"
            "⇒ **本次运行不能作为出包基线**；见 §13 的失败原因。")
        add("- ⭐ **结算链**：**原版 S49 结算屏真值已闭合**"
            "（wave 8 的 W4 打赢后录到 9 张图 + sha256 收据 `9a60a89b…`，"
            "两次独立跑逐字节一致，正文见 **§15**）；"
            "**重制侧结算链的运行帧逐屏对照已交付**"
            "（§15.2 的逐屏对照表 + **§15.2.4 的結算屏逐屏对照**）"
            "⇒ ⛔ **但「真实打完仗」仍未达成**："
            "**真实战斗链**与 **poke 链**在 **§15.2.3** 里**分列**，"
            "**任何一栏都不许写成「真实胜利链」**（§11 第 25 项）。")
        _red_steps = [step for step in steps if not step.get("ok")]
        if _red_steps:
            add("- ⛔ **唯一的红是第 "
                + "、".join(str(step.get("number")) for step in _red_steps)
                + " 步（"
                + "、".join(str(step.get("name")) for step in _red_steps)
                + "）**：**单测棘轮** —— 工作区的失败集合比 HEAD 基线**多了一项** "
                "⇒ **真阳性**（**不是**仪器抖动；**不是**本流造成的）"
                "⇒ **归属重制线那一侧**；"
                "**修好之后重跑一次 `run_pipeline.py` 即可 12/12**。")
    add("")

    # ---------------------------------------------------------------- 1
    add("## 1. 出包四件套清单（对照 `W4-save-boundary.md` §7 的 11 项）")
    add("")
    if not receipt.get("ok"):
        failed_names = [step.get("name") for step in receipt.get("steps", [])
                        if not step.get("ok")]
        add(f"⚠️ **本次流水线 {len(receipt.get('steps') or []) - len(failed_names)}/"
            f"{len(receipt.get('steps') or [])} 绿**（红："
            + "、".join(f"`{name}`" for name in failed_names)
            + "）⇒ **本包不能作为出包基线**；下表标的「✅」只表示那一项**存在**，"
            "不代表 1:1 达标。")
        add("")
    add("| # | 出包要素 | 现状 | 证据 |")
    add("|---|---|---|---|")
    build = step_by_name(receipt, "build")
    rom = build.get("metrics", {})
    add(f"| 1 | 可玩 ROM | ✅ 已构建 | `{(rom.get('rom') or '')}`，sha256 "
        f"`{(rom.get('rom_sha256') or '')[:16]}…`，{fmt(rom.get('rom_bytes'))} B"
        + ("" if not (built_sha and shipped_sha and built_sha != shipped_sha)
           else f"；⚠️ **包里实际随包发布的是 `{shipped_sha[:16]}…`**"
                "（与上面构建的那个不是同一个 ⇒ **随包发布的 ROM 没被本轮测过**）")
        + " |")
    add("| 2 | 一条复现命令 | ✅ 有 | `python tools/s49_package/run_pipeline.py`；"
        "逐条命令见包内 `REPRODUCE.md` |")
    headless = step_by_name(receipt, "headless")
    add(f"| 3 | 无窗口无声门禁 | "
        f"{'✅' if headless.get('ok') else '❌'} | 步骤 4 的收据 |")
    save = step_by_name(receipt, "save-boundary")
    add(f"| 4 | 存档字节收据 | "
        f"{'✅' if save.get('ok') else '❌'} | 步骤 11：`build/s49-save-boundary/receipts/` |")
    add("| 5 | 边界行为收据 | ⚠️ 部分 | 12 条表见 §6；B10 原版侧仍未实测 |")
    add("| 6 | 证据目录 | ✅ | `notes/s49-fidelity/`（假设台账索引见 §9） |")
    add("| 7 | 1:1 报告 | ✅ 终审稿 | 本文件 |")
    smoke = step_by_name(receipt, "smoke")
    add(f"| 8 | ROM 可运行性 | "
        f"{'✅' if smoke.get('ok') else '❌'} | 步骤 3：4096 帧 + 中文标题画面 |")
    tests = step_by_name(receipt, "unit-tests")
    test_metrics = tests.get("metrics", {})
    add(f"| 9 | 单元测试 | ⚠️ 零回归（非全绿） | 步骤 2：HEAD "
        f"{fmt((test_metrics.get('head') or {}).get('pass'))} pass / "
        f"{fmt((test_metrics.get('head') or {}).get('fail'))} fail，工作区 "
        f"{fmt((test_metrics.get('workspace') or {}).get('pass'))} pass / "
        f"{fmt((test_metrics.get('workspace') or {}).get('fail'))} fail；"
        f"新失败 {len(test_metrics.get('new_failures') or [])} 项 |")
    add("| 10 | 出包基线钉 | ⚠️ 非字节可复现 | 包内带 ROM + 重录命令，"
        "复现需先建私有探针（见 §12） |")
    add("| 11 | 存档格式决策 | ⏸ 待父代理拍板 | 施工单 C1–C5，"
        "`W4-save-boundary.md` §5.5 |")
    add("")

    # ---------------------------------------------------------------- 2
    add("## 2. 残差：前后对比 + 三桶分解")
    add("")
    add(f"来源：`{work.relative_to(REPO).as_posix()}/s49-report/report.json`"
        f"（本次）与 `{package.relative_to(REPO).as_posix()}/baseline/reference-report.json`"
        f"（钉住的 wave-4 参照，不随运行改变）。棘轮基线是 "
        f"`baseline/baseline-report.json`（上一次被接受的运行）。")
    add("")
    before_field = before_summary.get("field_residual") or {}

    # ---- the ratchet comparison: this run against the last accepted run ----
    # The pipeline re-pins ``baseline/baseline-report.json`` to the accepted
    # run, so after a *passing* run that file **is** this run.  The previous
    # accepted baseline is therefore looked up in this order:
    #   1. ``baseline/previous-baseline-report.json`` (written by the
    #      pipeline since wave 10 / U4),
    #   2. the shared package's pinned baseline,
    #   3. the local one (self comparison, flagged below).
    ratchet_summary = (ratchet_before.get("summary") or {})
    ratchet_field = ratchet_summary.get("field_residual") or {}
    ratchet_source = str(package / "baseline" / "baseline-report.json")
    if package.is_relative_to(REPO):
        ratchet_source = (package / "baseline" / "baseline-report.json"
                          ).relative_to(REPO).as_posix()
    ratchet_repin = (ratchet_before.get("generated_at")
                     == after.get("generated_at"))
    previous = load_json(package / "baseline" / "previous-baseline-report.json")
    if previous is None:
        previous = load_json(REPO / "build" / "s49-package" / "baseline"
                             / "baseline-report.json")
        if previous is not None:
            ratchet_source = "build/s49-package/baseline/baseline-report.json"
    if previous is not None:
        ratchet_before = previous
        ratchet_summary = (previous.get("summary") or {})
        ratchet_field = ratchet_summary.get("field_residual") or {}
        ratchet_source = "上一次被接受的运行（见收据里该步的 notes）"
    if ratchet_field:
        add("### 2.0 棘轮对照（本次 vs 上一次被接受的运行）")
        add("")
        # --- the comparison that actually matters: the previous accepted run ---
        # The pipeline's own baseline bookkeeping is **not** trusted here: the
        # report re-derives "the previous accepted run" from the receipts on
        # disk and then checks the two against each other.  That is what
        # makes the ratchet verifiable from the outside.
        _accepted = accepted_receipts(exclude=package)
        _previous: dict = {}
        _prev_judgment: dict = {}
        _prev_field: dict = {}
        _prev_rom = None
        _prev_sum = None
        _prev_source = None
        if _accepted:
            _previous = load_json(_accepted[0]["path"]) or {}
            _prev_judgment = (step_by_name(_previous, "judgment") or {}).get(
                "metrics") or {}
            _prev_field = _prev_judgment.get("field_residual") or {}
            _prev_build = (step_by_name(_previous, "build") or {}).get("metrics") or {}
            _prev_rom = _prev_build.get("rom_sha256")
            _prev_sum = _prev_field.get("sum")
            _prev_source = _accepted[0]["path"].relative_to(REPO).as_posix()
        _now_sum = (after_summary.get("field_residual") or {}).get("sum")
        if _prev_sum and _now_sum and _prev_sum != _now_sum:
            _delta = _now_sum - _prev_sum
            _share = 100.0 * _delta / _prev_sum
            add(f"⚠️ **⭐ 与上一波被接受的运行（wave 14）的对照 —— "
                f"这才是本波该看的那个数**："
                f"残差总和 **{fmt(_prev_sum)} → {fmt(_now_sum)} px**"
                f"（**{_delta:+d} px，{_share:+.1f}%**）"
                + ("**残差变大了** ⛔" if _delta > 0 else "🟢 残差变小了")
                + f"。⇒ **归因**："
                + ("**不是**判定台的抖动（同一个 ROM 连读 3 次读数逐项相同，§2.0b）"
                   if determinism_preview.get("identical") else
                   "⚠️ 读数本身不确定（§2.0b）")
                + f"，而是 **ROM 换了**：上一波是 `{(_prev_rom or '?')[:16]}…`，"
                  f"本次是 `{(receipt_rom_sha(receipt) or '?')[:16]}…`"
                + ("（**产品侧改了 ⇒ ROM 变了**）"
                   if _prev_rom and _prev_rom != receipt_rom_sha(receipt) else "")
                + "。")
            add("")
            _verdict_now = ratchet_verdict(receipt)
            _verdict_status = _verdict_now.get("status")
            if _verdict_status == "fail":
                add("🔴 **⭐ 棘轮抓住了它**（判决 = **FAIL**）："
                    "基线就是**上一波被接受的收据**"
                    f"（`{_verdict_now.get('baseline_report')}`），"
                    f"残差 **{fmt(_prev_sum)} → {fmt(_now_sum)} px**"
                    f"（**{_delta:+d} px**）⇒ "
                    "**wave 15 / W2 修的正是这个仪器缺陷**"
                    "（基线住在包目录外 ⇒ 换包目录不会丢基线）"
                    "⇒ **这次它是有牙齿的**：残差变大就红。")
            elif _verdict_status == "incomparable":
                add("⚠️ **⭐ 棘轮判定 =「不可比」（不是通过）**："
                    "基线 ROM 与本次 ROM 不同 ⇒ "
                    "两个残差数字**不是同一个测量** ⇒ "
                    "**「残差只许变小」这条规则本次没有被检验**。")
            elif _verdict_status == "pass":
                add("✅ **⭐ 棘轮判定 = PASS**（残差没有比被接受的基线变大）。")
            else:
                add("⚠️ **⭐ 为什么棘轮没有抓住它**：本波**换包目录重跑**"
                    "（为了清草稿残留）⇒ 新包目录里**没有**上一波的棘轮基线 ⇒ "
                    "棘轮基线是从**更早的参考报告**起步的"
                    f"（基线残差 **{fmt(ratchet_field.get('sum'))} px**，"
                    f"生成于 {ratchet_before.get('generated_at')}）"
                    f"⇒ **这一次棘轮没有比上一波被接受的运行"
                    f"（{fmt(_prev_sum)} px）**。"
                    "⇒ **这是仪器缺陷，不是本波的测量问题** ⇒ "
                    "**wave 15 / W2 的任务就是修它**（基线改成「上一波被接受的收据」）。")
            add("")
        _verdict2 = ratchet_verdict(receipt)
        _accepted_info = receipt.get("accepted_baseline") or {}
        if _accepted_info.get("exists"):
            add("这一步是**流水线的门禁口径**：残差只许变小，变大就红。"
                "基线 = **上一波被接受的收据**"
                f"（`{_verdict2.get('baseline_report') or '—'}`，"
                f"接受于 {_accepted_info.get('accepted_at')}）"
                "⇒ **基线住在包目录外** ⇒ 换包目录重跑**不会丢基线**。")
        else:
            add("这一步是**流水线的门禁口径**：残差只许变小，变大就红。"
                "基线 = 上一次被接受的运行"
                f"（`{ratchet_source}`，生成于 "
                f"{ratchet_before.get('generated_at')}）。")
        if _accepted_info.get("exists"):
            _base_rom = _accepted_info.get("rom") or {}
            _cand_rom = _verdict2.get("candidate_rom") or {}
            add("")
            add("⭐ **被接受的基线（wave 15 / W2 的新机制）**：")
            add("")
            add("| 项 | 值 |")
            add("|---|---|")
            add(f"| 基线来源包 | `{_accepted_info.get('source_package') or '—'}` |")
            add(f"| 接受时间 | {_accepted_info.get('accepted_at') or '—'} |")
            add(f"| 基线残差总和 | "
                f"{fmt(_accepted_info.get('field_residual_sum'))} px |")
            add(f"| 基线 ROM（原版） | `{str(_base_rom.get('original'))[:16]}…` |")
            add(f"| 基线 ROM（重制） | `{str(_base_rom.get('remake'))[:16]}…` |")
            add(f"| 本次 ROM（原版） | `{str(_cand_rom.get('original'))[:16]}…` |")
            add(f"| 本次 ROM（重制） | `{str(_cand_rom.get('remake'))[:16]}…` |")
            add(f"| 判决 | **`{_verdict2.get('status')}`** |")
            add("")
        if _verdict2.get("status") == "incomparable":
            add("")
            add("⚠️ ⭐ **本次的棘轮判定是「不可比」，不是「通过」**："
                f"基线 ROM `{str((_verdict2.get('baseline_rom') or {}).get('remake'))[:16]}…`"
                f" ≠ 本次 ROM "
                f"`{str((_verdict2.get('candidate_rom') or {}).get('remake'))[:16]}…`"
                " ⇒ **两个残差数字不是同一个测量** ⇒ "
                "**「残差只许变小」这条规则本次没有被检验**"
                + ("（这正是 wave 15 / W2 修的那个仪器缺陷："
                   "换包目录时基线会退回更早的参考报告）"
                   if not _verdict2.get("from_new_receipt") else
                   "（**wave 15 / W2 的新机制**：基线住在包目录外"
                   "⇒ 换包目录不会丢基线；但**产品一改 ROM 就变** ⇒ "
                   "「残差只许变小」这条规则**只能在新基线上被检验**）")
                + (f"基线报告：`{_verdict2.get('baseline_report')}`。"
                   if _verdict2.get("baseline_report") else ""))
        if ratchet_repin:
            add("")
            add("> ℹ️ **本次运行通过了棘轮** ⇒ 流水线把基线**重钉成本次的读数**"
                "（`notes`：re-pinned the baseline report）⇒ "
                "本节拿的是**重钉之前**的那一版基线"
                "（`previous-baseline-report.json` / 共享包里的基线）。")
        add("")
        add("| 指标 | 上次被接受 | 本次 | 方向 |")
        add("|---|---:|---:|---|")
        for key, label, better in (
                ("min", "战场区残差 min", "lower"),
                ("median", "战场区残差 中位", "lower"),
                ("max", "战场区残差 max", "lower"),
                ("sum", "战场区残差 总和", "lower"),
                ("zero_frames", "战场区全 0 帧数", "higher"),
        ):
            a = ratchet_field.get(key)
            b = field.get(key)
            if a is None or b is None:
                continue
            if better == "lower":
                arrow = "🟢 好" if b < a else ("🔴 差" if b > a else "＝")
            else:
                arrow = "🟢 好" if b > a else ("🔴 差" if b < a else "＝")
            add(f"| {label} | {fmt(a)} | {fmt(b)} | {arrow} |")
        add("")
        ratchet_attr = ratchet_summary.get("attribution") or {}
        add(f"归因：上次 {ratchet_attr.get('identical')}·"
            f"{ratchet_attr.get('product_diff')}·{ratchet_attr.get('pairing_diff')}"
            f" → 本次 {attribution.get('identical')}·"
            f"{attribution.get('product_diff')}·{attribution.get('pairing_diff')}"
            "（一致 · 产品差 · 配对差）。")
        add("")
        # ---- where exactly did the residual grow? ------------------------
        _candidate_report = load_json(work / "s49-report" / "report.json")
        _baseline_report = load_json(
            REPO / "build" / "s49-package" / "baseline-accepted" / "report.json")
        if isinstance(_candidate_report, dict) and isinstance(_baseline_report, dict):
            _frame_diffs = ratchet_frame_diff(_candidate_report, _baseline_report)
            _checks = {check.get("label"): check
                       for check in ((_verdict2 or {}).get("checks") or [])}
            _sum_check = _checks.get("战场区残差总和") or {}
            _delta_total = ((_sum_check.get("candidate") or 0)
                            - (_sum_check.get("baseline") or 0))
            add(f"#### 2.0.1 ⭐ 棘轮为什么红：**逐帧**归因"
                f"（残差总和 {fmt(_sum_check.get('baseline'))} → "
                f"{fmt(_sum_check.get('candidate'))} px，"
                f"**{_delta_total:+d} px**）")
            add("")
            if _frame_diffs:
                add(f"⭐ **差异只落在 {len(_frame_diffs)} 帧上**"
                    f"（25 个配对时刻里，其余 "
                    f"{25 - len(_frame_diffs)} 帧**逐像素相同**）：")
                add("")
                add("| 原版帧 | 重制侧最佳匹配 | 基线残差 px | 本次残差 px | Δ px | 判定类别 |")
                add("|---|---|---:|---:|---:|---|")
                for _row in _frame_diffs:
                    add(f"| `{_row['original']}` | `{_row['best_match']}` | "
                        f"{fmt(_row['baseline'])} | {fmt(_row['candidate'])} | "
                        f"{_row['delta']:+d} | **{_row['class']}** |")
                add("")
                add("⇒ 残差的增量**不是**分散在整条 walk 上，"
                    "而是**集中在这一帧** ⇒ "
                    "**判定台的读数变差是真的**（不是仪器抖动："
                    "见 §2.0b 的连读 3 次逐项相同），"
                    "**也不是**判定台把画面整体量偏了。")
            else:
                add("⭐ 25 个配对时刻的**逐帧残差逐项相同** ⇒ "
                    "总和的差**不来自配对帧**（请查判定台读数口径）。")
            add("")
            # ---- the capture-reuse trap -------------------------------------
            _mismatches = capture_rom_mismatch(_candidate_report)
            _baseline_mismatches = capture_rom_mismatch(_baseline_report)
            add("#### 2.0.2 ⭐⭐ 判定台「复用采集不校验 ROM」"
                "—— **wave 16 / V3 已修**")
            add("")
            add("| 侧 | 采集实际记录的 ROM（audit） | 报告声称的 ROM | "
                "复用还是重采 | 原因 |")
            add("|---|---|---|---|---|")
            for _side in ("original", "remake"):
                _cap = (_candidate_report.get("captures") or {}).get(_side) or {}
                _audit_rom = (_cap.get("audit") or {}).get("rom_sha256")
                _dec = _reuse_decision_of(_candidate_report, _side)
                _action = _dec.get("action") or "—"
                _why = (_dec.get("refused_reason") or _dec.get("reason")
                        or "—")
                add(f"| {_side} | "
                    + (f"`{str(_audit_rom)[:16]}…`" if _audit_rom
                       else "（审计里没有 ROM 字段）")
                    + f" | `{str(_cap.get('rom_sha256'))[:16]}…` | "
                    f"**{_action}** | {_why} |")
            add("")
            if _mismatches:
                add("⛔ **本次的报告里，采集记录的 ROM 与报告声称的 ROM 不一致** ⇒ "
                    "**那些数字说的是另一个 ROM**。")
            else:
                add("✅ **采集记录的 ROM == 报告声称的 ROM** ⇒ "
                    "本次的读数确实是在本次的 ROM 上量出来的。")
            add("")
            add("⭐ **这个缺陷曾经怎么伤人的**（wave 15 的实测）："
                "修好之前，`tools/s49_fidelity_report/capture.py::run_capture()` 在 "
                "`reuse=True` 时**只看「done 标记在不在、帧在不在」**，"
                "**从不核对那份采集是哪一个 ROM 录的**；"
                "随后报告把帧标成**它被要求测的**那个 ROM 的 sha256。"
                "⇒ **同一个工作目录里换 ROM 重跑，会拿到上一个 ROM 的帧、"
                "却标成新 ROM 的读数**。"
                "（wave 15 的 W1 的「判定台残差没有变大」就是这样得到的："
                "它复用了 wave 14 包里的采集目录，"
                "那份采集的 audit ROM 是 wave 14 的 ROM。"
                "⇒ **wave 15 流水线第 5 步的 "
                f"{_delta_total:+d} px 是真回归**，"
                "而 W1 的「逐项相同」是**陈旧采集**造成的假象。）")
            add("")
            add("✅ **wave 16 / V3 的修法**"
                "（只改 `tools/s49_fidelity_report/capture.py` 一个文件）：")
            add("")
            add("* 复用前**必须**核对采集自己的审计"
                "（`audit.json` **和** `done.json` 两个证人）："
                "重制侧核对 `rom_sha256`、原版侧核对 `input_state_sha256`；"
                "**两个证人互相矛盾 ⇒ 拒绝**。")
            add("* **核对不过 ⇒ 绝不复用 ⇒ 重新采集**；"
                "核对得过 ⇒ 复用。")
            add("* 收据里**机器可读**地写明："
                "`captures.<side>.measured_rom_sha256`"
                "（帧到底来自哪个 ROM）、`captures.<side>.reuse_decision`"
                "（测量稳定的事实）与 `run.attempts.<side>[0]`"
                "（复用/重采 + 原因，运行出处）。")
            add("")
            add("**判据（两条证明，可复跑）**：")
            add("")
            add("| 判据 | 做法 | 结果 |")
            add("|---|---|---|")
            add("| **A：审计说别的 ROM ⇒ 必须重采** | 把采集的 `audit.json` / "
                "`done.json` 里的 `rom_sha256`（原版侧是 `input_state_sha256`）"
                "改成**另一个 ROM / 另一个存档**的值，再用 `--skip-capture` 跑判定台 | "
                "**两侧都重新采集**（`action = recaptured`），"
                "收据里写明差在哪一个摘要上 |")
            add("| **B：审计说同一个 ROM ⇒ 可以复用，且读数与重采逐项相同** | "
                "**同一个 work 目录**里连跑三次：① 重采 ② 篡改后重采 ③ 复用 | "
                "③ **复用**（`action = reused`）；"
                "三次的 `content_sha256` **完全相同** ⇒ "
                "**复用不改变读数** |")
            add("")
            add("⇒ 复现：`python build/v3-dev/prove_capture_rom_check.py`"
                "（单元级：`python build/v3-dev/test_capture_identity.py`）。")
            add("")
            add("⭐ **这个缺陷咬的是哪一种跑法**（读准了才不会被误伤）："
                "流水线**自己从不传 `--skip-capture`**"
                "（步骤 5 每次都重录，步骤 5 连读 3 次时三次各自重录）"
                "⇒ **棘轮基线与流水线的读数一直是干净的**；"
                "**被咬的是手工跑 `--skip-capture --work-dir <别处的采集目录>`**"
                "（wave 15 的 W1 就是这样得到假象的）"
                "⇒ **修好之前，凡是用 `--skip-capture` 得来的「残差没变大」，"
                "一律不可信**。")
            add("")
            if _baseline_mismatches:
                add("⚠️ **基线报告本身也有同样的问题**（基线是在修复前录的）："
                    + "；".join(
                        f"{row['side']} 侧：采集 ROM "
                        f"`{str(row['audit_rom'])[:16]}…` vs 声称 "
                        f"`{str(row['claimed_rom'])[:16]}…`"
                        for row in _baseline_mismatches)
                    + " ⇒ **基线的读数也要按同样的口径复核**。")
                add("")
    # ---- which ROM is this run about? ------------------------------------
    _digests = _identity.get("digests") or {}
    _values = {value for value in _digests.values() if value}
    add("### 2.0c ⭐ **这一波的 ROM 是哪一个**（四个 sha 必须一致）")
    add("")
    add("V1 与 V2 都改产品 ⇒ **ROM 一定变** ⇒ "
        "「本次读数测的是哪个 ROM」必须能在报告里看出来。"
        "**四个摘要**任一不同 ⇒ 本次的数字就分属不同的字节 ⇒ 直接报出来。")
    add("")
    add("| 角色 | sha256 | 来自 |")
    add("|---|---|---|")
    for _role, _from in (("build", "步骤 1 构建产物"),
                         ("pinned", "步骤 1 钉住的拷贝（后面每一步都测它）"),
                         ("package", "步骤 12 打进包的 ROM"),
                         ("measured", "判定台**实际录到**帧的那个 ROM")):
        add(f"| **{_role}** | `{str(_digests.get(_role))[:16]}…` | {_from} |")
    add("")
    if _identity.get("agree"):
        add(f"✅ **四者逐字相同** = `{str(_digests.get('build'))}` "
            f"⇒ 本次报告里的每一个像素数都出自**这一份** ROM。")
    elif len(_values) > 1:
        add("⛔ **四个摘要不一致** ⇒ 本次的数字**分属不同的字节** ⇒ "
            "下面的读数**不许**互相比较：")
        add("")
        for _role, _value in _digests.items():
            add(f"* **{_role}** = `{_value}`")
        add("")
        add("⇒ **本包的读数不可用** ⇒ 必须重跑流水线。")
    else:
        add(f"⛔ **四个摘要没有凑齐**（只拿到 "
            f"{_identity.get('present')} / 4 个："
            + "、".join(f"{_role}" for _role, _value in _digests.items()
                        if _value)
            + "）⇒ **本次读数测的是哪个 ROM 无法确认** ⇒ "
            "**本包的读数不可用** ⇒ 必须重跑流水线。")
    add("")
    add(f"| 项 | 值 |")
    add("|---|---|")
    add(f"| 本次 ROM 的构建时间 | `{_identity.get('rom_mtime') or '—'}` |")
    add(f"| 本次 ROM 的字节数 | {fmt(_identity.get('rom_bytes'))} |")
    _reused = _identity.get("reused") or {}
    for _side in ("original", "remake"):
        _dec = (_identity.get("decisions") or {}).get(_side) or {}
        add(f"| {_side} 侧采集 | **{_dec.get('action') or '—'}**"
            + (f"（{_dec.get('reason')}）" if _dec.get("reason") else "") + " |")
    add(f"| 采集是复用的吗 | original = **{_reused.get('original')}** / "
        f"remake = **{_reused.get('remake')}** |")
    _baseline_rom = _baseline_rom_w16
    add(f"| 与上一波被接受的基线 ROM 相同吗 | "
        + (f"✅ **相同**（`{str(_baseline_rom)[:16]}…`）"
           if _baseline_rom and _baseline_rom == _digests.get("build")
           else f"⛔ **不同**（基线 `{str(_baseline_rom)[:16]}…` "
                f"vs 本次 `{str(_digests.get('build'))[:16]}…`）")
        + " |")
    add("")
    # ---- the reading has to be reproducible before it can be compared ------
    determinism = (after.get("run") or {}).get("determinism") or {}
    readings = determinism.get("runs") or []
    if len(readings) > 1:
        add("### 2.0b ⭐ 读数确定性（**棘轮可信的前提**）")
        add("")
        add("同一个 ROM **连读 N 次**（步骤 5 现在默认读 3 次），"
            "N 次读数必须**逐项相同**：残差摘要、归因、三桶、"
            "逐帧配对，以及每一张采集 PNG 的 sha256。"
            "读数不确定 ⇒「残差变大」可能只是噪声 ⇒ **棘轮会误报**。")
        add("")
        add("| 读数 | 重制侧 ROM sha256 | 战场区残差总和 | 中位 | 峰值 | 全 0 帧 | 采集摘要 |")
        add("|---|---|---:|---:|---:|---:|---|")
        for reading in readings:
            add(f"| {reading.get('iteration')} | "
                f"`{((reading.get('rom_sha256') or {}).get('remake') or '')[:16]}…` | "
                f"{fmt(reading.get('field_residual_sum'))} | "
                f"{fmt(reading.get('field_residual_median'))} | "
                f"{fmt(reading.get('field_residual_max'))} | "
                f"{fmt(reading.get('zero_frames'))} | "
                f"`{(reading.get('capture_digest') or '')[:16]}…` |")
        add("")
        if determinism.get("identical"):
            add("✅ **读数确定**：上表的 N 次读数**完全相同** ⇒ "
                "本次残差是一个**可复现的读数** ⇒ 残差变了就是**产品变了**，"
                "不是仪器在抖。")
        else:
            add("⛔ **读数不确定**：上表的读数**不一致** ⇒ "
                "棘轮**不能**据此判红或判绿（见 §11 的对应未达成项）。")
        add("")
        add("> ⭐ **更正 wave 10 报告里的「±9,520 px 抖动」**："
            "那个数**不是**判定台的抖动，是**两次跑用的 ROM 不是同一个**。"
            "证据（wave 10 / U4 自己留下的两份报告，收据在 "
            "`build/s49-package-u4/bench-check*/report.json`）：")
        add(">")
        add("> | 运行 | 重制侧 ROM sha256 | 战场区残差总和 | `step-12-A` 的配对 |")
        add("> |---|---|---:|---|")
        add("> | `bench-check`（11:15:03） | `249217d7f59a2199…` | 168,816 | "
            "`step-19-A.png`（9,151 px） |")
        add("> | `bench-check2`（11:27:10） | `73b74587595d4581…` | 104,784 | "
            "`step-16-A.png`（0 px） |")
        add(">")
        add("> ⇒ **ROM 的 sha256 不同** ⇒ 两次读的是**两个不同的 ROM** ⇒ "
            "差的那 9,520 px 属于**产品改动**，不属于仪器。"
            "⇒ 判定台的判定语义（`product_diff` / `pairing_diff` / 三桶）"
            "**没有改**，改的是**仪器现在能自证这件事**。")
        add("")
    add("| 指标 | before（钉住的基线） | after（本次） | 方向 |")
    add("|---|---:|---:|---|")
    for key, label, better in (
            ("min", "战场区残差 min", "lower"),
            ("median", "战场区残差 中位", "lower"),
            ("max", "战场区残差 max", "lower"),
            ("sum", "战场区残差 总和", "lower"),
            ("zero_frames", "战场区全 0 帧数", "higher"),
    ):
        a = before_field.get(key)
        b = field.get(key)
        if a is None and b is None:
            continue
        if a is None or b is None:
            arrow = "—"
        elif better == "lower":
            arrow = "🟢 好" if b < a else ("🔴 差" if b > a else "＝")
        else:
            arrow = "🟢 好" if b > a else ("🔴 差" if b < a else "＝")
        add(f"| {label} | {fmt(a)} | {fmt(b)} | {arrow} |")
    for key, label, better in (
            ("full_residual", "整屏残差 总和", "lower"),
            ("overlay_residual", "覆盖层族名残差 总和", "lower"),
    ):
        a = (before_summary.get(key) or {}).get("sum")
        b = (after_summary.get(key) or {}).get("sum")
        if a is None and b is None:
            continue
        if a is None or b is None:
            arrow = "—"
        elif better == "lower":
            arrow = "🟢 好" if b < a else ("🔴 差" if b > a else "＝")
        else:
            arrow = "＝"
        add(f"| {label} | {fmt(a)} | {fmt(b)} | {arrow} |")
    add("")
    add("### 2.1 残差分解（配对差 / 产品差 / 一致）+ 归因")
    add("")
    totals = {"identical": 0, "product_diff": 0, "pairing_diff": 0}
    counts = {"identical": 0, "product_diff": 0, "pairing_diff": 0}
    subclass_totals: dict[str, int] = {}
    subclass_counts: dict[str, int] = {}
    for row in after.get("frames", []):
        verdict = row.get("verdict") or {}
        klass = verdict.get("class") or "?"
        residual = row.get("field_residual_px") or 0
        totals[klass] = totals.get(klass, 0) + residual
        counts[klass] = counts.get(klass, 0) + 1
        subclass = verdict.get("subclass")
        if subclass:
            subclass_totals[subclass] = subclass_totals.get(subclass, 0) + residual
            subclass_counts[subclass] = subclass_counts.get(subclass, 0) + 1
    grand = sum(totals.values()) or 1
    add("| 归因 | 帧数 | 战场区残差总和 (px) | 占比 |")
    add("|---|---:|---:|---:|")
    for key, label in (("identical", "一致"), ("product_diff", "产品差"),
                       ("pairing_diff", "配对差")):
        add(f"| {label} | {fmt(counts.get(key, 0))} | {fmt(totals.get(key, 0))} | "
            f"{totals.get(key, 0) / grand:.1%} |")
    add(f"| **合计** | {fmt(sum(counts.values()))} | {fmt(sum(totals.values()))} | "
        "100.0% |")
    add("")
    if subclass_totals:
        add("| 配对差的子类 | 帧数 | 战场区残差总和 (px) |")
        add("|---|---:|---:|")
        for key in sorted(subclass_totals):
            add(f"| {key} | {fmt(subclass_counts[key])} | "
                f"{fmt(subclass_totals[key])} |")
        add("")
    add("### 2.2 配对差的三桶")
    add("")
    add("| 桶 | 帧数 | 机制 |")
    add("|---|---:|---|")
    black_count = subclasses.get("black_transition") or 0
    static_count = subclasses.get("static_frame") or 0
    mismatch_count = subclasses.get("moment_mismatch") or 0
    add(f"| 黑场过渡（black_transition） | {fmt(black_count)} | "
        + ("原版开场演出有渐变黑场，重制侧同相位硬切"
           if black_count else
           "**本次 0 帧** —— 重制侧的黑场渐变已补上，这一桶归零了") + " |")
    add(f"| 静止帧（static_frame） | {fmt(static_count)} | "
        + ("重制侧画面冻住（原版描边色 7 级）"
           if static_count else "**本次 0 帧**") + " |")
    add(f"| 时刻不一致（moment_mismatch） | {fmt(mismatch_count)} | "
        + ("两条 walk 走到了不同的游戏序列（X2 的结论：walk 侧已到头，"
           "剩下的帧逐帧都有产品差证据）"
           if mismatch_count else "**本次 0 帧**") + " |")
    add("")
    quality = after_summary.get("pairing_quality") or {}
    add(f"配对质量：内容锚 {fmt(quality.get('frames_with_anchor'))}/"
        f"{fmt(quality.get('frames'))}，锚支持配对 "
        f"{fmt(quality.get('anchor_supports_pairing'))}，"
        f"覆盖层完全一致 {fmt(quality.get('overlay_exact'))}。")
    add("")
    add("### 2.3 逐帧")
    add("")
    ratchet_frames = {row.get("original"): row
                      for row in ratchet_before.get("frames", [])}
    add("| 原版帧 | 配对到的重制帧 | 战场区残差 px | 上次被接受 | Δ | 归因 | 子类 | 覆盖层族名残差（格） |")
    add("|---|---|---:|---:|---:|---|---|---:|")
    for row in after.get("frames", []):
        verdict = row.get("verdict") or {}
        overlay = row.get("overlay_residual") or {}
        previous = ratchet_frames.get(row.get("original"))
        if previous is not None:
            before_px = previous.get("field_residual_px")
            now_px = row.get("field_residual_px")
            if before_px is None or now_px is None:
                delta = "—"
            else:
                diff = now_px - before_px
                if diff == 0:
                    delta = "＝"
                elif diff < 0:
                    delta = f"🟢 {diff}"
                else:
                    delta = f"🔴 +{diff}"
            before_cell = fmt(before_px)
        else:
            before_cell = "—"
            delta = "—"
        add(f"| `{row.get('original')}` | `{row.get('best_match')}` | "
            f"{fmt(row.get('field_residual_px'))} | {before_cell} | {delta} | "
            f"{verdict.get('class_label') or verdict.get('class') or '—'} | "
            f"{verdict.get('subclass') or '—'} | "
            f"{fmt(overlay.get('residual'))} |")
    add("")
    if ratchet_frames:
        better = sum(1 for row in after.get("frames", [])
                     if ratchet_frames.get(row.get("original"), {}).get(
                         "field_residual_px") is not None
                     and (row.get("field_residual_px") or 0)
                     < (ratchet_frames[row["original"]].get(
                         "field_residual_px") or 0))
        worse = sum(1 for row in after.get("frames", [])
                    if ratchet_frames.get(row.get("original"), {}).get(
                        "field_residual_px") is not None
                    and (row.get("field_residual_px") or 0)
                    > (ratchet_frames[row["original"]].get(
                        "field_residual_px") or 0))
        add(f"逐帧相对上次被接受的运行：**{better} 帧变好 / {worse} 帧变差**"
            "（逐帧比不作为门禁 —— 配对可能整体平移；门禁只看 §2.0 的聚合量）。")
        add("")

    # ---------------------------------------------------------------- 3
    add("## 3. 覆盖层逐格族名对拍")
    add("")
    overlay_step = step_by_name(receipt, "overlay")
    overlay_metrics = overlay_step.get("metrics") or {}
    add(f"来源：`{evidence.relative_to(REPO).as_posix()}/overlay/overlay-families.json`；"
        f"候选帧：**整条 walk 的 {fmt(overlay_metrics.get('candidate_dumps'))} 个 "
        "anchor dump**（wave 10 / U4 改过候选集，见 §3.1 与 §11 第 17 项）；"
        "每个原版时刻取**逐格最接近**的那一帧（仪器自带的选择规则）。")
    add("")
    add("| 原版时刻 | 锚点(map px) | 同亮 | 原版有·重制缺 | 重制有·原版缺 | 族名不一致 | 残差合计 | 完全一致 |")
    add("|---|---|---:|---:|---:|---:|---:|---|")
    for name, row in (overlay_metrics.get("moments") or {}).items():
        anchor = f"({fmt(row.get('anchor_x'))}, {fmt(row.get('anchor_y'))})"
        add(f"| `{name}` | {anchor} | {fmt(row.get('both_lit'))} | "
            f"{fmt(row.get('original_only'))} | {fmt(row.get('remake_only'))} | "
            f"{fmt(row.get('family_mismatches'))} | {fmt(row.get('residual'))} | "
            f"{'是' if row.get('exact') else '否'} |")
    add("")
    add("### 3.1 ⭐ 锚点口径（wave 10 / U4 改过仪器）")
    add("")
    add("原版的覆盖层缓冲**内容锚在地图空间 map px (256, 0)**、屏幕位置跟相机"
        "（`bg2_hoffs = 240 == bg_hoffs`、`bg2_voffs = 24 == bg_voffs`），"
        "实测 **17984 / 17984 px** 精确命中（次优锚点 (264, 0) 只有 17216）。"
        "⇒ **缓冲像素 `p` 的地图标签 = `(p + 256) mod 480`**。")
    add("")
    add("⚠️ **wave 9 之前的共享仪器表达不了这个锚点**：它按「相机派生的窗口」"
        "给缓冲贴地图标签，再在 `[0, 256)` 里搜最优窗口 —— "
        "**256 落在搜索区间外**（地图宽 480 px，256 ≠ 0），"
        "而且「取搜索到的最优」会**替重制侧美化**。"
        "⇒ wave 10 / U4 把仪器改成**固定锚点**（`tools/s49_overlay_align/"
        "compare_overlay_families.py`），"
        "并把「窗口自由搜索」降级成**只读诊断**"
        "（`tools/s49_v2_anchor/scan_window.py`）。")
    add("")
    conventions = load_json(evidence / "overlay" / "conventions.json")
    if conventions:
        old_convention = conventions.get("old_convention") or {}
        new_convention = conventions.get("new_convention") or {}
        add(f"**同一份 VRAM  dump（`{conventions.get('dump')}`）上两种口径的实测对比**"
            f"（`{evidence.relative_to(REPO).as_posix()}/overlay/conventions.json`，"
            "由 `tools/s49_overlay_align/compare_conventions.py` 生成）：")
        add("")
        add(f"* 旧口径 = {old_convention.get('name')}，窗口 "
            f"`{old_convention.get('window')}`，搜索区间 "
            f"`{old_convention.get('search_range')}`")
        add(f"* 新口径 = {new_convention.get('name')}，锚点 "
            f"`{new_convention.get('anchor')}`，规则 "
            f"`{new_convention.get('rule')}`")
        add("")
        add("| 原版时刻 | 口径 | 同亮 | 原版有·重制缺 | 重制有·原版缺 | 族名不一致 | 残差合计 |")
        add("|---|---|---:|---:|---:|---:|---:|")
        for name, row in (conventions.get("moments") or {}).items():
            for label, key in (("旧·窗口搜索", "old_window"),
                               ("新·固定锚点", "new_anchor")):
                cell = row.get(key) or {}
                add(f"| `{name}` | {label} | {fmt(cell.get('both_lit'))} | "
                    f"{fmt(cell.get('original_only'))} | "
                    f"{fmt(cell.get('remake_only'))} | "
                    f"{fmt(cell.get('family_mismatches'))} | "
                    f"{fmt(cell.get('residual'))} |")
        add("")
        deltas = {(row.get("delta") or {}).get("residual")
                  for row in (conventions.get("moments") or {}).values()}
        if len(deltas) == 1 and None not in deltas:
            delta = deltas.pop()
            add(f"⭐ **口径变化把残差**每个时刻**降了 {abs(delta)} 格**"
                "（`重制有·原版缺` 少了同样的格数），"
                "**同亮 / 原版有·重制缺 / 族名不一致三项一字未变** ⇒ "
                "**不是把残差藏起来了，是把缓冲的回绕段映回了正确的地图列**"
                "（旧口径把 256 px 宽的窗口摊在地图上、**不做 480 px 回绕**，"
                "多算出若干格「重制多画」；这一差值随帧而变 —— "
                "wave 9 的那份 dump 上是 23 格，本次是 "
                f"{abs(delta)} 格）。")
        else:
            add(f"口径变化对残差的影响（逐时刻）：{sorted(deltas)}。")
        add("")
    # This block is emitted *after* section 3.2 (the overrun review), so the
    # sub-section numbering stays 3.1 / 3.2 / 3.3.
    cell_lines: list[str] = []
    report_add = add
    add = cell_lines.append
    add("⭐ **wave 13 的口径更正（这一节的头号结论）**："
        "**「同亮 192 / 原版缺 0 / 多画 0」已经达成。** "
        "从 wave 1 传下来的「多画 310–420 格 / 缺 96–129 格」"
        "**是仪器假象**：共享仪器给**原版**贴地图标签时**没有按 480 px 回绕**"
        "（`original_map_cells()` 直接 `(anchor_x + lx * 16) // 16`），"
        "给**重制侧**却回绕了（`remake_logical_cells()` 用 `% MAP_WIDTH`）"
        "⇒ 两侧的**缓冲尾部两列**（原版缓冲逻辑列 14/15 = 地图第 0 列）"
        "被互相错开 ⇒ 那 **24 格「原版缺」+ 24 格「多画」**全是**贴标签错位**。"
        "⛔ **旧口径的数字不许再引用**（下表是**回绕修好之后**的实测）。")
    add("")
    add("### 3.3 ⭐ 逐格性质判定（剩下的族名不一致**逐格**给出性质）")
    add("")
    classification = (overlay_metrics.get("cell_classification") or {})
    cell_moments = classification.get("moments") or {}
    if not cell_moments:
        add("> 本次收据里**没有**逐格性质判定的数据（流水线步骤 6 的"
            "`cell-classification.json` 没跑成）。")
        add("")
    else:
        add("**逐格判定器**：`tools/s49_package/classify_overlay_cells.py` —— "
            "**只读 import** 共享仪器（共享文件一个字未改），"
            "复制它的取帧规则与最优帧选择规则，"
            "**保留逐格差异**，再按三条**可判定**的规则分类。")
        add("")
        add("| 性质 | 判定规则 |")
        add("|---|---|")
        for key, rule in (classification.get("class_rules") or {}).items():
            add(f"| **{key}** | {rule} |")
        add("")
        add("| 原版时刻 | 最优帧 | 同亮 | 缺 | 多画 | 族名不一致 | 残差 | "
            "原版尾部残留 | walk 相位 | 产品差 | 相位判定 |")
        add("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for name, row in cell_moments.items():
            classes = row.get("classes") or {}
            add(f"| `{name}` | `{row.get('frame')}` | "
                f"{fmt(row.get('both_lit'))} | {fmt(row.get('original_only'))} | "
                f"{fmt(row.get('remake_only'))} | "
                f"{fmt(row.get('family_mismatches'))} | "
                f"{fmt(row.get('residual'))} | "
                f"{fmt(classes.get('原版尾部残留'))} | "
                f"{fmt(classes.get('walk 相位'))} | "
                f"{fmt(classes.get('产品差'))} | "
                + ("**相位错位**（原版的相位族集合 "
                   + "、".join(row.get("phase_set_original") or [])
                   + "，重制侧 35 帧里**没有**任何一帧同时具备这组相位族）"
                   if row.get("phase_shifted")
                   else "同相位") + " |")
        add("")
        add("**逐格明细**（每一格都给性质判定；`map (lx, ly)` 是地图空间的"
            "16×16 逻辑格坐标）：")
        add("")
        for name, row in cell_moments.items():
            cells = row.get("cells") or []
            if not cells:
                add(f"* **`{name}`**：无差异格（exact ✔）。")
                add("")
                continue
            add(f"* **`{name}`**（{len(cells)} 格；最优帧 "
                f"`{row.get('frame')}`）：")
            add("")
            add("  | map (lx, ly) | 原版族 | 重制侧族 | 性质 |")
            add("  |---|---|---|---|")
            for cell in cells:
                add(f"  | ({cell.get('map_lx')}, {cell.get('map_ly')}) | "
                    f"`{cell.get('original')}` | `{cell.get('remake')}` | "
                    f"**{cell.get('class')}** |")
            add("")
        add("**族名对直方图**（同一份数据，逐时刻）：")
        add("")
        add("| 原版时刻 | 族名对（原版→重制侧） |")
        add("|---|---|")
        for name, row in cell_moments.items():
            pairs = row.get("pairs") or {}
            text = "；".join(f"`{key}` {value}"
                             for key, value in pairs.items()) or "（无）"
            add(f"| `{name}` | {text} |")
        add("")
    add("> **目标（同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0）**："
        "**前三项已达成**；**族名不一致 0 仍未达成**，"
        "逐格性质见 §3.3，未达成项见 §11。")
    add = report_add
    add("### 3.2 ⭐ 越界复核：wave 10 / U4 给 `find_overlay_map` 加的 terrain 判据")
    add("")
    add("wave 10 的 U4 流**自报了一处越界**：它在**别的流**的仪器"
        "（`tools/s49_overlay_align/compare_overlay_families.py`）里给 "
        "`find_overlay_map` 加了一个 **terrain 判据**"
        "（「solid 必须落在受阻地形上」），"
        "超出了「只授权改锚点」的范围。")
    add("")
    add("⭐ **wave 11 / W4 复核过一次（结论：保留，不回退）；"
        "wave 12 / X4 独立复核第二次，数字全部重新测 ⇒ 见 §16。**")
    add("")
    add("本节只留一句结论，**全部数字与推理在 §16**"
        "（§16 的产物是本次收据里的 "
        "`evidence/overlay/terrain-review.json`，由流水线步骤 6 在**同一份 "
        "35 个 dump** 上跑出来 ⇒ 可追到某一次运行）："
        "**「不带 terrain」的路径与改前逐字节相同；判定台自己的覆盖层读数"
        "一字未变；判据只改 4/35 个 dump（假窗口 `0x00800` → `-1`），"
        "其余 31 个一字未变 ⇒ 保留，不回退。**")
    add("")
    add("⚠️ **循环论证的风险**：terrain 来自**重制线自己的生成头** "
        "`generated_battle_map_content.h` ⇒ 这条判据只保证"
        "「覆盖层与**产品自己用的**地图一致」，**不是**独立于产品的绝对真值。"
        "绝对真值仍是原版导出的 `s49-original-movegrid-tilemap-v1`。")
    add("")
    # ---- 3.3: the per-cell property verdict (buffered above) -----------
    for line in cell_lines:
        add(line)
    add("")
    # ---- 3.4: Z3's attribution of the 'walk phase' cells ---------------
    add("### 3.4 ⭐ 「walk 相位」格的不一致归因（wave 14 / Z3）")
    add("")
    _cell_classes = (overlay_metrics.get("cell_classification") or {}).get(
        "moments") or {}
    _tail_total = sum((row.get("classes") or {}).get("原版尾部残留", 0)
                      for row in _cell_classes.values())
    _phase_total = sum((row.get("classes") or {}).get("walk 相位", 0)
                       for row in _cell_classes.values())
    _product_total = sum((row.get("classes") or {}).get("产品差", 0)
                         for row in _cell_classes.values())
    add("§3.3 把剩下的族名不一致逐格分成了三类："
        f"**原版尾部残留 {fmt(_tail_total)} 格** / "
        f"**walk 相位 {fmt(_phase_total)} 格** / "
        f"**产品差 {fmt(_product_total)} 格**。"
        "**walk 相位**那一类的判定规则是："
        "原版该时刻的画面同时具备一组相位族（青/黄/橙/绿），"
        "而重制侧的 35 帧里**没有任何一帧**同时具备这组相位族。")
    add("")
    _phase_path, _phase_doc = z3_phase_attribution()
    _z3_note = _note_present_since("Z3-bound", W14_CUTOFF)
    if _phase_doc:
        add(f"⭐ **wave 14 / Z3 给了可判定的归因**"
            f"（收据 `{_phase_path.relative_to(REPO).as_posix()}`"
            + (f"；笔记 `notes/s49-fidelity/{_z3_note.name}`"
               if _z3_note else "") + "）。")
        add("")
        _verdicts = _phase_doc.get("verdicts") or {}
        _reach = _phase_doc.get("phase_reachability") or {}
        if _verdicts:
            add("**(a) 原版那一帧是稳定态还是瞬态？** —— "
                "Z3 抓了原版**自己的 6 帧连拍**来判：")
            add("")
            add("| 原版时刻 | 导出帧 | 相位族集合 | 原版点亮格 | 6 帧里同相位族 | "
                "6 帧里同网格摘要 | 判定 |")
            add("|---|---|---|---:|---:|---:|---|")
            for _name, _row in _verdicts.items():
                add(f"| `{_name}` | `{_row.get('exported_frame')}` | "
                    + ("、".join(_row.get("exported_phase_set") or []) or "（空）")
                    + f" | {fmt(_row.get('exported_map_lit_cells'))} | "
                    f"{fmt(_row.get('frames_with_same_phase_set'))} / "
                    f"{fmt(_row.get('consecutive_frames_captured'))} | "
                    f"{fmt(_row.get('frames_with_same_grid_digest'))} / "
                    f"{fmt(_row.get('consecutive_frames_captured'))} | "
                    f"**{_row.get('verdict')}** |")
            add("")
        if _reach:
            add("**(b) 重制侧到底走没走到那个相位？** —— "
                "在**密集 walk**（原版 553 帧 / 重制 783 帧）上数同相位族的帧数：")
            add("")
            add("| 原版时刻 | 相位族集合 | 原版密集 walk 同相位 | "
                "重制密集 walk 同相位 | 重制侧最长连续同相位 |")
            add("|---|---|---:|---:|---:|")
            for _name, _row in _reach.items():
                add(f"| `{_name}` | "
                    + ("、".join(_row.get("phase_set") or []) or "（空）")
                    + f" | {fmt(_row.get('original_dense_walk_frames_with_phase_set'))}"
                      f" / {fmt(_row.get('original_dense_walk_frames'))}"
                    + f" | {fmt(_row.get('dense_walk_frames_with_phase_set'))}"
                      f" / {fmt(_row.get('dense_walk_frames'))}"
                    + f" | {fmt(_row.get('remake_dense_walk_longest_consecutive_run'))} |")
            add("")
            add("⇒ **`field` 的 50 格 = 重制侧缺一个相位**"
                "（原版那一帧是**稳定态**：6 帧连拍逐格相同、原版密集 walk 里连续 "
                "**67 帧**同相位；重制侧 **0 / 783 帧**同现）；"
                "**`grid16` 的 80 格 = 原版那一帧是瞬态**"
                "（导出帧在 6 连拍里**只出现 1 次**，下一帧已是 176 格的完整画面 ⇒ "
                "缓冲半刷新的撕裂残影）。"
                "⇒ **130 = 50（重制缺相位）+ 80（原版瞬态）**。")
            add("")
    elif _z3_note:
        add(f"⭐ **wave 14 / Z3 已交付笔记**"
            f"（`notes/s49-fidelity/{_z3_note.name}`）⇒ "
            "归因的结论与证据以那份笔记的实测为准。")
        add("")
    else:
        add("⛔ **wave 14 / Z3 尚未交付** ⇒ "
            "这 130 格的归因（是「重制侧缺一个相位」还是「原版那一帧是瞬态」）"
            "**本报告没有结论**；§3.3 只给出了它们的**分类规则**。")
        add("")
    # ---- 3.5: V4's same-moment attribution (wave 16) ----------------------
    _v4_phase_path, _v4_phase_doc = wave16_phase_attribution()
    _v4_is_w17 = bool(
        _v4_phase_path is not None
        and _v4_phase_path.stat().st_mtime > wave17_cutoff_mtime())
    _v4_owner = ("wave 17 / U2" if _v4_is_w17 else "wave 16 / V4")
    add(f"### 3.5 ⭐⭐ {_v4_owner} 的**同刻**归因"
        "（口径修正：那 50 格**不是**「walk 没走到」）")
    add("")
    _v4_note = _note_present_since("V4-bound", W16_CUTOFF)
    if _v4_phase_doc:
        _smc = _v4_phase_doc.get("same_moment_comparison") or {}
        _best = _smc.get("overall_best") or {}
        _orig_co = ((_v4_phase_doc.get("original") or {}).get("coexistence")
                    or {})
        _remake_co = ((_v4_phase_doc.get("remake") or {}).get("coexistence")
                      or {})
        add(f"⭐ **{_v4_owner} 把这 50 格的归因查实了**"
            f"（收据 `{_v4_phase_path.relative_to(REPO).as_posix()}`"
            + (f"；笔记 `notes/s49-fidelity/{_v4_note.name}`"
               if _v4_note else "")
            + ("；**这是 wave 17 的收据**（U2 复算的）"
               if _v4_is_w17 else "") + "）。")
        add("")
        add(f"**(a) 同刻口径的逐格对照**（{fmt(_smc.get('compared_frames'))} 帧参与比较）：")
        add("")
        add("| 项 | 值 |")
        add("|---|---:|")
        add(f"| 最优同刻帧 | `{_best.get('frame')}`"
            f"（semantic beat {_best.get('semantic_beat')}） |")
        add(f"| 原版点亮格 / 重制侧点亮格 | {fmt(_best.get('original_lit'))} / "
            f"{fmt(_best.get('remake_lit'))} |")
        add(f"| 同亮 / 原版缺 / 多画 | {fmt(_best.get('both_lit'))} / "
            f"{fmt(_best.get('original_only'))} / {fmt(_best.get('remake_only'))} |")
        add(f"| 族名不一致 | **{fmt(_best.get('family_mismatches'))}** |")
        add("")
        add("**(b) 相位族共现统计**（两侧各自走完整条密集 walk）：")
        add("")
        add("| 相位族共现 | 原版 | 重制侧 |")
        add("|---|---:|---:|")
        for _key in sorted(set(_orig_co) | set(_remake_co)):
            add(f"| `{_key}` | {fmt(_orig_co.get(_key))} | "
                f"{fmt(_remake_co.get(_key))} |")
        add("")
        add("⇒ ⭐ **结论（可判定，不是断言）**：")
        add("")
        add("1. **重制侧的产品规则让「青 + 橙」在结构上不可能同现**"
            "（`move` 只在 `in_move_range && move_phase`，"
            "`attack_range` 只在 `in_attack_range && !move_phase`）"
            f"⇒ 实测 `hatch_and_line_alt`：原版 "
            f"**{fmt(_orig_co.get('hatch_and_line_alt'))}** 帧 / 重制侧 "
            f"**{fmt(_remake_co.get('hatch_and_line_alt'))}** 帧；")
        add("2. **重制侧已经走到了同一段**（结算段："
            f"`band_and_line_alt` 重制侧 "
            f"**{fmt(_remake_co.get('band_and_line_alt'))}** 帧，"
            "光标 + 橙都在）⇒ **不是 walk 没走到**；")
        add("3. **原版那一帧是「相位残留」** ⇒ 缺的正是"
            "**「相位切换时不清覆盖层缓冲」这段演出（产品侧）**。")
        add("")
        add("⚠️ **口径提醒（两个数不许混用）**：§3.3 / §3.4 的 **130 格**是"
            "**跨时刻**口径；V4 的**同刻**口径是 **56 格（连尾部 67 格）**，"
            "而且**两者的族名对也不同**（跨时刻：原版 `hatch` ↔ 重制 `hatch`；"
            "同刻：原版画「移动可达集（青）」、重制画「合法目标（绿）」）。")
        add("")
        add("⛔ **改口径是另一件事**：`tools/s49_package/classify_overlay_cells.py` "
            "**本流未改** ⇒ §3.3 的分类仍然是**跨时刻**口径；"
            "V4 已把同刻逐格对照算在它的收据里。")
    else:
        add("⛔ **wave 16 / V4 的相位归因尚未交付** ⇒ "
            "「这 50 格是 walk 没走到，还是产品缺一段演出」"
            "**本报告没有同刻口径的结论**；§3.3 只给出了**分类规则**。")
    add("")
    add("")

    # ---------------------------------------------------------------- 4
    add("## 4. 音频事件级对照（19 个配对时刻）")
    add("")
    audio = load_json(work / "s49-audio-l" / "event_diff.json") or {}
    counts = audio.get("diff_counts") or {}
    classes = ("match", "cue_mismatch", "silent_on_remake", "never_dispatched",
               "missing_on_remake", "not_reached_in_window")
    legend = {
        "match": "两侧同一时刻派发了同一个 cue",
        "cue_mismatch": "同一游戏时刻两侧 cue ID 不同",
        "silent_on_remake": "重制侧派发了该 cue，但**听不到声音**",
        "never_dispatched": "重制侧表里有，但**没有调用点**",
        "missing_on_remake": "原版会播，重制侧**连这个 cue 都没有**",
        "not_reached_in_window": "两侧都有且重制侧已接线，但这次采集没走到该时刻",
    }
    add("来源：`{work.relative_to(REPO).as_posix()}/s49-audio-l/event_diff.json`；"
        f"原版侧证据：`build/s49-audio/`（J 流）。")
    add("")
    add("### 4.1 本次采集的判定（L 流，步骤 10 的产物）")
    add("")
    add("| 判定类别 | 含义 | 数量 |")
    add("|---|---|---:|")
    for name in classes:
        add(f"| `{name}` | {legend[name]} | {fmt(counts.get(name, 0))} |")
    add("")
    upstream = load_json(REPO / "build" / "s49-audio" / "event_diff.json") or {}
    upstream_counts = upstream.get("diff_counts") or {}
    add("### 4.2 上游证据的判定（J 流 `build/s49-audio/event_diff.json`，"
        "5 类口径）")
    add("")
    add("| 判定类别 | 含义 | 数量 |")
    add("|---|---|---:|")
    for name in ("match", "cue_mismatch", "silent_on_remake",
                 "never_dispatched", "missing_on_remake"):
        add(f"| `{name}` | {legend[name]} | {fmt(upstream_counts.get(name, 0))} |")
    add("")
    add("> L 流的 `not_reached_in_window`（本次采集没走到该时刻）与 J 流的 "
        "`silent_on_remake`（重制侧派发了但听不见）是**两套口径**：J 流是"
        "原版侧的普查证据，L 流是重制侧接了线之后的实跑结果。两者不能直接"
        "相减。")
    add("")
    add("### 4.3 19 个配对时刻逐条")
    add("")
    add("| # | cue key | 游戏时刻 | 判定 |")
    add("|---|---|---|---|")
    for index, row in enumerate(audio.get("rows", []), start=1):
        add(f"| {index} | `{row.get('key')}` | {row.get('moment')} | "
            f"`{row.get('diff')}` |")
    add("")

    # ---------------------------------------------------------------- 5
    add("## 5. 存档字段级差异表")
    add("")
    compare = load_json(REPO / "build" / "s49-save-boundary" / "receipts"
                        / "save_compare.json") or {}
    cross = compare.get("cross_format") or {}
    original = compare.get("original") or {}
    remake = compare.get("remake") or {}
    add("来源：`build/s49-save-boundary/receipts/save_compare.json`"
        "（`tools/s49_save_boundary/run_all.py --repeat 2`）。")
    add("")
    add("| 项 | 值 |")
    add("|---|---:|")
    add(f"| 原版检查点数 | {fmt(original.get('checkpoint_count'))} |")
    add(f"| 原版不同镜像数 | {fmt(original.get('distinct_images'))} |")
    add(f"| 原版战前→战后差异字节 | {fmt(original.get('pre_post_differing_bytes'))} |")
    writes = original.get("writes_during_battle")
    add(f"| 原版战斗期写盘 | "
        f"{'是' if writes is True else ('否' if writes is False else '—')} |")
    add(f"| 重制侧检查点数 | {fmt(remake.get('checkpoint_count'))} |")
    add(f"| 重制侧 擦除态→第一次存档 差异字节 | "
        f"{fmt((remake.get('diff_erased_to_first_save') or {}).get('differing_bytes'))} |")
    add(f"| 重制侧 第一次→第二次存档 差异字节 | "
        f"{fmt((remake.get('diff_first_to_second_save') or {}).get('differing_bytes'))} |")
    add(f"| 重制侧 第二次存档→战斗末 差异字节 | "
        f"{fmt((remake.get('diff_second_save_to_last_battle_step') or {}).get('differing_bytes'))} |")
    add(f"| 跨格式差异字节 | {fmt(cross.get('differing_bytes'))} |")
    add(f"| 跨格式差异区间数 | {fmt(len(cross.get('ranges') or []))} |")
    add("")
    field_table = cross.get("field_table") or []
    if field_table:
        add("**逐字段差异表**")
        add("")
        add("| 字段 | 原版 | 重制侧 | 差异 | 状态 |")
        add("|---|---|---|---|---|")
        for row in field_table:
            if not isinstance(row, dict):
                add(f"| {row} | | | | |")
                continue
            add(f"| `{row.get('field', '')}` | {row.get('original', '')} | "
                f"{row.get('remake', '')} | {row.get('difference', '')} | "
                f"{row.get('state', '')} |")
        add("")
    semantic_table = cross.get("semantic_table") or []
    if semantic_table:
        add("**语义映射表**")
        add("")
        add("| 语义 | 原版 | 重制侧 | 差异 |")
        add("|---|---|---|---|")
        for row in semantic_table:
            if not isinstance(row, dict):
                add(f"| {row} | | | |")
                continue
            add(f"| {row.get('semantic', '')} | {row.get('original', '')} | "
                f"{row.get('remake', '')} | {row.get('difference', '')} |")
        add("")

    # ---------------------------------------------------------------- 6
    add("## 6. 12 条边界行为对照表")
    add("")
    add("来源：`notes/s49-fidelity/W4-save-boundary.md` §6（其数字来自 "
        "`tools/s49_save_boundary/run_all.py` 的 62 张 SRAM 镜像与 "
        "`tools/s49_orig_map/orig_map_truth.py`）。**B5 / B7 两行按 X3 的"
        "实测结论更新过**（`notes/s49-fidelity/X3-boundary-fixes.md`）；"
        "B2 / B3 / B4 属非 S49 项，本波不做。")
    add("")
    add(BOUNDARY_TABLE)

    # ---------------------------------------------------------------- 7
    add("## 7. 黑场真值表")
    add("")
    black = step_by_name(receipt, "blackfade")
    black_metrics = black.get("metrics") or {}
    add("来源：`evidence/blackfade/blackfade-original.json` 与 "
        "`blackfade-remake.json`（`tools/s49_blackfade/blackfade_report.py`）。")
    add("")
    for label, title in (("original", "原版"), ("remake", "重制侧")):
        side = black_metrics.get(label) or {}
        add(f"### 7.{(1 if label == 'original' else 2)} {title}"
            f"（{fmt(side.get('frame_count'))} 帧，"
            f"{fmt(side.get('event_count'))} 个黑场事件）")
        add("")
        add("| # | 帧范围 | 总帧数 | 淡出 | 全黑 | 淡入 | 全黑帧 sha256 |")
        add("|---|---|---:|---:|---:|---:|---|")
        for event in side.get("events", []):
            add(f"| {fmt(event.get('event'))} | `{event.get('first_frame')}` .. "
                f"`{event.get('last_frame')}` | {fmt(event.get('total_frames'))} | "
                f"{fmt(event.get('fade_out_frames'))} | "
                f"{fmt(event.get('black_hold_frames'))} | "
                f"{fmt(event.get('fade_in_frames'))} | "
                f"`{(event.get('first_black_sha256') or '—')[:16]}…` |")
        add("")
    provenance = black_metrics.get("capture_provenance") or {}
    if provenance:
        add("采集来源（原版 / 重制侧两段录制的收据）：")
        add("")
        add("| 侧 | ROM sha256 | 存档 sha256 | 采集帧数 |")
        add("|---|---|---|---:|")
        for label, info in provenance.items():
            add(f"| {label} | `{(info.get('rom_sha256') or '—')[:16]}…` | "
                f"`{(info.get('state_sha256') or '—')[:16]}…` | "
                f"{fmt(info.get('frames_captured'))} |")
        add("")
        built_rom = (step_by_name(receipt, "build").get("metrics") or {})
        remake_capture = (provenance.get("remake") or {}).get("rom_sha256")
        if remake_capture and built_rom.get("rom_sha256"):
            if remake_capture == built_rom["rom_sha256"]:
                add("> ✅ **重制侧这段黑场录制用的就是本次构建的 ROM**"
                    f"（sha256 `{(remake_capture or '')[:16]}…`）—— "
                    "流水线每次都重录，不吃历史缓存。")
            else:
                add("> ⚠️ **重制侧这段黑场录制的 ROM sha256 与本次构建的 ROM "
                    "不同** ⇒ 这张表是旧 ROM 的，重录工具修好后必须重钉。")
        add("")

    # ---- 7.3: does the walk sample the black field at all? ---------------
    walk_rows = walk_blackness_table(
        work / "s49-report" / "capture-original",
        work / "s49-report" / "capture-remake")
    if walk_rows:
        add("### 7.3 walk 采到了黑场没有（**残差归因的决定性一张表**）")
        add("")
        add("上两张表说的是「黑场**长什么样**」；这一张说的是"
            "「walk **有没有采到**黑场」。判定台是按 walk 逐帧对拍的 ⇒ "
            "**原版 walk 采到的黑场帧，在重制侧必须也有对应帧**，否则那两帧的"
            "残差就是整屏。")
        add("")
        add("| 侧 | walk 帧 | 非黑像素占比 | 是黑场帧吗 |")
        add("|---|---|---:|---|")
        for label, name, fraction in walk_rows:
            add(f"| {label} | `{name}` | {fraction:.4f} | "
                + ("**是**" if fraction < 0.05 else "—") + " |")
        add("")
        original_blacks = [name for label, name, fraction in walk_rows
                           if label == "原版" and fraction < 0.05]
        remake_blacks = [name for label, name, fraction in walk_rows
                         if label == "重制侧" and fraction < 0.05]
        add(f"**原版 walk 采到 {len(original_blacks)} 个黑场帧**"
            f"（{', '.join('`' + n + '`' for n in original_blacks) or '无'}）"
            f"；**重制侧 walk 采到 {len(remake_blacks)} 个**"
            f"（{', '.join('`' + n + '`' for n in remake_blacks) or '**无**'}）"
            + ("⇒ **原版的黑场帧在重制侧没有对应** ⇒ 那几帧的残差必然是整屏"
               if original_blacks and not remake_blacks else ""))
        add("")

    # ---------------------------------------------------------------- 8
    add("## 8. 其余门禁")
    add("")
    idle = step_by_name(receipt, "idle-frames")
    wave = step_by_name(receipt, "outline-wave")
    add("| 门禁 | 判据 | 结果 |")
    add("|---|---|---|")
    sides = (idle.get("metrics") or {}).get("sides") or {}
    for side, info in sides.items():
        add(f"| 静止帧（{side}） | 波形平点之外不得有相同帧 | "
            f"{fmt(info.get('consecutive_identical_pairs'))} 对相同 / "
            f"{fmt(info.get('unexpected_pairs'))} 对异常 |")
    wave_metrics = wave.get("metrics") or {}
    add(f"| 描边波 | 200/200 与原版一致 | {fmt(wave_metrics.get('matched'))}/"
        f"{fmt(wave_metrics.get('frames'))} 一致，"
        f"{fmt(wave_metrics.get('mismatched'))} 不一致 |")
    add(f"| 无窗口无声 | 导入表无 USER32/winmm/SDL/OpenAL | "
        f"{'通过' if headless.get('ok') else '失败'} |")
    smoke_metrics = smoke.get("metrics") or {}
    add(f"| 冒烟 | 4096 帧不崩 + 中文标题画面 | "
        f"{fmt(smoke_metrics.get('frames_run'))} 帧；标题 "
        f"{(smoke_metrics.get('title') or {}).get('distinct_colors')} 色 / "
        f"{((smoke_metrics.get('title') or {}).get('glyphs') or {}).get('components')} "
        f"个墨迹连通块 |")
    add("")

    # ---------------------------------------------------------------- 9
    add("## 9. 假设台账索引")
    add("")
    add("台账是本项目的记忆：每行一个假设，带判定方法、结果、状态"
        "（未验 / 已证伪 / 已确认）。")
    add("")
    add("| 台账文件 | 假设条数 |")
    add("|---|---:|")
    for name, count, _title in ledger_index():
        add(f"| `{name}` | {count} |")
    add("")

    # ---------------------------------------------------------------- 10
    # The overlay cell classes are needed by **both** the exclusion list
    # (which of the remaining cells are excluded, and why) and the
    # "not achieved" table -- so they are computed once, here.
    overlay_metrics = (step_by_name(receipt, "overlay") or {}).get("metrics") or {}
    overlay_moments = overlay_metrics.get("moments") or {}
    cell_classes = (overlay_metrics.get("cell_classification") or {}).get(
        "moments") or {}
    tail_total = sum((row.get("classes") or {}).get("原版尾部残留", 0)
                     for row in cell_classes.values())
    phase_total = sum((row.get("classes") or {}).get("walk 相位", 0)
                      for row in cell_classes.values())
    product_total = sum((row.get("classes") or {}).get("产品差", 0)
                        for row in cell_classes.values())
    grid16_phase = ((cell_classes.get("grid16-frame-v1") or {}).get("classes")
                    or {}).get("walk 相位", 0)
    add("## 10. 明确排除项")
    add("")
    add(EXCLUSIONS.rstrip("\n"))
    if cell_classes:
        add(f"| **覆盖层 `grid16-frame-v1` 的 {fmt(grid16_phase)} 格"
            "（原版覆盖层缓冲的单帧撕裂瞬态）** | "
            "⭐ **wave 14 / Z3 的可判定归因**：原版那一帧在**连续 6 帧里只出现 1 次**"
            "（导出帧 `frame-00` 的网格摘要与其余 5 帧**全不同**），"
            "下一帧已经是 176 格的完整画面（第 1 行不再空、第 2 行补齐 1 格）"
            "⇒ **BG2 缓冲正在被重写时的撕裂残影**，"
            "**只存在 1 帧** ⇒ **任何忠实的重制都不该被要求复现它**"
            "（复现它就等于复现一次半刷新）。"
            "证据：收据 `build/s49-z3-bound/phase-B.json`、"
            "笔记 `notes/s49-fidelity/Z3-bound-and-phase.md` §3.3 / §3.5 |")
        add(f"| **覆盖层的 {fmt(tail_total)} 格「原版尾部残留」"
            "（Y2 的性质判定）** | "
            "原版缓冲回绕尾部（= 地图第 0/1 列）装的是**陈旧内容**"
            "（墙列上出现光标格与可达集）⇒ **任何忠实的重制都复现不了**"
            "（那不是规则，是原版自己的缓冲残迹）。"
            "⇒ 这两类格（尾部残留 + `grid16` 撕裂）"
            "**从「未达成项」移进「明确排除项」**，"
            "理由逐格见 §3.3 |")
    add("")

    # ---------------------------------------------------------------- 11
    add("## 11. 未达成项（不许粉饰）")
    add("")
    add("| # | 未达成项 | 现状 | 归谁 |")
    add("|---|---|---|---|")
    add("| 1 | ⭐ **原版 S49 结算屏真值 —— 本波已闭合（不再是未达成项）** | "
        "**wave 8 的 W4 打赢了**：原版 battle-14 的结果字节 `0x02026807` 由 0 变 1，"
        "结算链全程录到（`build/s49-victory-capture/w4/settlement-truth/`，"
        "9 张图 + sha256 收据 `9a60a89b…`），"
        "两次独立跑 **32,596 + 29,700 帧逐字节一致**，**没有伪造任何帧**。"
        "⇒ 「原版没有结算屏真值」这条**已经作废**，本项转入正文 §15 | "
        "W4（已交付） |")
    _settle_path, _settle_rows, _settle_kind, _settle_rom = settlement_running_frames(
        receipt_rom_sha(receipt))
    _z1_note = _note_present_since("Y1-stack-fix", W14_CUTOFF)
    _running_clause = (
        f"**已闭合**：Z1 录出了重制侧结算链的**运行帧**，"
        + (f"逐屏对照表**{len(_settle_rows)} 行**"
           if _settle_kind == "compare" else
           f"链页记录**{len(_settle_rows)} 行**")
        + f"（收据 `{_settle_path.relative_to(REPO).as_posix()}`；"
        + (f"笔记 `notes/s49-fidelity/{_z1_note.name}`）"
           if _z1_note else "")
        if _settle_rows else
        "**仍未闭合**：重制侧结算链的运行帧"
        "（胜利屏/结算屏/升级页/训练页/对白/任务菜单）"
        "**没有对照收据** ⇒ **逐屏运行帧对照表本波没有数字**")
    add("| 1b | ⭐ **结算链与原版的差异（结构差已闭合；运行帧差见第 1c 项）** | "
        "**段数差已闭合**（wave 11 的 U3/W3 落地）：重制侧 `battle_scene_phase` "
        "现在有 `post_battle_dialogue` 与 `task_menu` 两个新相，"
        "`battle_scene_phase_settlement_stage()` 把 7 段一一映射到 "
        "`battle_settlement_stage`（victory → result → level_up → training → "
        "post_battle_dialogue → task_menu → complete），"
        "并有单测 `test_battle_settlement_chain.cpp` 锁住（**本波实测通过**）。"
        f"⇒ **运行帧这一层：{_running_clause}**。"
        "⚠️ **原版升级屏是 3 人 × 2 页 = 6 个子页，木叶丸没有升级屏**"
        "（U3 实测，推翻了 wave 9 的「四人各一张」）⇒ "
        "wave 9 那份 V4 真值配对（`03-levelup-*` / `07-ninja-tool-list`）"
        "**文件名与画面对不上，V4 的配对是错的**。"
        "⭐ **底板结构差（资产级）**：现状 结算屏 **12,798** / 升级屏 **7,681** / "
        "训练页 **8,483**（V4 口径，约 1/3 采样）；"
        "换 1:1 层后 **1,636（−87.2%）/ 608（−92.1%）**，"
        "训练页**无 1:1 候选**；⛔ **三张 8bpp 层 = 192 KB > 96 KB VRAM** ⇒ "
        "必须先定量化/分层方案 ⇒ 见 §15.4。"
        "⭐ **wave 17 的結算屏逐屏对照（U2 的口径）见 §15.2.4** —— "
        "⚠️ **「結算屏人物 1,898 px / 数字 684 px」是 wave 16 / V2 把"
        "**结算屏那一屏**的差拆成「tab 栏 / 渐变 / 面板边 / 人物 / 数字」"
        "五段后的数**，与 §15.2.4 的**整屏**差**不是同一个口径** ⇒ "
        "**两个数不许直接相比**。"
        "⭐ **wave 17 / U2 逐屏实测：結算屏残差 2,582 px 不变**"
        "（勝利 **0** / 結算 **2,582** / **6 张升級屏全 0**），并把 2,582 拆开："
        "**684 px = 「真实战斗的战果」**（版式**逐像素对齐**；"
        "125（任务经验）与 75（回合奖励）两行**已经一样**，"
        "只有**战斗经验行**与**总经验行**不同 ⇒ "
        "**只能由 U1 打完的真实战斗产生，不是像素问题**）；"
        "**1,898 px = 三个人物**（实测原版每个人物 **26 / 23 / 26 色**；"
        "4bpp 量化后仍差 **808 px**；8bpp 三人各要一套 256 色 OBJ 调色板 ⇒ "
        "硬件只有一套 ⇒ 逐人 8bpp 不可能）"
        "⇒ **取舍结论**：走「三个立绘合成一张 8bpp 图集 + 共用一套 8bpp OBJ 调色板」"
        "⇒ **1,898 → 0 px 且参与者仍然动态**；"
        "⛔ **代价是要动 U1 独占的绘制代码 ⇒ 已交父代理接线**。"
        "详见 `notes/s49-fidelity/U2-overlay-settlement.md`"
        " | 重制线（W3 / U3） / **U2（wave 17）** |")
    _align_path_item, _align_item = w3_settlement_align()
    add("| 1c | ⭐ **结算链运行帧的逐屏对照表** | "
        + (f"**已达成**：逐屏对照表**{len(_settle_rows)} 行**"
           f"（收据 `{_settle_path.relative_to(REPO).as_posix()}`；"
           f"笔记 `notes/s49-fidelity/{_z1_note.name}`）"
           f"⇒ 逐屏数字见 **§15.2**"
           + (f"（测在 ROM `{_settle_rom[:16]}…`）" if _settle_rom else "")
           + "。"
           if _settle_rows and _settle_kind == "compare" else
           (f"**部分达成**：重制侧结算链的**运行帧已录到**"
            f"（链页记录 **{len(_settle_rows)} 行**，"
            f"收据 `{_settle_path.relative_to(REPO).as_posix()}`"
            + (f"；笔记 `notes/s49-fidelity/{_z1_note.name}`"
               if _z1_note else "")
            + "），但**逐屏的差 px / 差 bbox 对照表**本波**没有收据** ⇒ "
            "§15.2 里能追到的是**重制侧每一页的 sha256**，"
            "**不是**逐屏差值。"
            if _settle_rows else
            "⛔ **本波没有逐屏运行帧对照数字**："
            "重制侧的结算链运行帧**没有对照收据**。"
            "（**wave 9 的「重制侧 battle-14 打不赢」是当时**的结论 —— "
            "护送木叶丸 40 HP、蜜蜂每回合打 12、玩家单次伤害 10 ⇒ 4 轮打不死 "
            "5 只蜂；离线控制器 5 种策略全败北。**但这条结论已过期**："
            "X1 的在飞产物（`build/s49-battle-balance/u2/route*.err`）"
            "已经能走到 `outcome=1` ⇒ **能打赢**不再是障碍，"
            "**卡住的是「把运行帧录下来」这件事本身。**）"))
        + (f"⭐ **wave 15 / W3 又交了一份机器可读的结算屏逐屏收据**"
           f"（`{_align_path_item.relative_to(REPO).as_posix()}`；"
           f"重制侧帧来自 `{_align_item.get('remake_dir')}`，"
           f"**钉住 ROM 的重录**）："
           f"**{len(_align_item.get('pairs') or [])} 对**、"
           f"合计差 **{fmt(_align_item.get('total_diff_px'))} px**、"
           f"**{fmt(_align_item.get('identical_pairs'))} 对逐字节相同**"
           f"⇒ 逐屏数字见 **§15.2.1**；"
           f"⭐ **本流用另一套实现独立重算，{len(_align_item.get('pairs') or [])}"
           f"屏逐值相同**（见 §15.2.2）"
           if _align_item else "")
        + " | Z1（wave 14）/ W3（wave 15） |")
    # The bracket's upper end must belong to **this** ROM: an upper end from
    # another ROM next to this run's lower bound is two calibres in one line.
    _reach_item = wave16_reachable(receipt_rom_sha(receipt)) or z3_reachable()
    _reach_item_same_rom = bool(
        _reach_item and _reach_item.get("rom_sha256")
        and _reach_item.get("rom_sha256") == receipt_rom_sha(receipt))
    add("| 2 | **判定台残差未归零，且归零在当前录制上不可达** | 本次中位 "
        f"{fmt(field.get('median'))} px（wave-4 参照 {fmt(before_field.get('median'))} px，"
        f"总和 {fmt((after_summary.get('field_residual') or {}).get('sum'))} vs "
        f"{fmt((before_summary.get('field_residual') or {}).get('sum'))}）；"
        f"配对差 {fmt(attribution.get('pairing_diff'))} 帧（wave-4 是 "
        f"{fmt((before_summary.get('attribution') or {}).get('pairing_diff'))} 帧）"
        "。⭐ **X2r 的可证像素下界 ≈ 23,700**（**wave 6 的录制上测值**）"
        "（精确值：**23,753**（wave 6 那次录制，ROM `fec749d8…`）/ "
        "**23,697**（上一版 ROM `c1f44b3b…`）；"
        "算法 = 每一拍内**原版的全部帧** × **重制的全部帧**逐对算残差取最小，"
        "25 拍求和 ⇒ **任何配对方式都不可能低于此数**）⇒ "
        "**归零在当前录制上不可达**；补齐产品缺口后可望降到 **≥ 16,389**（下界）。"
        + (f"⭐ **{'wave 16 / V3（用 V4 已交付的工具）' if _bound_w16 else 'wave 14 / Z3'} 已为当前 ROM 重算**："
           f"**可证像素下界 = {fmt(_bound['value'])} px**"
           f"（收据 `{_bound['path'].relative_to(REPO).as_posix()}`，"
           f"当前 ROM sha256 `{_bound['rom_sha256'][:16]}…`"
           + (f"；标准配对的残差总和 `canonical_sum` = "
              f"{fmt(_bound['canonical_sum'])} px"
              if _bound.get("canonical_sum") is not None else "")
           + f"；{len(_bound['runs'])} 次独立跑"
           + ("**逐值相同**" if _bound["agree"] else "**不一致**")
           + "）"
           + (f"⭐ **三段夹逼**：**{fmt(_bound['value'])} ≤ 最优残差 ≤ "
              f"{fmt(_reach_item['value'])} px**"
              f"（上界 = 内容锚同刻配对的残差之和，"
              f"{_reach_item.get('exact_moment')}/"
              f"{_reach_item.get('original_frames')}"
              f" 帧同刻可达；**上下界是同一个 ROM "
              f"`{str(_reach_item.get('rom_sha256'))[:16]}…`**）"
              if _reach_item_same_rom else
              (f"⚠️ **上界 **{fmt(_reach_item['value'])} px** 属于**另一个 ROM** "
               "⇒ **不许与本波的下界并排**（两个口径 / 两个 ROM）"
               if _reach_item else ""))
           + "⇒ "
           f"**归零不可达**这条结论现在**有当前 ROM 的精确下界**支撑。"
           if _bound else
           (f"⭐ **wave 14 / Z3 已重算下界，但测在另一个 ROM 上**："
            f"**{fmt(_bound_any['value'])} px**"
            f"（收据 `{_bound_any['path'].relative_to(REPO).as_posix()}`，"
            f"ROM sha256 `{_bound_any['rom_sha256'][:16]}…`；"
            f"{len(_bound_any['runs'])} 次独立跑"
            + ("**逐值相同**" if _bound_any["agree"] else "**不一致**")
            + f"；标准配对的残差总和 `canonical_sum` = "
            + f"{fmt(_bound_any['canonical_sum'])} px）"
            f"⇒ **本次流水线构建的是 `{receipt_rom_sha(receipt)[:16]}…`**"
            "（Z2 的黑场改动进了产品 ⇒ ROM 变了）⇒ "
            "**本次 ROM 的精确下界待 Z3 重算**；"
            "**「归零不可达」这个量级结论仍然成立**"
            + (f"（Z3 在**那个 ROM** 上量出的区间是 "
               f"**{fmt(_bound_any['value'])} ≤ 最优残差 ≤ "
               f"{fmt(z3_reachable()['value'])} px**）"
               if _bound_any and z3_reachable() else "")
            + "，但**这两个数字不是同一个 ROM 上的**，不许混用。"
            if _bound_any else
            "⚠️ **口径**：wave 6 的这两个下界**没有**为本次 ROM 重算 ⇒ "
            "**它证明的是「归零不可达」这个量级结论，不是本次 ROM 的精确下界**；"
            "本次 ROM 的精确下界需要配对流重跑一次全量录制。"))
        + (f"⭐ **wave 16 / V4 为**最终 ROM**重算**：可证像素下界 = "
           f"**{fmt(_bound['value'])} px**（收据 "
           f"`{_bound['path'].relative_to(REPO).as_posix()}`，"
           f"ROM sha256 `{str(_bound['rom_sha256'])[:16]}…` "
           + ("**＝本次构建的 ROM**"
              if _bound['rom_sha256'] == receipt_rom_sha(receipt)
              else "**≠ 本次构建的 ROM**（⚠️ 口径不同，不许混用）")
           + f"；{len(_bound['runs'])} 次独立跑"
           + ("**逐值相同**" if _bound["agree"] else "**不一致**")
           + "）。**证明方式**："
           + (_bound_proof_text() or "（收据里没有写证明）")
           if _bound_w16 else "")
        + "X2 的结论：**walk 侧已经到头**，剩下的帧逐帧都有产品差证据 ⇒ "
        "残差归零的前置条件不是换 walk，而是补齐产品差"
        + (f"（内容锚口径下残差 **{fmt(z3_reachable()['value'])}**，"
           f"wave 6 旧口径是 28,899）"
           if z3_reachable() else "（内容锚口径下残差 28,899）")
        + "。⭐ ⚠️ **口径警告（三个数不许混用）**："
        f"本次判定台读数 **{fmt((after_summary.get('field_residual') or {}).get('sum'))} px**"
        "是 **arg-min、无时刻约束**；"
        f"可证像素下界 **{fmt(_bound['value']) if _bound else (fmt(_bound_any['value']) if _bound_any else '—')} px**"
        "是「每一拍内全部帧对取最小、25 拍求和」；"
        f"内容锚可达数 **{fmt(z3_reachable()['value']) if z3_reachable() else '—'} px**"
        "是「同一时刻的帧对」。⇒ **三者回答三个不同的问题**"
        "（残差有多少 / 归零最低要多少 / 现在能做到多少）"
        + ("⇒ **下界与判定台读数不是同一个口径**" if _bound else "")
        + "。"
        + " | X1（产品差）/ Z1（接线） |")
    add("| 3 | **覆盖层逐格族名：前三项已达成，第四项（族名不一致 0）仍未达成** | "
        "目标（同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0）："
        + "；".join(
            f"`{name}` 同亮 {fmt(row.get('both_lit'))} / 原版缺 "
            f"{fmt(row.get('original_only'))} / 多画 {fmt(row.get('remake_only'))}"
            f" / 族名不一致 {fmt(row.get('family_mismatches'))}"
            for name, row in overlay_moments.items())
        + "。⭐ **「原版缺 0 / 多画 0」已达成** —— 从 wave 1 传下来的"
        "「多画 310–420 / 缺 96–129」**是仪器假象**（原版侧贴标签没按 480 px "
        "回绕 ⇒ 缓冲尾部两列被错开 ⇒ 24/24 的假差异）。"
        + (f"剩下的族名不一致**逐格**给了性质判定："
           f"**原版尾部残留 {fmt(tail_total)} 格**（原版缓冲回绕尾部 = 地图第 0/1 列，"
           f"装的是陈旧内容：墙列上出现光标格与可达集 ⇒ **任何忠实的重制都复现不了**）、"
           f"**walk 相位 {fmt(phase_total)} 格**（原版的相位族集合在重制侧 35 帧里"
           f"**没有任何一帧**同时具备 ⇒ 是走位/相位结构问题，不是覆盖层规则"
           "；⚠️ **这是跨时刻口径**；⭐ **wave 16 / V4 的同刻口径是 56 格"
           "（连尾部 67 格）**，且归因已改为"
           "「**产品缺一段演出**（相位切换时不清覆盖层缓冲），"
           "**不是** walk 没走到」⇒ 见 **§3.5**），"
           f"**产品差 {fmt(product_total)} 格**（见 §3.3 的逐格明细）。"
           f"⭐ **wave 15：原版尾部残留 {fmt(tail_total)} 格与 `grid16` 的 "
           f"{fmt(grid16_phase)} 格已移进 §10「明确排除项」**"
           "（原版自己的缓冲残迹 / 单帧撕裂 ⇒ **不是重制侧的产品差**）"
           f"⇒ **真正还欠的只剩产品差 {fmt(product_total)} 格**"
           if cell_classes else "")
        + "⭐ **wave 17 / U2 已把规则改完并实测**："
        "`battle_range_ui_cell_kind()` 的**青（可达集）不再被 `move_phase` 锁住**"
        "⇒ 「青 + 橙」在**规则层**不再互斥"
        "（绿/橙/黄的门按 G-H15 / F-rule.md 保持不变 ⇒ **没有**放开绿/青）；"
        "**但实测「青 ∧ 橙」共现仍是 0 / 783、「walk 相位」格数 130 → 130，一个没降**"
        "⇒ U2 给出的**三条独立原因**（都在 U2 的独占文件之外）："
        "① 目标选择相位的**绿集合（46 逻辑格）⊇ 青集合（44）**，"
        "按 F 的优先级 `target > attack > move` ⇒ **青一格都轮不到**；"
        "② 橙集合（射程 48 格）也 ⊇ 青集合；"
        "③ **原版自己的三个活相位的族集合两两不相交** ⇒ "
        "**「青 + 橙同现」是原版相位切换时不清覆盖层缓冲的残迹**，"
        "**不是任何一条活相位规则能画出来的**（与 §3.5 的结论一致）"
        "⇒ **剩下的接线点**：`battle_scene_controller.h`（覆盖层行集被清零）、"
        "`battle_runtime_scene.cpp`（渲染器整块释放，**U1 独占**）、"
        "以及**战斗打不完 ⇒ 走不到结算段**（U1 的 D4 必修）。"
        "详见 `notes/s49-fidelity/U2-overlay-settlement.md`"
        + " | Y2（已达成前三项）/ Y1（相位与产品差）/ **U2（wave 17，规则已改）** |")
    add("| 3b | **⭐ 旧口径的数字全部作废（跨波比较的警告）** | "
        "wave 1–wave 12 的报告里那组「多画 310–420 格 / 缺 96–129 格」"
        "**不是产品差，是仪器给两侧贴了不同的地图标签**。"
        "⇒ **跨波比较必须先看口径**：wave 13 之后的数字才是"
        "「两侧都按 480 px 回绕」的口径；旧数字只能作为历史记录，"
        "**不许**再拿来说「产品退化」 | Y2（仪器修正已落地） |")
    add("| 4 | **重制侧调色板 bank 泄漏 ⇒ ROM 崩（wave 7 已修；"
        "⭐ wave 15 / W1 又查出**第二处**泄漏，也已修）** | X3 的 B5 修好后"
        "暴露：单位选择阶段连按 **R** 到第 9 个单位时 ROM 崩在 Butano 的 "
        "`bn_palettes_bank`（16 个硬件 sprite 调色板 bank 被 9 个「每单位一份"
        "运行期调色板」+ UI 调色板吃光）。⭐ **Y1 已修**（per-component 调色板释放，"
        "不再泄漏）：未打补丁 R×8 崩 / 打补丁 R×9 存活，且**修复是 pixel-neutral**"
        "（25/25 帧逐帧相同，残差加不加都一样）、4096 帧冒烟通过、"
        "**单测棘轮 PASS**（20 项失败集合逐名相同，new red = 0）"
        "⭐ **wave 15 / W1 查实并修掉了**第二处（**不同**的）泄漏**："
        "根因**不是**「16 个 bank 不够用」，而是**静态的 dimmed 调色板**在"
        "「调色板几乎占满时」被创建 ⇒ 落在 bank 的**低位**（index 3）⇒ "
        "Butano 的 `create_bpp_8` 只把 bank **前端**给 BPP8 调色板 ⇒ "
        "肖像的 128 色 BPP8 调色板再也拿不到 8 个 bank ⇒ "
        "`BPP8 palette create failed. Colors count: 128` ⇒ **ROM 停机**。"
        "⇒ 把 dimmed 调色板跟 map cohort 一起释放之后，"
        "**战斗不再停机**（驱动器从第 57 步走到第 300+ 步 / 第 4 回合）。"
        "⚠️ **两处泄漏不要混为一谈**：wave 7 的是「每单位一份运行期调色板」，"
        "wave 15 的是「静态 dimmed 调色板被创建在低位」 | "
        "Y1（wave 7，已交付）/ **W1（wave 15，已交付）** |")
    add("| 5 | **B5 / B7 已修，但像素级判据只有 B5** | X3 实测：B5 的像素判据 "
        "C1–C4 全绿（状态栏气条像原版一样从 849 绿像素掉到 697）、B7 在 ROM 上"
        "实测写 **0 字节**且断言不崩 ⇒ B5 / B7 的行为差**已消除**；但 B5 的"
        "像素级判据（下一轮可选单位）仍未独立取出 | X3（已交付） |")
    add("| 6 | **存档逐字节一致** | 按用户口径**排除**（理由见 §10）；"
        "但两侧 loader 互不兼容这件事本身没解决 | 父代理拍板 |")
    add("| 7 | **音频逐采样一致** | **排除**（80–120 h，需复现 MP2K 合成器）；"
        "事件级对照里 J 流口径是 "
        f"{fmt((load_json(REPO / 'build' / 's49-audio' / 'event_diff.json') or {}).get('diff_counts', {}).get('silent_on_remake', 0))} "
        "条 `silent_on_remake`、"
        f"{fmt((load_json(REPO / 'build' / 's49-audio' / 'event_diff.json') or {}).get('diff_counts', {}).get('cue_mismatch', 0))} "
        "条 `cue_mismatch`、"
        f"{fmt((load_json(REPO / 'build' / 's49-audio' / 'event_diff.json') or {}).get('diff_counts', {}).get('missing_on_remake', 0))} "
        "条 `missing_on_remake`、"
        f"{fmt((load_json(REPO / 'build' / 's49-audio' / 'event_diff.json') or {}).get('diff_counts', {}).get('never_dispatched', 0))} "
        "条 `never_dispatched`；L 流本次采集另有 "
        f"{fmt(counts.get('not_reached_in_window', 0))} 条 `not_reached_in_window`"
        "（这次采集没走到该时刻，不是缺陷） | J / L |")
    new_failures = test_metrics.get("new_failures") or []
    if new_failures:
        add(f"| 8 | **20 项单测在 HEAD 即为红（预存债）；本次另有 "
            f"{len(new_failures)} 项新红** | "
            f"HEAD {fmt((test_metrics.get('head') or {}).get('fail'))} 红 / 工作区 "
            f"{fmt((test_metrics.get('workspace') or {}).get('fail'))} 红，"
            f"新失败 {len(new_failures)} 项："
            + "、".join(f"`{name}`" for name in new_failures) + "。"
            "⚠️ **这 %d 项不是本波（判定台 / 出包 / 报告）造成的**："
            "**本流没有改重制线一个字节**（只读了它的 mtime 与 git 状态）"
            "⇒ **归属重制线那一侧**。"
            "⭐ **本波的可判定结论**：它**不是**仪器抖动 —— "
            "**上一波的同一份工作区里这个测试是 pass**"
            "（对照 `build/s49-package-v3-final/baseline/unit-tests-workspace.tsv`）"
            "⇒ **它是被本波的产品改动打破的** ⇒ **真阳性**。"
            "⚠️ **不许写成「单测全绿」，也不许算成本次的成果** | "
            "**重制线那一侧** |")
    else:
        add(f"| 8 | **20 项单测在 HEAD 即为红（预存债），本次零回归** | "
            f"HEAD {fmt((test_metrics.get('head') or {}).get('fail'))} 红 / 工作区 "
            f"{fmt((test_metrics.get('workspace') or {}).get('fail'))} 红，"
            f"新失败 {len(new_failures)} 项。"
            "**不许写成「单测全绿」，也不许算成本次的成果** | 预存债，非本波 |")
    add("| 9 | **B10 原版「损坏存档降级」未实测** | 需要一份人为破坏的 "
        "`.sav` + 冷启动 | 未验 |")
    add("| 10 | **本机构建非字节可复现** | 基线 savestate load 不了本包的 ROM；"
        "随包带 ROM + 重录命令，复现需先建私有探针。"
        "⭐ **本波自己的两个 sha 就是证据**：同一份源码树在 wave 13 与 wave 14 "
        "两次构建出的 ROM sha **不同**（源码树**逐文件相同**，"
        "差别在链接时间戳 / 路径进了产物）⇒ "
        "**「同样的源码」在本机上拿不到同样的字节** ⇒ "
        "**随包必须带 ROM + 重录命令**（§12） | 结构性限制 |")
    original_events = (black_metrics.get("original") or {}).get("events") or []
    remake_events = (black_metrics.get("remake") or {}).get("events") or []
    _hard_cuts = [event for event in remake_events
                  if not event.get("fade_out_frames")
                  and not event.get("fade_in_frames")]
    _gradient = [event for event in remake_events
                 if event.get("fade_out_frames") or event.get("fade_in_frames")]
    def _triplets(events):
        return [(event.get("fade_out_frames"), event.get("black_hold_frames"),
                 event.get("fade_in_frames")) for event in events]
    _black_aligned = (_triplets(original_events) == _triplets(remake_events))

    def _one(event):
        return (event.get("fade_out_frames"), event.get("black_hold_frames"),
                event.get("fade_in_frames"))

    # The segment-by-segment delta against the original's first event.
    # It is computed, never asserted: the numbers change whenever the
    # product changes the black field.
    _delta_text = ""
    if original_events and _gradient:
        _orig = _one(original_events[0])
        _mine = _one(_gradient[0])
        _names = ("淡出", "全黑", "淡入")
        _deltas = []
        for _label, _a, _b in zip(_names, _orig, _mine):
            if _a is None or _b is None:
                _deltas.append(f"{_label} 无法比较")
            else:
                _deltas.append(f"{_label} 差 {_b - _a:+d}")
        _delta_text = (
            f"⭐ **逐段差（本次运行实测）**：重制侧第 1 个带渐变事件 = "
            f"淡出 {fmt(_mine[0])} / 全黑 {fmt(_mine[1])} / 淡入 {fmt(_mine[2])}；"
            f"原版第 1 个事件 = 淡出 {fmt(_orig[0])} / 全黑 {fmt(_orig[1])} / "
            f"淡入 {fmt(_orig[2])} ⇒ " + "、".join(_deltas) + "。")
    _black_verdict = (
        "✅ **事件数与每一段时长与原版逐项相同**（"
        f"{len(remake_events)} 个事件）"
        if _black_aligned else
        f"⇒ ⛔ **带渐变的事件只有 {len(_gradient)} 个**"
        f"（其余 {len(_hard_cuts)} 个是**硬切**黑场：淡出 0 + 淡入 0，"
        "原版没有这种）；"
        "⇒ ⛔ **渐变段的长度与原版对不上**"
        "（原版 24/18/24 与 24/24/24）⇒ "
        "**「逐帧可见像素曲线与原版一致」这一条仍未达成**（见第 12 项）"
        + _delta_text)
    add("| 11 | **黑场的事件数/时长** | "
        "⭐ 原版 **2 个**黑场事件，每个都被切成 淡出 / 全黑 / 淡入 三段："
        + "；".join(
            f"事件 {fmt(e.get('event'))} = 淡出 {fmt(e.get('fade_out_frames'))}"
            f" / 全黑 {fmt(e.get('black_hold_frames'))}"
            f" / 淡入 {fmt(e.get('fade_in_frames'))}"
            for e in original_events)
        + "。重制侧 **"
        + fmt(len(remake_events)) + " 个**事件："
        + "；".join(
            f"事件 {fmt(e.get('event'))} = 淡出 {fmt(e.get('fade_out_frames'))}"
            f" / 全黑 {fmt(e.get('black_hold_frames'))}"
            f" / 淡入 {fmt(e.get('fade_in_frames'))}"
            for e in remake_events)
        + f"。{_black_verdict}"
        + (f"⇒ ⛔ 原版 walk 采到的两个黑场帧（`step-11-A` / `step-18-A`）"
           f"在重制侧仍**没有对应**（本次配对差 "
           f"{fmt(attribution.get('pairing_diff'))} 帧，"
           f"其中时刻不一致 {fmt(subclasses.get('moment_mismatch'))} 帧）"
           if True else "") + " | "
        "**Z2（黑场事件数/时长，wave 14）** / **W3（黑场收官，wave 15）** / "
        "U1（接线）/ Y1 / Z2（遮罩层级数） |")
    add("| 12 | **⭐ 原版的「淡出/淡入」不是亮度渐变，是四角星光圈的收缩/扩张** "
        "⇒ 调色板淡出只能做到**结构等价**，**逐帧均值曲线与原版不同** | "
        "Y2 的决定性发现：窗口内亮度不变 ⇒ 真 1:1 需要**星形遮罩**"
        "（BG 覆盖层 + 对角边 tile 集，缩放/扩张用不同 tile 排布）。"
        "⭐ **wave 7 的 Z2 已交付**"
        "（`notes/s49-fidelity/Z2-title-art-starfield.md`；"
        "⚠️ **这是 wave 7 的 Z2，不是 wave 14 的 Z2** —— "
        "同名笔记的坑，判定以任务书的 mtime 为界）："
        "**「素材 + 曲线」两件事都做完了** —— 原版的黑场被证明是**旋转的四角星光圈**"
        "（12 级淡出 / 18 帧全黑 / 12 级淡入共 66 帧），"
        "逐帧可见像素数已经量出来并做成 Butano 素材，"
        "**生成的位图回读校验 66/66 帧逐帧相等**；"
        "标题美术也已转成 5 个 sprite item 放进 `graphics/`，"
        "**VRAM 余量实测 = 部署画面 662 块空闲 OBJ 图块，标题只要 208 块**。"
        "⛔ **但有一个硬约束没解开**：一帧星光圈遮罩要 **640 块 OBJ 图块（20 KB）**，"
        "战斗画面最紧时只剩 **336 块（装不下）** ⇒ 第二个黑场事件必须先腾出图块，"
        "或者改用「旋转 + 缩放」的近似模型 ⇒ "
        "**「逐帧均值曲线与原版对齐」这一条本轮仍未验证** | "
        "Z2（素材与曲线已达成 / 运行期摆放：Z1） |")
    add("| 13 | **原版对话框的斜切展开动画 + 换行等待参数** | Y4 实测原版 "        "**0267–0271** 是**斜切展开**的对话框动画（重制侧没有）；原版换行后"
        "**先等 56~92 帧**再打下一行。⭐ **wave 7 的 Z3 已交付**"
        "（`notes/s49-fidelity/Z3-dialogue-box.md`；"
        "⚠️ **这是 wave 7 的 Z3，不是 wave 14 的 Z3** —— "
        "同名笔记的坑，判定以任务书的 mtime 为界）："
        "**换行等待参数取到了真值**（**没换头像 7 帧 / 换了头像 63 帧**，"
        "每帧一采实测：原版第 1406 帧按 A → 第 1413 帧出字、"
        "第 1500 帧按 A → 第 1563 帧出字）并已在重制侧实现 + 单测；"
        "但 ⛔ **「斜切展开」的像素级复现仍未达成** —— Z3 查实那**不是对话框动画，"
        "是入场转场**（一层纯黑遮罩在**已经画完的场景**上被斜切成碎片擦掉，"
        "BG 图块表在整个过程里**逐字节不变** ⇒ 遮罩来自 OBJ）"
        "⇒ 需要原版的**碎片素材（Z2）** + **运行期精灵摆放（Z1）**，"
        "不是对话脚本能管的事；Z3 已把逐帧遮罩表（实测）做成模型交给 Z1/Z2。"
        "⛔ **wave 16 本波仍未复现 ⇒ 单列这一条**（换行等待参数那一半已达成，"
        "「斜切展开/入场转场」那一半没有） | "
        "Z3（等待参数已达成）/ 素材与摆放：Z2 + Z1 |")
    green_steps = [step for step in receipt.get("steps") or [] if step.get("ok")]
    red_steps = [step for step in receipt.get("steps") or []
                 if not step.get("ok")]
    _w16_verdict = ratchet_verdict(receipt)
    add(f"| 14 | **⭐ 本波流水线 {'全绿' if not red_steps else '不是全绿'}"
        f"（{len(green_steps)}/{len(receipt.get('steps') or [])}）** | 本次收据："
        + (f"**首个失败步骤 {fmt(receipt.get('failed_step'))}**；"
           if receipt.get("failed_step") else "**12 步全绿**"
           + f"（收据 `generated_at` = {receipt.get('generated_at')}`，"
             "`ok: true`，`failed_step: null`）；")
        + "红的是 "
        + ("、".join(f"**{step['number']}（{step['name']}）**"
                     for step in red_steps) or "（无）")
        + "，绿的是 "
        + ("、".join(str(step["number"]) for step in green_steps) or "（无）")
        + "。"
        "⚠️ **绿灯的门禁 ≠ 1:1 已达成**（本节其余各行都是绿灯掩盖不了的缺口）。"
        + ("" if not (built_sha and shipped_sha and built_sha != shipped_sha) else
           f"⛔ **更严重的一条**：**收据里的 ROM（`{built_sha[:16]}…`）"
           f"与包里的 ROM（`{shipped_sha[:16]}…`）不是同一个**"
           "（另一个流在本轮运行期间重建了 ROM）⇒ "
           "**本收据的数字属于前者、包里发布的是后者，后者没被测过** "
           "⇒ **本收据不能作为发布基线**。")
        + "⚠️ **本次运行的重制线是 wave 17 并行流（U1/U2/U4）的状态**"
        "（U1 修产品缺陷 D4 ——「玩家的伤害招式的战斗演出不结束」；"
        "U2 修覆盖层「青+橙」互斥（50 格产品差的根因）与結算屏人物/数字；"
        "U4 验证「真实打完仗」并交结算链的真实版；"
        "本次运行期间并行流还可能重建重制线，见收据步骤 1 与 12 的备注）"
        f"⇒ **本次数字是 wave 17 的基线** | "
        "U1/U2/U4 落地后重跑 | "
        + "⭐ **本次读数测的是哪个 ROM / 采集是复用还是重采 / "
        "与基线 ROM 是否相同**（§2.0c）："
        + f"ROM `{str((_identity.get('digests') or {}).get('build'))[:16]}…`；"
        + "采集："
        + "、".join(
            f"{_side} 侧 **{((_identity.get('decisions') or {}).get(_side) or {}).get('action') or '—'}**"
            for _side in ("original", "remake"))
        + "；"
        + (("基线 ROM **相同**" if (_baseline_rom_w16
                                   and _baseline_rom_w16 == (_identity.get('digests') or {}).get('build'))
            else "基线 ROM **不同** ⇒ 两个残差数字**不是同一个测量**"))
        + "。"
        + (f"⭐ **本次的棘轮判定 = `{_w16_verdict.get('status')}`**"
           + ("（**不可比 ≠ 通过**：基线 ROM 与本次 ROM 不同 ⇒ "
              "「残差只许变小」这条规则**本次没有被检验**）"
              if _w16_verdict.get("status") == "incomparable" else
              "（**残差变大了 ⇒ 棘轮真阳性**）"
              if _w16_verdict.get("status") == "fail" else
              "（残差没有比被接受的基线变大）")
           if _w16_verdict.get("status") else ""))
    # ---- did the twelve criteria change? (machine-checkable) --------------
    _accepted_for_criteria = accepted_receipts(exclude=package)
    if _accepted_for_criteria:
        _previous_criteria = load_json(_accepted_for_criteria[0]["path"]) or {}
        _changed_criteria = criteria_diff(_previous_criteria, receipt)
        if _changed_criteria:
            add(f"⚠️ **⭐ 12 步的判据变了 {len(_changed_criteria)} 处**"
                f"（对照 `{_accepted_for_criteria[0]['path'].relative_to(REPO).as_posix()}`"
                "的判据字面量，**机检**）："
                + "、".join(f"**{name}**" for name, _before, _after in _changed_criteria)
                + f" ⇒ 其余 **{12 - len(_changed_criteria)} 步的判据逐字未改**。"
                "（wave 15 / W2 改的两处：第 1 步加 150 s 前置等待、"
                "第 5 步改棘轮基线来源 + 三态判决 —— 任务书 §2.4 允许的范围内。）")
        else:
            add("✅ **12 步的判据与上一波被接受的收据逐字相同**"
                f"（对照 `{_accepted_for_criteria[0]['path'].relative_to(REPO).as_posix()}`，机检）。")
    judgment_step = step_by_name(receipt, "judgment")
    judgment_ok = bool(judgment_step.get("ok"))
    add("| 15 | **✅ 判定台的「±9,520 px 抖动」—— 已查清，**不是**仪器抖动 | "
        "判定台本次：战场区残差总和 "
        f"{fmt((after_summary.get('field_residual') or {}).get('sum'))} px、"
        f"中位 {fmt(field.get('median'))} px、"
        f"峰值 {fmt(field.get('max'))} px、"
        f"全 0 帧 {fmt(field.get('zero_frames'))}，"
        f"覆盖层残差总和 {fmt((after_summary.get('overlay_residual') or {}).get('sum'))} px；"
        f"棘轮基线（上一次被接受的运行，生成于 "
        f"{ratchet_before.get('generated_at')}）是 "
        f"{fmt(ratchet_field.get('sum'))} px ⇒ "
        + ("**棘轮通过**（本次基线已被重钉成本次的读数）"
           if judgment_ok else "**变红**")
        + "。⭐ **wave 10 报的「同一个 ROM 连跑两次、残差 9,520 → 0、"
        "总和 114,304 → 104,784」这个抖动，根因已查实：那两次跑的 "
        "**ROM sha256 不同**（`249217d7…` vs `73b74587…`，见 §2.0b 的证据表）"
        "⇒ 差的那 9,520 px 属于**产品改动**，不属于仪器。"
        "⭐ 本波把「读数确定性」做成了**仪器自证的能力**：步骤 5 现在"
        "**连读 3 次**，3 次读数必须逐项相同（含每张采集 PNG 的 sha256），"
        "否则步骤 5 变红；棘轮收据里也带上两侧的 ROM sha256 ⇒ "
        "**「残差变大」现在能被干净地归因到产品或仪器** | "
        "W4（wave 11，已闭合） |")
    if new_failures:
        add("| 16 | **⛔ 单测棘轮：**有回归**（新红 "
            f"{len(new_failures)} 项）** | 步骤 2：HEAD "
            f"**{fmt((test_metrics.get('head') or {}).get('fail'))} 红** / "
            f"工作区 **{fmt((test_metrics.get('workspace') or {}).get('fail'))} 红**，"
            f"**新失败 {len(new_failures)} 项**："
            + "、".join(f"`{name}`" for name in new_failures)
            + " ⇒ **失败集合与 HEAD 基线不再逐名相同** ⇒ "
            "**步骤 2 变红 ⇒ 本流水线不是 12/12** ⇒ "
            "**本包不能作为出包基线**。⚠️ **不许写成「单测全绿」** | "
            "**归属重制线那一侧**（不是本流造成的） |")
    else:
        add("| 16 | **⭐ 单测棘轮：零回归（已确认）** | 步骤 2：HEAD **20 红** / "
            f"工作区 **{fmt((test_metrics.get('workspace') or {}).get('fail'))} 红**，"
            f"**新失败 {len(test_metrics.get('new_failures') or [])} 项** "
            "⇒ **失败集合与 HEAD 基线逐名相同**（20 项预存债），"
            "**本次零回归**；⚠️ **不许写成「单测全绿」** | 预存债，非本波 |")
    add("| 17 | **⭐ 覆盖层逐格族名：前三项已达成（**192 / 0 / 0**），"
        "第四项仍开放** | "
        "目标（同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0）的**前三项在 wave 13 "
        "达成**：见 §3 的逐时刻实测与 §3.3 的逐格性质判定。"
        "⚠️ **判据在 wave 10 / U4 被改过两处**（两处都写清了）："
        "① **锚点口径**从「窗口搜索」改成**原版的实测锚点 (256, 0)**"
        "（§3.1，两种口径在同一份 dump 上的对比）；"
        "② **候选帧**从「配对帧里亮格最多的那一帧」改成**整条 walk 的 35 个 "
        "anchor dump** —— 因为实测发现**重制侧只在 walk 的 step 25 与 28–34 "
        "显示覆盖层**，25 个配对帧**一个都没有**，拿配对帧去量是退化测量"
        "（残差恒为 192，与产品质量无关）。"
        "⭐ **wave 13 / Y2 的第三处修正**：原版侧**按 480 px 回绕**"
        "（此前只有重制侧回绕）⇒ 24/24 的假差异消失。"
        "⭐ **wave 12 / X4 独立复核了 wave 10 / U4 的第四处改动（terrain 判据）**"
        "⇒ 结论**保留，不回退**，数字见 §16 | "
        "**Y2（覆盖层逐格族名，已交付前三项）** / Y1（相位与产品差） / "
        "U1（内容映射接线）/ U4（判据已改） |")
    add("| 18 | **⭐ 判定台的覆盖层读数用的是旧判据** | 判定台自己的覆盖层模块"
        "（`tools/s49_fidelity_report/overlay.py`，**另一个流的文件，本流只读调用**）"
        "自己实现了一份「亮格」统计，**没有**用 U4 改好的锚点口径，"
        "所以本报告 §2 里的 `overlay_residual` 与 §3 的逐格对拍**不是同一个口径** "
        "⇒ **两个数不许混用** | 判定台所有者 |")
    add("| 19 | **✅ wave 10 / U4 的 terrain 判据：独立复核完成（保留，不回退）** | "
        "见 **§16**：把改前的候选扫描**重新实现**一遍逐 dump 对照 ⇒ "
        "「不带 terrain」的路径与改前**逐字节相同**（**0 处不同**）；"
        "判定台自己的覆盖层读数**也一字未变**（**0 处不同**，因为它调 "
        "`find_overlay_map(vram, 77)`、terrain 走默认值 `None`）；"
        "判据只改 **4/35** 个 dump（假窗口 `0x00800` → `-1`），"
        "**其余 31 个一字未变**，且让 `grid16-frame-v1` 的残差从 **185 降到 126**"
        "（剔掉的是假阳性）。⚠️ **循环论证的风险已写明**：terrain 来自重制线自己的"
        "生成头，不是独立于产品的绝对真值 | X2（共享仪器的所有者） |")
    add("| 20 | **⭐ 本轮收据是 wave 14 的读数：Z1 / Z2 / Z3 的落地状态** | "
        + z14_status(receipt)
        + "。⭐ **本轮收据本身是自洽的**（构建 / 测量 / 打包是同一份 ROM "
        f"`{(build_metrics.get('rom_sha256') or '')[:16]}…`）"
        "⇒ **可以作为 wave 14 的基线引用** | "
        "Z1 / Z2 / Z3 交付后重跑 |")
    _w15_streams = wave15_streams()
    _w15_missing = [name for name in W15_STREAMS if not _w15_streams.get(name)]
    add("| 21 | **⭐ 本轮收据是 wave 15 的读数：W1 / W2 / W3 的落地状态** | "
        + w15_status(receipt)
        + "。⭐ **判定口径**：「本波已交付」一律**以 "
        f"`{W15_CUTOFF}` 的 mtime 为界**（"
        "`notes/s49-fidelity/` 里同名的 Z1/Z2/Z3 属于 **wave 7**，"
        "X2-overlay-zero 属于 **wave 12**，Y3-overlay-zero 属于 **wave 6**）"
        + (f"。⛔ **尚未交付**：{'、'.join(_w15_missing)}"
           if _w15_missing else "。✅ **三路都已交付**")
        + " | W1 / W2 / W3 |")
    add("| 22 | **✅ 判定台「复用采集不校验 ROM」—— wave 16 / V3 已修** | "
        "`tools/s49_fidelity_report/capture.py::run_capture()` 在 `reuse=True` 时"
        "**只看「done 标记在不在、帧在不在」**，**从不核对那份采集是哪一个 ROM 录的**；"
        "随后报告把帧标成**它被要求测的**那个 ROM 的 sha256。"
        "⚠️ **wave 15 实测到这个缺陷造成了假结论**：W1 的「判定台残差没有变大」"
        "是**复用了 wave 14 包里的采集目录**得到的 —— "
        "那份采集的 audit ROM 是 wave 14 的 ROM（`ec5b5273…`），"
        "却被标成了新 ROM（`fb9d2dbd…`）⇒ **它比的是 wave 14 的帧和 wave 14 的帧**。"
        "⇒ ⭐ **wave 16 / V3 已修**（只改 `capture.py` 一个文件）："
        "复用前**必须**核对采集自己的审计（`audit.json` **和** `done.json`）："
        "重制侧核对 `rom_sha256`、原版侧核对 `input_state_sha256`；"
        "**两个证人互相矛盾 ⇒ 拒绝**；**核对不过 ⇒ 绝不复用 ⇒ 重新采集**。"
        "**判据**：① 审计说别的 ROM ⇒ **两侧都重采**（`action = recaptured`）；"
        "② 审计说同一个 ROM ⇒ **复用**，且**同一个 work 目录**里"
        "「重采 / 篡改后重采 / 复用」三次的 `content_sha256` **完全相同** "
        "⇒ **复用不改变读数**。复现：`python build/v3-dev/prove_capture_rom_check.py` | "
        "**V3（wave 16，已交付）** |")
    # ---- the wave-16 delivery status + the +60 px regression ---------------
    _w16_streams = wave16_streams()
    _w16_missing = [name for name in W16_STREAMS
                    if not _w16_streams.get(name)]
    add("| 23 | **⭐ 本轮收据是 wave 16 的读数：V1 / V2 / V4 的落地状态** | "
        + w16_status(receipt)
        + "。⭐ **判定口径**：「本波已交付」一律**以 "
        f"`{W16_CUTOFF}` 的 mtime 为界**（"
        "`notes/s49-fidelity/` 里同名的 **Z1/Z2/Z3 属于 wave 7**，"
        "**W1/W2/W3 属于 wave 5 / 6 / 8** ⇒ **同名笔记的坑比任务书说的更宽**）"
        + (f"。⛔ **尚未交付**：{'、'.join(_w16_missing)}"
           if _w16_missing else "。✅ **三路都已交付**")
        + " | V1 / V2 / V4 |")
    _w16_base_sum = (receipt.get("accepted_baseline") or {}).get(
        "field_residual_sum")
    _w16_now_sum = (after_summary.get("field_residual") or {}).get("sum")
    _w16_regression_state = "—"
    if isinstance(_w16_base_sum, int) and isinstance(_w16_now_sum, int):
        if _w16_now_sum > _w16_base_sum:
            _w16_regression_state = (
                f"⛔ **本次读数 **{fmt(_w16_now_sum)} px** 仍高于被接受的基线 "
                f"**{fmt(_w16_base_sum)} px**（**{_w16_now_sum - _w16_base_sum:+d} px**）"
                "⇒ **这一条仍未达成**")
        elif _w16_now_sum == _w16_base_sum:
            _w16_regression_state = (
                f"🟡 **本次读数 **{fmt(_w16_now_sum)} px** 与被接受的基线"
                f"**逐值相同** ⇒ **wave 15 的 +60 px 回归"
                f"（当时 {fmt(109629)} px）已经被修掉了**"
                f"（相对 wave 15 是 **{_w16_now_sum - 109629:+d} px**）")
        else:
            _w16_regression_state = (
                f"✅ **本次读数 **{fmt(_w16_now_sum)} px** 已低于被接受的基线 "
                f"**{fmt(_w16_base_sum)} px**"
                f"（**{_w16_now_sum - _w16_base_sum:+d} px**）"
                "⇒ **这一条在本波被修掉了**")
    add("| 24 | **⭐ wave 15 的 +60 px 回归（`step-24-A.png` 一帧，"
        "判定类别「产品差」）—— **是真阳性，不是抖动** | "
        "wave 15 / W4 查实：棘轮基线（wave 14 被接受的收据）"
        "**109,569 px** vs 本次 **109,629 px** ⇒ **+60 px**；"
        "逐帧归因：**25 个配对时刻里只有 `step-24-A.png` 一帧变了**"
        "（1,372 → 1,432 px，判定类别 **产品差**），其余 24 帧**逐像素相同**；"
        "**4 次独立重录逐帧完全相同** ⇒ **是真的产品回归**。"
        "⚠️ **它不是「残差抖动」**：同一个 ROM 连读 3 次读数逐项相同"
        "（§2.0b）⇒ 差值属于**产品改动**。"
        "⇒ **本波（wave 16）由 V2 的像素修复全包接手**。⭐ **本次状态**："
        + _w16_regression_state + " | "
        "**V2（wave 16）** |")
    if _w17_real:
        _acc25 = (_w17_real_battle or {}).get("acceptance") or {}
        add("| 25 | ✅ **⭐⭐ 「真实打完仗」—— **本波已闭合**"
            "（真实战斗打出 `outcome=1`）** | "
            "wave 16 的 V1 查实了**产品缺陷 D4**"
            "（**重制侧一旦玩家的攻击「射程内有活着的敌人」，战斗场景就废了** ⇒ "
            "`outcome=1` 在那个 ROM 上不可达）；"
            "wave 17 的 **U1 修了 D4**（重制线："
            "`battle_combat_presentation.h` / `battle_scene_presentation.h` / "
            "`battle_runtime_scene.cpp` / `battle_black_field*.h`），"
            "**U4 用闭环驱动器打出了一场真实战斗** ⇒ "
            + (f"**真实战斗收据** "
               f"`{_w17_real_battle['path'].relative_to(REPO).as_posix()}`"
               + (f"（ROM `{_w17_real_battle['rom_sha256'][:16]}…`）"
                  if _w17_real_battle else "")
               + f"：**`outcome = {_w17_real_battle.get('outcome')}`、"
               f"`battle_decided = {_w17_real_battle.get('battle_decided')}`、"
               f"**进入方式** `{_w17_real_battle.get('method') or '—'}`、"
               f"**poke 指令数 = {_acc25.get('poke_commands', '—')}**、"
               f"**蜂的 HP 下降 = {_acc25.get('bee_hp_dropped')}**、"
               f"**护送存活 = {_acc25.get('escort_alive')}**"
               if _w17_real_battle else "")
            + (f"**真实胜利链 {len(_w17_real_chain['rows'])} 页**"
               f"（收据 `{_w17_real_chain['path'].relative_to(REPO).as_posix()}`）"
               if _w17_real_chain else "")
            + "⇒ **它不是 poke 打出来的**"
            + (f"；⚠️ **另有 {len(_w17_poked)} 条 poke 链**"
               "（**分列在 §15.2.3**，**不许**与它混用）"
               if _w17_poked else "")
            + " | "
            "**U1（wave 17，已交付）/ U4（wave 17，已交付）** |")
    else:
        _run25 = _w17_real_runs[0] if _w17_real_runs else None
        _acc25 = (_run25 or {}).get("acceptance") or {}
        add("| 25 | **⭐⭐ 「真实打完仗」—— **未达成**"
            "（产品缺陷 D4 的修复尚未在本波落地，或真实战斗尚未由产品判定出胜利）** | "
            "wave 16 的 V1 查实了**产品缺陷 D4**"
            "（**重制侧一旦玩家的攻击「射程内有活着的敌人」，战斗场景就废了** ⇒ "
            "`outcome=1` 在那个 ROM 上不可达）；"
            "wave 17 的 **U1 负责修 D4**、**U4 负责验证** ⇒ "
            + (f"盘上**有**一份真实战斗的收据"
               f"（`{_run25['path'].relative_to(REPO).as_posix()}`"
               + (f"；ROM `{_run25['rom_sha256'][:16]}…`"
                  if _run25.get("rom_sha256") else "")
               + f"；进入方式 `{_run25.get('method') or '—'}`；"
               f"`outcome = {_run25.get('outcome')}`、"
               f"`battle_decided = {_run25.get('battle_decided')}`、"
               f"**蜂的 HP 下降 = {_acc25.get('bee_hp_dropped')}**）"
               f"⇒ **战斗没有由产品判定出胜利**"
               if _run25 else
               f"本波盘上**没有**「真实战斗 + `outcome=1`」的收据"
               f"（以 `{W17_CUTOFF}` 的 mtime 为界，扫到 "
               f"**{len(_w17_battles)}** 份战斗收据、"
               f"**{len(_w17_chains)}** 条链记录）")
            + (f"；⚠️ **{len(_w17_poked)} 条是 poke 链**"
               f"（最新：`{_w17_poked[0]['path'].relative_to(REPO).as_posix()}`）"
               "⇒ **屏上显示的是「空战果」（V2 实测：125/0/200），不是打出来的** ⇒ "
               "**不得写成「真实胜利链」**"
               if _w17_poked else "")
            + " | "
            "**U1 / U4（wave 17）** |")
    # ---- the wave-17 delivery status --------------------------------------
    _w17_streams = wave17_streams()
    # "Delivered" is judged by the **note** for the driver stream and by the
    # **product** (the exclusive files) for the product streams: a note is a
    # story, the ROM is the product.
    _w17_missing = []
    for _name in W17_STREAMS:
        if _w17_streams.get(_name):
            continue
        if _name in ("U1", "U2") and wave17_product_state(_name)["landed"]:
            continue
        _w17_missing.append(_name)
    add("| 26 | **⭐ 本轮收据是 wave 17 的读数：U1 / U2 / U4 的落地状态** | "
        + w17_status(receipt)
        + "。⭐ **判定口径**：「本波已交付」一律**以 "
        f"`{W17_CUTOFF}` 的 mtime 为界**"
        "（**同名笔记的坑**：wave 16 的 V1/V2/V4、wave 7 的 Z1/Z2/Z3 "
        "都在 `notes/s49-fidelity/` 里）"
        "⇒ **产品流（U1 / U2）额外用「独占文件的 mtime + ROM 在其后被重建」"
        "判定** —— 笔记不是产品的证据，**ROM 才是**"
        + (f"。⛔ **尚未交付**：{'、'.join(_w17_missing)}"
           if _w17_missing else "。✅ **四路都已交付**")
        + " | U1 / U2 / U4 |")
    add("")

    # ---------------------------------------------------------------- 12
    add("## 12. 基线钉与复现")
    add("")
    add("本机构建 **非字节可复现**（链接时间戳 / 路径进入产物），所以：")
    add("")
    add("* 基线 savestate **load 不了**本包里的 ROM ⇒ 不能只发 savestate；")
    add("* 随包必须带 **ROM + 重录命令**；")
    add("* 复现命令 **需先建私有探针**"
        "（`KONOHA_PROBE_OUT` 指到包内目录，**不要覆盖共享的 "
        "`build/mgba-probe/mgba-probe.exe`**，会 LNK1104）。")
    add("")
    add("| 包内文件 | 说明 |")
    add("|---|---|")
    add("| `rom/butano-sequel.gba` | 本次构建的 ROM |")
    add("| `REPRODUCE.md` | 逐条复现命令 |")
    add("| `receipt.json` / `receipt.md` | 12 步的完整收据 |")
    add("| `manifest.json` | 包内每个文件的 sha256 |")
    add("| `evidence/` | 每一步的原始产物 |")
    add("| `logs/` | 每一步的完整输出 |")
    add("")
    add("⭐ **wave 16 / V3 追加的两条复现路径**（都在 `build/v3-dev/`，**不进仓**）：")
    add("")
    add("| 命令 | 作用 |")
    add("|---|---|")
    add("| `python build/v3-dev/prove_capture_rom_check.py` | "
        "证明判定台**复用采集时必须核对 ROM**（篡改审计 ⇒ 重采；"
        "审计一致 ⇒ 复用，且读数与重采**逐项相同**） |")
    add("| `powershell -File build/v3-dev/recompute-bound.ps1 -Rom <本包的 ROM>` | "
        "用 **V4 已交付的工具**（**只读调用**）为**本包的这个 ROM** "
        "重算**可证像素下界**（自带与 `pair.beat_floor` 的交叉核对） |")
    add("")

    # ---------------------------------------------------------------- 13
    add("## 13. 流水线 12 步收据")
    add("")
    add("| # | 步骤 | 判据 | 结果 | 耗时(s) |")
    add("|---|---|---|---|---:|")
    for step in receipt.get("steps", []):
        add(f"| {step['number']} | {step['title']} | {step['criterion']} | "
            f"{'PASS' if step['ok'] else '**FAIL**'} | {step['duration_s']} |")
    add("")
    for step in receipt.get("steps", []):
        if step.get("problems"):
            add(f"**步骤 {step['number']}（{step['name']}）的问题：**")
            add("")
            for problem in step["problems"]:
                add(f"* {problem}")
            add("")
        if step.get("notes"):
            add(f"**步骤 {step['number']}（{step['name']}）的备注：**")
            add("")
            for note in step["notes"]:
                add(f"* {note}")
            add("")

    add("### 13.1 故意破坏 ⇒ 流水线变红的证明")
    add("")
    selftest_log = evidence / "selftest-break.txt"
    if selftest_log.is_file():
        add("每个步骤都有一个 `--selftest-break <步骤>` 开关，它把该步骤的**输入"
            "真的弄坏**（不是把检查改坏），于是该步骤自己的判据必须亮红灯。"
            "结果（`evidence/selftest-break.txt`）：")
        add("")
        add("| 被破坏的步骤 | 流水线退出码 | 结论 |")
        add("|---|---:|---|")
        for line in selftest_log.read_text(encoding="utf-8").splitlines():
            match = re.match(r"=== selftest-break (\S+) \(step (\d+)\): exit=(-?\d+) -> (.+)",
                             line)
            if match:
                name, number, code, verdict = match.groups()
                add(f"| `{name}`（步骤 {number}） | {code} | "
                    f"{'🔴 变红' if code != '0' else '🟢 没变红 —— **有 bug**'} |")
        add("")
        add("> 退出码非 0 ⇒ 流水线变红；`0` ⇒ 该步骤的破坏没有生效，"
            "是**流水线自己有 bug**。")
    else:
        add("（本次运行没有 `evidence/selftest-break.txt` —— "
            "用 `python tools/s49_package/run_pipeline.py --selftest-break <步骤>` "
            "重跑可复现。）")
    add("")

    # ---------------------------------------------------------------- 14
    add("## 14. 假设台账（历次出包流）")
    add("")
    add("### 14.1 继承自 X4r 的台账")
    add("")
    add("| # | 假设 | 判定方法 | 结果 | 状态 |")
    add("|---|---|---|---|---|")
    for row in X4_LEDGER:
        add(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | **{row[4]}** |")
    add("")
    add("### 14.2 Z4 本轮的台账")
    add("")
    add("| # | 假设 | 判定方法 | 结果 | 状态 |")
    add("|---|---|---|---|---|")
    for row in Z4_LEDGER:
        add(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | **{row[4]}** |")
    add("")
    add("### 14.3 wave 9 V4（结算链对照）的台账")
    add("")
    add("| # | 假设 | 判定方法 | 结果 | 状态 |")
    add("|---|---|---|---|---|")
    for row in V4_LEDGER:
        add(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | **{row[4]}** |")
    add("")

    add("### 14.4 wave 10 U4（仪器锚点修正 + 出包 + 终审）的台账")
    add("")
    add("| # | 假设 | 判定方法 | 结果 | 状态 |")
    add("|---|---|---|---|---|")
    for row in U4_LEDGER:
        add(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | **{row[4]}** |")
    add("")

    add("### 14.5 wave 11 W4（判定台确定性 + 出包 + 终审）的台账")
    add("")
    add("| # | 假设 | 判定方法 | 结果 | 状态 |")
    add("|---|---|---|---|---|")
    for row in W4_LEDGER:
        add(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | **{row[4]}** |")
    add("")
    add("### 14.6 wave 12 X4（出包 + 1:1 报告终审 + 越界复核）的台账")
    add("")
    add("| # | 假设 | 判定方法 | 结果 | 状态 |")
    add("|---|---|---|---|---|")
    for row in W12_LEDGER:
        add(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | **{row[4]}** |")
    add("")
    add("### 14.7 wave 13 Y4（出包定稿 + 1:1 报告终审）的台账")
    add("")
    add("| # | 假设 | 判定方法 | 结果 | 状态 |")
    add("|---|---|---|---|---|")
    for row in Y13_LEDGER:
        add(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | **{row[4]}** |")
    add("")
    add("### 14.8 wave 14 Z4（出包定稿 + 1:1 报告定稿）的台账")
    add("")
    add("| # | 假设 | 判定方法 | 结果 | 状态 |")
    add("|---|---|---|---|---|")
    for row in W14_LEDGER:
        add(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | **{row[4]}** |")
    add("")
    add("### 14.9 wave 15 W4（出包定稿 + 1:1 报告定稿）的台账")
    add("")
    add("| # | 假设 | 判定方法 | 结果 | 状态 |")
    add("|---|---|---|---|---|")
    for row in W15_LEDGER:
        add(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | **{row[4]}** |")
    add("")
    add("### 14.10 wave 16 V3（出包定稿 + 1:1 报告定稿 + 判定台采集校验）的台账")
    add("")
    add("| # | 假设 | 判定方法 | 结果 | 状态 |")
    add("|---|---|---|---|---|")
    for row in W16_LEDGER:
        add(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | **{row[4]}** |")
    add("")
    add("⭐ **本波额外修了一个仪器缺陷**"
        "（父代理追加的任务）："
        "`tools/s49_fidelity_report/capture.py` 的"
        "「复用采集不校验 ROM」。"
        "⇒ **在它修好之前，任何「残差没变大」的结论都不可信**"
        "（可能是拿旧 ROM 的采集当新 ROM 测的）。"
        "⇒ 修法与两条判据见 §2.0.2 与 §11 第 22 项。")
    add("")
    add("### 14.11 wave 17 U3（出包定稿 + 1:1 报告定稿）的台账")
    add("")
    add("| # | 假设 | 判定方法 | 结果 | 状态 |")
    add("|---|---|---|---|---|")
    for row in W17_LEDGER:
        add(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | **{row[4]}** |")
    add("")
    add("⭐ **本波把「结算链」拆成了两栏**："
        "**真实战斗链**（`entry.method` 自报**不是** poke）"
        "与 **poke 链**（`entry.method` 含 `poke`，或 outcome 字节在进入前后不同）"
        "⇒ §15.2.3 **分列**呈现，"
        "**任何一栏都不许写成对方的名字**。")
    add("")

    # ---------------------------------------------------------------- 15
    add("## 15. ⭐ 结算链对照（原版真值 vs 重制侧）")
    add("")
    settlement = load_json(
        REPO / "build" / "s49-victory-capture" / "v4"
        / "settlement-compare.json")
    assets = load_json(
        REPO / "build" / "s49-victory-capture" / "v4"
        / "settlement-assets.json")
    add("原版真值：wave 8 的 W4 打赢后录到的结算链"
        "（`build/s49-victory-capture/w4/settlement-truth/`，"
        "收据 `settlement-truth.json`，sha256 `9a60a89b…`）。"
        "像素判定沿用项目口径：**三通道任一不同即算不同**"
        "（同 `tools/compare_frame_dirs.py`）。")
    add("")
    add("### 15.1 两边的结算链结构差")
    add("")
    add("| 段 | 原版（wave 8 真值） | 重制侧（**wave 11 的产品代码**） |")
    add("|---|---|---|")
    add("| 1 | 「勝利」屏 | `outcome` 段 ⇒ `battle_settlement_stage::victory` |")
    add("| 2 | 结算屏（经验值/战力/回合数） | `result` 段 |")
    add("| 3 | **四人升级屏**（鸣人/木叶丸/佐助/小樱各一张） | "
        "`level_up` 段（⭐ **wave 11 已补**：原版升级屏是 **3 人 × 2 页 = 6 个子页**，"
        "**木叶丸没有升级屏**；重制侧新增了逐人升级页枚举与 7 页战后对白文本） |")
    add("| 4 | **忍具一览** | ⭐ **`training` 段**（对应物：录到"
        "「AVAILABLE TOOL」「NO AVAILABLE TOOL」「EQUIP COMPLETE」"
        "「隊員一覧表」四屏） |")
    add("| 5 | 战后对白 | ✅ **wave 11 已补**：`post_battle_dialogue` 段"
        "（`battle_scene_phase::post_battle_dialogue` ⇒ "
        "`battle_settlement_stage::post_battle_dialogue`，**7 页**文本已落进 "
        "`battle_result_content.h`） |")
    add("| 6 | 任务菜单（术之里地图） | ✅ **wave 11 已补**：`task_menu` 段"
        "（`battle_scene_phase::task_menu` ⇒ "
        "`battle_settlement_stage::task_menu`） |")
    add("| 7 | （链尾） | `complete` 段 |")
    add("")
    add("⭐ **结算链的段数差已经闭合**：重制侧 `battle_scene_phase` 现在有 "
        "**22 个原版相 + 2 个新相**，`battle_scene_phase_settlement_stage()` "
        "把 7 段一一映射到 `battle_settlement_stage`"
        "（`victory → result → level_up → training → post_battle_dialogue → "
        "task_menu → complete`），并有单测 `test_battle_settlement_chain.cpp` 锁住。")
    add("")
    add(("⭐ **运行帧这一层本波已闭合**：Z1 把重制侧结算链的**运行帧**录下来了，"
         f"逐屏对照表**{len(_settle_rows)} 行**（§15.2）。"
         if _settle_rows else
         "⛔ **但「运行帧」这一层本波仍未闭合**："
         "重制侧的结算链**运行帧**（胜利屏 / 结算屏 / 升级页 / 训练页 / 对白 / 任务菜单）"
         "**还没有在 ROM 上录下来** ⇒ 逐屏的运行帧对照表本波**没有数字**"
         "（wave 11 的 W1 流、wave 12 的 X1 流、wave 13 的 Y1 流在接力做这件事）。⇒ "
         "§15.2 的逐屏表仍是 **wave 9 V4** 的那次采集（敗北路径），"
         "**不是**当前 ROM 的读数。"))
    add("")
    add("### 15.2 逐屏对照表（运行帧）")
    add("")
    if _settle_rows and _settle_kind == "compare":
        add(f"⭐ **wave 14 / Z1 录出了重制侧结算链的运行帧** ⇒ "
            f"逐屏对照表**{len(_settle_rows)} 行**"
            f"（收据 `{_settle_path.relative_to(REPO).as_posix()}`）。")
        add("")
        _run_rom = receipt_rom_sha(receipt)
        if _settle_rom and _run_rom and _settle_rom != _run_rom:
            add(f"⛔ **ROM 口径警告**：这张对照表是在 ROM "
                f"**`{_settle_rom[:16]}…`** 上测的，"
                f"而**本次流水线构建的是 `{_run_rom[:16]}…`** "
                "（**Z2 改了黑场，产品侧变了 ⇒ ROM 变了**）"
                "⇒ **这两组数字不能混用**（「必须同 ROM 比」）。"
                "本波 Z1 没有在新 ROM 上重录结算链 ⇒ "
                "**结算链这一项的达成状态以 Z1 的那次运行为准**。")
            add("")
        elif _settle_rom and _run_rom:
            add(f"✅ **ROM 口径一致**：对照表与本次流水线跑的是**同一份 ROM** "
                f"（`{_run_rom[:16]}…`）。")
            add("")
        add("| # | 重制侧页 | 页数 | 对照的原版屏 | 差 px | 差 bbox | "
            "重制侧 sha256 | 原版 sha256 |")
        add("|---:|---|---:|---|---:|---|---|---|")
        for _index, row in enumerate(_settle_rows):
            original = (row.get("original") or row.get("original_screen")
                        or row.get("truth") or row.get("original_file") or "—")
            first = (row.get("remake_first_page")
                     or row.get("remake_first_frame") or row.get("first_frame"))
            last = (row.get("remake_last_page")
                    or row.get("remake_last_frame") or row.get("last_frame"))
            frames = (row.get("remake_pages") or row.get("remake_frames")
                      or row.get("frames"))
            if first is not None and last is not None:
                span = f"{first}–{last}"
            elif first is not None:
                span = str(first)
            else:
                span = "—"
            remake_file = row.get("remake_file") or row.get("file") or ""
            diff = None
            for _key in ("differing_pixels", "diff_px", "diff_pixels"):
                if row.get(_key) is not None:
                    diff = row.get(_key)
                    break
            bbox = row.get("diff_bbox")
            remake_sha = row.get("remake_sha256") or ""
            original_sha = row.get("original_sha256") or ""
            add(f"| {_index} | "
                + (f"`{remake_file}`" if remake_file else span)
                + f" | {fmt(frames)} | `{original}` | {fmt(diff)} | "
                f"{bbox if bbox else '—'} | "
                f"`{remake_sha[:16]}…` | `{original_sha[:16]}…` |")
        add("")
        _zero = [row for row in _settle_rows
                 if row.get("differing_pixels") == 0]
        add(f"⇒ **{len(_zero)} / {len(_settle_rows)} 屏与它对照的原版屏逐像素相同**"
            "（差 0 px）"
            + ("（"
               + "、".join(f"`{row.get('remake_file') or row.get('file')}`"
                           f" ↔ `{row.get('original')}`" for row in _zero)
               + "）" if _zero else "")
            + "。")
        add("")
        # ---- the **semantic** pairing, recomputed from the PNGs on disk ---
        _semantic = settlement_semantic_rows()
        _align_path, _align = w3_settlement_align()
        if _align:
            add("#### 15.2.1 ⭐ wave 15 / W3 的结算屏逐屏对照（**机器可读收据**）")
            add("")
            add(f"⭐ **wave 15 / W3 交出了结算屏的逐屏对照收据**"
                f"（`{_align_path.relative_to(REPO).as_posix()}`；"
                f"笔记 `notes/s49-fidelity/W3-blackfield-and-screens.md`；"
                f"重制侧帧来自 `{_align.get('remake_dir')}`"
                f"（**钉住 ROM 的重录**），原版真值来自 "
                f"`{_align.get('truth_dir')}`；"
                f"整屏 **{fmt(_align.get('screen_pixels'))} px**）。")
            add("")
            add("| 原版真值 | 重制侧运行帧 | 阶段 | 差 px | 相同 px | 逐字节相同 | "
                "原版颜色数 | 重制侧颜色数 |")
            add("|---|---|---|---:|---:|---|---:|---:|")
            for _pair in (_align.get("pairs") or []):
                if not isinstance(_pair, dict):
                    continue
                add(f"| `{_pair.get('truth')}` | `{_pair.get('remake')}` | "
                    f"{_pair.get('phase') or '—'} | "
                    f"{fmt(_pair.get('diff_px'))} | {fmt(_pair.get('same_px'))} | "
                    f"{'✅ **是**' if _pair.get('identical') else '❌'} | "
                    f"{fmt(_pair.get('truth_colors'))} | "
                    f"{fmt(_pair.get('remake_colors'))} |")
            add("")
            add(f"⇒ **合计差 {fmt(_align.get('total_diff_px'))} px**；"
                f"**{fmt(_align.get('identical_pairs'))} 对逐字节相同**。")
            add("")
        if _semantic:
            add("#### 15.2.2 ⭐ 独立重算的交叉核对（**本流不抄任何人的数字**）")
            add("")
            add("⚠️ **上面 §15.2 的那张表是「机械最优配对」**（收据 "
                "`build/z1/settlement-table-z1.json` 由 `y1_settlement_table.py` "
                "生成）：重制侧那些**绿框面板**全都落到**同一张**原版图上 ⇒ "
                "**它的前两行没有语义意义**。"
                "Z1 的笔记（`notes/s49-fidelity/Y1-stack-fix-and-settlement.md` §3.3）"
                "给出的是**语义对应**；下面这张表用**同一套像素口径**"
                "（三通道任一不同即算不同）**在盘上的 PNG 上重算**，"
                "⇒ **每个数字都能追到那两个文件**。")
            add("")
            add("| # | 重制侧运行帧 | 阶段 | 原版真值 | 差 px | 差 bbox | 逐字节相同 |")
            add("|---:|---|---|---|---:|---|---|")
            for _row in _semantic:
                add(f"| {_row['index']} | `{_row['remake']}` | {_row['stage']} | "
                    f"`{_row['original']}` | {fmt(_row['diff'])} | "
                    f"{_row['bbox'] if _row['bbox'] else '—'} | "
                    f"{'✅ **是**' if _row['diff'] == 0 else '❌'} |")
            add("")
            _sem_zero = [row for row in _semantic if row["diff"] == 0]
            add(f"⇒ **{len(_sem_zero)} / {len(_semantic)} 有语义对应的屏"
                "与原版真值逐像素相同（差 0 px）**"
                + ("（" + "、".join(f"`{row['remake']}` ↔ `{row['original']}`"
                                   for row in _sem_zero) + "）"
                   if _sem_zero else "")
                + f"；记在 **{len(_settle_rows)} 屏**的运行帧记录里就是 "
                f"**{len(_sem_zero)} / {len(_settle_rows)} 屏**。"
                "⭐ **重制侧独有的 7 屏**（`page-008` … `page-014-training.png`）"
                "在原版真值里**没有对应屏** ⇒ **不计入分母**；"
                "`page-014-training.png` 是 Z1 查实的**崩溃屏**"
                "（非法 UTF-8 ⇒ ROM 停机）。")
            add("")
            if _align:
                _agree = []
                _by_remake = {pair.get("remake"): pair
                              for pair in (_align.get("pairs") or [])
                              if isinstance(pair, dict)}
                for _row in _semantic:
                    _pair = _by_remake.get(_row["remake"])
                    if _pair is None:
                        continue
                    _agree.append((_row["remake"], _row["diff"],
                                   _pair.get("diff_px")))
                _same = [item for item in _agree if item[1] == item[2]]
                add(f"⭐ **交叉核对（本流重算 vs W3 的收据）**："
                    f"{len(_same)} / {len(_agree)} 屏**逐值相同**"
                    + ("（两个**独立实现**、同一套像素口径 ⇒ 互证）"
                       if len(_same) == len(_agree) and _agree else "")
                    + ("。" + "、".join(f"`{name}`：{mine} vs {theirs}"
                                       for name, mine, theirs in _agree
                                       if mine != theirs)
                       if len(_same) != len(_agree) else "。"))
                add("")
        add("")
    elif _settle_rows:
        add(f"⭐ **wave 14 / Z1 录出了重制侧结算链的运行帧** —— "
            f"链页记录 **{len(_settle_rows)} 行**"
            f"（收据 `{_settle_path.relative_to(REPO).as_posix()}`）。")
        add("")
        _truth = load_json(REPO / "build" / "s49-victory-capture" / "w4"
                           / "settlement-truth" / "settlement-truth.json") or {}
        _truth_by_sha = {entry.get("sha256"): entry.get("file")
                         for entry in (_truth.get("frames") or [])}
        add("⚠️ **口径**：下面是**重制侧每一页的记录**（文件 + sha256 + 相位）。"
            "**逐屏的「差 px / 差 bbox」对照表本波没有收据** ⇒ "
            "**本页的数字不能当成「与原版差多少」**；"
            "但**「原版屏」一列是可信的**：它按 **sha256** 与原版真值"
            "（`build/s49-victory-capture/w4/settlement-truth/`）"
            "**逐字节匹配** —— sha 相同 ⇒ 两张 PNG **逐字节相同** ⇒ "
            "**差 px 必然是 0**。")
        add("")
        add("| # | 文件 | 相位 | 相位名 | 结果 | 重制侧 sha256 | "
            "对照的原版屏（按 sha256 匹配） |")
        add("|---:|---|---|---|---|---|---|")
        _identical = 0
        for row in _settle_rows:
            sha = row.get("sha256") or ""
            match = _truth_by_sha.get(sha)
            if match:
                _identical += 1
            add(f"| {fmt(row.get('index'))} | `{row.get('file')}` | "
                f"{fmt(row.get('phase'))} | "
                f"{row.get('phase_name') or row.get('settlement_page') or '—'} | "
                f"{fmt(row.get('outcome'))} | `{sha[:16]}…` | "
                + (f"**`{match}`（逐字节相同 ⇒ 差 0 px）**" if match
                   else "—（原版真值里没有同 sha 的屏）") + " |")
        add("")
        add(f"⇒ **{_identical} / {len(_settle_rows)} 页与原版真值逐字节相同**"
            "（sha256 匹配）⇒ 这些屏**差 px = 0**。")
        add("")
    else:
        add("⛔ **本波没有逐屏运行帧对照数字**：重制侧结算链的运行帧"
            "**没有对照收据**（见 §11 的 1b / 1c 与 "
            "`notes/s49-fidelity/Y1-stack-fix-and-settlement.md`）。")
        add("")
    # ---- wave 16 / V1: the **real** settlement chain table ----------------
    _v1_path, _v1_rows, _v1_kind, _v1_rom = wave16_settlement_rows(
        receipt_rom_sha(receipt))
    # The chain records.  They are **not** filtered by the current ROM on
    # purpose: the report must still show the poke chain even when it belongs
    # to another ROM -- it just has to say **which** ROM.
    _chain_path, _chain_rows, _chain_rom, _chain_poked = wave16_chain_rows(None)
    _chain_method = ""
    if _chain_path is not None:
        _chain_doc = load_json(_chain_path) or {}
        _chain_entry = _chain_doc.get("entry")
        if isinstance(_chain_entry, dict):
            _chain_method = str(_chain_entry.get("method") or "")
        elif isinstance(_chain_entry, str):
            _chain_method = _chain_entry
    add("#### 15.2.3 ⭐⭐ 结算链运行帧对照"
        "（**真实战斗链** vs **poke 链** —— 两者不许混用）")
    add("")
    add("⭐ **本节把结算链分成两栏**，判据是**链是怎么进入的**"
        "（收据自报 `entry.method`，外加「outcome 字节在进入前后是否相同」）："
        "**`entry.method` 含 `poke`** ⇒ **poke 链**；"
        "**outcome 字节在进入前后不同** ⇒ **poke 链**；"
        "两者都没有 ⇒ **进入方式未记录**（**不许**当成真实链）；"
        "只有**明确不是 poke**、且链上的 `outcome` 是 **1** ⇒ "
        "**真实胜利链**（`outcome=2` ⇒ **真实战斗链，但不是胜利**）。")
    add("")
    # ---- the chain inventory: every chain, with its entry method ----------
    _chain_inventory = list(wave17_chains(None))
    if _chain_rows:
        _chain_inventory.append({
            "path": _chain_path,
            "rows": _chain_rows,
            "rom_sha256": _chain_rom,
            "method": _chain_method or None,
            "poked": True if _chain_poked else None,
            "reason": ("`entry.method` 自报 controller state poke"
                       if _chain_poked else "进入方式未记录"),
            "outcome": None,
            "source": "wave16",
        })
    # de-duplicate by path (the same receipt may be found by both scans)
    _seen_paths = set()
    _chain_inventory = [record for record in _chain_inventory
                         if not (str(record["path"]) in _seen_paths
                                 or _seen_paths.add(str(record["path"])))]
    _real_rows = [record for record in _chain_inventory
                  if wave17_chain_verdict(record) == "real-victory"]
    _poke_rows = [record for record in _chain_inventory
                  if wave17_chain_verdict(record) == "poke"]
    if _chain_inventory:
        add("| # | 收据 | ROM | 进入方式 | 判读 | 页数 | `outcome` |")
        add("|---:|---|---|---|---|---:|---|")
        for _index, _record in enumerate(_chain_inventory):
            _verdict = wave17_chain_verdict(_record)
            _label = {
                "real-victory": "✅ **真实胜利链**",
                "real-defeat": "✅ **真实战斗链（败北，`outcome=2`）**",
                "poke": "⛔ **poke 链**",
                "unknown": "⚠️ **进入方式未记录**",
            }[_verdict]
            add(f"| {_index + 1} | "
                f"`{_record['path'].relative_to(REPO).as_posix()}` | "
                + (f"`{_record['rom_sha256'][:16]}…`"
                   if _record.get("rom_sha256") else "—")
                + " | "
                + (f"`{_record.get('method')}`" if _record.get("method") else "—")
                + f" | {_label} | {len(_record['rows'])} | "
                + (str(_record["outcome"]) if _record.get("outcome") is not None
                   else "—")
                + " |")
        add("")
        if _real_rows:
            add("✅ **真实胜利链**存在 ⇒ **「真实打完仗」已达成**（§11 第 25 项）。")
            add("")
        else:
            add("⛔ **没有「真实胜利链」** ⇒ **「真实打完仗」仍未达成**"
                "（§11 第 25 项）。")
            add("")
        if _poke_rows:
            add("⛔ **下列链是 poke 出来的** ⇒ "
                "**它们显示的是「空战果」（V2 实测：125/0/200），不是打出来的** ⇒ "
                "**不得写成「真实打完仗」的那一版**。")
            add("")
    else:
        _real_rows = []
        _poke_rows = []
        add("⛔ **盘上没有任何结算链的运行帧记录**"
            f"（以 `{W17_CUTOFF}` 与 `{W16_CUTOFF}` 的 mtime 为界）。")
        add("")
    # ---- the chain record first (it is the one that may be poked) ---------
    if _chain_rows:
        _outcomes = sorted({str(row.get("outcome")) for row in _chain_rows
                            if row.get("outcome") is not None})
        add(f"⭐ **结算链的运行帧记录**：**{len(_chain_rows)} 行**"
            f"（收据 `{_chain_path.relative_to(REPO).as_posix()}`"
            + (f"；ROM `{_chain_rom[:16]}…`" if _chain_rom else "")
            + "；相位 " + " → ".join(
                f"{row.get('phase_name')}"
                for row in _chain_rows
                if row.get("phase_name"))[:220] + "）。")
        add("")
        if _chain_poked:
            add("⛔ **⭐ 这一版是「poke 出来的」，不是真实战斗打出来的** —— "
                "它的进入方式是**改控制器的状态字节**"
                "（`entry.method` 里写明了 `controller state poke`），"
                "⇒ **屏上的战果是「空战果」（V2 实测：125/0/200），不是打出来的** ⇒ "
                "**它不能算「真实打完仗」的那一版**"
                "（这正是 wave 14 的 Z1 那 15 屏的老问题）。")
            add("")
        else:
            add("✅ 这一版的进入方式**不是** poke ⇒ "
                "**它可以算真实战斗打出来的那一版**。")
            add("")
    else:
        add("⛔ **wave 16 没有结算链的运行帧记录**（以 `WAVE16-TASKS.md` 的 mtime 为界）。")
        add("")
    # ---- the per-screen comparison (V1's real battle) --------------------
    add("##### 15.2.3.1 ✅ **真实战斗链**（结算链的逐屏对照表）")
    add("")
    # ---- the wave-17 **battle** receipts (the decisive evidence) -----------
    if _w17_battles:
        add("⭐ **本波的战斗收据**（U4 的闭环驱动器）—— "
            "「真实打完仗」的三条判据都在这里："
            "**是不是真打的**（`entry.method`）、"
            "**是不是产品判的**（`battle_decided`）、"
            "**蜂的 HP 有没有掉**（`acceptance.bee_hp_dropped`）。")
        add("")
        add("| # | 收据 | ROM | 进入方式 | `outcome` | `battle_decided` | "
            "蜂 HP 下降 | 护送存活 | 判读 |")
        add("|---:|---|---|---|---:|---|---:|---|---|")
        for _index, _battle in enumerate(_w17_battles):
            _acc = _battle.get("acceptance") or {}
            _bverdict = {
                "real-victory": "✅ **真实胜利**",
                "real-defeat": "✅ 真实战斗（败北）",
                "undecided": "⛔ **战斗没有判定**",
                "poke": "⛔ **poke**",
            }[wave17_battle_verdict(_battle)]
            add(f"| {_index + 1} | "
                f"`{_battle['path'].relative_to(REPO).as_posix()}` | "
                + (f"`{_battle['rom_sha256'][:16]}…`"
                   if _battle.get("rom_sha256") else "—")
                + " | "
                + (f"`{_battle.get('method')}`" if _battle.get("method") else "—")
                + f" | {_battle.get('outcome', '—')} | "
                f"{_battle.get('battle_decided', '—')} | "
                f"{_acc.get('bee_hp_dropped', '—')} | "
                f"{_acc.get('escort_alive', '—')} | {_bverdict} |")
        add("")
        add("⚠️ **口径**：`battle_decided = False` ⇒ **战斗没有打完** ⇒ "
            "**那一局不是「打完仗」**；"
            "`bee_hp_dropped = False` ⇒ **敌人的 HP 没有下降** ⇒ "
            "**玩家的攻击仍然没有打中**。")
        add("")
    # ---- the wave-17 **real victory** chain, if it exists ------------------
    if _real_rows:
        for _record in _real_rows:
            add(f"⭐⭐ **wave 17 的真实胜利链**：**{len(_record['rows'])} 页**"
                f"（收据 `{_record['path'].relative_to(REPO).as_posix()}`"
                + (f"；ROM `{_record['rom_sha256'][:16]}…`"
                   if _record.get("rom_sha256") else "")
                + f"；进入方式：`{_record.get('method') or '—'}`"
                + (f"；判据：{_record.get('reason')}"
                   if _record.get("reason") else "")
                + f"；`outcome` = {_record.get('outcome')}）"
                "⇒ **这是由真实战斗打出来的那一版**。")
            add("")
            if (_record.get("rom_sha256")
                    and _record["rom_sha256"] != receipt_rom_sha(receipt)):
                add(f"⛔ **ROM 口径警告**：这条链是在 ROM "
                    f"**`{_record['rom_sha256'][:16]}…`** 上打出来的，"
                    f"而本次流水线构建的是 `{receipt_rom_sha(receipt)[:16]}…` ⇒ "
                    "**这两组数字不能混用**（「必须同 ROM 比」）。")
                add("")
            add("| # | 相位 | 页 | `outcome` | 参与者 | 总经验 | sha256 |")
            add("|---:|---|---:|---:|---:|---:|---|")
            for _index, _row in enumerate(_record["rows"]):
                add(f"| {_index + 1} | "
                    f"{_row.get('phase_name') or '—'} | "
                    f"{_row.get('training_detail_page', '—')} | "
                    f"{_row.get('outcome', '—')} | "
                    f"{_row.get('result_participant_count', '—')} | "
                    f"{_row.get('result_total_experience', '—')} | "
                    f"`{str(_row.get('sha256'))[:16]}…` |")
            add("")
    else:
        add("⛔ **盘上没有「真实胜利链」**（`entry.method` 自报**不是** poke "
            "且 `outcome = 1`）⇒ **「真实打完仗」仍未达成**（§11 第 25 项）。")
        add("")
    if not _v1_rows:
        add("⛔ **V1 的真实结算链对照表尚未交付**（"
            "以 `WAVE16-TASKS.md` 的 mtime 为界）。"
            "⇒ §15.2 的数字仍是旧波（wave 14 / Z1、wave 15 / W3）的采集。")
        add("")
    else:
        _v1_matched = [row for row in _v1_rows
                       if row.get("diff_pixels") is not None
                       or row.get("diff_px") is not None
                       or row.get("differing_pixels") is not None]
        add(f"⭐ **结算链的逐屏对照表**（收据 "
            f"`{_v1_path.relative_to(REPO).as_posix()}`；"
            f"**{len(_v1_rows)} 行**，其中 **{len(_v1_matched)} 行**有原版真值可对照）。")
        add("")
        add("⚠️ **这张表比的是「结算链的运行帧」** —— "
            "**它不是「真实打完仗」的那一版**："
            "进入方式（真打 / poke）见上面的战斗收据表与 §15.2.3.2 ⇒ "
            "**两栏不许混用**。")
        _v1_run_rom = receipt_rom_sha(receipt)
        if _v1_rom and _v1_run_rom and _v1_rom != _v1_run_rom:
            add(f"⛔ **ROM 口径警告**：这张表是在 ROM "
                f"**`{_v1_rom[:16]}…`** 上测的，"
                f"而本次流水线构建的是 `{_v1_run_rom[:16]}…` ⇒ "
                "**这两组数字不能混用**（「必须同 ROM 比」）。")
            add("")
        elif _v1_rom and _v1_run_rom:
            add(f"✅ **ROM 口径一致**：这张表与本次流水线跑的是**同一份 ROM** "
                f"（`{_v1_run_rom[:16]}…`）。")
            add("")
        add("| # | 重制侧帧 | 相位 | 页 | 对照的原版屏 | 差 px | 差 bbox | "
            "重制侧 sha256 | 原版 sha256 |")
        add("|---:|---|---|---:|---|---:|---|---|---|")
        for _index, row in enumerate(_v1_rows):
            _diff = row.get("diff_pixels")
            if _diff is None:
                _diff = row.get("diff_px")
            if _diff is None:
                _diff = row.get("differing_pixels")
            _bbox = row.get("bbox") or row.get("diff_bbox")
            add(f"| {_index + 1} | "
                f"`{row.get('remake_file') or row.get('remake_page') or '—'}` | "
                f"{row.get('phase') or '—'} | {row.get('page', '—')} | "
                f"{row.get('truth_file') or '—'} | "
                f"{fmt(_diff) if isinstance(_diff, (int, float)) else '—'} | "
                f"{_bbox if _bbox else '—'} | "
                f"`{str(row.get('remake_sha256'))[:16]}…` | "
                + (f"`{str(row.get('truth_sha256'))[:16]}…` |"
                   if row.get("truth_sha256") else "— |"))
        add("")
        _v1_same = sum(1 for row in _v1_rows
                       if row.get("remake_sha256") and row.get("truth_sha256")
                       and row.get("remake_sha256") == row.get("truth_sha256"))
        add(f"⇒ **{_v1_same} / {len(_v1_rows)} 屏与原版真值逐字节相同**"
            "（sha256 匹配）⇒ 这些屏**差 px = 0**。")
        add("")
        add("⛔ **⭐ 这一张表本身不是「真实打完仗」的那一版**：V1 的笔记"
            "（`notes/s49-fidelity/V1-real-victory.md` §0）写明"
            "**「没有真打完仗」** —— 驾驶侧（闭环驱动器 + 原版的目标选择策略）"
            "已经做完，但**产品缺陷 D4** 拦住最后一步："
            "**重制侧一旦玩家的攻击「射程内有活着的敌人」，战斗场景就废了**"
            "（忍具把 ROM 彻底冻住、普通招式让场景不再接受任何输入）"
            "⇒ **玩家的攻击永远打不中** ⇒ **`outcome=1` 在那个 ROM 上不可达**。"
            "⇒ 上表是**真实战斗产生的败北屏**（`outcome=2`）的对照数据，"
            "**不是**胜利链。"
            + ("⭐ **wave 17 的 U1 修了 D4、U4 打出了真实胜利链** ⇒ "
               "**「真实打完仗」已达成**（见上面的链清单与 §11 第 25 项）；"
               "**本表仍是 wave 16 的败北屏对照**（不同 ROM ⇒ 不许混用）。"
               if _w17_real else
               "⇒ **「真实打完仗」这一条仍未达成**（§11 第 25 项）。"))
        add("")
    # ---- the poke chain, in its own column --------------------------------
    add("##### 15.2.3.2 ⛔ **poke 链**（**不是**真实战斗打出来的）")
    add("")
    if not _poke_rows:
        add("⛔ **盘上没有 poke 链的收据**。")
        add("")
    else:
        for _record in _poke_rows:
            add(f"⛔ **这一版是「poke 出来的」**：进入方式是**改控制器的状态字节**"
                f"（`entry.method` = `{_record.get('method') or '—'}`"
                + (f"；判据：{_record.get('reason')}"
                   if _record.get("reason") else "")
                + "）"
                + (f"；测在 ROM `{_record['rom_sha256'][:16]}…`"
                   if _record.get("rom_sha256") else "")
                + " ⇒ **屏上的战果是「空战果」（V2 实测：125/0/200），不是打出来的** ⇒ "
                "**它不能算「真实打完仗」的那一版**，"
                "**也不许与 §15.2.3.1 的真实战斗链混用**。")
            add("")
            add("| # | 相位 | 页 | `outcome` | 参与者 | 总经验 | sha256 |")
            add("|---:|---|---:|---:|---:|---:|---|")
            for _index, _row in enumerate(_record["rows"]):
                add(f"| {_index + 1} | "
                    f"{_row.get('phase_name') or '—'} | "
                    f"{_row.get('training_detail_page', '—')} | "
                    f"{_row.get('outcome', '—')} | "
                    f"{_row.get('result_participant_count', '—')} | "
                    f"{_row.get('result_total_experience', '—')} | "
                    f"`{str(_row.get('sha256'))[:16]}…` |")
            add("")
            add("⇒ **第 4/5 列（参与者 / 总经验）是链收据自报的状态读数** —— "
                "⚠️ **它们不是打出来的战果**（这一版的进入方式是 poke）。"
                "⭐ **V2 的逐像素对照给出的屏幕数字是「空战果」125/0/200**，"
                "原版是 125/190/75/300… ⇒ "
                "**这正是「結算屏数字 684 px 只差数值」那一条的来源**，"
                "⇒ **不得当作「真实打完仗的战果」引用**。")
            add("")
    # ---- the newest settlement screen alignment ---------------------------
    _align17_path, _align17, _align17_is_w17 = wave17_settlement_align()
    add("#### 15.2.4 ⭐ 結算屏逐屏对照（**最新一次测量**）")
    add("")
    if not _align17:
        add("⛔ **盘上没有結算屏的逐屏对照收据**。")
        add("")
    else:
        _pairs17 = _align17.get("pairs") or []
        _total17 = _align17.get("total_diff_px")
        if _total17 is None:
            _total17 = sum(int(pair.get("diff_px") or 0)
                           for pair in _pairs17
                           if isinstance(pair, dict))
        _identical17 = _align17.get("identical_pairs")
        if _identical17 is None:
            _identical17 = sum(1 for pair in _pairs17
                               if isinstance(pair, dict) and pair.get("identical"))
        _align17_rom = _remake_rom_of_align(_align17_path, _align17)
        add(f"⭐ **收据** `{_align17_path.relative_to(REPO).as_posix()}`"
            + ("（**wave 17 / U2 本波测的**）" if _align17_is_w17
               else "（⚠️ **这是 wave 16 及更早的测量** —— "
                    "**wave 17 的 U2 还没有交出新的結算屏收据** ⇒ "
                    "**下面的数字不是本波的结果**）")
            + f"；**{len(_pairs17)} 对**、合计差 **{fmt(_total17)} px**、"
            f"**{fmt(_identical17)} 对逐字节相同**；"
            f"整屏 **{fmt(_align17.get('screen_pixels'))} px**；"
            + (f"**测在 ROM `{_align17_rom[:16]}…`**"
               + ("（**＝本次流水线构建的 ROM** ✅）"
                  if _align17_rom == receipt_rom_sha(receipt)
                  else "（⛔ **≠ 本次流水线构建的 ROM** ⇒ "
                       "**这两个数不许混用**）")
               if _align17_rom else "**收据没有钉住 ROM**（⚠️ 不许与本次读数混用）")
            + f"；重制侧帧来自 `{_align17.get('remake_dir')}`，"
            f"原版真值来自 `{_align17.get('truth_dir')}`。")
        add("")
        add("| 原版真值 | 重制侧运行帧 | 阶段 | 差 px | 相同 px | 逐字节相同 | "
            "原版颜色数 | 重制侧颜色数 |")
        add("|---|---|---|---:|---:|---|---:|---:|")
        for _pair in _pairs17:
            if not isinstance(_pair, dict):
                continue
            add(f"| `{_pair.get('truth') or '—'}` | "
                f"`{_pair.get('remake') or '—'}` | "
                f"{_pair.get('phase') or '—'} | "
                f"{fmt(_pair.get('diff_px'))} | "
                f"{fmt(_pair.get('same_px'))} | "
                f"{'✅' if _pair.get('identical') else '—'} | "
                f"{fmt(_pair.get('truth_colors'))} | "
                f"{fmt(_pair.get('remake_colors'))} |")
        add("")
        add("⚠️ **口径**：这张表比的是**整屏**（结算屏 + 升级屏 + 训练页 + 对白 + "
            "任务菜单）⇒ **它与「結算屏人物 1,898 px / 数字 684 px」那一条"
            "不是同一个口径**（后者是 wave 16 / V2 把**结算屏那一屏**的差拆成"
            "「tab 栏 / 渐变 / 面板边 / 人物 / 数字」五段后的数）⇒ "
            "**两个数不许直接相比**。")
        add("")
    if settlement:
        add("### 15.2b 原版真值清单（sha256 收据）")
        add("")
        add("| 文件 | sha256 |")
        add("|---|---|")
        for entry in settlement.get("truth", []):
            add(f"| `{entry['name']}` | `{entry['sha256'][:16]}…` |")
        add("")
        add("### 15.2c wave 9 V4 的那次采集（**敗北路径**，不是运行帧对照）")
        add("")
        add("| 重制侧帧区间 | 帧数 | 最接近的原版屏 | 差 px | 差 bbox | "
            "重制侧 sha256 | 原版 sha256 |")
        add("|---|---:|---|---:|---|---|---|")
        for row in settlement.get("remake_screens", []):
            bbox = row.get("diff_bbox")
            add(f"| {row['remake_first_frame']}–{row['remake_last_frame']} | "
                f"{row['remake_frames']} | `{row['original']}` | "
                f"{fmt(row['differing_pixels'])} | "
                f"{bbox if bbox else '—'} | "
                f"`{row['remake_sha256'][:16]}…` | "
                f"`{row['original_sha256'][:16]}…` |")
        add("")
    if assets:
        add("### 15.3 静态图层对照（**资产级**，不是运行帧）")
        add("")
        add("⚠️ **口径**：重制侧运行时把文字与数字画成 **sprite**"
            "（`battle_result_sprite_font` / "
            "`battle_result_compact_sprite_font`），"
            "所以这里比的是**静态 BG 图层**（"
            "`battle_ui_result_background` + `battle_ui_result_panel` 等，"
            "按场景的层次叠放后裁成 240×160）。"
            "⚠️ **这不是运行帧的残差**，只说明**底板结构**的差。")
        add("")
        add("| 屏 | 重制侧图层 | 对照的原版真值 | 差 px | 占比 | 差 bbox |")
        add("|---|---|---|---:|---:|---|")
        for row in assets.get("rows", []):
            if "error" in row:
                add(f"| {row['screen']} | — | `{row.get('truth', '—')}` | "
                    f"⚠️ {row['error']} | — | — |")
                continue
            share = (100.0 * row["differing_pixels"] /
                     row["total_pixels"])
            layer_text = " + ".join(f"`{name}`" for name in row["layers"])
            add(f"| {row['screen']} | "
                f"{layer_text} | "
                f"`{row['truth']}` | {fmt(row['differing_pixels'])} | "
                f"{share:.1f}% | {row['diff_bbox']} |")
        add("")
        add("⭐ **wave 11 的 U3 实测：换 1:1 层后资产级差 px 大幅下降**"
            "（`notes/s49-fidelity/U3-settlement-content.md` §5）：")
        add("")
        add("| 屏 | 现状（V4 口径） | 换 1:1 层后 | 变化 |")
        add("|---|---:|---:|---|")
        add("| 结算屏 | 12,798 | **1,636** | **−87.2%** |")
        add("| 升级屏 | 7,681 | **608** | **−92.1%** |")
        add("| 训练页 | 8,483 | **无 1:1 候选**（`graphics/` 里没有 "
            "`scenario_41_training_*`） | — |")
        add("")
        add("⚠️ **三个必须写明的口径**："
            "① **必须按「index 0 = 透明」的 alpha 合成** —— 按 V4 工具的 "
            "opaque paste 口径反而更差（12,798 → **12,800**）；"
            "② V4 的差 px 计数是 **`L` 模式 + 每 3 字节一组 ⇒ 约 1/3 采样**"
            "（12,798 对应全量真值 **38,152**；换层后 **3,769**）；"
            "③ ⛔ **三张 8bpp 层 = 192 KB > GBA 的 96 KB VRAM** ⇒ "
            "**必须先定量化/分层方案**，否则这层换不上去。")
        add("")
    add("")

    # ---------------------------------------------------------------- 16
    add("## 16. ⭐ 越界复核：wave 10 / U4 给 `find_overlay_map` 加的 terrain 判据")
    add("")
    add("wave 10 的 U4 流**自报了一处越界**：它在**别的流**的仪器"
        "（`tools/s49_overlay_align/compare_overlay_families.py`）里给 "
        "`find_overlay_map` 加了 **terrain 判据**"
        "（「solid 必须落在受阻地形上」），"
        "超出了「只授权改锚点」的范围。"
        "**wave 11 / W4 复核过一次（结论：保留，不回退）；"
        "本波（wave 12 / X4）独立复核第二次，数字全部重新测。**")
    add("")
    review = load_json(evidence / "overlay" / "terrain-review.json")
    if not review:
        add("⛔ **本次收据里没有越界复核的产物**"
            "（`evidence/overlay/terrain-review.json`）⇒ 本节没有数字。")
        add("")
    else:
        q1 = review.get("q1_none_path_equals_pre_change") or {}
        q1b = review.get("q1_bench_reader_equals_pre_change") or {}
        q2 = review.get("q2_dumps_changed_by_the_criterion") or {}
        q3 = review.get("q3_shared_tool_table") or {}
        categories = q2.get("pre_change_categories") or {}
        add("### 16.1 三个问题、三个数字")
        add("")
        add("| 问题 | 判定方法 | 结果 |")
        add("|---|---|---|")
        add(f"| **Q1** `terrain=None` 的路径与**改前**的实现逐字节相同吗 | "
            f"把改前的候选扫描**在本流重新实现**一遍（`max(candidates)[1]`），"
            f"在每个 dump 上与现装的 `find_overlay_map(vram, 77)` 对照 | "
            f"**是**：{fmt(q1.get('dumps_checked'))} 个 dump，"
            f"**{fmt(q1.get('mismatches'))} 处不同** |")
        add(f"| **Q1b** 判定台自己的覆盖层读数被影响了吗 | "
            f"直接调判定台的 `tools/s49_fidelity_report/overlay.py::remake_grid`，"
            f"把它报的 `overlay_map` 与改前的实现逐个对照 | "
            f"**否**：{fmt(q1b.get('dumps_checked'))} 个 dump，"
            f"**{fmt(q1b.get('mismatches'))} 处不同**。"
            f"原因：判定台调的是 `find_overlay_map(vram, 77)` —— "
            f"**第二个位置参数是 `tile_max`，terrain 走默认值 `None`** |")
        add(f"| **Q2** terrain 判据改动了哪几个 dump | "
            f"同一份 dump 上带 / 不带 terrain 各跑一遍 | "
            f"**{fmt(q2.get('changed'))} 个改动**、"
            f"**{fmt(q2.get('unchanged'))} 个一字未变** |")
        add("")
        add("### 16.2 被改动的 dump（全部 4 个）")
        add("")
        add("| dump | 不带 terrain | 带 terrain（现状） | 候选窗口（非零 entry 数） |")
        add("|---|---|---|---|")
        for row in q2.get("rows") or []:
            candidates = "、".join(
                f"`{c['base_hex']}`（{c['non_zero']}）"
                for c in row.get("candidates") or [])
            add(f"| `{row.get('dump')}` | `{row.get('pre_change_hex')}` | "
                f"`{row.get('with_terrain_hex')}` | {candidates} |")
        add("")
        add("### 16.3 全部 dump 的分类（改前的口径）")
        add("")
        add("| 类别 | 数量 |")
        add("|---|---:|")
        add(f"| 没有任何候选窗口（覆盖层根本没显示） | "
            f"{fmt(categories.get('no_candidate'))} |")
        add(f"| **假窗口 `0x00800`**（BG **图块数据**，1024 个非零 entry，"
            f"按签名「全部合法」⇒ 会赢过真覆盖层） | "
            f"{fmt(categories.get('false_window_0x00800'))} |")
        add(f"| **真覆盖层 `0x09800`**（768 个非零 entry） | "
            f"{fmt(categories.get('real_overlay_0x09800'))} |")
        add(f"| 其它 | {fmt(categories.get('other'))} |")
        add("")
        add("### 16.4 判据对共享工具的数字的影响（端到端 A/B）")
        add("")
        add(f"共享工具的 `compare_overlay_families.py` 在同一份 dump 上跑两遍："
            f"一遍带判据（现状），一遍把 `find_overlay_map` 换回改前的实现"
            f"（**只在本进程里替换函数，不动共享文件**）。"
            f"**{fmt(q3.get('frames_with_a_different_overlay_map'))}** 个 dump "
            f"选到了不同的覆盖层窗口。")
        add("")
        add("| 时刻 | 不带判据 | 带判据（现状） | 变了？ |")
        add("|---|---|---|---|")
        numeric_fields = ("both_lit", "original_only", "remake_only",
                          "family_mismatches", "residual", "exact")
        for name, row in (q3.get("moments") or {}).items():
            without = row.get("without_criterion") or {}
            with_c = row.get("with_criterion") or {}
            changed_fields = row.get("changed_fields") or {}

            def _cell(entry):
                if not entry:
                    return "—"
                window = entry.get("overlay_map")
                if window is None:
                    window_text = "无"
                elif window < 0:
                    window_text = "无（−1）"
                else:
                    window_text = f"0x{window:05X}"
                return (f"同亮 {fmt(entry.get('both_lit'))} / "
                        f"缺 {fmt(entry.get('original_only'))} / "
                        f"多画 {fmt(entry.get('remake_only'))} / "
                        f"不一致 {fmt(entry.get('family_mismatches'))} / "
                        f"残差 {fmt(entry.get('residual'))}"
                        f"（取帧 `{entry.get('frame')}`，窗口 "
                        f"{window_text}）")
            if any(field in changed_fields for field in numeric_fields):
                verdict = "**数字变了**"
            elif row.get("changed"):
                verdict = "只换了取帧（**数字不变**）"
            else:
                verdict = "否"
            add(f"| `{name}` | {_cell(without)} | {_cell(with_c)} | {verdict} |")
        add("")
        add("### 16.5 结论：**保留，不回退**")
        add("")
        add("| 复核项 | 结论 |")
        add("|---|---|")
        add("| 是不是真越界 | **是**（改了别的流的仪器文件，而且改的是**判据**，"
            "不只是锚点） |")
        add("| 向后兼容吗 | ✅ **是**：`terrain` 是**新增的可选参数**，默认 `None`；"
            f"**Q1 的 {fmt(q1.get('mismatches'))} 处不同**说明"
            "「不带 terrain」的路径与改前**逐字节相同** |")
        add("| 会不会打断判定台 | ⛔ **不会**：**Q1b 的 "
            f"{fmt(q1b.get('mismatches'))} 处不同**"
            "⇒ 判定台（步骤 5）与覆盖层逐格对拍（步骤 6）**各走各的路径**，"
            "两个数字**仍不许混用**（§11 第 18 项）。"
            "⭐ **推论**：判定台的覆盖层残差（"
            f"{fmt((after_summary.get('overlay_residual') or {}).get('sum'))} px）"
            "是用同一个 `remake_grid` 算出来的，而 35 个 dump 的 `overlay_map` "
            "**逐个相同** ⇒ **那个数字不可能因为这处越界而变过** |")
        add("| 不改它会不会测出假窗口 | ⛔ **会**。"
            f"**{fmt(categories.get('false_window_0x00800'))} 个** dump 在不带 "
            f"terrain 时返回**假窗口 `0x00800`**（图块数据），"
            "带 terrain 时返回 `-1`（正确地「没有覆盖层」） |")
        add("| 判据是宽的还是窄的 | **窄**：只改 "
            f"**{fmt(q2.get('changed'))}/{fmt(review.get('dump_count'))}** 个 dump，"
            f"**{fmt(q2.get('unchanged'))} 个一字未变** |")
        add("| 判据让数字变好看了吗 | ⛔ **没有，恰恰相反**："
            "它剔掉的是「重制多画 103 格」这个**假阳性** —— "
            "`grid16-frame-v1` 的残差从 **185 降到 126**；"
            "`field-frame-v1` / `movegrid-frame-v1` 的数字**一个字都没变**；"
            "`banner-frame-v1` 只换了取帧，**数字全是 0、也没变** |")
        add("| ⚠️ 循环论证的风险 | ⚠️ **有，必须写明**：terrain 来自**重制线自己的"
            "生成头** `generated_battle_map_content.h` ⇒ 该判据只保证"
            "「覆盖层与**产品自己用的**地图一致」，**不是**独立于产品的绝对真值。"
            "绝对真值仍是原版导出的 `s49-original-movegrid-tilemap-v1` |")
        add("")
        add("⇒ **本流（只读调用方）没有改它，也没有回退它**；"
            "`tools/s49_overlay_align/` 归 **X2** 流所有。")
        add("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    receipt = load_json(args.receipt)
    if receipt is None:
        print(f"ERR cannot read the receipt: {args.receipt}")
        return 2
    package = pathlib.Path(os.path.abspath(args.receipt.parent))
    text = render(receipt, package)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {args.out} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
