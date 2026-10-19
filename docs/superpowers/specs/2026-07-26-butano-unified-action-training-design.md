# Butano 主动技/被动技统一训练架构设计

## 目标

纠正现有 Butano 战后训练只处理 15 个主动技槽的结构缺口，恢复原 ROM 同一训练控制器
同时列出主动技与被动技、统一消费训练点并把结果写回角色持久成长记录的行为。

这不是新增一个展示截图，也不是为被动技另建一套页面。完成后，训练结果必须沿现有
`character_progression_record → battle_scenario_loader → battle_unit_instance.passives`
链进入后续真实战斗，并被已经实现的被动查询与结算消费者读取。

## ROM 证据

- `0x08093670` 把当前训练行交给 `0x08093070`。
- `0x08093160` 先统一递减角色模板 `+0xBA` 的训练点。
- 训练行 `+4 == 4` 时，`0x08093170..0x08093188` 把等级写入
  `template + 0x51 + slot_index * 4`，即 24 个 secondary/passive 槽。
- 其他训练行由 `0x080931A0..0x080931B4` 写入
  `template + 0x15 + slot_index * 4`，即 15 个 primary/action 槽。
- type 4 行的 `+6` 是 45 项被动成长表 ID，`0x080932CA` 读取对应记录的
  `per_level_a` 生成训练反馈。
- 自然场景 42 观测中，鸣人有 8 个非空主动槽；第一个 type 4 行正好是目录索引 8，
  行记录 `03 05 06 04 04 06 01 00` 指向 secondary slot 0、被动成长 ID 1。

因此，最小可信目录顺序是：按角色模板顺序列出全部非空 primary 槽，再按模板顺序列出
全部非空 secondary 槽。锁定、未习得、已习得与满级仍是同一套
`0xFF / 0 / 1..3` 状态机。

## 方案比较

### 方案 A：新增独立被动训练页

会复制角色切换、条目循环、训练点、错误反馈和退出逻辑，也与 ROM 的同一目录/确认函数
不符，拒绝。

### 方案 B：只新增 `train_secondary_passive`

能写数据，但玩家没有入口，controller、UI 与存档后的战斗装载无法形成可验收闭环，拒绝。

### 方案 C：泛化现有训练 flow

把 `battle_primary_training_flow` 重构为 `battle_training_flow`，每个条目显式携带
`primary_action` 或 `secondary_passive` 类型。flow 仍只拥有选择状态，角色数据继续由
controller 持有；确认操作按条目类型调用唯一领域命令。该方案复用现有控制器阶段、结果链、
训练点、角色切换、错误显示、SRAM 和场景装载，采用。

## 领域模型

新增 `battle_training_entry_kind`：

- `primary_action`：身份来自 87 项主动动作表，状态来自 15 个 primary 槽；
- `secondary_passive`：身份来自 45 项被动成长表，状态来自 24 个 secondary 槽。

`train_primary_action` 保持主动动作数值成长资格校验。新增
`train_secondary_passive`，执行以下事务：

1. 验证角色有效、动作状态已初始化；
2. 验证槽位存在且不是空被动；
3. 拒绝 `0xFF` 锁定、等级 3、无训练点和无有效成长定义；
4. 成功时只做一次 `training_points -= 1` 与对应 secondary 槽等级 `+1`；
5. 失败时角色记录逐字节不变。

被动可训练性由 ROM 绑定的 45 项成长记录决定：ID 有效、记录身份匹配、target type 非零，
且 `per_level_a` 或 `per_level_b` 至少一个非零。UI 不复制这些规则。

## Flow 与场景接线

`battle_training_flow` 以固定顺序投影一个只读目录：

1. 当前角色全部非空 primary 槽；
2. 当前角色全部非空 secondary 槽。

快照包含条目类型、槽位、定义 ID、当前等级、解锁等级、剩余训练点、预览错误和最近提交错误。
上下只切换条目；L/R 只切换有训练点的有效参战角色；A 按类型调用领域命令；B 结束训练。

`battle_scene_controller` 继续持有 progression roster 和 flow，renderer 只读
`training_snapshot()`。训练阶段不复制技能定义、不直接扣点，也不触碰 battle session。
战斗结束合并进 campaign 时，15+24 个状态继续由既有原子合并与 SRAM 双槽机制保存。

## 玩家可见行为

- 入口：胜利结果和升级页完成后，有训练点时进入同一个 `TRAINING` 阶段。
- 展示：条目明确显示 `ACT` 或 `PASS`、定义身份、`LOCK / NEW / LVn / MAX` 和剩余 TP。
- 操作：上下遍历主动技与被动技，L/R 切换角色，A 投入一点，B 结束。
- 成功：TP 立即减一，等级立即增加；被动首次从 0 升到 1 后，后续战斗装载即可查询。
- 失败：锁定、满级、无点数、空槽或无成长定义时记录不变，并显示稳定错误码。
- 空状态：没有非空条目时显示 `NO TRAINING ENTRIES`，B 仍可退出。
- 数据缺失：没有经过二次校字的被动名称暂显示 `PASSIVE #ID`；不得把猜测文本写成正式名称。

## 集成证明

使用角色 3 的真实 secondary slot 13（被动 ID 15、level 5 解锁）做领域与场景装载证明：

1. 等级同步把槽状态从 `0xFF` 变为 0；
2. 训练确认把它从 0 变为 1，并消费一个 TP；
3. `apply_character_action_progression` 把 ID 15、level 1 写入单位 passive state；
4. `battle_passive_state::query(0x14)` 返回该槽和 ROM 表计算值 30；
5. 失败事务不改变 progression，主动技训练既有路线不回归。

## 边界

本里程碑闭合主动技/被动技共用训练架构、持久状态和后续战斗装载，不宣称 45 种被动的
全部战斗消费者、全部名称校字、训练专属动画/音频或更晚章节自然路线已经全部完成。
这些仍由完整战斗 Goal 后续里程碑继续闭合。
