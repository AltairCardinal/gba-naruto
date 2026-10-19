"""Bounded unit-pool address alias; no live value or whole-writer proof."""
from pathlib import Path
import json,hashlib,sys
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
from tools.analyze_rom_ai_entry_domains import read_coverage,ROM_SHA256
rom=(root/'rom/base.gba').read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest();assert sha(rom)==ROM_SHA256
coverage=read_coverage(root);points=[]
for a,size in [(0x75188,4),(0x6a99e,2),(0x6a9a0,2),(0x6a9a2,2),(0x6a9a4,2),(0x6a9ae,2),(0x6a9b0,2),(0x6a9b2,2),(0x6a9ba,2),(0x6a9bc,2),(0x6a9be,2),(0x6a9c4,2),(0x6a9ce,2),(0x6a9d0,2),(0x6a9d2,2),(0x6a9da,2),(0x6a9dc,2)]:
 owners=[r for r in coverage['claims'] if r['role']=='primary' and r['range'][0]<=a and a+size<=r['range'][1]]
 assert len(owners)==1 and 'reachable_instruction_bytes' in owners[0]['claim_kind'] and owners[0].get('mode')=='thumb'
 points.append({'offset':a,'raw_hex':rom[a:a+size].hex(),'owner':owners[0]})
for a,word in [(0x6a99e,0x2101),(0x6a9a0,0x24ea),(0x6a9a2,0x0064),(0x6a9ae,0x7002),(0x6a9b0,0x30d0),(0x6a9b2,0x6002),(0x6a9ba,0x290c),(0x6a9bc,0xd9f4),(0x6a9be,0x2100),(0x6a9ce,0x7002),(0x6a9d0,0x30d0),(0x6a9d2,0x6002),(0x6a9da,0x2902),(0x6a9dc,0xd9f4)]:
 assert int.from_bytes(rom[a:a+2],'little')==word
literals=[]
for a,expected in [(0x6a9a4,0x020240c0),(0x6a9c4,0x02025884)]:
 half=int.from_bytes(rom[a:a+2],'little');assert half>>11==9 and (half>>8)&7==3
 literal=((a+4)&~3)+(half&255)*4;value=int.from_bytes(rom[literal:literal+4],'little');assert value==expected
 owner=next(r for r in coverage['claims'] if r['role']=='primary' and r['range'][0]<=literal and literal+4<=r['range'][1]);assert 'literal' in owner['claim_kind']
 literals.append({'instruction':a,'literal_offset':literal,'value':value,'owner':owner})
primary,extra=[r['value'] for r in literals];stride=0xea*2;assert primary+13*stride==extra
print(json.dumps({'schema':'rom-ai-unit-pool-alias-preflight-v1','rom_sha256':ROM_SHA256,'function_range':[0x6a99c,0x6a9e4],'function_sha256':sha(rom[0x6a99c:0x6a9e4]),'points':points,'literals':literals,'stride':stride,'main_slots_explicitly_cleared':list(range(1,13)),'extra_slots_explicitly_cleared':list(range(3)),'recognized_unit_data_store_fields':[{'offset':0,'size':1},{'offset':0xd0,'size':4}],'configured_cd_field':0xcd,'main_slot_13_base':primary+13*stride,'extra_slot_0_base':extra,'address_alias_verified':True,'slot_13_cd_address':extra+0xcd,'slot_13_cd_live_value_proved':False,'initial_clear_proves_cd_zero':False,'stack_or_async_aliases_exhausted':False,'promotion_bytes':0},indent=2,sort_keys=True))
