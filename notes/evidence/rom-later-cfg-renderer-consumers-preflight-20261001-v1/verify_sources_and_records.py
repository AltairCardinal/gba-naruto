"""Semantic CFG source verification and independent consumer/parser replay."""
import gzip,hashlib,json,struct
from pathlib import Path
from tools.verify_rom_cfg_proven_roots import verify_rom_cfg_proven_roots
from tools.verify_rom_cfg_proven_roots_v3 import verify_rom_cfg_proven_roots_v3
from tools.verify_rom_cfg_proven_roots_v6 import verify_rom_cfg_proven_roots_v6
from tools.export_rom_fixed_renderer_script_records import _prove_parameter_flow
from tools.export_rom_training_text_script_inventory import _parse_training_record,_sjis_ranges
root=Path('.');run=Path(__file__).parent;rom=(root/'rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest()=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
screen=json.loads((run/'later-cfg-v3.json').read_bytes())
reports={}
for version,verifier in [(1,verify_rom_cfg_proven_roots),(3,verify_rom_cfg_proven_roots_v3),(6,verify_rom_cfg_proven_roots_v6)]:
 path=root/f'artifacts/rom-cfg-proven-roots-v{version}';report=verifier(root,path.resolve())
 assert report['verified'],report
 reports[path.as_posix()]=report
sjis=_sjis_ranges(rom);records={};exclusions=[];path_vector=[]
for row in screen['unknown_literal_sites']:
 assert row['source_artifact'] in reports
 site=row['site'];half=struct.unpack_from('<H',rom,site)[0]
 assert half&0xf800==0x4800
 literal=((site+4)&~3)+4*(half&255)
 assert literal==row['literal'] and struct.unpack_from('<I',rom,literal)[0]==0x08000000+row['target']
 sink=_prove_parameter_flow(rom,site,(half>>8)&7);assert sink==row['interpreter_callsite']
 path_vector.append([site,row['target'],sink,hashlib.sha256(rom[site:sink+4]).hexdigest()])
 if 'candidate_range' in row:
  parsed=_parse_training_record(rom,row['target'],0x7554,sjis)
  assert [row['target'],parsed['end']]==row['candidate_range'] and parsed['opcode_sequence']==row['opcodes']
  records[tuple(row['candidate_range'])]=row['opcodes']
 else:
  try:_parse_training_record(rom,row['target'],0x7554,sjis)
  except ValueError as error:
   assert 'unsupported opcode'in str(error)
   exclusions.append({'site':site,'target':row['target'],'reason':str(error)})
  else:raise AssertionError('excluded root accepted by independent parser')
coverage_raw=gzip.decompress((root/'notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-after.json.gz').read_bytes())
assert hashlib.sha256(coverage_raw).hexdigest()=='b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
segments=json.loads(coverage_raw)['segments'];ranges=sorted(records)
assert all(b<=c for (a,b),(c,d)in zip(ranges,ranges[1:]))
for a,b in ranges:
 hits=[s for s in segments if s['range'][0]<b and a<s['range'][1]]
 assert all(s['primary_class']=='unknown'for s in hits)
 assert sum(min(b,s['range'][1])-max(a,s['range'][0])for s in hits)==b-a
assert len(path_vector)==36 and len(records)==27 and sum(b-a for a,b in records)==1656
print(json.dumps({'schema':'later-cfg-low-script-independent-preflight-v1','source_semantic_verifiers':reports,
                  'consumer_count':len(path_vector),'consumer_path_vector':path_vector,
                  'consumer_vector_sha256':hashlib.sha256(json.dumps(path_vector,separators=(',',':')).encode()).hexdigest(),
                  'records':[{'range':[a,b],'opcode_sequence':records[(a,b)],'bytes_sha256':hashlib.sha256(rom[a:b]).hexdigest()}for a,b in ranges],
                  'unique_record_count':len(records),'unknown_intersection_bytes':1656,'excluded_sites':exclusions,
                  'tier1_accepted':False,'promotion_bytes':0,'natural_runtime_reachability':False},sort_keys=True,indent=2))
