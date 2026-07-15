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
