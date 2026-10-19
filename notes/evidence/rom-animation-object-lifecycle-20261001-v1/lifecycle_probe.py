"""Artificial object lifecycle states, separate from natural runtime claims."""
import json
import struct
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from bounded_thumb import execute

POOL = 0x03003BB8
OTHER = 0x03003078
SP = 0x03007000
TABLE = 0x03007200
BASE = 0x08000000


def put(memory, address, size, value):
    for byte in range(size):
        if address + byte not in memory:
            raise ValueError('fixture write outside allocated RAM')
        memory[address + byte] = value >> (byte * 8) & 255


def get(memory, address, size):
    return sum(memory[address + byte] << (byte * 8) for byte in range(size))


def registers():
    result = [0xA0010000 + 0x100 * n + n for n in range(16)]
    result[13], result[14] = SP, 0x08000001
    return result


def state():
    ranges = [(POOL - 8, POOL + 128 * 60 + 8),
              (OTHER - 8, OTHER + 16 * 180 + 8), (SP - 64, SP + 32),
              (TABLE, TABLE + 64), (0x030059B8, 0x03005BB8 + 4),
              (0x03000075, 0x03000076), (0x030009E8, 0x030009EC),
              (0x03005E2D, 0x03005E2E), (0x03005E4A, 0x03005E4B)]
    return {address: (address * 37 + 19) & 255
            for start, end in ranges for address in range(start, end)}


def nodes_and_literals(rom, windows):
    source = json.loads((HERE / 'counter-inventory.json').read_text())
    nodes = set()
    for start, finish in source['source_ranges']:
        at = start
        while at < finish:
            h = struct.unpack_from('<H', rom, at)[0]
            size = 4 if h & 0xF800 == 0xF000 else 2
            if any(root <= at < end for root, end in windows):
                nodes.add(at)
            at += size
    literals = set()
    for at in nodes:
        h = struct.unpack_from('<H', rom, at)[0]
        if h & 0xF800 == 0x4800:
            word = ((at + 4) & ~3) + 4 * (h & 255)
            literals.update(range(word, word + 4))
    return nodes, literals


def run(rom, root, end, memory, seed=None, *, stops=(), budget=20000):
    nodes, literals = nodes_and_literals(rom, [(root, end)])
    regs = registers()
    for reg, value in (seed or {}).items():
        regs[reg] = value
    return execute(rom, root, nodes, regs, memory, literals, stops=stops, budget=budget)


def initialize(rom, memory):
    return run(rom, 0x62560, 0x6259C, memory)


def allocate(rom, memory, *, alternate=False, flags=0x10203040):
    memory = dict(memory)
    stack = [0x12345678, 0x1234789A, 0x12349ABC, flags, 0x0808AA51]
    for n, value in enumerate(stack):
        put(memory, SP + n * 4, 4, value)
    if alternate:
        for offset in (8, 16):
            put(memory, TABLE + offset, 4, 0x08458474)
            put(memory, TABLE + offset + 4, 4, 0x0845848C)
        put(memory, TABLE + 24, 4, 0x08458578)
        put(memory, TABLE + 28, 4, 0x08458474)
        return run(rom, 0x625A4, 0x626B0, memory,
                   {0: TABLE, 1: 0x12340001, 2: 0x12341234, 3: 0x12343456})
    return run(rom, 0x626B4, 0x62786, memory,
               {0: 0x08458474, 1: 0x0845848C, 2: 0x12341234, 3: 0x12343456})


def disable(rom, memory, address):
    return run(rom, 0x62788, 0x62798, memory, {0: address})


def filter_scan(rom, memory):
    return run(rom, 0x627B0, 0x62816, memory, stops=(0x62816,))


def restore_counter(rom, *, guard, saved, counter, argument, wait=197):
    memory = state()
    for address, size, value in [(0x030009E8, 4, guard), (0x03005E2D, 1, saved),
                                 (0x03000075, 1, counter), (0x03005E4A, 1, wait)]:
        put(memory, address, size, value)
    return run(rom, 0x857E4, 0x8584A, memory, {0: argument})
