"""Trace inventory for planning; no independent parameter proof."""
import hashlib,json
from pathlib import Path
from collections import Counter
base=Path('notes/evidence')
paths={
 'union':base/'rom-renderer-batch-plan-20261001-v1/union.json',
 'routes':base/'rom-fixed-text-route-preflight-20261001-v1/routes-frozen-replay.json',
 'animation':base/'rom-animation-pool-caller-screen-20261001-v1/callers-v3.json',
 'ram':base/'rom-ram-protocol-tag-preflight-20261001-v1/protocol-v2.json',
 'membership':base/'rom-renderer-source-plan-20261001-v1/source-map.json'}
raw={k:p.read_bytes()for k,p in paths.items()};x={k:json.loads(v)for k,v in raw.items()};sites=set(x['union']['unique_sites']);traces={}
for r in x['routes']['rows']:
 if r['site']in sites:traces[r['site']]=r['trace']
for r in x['animation']['literal_rows']:
 if r['source']['at']in sites:traces[r['source']['at']]=r['trace']
for r in x['ram']['rows']:
 if r['source']['at']in sites:traces[r['source']['at']]=r['trace']
assert set(traces)==sites
rom=Path('rom/base.gba').read_bytes();assert hashlib.sha256(rom).hexdigest()=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
members={r['site']:r for r in x['membership']['rows']};rows=[]
for site,trace in sorted(traces.items()):
 cursor=site
 for insn in trace:
  assert insn['at']==cursor
  data=bytes.fromhex(insn['bytes']);assert rom[cursor:cursor+len(data)]==data
  cursor+=len(data)
 assert trace[-1]['mnemonic']=='bl'and all(i['mnemonic']!='bl'for i in trace[:-1])
 a,b=members[site]['claim_range']
 rows.append({'site':site,'sink':trace[-1]['at'],'callee_operands':trace[-1]['operands'],'instruction_count':len(trace),'raw_path_bytes':cursor-site,'path_sha256':hashlib.sha256(rom[site:cursor]).hexdigest(),'path_within_same_instruction_claim':a<=site and cursor<=b,'trace_mnemonics':[i['mnemonic']for i in trace]})
print(json.dumps({'schema':'renderer-flow-cost-v1','inputs':{k:{'path':str(paths[k]),'sha256':hashlib.sha256(v).hexdigest()}for k,v in raw.items()},'rows':rows,'site_count':len(rows),'instruction_occurrence_count':sum(len(t)for t in traces.values()),'mnemonic_occurrences':dict(Counter(i['mnemonic']for t in traces.values()for i in t)),'length_histogram':dict(Counter(len(t)for t in traces.values())),'same_claim_path_count':sum(r['path_within_same_instruction_claim']for r in rows),'callee_counts':dict(Counter(r['callee_operands']for r in rows)),'max_instructions':max(r['instruction_count']for r in rows),'promotion_bytes':0,'independent_parameter_proof':False,'scope':'Previously screened straight-line trace inventory and raw byte identities only; Capstone register preservation remains unaccepted without independent raw effect verifier.'},sort_keys=True,indent=2))
