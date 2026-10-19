## Context

当前 `tools/audit_re_completion.py` 已证明 32/32 bank 的元数据、条目、文档覆盖与基准 ROM fidelity，其中 23 个是有效 bank、9 个是 `disproved` tombstone；这项审计明确不覆盖完整字段语义、真实写回或端到端运行时。前三个顺序 change 负责闭合 scenario 41、`levels` 与九个剩余 `code_verified` bank，本 change 只处理其后的 P2 缺口并执行最终审计。

P2 横跨四类现有资产：80 个有效 audio cue 的语义证据、legacy editor 表与 `rom_*` mirror、玩家可见字段及 serializer、最终文档和自动化门禁。设计必须保留 immutable base ROM、已有 patch conflict gate、mGBA 快照复放与 `run_guarded.py` 的 owned-process-tree 资源边界，且不能用调查标签伪装官方名称。

## Goals / Non-Goals

**Goals:**

- 让 72 个当前 `unknown` audio cue 都获得可重放、可定位来源的玩家语义，并保留证据等级与 `official_name_known` 边界。
- 为每个 legacy CRUD 字段建立“禁写或安全写入”的显式决定，使任意允许写入都能定位真实 ROM 记录并通过字段级 serializer 和 patch 安全门禁。
- 对玩家可见字段建立完整分类；只有语义和安全写回均闭合的字段才对 editor 开放。
- 让最终 completion audit 直接核验 32 个结构和所有完成门槛，并以 fail-closed 方式控制 100% 声明。
- 复用已有快照和运行时状态，降低重复导航开销；资源异常时只终止守卫拥有的进程树。

**Non-Goals:**

- 不重复前三个 change 的具体运行时调查。
- 不开发新的网页编辑器产品能力、UI 信息架构或协作功能。
- 不要求在缺少官方资料时伪造官方曲名/音效名，也不为内部 padding 或尚不可见字段强行赋予玩家语义。

## Decisions

### 1. 先验证依赖，再允许 P2 最终审计

本 change 的执行入口先读取前三个 change 的验证报告、持久证据和当前 bank 状态。最终门禁要求所有有效 bank 均达到项目规定的运行时证据，所有已证伪别名保持空 tombstone 和禁写；任何依赖仍为未完成、证据文件缺失或状态与证据不一致时，P2 可以继续采集独立证据，但不能生成通过的最终结论。

选择这种显式依赖门禁，而不是把前三个 change 的任务复制到本 change，是为了保持问题边界和避免同一运行时结论出现两套责任来源。

### 2. 用机器可读证据账本闭合 audio cue，不直接覆盖调查历史

扩展现有 audio cue 提取结果，使每个有效 cue 至少包含：ID、稳定语义标识、玩家事件描述、证据等级、source addresses、输入/快照标识、复放结果、`official_name_known`。72 个当前 `unknown` 必须分别通过下列任一门槛后才能改名：

- 两个相互独立但语义一致的自然事件实例；或
- 一个只改变目标事件的单因素 A/B，且捕获 wrapper ID/调用 PC、状态与预期可见或行为结果。

既有 A/B 级候选也需按相同规则复核；没有官方来源时 `official_name_known=false`，稳定语义名仍是项目调查标签。相比按听感批量命名，这种账本能让审计器拒绝无来源名称，并允许后续证据提高等级而不篡改历史记录。

### 3. 以字段能力清单控制 CRUD 与 ROM mirror，默认拒绝

为当前 legacy CRUD schema 与 `rom_*` mirror 建立逐字段映射。每个字段记录：editor 表/列、bank/record identity、ROM offset 公式、宽度/编码、immutable-base `before` 来源、serializer、约束、冲突域、语义证据与允许状态。

只有同时满足以下条件才标记为可编辑：

1. 记录身份、索引和 ROM 边界唯一；
2. 字段语义由代码流、运行时观察或安全单因素 A/B 支持；
3. serializer 对完整字段宽度执行可逆编码并验证 base bytes；
4. 相关范围、指针、长度和跨生成器冲突检查存在；
5. 单元测试和正式 DB→build 集成测试能在 wiring、offset 或 serializer 破坏时失败。

不满足任一条件的字段维持只读或返回不含 `offset/after_hex` 的诊断。采用集中能力清单而不是在各 generator 中继续添加隐式例外，可使 API、后端和构建器共享同一授权边界。

### 4. 玩家可见字段按“证明、写回、开放”三阶段推进

