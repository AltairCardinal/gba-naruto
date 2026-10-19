"""Bounded raw source and real-callee save probes; natural resume stays open."""
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
import sys

ROOT = Path.cwd().resolve()
BASE = ROOT / 'notes/evidence/rom-animation-object-lifecycle-20261001-v1'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BASE))
from bounded_thumb import execute
from tools.verify_rom_cfg_inventory import _decode, _raw_control_flow
from tools.thumb_branch import decode_thumb_bl

SP = 0x03007000
POOL = 0x03003BB8
COUNTER = 0x03000075
SAVED = 0x03005E2D
WINDOWS = ((0x8584C, 0x859B0), (0x64A48, 0x64A5C), (0x857E4, 0x8584A),
           (0x61E00, 0x61E1C), (0x857B8, 0x857D0))


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits-1)) else value


@lru_cache(maxsize=16)
def closure(rom, root, end):
    if not 0 <= root < end <= len(rom) or (root | end) & 1:
        raise ValueError('invalid source bounds')
    pending, nodes, calls, literals, frontiers = [root], {}, [], set(), []
    occupied = set()
    while pending:
        at = pending.pop()
        if at in nodes:
            continue
        if at < root or at >= end:
            raise ValueError('control flow escapes source boundary')
        item = _decode(rom, at, 'thumb')
        if not item['accepted'] or at + item['size'] > end:
            raise ValueError('unsupported or partial source instruction')
        span = set(range(at, at+item['size']))
        if occupied & span:
            raise ValueError('source instruction partition overlap')
        occupied.update(span)
        nodes[at] = item
        h = struct.unpack_from('<H', rom, at)[0]
        if h & 0xF800 == 0x4800:
            word = ((at+4)&~3) + 4*(h&255)
            if word+4 > len(rom):
                raise ValueError('literal access escapes ROM')
            literals.add(word)
        flow = _raw_control_flow('thumb', rom[at:at+item['size']], at)
        if item['flow_kind'] == 'call':
            calls.append({'at': at, 'target': flow['target_file_offset']})
        if item['flow_kind'] in ('conditional_branch', 'unconditional_branch'):
            if not root <= flow['target_file_offset'] < end:
                raise ValueError('direct branch escapes source boundary')
        if item['flow_kind'] in ('linear', 'conditional_branch', 'call') and at+item['size'] >= end:
            raise ValueError('fallthrough escapes source boundary')
        for edge in item['successors']:
            if edge['mode'] != 'thumb':
                raise ValueError('source mode switch remains outside bounded contract')
            if edge['kind'] != 'call_target':
                pending.append(edge['file_offset'])
        if not item['successors']:
            frontiers.append({'at': at, 'flow_kind': item['flow_kind']})
        if len(nodes) > 512:
            raise ValueError('source worklist budget exceeded')
    return {'root': root, 'end': end, 'nodes': sorted(nodes),
            'calls': sorted(calls, key=lambda x:x['at']), 'literal_words': sorted(literals),
            'frontiers': sorted(frontiers, key=lambda x:x['at'])}


def raw_closure(rom, root, end):
    pending, nodes, occupied = [root], set(), set()
    while pending:
        at = pending.pop()
        if at in nodes:
            continue
        if at < root or at+2 > end or at & 1:
            raise ValueError('raw control flow escapes bounds')
        h = struct.unpack_from('<H', rom, at)[0]
        size = 4 if h & 0xF800 == 0xF000 else 2
        if at+size > end or occupied & set(range(at, at+size)):
            raise ValueError('raw partition mismatch')
        occupied.update(range(at, at+size));nodes.add(at)
        if size == 4:
            second = struct.unpack_from('<H', rom, at+2)[0]
            if second & 0xF800 != 0xF800:
                raise ValueError('raw BL suffix mismatch')
            pending.append(at+4)
        elif h & 0xFF00 == 0x4700 or h & 0xFF00 == 0xBD00:
            continue
        elif h & 0xF800 == 0xE000:
            pending.append(at+4+signed(h&2047,11)*2)
        elif h & 0xF000 == 0xD000:
            if (h >> 8 & 15) >= 14:
                raise ValueError('raw SVC/undefined remains outside source contract')
            pending.extend((at+2,at+4+signed(h&255,8)*2))
        elif h & 0xFC00 == 0x4400 and ((h&7)|((h>>4)&8)) == 15:
            raise ValueError('raw high-PC operation unsupported')
        else:
            pending.append(at+2)
        if len(nodes)>512:
            raise ValueError('raw worklist budget exceeded')
    return sorted(nodes)


