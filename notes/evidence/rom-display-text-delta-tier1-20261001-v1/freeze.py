"""Freeze the public 92-site/85-record contract from immutable inputs."""
import ast,gzip,hashlib,json,struct
from pathlib import Path
from tools.export_rom_fixed_consumer_text_inventory import _renderer_record_end,_sjis_ranges
from tools.verify_rom_fixed_consumer_text_inventory import _independent_renderer_end,_independent_sjis_ranges
sha=lambda raw:hashlib.sha256(raw).hexdigest()
canonical=lambda v:(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
base=Path('notes/evidence');union_path=base/'rom-renderer-batch-plan-20261001-v1/union.json';cost_path=base/'rom-renderer-flow-cost-20261001-v1/cost.json';source_path=base/'rom-renderer-source-plan-20261001-v1/source-map.json'
u=json.loads(union_path.read_text());cost=json.loads(cost_path.read_text());source=json.loads(source_path.read_text());rom=Path('rom/base.gba').read_bytes()
assert sha(rom)=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
pre=base/'rom-small-cfg-batch-canonical-20260930-v1/coverage-after.json.gz';pr=gzip.decompress(pre.read_bytes());assert sha(pr)=='b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2';cov=json.loads(pr)
members={r['site']:r for r in source['rows']};claims={c['id']:c for c in cov['claims']};consumers=[]
for row in cost['rows']:
 m=members[row['site']];h=struct.unpack_from('<H',rom,row['site'])[0];assert h&0xff00==0x4800
 consumers.append({'site':row['site'],'sink':row['sink'],'target':m['target'],'callee':int(row['callee_operands'][1:],16),'literal_word':((row['site']+4)&~3)+4*(h&255),'owner_range':m['claim_range'],'claim_id':m['claim_id'],'evidence_path':m['evidence_path'],'path_sha256':row['path_sha256'],'instruction_count':row['instruction_count']})
records=[]
for a,b in u['unique_ranges']:
 s=next(s for s in cov['segments']if s['range'][0]<=a<s['range'][1]);assert s['primary_class']=='unknown'
 end=_renderer_record_end(rom,a,s['range'][1],_sjis_ranges(rom));assert end==b==_independent_renderer_end(rom,a,s['range'][1],_independent_sjis_ranges(rom))
 records.append({'range':[a,b],'limit':s['range'][1],'bytes_sha256':sha(rom[a:b]),'nul_inclusive':True})
labels=['inventory-v2','inventory-v3','roots-v6','roots-v17','roots-v18','battle-controller'];dirs=['rom-cfg-inventory-v2','rom-cfg-inventory-v3','rom-cfg-proven-roots-v6','rom-cfg-proven-roots-v17','rom-cfg-proven-roots-v18','rom-battle-controller-cfg-v1'];tools=['verify_rom_cfg_inventory','verify_rom_cfg_inventory_v3','verify_rom_cfg_proven_roots_v6','verify_rom_cfg_proven_roots_v17','verify_rom_cfg_proven_roots_v18','verify_rom_battle_controller_cfg']
source_receipt=base/'rom-renderer-source-replay-20261001-v1/attempt2/result.json';reports={r['name']:r['report']for r in json.loads(source_receipt.read_text())['rows']};assert all(r['verified']for r in reports.values())
sources=[{'label':label,'artifact_dir':'artifacts/'+directory,'verifier_module':'tools.'+tool}for label,directory,tool in zip(labels,dirs,tools)]
inputs={str(p)for p in [pre,union_path,cost_path,source_path,source_receipt]}
for spec in sources:inputs.update(str(p)for p in Path(spec['artifact_dir']).iterdir()if p.is_file())
inputs.update(source['identities'])
queue=[Path('tools')/(tool+'.py')for tool in tools]+[Path('tools/rom_display_text_parameter_flow.py'),Path('tools/export_rom_fixed_consumer_text_inventory.py'),Path('tools/verify_rom_fixed_consumer_text_inventory.py'),Path('tools/export_rom_small_cfg_dependency_batch.py'),Path('tools/export_rom_cfg_proven_roots_v21.py'),Path('tools/rom_small_cfg_callback_gaps_independent_verifier.py'),Path('tools/verify_rom_renderer_records_delta.py')]
seen=set()
while queue:
 p=queue.pop()
 if str(p)in seen:continue
 seen.add(str(p));inputs.add(str(p))
 for node in ast.walk(ast.parse(p.read_text())):
  names=[]
  if isinstance(node,ast.Import):names=[n.name for n in node.names]
  if isinstance(node,ast.ImportFrom):
   if node.module=='tools':names=['tools.'+n.name for n in node.names]
   elif node.module:names=[node.module]
  for name in names:
   if name.startswith('tools.'):
    q=Path(name.replace('.','/')+'.py')
    if q.is_file()and '_vendor'not in str(q):queue.append(q)
# Pin vendor decoder files required by the source raw CFG verifiers.
from tools.verify_rom_cfg_inventory import DECODER_FILES
inputs.update(DECODER_FILES)
windows=[(0x6626c,0x66736),(0x66758,0x66790),(0x667a0,0x667ca),(0x65e80,0x65eb6),(0x53d644,0x53d73c)]
contract={'schema':'rom-display-text-delta-contract-v1','rom':{'path':'rom/base.gba','size':len(rom),'sha256':sha(rom)},'precoverage':{'path':str(pre),'raw_sha256':sha(pr)},'consumers':consumers,'records':records,'sources':sources,'source_reports':reports,'semantic_windows':[{'range':[a,b],'sha256':sha(rom[a:b])}for a,b in windows],'inputs':[{'path':p,'size':Path(p).stat().st_size,'sha256':sha(Path(p).read_bytes())}for p in sorted(inputs)],'scope':{'fixed_candidate_site_denominator':True,'whole_rom_consumer_denominator':False,'source_cfg_verified':True,'raw_parameter_paths_verified':True,'natural_runtime_reachability':False,'editing_or_relocation_safety':False,'padding_or_free_space':False,'command_script_semantics':False}}
assert (len(consumers),len(records),sum(b-a for a,b in u['unique_ranges']))==(92,85,1053)
p=Path('tools/data/rom-display-text-delta-contract-v1.json');p.write_bytes(canonical(contract));print(json.dumps({'contract_sha256':sha(p.read_bytes()),'input_count':len(inputs),'consumer_count':len(consumers),'record_count':len(records)}))
