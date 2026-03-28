# Resource Table Analysis: `0x596F98`

Date: `2026-03-28`

## Summary

The region near `0x596F98` is now best described as a fixed-size resource descriptor table with `0x10`-byte entries.

Each non-empty entry contains four ROM pointers. The columns are not equivalent.

Current working model:

- column 0: palette-like or shared base resource
- column 1: nested descriptor block
- column 2: sparse binary or secondary resource block
- column 3: sparse binary, likely mask/attribute/tile-layout-adjacent data

## Evidence

Tool outputs:

- `notes/table-596F98-10.json`
- `notes/table-596F98-20.json`
- `notes/profile-596F98.json`
- `notes/block-17A1A4.json`
- `notes/block-17ED7C.json`
- `notes/block-17EDA8.json`
- `notes/block-17D904.json`

Representative rows:

```text
row 1 @ 0x596FA8: 0x0817A1A4, 0x0817ED7C, 0x0817EDA8, 0x0817D904
row 2 @ 0x596FB8: 0x0817A1A4, 0x08180224, 0x08180254, 0x0817EDAC
row 3 @ 0x596FC8: 0x0817A1A4, 0x081822D0, 0x081822FC, 0x08180258
row 4 @ 0x596FD8: 0x0817A1A4, 0x08183F78, 0x08183FB0, 0x08182300
```

Column profile summary:

```text
col 0: non_pointer=2, palette_like=10
col 1: nested_descriptor=10, non_pointer=2
col 2: binary_or_compressed=1, nested_descriptor=2, non_pointer=2, palette_like=1, sparse_binary=6
col 3: non_pointer=2, sparse_binary=10
```

## Key block interpretations

### `0x17A1A4`

- Best current classification: `palette_like`
- First 16 halfwords all fit GBA color range `0x0000-0x7FFF`
- Matches the shape of palette data better than compressed graphics

### `0x17ED7C`

- Best current classification: `nested_descriptor`
- Starts with five ROM pointers:

```text
0x0817ED04
0x0817ED1C
0x0817ED34
0x0817ED4C
0x0817ED64
```

- Followed by compact numeric fields such as:

```text
0x00080000
0x00060002
0x00040001
0x00040003
0x00080004
```

These values look more like dimensions, indices, or subresource layout descriptors than executable code.

### `0x17EDA8` and `0x17D904`

- Best current classification: `sparse_binary`
- High zero ratio
- May be masks, per-tile flags, layout fragments, or other compact metadata blocks

## What this probably means

This table is likely indexing visual resources rather than chapter scripts or game logic.

That is useful because:

- it gives a reliable example of the ROM's descriptor style
- it confirms nested resource records are used in this game
- it provides a template for how other data systems may also be organized

## Recommended next targets

The most productive next technical tasks are:

1. Walk the nested descriptor pointed to by column 1 and determine its exact field layout
2. Identify whether columns 2 and 3 are paired mask/tilemap/attribute data
3. Search for analogous `0x10`-byte pointer tables elsewhere in ROM
4. In parallel, shift one branch of work toward text and script discovery, since graphics/resource tables alone will not unlock sequel authoring

## Practical implication for sequel work

This result improves confidence that the ROM is data-driven in at least some subsystems, but it does not yet prove chapter flow is equally editable. The next strategic priority should therefore split in two:

- continue resource table decoding for general ROM format knowledge
- start a dedicated text/script attack path for scenario and event editing
