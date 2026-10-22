# 自身型忍术表现事务证据与架构纠错（2026-07-27）

## 结论

此前 Butano 表现层只有“地图效果”和“对敌决斗”两条通路，并把不属于
`animation_family == 1 && opponent_unit` 的动作全部塞入地图效果。这个二分法不符合原作：

- 小李动作 43“第一　开门　开”进入森林忍术舞台，只显示施术者和单侧 HP；
- 宁次动作 38“白眼”也进入相同结构的单角色忍术舞台；
- 两者都经历黑色星形转场、术名、角色肖像/对白、自身效果、返回原地图；
- 整段不显示对手角色，也没有双人分隔线。

因此新增的是可复用的 `self_technique` 表现事务，不是动作 38/43 的角色 ID 特判，更不是
把录像帧或整屏截图打包进 ROM。领域 resolver 仍先提交查克拉、状态和回合结果；表现层只
消费事件并编排 stage/actor/title/effect/HUD track。

```text
ActionDefinition
  animation_family == 5
  target == self_or_implicit_actor
                │
                ▼
self_technique presentation
  transition_in(map)
    → duel_setup(stage + actor + one-side HUD)
    → actor_prep(stage + actor + one-side HUD)
    → technique_title(stage + actor + title + one-side HUD)
    → action_movie(stage + actor + effect + one-side HUD)
    → result(stage + actor + one-side HUD)
    → transition_out(map)
```

## 录像输入与逐帧窗口

来源：

- 视频：`https://www.youtube.com/watch?v=ZHSWgzBmUFQ`
- 标题：`【写輪眼サスケVS白眼ネジ】...part.20`
- 本地文件：
  `build/battle-special-actions-video-analysis-20260727-01/ZHSWgzBmUFQ.mp4`
- 文件规格：H.264 640×360、30 fps，时长 2619.768163 秒；
- SHA-256：
  `5c3a9ad6716e0fc81f1af3b2007388b575d1ff8ed9ce6e62578e4e9a9f6b6e7a`。

下载经过 `tools/run_guarded.py` 的统一 heavy lock：
`build/battle-special-actions-video-analysis-20260727-01/neji-full-download-guard.json`，
child exit 0，peak tree RSS 72.6875 MiB。第一次分段下载失败的记录保留在
`neji-video-download-guard.json`，没有把失败产物当作证据。

使用 ffmpeg 对 1280–1320 秒连续窗口按 2 fps 采样，得到 80 个顺序画面；生成命令、时间
和退出状态在 `byakugan-contact-guard.json`。两张接触表的 SHA-256：

| 文件 | 覆盖时间 | SHA-256 |
|---|---:|---|
| `byakugan-contact-01.jpg` | 1280.0–1299.5 s | `bec518ac4f965c5ee60f4e8086f66b32c9b3d4e9db2a085a7d32d0d625b427ce` |
| `byakugan-contact-02.jpg` | 1300.0–1319.5 s | `22f72539f4ac9c04907ea3be8c6ef8f904dba974d161401f786c879698c1566f` |

可见时序：

| 原视频窗口 | 动作 | 可见结构 |
|---:|---|---|
| 约 1282–1292 s | 第一　开门　开 | 地图确认 → 星形转场 → 单角色森林舞台/单侧 HP → 术名 → 小李肖像对白 → 自身效果 → 地图 |
| 约 1301–1312 s | 白眼 | 地图确认 → 星形转场 → 单角色森林舞台/单侧 HP → 术名 → 宁次肖像对白 → `+30%` 自身效果 → 地图 |

0.5 秒采样足以签发阶段结构和单/双角色分流，但不足以签发逐帧 hold、确切转场持续时间、
肖像动画帧或专属音效；这些仍需原 ROM I/O/OAM/VRAM/PRAM trace。

## ROM 与内容表交叉验证

原 ROM 输入：

