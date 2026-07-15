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

## Nested resource descriptors

`resource-pointers@0x596F0C` is five 16-byte records, each containing four
resource pointers. Literal `0x0807B278` supplies the base to `0x080625A4`; its
16-byte path indexes ID×16 and installs/copies the record fields. The former
20-u32 bank merely flattened these five records.

Legacy `rom_fonts` and `rom_resource_pointers` rows are diagnostic-only.
Legacy high-level `levels` rows were already rejected because they lack a
lossless mapping to the corrected effect records.
