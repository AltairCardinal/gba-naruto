"""Exact ROM slot words and pinned-CFG literal consumers; no computed-writer closure."""
import hashlib,json,struct
from pathlib import Path
from tools._vendor.capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from tools.verify_rom_fixed_renderer_script_records import _cfg_blocks
rom=Path('rom/base.gba').read_bytes();assert hashlib.sha256(rom).hexdigest()=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
blocks,cfg=_cfg_blocks(Path('.'));word=struct.pack('<I',0x0200a888);offsets=[];at=0
while True:
 at=rom.find(word,at)
 if at<0:break
 offsets.append(at);at+=1
rows=[];engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
for block in blocks:
 if block.get('mode')!='thumb':continue
 lo,hi=block['range']
 for insn in engine.disasm(rom[lo:hi],lo):
  at=insn.address;half=struct.unpack_from('<H',rom,at)[0]
  if insn.size!=2 or half&0xf800!=0x4800:continue
  literal=((at+4)&~3)+4*(half&255)
  if struct.unpack_from('<I',rom,literal)[0]!=0x0200a888:continue
  rows.append({'site':at,'literal':literal,'block_id':block['id'],'block_range':[lo,hi],
               'disassembly':[{'offset':i.address,'bytes':i.bytes.hex(),'mnemonic':i.mnemonic,'operands':i.op_str} for i in engine.disasm(rom[max(lo,at-24):min(hi,at+48)],max(lo,at-24))]})
print(json.dumps({'schema':'renderer-ram-text-slot-preflight-v1','slot':0x0200a888,'exact_word_occurrences':offsets,'cfg_literal_consumers':rows,'upstream_cfg_contract':cfg,'computed_writers_exhausted':False,'promotion_bytes':0},sort_keys=True,indent=2))
