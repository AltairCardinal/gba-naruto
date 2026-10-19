# Butano 持久被动属性重算设计

日期：2026-07-27

## 纠错目标

角色副技能不能只停留在“已学习 ID/等级”和通用查询器里。原 ROM 在建立角色战斗模板时，
直接遍历 24 个副技能槽，把已学习被动换算进 HP、查克拉、攻、防、敏、移动、忍具容量和
结印成本。战斗 loader、临时状态 reducer、AI、HUD 与战前整备必须看到同一份被动修正后
基线，不能各自复制一套数值。

机读证据为
`notes/battle-persistent-passive-stat-bindings-20260727.json`，绑定完整函数
`0x0806D964..0x0806DDA3`、两个有序 pass、定义表和 flat jump table。

## 复用判断

1. 直接复用既有 `CharacterProgressionRecord.secondary_action_levels[24]`、
   `battle_passive_state`、45 项生成定义、角色等级成长公式和 scenario loader。
2. 抽取一个无副作用的持久被动重算函数，供战斗 loader 与 campaign 整备共同调用；
   不在两条链中各写一套 switch。
3. 新能力追加到“progression → passive state → stat baseline → battle/campaign consumer”
   链路，不建立关卡专用角色模板。
4. 不复用临时战斗状态 reducer：临时状态有 16 槽、duration 与到期重算，持久被动来自
   角色成长档案，生命周期和顺序不同；强行合并会破坏状态到期基线。

## ROM 契约

- 每个角色有 24 个四字节副技能槽，ID 在 `unit+0x50+4*i`，等级在
  `unit+0x51+4*i`；ID 0、等级 0/`0xFF` 不生效。
- 定义表位于 `0x085459C8`，每条 12 字节；数值公式是
  `base_a + per_level_a × (stored_level - 1)`。
- 必须先完整执行百分比/减免 pass，再完整执行固定加值 pass，不能按槽逐项混合：
  - target 2：HP 百分比提升，上限 999；
  - target 6：防御百分比提升，上限 99；
  - target 8：敏捷百分比提升，上限 99；
  - target 11：结印成本百分比降低，下限 1；
  - target 1/3/4/5/7/9/10：分别固定增加 HP、查克拉、攻击、防御、敏捷、移动、
    忍具容量，上限为 999/9/99/99/99/9/99；
  - target 2/6/8 在固定加值 jump table 中显式落到 no-op。

## 单一数据流

```text
CharacterProgressionRecord
  ├─ level
  └─ secondary_action_levels[24]
             │
             ▼
character_passive_state(UnitDefinition, levels)
             │
             ├─ 角色等级基础成长
             ▼
apply_persistent_passive_stats
  ├─ pass 1: percentage/reduction
  └─ pass 2: flat addition
             │
             ├─ BattleScenarioLoader → BattleUnitInstance/base_*
             └─ CampaignEquipmentService → capacity validation
```

战斗实例的 `base_attack/base_defense/base_agility/base_move_range/base_max_hp` 必须保存被动
修正后的基线。临时增减益到期时因此回到“等级 + 持久被动”，而不是回到 LV1 或纯等级值。

## 用户可见行为与边界

- 在统一训练页学习/升级属性被动后，下一场战斗的满 HP、查克拉和战斗属性立即按等级生效。
- 生命被动同时改变当前/最大/基准 HP；新战斗仍以满值开始。
- 忍具容量被动进入战前装备合法性判断，不再出现“学会了但仍按旧容量拒绝”的情况。
- 无学习状态、锁定状态、空槽与错误角色不会产生修正。
- 当前九格 `equipped_tools` 是角色记录的物理槽上限；ROM `0x08090004` 直接按容量统计
  扫描 `+0xB1+i`，没有逐件重量字段。target 10 的算术上限 99 不能反推为 99 个装备格；
  全角色/等级/训练组合仍必须证明生产可达容量不越过九格。
- target `0x0D..0x13` 的动作修正消费者由后续
  `2026-07-27-butano-passive-action-modifiers-design.md` 闭合；本切片自身仍只负责
  targets 1–11，不能把两种生命周期合并成一个 reducer。
