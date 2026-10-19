# Butano 战斗实例等级属性成长实施计划

## 目标

把已有 ROM 角色成长纯函数接入正式 scenario loader，使玩家进度、敌方等级、脚本角色和
部署角色的等级实际决定战斗 HP、查克拉、攻、防、敏、移动和忍具容量，而不是只改变标签与
技能解锁。

## 复用决策

- 直接复用 `character_stats_at_level` 和生成的 63 条
  `character_growth_definitions`；
- 在 loader 这一唯一实例化链追加应用，不在 UI、AI 或各关卡重算；
- `BattleUnitInstance` 只补此前丢失的忍具容量；已有当前值和 `base_*` 字段继续作为
  状态 reducer 的唯一基线。

## TDD

- [x] RED：LV9 policy 加载后仍是 LV1 属性。
- [x] RED：LV2 progression 的技能状态正确、战斗属性错误。
- [x] RED：实例缺少第七成长字段 `ninja_tool_capacity`。
- [x] GREEN：玩家、敌方与 progression 统一应用七项成长。
- [x] REFACTOR：成长公式保持在 `battle_progression`，loader 只负责跨表接线。

## 验证

- [x] 77 个宿主 C++ 全量通过。
- [x] 94 个相关 Python 测试通过，1 skip。
- [x] 固定 devkitARM 构建通过。
- [x] 静音 mGBA 三场连续路线进入 round 2，最终 SP 和错误码正常。
- [x] `rom/base.sav` 哈希保持不变。
