# Reverse Engineering Current Gaps（更新至 2026-09-01）

> **严格证明更正（更新至 2026-08-31）：** 本文原先把“每个 bank 至少有一次运行时身份关联”
> 写成 22/22 完成，这不能证明全记录、全字段或全 ROM 语义已穷尽。当前机器审计
> 显示：ROM 有 6,142,176 / 6,291,456 字节可保守精确定位（149,280 字节
> 仍显式未知，97.627258% / 2.372742%）；114 条指针表候选已全部裁决（60 accepted、26 alias、
> 28 rejected，open 0）；22 个
> 有效 bank 的直接证据声明只覆盖 23 / 2,954 条
> 记录；实体 GBA 为 0/1。权威口径见
> `docs/reverse-engineering-proof-policy.md` 与
> `sequel/reverse-engineering-proof.json`。

## 摘要

按 handoff 第 4 节 7 类硬指标，当前状态：

| 指标 | 当前 | 目标 | 缺口 |
|---|---:|---:|---|
| 历史 bank 名称调查 | 32/32 | 32/32 | 仅身份目录闭合，不是全 ROM 分母 |
| 有效 bank 至少一次运行时身份 | 22/22 | 22/22 | 标签闭合；全记录/字段穷尽为 0/22 |
| ROM 字节语义分类 | 6,142,176 / 6,291,456 | 6,291,456 / 6,291,456 | 2.372742% 显式未知 |
| 指针表候选裁决 | 114/114 | 114/114 | 60 accepted / 26 alias / 28 rejected；open 0 |
| 已枚举图像主目录静态导出 | 100% | 100% | ✓ |
| 战斗特效精确 phase | 18/18 | 18/18 | ✓；Group 6/7/8/9/10/12/13 为受控 sequence，Group 15 为自然 action 64 |
| 战斗特效 production 最终像素 | 18/18 | 18/18 | ✓；6 个 controlled sequence 组不声称自然入口 |
| 音频结构提取与整曲渲染 | 100% | 100% | ✓ |
| 音频 cue 人类语义 | 80/80 | 80/80 | ✓（72 D 级 unknown 是合法命名状态） |
| 对白与字库静态提取 | 100% | 100% | ✓ |
| 地图静态/资源写回 | 100% | 100% | ✓ |
| 四张固定章节根表 | 204/204 槽（200 非空） | 204/204 | ✓；静态闭包不等于自然玩法全路径 |
| 角色/成长/技能 bank + 字段命名 | 220/220 + C 级 | 220/220 + 全量 | ✓（+0x0D/+2/+3/+9 C 级闭合） |
| 实体 GBA 发布验证 | 0/1 | 1/1 | 真机硬件未提供 |

## 剩余缺口的执行路径

2026-08-11 已新增固定 boot interwork ARM 根闭包：唯一 Thumb BL→`BX pc`→ARM B
producer 静态绑定到 `0x0800024C`，独立 worklist 闭合 92 条 ARM 指令、8 个 block、
10 条 edge、0 个 frontier 及 9 个 literal，精确减少 unknown 414 字节。该成果不
证明完整 reset-to-root 运行时路径，也不授权把跳过的 veneer 对齐、sibling、RAM
目标或周边约 40 KiB 一并分类；详见 `notes/rom-boot-interwork-20260811.md`。

同日 fixed-consumer 文本 artifact 批量扩展到 9 表、575 槽（含 1 个显式 null）和
570 条 parser-bounded 记录；新增 1,180 个表字节与 4,024 个消费字节。混合
`0x5A7FCC..0x5A802C` UI 资源表因缺少文本前缀索引上界而失败关闭地排除，不能把
其前 18 个 text-like 槽认领为完整文本分母。

同日又从控制器范围中的三条固定 Thumb BL producer 证明两个新 CFG root，并以
v2/v3 指令入口作为 opaque stop 独立闭合 6,166 条指令、1,203 个 block 和
12,966 个字节。coverage 仅提升 12,946 个仍 unknown 的可达代码字节，并把三条
producer 的 12 字节单列；27 个间接目标和一个 decode failure 继续开放。详见
`notes/rom-cfg-proven-roots-20260811.md`。

2026-08-12 又从同一控制器固定五条 Thumb BL producer，证明 `0x0689A4`、
`0x06B49C` 与 `0x0851F8` 三个新根；以 v2/v3/首批 proven-roots 入口为 opaque
stop 独立闭合 4,809 条指令、835 个 block 与 9,876 个字节。coverage 提升全部
闭包字节并单列 20 个 producer 字节；27 个间接目标和一个 unsupported instruction
继续开放。详见 `notes/rom-cfg-proven-roots-v2-20260812.md`。

2026-08-13 至 2026-08-20 已继续完成 proven-roots v3–v8、固定消费者与多类已验证
零填充/资源窗口接入。v8 从 scene visual source closure 固定唯一
`0x0808BE5C→0x0808B99C` Thumb BL，独立闭合 113 条指令、20 个 block、246 字节，
保留 1 个间接 frontier。随后 battle-effect sprite source 批次复用既有 artifact，
将 237 个完整 source range、11,120 字节从 unknown 晋升；随后 referenced text slot
padding additive artifact 又将 133 段、1,255 字节固定消费者 NUL 后结构零填充从
unknown 晋升；selector direct 来源记录 artifact 随后将固定 46×20 字节完整记录的
920 字节从 unknown 晋升；selector 代码窗口 artifact 再只将 10 个完整 source
window 中的 19 段 current-unknown 交集、1,252 字节晋升；菜单肖像调色板 artifact
随后又把 70 段固定 128 字节物理 BGR555 palette、共 8,960 字节从 unknown 晋升。
正式 coverage 为 6,102,121 / 6,291,456（96.9906%），unknown 189,335、claim
13,872、segment 16,119；这仍不证明 semantic complete。

同日随后接入 scene visual source-range 批次：从 `scene-visual-packs-v1` 固定
9-record source table 的 57 段、88,756 字节完整分母
冻结 29 段、3,288 字节候选，保留 pack 5 已有 LZ77 owner 的 31 字节，只晋升
29 段、3,257 个 current-unknown 字节。接入后 coverage 为 6,105,378 / 6,291,456
（97.0424%），unknown 186,078、claim 13,901、segment 16,142；仍不证明 semantic
complete、自然可达、最终像素等价、编辑/重定位安全或 free space。

### 1. 22/22 bank runtime identity 标签（非穷尽证明）

最后一项 `data-table-b` 已通过自然 action-7 ID 0 单指针像素 A/B 闭合。
两案均命中真实 selector/entry 一次，`0x085A1580→0x085A1598` 使最终画面
改变 928 像素；证据见
`artifacts/data-table-b-message0-pointer-pixel-ab-v1/`。

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

### 2. 实体 GBA 验证 0/1

**Real blocker**: 当前环境无 GBA 硬件设备，无法执行真机测试。
handoff 第 5.2 节已声明此风险。

按 user 授权的 Goal 不允许 mGBA 替代真机（aggregate verifier
production_ninja_tool_handler_extension_group_ids 已确认 Group 16/17
有 mGBA runtime evidence，但实体 GBA 仍需真机）。

## 2026-08-09 增量

## 2026-08-13 字节覆盖增量

