# Comet Design Handoff

- Change: close-scenario-41-battle-runtime
- Phase: design
- Mode: compact
- Context hash: 6f55878b22770e0f1fc1c835f864ffafe14c2d9676ed5f2c4b4a9baa7e71e26f

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/close-scenario-41-battle-runtime/proposal.md

- Source: openspec/changes/close-scenario-41-battle-runtime/proposal.md
- Lines: 1-32
- SHA256: 7ee07c963b6b28cbb2afde3074dbf137eaeabb1c997ce74d16bfcdc4507880c1

```md
## Why

scenario 41 已能稳定进入 battle 41 表现，但现有可操作快照位于玩家选择 hook 之后，因而不能证明玩家控制、正常行动提交、胜负判定或 postbattle 交接。必须从任务准备菜单以前的自然状态建立可复放快照链，并用可审计的运行时证据闭合这段控制流，才能继续验证升级与剩余 bank。

## What Changes

- 建立从真实 `tutorial-ui-save.sav` 到 scenario 41 任务准备、开始任务、开场教学、玩家回合和 postbattle 的分阶段 mGBA 快照链，避免重复导航和越过目标 hook。
- 提供 Windows mGBA GDB 只读内存、断点与有界分块读取能力，并保留浏览器模拟器的实例内输入作为不干扰桌面的补充路径。
- 在 `0x08073940/0x08073946` 玩家单位选择、当前单位、行动菜单、MOVEDONE、胜负检查、结果写入和 battle 退出边界收集可复现的运行时证据。
- 自然完成 scenario 41 两回合教程，并固化 victory 与 postbattle 检查点。
- 所有重任务统一经过资源守卫、共享锁和精确 owned-process-tree 清理；定期记录系统可用内存与进程树峰值。
- 同步交接文档、路线图、紧凑证据和回归测试；阶段成果独立提交并推送远端。
- 本 change 不宣称 levels 已验证，也不升级其余 `code_verified` bank。

## Capabilities

### New Capabilities

- `scenario-41-battle-runtime`: 从自然任务准备状态证明玩家控制、正常行动、胜利与 postbattle 交接，并提供可复放快照和紧凑运行时证据。
- `bounded-native-mgba-probing`: 在 Windows 原生 mGBA 上以有界 GDB 读、断点和资源守卫安全复放项目快照。

### Modified Capabilities

无。当前 OpenSpec 尚无既有主规格；本 change 建立首批运行时验收规格。

## Impact

- 诊断工具：`tools/mgba_gdb_probe.py`、玩家控制/胜负链 probe builder、资源守卫入口。
- 运行时驱动：`play/_scripts/runtime-formation-probe.js` 及其测试。
- 证据与快照：`artifacts/runtime-checkpoints/`、`notes/`。
- 稳定文档：`docs/reverse-engineering-handoff-20260711.md`、`docs/sequel-roadmap.md`、工具说明。
- 不引入新的全局进程清理策略，不使用按进程名批量终止，也不把预览地图或已越过 hook 的 savestate 当作正证据。
```

## openspec/changes/close-scenario-41-battle-runtime/design.md

- Source: openspec/changes/close-scenario-41-battle-runtime/design.md
- Lines: 1-76
- SHA256: 7197b377097fef6d918f6ac2e6480ead3149e907104d830dc6ddc811e5455f1a

