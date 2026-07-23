# mGBA 开发成本与耗时异常审计（2026-07-16）

## 1. 审计范围与结论

本审计覆盖主任务 `019f65ba-8399-7601-bb67-b98df6baf887` 从
2026-07-15 20:22:46 到用户于 2026-07-16 01:19:22 转向解释/统计请求的开发窗口。
另单独记录未被取消的 `single_input_runner` 在该窗口之后继续运行并提交的事件。

结论：mGBA 0.10.5 本体回移不是最大异常。最大成本和墙钟来源是三段证据链在实现后
才逐步补齐 trust root、freshness、canonical path、main wiring 和严格解析合同，导致串行
review/fix/rereview。用户转向统计后写代理仍继续提交，则是独立的编排和授权边界异常。

开发截止时的校正统计如下：

| 类别 | 有效 token | 墙钟 | 占有效 token | 占墙钟 |
|---|---:|---:|---:|---:|
| mGBA 可用化：Mac guard、环境、0.10.5 回移 | 1,204,588 | 1:29:23 | 31.2% | 30.1% |
| 三段证据链加固 | 1,745,751 | 2:28:49 | 45.2% | 50.2% |
| frame-80 与 prebattle 功能本体 | 630,143 | 0:37:15 | 16.3% | 12.6% |
| 陈旧任务核对、新计划、single runner 截止片段 | 284,045 | 0:21:10 | 7.3% | 7.1% |
| **合计** | **3,864,527** | **4:56:37** | **100%** | **100%** |

保守估计可避免的关键路径墙钟为 **47–72 分钟**：审查模式 40–65 分钟，Comet
选择门约 1.5 分钟，构建完成误判约 1.4 分钟，陈旧 Task5 核对约 3.6 分钟。真正通过
并行缩短的关键路径约 10–20 分钟，未抵消上述流程开销。

## 2. 统计口径纠正

### 2.1 上一轮“1,689 万有效 token”为什么错误

Codex 子代理 JSONL 在真正的 `Message Type: NEW_TASK` 之前会复制父线程历史，其中包括
旧 `token_count`、工具输出和 compaction。直接读取子日志最后一个累计值，会把父历史重复
计给每个子代理。

本审计改用以下口径：

1. 主线程按开发截止时的累计 token；
2. 每个子代理以 `NEW_TASK` 之前最后一个 `token_count` 为基线；
3. 子代理成本只计算基线后的增量；
4. `effective = (input - cached_input) + output`；
5. raw token 只表示模型流量，缓存输入不得按等价成本解释。

按此修正，开发截止时：

- 主线程有效 token：`1,442,626`；
- 子代理真实新增有效 token：`2,421,901`；
- 合计有效 token：`3,864,527`；
- 合计 raw token：约 `155,468,495`；
- 其中缓存输入约 `151,603,968`。

如果把 23 个 JSONL 的末尾累计值直接相加，表面 raw 会超过 10.6 亿；其中约 8.94 亿
（约 84%）只是 `fork_turns=all` 在 legacy history 中物化的父历史记录，不是子代理发出的新
请求。到本审计启动前，按 fork 基线校正后的实际新增 raw 约 1.70 亿，而不是十亿级。

系统 goal counter 在暂停点另报主任务 `1,264,337` token、活跃时间 `16,643` 秒。该计数器
与 JSONL 的“非缓存输入 + 输出”不是同一口径，因此保留为产品侧参考，不用于阶段分摊。

用户转向解释后，`single_input_runner` 又新增约 `116,985` 有效 token，并于 01:30:09
提交 `f252dbd`；这部分不计入上表，但计入异常 17。

### 2.2 耗时口径

- 开发截止墙钟：4:56:37；
- goal active time：4:37:23；
- 子代理会话墙钟不能相加，因为存在并行和等待 follow-up；
- 子代理 `task_complete.duration_ms` 可用于估算活跃执行，但多 turn 会话必须累加
  `NEW_TASK` 后的所有真实 task-complete，不能用整个文件首尾时间代替。

## 3. 异常清单、根因与解决方式

### 异常 1：macOS 前置能力未在交接入口一次性预检

**证据**：运行后才发现原 guard 依赖 Linux `/proc`，本机脚本化 mGBA 是 0.11 开发版，
而任务要求精确 0.10.5。Mac guard、环境和 CLI 审计共占 1:02:49。