- proven-roots v3/v4 已通过独立 verifier 和 coverage audit，新增 1,154 个 Thumb
  指令字节；当前 unknown 为 271,373，语义覆盖 95.6866%。
- `0x07305C` 的 6 个间接 PC frontier 仍明确开放；不得从静态包络推导目标。
- `0x07504E` 是该时点的历史候选；后续已由正式控制器 CFG 处理，不再是当前待办。
- 其他全局门禁（bank 全字段、编辑器、真机）不属于当前字节覆盖 Goal 的完成条件。

## 2026-08-20 字节覆盖增量

- proven-roots v8 正式 artifact、独立 verifier、coverage 与 proof 合同均已接入；
  20 个新 block 精确晋升 246 字节，producer 和 source consumer 未重复认领。
- battle-effect sprite source 批次以既有独立 verifier 重建 178 段 component list、
  18 张 definition pointer table、23 段 animation timeline 和 18 张 animation pointer
  table，共 237 claim / 11,120 字节；分母 SHA-256 为
  `c30b25fbed4a80914e8bc9e8d33ec7545e47a01a005866460323ac8c9b84ba30`。
- referenced text slot padding additive artifact 独立重建 direct selector 46/550、
  configured selector 38/368、chapter speaker-label 49/337，共 133 claim / 1,255
  字节；只分类首个 NUL 后到固定槽末尾的全零结构填充，不声明文本语义、自然可达、
  编辑/写回安全或可安全分配空间。
- selector direct source-record artifact 独立重建固定 46-row producer/vector、目标槽
  stride 和 renderer/parser 调用链，将 `0x0059F5F0..0x0059F988` 的 46×20 字节、
  共 920 字节完整晋升；不声明 bytes 2..19 字段语义、自然可达或写回安全。
- selector-code-window artifact 独立冻结 10 个完整 source window、2,754 字节，只将
  其中 19 段、1,252 字节 current-unknown 交集晋升为 `consumer_code_slice`；1,502
  字节已有 primary ownership 保持不变，bridge/mapper promotion 均为 0。不声明
  instruction-only、自然运行时可达、global caller 穷尽、安全编辑/重定位、可分配
  空间或新字段语义。
- menu-portrait palette artifact 从 63×5 目录表、special pair、u8 selector 与五条
  GPU queue caller 独立重建 311 个逻辑输出；74 个资源按物理指针/range 去重为
  70 段 128 字节 palette，共 8,960 字节。70 段只有 54 种内容哈希；唯一跨资源
  别名 `0x084098C4` 由资源 `[0,67,68,69,70]` 共用。该批不声明动态 caller 域、
  全部自然可达、graphics、像素等价、独立别名原位编辑、relocation 或 free space。
- scene-visual source-range artifact 从固定 9-record source table 的 57 段、88,756
  字节完整分母冻结 29 段、
  3,288 字节候选；pack 5 的 31 字节保留既有 LZ77 owner，实际晋升 29 段、3,257
  字节。类别为 shared OBJ palette 2/64、BG palette 9/2,304、definition 9/697、
  animation 9/192；不声明全部来源、自然可达、最终像素、编辑/重定位或 free space。
- Cutscene OBJ source-range artifact 从两个固定四记录根表重建 4 个资源 ID 的 10 个
  frame 与 10 个 animation，将 28 段、400 字节晋升；四类分母为 component definition
  10/240、definition pointer table 4/40、animation timeline 10/80、animation pointer
  table 4/40。manifest SHA-256 为
  `a0e97ec43858a145a7c26dc71c5b89dfe8c4d9a5d6074ccad88c4ae56e03afd5`，verifier
  SHA-256 为 `a1075b8885378fe2c26c1c262126ad8098bb81c171a805cb3e08ed0d8217c446`；不声明未知
  component 字段语义、自然可达、最终场景合成、graphics/palette、编辑/重定位、相邻
  间隙或 free space。
- proven-roots v9 从冻结 battle-controller CFG provenance 固定 11 条 target-limited
  Thumb BL：9 条真实 controller source instruction 证明 8 个 root，另两条
  `0x0736A4`、`0x07445C` 保留为 excluded provenance。独立重建 299 条指令、62 个
  block、628 字节、16 条 cross-edge、7 个 opaque return 与 0 个真正 frontier；只
  晋升接入前完整 current-unknown 的 62 个 block，两条 excluded producer 继续 unknown。
- 当前 classified 6,106,406、unknown 185,050、claim 13,991、segment 16,239，语义覆盖
  97.0587%；coverage SHA-256 为
  `778a4a856cadfe222dd415950a6c356e94bf3ee64b58ab5a4ad3a00231e38458`，proof spec
  SHA-256 为 `752186af8d045b4b28e5526a5924239abc8c2eabcee27853dd2268fcb1c7483a`。
- v9 正式审计 retry2 已完成：67/67 个唯一 verifier 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 57/57，bad=0；报告/guard SHA-256 分别为
  `edf91b6fa655b885aa89ffb9c703b80564f7ba50d05d7f094e665ff232eb349b`、
  `bf804fb9f3c02ed2e4a1112de500e88c15cfcfbc54039849b6d200edb915ef34`，
  峰值 RSS 586.5546875 MiB。报告仍为 `complete=false`、175 blockers，正确反映
  unknown、bank 穷尽、七个全局门与外部 trust anchor 尚未完成。
- v8 仍保留 1 个 `indirect_pc_target`；不得把相邻 10/16 字节洞或整个 root window
  直接提升为代码。
- Goal 保持 active；下一批必须从当前 unknown 与已验证 producer/source provenance
  的交集重新冻结分母，不能复用过期候选数字。

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
  identity 由 20/22 提升到 21/22。
- `data-table-b` natural action-7 message 0 `text_ptr` A/B 闭合；bank runtime
  identity 由 21/22 提升到 22/22。

## 2026-08-21 parser / dispatcher additive coverage

- `rom-parser-bound-zero-padding-v1` 以固定 parser 边界和独立 verifier 晋升 142 段、
  198 字节逐字节零填充；其中 m4a wave alignment 为 57 段/113 字节，chapter
  terminal-to-fixed-root 为 85 段/85 字节。
- proven-roots v3 的完整 sparse dispatcher 分母额外关闭 8 个 masked residual cell、
  32 字节；proven-roots v7 的 45-cell indexed dispatcher 分母关闭 9 个完整 table
  cell、36 字节。两者只声明固定表单元，不声明运行时选择或 target 可达。
- 三批只接收完整 current-unknown range，部分重叠、分母漂移、artifact/verifier
  symlink、payload 篡改或 coverage 自引用均失败关闭。
- 当前 classified 6,106,672、unknown 184,784、claim 14,150、segment 16,247；
  coverage SHA-256 为
  `bb8ed0aeaae25c7581f740a2473506c9fe9fe10a5cd1bdb389b8675e3ede21a1`。
- 正式审计 68/68 unique verifier 均 `contract_ok=true`，ROM byte gate 58/58；报告
  SHA-256 为 `eb26328d6cc861d91cb625de6ffc229947514c6c1c158a4332b280acbabde7f0`。
  `semantic_classification_complete=false` 仍是正确结果。

## 2026-08-21 direct CpuSet-bound palette additive coverage

