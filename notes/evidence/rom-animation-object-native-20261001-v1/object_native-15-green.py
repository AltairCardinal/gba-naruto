"""Joint finite object fixtures on a pinned native core, with raw load traces."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path.cwd().resolve()
HERE=Path(__file__).resolve().parent
PARENT=ROOT/'notes/evidence/rom-animation-irq-arm-native-20261001-v2'
spec=importlib.util.spec_from_file_location('parent_native_contract',PARENT/'arm_probe.py')
parent=importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)
sys.path.insert(0,str(ROOT))
from tools.verify_rom_cfg_inventory import _decode
from tools.verify_rom_text_bg_task_closure import FULL_CODE_RANGES

POOL=0x03003BB8
SP=0x03007000
STOP=0x08000000
BASE=0x08000000
MANAGER=0x0200A8A4
GLOBAL=0x02002880
ROM=(ROOT/'rom/base.gba').read_bytes()
SOURCE=json.loads((ROOT/'notes/evidence/rom-animation-object-lifecycle-20261001-v1/counter-inventory.json').read_text())['source_ranges']+FULL_CODE_RANGES


def ranges(windows):
    intervals=[]
    for lo,hi in windows:
        for start,end in SOURCE:
            begin,finish=max(lo,start),min(hi,end)
            if begin<finish:
                at=begin
                while at<finish:
                    item=_decode(ROM,at,'thumb')
                    if not item['accepted'] or at+item['size']>finish:
                        raise ValueError('source partition')
                    at+=item['size']
                intervals.append([BASE+begin,BASE+finish])
    merged=[]
    for lo,hi in sorted(intervals):
        if merged and lo<=merged[-1][1]:
            merged[-1][1]=max(merged[-1][1],hi)
        else:
            merged.append([lo,hi])
    return merged


def fixture(root,windows,*,stop=STOP,budget=2000,regs=None,memory=(),peek=(),bios=False):
    registers=[0xA0010000+0x100*i+i for i in range(15)]
    registers[13:15]=[SP,STOP|1]
    for index,value in (regs or {}).items():
        registers[index]=value
    allowed=ranges(windows)
    if bios:
        allowed+=[[BASE+0x9C0DC,BASE+0x9C0E4],[0,0x4000]]
    return {'root':BASE+root,'stop':stop,'ranges':allowed,'budget':budget,'registers':registers,
            'cpsr':0xFF,'spsr':0xFF,'banked':[[0xD3,0x03007E00,0]],'memory':list(memory),'peek':list(peek)}


def protocol(f):
    root,stop,budget,allowed=(f[k] for k in ('root','stop','budget','ranges'))
    if not 1<=budget<=500000 or not 1<=len(allowed)<=128 or not any(lo<=root<hi for lo,hi in allowed):
        raise ValueError('native bounds')
    if any(lo>=hi or lo<=stop<hi for lo,hi in allowed):
        raise ValueError('source stop overlap')
    small={**f,'budget':min(budget,2000),'ranges':[[root,root+2]]}
    lines=parent.protocol(small).splitlines()
    lines[-1]=' '.join(map(str,['run',root,stop,budget,len(allowed),*(v for pair in allowed for v in pair)]))
    return '\n'.join(lines)+'\n'


def execute(fixtures, *, persistent=False):
    if hashlib.sha256(ROM).hexdigest()!=parent.ROM_SHA:
        raise ValueError('ROM identity')
    pieces=[protocol(f) for f in fixtures]
    if persistent:
        pieces=[pieces[0],*['\n'.join(piece.splitlines()[1:])+'\n' for piece in pieces[1:]]]
    completed=subprocess.run([str(HERE/'mgba-arm-probe'),str(ROOT/'rom/base.gba')],
                             input=''.join(pieces),text=True,capture_output=True,timeout=90)
    if completed.returncode:
        raise ValueError(f'native failure {completed.returncode}: {completed.stderr[-2000:]}; {completed.stdout[-1000:]}')
    rows=[json.loads(line) for line in completed.stdout.splitlines()]
    snapshot=rows.pop(0)
    expected=json.loads((HERE/'hle-bios-reference.json').read_text())
    bios=bytes.fromhex(snapshot.pop('bios_hex'))
    if len(bios)!=expected['size'] or hashlib.sha256(bios).hexdigest()!=expected['sha256']:
        raise ValueError('BIOS identity')
    if snapshot!={'snapshot_verified':True,'state_size':397312,'snapshot_sha1':'e7ade0ed82bb0f2d3d52070b280a8c84bb8abbab'}:
        raise ValueError('baseline identity')
    if len(rows)!=len(fixtures):
        raise ValueError('case count')
    for f,row in zip(fixtures,rows,strict=True):
        if row['status']!=1 or row['stop']!=f['stop']:
            raise ValueError('native stop')
        row['reads']=[w for w in row['writes'] if isinstance(w,dict) and w.get('read')]
        row['writes']=[w for w in row['writes'] if not isinstance(w,dict) or not w.get('read')]
        row['snapshot_sha1']=snapshot['snapshot_sha1']
        row['input']=f
    return rows


def values(row):
    return {(a,w):v for a,w,v in row['peek']}


def allocation_fixture(*,free=127,context=0xA1234567,alternate=False,flags=0x20,group=0):
    if free is not None and free not in range(128):
        raise ValueError('free slot')
    table=0x03007200
    memory=[[4,POOL+60*i,3] for i in range(128)]
    if free is not None:
        memory += [[4,POOL+60*free,0],[4,POOL+60*free+0x2C,context]]
    stack=[0x12345678,0x1234789A,0x12349ABC,flags,0x0808AA51]
    memory += [[4,SP+4*i,value] for i,value in enumerate(stack)]
    if alternate:
        memory += [[4,table,0x0845854C],[4,table+4,0x08458558]]
        root,windows,regs=0x625A4,[(0x625A4,0x626B0)],{0:table,1:0,2:group,3:0x12343456}
    else:
        root,windows,regs=0x626B4,[(0x626B4,0x62786)],{0:0x0845854C,1:0x08458558,2:group,3:0x12343456}
    peek=[] if free is None else [[4,POOL+60*free+0x2C],*[[2,POOL+60*free+off] for off in (0x14,0x16,0x18)]]
    f=fixture(root,windows,regs=regs,memory=memory,peek=peek,bios=alternate and bool(flags&0x400000))
    return f


def allocate(**kwargs):
    f=allocation_fixture(**kwargs)
    free=kwargs.get('free',127)
    row=execute([f])[0]
    row['handle']=row['registers'][0]
    row['fields']={} if free is None else {a-(POOL+60*free):v for a,w,v in row['peek']}
    return row


def lookup(tags,needle):
    if len(tags)!=10 or any(not 0<=t<=255 for t in [*tags,needle]):
        raise ValueError('manager lookup domain')
    f=fixture(0x655B4,[(0x655B4,0x655F0)],regs={0:needle},
              memory=[[1,MANAGER+i*0x4D0+0x13,t] for i,t in enumerate(tags)])
    row=execute([f])[0]
    index=next((i for i,t in enumerate(tags) if t==needle),10)
    if row['registers'][0]!=MANAGER+index*0x4D0:
        raise ValueError('lookup oracle')
    row['index']=index
    return row


def sort_pool(flags,keys):
    if len(flags)!=128 or len(keys)!=128:
        raise ValueError('pool sort domain')
    memory=[[4,POOL+60*i,value] for i,value in enumerate(flags)]
    memory += [[2,POOL+60*i+offset,keys[i]&65535] for i in range(128) for offset in (6,0x1A)]
    peek=[[1,0x03005BB8],*[[4,0x030059B8+4*i] for i in range(128)]]
    f=fixture(0x627B0,[(0x627B0,0x6291A)],budget=500000,memory=memory,peek=peek)
    row=execute([f])[0]
    data=values(row)
    count=data[(0x03005BB8,1)]
    row['order']=[(data[(0x030059B8+4*i,4)]-POOL)//60 for i in range(count)]
    return row


def callback(*,context=0,manager_slot=0,pending=0,last_slot=0):
    obj=POOL+127*60
    memory=[[4,obj,1],[2,obj+0x2C,context],[2,obj+0x2E,last_slot],[2,obj+0x30,pending],
            [1,GLOBAL+2,3],*[[1,MANAGER+i*0x4D0+0x13,i] for i in range(10)],
            [1,MANAGER+3*0x4D0+0x16,manager_slot],[4,0x0201BD58,0],[2,0x0201BD5C,0]]
    peek=[[2,obj+off] for off in (0x2C,0x2E,0x30)]
    f=fixture(0x8AA50,[(0x8AA50,0x8ACC6),(0x655B4,0x655F0)],regs={0:obj},memory=memory,peek=peek,bios=True)
    row=execute([f])[0]
    row['own_fields']={a-obj:v for a,w,v in row['peek']}
    return row


def select_and_advance(*,group,slot,flags,count,timer):
    # This fixture binds one two-slot sequence; invalid domains are refused.
    if group!=0 or slot not in (0,1) or not 0<=timer<=65535 or not 0<=count<=255:
        raise ValueError('bounded sequence domain')
    obj=POOL+127*60
    memory=[[4,obj,flags],[2,obj+0x14,group],[2,obj+0x16,slot],[2,obj+0x18,timer],
            [4,obj+0x20,0x08458558],[1,0x03000075,count]]
    boundary=0x629B0 if flags&0x8000 else 0x629B4
    select=fixture(0x6298C,[(0x6298C,boundary)],stop=BASE+boundary,regs={7:obj},memory=memory,
                   peek=[[4,SP]],budget=2000)
    first=execute([select])[0]
    sequence=values(first)[(SP,4)]
    memory.append([4,SP,sequence])
    advance=fixture(0x63238,[(0x63238,0x632F8),(0x62798,0x627AA)],stop=BASE+0x632F8,regs={7:obj},
                    memory=memory,peek=[[2,obj+off] for off in (0x14,0x16,0x18)]+[[4,obj]],budget=20000)
    row=execute([advance])[0]
    row.update(group=values(row)[(obj+0x14,2)],slot=values(row)[(obj+0x16,2)],
               timer=values(row)[(obj+0x18,2)],flags=values(row)[(obj,4)],
               lookup_before_freeze={BASE+a for a in (0x6298C,0x6298E,0x62994,0x62998)}.issubset({r['pc'] for r in first['reads']}),selection=first,sequence=sequence)
    return row


def lifecycle_chain(*,context=0):
    obj=POOL+127*60
    first=allocation_fixture(free=127,context=context)
    first['memory'] += [[1,GLOBAL+2,3],*[[1,MANAGER+i*0x4D0+0x13,i] for i in range(10)],
                        [1,MANAGER+3*0x4D0+0x16,3],[4,0x0201BD58,0],[2,0x0201BD5C,0]]
    own_peek=[[4,obj],*[[2,obj+off] for off in (0x14,0x16,0x18,0x2C,0x2E,0x30)]]
    dispatch=fixture(0x62940,[(0x62940,0x62958),(0x9C114,0x9C116),(0x8AA50,0x8ACC6),(0x655B4,0x655F0)],
                     stop=BASE+0x62958,regs={7:obj,2:127<<16},peek=own_peek,bios=True)
    disable=fixture(0x62788,[(0x62788,0x62798)],regs={0:obj},peek=own_peek)
    scan=fixture(0x627B0,[(0x627B0,0x6291A)],budget=500000,peek=[*own_peek,[1,0x03005BB8]])
    reallocate=allocation_fixture(free=127,context=context)
    reallocate['memory']=[]
    reallocate['peek']=own_peek
    rows=execute([first,dispatch,disable,scan,reallocate],persistent=True)
    if rows[0]['registers'][0]!=obj or rows[4]['registers'][0]!=obj:
        raise ValueError('chain handle reuse')
    binding=[r for r in rows[1]['reads'] if r.get('pc')==BASE+0x6294C]
    if binding!=[{'read':True,'pc':BASE+0x6294C,'width':4,'address':obj+0x28,'value':BASE+0x8AA51}]:
        raise ValueError('real allocated callback dispatch')
    if values(rows[2])[(obj,4)]!=0x22 or values(rows[3])[(obj,4)]!=0x20 or values(rows[3])[(0x03005BB8,1)]!=127:
        raise ValueError('disable/filter reserved lifecycle')
    # Inactive scan clears reserved bit; unrelated high flag 0x20 survives.
    for off in (0x2C,0x2E,0x30):
        if values(rows[1])[(obj+off,2)]!=values(rows[4])[(obj+off,2)]:
            raise ValueError('reallocation stale callback context')
    return rows


def callback_tail(*,meta2,meta3,meta12,handles=None):
    handles=list(handles) if handles is not None else [POOL+60*i for i in (127,126,125)]
    if len(handles)!=3 or any(not POOL<=a<POOL+128*60 or (a-POOL)%60 for a in handles):
        raise ValueError('explicit pool handle domain required')
    if any(not 0<=v<=255 for v in (meta2,meta3,meta12)):
        raise ValueError('metadata byte')
    descriptor=0x03007400
    memory=[[1,descriptor+2,meta2],[1,descriptor+3,meta3],[1,descriptor+0x12,meta12],
            [4,GLOBAL+0x2B0,handles[1]],[4,GLOBAL+0x2B4,handles[2]]]
    critical=[]
    peek=[]
    for address in sorted(set(handles)):
        memory += [[4,address,0xA5030001],[2,address+0x10,0],
                   [2,address+0x14,0x1234],[2,address+0x16,0x5678],[2,address+0x18,0x9ABC],
                   [4,address+0x28,0x0808AA51]]
        peek += [[4,address],[2,address+0x10],*[[2,address+off] for off in (0x14,0x16,0x18)],[4,address+0x28]]
        critical += [(address+0x14,2,0x1234),(address+0x16,2,0x5678),(address+0x18,2,0x9ABC),(address+0x28,4,0x0808AA51)]
    f=fixture(0x8AC26,[(0x8AC26,0x8ACB6)],stop=BASE+0x8ACB6,regs={2:handles[0],5:descriptor,7:GLOBAL},
              memory=memory,peek=peek)
    row=execute([f])[0]
    data=values(row)
    expected={a:0xA5030001 for a in set(handles)}
    tile={a:0 for a in set(handles)}
    if meta12:
        expected[handles[0]] &= 0xFFFDFFFF
    for index,meta,base in ((1,meta3,0x384),(2,meta2,0x398)):
        if meta:
            expected[handles[index]] &= 0xFFFDFFFF
            tile[handles[index]]=base+4*meta
        else:
            expected[handles[index]] |= 0x20000
    if any(data[(a,4)]!=v or data[(a+0x10,2)]!=tile[a] for a,v in expected.items()):
        raise ValueError('tail alias/order oracle')
    if any(data[(a,w)]!=v for a,w,v in critical):
        raise ValueError('tail critical-field mutation')
    row.update(tile10=[data[(a+0x10,2)] for a in handles],critical_unchanged=True,handles=handles)
    return row


def lookup_certificate(rom):
    # Exact finite leaf, raw words independently bound; tags influence only matches.
    expected=bytes.fromhex('30b50006030e00220c48c17c051c99420dd02c1c9a21c900501c0006020e092a05d8101c48430019c07c9842f4d19a20c0005043401930bc02bc0847a4a80002')
    if rom[0x655B4:0x655F4]!=expected:
        raise ValueError('fixed manager leaf raw contract changed')
    return {'root':0x655B4,'code_range':[0x655B4,0x655F0],'literal_range':[0x655F0,0x655F4],
            'return_indices':list(range(11)),'tag_reads_indices':list(range(10)),
            'base':MANAGER,'stride':0x4D0,'needle_width':8,'counter_initial':0,
            'counter_step':1,'counter_bound':9,'no_match_index':10,
            'counter_rank_bound':10,'ordinary_callee_has_no_nested_call':True,
            'return_pointer_domain_is_ewram':True,'natural_tag_or_handle_domain_proven':False}


def descriptor_heads(*,sequence,descriptor_table):
    # Conditional entry-to-head path only: body rendering is deliberately not executed.
    if any(type(a) is not int or a%4 or not 0<=a<len(ROM)-4 for a in (sequence,descriptor_table)):
        raise ValueError('aligned ROM pointer domain')
    index=int.from_bytes(ROM[sequence:sequence+2],'little',signed=True)
    if index<0 or descriptor_table+index*4+4>len(ROM):
        raise ValueError('sequence sentinel cannot bind descriptor')
    descriptor=int.from_bytes(ROM[descriptor_table+index*4:descriptor_table+index*4+4],'little')-BASE
    if not 0<=descriptor<len(ROM)-2 or descriptor%2:
        raise ValueError('descriptor ROM domain')
    heads=[]
    for n in range(17):
        at=descriptor+n*0x14
        if at+2>len(ROM):
            raise ValueError('descriptor ROM bound')
        heads.append(at)
        if ROM[at:at+2]==b'\xff\xff':
            break
    else:
        raise ValueError('descriptor finite entry bound')
    if len(heads)<2:
        raise ValueError('empty descriptor not supported by this binding path')
    obj=POOL+127*60
    bind=fixture(0x629E6,[(0x629E6,0x62A0A)],stop=BASE+0x62A0A,regs={7:obj},
                 memory=[[4,SP,BASE+sequence],[4,obj+0x1C,BASE+descriptor_table]])
    fixtures=[bind]
    for previous,current in zip(heads,heads[1:]):
        boundary=0x63220 if current==heads[-1] else 0x63208
        fixtures.append(fixture(0x631F6,[(0x631F6,0x63208)],stop=BASE+boundary,regs={8:BASE+previous}))
    rows=execute(fixtures)
    if rows[0]['registers'][8]!=BASE+descriptor:
        raise ValueError('actual descriptor binding')
    observed=[]
    for row in rows:
        pc=BASE+(0x629FC if row is rows[0] else 0x631FE)
        accesses=[r for r in row['reads'] if r['pc']==pc]
        if len(accesses)!=1 or accesses[0]['width']!=2:
            raise ValueError('head read width/cardinality')
        observed.append(accesses[0]['address']-BASE)
    if observed!=heads:
        raise ValueError('actual head walk')
    return {'sequence':sequence,'descriptor_table':descriptor_table,'heads':heads,'sentinel':heads[-1],
            'read_bytes':[a+i for a in heads for i in range(2)],'traces':rows,
            'body_rendering_executed':False,'natural_slot_domain_proven':False}
