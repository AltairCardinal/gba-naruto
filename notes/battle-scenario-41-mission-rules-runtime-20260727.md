# Scenario 41 任务规则、四回合路线与音频故障边界（2026-07-27）

## 结论

旧 scenario 41 原型曾把整屏截图、固定选项和预录路线拼成“战斗”。该实现已经退出
生产入口，不能作为战斗系统完成证据。当前 battle 41 variant 0 由通用
`battle_scene_controller` 驱动真实单位、地图、移动、行动目录、resolver、AI、胜负条件、
结果、升级、修炼和 campaign 存档；场景渲染与 mGBA 脚本都不能直接写 HP、坐标、回合或
胜负。

本轮闭合的是 scenario 41 的任务级行动限制和原作四回合结算路线，不是全部关卡、全部
技能表现或完整音频等价。

## 可复用架构

```text
battle_content_entry
  ├─ scenario / formation
  ├─ map / collision
  └─ condition variant
          │
          ├──────── mission rules (battle + variant)
          │                 │
          ▼                 ▼
  battle_scene_controller → battle_action_access_policy
          │
          ├─ BattleSession / movement / resolver
          ├─ player action flow / AI turn flow
          ├─ turn flow / condition evaluation
          └─ result / progression / training / campaign save
                              │
                              ▼
                    presentation event queue
                              │
                              ▼
                 renderer + semantic audio events
```

- `battle_mission_rules_for(battle_id, variant)` 是关卡数据，不是 renderer 或 Lua 的条件分支。
- battle 41 variant 0 只允许主动动作 5，禁用忍具；未配置关卡保持通用目录。
- controller 把任务策略追加到既有 `battle_action_access_policy`，没有第二套技能过滤器。
- AI 配置、胜负条件、任务行动限制和表现脚本保持四个独立输入；任何一层都不能伪造其他层
  的结果。
- `presentation_pending()` 暴露只读队列状态，使 phase 音频必须等待领域产生的演出事件
  被消费并播放完成，避免“领域先胜利、致命一击还没演完”时抢播下一阶段。

## 四回合运行时路线

`tools/butano/mgba_battle_41_shared_runtime.lua` 只通过按键驱动通用 UI，并从 telemetry
读取当前玩家和首个活动敌人的坐标。前三回合执行任务允许的移动/结束行动，第四回合从敌人
实时位置选择邻接格并使用动作 5；脚本不写单位坐标、HP、行动结果或胜负。

最终受资源守卫的 mGBA 证据：

- 证据目录：`artifacts/butano-s41-four-round-runtime-20260727-22/`
- 完成帧：879
- battle：41
- round：4
- 任务经验：100
- 战斗经验：50
- 回合奖励：0
- 总经验：150
- 鸣人：LV1 → LV2，剩余经验 0
- 修炼：动作 8，等级 0 → 1，修炼点 1 → 0
- campaign save generation：1
- save verified：1
- controller/player error：0/0

权威结果见 `audit.json` 和 `done.json`。这条路线证明结果由共享领域链生成，不证明当前 AI
逐格路径已经与原 ROM 完全一致。

## 黑屏与音频故障

### 已排除

- mGBA 0.10.5 不是“进入战斗必须再按一次 A”的根因。
- 黑屏不是 scenario 41 结果页截图或 Lua 等待第二次确认。
- Maxmod v1.22.2 mixer 与上游对应版本字节一致；修改 fetch threshold 无效并已撤回。
- soundbank 的 sample/module 数量和 pointer table 没有整体错位。

### 运行时证据

致命一击会先把领域 phase 切换为 `outcome`，而 combat presentation 仍在
title/movie/impact/result 阶段。旧接线立即提交胜利音频，冻结时 GDB 处于 IRQ/Maxmod
更新，首次捕获的源指针落在 sound 51 数据。把 phase 音频延后到
`!presentation.busy() && !controller.presentation_pending()` 后，停点离开致命一击，
但重复提交导入 WAV SFX 仍会在后续结果/训练页破坏 mixer 状态；移除单个 51/52/158
不能稳定闭合。

最终安全策略是：

- 保留 `battle_audio_event → battle_audio_director` 的语义映射边界；
- 保留稳定的 S3M 战前、战斗、组合技和战后 BGM；
- `battle_audio_runtime` 暂不向 Maxmod 提交任何导入 WAV SFX；
- UI、命中、胜利、结果和升级的视觉反馈保持，短音效暂时缺失；
- 原 WAV、失败 manifest 和运行目录保留作为后续替换资产/修复转换器的证据。

music-only build 的完整四回合运行在 success marker 触发后正常退出；因此已确认本轮黑屏
由 SFX 后端路径造成，而不是战斗 controller 或 mGBA 输入状态。

## TDD 与验证

- 红灯：任务规则/控制器目录、round 4 结果、phase 音频门控、演出队列 pending 契约和
  禁用不稳定 PCM 提交均先由测试证明旧行为不满足。
- 绿灯：
  - 全部 game host C++ 程序通过：
    `build/resource-guard/20260727-s41-music-only-full-host.json`
  - 23 个相关 Python wiring/脚本测试通过。
  - ARM 构建通过：
    `build/resource-guard/20260727-s41-final-arm-build.json`
  - mGBA 四回合通过：
    `build/resource-guard/20260727-s41-final-four-round-mgba.json`
- 最终 ROM SHA-256：
  `0dc2d07097fe2681bce5ba7c4c15a55c0f4bb9278a93aaa7154f6fdc4d380654`
- 最终 ELF SHA-256：
  `bbf9ec00093b928d5051dbad1a35f2984ad62a6fbe5bd35abe4ec2f13d07ae30`

## 尚未完成

- 当前 WAV SFX 全部禁用，音效与原作不等价；需重做 Maxmod-safe 资产与非静音波形/听感验收。
- scenario 41 当前 AI 选择合法且由配置驱动，但逐格路径尚未签发为原作精确等价。
- 逐技能专属切入、特效、字形、音画时点仍有大量未闭合项。
- 全零动作 39/40/52 的非命令用途、部分对象/章节脚本、Arena 完整入口和 Link 等仍未闭合。
- 一个 battle 41 样本不能单独证明全部 47 场可制作；完整战斗 Goal 保持 active。
