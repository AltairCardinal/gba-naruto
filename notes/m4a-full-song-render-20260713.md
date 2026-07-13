# MP2K 整曲 PCM 与 CGB 联合输出（2026-07-13）

## 结果

`tools/m4a_song_engine.py` 现以 player 为单位连接 MPlay tempo accumulator、全部
track VM、gate/EOT/FINE、dirty pitch/mix 传播、10+4 通道池、DirectSound ADSR/
sampler、CGB channel-4 noise 和 6×264 reverb ring。每次 SoundMain 先执行该
player 所有到期 tick，再更新 CGB，最后混合一个 264-frame DirectSound chunk。

`tools/render_m4a_pcm_bank.py` 对 80 个有效 sound ID 生成 stereo 8-bit RIFF：

- 62/62 无 GOTO 的一次性音效全部由 FINE 加声道尾音自然结束，最长是 sound 54
  的 410 次 SoundMain；
- 18/18 循环曲等待每条含 GOTO 的 track 都实际执行首次 GOTO，无一触及 7200
  次安全上限；共执行 138 个 GOTO；
- 80/80 PCM 都有非零帧；总计 12,664,872 frames、约 803.20 秒；
- 15,816 次 DirectSound allocation、11 次 CGB allocation、436 次在真实
  SoundMain 生命周期中的 allocator rejection；
- sound 144 的 11 个 channel-4 N06 连续重触发，第二个 chunk 起持续有声，
  第 68 次调用 FINE 后停止；PCM SHA-256 为
  `70eb804979782044634fa3b307cff5fdf84c6a6da04e0b09aa299a5176c2253d`。

完整 80 行证据在 `artifacts/audio/full-song-render-evidence.json`，WAV 与 build
manifest 位于 `build/audio-v2/pcm/`。

## CGB 与 DirectSound 的硬件尺度

ROM 初始化在 `0x0809AD2A` 写 NR50=`0x77`，并在 `0x0809AE7A` 写
SOUNDCNT_H=`0xA90E`：PSG 为 100%，两个 DirectSound FIFO 也为 100%，A/B 分别
路由左右。GBATEK 的 SOUNDCNT_L/H 位定义与 mGBA 的 GBA `_sample` 实现共同确认：
DirectSound signed byte 在硬件内部左移 2；PSG 经 SOUNDCNT_H volume shift 后相加，
最终应用 10-bit bias clamp。

本 ROM 唯一执行的 PSG tone 是 NR43=`0x14`、32,768 Hz、15-bit LFSR。NR50=7、
PSG volume mode=2 时，channel-4 当前 0..15 volume 映射到 DirectSound byte 平面
的 `noise_bit * volume * 4`，再和 DirectSound 相加并钳到 -128..127。相位累加器
把 32,768 Hz LFSR transition 放到 15,768 Hz 的同一 PCM 时间轴；重触发重置 LFSR。

参考实现：

- GBATEK GBA sound control：<https://mgba-emu.github.io/gbatek/#gba-sound-control-registers>
- mGBA GBA hardware mixer：<https://github.com/mgba-emu/mgba/blob/master/src/gba/audio.c>
- mGBA PSG/noise：<https://github.com/mgba-emu/mgba/blob/master/src/gb/audio.c>

## GOTO / TIE 边界纠正

旧 one-loop MIDI 报告的 46 个 `open TIE` 表示“到结构分析截断点没有显式 EOT”，
不等于 46 个硬件 channel 都仍活跃。整曲引擎不会在 backward GOTO 截断；138 条
循环 track 都执行到目标命令。首次 GOTO 快照共有 21 个 active tied channel，
分布于 sound 3/7/8/10/11/13；它们跨边界保留。其余结构 open TIE 在到达快照前
已受 sample 结束、channel replacement 或后续命令生命周期影响。两个数字属于
不同层级，均保留，不能再把 46 直接解释为硬件泄漏。

## 尚未闭合的强门槛

独立动态差分现已闭合：sound 101 的 79/79 个 264-frame 双声道 Direct FIFO 块与
离线引擎逐字节一致；sound 144 的 68/68 组可读 NR4x/NR51 和 channel-4 status
时间线一致，详见 `notes/m4a-emulator-differential-20260713.md`。当前批量工具仍按
“单 cue、隔离 player”渲染；同一 player slot 的 retrigger/stop、多个 linked player
同时播放、全局 CGB pool 竞争仍需单独闭合。80 个 cue 的玩家可见语义命名也尚未
完成。因此不得把音频或全项目提前标为 100%。
