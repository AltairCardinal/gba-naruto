# Story bank identity correction (2026-07-12)

## Revoked conclusion

The five catalogs at `0x53636C`, `0x536BC8`, `0x538FF0`, `0x53AB78`, and
`0x53C3C0` are not story/chapter pointer tables. Their pointer counts and
similar byte prefixes were insufficient semantic evidence.

## Corrected actual container and consumer

The master table at file `0x465B70` has 8-byte entries. Entries 1, 2, 8, 11,
and 14 point respectively to `0x536368`, `0x536BC4`, `0x538FEC`, `0x53AB74`,
and `0x53C3BC`—exactly four bytes before the former bank starts.

Each object is a song descriptor. Byte 0 is `track_count`, byte 2 is priority,
byte 3 is flags, `+4` is a sequence pointer, and `+8` begins track pointers.
The old banks sliced at `+4`, so their pointer count was one sequence pointer
plus `track_count` track pointers:

| legacy bank | real descriptor | track count | former pointer count |
|---|---:|---:|---:|
| story | `0x536368` | 8 | 9 |
| story-b | `0x536BC4` | 10 | 11 |
| story-c | `0x538FEC` | 9 | 10 |
| story-d | `0x53AB74` | 10 | 11 |
| story-e | `0x53C3BC` | 8 | 9 |

`0x0809AAC0` computes `sound_id*8`, selects a 12-byte player slot from the
master row and calls song/track initializer `0x0809B1F4`. The first pointer is
sequence data, not a Thumb chapter handler.

## Durable changes

- `tools/extract_audio_resource_sets.py` extracts all 80 non-empty sound IDs.
  The graphics-named tool remains only as a compatibility wrapper.
- Only `story-c/d/e` remain disproved tombstones. `story` and `story-b` were
  reassigned to the proven chapter tables `0x60C74/0x60D54`.
- `tools/revoke_false_story_banks.py` regenerates those tombstones.
- Semantic story/chapter imports are disabled; the four `rom_story_b..e`
  generators now emit diagnostic-only records and cannot modify ROM.

The real chapter flow was subsequently closed through selector `0x0808F544`;
see `notes/chapter-flow-runtime-chain-20260712.md`.
