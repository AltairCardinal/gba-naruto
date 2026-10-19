# Similar Pointer-Table Candidates

## 2026-08-09 strict-proof rescan

`find_similar_tables.py` previously referenced an undefined `ROM_BASE`, so the
current version could not be rerun and was not valid negative evidence for “no
additional structure”. After adding the missing constant and a regression test,
the full-ROM command

```bash
python3 tools/find_similar_tables.py rom/base.gba --min-rows 4
```

returns **114 heuristic candidates**. The top ranges are
`0x596D5C..0x59904C` (342 nonzero rows),
`0x5A4E14..0x5A57C4` (155), and
`0x5A2B08..0x5A2EE8` (62). The immutable scan denominator remains 114. A
separate evidence-derived overlay currently adjudicates all 114 entries: 61
`accepted`, 25 `alias_of`, and 28 `rejected`; 0 remain open. The heuristic scan
is therefore closed, while full-ROM semantic coverage remains a separate gate.

The 114-item primary output is `sequel/similar-table-candidates-v1.json`; it is
not rewritten during adjudication. Decisions live in
`sequel/similar-table-adjudications-v1.json`.
`tools/verify_similar_table_candidates.py` independently rebuilds both the scan
and all 114 evidence-backed decisions from canonical ROM slices, rejecting a
deleted candidate, deleted decision, changed range, changed evidence hash, or
changed zero terminator.

## 2026-03-28 historical scan

以下 38 条输出和旧 ROM 文件名仅保留为历史记录，不是 2026-08-09 的 114 条重扫
primary output。

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
0x596D5C-0x59903C rows=342 zero_rows=216 reused_col0=5
0x5A4E14-0x5A57C4 rows=155 zero_rows=0 reused_col0=87
0x5A2B08-0x5A2EE8 rows=62 zero_rows=0 reused_col0=0
0x599280-0x5994D0 rows=37 zero_rows=0 reused_col0=0
0x5995AC-0x5997AC rows=32 zero_rows=0 reused_col0=0
```

## Superseded scan candidate: `0x5A4E14`

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

## Corrected interpretation (2026-07-29)

The four-column profile was an artifact of the scanner. The consumer-defined
matrix begins at `0x5A4DEC`, has 63 records × 40 bytes and five
`(graphics,palette)` pairs per record. `0x5A4E14` is simply the start of record
1 after the all-zero record 0. Grouping its 310 pairs as 155×16 causes 31 rows
to cross portrait boundaries.

The existing `artifacts/menu-portraits-v1/` covers all 310 pairs in this suffix,
so candidate 100 is closed as a strict-subrange alias of the 63×40-byte source
table. The global denominator still has 45 open candidates.

## Corrected interpretation of `0x5A2B08`

This correction rejects candidate 99's aggregate 16-byte grouping while
preserving both canonical child tables. It is not negative evidence that the
full ROM contains no additional structures.

The apparent 62×16 range also crosses consumer-defined boundaries:

- `0x5A2B08..0x5A2C44`: 79 message pointers;
- `0x5A2C44..0x5A2EF4`: 172 LZ77 glyph pointers;
- `0x5A2EF4..0x5A320A`: 79×10 message/glyph bindings.

The old candidate ended after glyph 168 and silently omitted glyphs 169–171.
The complete export and independent verifier are
`artifacts/battle-presentation-glyphs-v1/`,
`tools/export_battle_presentation_glyphs.py` and
`tools/verify_battle_presentation_glyphs.py`.
