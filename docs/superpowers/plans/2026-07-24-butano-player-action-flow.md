# Butano 通用玩家行动控制器与场景适配计划

**Goal:** 将玩家侧“动作浏览 → 目标预览/确认 → 效果提交 → 朝向 → 防御 → 单位完成”
从 `scenario_41_battle` 的固定 switch 中抽出，形成可供其他关卡复用的应用层状态机。

**Architecture:** `battle_player_action_flow` 只保存 modal phase、目录游标、目标 preview 与
最近领域结果；唯一可变领域状态仍是外部 `BattleSession`。它组合
`battle_action_browser`、`battle_action_execution`、`battle_turn_flow` 和
`battle_defense_browser`。关卡可传入显式 action access policy 表达教程限制，但不得复制
角色学习、成本、目标或防御规则。

## Task 1：通用玩家行动 flow

- [x] 红测：非法 phase 不推进；打开动作列表从完整目录按 access policy 投影。
- [x] 红测：目标 preview 零写，非法目标保留 target phase，合法确认进入 facing/outcome。
- [x] 红测：朝向、防御浏览/取消、无防御和可用防御动作都走共享尾部。
- [x] 实现固定容量 flow snapshot 与错误结果，不存储 HP/坐标/资源副本。

## Task 2：scenario 43 跨关卡流程

- [x] 红测：scenario 43 选择 action 7、召唤影分身、确认朝向/无防御后切到敌方。
- [x] 红测：教学 access policy 只影响列表可见项，不改变角色完整目录。

## Task 3：scenario 41 适配

- [x] 红测：source wiring 要求玩家侧通过 `_player_flow`，禁止 facade 直接提交玩家 resolver。
- [x] 教程 action 5 由显式 access policy 选择，目标 preview 与确认委托 flow。
- [x] 结束行动、朝向和防御菜单委托 flow；scenario snapshot 只复制只读 flow view。
- [x] 保持既有无隐藏 A 的黄金路线和可见文案。

## Task 4：验收

- [x] 全宿主 C++、定向 Python、格式检查。
- [x] 无警告 devkitARM 构建与受守卫 mGBA 路线。
- [x] 文档明确通用 flow 已接入范围与 AI/资源命令/跨关卡表现剩余边界。