- 复用 `rom-direct-cpuset-gpu-inventory-v1` 的独立 direct-CpuSet verifier，从完整
  12-source 分母严格分区出 6 个已有 owner 与 6 个完整 current-unknown source；只把
  后者按 32-byte BGR555 palette 晋升，共 192 字节。
- coverage 合同绑定 candidate/promoted/preowned 三套分母哈希、六段逐范围 ROM bytes
  哈希、packed bytes 哈希与 `already_bound_operations` 的真实数组 selector；第七个
  eligible、partial overlap、缺 selector、artifact/verifier/coverage 身份漂移均失败关闭。
- `0x00405FF0` 虽同时存在 256-byte copy witness，只采用两条精确 32-byte witness，
  不扩张父记录，也不声明自然运行时、最终像素、编辑/重定位、相邻数据或 free space。
- 当前 classified 6,106,864、unknown 184,592、claim 14,156、segment 16,257；coverage
  SHA-256 为 `deac60656258e8529e5aecc2ac01927d7d67ecd82145f100a5d6976a973e83e7`。
- 正式审计 68/68 unique verifier 均 `exit_code=0`、`contract_ok=true`，ROM byte gate
  58/58；报告 SHA-256 为
  `1d3af10340e35917d0033c4f0db26b33dfbb2c754339743329f40fc0e56ff7e1`。
  `semantic_classification_complete=false` 仍是正确结果。

上述 NOP 候选现已由下节闭合。

## 2026-08-21 boot-interwork veneer alignment NOP additive coverage

- 复用 `rom-boot-interwork-v1` 的固定 BL→BX pc→ARM B producer chain、artifact 身份
  与独立 verifier，只把其显式跳过的 `[0x0009C56E,0x0009C570)` 两字节 `C0 46`
  （LE `0x46C0`，Thumb `MOV r8,r8`）晋升为 veneer alignment NOP。
- artifact 的 `skipped_interwork_padding_classified=false` scope 保持不变；coverage
  additive claim 重新绑定 exact current owner、前后 spine owner、四个 JSON selector、
  packed bytes 与 range denominator。partial/显式 primary overlap、重复 batch/kind、
  ROM/artifact/verifier 身份漂移和 verifier failure 均失败关闭。
- 不声明自然可达、全局不可达、sibling veneer、RAM 目标、周边代码、编辑/重定位或
  可分配空间。
- 当前 classified 6,106,866、unknown 184,590、claim 14,157、segment 16,257；
  coverage/proof SHA-256 分别为
  `5dc289d3b088b6f565e121ae9de2f288fa32a1c62cac4ad98027dbc9ffe3abca`、
  `5da730524544645d25657e56d84e605c47a73deede6436e8a96c6628ffca7812`。
- coverage/formal auditor SHA-256 分别为
  `9a2796a7b99f44ca5f8994486c56cfcf6bcf54579d93cafb0b0284a3c2f991f1`、
  `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`。
- 正式审计 68/68 unique verifier 均 `exit_code=0`、`contract_ok=true`，ROM byte gate
  58/58、bad=0；报告/guard SHA-256 分别为
  `ccbf80ad4c74923135d00b86538fc48dc58d206e9cc31357086d2c07f1f0f0d0`、
  `9af466c626ec5cac1d29ca4adcfd6dd1b75c1a9652781bfbbda7583efa4488ec`，峰值 RSS
  611.171875 MiB；`semantic_classification_complete=false` 仍是正确结果。

下节已闭合的候选是文件 `[0x0053D714,0x0053D73C)` / GBA
`[0x0853D714,0x0853D73C)` 的 40 字节：完整 `[0x0053D644,0x0053D73C)` 31×8-byte
SJIS lookup 分母中的 rows 26..30，五个 `<HBBI>=(0,0,0,0)` empty lookup rows。必须
绑定 31-row lookup loop、renderer parser、full-table/row bytes、前后表边界和完整
current-unknown；不得因全零或历史命名把它称为 reserved、free space、自然不可达、
可编辑或可重定位。

## 2026-08-22 SJIS empty lookup rows additive coverage

- 文件 `[0x0053D714,0x0053D73C)` / GBA `[0x0853D714,0x0853D73C)` 的 40 字节
  是完整 `[0x0053D644,0x0053D73C)` 31-row lookup 的 rows 26..30；五行均为
  `<HBBI>=(0,0,0,0)`。coverage 只新增一个
  `dialogue_font_sjis_empty_lookup_row_bytes` claim，并同时绑定真实 lookup/parser、
  左右 owner、完整表/行/范围哈希、两套既有独立 verifier 与 current-unknown。
- 窄语义仅限五个冻结 empty lookup rows；不声明 padding、reserved/free space、
  global unreachable、natural runtime、全消费者、完整 Unicode、编辑或重定位安全。
- 当前 classified 6,106,906、unknown 184,550、claim 14,158、segment 16,257
  （97.0667% / 2.9333%）。coverage/auditor/proof SHA-256 分别为
  `3b562213df931df21e1bf237226c73279b883d427d02dccbf54e063bd18e3dd7`、
  `a0109d2443858b09f9193f80a45dafa046e9661c863440b6ddcb42e651936f29`、
  `ba3f4a3ecc51931478bdacc4f7124d68c3faeac4c2262f2f36be926088dc1f29`。
- 正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard
  SHA-256 分别为
  `ff6087c3313dec3b71f16d96af9aa503844a44aa4ea1a2f286e21b98dc5c93bc`、
  `0260f58160f8f6f1ac108bf5254179fa6f443c4d6cfca43173fc9776211919ca`，峰值 RSS
  614.55078125 MiB；`semantic_classification_complete=false` 仍是正确结果。

## 2026-08-22 motion-spawn→sequence-descriptor alignment-gap additive coverage

- 文件 `[0x0053EF2E,0x0053EF30)` / GBA `[0x0853EF2E,0x0853EF30)` 的两个
  current-unknown `00` 字节恰好连接左表终点和下一 4-byte 边界。coverage 新增一个
  `motion_spawn_sequence_descriptor_alignment_gap_bytes` claim。
- 左侧冻结 `[0x53EE98,0x53EF2E)` 的 15×10-byte motion table、15 个完整 record 及
  索引 14 的 `<hhhhh>=(-1,0,0,0,0)` 显式 terminator；右侧冻结
  `[0x53EF30,0x53F140)` 的 22×24-byte sequence-descriptor 完整 source。右侧既有
  primary owner 只覆盖 `[0x53EF30,0x53F138)`，完整 528-byte source 与 520-byte
  primary owner 分开验证。
- helper 同时绑定左右 owner ID/range/class、规范 artifact/manifest/verifier/upstream
  test 路径与哈希、两套独立 verifier 输出、ROM/表/候选/范围分母哈希、对齐公式和
  current-unknown。partial/primary/secondary overlap、重复 batch/kind、非规范同哈希副本、
  symlink/out-of-tree、identity/selector/terminator/table 漂移均失败关闭。
- 窄语义只说明这两个字节用于达到下一 4-byte 边界；不声明 padding、reserved/free
  space、自然运行时可达、全局不可达、编辑/重定位安全、可安全分配、邻接字节、
  额外表字段或消费者完备性。
