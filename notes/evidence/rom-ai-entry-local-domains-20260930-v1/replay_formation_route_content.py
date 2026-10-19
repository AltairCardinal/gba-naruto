"""Fixed formation contents only; not a live writer or actor domain proof."""
from pathlib import Path
import json,hashlib,sys
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
from tools.extract_positions import extract_positions
rom=(root/'rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest()=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
extractor_sha=hashlib.sha256((root/'tools/extract_positions.py').read_bytes()).hexdigest()
assert extractor_sha=='71482f22724665f12621b4d2d40e00536338cde799ed0fa7594d004d7ea2a35c'
counts={};records=[]
for r in extract_positions(rom)['entries']:
 v=r['selector']
 if not v:continue
 route='first_special' if ((v+3)&255)<=2 else 'alternate_special' if ((v+6)&255)<=2 else 'ordinary'
 cd=bytes.fromhex(r['raw_hex'])[14];key=(route,r['affiliation'],cd);counts[key]=counts.get(key,0)+1
 records.append({'id':r['id'],'offset':r['rom_offset'],'route':route,'raw_selector':v,'raw_affiliation':r['affiliation'],'raw_plus_0e':cd})
report={'schema':'rom-ai-formation-route-content-preflight-v1','rom_sha256':hashlib.sha256(rom).hexdigest(),'extractor_sha256':extractor_sha,'promotion_bytes':0,'matrix_index_domain_proved_here':False,'callee_state_preservation_proved':False,'raw_affiliation_is_live_actor_cc_claimed':False,'source_plus_0e_is_live_cd_claimed':False,'counts':[{'route':k[0],'raw_affiliation':k[1],'raw_plus_0e':k[2],'count':v} for k,v in sorted(counts.items())],'records':records}
print(json.dumps(report,indent=2))
