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
