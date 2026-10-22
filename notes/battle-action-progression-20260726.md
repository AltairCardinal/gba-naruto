# 战斗技能状态、修炼与等级成长证据（2026-07-26）

## 结论

原作的角色等级、技能解锁和技能习得是三个不同状态，不能用“角色达到等级”直接生成
可战斗技能。每个角色持久保存 15 个主技能槽和 24 个副技能槽；每槽的四字节记录为
`技能 ID / 状态 / 解锁等级 / 保留`。

状态机为：

```text
0xFF 锁定
  │ 角色等级达到解锁等级
  ▼
0 未习得
  │ 消耗 1 修炼点
  ▼
1 级 ──消耗 1 点──> 2 级 ──消耗 1 点──> 3 级
```

- `0xFF` 与 `0` 都不能进入战斗动作目录；
- 只有 `1..254` 会被原作战斗目录构建器接受；
- 等级阈值只执行 `0xFF → 0`，不会自动习得；
- 战斗动作模板按持久技能等级物化数值成长，公式为
  `base + per_level_growth × (action_level - 1)`，结果保存为 `u8`。

公开攻略关于“角色每升一级获得一点修炼点、每点提升一项忍术、多数忍术最高三级”的
说明只用于补充玩家可见描述和三级上限；状态转换、扣点和数值成长均以 ROM 控制流为
主要证据。

## ROM 证据

基准 ROM：`rom/base.gba`，SHA-256
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

| 语义 | 地址范围 | SHA-256 |
|---|---|---|
| 四字节槽初始化 | `0x0806D4A0..0x0806D580` | `094dc8b1249e73061d40dccc45e0183b818368cf707b604717e284f0732fa605` |
| 战斗目录状态门 | `0x0806FDF2..0x0806FE3A` | `3b72284a0f73ff76c8b6f7b590472cbb29c4580f0d353cf881b53973b24f815a` |
| 升级解锁 `0xFF→0` | `0x080899EC..0x08089AD0` | `3c6b60470f9ed33e40f98cdbb434cfac380935ea10fbf2ec55ea797c122b7139` |
| 修炼点扣除与槽等级增加 | `0x08093070..0x080931CE` | `81a9e46969e5844a003af593ae885e28c518ce343e376525b3d3a267f42dc6c2` |
| 动作等级成长物化 | `0x0806D85C..0x0806D910` | `dd78df15b6599a2bc73fd04e5b04f8a58cb8d761f7d7ae3a0460a5daae9daa7f` |

`0x08093160` 先统一递减角色模板 `+0xBA` 的修炼点。训练行 `+4 == 4` 时，
`0x08093170..0x08093188` 增加 `template + 0x51 + slot*4` 的副技能/被动状态；
其他训练行由 `0x080931A0..0x080931B4` 增加
`template + 0x15 + slot*4` 的主技能状态。动作成长的目标类型为：

1. potency；
2. 基础段数；
3. 成功率；
4. 距离/直线 flags；
5. 范围/形状 flags；
6. 持续回合；
7. 不调整。

完整机读 manifest 为
`notes/battle-action-progression-20260726.json`，可由
`tools/analyze_battle_action_progression.py` 重建并校验所有证据片段哈希。

## 旧实现为何不是技能系统

旧 Butano `action_slot_available` 只比较角色等级与槽的解锁等级，导致：

- 锁定状态 `0xFF` 达到阈值后直接进入战斗，相当于跳过修炼；
- 初始状态为 `0` 的技能永久被过滤，没有任何状态转移能使其可用；
- 技能没有持久等级，因此 UI、目录和 resolver 只能看到基础模板；
- 同一技能“1 级/3 级”不会产生不同结算结果。

共有 20 个 resolver 已支持、但所有角色槽都只以状态 `0` 初始化的主动动作因此永久不可达：

`23, 24, 25, 26, 27, 31, 33, 36, 37, 38, 41, 51, 54, 55, 56, 57, 58, 60, 61, 66`。

这不是内容缺一条菜单项，而是角色成长状态没有进入战斗领域模型。

## Butano 领域链

当前唯一数据流为：

