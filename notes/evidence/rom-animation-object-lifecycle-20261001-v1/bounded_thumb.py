"""Bounded raw Thumb executor extracted from the prior advance probe.

Only the explicitly supplied instruction members, literal/data reads, RAM bytes,
callees and stop addresses are allowed. This is not a general GBA emulator.
"""
import struct

BASE = 0x08000000
MASK = 0xFFFFFFFF


def signed(value, width=32):
    return value - (1 << width) if value & (1 << (width - 1)) else value


def execute(rom, root, nodes, registers, memory, rom_bytes, *,
            stops=(), callees=(), return_address=0x08000001, budget=20000):
    if (return_address & ~1) - BASE in nodes or (return_address & ~1) - BASE == root:
        raise ValueError('return sentinel overlaps frozen source or root')
    registers, memory = list(registers), dict(memory)
    reads, writes, visited = [], [], []
    pc = root
    z = n = c = v = False

    def store(address, size, value):
        if address & (size - 1):
            raise ValueError('unaligned artificial RAM write')
        if not all(address + byte in memory for byte in range(size)):
            raise ValueError(f'write outside artificial RAM: {address:08x}')
        value &= (1 << (size * 8)) - 1
        for byte in range(size):
            memory[address + byte] = value >> (byte * 8) & 255
        writes.append({'at': pc, 'address': address, 'size': size, 'value': value})

    def load(address, size):
        if address & (size - 1):
            raise ValueError('unaligned artificial read')
        if BASE <= address < BASE + len(rom):
            offset = address - BASE
            if not all(offset + byte in rom_bytes for byte in range(size)):
                raise ValueError(f'unapproved ROM read: {offset:06x}')
            value = int.from_bytes(rom[offset:offset + size], 'little')
        else:
            if not all(address + byte in memory for byte in range(size)):
                raise ValueError(f'read outside artificial RAM: {address:08x}')
            value = sum(memory[address + byte] << (byte * 8) for byte in range(size))
        reads.append({'at': pc, 'address': address, 'size': size, 'value': value})
        return value

    def nz(value):
        nonlocal z, n
        z, n = value == 0, bool(value & 0x80000000)

    def arithmetic(a, b, subtract=False):
        nonlocal c, v
        value = (a - b if subtract else a + b) & MASK
        c = a >= b if subtract else a + b > MASK
        v = bool(((a ^ b) if subtract else ~(a ^ b)) & (a ^ value) & 0x80000000)
        nz(value)
        return value

    def branch_register(value):
        if not value & 1:
            raise ValueError('unsupported ARM interwork')
        return (value & ~1) - BASE

    def report(ordinary_return):
        return {'memory': memory, 'registers': registers, 'reads': reads,
                'writes': writes, 'visited': visited, 'stop': pc,
                'ordinary_return': ordinary_return, 'natural_execution': False}

    for _ in range(budget):
        if pc == (return_address & ~1) - BASE:
            return report(True)
        if pc in stops:
            return report(False)
        if pc not in nodes or pc + 2 > len(rom):
            raise ValueError(f'control outside frozen source: {pc:06x}')
        visited.append(pc)
        h = struct.unpack_from('<H', rom, pc)[0]
        next_pc = pc + 2
        group = h & 0xF800
        dst, src = h & 7, (h >> 3) & 7
        if group == 0x2000:
            dst = h >> 8 & 7
            registers[dst] = h & 255
            nz(registers[dst])
        elif group == 0x2800:
            arithmetic(registers[h >> 8 & 7], h & 255, True)
        elif group in (0x3000, 0x3800):
            dst = h >> 8 & 7
            registers[dst] = arithmetic(registers[dst], h & 255, group == 0x3800)
        elif group == 0x1800:
            operand = h >> 6 & 7
            value = operand if h & 0x400 else registers[operand]
            registers[dst] = arithmetic(registers[src], value, bool(h & 0x200))
        elif h & 0xE000 == 0:
            shift, operation = h >> 6 & 31, h >> 11 & 3
            value = registers[src]
            if operation == 0:
                if shift:
                    c = bool(value & (1 << (32 - shift)))
                result = value << shift & MASK
            elif operation == 1:
                shift = shift or 32
                c = bool(value & (1 << (shift - 1)))
                result = value >> shift
            elif operation == 2:
                shift = shift or 32
                c = bool(value & (1 << (shift - 1)))
                result = signed(value) >> shift & MASK
            else:
                raise ValueError('unsupported shift')
            registers[dst] = result
            nz(result)
        elif h & 0xFC00 == 0x4000:
            operation = h >> 6 & 15
            if operation == 0:
                registers[dst] &= registers[src]
            elif operation == 9:
                registers[dst] = arithmetic(0, registers[src], True)
            elif operation == 10:
                arithmetic(registers[dst], registers[src], True)
            elif operation == 12:
                registers[dst] |= registers[src]
            elif operation == 13:
                registers[dst] = registers[dst] * registers[src] & MASK
            else:
                raise ValueError('unsupported ALU opcode')
            if operation != 10:
                nz(registers[dst])
        elif h & 0xFC00 == 0x4400:
            dst, src = (h & 7) | (h >> 4 & 8), h >> 3 & 15
            operation = h >> 8 & 3
            if operation == 0 and dst != 15 and src != 15:
                registers[dst] = registers[dst] + registers[src] & MASK
            elif operation == 1 and dst != 15 and src != 15:
                arithmetic(registers[dst], registers[src], True)
            elif operation == 2 and dst != 15 and src != 15:
                registers[dst] = registers[src]
            elif operation == 3 and not h & 0x80 and src != 15:
                next_pc = branch_register(registers[src])
            else:
                raise ValueError('unsupported high-register opcode')
        elif group == 0x4800:
            registers[h >> 8 & 7] = load(BASE + ((pc + 4) & ~3) + 4 * (h & 255), 4)
        elif h & 0xF000 in (0x6000, 0x7000, 0x8000):
            size = {0x6000: 4, 0x7000: 1, 0x8000: 2}[h & 0xF000]
            address = registers[src] + size * (h >> 6 & 31) & MASK
            if h & 0x800:
                registers[dst] = load(address, size)
            else:
                store(address, size, registers[dst])
        elif h & 0xFE00 == 0x5E00:
            value = load(registers[src] + registers[h >> 6 & 7] & MASK, 2)
            registers[dst] = signed(value, 16) & MASK
        elif h & 0xF000 == 0x9000:
            address = registers[13] + 4 * (h & 255) & MASK
            reg = h >> 8 & 7
            if h & 0x800:
                registers[reg] = load(address, 4)
            else:
                store(address, 4, registers[reg])
        elif h & 0xFF00 == 0xB000:
            delta = 4 * (h & 127)
            registers[13] = registers[13] + (-delta if h & 128 else delta) & MASK
        elif h & 0xF600 == 0xB400:
            selected = [reg for reg in range(8) if h & (1 << reg)]
            if h & 0x100:
                selected.append(15 if h & 0x800 else 14)
            if not selected:
                raise ValueError('unsupported empty stack multiple')
            if h & 0x800:
                address = registers[13]
                for reg in selected:
                    value = load(address, 4)
                    if reg == 15:
                        next_pc = branch_register(value)
                    else:
                        registers[reg] = value
                    address += 4
                registers[13] = address & MASK
            else:
                address = registers[13] - 4 * len(selected) & MASK
                registers[13] = address
                for reg in selected:
                    store(address, 4, registers[reg])
                    address += 4
        elif h & 0xF000 == 0xD000:
            condition = h >> 8 & 15
            conditions = {0: z, 1: not z, 2: c, 3: not c, 4: n, 5: not n,
                          6: v, 7: not v, 8: c and not z, 9: not c or z,
                          10: n == v, 11: n != v, 12: not z and n == v,
                          13: z or n != v}
            if condition not in conditions:
                raise ValueError('unsupported conditional branch or SVC')
            if conditions[condition]:
                next_pc = pc + 4 + 2 * signed(h & 255, 8)
        elif group == 0xE000:
            next_pc = pc + 4 + 2 * signed(h & 2047, 11)
        elif group == 0xF000:
            second = struct.unpack_from('<H', rom, pc + 2)[0]
            if second & 0xF800 != 0xF800:
                raise ValueError('invalid BL suffix')
            delta = (h & 2047) << 12 | (second & 2047) << 1
            next_pc = pc + 4 + signed(delta, 23)
            if next_pc not in callees:
                raise ValueError(f'unexpected callee: {next_pc:06x}')
            registers[14] = BASE + pc + 4 | 1
        else:
            raise ValueError(f'unsupported opcode at {pc:06x}: {h:04x}')
        pc = next_pc
    raise ValueError('probe instruction budget exhausted')
