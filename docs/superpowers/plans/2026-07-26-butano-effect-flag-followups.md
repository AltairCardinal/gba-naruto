# Butano 战斗效果高位 follow-up 实施记录

## 目标

用 ROM 指令和生产路线闭合 effect byte 的 `0x80/0x40`，避免非零定义仅“解析成功”却没有
对应玩法效果。

## 复用判断

1. 直接复用 `battle_action_resolver`、`battle_status_store`、有序属性 reducer、
   防御准备、战场对象到期 resolver 和外层会话/RNG 事务。
2. 高位 follow-up 同时被普通 damage、反应和对象消费，应抽成一个内部 policy，不为毒手里剑、
   毒烟和毒起爆牌分别维护三套实现。
3. 新行为追加到共享 queued-event 结算链；renderer 只读取状态数量，不写领域状态。
4. 不建立独立技能 FSM，因为它会绕过命中门、目标策略、状态容量和回滚语义。

## TDD 记录

- [x] RED：`0x80` 有效命中未建立 `0x3F`
- [x] RED：毒手里剑未建立 `0x1F/0x21/0x23`
- [x] RED：毒烟工具被防御准备拒绝
- [x] RED：状态容量不足未证明会话和 RNG 原子回滚
- [x] RED：type 1 对象容量失败会泄漏伤害和 RNG，且多目标后置失败会部分提交
- [x] RED：ROM telemetry 缺少 cursor unit 状态字段
- [x] GREEN：共享 follow-up policy
- [x] GREEN：毒烟保留忍具来源、ID 和 slot
- [x] GREEN：controller 正式目录集成
- [x] GREEN：HUD `ST` 与 mGBA action 11 路线
- [x] GREEN：致死目标 HP/active 遥测与原 ROM 后置 follow-up 顺序
- [x] GREEN：type 1 对象单目标/多目标失败整事务回滚
- [x] REFACTOR：普通、反应和对象到期共用 policy

## 验证边界

专属状态名称、图标、动画和非静音音频不在本里程碑签发范围；完整战斗系统仍未完成。
