"""Freeze two allocator base pairs and parse candidate first-slot descriptors."""
import hashlib
import json
import struct
from pathlib import Path
from tools._vendor.capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

rom = Path('rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest() == '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
raw = Path('sequel/rom-byte-coverage.json').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
windows = []
for lo, hi in [(0x6f8fe,0x6f918),(0x71044,0x71064),(0x626b4,0x62766),(0x62924,0x62a0a),(0x631f6,0x63208),(0x63238,0x6327a)]:
    windows.append({'range':[lo,hi], 'sha256':hashlib.sha256(rom[lo:hi]).hexdigest(),
                    'raw_hex':rom[lo:hi].hex(),'linear_disassembly':[
                        {'at':i.address,'bytes':i.bytes.hex(),'mnemonic':i.mnemonic,'operands':i.op_str} for i in engine.disasm(rom[lo:hi],lo)]})
assert windows[2]['sha256']=='09cd85fb8fcdc85751019c67ef6b91d6d3d64c1fbeb0b0496e270234f846d804'
assert windows[3]['sha256']=='23ead2fcc1537d16a632bf68dbccdb96a142af170410f862baaf4c1d750e0a18'
assert windows[4]['sha256']=='79cb19c28c7f5a75ed323f99c837e131c0e11dd06c91f422e60ac9ff859e8f44'
assert windows[5]['sha256']=='b6dc39ac66ecaac48e16f37406bab7e579362759e9e3570e9c6fa9e24ec0ab23'

def literal(at):
    half = struct.unpack_from('<H',rom,at)[0]
    assert half & 0xf800 == 0x4800
    location = ((at+4)&~3)+4*(half&255)
    return {'site':at,'register':(half>>8)&7,'literal_word':location,
            'target':struct.unpack_from('<I',rom,location)[0]-0x08000000}

rows=[]
for first, second, call in [(0x6f90c,0x6f90e,0x6f914),(0x71044,0x71046,0x71060)]:
    a,b=literal(first),literal(second)
    assert a['register']==0 and b['register']==1
    # Interpret only group=0/slot=0 under the existing allocator/renderer grammar.
    sequence=struct.unpack_from('<I',rom,b['target'])[0]-0x08000000
    record_id,duration=struct.unpack_from('<HH',rom,sequence)
    descriptor=struct.unpack_from('<I',rom,a['target']+4*record_id)[0]-0x08000000
    assert 0x45832c <= descriptor < 0x458794
    p=descriptor
    entries=[]
    while p+2<=0x458794:
        if struct.unpack_from('<h',rom,p)[0]==-1:
            break
        assert p+20<=0x458794
        entries.append({'range':[p,p+20],'raw_hex':rom[p:p+20].hex()})
        p+=20
    else:
        raise ValueError('candidate descriptor lacks a bounded sentinel')
    rows.append({'base_loads':[a,b],'allocator_callsite':call,'assumed_group':0,'assumed_initial_slot':0,
                 'sequence':sequence,'first_record_id':record_id,'duration':duration,
                 'descriptor':descriptor,'entries':entries,'sentinel_head_range':[p,p+2],
                 'sentinel_word_hex':rom[p:p+4].hex(),
                 'sequence_next_head':struct.unpack_from('<h',rom,sequence+4)[0],
                 'full_consumer_flow_verified':False})
inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in [
    'sequel/rom-byte-coverage.json','tools/export_rom_fixed_animation_descriptor_groups.py',
    'tools/verify_rom_fixed_animation_descriptor_groups.py']}
print(json.dumps({'schema':'animation-base-pairs-preflight-v1','inputs':inputs,'rows':rows,'windows':windows,
                  'scope':'Two fixed base-pair examples and historical parser identity only; no complete caller flow, record lifecycle, source CFG replay or promotion.',
                  'promotion_bytes':0},sort_keys=True,indent=2))
