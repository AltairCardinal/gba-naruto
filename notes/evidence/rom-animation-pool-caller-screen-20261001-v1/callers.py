"""Bounded constant-argument preflight; candidate shapes, never accepted claims."""
import hashlib
import json
import re
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
segments=json.loads(raw)['segments']
screen_path=Path('notes/evidence/rom-large-unknown-anchor-screen-20261001-v1/anchors.json')
pool=next(r for r in json.loads(screen_path.read_text())['rows'] if r['range']==[0x45832c,0x458794])
engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB);engine.detail=True

def branch(at):
    a,b=struct.unpack_from('<HH',rom,at)
    if a&0xf800!=0xf000 or b&0xf800!=0xf800:return None
    offset=((a&2047)<<12)|((b&2047)<<1)
    if offset&0x400000:offset-=0x800000
    return at+4+offset

rows=[]
for source in pool['classified_thumb_ldr_shapes']:
    at=source['at'];owner=next(s for s in segments if s['range'][0]<=at<s['range'][1])
    assert owner['primary_class']==source['owner_class']
    hi=min(at+80,owner['range'][1]);state={};trace=[];reason='owner_or_window_end';call=None
    for insn in engine.disasm(rom[at:hi],at):
        trace.append({'at':insn.address,'bytes':insn.bytes.hex(),'mnemonic':insn.mnemonic,'operands':insn.op_str})
        if insn.mnemonic=='bl':
            call={'site':insn.address,'target':branch(insn.address)}
            assert call['target']==int(insn.op_str[1:],16)
            reason='first_call';break
        if insn.mnemonic.startswith('b') or insn.mnemonic in ('pop','svc'):
            reason='control_boundary';break
        old=dict(state)
        for reg in insn.regs_access()[1]:state.pop(insn.reg_name(reg),None)
        half=int.from_bytes(insn.bytes,'little') if insn.size==2 else None
        if half is not None and half&0xf800==0x4800:
            literal=((insn.address+4)&~3)+4*(half&255)
            if literal+4<=len(rom):state[f'r{(half>>8)&7}']=struct.unpack_from('<I',rom,literal)[0]
        elif insn.mnemonic=='movs':
            match=re.fullmatch(r'(r\d+), #(0x[0-9a-f]+|\d+)',insn.op_str)
            if match:state[match[1]]=int(match[2],0)
        elif insn.mnemonic in ('lsls','lsrs'):
            match=re.fullmatch(r'(r\d+), (r\d+), #(0x[0-9a-f]+|\d+)',insn.op_str)
            if match and match[2] in old:
                value,shift=old[match[2]],int(match[3],0)
                state[match[1]]=((value<<shift)&0xffffffff) if insn.mnemonic=='lsls' else (value>>shift)
        elif insn.mnemonic in ('mov','adds'):
            match=re.fullmatch(r'(r\d+), (r\d+)(?:, #0)?',insn.op_str)
            if match and match[2] in old:state[match[1]]=old[match[2]]
    candidate=bool(call and call['target']==0x626b4 and all(r in state for r in ['r0','r1','r2']) and state['r2']==0 and all(0x0845832c<=state[r]<0x08458794 for r in ['r0','r1']))
    exclusion = None
    if not candidate:
        if call is None:exclusion=reason
        elif call['target']!=0x626b4:exclusion='different_first_callee'
        elif not all(r in state for r in ['r0','r1','r2']):exclusion='missing_bounded_constant_arguments'
        elif state['r2']!=0:exclusion='not_fixed_group_zero'
        else:exclusion='base_pair_not_wholly_in_pool'
    rows.append({'source':source,'stop':reason,'first_call':call,'known_registers':state,'fixed_pair_exclusion':exclusion,
                 'fixed_pair_group0_candidate':candidate,'trace':trace})

encoded=[]
halves=[x[0]for x in struct.iter_unpack('<H',rom)]
for i,a in enumerate(halves[:-1]):
    if a&0xf800==0xf000 and halves[i+1]&0xf800==0xf800 and branch(i*2)==0x626b4:encoded.append(i*2)
candidate_calls=sorted({r['first_call']['site']for r in rows if r['fixed_pair_group0_candidate']})
pairs=sorted({(r['known_registers']['r0']-0x08000000,r['known_registers']['r1']-0x08000000)for r in rows if r['fixed_pair_group0_candidate']})
assert set(candidate_calls)<=set(encoded)
renderer_hypotheses=[]
for row in rows:
    call=row['first_call']
    if not call or call['target'] not in (0x66758,0x667a0):continue
    target=row['known_registers'].get('r0',0)-0x08000000
    if not 0x45832c<=target<0x458794:continue
    end=_renderer_record_end(rom,target,0x458794,_sjis_ranges(rom))
    assert end==_independent_renderer_end(rom,target,0x458794,_independent_sjis_ranges(rom))
    renderer_hypotheses.append({'source':row['source']['at'],'call':call,'range':[target,end],
                               'bytes_sha256':hashlib.sha256(rom[target:end]).hexdigest()})
text_ranges=sorted({tuple(r['range'])for r in renderer_hypotheses})
assert all(a[1]<=b[0]for a,b in zip(text_ranges,text_ranges[1:]))
print(json.dumps({'schema':'animation-pool-fixed-callers-preflight-v1','inputs':{'coverage_sha256':hashlib.sha256(raw).hexdigest(),'screen_sha256':hashlib.sha256(screen_path.read_bytes()).hexdigest()},
                  'literal_rows':rows,'row_count':len(rows),'stop_counts':dict(Counter(r['stop']for r in rows)),
                  'candidate_calls':candidate_calls,'candidate_base_pairs':[list(p)for p in pairs],
                  'all_rom_bl_encoding_shapes':encoded,'full_rom_bl_shape_count':len(encoded),
                  'renderer_hypotheses':renderer_hypotheses,'renderer_hypothetical_bytes':sum(b-a for a,b in text_ranges),
                  'promotion_bytes':0,'scope':'116 prior LDR shapes with maximum 80B/same-owner local constant propagation; full-ROM raw BL encoding denominator only. No stack/flags, CFG/source verifier, aliases, computed producers, runtime or semantic acceptance.'},sort_keys=True,indent=2))
