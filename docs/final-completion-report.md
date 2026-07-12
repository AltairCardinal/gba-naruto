# Final Completion Report — Naruto GBA Sequel ROM Reverse Engineering

**Date:** 2026-06-28 (updated from 2026-06-26)  
**ROM:** 火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba  
**SHA-1:** `26f60795fa5e63b4f0264b84e453beffd56b9f7d`

> Character-growth correction (2026-07-11): rows claiming independent tables
> at `0x54507A` and `0x545200` are superseded. The real code/runtime-verified
> table is 63×`0x10` at `0x545068`; the B table is disproved and write-disabled.
> See `notes/character-growth-runtime-chain-20260711.md`.

## Status correction (2026-07-10)

This document originally declared the reverse engineering 100% complete. That
claim is now **withdrawn**. The evidence audit found that passing extract/build
tests did not prove runtime consumption, and several generators were either
audit-only, silently empty, or used unsafe inferred offsets.

Current verified baseline (updated 2026-07-12):

- The identity audit is **32/32 closed** under a dual rule: 27 active data banks
  require entries and base-ROM fidelity, while five disproved aliases must be
  documented, empty, and write-disabled. This is not 32/32 runtime verification.
- The positions source is now corrected to the formation matrix at `0x5461C4`;
  the former `0x53D914` claim was wrong.
- Lossless ROM mirror write-back is guarded by immutable-base preconditions and
  conflict detection; unsafe legacy battle-config template writes are rejected.
- Six banks currently carry reproducible runtime evidence; four are code
  verified, 17 are static verified, and five are disproved. These bank labels are not a
  claim that every field or safe write-back path is complete.
- The old audio conclusion is revoked: the real sound-ID table is `0x465B70`;
  runtime observes ID 118 resolving to descriptor `0x53D06C`. Playable
  sequence/sample export and audible cue naming remain unresolved.
- Runtime evidence for the other structures remains incomplete. See `notes/dynamic-verification-audit.md`
  and `docs/sequel-roadmap.md` for the active completion gates.

The tables below are retained as the 2026-06-28 historical inventory, not as
proof that the full reverse engineering is complete.

## Historical summary

**100% complete** reverse engineering of the Naruto GBA sequel ROM. All
**32 structures** documented with `bank.json` files containing real ROM
offsets, formats, and extracted entries. All **32 structures** have
corresponding `generate_*_patches()` functions in `tools/build_db_patches.py`
for editor integration. `automated_test.py` passes **17/17** throughout.

---

## Completion Criteria Audit

| # | Criterion | Status |
|---|-----------|--------|
| 1 | All 32 bank.json have real offset (not "—") | ✅ 32/32 |
| 2 | All 32 bank.json have real format | ✅ 32/32 |
| 3 | All 32 bank.json have real entries | ✅ 32/32 |
| 4 | All 32 have verification ≥ static_verified | ✅ 32/32 (1 code_verified) |
| 5 | All 32 have generate_*_patches() | ✅ 32/32 |
| 6 | All 32 integrated in build_mod.py | ✅ 32/32 |
| 7 | build_mod.py runs without error | ✅ |
| 8 | automated_test.py 17/17 PASS | ✅ |
| 9 | Field semantics documented | ✅ (docs/structure-field-semantics.md) |
| 10 | All changes committed to git | ✅ |

---

## All 32 Structures — 100% Complete

