# Butano Scenario 43 Campaign Completion Implementation Plan

> **执行约束：** 用户已要求内联直接执行；遵循仓库 TDD、重资源守卫和
> 不自动提交规则。

**目标：** 用同一套共享生产运行时完成 scenario 43 的多敌战斗、影分身、
敌方多单位回合、原作奖励结算、战役保存与 scenario 44 冷启动，证明当前
实现是可扩展战斗架构，而不是截图或关卡选项拼接。

**架构：** 继续复用 `battle_campaign_route`、
`battle_campaign_scene_progression`、`battle_scene_controller`、生成的 ROM
形成/胜负条件/奖励内容及 SRAM 事务。测试和 mGBA 驱动只允许通过公开语义
操作或 GBA 按键推进，不允许写入战斗或战役内存；生产代码不得加入
scenario 43 专用胜利、伤害或路由分支。

## 原作验收规格

- battle 43 variant 0 使用 9×22 地图。
- 初始单位为 Naruto `(4,17)`，以及三名 50 HP 敌人 `(2,11)`、
  `(4,10)`、`(6,11)`；槽位 5..12 是预留槽。
- 行动 7 消耗 3 chakra，在合法空格创建同阵营 Naruto 分身；分身进入后续
  玩家回合调度。
- 敌方三个有效单位必须分别通过共享 AI 回合完成行动。
- 胜利只能由生成条件 `no_valid_unit_for_side(enemy)` 产生。
- 三名敌人各携带 10 battle EXP；任务奖励为 125 EXP，5 回合内奖励 25
  EXP。为复现原作 155 EXP，验收路线必须超过 5 回合。
- 从 `LV2/EXP110/TP1` 开始，胜利结算后必须得到
  `LV3/EXP0/TP2`，并推进、保存到 scenario 44。
- scenario 44 冷启动必须使用 `team_seven` 队伍策略进入共享控制器。

## 任务

### 1. 主机端 scenario 43→44 纵向切片

- [x] 新建 `butano-sequel/game/tests/test_battle_campaign_scenario_43.cpp`。
- [x] 只调用控制器公开操作：`confirm`、`move_cursor`、`cycle_unit`、
  `tick`、`cancel`。
- [x] 纠正重复 prepare 的测试契约错误；生产 controller 无需关卡特判修复。
- [x] 覆盖分身、多敌 AI、超过 5 回合、三敌击倒、155 EXP、升级训练点、
  campaign commit 和 route advance。

### 2. mGBA 实机战役路线

- [x] 先扩展 `tests/test_butano_battle_campaign_route_runtime_script.py` 的失败契约。
- [x] 扩展 `tools/butano/mgba_battle_campaign_route.lua`，通过遥测读状态和
  GBA 按键完成 scenario 43；不得使用 `emu:write`。
- [x] 第一进程从已验证 scenario 43 SAV 完成战斗并保存 scenario 44。
- [x] 第二进程冷启动该 SAV，确认 scenario 44、battle 44 和 Team 7 可见。

### 3. 回归、ARM 与持久证据

- [x] 运行隔离主机测试、全量主机测试、相关 Python 集成测试与格式检查。
- [x] 经 `tools/run_guarded.py` 完成 ARM build 和两次 mGBA 运行。
- [x] 记录 ROM/ELF/SAV hash、关键遥测、截图信号、运行资源和失败边界。
- [x] 同步战斗架构设计、运行时证据和 `docs/sequel-roadmap.md`。
