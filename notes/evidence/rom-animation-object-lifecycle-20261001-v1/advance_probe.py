"""Prior artificial advance API, now using the shared bounded Thumb executor."""
from bounded_thumb import execute
from lifecycle_probe import nodes_and_literals, put, get

BASE = 0x08000000
OBJECT = 0x03001000
STACK = 0x03003000
COUNTER = 0x03000075
MASK = 0xFFFFFFFF


def probe(rom, sequence, *, flags, count, timer=0):
    if (any(type(x) is not int for x in (sequence, flags, count, timer))
            or not 0 <= flags <= MASK or not 0 <= count <= 255
            or not 0 <= timer <= 65535 or not 0 <= sequence <= len(rom) - 8):
        raise ValueError('invalid artificial state')
    registers = [0] * 16
    registers[7], registers[13] = OBJECT, STACK
    memory = {OBJECT + n: 0 for n in range(0x3C)}
    memory.update({STACK + n: 0 for n in range(4)})
    memory[COUNTER] = count
    put(memory, OBJECT, 4, flags)
    put(memory, OBJECT + 0x18, 2, timer)
    put(memory, STACK, 4, BASE + sequence)
    nodes, literals = nodes_and_literals(rom, [(0x63238, 0x632F8), (0x62798, 0x627AA)])
    literals.update(range(sequence, sequence + 8))
    result = execute(rom, 0x63238, nodes, registers, memory, literals,
                     stops=(0x632F8,), callees=(0x62798,))
    memory = result['memory']
    return {'slot': get(memory, OBJECT + 0x16, 2), 'group': get(memory, OBJECT + 0x14, 2),
            'timer': get(memory, OBJECT + 0x18, 2), 'flags': get(memory, OBJECT, 4),
            'sequence_reads': [[r['address'] - BASE, r['size']] for r in result['reads']
                               if BASE + sequence <= r['address'] < BASE + sequence + 8],
            'visited': result['visited'], 'writes': result['writes'],
            'natural_execution': False, 'external_writers_covered': False}
