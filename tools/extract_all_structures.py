#!/usr/bin/env python3
"""
Universal ROM structure extractor.

For every sequel/content/*/bank.json that has table_offset + entry_count +
entry_size + entry_format.fields, extract all entries from the ROM and
write them back into bank.json under the "entries" key.

This is Phase 5: extract what Phase 4 only described.

Usage:
    python tools/extract_all_structures.py [--dry-run] [--structure NAME]
"""
import json
import struct
import sys
from pathlib import Path

ROM_PATH = Path('build/naruto-sequel-dev.gba')
CONTENT_DIR = Path('sequel/content')
ENTRY_KEY = 'entries'

# type → struct format char(s) + python reader
TYPE_READERS = {
    'u8':  ('B', lambda b: b[0]),
    'u16': ('H', lambda b: struct.unpack('<H', b)[0]),
    'u32': ('I', lambda b: struct.unpack('<I', b)[0]),
    's8':  ('b', lambda b: struct.unpack('<b', b)[0]),
    's16': ('h', lambda b: struct.unpack('<h', b)[0]),
    's32': ('i', lambda b: struct.unpack('<i', b)[0]),
}

def extract_entry(rom: bytes, offset: int, fields: list) -> dict:
    """Extract one entry by reading each field at its offset."""
    out = {'_raw_offset': offset}
    for f in fields:
        pos = offset + f['offset']
        size = f['size']
        if pos + size > len(rom):
            out[f['name']] = None
            out[f'{f["name"]}_truncated'] = True
            continue
        chunk = rom[pos:pos + size]
        ftype = f.get('type', f'u{size*8}')
        if ftype in TYPE_READERS:
            out[f['name']] = TYPE_READERS[ftype][1](chunk)
        else:
            # unknown type → store hex
            out[f['name']] = chunk.hex()
        out[f'{f["name"]}_hex'] = chunk.hex()
    return out

def extract_structure(rom: bytes, bank_path: Path, dry_run=False) -> tuple[str, int]:
    """Returns (status, n_entries)."""
    data = json.load(open(bank_path))
    name = bank_path.parent.name

    # Pre-conditions
    ef = data.get('entry_format')
    if not ef or not isinstance(ef, dict) or 'fields' not in ef:
        return 'skipped (no entry_format.fields)', 0
    if 'table_offset' not in data:
        return 'skipped (no table_offset)', 0
    if 'entry_count' not in data or 'entry_size' not in data:
        return 'skipped (no entry_count/size)', 0

    offset = data['table_offset']
    count = data['entry_count']
    size = data['entry_size']
    fields = ef['fields']

    if offset + count * size > len(rom):
        return f'skipped (out of ROM: offset {offset} + {count*size} > {len(rom)})', 0

    entries = []
    for i in range(count):
        e = extract_entry(rom, offset + i * size, fields)
        e['_index'] = i
        entries.append(e)

    if not dry_run:
        data[ENTRY_KEY] = entries
        data['extraction'] = {
            'tool': 'tools/extract_all_structures.py',
            'extracted_count': count,
            'rom_offset': offset,
            'rom_offset_hex': f'0x{offset:X}',
        }
        bank_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    return 'ok', count

def main():
    dry_run = '--dry-run' in sys.argv
    only = None
    if '--structure' in sys.argv:
        only = sys.argv[sys.argv.index('--structure') + 1]

    if not ROM_PATH.exists():
        print(f'FATAL: ROM not found: {ROM_PATH}', file=sys.stderr)
        sys.exit(2)

    rom = ROM_PATH.read_bytes()
    print(f'[extract] ROM: {ROM_PATH} ({len(rom)} bytes)')

    summary = []
    for bank_path in sorted(CONTENT_DIR.glob('*/bank.json')):
        if only and bank_path.parent.name != only:
            continue
        status, n = extract_structure(rom, bank_path, dry_run=dry_run)
        marker = '🔍' if dry_run else '✅' if status == 'ok' else '⏭️'
        print(f'  {marker} {bank_path.parent.name:30s} {status:50s} entries={n}')
        summary.append((bank_path.parent.name, status, n))

    total = sum(n for _, s, n in summary if s == 'ok')
    ok = sum(1 for _, s, _ in summary if s == 'ok')
    print(f'\n[extract] {ok} structures, {total} total entries' + (' (dry-run)' if dry_run else ''))

if __name__ == '__main__':
    main()
