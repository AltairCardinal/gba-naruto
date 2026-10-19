"""Bounded protocol-tag writer/reader preflight, no renderer or promotion claim."""
import hashlib
import json
import struct
from pathlib import Path
from collections import Counter
from tools._vendor.capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from tools.export_rom_fixed_consumer_text_inventory import _renderer_record_end, _sjis_ranges
from tools.verify_rom_fixed_consumer_text_inventory import _independent_renderer_end, _independent_sjis_ranges

rom=Path('rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest()=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
raw=Path('sequel/rom-byte-coverage.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
segments=json.loads(raw)['segments'];screen=Path('notes/evidence/rom-large-unknown-anchor-screen-20261001-v1/anchors.json')
pool=next(r for r in json.loads(screen.read_text())['rows']if r['range']==[0x12ee10,0x12f298])
engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB);engine.detail=True
rows=[]

def bl(at):
    a,b=struct.unpack_from('<HH',rom,at)
    assert a&0xf800==0xf000 and b&0xf800==0xf800
    n=((a&2047)<<12)|((b&2047)<<1)
    if n&0x400000:n-=0x800000
    return at+4+n

for source in pool['classified_thumb_ldr_shapes']:
    at=source['at'];owner=next(s for s in segments if s['range'][0]<=at<s['range'][1]);hi=min(at+64,owner['range'][1])
    half=struct.unpack_from('<H',rom,at)[0];register=f'r{(half>>8)&7}'
    preserved=True;call=None;trace=[];stop='owner_or_window_end'
    for insn in engine.disasm(rom[at:hi],at):
        trace.append({'at':insn.address,'bytes':insn.bytes.hex(),'mnemonic':insn.mnemonic,'operands':insn.op_str})
        if insn.mnemonic=='bl':
            call={'at':insn.address,'target':bl(insn.address)}
            assert call['target']==int(insn.op_str[1:],16);stop='first_call';break
        if insn.address!=at and register in [insn.reg_name(x)for x in insn.regs_access()[1]]:preserved=False
        if insn.mnemonic.startswith('b')or insn.mnemonic in ('pop','svc'):stop='control_boundary';break
    binding=bool(preserved and register=='r2'and call and call['target']in(0x85a40,0x85b8c))
    row={'source':source,'register':register,'preserved':preserved,'first_call':call,'stop':stop,
         'conditional_tag_binding_candidate':binding,'trace':trace}
    if binding:
        target=source['target'];role='emit_fixed14'if call['target']==0x85a40 else'match_nul_or14'
        row.update(role=role,raw_first14_hex=rom[target:target+14].hex())
        if role=='emit_fixed14':end=target+14
        else:
            end=target
            while end<target+14:
                byte=rom[end];end+=1
                if byte==0:break
        row['hypothetical_read_range']=[target,end]
    if preserved and register=='r0'and call and call['target']in(0x66758,0x667a0):
        target=source['target']
        end=_renderer_record_end(rom,target,0x12f298,_sjis_ranges(rom))
        assert end==_independent_renderer_end(rom,target,0x12f298,_independent_sjis_ranges(rom))
        row['renderer_hypothetical_range']=[target,end]
    rows.append(row)

windows=[]
for lo,hi in [(0x85a40,0x85a74),(0x85a74,0x85b8c),(0x85b8c,0x85bc0),(0x85bc0,0x85d00),(0x857e4,0x85850)]:
    windows.append({'range':[lo,hi],'sha256':hashlib.sha256(rom[lo:hi]).hexdigest(),'raw_hex':rom[lo:hi].hex(),
                    'linear_disassembly':[{'at':i.address,'mnemonic':i.mnemonic,'operands':i.op_str}for i in engine.disasm(rom[lo:hi],lo)]})
anchors=[]
for at in [0x85a56,0x85b1c,0x85ba0,0x85c5a]:
    half=struct.unpack_from('<H',rom,at)[0];literal=((at+4)&~3)+4*(half&255)
    anchors.append({'ldr':at,'literal':literal,'ram':struct.unpack_from('<I',rom,literal)[0]})
assert [x['ram']for x in anchors]==[0x03005e30,0x03005e30,0x03005e34,0x03005e34]
text_ranges=sorted({tuple(r['renderer_hypothetical_range'])for r in rows if 'renderer_hypothetical_range'in r})
assert all(a[1]<=b[0]for a,b in zip(text_ranges,text_ranges[1:]))
print(json.dumps({'schema':'ram-protocol-tag-preflight-v1','inputs':{'coverage_sha256':hashlib.sha256(raw).hexdigest(),'screen_sha256':hashlib.sha256(screen.read_bytes()).hexdigest()},
                  'rows':rows,'windows':windows,'pointer_anchors':anchors,'row_count':len(rows),
                  'candidate_count':sum(r['conditional_tag_binding_candidate']for r in rows),
                  'renderer_hypothetical_record_count':len(text_ranges),'renderer_hypothetical_bytes':sum(b-a for a,b in text_ranges),
                  'first_call_counts':dict(Counter(f"{r['first_call']['target']:06x}"for r in rows if r['first_call'])),
                  'promotion_bytes':0,'scope':'Local literal-to-first-call and raw RAM pointer field identities; reader ranges are conditional hypothetical prefixes only. No full CFG, all writers, shared state, live pipeline readiness, channel protocol semantics or natural execution proof.'},sort_keys=True,indent=2))