```md
## Context

当前调查闭合为 32/32，但证据分布仍是 13 `runtime_verified`、10 `code_verified`、9 `disproved`。scenario 41 已有稳定 battle 41 表现和可操作目标网格快照，但该快照位于 `0x08073940/0x08073946` 玩家选择边界之后；从它加载新 ROM 时 scratch 为零只能证明检查点越过 hook，不能否定控制流。

本轮已验证 Windows mGBA 0.10.5 可加载项目 `.ss9`、通过 Qt GDB 端点读取寄存器/内存和设置断点；最小化窗口的定向 `PostMessage` 不能可靠改变 GBA KEYINPUT。浏览器模拟器的实例内 `buttonPress/buttonUnpress` 可可靠导航，但 Chrome 进程树更重。两条路径都必须受现有 Windows Job Object / POSIX process group、共享 heavy 锁和内存门禁约束。

## Goals / Non-Goals

**Goals:**

- 从真实存档逐阶段固化可复放快照，证明 scenario 41 进入玩家控制。
- 自然完成两回合教程，捕获 MOVEDONE、胜负检查、结果写入、battle 退出与 postbattle 状态。
- 形成 Windows 原生 mGBA 的有界 GDB 读取和断点工具，并与浏览器实例内输入互补。
- 为每个正结论保留紧凑 JSON、关键地址、输入路线、ROM/快照哈希和资源峰值。
- 以 TDD、集成测试、独立审查、阶段提交和推送维持可持续调查链路。

**Non-Goals:**

- 不在本 change 内证明 level 2、训练点或 levels record A/B。
- 不升级其余 `code_verified` bank，不启动网页编辑器产品开发。
- 不用强制 WRAM 胜利位、作弊补丁或预载状态替代自然控制流证据。
- 不使用全局键盘注入或按进程名批量清理。

## Decisions

### 1. 以自然存档建立单向快照阶梯

从 `tutorial-ui-save.sav` 冷加载开始，在 PUSH START、Continue、木叶主界面、scenario 41 剧情、任务准备、开始任务、教学、玩家行动、victory 和 postbattle 边界分别保存 `.ss9`。每个快照记录来源、输入、SHA-256 和可见/内存分类；后续实验从最近的前置快照开始。

选择该方案而不是复用旧 actionable 快照，是因为旧快照已越过玩家选择 hook。选择逐屏快照而不是长固定延迟序列，是因为方向键和转场会丢失边沿。

### 2. 运行时结论采用双通道交叉证明

ROM observer 在已静态验证的直接 BL call site 发布 magic、hit count 和参数；原生 mGBA GDB 在相同或相邻 PC 设置断点并读取 scratch、battle control 和单位状态。正结论至少要求一个自然输入路径、一个精确地址证据以及与屏幕/状态一致的结果。

只观察屏幕、只观察预载 battle ID，或在已越过 hook 的 savestate 上得到零命中均不构成结论。

### 3. 输入与调试采用混合路径

Windows mGBA 负责 `.ss9` 快速复放、只读内存、断点和寄存器；浏览器模拟器只负责 mGBA 窗口无法可靠接收的实例内输入。禁止 `SendInput`、焦点抢占和全局按键。若后续证明 mGBA 脚本接口能定向输入，可在不降低隔离性的前提下替换浏览器输入。

### 4. GDB 大区间读取固定分块

mGBA GDB 对大于 256 字节的单个 memory packet 返回 `E06`。逻辑读取必须按不超过 256 字节分块并按地址顺序拼接；任何子块错误都使整个读取失败并写出可操作诊断。

### 5. 自然胜利门禁按控制链逐级成立

玩家控制以 `0x08073940/0x08073946` 自然命中为首门禁；随后要求自然移动和行动提交命中 MOVEDONE，再命中 `0x0807444E → 0x080777FC → 0x08073068 → 0x08074FDA`，最终进入 `0xF400` postbattle。每一级都记录输入与前后状态，禁止用后一级状态倒推前一级已发生。

### 6. 所有重任务通过同一资源所有权边界

静态扫描、Chrome probe 和 mGBA probe 统一经 `tools/run_guarded.py` 与共享锁运行。只允许终止本次 Job Object/process group；每批前后检查可用内存并记录 owned-tree 峰值。失败摘要必须保留，不能因清理异常覆盖原始诊断。

## Risks / Trade-offs

- [快照捕获在按键或 DMA 中间态] → 每个候选快照先零输入重放并等待稳定，再作为前置状态；保留失败快照仅作导航线索。
- [浏览器与原生 mGBA 时序不同] → 结论绑定 GBA 地址、WRAM 和 ROM bytes，不以宿主帧率作为验收条件。
- [observer 改变寄存器或返回链] → 对每个 wrapper 做精确机器码、literal、寄存器/SP/LR 保存和错误 ROM 测试，并由独立审查复核。
- [教程输入复杂导致重复成本] → 快照阶梯只向前扩展，成功边界提交到 `artifacts/runtime-checkpoints/`。
- [资源再次异常] → 共享锁、准入、树级 RSS、wall/idle timeout 和精确 owned-tree 清理保持强制；禁止无界全 ROM Capstone。
- [预览地图形成假阳性] → strict battle arrival 之外还要求玩家 hook 或可操作菜单/行动事件；预览状态明确记录为负证据。

## Migration Plan

1. 完成并审查 mGBA GDB 与玩家控制 observer 的测试和工具说明。
2. 从真实存档重建并验证最早必要快照，删除或忽略仅用于导航的临时 build 产物。
3. 从任务准备快照命中玩家控制，固化首个正证据与新前置快照。
4. 沿自然教程逐段扩展到 MOVEDONE、victory 和 postbattle，逐阶段提交并推送。
5. 更新交接、路线图和 checkpoint README；将 levels 留给后续 change。

回滚仅删除本 change 新增的探针、测试和证据，不改动基础 ROM，也不回滚用户已有工作。

## Open Questions

- 任务准备菜单的方向键消抖状态位尚未完全命名；在正证据前需要用行为与内存双重判别第三项。
- 原生 mGBA 是否可通过官方脚本接口实现无焦点实例内输入仍待评估；当前不以此阻塞混合路线。
```

