# Butano 战斗音频事件化与非静音运行证据（2026-07-27）

> **最终纠正（同日）**：战役路由 ROM 的全零录音已经修复。根因不是 mGBA，也不是
> Maxmod 资产或歌曲数据，而是 SRAM 存档解码在 GBA 上建立约 `0x123c` 字节栈帧，嵌套
> 清零时越过 IWRAM 栈边界并覆盖 Maxmod 跳板。生产路径现复用 EWRAM 中调用方持有的
> decode workspace，核心解码栈帧降到 `0x6c`。新 ROM 的 600 帧录音有 539,784 个
> 非零采样、RMS 887.7133、峰值 6528，`>=8192` 和 `>=16384` 的同声道相邻突跳均为
> 0；scenario 41 完整结算保存并冷启动进入 battle 42 也已复验。WAV SFX 仍按下述边界
> 保持禁用，已恢复的是事件驱动的 S3M BGM。
>
> **此前纠正（同日）**：本文记录的 battle 9 非静音路线证明了当时录音波形没有旧 PCM
> 的跨半幅跳变，但不能证明所有导入 WAV SFX 在更长路线中稳定。scenario 41 四回合回归
> 已复现 IRQ/Maxmod mixer 冻结；逐项关闭和 GDB 证明问题位于重复 WAV SFX 提交，而非
> mGBA 前端或战斗状态机。当前生产适配器保留 S3M BGM，暂停提交全部 WAV SFX；完整路线
> 已在 `artifacts/butano-s41-four-round-runtime-20260727-22/` 通过。本文后续所有
> “音频骨架闭合”只指语义事件与 BGM 接线，不再表示 SFX 已签发。详见
> `notes/battle-scenario-41-mission-rules-runtime-20260727.md`。

## 结论

旧 scenario 41 原型把整屏截图、固定选项和单条按键路线拼成演示，这条实现已经废弃。
当前通用战斗运行时虽然已经由 `battle_encounter_runtime`、`battle_scene_controller`
和 `battle_scene_presentation` 驱动真实领域状态，但本轮复核发现它没有任何
`bn::music` 或 `bn::sound` 调用：音频资产仍被链接，Maxmod 后端也在工作，然而战前和
战斗状态机没有向音频层发事件。因此冷启动录音全零；继续切换 mGBA 版本、渲染器或宿主
音频后端不能修复这个缺口，根因**不是 mGBA 前端**。

本轮把音频接入同一战斗事件链，并用非静音冷启动和完整战斗输入重放验证。音频不再绑定
截图序号、固定帧表或 scenario 41 专用分支。

## 战役路由回归的根因与修复

战役路由接入 SRAM 后，歌曲层仍在推进 pattern，歌曲资产与旧稳定 ROM 逐字节一致，但
`mpp_Channel_NewNote` 从未被调用，20 个 mixer channel 全部 disabled。进一步在
Maxmod IWRAM 跳板目标处加写监控，确认旧故障 ROM 的
`__mpp_Channel_NewNote_from_arm` 目标会被 `memset` 调用链从 `0x03000B05`
依次改写为 campaign buffer 内容；写入者 PC 为 `0x0300181C`，调用者 LR 为
`0x0800212D`，当时 SP 已到 `0x030022E8`。

反汇编把调用者闭合到按值返回的 `decode_battle_campaign_slot`：它在 ARM 构建中分配
约 `0x123c` 字节栈空间，并在 SRAM 双槽解析的嵌套调用中覆盖位于低地址 IWRAM 的
Maxmod 代码。修复没有另建存档系统，而是扩展已有 `battle_campaign_sram_workspace`：

- `decode_battle_campaign_slot_into` 将结果写入调用方提供的槽；
- `load_latest_battle_campaign_slot_into` 与
  `next_battle_campaign_save_target_into` 复用同一组 decoded slots；
- SRAM 读取、保存和读回验证都使用 main 已持有的 EWRAM workspace；
- 旧按值返回 API 只保留为宿主兼容包装，GBA 生产调用点不再使用。

修复后 ARM 反汇编中 decode 栈帧为 `0x6c`，SRAM load 总栈帧为 `0x54`。Maxmod 运行
追踪在 100 帧内得到 88 次 `mmFrame`、1 次 `NewNote`、1 次声道分配进入和 1 次成功
返回（`r0=0`），跳板目标始终为 `0x03000B05` 且写命中为 0；下一帧前景声道由 0
变为 1。

