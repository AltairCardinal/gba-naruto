## ADDED Requirements

### Requirement: 只接受已闭合的 scenario 41 战后依赖
levels 运行时验证流程 MUST 仅使用 `close-scenario-41-battle-runtime` 已验收并固化的自然 victory/postbattle checkpoint；证据 MUST 记录 checkpoint、基础 ROM 和依赖证据文件的哈希，且不得以战斗入口、瞬时战场或强制胜利状态替代该依赖。

#### Scenario: 依赖满足后开始验证
- **WHEN** `close-scenario-41-battle-runtime` 已提供通过胜利链与自然 postbattle 门槛的 checkpoint 和证据清单
- **THEN** levels 流程可以从该 checkpoint 开始，并在产物中关联其路径与哈希

#### Scenario: 依赖缺失时保持原状态
- **WHEN** victory/postbattle checkpoint 缺失、哈希不匹配或依赖证据尚未验收
- **THEN** 流程 MUST 停止 levels 结论升级，并保持 `code_verified`

### Requirement: 固化自然升级与训练分配前状态
流程 SHALL 在同一条自然 postbattle 运行中证明 Naruto 已达到 level 2，记录可追溯的 EXP 原始值及其战前/战后对照，并同时观测 Naruto template `+0xBA > 0` 与 `0x0200A880 == 3`。这些值 MUST 来自可复验的运行时快照，而非静态推断或写内存伪造。

#### Scenario: 捕获合格的升级边界
- **WHEN** 从已验收 checkpoint 按记录输入完成自然 postbattle 并进入训练分配前界面
- **THEN** 同一证据快照显示 Naruto level 2、EXP 原始值与对照、`0x02022EF0 + 0xBA` 为正数且 `0x0200A880` 等于 3

#### Scenario: 任一状态门槛不满足
- **WHEN** level、EXP 对照、训练点或 `A880` 任一值缺失、来自不同运行或不满足约束
- **THEN** 该运行 MUST 作为未闭合证据保存，且不得用于升级 bank 状态

### Requirement: 证明自然 levels consumer 调用链
透明运行时探针 MUST 在不改变原函数行为的前提下证明自然命中 `0x0808E16E → 0x08093698 → 0x08093070 → 0x080932CA`。证据 SHALL 关联新鲜命中计数、调用顺序、训练 row type 4、有效 levels ID、`0x085459C8 + ID * 12` 记录地址及其 `+6` 原值。

#### Scenario: 完整命中并消费训练点
- **WHEN** 玩家在自然训练分配界面确认一个 type 4 且 levels ID 有效的 row
- **THEN** 探针按顺序记录四个边界命中，训练点恰减 1，对应次槽等级恰加 1，并记录被消费 record 的 ID、地址和 `+6` 值

#### Scenario: 拒绝陈旧或不完整命中
- **WHEN** magic/计数不是本次 checkpoint 恢复后的新鲜值、调用顺序不完整、row type 不为 4 或 ID 越界
- **THEN** 流程 MUST 将该样本判为无效，不得据此声称 consumer 已获运行时验证

### Requirement: 对自然命中 record 的加六字段执行单因素 A/B
流程 MUST 从不可变基础 ROM 构建 control 与 variant，且两者除自然命中 levels record 的 `+6` 字段外逐字节一致。variant SHALL 只把该字段从 `n` 改为 `n + 1`；两组 MUST 加载同一 checkpoint、执行同一输入和采样窗口，并分别保留 ROM 差异清单与运行时结果。

#### Scenario: 单因素结果符合消费公式
- **WHEN** control 与 variant 都自然命中同一 ID、同一 row，并到达 `0x080932CA`
- **THEN** 输出差异 MUST 与 `base_a + per_level_a * (stored_level - 1)` 对 `+6` 单步变化的预测一致，同时训练点消耗和次槽选择等非目标条件保持一致

#### Scenario: A/B 控制条件受到污染
- **WHEN** 两个 ROM 存在目标 `+6` 之外的字节差异，或 checkpoint、输入、命中 ID、row、采样窗口不一致
- **THEN** A/B MUST 判为无效并重新执行，不得升级 `levels`

### Requirement: 证据闭合后才升级 levels 状态
流程 MUST 仅在依赖 checkpoint、自然升级状态、完整 consumer 调用链和单因素 A/B 全部通过后，将 `sequel/content/levels/bank.json` 的 verification 更新为 `runtime_verified`，并在同一工作周期同步紧凑证据、调查笔记、逆向交接和路线图。该升级 SHALL 不改变其他 bank 的验证状态。

#### Scenario: 全部门槛通过
- **WHEN** 每项门槛都有可复验制品且自动审计确认 levels bank 与文档一致
- **THEN** `levels` 更新为 `runtime_verified`，路线图重新计算并记录新的 verification 分布

#### Scenario: 部分门槛失败
- **WHEN** 任一门槛失败、无法复现或只有静态代码证据
- **THEN** `levels` MUST 保持 `code_verified`，负结果和下一步 MUST 写入持久项目文件，其他 bank 保持不变