## openspec/changes/close-scenario-41-battle-runtime/tasks.md

- Source: openspec/changes/close-scenario-41-battle-runtime/tasks.md
- Lines: 1-47
- SHA256: 2eece676542b9945c5935c46aee1960890a2b1ce9c1d609073d0840cc7876daa

```md
## 1. 固化调查基线

- [ ] 1.1 审计当前未提交 probe、测试和 build 产物，区分可持久证据、临时导航文件与用户既有修改
- [ ] 1.2 记录 Windows mGBA 0.10.5 来源、版本、SHA-256、源码 commit 和可复现安装位置
- [ ] 1.3 运行资源与内存基线检查，确认所有后续 mGBA/Chrome 命令使用共享 heavy 锁和 owned-tree guard

## 2. 完成原生 mGBA 与玩家控制探针

- [ ] 2.1 以红绿重构完成 GDB RSP 寄存器、断点、watchpoint、错误输出和 256 字节分块读取测试
- [ ] 2.2 以红绿重构完成玩家单位选择与当前单位双 observer 的精确机器码、literal、call-site/cave 和错误 ROM 测试
- [ ] 2.3 让浏览器 runtime decoder 在 plan 与 settle 循环读取两个 observer，并补齐 wiring 回归测试
- [ ] 2.4 更新工具 README，说明原生 mGBA、混合输入、快照和资源守卫使用方法与失败边界

## 3. 建立 scenario 41 前置快照阶梯

- [ ] 3.1 从 `tutorial-ui-save.sav` 冷加载并零输入复验 PUSH START、Continue 与木叶主界面快照
- [ ] 3.2 自然进入 scenario 41，捕获 opcode `0x08031D5F` 终止并固化任务准备菜单快照
- [ ] 3.3 行为与内存双重确认“查看战场”和“开始任务”菜单项，保留预览地图为负证据
- [ ] 3.4 固化位于玩家选择 hook 之前的“开始任务”或开场教学快照，并记录输入、ROM/状态哈希

## 4. 证明玩家控制边界

- [ ] 4.1 从 hook 前快照运行双 observer，证明 `0x08073940/0x08073946` 自然命中且参数与玩家单位一致
- [ ] 4.2 用原生 mGBA breakpoint 或相邻 PC 独立复核命中，并记录寄存器、scratch、battle control 与资源峰值
- [ ] 4.3 在基础 ROM 或无 observer 对照上复放相同输入，确认探针未改变玩家可见行为
- [ ] 4.4 固化首个玩家控制检查点与紧凑 JSON 证据

## 5. 闭合自然行动、胜利与 postbattle

- [ ] 5.1 从玩家控制快照完成第一回合 `(4,4)→(4,7)`，捕获 MOVEDONE 与回合状态变化
- [ ] 5.2 固化回合边界快照并完成教程中断、朝向和防御选择
- [ ] 5.3 完成第二回合到 `(4,10)` 的自然行动，捕获胜负谓词与 result 写入链
- [ ] 5.4 证明 battle controller 经 `0x08074FDA` 退出并进入 `0xF400` postbattle
- [ ] 5.5 固化 victory/postbattle 快照，在基础 ROM 上零输入复放并生成紧凑证据

## 6. 同步证据与功能边界

- [ ] 6.1 新增调查记录，写明尝试、结果、关键地址、快照来源和被否定的假设
- [ ] 6.2 更新 checkpoint README、逆向交接和路线图，明确玩家控制/胜利已证明而 levels 尚未证明
- [ ] 6.3 更新完成度审计输入；除非证据门禁成立，不改变任何 bank 的 verification 状态

## 7. 验证、审查与阶段交付

- [ ] 7.1 运行相关 Python、Node、集成、格式与 `git diff --check` 验证，并保存资源守卫摘要
- [ ] 7.2 对 probe ABI、快照来源、正负证据和资源清理做独立子代理审查并处理结论
- [ ] 7.3 清理仅由本轮创建的临时 build 诊断文件，保留已选定的持久快照和证据
- [ ] 7.4 检查 `git status`，按阶段创建聚焦提交并推送 `origin/task/units-character-definitions`
```

## openspec/changes/close-scenario-41-battle-runtime/specs/bounded-native-mgba-probing/spec.md

