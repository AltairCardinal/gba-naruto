# Scenario 41 音频参考包

本目录记录 scenario 41 的原 PCM→Butano 音频转换证据。

- cue 5：战前任务菜单。
- cue 14：正式战斗。
- cue 15：忍者组合拳演出。
- cue 8：战后对白。
- cue 2：返回世界地图。
- cue 4：章节开场的参考曲，仅保留参考 S3M，不在从任务菜单开始的复刻路线播放。
- `sfx-manifest.json`：UI、战斗、胜利、结果和升级音效的来源/输出哈希。

旧音乐输入 `build/audio-v2/pcm/sound_NNN.wav` 的离线整曲渲染已被运行听感推翻：它自身含约 `1.4%` 的跨半幅采样突跳，会被 Maxmod 如实播放为严重撕裂。当前音乐输入改为 `build/scenario-41-original-bgm-capture-20260722-01/` 中从原 ROM checkpoint 录得的 mGBA 运行时 PCM；持久的 22050 Hz 单声道中间件位于 `butano-sequel/audio-runtime-bgm/`。生成器再去直流并输出 `butano-sequel/audio/sound_NNN.s3m`。manifest 记录当前 WAV/S3M 哈希、格式、直流偏置和增益。转换实现为 `tools/butano/generate_scenario_41_audio_assets.py`，算法参考源码固定在 `third_party/gba-wav-to-s3m-converter` 提交 `ec956fc951cc637153139cb968721f427c802e51`。

音效用 `tools/butano/generate_scenario_41_sfx_assets.py` 确定性下混为单声道并重采样到 22050 Hz。manifest 中的名称是运行时阶段语义，不是官方曲名。
