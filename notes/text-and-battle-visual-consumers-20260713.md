# Text and battle visual consumer corrections (2026-07-13)

## Character/profile description text

The historical `data-table-a@0x5A14A4` was physical entries 26..45 of the
complete 46-pointer table at `0x5A143C..0x5A14F3`. All targets are
NUL-terminated game-encoded long text. Literals at `0x0808A704` and
`0x0808B214` load the canonical base; `0x0808A6D4` indexes ID×4 and the bound
at `0x0808A6F6` is 45. The bank is now `code_verified` profile text.

## Battle/effect message text

The historical `data-table-b@0x5A2120` was physical entries 59..78 of the
complete 79-pointer table at `0x5A2034..0x5A216F`. Literals at `0x08098624`
and `0x08099D58` select the base; consumers at `0x080985D8` and `0x08099D26`
index ID×4 and pass the selected NUL text to `0x08098290`. Its 79 IDs match
the visual descriptor count.

## Battle/effect visual descriptors

`tile-assets@0x5A3218` was only descriptor 0 fields `+0x0C..+0x20`. The
canonical table is `0x5A320C..0x5A4707`, 79 records × `0x44`; four records are
valid all-zero sentinels. Nine literals load `0x085A320C`.
`0x08098442..0x08098460` computes `(input_id-1)*0x44`; consumers load the
`+0x0C` LZ graphics stream, `+0x10` LZ layout/object stream, and `+0x14`
16-byte palette source. Remaining words stay lossless and conservatively
numbered until their individual consumers are named.

## Visual variant matrix

The initial structural grouping as 31×10 pairs was still not the consumer's
index dimension. Function `0x08096138` proves the canonical formula:

`0x085A4DEC + record_id*40 + variant*8`

for variants 0..4. Variant 5 returns the special pair at `0x085A4DE4`.
Therefore the main table is 63 records × five LZ-gfx/RGB555-palette pairs,
ending at `0x5A57C4`; record 0 is intentionally all zero. The historical
`menu-ui@0x5A5774` view flattened canonical records 61 and 62.

A controlled runtime A/B then replaced only record 7 / variant 0 at `0x5A4F04`
with the valid record 3 / variant 0 pair. At the same scenario 39
`ShowPortrait(1,7,0)` step, with the same relocated script cursor and fourth
dispatch, the visible portrait changed from Kakashi to Sakura. The corrected
bank is now `runtime_verified`; compact evidence is stored in
`artifacts/runtime-checkpoints/visual-variant-runtime-evidence.json`.

All four legacy partial editor schemas are diagnostic-only.