- Source: openspec/changes/close-scenario-41-battle-runtime/specs/bounded-native-mgba-probing/spec.md
- Lines: 1-62
- SHA256: 6832e437a680ffcd4b58dca4605e1489663785714baed129f8acf62f0eb682f4

```md
## ADDED Requirements

### Requirement: 原生 mGBA 运行必须可追溯
系统 SHALL 记录所用 Windows mGBA 可执行文件版本、发布来源、文件哈希、ROM 和 savestate，并以结构化 JSON 输出寄存器、停止点和读取区域。

#### Scenario: 快照只读检查
- **WHEN** 使用原生 mGBA 加载项目 ROM 与 `.ss9` 并请求若干内存区域
- **THEN** 输出 SHALL 包含 mGBA 命令、停止原因、寄存器和每个地址区域的精确十六进制内容

### Requirement: 大区间内存读取必须有界分块
GDB 客户端 MUST 将逻辑内存读取拆为不超过 256 字节的请求，并保持顺序拼接。

#### Scenario: 读取超过 mGBA 包限制的区域
- **WHEN** 调用方请求 600 字节或完整 EWRAM
- **THEN** 客户端 SHALL 发送多个最大 256 字节的连续请求并返回等长拼接结果

#### Scenario: 任一分块失败
- **WHEN** mGBA 对某个分块返回 `E..` 错误
- **THEN** 整个逻辑读取 MUST 失败并在输出 JSON 中保留错误类型与消息

### Requirement: GDB 会话必须属于本次探针运行
原生 mGBA 探针 MUST 在启动前拒绝已被占用的 GDB 端口，在连接后验证请求 ROM 的运行时指纹，并且只清理本次启动的进程树。探针 MUST NOT 向身份不明的 GDB endpoint 发送远端终止命令。

#### Scenario: 端口已被其他进程占用
- **WHEN** 预定 GDB 端口在启动本次 mGBA 前已经监听
- **THEN** 探针 SHALL 在创建子进程前失败，记录端口冲突，并且不得连接或终止现有 endpoint

#### Scenario: 运行时 ROM 指纹不匹配
- **WHEN** GDB 读取的 ROM 固定区间与请求 ROM 的对应字节不一致
- **THEN** 探针 MUST 将会话判为不属于本次实验、关闭客户端连接并只清理自己启动的进程树

### Requirement: 停止事件必须与目标边界一致
断点或 watchpoint 运行 SHALL 严格解析 GDB stop packet，并验证停止类型、寄存器 PC 以及适用时的访问地址与请求目标一致；任意其他暂停、异常或 trap 不得记为目标命中。

#### Scenario: 非目标 trap 或 PC 不匹配
- **WHEN** continue 返回 stop packet，但原因或 PC 不对应请求断点
- **THEN** 结果 MUST 为失败并保留 stop packet、实际 PC 与期望地址

### Requirement: 运行必须受项目资源守卫约束
每个 mGBA 或浏览器 probe SHALL 在项目资源守卫下运行，并只清理守卫拥有的进程树。

#### Scenario: 正常完成
- **WHEN** probe 在 wall、idle 和 RSS 门槛内结束
- **THEN** 守卫摘要 SHALL 记录 backend、子 PID、峰值 tree RSS、命令和完成原因

#### Scenario: 超时或超内存
- **WHEN** probe 超过规定 wall/idle/RSS 门槛
- **THEN** 守卫 MUST 只终止本次 Windows Job Object 或 POSIX process group，并保留原始失败诊断

### Requirement: 输入不得影响其他桌面应用
系统 MUST 避免全局键盘注入、焦点抢占和按进程名批量终止。

#### Scenario: 原生窗口不能可靠接收定向输入
- **WHEN** 最小化 mGBA 的 `PostMessage` 未触发 KEYINPUT
- **THEN** 系统 SHALL 使用浏览器模拟器实例内按钮 API 或其他同等隔离路径，而不是 `SendInput`

### Requirement: probe 功能变化必须经过 TDD 与独立复核
新增或修改 probe 行为 SHALL 先有因正确原因失败的测试，再实现最小修复，并完成相关单元、集成与代码审查。

#### Scenario: 新增 GDB 分块读取
- **WHEN** 引入自动分块能力
- **THEN** 测试 SHALL 先证明旧实现只发送单个过大请求，再验证分块地址、大小和拼接结果
```

## openspec/changes/close-scenario-41-battle-runtime/specs/scenario-41-battle-runtime/spec.md

- Source: openspec/changes/close-scenario-41-battle-runtime/specs/scenario-41-battle-runtime/spec.md
- Lines: 1-63
- SHA256: f50ea1bd48d5322d0cb95ac31e3ede1239cca0065dd57bd3aef67dd3f0e0098d

