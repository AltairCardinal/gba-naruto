# 战斗实例等级属性成长接线（2026-07-26）

## 纠错结论

此前 `battle_scenario_loader` 会把 progression 或章节 policy 的等级写入
`BattleUnitInstance.level`，并用它初始化技能解锁状态，但 HP、查克拉、攻、防、敏、移动
仍直接复制角色定义的 LV1 基础值。结果是 UI 虽显示 LV9，伤害、存活、AI 评分和状态重算
仍按 LV1 运行；`ninja_tool_capacity` 甚至没有进入战斗实例。这不符合完整角色数据模型。

当前链路修正为：

```text
CharacterProgressionRecord.level / ScenarioPolicy.character_levels
        │
        ▼
63×0x10 CharacterGrowthDefinition
        │  base + growth × (level - 1) / 100 + clamp
        ▼
BattleUnitInstance
  ├─ hp/max_hp, chakra/max_chakra
  ├─ attack/defense/agility/move_range
  ├─ base_* 等级基线
  └─ ninja_tool_capacity
        │
        ▼
status reducer / action preview / AI utility / scene snapshot / HUD
```

玩家持久进度、敌人、脚本角色和部署 placeholder 都经过同一个 loader 入口。当前 HP/查克拉
在新战斗中从等级上限满值开始；攻防敏、移动和最大 HP 的 `base_*` 同步设置，使临时状态
到期后回到该等级基线，而不是错误回到 LV1。

## 原 ROM 证据

稳定证据记录在 `notes/character-growth-runtime-chain-20260711.md`：

- 成长表：file `0x545068..0x545457`，63×`0x10`；
- 消费函数：Thumb `0x0806D964`；
- formation→battle 调用点：`0x0806AD40`；
- 模板字段随后复制到 `0x020240C0 + slot*0x1D4` 战斗单位；
- 公式：`base + growth × (level - 1) / 100`，HP 上限 999，攻防敏上限 99，
  移动上限 5，查克拉/忍具容量上限 9。

这里的 `9` 是纯等级成长阶段的基础钳制，不是持久被动后的最终上限。后续重新解码同一
函数的 `0x0806DAE6..0x0806DD95` 后确认：24 个副技能槽还会先执行百分比/结印减免，
再执行固定加值；target 10 对模板 `+6` 的最终钳制是 99。完整函数、jump table 与字段
证据见 `notes/battle-persistent-passive-stat-bindings-20260727.json`。

受控原 ROM A/B 已证明 character 1 的成长记录改变后，只改变模板与战斗单位对应字段，
不是人物信息页的孤立显示数据。

## TDD 与验证

RED：

- battle 15 policy 指定鸣人 LV9，实例仍为 LV1 的 HP 80；
- progression 结算后的 LV2 鸣人加载进 battle 41，实例仍为 HP 80；
- `BattleUnitInstance` 不存在 `ninja_tool_capacity`。

GREEN：

- LV1：HP80、CK5、AT14、DF13、AG8、MV3、忍具容量5；
- LV2：HP94、CK5、AT15、DF14、AG9、MV3、忍具容量5；
- LV9：HP196、CK5、AT22、DF21、AG16、MV3、忍具容量5；
- 后续完整解析 `0xB8` 编队记录后纠正：battle 10 variant 0 的敌方鸣人从
  record `+0x0F=0x14` 得到 **LV20**，精确值为 HP355、AT33、DF32、AG27；
- progression 技能状态应用后不会覆盖等级属性。

验证产物：

- 77 个宿主 C++：`/tmp/battle-level-stats-full-host-20260726-01.json`；
- 94 个成长提取、生成、文档与接线 Python 测试，1 skip；
- devkitARM：`/tmp/battle-level-stats-arm-build-20260726-01.json`；
- 静音 mGBA 回归：`artifacts/butano-level-stats-runtime-20260726-01/`。

mGBA 路线完成 battle 41→43→9、召唤后 9 个活动单位和 round 2，最终
SP `0x03006AE4`，controller/player error 与两个陷阱日志均为 0。该路线使用故事 LV1
角色，只证明 ARM 会话布局与完整回合未回归；LV2/LV9/LV20 精确成长由 loader
集成测试直接证明，
不能用 LV1 截图替代。

## 边界

- `ninja_tool_capacity` 已成为战斗实例事实，但战斗 HUD 尚未显示该字段；
- 已学习 targets `1–11` 现会进入等级属性后的持久被动重算；临时状态 reducer 的
  `base_*` 因而回到“等级 + 被动”基线；
- target 10 的 byte 统计上限 99 不等于 99 个装备槽；九格 UI/存档和每件忍具的容量
  消耗规则必须分开建模；
- 章节层仍需为非玩家敌人提供有证据的等级，默认 0 继续安全解释为 LV1；
- 多角色战后逐页、持久存档序列化、训练页面和非静音音频仍未闭合；
- 本里程碑修复角色等级→战斗数值，不代表完整战斗 Goal 已完成。

编队等级、15/24 动作槽和 9 忍具的后续完整接线见
`notes/battle-formation-runtime-config-20260726.md`；该记录取代早期把 battle 10 敌方鸣人
人工读成 LV2 的摘要。
