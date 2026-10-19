# Butano 敌方资源指令回合策略 Implementation Plan

**Goal:** 让敌方单位在统一战斗回合中，依据已逆出的原作效用权重自主比较技能、结印回查克拉、休息回血，并通过同一事务链完成回合和运行时反馈。

**Architecture:** 不新增 AI 专用效果系统。`battle_resource_commands` 提供单一的纯单位预览规则；`battle_ai` 将合法资源变化投影到现有 `battle_ai_utility_scorer`；`battle_ai_turn_flow` 在会话副本中调用已有资源事务与 `battle_turn_flow`，成功后原子提交；`battle_scene_presentation` 只读取结果并显示反馈。

**Evidence boundary:** 资源公式沿用已经由教程、ROM 事务函数和玩家命令验证的规则；选择策略只使用 ROM AI 评分器已经绑定的 HP/查克拉权重与严格大于替换规则。当前证据不足以确定 AI 防御选择，仍保持独立待逆向边界，不猜测实现。

## Reuse decision

1. 直接复用 `battle_resource_commands`、`battle_ai_utility_scorer`、`battle_turn_flow` 和 `battle_scene_presentation`。
2. 将已有 session 预览公式抽成纯单位重载，供玩家和 AI 共用；不复制公式。
3. 新能力追加到 `loadout → catalog → planner → transaction → controller → presentation` 现有链路。
4. 不建立独立 AI 资源状态机，因为这会造成玩家/敌方公式和回合尾语义分叉。

## Task 1：纯资源预览

- [x] 在 `test_battle_resource_commands.cpp` 先断言纯单位预览与 session 预览完全一致，并覆盖移动后拒绝。
- [x] 确认测试因缺少重载而编译失败。
- [x] 增加 `preview(unit, type, amount, movement_previewed)`，session 版本只负责阶段/选中单位校验并委托。
- [x] 重跑测试并确认通过。

## Task 2：AI 资源候选

- [x] 在 `test_battle_ai.cpp` 先覆盖低查克拉结印、低血休息、满资源不选、技能效用更高时仍选技能。
- [x] 确认红测。
- [x] 为 `ai_action` 增加资源指令和数量；只在 actor 原始格生成合法候选。
- [x] 使用资源投影和空事件调用 `battle_ai_utility_scorer::score`，保留现有严格 `>` 取胜规则。
- [x] 重跑测试并重构重复投影代码。

## Task 3：事务式敌方回合

- [x] 在 `test_battle_ai_turn_flow.cpp` 先覆盖精确 HP/查克拉变化、单位完成/换边、失败零写。
- [x] 确认红测。
- [x] 在 session/RNG 副本上调用共享资源 commit，再通过 `complete_non_target_action` 推进。
- [x] 将资源类型、数量和变化量写入结果；全部成功后才提交副本。
- [x] 重跑测试。

## Task 4：运行时反馈与集成

- [x] 先增加 scene controller/presentation/wiring 失败测试。
- [x] 将资源结果接到现有 presentation event，显示 `CHAKRA +N HP -M` 或 `REST HP +N`。
- [x] 保持 presentation 只读，不把 UI 作为战斗状态来源。
- [x] 运行相关宿主单元/集成测试、Python wiring 测试、格式检查和 devkitARM 构建。
- [x] 使用受资源守卫的 mGBA 在至少两个真实战斗配置中验证，不覆盖原始证据。
- [x] 更新架构文档、证据记录和路线图，明确 AI 防御仍未闭合。
