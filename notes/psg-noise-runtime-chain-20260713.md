# PSG/noise runtime chain (2026-07-13)

## Scope and corpus

The one-loop executor resolves all 16,180 notes. The only non-DirectSound
corpus is 11 notes in sound ID 144. Every one selects voice 43 and terminal
tone `0x46597C`: type `0x0C`, key 60, length 0, pointer 0, ADSR
`0/0/15/0`. The executed note key is 72, duration 6; velocities are 12×2,
32×2 and 52×7. Thus `type & 7 == 4` selects the GBA CGB channel-4 noise path;
there are no executed square or wave-channel tones to model for this ROM.

## Code chain and exact semantics

- `MidiKeyToCgbFreq` at `0x0809B494` indexes the 60-byte channel-4 table at
  file offset `0x46475C`: keys through 20 use index 0, otherwise index
  `min(key - 21, 59)`. Key 72 therefore writes NR43 `0x14`.
- NR43 encodes shift, seven-bit width, and divisor. Its clock is
  `262144 / (divisor * 2^shift)`, with divisor code zero interpreted as 0.5.
  NR43 `0x14` is 32,768 Hz and uses the 15-bit LFSR.
- The LFSR feedback is bit 0 XOR bit 1; shift right, insert feedback at bit
  14, and also at bit 6 only when the width bit is set.
- `CgbModVol` at `0x0809B58C` computes the discrete 0–15 volume goal and
  NR51 pan mask. `CgbSound` at `0x0809B5F4..0x0809BA3C` performs the hardware
  channel allocation, envelope and register writes. This tone's attack,
  decay and release are zero, so it enters sustain immediately and stops
  immediately after its six-tick gate.

The executed start vectors are:

| velocity | notes | NR41 | NR42 | NR43 | NR44 | NR51 |
|---:|---:|---:|---:|---:|---:|---:|
| 12 | 2 | `00` | `18` | `14` | `80` | `88` |
| 32 | 2 | `00` | `28` | `14` | `80` | `88` |
| 52 | 7 | `00` | `48` | `14` | `80` | `88` |

Release writes NR42 `0x08` and NR44 `0x80`.

## Durable implementation and boundary

`tools/m4a_psg.py` locks the ROM lookup, NR43 clock, 15/7-bit LFSR step,
`CgbModVol`, start vector and this tone's release vector. The full instrument
mapping records the 11 actual vectors in `build/audio-v2/instrument-map.json`;
the compact fixture is `artifacts/audio/psg-noise-evidence.json`.

This closes the executed PSG tone's code consumption and hardware-register
semantics. It does **not** yet claim a final audible render: the noise oscillator
must still be scheduled against the DirectSound mixer and written into the
combined PCM/WAV stream.
