"""Bounded source content and instruction-owner inventory; no promotion."""
from pathlib import Path
import json,hashlib,sys
from collections import Counter
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
from tools.extract_positions import extract_positions
rom=(root/'rom/base.gba').read_bytes();raw=(root/'sequel/rom-byte-coverage.json').read_bytes();coverage=json.loads(raw)
rows=[r for r in extract_positions(rom)['entries'] if r['selector'] in (253,254,255)]
points=[]
for a in (0x8429c,0x842a6,0x6aad4,0x6ab1e,0x6ad6e,0x6ad90):
 owners=[r for r in coverage['claims'] if r['role']=='primary' and r['range'][0]<=a and a+2<=r['range'][1]]
 assert len(owners)==1 and 'reachable_instruction_bytes' in owners[0]['claim_kind']
 points.append({'offset':a,'raw_hex':rom[a:a+2].hex(),'owner':owners[0]})
result={'schema':'rom-ai-scorer-exclusion-preflight-v1','rom_sha256':hashlib.sha256(rom).hexdigest(),'canonical_sha256':hashlib.sha256(raw).hexdigest(),'promotion_bytes':0,'matrix_first_branch_records':len(rows),'initial_c0_mask_formula':'(record[1] | little_endian_u32(record[8:12]) | 0x10) & 0x0E','initial_c0_mask_content_counts':dict(Counter(str((r['affiliation']|r['aux_u32']|16)&14) for r in rows)),'natural_runtime_state_proved':False,'callee_side_effects_proved':False,'writer_denominator_complete':False,'points':points,'windows':{f'{a:06x}..{b:06x}':hashlib.sha256(rom[a:b]).hexdigest() for a,b in ((0x84274,0x84350),(0x6ac70,0x6ae90),(0x6aa64,0x6ac70))}}
print(json.dumps(result,indent=2,sort_keys=True))
