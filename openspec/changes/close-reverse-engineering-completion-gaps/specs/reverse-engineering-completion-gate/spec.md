## ADDED Requirements

### Requirement: 最终审计必须验证前三个 change 的依赖
最终 completion audit SHALL 读取 `close-scenario-41-battle-runtime`、`verify-levels-runtime` 和 `upgrade-remaining-runtime-banks` 的验证结果及持久证据；任一依赖未验证、证据缺失或当前状态不一致时 MUST 阻止完成声明。

#### Scenario: 三个依赖均有效
- **WHEN** 三个前置 change 的验证报告、快照/证据哈希和当前 bank 状态均可复核且一致
- **THEN** 系统 SHALL 允许继续执行 P2 最终门禁

#### Scenario: 一个依赖未完成
- **WHEN** 任一前置 change 仍 active/failed、缺少验证报告或证据与当前文件不一致
- **THEN** completion audit MUST 返回 `not_proven` 并列出具体依赖，不得恢复 100% 声明

### Requirement: 32 个结构必须有逐项完成矩阵
系统 SHALL 为权威清单中的 32 个结构逐项核验无别名冲突的身份/边界、可复现提取器或等价机器验证、字段语义、编辑字段安全写回、对应测试和运行时证据。当前基线预期为 23 个有效 `runtime_verified` bank 与 9 个空且禁写的 `disproved` tombstone，不得剩余有效 `code_verified` 或 `static_verified` bank。

#### Scenario: 结构矩阵全部通过
- **WHEN** 32 行均引用存在且哈希一致的证据，23 个有效 bank 达到 runtime 门槛，9 个 tombstone 保持负证据、空 entries 和禁写
- **THEN** 结构门禁 SHALL 报告 32/32，并分别报告 23 runtime / 9 disproved

#### Scenario: 只有元数据与 ROM fidelity 通过
- **WHEN** `audit_re_completion.py` 的旧式 32/32 元数据/字节检查通过，但任一结构缺少运行时语义、提取验证或安全写回证据
- **THEN** 最终结构门禁 MUST 失败，且不得把旧式 32/32 输出解释为逆向工程 100%

#### Scenario: 权威结构身份经证据变更
- **WHEN** 新证据证明某有效 bank 是别名/tombstone，或某 tombstone 实为独立结构
- **THEN** 系统 MUST 先同步权威清单、提取器、负证据和计数，并重新执行全部 32 行审计，不能静默沿用 23/9 分布

### Requirement: 全部语义与安全写回门禁必须共同通过
completion audit MUST 聚合 audio cue semantic closure、legacy ROM mirror boundary 与 player-visible field writeback 的机器报告；任一有效 cue、玩家可见字段或 CRUD 输入仍为 unknown、未分类、可绕过或不可安全写回时，整体状态 SHALL 为未完成。

#### Scenario: P2 子门禁全绿
- **WHEN** audio 80/80、CRUD 字段映射 100%、玩家可见字段分类/语义/写回覆盖均通过且无未决项
- **THEN** 系统 SHALL 将 P2 semantic/writeback gate 标记为通过

#### Scenario: 存在未分类或未证明项
- **WHEN** 任一报告包含 `unknown`、`unclassified`、`not_proven`、不安全写入或证据冲突
- **THEN** 整体 completion 状态 MUST 为失败，并输出可执行的缺口清单

### Requirement: 完整构建、测试和模拟器验收必须可复核
系统 SHALL 在同一已记录 commit 和基准 ROM 上运行格式检查、相关及全量 Python/Node/backend 单元测试、CRUD/正式构建集成测试、完整 ROM build、completion audit 与受守卫 mGBA 验收，并保存命令、退出码、输入/输出哈希和资源摘要。

#### Scenario: 全量验证成功
- **WHEN** 所有规定命令在同一 commit 上退出 0，构建报告与 ROM 哈希一致，mGBA 从可追溯快照复放并满足验收断言
- **THEN** verification gate SHALL 通过并引用持久报告，而不是只记录聊天结论

#### Scenario: 集成点发生 silent skip
- **WHEN** 测试因 DB、ROM、mGBA、OCR 或路径缺失而跳过原本 required 的集成验收
- **THEN** 全量验证 MUST 将其视为未证明或失败，不能把较窄子集的绿色结果提升为整体通过

### Requirement: 运行时工作必须复用快照并受资源守卫
所有可复放运行时证据 SHALL 优先从距离目标事件最近且来源可追溯的 mGBA 保存状态开始，记录 ROM/快照哈希和输入序列；所有重任务 MUST 使用共享锁、内存准入、owned-tree RSS/wall/idle 限制并只清理本次守卫拥有的进程树。

#### Scenario: 从稳定快照复放
- **WHEN** 重复验证同一玩家事件或字段 A/B
- **THEN** 两侧 SHALL 加载同一已追踪快照而非重复完整导航，并在证据中记录其哈希与来源

#### Scenario: 项目任务发生内存异常
- **WHEN** 守卫检测本次拥有的进程树超过 RSS/timeout 门槛
- **THEN** 守卫 SHALL 只终止该 Job Object/process group、写入原因与峰值摘要，且不得按名称批量终止 Python、Chrome 或其他全局进程

### Requirement: 阶段成果必须持久化并以本地 commit 可追溯
每个可独立验收的证据批次 SHALL 在相关测试通过后同步 bank/notes/docs/roadmap，检查变更范围，再创建范围明确的本地 commit 并记录 commit hash；不得把无关用户改动或临时模拟器产物混入提交。

#### Scenario: 一个 P2 批次通过
- **WHEN** 一组 cue、字段或 CRUD 边界达到其独立验收门槛
- **THEN** 仓库 SHALL 包含对应持久证据、测试和文档更新，且记录的本地 commit hash 可定位到该阶段提交

### Requirement: 100% 声明和最终报告必须 fail closed
系统 MUST 仅在全部 required gate 为 `pass` 时设置 `completion_claim_allowed=true`、更新 `docs/final-completion-report.md` 为 100% 并允许 Draft PR 进入后续发布决策；`fail`、`not_proven`、证据缺失或报告不一致均 SHALL 保持非完成状态。

#### Scenario: 所有门槛真实通过
- **WHEN** 依赖、32 结构、audio、字段/写回、完整测试/构建/mGBA 和文档一致性全部为 `pass`
- **THEN** 系统 SHALL 允许恢复 100% 声明，且最终报告的每个数字和结论可追溯到机器制品

#### Scenario: 任一门槛未通过
- **WHEN** 任一 required gate 为 `fail`、`not_proven`、缺失或过期
- **THEN** 系统 MUST 设置 `completion_claim_allowed=false`，最终报告 SHALL 明确列出未完成项，且不得宣称逆向工程完成

#### Scenario: 文档与机器报告不一致
- **WHEN** 最终报告、交接文档或路线图中的结构数、证据分布、测试结果或完成布尔值与机器报告不同
- **THEN** 文档一致性门禁 MUST 失败并阻止完成声明
