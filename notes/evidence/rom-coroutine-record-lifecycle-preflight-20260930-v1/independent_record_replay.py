"""Independent raw initializer/literal checks, not global task semantics."""
import hashlib
import json
import struct
from pathlib import Path

run = Path(__file__).resolve().parent
rom = Path('rom/base.gba').read_bytes()
report = json.loads((run/'record-shapes-v3.json').read_text())
assert hashlib.sha256(rom).hexdigest()==report['rom_sha256']
half=lambda a:struct.unpack_from('<H',rom,a)[0]
word=lambda a:struct.unpack_from('<I',rom,a)[0]
assert half(0x61d16)==0x2200 and half(0x61d1e)&0xff00==0x2000
stride=half(0x61d1e)&255
assert half(0x61d46)&0xff00==0x2a00
last=half(0x61d46)&255
assert stride==0x4c and last==7
assert half(0x61d22)==0x2701 and rom[0x61d24:0x61d28].hex()=='01235b42'
for binding in report['literal_bindings']:
    a=binding['instruction'];raw=half(a)
    assert raw&0xf800==0x4800
    p=((a+4)&~3)+4*(raw&255)
    assert p==binding['literal'] and word(p)==binding['value']
pool=word(0x61d68)
assert pool==0x03000a88
assert [r['record_base'] for r in report['fixed_initializer_records']]==[pool+stride*i for i in range(last+1)]
assert pool+stride*(last+1)==word(0x61df4)==0x03000ce8
assert half(0x61d9a)==0x2b00
branch=half(0x61d9c);delta=(branch&255)*2
if delta&0x100:delta-=0x200
assert branch&0xff00==0xd000 and 0x61d9c+4+delta==0x61dc8
assert word(word(0x61dfc)-0x08000000)==0xffffffff
assert report['alias_arithmetic']['saved_sp_store_address']==0x03000cec
assert sorted({(v+2)&255 for v in range(256)})==report['unrestricted_u8_plus2_mod256_domain']
print(json.dumps({'initializer_literal_and_slot_zero_marker_replayed':True,
                  'initial_record_count':last+1,'stride':stride,'pool_base':pool,
                  'pool_end_aliases_callback_base':True,
                  'membership_excluded_shapes':len(report['excluded_raw_decoder_shapes']),
                  'global_writer_or_resume_domain_closed':False,'promotion_bytes':0},sort_keys=True,indent=2))
