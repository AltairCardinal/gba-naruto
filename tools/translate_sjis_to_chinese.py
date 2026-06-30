#!/usr/bin/env python3
"""
Translate SJIS bytes → game tile Chinese chars using 熊组汉化 mapping.

The mapping is a 1:1 byte → tile-char lookup that the 熊组汉化 group
created by replacing GBA tile images (font table). Each SJIS double
byte maps to a single displayed character in-game.

To build the mapping:
1. OCR game dialogue screenshots with mmx vision
2. Match OCR output (Chinese) with known dialogue byte streams in ROM
3. Add each SJIS byte → Chinese char pair to sjis-to-tile-mapping.json

Usage:
    python tools/translate_sjis_to_chinese.py [--dry-run]
    # Translates group0-49 dialogue bytes, writes to editor.db
"""
import json
import sqlite3
import sys
from pathlib import Path

MAPPING_FILE = Path('sequel/content/text/sjis-to-tile-mapping.json')
DB_PATH = Path('sequel/editor.db')


def load_mapping() -> dict:
    """Load SJIS byte (hex string) → tile char mapping."""
    data = json.load(open(MAPPING_FILE))
    return data.get('mapping', {})


def translate_bytes(data: bytes, mapping: dict) -> tuple[str, list[str]]:
    """
    Translate SJIS byte sequence to game tile chars.

    Returns (display_text, list_of_unknown_byte_hex).
    Unknown bytes (not in mapping) are skipped but tracked.
    """
    out = []
    unknowns = []
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0x0a:
            out.append('\n')
            i += 1
        elif 0x81 <= b <= 0xFC:
            # SJIS lead byte
            if i + 1 < len(data):
                t = data[i + 1]
                if 0x40 <= t <= 0xFC:
                    key = f'{b:02X}{t:02X}'
                    if key in mapping:
                        out.append(mapping[key])
                    else:
                        out.append('?')  # unknown byte
                        unknowns.append(key)
                    i += 2
                    continue
            out.append('?')
            if 0x81 <= b <= 0xFC:
                unknowns.append(f'{b:02X}')
            else:
                unknowns.append(f'{b:02X}')
            i += 1
        elif 0x20 <= b <= 0x7e:
            # ASCII
            out.append(chr(b))
            i += 1
        else:
            out.append(f'[{b:02X}]')
            i += 1
    return ''.join(out), unknowns


def main():
    dry_run = '--dry-run' in sys.argv
    mapping = load_mapping()
    print(f'Mapping size: {len(mapping)} SJIS double bytes')

    rom = Path('build/naruto-sequel-dev.gba').read_bytes()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Translate all 50 group dialogue entries from ROM
    table_offset = 0x461CE8
    print(f'\n=== Translating group dialogue pointer table ===')
    total_known = 0
    total_unknown = 0

    for i in range(50):
        pos = table_offset + i * 4
        ptr = int.from_bytes(rom[pos:pos+4], 'little')
        if ptr == 0:
            continue
        text_offset = ptr - 0x08000000 if 0x08000000 <= ptr <= 0x09000000 else ptr
        if text_offset >= len(rom):
            continue
        # Find length
        real_len = 0
        for j in range(200):
            if text_offset + j >= len(rom) or rom[text_offset + j] == 0x00:
                real_len = j
                break
        data = rom[text_offset:text_offset + real_len]
        translated, unknowns = translate_bytes(data, mapping)
        n_known = real_len // 2 - len(unknowns)
        total_known += n_known
        total_unknown += len(unknowns)

        key = f'group{i}'
        print(f'\ngroup{i}:')
        print(f'  raw ({real_len}b): {data[:30].hex()}...')
        print(f'  translated: {translated}')
        if unknowns:
            unique_unknowns = list(set(unknowns))
            print(f'  unknown SJIS bytes: {len(unknowns)} ({unique_unknowns[:5]}{"..." if len(unique_unknowns) > 5 else ""})')

        if not dry_run:
            cur.execute("UPDATE dialogues SET text_ja = ? WHERE key = ?", (translated, key))

    conn.commit()
    conn.close()

    print(f'\n=== Summary ===')
    print(f'Total mapped chars: {total_known}')
    print(f'Total unknown bytes: {total_unknown}')


if __name__ == '__main__':
    main()
