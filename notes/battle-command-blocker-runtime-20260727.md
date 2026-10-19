# Butano 命令阻断与金缚术运行闭环（2026-07-27）

## 失败基线

用户指出当前实现仍把演出拼接当作战斗。针对 action 80 的审计确认该问题确实存在：

- 命中后只写 `reaction_state=0x30`，没有 `0x3F` 活动状态；
- 玩家选人、单位轮换和 AI actor 调度都不消费 blocker；
- battle 20 在玩家整侧不可行动时进入空选择/AI 错误，而不是完成空阵营边界。

TDD RED：

- `test_battle_effect_handlers` 失败于 `applied_status_count == 0`；
- `test_battle_session` 失败于 blocker 单位仍可 `select_unit`；
- `test_battle_turn_flow` 首先因缺少 `advance_empty_side` 无法编译；
- 全场景百回合压力测试失败于 battle 20 variant 0 的
  `battle_scene_control_error::ai_flow_failed`。

## 原 ROM 证据

`tools/analyze_battle_command_blockers.py` 对 `rom/base.gba`
SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
做 fail-closed 验证，输出
`notes/battle-command-blocker-bindings-20260727.json`：

- action 80 `0x08545958`：effect `0x3F`、成功率 85、raw duration 2；
- `0x08077560 → 0x0806A8C0`：reaction `0x30`；
- `0x0807758A → 0x0806C204`：同一 handler 写入持久状态；
- `0x080736E4 → 0x08075350`：翻转阵营后执行单位激活；
- 激活函数依序查询 `3F/3E/3D/0F/11/15`，任一命中就跳过该单位。

结论：状态库是行动资格事实源；reaction byte 只是表现状态。

## 实现

- 新增共享 `battle_commands_blocked`，六个 code 只定义一次；
- `battle_action_resolver` 的 effect `0x3F` 命中后写入 duration 4 的活动状态，再更新 reaction；
- `battle_session` 的唯一资格门同时服务玩家选择、轮换和 AI；
- 新增事务式 `battle_turn_flow::advance_empty_side`：没有可行动单位时仍执行
  status/object tick、condition、side-start passive 和边界脚本，然后切换阵营；
- 没有存活参与者的不存在阵营不被伪造成一轮空行动，保持单单位宿主测试的旧边界。

## 验证

- 92/92 个 `butano-sequel/game/tests/test_*.cpp` 以
  `clang++ -std=c++20 -Wall -Wextra -Werror` 编译并运行通过；guard：
  `build/command-blockers-all-host-summary-final.json`。
- 相关 Python 16/16 通过，包括 ROM analyzer、单领域门禁、phase contract 和 mGBA
  脚本契约。
- devkitARM 最终构建 guard：
  `build/command-blockers-arm-build-summary-20260727-final.json`。
  - ROM SHA-256：
    `bf3b05fbc224a6c2419ff02c89f5f638460332189adaf4d1b034b4df614b5daf`
  - ELF SHA-256：
    `d0cda81cc8d78efff616b836000d1903c2299fc7380d60706578634254952b44`
- 静音 mGBA 最终路线：
  `build/butano-command-blockers-runtime-20260727-final/`。
  - frame 2804；
  - battle 9、round 2、phase 1、9 个活动单位；
  - `last_control_error=0`、`last_player_error=0`；
  - execution trap 与 memory-write trap 均为空；
  - final state SHA-256：
    `dabb905acd1310eccd0bbcbb048b0099bf629a434ad4f170836b677adaff1177`。

全场景宿主测试自然触发并闭合 battle 20 的整侧阻断；mGBA 路线用于最终 ARM
控制器/多单位回归，没有伪造大蛇丸或强制 resolver 输入，因此不把它描述成金缚术专属
可见演出验收。

## 未完成边界

- 金缚术专属图标、逐帧表现和 sound cue 尚未绑定；
- 非静音音频未验证，本轮不能宣称音频撕裂已修复；
- 其余动作的专属表现和完整章节导航仍属于战斗 Goal 后续里程碑。

