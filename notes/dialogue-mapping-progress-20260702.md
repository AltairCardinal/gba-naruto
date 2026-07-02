# Dialogue Mapping - Deep Progress (2026-07-02)

## What I've verified through ~4 hours of investigation

1. **BREAKTHROUGH commit 473a737 partially wrong**:
   - IWRAM 0x78 holds a record index, NOT a ROM file offset
   - LE-correct pointers point to records at ROM 0x8DF0-0xB8EB
   - Records contain cp932 SJIS JAPANESE text (verified via cp932 decode)

2. **Records are cp932 SJIS-encoded Japanese dialogue**:
   - State 0 record at 0x8D99 decodes as cp932 to Japanese text like
     "絈・尖・夜夜訴嬉煮瓜奇移訴……奇妓訴嬉扶誼誘嬉煮瓜奇移訴……"
   - These are valid Japanese kanji/kana (e.g., 奇 = strange, 訴 = complaint)

3. **Renderer chain (verified via capstone disasm)**:
   - 0x0808942C (THUMB): function start, sets r6 = r0 (= dialogue data ptr)
   - 0x0808947A: `ldr r6, [pc, #0xe0]` → r6 = literal pool value 0x0201BD48 (EWRAM addr)
   - 0x0201BD48 contains ptr 0x06002000 (VRAM char base for tile rendering)
   - So dialogue data flows: records → SJIS bytes → tile indices → VRAM tiles → screen

4. **Tile graphics replaced by 熊组汉化**:
   - Original ROM has Japanese kanji tiles
   - 熊组汉化 patched tiles to display Chinese chars
   - Same SJIS bytes now produce Chinese on screen
   - Tile data at 0x6000000-0x600FFFF (BG char) is largely blank/white in my captures

5. **Text tiles found in WRAM 0x0200A900**:
   - Breakthrough's captures show tile_idx 304-309, 292-297, 314-317 for text
   - Tile graphics for these indices are at VRAM 0x604C00+, 0x604880+, 0x605080+
   - These regions are NOT in my captured VRAM ranges

6. **Captured data so far** (under /tmp/):
   - `ewram-v1/` (30 states): EWRAM 0x0201BD48 area + IWRAM 0x78 pointer
   - `vram-bg-v1/` (30 states): All 4 BG tilemaps + control registers
   - `vram-tile-v1/` (30 states): VRAM 0x6002000-0x600A000 tile graphics (32KB)
   - `vram-bg3-char-v1/` (30 states): VRAM 0x6000000-0x6002000 BG3 char data
   - `oam-v1/` (30 states): OAM sprite attribute table

## What's missing to complete the mapping

1. **VRAM 0x604000-0x608000** capture (where dialogue text tiles should be)
2. **Tile graphics rendering** to identify which Chinese char each tile represents
3. **Alignment** between cp932-decoded records and VRAM tile indices
4. **Multiple dialogue frames** captured at different states to expand mapping

## Final puzzle

The records at ROM 0x8DF0+ contain cp932 SJIS Japanese text (Japanese kanji/kana).
Each SJIS byte pair decodes to a Japanese char. The same SJIS bytes display as
Chinese chars on screen (due to 熊组汉化 tile replacement).

To build the SJIS→Chinese mapping, I need:
- VRAM tile graphics (to know which Chinese char each tile shows)
- Cross-reference with OCR'd Chinese text
- This gives: tile_idx → Chinese char
- Then: SJIS bytes → tile_idx → Chinese char

But the records contain cp932 JAPANESE text. The relationship between SJIS bytes
and tile indices depends on the game's FONT TABLE which I haven't located yet.

## Status

The dialogue mapping research has:
- ✅ Identified IWRAM 0x78 as record index (not ROM offset)
- ✅ Decoded records as cp932 SJIS Japanese text
- ✅ Located the renderer chain (literal pool → EWRAM ptr → VRAM base)
- ✅ Found text tile indices in WRAM 0x0200A900 buffer
- ❌ Located the FONT TABLE mapping SJIS bytes to tile indices
- ❌ Extracted the tile graphics for text tiles
- ❌ Built the comprehensive SJIS→Chinese mapping

## Tools shipped

- `tools/decode_dialogue_record.py` - decodes records using existing 20-char mapping
- `tools/decode_dialogue_record.py` - decodes records as cp932 (for Japanese text)
