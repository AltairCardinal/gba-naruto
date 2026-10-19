"""Seven schema-specific promoted code domains; screening only, not new claims."""
import gzip,hashlib,json,struct
from pathlib import Path
from tools._vendor.capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from tools.verify_rom_fixed_renderer_script_records import _prove_parameter_flow,_parse
root=Path('.');rom=(root/'rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest()=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
raw=gzip.decompress((root/'notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-after.json.gz').read_bytes())
assert hashlib.sha256(raw).hexdigest()=='b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
segments=json.loads(raw)['segments'];unknown=[s['range']for s in segments if s['primary_class']=='unknown'];engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
sjis=tuple((int.from_bytes(rom[p:p+2],'little'),int.from_bytes(rom[p:p+2],'little')+rom[p+2])for p in range(0x53d644,0x53d73c,8))
inputs={};domains=[];rows=[];excluded=[]
for version in range(15,22):
 path=Path(f'artifacts/rom-cfg-proven-roots-v{version}/rom-cfg-proven-roots-v{version}.json');pr=path.read_bytes();mr=(path.parent/'manifest.json').read_bytes();manifest=json.loads(mr);receipt=manifest['files'][path.name];digest=hashlib.sha256(pr).hexdigest()
 if isinstance(receipt,str):assert receipt==digest
 else:assert receipt['sha256']==digest and receipt['size']==len(pr)
 inputs[path.as_posix()]={'size':len(pr),'sha256':digest,'manifest_sha256':hashlib.sha256(mr).hexdigest()};data=json.loads(pr)
 if version==15:
  assert len(data['targets'])==data['promotion']['accepted_root_count']
  ranges=[r for t in data['targets'] for r in t['code_ranges']]
 elif version==16:ranges=data['promotion']['ranges']
 else:ranges=[c['range']for c in data['promotion']['claims']if c['kind']=='reachable_thumb_code']
 promoted_bytes=0;instructions=0
 for lo,hi in ranges:
  owners=[s for s in segments if s['range'][0]<hi and lo<s['range'][1]]
  if not all(f'proven_roots_v{version}'in s['primary_class'] and 'thumb'in s['primary_class'] for s in owners):
   excluded.append({'version':version,'range':[lo,hi],'reason':'canonical class does not prove a pure promoted Thumb instruction domain','classes':sorted(set(s['primary_class']for s in owners))});continue
  assert sum(min(hi,s['range'][1])-max(lo,s['range'][0])for s in owners)==hi-lo
  cursor=lo
  for i in engine.disasm(rom[lo:hi],lo):
   assert i.address==cursor;cursor+=i.size;instructions+=1
   if i.size!=2:continue
   at=i.address;half=struct.unpack_from('<H',rom,at)[0]
   if half&0xf800!=0x4800:continue
   literal=((at+4)&~3)+4*(half&255);target=struct.unpack_from('<I',rom,literal)[0]-0x08000000
   if not 0<=target<len(rom) or not any(a<=target<b for a,b in unknown):continue
   row={'version':version,'site':at,'literal_word':literal,'target':target,'owner_range':[lo,hi]}
   try:
    row['interpreter_callsite']=_prove_parameter_flow(rom,at,(half>>8)&7)
    try:stop,ops=_parse(rom,target,len(rom),sjis);row.update(syntax_range=[target,stop],opcodes=ops)
    except ValueError as error:row['parser_exclusion']=str(error)
   except ValueError as error:row['flow_exclusion']=str(error)
   rows.append(row)
  assert cursor==hi
  promoted_bytes+=hi-lo
 domains.append({'version':version,'code_ranges':ranges,'screened_code_bytes':promoted_bytes,'screened_instruction_count':instructions})
print(json.dumps({'schema':'late-cfg-promoted-literal-screen-v1','inputs':inputs,'domains':domains,'excluded_domains':excluded,'unknown_literal_consumers':rows,'promotion_bytes':0,'source_semantic_verifiers_rerun':False,'scope':'Only seven promoted code domains; excludes full closures, coarse owners, RAM or computed target denominators.'},sort_keys=True,indent=2))
