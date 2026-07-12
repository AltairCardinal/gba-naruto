# Real audio engine and runtime chain (2026-07-12)

## Result

The former audio identities are revoked. `0x53F138` is a palette table, while
`0x599634` / `0x08079668` are a message table and dispatcher. The real chain is:

`0x08061E6C` public wrapper → `0x0809AAC0` sound-ID dispatcher →
`0x08465B70 + sound_id*8` → player slot `+ player_index*12` →
song/track initializer `0x0809B1F4`.

The hardware initializer at `0x0809AE3C` writes GBA sound, FIFO and DMA
register families including `0x04000060`, `0x04000080`, `0x04000084`,
`0x040000A0` and `0x040000A4`.

## Formats

The sound-ID domain is 0..158. ID 159 is not a row: its would-be location is
already empty-descriptor data at `0x466068`. There are 80 non-empty IDs:
1..18, 51..54, and 101..158. Empty IDs point to `0x08466068`.

Master row (8 bytes): descriptor pointer at `+0`, player index u16 at `+4`,
and a losslessly retained, not-yet-named u16 at `+6`.

Song descriptor is an m4a `SongHeader`: byte 0 track count; byte 1 block count
(the earlier “reverb” label is withdrawn); byte 2 priority; byte 3 reverb;
`+4` is the voicegroup/tone-table pointer; `+8` contains `track_count` track
sequence pointers. This corrects both the old `0x800000NN`
interpretation: count is byte 0, not the low 24 bits. ID 51 starts
`07 00 0A 80`; the old interpretation would yield impossible count `0x0A0007`.

## Reachable track and wave extraction

`tools/extract_audio_assets.py` follows the corrected pointer graph instead of
scanning arbitrary ROM byte patterns. On the base ROM it reproducibly exports:

- 80 active songs/SFX descriptors;
- 217 exact track command blobs, bounded by the next track or descriptor;
- 23 referenced voicegroup starts and 387 structurally valid tone records;
- 79 unique non-empty DirectSound waves reachable from type-0 tones.

The wave header is 16 bytes: u16 type, u16 status, u32 fixed-point frequency,
u32 loop start, u32 sample count, then signed 8-bit PCM. For example wave
`0x46606C` has frequency `0x00DAC000 / 1024 = 14000 Hz`, loop start 10505,
20789 samples, and PCM begins at `0x46607C`. WAV export converts signed ROM PCM
to the unsigned 8-bit representation required by RIFF. Outputs and a manifest
are in `build/audio-v2/`. The legacy `tools/extract_audio.py` 12-byte heuristic
is explicitly superseded.

## Runtime proof

`tools/build_audio_runtime_probe.py` replaces only the checked BL at
`0x08061E72` and a zero-filled stub at `0x0809E800`. It records hit count,
first/last sound ID and resolved descriptor at `0x0203FF60`, then calls the
original dispatcher.

The title/new-game run did not reach the strict battle gate, so it is not
battle evidence. It nevertheless produced independent audio evidence:

- raw scratch `e600000076000000760000006cd05308`
- 230 wrapper calls
- first and last sound ID 118 (`0x76`)
- resolved descriptor `0x0853D06C`
- base master row 118 independently contains `0x0853D06C`, player config
  `0x00020002`

This proves the sound-ID table at runtime. It does not yet name the audible cue
or prove every descriptor field.

## Durable artifacts and important ranges

- `tools/extract_audio_resource_sets.py`, `tools/extract_audio_engine.py`,
  `tools/extract_audio_assets.py`
- `tools/build_audio_runtime_probe.py`
- `sequel/content/audio/bank.json`, `sequel/content/sappy-engine/bank.json`
- persistent editor mirror `rom_audio_sound_ids`; refresh uses INSERT OR IGNORE
  so edits survive re-import. `generate_audio_sound_id_patches` validates the
  sparse ID, exact row offset, immutable base descriptor/config, ROM pointer
  range/alignment and target track count before emitting an 8-byte real write
- master `0x465B70..0x466067`; descriptors `0x536368..0x53D58B`; engine code
  around `0x09AA3C..0x09B3DA`