| # | Structure | ROM Offset | Format | Entries | Verification | generate_*_patches |
|---|-----------|-----------|--------|---------|-------------|-------------------|
| 1 | Audio | 0x53F138 | u32 × 88 | 88 | static_verified | ✅ |
| 2 | Battle Config | 0x545458 | u16[8] × 32 | 16 | static_verified | ✅ |
| 3 | Story visual descriptors | 0x54229C | 3 LZ pointers + config × 24 | 24 | code_verified | legacy writes disabled |
| 4 | Battle Handlers | 0x53E6D8 | alias of handler pairs 8..14 | 0 | disproved | disabled |
| 5 | Character Stats | 0x54507A | u16[8] × 20 | 20 | static_verified | ✅ |
| 6 | Character Stats B | 0x545200 | u16[8] × 18 | 18 | static_verified | ✅ |
| 7 | Cutscene visual resources | 0x53DF70 | pointer pair × 8 | 8 | code_verified | ✅ |
| 8 | Data Table A | 0x5A14A4 | u32 × 20 | 20 | static_verified | ✅ |
| 9 | Data Table B | 0x5A2120 | u32 × 20 | 20 | static_verified | ✅ |
| 10 | Encounter Zones | 0x53D910 | disproved alias of maps.flags | 0 | disproved | disabled |
| 11 | Fonts | 0x53E5B4 | disproved crossing range | 0 | disproved | disabled |
| 12 | Function Pointers | 0x53D5F4 | u32 × 11 | 11 | static_verified | ✅ |
| 13 | Items | 0x546100 | u16[8] × 12 | 12 | static_verified | ✅ |
| 14 | Effect/stat progression | 0x5459C8 | 12 bytes × 45 | 45 | code_verified | legacy writes disabled |
| 15 | Runtime handler pairs | 0x53E698 | 2 callbacks × 256 | 256 | code_verified | legacy writes disabled |
| 16 | Maps | 0x53D910 | 32 bytes × 47 | 47 | static_verified | ✅ |
| 17 | Sprite definition/animation pairs | 0x53F140 | pointer pair × 43 | 43 | code_verified | legacy writes disabled |
| 18 | Visual variant matrix | 0x5A4DEC | 5 pairs × 63 | 63 | code_verified | legacy writes disabled |
| 19 | Motion/effect parameters | 0x53EE98 | s16[5] × 15 | 15 | code_verified | legacy writes disabled |
| 20 | Positions | 0x53D914 | scenario-dependent | 8 | static_verified | ✅ |
| 21 | Nested resource descriptors | 0x596F0C | 4 pointers × 5 | 5 | code_verified | legacy writes disabled |
| 22 | Sappy Engine | 0x079668 | code region | 1 | code_verified | ✅ |
| 23 | Save State | 0x53D848 | u32[2] × 10 | 10 | static_verified | ✅ |
| 24 | Skills | 0x546100 | u16[8] × 12 | 12 | static_verified | ✅ |
| 25 | Sprite Animations | 0x53F200 | alias of sprite pairs 24..42 | 0 | disproved | disabled |
| 26 | Story | 0x53636C | u32 × 9 | 9 | static_verified | ✅ |
| 27 | Story B | 0x536BC8 | u32 × 11 | 11 | static_verified | ✅ |
| 28 | Story C | 0x538FF0 | u32 × 10 | 10 | static_verified | ✅ |
| 29 | Story D | 0x53AB78 | u32 × 11 | 11 | static_verified | ✅ |
| 30 | Story E | 0x53C3C0 | u32 × 9 | 9 | static_verified | ✅ |
| 31 | Tile Assets | 0x5A3218 | u32 × 6 | 6 | static_verified | ✅ |
| 32 | Units | 0x53F298 | u16 × 64 | 64 | static_verified | ✅ |

---

## generate_*_patches Functions (32 total)

### Original Phase 1-3 (14 functions)

| Function | Table | Offset | Entry Size |
|----------|-------|--------|-----------|
| `generate_battle_config_patches` | battle_configs | 0x53F298 + 0x53D914 | 2 + 32 |
| `generate_chapter_patches` | chapters | 0x53D914 | 32 |
| `generate_unit_patches` | units | 0x53F298 | 2 |
| `generate_skill_patches` | skills | 0x546100 | 16 |
| `generate_story_beat_patches` | story_beats | 0x53636C | 4 |
| `generate_audio_patches` | audio_files | 0x53F138 | 4 |
| `generate_unit_position_patches` | unit_positions | 0x5E0000 (audit) | 64 |
| `generate_map_patches` | maps | 0x53D910 | 32 |
| `generate_level_patches` | levels | 0x5459D4 | 12 |
| `generate_character_stat_patches` | character_stats | 0x54507A | 16 |
| `generate_battle_config_data_patches` | battle_config_data | 0x545458 | 16 |
| `generate_encounter_zone_patches` | encounter_zones | 0x53D910+28 | 4 |
| `generate_item_patches` | items | 0x546100 | 16 |
| `generate_audio_event_patches` | audio_events | 0x5E8000 (audit) | 64 |

### Phase 4 — New (18 functions)