**直接根因**：交接只写了目标版本和内存约束，没有可执行的环境矩阵；第一次真实运行才暴露
Darwin RSS/available-memory 缺口和 CLI 能力差异。

**系统根因**：环境能力被当作实现细节，而不是恢复任务的第一道机器门禁。

**解决方式**：交接恢复时先运行一个只读 preflight，固定检查 OS/架构、精确 mGBA commit、
`--script`、Lua sentinel、guard backend、available memory、PGID RSS、ROM/state hash。任一失败
先生成单独前置任务，不进入 ROM 计划。

### 异常 2：Darwin guard 首实现的所有权模型不一致

**证据**：初始实现按 PPID 树统计 RSS，但清理按 PGID；review 证明根进程退出后 owned PGID
子进程可能被记为 0。随后又补 malformed `ps` fail-closed 和长生命周期集成测试，首实现后的
review/fix/rereview 尾部约 28 分钟。

**直接根因**：监控和清理没有共享同一个“owned process group”定义。

**系统根因**：测试覆盖普通父子树，未先列 root-exit、孤儿后代、畸形 `ps` 三个所有权反例。

**解决方式**：资源守卫设计必须先定义唯一 ownership primitive；RSS、超时、清理和残留检查
全部使用它。平台实现前必须有 root-exit grandchild、malformed enumeration、unrelated process
三类集成 RED。

### 异常 3：Comet 唯一匹配后仍重复进入人工选择门

**证据**：12:36:50 已确认 handoff、diff、plan 唯一匹配
`close-scenario-41-battle-runtime`；12:38:15 仍请求三选一，synthetic continuation 又重复提示并
标记 blocked，12:40:00 才恢复。额外编排约 1.5 分钟。

**直接根因**：严格执行 Comet 多 change 决策点，没有使用用户已给出的自主授权和唯一匹配事实。

**系统根因**：workflow 不区分真人未回复与内部自动 continuation。

**解决方式**：handoff/change/diff 三方唯一匹配且只是续接已有 build 时允许自动恢复，并在日志
记录选择理由。否则只问一次；没有真人输入时不得重复提示或累计 blocked 次数。

### 异常 4：一次瞬时 CPU 快照被误判为构建挂起

**证据**：必要构建 2:40.8 内正常 `completed/0`。单次 `ps` 见 CMake/Ninja CPU=0 后宣布异常，
但构建已完成；终态读取滞后约 1:25.7。

**直接根因**：先看瞬时进程快照，后读原子终态 summary。

**系统根因**：静默构建没有 heartbeat，runner 完成通知没有和主线程状态联动。

**解决方式**：hang 判定顺序固定为 terminal summary、根 PID、连续 heartbeat/mtime。单次 0% CPU
永远不能判挂；只有 owner 存活且连续超过 idle 阈值没有 heartbeat 才能清理。

### 异常 5：mGBA backport 的 evidence contract 在初审后才定义

**证据**：`601b757` 后 review 一次发现 stale evidence、wrapper rc、patch TOCTOU、路径重叠/
symlink alias、真实 manifest 与 staged sentinel 不一致、helper-only wiring 等 Important。fix1
`5de8887` 增加约 510 LOC，约为初始实现增量的 52%；review 到最终批准关键路径约 42 分钟，
有效 token `349,474`。

**直接根因**：实现前没有 freshness、immutable patch bytes、canonical path conflict、main wiring
合同；13 个局部测试被误当作端到端证据。

**系统根因**：没有共享 Evidence Trust Matrix，提交前也没有统一 main integration 门禁。

**解决方式**：编码前列出每个 artifact 的 producer、canonical trust-root path、expected SHA、
fresh run-id、mandatory/optional。每个 trust root 必测同字节错误位置，每个输出必测 symlink/
directory/FIFO，每条 finding 必须对应独立 RED。

### 异常 6：APPROVED 后仍为非阻塞 Minor 启动新修复轮

**证据**：backport rereview 已 APPROVED，只剩 `sentinel.lua` 预置 symlink 的非阻塞 Minor，仍启动
`1b37afa` 和再次复审。frame80 rereview APPROVED 后，也为 superseded 文档启动 `693e40d` 收尾。

**直接根因**：把“彻底无 finding”当作进入 ROM 下一步的条件。

**系统根因**：Comet thorough 没有 Critical/Important 与 Minor 的成本优先级规则。

