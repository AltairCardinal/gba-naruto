# 事故记录 · wave 5 四路子代理**同时**丢失（2026-10-24 05:41）

> 记录人：主代理（mvs_4e730a9ded524558a303c115875a9707）
> 目的：把「运行时中断导致子代理批量丢失」这件事变成**可复用的知识**，而不是只在对话里。

---

## 0. 现象

wave 5 的 **4 个子代理在同一个时间戳（`endedAtMs = 1792791721152` ≈ 05:41）同时变成 `lost`**：

| 流 | task_id | 状态 | `task_output` |
|---|---|---|---|
| X1 像素差 | `bg_dd5a8ba9-…` | **lost** | `(no output yet)` |
| X2 配对归零 | `bg_5296de10-…` | **lost** | `(no output yet)` |
| X3 边界产品差 | `bg_64afc9ac-…` | **lost** | `(no output yet)` |
| X4 出包 | `bg_399ec5e3-…` | **lost** | `(no output yet)` |

⇒ 四路的**输出流一条都没写出来**，但**文件系统上的产物是真的**。

---

## 1. 关键事实：任务**已经干了 41 分钟的活**，不是「什么都没做」

从文件系统 mtime 反推（wave 5 于 05:00 开火，05:41 丢失）：

| 流 | 盘上留下的东西 |
|---|---|
| **X3** | 改了 `battle_session.h`（`cycle_roster_unit` 去掉 `side == _current_side` 过滤 ⇒ B5 跨阵营轮转）、`battle_campaign_sram.h/.cpp`（新增 `battle_campaign_save_trigger` 枚举 + `suppressed` 结果）、`src/main.cpp`（战斗结果改成 suppress ⇒ B7）；新增 3 个测试（`test_battle_roster_cross_side.cpp`、`test_battle_campaign_sram_trigger.cpp`，改了 `test_battle_roster_scheduler.cpp`）；`tools/s49_x3_boundary/check_b5_rotation.py`；**ROM 在 04:57 重建过一次** |
| **X2** | 建了 `tools/s49_pairing/` **8 个文件**：`__init__.py`、`walkspec.py`、`pair.py`、`anchors.py`、`record.py`、`savestate.py`、`bench_view.py`、`lua/record_walk.lua` |
| **X4** | `tools/s49_package/__init__.py`、`tools/s49_package/run_unit_tests.sh` |
| **X1** | ❌ **一行产品代码都没改**（还在分析/测量阶段） |

⇒ **「lost」≠「没干活」**。丢失只影响**回传**，不影响**磁盘上的产物**。

---

## 2. 处置：不要重开空白任务，要「接管」

重开的四份任务书都加了同一段接管说明：

> 上一任在 05:41 被运行时中断（不是你的错）。产物在盘上，**但全部未经验证**。
> 第一件事是**跑一遍看它们到底能不能用**，然后修好或重写 ——
> **不要假设它们是对的**，也不要从零重做已经做对的部分。

**重开后 4 路全部正常启动并产出。**

⚠️ 有一处**必须专门排查的风险**（X3 留下的）：
`src/main.cpp` 把断言改成了 `BN_ASSERT(saved.success() && saved.suppressed, …)`
⇒ 如果任何一条路径没能真的被 suppress，**游戏会断言崩溃**。
⇒ 接管任务书里把「**ROM 实测跑通战斗流程不崩**」列成了显式验收项。

---

## 3. 可复用的教训

1. **`lost` 不等于「没做」** ⇒ 丢失后第一件事是**查文件系统 mtime**，而不是重开空白任务。
2. **「产出在盘上」≠「产出是对的」** ⇒ 接管任务必须**显式要求重新验证**（构建、门禁、复跑），
   否则会把上一任的错误当成事实继承下去（本次 X3 的断言改动就是这种风险）。
3. **不要用 `git stash` 来做基线对照**（wave 5 有 4 个子代理在并行改同一棵树）。
   用 `git archive HEAD` 抽只读快照（见 `Q-unit-test-baseline.md`）。
4. **子代理的产物必须自己复跑一遍才敢写进报告**。

---

## 4. 本轮新增的实测经验（与丢失无关，但同批）

* **mGBA 探针**：只有 `frames` / `run` / `framedump` / `keyseq` **会前进帧**；
  `rawshot` / `dump` / `shot` **不会**（W3 实测，证伪了 M 流的 M15）。
* **杀 Python 客户端不杀探针子进程** ⇒ 每次跑完/取消后要查一遍
  `Win32_Process` 里的 `mgba-probe.exe`（W3 曾因此白烧约 6000 s CPU）。
* **重制线 20 个单测在 HEAD 就是红的**（预存债）⇒ 出包门禁用**棘轮式**（失败集合逐名相同），
  不用「全绿」。详见 `Q-unit-test-baseline.md`。
* **并发构建会互相覆盖**（同一个 `butano-sequel.gba` 输出）⇒ 同一时刻只允许一路做构建。
