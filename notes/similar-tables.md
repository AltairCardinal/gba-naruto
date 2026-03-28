# Similar Pointer-Table Candidates

Date: `2026-03-28`

Primary scan output:

- `notes/similar-tables.json`

Tool used:

```bash
python3 tools/find_similar_tables.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  --start 0x500000 \
  --min-rows 4 \
  --output notes/similar-tables.json
```

## Summary

The late-ROM region contains many `0x10`-byte pointer-table candidates, which supports the idea that this game organizes a large amount of resource data through regular four-pointer descriptor records.

Top candidates found:

```text
0x596D5C-0x59904C rows=342 zero_rows=217 reused_col0=0
0x5A4E14-0x5A57C4 rows=155 zero_rows=0 reused_col0=87
0x5A2B08-0x5A2EE8 rows=62 zero_rows=0 reused_col0=0
0x599280-0x5994D0 rows=37 zero_rows=0 reused_col0=0
0x5995AC-0x5997AC rows=32 zero_rows=0 reused_col0=0
```

## Verified follow-up candidate: `0x5A4E14`

This region was inspected directly with:

```bash
python3 tools/analyze_table.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x5A4E14 \
  0x10 \
  8 \
  --output notes/table-5A4E14-10.json

python3 tools/profile_table_blocks.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x5A4E14 \
  0x10 \
  8 \
  --output notes/profile-5A4E14.json
```

Representative rows:

```text
row 0 @ 0x5A4E14: 0x08408BD8, 0x084098C4, 0x08409944, 0x0840A6A4
row 1 @ 0x5A4E24: 0x0840A724, 0x0840B4F8, 0x0840B578, 0x0840C260
row 2 @ 0x5A4E34: 0x0840C2E0, 0x0840D128, 0x0840DF00, 0x0840E9D8
```

Column profile summary:

```text
col 0: binary_or_compressed=5, palette_like=3
col 1: palette_like=8
col 2: binary_or_compressed=3, palette_like=5
col 3: palette_like=8
```

## Interpretation

`0x5A4E14` is probably not the same subtype as `0x596FA8`.

Differences:

- it is denser, with no zero rows in the sampled region
- it points mostly into the `0x40xxxx` ROM range
- it lacks the obvious nested-descriptor pattern seen in column 1 of `0x596FA8`

Working model:

- `0x596FA8` looks like a layered descriptor table
- `0x5A4E14` looks like a flatter visual asset bank

This is useful because it suggests the ROM may use more than one standardized resource-table schema rather than a single universal format.
