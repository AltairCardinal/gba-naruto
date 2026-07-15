## 1. 前置条件与基线

- [ ] 1.1 确认独立 `levels` change 已完成并同步主线；若未完成，停止本 change 的实现且不借用其证据。
- [ ] 1.2 运行当前完成度审计，记录九个目标 bank 的 canonical 地址、record shape、初始等级、现有正/负证据和基线提交。
- [ ] 1.3 盘点现有构建器、运行时驱动、mGBA/GDB、快照、code cave 与 scratch 分配，形成逐 bank 复用矩阵；只有现有链路无法满足调用约定时才批准新增专属探针。
- [ ] 1.4 为四个共享事件批次指定 ROM、快照、公共驱动和文档文件的单一所有者，并把互不写共享状态的静态复核/证据审查分配给子代理；平台支持时让重复清单核对使用低开销模型。
- [ ] 1.5 在资源守卫下运行一次 mGBA 基线恢复，记录项目 PID 树峰值、系统可用内存、墙钟/空闲超时和精确清理边界，确认不会按进程名批量终止非项目进程。

## 2. 共享快照与证据基础

- [ ] 2.1 先为快照谱系清单、基线/变体实验清单、探针固定头和半写状态拒绝逻辑编写失败测试，并确认均因缺失的新合同而失败。
- [ ] 2.2 以最小实现补齐 ROM/mGBA/父状态哈希、自然输入来源、保存边界、关键 WRAM 不变量、唯一修改范围和资源守卫摘要的结构化记录，使 2.1 的测试通过。
- [ ] 2.3 重构共享事件解码与证据校验，复用现有 hook/wrapper 和运行时驱动模式；加入 code cave、scratch、hook 原字节及单因素 diff 的重叠/边界测试并重跑相关测试。
- [ ] 2.4 从自然 scenario 41 路线建立位于有效动作 selector 之前的 mGBA 父快照，零额外输入冷恢复并验证 battle ID、单位、地图与 UI 边界；不得复用已经越过目标调用的快照。
- [ ] 2.5 为 story/过场、地图加载和自然音频事件分别确认现有可用父快照；缺失时记录最短自然输入路线和待建立边界，不以来源不明的状态作为最终证据。
- [ ] 2.6 在资源守卫下完成共享基线回放集成测试，保存紧凑结果并确认临时 ROM、截图与原始 GDB 日志仍位于忽略目录。

## 3. 批次 A：scenario 41 战斗资源

