## ADDED Requirements

### Requirement: 执行顺序与范围边界
系统 MUST 在独立的 `levels` change 完成后才开始本 change 的实现与最终验收，并且 SHALL 只处理 `battle-encounters`、`cutscene-scripts`、`data-table-b`、`map-events`、`map-sprites`、`palettes`、`resource-pointers`、`sappy-engine` 和 `tile-assets` 九个 bank。

#### Scenario: levels 尚未完成
- **WHEN** `levels` change 尚未完成或其运行时结论尚未同步到主线
- **THEN** 本 change MUST 保持未完成状态，且不得用本 change 的证据替代 levels 验证

#### Scenario: 排除收尾事项
- **WHEN** 执行者发现 P2 audio cue、legacy web、ROM mirror 或续作编辑器事项
- **THEN** 这些事项 MUST 留在对应后续 change，且不得混入本 change 的实现或验收

### Requirement: 统一运行时证据门禁
每个目标 bank SHALL 以自然 selector 或自然游戏事件为起点，证明 selector、真实 ROM 表项和可见、音频或行为结果之间的同一条数据链。只有三项证据均成立时，bank 才 MUST 标记为 `runtime_verified`；历史 slug 或旧误识别地址 MUST NOT 作为语义证据。

#### Scenario: 三重证据闭合
- **WHEN** 自然事件产生 selector，探针证明它选择真实 ROM 目标，且受控对照产生与字段语义一致的结果差异
- **THEN** 证据 MUST 记录 selector、ROM 地址/内容、消费者边界和结果差异，并 MAY 将该 bank 升为 `runtime_verified`

#### Scenario: 只有静态消费者证据
- **WHEN** 只能证明 Thumb 消费者或引用链，不能证明自然 selector 和结果链
- **THEN** bank MUST 保持 `code_verified`，且不得以“未发现异常”替代运行时证据

#### Scenario: 动态 A/B 技术上不合理
- **WHEN** 受控 A/B 会修改可执行代码、函数指针或造成无法接受的安全风险，或消费者没有可观察的独立输出
- **THEN** 系统 MUST 放弃危险修改并改用只读断点、自然命令链或前后状态因果证据；若替代证据仍不足，bank 保持 `code_verified` 且本 change MUST 保持未完成

### Requirement: 快照复用与来源可追溯
运行时实验 SHALL 使用 mGBA 保存状态固化由自然输入到达的稳定边界，优先从最近的有效快照继续，避免重复执行无关导航。每个接受的快照 MUST 记录 ROM 哈希、模拟器版本、父状态或自然输入来源、保存边界和适用范围。

#### Scenario: 已有适用快照
- **WHEN** 后续探针需要的起始状态可由已验证快照准确恢复
- **THEN** 探针 SHALL 复用该快照，并 MUST 验证关键内存状态后再采集证据

#### Scenario: 快照位于目标调用之后
- **WHEN** 快照恢复点已经越过待验证 selector 或消费者调用
- **THEN** 系统 MUST 将其判定为不适用，并从更早的自然边界建立新快照，不得把全零探针结果解释为调用未发生

#### Scenario: 快照来源不明
- **WHEN** 无法证明快照对应 ROM、自然输入路线或保存边界
- **THEN** 该快照 MUST NOT 用作最终证据

### Requirement: 运行时资源安全
所有 mGBA、浏览器兼容探针和高开销分析 SHALL 在项目资源守卫下运行，并定期记录项目进程树内存。异常处理 MUST 精确限制在本项目启动并登记的 PID 树，MUST NOT 批量终止系统中的 Python、Chrome 或模拟器进程。

#### Scenario: 内存正常
- **WHEN** 项目进程树内存低于配置上限且仍在产生进展
- **THEN** 守卫 SHALL 允许实验继续，并记录峰值内存与退出状态

#### Scenario: 项目进程树异常
- **WHEN** 项目进程树超过内存上限、空闲超时或墙钟超时
- **THEN** 守卫 MUST 只终止该次登记的项目进程树、保存诊断摘要并释放共享锁

