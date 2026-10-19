# 持久被动属性重算运行记录（2026-07-27）

## 纠错结论

旧覆盖分析只搜索通用查询器 `0x0806DDA4` 的 BL 调用，因而把 targets `1–11` 的 18 条
被动定义误报成“ROM 无直接消费者”。实际 `0x0806D964` 在完成角色等级成长后，直接
遍历同一角色的 24 个副技能槽并修改战斗模板。旧 Butano 虽保存和训练这些被动，却只把
它们装入 `battle_passive_state`，没有形成角色战斗属性；这是一条真实角色架构断链。

fail-closed 分析器
`tools/analyze_battle_persistent_passive_stats.py` 现锁定：

- 基准 ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`；
- 完整函数 `0x0806D964..0x0806DDA3`：
  `9cbcf9e7a568f31c837e2aa7acdb3ed265ccde914044746dd99eaa498a9c2a2c`；
- 百分比/减免 pass `0x0806DAE6..0x0806DC19`；
- 固定加值 pass `0x0806DC1A..0x0806DD95`；
- 定义表 `0x085459C8` 与 flat jump table `0x0806DC7C`。

机读完整字段、指令门、跳表和公式见
`notes/battle-persistent-passive-stat-bindings-20260727.json`。

## 原作规则

每槽 ID 位于 `unit+0x50+4*i`、等级位于 `unit+0x51+4*i`；ID 0、等级 0/`0xFF`
不生效。数值统一为：

```text
base_a + per_level_a × (stored_level - 1)
```

顺序不是按单个槽“读到就全部应用”，而是先完整执行 targets `2/6/8/11` 的 HP/防御/
敏捷百分比提升和结印成本降低，再重新遍历 24 槽，执行 targets `1/3/4/5/7/9/10`
的固定加值。target `2/6/8` 在第二个 jump table 中显式 no-op。最终钳制为：

| target | 字段 | 上下限 |
|---:|---|---:|
| 1 / 2 | 最大 HP 固定 / 百分比 | 999 |
| 3 | 查克拉容量 | 9 |
| 4 | 攻击 | 99 |
| 5 / 6 | 防御固定 / 百分比 | 99 |
| 7 / 8 | 敏捷固定 / 百分比 | 99 |
| 9 | 移动 | 9 |
| 10 | 忍具容量 | 99 |
| 11 | 结印成本百分比降低 | 最小 1 |

target 10 的 99 是该算术分支的指令级钳制，不是装备结构尺寸。后续复核既有装备链确认：
`0x08090004` 直接以角色 `+0x06` 的该统计值作为循环上界，在 `+0xB1+i` 寻找空槽并只把
`+0xB0` 已装备数量加一；没有读取忍具模板中的逐件重量。角色记录的物理区只有九个 ID。
因此业务语义是“可装备数量”，不是 99 格或逐件容量成本；生产内容必须把可达值限制在
物理九格，Butano 的九元素数组继续作为独立 fail-closed 边界。

## Butano 数据流

`battle_progression.h` 现以一个纯函数统一计算“等级属性 + 持久被动”：

```text
CharacterProgressionRecord.secondary_action_levels
  → character_passive_state
  → apply_persistent_passive_stats
       ├─ BattleScenarioLoader
       │    → hp/max_hp/chakra/attack/defense/agility/move
       │    → base_* 与 hand_seals
       └─ BattleCampaignEquipmentService
            → ninja_tool_capacity validation
```

scenario loader 先应用玩家 progression 或 formation 自带 24 槽状态，再计算属性。敌人、
脚本单位和玩家因此共用一条路径。`base_*` 保存被动修正后的基线，临时增减益到期后不会
错误回到纯等级值。campaign 整备复用同一函数；它仍受九格物理装备数组限制，不会越界。

## TDD 证据

RED：

- 新领域测试因不存在 `persistent_passive_stat_result`/
  `apply_persistent_passive_stats` 而编译失败；
- LV9 鸣人把 passive 1 训练到 LV1 后，经真实 battle 41 loader 的 HP 仍等于纯等级值；
- 忍具容量被动训练后，campaign 仍按旧容量拒绝额外分配；
- ROM 已证实 target 10 上限 99 后，测试先观察到 Butano 错误钳制为 9；
- 覆盖矩阵仍报告 `17 direct / 28 no-direct`。

GREEN：

- targets `1–11` 的字段、双 pass 顺序、逐级公式和上下限通过表驱动测试；
- LV9 鸣人 passive 1 使战斗实例 `max_hp/hp/base_max_hp` 在纯等级值上固定增加 30；
- LV16 鸣人 passive 7 使整备容量增加 1；
- target 10 从基础 9、被动 LV3 得到 12，不再被错误钳制；
- 覆盖矩阵修正为 35 条已有 ROM 生产消费者、10 条尚未闭合。

## 验证

- 全部 93 个 `butano-sequel/game/tests/test_*.cpp` 以
  `clang++ -std=c++20 -Wall -Wextra -Werror` 编译并执行通过；guard：
  `build/resource-guard/butano-persistent-passive-stats-host-20260727-01.json`。
- 相关 ROM/analyzer/generator/wiring 文档 Python 测试 121/121 通过。
- `git diff --check` 通过。
- 固定摘要 devkitARM 构建通过；guard：
  `build/resource-guard/butano-persistent-passive-stats-arm-20260727-01.json`。
  - ROM SHA-256：
    `be4201732a3a9dcf7ddfdb73fe107db75b7dc842fed8c99b6f5fbf85a31ef6d7`
  - ELF SHA-256：
    `46e9f9c9de1d83db2f8bdb1f8cccb910f2b9c4f0296ff5805eea1e51de072ab9`
- 受守护静音 mGBA：
  `build/butano-persistent-passive-stats-runtime-20260727-01/`。
  - frame 2804，battle 9，round 2，phase 1，活动单位 9；
  - 鸣人动作 2/忍具、小樱动作 1、佐助动作 2/5/16 均从正式目录可见；
  - controller/player error 为 0，两类 trap 文件均为空；
  - final state SHA-256：
    `9028d76a14b766049f323f0b96ceec3c6e76580a2cd284348b85d20c320ecef7`。

额外单独运行的旧 `tests.test_character_definition_writeback` 两项仍在
`web-editor/backend/rom_models.py` 因 SQLite 绑定 list 字段失败；该失败可独立复现，
不经过本轮文件，未越界修改。

## 未完成边界

- 自然 ARM 新档路线没有已训练的 targets `1–11`，因此 mGBA 只作完整 battle/controller
  回归；精确被动数值由真实 loader 与 campaign 集成测试验收。
- targets `0x0D–0x13` 的动作修正内联消费者已由后续
  `notes/battle-passive-action-modifier-runtime-20260727.md` 解码并接入统一 catalog；
  当前覆盖为 44 条生产消费者、1 条 ID 0 哨兵。
- 忍具装备例程已确认不存在逐件容量成本；仍需对全部 63 角色、等级和可训练 target 10
  组合证明生产可达值不会超过九格，不能只依赖算术分支的 99 上限。
- 被动名称二次校字、训练/属性变化专属表现和非静音音频未闭合；不能宣称完整战斗或音频
  已功能等价。
