"""Candidate-only aligned words and LDR shapes into 17 large unknown segments."""
import bisect
import hashlib
import json
import struct
from pathlib import Path
from tools._vendor.capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

rom = Path('rom/base.gba').read_bytes()
raw = Path('sequel/rom-byte-coverage.json').read_bytes()
assert hashlib.sha256(rom).hexdigest() == '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
assert hashlib.sha256(raw).hexdigest() == 'b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
segments = json.loads(raw)['segments']
large = [s['range'] for s in segments if s['primary_class'] == 'unknown' and s['range'][1]-s['range'][0] >= 1024]
starts = [r[0] for r in large]
rows = [{'range': r, 'bytes': r[1]-r[0], 'aligned_word_shapes': [], 'classified_thumb_ldr_shapes': []} for r in large]

def index(target):
    at = bisect.bisect_right(starts, target) - 1
    return at if at >= 0 and target < large[at][1] else None

for at in range(0, len(rom)-3, 4):
    target = struct.unpack_from('<I', rom, at)[0] - 0x08000000
    i = index(target)
    if i is not None:
        rows[i]['aligned_word_shapes'].append({'at': at, 'target': target})

engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
domains = []
for segment in segments:
    kind = segment['primary_class']
    if 'thumb' not in kind or not (kind.endswith('thumb_code') or kind == 'armv4t_boot_thumb_handoff_reachable_code'):
        continue
    lo, hi = segment['range']
    domains.append({'range': [lo, hi], 'class': kind})
    for at in range((lo+1)&~1, hi-1, 2):
        half = struct.unpack_from('<H', rom, at)[0]
        if half & 0xf800 != 0x4800:
            continue
        literal = ((at+4)&~3) + (half&255)*4
        if literal+4 > len(rom):
            continue
        target = struct.unpack_from('<I', rom, literal)[0] - 0x08000000
        i = index(target)
        if i is None:
            continue
        insns = list(engine.disasm(rom[at:at+2],at))
        assert len(insns)==1 and insns[0].size==2 and insns[0].mnemonic=='ldr'
        rows[i]['classified_thumb_ldr_shapes'].append({'at': at, 'literal': literal, 'target': target,
                                                      'halfword': f'{half:04x}', 'owner_class': kind,
                                                      'primary_claim_ids': segment['primary_claim_ids']})

for row in rows:
    row['aligned_word_count'] = len(row['aligned_word_shapes'])
    row['ldr_count'] = len(row['classified_thumb_ldr_shapes'])
print(json.dumps({'schema':'large-unknown-anchor-screen-v1','inputs':{'rom_sha256':hashlib.sha256(rom).hexdigest(),'coverage_sha256':hashlib.sha256(raw).hexdigest()},
                  'rows':rows,'screened_thumb_segment_bytes':sum(r['range'][1]-r['range'][0] for r in domains),
                  'screened_thumb_segment_count':len(domains),'domain_classes':sorted({r['class'] for r in domains}),
                  'large_bytes':sum(r['bytes'] for r in rows),'promotion_bytes':0,
                  'scope':'4-byte-aligned full-ROM word shapes and 2-byte LDR shapes in listed canonical Thumb classes only. No full upstream verifier replay, register flow, index domain, natural reachability, computed/RAM/unaligned/ARM producer exclusion or semantic claims.'},sort_keys=True,indent=2))
