# 对敌控制术战斗事务证据（2026-07-27）

## 目的

纠正 Butano 表现层把所有非 `animation_family == 1` 动作降级为地图效果的问题。
原 ROM 模板的 `presentation.animation_family` 只是共享显示资源绑定，不能独自决定
“地图效果 / 单施术者 / 双角色战斗”的场景结构。场景分类必须同时消费目标策略与
resolver 效果语义，且只能投影已经提交的战斗事务。

## 录像与可复核产物

- 视频：[YouTube「【GBA】NARUTO -ナルト- 木ノ葉戦記」](https://www.youtube.com/watch?v=I6MbYo17eJ0)
- 本地视频：
  `build/battle-presentation-video-analysis-20260727-01/I6MbYo17eJ0.mp4`
- 视频 SHA-256：
  `b3aceb65a0ab4edeaf06fa9c528c243a7593dc6d4d077c859d72047e572c9a33`
- 分析区间：`950.0s..975.0s`，每秒 2 帧，共 50 帧。
- 联系表：
  `build/battle-control-video-frame-analysis-20260727-01/shikamaru-0950-0975-contact.png`
- 联系表 SHA-256：
  `643d0a3fb2f8deeadedeb20e07c597879b98258f71a2bd57b06c89ea19abd7f5`
- 抽帧 guard：
  `build/resource-guard/battle-control-video-frame-analysis-20260727-01.json`
- 联系表 guard：
  `build/resource-guard/battle-control-video-contact-precise-20260727-01.json`

帧号换算为 `950.0 + (frame - 1) × 0.5` 秒。关键帧：

| 抽帧 | 时间 | 可见事实 | SHA-256 |
|---|---:|---|---|
| `frame-019.png` | 959.0s | `影真似の術` 已进入森林双角色舞台；施术者、目标、双方 HP/查克拉和中央分隔线同时存在 | `0fa04ebe620b5e9bb6ed77b8db50673b0429f47db9129f2ae49d2871e4327bc6` |
| `frame-023.png` | 961.0s | 独立术名/肖像 cut-in；不在地图选项或确认框中播放 | `fb9ac742679c7472a4473dcb4d7e65f36b09d8e33f85e3524f4e78b40d2583a1` |
| `frame-033.png` | 966.0s | 返回同一双角色舞台做命中判定，画面显示 `MISS!`；表现不能伪造领域命中 | `27ed892c17b2d94d0540c5b1fc885070f9fe11cfb6db63ca7e859d949f115716` |
| `frame-041.png` | 970.0s | 事务结束后才回到原战场地图与等待状态 | `ad56a6adeb172be9d01993072a8be49d473adf0a38a8531e4bfd43a4ede164af` |

这段连续证据给出有序状态：

```text
地图目标确认
  → 转场
  → 施术者/目标双角色舞台 + 双侧 HUD
  → 术名/肖像 cut-in
  → 双角色命中判定（本样本为 MISS）
  → 返回地图
```

它直接排除了“控制术只在地图上显示一张效果图”的实现。视频中的日文身份是
`影真似の術`；生成内容表中的中文动作 24 为同一鹿丸对敌控制术槽。视频只证明该
事务形态和这条自然路线，不签发动作 23、80 的逐帧专属资产等价。

## 生产分类与领域边界

新增 `battle_combat_presentation_kind::control_technique`。分类不硬编码角色或关卡：

```text
presentation family 5
AND target policy = opponent_unit
AND resolver effect ∈ {14, 15, 63}
  → control_technique
```

这三个效果分别覆盖当前已知的对敌控制动作 23、24、80。共享 family 5 的动作 22
`解` 是 linked-cleanup effect 11，仍为地图动作；不能因为资源 family 相同而误放进
控制术。family 5 的自己、友军、占用单位或空格动作也继续由各自事务族负责。

`control_technique` 复用通用八阶段事务：

```text
transition_in
  → duel_setup
  → actor_prep
  → technique_title
  → action_movie
  → impact × resolver impact_count
  → result
  → transition_out
```

每个阶段只声明 `map/stage/actor/target/title/effect/hud` 轨道。HP、命中/未命中、
状态写入、行动资格和回合推进仍来自 resolver 与
`battle_scene_presentation_event`；renderer 没有业务写入口。玩家与 AI 共用同一表和
同一状态机，不存在“选择某截图选项后跳到另一张截图”的控制路径。

## TDD 与当前边界

- 红：
  `build/resource-guard/butano-opponent-control-transaction-cpp-red-20260727-01.json`
  因生产 enum/route 不存在而失败。
- 绿（定义与事务）：
  `build/resource-guard/butano-opponent-control-transaction-cpp-green-20260727-02.json`
- 绿（场景集成）：
  `build/resource-guard/butano-opponent-control-scene-integration-green-20260727-01.json`
- 最终 focused/refactor：
  `build/resource-guard/butano-opponent-control-focused-final-20260727-01.json`

宿主测试证明动作 23/24/80 进入同一双角色事务；动作 24 的完整场景测试必须看到术名、
双角色舞台和 impact，结束后恢复地图。

最终回归：

- 95/95 宿主 C++：
  `build/resource-guard/butano-opponent-control-full-host-final-20260727-01.json`，
  guard peak 151.54296875 MiB；
- 9/9 表现 wiring / mGBA probe Python 测试通过；
- devkitARM：
  `build/resource-guard/butano-opponent-control-arm-build-final-20260727-01.json`，
  guard peak 84.67578125 MiB；
- ROM / ELF SHA-256：
  `65d023270e5832e0811ef9f8c7821b08731155c9dada6ffb0bee6f01434ffcce` /
  `3bb1aee0a054ef4e317752c847f63e2ee019a249f46f4d8b35a686cdac71e59b`；
- 精确 ELF telemetry 地址仍为 `0x0201FBC4`，解析证据：
  `build/resource-guard/butano-opponent-control-elf-nm-final-20260727-01.json`；
- 非静音 battle 9 回归消费 518/518 个输入、运行 6500 帧，在 round 2
  `unit_selection` 完成且最后动作 16；WAV 有 5,311,038 个非零采样，
  相邻跳变 `>=16384` 为 0，WAV SHA-256 为
  `a96a1681589841f61fc502e788732e2d0272d2640eb14d7877143f6dba77bfcb`。
  guard、telemetry 和分析分别位于
  `build/resource-guard/butano-opponent-control-audio-regression-final-20260727-01.json`、
  `build/butano-opponent-control-audio-regression-20260727-02/report.json` 和
  `build/butano-opponent-control-audio-regression-20260727-02/analysis.json`。

该 mGBA 路线是 ROM/音频/既有战斗流程回归，不包含动作 24，因此不能替代上述动作 24
场景集成测试，也不能签发控制术的 GBA 自然交互路线。

当前只闭合“事务形态与生产接线”。动作 23/24/80 的 ROM 派生专属 cut-in、动作轨、
控制效果、音效和逐帧时长尚未逐项提取；忍具 49–66 虽同为 family 5 且目标为敌方，
目前缺少自然录像/ROM 事件证据，仍不把它们猜成投掷事务。完整战斗 Goal 保持未完成。
