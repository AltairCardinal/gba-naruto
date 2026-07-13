# DirectSound pitch-step 与 mixer phase（2026-07-13）

## ROM 精确公式

`MidiKeyToFreq` 位于 `0x0809A998..0x0809A9F2`。它读取 180-byte scale 表
`0x084645C4` 与 12×u32 frequency 表 `0x08464678`，并通过
`0x08099D7C` 的 ARM `UMULL` helper 取得 unsigned product 高 32 位。

精确整数流程：

```text
if key > 178: key=178, fine=255
p0 = freq[scale[key] & 15] >> (scale[key] >> 4)
p1 = freq[scale[key+1] & 15] >> (scale[key+1] >> 4)
interp = p0 + high32((p1-p0) & 0xffffffff, fine << 24)
step = high32(wave.frequency_raw, interp)
```

没有使用 `2**()` 或浮点近似。`wave.frequency_raw` 是 Q10 Hz；key 60 / fine 0
时 `interp=0x400000`，所以 step 恰为 `frequency_raw>>10`。

`tools/m4a_pitch_step.py` 固化公式、key/fine u8 门禁、key>178 钳位和 23-bit
mixer phase。wave `0x46606C` (`frequency_raw=0x00DAC000`) 的关键向量从
key0 的 437 覆盖到 clamp 后 13528415，均由测试锁定。

## mixer 消费链

新音与持续更新分别从 `0x0809A8DC`、`0x0809A654` 调该函数，结果写
SoundChannel `+0x20`。ARM mixer `0x0809A0E8` 使用：

```text
phase += SoundInfo.divFreq * channel.step
advance = phase >> 23
phase &= 0x7fffff
```

本 ROM mode `0x0095FA00` 对应 264 samples/VBlank、PCM 15768 Hz、
`divFreq=532`。

## 全库 nominal 覆盖与边界

`map_m4a_instruments.py` 现在为全部 16169 个 DirectSound note 计算 nominal
center step：普通 tone 使用 MIDI note；drum 使用 child tone root key。79/79 waves
全部覆盖，零无效/零 step，范围 437..671241。

后续已把 `TrkVolPitSet 0x0809B3E0` 的 note-on 状态接入 timeline：KEYSH 是原始
signed s8；BEND/TUNE 以 `0x40` 为中心；BENDR 是 unsigned semitone range，默认 2。
精确组合为 `(tune+bend*bendr)<<2 + keyShift<<8`，高位是 signed key delta、低 8 位
是 fine；负 key 在 `0x0809A8A4` 钳为 0。ROM jump table `0x08464534` 的八个 handler
指针也由测试锁定。

全库 16169/16169 DirectSound notes 都得到有效 track note-on step，其中 312 条为
noncenter，范围 437..689951。真实 229 个 BEND 因而不再被完全忽略。

这仍不是完整动态 pitch timeline：LFO/MOD，以及音符已经发声后才发生的
KEYSH/BEND/TUNE 命令尚未输出 automation。不能把 note-on coverage 宣称为整曲
bit-accurate pitch。

紧凑证据：`artifacts/audio/pitch-step-evidence.json`。