```md
## ADDED Requirements

### Requirement: 快照必须保留自然来源与稳定边界
系统 SHALL 从真实 `tutorial-ui-save.sav` 或已验证的前置 `.ss9` 建立 scenario 41 快照阶梯，并为可持久使用的快照记录输入路线、ROM 哈希、快照哈希、屏幕状态和关键 WRAM 状态。

#### Scenario: 稳定快照可零输入复放
- **WHEN** 在相同 ROM 上加载一个标记为稳定的 scenario 41 快照并不发送输入
- **THEN** 它在规定 settle 周期内保持同一 UI/战斗边界且关键状态与记录一致

#### Scenario: 中间态快照不得提升证据
- **WHEN** 快照加载后自动转场、返回不同 UI 或只短暂满足 battle/map 条件
- **THEN** 系统 MUST 将其标记为导航或负证据，而不是稳定正证据

### Requirement: 玩家控制必须由精确运行时边界证明
系统 SHALL 在自然 scenario 41 路径中证明 `0x08073940` 玩家单位选择链或其已验证直接调用点 `0x08073946 → 0x0806F718` 被执行，并记录命中次数与实参。

#### Scenario: 自然玩家选择命中
- **WHEN** 从玩家选择之前的稳定快照推进到第一个玩家回合
- **THEN** observer magic 有效、hit count 大于零，且参数与当前玩家单位状态一致

#### Scenario: 越过 hook 的快照为零
- **WHEN** 从已位于目标网格之后的快照加载 observer ROM 且 scratch 为零
- **THEN** 系统 MUST 只记录“该快照未执行 hook”，不得据此否定玩家控制链

### Requirement: Observer 命中必须相对 checkpoint 基线保持新鲜
运行时证据 MUST 在加载 checkpoint 后、发送目标输入前读取每个 observer 的基线，并且只接受 magic 有效、命中计数相对基线递增且事件顺序与控制链一致的新样本。证据计划 SHALL 明确列出每个输入，禁止未记录的 adaptive confirm、recovery key 或自动 settle 输入参与正结论。

#### Scenario: 单一开始任务输入产生新命中
- **WHEN** 从已验证的“开始任务”行或确认框 checkpoint 读取零/旧基线后，只发送清单中的一次 A 并进入玩家回合
- **THEN** 玩家选择 observer 的命中计数 SHALL 相对基线递增，事件序号早于后续当前单位/行动事件，且证据保留输入和前后样本

#### Scenario: Savestate 携带旧 observer 样本
- **WHEN** checkpoint 加载后已经包含有效 magic 和非零命中计数，但本次输入后计数没有递增
- **THEN** 该样本 MUST 判为陈旧，不得用于证明本次自然控制流

#### Scenario: 自动恢复输入形成假阳性
- **WHEN** runtime driver 在清单外自动发送 A、B 或方向键后才出现命中
- **THEN** 该运行 MUST 判为导航或诊断样本，而不是玩家控制正证据

### Requirement: 行动与胜利必须沿自然控制链闭合
系统 SHALL 通过玩家输入自然完成 scenario 41 教程行动，并依次证明 MOVEDONE、胜负谓词、结果写入与 battle controller 退出。

#### Scenario: 自然行动提交
- **WHEN** 玩家按教程规则移动并结束行动
- **THEN** 运行时证据命中 MOVEDONE 队列边界并记录单位坐标、回合和行动状态变化

#### Scenario: 自然胜利
- **WHEN** 两回合教程按已知路线完成且 Iruka 不再满足有效存活条件
- **THEN** 证据 SHALL 覆盖 `0x0807444E`、`0x080777FC`、`0x08073068` 与 `0x08074FDA`，并显示 battle result 从未决变为胜利

### Requirement: postbattle 状态必须独立固化
系统 SHALL 在自然胜利后固化一个可零输入复放的 postbattle 检查点，并证明控制器进入 `0xF400` 状态。

#### Scenario: 胜利后交接
- **WHEN** battle controller 完成自然胜利退出
- **THEN** 新快照在复放时保持 postbattle 边界，且其证据不依赖强制 WRAM 写入

### Requirement: 证据范围必须显式限制
系统 MUST 在运行时证据中区分已证明、未证明与被否定的结论。

#### Scenario: 本 change 完成但 levels 未验证
- **WHEN** 玩家控制、自然胜利与 postbattle 已闭合但尚未观察升级训练 UI
- **THEN** 文档 SHALL 保持 levels 为 `code_verified`，并把 level/EXP/训练点证明交给后续 change
```
