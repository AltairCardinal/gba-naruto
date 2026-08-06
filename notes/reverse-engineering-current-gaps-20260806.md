# Reverse Engineering Current Gaps（2026-08-06）

## 摘要

按 handoff 第 4 节 7 类硬指标，当前状态：

| 指标 | 当前 | 目标 | 缺口 |
|---|---:|---:|---|
| 已知 bank 目录与 ROM 字节 | 32/32 | 32/32 | ✓ |
| 有效 bank 运行时身份 | 13/22 | 22/22 | 9 个 code_verified bank 待 player-visible 闭合 |
| 已枚举图像主目录静态导出 | 100% | 100% | ✓ |
| 战斗特效精确 phase | 10/18 | 18/18 | 8 groups: [6, 7, 8, 9, 10, 12, 13, 15] |
| 战斗特效 production 最终像素 | 12/18 | 18/18 | 6 groups: [6, 7, 8, 9, 10, 12] |
| 音频结构提取与整曲渲染 | 100% | 100% | ✓ |
| 音频 cue 人类语义 | 80/80 | 80/80 | ✓（72 D 级 unknown 是合法命名状态） |
| 对白与字库静态提取 | 100% | 100% | ✓ |
| 地图静态/资源写回 | 100% | 100% | ✓ |
| primary/alternate 章节入口表 | 112/112 | 112/112 | ✓ |
| 角色/成长/技能 bank + 字段命名 | 220/220 + C 级 | 220/220 + 全量 | ✓（+0x0D/+2/+3/+9 C 级闭合） |
| 实体 GBA 发布验证 | 0/1 | 1/1 | 真机硬件未提供 |

## 剩余 4 大缺口的执行路径

### 1. 22/22 bank runtime identity（缺 9 个）

按 ROI 排序：
- **Tier 1** (palettes, tile-assets): 单字节 patch + mGBA render diff
- **Tier 2** (map-events, map-sprites): scenario 41/50 快照 + controlled probe
- **Tier 3** (battle-encounters, cutscene-scripts): scenario 47+ 快照 + 多帧对比
- **Tier 4** (sappy-engine, levels, data-table-b): 间接可见

**注意**: palettes bank player-visible closure 实验已尝试但 baseline vs
candidate PNG SHA 完全相同。原因：palettes bank consumer
(0x080806B0/0x08080764/0x08080814) 是 task spawn 路径，必须有 active
task spawn 才能消费 record 数据。battle 8 round 3 AI 选择 action 61
（斩首大刀），不消费 palettes record 0。

### 2. 战斗特效 phase/pixel（缺 6/7/8/9/10/12）

Group 6/7/8/9/10/12 共享同一 dispatcher 链路（已 disasm 完整）：
- 中层 dispatcher 0x0807B8B8（21-case switch）
- 内层 dispatcher 0x0807C93C（13-case switch）
- Group 6 case 8 handler 0x0807CCA8
- Group 12 case 14 handler 0x0807CD3C

dispatcher 链路的最外层触发器是 **dynamic callback**，无法静态追踪。
scenario 50 + 600 帧输入推进 + 内层 dispatcher 断点实验显示 0 次命中
——确认普通 battle 路径不触发 Group 6/7/8/9/10/12 dispatcher。

**唯一 closure 路径**: 未 tracked 剧情关卡 + mGBA AI selector tracer。
Group 13 已知走 battle 3 路线（再不斩 action 61），但 Group 12 (action
32 雷切) 在 standard formation matrix 中 occurrence=0——必须找
specific 剧情关卡触发器（handoff 5.1 已声明）。

### 3. 实体 GBA 验证 1/1

**Real blocker**: 当前环境无 GBA 硬件设备，无法执行真机测试。
handoff 第 5.2 节已声明此风险。

按 user 授权的 Goal 不允许 mGBA 替代真机（aggregate verifier
production_ninja_tool_handler_extension_group_ids 已确认 Group 16/17
有 mGBA runtime evidence，但实体 GBA 仍需真机）。

### 4. 战斗特效 phase 还缺 Group 13/15（除 6/7/8/9/10/12 外）

Group 13/15 在 production_pixel_ab 已闭合（controlled runtime 路径），
但 phase_verified 未达 ——因为 Group 13 phase closure 用 ninja-tool
hardcoded-handler 路径，需要独立的 phase 实验。

## 当前会话净交付

按 `tools/analyze_reverse_engineering_gaps.py` 输出（commit 92e1b7b01
+ abd11fd70 改进）：

### 工具新增
- tools/disassemble_battle_effect_dispatchers.py: dispatcher 链路反汇编
- tools/mgba_battle_effect_dispatcher_tracer.lua: 内层 dispatcher 断点 tracer
- tools/mgba_palettes_player_visible.lua: cold-boot 截图 probe
- tools/mgba_palettes_spawn_capture.lua: spawn-then-screenshot probe
- tools/analyze_reverse_engineering_gaps.py: 汇总当前 gaps

### Artifacts promoted
- artifacts/battle-effect-group12-ai-observer-v1/ (Group 12 action 32
  不可达确认)

### 笔记新增
- notes/battle-effect-group6-entry-audit-20260806.md v2: Group 6/7/8/9/10/12
  完整 dispatcher 链路
- notes/group12-natural-entry-ai-observer-20260806.md: Group 12 AI observer
  实验记录
- notes/bank-player-visible-closure-plan-20260806.md: 9/22 bank closure
  规划
- notes/palettes-bank-player-visible-attempt-20260806.md: palettes bank
  closure 尝试失败记录
- docs/reverse-engineering-handoff-20260806.md: 交接文档
- docs/structure-field-semantics.md: 字段命名 C 级闭合（+0x0D/+2/+3/+9）

### 硬指标
未变：phase 10/18, pixel 12/18, 13/22 runtime + 9/22 code_verified。
已达成：100% 静态覆盖 + audio/对白/字库/地图/章节入口/角色/技能
bank + 字段 C 级命名 + 实体 GBA 0/1（无硬件）。

## 未达成目标的真实成本评估

按当前可推进路径计算：
- 9/22 bank closure: ~20-30 小时 mGBA + 5 小时 disasm
- 6/7/8/9/10/12 dispatcher natural route: ~10-20 小时 mGBA 剧情关卡扫描
- Group 13/15 phase closure: ~3-5 小时 mGBA
- 实体 GBA 验证: 无法在当前环境推进（需真机）

总计 ~38-60 小时 mGBA + disasm 工作。即使按完整工作日（8小时），
也需要 5-8 个完整工作日。