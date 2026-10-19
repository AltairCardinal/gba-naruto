"""Existing raw verifier decoders independently replay the fixed target scan."""
from pathlib import Path
import sys,json,hashlib,struct
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
from tools.verify_rom_prebattle_menu_controller_cfg import _direct_target
from tools.verify_rom_boot_interwork import _arm_b_target
rom=(root/'rom/base.gba').read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(rom)=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
original=json.loads((root/'build/experiments/active/ai-producer-denominator/five-roots-20260930-v1/inventory.json').read_text());targets={int(k,16) for k in original['targets']};thumb={a:[] for a in targets};arm={a:[] for a in targets};pointers={a:[] for a in targets}
for offset in range(0,len(rom)-1,2):
 item=_direct_target(rom,offset)
 if item and item[0] in targets:
  target,kind,size=item;thumb[target].append({'offset':offset,'mnemonic':kind,'raw_hex':rom[offset:offset+size].hex()})
for offset in range(0,len(rom)-3,4):
 word=struct.unpack_from('<I',rom,offset)[0]
 if word>>28==15 or (word>>25)&7!=5:continue
 # B and BL share target arithmetic; normalize only the link bit for the existing B decoder.
 target=offset+_arm_b_target((word&~(1<<24)).to_bytes(4,'little'),0)
 if target in targets:arm[target].append({'offset':offset,'mnemonic':'bl' if word&(1<<24) else 'b','raw_hex':rom[offset:offset+4].hex(),'source_mode':'arm','entry_mode':'thumb','mode_switch_claimed':False})
for target in sorted(targets):
 old=[(r['offset'],r['mnemonic'],r['raw_hex']) for r in original['targets'][f'{target:06x}']['thumb_bl_b_shapes']]
 new=[(r['offset'],r['mnemonic'],r['raw_hex']) for r in thumb[target] if r['mnemonic'] in ['bl','b']];assert old==new
 for tag in [0,1]:
  word=0x08000000+target+tag;needle=word.to_bytes(4,'little');positions=[];cursor=0
  while True:
   found=rom.find(needle,cursor)
   if found<0:break
   positions.append(found);cursor=found+1
  expected=next(r['offsets'] for r in original['targets'][f'{target:06x}']['exact_word_occurrences'] if r['tag']==tag);assert expected==positions
  pointers[target].append({'tag':tag,'word':word,'offsets':positions})
print(json.dumps({'schema':'rom-ai-five-root-producer-independent-preflight-v1','rom_sha256':sha(rom),'original_inventory_sha256':sha((root/'build/experiments/active/ai-producer-denominator/five-roots-20260930-v1/inventory.json').read_bytes()),'decoder_sources':{p:sha((root/p).read_bytes()) for p in ['tools/verify_rom_prebattle_menu_controller_cfg.py','tools/verify_rom_boot_interwork.py']},'verified':True,'scan_range':[0,len(rom)],'scope':'all halfword Thumb BL/B/Bcond encodings, all word ARM B/BL encodings excluding cond=NV, exact tagged and untagged pointer words at every byte; shapes only','natural_runtime_reachability_proved':False,'computed_incoming_producers_closed':False,'promotion_bytes':0,'targets':{f'{a:06x}':{'thumb_shapes':thumb[a],'arm_shapes':arm[a],'exact_words':pointers[a]} for a in sorted(targets)}},indent=2,sort_keys=True))
