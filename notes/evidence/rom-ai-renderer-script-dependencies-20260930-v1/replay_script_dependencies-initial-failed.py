"""Reuse accepted script parsing and bounded literal-to-r0 flow; no side-effect proof."""
from pathlib import Path
import sys,json,hashlib
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
from tools.analyze_rom_ai_entry_domains import read_coverage,ROM_SHA256
from tools import verify_rom_fixed_renderer_script_records as verifier
rom=(root/'rom/base.gba').read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(rom)==ROM_SHA256
module='tools/verify_rom_fixed_renderer_script_records.py'
assert sha((root/module).read_bytes())=='c7f3eeaabc4a6755c7974838084aa7495f866924e40fd4ea2bb072d5db7f3927'
artifact='artifacts/rom-fixed-renderer-script-records-v1/rom-fixed-renderer-script-records.json'
raw=(root/artifact).read_bytes();assert sha(raw)=='7b56a9a05d8ea7d78bddd68dba874f0c7cae2ae3fa5d1aa6c2ab3a3949ec7698'
x=json.loads(raw);coverage=read_coverage(root);rows=[]
for site,literal,register,call,target,end in [(0x74210,0x74294,2,0x74254,0x175d,0x177d),(0x74304,0x74384,2,0x74348,0x175d,0x177d),(0x7425e,0x74298,0,0x74260,0x177d,0x1781),(0x74352,0x74388,0,0x74354,0x177d,0x1781)]:
 assert int.from_bytes(rom[literal:literal+4],'little')==0x08000000+target
 half=int.from_bytes(rom[site:site+2],'little');assert half&0xf800==0x4800 and (half>>8)&7==register
 assert ((site+4)&~3)+(half&255)*4==literal
 owner=next(r for r in coverage['claims'] if r['role']=='primary' and r['range'][0]<=site and call+4<=r['range'][1])
 assert owner['claim_kind']=='battle_controller_cfg_reachable_instruction_bytes'
 assert verifier._prove_parameter_flow(rom,site,register)==call
 record=next(r for r in x['records']['items'] if r['range']==[target,end]);assert sha(rom[target:end])==record['bytes_sha256']
 ranges=tuple((int.from_bytes(rom[0x53d644+i*8:0x53d646+i*8],'little'),rom[0x53d646+i*8]) for i in range(31))
 parsed=verifier._parse(rom,target,end,tuple((a,a+n) for a,n in ranges));assert parsed==(end,record['opcode_sequence'])
 rows.append({'literal_instruction':site,'literal_word':literal,'interpreter_callsite':call,'script_record':record,'instruction_owner':owner,'bounded_parameter_flow_replayed':True,'record_parse_replayed':True,'callee_side_effects_proved':False})
print(json.dumps({'schema':'rom-ai-renderer-script-dependencies-preflight-v1','rom_sha256':ROM_SHA256,'reused_verifier_path':module,'reused_artifact_path':artifact,'rows':rows,'promotion_bytes':0,'script_interpreter_not_state_switch':True,'all_interpreter_incoming_producers_closed':False,'instruction_owner_source':'immutable canonical archive','script_side_effects_and_wait_frame_state_preservation_proved':False},indent=2,sort_keys=True))