#### Scenario: 发现非项目高占用进程
- **WHEN** 系统内存检查发现未由本次实验登记的高占用进程
- **THEN** 本 change MUST NOT 终止该进程，并 SHALL 将其排除在本项目异常处置之外

### Requirement: scenario 41 复用闭合战斗资源
`data-table-b` 与 `resource-pointers` SHALL 优先复用同一次 scenario 41 有效攻击或技能执行及其快照，分别捕获战斗消息和嵌套资源选择；如果同一事件无法触发其中一项，证据 MUST 明确分离两条路线。

#### Scenario: data-table-b 战斗消息闭环
- **WHEN** scenario 41 中的有效攻击或技能自然产生 battle/effect message ID
- **THEN** 探针 MUST 证明 ID 以四字节步长选择 `0x085A2034` 的 79 项文本指针之一、消费者获得相同 NUL 结尾文本，并由受控文本对照产生预期可见消息差异

#### Scenario: resource-pointers 资源闭环
- **WHEN** scenario 41 的有效动作自然选择嵌套资源 descriptor
- **THEN** 探针 MUST 证明 selector 以十六字节步长选择 `0x08596F0C` 的五项 descriptor 之一、四个资源字段进入已识别消费者，并将目标与具体可见资源输出对应

#### Scenario: 无效战斗路径
- **WHEN** 路线只触发空目标提示、入场动画或尚未进入有效动作消费者
- **THEN** 该结果 MUST 记为负证据，且 MUST NOT 用于升级 `data-table-b` 或 `resource-pointers`

### Requirement: 故事与过场视觉资源闭环
`battle-encounters` 与 `cutscene-scripts` SHALL 按其纠正后的视觉资源语义验证，不得解释为敌方编成或剧情脚本文本。

#### Scenario: battle-encounters 历史 slug 的真实视觉记录
- **WHEN** 自然 story opcode 选择 `0x0854229C` 的 24 项视觉 descriptor 之一
- **THEN** 探针 MUST 捕获 record index、三条 LZ77 源指针、config ID、解压目标和对应画面，并通过安全的单因素对照证明预期视觉差异

#### Scenario: cutscene-scripts 历史 slug 的真实资源对
- **WHEN** 自然过场或战斗 UI 选择 `0x0853DF70` 与相邻表中的 ID 0..3
- **THEN** 探针 MUST 捕获 gfx/palette 解压、对应 sprite pair 安装和可见结果，并证明两组表使用同一自然 ID

### Requirement: 地图回调与精灵资源闭环
`map-events` 和 `map-sprites` SHALL 从自然地图状态捕获运行时 selector，并分别证明回调分派和精灵定义/动画资源安装的真实目标。

#### Scenario: map-events 回调分派
- **WHEN** 自然地图行为令 `sb+0x770` 的运行时字节选择 `0x0853E698` 的 handler pair
- **THEN** 探针 MUST 证明 primary 与 secondary 地址由同一 `index << 3` 计算，非零 callback 进入间接调用边界，并把命中目标与随后行为对应

#### Scenario: map-sprites 资源安装
- **WHEN** 自然地图加载或实体出现选择 `0x0853F140` 的 43 项 definition/animation pair 之一
- **THEN** 探针 MUST 捕获 ID、两条 ROM 指针、安装/遍历目标及可见精灵结果，并通过安全对照证明预期的图像或动画差异

### Requirement: 动作参数闭环
`palettes` SHALL 按纠正后的 15 项、每项 10 字节的 motion/effect 参数语义验证，MUST NOT 再以调色板 RGB555 上传为验收标准。

#### Scenario: 自然效果选择参数记录
- **WHEN** 自然动作或效果选择 `0x0853EE98` 的记录
- **THEN** 探针 MUST 捕获 selector、十字节记录地址、消费者读取字段和对应运动/效果行为

