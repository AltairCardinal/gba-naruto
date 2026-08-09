# Reverse Engineering Current Gaps（2026-08-06）

## 摘要

按 handoff 第 4 节 7 类硬指标，当前状态：

| 指标 | 当前 | 目标 | 缺口 |
|---|---:|---:|---|
| 已知 bank 目录与 ROM 字节 | 32/32 | 32/32 | ✓ |
| 有效 bank 运行时身份 | 21/22 | 22/22 | 1 个 code_verified bank 待 runtime 闭合 |
| 已枚举图像主目录静态导出 | 100% | 100% | ✓ |
| 战斗特效精确 phase | 18/18 | 18/18 | ✓；Group 6/7/8/9/10/12/13 为受控 sequence，Group 15 为自然 action 64 |
| 战斗特效 production 最终像素 | 18/18 | 18/18 | ✓；6 个 controlled sequence 组不声称自然入口 |
| 音频结构提取与整曲渲染 | 100% | 100% | ✓ |
| 音频 cue 人类语义 | 80/80 | 80/80 | ✓（72 D 级 unknown 是合法命名状态） |
| 对白与字库静态提取 | 100% | 100% | ✓ |
| 地图静态/资源写回 | 100% | 100% | ✓ |
| primary/alternate 章节入口表 | 112/112 | 112/112 | ✓ |
| 角色/成长/技能 bank + 字段命名 | 220/220 + C 级 | 220/220 + 全量 | ✓（+0x0D/+2/+3/+9 C 级闭合） |
| 实体 GBA 发布验证 | 0/1 | 1/1 | 真机硬件未提供 |

## 剩余缺口的执行路径

### 1. 22/22 bank runtime identity（缺 1 个）

剩余项：
- **Tier 4** (`data-table-b`)：间接可见

**已闭合**：`palettes` 历史 slug 实为 motion/effect 参数表。自然 Group 3
零输入 A/B 把 record 0 `y_offset` 从 0 改为 32，严格传播为 task/OAM Y +32，
ack Mode 0 重放得到 286 个最终像素变化；运行内存差异仅限对应 task/OAM
字节。详见 `notes/motion-effect-parameter-player-visible-20260809.md`。

**已闭合**：`tile-assets` 的自然 Mode-0 场景链选择 presentation 3 / descriptor 2。
只把 descriptor 2 `+0x14` 的 layer-A palette pointer 从 `0x0834B228`
改为 `0x08349E74`，两次固定零输入 A/B 仅在 PRAM `0x050001E2..1FF`
留下差异，并改变最终 38,400 个像素；其余五个内存域完全一致。详见
`notes/tile-assets-descriptor-player-visible-20260809.md`。

**已闭合**：`map-sprites` 的 entry 1 `definition_ptr` 受控物化 A/B。两份 ROM
仅在 `0x53F148..149` 有实际字节差异；自然快照中已有的 ID 1 task 123 被显式
重新激活，并从各自 ROM 表物化 definition。两次运行均命中 `0x0806298C` 与
`0x08063108`，最终 OAM 改变 15 字节、画面 `(178,64)..(215,71)` 改变
213 像素。该证据不声称自然 loader 重入或 donor 原生 tile-base 兼容。详见
`notes/map-sprites-definition-player-visible-20260809.md`。

**已闭合**：`map-events` entry E4 primary 的自然恢复态 A/B。两案均在 frame 66
从 `0x0853EDB8` 经 trampoline 分派；只有基线进入 `0x0807F208` 并在 frame 67
渲染 group 3，frame 69 最终相差 37,436 像素。恢复点已越过 C3→E4 构造，故本轮
不声称重命中 expiry builder。详见 `notes/map-events-e4-player-visible-20260809.md`。

**已闭合**：历史 `battle-encounters` slug 实为 24 条 story visual descriptor。
受控 scenario-53 opcode `0x14` 快照中，record 0 `gfx_lz_ptr` 从
`0x0812FF50` 替换为合法 donor `0x081303E8`；两案均命中原生 state dispatch、
`0x08087C9C` loader 和三路 LZ77，第 8 次 overlay VBlank 最终相差 1,603 像素。
该证据不声称自然 scenario-53 导航或其余 23 条 record。详见
`notes/battle-encounters-story-visual-player-visible-20260809.md`。