def partition(rom, windows):
    nodes, words = set(), set()
    for a,b in windows:
        graph = closure(rom,a,b)
        if raw_closure(rom,a,b) != graph['nodes']:
            raise ValueError('independent raw control flow disagrees')
        nodes.update(graph['nodes']);words.update(graph['literal_words'])
    return nodes,{byte for word in words for byte in range(word,word+4)}


def put(memory, address, size, value):
    for byte in range(size):
        if address+byte not in memory:
            raise ValueError('fixture RAM boundary exceeded')
        memory[address+byte] = value >> (8*byte) & 255


def get(memory, address, size):
    return sum(memory[address+n] << (8*n) for n in range(size))


def registers():
    regs = [0xA0010000+256*n+n for n in range(16)]
    regs[13], regs[14] = SP,0x08000001
    return regs


def state():
    return {at: (at*37+19)&255 for at in range(0x03000000,0x03008000)}


def binding(rom):
    expected = 'a95b7b4ebd38bd2422bad8c1ac40a932dae4f2173577b466152c8e1f0410660d'
    if hashlib.sha256(rom[0x61D7C:0x61DEA]).hexdigest() != expected:
        raise ValueError('registrar source identity changed')
    h, slot, first, second = struct.unpack_from('<HHHH',rom,0x85A04)
    if h != 0x4903 or slot != 0x2005 or decode_thumb_bl(0x85A08,first,second) != 0x61D7C:
        raise ValueError('literal registration producer changed')
    callback = struct.unpack_from('<I',rom,0x85A14)[0]
    if callback != 0x0808584D:
        raise ValueError('callback literal changed')
    nodes, literals = partition(rom,((0x61D7C,0x61D8C),(0x61D8C,0x61DEA)))
    literals.update(range(0x53D604,0x53D608))
    regs = registers();regs[0],regs[1] = 5,callback
    trace = execute(rom,0x61D7C,nodes,regs,state(),literals,callees=(0x61D8C,))
    memory = trace['memory'];address=0x03000CE8+4*(5-1)
    return {'producer':0x85A08,'literal':0x85A14,'slot':5,'callback':get(memory,address,4),
            'callback_address':address,'argument':get(memory,0x03000D00+16,4),
            'record_entry':get(memory,0x03000A88+5*0x4C+8,4),
            'trace':trace,'natural_execution_proven':False,'context_resume_proven':False}


def save(rom, *, counter, saved, guard, wait, busy=0, allow_stop=True, flag_words=None):
    memory = state()
    for address,size,value in ((COUNTER,1,counter),(SAVED,1,saved),(0x030009E8,4,guard),
                               (0x03005E4A,1,wait),(0x03005D44,1,busy)):
        put(memory,address,size,value)
    before = list(flag_words) if flag_words is not None else [0xA5000000|(slot&3) for slot in range(128)]
    if len(before) != 128 or any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF for v in before):
        raise ValueError('exact 128 word flag domain required')
    for slot,value in enumerate(before):
        put(memory,POOL+60*slot,4,value)
    nodes,literals = partition(rom,WINDOWS)
    trace = execute(rom,0x8584C,nodes,registers(),memory,literals,
                    callees=(0x64A48,0x857E4,0x61E00,0x857B8),
                    stops=(0x85988,0x858E4) if allow_stop else ())
    call_targets = {call['at']:call['target'] for a,b in WINDOWS for call in closure(rom,a,b)['calls']}
    trace.update({'counter':get(trace['memory'],COUNTER,1),'saved':get(trace['memory'],SAVED,1),
                  'callee_targets':[call_targets[at] for at in trace['visited'] if at in call_targets],
                  'pool_flags':[{'slot':slot,'before':value,'after':get(trace['memory'],POOL+60*slot,4)}
                                for slot,value in enumerate(before)],
                  'task_marker_stores':sum(0x03000A88<=w['address']<0x03000A88+8*0x4C and w['value']==0xFFFFFFFF
                                           for w in trace['writes']),
                  'natural_execution_proven':False,'context_resume_proven':False})
    return trace


def postbattle(rom, *, counter):
    nodes,literals=partition(rom,((0x68DE4,0x68DF8),))
    memory=state();put(memory,COUNTER,1,counter)
    trace=execute(rom,0x68DE4,nodes,registers(),memory,literals,stops=(0x68DEC,))
    trace.update({'counter':get(trace['memory'],COUNTER,1),'producer_entry_proven':False,
                  'natural_execution_proven':False})
    return trace