从现有 bank schema、runtime template/UI reader 和 editor CRUD 列表生成字段盘点，优先覆盖 units、skills 以及其他已暴露给用户但仍未命名的字段。每个字段必须依次完成：

1. **证明**：ROM 字节/位域与玩家可见数值、文本、资源或行为建立因果关系；
2. **写回**：实现字段级 codec/serializer，并以单字段 diff 和相同快照路线验证预期变化；
3. **开放**：CRUD/API 才可接收该字段，错误、越界或证据不足时明确拒绝。

无法证明的 bytes 明确分类为 internal、reserved、padding 或 unknown，并保持不可编辑。这样既不漏掉用户已能编辑的危险列，也不把“100%”错误解释为必须猜完每个未使用字节。

### 5. 最终 completion audit 使用证据矩阵并 fail closed

在现有 32-bank 审计之上增加独立的机器可读完成矩阵。每个结构至少引用：身份/边界证据、提取器或等价验证、字段语义覆盖、可编辑字段写回覆盖、相关单元/集成测试和模拟器制品。全局门禁另外核验：

- 23 个有效 bank 与 9 个 `disproved` tombstone 的当前清单（若权威结构清单经证据变更，则计数和原因必须同步更新）；
- 不存在剩余 `code_verified`/`static_verified` 的有效 bank；
- audio cue、字段能力清单和 legacy CRUD 映射没有未决玩家可见项；
- 完整 build、Python/Node/backend 单元与集成测试、受守卫 mGBA 验收全部通过；
- 产物哈希、命令、时间和输入版本可复核；
- `docs/final-completion-report.md` 的数字和结论与机器报告一致。

审计输出明确区分 `pass`、`fail` 与 `not_proven`。只有所有 required gate 为 `pass` 才生成 `completion_claim_allowed=true`；任何缺失证据都视为未完成，而不是跳过。

### 6. 快照和资源安全是所有运行时证据的共同执行层

运行时实验从距离目标事件最近、来源可追溯的 mGBA 保存状态开始，并在结果中记录 ROM/状态哈希和输入序列。重型静态扫描、模拟器和浏览器运行继续通过共享 heavy lock、准入检查、wall/idle timeout 与 owned-tree RSS 上限；异常清理只能针对该 guard 创建的 Job Object/process group。

不采用按进程名清理或全局 Python/Chrome 终止，因为这会影响本机其他项目，也不能证明异常进程属于本次实验。

## Risks / Trade-offs

- [部分 cue 难以构造两个自然实例] → 优先用调用点分组和已有快照建立单因素 A/B；证据不足时保持门禁失败，不降低命名标准。
- [“玩家可见”边界遗漏隐蔽字段] → 合并 bank schema、UI/runtime reader、CRUD/API 和 generator 四个来源生成盘点，并对未分类字段令审计失败。
- [集中能力清单与 generator 漂移] → 让 generator/API 从同一清单派生授权，并增加故意破坏 wiring 时会失败的集成测试。
- [最终全量验证耗时或内存过高] → 复用 mGBA 快照、串行执行 heavy 作业并保存阶段报告；不得并发绕过共享锁。
- [历史文档数字与当前状态冲突] → 机器报告为数值来源，文档一致性测试比较结构清单、证据分布和完成布尔值。
- [严格门禁延后 100% 声明] → 这是有意取舍；`not_proven` 必须保守地视为未完成。

## Migration Plan

1. 验证前三个 change 的完成制品与当前基线，冻结本 change 的输入清单。
2. 扩展 audio cue 证据账本和复放工具，按可独立验收的 cue 批次闭合并提交。
3. 建立 legacy CRUD/ROM mirror 字段能力清单，先锁定所有未证明入口，再逐字段以 TDD 恢复安全写回。
4. 完成玩家可见字段盘点、语义证据、serializer 和正式 DB→build→mGBA A/B。
5. 扩展 completion audit 和文档一致性检查，运行全量测试、构建及模拟器验收。
6. 仅在机器报告全绿后更新最终报告、路线图和完成声明；任一步失败则保留非完成状态和失败清单。

回滚以字段能力清单的 deny 状态为安全基线：若新 serializer 或集成验证失败，撤销该字段的可编辑授权但保留调查证据和诊断，不恢复旧合成/模板写入。

## Open Questions

- 暂无需要在 open 阶段由用户裁决的问题；具体 cue 的事件路线和未命名字段的消费点属于实施期调查项，证据不足时按 fail-closed 规则处理。
