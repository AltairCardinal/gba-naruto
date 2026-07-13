# DirectSound mixer runtime chain (2026-07-13)

## Corrected identity

The ROM does not saturate DirectSound contributions. `SoundMain` packs each
signed contribution into one byte, adds it to the existing packed PCM word and
lets the high-byte overflow fall away. Every per-channel contribution and the
multi-channel sum therefore uses signed 8-bit modulo-256 wrap. A conventional
`clamp(-128, 127)` renderer is observably wrong.

## Executed corpus

All 16,169 DirectSound notes and all 79 reachable wave headers use type 0, the
normal forward-linear path. No executed tone uses fixed/no-interpolation,
reverse or delta modes. Seventy non-loop waves carry 8,442 notes; nine
`status & 0x4000` loop waves carry 7,727. Of the 80 songs, 58 use reverb 0 and
22 use reverb 128. These counts are regenerated in
`build/audio-v2/instrument-map.json`.

## ROM code and formulas

- `SoundMain` entry: `0x08099D8C`.
- Reverb/clear seed: `0x08099E1C..0x08099EC0`.
- ADSR and gain writes: `0x08099EC8..0x08099F82`.
- Loop/end branch: `0x0809A080..0x0809A0E4`.
- Forward-linear hot loop: `0x0809A0E8..0x0809A180`.

The source phase has 23 fractional bits. Each output sample uses:

```text
increment = u32(divFreq * step)
sample = s0 + ((phase * (s1 - s0)) >> 23)
rightContribution = (sample * gainRight) >> 8
leftContribution  = (sample * gainLeft) >> 8
right = s8((right + rightContribution) & 0xFF)
left  = s8((left  + leftContribution)  & 0xFF)
phase, advance = (phase + increment) & 0x7FFFFF, (phase + increment) >> 23
```

The right shifts are signed arithmetic shifts. `advance` may cross several
source samples or several loop lengths. At the final declared sample the engine
still pre-reads the next ROM byte as the interpolation guard; a faithful model
must not silently replace it with zero or the loop start.

For reverb, the current and previous DMA segments' right/left signed bytes are
summed. `x = (sum * reverb) >> 9`; when `x & 0x80`, the engine increments `x`
before storing the same low byte into both current planes. Reverb zero clears
the current planes. RIFF 8-bit output XORs each signed byte with `0x80` and
interleaves the right and left planes.

## Durable implementation and boundary

`tools/m4a_pcm.py` implements the signed interpolation, low-32-bit phase
advance, multi-source loop/end behavior, modulo-256 mixing, reverb seed and
stereo WAV writer. `tests/test_m4a_pcm.py` locks positive/negative half-step,
multi-sample phase advance, exact loop wrap, non-loop stop, overflow vectors,
reverb rounding and a real RIFF write/read round trip. Compact vectors live in
`artifacts/audio/directsound-mixer-evidence.json`.

This closes the sample-loop and buffer arithmetic used by the executed ROM
corpus. It does not yet produce a complete song: the remaining renderer must
schedule MP2K ticks, SoundMain invocations, note gates/envelopes, all active
channels and the already-modeled PSG oscillator onto one output timeline.
