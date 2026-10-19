# 原版动作 16 火遁组件化表现与 Butano 运行时（2026-07-26）

## 结论

动作 16 已从“按选项跳到预制画面/程序化火球”改成真实战斗事务上的组件化纵向切片：

```text
玩家或 AI 命令
  → 同一个 action resolver 提交领域结果
  → battle_scene_presentation_event
  → PresentationDefinition 的有序阶段和资源 ID
  → cut-in / title / movie / impact 独立 renderer track
  → 演出完成后释放输入锁并继续回合
```

表现层不拥有 HP、目标、命中次数、行动资格或回合写入口。动作 16 的资源也不是 240×160
截图：生成器直接读取 ROM，按 BG tilemap、palette、OAM shape/size、tile offset、翻转、
priority 和逐帧 hold 生成独立 BG/OBJ 资产及时间线。

这个里程碑只闭合动作 16 的已取证表现纵向切片，不代表完整战斗架构、87 个主动动作、
94 个忍具或音频已经功能等价。

## 可复现输入

- 原 ROM：`rom/base.gba`
- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 进入动作 16 前的原作快照：
  `build/original-fire-route-probe-20260726-97/output.ss9`
- 快照 SHA-256：
  `6291bbc90d3425e6fd6a327aa003f7cfd80a900740d947811e4a59ea9c50a377`
- 完整原作 GPU/OAM/CPU trace：
  `build/original-fire-presentation-trace-20260726-99/`
- cut-in 关键帧 trace：
  `build/original-fire-presentation-trace-20260726-98/`
- 命中结构化证据：
  `notes/evidence/original-action-16-fire-hit-sequence-20260726.json`
- cut-in/movie 结构化证据：
  `notes/evidence/original-action-16-fire-movie-components-20260726.json`

原作 trace 的主要阶段边界为：

| 原作帧 | 阶段 |
|---:|---|
| 7 | 行动初始化 |
| 51 | 决斗场建立 |
| 190 | cut-in/title 资源装载 |
| 192–310 | 肖像滑入、标题显示和窗口内白场淡化 |
| 311–437 | 四层 movie |
| 438–483 | 决斗场恢复 |
| 487–516 | 命中 OAM 序列 |
| 578 | 战场恢复 |
| 900 | 下一次交互提示 |

## Cut-in 与标题

cut-in 由仍在运行的决斗背景、独立 dialogue BG、512 像素宽肖像 BG 和三个 32×32
标题 OBJ 组成。主要 ROM 资源是：

- 肖像 tiles：`0x0834B248`，7168 字节，SHA-256
  `85067c2668849bb5e486323ed27bf74c7ed797eca533234ec3a5682ec4d38995`
- 肖像 tilemap：`0x0834C1CC`，840 字节，SHA-256
  `982514213960e6cfbdf74c15d2fe2b32b525c8e7d0db0ba2e77076856f1c6290`
- 肖像 palette：`0x0834C418`，32 字节，SHA-256
  `e6a298bb50adddb4fb1020899f19a56704130182965a3442d8b4550b6789caeb`

原作帧 300 证明淡化不是整屏 palette 替换，而是空间窗口内的硬件白场：

| 寄存器 | 值 | 语义 |
|---|---:|---|
| WIN0H | `0x00F0` | x = 0..240 |
| WIN0V | `0x2070` | y = 32..112 |
| WININ | `0x3F3F` | 窗口内允许 blending |
| WINOUT | `0x3F1F` | 窗口外关闭 blending |
| BLDCNT | `0x00B7` | 白场淡化目标 |
| BLDY | `0x0006` | 6/16 白场强度 |

Butano renderer 因此在 cut-in track 获取内部矩形窗口、窗口外 blending 和白场 alpha 的
临时所有权，并在 track 结束时逐项恢复原状态。它没有把淡化结果烘焙到截图里。

## Movie

movie 由四个互相独立的 regular BG track 和三个标题 OBJ 组成：

1. actor；
2. fire；
3. streaks；
4. dialogue；
5. title OBJ 0–2。

主要 ROM 资源：

- actor/fire tiles 0：`0x0837AFB8`，7552 字节，SHA-256
  `e67674f79db1fde3169d3a6a395c0d5850a8eca55d23ae27351719314e2cd311`
