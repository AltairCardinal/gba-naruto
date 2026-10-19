"""Execute a bounded ARMv4T Thumb subset against raw advance/helper bytes.

This is an artificial state probe, not natural mGBA execution. No callback,
allocator, descriptor drawing, external object writer or full timer domain is
covered. Every unsupported opcode or memory access stops the probe.
"""
from __future__ import annotations

import struct

BASE = 0x08000000
OBJECT = 0x03001000
STACK = 0x03003000
COUNTER = 0x03000075
MASK = 0xFFFFFFFF


def signed(value, width=32):
    return value - (1 << width) if value & (1 << (width - 1)) else value


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
    reads, visited, writes = [], [], []

    def store(address, size, value):
        if not all(address + n in memory for n in range(size)):
            raise ValueError(f'write outside artificial RAM: {address:08x}')
        for n in range(size):
            memory[address + n] = (value >> (8 * n)) & 255
        writes.append({'at': pc, 'address': address, 'size': size, 'value': value & ((1 << (8 * size)) - 1)})

    def load(address, size):
        if BASE <= address < BASE + len(rom):
            offset = address - BASE
            if sequence <= offset < sequence + 16:
                if offset + size > sequence + 8:
                    raise ValueError('sequence read passed the frozen suffix boundary')
                reads.append([offset, size])
            elif offset not in (0x6327C, 0x63280, 0x632C4, 0x63338, 0x627AC):
                raise ValueError(f'unexpected literal: {offset:06x}')
            if offset + size > len(rom):
                raise ValueError('ROM read overflow')
            return int.from_bytes(rom[offset:offset + size], 'little')
        if not all(address + n in memory for n in range(size)):
            raise ValueError(f'read outside artificial RAM: {address:08x}')
        return sum(memory[address + n] << (8 * n) for n in range(size))

    pc = 0
    store(OBJECT, 4, flags)
    store(OBJECT + 0x18, 2, timer)
    store(STACK, 4, BASE + sequence)
    writes.clear()
    pc = 0x63238
    z = n = c = v = False

    def nz(value):
        nonlocal z, n
        z, n = value == 0, bool(value & 0x80000000)

    def compare(a, b):
        nonlocal c, v
        result = (a - b) & MASK
        nz(result)
        c = a >= b
        v = bool(((a ^ b) & (a ^ result)) & 0x80000000)

    for _ in range(20000):
        if pc == 0x632F8:
            return {'slot': load(OBJECT + 0x16, 2), 'group': load(OBJECT + 0x14, 2),
                    'timer': load(OBJECT + 0x18, 2), 'flags': load(OBJECT, 4),
                    'sequence_reads': reads, 'visited': visited, 'writes': writes,
                    'natural_execution': False, 'external_writers_covered': False}
        if not (0x63238 <= pc < 0x632F8 or 0x62798 <= pc < 0x627AA):
            raise ValueError(f'control escaped frozen windows: {pc:06x}')
        visited.append(pc)
        h = struct.unpack_from('<H', rom, pc)[0]
        next_pc = pc + 2
        group = h & 0xF800
        dst, src = h & 7, (h >> 3) & 7
        if group == 0x2000:
            dst = (h >> 8) & 7
            registers[dst] = h & 255
            nz(registers[dst])
        elif group == 0x2800:
            compare(registers[(h >> 8) & 7], h & 255)
        elif group == 0x3000:
            dst = (h >> 8) & 7
            registers[dst] = (registers[dst] + (h & 255)) & MASK
            nz(registers[dst])
        elif group == 0x1800 and not h & 0x200:
            operand = (h >> 6) & 7
            value = operand if h & 0x400 else registers[operand]
            registers[dst] = (registers[src] + value) & MASK
            nz(registers[dst])
        elif h & 0xE000 == 0 and group != 0x1800:
            shift, operation = (h >> 6) & 31, (h >> 11) & 3
            value = registers[src]
            if operation == 0:
                result = (value << shift) & MASK
            elif operation == 1:
                result = value >> (shift or 32)
            elif operation == 2:
                result = (signed(value) >> (shift or 32)) & MASK
            else:
                raise ValueError('unsupported shift')
            registers[dst] = result
            nz(result)
        elif h & 0xFC00 == 0x4000:
            operation = (h >> 6) & 15
            if operation == 0:
                registers[dst] &= registers[src]
            elif operation == 9:
                registers[dst] = (-registers[src]) & MASK
            elif operation == 10:
                compare(registers[dst], registers[src])
            elif operation == 12:
                registers[dst] |= registers[src]
            else:
                raise ValueError('unsupported ALU opcode')
            if operation != 10:
                nz(registers[dst])
        elif h & 0xFC00 == 0x4400:
            dst = (h & 7) | ((h >> 4) & 8)
            src = (h >> 3) & 15
            operation = (h >> 8) & 3
            if operation == 1:
                compare(registers[dst], registers[src])
            elif operation == 2 and dst < 13:
                registers[dst] = registers[src]
            elif operation == 3 and h & 0x80 == 0:
                if src != 14 or registers[14] != (BASE + 0x632D0 | 1):
                    raise ValueError('unexpected return')
                next_pc = (registers[src] & ~1) - BASE
            else:
                raise ValueError('unsupported high-register opcode')
        elif group == 0x4800:
            registers[(h >> 8) & 7] = load(BASE + ((pc + 4) & ~3) + 4 * (h & 255), 4)
        elif h & 0xF000 == 0x6000:
            address = registers[src] + 4 * ((h >> 6) & 31)
            if h & 0x800:
                registers[dst] = load(address, 4)
            else:
                store(address, 4, registers[dst])
        elif h & 0xF800 == 0x7800:
            registers[dst] = load(registers[src] + ((h >> 6) & 31), 1)
        elif h & 0xF000 == 0x8000:
            address = registers[src] + 2 * ((h >> 6) & 31)
            if h & 0x800:
                registers[dst] = load(address, 2)
            else:
                store(address, 2, registers[dst])
        elif h & 0xFE00 == 0x5E00:
            value = load(registers[src] + registers[(h >> 6) & 7], 2)
            registers[dst] = signed(value, 16) & MASK
        elif h & 0xF000 == 0x9000:
            address = registers[13] + 4 * (h & 255)
            reg = (h >> 8) & 7
            if h & 0x800:
                registers[reg] = load(address, 4)
            else:
                store(address, 4, registers[reg])
        elif h & 0xF000 == 0xD000:
            condition = (h >> 8) & 15
            conditions = {0: z, 1: not z, 8: c and not z, 10: n == v}
            if condition not in conditions:
                raise ValueError('unsupported conditional branch')
            if conditions[condition]:
                next_pc = pc + 4 + 2 * signed(h & 255, 8)
        elif group == 0xE000:
            next_pc = pc + 4 + 2 * signed(h & 2047, 11)
        elif group == 0xF000:
            second = struct.unpack_from('<H', rom, pc + 2)[0]
            if second & 0xF800 != 0xF800:
                raise ValueError('invalid BL suffix')
            delta = ((h & 2047) << 12) | ((second & 2047) << 1)
            next_pc = pc + 4 + signed(delta, 23)
            if next_pc != 0x62798:
                raise ValueError('unexpected callee')
            registers[14] = (BASE + pc + 4) | 1
        else:
            raise ValueError(f'unsupported opcode at {pc:06x}: {h:04x}')
        pc = next_pc
    raise ValueError('probe instruction budget exhausted')
