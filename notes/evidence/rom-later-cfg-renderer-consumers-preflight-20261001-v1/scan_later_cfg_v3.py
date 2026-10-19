"""Later-CFG literal screening; file identity only, not new semantic acceptance."""
import gzip,hashlib,json,struct,re
from pathlib import Path
from tools._vendor.capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from tools.verify_rom_fixed_renderer_script_records import _prove_parameter_flow,_parse
root=Path('.');rom=(root/'rom/base.gba').read_bytes();assert hashlib.sha256(rom).hexdigest()=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
coverage=json.loads(gzip.decompress((root/'notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-after.json.gz').read_bytes()));unknown=[s['range'] for s in coverage['segments'] if s['primary_class']=='unknown']
sjis=tuple((int.from_bytes(rom[p:p+2],'little'),int.from_bytes(rom[p:p+2],'little')+rom[p+2])for p in range(0x53d644,0x53d73c,8));engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
rows=[];inputs={};seen=set();excluded=[]
def blocks_in(value):
 if isinstance(value,dict):
  if isinstance(value.get('blocks'),list):
   for block in value['blocks']:
    if isinstance(block,dict) and 'mode'in block and 'range'in block:yield block
  for key,item in value.items():
   if key!='blocks':yield from blocks_in(item)
 elif isinstance(value,list):
  for item in value:yield from blocks_in(item)

for path in sorted((root/'artifacts').glob('rom-cfg-proven-roots*/rom*.json')):
 if not re.fullmatch(r'rom-cfg-proven-roots-v\d+',path.parent.name):continue
 raw=path.read_bytes();manifest_path=path.parent/'manifest.json';mr=manifest_path.read_bytes();manifest=json.loads(mr);receipt=manifest['files'][path.name]
 digest=hashlib.sha256(raw).hexdigest()
 if isinstance(receipt,str):assert receipt==digest
 else:assert receipt['size']==len(raw) and receipt['sha256']==digest
 inputs[path.as_posix()]={'sha256':digest,'size':len(raw),'manifest_sha256':hashlib.sha256(mr).hexdigest()}
 data=json.loads(raw)
 blocks=list(blocks_in(data))
 if not blocks:excluded.append({'artifact':path.parent.as_posix(),'reason':'no supported structured block denominator; other instruction schemas not inferred'})
 for b in blocks:
  if b.get('mode')!='thumb':continue
  lo,hi=b['range'];cursor=lo
  for i in engine.disasm(rom[lo:hi],lo):
   assert i.address==cursor;cursor+=i.size;at=i.address
   if i.size!=2:continue
   half=struct.unpack_from('<H',rom,at)[0]
   if half&0xf800!=0x4800:continue
   literal=((at+4)&~3)+4*(half&255);target=struct.unpack_from('<I',rom,literal)[0]-0x08000000
   if not 0<=target<0x7554 or not any(a<=target<z for a,z in unknown) or at in seen:continue
   seen.add(at);row={'site':at,'literal':literal,'target':target,'source_artifact':path.parent.as_posix(),'block_id':b['id'],'instruction_size':i.size}
   try:
    row['interpreter_callsite']=_prove_parameter_flow(rom,at,(half>>8)&7)
    try:
     end,ops=_parse(rom,target,0x7554,sjis);row['candidate_range']=[target,end];row['opcodes']=ops;row['unknown_bytes']=sum(max(0,min(end,z)-max(target,a))for a,z in unknown)
    except ValueError as error:row['parser_exclusion']=str(error)
   except ValueError as error:row['flow_exclusion']=str(error)
   rows.append(row)
  assert cursor==hi
print(json.dumps({'schema':'later-cfg-low-literal-screen-v1','inputs':inputs,'target_range':[0,0x7554],'unknown_literal_sites':sorted(rows,key=lambda r:r['site']),'unsupported_block_schema_artifacts':excluded,'source_semantic_verifiers_rerun':False,'promotion_bytes':0,'accepted_claims':0},sort_keys=True,indent=2))