**解决方式**：APPROVED 后 Minor 默认进入 backlog；只有数据破坏/安全风险，或无需重型 smoke 且
预计不超过 5 分钟，才允许当轮处理。Minor 不得重启完整 reviewer/fixer 流水线。

### 异常 7：Step1 已发现的 provenance/wiring 缺口在 frame80 再次出现

**证据**：frame80 review 又发现仅记录路径而无 caller-known SHA、运行后不复验、strict
zero-input 与可注入按键的 diagnostic script 混型、main wiring 删除后测试仍绿。review/fix 阶段
有效 token `297,388`，关键路径约 34.5 分钟。

**直接根因**：Step2 仍按旧计划实现，没有吸收 Step1 review 的 trust-root/freshness/main-wiring
结论。

**系统根因**：review finding 只修当前 patch，没有升级成后续任务共享协议；新代理又独立造验证器。

**解决方式**：任何 Important finding 必须先更新共享 evidence contract/checklist，再开启下一步骤。
strict 与 diagnostic 必须在 schema/parser choice 层互斥；严格模式固定 replay path+SHA、禁止
pre-script、sentinel mandatory。

### 异常 8：共享工作树测试曾直接改写 tracked Lua

**证据**：frame80 fix1 的 RED 直接改写 tracked Lua，直到同一会话才补 `try/finally` 恢复。

**直接根因**：mutation fixture 没有使用临时副本。

**系统根因**：缺少测试前后 tracked hash/status invariant。

**解决方式**：所有 mutation tests 只能对 tmp copy 操作；测试命令前后自动比较 tracked inputs 的
SHA 和 `git status --porcelain`，漂移立即 fail closed。

### 异常 9：ignored evidence 目录复用，使持久文档指向已被覆盖的 run

**证据**：frame80 rereview 发现文档仍称旧 run 为 final，但同目录已被新 smoke 覆盖，只能再提交
superseded 文档修正。

**直接根因**：多个运行复用可变 evidence 目录。

**系统根因**：持久文档引用 mutable local path，而不是不可变 run manifest。

**解决方式**：输出固定为 `build/.../<run_id>/`，已存在 run-id 禁止覆盖；文档只引用 retained
manifest。旧 run 若不保留字节，必须在同一提交标为 superseded。

### 异常 10：prebattle acceptance 规格严重迟定并绕过复用

**证据**：`9d7185e` 后 review 发现 validator 仅验证文件与 JSON 自洽，未固定 Step2 trust roots；
sentinel 可选；guard/PGID/backend/RSS 不严格；PNG/SS9 parser 忽略 CRC/IEND/zlib 尾随和非法
filter；测试没有 actual builder 与负向漂移。fix1 `95ddbe3` 又增加约 905 LOC，为初始实现增量的
66%。16:01 到最终批准阶段有效 token约 `515,773`，关键路径约 56.5 分钟。

**直接根因**：手写平行 acceptance validator 和部分 PNG/SS9 parser，未先列 trust roots 和严格
解析规范，也没有直接复用 Step2 validator。

**系统根因**：把“绿测试 + compact JSON”误当 adversarial acceptance contract；review 批准前
OpenSpec 任务已被勾选。

**解决方式**：acceptance 只组合已有严格 validator；新 parser 只有在现有库/完整 SHA 无法满足
用户可见判据时才创建。任务状态在 fresh reviewer 0 Critical/0 Important 前只能是 reviewing，
不得勾完成。

### 异常 11：prebattle 两次修复未完整覆盖 reviewer 明确要求

**证据**：fix1 后仍漏 tracked repo patch 文件；fix2 `51a7938` 又只认证内容，允许 caller 把
tracked patch 指向同字节错误路径；`5f69b26` 才补 canonical path，第三次复审才批准。

**直接根因**：把“认证内容”误当“认证 trust-root identity”，且文字 finding 没有转成逐项测试矩阵。

**系统根因**：修复轮没有冻结 finding checklist，review cap 被“仍在 fix2 内补 correction”绕过。

**解决方式**：finding 必须结构化为 `ID -> RED -> production change -> evidence`。复审若发现上一轮
文字已明确要求但未覆盖的新 Important，立即停止微补丁并回到设计审计，不允许重命名当前轮次
继续。

### 异常 12：测试计数和验证命令没有机器固化

**证据**：报告停在 fix1 的 130 tests；fix2 后真实为 132。主线程先只能复现 117，再向实现代理
取回额外 15 个 acceptance tests，直到 16:57 才一致。

**直接根因**：报告手工维护数字，验证模块列表留在代理对话。

