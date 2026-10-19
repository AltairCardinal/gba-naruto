"""Freeze visible source inputs and acceptance denominators; no publication."""
import gzip,hashlib,json,re,struct
from pathlib import Path
from tools.verify_rom_fixed_renderer_script_records import _cfg_blocks,_prove_parameter_flow,_parse
root=Path('.');rom=(root/'rom/base.gba').read_bytes();assert hashlib.sha256(rom).hexdigest()=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
precoverage='notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-after.json.gz'
coverage_raw=gzip.decompress(Path(precoverage).read_bytes());assert hashlib.sha256(coverage_raw).hexdigest()=='b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
unknown=[s['range']for s in json.loads(coverage_raw)['segments']if s['primary_class']=='unknown']
base,_=_cfg_blocks(root);groups=[('inventory-v2-v3',base)];sources=[]
for v in [1,3,6]:
 name='rom-cfg-proven-roots.json' if v==1 else f'rom-cfg-proven-roots-v{v}.json';p=f'artifacts/rom-cfg-proven-roots-v{v}/{name}';sources.append(p);groups.append((f'proven-roots-v{v}',json.loads(Path(p).read_bytes())['extension']['blocks']))
pools=[[0,0x1cd0],[0x42ab,0x542e],[0x578c,0x7554]];sjis=tuple((int.from_bytes(rom[p:p+2],'little'),int.from_bytes(rom[p:p+2],'little')+rom[p+2])for p in range(0x53d644,0x53d73c,8));rows=[];records={}
for source,blocks in groups:
 for block in blocks:
  if block.get('mode')!='thumb':continue
  a,b=block['range']
  for site in range(a,b,2):
   half=struct.unpack_from('<H',rom,site)[0]
   if half&0xf800!=0x4800:continue
   literal=((site+4)&~3)+4*(half&255);target=struct.unpack_from('<I',rom,literal)[0]-0x08000000
   pool=next((p for p in pools if p[0]<=target<p[1]),None)
   if pool is None or not any(lo<=target<hi for lo,hi in unknown):continue
   sink=_prove_parameter_flow(rom,site,(half>>8)&7)
   row={'source':source,'block_id':block['id'],'site':site,'literal_word':literal,'target':target,'interpreter_callsite':sink,'path_sha256':hashlib.sha256(rom[site:sink+4]).hexdigest()}
   try:
    end,ops=_parse(rom,target,pool[1],sjis);row['accepted']=True;records[target]={'range':[target,end],'opcode_sequence':ops,'bytes_sha256':hashlib.sha256(rom[target:end]).hexdigest()}
   except ValueError as error:
    m=re.search(r'unsupported opcode (\d+)',str(error));assert m,error;row.update(accepted=False,excluded_opcode=int(m.group(1)))
   rows.append(row)
rows.sort(key=lambda r:r['site']);records=[records[p]for p in sorted(records)]
assert len(rows)==47 and sum(r['accepted']for r in rows)==34 and len(records)==29 and sum(b-a for a,b in(r['range']for r in records))==1668
paths={precoverage}
for dirname in ['rom-cfg-inventory-v2','rom-cfg-inventory-v3','rom-battle-controller-cfg-v1','rom-training-text-script-inventory-v1']+[f'rom-cfg-proven-roots-v{v}'for v in range(1,7)]:
 paths.update(p.as_posix()for p in (Path('artifacts')/dirname).iterdir()if p.is_file())
paths.update(['tools/verify_rom_cfg_inventory.py','tools/verify_rom_cfg_inventory_v3.py','tools/verify_rom_cfg_proven_roots.py','tools/verify_rom_battle_controller_cfg.py','tools/export_rom_fixed_renderer_script_records.py','tools/verify_rom_fixed_renderer_script_records.py','tools/export_rom_training_text_script_inventory.py','tools/verify_rom_training_text_script_inventory.py','tools/thumb_branch.py','tools/export_rom_small_cfg_dependency_batch.py','tools/export_rom_cfg_proven_roots_v21.py','tools/rom_small_cfg_callback_gaps_independent_verifier.py'])
paths.update(f'tools/verify_rom_cfg_proven_roots_v{v}.py'for v in range(2,7))
inputs=[{'path':p,'size':Path(p).stat().st_size,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}for p in sorted(paths)]
contract={'schema':'rom-renderer-records-delta-contract-v1','inputs':inputs,'later_cfg_payloads':sources,'target_pools':pools,'precoverage':{'path':precoverage,'raw_sha256':hashlib.sha256(coverage_raw).hexdigest()},'consumers':rows,'records':records,'consumer_count':47,'record_count':29,'promotion_bytes':1668,'scope':{'whole_rom_consumer_denominator':False,'natural_runtime_reachability':False,'context_lifecycle_closed':False,'new_opcode_semantics':False,'padding_or_free_space':False,'editing_or_relocation_safety':False}}
raw=(json.dumps(contract,sort_keys=True,indent=2)+'\n').encode();Path('tools/data/rom-renderer-records-delta-contract-v1.json').write_bytes(raw)
print(json.dumps({'contract_sha256':hashlib.sha256(raw).hexdigest(),'inputs':len(inputs),'consumers':len(rows),'records':len(records),'bytes':1668},sort_keys=True))