- 当前 classified 6,106,908、unknown 184,548、claim 14,159、segment 16,257
  （97.0667% / 2.9333%）。coverage/auditor/proof SHA-256 分别为
  `7b108bf257cc99e9d4af7a47824b51e79f23e823fc0e1fe6d59fbd47500a8eab`、
  `6fbf0059d76116a9d9bb5d1313223dcc942cadf29c5fcbd3682292fa632f53a6`、
  `57644273a2cf7e5f7f9bdfdad350cef0f21a99bb5137fcfa0900fc9d62b5b903`。
- 正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard
  SHA-256 分别为
  `3844c1ff49a4a2da5142f517ee3066a15eccadf2b87e864407a7bc0e369bdd89`、
  `66ae9eead07daaed3ac9485d8b75a6ba29eae1e901e7c2d9c65c47c1aafd52a7`，峰值 RSS
  584.328125 MiB；`semantic_classification_complete=false` 仍是正确结果。

## 2026-08-22 battle-presentation binding→tile-assets alignment-gap additive coverage

- 文件 `[0x005A320A,0x005A320C)` / GBA `[0x085A320A,0x085A320C)` 的两个
  current-unknown `00` 字节恰好连接左表 fixed-count endpoint 与下一 4-byte 边界。
  coverage 新增一个 `battle_presentation_tile_assets_alignment_gap_bytes` claim。
- 左侧冻结 `[0x5A2EF4,0x5A320A)` 的 79×10-byte battle-presentation binding table，
  末条 index 78 为 `glyph_count=2`、glyph IDs `[162,163]`，终点不是 terminator；
  右侧冻结 `[0x5A320C,0x5A4708)` 的 79×68-byte tile-assets table 及其首条 17-u32
  record。helper 同时绑定左右 owner、canonical artifact/manifest/verifier/test、
  表/候选/范围分母 SHA、两份独立 verifier report、精确 current-unknown 与对齐公式。
- 窄语义只说明这两个字节用于达到下一 4-byte 边界；不声明 padding、reserved/free
  space、自然运行时可达、全局不可达、编辑/重定位安全、可安全分配、邻接字节、
  额外字段语义或消费者完备性。
- 当前 classified 6,106,910、unknown 184,546、claim 14,160、segment 16,257
  （97.0667% / 2.9333%）。coverage/auditor/proof SHA-256 分别为
  `66f129450f31eb1ff9f4e931c219a463710b5caee21c0b1aa7f9c4ad3ffe70a6`、
  `2c604c710fc058c7ad9e07653a38385726671ae5940eb54f9b204df1c4567fe4`、
  `dc88f57780fde125b53b1ccffe29cdf1c3d0aecb880f0de30bb4f12f513c0782`。
- 正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard
  SHA-256 分别为
  `6839a623b83967b523f6aca76f5f420fcee326ef2fbbc11f19ca91a0a78a03c1`、
  `77a31c1b757eb5ab702fcbf62e466a3c91393ecdc027b72a2508ff98e45f34ea`，峰值 RSS
  593.7890625 MiB；`semantic_classification_complete=false` 仍是正确结果。

## 2026-08-22 runtime-state selector→handler-pair alignment-gap additive coverage

- 文件 `[0x0053E696,0x0053E698)` / GBA `[0x0853E696,0x0853E698)` 的两个
  current-unknown `00` 字节恰好连接 256×1-byte selector 的 fixed-count endpoint 与
  下一 4-byte 边界。coverage 新增一个
  `runtime_state_handler_table_alignment_gap_bytes` claim。
- 左侧完整表 `[0x53E596,0x53E696)` 的 SHA-256 为
  `4c1ad8b8ac883eb301132c83258ba1e1216b2e131c9ce9866d0de62956d5a01b`；三段
  ownership 必须连续覆盖，且 `[0x53E5A8,0x53E5B3)` 的 LZ77 record 38 primary
  不得被覆盖。右侧 `[0x53E698,0x53EE98)` 的 256×8-byte handler-pair table SHA-256
  为 `20e4727cf65dca82626ffc9637cb36561d5851971500b22a282c5a8c65c7c945`，由完整
  map-events bank 行向量及精确独立 verifier report 重建。
- 窄语义只说明这两个字节用于达到下一 4-byte 边界；不声明 padding、reserved/free
  space、自然运行时可达、全局不可达、跨表 dataflow、编辑/重定位安全、可安全分配、
  邻接字节、额外字段语义或消费者完备性。
- 当前 classified 6,106,912、unknown 184,544、claim 14,161、segment 16,257
  （97.0668% / 2.9332%）。coverage/auditor/proof SHA-256 分别为
  `a061b3f9fa9551d34f4a3add7b2b062152cc2c2f50f439dd75c210c004e3e1de`、
  `8dccae1f87c4137228551096c1de14878b1d96b7a733be9748598542a410f7c4`、
  `b8527d82fb35db5ad53e58fed96c873a95cf9b594c2ffdfba81c2d96434d81e4`。
- 正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard
  SHA-256 分别为
  `63520dee7225e55e24dbcb71f5c724dea2cdadeba1a2f5e591edf353dd08a529`、
  `ce11dfd822638d1617a148e7856262c7e566efd20000514404930c1442d6eab9`，峰值 RSS
  616.96484375 MiB；完整 proof 测试 49/49 通过，
  `semantic_classification_complete=false` 仍是正确结果。

## 2026-08-22 Cutscene OBJ palette→definition alignment-gap additive coverage

- 四个固定 Cutscene OBJ resource root 各产生一个精确两字节范围：
  `[0x0012DEFA,0x0012DEFC)`、`[0x0012E442,0x0012E444)`、
  `[0x0012E95E,0x0012E960)`、`[0x0012ED6E,0x0012ED70)`；8 个 ROM 字节均为
  `00`。独立 verifier 自行解析两张根表、slot 0、四条 type-0x10 palette stream、
  parser endpoint、4-byte alignment equation 与 rooted first definition record，并
  绑定完整表/行/范围/压缩流/解压流哈希。既有 28-range / 400-byte Cutscene source
  artifact 未被改写。
- 新增 4 个 `cutscene_obj_palette_definition_alignment_gap_bytes` additive claim，
  range-vector / packed-byte / claim-denominator SHA-256 分别为
  `374c247199713cc2e172ebff551ae7a5e40df4289437f45cf76c814e84bed5e6`、
  `af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc`、
  `dae7c87fa52a1e1e9f1a72279fc7839d8f26f07b126e80aca07450286abcc137`。
  不得由零值或邻接关系外推 padding、reserved/free/allocatable space、自然运行时
  可达、完整 Cutscene gap 分母、未知 definition 字段语义、最终像素、编辑或重定位
  安全。
- 当前 classified 6,106,920、unknown 184,536、claim 14,165、segment 16,257
  （97.0669% / 2.9331%）。coverage/auditor/proof SHA-256 分别为
  `f77fbbf6271d04989c0e16ac36287cf6bcd4d2454d9549eb5fbed693a757c33f`、
  `4908778b32fa5b2fc8473f88a8f3fa44f0541b5c9110d57260c3530ff38d65b4`、
  `8b1093446d04cd68f83ef5cf2d978cb618540ca9bf0203ba57ee3487a9fd1ba7`。