证据：

- 故障对照：
  `artifacts/butano-maxmod-allocation-current-20260727-06/`
- 修复后调用链：
  `artifacts/butano-maxmod-allocation-current-postfix-20260727-01/`
- 修复后 WAV：
  `build/butano-audio-repro-current-postfix-20260727-01/audio.wav`
- WAV 分析：
  `build/butano-audio-repro-current-postfix-20260727-01/integrity.json`
- scenario 41 完整结算/保存：
  `artifacts/butano-battle-campaign-route-audio-postfix-20260727-02/`
- SRAM 冷启动进入 battle 42：
  `artifacts/butano-battle-campaign-route-audio-postfix-b42-20260727-01/`
- ROM SHA-256：
  `8f19053a827ee15c4d1a0c0b7b43550aec7f2b74e2be2cd5468bb7bbf1493bad`
- ELF SHA-256：
  `570867daf9717e2ec3bbc3b8fe8fe10a243fd69effb95f4607daafb087abf479`

## 架构

```text
BattleSession / battle_scene_controller
              │
              ├── phase transition
              ├── accepted/rejected intent
              └── battle_scene_presentation stage
                              │
                              ▼
                    battle_audio_event
                              │
                              ▼
                    battle_audio_director
                              │
                              ▼
                battle_audio_command_batch
                              │
                              ▼
                    battle_audio_runtime
                              │
                              ▼
                       Butano / Maxmod
```

- `battle_audio_event` 是领域与表现层之间的语义边界，包括战前、开战、输入确认/取消/
  移动/拒绝、行动提交、术名、行动 movie、命中、战果弹窗、胜利、结算、升级、战后对白
  和战后地图。
- `battle_audio_director` 是纯函数映射，只产生固定容量命令批次，不读取按键、不操作
  Butano handle，也不能写 HP、坐标、回合或战果。
- `battle_audio_runtime` 是唯一 Butano 适配器，把经原 ROM checkpoint 验证的语义 cue
  映射到 `bn::music_items` / `bn::sound_items`。
- `battle_runtime_scene` 从 controller 的 phase 和 presentation stage 边沿发事件；
  `battle_preparation_scene` 从战前场景生命周期发事件。持续每帧轮询不会重复起播。
- 组合技不通过 action ID 或标题字符串反猜。`battle_scene_presentation_event` 显式携带
  `special_combination`，由玩家组合事务在 resolver 成功后设置；音频导演据此选择
  组合技术名 cue。
- renderer 和音频适配器只消费领域投影，不能修改战斗领域状态。

导演语义映射仍为：战前音乐 5、开战音乐 14 与音效 126、UI 确认/取消/移动/拒绝
102/103/104/105、行动提交 117、组合技术名音乐 15、行动 movie 116、命中 138、战果
弹窗音乐 14 与音效 149、胜利 158 与 51、结算 157 与 112、升级 52、战后对白音乐 8、
战后地图音乐 2。当前平台适配器只执行音乐命令；上述 sound 命令暂时为空操作。

## TDD 证据

红灯分别证明了以下能力在修改前不存在：

1. 缺少 `battle_audio_director` 及语义事件到命令的纯映射。
2. 表现事件缺少显式组合技语义。
3. 通用战斗 scene 没有从输入、phase 和 presentation stage 接线。
4. 冷启动仍停留在战前 scene，因此只接战斗 scene 后录音仍全零。
5. WAV 检查器和 mGBA core 录音器不能复放完整 JSONL 输入或输出遥测报告。

绿灯后，宿主 C++ 测试为 **95/95**；相关 Python 测试覆盖 wiring、录音器输入重放和
WAV 完整性分析。最终 ARM 构建通过：

- host guard：`build/resource-guard/butano-battle-audio-full-host-20260727-02.json`
- guard：`build/resource-guard/butano-battle-audio-arm-20260727-02.json`
- ROM SHA-256：
  `b969b6eaa2cce74909d43a6fbd5d965d077d432b3803eb141e788afe27bbc87f`
