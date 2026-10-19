"""Raw Thumb stores under fixed graph states, with physical IWRAM aliases.

Unknown addresses, unmodelled entry paths and hardware/BIOS effects remain open.
This classifier does not establish a global writer or natural lifetime domain.
"""
import struct

MASK = 0xFFFFFFFF
FIELDS = (('flags', 0, 4), ('group_slot_timer', 0x14, 0x1A),
          ('descriptor_sequence', 0x1C, 0x24), ('callback', 0x28, 0x2C))
TARGETS = (('counter_75', 0x75, 0x76), ('saved_5e2d', 0x5E2D, 0x5E2E))


def plus(base, delta):
    return (base + delta) & MASK if type(base) is int and type(delta) is int else None


def classify(at, raw_hex, kind, register, width, address, value, reachable):
    aligned = address & ~(width - 1) if address is not None else None
    physical = [(aligned + n) & 0x7FFF for n in range(width)
                if 0x03000000 <= aligned + n < 0x04000000] if aligned is not None else None
    overlaps = []
    pool_fields = []
    if physical is not None:
        for name, start, end in TARGETS:
            if any(start <= byte < end for byte in physical):
                overlaps.append(name)
        for slot in range(128):
            for name, start, end in FIELDS:
                if any(0x3BB8 + 60*slot + start <= byte < 0x3BB8 + 60*slot + end for byte in physical):
                    pool_fields.append({'slot': slot, 'field': name, 'range': [start, end]})
        if pool_fields:
            overlaps.append('pool_critical_fields')
    dma = aligned is not None and aligned < 0x040000E0 and 0x040000B0 < aligned + width
    return {'at': at, 'raw_hex': raw_hex, 'kind': kind, 'register': register, 'width': width,
            'effective_address': address, 'aligned_address': aligned,
            'iwram_bytes': physical, 'value': value & ((1 << (width*8))-1) if type(value) is int else None,
            'address_unknown': address is None, 'reachable_in_model': reachable,
            'overlaps': overlaps, 'pool_fields': pool_fields,
            'may_alias_targets': address is None or bool(overlaps),
            'dma_control_or_address_write': dma, 'global_writer_exhaustiveness_proven': False,
            'scope': 'direct physical bytes only; IRQ/BIOS/DMA/context/unknown entries remain open'}


def stores(rom, offsets, states):
    offsets = set(offsets)
    occupied = set()
    for at in sorted(offsets):
        if type(at) is not int or at < 0 or at + 2 > len(rom):
            raise ValueError('instruction bounds invalid')
        h = struct.unpack_from('<H', rom, at)[0]
        size = 4 if h & 0xF800 == 0xF000 else 2
        if at + size > len(rom):
            raise ValueError('instruction bounds invalid')
        if size == 4 and struct.unpack_from('<H', rom, at+2)[0] & 0xF800 != 0xF800:
            raise ValueError('invalid BL partition')
        if occupied & set(range(at, at+size)):
            raise ValueError('instruction partition overlap')
        occupied.update(range(at, at+size))
    result = []
    for at in sorted(offsets):
        h = struct.unpack_from('<H', rom, at)[0]
        regs = states.get(at, {}).get('registers', {})
        register, base = h & 7, h >> 3 & 7
        events = []
        if h & 0xF800 in (0x6000, 0x7000, 0x8000):
            width = {0x6000: 4, 0x7000: 1, 0x8000: 2}[h & 0xF800]
            events.append((register, width, plus(regs.get(base), width*(h >> 6 & 31)), 'str_immediate'))
        elif h & 0xFE00 in (0x5000, 0x5200, 0x5400):
            width = {0x5000: 4, 0x5200: 2, 0x5400: 1}[h & 0xFE00]
            events.append((register, width, plus(regs.get(base), regs.get(h >> 6 & 7)), 'str_register'))
        elif h & 0xF800 == 0x9000:
            register = h >> 8 & 7
            events.append((register, 4, plus(regs.get(13), 4*(h & 255)), 'str_sp_relative'))
        elif h & 0xF800 == 0xC000 or h & 0xFE00 == 0xB400:
            selected = [r for r in range(8) if h & (1 << r)]
            push = h & 0xFE00 == 0xB400
            if push and h & 0x100:
                selected.append(14)
            if not selected:
                raise ValueError('empty multiple store is unsupported')
            address = plus(regs.get(13), -4*len(selected)) if push else regs.get(h >> 8 & 7)
            for n, register in enumerate(selected):
                events.append((register, 4, plus(address, 4*n), 'push' if push else 'stmia'))
        for register, width, address, kind in events:
            result.append(classify(at, rom[at:at+2].hex(), kind, register, width,
                                   address, regs.get(register), at in states))
    return result