- 正式审计实际执行 69 个唯一结构化 contract（59 个 ROM byte 加 10 个 bank），
  69/69 均 `exit_code=0`、`contract_ok=true`；ROM byte gate 59/59、bad=0、175
  blockers。proof spec 的 gate verifier 配置总数为 70，另 11 个旧 gate verifier
  只有哈希绑定、不属于本次结构化执行分母。report/guard SHA-256 分别为
  `6238a8f64de72cea9e0536d4a72f7b6825d0ea4dc1ac63b888d9516b9544f555`、
  `ef9da54d81f0f1fe12e30fabefc6615de1476b274a964b961e9b641458f95ced`，峰值 RSS
  616.93359375 MiB。报告仍为 `complete=false`、`claim_status=incomplete`，
  `semantic_classification_complete=false` 仍是正确结果。

## 2026-08-22 positions auxiliary dispatch additive coverage

- `rom-positions-aux-dispatch-v1` 独立重建 48 groups × 3 variants 的 144 张
  16×4-byte auxiliary cell table，共 2,304 cells / 9,216 bytes；范围分母、ROM
  原字节和 handler 读取足迹均由独立 verifier 失败关闭复验。
- byte 0 只声明为 bounded dispatch selector；bytes 1..3 只声明为
  handler-dependent raw operands，不赋予统一业务语义。144 个完整范围均从
  current-unknown 提升；variant header 和末尾 `[0x00596204,0x00596D5C)` 的
  2,904-byte gap 保持未知。
- 该里程碑 classified 6,116,136、unknown 175,320、claim 14,309、segment 16,401
  （97.2134% / 2.7866%）。coverage/auditor/proof SHA-256 分别为
  `8bf64bbe0e9ca124f867cb7e97af9ee439a89e636450ae54af479985268be6ca`、
  `08f92ffbd7fe5cacb51a15ba5d30436f1467f56cfe35a088596e96788bb98718`、
  `384c13515ea65a93e1dea73add93503ea1c159f2126c82ab41ae7dc89395169b`。
- 正式审计实际执行 70 个唯一结构化 contract（60 个 ROM byte 加 10 个 bank），
  70/70 均 `exit_code=0`、`contract_ok=true`；ROM byte gate 60/60、bad=0、175
  blockers。report/guard SHA-256 分别为
  `e459ab6ae67b944141bbd18e148d1b135daaf557f706efda2f1c159933e76482`、
  `20eb2e4e731ba2b193c27b8aa391bc671c2a8d56c77bdcaac69a199af7e9d969`，峰值 RSS
  639.55859375 MiB。报告保持 `complete=false`、`claim_status=incomplete`；不声明
  自然可达、runtime group/variant bounds、统一字段语义、ABI、编辑/写回/重定位、
  next header、末尾 gap 或 free space。

## 2026-08-22 battle gameplay sound selector additive coverage

- `rom-battle-sound-selector-v1` 独立重建 `[0x0053E496,0x0053E596)` 的
  256×u8 selector table，固定表 SHA-256
  `2f77582ae5eea1711b079fc8ce67d36e95ec68bf0e2bd0a3d5780eb3d9819b5d`，并逐条
  验证五条直接 little-endian pointer-literal 消费路径。artifact manifest 位于
  `artifacts/rom-battle-sound-selector-v1/manifest.json`。
- coverage 只新增一个完整 primary claim：256 个接入前 current-unknown 字节均分类为
  `battle_gameplay_sound_selector_table`；左边 `0x53E495` 保持 unknown，右边
  `0x53E596` 仍由既有 `battle_effect_runtime_state_sequence_table` owner 持有。
- 不声明自然全索引/全路径可达、computed/RAM/indirect 消费者穷尽、所有 selector
  consumers 穷尽、零/非零或 gameplay 值语义、左邻结构关系、右邻业务关系、完整播放
  例程、播放成功、全部音频穷尽、编辑/写回/重定位或 free/allocatable space。
- 该里程碑 classified 6,116,392、unknown 175,064、claim 14,310、segment 16,402
  （97.2174% / 2.7826%）。coverage/auditor/proof SHA-256 分别为
  `6af3216caf853045b0590389a11abf161e4e489a183f308d940db9e64a67e9b7`、
  `6a2da86067afbb413a355df4d70e4b13b039dd0c213fff47fce5bed4b66107b4`、
  `d235fb19024e62b7f6c7bf6e7c62935e6422e93f3940574c8730034fac8c7ca3`。
- 正式审计实际执行 71 个唯一结构化 contract（61 个 ROM byte 加 10 个 bank），
  71/71 均 `exit_code=0`、`contract_ok=true`；ROM byte gate 61/61、bad=0、175
  blockers。proof spec 的 gate verifier 配置总数为 72，其中 11 个旧 gate verifier
  只有哈希绑定。report/guard SHA-256 分别为
  `6fc14885e20e4e63600d2f04130678cbe16f011d85ae2cb58f8968f36b3706c3`、
  `fad0d92819377e6b16cccd6cbbbe8967c7d4eb0ef15b482fdb6bf170be0b3140`；峰值 RSS
  648.578125 MiB。报告保持 `complete=false`、`claim_status=incomplete`。

## 2026-08-23 battle-condition records additive coverage

- `rom-battle-condition-records-v1` 独立重建完整 47 battles × 3 variants ×
  `0x44`-byte 物理表、141 variants、1,128 predicate slots 及 raw interpreter layout；
  canonical manifest SHA-256 为
  `c9ea59da9e2f870446f51a0424317ca6dfb23daa67a348bb0a78093b86d3c079`。
- coverage 只提升接入前 current-unknown 的 84 个 fragment / 2,772 bytes：41 个 raw
  variant-prefix fragment / 164 bytes 与 43 个 predicate fragment / 2,608 bytes。
  既有 fixed-table 和 positions-aux primary owner 保持不变；右侧
  `[0x00596CCC,0x00596D5C)` 的 144-byte zero gap 继续 unknown。
- 不声明自然 battle/variant 可达、全消费者穷尽、prefix/predicate 业务语义、handler
  4/5 自然使用、编辑/写回/重定位或 free/allocatable space。
- 当前 classified 6,119,164、unknown 172,292、claim 14,394、segment 16,483
  （97.2615% / 2.7385%）。coverage/auditor/proof SHA-256 分别为
  `dd2a64883da6a5b561336a70d90ceb97a6ca7eb282b3bd09b0f3ec2d9ed0d156`、
  `b81ea9a433d19fe9d64068f79f4ca692ab70764715f22ded46c64e2a6f508039`、
  `a6032881de87c4faa045fbc5fb15b05043a1971da24a748114da70603f6074b3`。
- 正式审计执行 72 个唯一结构化 contract（62 个 ROM byte 加 10 个 bank），72/72
  均 `exit_code=0`、`contract_ok=true`；ROM byte gate 62/62、bad=0、175 blockers。
  proof spec 的 gate verifier 配置总数为 73，其中 11 个旧 gate verifier 只有哈希绑定。
  report/guard SHA-256 分别为
  `15191084bcf75fa7908708f25d69cb436cd36f99b4815eeecc2926c64c4c8b41`、
  `3aeef7dc59c22f965b567641419b27d773cc61fbb30a0abba8f95c6d5caf135f`；正式审计耗时
  2,828.498 秒、峰值 RSS 623.84375 MiB。报告保持 `complete=false`、
  `claim_status=incomplete`。用户已要求在此里程碑后暂停；Goal API 仍为 `active`，收到
  明确恢复指令前不得继续新逆向写入。

