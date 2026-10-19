"""Reproduce local raw proof; not a display-record packet acceptance."""
from pathlib import Path
import hashlib,json
from tools.rom_display_text_parameter_flow import prove_parameter_flow
run=Path(__file__).parent
for name,digest in json.loads((run/'inputs.json').read_text()).items():
 assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
source=json.loads(Path('notes/evidence/rom-renderer-source-replay-20261001-v1/attempt2/result.json').read_text())
assert source['completed_count']==source['passed_count']==6
cost=json.loads(Path('notes/evidence/rom-renderer-flow-cost-20261001-v1/cost.json').read_text())
members={r['site']:r for r in json.loads(Path('notes/evidence/rom-renderer-source-plan-20261001-v1/source-map.json').read_text())['rows']}
rom=Path('rom/base.gba').read_bytes();assert hashlib.sha256(rom).hexdigest()=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
results=[]
for row in cost['rows']:
 member=members[row['site']]
 result=prove_parameter_flow(rom,site=row['site'],sink=row['sink'],target=member['target'],owner_range=member['claim_range'])
 assert result['path_sha256']==row['path_sha256']
 results.append(result)
print(json.dumps({'schema':'display-text-local-parameter-proof-v1','paths':results,'path_count':len(results),'instruction_occurrences':sum(r['instruction_count']for r in results),'source_semantic_receipt_passed_count':6,'source_receipt_replayed_now':False,'promotion_bytes':0,'display_record_packet_accepted':False,'scope':'Local raw r0 effects proven; source receipt identity pinned separately. Complete display text contract, independent record acceptance and managed publication remain pending.'},sort_keys=True,indent=2))