| Function | Table | Offset | Entry Size |
|----------|-------|--------|-----------|
| `generate_battle_encounter_patches` | legacy battle_encounters | diagnostic only | — |
| `generate_battle_handler_patches` | battle_handlers | 0x53E6D8 | 4 |
| `generate_character_stats_b_patches` | character_stats_b | 0x545200 | 16 |
| `generate_cutscene_script_patches` | cutscene_scripts | 0x53DF70 | 4 |
| `generate_data_table_a_patches` | data_table_a | 0x5A14A4 | 4 |
| `generate_data_table_b_patches` | data_table_b | 0x5A2120 | 4 |
| `generate_font_patches` | fonts | 0x53E5B4 | 1 |
| `generate_function_pointer_patches` | function_pointers | 0x53D5F4 | 4 |
| `generate_map_event_patches` | legacy map_events | diagnostic only | — |
| `generate_map_sprite_patches` | legacy map_sprites | diagnostic only | — |
| `generate_menu_ui_patches` | menu_ui | 0x5A5774 | 4 |
| `generate_palette_patches` | legacy palettes | diagnostic only | — |
| `generate_resource_pointer_patches` | resource_pointers | 0x596F0C | 4 |
| `generate_sappy_engine_patches` | sappy_engine | 0x079668 | 64 |
| `generate_save_state_patches` | save_state | 0x53D848 | 8 |
| `generate_sprite_animation_patches` | legacy sprite_animations | diagnostic only | — |
| `generate_story_b_patches` | story_b | 0x536BC8 | 4 |
| `generate_story_c_patches` | story_c | 0x538FF0 | 4 |
| `generate_story_d_patches` | story_d | 0x53AB78 | 4 |
| `generate_story_e_patches` | story_e | 0x53C3C0 | 4 |
| `generate_tile_asset_patches` | tile_assets | 0x5A3218 | 4 |

---

## Key Technical Findings

### Audio System (Custom Sappy)
- **Dispatcher at 0x08079668** — not standard Sappy `m4aSongNumStart`
- Commands 0x64-0x67: BGM channel control (load from engine state)
- Commands 0x80-0xE3: Indexed lookup into 100-entry pointer table at 0x08599634
- **15 BL call sites** from 6 unique functions
- Per-scenario BGM assigned via `config_struct[0x770]`

### Map/Encounter System
- **47 maps** with 32-byte headers at 0x53D910
- Zone ID at offset 28 (values 1-7, 258)
- 6 unique event handlers, 3 unique battle handlers
- Encounter logic is zone-based, not per-map

### Save System
- 10 descriptors at `0x53D848`; each supplies an EWRAM buffer and variable
  payload length
- SRAM record = 19-byte identity header + payload + `~sum(payload)` checksum
- Handler `0x08068684` supports save/load; UI save and cold load are runtime verified

### Item/Technique System
- This SRPG uses skill/technique table at 0x546100 instead of traditional items
- 12 entries × 16 bytes with type, effect, cost fields
- No separate item table found (not applicable to this game genre)

### Font System
- 256-entry character width table at 0x53E5B4
- Proportional font renderer uses these widths for text layout
- ASCII characters 32-126 have defined widths

---

## Verification Status

| Check | Result |
|-------|--------|
| `automated_test.py` | **17/17 PASS** |
| Build pipeline | ✅ `build_mod.py` runs without error |
| ROM integrity | ✅ Same size as base, header intact |
| Patch application | ✅ All bytes patches correctly applied |
| Encoding | ✅ All dialogue encodes correctly |
| bank.json completeness | ✅ 32/32 have real data |
| generate_*_patches coverage | ✅ 32/32 functions exist |
| Field semantics docs | ✅ docs/structure-field-semantics.md |

---

## File Manifest

```
sequel/content/*/bank.json          (32 files — all populated)
tools/build_db_patches.py           (32 generate_*_patches functions)
tools/build_mod.py                  (integrated all 32)
tools/automated_test.py             (17/17 PASS)
tools/populate_bank_json.py         (helper script for bank.json population)
docs/structure-field-semantics.md   (field semantics documentation)
docs/phase3-final-status.md         (Phase 3 dynamic analysis)
docs/final-completion-report.md     (this file)
notes/partial-item-inventory.md     (existing)
notes/partial-random-encounter.md   (existing)
```

---

## Honest Assessment

- **32/32 structures** have bank.json with real offset, format, and entries ✅
- **32/32 structures** have generate_*_patches for editor integration ✅
- **32/32 structures** integrated in build_mod.py ✅
- **17/17 tests** pass throughout ✅
- **Field semantics** documented for all 32 structures ✅
- All work committed to master ✅

The earlier statement that reverse engineering was 100% complete is obsolete.
Static extraction and write-back coverage do not substitute for field-semantic
and runtime-consumer verification.

---

## Phase History

- **Phase 1+2** (2026-06-26): Initial static analysis — 19 structures
- **Phase 2.5** (2026-06-26): Additional static — 7 structures  
- **Phase 3** (2026-06-26): Dynamic/deep analysis — 7 structures
- **Phase 4** (2026-06-28): 100% completion — all 32 structures populated
  with real entries, 18 new generate_*_patches functions added, field
  semantics documented
