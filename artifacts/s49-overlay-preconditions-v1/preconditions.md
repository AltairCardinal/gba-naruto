# S49 覆盖层 1:1 接线的前置核对（自动生成）

本文件由 `tools/butano/verify_s49_overlay_preconditions.py` 生成，不要手工编辑。

| 核对项 | 结果 |
| --- | --- |
| `tiles` | ✅ 通过 |
| `visible_window` | ✅ 通过 |
| `source_identity` | ✅ 通过 |
| `upload` | ✅ 通过 |

## `tiles`

- **blocks_compared**: 32
- **original_bytes**: 1024
- **expanded_bytes**: 2048
- **expansion_rule**: v==0 -> 0, 1<=v<=11 -> 224+v, v>11 -> 0

## `visible_window`

- **scroll**: {'hoffs': 240, 'voffs': 24}
- **formula**: entry[(row + 3) % 32][(column + 30) % 32]
- **states**: {'banner-frame-v1': {'scroll': {'hoffs': 240, 'voffs': 24}, 'declared_matches_formula': True, 'palette_banks': [12], 'tile_indices': [256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 278, 279, 280, 281], 'distinct_tiles': 14, 'lit_entries': 580}, 'field-frame-v1': {'scroll': {'hoffs': 240, 'voffs': 24}, 'declared_matches_formula': True, 'palette_banks': [12], 'tile_indices': [256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 278, 279, 280, 281], 'distinct_tiles': 14, 'lit_entries': 580}, 'grid16-frame-v1': {'scroll': {'hoffs': 152, 'voffs': 40}, 'declared_matches_formula': True, 'palette_banks': [12], 'tile_indices': [256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 270, 272, 278, 279, 280, 281], 'distinct_tiles': 16, 'lit_entries': 573}, 'movegrid-frame-v1': {'scroll': {'hoffs': 240, 'voffs': 24}, 'declared_matches_formula': True, 'palette_banks': [12], 'tile_indices': [256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 278, 279, 280, 281], 'distinct_tiles': 14, 'lit_entries': 580}}

## `source_identity`

- **finding**: the S49 battle overlay's closed original side is the remake tree's own runtime receipt, not a reverse family; the reverse family overview-gradient-overlay-v1 is the character overview gradient overlay on BG0
- **consequence**: W2 is not blocked on a missing reverse family -- but W4's 'the original side is already closed' premise must be read as 'the closed side is in this tree, in a runtime receipt'
- **facts**: {'reverse_family': {'id': 'overview-gradient-overlay-v1', 'layer': 'BG0', 'palette_bank': 13, 'tile_count': 11, 'tilemap_dimensions': [30, 20], 'checkpoint': 'artifacts/runtime-checkpoints/alternate-character-overview.ss9', 'controller': '0x0808DCE0'}, 's49_overlay_source': {'id': 'artifacts/s49-original-movegrid-tilemap-v1', 'layer': 'BG2', 'palette_bank': 12, 'tile_count': 32, 'tilemap_dimensions': [32, 32], 'checkpoint': 'artifacts/s49-remake-walk-20261021-v1', 'controller': 'the S49 battle controller'}}

## `upload`

- **logical_tiles_now**: 77
- **logical_tiles_new**: 52
- **bytes_now**: 4928
- **bytes_new**: 3328
- **delta_bytes**: -1600
- **tile_pages_now**: 3
- **tile_pages_new**: 2
- **map_bytes**: 2048
- **base_alignment_bytes**: 64