- [ ] 3.1 为 `data-table-b` 现有 battle-message wrapper 的真实 selector、79 项边界、scratch 发布顺序和运行时驱动 wiring 编写/补齐失败测试，确认测试能暴露漏 hook 或错误 ID。
- [ ] 3.2 最小扩展并重构 `data-table-b` 探针，复用 `build_battle_message_runtime_probe.py`，使单元与模拟器集成测试通过。
- [ ] 3.3 从同一 pre-action 快照成对运行 `data-table-b` 基线与单一文本指针对照，证明 ID、`0x085A2034 + id*4`、NUL 文本消费者及可见消息；若只命中空目标提示，记录负证据并建立实际有效动作路线。
- [ ] 3.4 根据 3.3 的证据更新 `data-table-b` 最终等级、bank 元数据、紧凑证据、调查说明、路线图和完成度审计；不满足三重门禁时保持 `code_verified` 并让本 change 保持未完成，继续执行明确的缺口路线。
- [ ] 3.5 为 `resource-pointers` 现有 wrapper 的五项 descriptor 边界、四字段捕获、安全 palette shift 和运行时 wiring 编写/补齐失败测试。
- [ ] 3.6 最小扩展并重构 `resource-pointers` 探针，复用 `build_resource_pointer_runtime_probe.py`，使单元与模拟器集成测试通过。
- [ ] 3.7 从同一 scenario 41 有效动作成对运行 `resource-pointers` 基线/兼容字段对照，证明 selector、`0x08596F0C + id*0x10`、四个消费者字段和具体资源结果；若战斗动作不触发该表，保存负证据并转向实际状态/overlay 路线。
- [ ] 3.8 根据 3.7 的证据更新 `resource-pointers` 最终等级、bank 元数据、紧凑证据、调查说明、路线图和完成度审计。
- [ ] 3.9 为 `tile-assets` 的 `(id-1)*0x44` 选择、`+0x0C/+0x10/+0x14` 字段捕获、VRAM/palette 目标和单因素变体编写失败测试。
- [ ] 3.10 最小实现并重构 `tile-assets` 调用点探针与运行时解码，优先追加到现有战斗视觉链，使单元与模拟器集成测试通过。
- [ ] 3.11 从同一有效战斗效果成对运行 `tile-assets` 基线/兼容图块或 palette 对照，保存 selector、ROM descriptor、解压/拷贝目标、帧摘要和预期视觉差异。
- [ ] 3.12 根据 3.11 的证据更新 `tile-assets` 最终等级、bank 元数据、紧凑证据、调查说明、路线图和完成度审计。
- [ ] 3.13 为 `palettes` 的 15 项十字节 motion/effect 记录、真实 selector、字段读取和安全单字段变体编写失败测试，并明确拒绝旧 RGB555 palette 验收。
- [ ] 3.14 最小实现并重构 `palettes` 调用点探针与运行时解码，使单元与模拟器集成测试通过。
- [ ] 3.15 从自然动作/效果成对运行 `palettes` 基线/参数对照，证明 `0x0853EE98 + id*10` 与方向、时序、幅度或终止行为的因果差异；若无安全字段，改用只读 selector/消费者/前后状态链，证据仍不足时记录阻塞且不验收该项。
- [ ] 3.16 根据 3.15 的证据更新 `palettes` 最终等级、bank 元数据、紧凑证据、调查说明、路线图和完成度审计。
- [ ] 3.17 在守卫下重放批次 A 全部基线/变体，检查四项互不冒用证据、记录峰值内存并运行相关单元、集成、bank identity、审计及 `git diff --check`。
- [ ] 3.18 让独立审查者检查 wrapper 调用约定、ROM diff、截图/消息因果和证据等级；处理意见后，将批次 A 的完整闭环创建为范围明确的本地 commit，并记录 commit hash。

## 4. 批次 B：故事与过场视觉资源

- [ ] 4.1 从自然 story 路线建立位于视觉 selector 之前的 mGBA 快照，验证 script cursor、story opcode 和屏幕状态，记录谱系与资源守卫摘要。
- [ ] 4.2 为 `battle-encounters` 的 24 项真实视觉 descriptor、三条 LZ77 指针、config ID 和解压目标编写失败测试，确保不再按敌方编成解释。
- [ ] 4.3 最小实现并重构 `battle-encounters` selector/loader 探针与单因素兼容资源对照，使单元与模拟器集成测试通过。
- [ ] 4.4 成对重放 `battle-encounters` 基线/变体，证明自然 opcode、`0x0854229C + id*record_size`、三流消费者和预期画面差异；随后更新最终等级、元数据、证据、路线图和审计。
- [ ] 4.5 为 `cutscene-scripts` 的 ID 0..3、两组相邻资源 pair、gfx/palette 解压和 sprite pair 安装编写失败测试，确保同一 ID 贯穿两组表。
- [ ] 4.6 最小实现并重构 `cutscene-scripts` selector/loader 探针与兼容资源对照，使单元与模拟器集成测试通过。
- [ ] 4.7 成对重放 `cutscene-scripts` 基线/变体，证明真实 ROM pair、解压/安装目标和预期可见结果；随后更新最终等级、元数据、证据、路线图和审计。
- [ ] 4.8 在资源守卫下重放批次 B，运行相关单元、集成、identity 和完成度审计，记录内存峰值并检查没有历史 slug 语义回归。
- [ ] 4.9 经独立视觉证据与 ROM diff 审查后，将批次 B 的完整闭环创建为范围明确的本地 commit，并记录 commit hash。

## 5. 批次 C：地图回调与精灵资源

