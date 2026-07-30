# Static bank identity corrections (2026-07-13)

## Fonts tombstone

`fonts@0x53E5B4` has no literal/xref. Its claimed 256-byte extent crosses the
canonical handler-pair base `0x53E698`; the final 28 bytes are Thumb pointers,
not widths. The bank is now an empty, write-disabled tombstone. Dialogue glyph
work must use the separately proven `0x53D644` lookup chain.

## Effect/stat progression records

The historical `levels@0x5459D4` base was physical record 1. The canonical
table is `0x5459C8..0x545BE3`, 45 records × 12 bytes, immediately followed by
skills at `0x545BE4`. Six literals load `0x085459C8`; consumers index ID×12 and
compute `base + per_level*(slot_level-1)`. Fields are target type, one reserved
byte, two base values, two per-level values, and a reserved u16.

## Character visual matrix alias

The earlier five-descriptor correction is itself superseded. The canonical
character battle visual matrix starts at `0x596D5C`, uses 16-byte rows, and
`0x596F0C = 0x596D5C + 27×16`. The five former
`resource-pointers@0x596F0C` records are therefore rows 27..31: character 4
visual slots 0..4. Every four-pointer tuple exactly matches
`artifacts/character-battle-visuals-v1/manifest.json`.

Literal `0x0807B278` and consumer `0x0807B220→0x080625A4` prove that this
consumer deliberately starts at the five-row subview; they do not create an
independent bank identity. `resource-pointers` is now an empty, write-disabled
tombstone, superseded by the canonical visual artifact.

Legacy `rom_fonts` and `rom_resource_pointers` rows are diagnostic-only.
Legacy high-level `levels` rows were already rejected because they lack a
lossless mapping to the corrected effect records.
