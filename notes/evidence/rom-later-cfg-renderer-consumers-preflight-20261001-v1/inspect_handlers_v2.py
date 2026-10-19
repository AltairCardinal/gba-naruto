"""Read-only bounded handler inspection; no grammar expansion or promotion."""
import hashlib,json
from pathlib import Path
from tools._vendor.capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from tools.verify_rom_fixed_renderer_script_records import _cfg_blocks
from tools.analyze_rom_renderer_handler_graphs import walk_handler
root=Path('.');rom=(root/'rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest()=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
blocks,cfg=_cfg_blocks(root);engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB);membership={}
windows=[(0x67158,0x675e4),(0x66d14,0x66e10),(0x68352,0x68370)]
for b in blocks:
 a,z=b['range']
 if b.get('mode')!='thumb' or not any(a<hi and lo<z for lo,hi in windows):continue
 cursor=a
 for i in engine.disasm(rom[a:z],a):
  assert i.address==cursor;membership[i.address]=i.size;cursor+=i.size
 assert cursor==z
handlers=[]
for label,entry,bounds,stops in [('opcode2',0x671da,(0x671da,0x671ea),{0x68354}),('opcode5-6-shared',0x67210,(0x67210,0x675e4),{0x68354,0x6835e})]:
 try:handlers.append({'label':label,**walk_handler(rom,entry,bounds,stops,membership,context_targets={0x9c574})})
 except ValueError as error:handlers.append({'label':label,'membership_or_decode_failure':str(error),'promotion_bytes':0})

disassembly={f'{lo:06x}-{hi:06x}':[{'offset':i.address,'bytes':i.bytes.hex(),'mnemonic':i.mnemonic,'operands':i.op_str,'accepted_instruction_member':membership.get(i.address)==i.size} for i in engine.disasm(rom[lo:hi],lo)] for lo,hi in windows}
print(json.dumps({'schema':'renderer-opcode2-6-inspection-v1','rom_sha256':hashlib.sha256(rom).hexdigest(),'cfg':cfg,'handlers':handlers,'disassembly':disassembly,'promotion_bytes':0,'new_grammar_accepted':False},sort_keys=True,indent=2))
