"""Backward dependency planning, not a complete value-domain proof."""
from collections import deque
import json
import struct

from flow import allocator_contract, local
from tools.verify_rom_cfg_inventory import _decode


def compile_graph(rom, offsets, roots):
    decoded = {at: _decode(rom, at, 'thumb') for at in sorted(offsets)}
    if not roots <= offsets or any(not i['accepted'] for i in decoded.values()):
        raise ValueError('invalid source graph')
    predecessors = {at: set() for at in offsets}
    for at, i in decoded.items():
        for edge in i['successors']:
            if edge['kind'] != 'call_target' and edge['file_offset'] in offsets:
                predecessors[edge['file_offset']].add(at)
    return {'decoded': decoded, 'predecessors': predecessors,
            'rom_sha256': local.sha(rom), 'offsets': offsets, 'roots': roots}


def dependencies(rom, offsets, roots, site, field, *, budget=5000, context=None):
    if field % 4 or field < 0 or site not in offsets or budget < 1:
        raise ValueError('invalid dependency input')
    graph = context if context is not None else compile_graph(rom, offsets, roots)
    if graph['rom_sha256'] != local.sha(rom) or graph['offsets'] != offsets or graph['roots'] != roots:
        raise ValueError('cached graph identity mismatch')
    allocator_contract(rom)
    decoded, predecessors = graph['decoded'], graph['predecessors']
    if decoded[site]['flow_kind'] != 'call':
        raise ValueError('sink is not a call instruction')
    pending = deque((at, 'stack', field) for at in sorted(predecessors[site]))
    seen, found = set(), {}

    def emit(row):
        found[json.dumps(row, sort_keys=True)] = row

    def before(at, kind, needed):
        if at in roots or not predecessors[at]:
            emit({'kind': 'unproved_entry_value', 'at': at, 'value_kind': kind, 'index': needed})
        for source in sorted(predecessors[at]):
            pending.append((source, kind, needed))

    while pending:
        at, kind, needed = pending.popleft()
        key = at, kind, needed
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > budget:
            raise ValueError('dependency planning budget exhausted')
        i = decoded[at]
        h = struct.unpack_from('<H', rom, at)[0]
        group = h & 0xF800
        if i['flow_kind'] == 'call':
            target = next(e['file_offset'] for e in i['successors'] if e['kind'] == 'call_target')
            if kind == 'register' and target == 0x626B4 and 4 <= needed <= 11:
                before(at, kind, needed)
            else:
                emit({'kind': 'unproved_callee_stack_effect' if kind == 'stack' else 'unproved_callee_register_effect',
                      'at': at, 'target': target, 'value_kind': kind, 'index': needed})
            continue
        instruction = next(local.ENGINE.disasm(rom[at:at + i['size']], at, count=1))
        writes = [instruction.reg_name(r) for r in instruction.regs_access()[1]]
        if kind == 'stack':
            if group == 0x9000 and 4 * (h & 255) == needed:
                before(at, 'register', (h >> 8) & 7)
            elif (instruction.mnemonic.startswith('str') or instruction.mnemonic in ('stm', 'stmia')) and group != 0x9000:
                emit({'kind': 'possible_stack_alias_store', 'at': at, 'offset': needed,
                      'raw_hex': rom[at:at + i['size']].hex()})
            elif 'sp' in writes:
                emit({'kind': 'stack_frame_boundary', 'at': at, 'offset': needed})
            else:
                before(at, kind, needed)
            continue
        register_name = {9: 'sb', 10: 'sl', 11: 'fp', 12: 'ip', 14: 'lr'}.get(needed, f'r{needed}')
        if register_name not in writes:
            before(at, kind, needed)
        elif group == 0x2000 and (h >> 8) & 7 == needed:
            emit({'kind': 'constant_producer', 'at': at, 'register': needed, 'value': h & 255})
        elif group == 0x4800 and (h >> 8) & 7 == needed:
            word = ((at + 4) & ~3) + 4 * (h & 255)
            emit({'kind': 'literal_producer', 'at': at, 'register': needed, 'literal_word': word,
                  'value': struct.unpack_from('<I', rom, word)[0]})
        elif group == 0x9800 and (h >> 8) & 7 == needed:
            before(at, 'stack', 4 * (h & 255))
        elif h & 0xFF00 == 0x4600:
            before(at, 'register', (h >> 3) & 15)
        elif h & 0xFE00 == 0x1C00 and (h >> 6) & 7 == 0:
            before(at, 'register', (h >> 3) & 7)
        else:
            emit({'kind': 'dynamic_register_definition', 'at': at, 'register': needed,
                  'mnemonic': instruction.mnemonic, 'operands': instruction.op_str,
                  'raw_hex': rom[at:at + i['size']].hex()})
    if not found:
        raise ValueError('dependency graph has no bounded frontier')
    return {'frontiers': [found[k] for k in sorted(found)], 'visited_dependency_states': len(seen),
            'scope': 'planning only; branches not narrowed and allocator preservation is conditional',
            'promotion_bytes': 0}
