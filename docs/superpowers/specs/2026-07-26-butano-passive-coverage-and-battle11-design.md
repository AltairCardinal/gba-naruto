# Butano 被动覆盖审计与 battle 11 双属性被动设计

## 目标

把“45 条被动成长定义”与“原 ROM 中实际存在的战斗消费者”分开建模，并补齐
目前证据已经闭合、但 Butano 仍明确留空的 battle 11 专属 target `0x20`。

本轮不根据名称或成长数值猜测 `0x01–0x0B、0x0D–0x13` 的效果。本文当时把
`0x1A–0x1C` 归为表现配置；该判断已被后续完整消费者数据流纠正为地形类别逐路径预算，
当前设计见主架构第 28 节和 `notes/battle-terrain-passive-runtime-20260726.md`。

## ROM 证据边界

- `0x0806DDA4..0x0806DE15`：24 个 secondary slot 的统一查询器；
- `0x085459C8`：45×12 字节成长定义；
- 15 个直接调用只请求 `0x0C、0x14–0x20`；
- `0x0806DF88..0x0806E1AF` 按 `0x1D → 0x1E → 0x1F → 0x20`
  查询，四族共享 `unit+0xBE` latch；
- `0x20` 只在 battle ID 11 生效，依次建立：
  - status `0x1E`，duration 0，value 为 `value_a`；
  - status `0x22`，duration 0，value 为 `value_b`；
  - 然后设置 latch 并重算属性。

`duration 0` 按现有状态生命周期表示不随 side-end 自然递减。两条状态必须原子提交：
任一写入失败时单位与 latch 均保持原样。

## 领域设计

### 覆盖矩阵

新增可复现分析器，把每个 passive ID 绑定到：

- target type 和成长参数；
- 原内容目录中引用该定义的角色模板；
- ROM 直接查询调用点；
- 当前 Butano 消费状态；
- 证据状态：已实现、原 ROM 无直接消费者、表现链待闭合或机械链已实现。

矩阵只陈述可验证事实，不从日文名或数值反推玩法。

### battle ID 所有权

`battle_session` 保存 encounter 的 battle ID。场景装载器从
`battle_scenario_definition::battle_id` 写入候选 session，仍保持现有原子装载语义。
side-start 被动系统从 session 传入 battle ID，不读取全局场景变量。

### `0x20` 事件

新增中性的 `battle_11_dual_boost` 事件 kind。它只表示已证实的机械结果，不声称
未校字的可见名称。事件公开两条状态的 code/value/duration，表现队列至少能显示该被动
已触发以及两项数值；后续得到原作演出证据后可替换视觉，不改变领域事件。

## 用户可见行为

- battle 11 中，携带并学会 passive ID 35 的活动单位在所属阵营回合开始时触发一次；
- 单位攻击与敏捷按两条永久状态重算；
- 同一阈值周期不会重复触发；非 battle 11 不触发；
- 若状态槽不足，整个效果失败且不产生部分增益或伪事件；
- 其他 44 项的行为只按已证实消费者执行，未知项不会显示成已生效。

## 验收

1. 覆盖分析器产出 45 行且精确区分 17 条有 ROM 直接消费者与 28 条无直接消费者。
2. battle 11 的 passive 35 按 `value_a/value_b` 建立 `0x1E/0x22`，设置 latch 并重算。
3. 同一单位在其他 battle ID 不变化。
4. 第二条状态写入失败时第一条也不残留。
5. 场景装载后 session 的 battle ID 与生成场景一致。
6. 主机测试、ARM 构建和受守卫 mGBA 路线均通过。
