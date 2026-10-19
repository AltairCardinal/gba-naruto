# Butano 防御准备与来袭反应实施计划

**Goal:** 把防御尾部从“只保存动作 ID”升级为可校验、原子扣费、建立一次性反应令牌并由
共享 resolver 在敌方来袭时消费的领域事务。

**Architecture:** 新增无 UI 依赖的 `battle_defense_preparation`。它只接受 ROM 反应优先级
表中已证实的 effect category，复用动作成本、状态槽和 action definition；预览不写会话，
提交在会话副本上扣费并建立 status token。`battle_turn_flow::complete_defense` 在同一副本
中完成“准备 → 单位完成 → condition”，任一步失败都不污染真实会话。来袭仍由
`battle_action_resolver` 的 reaction preprocessor 消费令牌。

## 约束

- 不按技能名称判断防御资格；使用证据绑定的 reaction effect code。
- 不另建关卡专用防御表或 UI 状态。
- 主动术与忍具的身份不能只靠同一个 8 位 ID；准备结果必须保留来源种类和忍具槽。
- 写轮眼 0x10：跳过 miss，只在首个有效 hit 消费，截断后续 hit，目标无伤。
- 火弹 0x19：只在相邻敌方有效 hit 消费，以防御者为 source 反向结算。
- 其他反应 code 在缺少运行时语义前保持明确 unsupported，不能猜测。

### Task 1：防御准备领域事务

- [x] 红测：防御阶段预览写轮眼合法，火遁/影分身类别拒绝，查克拉不足拒绝且会话不变。
- [x] 红测：提交 action 15 原子扣 2 查克拉、建立 0x10/action 15 token，并保留来源类型。
- [x] 实现 `battle_defense_preparation.h` 与明确错误枚举。
- [x] 绿测：主动术与忍具成本、状态容量失败和无防御路径通过。

### Task 2：与回合尾和来袭 resolver 串联

- [x] 红测：`complete_defense` 任一步失败保持 defense-select 会话不变。
- [x] 实现带 action definition 的 `complete_defense` 原子重载。
- [x] 集成测试：玩家准备写轮眼后切敌方，三段攻击首个有效 hit 消费且 HP 不变。
- [x] 集成测试：未命中的 hit 不消费；第二次攻击不再受保护。

### Task 3：反击与边界

- [x] 以 action result 子事件表达火弹反向 source/target，不让表现层扣血。
- [x] 测试相邻限制、一次消费、反击击倒和非相邻不触发。
- [x] 未闭合的 0x04/0x0A/0x09/0x16 保持 unsupported；路线图在 Task 4 同步。

### Task 4：验收

- [x] 全量宿主 C++ 与定向 Python。
- [x] Docker/devkitARM 构建。
- [x] mGBA 场景 41 无防御路线回归；不把它冒充写轮眼可见验收。
- [x] 更新架构、领域证据和路线图。
