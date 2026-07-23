# Butano Scenario 41 复刻运行证据（2026-07-22）

## 结论与计时

- Goal：`1:1复刻这个战斗关卡，包括ui、场景、角色、战斗动画、战斗流程、音效、回合流程`。
- Goal 实测截至最终全量回归完成后为 `28,753 秒 = 7.9869 小时`。计时包含当前 Codex 主模型的分析、TDD、实现、资产生成、构建、mGBA 等待、故障定位和文档；不换算成人类工时。
- 实现从战前任务菜单开始，完整覆盖四回合战斗、组合拳、结算、升级、11 页战后对白和返回世界地图。
- `butano-sequel/butano-sequel.gba` 在运行时实录音频替换和战斗入口状态修复后受控构建成功，ROM 为 `7,788,332` 字节，SHA-256 为 `3cdd89a46f03d713d75227cc2c173769ae8fad194e7e860ff03d7bd1c221ce1c`。

## 视觉与流程证据

原 ROM 参考包为：

- `artifacts/scenario-41-prebattle-reference-v1/`：战前菜单 4 个选中态和开始确认。
- `artifacts/scenario-41-reference-v1/`：地图、单位、移动、朝向、术菜单、教程等主边界。
- `artifacts/scenario-41-combat-reference-v1/`：行动菜单、确认、目标、战斗对白和弹窗。
- `artifacts/scenario-41-extended-reference-v1/`：胜利、结算、升级、11 页战后对白和世界地图。

最终黄金路线 `build/butano-s41-final-audio-route-golden-20260722-01/`：

- 资源守卫 `completed/0`、`degraded=false`，峰值 `113.5546875 MiB`。
- 2440 帧路线生成 38 个稳定边界；与上一轮已签发基准逐张比较为 **38/38 normalized RGB 完全一致**。
- 用户路线为战前菜单选择“开始任务”→确认→四回合→忍者组合拳→战斗对白→弹窗→胜利→`100 / 50 / 0 = 150`→鸣人 LV2、体力 `+14`→11 页战后对白→世界地图。

组合拳原作时间轴位于 `artifacts/scenario-41-attack-animation-v1/`，共 264 帧、173 个唯一帧，时间轴 SHA-256 为 `f10ddd3cf9a6088bc574cf41c069c4c7e701a1d1dd2c49aa4ce98c3dd560e931`。最终 Butano 实机 trace 位于 `build/butano-s41-final-audio-route-attack-trace-20260722-01/`，逐帧结果为 **264/264 normalized RGB 完全一致**。开头 4 帧使用原作 BG alpha 混合，黑场淡入使用 GBA 硬件 fade，不再存在先前的 18 帧差异。

## 原版音频状态取证

旧断点只监听公共 wrapper，得到 0 hit，不能证明“攻击无音效”。本轮改用两个独立证据源：

1. 直接读取原版 `.ss9` 中四个 MP2K player 的当前 descriptor；
2. `tools/butano/mgba_audio_recorder.c` 从同一攻击确认存档做零输入/A 键双录音，并逐帧记录 player descriptor 变化。

原版阶段音乐已闭合为：

| 阶段 | 原版 player 0 | Butano 资产 |
|---|---:|---|
| 战前任务菜单 | cue 5 | `sound_005.s3m` |
| 正式战斗 | cue 14 | `sound_014.s3m` |
| 组合拳演出 | cue 15 | `sound_015.s3m` |
| 战后对白 | cue 8 | `sound_008.s3m` |
| 返回世界地图 | cue 2 | `sound_002.s3m` |

攻击双录音位于 `build/scenario-41-original-attack-audio-20260722-01/`；A 路线和零输入路线从 0.03186 秒起出现差异。player trace `build/scenario-41-original-attack-audio-20260722-02/player-trace.log` 进一步给出：录音 frame 48 把 cue 14 切为 cue 15，frame 65 触发 sound 116，frame 141 触发 sound 138。映射到已导出的动画时间轴后，Butano 在 animation frame 47/64/140 执行相同类别的音乐/音效切换。

其余 checkpoint 证明并接入：UI sound 102/103/104/105，战斗选择 sound 126，目标/提交 sound 117，战斗弹窗 sound 149，胜利 sound 158 + jingle 51，结果 sound 157 + sound 112，升级 jingle 52。语义名称是按可见阶段与 descriptor 变化作出的事件级命名，不冒充游戏官方曲名。

五首 BGM 不再使用离线 MP2K PCM 渲染。它们来自原 ROM checkpoint 的 mGBA 运行时实录，先下混并重采样为 Maxmod 要求的单声道 unsigned 8-bit 22050 Hz，再封装为 S3M。音效仍由原立体声 PCM 算术平均为单声道并确定性重采样到 22050 Hz。来源、源/转换后 PCM、WAV/S3M 哈希、直流偏置、增益和时长在 `artifacts/scenario-41-audio-reference-v1/` 中持久化。

最终音频状态运行 `build/butano-s41-final-audio-route-states-20260722-01/` 在帧 20/500/1000/1600/2200 均验证 Maxmod 主开关、DMA1/2 和 Timer0 活跃，结果为 5/5 active。

### 音频撕裂与战斗黑屏回归

首次音频版错误地把转换器不支持的立体声 15768 Hz PCM 直接封装为 S3M。音频库因此达到 `6,488,992` 字节，ROM 达 `9,658,124` 字节，`scenario_41_map` 等关键描述符被推到 `0x0893xxxx`；宿主录音均值约为 `-8,550/-7,393`，并出现 `1.51%/1.38%` 的大幅样本跳变。用户实际运行表现为持续撕裂，开始战斗后黑屏。