#### Scenario: 单因素参数对照
- **WHEN** 已识别字段可在不破坏控制流的情况下安全改变
- **THEN** 对照 ROM MUST 只改变该字段，并产生方向、时序、幅度或终止行为上的预期差异

### Requirement: Sappy 命令处理闭环
`sappy-engine` SHALL 通过自然音频事件验证实际命令处理链，而不是修改引擎代码。证据 MUST 连接命令字节、命中 handler、声道状态变化和可听或可测音频结果。

#### Scenario: 自然命令被处理
- **WHEN** 游戏自然播放已识别音乐或音效并产生 Sappy 命令
- **THEN** 探针 MUST 捕获命令字节、handler PC、处理前后声道状态和对应音频结果

#### Scenario: 禁止代码区 A/B
- **WHEN** 唯一可想象的对照需要直接修改 Sappy 可执行代码或调度表
- **THEN** 系统 MUST 放弃该对照，保留代码完整性，并根据自然命令链的证据强度记录最终等级和限制

### Requirement: 战斗视觉 descriptor 闭环
`tile-assets` SHALL 按 `0x085A320C` 的 79 项、每项 `0x44` 字节 battle/effect descriptor 验证，证明自然 ID、LZ77/palette 源字段、目标内存和屏幕结果的一致性。

#### Scenario: 自然战斗效果加载
- **WHEN** 有效攻击、技能或战斗效果自然选择 descriptor ID
- **THEN** 探针 MUST 证明消费者按 `(id - 1) * 0x44` 定位记录，并捕获 `+0x0C`、`+0x10` LZ77 流、`+0x14` palette copy 与实际 VRAM/palette 目标

#### Scenario: 安全图块对照
- **WHEN** 可对单一图块或 palette 字段做有界修改且不会改变控制流
- **THEN** 对照结果 MUST 只在预期战斗视觉位置产生可解释差异，并保留基线与变体截图或帧摘要

### Requirement: 测试驱动与可复现证据
新增或修改任何探针、解析器或验证逻辑 MUST 遵循红—绿—重构流程，并 SHALL 同时覆盖纯逻辑单元测试和相关模拟器集成边界。每项结论 MUST 由仓库内的脚本、紧凑证据和文档复现，不得依赖聊天记录。

#### Scenario: 新增探针功能
- **WHEN** 实现新的 hook、selector 解码或证据判定
- **THEN** 必须先运行因正确原因失败的测试，再以最小实现通过测试，重构后重跑相关单元与集成测试

#### Scenario: 证据不可复现
- **WHEN** 结论缺少 ROM 哈希、输入、地址、快照来源、输出或复现命令中的任一关键项
- **THEN** 该结论 MUST 保持未验收，且不得更新 bank 的验证等级

### Requirement: 阶段性同步与最终审计
每个完成的 bank 或共享运行时事件 SHALL 在同一工作周期更新 bank 元数据、稳定证据文档、`docs/sequel-roadmap.md` 和完成度审计。阶段性成果 MUST 经过审查与验证后独立提交并推送远端，最终验收 MUST 逐项说明九个 bank 的证据等级和未决限制。

#### Scenario: 单项 bank 闭环
- **WHEN** 某个 bank 满足运行时门禁，或严格负证据证明它应作为非独立结构改为 `disproved`
- **THEN** 同一阶段提交 MUST 包含对应证据、元数据、路线图和审计更新，并在推送前通过范围匹配的测试

#### Scenario: 共享事件闭合多个 bank
- **WHEN** scenario 41 或其他自然事件同时为多个 bank 提供独立可判定的证据
- **THEN** 系统 MAY 在一个阶段提交中同步这些结论，但 MUST 为每个 bank 分别列出 selector、ROM 目标、结果和判定依据

#### Scenario: change 最终验收
- **WHEN** 本 change 准备完成
- **THEN** 审计 MUST 覆盖全部九个 bank，且每项均为 `runtime_verified` 或有严格身份负证据的 `disproved`；任何缺失、间接、不确定或仍为 `code_verified` 的证据 MUST 视为未完成