**系统根因**：提交不携带可机器重放的 verification manifest。

**解决方式**：每个实现提交生成 tracked `verification` 报告段或 JSON，固定 commit SHA、精确命令、
模块列表、expected/actual count 和 skip。主线程复跑计数必须 100% 一致才允许完成。

### 异常 13：陈旧 Task5 checkbox 被当成真实未执行任务

**证据**：Comet 根据 first unchecked 选择 Task5；3.6 分钟只读核对后才确认历史上 6 步均已执行，
终态是 not-proven，只是 checkbox 未同步，raw build 又已缺失。

**直接根因**：计划 checkbox 与持久 evidence、历史 commit 不一致。

**系统根因**：恢复流程把 plan 当唯一真相，没有 reconcile commit/evidence/status。

**解决方式**：任务结论提交时原子同步 plan、OpenSpec、progress 和 roadmap。恢复先跑不超过 2 分钟
的 reconcile；若 unchecked 与终态证据冲突，禁止模拟，只记录冲突并转到已知下一实验。

### 异常 14：子代理普遍使用完整历史 fork

**证据**：backport、frame80、prebattle 三段 raw/effective 比约 22x、17x、43x。短小 Task5
只读审计仍新增约 `96,520` 有效 token/3.8 分钟。大量 cached token 虽不等价计费，仍增加上下文、
延迟和误引用旧状态的风险。

**直接根因**：子代理默认 `fork_turns=all`，reviewer/fixer 获得完整主线程和巨大工具输出。

**系统根因**：没有 context package 大小上限，也没有按任务类型选择 fork 策略。

**解决方式**：review/audit 默认 `fork_turns=none`，只传 commit range、spec、报告和 finding checklist；
最多传最近 2–3 turns。自包含 context package 目标 4–8k、16k 硬上限；首请求输入 32k 预警、
64k 强制改为摘要。单个工具输出默认 4k，8k 预警，16k/64KB 必须截断或落盘后摘要。

### 异常 15：低成本 MiniMax 两次没有形成可用产出

**证据**：第一次因输出额度耗尽未返回；后续计划草稿含不可用的 shell/Python 混搭，主线程只能
保留抽象结构。

**直接根因**：委派提示仍偏大，输出合同和本地可验证边界不够窄。

**系统根因**：低成本 sidecar 没有一次失败即降级/停止规则。

**解决方式**：MiniMax 只接收小于 10k 的摘录和结构化 JSON 合同；一次失败后最多缩小提示重试
一次，第二次失败立即回到本地确定性命令，不再继续消耗。

### 异常 16：并行收益有限，且出现错误并行

**证据**：真正有效的 guard/CLI 并行约节省 10 分钟；多数 major review/fix 基本串行。Task5 审计、
segment audit、planning 也近似串行。single runner 与用户统计并行属于错误并行。

**直接根因**：派发前未标注 critical-blocking、sidecar、write，主线程经常只等待代理。

**系统根因**：以“代理数量”代替关键路径分析。

**解决方式**：派发前标注依赖和写权限；只有结果晚于当前本地工作、且不共享写范围的任务才并行。
主线程连续两次只做 `wait_agent` 时停止新增 sidecar，重新评估关键路径。

### 异常 17：用户改变意图后写代理没有被取消

**证据**：`single_input_runner` 01:14 启动。用户 01:18 转向询问耗时，01:19 要求统计，01:20
goal 已 paused；父线程没有调用 `interrupt_agent`。代理仍于 01:30:09 提交 `f252dbd`，随后结束。
用户询问到提交继续约 12 分钟，新增约 116,985 有效 token，并产生 8 文件、约 +1220/-59 的写入。

**直接根因**：父代理转去回答状态，但没有先列出并中断 write-capable agents。

**系统根因**：parent turn aborted、goal paused 和新用户意图不会自动级联取消子代理；子代理也没有
提交前 parent lease。

**解决方式**：新用户从开发切到解释/审计/统计时，第一步必须 `list_agents`，中断全部写代理，
检查工作树，再回答。parent paused/blocked/aborted 触发全局 no-commit barrier；子代理提交前必须
验证当前 parent lease 和 goal status。统计/审计模式持有全局只读锁。

`f252dbd` 当前保留，不回滚，但状态只能是 **unreviewed implementation**：没有 reviewer 批准，
没有运行 ROM，没有发送按键，也没有提升 scenario 41/controller 进度。

