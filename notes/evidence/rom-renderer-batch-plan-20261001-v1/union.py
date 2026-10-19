"""Frozen evidence union research: no executable production contract or promotion."""
import hashlib,json
from pathlib import Path
names={
 'routes':'notes/evidence/rom-fixed-text-route-preflight-20261001-v1/routes-frozen-replay.json',
 'animation':'notes/evidence/rom-animation-pool-caller-screen-20261001-v1/callers-v3.json',
 'ram':'notes/evidence/rom-ram-protocol-tag-preflight-20261001-v1/protocol-v2.json',
 'pending':'notes/evidence/rom-renderer-records-delta-tier1-20261001-v1/final/rom-renderer-records-delta.json',
 'coverage':'sequel/rom-byte-coverage.json', 'proof':'sequel/reverse-engineering-proof.json'}
raw={k:Path(p).read_bytes()for k,p in names.items()}
x={k:json.loads(v)for k,v in raw.items()}
assert hashlib.sha256(raw['coverage']).hexdigest()=='b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
assert hashlib.sha256(raw['proof']).hexdigest()=='465a13104b6c9a6d0ea418ca513dd0be732438634f1124a3a531c893b11db568'
groups={
 'routes':[{'site':r['site'],'range':r['hypothetical_read_range']}for r in x['routes']['rows']if r.get('first_call',{}).get('target')in(0x66758,0x667a0)],
 'animation':[{'site':r['source'],'range':r['range']}for r in x['animation']['renderer_hypotheses']],
 'ram':[{'site':r['source']['at'],'range':r['renderer_hypothetical_range']}for r in x['ram']['rows']if 'renderer_hypothetical_range'in r]}
allranges=sorted({tuple(r['range'])for rows in groups.values()for r in rows})
assert all(a[1]<=b[0]for a,b in zip(allranges,allranges[1:]))
pending=[r['range']for r in x['pending']['records']]
assert all(not(a<d and c<b)for a,b in allranges for c,d in pending)
for lo,hi in allranges:
 parts=[s for s in x['coverage']['segments']if s['range'][0]<hi and lo<s['range'][1]]
 assert all(s['primary_class']=='unknown'for s in parts)
 assert sum(min(hi,s['range'][1])-max(lo,s['range'][0])for s in parts)==hi-lo
sites=sorted({r['site']for rows in groups.values()for r in rows})
print(json.dumps({'schema':'renderer-batch-planning-union-v1','inputs':{k:{'path':names[k],'sha256':hashlib.sha256(v).hexdigest()}for k,v in raw.items()},
 'groups':{k:{'site_count':len(v),'record_count':len(set(tuple(r['range'])for r in v)),'bytes':sum(b-a for a,b in set(tuple(r['range'])for r in v)),'candidates':v}for k,v in groups.items()},
 'unique_sites':sites,'unique_site_count':len(sites),'unique_record_count':len(allranges),'unique_ranges':allranges,
 'hypothetical_unknown_bytes':sum(b-a for a,b in allranges),'cross_group_overlap_count':0,'pending_overlap_count':0,
 'existing_pending_records':len(pending),'existing_pending_bytes':sum(b-a for a,b in pending),
 'promotion_bytes':0,'tier1_ready':False,'tier2_ready':False,
 'missing_acceptance':['complete source CFG and literal-to-call dataflow for all 92 sites','independent raw path and renderer bridge verification','frozen immutable input contract and fail-closed mutation TDD','managed export/verifier CLI integration and stable replay'],
 'scope':'85 candidate records / 92 bounded sites only; no formal producer denominator, runtime, edit safety, Tier1 or coverage acceptance.'},sort_keys=True,indent=2))