- `rom/base.gba`
- SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`

生成内容表提供与录像相互独立的结构证据：

| 动作 | 角色主槽 | animation family | target | effect |
|---:|---|---:|---|---|
| 38 白眼 | 宁次（角色 11）主槽 6 | 5 | `self_or_implicit_actor` | code `0x12`、potency 20、duration 1 |
| 43 第一　开门　开 | 小李主槽 | 5 | `self_or_implicit_actor` | code `0x13` 系列的第一阶段生产者 |

这支持用“表现族 + 目标策略”建立通用分流。不能把所有 family 5 动作一并归入
`self_technique`：该族还包含召唤、友方目标和对敌动作，必须继续按目标策略和独立录像/
ROM trace 分流。

动作 39“柔拳八卦掌”、40“回天术”和 52“砂缚柩”仍是 16 字节全零模板，且没有角色
primary/formation 引用；它们不是缺失的普通命令按钮。其剧情、派生演出或废弃身份仍未
闭合，不得为凑齐技能列表猜造可选命令。

## 反汇编纠错：`0x0806B9DC` 不是动作消费者

此前调查曾把 `0x0806B9DC` 内对 39/40/55 的 switch 误读为动作 39/40 的表现分支。
重新沿调用者和地址计算复核后：

- 调用者为 `0x0807249E`、`0x08073D44`；
- 函数以单位索引和目标 x/y 为输入；
- 单位记录地址是 `0x020240C0 + index × 0x1D4`；
- 函数沿路径更新单位位置；
- 39/40/55 在这里是角色 ID 的移动表现特例，不是 action ID。

因此这段函数不能用于签发动作 39/40 的语义。类似地，只看到回调常量或资源编号也不能
直接把它解释为 action ID；后续必须先闭合生产者、调用参数和单位/动作表基址。

## TDD 与生产实现

红灯：

- `test_battle_combat_presentation.cpp` 先要求动作 38/43 产生
  `self_technique`、七阶段、单 actor/HUD、无 target/map，并因枚举和查询不存在而编译
  失败；
- `test_butano_battle_combat_presentation_runtime_wiring.py` 先要求 renderer 区分
  `single_actor_stage()` 与 `versus_divider_visible()`，因生产代码仍用
  `duel_stage_visible()` 统一画分隔线而失败。

绿灯：

- `battle_combat_presentation.h` 新增数据驱动的 `self_technique` 定义，仅对
  `family 5 + self_or_implicit_actor` 生效；
- 单角色阶段持续保留 stage、actor、HUD，title/effect 只是正交附加 track；
- 双人分隔线只在 actor 与 target 同时可见时出现；
- 单角色施术者和单侧 HP 放在右侧；地图效果和双人对敌布局不变；
- 当前 12/8/30/42/48/18/12 帧是结构性占位时长，不宣称原作逐帧等价。

聚焦验证：

```text
g++ -std=c++20 -Wall -Wextra -Werror \
  -Ibutano-sequel/game/include \
  butano-sequel/game/tests/test_battle_combat_presentation.cpp

python3 -m unittest \
  tests.test_butano_battle_combat_presentation_runtime_wiring
```

领域测试和新增 wiring 测试均已从正确原因的红灯进入绿灯。

最终验证：

- 95/95 个宿主 C++ 程序通过；guard：
  `build/resource-guard/butano-self-technique-full-host-20260727-03.json`，
  peak tree RSS 136.859375 MiB；
- 相关 runtime/build/audio Python 共 29 项通过、1 项显式跳过；架构持久性文档
  59/59 通过；
- 固定 devkitARM 构建通过；guard：
  `build/resource-guard/butano-self-technique-arm-build-20260727-01.json`，
  peak tree RSS 72.05859375 MiB；
- ROM/ELF SHA-256：
  `0586cd542fcd067d01341a7abc055164878f401794245aff2eda6f869943c954` /
  `af13c48762371d86e728da9a48465599cf7c1adc63e27cfd411ea9dcb72061a4`；
- mGBA battle 9 回归在 frame 6151 完成动作 16，活动单位 8、round 2、unit selection，
  control/player error 均为 0，execution/memory-write trap 均为 0 字节；guard：
  `build/resource-guard/butano-self-technique-regression-mgba-20260727-01.json`，
  audit SHA-256：
  `ca0a9d325ef507378ef22e98df34b21ae7055771d987ea2be5fb996b914e206e`；
- 同一 ROM 的 6500 帧非静音直接 core 录音消费 518/518 个输入事件，
  7,131,188 个声道采样中 5,311,038 个非零，`>=16384` 相邻跳变为 0，
  `>=8192` 为 78（0.001094%）；WAV SHA-256：
  `a96a1681589841f61fc502e788732e2d0272d2640eb14d7877143f6dba77bfcb`。
  该录音在 6500 帧落于 battle 9 round 2 facing selection，而可见 GUI 路线已在
  6151 帧回到 unit selection；因此录音只签发非静音/无严重跳变，不把 core 重放终点
  宣称为完整输入时序等价。

全量 184 项 Python discovery 另有 3 个既存 reference-export error，分别缺少
`build/scenario-41-attack-trace-20260722-01/frame-0006.png`、
`build/scenario-41-attack-trace-20260722-04/state-0056.ss9` 和
`build/macos-prebattle-frame80-step2-20260715/frame80.png`；它们不读取本轮代码，未为
凑绿而生成伪 reference。

## 边界与下一步

- 已修复：自身型忍术不会再作为地图效果，也不会伪造对手或双人分隔线；
- 已保留：领域状态 code `0x12/0x13`、查克拉和回合仍由统一 resolver/session 决定；
- 未完成：动作 38/43 的 ROM 派生肖像表达式、手势/自身效果组件、转场逐帧 hold 和专属
  音效；
- 未完成：family 5 中召唤、友方目标、对敌动作的其余表现子族；
- 未完成：全 87 主动动作和 94 忍具的逐项专属表现。因此这次纠错不代表完整战斗 Goal
  完成。
