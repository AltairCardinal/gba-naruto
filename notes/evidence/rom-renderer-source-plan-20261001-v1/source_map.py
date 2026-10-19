"""Read-only identity/membership screening, not a full source CFG replay."""
import hashlib,json,struct
from pathlib import Path
from collections import Counter
from tools._vendor.capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
sha=lambda b:hashlib.sha256(b).hexdigest()
paths=['notes/evidence/rom-renderer-batch-plan-20261001-v1/union.json','sequel/rom-byte-coverage.json','rom/base.gba']
raw=[Path(p).read_bytes()for p in paths];union,cov=json.loads(raw[0]),json.loads(raw[1]);rom=raw[2]
assert sha(raw[1])=='b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
assert sha(rom)=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
claims={c['id']:c for c in cov['claims']};engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB);rows=[];identities={};decoded={}
for site in union['unique_sites']:
 seg=next(s for s in cov['segments']if s['range'][0]<=site<s['range'][1]);assert len(seg['primary_claim_ids'])==1
 claim=claims[seg['primary_claim_ids'][0]];a,b=claim['range'];data=rom[a:b]
 assert sha(data)==claim['bytes_sha256']
 if claim['id']not in decoded:
  insns=list(engine.disasm(data,a));assert sum(i.size for i in insns)==b-a
  decoded[claim['id']]={i.address:i.size for i in insns}
 assert decoded[claim['id']].get(site)==2
 half=struct.unpack_from('<H',rom,site)[0];assert half&0xf800==0x4800
 literal=((site+4)&~3)+4*(half&255);target=struct.unpack_from('<I',rom,literal)[0]-0x08000000
 expected={tuple(r['range'])for g in union['groups'].values()for r in g['candidates']if r['site']==site}
 assert any(lo==target for lo,hi in expected)
 for pathkey,hashkey in [('evidence_path','evidence_sha256'),('promotion_manifest_path','promotion_manifest_sha256'),('independent_verifier_path','independent_verifier_sha256')]:
  path=claim[pathkey];current=sha(Path(path).read_bytes());identities[path]={'sha256':current,'expected_sha256':claim[hashkey],'matches':current==claim[hashkey]}
 rows.append({'site':site,'target':target,'claim_id':claim['id'],'claim_kind':claim['claim_kind'],'primary_class':seg['primary_class'],'claim_range':claim['range'],'evidence_path':claim['evidence_path'],'evidence_selector':claim.get('evidence_selector'),'verifier_path':claim['independent_verifier_path'],'raw_instruction_partition_member':True})
print(json.dumps({'schema':'renderer-source-plan-v1','inputs':{p:sha(b)for p,b in zip(paths,raw)},'rows':rows,'source_counts':dict(Counter(r['evidence_path']for r in rows)),'class_counts':dict(Counter(r['primary_class']for r in rows)),'identities':identities,'identity_mismatch_count':sum(not v['matches']for v in identities.values()),'coarse_owner_count':sum(r['claim_kind']=='consumer_code_slice'for r in rows),'site_count':len(rows),'promotion_bytes':0,'full_source_verifiers_rerun':False,'scope':'Existing claim identity and local raw decode membership only; no CFG entry/path, literal taint, caller completeness, bridge or Tier1 acceptance.'},sort_keys=True,indent=2))
