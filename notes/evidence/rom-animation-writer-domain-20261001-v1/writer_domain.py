"""Raw Thumb stores under fixed graph states, with physical IWRAM aliases.

Unknown addresses, unmodelled entry paths and hardware/BIOS effects remain open.
This classifier does not establish a global writer or natural lifetime domain.
"""
import struct

MASK = 0xFFFFFFFF
FIELDS = (('flags', 0, 4), ('group_slot_timer', 0x14, 0x1A),
          ('descriptor_sequence', 0x1C, 0x24), ('callback', 0x28, 0x2C))
TARGETS = (('counter_75', 0x75, 0x76), ('saved_5e2d', 0x5E2D, 0x5E2E))


def cover_range(rom, start, end, existing):
    from tools.verify_rom_cfg_inventory import _decode
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(rom) or (start | end) & 1:
        raise ValueError('invalid declared range')
    cursor, added, cross = start, set(), set()
    while cursor < end:
        candidate = cursor
        if cursor not in existing and cursor - 2 in existing:
            prior = _decode(rom, cursor-2, 'thumb')
            if prior['accepted'] and prior['size'] == 4:
                candidate = cursor - 2
        item = _decode(rom, candidate, 'thumb')
        if not item['accepted']:
            raise ValueError(f'declared range lacks complete source partition at {cursor:06x}')
        finish = candidate + item['size']
        if candidate in existing:
            if candidate < start or finish > end:
                cross.add(candidate)
        else:
            if candidate < start or finish > end:
                raise ValueError('uncovered partial instruction partition')
            added.add(candidate)
        cursor = finish
    return {'new_nodes': sorted(added), 'cross_boundary_existing_nodes': sorted(cross),
            'range_start_is_instruction': start in existing or start in added}


def root_set(decoded, declared):
    offsets = set(decoded)
    if not set(declared) <= offsets:
        raise ValueError('declared root lacks source membership')
    roots = set(declared)
    predecessors = {at: set() for at in offsets}
    for at, item in decoded.items():
        for edge in item['successors']:
            target = edge['file_offset']
            if target not in offsets:
                continue
            if edge['kind'] == 'call_target':
                roots.add(target)
            else:
                predecessors[target].add(at)
    roots |= {at for at, incoming in predecessors.items() if not incoming}
    reached, pending = set(), list(roots)
    while pending:
        at = pending.pop()
        if at in reached:
            continue
        reached.add(at)
        pending.extend(e['file_offset'] for e in decoded[at]['successors']
                       if e['kind'] != 'call_target' and e['file_offset'] in offsets)
    disconnected = offsets - reached
    roots |= disconnected
    return {'roots': sorted(roots), 'disconnected_unproven_nodes': sorted(disconnected)}


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
