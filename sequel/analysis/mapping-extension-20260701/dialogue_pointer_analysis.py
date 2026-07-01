"""Dialogue pointer analysis - 0x03000078 = current dialogue ROM file offset.

For each state in chapter 1 intro, read 0x03000078 (16-bit) and use as ROM file offset.
Read dialogue data block at that offset, extract SJIS bytes, cross-reference with OCR.
"""
import json
import re
from pathlib import Path

ROM_PATH = Path('/root/gba-naruto/build/naruto-sequel-dev.gba')
STATES_PATH = Path('/tmp/dialogue-v7')
OCR_PATH = Path('/tmp/ocr-v2.txt')
OUTPUT_PATH = Path(__file__).parent / 'dialogue_pointer_mapping.json'

# Load IWRAM states
states = []
for i in range(30):
    with open(STATES_PATH / f'state-{i:03d}.json') as f:
        s = json.load(f)
    states.append(s)

# Get 0x03000078 (16-bit little-endian) - current dialogue pointer
pointers = [int(s['iwram'][0x78*2:0x7A*2], 16) for s in states]
print(f'Got {len(pointers)} dialogue pointers')

# Load ROM
rom = ROM_PATH.read_bytes()

# Load OCR
ocr_text = OCR_PATH.read_text()
ocr_map = {}
shot_re = re.compile(r'=== (shot-\d+)\.png ===\n(.*?)(?=\n===|\Z)', re.DOTALL)
for m in shot_re.finditer(ocr_text):
    shot_id = int(m.group(1).split('-')[1])
    text = m.group(2).strip()
    lines = [l for l in text.split('\n') if l.strip() and '<think>' not in l]
    # Take first non-empty line as dialogue (skip character name)
    if len(lines) >= 2:
        ocr_map[shot_id] = lines[1]
    elif lines:
        ocr_map[shot_id] = lines[0]
    else:
        ocr_map[shot_id] = ''

# Extract dialogue bytes for each state
results = []
for i, ptr in enumerate(pointers):
    if ptr < len(rom) - 100:
        data = rom[ptr:ptr+200]
        results.append({
            'state': i,
            'ptr': f'0x{ptr:04X}',
            'rom_data_first_64': data[:64].hex(),
            'ocr': ocr_map.get(i, '?')[:80],
        })

# Save
with open(OUTPUT_PATH, 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'Saved to {OUTPUT_PATH}')

# Print summary
print('\n=== Dialogue pointer mapping (state -> ROM offset -> OCR) ===')
for r in results:
    print(f'  state {r["state"]:2}: ROM 0x{r["ptr"]} | {r["ocr"][:50]}')
