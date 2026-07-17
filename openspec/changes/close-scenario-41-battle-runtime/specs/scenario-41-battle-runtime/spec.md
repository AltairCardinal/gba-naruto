## ADDED Requirements

### Requirement: 快照必须保留自然来源与稳定边界
系统 SHALL 从真实 `tutorial-ui-save.sav` 或已验证的前置 `.ss9` 建立 scenario 41 快照阶梯，并为可持久使用的快照记录输入路线、ROM 哈希、快照哈希、屏幕状态和关键 WRAM 状态。

#### Scenario: 稳定快照可零输入复放
- **WHEN** 在相同 ROM 上加载一个标记为稳定的 scenario 41 快照并不发送输入
- **THEN** 它在规定 settle 周期内保持同一 UI/战斗边界且关键状态与记录一致

#### Scenario: 中间态快照不得提升证据
- **WHEN** 快照加载后自动转场、返回不同 UI 或只短暂满足 battle/map 条件
- **THEN** 系统 MUST 将其标记为导航或负证据，而不是稳定正证据

#### Scenario: 周期性前景动画必须有界精确重现
- **WHEN** 候选快照的固定 settle 帧因角色动画而不能保持同一全屏像素
- **THEN** 系统 MUST 在不发送输入的 600 帧内找到 `1 <= p <= 300`，使 frame `0`、`p`、`2p` 的 normalized RGB8 全屏像素完全一致，并用两段独立 `p`-frame replay 复核关键状态；找不到时保持 `not-proven`

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

#### Scenario: 原生帧时序输入按互斥模式精确审计
- **WHEN** 证据清单使用原生 mGBA frame timing，并按顺序记录三段独立 guarded run 的显式 A，且每段均为 `downFrame=5`、`upFrame=13`、`holdFrames=8`、`captureFrame=80`
- **THEN** evaluator SHALL 接受该 frozen native plan，不要求 `captureFrame` 跨 event 递增，并继续要求每个 event 为 explicit 且 down/up complete

#### Scenario: 输入计划 timing mode 或事件链不精确
- **WHEN** frozen plan item 未恰好使用 legacy `holdMs` 或 native `downFrame/upFrame/holdFrames/captureFrame` 一种模式、同一 plan 混用模式、native 字段不是整数或不满足 `downFrame > 0`、`upFrame > downFrame`、`holdFrames === upFrame - downFrame`、`captureFrame > upFrame`，或者 event 与 plan 的 mode、公共字段、全部 timing 字段、数量或顺序不一致
- **THEN** evaluator MUST fail closed，且 MUST NOT 从原生帧派生近似 `holdMs`

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
