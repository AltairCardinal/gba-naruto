# Butano 持久被动动作修正设计

日期：2026-07-27

## 纠错目标

角色被动不能只存在于训练档案或通用查询器中。原 ROM 在每次建立主动技/忍具的运行时
动作副本时，直接遍历角色的 24 个副技能槽，按固定顺序修改 potency 与成功率。目录、
玩家、AI、预览和 resolver 必须消费同一份修正后定义；表现层不能另算数值，也不能用
选项或截图模拟被动生效。

机读证据为
`notes/battle-passive-action-modifier-bindings-20260727.json`，它 fail-closed 绑定
`0x0806D6B8..0x0806D855`、两个有序 pass、定义表、flat jump table，以及主动技和忍具
两个初始化器的真实调用点。

## 复用判断

1. 直接复用 `battle_passive_state`、45 项生成被动定义、主动技等级物化和忍具动作模板。
2. 抽取一个纯函数修正 `action_definition` 副本，主动技与忍具 catalog 共用；不在玩家、
   AI、browser、preview 或 resolver 中复制 switch。
3. 新规则追加在既有 `BattleUnitInstance → BattleActionCatalog → Browser/AI/Resolver`
   链路，不能建立关卡或角色专用动作表。
4. 不复用角色属性重算：targets 1–11 修改长期角色基线，targets 13–19 修改单次命令的
   动作副本，字段与生命周期不同。

## ROM 契约

- 每槽 ID、等级、失活条件和数值公式与持久属性被动一致：
  `base_a + per_level_a × (stored_level - 1)`。
- 必须先遍历全部 24 槽执行百分比 pass，再重新遍历全部 24 槽执行固定加值 pass。
- 运行时动作字段只按 ROM 数字契约解释：
  - `+0..+1`：成本/动画 header；
  - `+2 low 6 bits`：effect code；
  - `+4`：potency；
  - `+6`：成功率。
- 百分比 pass：
  - target 14：`header == 0x0102 && effect != 0x21`，或 effect `0x0A`，
    potency 百分比提升，上限 99；
  - target 16：header `0x0101`，potency 百分比提升，上限 99。
- 固定 pass：
  - targets 13/15/17：分别按上述物理谓词、header `0x0101`、header `0x0105`
    固定增加 potency，上限 99；
  - targets 14/16：显式 no-op，因为已在百分比 pass 处理；
  - target 18：仅 effect `0x1A` 固定增加 potency，以 u8 保存，ROM 无显式 99 钳制；
  - target 19：所有运行时动作增加成功率；ROM 在 u8 写入前比较 999，现有定义不会溢出。
- 主动技初始化顺序是“动作等级成长 → 被动修正”；忍具顺序是“模板/槽成本物化 →
  被动修正”。

## 单一数据流

```text
CharacterProgressionRecord.secondary_action_levels
                     │
                     ▼
BattleUnitInstance.passives
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
active action template      ninja tool template
          │ level growth         │ tool-slot cost binding
          └──────────┬──────────┘
                     ▼
apply_persistent_passive_action_modifiers
          ├─ pass 1: percentage
          └─ pass 2: flat addition
                     │
                     ▼
BattleActionCatalog
          ├─ player browser / preview
          ├─ AI candidate / execution
          └─ shared resolver / presentation events
```

## 用户可见行为与边界

- 训练相应被动后，下一场战斗中符合谓词的主动技/忍具威力或成功率会改变；不符合谓词的
  动作保持原值。
- 玩家预览、AI 选择和最终结算读取同一 catalog 定义，不会出现预览增强但结算回退。
- 空槽、锁定、未学习和非法被动 ID 不产生修正。
- 本里程碑只绑定数值谓词，不给 targets 13–19 猜测未经校字的名称，也不新增专属动画。
- target 19 的 ROM 比较常量 999 与 u8 存储不一致；实现保留 ROM 现有定义可达范围，
  不凭空扩展字段宽度。
- 这闭合被动定义的生产消费者，不代表所有主动技可达性、每件忍具容量成本、专属表现或
  非静音音频已经功能等价。