```text
CharacterProgressionRecord
  ├─ level / experience / training_points
  ├─ primary_action_levels[15]
  └─ secondary_action_levels[24]
                 │
                 ▼
BattleScenarioLoader
                 │
                 ▼
BattleUnitInstance
  ├─ primary_action_levels → ActionLoadout → ActionCatalog
  │                                           │
  │                              action_definition_at_level
  │                                           │
  │                                           ▼
  │                              Browser / AI / Resolver / TurnFlow
  └─ passives
       ├─ targets 1–11 → ordered persistent stat recalculation
       └─ other targets → PassiveQuery → PassiveConsumers
```

- `initialize_character_action_progression` 从角色不可变定义初始化全部槽状态；
- `synchronize_character_action_unlocks` 只把新达到阈值的 `0xFF` 转成 `0`；
- `train_primary_action` 原子验证槽、修炼点、可成长性和三级上限，再扣一点并提升一级；
- `train_secondary_passive` 对 24 个副槽执行相同事务边界，并以 45 项 ROM 被动成长表
  验证可训练性；
- scenario loader 对玩家角色按角色 ID 注入持久进度；没有玩家进度的敌人从不可变角色定义
  初始化运行时状态；
- catalog 只接收状态 `1..254`，并在 browser 和 resolver 之前物化等级成长；
- UI 与 360 字节遥测都从 player/training snapshot 读取等级和条目类型，表现层不回写
  角色定义或 progression。

Kiba 的 action 23 已作为可达性回归：初始化时状态为 `0`，消耗一点修炼点后变为 `1`，
随后由正式 scenario→unit→catalog 链找到。鸣人 action 5 的三级目录 potency 为 20，
一级为 10；把相同攻防归一化后送入正式 resolver，三级单段伤害严格比一级多 10。

## ARM 运行与资源边界

增加技能状态后，运行时验证还暴露了两个不能被宿主测试替代的 GBA 问题：

1. 41→43 场景切换时，静态文字和剧本字形 sprite 句柄被清空，但 Butano 要到下一次
   `bn::core::update()` 才回收 OBJ tile。新场景提前创建双人头像会触发
   `bn_sprite_tiles_manager.cpp:921` 的 128-tile 分配失败。现在先清空所有持久 sprite
   句柄、提交一次 core update，再创建新光标和头像。
2. 防御结算已有 EWRAM 事务副本，`battle_turn_flow::complete_defense` 又在栈上复制整份
   12 单位 session。按 A 后 SP 从 `0x03006AE4` 跌到 `0x030012E4`，覆盖 IWRAM/Maxmod
   区域并停在 `mmMixerMix`。现在 encounter runtime 只建立一份 EWRAM 候选；玩家资源、
   主动技能、AI 资源/技能、效果后处理、防御准备和回合收尾全部使用 `*_in_place`
   操作这份候选。失败丢弃工作区，成功才一次提交正式状态；宿主包装器仍保留事务语义。

最终静音 mGBA 证据为
`artifacts/butano-action-progression-runtime-20260726-09/`：

- 完成 battle 41→43→9 三场切换；
- battle 9 进入 round 2，活动单位为 9；
- 鸣人 action `2/5/7`、佐助 `2/5/16`、小樱 `1` 均从 ARM 遥测读到 `LV1`；
- 最终 SP 为 `0x03006AE4`，controller/player error 均为 0；
- ROM/ELF SHA-256 分别为
  `9aab2400ddfa3f362f351a2536407ce1d14f81771a8f2f11b0eb5d53c4228209` /
  `9aa37cbacc6ca03c4b0e4ce7fd1573839359bec51b9d94b94daac161fec7e87a`。

该路线使用 `mute=1`，证明战斗栈不再确定性破坏 Maxmod 状态，但不能签发主观音频听感。

## 边界

本里程碑现已闭合主/副技能共同的持久状态、等级解锁和训练分配架构。后续
`notes/battle-unified-training-runtime-20260726.md` 证明统一目录、secondary 领域事务、
controller、ARM 页面和 passive consumer 装载闭环。45 项被动的全部消费者、名称二次
校字、逐技能动画和非静音音频仍不是已完成范围。targets `0x0D–0x13` 的动作修正消费者
已由 `notes/battle-passive-action-modifier-runtime-20260727.md` 接入“动作等级成长后”
的统一 catalog 顺序。
targets `1–11` 的内联属性消费者已由
`notes/battle-persistent-passive-stat-bindings-20260727.json` 与运行记录闭合，不能再
列入“无消费者被动”。
