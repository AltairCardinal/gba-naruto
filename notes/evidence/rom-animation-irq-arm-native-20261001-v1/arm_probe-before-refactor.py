"""Fixed copied callbacks executed through a pinned, bounded native ARM core."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd().resolve()
ROM = ROOT / 'rom/base.gba'
ROM_SHA = '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
COPIES = ((0x638, 0x03005CE8, 92), (0x690, 0x03005D50, 164))
STOP = 0x08000000


def code_ranges(root, relocated=False):
    start, end = {0x638: (0x638, 0x680), 0x690: (0x690, 0x714)}[root]
    base = dict((r, d-r) for r, d, _ in COPIES)[root] if relocated else 0x08000000
    return ((start+base, end+base),)


def raster_fixture(root, relocated, line, bank, active):
    if root not in (0x638, 0x690) or not 0 <= line <= 65535 or not 0 <= bank <= 255:
        raise ValueError('finite callback input')
    registers = [0x11110000+i*0x100 for i in range(15)]
    registers[13] = 0x03007000
    registers[14] = STOP
    memory = [[1, 0x03005CE6 if root == 0x638 else 0x03005D4E, bank]]
    data = 0x02000000+bank*1280+min(line,159)*8 if root == 0x638 else 0x02002740+bank*160+min(line,159)
    if root == 0x638:
        physical = 0x02000000 | ((data-0x02000000)&0x3FFFF)
        memory += [[4,physical,0x12345678],[4,physical+4,0x89ABCDEF]]
        expected = [[0x04000040,4,0x12345678],[0x04000044,4,0x89ABCDEF]]
    else:
        memory += [[1,data,int(active)],[2,0x0300004E,0x1234],[2,0x03000052,0x5678],[4,0x03005CCC,0x89ABCDEF]]
        expected = [[0x04000050,2,0x1234],[0x04000054,2,0x5678],[0x04000048,4,0x89ABCDEF]] if active else [[0x04000050,2,255],[0x04000054,2,16],[0x04000048,4,0x3F3F3F3F]]
    if line >= 160:
        expected = []
    ranges = code_ranges(root,relocated)
    return {'family':'raster','source_root':root,'relocated':bool(relocated),'line':line,'bank':bank,'active':bool(active),
            'root':ranges[0][0],'stop':STOP,'ranges':ranges,'budget':100,'registers':registers,
            'cpsr':0xDF,'spsr':0xDF,'memory':memory,'io':[[6,line]],
            'copies':[list(next(c for c in COPIES if c[0]==root))] if relocated else [],
            'peek':[[1,0x03000075]],'expected_writes':expected,'data_address':data}


def protocol(fixture):
    root, stop, ranges, budget = (fixture[k] for k in ('root','stop','ranges','budget'))
    if not 1 <= budget <= 2000 or not 1 <= len(ranges) <= 8 or not any(lo <= root < hi for lo,hi in ranges):
        raise ValueError('root/budget/ranges')
    if any(lo <= stop < hi or lo >= hi for lo,hi in ranges):
        raise ValueError('stop aliases source')
    lines = ['begin']
    for mode,sp,lr in fixture.get('banked',[]):
        if mode not in (0xDF,0xD2,0xD3) or not 0x03000000 <= sp <= 0x03008000:
            raise ValueError('banked fixture')
        lines += [f'cpsr {mode}',f'reg 13 {sp}',f'reg 14 {lr}']
    lines += [f"cpsr {fixture.get('cpsr',0xDF)}",f"spsr {fixture.get('spsr',0xDF)}"]
    for n,value in enumerate(fixture.get('registers',[])):
        if n > 14 or not 0 <= value <= 0xFFFFFFFF:
            raise ValueError('register fixture')
        lines.append(f'reg {n} {value}')
    for width,address,value in fixture.get('memory',[]):
        if width not in (1,2,4) or address%width or not ((0x02000000 <= address and address+width <= 0x02040000) or (0x03000000 <= address and address+width <= 0x03008000)) or not 0 <= value < 1 << (width*8):
            raise ValueError('RAM fixture')
        lines.append(f'mem {width} {address} {value}')
    for source,dest,size in fixture.get('copies',[]):
        lines.append(f'copy {source+0x08000000} {dest} {size}')
    for address,value in fixture.get('io',[]):
        lines.append(f'io {address} {value}')
    for width,address in fixture.get('peek',[]):
        lines.append(f'peek {width} {address}')
    lines.append(' '.join(map(str, ['run',root,stop,budget,len(ranges),*(v for pair in ranges for v in pair)])))
    return '\n'.join(lines)+'\n'


def execute(fixtures, *, raw=False):
    if hashlib.sha256(ROM.read_bytes()).hexdigest() != ROM_SHA:
        raise ValueError('ROM identity')
    completed = subprocess.run([str(HERE/'mgba-arm-probe'),str(ROM)],input=''.join(protocol(f) for f in fixtures),text=True,capture_output=True,timeout=90)
    if completed.returncode:
        raise ValueError(f'native failed {completed.returncode}: {completed.stderr}; {completed.stdout[-3000:]}')
    rows = [json.loads(line) for line in completed.stdout.splitlines()]
    snapshot = rows.pop(0)
    bios = bytes.fromhex(snapshot.pop('bios_hex'))
    reference = json.loads((HERE/'hle-bios-reference.json').read_text())
    if len(bios) != reference['size'] or hashlib.sha256(bios).hexdigest() != reference['sha256']:
        raise ValueError('embedded BIOS identity')
    if snapshot != {'snapshot_verified':True,'state_size':0x61000}:
        raise ValueError('native snapshot identity')
    if len(rows) != len(fixtures):
        raise ValueError('native case count')
    for fixture, row in zip(fixtures, rows, strict=True):
        if row['status'] != 1 or row['stop'] != fixture['stop']:
            raise ValueError('native stop')
        if 'expected_writes' in fixture:
            actual = [[w[2],w[1],w[3]] for w in row['writes'] if isinstance(w,list)]
            if actual != fixture['expected_writes'] or any(isinstance(w,dict) for w in row['writes']):
                raise ValueError(f'write mismatch {fixture}: {row}')
            if row['peek'] != [[0x03000075,1,0]]:
                raise ValueError('counter modified')
        row['verified'] = True
    return rows


def context_pair(slot, wait, *, variant=0):
    if slot not in range(1,7) or not 0 <= wait <= 255 or not 0 <= variant <= 1:
        raise ValueError('finite context slot/wait/variant')
    base = 0x03000A88
    record = base+slot*0x4C
    regs = [((0x11223300+i*0x10000) ^ (0xFEDCBA98 if variant else 0)) & 0xFFFFFFFF for i in range(15)]
    regs[0], regs[13], regs[14] = wait, 0x03007000, STOP|1
    before = [[1,record,slot+1],[4,record+8,0x08061CBC|1],[1,record+0x4C,8],
              [4,0x03000D18,record],[4,0x03002E20,0x03006000],[4,0x03002E1C,STOP]]
    peeks = [[4,record+off] for off in range(0,0x4C,4)]
    peeks += [[1,record+1],[4,0x03000D18],[1,0x03000A84]]
    save = {'family':'context-save','root':0x0809C574,'stop':STOP,
            'ranges':[[0x0809C574,0x0809C57C],[0x0800024C,0x080003BC]],'budget':2000,
            'registers':regs,'cpsr':0xFF,'spsr':0xA00000FF,'memory':before,'peek':peeks}
    row = execute([save],raw=True)[0]
    values = {a:v for a,w,v in row['peek'] if w==4 and record <= a < record+0x4C}
    state = {a-record:v for a,v in values.items()}
    expected = {4:regs[13],8:regs[14],0xC:0xA00000FF,0x10:regs[0],
                **{0x14+(r-1)*4:regs[r] for r in range(1,13)},0x44:regs[14],0x48:0x08000278}
    for off,value in expected.items():
        if state[off] != value:
            raise ValueError(f'save field {off:x}: {state[off]:x} != {value:x}')
    if next(v for a,w,v in row['peek'] if a==record+1 and w==1) != wait:
        raise ValueError('save wait marker')
    memory = []
    for index in range(8):
        memory += [[1,base+index*0x4C,index+1],[4,base+index*0x4C+8,0xFFFFFFFF]]
    memory += [[4,a,value] for a,value in values.items()]
    resume = {'family':'context-resume','root':0x0800024C,'stop':STOP,
              'ranges':[[0x0800024C,0x080003BC]],'budget':2000,'cpsr':0xDF,'spsr':0xDF,
              'registers':[0]*13+[0x03006000,STOP],'memory':memory,'peek':peeks}
    restored = execute([resume],raw=True)[0]
    selected = 0x080003A4 in restored['visited']
    final_wait = next(v for a,w,v in restored['peek'] if a==record+1 and w==1)
    if selected != (wait==1) or final_wait != (1 if wait==1 else (wait-1)&255):
        raise ValueError('wait/select oracle')
    if selected:
        expected_regs = regs[:]
        expected_regs[1],expected_regs[2] = regs[2],regs[1]
        # LR is the saved resume PC; r0 and r3..r12 and SP preserve raw values.
        if restored['registers'][:15] != expected_regs or restored['spsr'] != 0xA00000FF:
            raise ValueError('resume register oracle')
    row.update(record=state,original_registers=regs,input=save)
    restored.update(selected=selected,wait=final_wait,input=resume)
    return row,restored


def irq_case(root, line, bank, active, *, relocated_irq=True):
    fixture = raster_fixture(root,True,line,bank,active)
    raster_writes = fixture.pop('expected_writes')
    slot, pending = (0,1) if root==0x638 else (2,4)
    irq_root = 0x0300007C if relocated_irq else 0x08000104
    irq_delta = irq_root-0x104
    fixture.update(family='irq-dispatch',root=irq_root,cpsr=0xD2,spsr=0xDF,budget=2000,
                   ranges=[[irq_root,0x244+irq_delta],*fixture['ranges']],
                   banked=[[0xDF,0x03006000,STOP]])
    fixture['registers'][14] = STOP
    fixture['copies'].append([0x104,0x0300007C,512])
    fixture['memory'] += [[4,0x03000014+slot*4,code_ranges(root,True)[0][0]]]
    fixture['io'] += [[0x200,pending],[0x202,pending],[0x208,1]]
    row = execute([fixture],raw=True)[0]
    callback_ranges = code_ranges(root,True)
    row['callback_writes'] = [[w[2],w[1],w[3]] for w in row['writes'] if isinstance(w,list) and any(lo<=w[0]<hi for lo,hi in callback_ranges)]
    if row['callback_writes'] != raster_writes or row['registers'][13] != 0x03007000 or row['registers'][14] != STOP or row['cpsr']&255 != 0x92 or row['spsr'] != 0xDF:
        raise ValueError(f'IRQ dispatch oracle: {row}')
    if row['peek'] != [[0x03000075,1,0]]:
        raise ValueError('IRQ counter modified')
    row['input'] = fixture
    return row


def cpuset_case(source):
    _,dest,size = next(c for c in COPIES if c[0]==source)
    rom = ROM.read_bytes()
    values = [int.from_bytes(rom[a:a+4],'little') for a in range(source,source+size,4)]
    regs = [0]*15
    regs[0:3] = [0x08000000+source,dest,0x04000000 | (size//4)]
    regs[13:15] = [0x03007000,STOP|1]
    fixture = {'family':'cpuset-HLE','root':0x0809C0E0,'stop':STOP,'ranges':[[0x0809C0E0,0x0809C0E4],[0,0x4000]],
               'banked':[[0xD3,0x03007E00,0]],'budget':2000,'cpsr':0xFF,'spsr':0xFF,'registers':regs,
               'memory':[[4,dest-4,0xA55A5AA5],[4,dest+size,0x5AA5A55A]],
               'peek':[[4,dest-4],*[[4,dest+i*4] for i in range(size//4)], [4,dest+size],[1,0x03000075]]}
    row = execute([fixture],raw=True)[0]
    expected = [[dest-4,4,0xA55A5AA5],*[[dest+i*4,4,value] for i,value in enumerate(values)],
                [dest+size,4,0x5AA5A55A],[0x03000075,1,0]]
    writes = [w for w in row['writes'] if isinstance(w,dict) and dest <= w['multiple_base'] < dest+size]
    if row['peek'] != expected or len(writes) != size//4 or [w['multiple_base'] for w in writes] != list(range(dest,dest+size,4)) or any(w['mask']!=8 or w['direction']!=0 for w in writes):
        raise ValueError('CpuSet HLE byte/boundary/write oracle')
    row.update(copy_verified=True,copied_bytes=size,input=fixture)
    return row
