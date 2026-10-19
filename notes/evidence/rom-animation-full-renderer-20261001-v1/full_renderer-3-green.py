"""Actual complete renderer entry/return over allocated single-object artificial states."""
import importlib.util
from pathlib import Path

ROOT=Path.cwd().resolve()
PARENT=ROOT/'notes/evidence/rom-animation-object-native-20261001-v1'
spec=importlib.util.spec_from_file_location('frozen_object_native',PARENT/'object_native.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
TABLE_DOMAINS={(0x458474,0x45848C):2,(0x4584AC,0x4584B8):1,(0x4584D4,0x4584E0):1,
               (0x458510,0x45851C):1,(0x45854C,0x458558):1,(0x458574,0x458580):1,(0x45859C,0x4585A8):1}
WINDOWS=[(0x62924,0x63338),(0x627B0,0x6291A),(0x8AA50,0x8ACC6),(0x655B4,0x655F0),
         (0x9C114,0x9C116),(0x62798,0x627AA),(0x61A80,0x61ACA),(0x61ACC,0x61AE4),(0x635B8,0x63604)]


def frame(*,sequence_table,descriptor_table,group,flags,count,slot=0,x=0,y=0,callback=True):
    if (descriptor_table,sequence_table) not in TABLE_DOMAINS or group not in range(TABLE_DOMAINS.get((descriptor_table,sequence_table),0)) or slot!=0:
        raise ValueError('explicit table/group and initial non-sentinel slot required')
    if not 0<=count<=255 or not 0<=flags<=0xFFFFFFFF or not -32768<=x<=32767 or not -32768<=y<=32767:
        raise ValueError('artificial parameter domain')
    rom=native.ROM
    sequence=int.from_bytes(rom[sequence_table+4*group:sequence_table+4*group+4],'little')-native.BASE
    index=int.from_bytes(rom[sequence:sequence+2],'little',signed=True)
    if index<0:
        raise ValueError('initial sequence is sentinel')
    descriptor=int.from_bytes(rom[descriptor_table+4*index:descriptor_table+4*index+4],'little')-native.BASE
    obj=native.POOL+127*60
    first=native.allocation_fixture(free=127,context=1,flags=flags,group=group)
    # Reserve the other 127 entries without making them active; use genuine allocator.
    first['memory']=[[w,a,2 if w==4 and native.POOL<=a<native.POOL+127*60 and (a-native.POOL)%60==0 else v] for w,a,v in first['memory']]
    first['registers'][0:4]=[native.BASE+descriptor_table,native.BASE+sequence_table,group,x&0xFFFFFFFF]
    first['memory'] += [[4,native.SP,y&0xFFFFFFFF],[4,native.SP+4,0],[4,native.SP+8,0],
                        [4,native.SP+16,native.BASE+0x8AA51 if callback else 0],
                        [1,0x03000075,count],[1,native.GLOBAL+2,3],
                        *[[1,native.MANAGER+i*0x4D0+0x13,i] for i in range(10)],
                        [1,native.MANAGER+3*0x4D0+0x16,0]]
    run=native.fixture(0x62924,WINDOWS,budget=500000,bios=True,
                       peek=[[4,obj],*[[2,obj+off] for off in (0x14,0x16,0x18,0x2C,0x2E,0x30)],[1,0x03005BB8]])
    run['ranges'].append([native.BASE+0x9C0E4,native.BASE+0x9C0E8])
    allocation,row=native.execute([first,run],persistent=True)
    if allocation['registers'][0]!=obj or row['registers'][13]!=native.SP:
        raise ValueError('allocated object / complete frame stack return')
    data=native.values(row)
    row.update(group=data[(obj+0x14,2)],slot=data[(obj+0x16,2)],timer=data[(obj+0x18,2)],flags=data[(obj,4)],
               sequence=sequence,descriptor=descriptor,allocation=allocation)
    row['sequence_reads']=[[r['address']-native.BASE,r['width']] for r in row['reads'] if native.BASE+sequence<=r.get('address',0)<native.BASE+sequence+8]
    row['descriptor_reads']=[r for r in row['reads'] if native.BASE+descriptor<=r.get('address',0)<native.BASE+descriptor+0x200]
    return row
