# Butano 战后主技能修炼页设计

> 此初始设计已被
> `docs/superpowers/specs/2026-07-26-butano-unified-action-training-design.md`
> 取代。生产实现不再限制为主技能，而是复用同一 flow 处理主动技和被动技；本文只保留
> 初始主动技接线的历史决策。

## 目标

把现有“角色升级后获得修炼点、领域函数可提升技能”的后台能力接入玩家可操作流程。
战斗胜利并完成等级结算后，若任一参战角色仍有修炼点，控制器进入主技能修炼阶段；
玩家可查看该角色全部非空主技能槽，并把修炼点投入已解锁且可成长的技能。

本设计恢复的是原 ROM 已绑定的
`结果结算 → state 3 → training-list controller → 训练确认 → 扣点/技能等级增加`
链。它不把修炼塞进战斗命令菜单，也不实现证据尚未闭合的副技能修炼。

## 方案选择

考虑过三个入口：

1. 战斗中的临时技能菜单：入口短，但会把持久成长命令混入单位回合事务，拒绝。
2. 独立木叶主菜单：长期形态合理，但当前 Butano 尚无完整章节/城镇导航壳，会新增无证据入口。
3. 战后等级结算后的训练阶段：与 `0x0808E16E → 0x08093698 → 0x0809337C`
   原 ROM 控制流一致，且可直接复用 controller 已持有的 progression roster，采用。

## 架构

新增 `battle_primary_training_flow`，它只拥有选择状态，不拥有角色数据。每次查询或提交都
接收 controller 的 `character_progression_record[3]`：

- 构建当前角色的非空主技能槽目录；
- 上下移动时只改变所选目录项；
- L/R 在有修炼点的有效角色之间循环；
- A 调用唯一领域命令 `train_primary_action(record, slot_index)`；
- B 结束训练阶段，不修改任何技能；
- 成功后重建快照，使剩余修炼点和技能等级立即可见。

`battle_scene_controller` 增加 `training` 阶段，并把只读
`battle_primary_training_snapshot` 放入统一 scene snapshot。结果阶段仍先结算经验和等级；
等级页确认后，controller 才根据 roster 决定进入 training 或 complete。

`battle_runtime_scene` 只显示角色名、剩余点数、技能名、当前状态和按键提示。它不读取
技能模板来决定能否升级，也不写 progression。错误反馈来自 flow 返回的稳定
`action_training_error`。

## 玩家可见行为

- 入口：胜利结果页确认，若发生升级先显示等级成长；随后有修炼点时进入 `TRAINING`。
- 展示：当前角色、剩余修炼点、选中技能名称，以及 `LOCK`、`NEW`、`LV1`、`LV2`、
  `MAX` 或不可成长状态。
- 操作：上下切换技能，L/R 切换有修炼点的角色，A 投入一点，B 结束修炼。
- 成功反馈：剩余点数减一，技能等级立即增加；新习得技能之后可由正式战斗 catalog 读取。
- 错误反馈：锁定、满级、不可成长或点数不足时保持数据不变，并显示对应错误。
- 空状态：没有非空主技能槽或没有可切换角色时安全显示空目录；B 仍可退出。
- 边界：本里程碑不保存到 SRAM，不实现副技能修炼，不补造未证实的说明文案或专属音效。

## 数据与错误边界

修炼事务的唯一事实源保持为 `train_primary_action`。UI 不预扣点，不先写技能等级，也不在
失败后做补偿。锁定状态 `0xFF`、未习得状态 `0` 与技能等级 `1..3` 保持原语义。

角色切换只接受 `active && action_states_initialized && training_points > 0` 的记录。
目录只排除 action ID 0/`no_ability` 的空槽，锁定和不可成长技能仍显示，以便玩家理解
完整技能列表与当前不可操作原因。

## 测试

1. flow 单元测试覆盖目录、上下循环、角色切换、锁定/满级/不可成长/无点数和成功扣点。
2. controller 集成测试从真实 battle 41 结果推进到升级、修炼、再进入 complete，并证明
   修炼后的技能等级留在同一 progression roster。
3. runtime wiring 测试约束 `TRAINING` 文本、输入路由和遥测字段，防止 UI 绕过 flow。
4. 全量宿主 C++、相关 Python、devkitARM 构建和静音 mGBA 路线验证阶段可达且无黑屏。

## 证据边界纠正

effect `0x3F` 调用的 `0x0806A8C0` 会把反应值写入原 ROM `unit+0xC0` 的 `0x70`
位域，并受状态 `0x15/0x11/0x0F/0x3F/0x3E/0x3D` 仲裁。该字段属于反应/表现状态，
不能被解释成一个尚缺的“禁止行动”消费者。持续生命周期由状态 `0x3F` 自身承担；
本里程碑不添加虚构的行动资格规则。
