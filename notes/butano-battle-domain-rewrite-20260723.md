# Butano 战斗领域与组件渲染纠错记录（2026-07-23）

## 纠错原因

用户复核指出，旧 scenario 41 以预制整屏画面和固定菜单路线拼出战斗外观，不能视为战斗架构。
本轮以此为失败基线：交互阶段的地图、单位、游标、HP、菜单、目标和结果必须来自同一份领域状态，
表现层不得写入坐标、HP、资源、行动账本或胜负。

## 已替换的运行链

- `battle_action_system.h` 将成本、效果、目标、范围、升级和表现绑定拆成正交策略；预览无写入，
  最终解析使用 session 副本原子提交，并支持逐 hit、命中 RNG、伤害、治疗、召唤、忍具槽消耗、
  写轮眼一次性反应和明确的 unsupported handler 错误；
- `battle_action_loadout.h` 从 63 条角色模板的 15 个主动槽按初始状态和等级生成实际动作列表，
  再与 87 条主动动作定义表做引用校验和实体化。鸣人等级 1 的通用列表是 `[2,5,7]`；
  scenario 41 的教程规则显式限制为动作 5，而敌方角色 30 的 AI 消费完整 `[1..6]`；
- AI 对每个可达落点和每个装备动作调用与玩家相同的 `battle_action_resolver::preview_units`，
  只提交合法且评分最高的候选；不再接收唯一的硬编码攻击，也不再按回合号移动到固定坐标；
- 动作提交现在显式携带面向；玩家面向目标，AI 使用规划落点到目标的朝向。任务保护单位缺失会返回
  `invalid_objective`，不会继续生成候选；
- `scenario_41_scene.cpp` 不再引用 `scenario_41_combat_layers.h`。活动战斗阶段统一保持一张清理后的
  `scenario_41_clean_map`，鸣人、敌人和游标分别由 sprite 按领域坐标移动，HP 和菜单由
  `present_scenario_41` + `render_battle_overlay` 实时生成；敌方 HP 归零且 `active=false` 后 sprite 消失；
- `generate_butano_battle_runtime_assets.py` 从哈希绑定的旧参考图机械派生无单位地图和独立敌方 sprite。
  生成只改变原图两个 32×32 区域，测试逐像素证明其他位置不变。一次内置生成式去物体尝试会改变
  整张像素图和尺寸，已判为不合格且没有进入工作区或 ROM。

## TDD 与验证

本轮新增或扩展的红绿测试覆盖：

- 动作提交面向；
- AI 保护目标配置错误；
- 多动作 AI 严格择优；
- 角色动作列表、等级解锁、关卡过滤和定义引用；
- 地图/敌方 sprite 的确定性生成和像素改动边界；
- 活动场景禁止重新引用整屏 combat layer；
- 实时 presenter 的行动菜单和术菜单。

验证结果：

- 宿主 C++：20 个测试程序全部通过；
- Python 相关生成器、构建、素材和研究文档测试：50 项通过，1 项环境开关构建测试跳过；
- `py_compile` 与 `git diff --check` 通过；
- Butano/ARM 构建经 `tools/run_guarded.py` 完成，峰值 RSS `64.75390625 MiB`，无降级；
- ROM：`butano-sequel/butano-sequel.gba`，大小 `7,605,664`，SHA-256
  `aefce90b11fcf9f41a7442ed73b36e69b3c5986be2a00a98cb8b6ecfd5c91b0d`；
- ELF SHA-256：`e80e2ca8a5cd476181edc0586e69d618fa5b0c2781f111ec32d5e8a84bb4c045`；
- mGBA 完整路线：`build/butano-component-runtime-20260723-01/`，2580 帧成功标记、最终 savestate、
  交互阶段和战后截图齐全；守卫摘要
  `build/resource-guard/butano-component-runtime-20260723-01.json`，峰值 RSS `53.56640625 MiB`，
  `completion_trigger=success-marker`。本次自动验收静音运行，因此不作为音频质量证据。

## 当前边界

这次已经修复“交互战斗由整屏截图和固定伤害驱动”的错误，但不能宣称完整功能等价：

- 不可交互的必杀动画、教程对白、胜利和战后结算仍暂时消费参考帧；它们只读领域结果，
  但后续仍应从原始 tile/sprite/timeline 重建；
- 87 条主动动作和 94 条忍具已经有完整模板，仍有 resolver handler 尚未实现，未实现项会被明确拒绝；
- 多目标范围、完整属性状态 reducer、递归反击/联动、完整七槽 AI utility、47 场 condition 数据、
  多角色/多敌/召唤/护送的通用运行场景仍需接入；
- scenario 41 facade 仍含关卡演出兼容状态，不能拿单关成功代替跨关卡架构验收。
