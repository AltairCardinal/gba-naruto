## ADDED Requirements

### Requirement: 玩家可见字段必须完成逐字段分类
系统 SHALL 合并 bank schema、UI/runtime reader、现有 CRUD/API 与 generator 输入，枚举所有玩家可见或用户可编辑字段，并把每个底层字段分类为 player-visible、internal、reserved、padding 或 unknown；任何已暴露给用户但仍为 unknown 的字段 MUST 阻止验收。

#### Scenario: Units 与 skills 未命名字段盘点
- **WHEN** 对 units、skills（包括既有 `+2/+3/+9` 缺口）及其他 editor 暴露字段执行盘点
- **THEN** 每个字段 SHALL 有唯一分类、来源位置和当前开放状态，且所有玩家可见 unknown 项被列为待闭合门禁

#### Scenario: 内部或 padding 字节
- **WHEN** 某字节没有玩家可见消费者且证据表明其为 internal、reserved 或 padding
- **THEN** 系统 SHALL 保存该分类与证据并保持不可编辑，无需伪造玩家语义名称

### Requirement: 玩家语义必须由因果证据支持
player-visible 字段 MUST 由代码流、同边界运行时观察或安全单因素 A/B，把具体 ROM 字节/位域与玩家可见数值、文本、资源或行为建立因果关系；仅数值碰巧相等、截图不同或函数可达不构成通过。

#### Scenario: 字段读取链闭合
- **WHEN** 运行时捕获从唯一 ROM record/field 到 consumer 和玩家可见输出的完整读取链
- **THEN** 系统 SHALL 登记字段语义、地址公式、编码和证据制品

#### Scenario: 单字段 A/B 闭合
- **WHEN** variant 只改变目标字段，control/variant 使用相同快照与输入，且可见或行为差异方向符合预期
- **THEN** 系统 SHALL 接受该字段语义，并保存唯一 ROM diff 与两侧结果

#### Scenario: 证据存在歧义
- **WHEN** 多个字段可解释同一变化、输入路线不同或 checkpoint 已越过目标 consumer
- **THEN** 系统 MUST 保持字段未证明和不可编辑，并记录负结果

### Requirement: 语义写回必须可逆且受字段约束
每个开放的 player-visible 字段 SHALL 使用与已证明格式一致的字段级 codec/serializer，验证范围、枚举、位掩码、宽度、端序、指针和 immutable-base 前置值，并保证未修改位和相邻字段不变。

#### Scenario: 合法字段往返
- **WHEN** 将基准记录解码后只修改一个合法玩家字段，再编码并重新解码
- **THEN** 目标字段 SHALL 等于新值，所有其他字段和未使用位 SHALL 与基准一致

#### Scenario: 越界或未知枚举值
- **WHEN** 用户提交无法由已证明字段编码表示的值
- **THEN** serializer MUST 在生成 patch 前拒绝该值并返回字段级错误

### Requirement: 编辑权限与证据状态保持一致
CRUD/API 和构建器 SHALL 共享字段能力清单；字段只有在语义证明、serializer、单字段 ROM diff、集成测试和运行时结果全部通过后才可编辑，任何一项退化时 MUST 自动回到拒绝状态。

#### Scenario: 字段完成全部门槛
- **WHEN** 某 player-visible 字段的证据、serializer、单字段 build 和 mGBA A/B 全部通过
- **THEN** 现有 CRUD SHALL 接受该字段，并在成功构建后提供明确结果反馈

#### Scenario: 字段证据或测试退化
- **WHEN** 对应证据文件缺失、哈希不匹配或相关测试失败
- **THEN** 能力审计 MUST 禁止该字段写入，不能沿用上一次通过状态