- [ ] 5.1 从自然地图加载/行为路线建立位于 selector 之前的 mGBA 快照，验证 map ID、`sb` 状态、实体列表和屏幕状态并记录谱系。
- [ ] 5.2 为 `map-events` 的 `sb+0x770` index、`index<<3`、primary/secondary pair 和非零间接调用边界编写失败测试；测试必须在任一半表地址错误时失败。
- [ ] 5.3 最小实现并重构 `map-events` 分派探针，保持函数指针只读，使单元与模拟器集成测试通过。
- [ ] 5.4 运行自然地图行为，证明 `0x0853E698` pair、命中 callback 与随后行为；若无法安全 A/B，使用只读自然分派链闭合因果证据，证据仍不足时记录阻塞并保持本 change 未完成。
- [ ] 5.5 为 `map-sprites` 的 43 项 definition/animation pair、安装参数、遍历目标和兼容资源对照编写失败测试。
- [ ] 5.6 最小实现并重构 `map-sprites` loader 探针，复用已有 sprite 资源安装链，使单元与模拟器集成测试通过。
- [ ] 5.7 成对重放 `map-sprites` 基线/变体，证明 `0x0853F140 + id*8`、两条 ROM 指针和预期精灵/动画差异；随后更新最终等级、元数据、证据、路线图和审计。
- [ ] 5.8 在资源守卫下重放批次 C，运行相关单元、集成、handler/sprite identity 和完成度审计，记录峰值内存并核对非项目进程未受影响。
- [ ] 5.9 经独立回调安全、资源兼容和证据等级审查后，将批次 C 的完整闭环创建为范围明确的本地 commit，并记录 commit hash。

## 6. 批次 D：Sappy 引擎自然命令链

- [ ] 6.1 选择一个已识别、可重复且不涉及 P2 cue 命名的自然音乐/音效事件，在命令处理前建立 mGBA 快照并记录 sound ID 与父状态。
- [ ] 6.2 为命令字节、handler PC、处理前后声道/FIFO/DMA 状态和音频摘要的捕获与关联编写失败测试；加入拒绝代码区或调度表变体的测试。
- [ ] 6.3 最小实现并重构 `sappy-engine` 自然命令跟踪，复用现有音频捕获和比较器，使单元与模拟器/音频集成测试通过。
- [ ] 6.4 在资源守卫下重放自然事件，连接命令、`0x09AE3C` 引擎代码、handler、声道状态和音频结果；不得直接修改可执行代码。
- [ ] 6.5 根据 6.4 判断 `sappy-engine` 是否满足运行时门禁；若不能，记录缺失的 handler/状态/音频关联和下一条非修改式调查路线，保持 `code_verified` 且不验收本 change。
- [ ] 6.6 经独立音频因果与代码完整性审查并通过相关测试后，将批次 D 的完整结论创建为范围明确的本地 commit，并记录 commit hash。

## 7. 九项完成度审计与文档收口

- [ ] 7.1 逐项核对九个 bank 均有自然 selector/事件、canonical ROM 目标、消费者边界、结果、A/B 可行性、正/负证据和明确最终等级；每项必须为 `runtime_verified` 或有严格身份负证据的 `disproved`，缺失、间接或仍为 `code_verified` 均不得通过。
- [ ] 7.2 重新生成完成度审计并核对统计分布、bank JSON、紧凑证据、`notes/`、逆向工程交接和 `docs/sequel-roadmap.md` 完全一致。
- [ ] 7.3 运行全部相关 Python/Node 单元测试、mGBA 集成重放、bank identity/提取器测试、资源守卫测试、完成度审计和 `git diff --check`，记录每项命令与结果。
- [ ] 7.4 检查最终项目 PID 树和系统可用内存，只清理本 change 明确创建的临时进程与已枚举忽略产物，不触碰其他项目进程或用户文件。
- [ ] 7.5 让独立审查者按 spec 对九项逐条做证据充分性、ROM patch 安全、测试覆盖和范围边界审查；修复问题并重跑受影响验证。
- [ ] 7.6 检查 `git status`，确保不混入 `levels`、P2 audio cue、legacy web/ROM mirror 或其他用户改动；创建最终审计收口的本地 commit，并记录 commit hash。
