# Butano 战斗命令阻断领域设计

日期：2026-07-27

## 纠错目标

金缚术不能只把目标画成受击姿态。它必须经过正式动作定义、命中门、状态存储和阵营调度，
在持续期间真正改变目标能否行动；玩家和 AI 必须消费同一规则。截图、动画帧和
`reaction_state` 均不得成为战斗规则的事实源。

## 原作契约

机读证据为 `notes/battle-command-blocker-bindings-20260727.json`：

- 动作 80 模板位于 `0x08545958`，effect `0x3F`，成功率 85%，raw duration 2；
- handler `0x0807755C` 先调用 `0x0806A8C0` 请求 reaction `0x30`，再调用
  `0x0806C204` 把 `0x3F` 写入活动状态；
- 阵营切换后，controller 在 `0x080736E4` 调用 `0x08075350`；
- 该函数按 `0x3F → 0x3E → 0x3D → 0x0F → 0x11 → 0x15` 查询活动状态，任一命中
  就跳过该单位的激活；
- duration 继续使用既有 `(raw & 0x7F) * 2` side-end tick 规则。

因此，行动资格必须查询持久状态，不能查询 `reaction_state == 0x30`。后者只是表现反馈。

## 复用判断

1. 直接复用 `battle_action_resolver` 的成功率、事务和 effect registry，
   `battle_status_store` 的 16 槽 upsert/tick，以及 `battle_session` 的唯一行动资格入口。
2. 六个 blocker code 需要抽成共享只读谓词，供选人、轮换、AI scheduler 共用；不再各写
   一套状态判断。
3. 新规则追加到现有“动作结算 → 状态存储 → session 调度 → 玩家/AI flow”链路。
4. 不建立独立的金缚术状态机，也不让 renderer、关卡脚本或截图资产拥有业务写入口。

## 领域数据流

```text
ActionDefinition(80, effect 0x3F, duration 2)
  → BattleActionResolver（85% 命中门）
  → StatusStore.upsert(0x3F, 4 ticks)
  → reaction_state 0x30（只供表现）
  → BattleSession.command eligibility
       ├─ 玩家 select/cycle
       └─ AI turn flow
  → side-end tick
  → 状态到期后恢复行动资格
```

## 用户可见行为

- 入口：大蛇丸从正式角色技能目录选择金缚术并指定敌方单位。
- 命中：目标进入束缚反应，并在持续状态存在期间不能被玩家选中，也不会被 AI 调度行动。
- 同阵营仍有其他单位：单位轮换和 AI 调度跳过被束缚者，其他单位正常行动。
- 状态到期：后续阵营开始时目标恢复可选和可行动。
- 整个阵营都被阻断：控制器自动执行该阵营的 side-end；状态、战场对象、胜负条件和
  边界脚本照常推进，不显示一个无法操作的空选择页，也不会报 AI 错误。
- 未命中：不写状态、不改行动资格。
- 状态槽已满：整个动作以 `status_capacity_exhausted` 拒绝，不留下半提交的束缚状态。

当前切片不宣称完成金缚术专属图标、逐帧演出或音效。空阵营实现只闭合已经由
`0x080736A4..0x080736E4` 证明的“side-end → 翻转阵营 → 激活可行动单位”顺序；未绑定的
专属状态到期演出仍保持未实现。
