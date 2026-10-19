# Butano 跨关卡 AI 效用运行时实施计划

> 本计划继续执行已批准的
> `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`，
> 不重建 scenario 41 专用流程，也不把固定目标、坐标或截图状态当作 AI。

**目标：** 让敌方行动从当前战场状态、完整可用动作和所有合法目标中生成候选，
按已闭合的原作目标索引、状态门和效用权重严格择优，再交给玩家共用的
`battle_action_resolver` 提交。

**复用判断：**

- 直接复用 `grid_map`、`compute_reachable_costs`、`battle_attribute_system::view`、
  `battle_action_eligibility` 和 `battle_action_resolver::preview_units`。
- 不另建 AI 专用伤害/资格/状态真值；缺少的是目标索引与评分器，应作为独立只读领域组件
  供所有关卡共用。
- `scenario_41_battle` 只消费通用 `ai_plan`；关卡规则后续通过 typed
  `AiScenarioRule` 追加，不在场景 FSM 中写回合号或固定目标。

## Task 1：七维目标索引

**文件：**

- 新建 `butano-sequel/game/include/konoha/battle_ai_target_index.h`
- 新建 `butano-sequel/game/tests/test_battle_ai_target_index.cpp`
- 修改 `butano-sequel/game/include/konoha/battle_session.h`

**红：** 测试要求同/异阵营分别保存最低 HP 比、最大 HP、攻击、防御、敏捷、移动和地图距离；
相等时保留单位槽扫描顺序；任务角色 override 能占满异阵营七槽。

**绿：** 使用派生属性视图和调用方提供的地图距离构建固定容量索引；给单位模型增加中性的
AI role/link 字段，不赋予未经证据确认的可见名称。

**验证：**

`python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_ai_target_index`

## Task 2：状态门与标准效用评分

**文件：**

- 新建 `butano-sequel/game/include/konoha/battle_ai_utility.h`
- 新建 `butano-sequel/game/tests/test_battle_ai_utility.cpp`

**红：** 测试覆盖两组 target status-any 门、五组同族门、actor `0x12/0x12` 与
`0x0D/0x0D` 惩罚、七槽权重叠加、多 hit 按目标聚合、伤害截顶、成功率、覆盖率、范围、
资源/生存项、普通 0–9 随机尾项及 random-only override。

**绿：** 评分器只消费模拟后的 actor、单位只读数组和 queued effect event；固定数组聚合，
不修改真实 `BattleSession`。

**验证：**

`python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_ai_utility`

## Task 3：通用候选生成接入

**文件：**

- 修改 `butano-sequel/game/include/konoha/battle_ai.h`
- 修改 `butano-sequel/game/tests/test_battle_ai.cpp`

**红：** 移除 `objective.target_unit` 必须预填的前提；测试要求 planner 枚举每个可达落点、
每个动作和每个符合 target policy 的活动单位，过滤共享 preview 判定的非法项，并选择
效用最高的目标/动作。固定 objective 仅作为显式关卡约束保留。

**绿：** 从 preview 生成中性 queued event，交给 Task 2 评分；严格 `>` 更新候选，
无合法动作安全结束。旧 `ability_definition` 兼容入口暂时保留，避免无关迁移。

**验证：**

`python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_ai`

## Task 4：集成与持久证据

**文件：**

- 修改 `notes/butano-battle-domain-rewrite-20260723.md`
- 修改 `docs/sequel-roadmap.md`

**验证：**

- 全部 `butano-sequel/game/tests/test_*.cpp`
- battle 分析 Python 测试
- `git diff --check`
- 经 `tools/run_guarded.py` 构建 ROM
- scenario 41 mGBA 路线仅用于回归“通用 planner 可提交合法动作”，不把单关通过冒充完整战斗系统

**完成边界：** 本里程碑只闭合跨关卡 AI 的目标与标准效用主链；typed scenario rule、
多目标/空地/召唤候选、完整 condition 数据和多关卡自然路线仍在后续里程碑。

## 后续执行记录（同日）

- Task 1–4 已完成，并继续接入 typed scenario rule、empty-tile/召唤候选和多目标 queued event；
- ROM 绑定的面积形状、全部非空 effect handler、单/变体/成对召唤、多单位调度、
  47×3 condition、战场对象会话归属和护送集成测试已经完成；
- 当前剩余工作不再是 AI/领域核心，而是 47 场地图部署、剧情触发点和失败/特殊结果的
  Butano 可见场景接入。运行证据与精确边界记录在
  `notes/butano-battle-domain-rewrite-20260723.md` 的 2026-07-24 续记。
