## ADDED Requirements

### Requirement: 每个有效 cue 都有机器可读语义记录
系统 SHALL 为 audio bank 中每个有效 cue 保存唯一记录，至少包含 cue ID、稳定语义标识、玩家事件描述、证据等级、source addresses、复放制品、输入/快照标识与 `official_name_known`；当前基线的 80 个有效 cue 不得遗漏或重复。

#### Scenario: 完整枚举有效 cue
- **WHEN** 对 audio bank 和语义账本执行覆盖审计
- **THEN** 账本 SHALL 与有效 cue ID 集合完全相等，并报告 80/80、零缺失和零重复

#### Scenario: 语义记录缺少来源
- **WHEN** 任一 cue 记录缺少 source address、可复放制品或事件描述
- **THEN** 审计 MUST 将该 cue 标记为 `not_proven`，且不得计入语义完成数

### Requirement: 语义命名必须达到可复现证据门槛
系统 MUST 只在两个相互独立且语义一致的自然事件实例，或一个隔离目标事件的单因素 A/B，捕获 cue ID、调用 PC、运行时状态和预期结果后，才把 `unknown` 替换为稳定玩家语义标识。

#### Scenario: 两个自然实例一致
- **WHEN** 同一 cue 在两个独立自然输入路线中命中，且两次玩家事件语义、调用来源和观测结果一致
- **THEN** 系统 SHALL 允许登记该玩家语义，并引用两个实例的持久证据

#### Scenario: 单因素 A/B 闭合
- **WHEN** control 与 variant 仅改变目标玩家事件，并捕获同一边界上的 cue/PC/状态差异和预期结果
- **THEN** 系统 SHALL 允许以该 A/B 为语义证据，并记录 ROM、快照、输入与结果哈希

#### Scenario: 仅凭听感或结构家族猜名
- **WHEN** 候选名称只有听感、波形、player/track 家族、截图或无事件语境的调用点支持
- **THEN** 系统 MUST 保持该 cue 为 `unknown` 或未完成候选，并阻止语义闭合通过

### Requirement: 调查语义不得冒充官方名称
系统 SHALL 区分项目调查语义与官方曲名/音效名；没有可引用的官方来源时 MUST 保存 `official_name_known=false`，且用户可见输出不得把调查标签称为官方名称。

#### Scenario: 无官方来源的稳定语义
- **WHEN** cue 已满足玩家事件语义门槛但没有官方命名来源
- **THEN** 系统 SHALL 保留稳定调查语义、证据等级和 `official_name_known=false`

### Requirement: 语义闭合必须消除全部有效 cue 的未知状态
在本 capability 验收时，系统 SHALL 证明现有 8 个候选和 72 个 `unknown` 均达到统一证据门槛；任一有效 cue 仍为 `unknown`、证据冲突或不可复放时，P2 audio 门禁 MUST 失败。

#### Scenario: 仍有一个 unknown cue
- **WHEN** 覆盖审计发现任一有效 cue 的稳定语义为空、为 `unknown` 或证据未达门槛
- **THEN** audio semantic closure SHALL 返回失败并列出具体 cue ID 和缺失证据
