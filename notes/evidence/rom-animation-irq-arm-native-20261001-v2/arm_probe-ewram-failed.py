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
        memory += [[4,data,0x12345678],[4,data+4,0x89ABCDEF]]
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
    lines = ['begin',f"cpsr {fixture.get('cpsr',0xDF)}",f"spsr {fixture.get('spsr',0xDF)}"]
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
    if rows.pop(0) != {'snapshot_verified':True,'state_size':0x61000}:
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
