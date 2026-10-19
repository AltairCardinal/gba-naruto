## Context

`sequel/content/levels/bank.json` 当前描述 `0x085459C8` 起始的 45 个 12-byte effect/stat progression records，静态消费者已证明 `base + per_level * (stored_level - 1)` 计算，但 verification 仍为 `code_verified`。现有 scenario 41 战斗入口 checkpoint 中 Naruto 为 level 1 / EXP 100、template `+0xBA=0`、`0x0200A880=0`，因此不能作为升级或 levels consumer 的自然证据。

本 change 位于 `close-scenario-41-battle-runtime` 之后。它必须从该 change 固化的真实 victory/postbattle checkpoint 开始，先证明自然升级状态，再进入训练分配 UI，捕获 `0x0808E16E → 0x08093698 → 0x08093070 → 0x080932CA`，最后只对自然命中 record 的 `+6` (`per_level_a`) 做单因素 A/B。运行时工作同时受既有资源安全约束：所有浏览器/模拟器重任务经共享 guard 与 lock 执行，不并发启动第二个重任务，不恢复全 ROM 对象化反汇编。

## Goals / Non-Goals

**Goals:**

- 建立可从依赖 checkpoint、ROM 哈希和输入序列复现的 levels 运行时证据链。
- 在同一自然 postbattle 边界记录 Naruto level 2、EXP 战前/战后值、template `+0xBA>0` 与 `A880==3`。
- 使用透明 hook 证明四段 consumer 调用链、自然 row type/ID、训练点与次槽等级变化。
- 通过 control/variant 仅修改自然命中 record `+6:n→n+1` 的 A/B 证明字段语义。
- 仅在全部门槛通过后升级 levels bank，并同步证据、笔记、交接与路线图。

**Non-Goals:**

- 不负责完成 scenario 41 的玩家控制、胜利或 postbattle；这些由前置 change 提供。
- 不强制写入 level、EXP、训练点、A880、row type、levels ID 或次槽等级来制造自然入口。
- 不验证或升级除 `levels` 之外的 bank，不宣称总逆向工程完成。
- 不修改游戏产品功能，不把诊断 ROM 或大体积临时输出纳入版本控制。

## Decisions

### 1. 以哈希锁定的依赖 checkpoint 作为硬门槛

实现首先读取 `close-scenario-41-battle-runtime` 的紧凑证据清单，校验 checkpoint、基础 ROM、scenario 41 胜利与自然 postbattle 标记。只有这些门槛同时成立，后续 probe 才能运行。checkpoint 路径本身不视为身份，所有运行结果都携带输入哈希。

选择该方案是因为 levels 证据必须建立在真实战后状态上；从旧 battle-entry checkpoint 继续、复用瞬时战场或通过内存写入伪造 state 3 都会把入口可达性与自然升级混淆。替代方案“让 levels probe 同时负责完成战斗”被放弃，因为它会重复前置 change、扩大输入和失败面，也难以隔离证据责任。

### 2. 将验证拆成状态、调用链和字段因果三层

第一层从依赖 checkpoint 运行到训练分配前稳定边界，保存 Naruto template 和关键控制字段的原始 before/after bytes：level、EXP、`+0xBA`、`0x0200A880`。EXP 不预设未经运行时证明的最终常量，而是记录原始值、战前值及与 level 2 同一时刻的关联。

第二层在相同入口安装透明 observer，记录四个地址的新鲜命中计数和顺序；确认 row 时同时捕获 row type、levels ID、record 地址/原始 12 bytes、训练点和对应次槽等级的 before/after。只有 type 4、ID 有效、训练点恰减 1、次槽等级恰加 1 才闭合自然 consumer 证据。

第三层基于第二层自然发现的 ID 生成 A/B，验证 record `+6` 的因果作用。分层而非一次性下结论，使“已升级但未打开训练 UI”“调用链命中但字段未消费”“A/B 受其他字节污染”可以被分别诊断和持久记录。

### 3. 使用可验证的透明 hook，不改变自然状态机

probe builder 从 SHA-1 锁定的不可变基础 ROM 生成诊断 ROM；每个 hook 在改写前校验原始指令和零填充 cave。wrapper 保存并恢复原函数需要的寄存器、SP 与返回链，只写独立 scratch；记录采用 magic 无效化、写 payload、最后发布 magic 的提交顺序，并在 checkpoint 恢复后用新鲜基线排除 savestate 旧值。

优先复用现有 Thumb branch 编码、probe builder、runtime decoder、guard 和证据序列化能力，不建立第二套运行框架。若一个 ROM 无法在已验证 cave 内安全容纳全部 wrapper，可按“入口链”和“确认/consumer”拆为两个 observer ROM，但两者必须加载同一 checkpoint，并通过调用边界关联；不得为了合并探针覆盖非零 ROM 区域。

替代方案包括调试器断点和直接改写状态。断点适合人工探索但难以形成可重复的 CI 制品；状态改写会破坏“自然命中”前提，因此不作为验收证据。

