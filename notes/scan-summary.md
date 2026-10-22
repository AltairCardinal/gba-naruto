# Initial Scan Summary

Date: `2026-03-28`

ROM scanned with:

```bash
python3 tools/scan_rom.py '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba'
```

## High-level results

- ROM size: `6291456` bytes (`0x600000`)
- aligned in-ROM pointers: `22252`
- unique pointer targets: `16446`
- ASCII-like runs kept in report: `256`
- zero runs kept in report: `256`

The JSON report is stored at:

- `notes/scan-report.json`

## Findings worth pursuing

### 1. `0x004081` is a strong candidate anchor

- It is the hottest target in the first scan with `557` references.
- The bytes around it are highly repetitive and non-ASCII.
- This could be a shared text block, dictionary-like structure, or another repeatedly referenced resource.

Hex sample:

```text
00004081: 9c825482 4f819300 00000000 00000000
00004091: 00000000 00000000 000095b6 97cf8c5b
000040a1: 825094c8 8b628c5e 9ac39144 96de959c
```

### 2. `0x17A1A4` looks structured, not random

- It has `97` references in the pointer scan.
- The data includes short repeated patterns and long zero padding.
- This shape is compatible with tile, palette, animation frame, or fixed-size table data.

Hex sample:

```text
0017a1a4: 187e8410 2a2df14a 2b327f63 593e701d
0017a1b4: ce3d4a2d a965c638 ff7f5a77 945a2104
0017a1c4: 00000000 00000000 00000000 00000000
```

### 3. `0x09E6EE` is a promising free-space candidate

- The zero-filled run starts at `0x09E6EE`
- Observed zero-filled length is at least `1100` bytes

This is not enough to assume it is globally safe, but it is a strong place to validate pointer redirection or tiny injected data blocks later.

## What this scan did not solve

- It did not locate actual Chinese script text yet.
- It did not identify compression formats.
- It did not distinguish code pointers from asset pointers.
- It did not isolate chapter, map, or unit tables.

## Recommended next step

The next tool should focus on one of these:

1. Pointer back-reference explorer for a chosen target offset
2. Binary block classifier for likely graphics/palette/compressed regions
3. Text-search helper for Shift-JIS-like or custom double-byte ranges

The most practical next move is `1`, because it will show which ROM areas reference `0x004081` and whether those callers look like pointer tables or code.

## Follow-up: pointer back-reference results

Tool used:

```bash
python3 tools/find_pointer_refs.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x4081 \
  --output notes/pointer-refs-004081.json

python3 tools/find_pointer_refs.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x17A1A4 \
  --output notes/pointer-refs-17A1A4.json
```

### `0x004081`

- References found: `557`
- Current heuristic could not classify these references cleanly.
- Early references are widely distributed in low ROM offsets such as `0x000C64`, `0x001628`, `0x005924`.

Interpretation:

- This does not yet look like one neat central table.
- It may be a broadly reused encoded resource, dictionary block, or script-related structure.
- It is not the best next target for rapid structural progress.

### `0x17A1A4`

- References found: `97`
- All current matches classify as `likely_pointer_table`
- References cluster in the `0x596FA8` and later `0x59xxxx` regions

Hex around the first cluster:

```text
00596f90: 00000000 00000000 00000000 a4d71708
00596fa0: d4d81708 c4a11708 a4a11708 7ced1708
00596fb0: a8ed1708 04d91708 a4a11708 24021808
00596fc0: 54021808 aced1708 a4a11708 d0221808
```

Interpretation:

- This region strongly resembles a resource descriptor table.
- The recurring `0x0817A1A4` pointer appears interleaved with nearby `0x0817xxxx` and `0x0818xxxx` addresses.
- The layout shows repeated `16-byte` stepping between occurrences, which is a strong sign of fixed-size entries.

Updated recommendation:

The next reverse-engineering step should shift from “follow a hot target” to “decode the structure of the pointer table around `0x596F90`”. That is more likely to expose reusable asset formats and chapter/resource indexing.

## Follow-up: table structure analysis

Tool used:

```bash
python3 tools/analyze_table.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x596F98 \
  0x10 \
  16 \
  --output notes/table-596F98-10.json
```

Comparison run:

```bash
python3 tools/analyze_table.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x596F98 \
  0x20 \
  8 \
  --output notes/table-596F98-20.json
```

