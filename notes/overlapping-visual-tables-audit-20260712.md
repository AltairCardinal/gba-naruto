# Overlapping visual-table correction at `0x53EE98..0x53F298` (2026-07-13)

## Result

The historical `palettes`, `map-sprites`, and `sprite-animations` catalogs
overlapped and had no literal references to their claimed bases. TDD now pins
their real identities and rejects all three legacy editor shapes.

## Motion/effect parameters

Literals at `0x08080744`, `0x080807F0`, and `0x08080898` all resolve to
`0x0853EE98`. Consumers `0x080806B0`, `0x08080764`, and `0x08080814` multiply
a runtime index by ten, walk 10-byte records, and pass five signed-halfword
parameters to `0x08080218`: effect ID, signed X/Y offsets, render attributes,
and duration/control. Record 14 is `(-1,0,0,0,0)` and terminates the
chain. The historical `palettes` slug now represents these 15 code-verified
records; no RGB555 palette semantics remain.

## Sprite definition/animation pairs

`0x08080B08` loads literal `0x0853F140` and passes the table through
`0x08063494` to `0x080625A4`. At `0x08062668`, the selected ID is multiplied by
eight and the two pointers are installed at sprite-task offsets `+0x1C/+0x20`.
The independent literal `0x0853F298` closes the table at 43 records.

The historical `map-sprites@0x53F1DC` base was canonical pair 19 `+4`; its
47-word shape was misaligned. That slug now represents the complete 43-pair
table at `0x53F140`.

## Duplicate subset

`sprite-animations@0x53F200` equals `0x53F140 + 24*8`. Its former 38 u32 words
exactly flatten canonical pairs 24..42, so it is an empty, write-disabled
`disproved` tombstone superseded by `map-sprites`.

Legacy `rom_palettes`, `rom_map_sprites`, and `rom_sprite_animations` rows are
diagnostic-only until the editor adopts the corrected record schemas.
