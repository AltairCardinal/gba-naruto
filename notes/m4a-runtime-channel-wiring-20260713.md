# MP2K 运行时通道连接（2026-07-13）

## 结论

`tools/m4a_runtime_channels.py` 已把持久 `MPlayTrackVM` 和
`MPlayMusicalState` 产生的 `NoteRequest` 接到真实 terminal tone、10 个
DirectSound 通道和 4 个固定 CGB 通道。该层复用既有的 tone/drum 解析、ROM
pitch 表、双声道整数增益、ADSR、forward-linear sampler、priority/steal 和
track chain 实现，没有另建平行解析器。

真实 sound ID 1 的 track `0x08535CFC`、voicegroup `0x0846480C`、voice 0、
key 57 会到达 wave `0x0846606C`，step 为 11772。两个同 key 音符占用 slot 0/1，
EOT 只释放 newest slot 1；首个 264-frame stereo chunk 的 SHA-256 是
`da11e7ede6b8fa119983d90d69f526aeffb11a9a49682d9caf36aea215d5939c`。

真实 sound ID 144 的 voice 43、key 72 会到达固定 CGB channel 4，启动寄存器是
`NR41=00 NR42=18 NR43=14 NR44=80 NR51=88`。

## 纠正与持续更新

`ply_note 0x0809A79C..0x0809A8DC` 对 drum child 仍会叠加 track pitch。运行时
因此显式保留 signed coarse delta，使用 `terminal root + delta`，不能用已经下限
钳制的 `pitch_key-event_key` 反推。测试向真实 drum tone `0x08464F2C` 施加
`delta=1, fine=128`，得到 key 61、step 15273。

活跃音符随后会消费 track 的 `pitch_dirty/mix_dirty`：KEYSH/BEND/BENDR/TUNE/LFO
更新 DirectSound step（CGB noise 更新 NR43），VOL/PAN/MODT 更新 channel pre-envelope
gain；传播后清除 dirty 位。自然 sample/envelope 停止只把 status 清零，下一次
`0x0809A474..0x0809A4B8` track sweep 才解除 stale chain，代码和测试也保持这个时序。

DirectSound 不复制 CGB 分支在 `0x0809A8AE..0x0809A8C4` 使用的 tone
`length/pan_sweep` pseudo-echo 字段；此前混用已由真实 drum 向量纠正。

## 全库结构覆盖与边界

80 首、217 tracks 各执行 2048 个 track ticks，共发出 17546 个请求：17121 次
DirectSound 分配、11 次 CGB 分配、414 次 allocator rejection。该 bounded run
没有推进 SoundMain sample/envelope 生命周期，所以这三个数字只能证明每个请求都
到达解析/分配路径，**不能**解释成真实播放的声道占用或丢音统计。

机器证据在 `artifacts/audio/runtime-channel-wiring-evidence.json`。尚未闭合的是
player 级 MPlayClock/SoundMain 整曲调度、CGB envelope/noise PCM、Direct+CGB 联合
WAV、46 个跨 backward-GOTO open TIE 的真实生命周期，以及 emulator 内部 buffer
差分；因此音频整曲仍不得宣称完成。
