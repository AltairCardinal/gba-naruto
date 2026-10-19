# Butano 数据驱动防御浏览器与场景接线计划

**Goal:** 用角色实例等级、完整主动动作槽和本场忍具槽生成防御动作浏览器，替换
scenario 41 “按 A 直接跳过防御”的占位分支。

**Architecture:** `battle_defense_browser` 只负责把 `UnitInstance → UnitDefinition →
ActionDefinition` 与装备槽投影成稳定菜单项，并为每项调用
`battle_defense_preparation::preview`。列表保留原作“进攻术也可浏览”的行为，但确认资格由
领域错误决定。场景 facade 只保存游标，不复制类别规则；提交仍由
`BattleTurnFlow::complete_defense` 完成。

## Task 1：实例等级与装载策略

- [x] 红测：单位实例保存等级，场景加载策略可覆盖角色等级，零值回退为 1。
- [x] 实现 `UnitInstance.level` 与 loader policy 接线。

## Task 2：数据驱动浏览器

- [x] 红测：等级 14 的角色 2 浏览完整已学主动术，action 15 可确认。
- [x] 红测：装备火弹 46 时保留忍具来源和槽；普通忍具可浏览但类别拒绝。
- [x] 实现固定容量 `battle_defense_browser`，列表生成零写会话。

## Task 3：scenario 41 输入与表现接线

- [x] 红测：防御确认可选择“不使用/浏览动作”，浏览列表来自通用服务。
- [x] 红测：鸣人的进攻术可浏览但确认不推进回合；B 返回防御确认。
- [x] 保留既有默认“不使用”黄金路线，避免新增隐藏 A。

## Task 4：验收

- [x] 全宿主 C++、定向 Python、diff check。
- [x] devkitARM 与受守卫 mGBA 路线。
- [x] 文档明确剩余截图资产只承担表现，不作为战斗结果来源。
