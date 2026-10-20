#!/usr/bin/env python3
"""
Phase 5.3 — Extract ALL text segments from the dialogue region.

The dialogue pointer table at 0x461CE8 references 50 dialogue slots
(some null), but the actual dialogue text region (0x458000-0x460000)
contains 200+ additional text blocks. These are referenced indirectly via
game engine state or are unused slots from the development process.

This script extracts all segments and writes dialogue-bank-full.json.
The importer then loads them into editor.db.

Encoding (corrected 2026-10-20):
    The ROM does NOT store Shift-JIS.  It stores a custom double-byte font
    code (lead byte 0x80..0x9F) that indexes the ROM's own bitmap font.
    Decoding those bytes as cp932/gbk produced the mojibake this script used
    to emit.  See notes/font-encoding.md and
    notes/text-writeback-migration-20261020.md.

    Consequence: this ROM is the 熊组 Chinese localization, so the decoded
    text *is* the Chinese text.  There is no recoverable original Japanese
    here - the Japanese was replaced by the patch.  `text_zh` therefore holds
    the real text, and `text_ja` mirrors it so the editor shows readable
    content in the column it edits.
"""
import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools import text_codec  # noqa: E402

ROM_PATH = Path('build/naruto-sequel-dev.gba')
OUTPUT = Path('sequel/content/text/dialogue-bank-full.json')


def safe_decode(data: bytes, encoding: str) -> str:
    """Decode bytes, stopping at first error. Returns decoded string + truncation flag."""
    out = bytearray()
    for i, b in enumerate(data):
        if b == 0x00:
            break
        out.append(b)
    # Try progressively shorter prefixes until one decodes
    for j in range(len(out), max(len(out) - 16, 0), -1):
        try:
            return out[:j].decode(encoding)
        except UnicodeDecodeError:
            continue
    return ''


def main():
    rom = ROM_PATH.read_bytes()
    print(f'ROM: {ROM_PATH} ({len(rom)} bytes)')

    mapping, _ = text_codec.load_mapping()

    def font_decode(raw: bytes) -> str:
        """Decode ROM text bytes with the game's own font codes."""
        return text_codec.decode(raw, mapping)

    # Region 1: dialogue pointer table at 0x461CE8 (50 entries)
    # This is the canonical dialogue slot list.
    table_offset = 0x461CE8
    dialogue_entries = []
    for i in range(50):
        pos = table_offset + i * 4
        if pos + 4 > len(rom):
            break
        ptr = struct.unpack('<I', rom[pos:pos + 4])[0]
        if ptr == 0:
            dialogue_entries.append({
                'idx': i, 'slot': f'group{i}',
                'empty': True, 'ptr': 0,
            })
            continue
        if 0x08000000 <= ptr <= 0x09000000:
            text_offset = ptr - 0x08000000
        else:
            text_offset = ptr
        if text_offset >= len(rom):
            continue
        raw = rom[text_offset:text_offset + 200]
        # Find real length
        real_len = 0
        for j in range(200):
            if text_offset + j >= len(rom) or rom[text_offset + j] == 0x00:
                real_len = j
                break
        text = font_decode(raw[:real_len])
        dialogue_entries.append({
            'idx': i, 'slot': f'group{i}',
            'text_ja': text,
            'text_zh': text,
            'raw_hex': raw[:real_len].hex(),
            'text_len': real_len,
            'text_offset': text_offset,
            'ptr': ptr,
            'source': 'dialogue_pointer_table@0x461CE8',
        })

    # Region 2: 0x458000-0x460000 — large SJIS/GBK text region
    # This contains the bulk of 熊组's Chinese localization.
    region2 = []
    region_start, region_end = 0x458000, 0x460000
    i = region_start
    seg_idx = 0
    while i < region_end:
        while i < region_end and rom[i] == 0x00:
            i += 1
        if i >= region_end:
            break
        seg_start = i
        while i < region_end and rom[i] != 0x00:
            i += 1
        seg = rom[seg_start:i]
        if len(seg) >= 20:
            text_ja = font_decode(seg)
            text_zh = text_ja
            cn_count = sum(1 for c in text_zh if '\u4e00' <= c <= '\u9fff')
            region2.append({
                'idx': seg_idx,
                'slot': f'textblock_{seg_start:06X}',
                'text_ja': text_ja,
                'text_zh': text_zh,
                'cn_char_count': cn_count,
                'raw_hex': seg.hex(),
                'text_len': len(seg),
                'text_offset': seg_start,
                'source': f'region_0x458000-0x460000',
            })
            seg_idx += 1

    # Region 3: 0x00076D — title screen text
    region3 = []
    title_start = 0x00076D
    title_seg = rom[title_start:title_start + 412]
    text_ja = font_decode(title_seg)
    text_zh = text_ja
    region3.append({
        'idx': 0,
        'slot': f'titlescreen_0x00076D',
        'text_ja': text_ja,
        'text_zh': text_zh,
        'raw_hex': title_seg.hex(),
        'text_len': 412,
        'text_offset': title_start,
        'source': 'titlescreen_0x00076D',
    })

    all_entries = dialogue_entries + region2 + region3

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # Explicit UTF-8: the default locale codec (gbk on Windows) cannot encode
    # the katakana / full-width punctuation the ROM's text contains.
    from tools.lib.io import write_text as write_text_lf
    write_text_lf(
        OUTPUT, json.dumps(all_entries, ensure_ascii=False, indent=2)
    )
    print(f'\nWrote {len(all_entries)} entries to {OUTPUT}')
    print(f'  - dialogue_pointer_table: {len(dialogue_entries)} (50 slots, {sum(1 for e in dialogue_entries if not e.get("empty"))} non-empty)')
    print(f'  - region 0x458000-0x460000: {len(region2)} segments')
    print(f'  - titlescreen 0x00076D: {len(region3)}')


if __name__ == '__main__':
    main()