### Key result

The `0x10`-byte interpretation is more convincing than `0x20`.

Observed rows:

```text
row 1 @ 0x596FA8: 0x0817A1A4, 0x0817ED7C, 0x0817EDA8, 0x0817D904
row 2 @ 0x596FB8: 0x0817A1A4, 0x08180224, 0x08180254, 0x0817EDAC
row 3 @ 0x596FC8: 0x0817A1A4, 0x081822D0, 0x081822FC, 0x08180258
row 4 @ 0x596FD8: 0x0817A1A4, 0x08183F78, 0x08183FB0, 0x08182300
```

Interpretation:

- This looks like a sequence of four-pointer descriptors.
- The first field is often reused across adjacent entries.
- The later fields advance through nearby resource regions.
- Empty entries are represented as all-zero rows.

### Secondary structure clues

Data at `0x17ED7C` begins with additional pointers and then small integer-looking fields:

```text
0017ed7c: 04ed1708 1ced1708 34ed1708 4ced1708
0017ed8c: 64ed1708 00000800 02000600 01000400
0017ed9c: 03000400 04000800 ffff0000 90ed1708
```

This is a strong sign that the first-level table points to descriptor blocks, not directly to decoded graphics or map data.

### Current working model

The region near `0x596FA8` is likely a resource table whose entries each contain four references:

- a shared base/header-like block
- one or more variant/resource blocks
- a secondary descriptor block

That is not proven yet, but it fits the repeated pointer patterns better than a flat graphics table.

## Recommended next step

The next tool should walk one level deeper:

1. Given a table entry, inspect each pointed block
2. Detect whether the pointed block starts with more ROM pointers
3. Estimate the local structure size and whether the block looks like:
   - nested descriptor
   - palette-like data
   - compressed binary
   - raw tile data

This should let us label the four columns in the `0x596FA8` table instead of only observing repetition.

## Follow-up: column role profiling

Tool used:

```bash
python3 tools/profile_table_blocks.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x596F98 \
  0x10 \
  16 \
  --output notes/profile-596F98.json
```

Key result:

```text
col 0: non_pointer=2, palette_like=10
col 1: nested_descriptor=10, non_pointer=2
col 2: binary_or_compressed=1, nested_descriptor=2, non_pointer=2, palette_like=1, sparse_binary=6
col 3: non_pointer=2, sparse_binary=10
```

This materially strengthens the working interpretation of the table:

- column 0 is most likely palette-like/shared base resource data
- column 1 is consistently a nested descriptor layer
- columns 2 and 3 are downstream binary resource blocks, probably layout, mask, or attribute related

That means the `0x596FA8` table is not just “some pointers”; it is a typed resource descriptor table. This is the first subsystem in the ROM for which the project now has a credible structural model.

## Follow-up: text-region reconnaissance

Tool used:

```bash
python3 tools/find_sjis_blocks.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  --output notes/sjis-blocks.json
```

This scan is heuristic and noisy, but it produced several promising low-ROM blocks that decode as Shift-JIS-shaped text:

- `0x00076C`
- `0x000919`
- `0x00099D`
- `0x000BFE`
- `0x000C3D`
- `0x000C75`
- `0x000CF3`

Interpretation:

- the ROM likely still contains ordinary text-like byte streams in at least one subsystem
- the low ROM region is a better text target than the large high-offset false positives
- the project now has a second productive reverse-engineering branch besides graphics/resource descriptors

## Follow-up: stricter text extraction

Outputs:

- `notes/text-block-00076C.json`
- `notes/text-block-000C3D.json`

The `0x00076C` bank extracted as one large, newline-heavy string list. That is consistent with menu/help/tutorial text.

The `0x000C3D` bank extracted as mixed text and compact binary fragments, which suggests the surrounding system may embed tiny control records between strings.

## Follow-up: broader table search

Outputs:

- `notes/similar-tables.json`
- `notes/table-5A4E14-10.json`
- `notes/profile-5A4E14.json`

This search found `38` late-ROM candidates for `0x10`-byte four-pointer tables. The strongest verified additional candidate is `0x5A4E14`, which appears to be another asset bank but with a flatter profile than `0x596FA8`.

This changes the ROM model in an important way:

- there is probably not just one resource-table schema
- the game likely uses multiple table families for different asset classes
