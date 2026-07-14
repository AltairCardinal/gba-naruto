## ADDED Requirements

### Requirement: Legacy CRUD 字段必须有完整决策清单
系统 SHALL 枚举现有 legacy web CRUD 的每个表和字段，并为其记录对应 `rom_*` mirror/bank 记录身份、ROM offset 公式、编码宽度、serializer、语义证据和 `editable` 或 `denied` 决定；未分类字段 MUST 令边界审计失败。

#### Scenario: CRUD 字段完整盘点
- **WHEN** 审计数据库 schema、现有 CRUD/API、mirror 表和 patch generator
- **THEN** 每个可输入字段 SHALL 恰好对应一条能力决定，且不存在未分类、重复授权或悬空 mirror 映射

### Requirement: 真实 ROM 写入采用显式允许列表
系统 MUST 仅允许同时具备唯一记录身份、合法索引和边界、immutable-base `before` 字节、完整字段 serializer、范围/指针/长度检查、跨生成器冲突检查及可报警测试的字段产生 game-effective patch。

#### Scenario: 已证明字段生成 patch
- **WHEN** 用户通过现有 CRUD 修改一个 allowlisted 字段，且值通过领域与编码校验
- **THEN** 构建器 SHALL 只在声明的 ROM 字段范围生成带 `before_hex`/`after_hex` 的 patch，并通过 immutable-base 与冲突门禁

#### Scenario: Base ROM 前置字节不匹配
- **WHEN** 目标 ROM 字节与能力清单记录的 immutable-base 前置值不一致
- **THEN** 构建 MUST 失败并报告记录、字段与 offset，不得继续写入

#### Scenario: 跨生成器重叠
- **WHEN** 两个 generator 对同一 ROM 区域生成不一致字节
- **THEN** 冲突门禁 MUST 拒绝构建，即使其中一个写入来自 legacy CRUD

### Requirement: 未证明入口默认拒绝且不携带写入载荷
任何缺少记录身份、字段语义、serializer 或安全测试的 legacy 字段 MUST 保持只读或返回诊断；诊断不得包含可执行的 `offset`、`after_hex` 或 bytes patch。

#### Scenario: 未映射 legacy 字段被修改
- **WHEN** CRUD 请求尝试修改未完成能力证明的 legacy 字段
- **THEN** 系统 SHALL 返回明确的不可编辑错误或无写入载荷的诊断，并保持 ROM 输出哈希不变

#### Scenario: 绕过 API 直接污染数据库
- **WHEN** 未授权字段通过旧数据库行进入正式 build
- **THEN** generator MUST 拒绝该字段或产生无写入载荷的诊断，不能因数据库中存在值而恢复旧模板/合成写入

### Requirement: CRUD 到正式构建必须有破坏即失败的集成测试
系统 SHALL 对每个恢复写入的字段族提供现有 CRUD/API→隔离 DB snapshot→正式 generator→patch safety gate→ROM 的集成测试，并证明无关 ROM 字节及全局构建产物不被修改。

#### Scenario: 单字段隔离构建
- **WHEN** 在完整 mirror DB 中只修改一个 allowlisted 字段并运行正式 build
- **THEN** ROM diff SHALL 只包含该字段声明的字节范围，输出报告与 ROM 哈希一致，且真实 editor DB/全局 build 哈希保持不变

#### Scenario: Wiring 或 serializer 被破坏
- **WHEN** 测试中的 CRUD 列映射、mirror identity、offset 或 serializer 任一被故意置错
- **THEN** 至少一个对应集成测试 MUST 失败，而不是静默跳过或生成假绿报告