## 2026-08-23 CFG proven-roots v10 additive coverage

- `rom-cfg-proven-roots-v10` 固定全 ROM 三条 target-limited Thumb BL producer 分母；
  独立 verifier 不导入 exporter，自行重建 source bounded worklist 264 instructions /
  35 blocks / 580 bytes / 26 external call edges / 0 frontier，以及 `0x08B278`
  target worklist 36 instructions / 7 blocks / 72 code bytes / 0 frontier，并验证两条
  PC-relative LDR 实际消费的 8 literal bytes。
- coverage 只提升接入前 current-unknown 的 7 个完整代码 block 和 2 个完整 literal
  claim，共 80 bytes。manifest/payload SHA-256 分别为
  `7bc6a70cb8409b44075df6e1031b9d80bdb19898605735dedd2a2acf9d495991`、
  `5edad0689b630e68c6ee304aac2f56e3d5c83e65ee7c2c7a7308e0fd980fd50e`。
- 不声明自然运行时可达、全局代码图、间接目标穷尽、函数 ABI、业务语义、编辑/
  重定位或 free/allocatable space。
- 当前 classified 6,119,244、unknown 172,212、claim 14,403、segment 16,492
  （97.2628% / 2.7372%）。coverage/auditor/proof SHA-256 分别为
  `c65ec320a432681600bda916254f3265489829ee2f0b8b885b885b5436d35396`、
  `e440b797a04d8186a854de5d174a46dbcb459e0a0abf515a0249ea4121a23c8f`、
  `75d5e48249a3ee200dd8b741faf2c304e390d74614a25c8a161746300d8017e1`。
- 正式审计执行 73 个唯一结构化 contract（63 个 ROM byte 加 10 个 bank），73/73
  均 `exit_code=0`、`contract_ok=true`；ROM byte gate 63/63、bad=0、175 blockers。
  proof spec 的 gate verifier 配置总数为 74，其中 11 个旧 gate verifier 只有哈希绑定。
  report/guard SHA-256 分别为
  `0d761f8cdc7d21de305af6295d518981a0b6bafb242e5b4e433c83e5a4aeacda`、
  `915828bb3b01d54c7c7802ca482d6416df07ce2702e7531e0ee17186a7f94822`；正式审计耗时
  2,592.267 秒、峰值 RSS 615.17578125 MiB、非降级。报告保持 `complete=false`、
  `claim_status=incomplete`。该暂停点已由用户 2026-08-27 的明确恢复指令取代。

## 2026-08-27 DirectSound pitch lookup 344-byte additive coverage

- 旧 318-byte/90-byte 候选估计已被实际五范围合同取代：16-byte mixed Thumb/ARM
  high32 helper、92-byte closed Thumb consumer、8-byte consumed literals、180-byte
  u8 scale descriptors 与 48-byte（12×u32）frequency table，共 344 bytes。
- 独立 verifier 重建两个 target-limited raw Thumb BL producer、44 instructions / 5
  blocks / 0 frontier 的 consumer、5 instructions / 2 blocks / 0 frontier 的 helper、
  两条 PC-relative literal 与完整 key/fine/index 域。producer bytes/source membership
  仅作 provenance，仍保持 unknown；不声明自然运行时、全局 caller/code/indirect
  或 computed/RAM consumer、播放行为、编辑、写回、重定位或 allocatable space。
- canonical manifest/payload/binary SHA-256 分别为
  `61f58bd4309d3b63389bdd09ddd62281dee6fe6ce91bcce0c351ce703012805d`、
  `ea54c37199704e58f4fcfb0c7dccf3227a23c6363692a4f238ebd807a8003d85`、
  `cdf62999570f66a283667ed85f535da4e04f8cbf5ea8a33ef66d1bee8ab0e850`。
- 当前 classified 6,121,624、unknown 169,832、claim 14,471、segment 16,582
  （97.3006% / 2.6994%）。coverage/auditor/proof SHA-256 分别为
  `922e06e9b195a31ae6a8ab8c03cb06159aee7218bc4268ac56e22c729b740de6`、
  `eb98accbd486377e4d5cf00f2708f7fff75b1b22319ed4dc1d7c24b7abb582d2`、
  `cf242a73211f4cda07a70c6c3bc0f59d8f5a9c995334d9fecd6bf6b808df2c0a`。
- 正式审计执行 78 个唯一结构化 contract（68 个 ROM byte 加 10 个 bank），78/78
  均 `exit_code=0`、`contract_ok=true`；ROM byte gate 68/68、bad=0、175 blockers。
  report/guard SHA-256 分别为
  `9ff9072dc1e501bd6bef9f792f6a318640ea9b8594719effa514288595d4714e`、
  `eadf80d080f795495304028e9ee8f4074a1ff34e768571e7152b917b278fe133`；审计耗时
  2,702.786 秒、峰值 RSS 625.96875 MiB、非降级。报告保持 `complete=false`、
  `claim_status=incomplete`。
- 当前首选缺口为 PSG noise lookup 的最多 220 个 current-unknown 字节：consumer
  `[0x09B494,0x09B534)` 与 table `[0x46475C,0x464798)`。必须先闭合 producer、
  raw Thumb CFG/literal 与完整 key→index 0..59 域；任一 frontier 或分母缺口均保留
  unknown。Goal active；Goal API 不返回套餐余额百分比，5% 阈值仍不可验证。

## 2026-08-28 PSG frequency lookup 226-byte additive coverage

- canonical artifact 位于 `artifacts/rom-psg-frequency-lookup-v1/`；manifest、payload、
  binary SHA-256 分别为
  `4fffbcc7e252595834adb368d10b3ce8f13323aee18cc518d98e0ff9c519575f`、
  `d2631b1a65a2e9fa0114dbd76a4e2c89853e3b2f402a491fdbc466e79dacd733`、
  `e625a5fcc208a971a1ec98723f12b863a707fa9dd3ba8442f7f6d86b3099623b`。
- 五个 current-unknown promotion range 共 226 bytes：154-byte bounded Thumb code、
  12-byte consumed pointer literal 与 60-byte channel-4 noise descriptor table；
  `[0x09B4C6,0x09B4C8)` 两字节保持 unknown。initializer→slot→trampoline 只作
  provenance，不外推 RAM/computed producer、writer、indirect caller、自然可达、
  非目标表业务语义、播放、编辑、写回、重定位或 allocatable space。
- 后续 19-byte fixed-consumer u8 triplet lookup 已完成；只晋升唯一 pointer literal
  `[0x075C0C,0x075C10)` 与五条 3-byte record `[0x53DFB0,0x53DFBF)`，consumer
  code 保留 generic CFG owner，四段 literal pool 与右侧 65 bytes 保持 unknown。
- 随后四段 artifact-bound align4 gap `[0x061D62,0x061D64)`、
  `[0x061D7A,0x061D7C)`、`[0x061DEA,0x061DEC)`、
  `[0x09B4C6,0x09B4C8)` 完成，共 8 bytes、4 claims。verifier/report SHA-256 为
  `befdf8545a0d2763514996935676a1a6384967174dcca119e0da62b71bd4da66` /
  `344e3fe2660a48342b5f82bb9d7aeefc28c1f4fe0b99fc3f23bdb2a894f3f662`；不声明
  padding、NOP、reserved/free/allocatable space、自然可达、compiler authorship、
  编辑、写回或重定位安全。
