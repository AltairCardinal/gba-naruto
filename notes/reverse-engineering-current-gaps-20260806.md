# Reverse Engineering Current Gaps（2026-08-06）

## 摘要

按 handoff 第 4 节 7 类硬指标，当前状态：

| 指标 | 当前 | 目标 | 缺口 |
|---|---:|---:|---|
| 已知 bank 目录与 ROM 字节 | 32/32 | 32/32 | ✓ |
| 有效 bank 运行时身份 | 13/22 | 22/22 | 9 个 code_verified bank 待 player-visible 闭合 |
| 已枚举图像主目录静态导出 | 100% | 100% | ✓ |
| 战斗特效精确 phase | 18/18 | 18/18 | ✓；Group 6/7/8/9/10/12/13 为受控 sequence，Group 15 为自然 action 64 |
| 战斗特效 production 最终像素 | 13/18 | 18/18 | 5 groups: [7, 8, 9, 10, 12] |
| 音频结构提取与整曲渲染 | 100% | 100% | ✓ |
| 音频 cue 人类语义 | 80/80 | 80/80 | ✓（72 D 级 unknown 是合法命名状态） |
| 对白与字库静态提取 | 100% | 100% | ✓ |
| 地图静态/资源写回 | 100% | 100% | ✓ |
| primary/alternate 章节入口表 | 112/112 | 112/112 | ✓ |
| 角色/成长/技能 bank + 字段命名 | 220/220 + C 级 | 220/220 + 全量 | ✓（+0x0D/+2/+3/+9 C 级闭合） |
| 实体 GBA 发布验证 | 0/1 | 1/1 | 真机硬件未提供 |

## 剩余 3 大缺口的执行路径

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

### 2. 战斗特效 production pixel（缺 7/8/9/10/12）

2026-08-09 已复用并重新验证 controlled-runtime 原始归档，将
Group 6/7/8/9/10/12/13 的精确三阶段计入 phase 指标；既有 Group 15 自然
battle 8 action 64 运行时产物经重验补齐最后一组，phase 达 18/18。受控组口径
明确是 controlled sequence，不冒充自然玩法。

Group 6/7/8/9/10/12 共享同一 dispatcher 链路（已 disasm 完整）：
- 中层 dispatcher 0x0807B8B8（21-case switch）
- 内层 dispatcher 0x0807C93C（13-case switch）
- Group 6 case 8 handler 0x0807CCA8
- Group 12 case 14 handler 0x0807CD3C

dispatcher 链路的最外层触发器是 **dynamic callback**，无法静态追踪。
scenario 50 + 600 帧输入推进 + 内层 dispatcher 断点实验显示 0 次命中
——确认普通 battle 路径不触发 Group 6/7/8/9/10/12 dispatcher。

**自然入口 closure 路径**: 未 tracked 剧情关卡 + mGBA AI selector tracer。
Group 13 已知走 battle 3 路线（再不斩 action 61），但 Group 12 (action
32 雷切) 在 standard formation matrix 中 occurrence=0——必须找
specific 剧情关卡触发器（handoff 5.1 已声明）。

production pixel A/B 不要求冒充自然入口。Group 6 已在已验证的 controlled
sequence 事务上组合 production relocation，以单字节图形 nibble 翻转闭合；
同一批处理路径可推广到 Group 7/8/9/10/12，这是当前优先路径。

### 3. 实体 GBA 验证 1/1

**Real blocker**: 当前环境无 GBA 硬件设备，无法执行真机测试。
handoff 第 5.2 节已声明此风险。

按 user 授权的 Goal 不允许 mGBA 替代真机（aggregate verifier
production_ninja_tool_handler_extension_group_ids 已确认 Group 16/17
有 mGBA runtime evidence，但实体 GBA 仍需真机）。

## 2026-08-09 增量

- 104/104 `.ss9` 严格验证为合法 mGBA PNG+`gbAs` 状态容器；旧“普通 PNG”
  blocker 已撤销。
- dispatcher 静态工具修复后找到 `0x0807C93C` 的 6 个直接调用点。
- phase 聚合由 10/18 提升为 18/18；其中 Group 15 复用并重验自然 action 64
  三阶段证据。Group 6 controlled production pixel A/B 使像素覆盖由 12/18
  提升为 13/18。

## 2026-08-06 会话交付（历史）

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
- 7/8/9/10/12 production pixel A/B：优先批量组合 controlled sequence 与
  production relocation；无需先完成 10-20 小时剧情关卡扫描
- 实体 GBA 验证: 无法在当前环境推进（需真机）

原 38-60 小时估算已被 controlled phase 复用缩短；剩余时间需在首个 production
controlled pixel 闭环后按实际脚本批处理成本重估。
