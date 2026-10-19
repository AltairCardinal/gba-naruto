# 主动动作自然可达性审计（2026-07-26）

## 为什么重新审计

此前覆盖率把“resolver 能解析某个 16 字节定义”近似成“这个动作能从正式战斗自然使用”，
并把角色主槽 `state=0` 误读成永久禁用。两者都会把数据表完成度包装成战斗系统完成度。

本审计以真实生产链为口径：

`63 角色模板 / 1,728 条关卡编队 / 组合配方`
→ `scenario loader`
→ `BattleSession`
→ `action catalog`
→ `玩家或 AI flow`
→ `统一 resolver`
→ `领域状态`
→ `只读 snapshot`
→ `renderer`

截图、录像帧和表现资源只能校验最后一层，不能代替前面的单位、动作、回合或结算状态。

## 可复现产物

- 分析器：`tools/analyze_battle_action_reachability.py`
- 测试：`tests/test_analyze_battle_action_reachability.py`
- 87 项机读清单：`notes/battle-action-reachability-20260726.json`

输入均按 SHA-256 fail-closed：

- 63 条角色模板：`sequel/content/units/bank.json`
- 1,728 条编队实例：`sequel/content/positions/bank.json`
- 87 条动作定义：`sequel/content/battle-config/bank.json`
- 87 条运行时视觉身份：`sequel/content/battle-config/action-identities.json`
- 五条组合产物、技能成长状态机和独立资源命令证据
- 原版 ROM 的动作 19 场景解锁函数、专属分支、调用窗口和字面量

## 状态口径纠正

ROM 已闭合的主槽状态机是：

- `0xFF`：锁定；
- `0`：已解锁、未学习；
- `1..3`：已学习等级。

因此 `state=0` 不能被称为“永久不可达”。它必须先经过修炼 `0→1`，随后才进入只接受
`1..254` 的战斗目录。共有 26 个动作身份至少有一条角色模板 `state=0` 路线，其中此前
被错误列为不可达的 20 个非空 effect 动作均属于这类。

另有 32 个身份存在“等级解锁后再修炼”路线。动作 19 的锁定槽
`unlock_level=0` 不是未闭合外部入口：原 ROM
`0x08089A1A..0x08089A4A` 明确规定 battle 31 / variant 0、角色 2（佐助）、
动作 19 时执行 `0xFF→0`。它随后仍需正常训练 `0→1`；错误 battle、Arena variant 1
和其他角色均不解锁。完整证据见 `notes/battle-scenario-action-unlock-20260726.md`。

## 关卡实例是正式动作来源

65 个动作身份至少出现在一条有效编队记录的 catalog 可接受主槽。关卡实例覆盖不是测试
夹具，而是原 ROM 构造器复制到战斗单位的正式配置。

动作 62“雾隐术”是最重要的纠正：

| 编队记录 | 角色 selector | 主槽 | state |
|---|---:|---:|---:|
| `g08_v0_r01` | 20（再不斩） | 4 | 3 |
| `g08_v2_r03` | 20（再不斩） | 4 | 3 |

`test_battle_scenario_loader.cpp` 现在从 battle 8 / variant 0 自然加载这条记录，验证：

1. 单位 2 是 25 级敌方再不斩；
2. 主槽 4 是 LV3 动作 62；
3. catalog 物化为当前查克拉成本 2、effect `0x0D`、self/implicit actor、
   raw duration 5；
4. 经过正式 resolver 后查克拉减少 2，并在再不斩身上写入 10 tick 的 `0x0D` 状态。

这证明动作 62 不是“测试专用内部动作”，也不是截图菜单里硬拼出来的选项。

## 派生、命令与全零模板

- 10、11、13、17、18 是两组件组合后的替换结果；它们不应伪装成角色主菜单里的五个
  独立槽位。
- 20 的精确显示身份是“结印”，动作定义全零，也没有 catalog 可接受主槽。独立资源命令
  已由原 ROM 和 checkpoint 证明执行“结印值作为 HP 成本、换取当前查克拉”的事务。
  这里记录二者的身份关联，但不会把全零动作 20 送进 resolver。
- 39“柔拳八卦掌”、40“回天术”、52“砂缚柩”均为精确显示身份，但动作定义全零，
  且在角色 primary 与有效编队 primary 中都没有引用。它们当前分类为
  `unreferenced_zero_template`；在闭合调用点或自然运行证据前，不猜造伤害、范围或状态。
- 0“没有”是哨兵，不把数千个空槽计成训练路线。

## 架构验收含义

本项证明的是“动作身份从哪里进入领域”的数据架构，不是宣称 87 项表现和玩法全部完成。
后续关卡必须继续通过同一条 loader/catalog/flow/resolver 链追加内容，不能在 scene 中直接
修改 HP、坐标、行动完成标志，也不能用整屏战斗截图代替单位或回合状态。

仍未闭合：

- 39/40/52 是否仅为废弃、表现或其他非主槽身份；
- 每个动作的专属逐帧表现、状态图标与非静音音频；
- 已知但语义不足的间接状态和 type-2 战场对象。

完整战斗 Goal 因此保持未完成。

## 2026-07-27 逐 handler 语义补强

后续 `test_battle_all_actions_runtime.cpp` 已从“resolve 成功”提升为逐 handler 权威后果门：
76 个角色模板动作、battle 8 action 62 和忍具 1–93 必须分别产生真实伤害、状态、召唤、
移动、身份变化、治疗、对象槽、查克拉变化或 reaction；action 9 只允许作为已证明的强制
组合组件。结合五个组合结果测试，全部 82 个非零主动定义与 93 个非空忍具定义已有生产
领域后果证据。详见 `notes/battle-all-action-semantic-sweep-20260727.md`。