- MPlayMain 修正版已完成：只晋升 600-byte code `[0x09A42C,0x09A684)` 与
  12-byte consumed literals `[0x09A688,0x09A694)`；2-byte preowned veneer 保持原
  owner，紧邻 2-byte gap 继续 unknown。旧 414-byte envelope 已证实截断控制流并
  作废。artifact/边界与非声明项见 `notes/rom-mplaymain-scheduler-20260828.md`。
- SoundMain relocated source 与三个独立 align4 gap 已完成，累计只晋升 916-byte
  mixed ARM/Thumb code、8-byte consumed literals 与 6-byte gap；既有 return veneer
  保留原 owner。完整证据见 `notes/rom-soundmain-relocated-cfg-20260828.md`。
- M4A initializer-chain 已完成：六个 primary claim 只晋升 390-byte bounded Thumb
  code 与 128-byte consumed literals，共 518 bytes；`0x061E28` raw producer 与
  `[0x09B1E6,0x09B1E8)` gap 继续 unknown。完整证据见
  `notes/rom-m4a-initializer-chain-20260829.md`。
- MP2K note allocator 已完成：四个 primary claim 只晋升 550-byte bounded Thumb
  code、8-byte consumed literals 与 4-byte initializer-consumed entry pointer，共
  562 bytes；四段相邻排除范围合计 68 bytes 保持 unknown。独立 worklist 为
  269 instructions、66 blocks、99 internal edges、5 external edges、2 returns、
  0 frontier；consumer command 域固定为 0..48。完整证据见
  `notes/rom-mp2k-note-allocator-20260829.md`。
- MP2K dispatcher 已完成：四个 primary claim 只净晋升 46-byte root code、12-byte
  table tail、40-byte handler code 与 4-byte consumed literal，共 102 bytes；五段
  既有 owner 共 238 bytes 只作 provenance。完整 bounded CFG 为 129 instructions、
  260 code bytes、36 blocks、65 internal edges、1 external edge、1 return、0 frontier
  与 18 条 dispatch edge。两个 2-byte gap 仍 unknown，历史 candidate-027 的整体
  rejected 状态未改写。完整证据见 `notes/rom-mp2k-dispatcher-20260829.md`。
- 当前 classified 6,124,601、unknown 166,855、claim 14,507、segment 16,617
  （97.3479% / 2.6521%）。coverage/auditor/proof SHA-256 分别为
  `22f8f88ca0929468289b749cb94b4aaa4c47d7a53fa68fe10cb93c9a01816839`、
  `ea5f1ad59d783c2cd75c1c7eb380c0eacd1c7001532a145e39949ba22f47824f`、
  `823e1b23940044a60fda275772f04e0cef05bf88a5fdd8fe024f53aa17092efa`。
- 正式审计执行 87 个唯一结构化 contract（77 个 ROM byte 加 10 个 bank），87/87
  均 `exit_code=0`、`contract_ok=true`；ROM byte gate 77/77、bad=0、175 blockers。
  report/guard SHA-256 分别为
  `3321709fa8440c8857d895b1cb467a3959989be0cc639abfe439bdb91e43ddc0`、
  `b6e177ccff24a0cb19ad6e500968c4905bae3a0758abd466a2174cfd4bf8d036`；耗时
  3,077.844030 秒、峰值 RSS 638.47265625 MiB、非降级。
- 当前首选缺口是拆分后的 CGB helper 与 `CgbSound`：先分别冻结
  `[0x09B53C,0x09B5F4)` 和 `[0x09B5F4,0x09BA3E)` 的 bounded closure，共享同一
  immutable precoverage；两个 artifact 独立接受后，再用已有 artifact-bound gap
  verifier 分类其中九个 2-byte align4 structure gap，统一执行一次 coverage/proof/
  formal。不得重开或直接晋升 1,960-byte 连续包络。
- 2026-08-30：CFG proven-roots v13 已完成 canonical artifact、dependency-first
  immutable bundle、coverage、proof 与 formal。固定目标 `0x080651F8` 的
  target-limited 全 ROM 直接 producer 分母只有已证 source 中的 `0x080614D0`
  一条 Thumb BL；只晋升 312-byte bounded Thumb code 与 80-byte consumed
  literals，共 392 bytes。`[0x0652DE,0x0652E0)`、
  `[0x06536A,0x06536C)` 两个 2-byte hole 继续 unknown；`0x065368 bx r0`
  保持唯一 unresolved indirect-PC frontier。canonical classified/unknown/claim/
  segment 为 6,126,775 / 164,681 / 14,558 / 16,673（97.3825% / 2.6175%），
  coverage SHA-256 为
  `e8787f8e200e84b2966c6f6b8c70ea164a0f90d81348d88e5daa614ea3cb8004`。
  正式 report/guard SHA-256 为
  `6bced154df1d4ca3940f597f64ef36bb5ebd8c3f9d995f62fce34ad92b8793c2` /
  `23893d0b4996fac334cc4b93596e1e3a28ee5cc7302636c5abd5b8b34037d369`；
  90/90 唯一结构化 contract 全通过，ROM byte gate 80/80、bad=0，报告正确保持
  `complete=false`、175 blockers。
- 2026-08-30：上述 V14 草稿已由独立 preflight、TDD、immutable bundle、canonical
  coverage、proof 与 formal-r2 取代。五条 V12/V13 accepted producer 证明
  `0x0624C0` 与 `0x062510` 双 root；只晋升 120-byte code + 40-byte literals，
  两个 `bx r0` 继续是 unresolved frontier，0 hole。V14 接入后 classified/unknown/claim/
  segment 为 6,126,935 / 164,521 / 14,562 / 16,677（97.385009% / 2.614991%）。
  formal-r2 91/91、ROM gate 81/81、bank 10/10 全过，仍正确为 `complete=false`、
  175 blockers；report/guard SHA-256 为
  `f9c2a1014b62dc7449db7f35965a1d42db01eb4972e43c81d961688e0befa786` /
  `3786c8d4e51c8070a021064433535429dc22efe5dcfb84ae4e156fe1039d7fa4`。
- 2026-08-30：V15 root-isolated packet 已完成 preflight、TDD、canonical artifact、
  coverage、proof 与 formal-r2。接受 `0x0611F4`、`0x0618FC`、`0x08B6F0`、
  `0x09A3E0` 四根，拒绝 `0x09C0F4`；只晋升 398-byte Thumb code 与 52-byte
  consumed literals，共 450 bytes。三处 indirect-PC frontier、六段合计 386-byte
  holes 与 rejected range 继续 unknown。V15 接入时 classified/unknown/claim/segment 为
  6,127,385 / 164,071 / 14,572 / 16,693（97.392162% / 2.607838%）。formal-r2
  92/92、ROM gate 82/82、bank 10/10、bad=0，仍正确为 `complete=false`、177
  blockers；report/guard SHA-256 为
  `3002d624f4a5354c4bf0f410aa7923c8377c33e96c263d6df6299ef67deefb63` /
  `b10f03289ab3b941a3bb3d0dd30edc806816dc5a262224ec5137a28e94ada220`。
