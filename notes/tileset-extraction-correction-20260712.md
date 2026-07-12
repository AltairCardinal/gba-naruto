# Tileset extraction correction (2026-07-12)

## Attempt and correction

The legacy extractor treated `0x53D910` as eight shifted rows. Re-reading the
consumer-compatible map headers proves 47 rows with stride `0x20`. Field 0 is
packed width/height, fields 1..6 are resource pointers, and field 7 is flags.

`tools/extract_tileset.py` now parses that layout, validates GBA ROM pointers,
LZ-decompresses tile graphics and exports all 47 tile atlases. The default is
grayscale raw palette indices. A colored atlas would be misleading because the
per-tile subpalette selector is not present in the tile-gfx stream; experimental
palette application is therefore opt-in.

## Result

- output: `build/tiles-v2/map_tileset_00.png` through `_46.png`
- manifest: `build/tiles-v2/manifest.json`
- extraction success: 47/47
- map 40 dimensions: 36×44
- map 40 gfx file offset: `0x118620`
- map 40 tile count: 384
- map 40 decompressed tile-data SHA-256:
  `f7d4d06c256553221a85289e152ad9a20a4ead2bb93053a19544dbffbd3444c2`
- map 40 PNG SHA-256:
  `6ab4de0f24dfa9bb331ab441846ae9fc7482b00f365911283d48fcbd32959dd7`

Regression coverage is in `tests/test_extract_tileset.py`. Important ranges:
header table `0x53D910..0x53DEF0`; map 40 header `0x53DE10`; its compressed tile
graphics begin at `0x118620`.

## Safe header writeback

The persistent `rom_map_headers` mirror now stores all 47 exact 32-byte rows,
including immutable `base_raw_hex`. Refresh uses INSERT OR IGNORE. The guarded
generator validates index 0..46, exact `_rom_offset`, base-ROM provenance,
dimensions 1..128, aligned 48 Mbit ROM pointers, `0x10` LZ headers and sane
decompressed sizes for all six non-null resource pointers before emitting one
32-byte row. `extra_ptr` alone may be null, matching the base table.

`tests/test_map_header_writeback.py` proves that map 40 width 36→32 survives a
refresh, targets `0x53DE10`, and preserves the remaining 30 bytes. It also
tests stale base, invalid dimension and non-LZ pointer rejection. This is a
safe lossless header path; only width/height currently have controlled runtime
A/B evidence. Pointer field identities remain code/format evidence plus
successful resource decompression, not six independent runtime A/B results.