### 4. A/B 的唯一变量是自然命中 record 的 `+6` u16

control 与 variant 从同一基础 ROM 和同一 observer patch 构建。两者的唯一差异必须是 `0x085459C8 + ID*12 + 6` 的 u16 从 `n` 到 `n+1`；构建器输出逐字节 diff，并拒绝 ID 越界、地址不匹配、非预期基础值或其他差异。两组加载同一 checkpoint，执行同一按键、等待与采样计划。

验收比较 `0x080932CA` 的实际输入/输出及其用户可观察或内存可观察结果，预测差异按 `base_a + per_level_a * (stored_level - 1)` 计算。训练点消耗、row、ID、次槽选择和非目标状态必须一致。选择 `n→n+1` 而不是极端值，可将影响限制为最小并避免溢出或分支行为变化。

替代方案“预先选择一个看似合适的 record”被拒绝；ID 必须由自然 UI 命中后确定，否则只能证明人为构造路径。

### 5. 资源守卫和 TDD 是执行入口的一部分

新增 builder、decoder、证据判定或 bank 审计逻辑时，先写因正确原因失败的测试，再做最小实现并重跑相关单元/集成测试。所有 runtime 命令经现有 `tools/run_guarded.py` 和共享 heavy lock 启动，输出资源摘要与进度心跳；每次重任务前后检查内存和项目自有进程，不影响无关浏览器或系统进程。

测试至少覆盖：原 ROM/hook/cave 校验、wrapper 机器码和返回链、scratch 发布顺序、旧 marker 处理、A/B 单字段 diff、证据 freshness/order、四项状态门槛、失败时不升级 bank，以及运行时脚本在实际采样循环中的 wiring。只有单元测试而没有 probe 与文档/审计集成验证，不满足完成条件。

### 6. bank 升级作为最后一次可回滚事务

紧凑 JSON 先固化输入哈希、状态快照、命中链、record 和 A/B 结果，再更新调查笔记。自动审计确认全部 spec 门槛后，才把 levels verification 改为 `runtime_verified`，同步交接和路线图，并从当前所有 bank 重新计算分布，不硬编码预计计数。其他 bank 的内容和状态保持字节级不变。

如果任何门槛失败，保留负结果和下一步，bank 继续 `code_verified`。这样失败的实验仍成为项目记忆，但不会制造状态漂移。

## Risks / Trade-offs

- [依赖 checkpoint 尚未闭合或后续被替换] → 在每次运行前校验依赖 change 的验收状态和全部哈希；不满足时快速失败。
- [savestate 带入旧 scratch，形成假命中] → checkpoint 恢复后采集 scratch 基线，使用 publish-last magic 和单调计数，只接受相对基线的新鲜事件。
- [多个 hook 改写影响时序或寄存器] → wrapper 无嵌套调用、严格保存约定、使用独立 scratch，并用未改字段的 control run 对照自然行为。
- [训练 row 或 ID 与预期不同] → 不预设 ID；把自然观测值作为后续 A/B 输入，越界或 type 非 4 时记录负结果而非强制修正。
- [A/B 输出被等待时间或输入抖动污染] → 使用同一 checkpoint 和确定性输入计划，记录逐步状态；若非目标条件不一致则整组作废。
- [重任务再次造成内存压力] → 强制共享 guard/lock、单重任务、资源摘要和所有权精确的进程清理；达到阈值时保存失败摘要并停止。
- [并行 change 改变 bank 分布] → 完成时重新运行 bank audit 计算实际分布，只更新 levels 对应条目和当前文档数字。

## Migration Plan

1. 验证 `close-scenario-41-battle-runtime` 的 checkpoint 与紧凑证据已完成并锁定哈希。
2. 按 TDD 增加状态解码、透明 observer builder、runtime wiring 与证据判定；生成物只放在忽略的 build 路径。
3. 在资源 guard 下捕获自然升级/训练分配前 checkpoint 和四项状态证据。
4. 从该 checkpoint 捕获完整 consumer 调用链、自然 row/ID 与训练点/次槽变化。
5. 对自然 ID 运行严格单字段 A/B，完成结果公式与非目标条件审计。
6. 固化紧凑证据和笔记；所有验证通过后才更新 levels bank、交接与路线图，并运行全量 bank audit。

回滚时删除或忽略诊断 build 输出，撤销尚未验收的 levels bank/路线图状态变更；已记录的负证据保留并标明未闭合。基础 ROM、依赖 checkpoint 和其他 bank 不做迁移。

## Open Questions

- 自然训练 UI 最终命中的 levels ID、row 以及 record `+6` 原值是什么？该值必须由第二层运行时证据发现，不能在实现前指定。
- scenario 41 胜利后的 Naruto EXP 精确值及 rollover 表现是什么？设计只要求同一快照记录原值和战前/战后对照，最终结论由自然运行决定。
- 四个 hook 能否安全放入同一已验证 cave 集合？实现阶段先做静态空间与返回链验证；若不能，则按调用边界拆分 observer ROM，但不放宽证据 freshness 和同 checkpoint 约束。