第一次所谓“修复”只解决了格式和 ROM 大小，用户随后分别在 mGBA 0.11、Homebrew mGBA 0.10.5、OpenGL/软件渲染和 SDL/Qt 音频组合下复验，撕裂和战斗黑屏均完全不变，因此该结论已被取代。进一步审计发现离线 `sound_005.wav` 自身已有 `1.403%` 的跨半幅相邻采样突跳，而原 ROM mGBA 实录的同类 `>=16384` 突跳为 `0%`；根因不是模拟器前端，而是作为 BGM 输入的离线 PCM。

当前生产音频库仍为 `4,619,200` 字节，ROM 位于 8 MiB 边界内，`scenario_41_map` 位于 `0x08769B98`。新的受控证据如下：

- 原 ROM 实录：`build/scenario-41-original-bgm-capture-20260722-01/`，五个阶段均从对应 checkpoint 受控录制。
- 诊断禁音：`butano-sequel-no-audio.gba` 的 600 帧录音共 `657,416` 个采样且全部为零；`build/butano-s41-no-audio-diagnostic-golden-20260722-01/` 完成 2440 帧并达到 38/38 PNG 一致。
- 生产候选：`build/butano-s41-runtime-s3m-golden-20260722-01/` 完成 2440 帧并达到 38/38 PNG 一致；其 ROM 与当前 `butano-sequel.gba` 逐字节相同。
- 宿主录音：`build/butano-s41-runtime-s3m-audio-20260722-01/cold-start-600f.wav` 的 RMS 为 `891.66`，均值 `-51.27`，`>=8192` 与 `>=16384` 相邻采样突跳均为 `0%`。

自动路线已经排除战斗切歌导致的确定性黑屏，但手工 mGBA 路线仍需用户对当前 SHA-256 做最终听感和输入时序确认；在该确认前不再把用户侧问题标记为已修复。

### 战斗入口额外 A 键修复（已被在线录屏复核取代）

> 2026-07-22 后续复核确认，本节把“额外 A”本身当成 bug 是错误的。原作确实在开始确认和单位选择之间保留一个需要 A 推进的可见战前对白；真正的 bug 是 Butano 没有渲染双方亮相、“开始”标题、对白和手里剑转场。下面保留旧调查过程作为历史，不再作为验收结论。新结论见 `notes/butano-battle-flow-video-review-20260722.md`。

用户进一步确认：选择“开始任务？”的“是”后仍保持黑屏，但在黑屏中再按一次 A 就会出现战斗画面。这一输入特征定位到状态机而非 mGBA：`prebattle_confirmation` 的“是”原先进入 `battle_phase::intro`，场景层在该阶段隐藏全部背景，presenter 又刻意返回四行空文本，因此该阶段必然是纯黑画面；第二次 A 只是在把不可见的 `intro` 推进到 `unit_select`。

修复后，“是”直接进入 `unit_select` 并发出 `intro_dismissed`，不再暴露无可见内容的中间阶段。测试先改为期待直接进入单位选择并观察到失败，再完成最小状态转换；冷启动黄金路线同时删除 frame 180 的冗余 A，并在 frame 135 新增 `battle-entry.png` 集成断言。

受控证据位于 `build/butano-s41-intro-black-fix-build-20260722-01/` 和 `build/butano-s41-intro-black-fix-golden-20260722-01/`：

- mGBA 0.10.5 script-backport 完成 2440 帧，资源守卫 `completed/0`、`degraded=false`，峰值 `109.92578125 MiB`。
- `battle-entry.png` 为 240×160、62 种颜色的可见战场画面，并非黑帧。
- 新路线共 39 张截图；除新增入口图外，原有 38 张与修复前生产基准逐字节 **38/38 完全一致**。
- 当前生产 ROM SHA-256 为 `3cdd89a46f03d713d75227cc2c173769ae8fad194e7e860ff03d7bd1c221ce1c`。自动运行层面已证明确认“是”后无需额外 A；用户仍需对这一新哈希做最终手工输入和听感确认。

## 音频后端故障修复

构建目录曾缓存一个用 null audio backend 编译的 `bn_audio_manager` 对象；仅修改 Makefile 为 Maxmod 不会改变对象名，导致 ROM 画面正常但实际静音。`tools/butano/build.sh` 现在检查依赖文件：若 Makefile 要求 Maxmod、依赖却没有 `bn_hw_audio_maxmod.h`，先执行受控 `make clean`。干净构建后依赖明确指向 Maxmod，宿主 mGBA 录音得到非零立体声 PCM。

## 功能边界

- 战前四行菜单都可移动选中；本纵切片只实现“开始任务”的后续功能，其余三项保持原作画面与光标反馈，但确认后返回无效反馈，不展开队伍/装备、地图查看或保存子系统。
- 本关包含一个已证明技能“忍者组合拳”和一条成功路线；不代表全游戏技能、AI、失败结算、部署、存档和章节系统已经完成。
- 视觉按本关参考帧签发；音频采用原 PCM 的功能等价 Maxmod 包装，不宣称 GBA MP2K 混音器逐采样 bit-exact。

## 可复验入口

```sh
python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game
python3 -m unittest tests.test_butano_scenario_41_audio tests.test_butano_scenario_41_runtime_script -v
tools/butano/build.sh
```

ROM 构建和 mGBA 运行必须继续经 `tools/run_guarded.py` 与 `build/resource-guard/heavy.lock` 执行。
