"""Reproduce only the affected packets; final full audit must independently replay all."""
import copy,hashlib,json,pathlib,sys
ROOT=pathlib.Path('/Users/altair/github/gba-naruto-reverse');sys.path.insert(0,str(ROOT))
from tools import audit_rom_byte_coverage as auditor
RUN=pathlib.Path(__file__).parent
COVERAGE_SHA='f55cebff32db536bf9847dc7dc9b147a0c8868ee37ddf4cd66187b687eba8b96'
PROOF_SHA='fad9c2b1c6cc9af8385826e1a41a2e72209ae151e8a4e4ffa6de934a7dd38a5a'
def sha(raw):return hashlib.sha256(raw).hexdigest()
c_raw=(ROOT/'sequel/rom-byte-coverage.json').read_bytes();p_raw=(ROOT/'sequel/reverse-engineering-proof.json').read_bytes()
assert sha(c_raw)==COVERAGE_SHA and sha(p_raw)==PROOF_SHA
original=json.loads(c_raw);candidate=copy.deepcopy(original);rom=(ROOT/'rom/base.gba').read_bytes()
fast={'rom-event-handler-cfg-v1','rom-sprite-component-source-v1','rom-cfg-proven-roots-v16','rom-cfg-proven-roots-v16-consumed-literals-v1'}
print('Replaying four frozen fast-audit verifiers...',flush=True)
projected=auditor._fast_audit_four_packet_claims(ROOT,rom,[c for c in original['claims'] if c.get('promotion_batch') not in fast])
print('Replaying bounded V10 verifier...',flush=True)
projected+=auditor._cfg_proven_roots_v10_claims(ROOT,rom,[c for c in original['claims'] if c.get('promotion_batch')!='cfg-proven-roots-v10'])
by_id={c['id']:c for c in projected};delta=[]
for i,old in enumerate(original['claims']):
 if old['id'] not in by_id:continue
 new=by_id[old['id']]
 assert {k:v for k,v in old.items() if k!='evidence_selector'}=={k:v for k,v in new.items() if k!='evidence_selector'}
 if old['evidence_selector']!=new['evidence_selector']:
  delta.append({'id':old['id'],'evidence_path':old['evidence_path'],'range':old['range'],'old_selector':old['evidence_selector'],'new_selector':new['evidence_selector']})
 candidate['claims'][i]=new
assert len(delta)==123 and len(by_id)==125
assert {k:v for k,v in original.items() if k!='claims'}=={k:v for k,v in candidate.items() if k!='claims'}
new_c=auditor._canonical_json_bytes(candidate);proof=json.loads(p_raw);changes=[]
for name,gate in proof['gates'].items():
 for e in gate.get('evidence',[]):
  if e['path']=='sequel/project.json':
   assert e['sha256']=='52e12bf8c0d3dd291cf8398f235ae89b5f8ca407ca974b9dcc47145722a9f248'
   e['sha256']=sha((ROOT/e['path']).read_bytes());changes.append(name+':project-input')
  elif name=='rom_byte_coverage' and e['path']=='sequel/rom-byte-coverage.json':
   assert e['sha256']==COVERAGE_SHA;e['sha256']=sha(new_c);changes.append(name+':coverage')
 for v in gate.get('verifiers',[]):
  if 'tools/audit_rom_byte_coverage.py' in v['command']:
   assert v['script_sha256']=='751097e634cab06306b08332ed581f22dadae5869ba337330a089aea0487ee92'
   v['script_sha256']=sha((ROOT/'tools/audit_rom_byte_coverage.py').read_bytes());changes.append(name+':auditor')
assert len(changes)==4,changes
new_p=(json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode()
# Source bytes must remain frozen throughout the potentially long packet replay.
assert sha((ROOT/'sequel/rom-byte-coverage.json').read_bytes())==COVERAGE_SHA
assert sha((ROOT/'sequel/reverse-engineering-proof.json').read_bytes())==PROOF_SHA
for name,raw in [('coverage-candidate.json',new_c),('proof-candidate.json',new_p)]:
 with (RUN/name).open('xb') as f:f.write(raw)
receipt={'status':'candidate_only_requires_full_formal_audit','before_coverage_sha256':COVERAGE_SHA,'after_coverage_sha256':sha(new_c),'before_proof_sha256':PROOF_SHA,'after_proof_sha256':sha(new_p),'auditor_sha256':sha((ROOT/'tools/audit_rom_byte_coverage.py').read_bytes()),'selector_delta':delta,'selector_changes':len(delta),'proof_identity_updates':changes,'classified_bytes':candidate['summary']['classified_bytes'],'unknown_bytes':candidate['summary']['unknown_bytes'],'claim_count':candidate['summary']['claim_count'],'segment_count':candidate['summary']['segment_count']}
with (RUN/'candidate-repair-receipt.json').open('x') as f:f.write(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='selector_delta'},indent=2),flush=True)