- actor/fire tiles 1：`0x0837C1E4`，2816 字节，SHA-256
  `efaa5d242654c6c6cffb7b2d2fae5588e8fd8974334f6fef1620f1f97b4d037e`
- streak tiles：`0x083497BC`，4096 字节，SHA-256
  `f210a464888b67b87682e742f02f84fc0881e44d03140ea7a3706a8bf6c81d83`

运行时内容保存 127 帧 palette/blend 时间线和 actor/fire/streak 独立滚动，不把最终合成
帧当作资产。玩家和 AI 只发出同一种 presentation event，因此不会各自维护一份火遁流程。

## 命中序列

原作帧 487–516 是 30 个活动帧、12 个 keyframe、最多 4 个 OAM 组件和 10 个唯一资产：

- tiles：`0x08345E64`，5120 字节，SHA-256
  `878505bd0d11d88fb0c72d9feeee8c4604625985cf9e496a3becb21a5165e867`
- palette：`0x083466C0`，32 字节，SHA-256
  `2a4e16536349b52f028284eacbaa3e6047b02047b6e77af7d26914320b514d29`

通用固定容量 renderer 按 keyframe duration 选择组件，切换独立 sprite item，并在组件数
减少或序列结束时释放多余槽。动作 16 只把 impact step 的 resource ID 绑定到该 sequence；
命中次数仍来自 resolver 产生的 `impact_count`。

## 运行时验收

最终 devkitARM 构建：

- guard：`build/action16-layer-fade-arm-build-20260726-04/guard.json`
- 结果：exit 0，峰值 19.87890625 MiB
- ROM SHA-256：
  `a035eeffd4a6e3f25562b92259604e6f03e2919fce5eb1dd4a507122f989f507`
- ELF SHA-256：
  `343eb2067017cadafdd71f7d2f0969e79eacbd3e5193bc27a447bcb0d6c06a69`

最终静音 mGBA 自然路线：

- 目录：`build/butano-action16-layer-fade-runtime-20260726-04/`
- frame 6145 完成；
- battle 9、round 2、unit selection；
- `last_resolved_action_id = 16`；
- `sasuke_fire_executed = true`；
- active units `9→8`；
- guard peak 119.3671875 MiB；
- audit SHA-256：
  `572eb1dda40aab7a508030d79025e61ab874571be6dd357e0929c19a869ad17e`。

Butano 与原作关键帧的 240×160 像素比较：

| 锚点 | Butano | 原作 | 差异 |
|---|---|---|---:|
| 标题/cut-in 完整帧 | `sasuke-fire-title.png` | frame 250 | 0/38400 |
| cut-in 窗口白场 | `sasuke-fire-cutin-fade.png` | frame 300 | 0/38400 |
| movie 参考帧 | `sasuke-fire-movie-reference.png` | frame 360 | 0/38400 |

这些比较只签发三个已绑定锚点；它们不自动证明每个中间帧、音频或其他动作等价。

## 调试结论

第一次接入硬件白场时，运行时在标题后停止。根因不是 mGBA：消息窗口取得全局透明混合
权重后只把自身隐藏，没有恢复进入窗口前的 top/bottom blending weights；cut-in 随后请求
白场 fade 时触发 Butano 对“不允许 fade 与非默认 transparency 同时存在”的状态约束。

修复采用资源所有权对称原则：

1. 消息窗口进入时保存原 top/bottom weights；
2. reset 时恢复保存值；
3. cut-in 进入时保存窗口边界、可见性、窗口 blending 和窗口外 blending；
4. cut-in 退出时完整恢复；
5. 对应 wiring 测试先失败，再由最小实现转绿。

因此此前“确认后黑屏/还要再按一次 A”的现象不能归因于系统默认 mGBA；当前动作 16 自然
路线不需要额外 A 才进入表现。

## 明确边界

- 已闭合的是动作 16 的 cut-in/title/movie/hit 表现纵向切片。
- 通用决斗角色动作和 HUD chrome 仍未逐像素闭合。
- 动作 17、18 不能因同属火遁 family 就复用动作 16 后宣称等价，仍需各自运行时证据。
- 其余动作族、状态/召唤/放置物的专属表现尚未逐族闭合。
- 本轮 mGBA 全部 `mute=1`；音频撕裂没有被本里程碑修复或验收。
- 完整战斗 Goal 仍处于 active，不能用本里程碑签发“完整战斗功能等价”。
