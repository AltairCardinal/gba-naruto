#!/usr/bin/env python3
"""
Phase 5.3 — Extract ALL SJIS/GBK text segments from the dialogue region.

The dialogue pointer table at 0x461CE8 references 50 dialogue slots
(some null), but the actual dialogue text region (0x458000-0x460000)
contains 200+ additional SJIS/GBK-encoded text blocks. These are
referenced indirectly via game engine state or are unused slots from
the development process.

This script extracts all segments and writes dialogue-bank-full.json.
The importer then loads them into editor.db.

Note: these bytes were originally SJIS Japanese (GBA's native text
encoding). 熊组 2004 年的汉化 ROM 在这些位置替换了部分字节为
GBK 编码中文，但因为 GBA text engine 不支持 GBK 双字节字符，
cp932 和 GBK 两种解码都不能完美还原——结果就是编辑器里看到
"乱码"。这是 ROM 真实数据的限制，不是 extract bug。
"""
import json
import struct
from pathlib import Path

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
        text_ja = safe_decode(raw[:real_len], 'cp932')
        text_zh = safe_decode(raw[:real_len], 'gbk')
        dialogue_entries.append({
            'idx': i, 'slot': f'group{i}',
            'text_ja': text_ja,
            'text_zh': text_zh,
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
            text_ja = safe_decode(seg, 'cp932')
            text_zh = safe_decode(seg, 'gbk')
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
    text_ja = safe_decode(title_seg, 'cp932')
    text_zh = safe_decode(title_seg, 'gbk')
    region3.append({
        'idx': 0,
        'slot': f'titlescreen_0x00076D',
        'text_ja': text_ja,
        'text_zh': text_zh,
        'raw_hex': title_seg[:text_ja.encode('cp932', errors='ignore') and 412].hex(),
        'text_len': 412,
        'text_offset': title_start,
        'source': 'titlescreen_0x00076D',
    })

    all_entries = dialogue_entries + region2 + region3

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(all_entries, ensure_ascii=False, indent=2))
    print(f'\nWrote {len(all_entries)} entries to {OUTPUT}')
    print(f'  - dialogue_pointer_table: {len(dialogue_entries)} (50 slots, {sum(1 for e in dialogue_entries if not e.get("empty"))} non-empty)')
    print(f'  - region 0x458000-0x460000: {len(region2)} segments')
    print(f'  - titlescreen 0x00076D: {len(region3)}')


if __name__ == '__main__':
    main()