**已闭合**：历史 `cutscene-scripts` slug 实为两张相邻的四记录视觉资源表。
自然胜利 ID 1 production-relocation A/B 直接把 `primary_ptr@0x53DF78` 从 ID 1
graphics 改为同尺寸 ID 2 donor；其余 ROM 字节相同，运行时除 VRAM 2,263 字节
外五个完整内存域不变，最终改变 4,032 像素。两边均经当前渲染器逐 RGB 重放与
独立 verifier 复验；边界不覆盖其他 ID、第二表字段 A/B 或实体 GBA。详见
`notes/cutscene-visual-resource-player-visible-20260809.md`。

**已闭合**：`sappy-engine` 是 `0x0809AE3C..0x0809AEF3` 的 184-byte
FIFO/DMA 初始化函数。共同恢复初始化前快照后，两案均命中 initializer、sound
101 dispatcher 与 SoundMain；仅修改 `0x0809AE76` immediate，使函数返回时
`SOUNDCNT_X 0x0080→0x0000`，其余控制流与首次 SoundMain FIFO 块相同。
后续 SoundMain 会重新打开 gate，故不声称持续静音或 WAV 差异。详见
`notes/sappy-engine-master-enable-runtime-20260809.md`。

**已闭合**：`levels` 在自然命中的 type-`0x1A` 状态调用点受控物化
record 21 / level 17，调用后恢复 live slot；单独把 `per_level_a` 从 1 改为 0
令查询输出 A 从 18 降为 2，严格符合成长公式。frame-120 屏幕相同，因此不声称
自然训练 UI 或玩家可见像素差。证据见
`artifacts/levels-status-per-level-ab-v1/`。

### 已闭合：战斗特效 production pixel（18/18）

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

production pixel A/B 不要求冒充自然入口。Group 6/7/8/9/10/12 已在已验证的
controlled sequence 事务上组合 production relocation，以单字节图形 nibble
翻转批量闭合；聚合 verifier 独立复核后为 18/18。Group 10 还精确记录了
`0x03007F9C` 的单字节栈路径残留，不把它隐藏为纯 VRAM 差异。详见
`notes/battle-effect-groups7-12-controlled-pixel-ab-20260809.md`。

### 2. 实体 GBA 验证 1/1

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
- 同一数据驱动链批量完成 Group 7/8/9/10/12，production modified-ROM pixel
  覆盖由 13/18 提升到 18/18；10 次主批运行与 4 次候选重选运行均经 heavy
  lock，峰值 owned-tree RSS 低于 80 MiB 且无 mGBA 残留。
- `palettes`（motion/effect 参数）自然 Group 3 record-0 `y_offset` A/B 闭合；
  bank runtime 指标由 13/22 提升为 14/22。两次 mGBA 峰值 RSS 不超过
  75 MiB，独立 verifier 从 raw archive 重建 ROM、三阶段内存与最终像素。
- `tile-assets` descriptor 2 的自然 selector/initializer 路线及最小 palette
  pointer A/B 闭合；bank runtime 指标由 14/22 提升为 15/22。两次 A/B
  峰值 RSS 均低于 108 MiB，计划/实际运行数为 2/2，盲试为 0。
- `map-sprites` entry 1 `definition_ptr` controlled materialization A/B 闭合；bank
  runtime identity 由 15/22 提升到 16/22。
- `map-events` entry E4 primary natural-recovery A/B 闭合；bank runtime identity
  由 16/22 提升到 17/22。
- `battle-encounters` record 0 story visual `gfx_lz_ptr` controlled opcode A/B 闭合；
  bank runtime identity 由 17/22 提升到 18/22。
- `levels` record 21 `per_level_a` controlled materialization A/B 闭合；bank runtime
  identity 由 20/22 提升到 21/22，剩余 `data-table-b`。

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
- 剩余 7/22 bank closure: 已验证“先复用已验快照、再固定两次 A/B”
  可把单 bank 成本压到约 1–3 小时；尚无入口的 bank 仍需额外 route discovery
- 实体 GBA 验证: 无法在当前环境推进（需真机）

原 38-60 小时估算已被 controlled phase 复用缩短；剩余时间需在首个 production
controlled pixel 已按实际脚本批处理闭合；当前可推进成本集中在 7 个 bank
player-visible closure。