- 2026-08-30：menu portrait LZ77 endpoint→palette gap 已完成。独立 verifier
  从 896 条 pointer-reachable LZ77、74 个菜单资源与 70 段物理 palette 分母重建
  52 段 / 110 bytes，长度分布 16×1、14×2、22×3，全部为零、紧邻且右端 align4；
  110 个单字节变异均能触发语义 guard。canonical classified/unknown/claim/segment 为
  6,127,495 / 163,961 / 14,624 / 16,693（97.393910% / 2.606090%）；coverage /
  proof SHA-256 为
  `c2798b35f4ac21f170c9a7575cbf10118aad98d58efbebf3d59ca9f599216133` /
  `eaa8b7f2b37feaa9686d83c84f6fd16672e6b6ae3038e0ccf16ece96c4698eb2`。
  formal report / guard SHA-256 为
  `92b4b471b972bcc789848f78192f8c5162deeeb0ab0c1bce77e818694e88ba3a` /
  `e0985d49922e2473229c8c28c4182013e9497718977e07807a52885e76b2b66e`；
  93/93 实际唯一命令、ROM gate 83/83、bank 10/10、bad=0，报告仍正确为
  `complete=false`、177 blockers。
- 2026-08-30：tile-BG LZ77 endpoint→palette source gap 已完成。独立 verifier 从
  896 条 pointer-reachable LZ77、79 个 descriptor、236 个 palette entry、108 个 raw
  range / 107 个 merged claim 的完整分母重建 84 段 / 165 bytes；长度分布为 31×1、
  25×2、28×3，全部为零、紧邻且右端 align4，165 个单字节变异均失败关闭。canonical
  classified/unknown/claim/segment 为 6,127,660 / 163,796 / 14,708 / 16,693
  （97.396533% / 2.603467%）；coverage / proof SHA-256 为
  `1ddc10027b7642399bce8c1a07871ce3a141ca6f2b323c19a650469274cb2df4` /
  `b7423201e3f84280c5556d8d42b95de6c03c07fefcfc85f3d05bf71d5c614c57`。
  formal report / guard SHA-256 为
  `37ef4055b419cb520e3bbaf953ca81f3ae72fdc2613032235498ec298dc87832` /
  `7d7fd44829fa1359c619182f2103b3856d359a63dc6f143113a10eb850592779`；
  94/94 实际唯一命令、ROM gate 84/84、bank 10/10、bad=0，报告仍正确为
  `complete=false`、177 blockers。两个非零 long gap 与七个 heterogeneous short gap
  正确保留在合同外。
- 2026-08-30 当时的下一缺口为 boot Thumb code→consumed-literal 的 12 段 / 24 bytes；必须从
  frozen boot artifact 的 27 code / 22 literal 完整分母独立投影全部正长度邻接，
  并从 raw ROM 重解 terminal flow，不能由 live coverage 反向发现。其后可做
  battle-effect LZ77→component 的 12 段 / 20 bytes；异构 direct-CpuSet/reuse palette
  gap 仍必须拆包。V15 386-byte holes、scheduler lifecycle frontier 与
  `0x061F14→0x09BA68` source-membership 缺口仍不适合短包整体晋升。
- 2026-08-31：上述 boot 包已完成。12 段均为 2-byte `0000` align4 boundary，独立
  verifier 从完整 27 code / 22 literal / 77 binding 分母及 raw Thumb terminal flow
  重建；canonical classified/unknown/claim/segment 为
  6,127,684 / 163,772 / 14,720 / 16,693（97.396914% / 2.603086%）。formal report /
  guard SHA-256 为
  `b98828aa94f6704cca82bca876b9154f5e950fc1afcd2df535f7e833f98d00d8` /
  `75afa7d5f183e08f4efb064d7fb0aadcfd4869694643871d7e096b2f8e3fcab0`；
  95/95 实际命令、ROM gate 85/85、bank 10/10 全部通过。下一阶段不再单独处理几十
  字节 gap，而是批量聚类 163,772 unknown，并优先选择预期净增至少 1,000 bytes 的
  可验证语义族。
- 2026-09-01：首个批量里程碑已完成。三个冻结 accepted CFG 的 Thumb PC-relative
  LDR literal 分母经独立 raw decoder 重建：v2 为 1,699 words / 6,796 bytes，
  proven-roots v6 为 745 / 2,980，proven-roots v1 为 349 / 1,396；目标零重叠，合计
  946 merged claims / 11,172 bytes。canonical classified/unknown/claim/segment 为
  6,138,856 / 152,600 / 15,666 / 17,182（97.574488% / 2.425512%）。coverage / proof
  SHA-256 为
  `66a5e95bd2927f9db13435f6862a052ad60634cfbd3a8b5dfad07459a4a12329` /
  `85962384fda90272f4d89f6ca523b1055b3963725669f4c13c8772faa8a56f5d`；formal-r2
  report / guard SHA-256 为
  `16c49cbb5cc95168b2e20b35b1a2f2fc6155638c5e27db59af1b88eb704143f7` /
  `abf5dcffb1cc326364c860badb15f5a7c29cc16eedff6ec94d5e22147ef2ba9f`。
  98/98 实际 verifier、ROM gate 88/88、bank 10/10 全部 contract-ok；formal-r1 因
  verifier 成功字段和 post-promotion identity 接入错误被保留为失败证据并由 r2 取代。
  下一步必须从 152,600 unknown 重新聚类，不得继续使用 163,772 的旧收益排序。

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

### 硬指标（2026-08-06 历史快照）
当时为 phase 10/18、pixel 12/18、13/22 runtime + 9/22 code_verified。当时完成的是
既有定义范围内的静态目录和若干专项指标；实体 GBA 当时及当前均为 0/1，未达成。
该历史快照不代表全 ROM 字节语义覆盖或逆向工程完成。

## 2026-08-06 历史成本估计（已被 2026-08-09 状态取代）

以下仅记录当时的 13/22 runtime 身份阶段估算；9 个 bank 标签后来已到 22/22，
但这不改变当前全记录/字段穷尽为 0/22、ROM 语义未完成及实体 GBA 0/1 的门禁。
当前缺口以证明规范为准。

按当时可推进路径估算，剩余 7/22 bank 身份 closure 使用“复用已验快照、固定两次
A/B”约需每项 1–3 小时；尚无入口者另需 route discovery。实体 GBA 当时无法推进。

原 38–60 小时估算随后被 controlled phase 复用缩短，并已被后续实际进度取代，
不得再用于估算当前严格完成目标。

## 2026-09-01 consumed-literal 第二批里程碑

- 新增四个失败关闭 packet：CFG v3 1,220 bytes、proven-roots 合并包 1,256 bytes、
  battle controller 536 bytes、v2 shadowed consumer slice 308 bytes；合计 3,320
  个此前 unknown 字节、274 个不重叠 ranges。
- authoritative classified/unknown/claim/segment 为
  6,142,176 / 149,280 / 15,940 / 17,344，语义覆盖 97.627258%。
- 非降级 formal 为 102/102 实际结构化 verifier contract-ok，ROM gate 92/92；
  incomplete 仅因 remaining unknown 和既有全局门禁，非本批错误。
- 下一批优先修复 battle status-bar caller 与 OAM/task slice 的冻结身份漂移，再与已
  直接通过的 profile selector 164 bytes、chapter selector 64 bytes、sprite loader
  tail 36 bytes 合并；不得把历史 accepted 标签当作当前 verifier 通过。