### 异常 18：主线程高频轮询放大长上下文成本

**证据**：审计前主线程累计约 316 次 `wait_agent`、27 次 `list_agents`、73 次
`send_message` 和 317 次执行调用。大量 30 秒等待—恢复并没有带来新证据，却让长上下文反复
采样。主线程实际 raw 接近一亿，其中绝大部分是 cached input。

**直接根因**：把轮询当作进度管理；代理未完成时频繁读状态、发催促消息。

**系统根因**：没有事件变化驱动和 polling budget；主线程在等待代理时缺少独立关键工作。

**解决方式**：等待默认 60 秒，只在 mailbox/status revision 变化时读取详情；连续三次无新证据
立即停止轮询。主线程连续两次只能等待时，不再派新 sidecar，转为本地可验证工作或向用户报告。
单代理工具调用 30 次预警、60 次硬停止；连续三次调用无新增证据时熔断。

### 异常 19：低风险任务统一使用高成本模型

**证据**：实现、日志提取、机械审查和只读核对均使用同一高端高推理模型。Task5 只读审计在
约 3.8 分钟内仍新增约 96.5k effective token；其中主要工作是读取既有 ledger、commit 和计划。

**直接根因**：原生子代理入口没有按任务风险选择模型，且 fork 完整上下文。

**系统根因**：编排只区分“是否外派”，没有“模型等级 + token budget + context budget”三元策略。

**解决方式**：高端模型仅用于直接实现、架构判断和最终验收；日志提取、文件摘要、测试点枚举
优先 MiniMax M2.7 或可用的 mini 模型；中等跨文件分析可用 MiniMax M3，结果必须由主模型以
本地证据复核。模型降级不允许扩大提示上下文作为补偿。

## 4. 统一整改门禁

### 4.1 任务预算

| 任务类型 | 预警 | 硬停止 | 停止动作 |
|---|---|---|---|
| 只读审计 | 25k effective 或 5 分钟 | 50k 或 10 分钟 | 返回已有证据，不再广搜 |
| reviewer | 50k 或 10 分钟 | 100k 或 20 分钟 | 冻结 findings，交主线程裁剪 |
| 实现代理 | 120k 或 30 分钟 | 250k 或 60 分钟 | 保存 RED/GREEN 状态，停止扩展 |
| 单一证据阶段 | 250k 或 30 分钟 | 400k 或 45 分钟 | 回到 Evidence Trust Matrix |
| 主任务单里程碑 | 1M 或 2 小时 | 2M 或 3 小时 | 输出阶段报告，重新授权范围 |

任何 fix1 新增 LOC 超过初始实现 25%，或相关测试数增加超过 20%，都表示规格/抽象不完整：停止
继续补丁，先做设计复盘。本轮三条 fix1 分别约 52%、41%、66%，均会触发该门禁。

### 4.2 审查门禁

1. 实现前提交 Evidence Trust Matrix；
2. Mutation Matrix 100% 覆盖 consumed artifacts；
3. 一次完整 reviewer 冻结全部 Critical/Important；
4. 最多一次阻塞 fix round；
5. 同 reviewer 做 focused closure；
6. closure 出现新的 Important 时停止微修，返回设计；
7. APPROVED 后 Minor 默认 backlog；
8. reviewer 批准前不得勾 plan/OpenSpec/roadmap 完成。

### 4.3 用户与代理状态门禁

1. 用户改变任务类型时先取消写代理；
2. `paused|blocked|aborted` 时禁止子代理提交；
3. audit/statistics 模式为全局只读；
4. 子代理默认 `fork_turns=none`；
5. 需要完整上下文时必须说明原因并记录估算大小；
6. 子代理提交必须持有 parent lease；
7. 未审查提交不得改变 roadmap 状态。

## 5. 后续执行优先级

1. 保留 accepted prebattle-menu 快照和已经批准的 evidence，不再扩展其解析/来源框架；
2. 将 `f252dbd` 视为未审查实现，只做一次限定 diff review，不重新进行证据架构设计；
3. review 通过后，从 accepted snapshot 只运行一次 Down；
4. 立即保存 candidate，并以零输入重放验收；
5. Down 未通过则报告具体状态，禁止继续 A；
6. Down 通过后只运行一次 A，以 `0x0808F957` 或 fresh entry observer 为唯一 controller gate；
7. 达到 gate 前不新增非阻塞证据功能、通用 parser 或历史重放。
