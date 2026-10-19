"""Reuse the prior bounded CPU model for vector, clear and DMA configuration.

DMA effects are a separate explicit immediate-fill model; no emulator/hardware
launch or natural producer/entry claim is made by these artificial cases.
"""
from functools import lru_cache
import json
from pathlib import Path
import struct
import sys

ROOT = Path.cwd().resolve()
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'notes/evidence/rom-animation-object-lifecycle-20261001-v1'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BASE))
from bounded_thumb import execute
from tools.verify_rom_cfg_inventory import _decode

SP = 0x03007000


@lru_cache(maxsize=8)
def partition(rom, root, end, source):
    data = json.loads((ROOT / source).read_text())
    if source.endswith('/counter-inventory.json'):
        ranges = data['source_ranges']
    elif 'targets' in data:
        ranges = [bounds for target in data['targets'] for bounds in target['code_ranges']]
    else:
        ranges = data['code_ranges']
    nodes, literals = set(), set()
    for start, finish in ranges:
        if finish <= root or start >= end:
            continue
        at = start
        while at < finish:
            item = _decode(rom, at, 'thumb')
            if not item['accepted'] or at + item['size'] > finish:
                raise ValueError('source partition changed')
            if root <= at < end:
                nodes.add(at)
                h = struct.unpack_from('<H', rom, at)[0]
                if h & 0xF800 == 0x4800:
                    word = ((at+4)&~3) + 4*(h&255)
                    literals.update(range(word, word+4))
            at += item['size']
    return frozenset(nodes), frozenset(literals)


def put(memory, address, size, value):
    for byte in range(size):
        if address+byte not in memory:
            raise ValueError('fixture access escaped RAM')
        memory[address+byte] = value >> (8*byte) & 255


def get(memory, address, size):
    return sum(memory[address+byte] << (8*byte) for byte in range(size))


def state():
    ranges = [(0x03000000,0x03000400), (SP-64,SP+8), (0x04000200,0x04000204),
              (0x04000004,0x04000008), (0x040000D4,0x040000E0),
              (0x03005E28,0x03005E50)]
    return {at:0xA5 for a,b in ranges for at in range(a,b)}


def run(rom, root, end, memory, seed=None, *, source, stops=()):
    nodes, literals = partition(rom,root,end,source)
    registers = [0xA0010000+256*n+n for n in range(16)]
    registers[13],registers[14] = SP,0x08000001
    for reg,value in (seed or {}).items():
        registers[reg]=value
    return execute(rom,root,nodes,registers,memory,literals,stops=stops)


def vector(rom, index, *, value=0x12345678, remove=False, default_vector=False):
    memory=state()
    if default_vector:
        for slot in range(3):put(memory,0x03000000+4*slot,4,0x08061535)
    put(memory,0x04000200,2,0xFFFF)
    put(memory,0x04000004,2,0xFFFF)
    result=run(rom,0x62510 if remove else 0x624C0,0x62548 if remove else 0x62500,
               memory,{0:index,1:value},source='artifacts/rom-cfg-proven-roots-v14/rom-cfg-proven-roots-v14.json')
    result.update({'counter':get(result['memory'],0x03000075,1),
                   'irq_enable':get(result['memory'],0x04000200,2),
                   'display_status':get(result['memory'],0x04000004,2),
                   'natural_index_domain_proven':False})
    return result


def clear_saved(rom):
    result=run(rom,0x857B8,0x857D0,state(),source='notes/evidence/rom-animation-object-lifecycle-20261001-v1/counter-inventory.json')
    result.update({'saved':get(result['memory'],0x03005E2D,1),
                   'counter':get(result['memory'],0x03000075,1)})
    return result


def boot_dma(rom):
    result=run(rom,0x60FB8,0x60FE0,state(),source='artifacts/rom-boot-thumb-handoff-cfg-v1/rom-boot-thumb-handoff-cfg.json',stops=(0x60FE0,))
    words={}
    transfers=[]
    for write in result['writes']:
        assert write['size']==4
        words[write['address']]=write['value']
        if write['address']!=0x040000DC:
            continue
        command=write['value']
        control=(command>>16)&0xFFE0  # DMA3 masks five reserved low control bits.
        if control!=0x8500:
            raise ValueError('unsupported DMA mode; only immediate 32-bit fixed-source increment-destination fill')
        source=(words[0x040000D4]&0x0FFFFFFE)&~3
        destination=(words[0x040000D8]&0x0FFFFFFE)&~3
        count=(command&0xFFFF) or 0x10000
        value=words.get(source)
        if value!=0:
            raise ValueError('zero source word not established by CPU configuration trace')
        region=destination>>24
        if region not in (2,3):
            raise ValueError('DMA destination is outside modelled RAM')
        limit=0x02040000 if region==2 else 0x03008000
        end=destination+4*count
        if end>limit:
            raise ValueError('DMA range crosses modelled physical RAM boundary')
        transfers.append({'at':write['at'],'command':command,'masked_control':control,
                          'source':source,'source_word':value,'destination':destination,
                          'count_words':count,'range':[destination,end],
                          'effect_model':'conditional immediate DMA3 fixed zero source',
                          'external_writer_exclusion_proven':False})
    if len(transfers)!=2:
        raise ValueError('boot DMA trigger denominator changed')
    covered=any(t['range'][0]<=0x03000075 and 0x03005E2E<=t['range'][1] for t in transfers)
    return {'cpu_trace':result,'transfers':transfers,
            'counter_saved_and_pool_inside_iwram_zero_range':covered,
            'cpu_trace_executes_dma_effects':False,'natural_runtime_proven':False,
            'source_address_ram_domain_natural_proven':False,'hardware_verified':False}