- ELF SHA-256：
  `072ab1deaf254635a15fb8b077a6d14d9e0f8dc26f89b780af3711e2fb50ca8d`
- battle telemetry：`0x0201FBC4`

## 非静音运行证据

### 修改前对照

`build/butano-battle-audio-baseline-20260727-01/cold-start-600f.wav` 共 657,416 个
采样，非零采样为 0。它证明当时的新战斗架构没有音频接线，而不是证明模拟器不能播放。

### 修改后冷启动

`build/butano-battle-audio-runtime-20260727-02/cold-start-600f.wav`：

- 657,416 个采样，540,872 个非零；
- RMS 888.8755，峰值 6528；
- 相邻同声道采样绝对跳变 `>=8192` 为 0，`>=16384` 为 0；
- WAV SHA-256：
  `2630255c631391a50b34fec1eb9e15a17a7a452b90648412189d6a604e4dc885`。

分析 manifest 为
`build/butano-battle-audio-runtime-20260727-02/cold-start-600f-analysis.json`。

### 完整战斗重放

先由受资源守卫的可视 mGBA 路线在 battle 9 记录部署、选人、移动、选技、目标确认、
火遁切入/movie/命中及地图恢复；随后录音器从冷启动确定性重放相同 JSONL 输入，而不是
加载不兼容的跨前端 savestate：

- 运行 6500 帧；
- 输入事件 **518/518** 全部消费；
- 最终 battle 9、round 2、unit selection、active units 8、last action 16；
- telemetry 地址 `0x0201FBC4`；
- `SOUNDCNT_X=128`，DMA1/DMA2 均为 `0xB640`；
- 3,565,594 个 stereo frame，7,131,188 个采样，其中 5,874,592 个非零；
- RMS 1132.3613，峰值 9792；
- 相邻同声道跳变 `>=16384` 为 0；
- `>=8192` 为 88/7,131,186，即 **0.001234%**；
- WAV SHA-256：
  `c6cc5a62493933d818fd64ad6889fe99c817b76f3eaed96670b1f90284befd25`。

文件：

- 录音：`build/butano-battle-audio-runtime-20260727-02/full-route-6500f-verified.wav`
- 音频分析：
  `build/butano-battle-audio-runtime-20260727-02/full-route-6500f-verified-analysis.json`
- 输入与硬件报告：
  `build/butano-battle-audio-runtime-20260727-02/full-route-6500f-report.json`
- 可视路线：
  `artifacts/butano-battle-audio-fire-route-20260727-01/`
- 录音 guard：
  `build/resource-guard/butano-battle-audio-full-route-capture-20260727-02.json`

此前失效 PCM 的跨半幅突跳约为 1.4%；本次完整路线的高阈值突跳为零、低阈值比例为
0.001234%，且峰值低于低阈值。两者不属于同一种撕裂波形。可视路线的 execution trap
和 memory-write trap 均为空，行动 16 后恢复地图并继续到第二回合，没有“确认后纯黑并
等待第二次 A”的状态。

## 复验

```sh
python3 tools/analyze_wav_integrity.py \
  build/butano-audio-repro-current-postfix-20260727-01/audio.wav \
  --output build/butano-audio-repro-current-postfix-20260727-01/integrity.json
```

完整重放通过 `tools/butano/mgba_audio_recorder.c` 的
`MGBA_AUDIO_INPUT_EVENTS`、`MGBA_AUDIO_REPORT` 和
`MGBA_AUDIO_TELEMETRY_ADDRESS` 传入输入日志、报告路径及遥测地址；mGBA 与其他高开销
任务必须经 `tools/run_guarded.py` 和 shared heavy lock 启动。

## 功能边界

- 已闭合的是通用、事件驱动、非静音的战斗音频骨架，以及 battle 9 动作 16 完整路线的
  无黑屏与波形级撕裂回归。
- 这不是对所有宿主声卡/系统的主观听感逐设备签发，也不是对原 ROM 的逐采样 bit-exact
  复刻。
- 87 个主动动作和 94 个忍具的逐项专属 cue、完整表现身份与原作时间点仍需各自自然路线
  取证；不能把当前通用 cue 当成所有技能已经音画等价。
- 全零身份 39/40/52 的非命令用途仍未闭合。完整战斗 Goal 保持未完成。
