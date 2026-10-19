"""Raw Thumb saved-register identities, with explicit private-frame assumptions.

All conditional branches are explored. Opaque child calls destroy every GPR fact;
only saved memory may survive under a named, unproved frame contract. SVC and
unknown returns stay frontiers. Caller stack memory is never summarized intact.
"""
from collections import deque
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path.cwd()))
from tools.verify_rom_cfg_inventory import _decode

spec = importlib.util.spec_from_file_location('frozen_animation_local',
    Path('notes/evidence/rom-animation-pool-lifecycle-20261001-v1/analysis.py'))
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


def register(name):
    if name.startswith('r') and name[1:].isdigit():
        return int(name[1:])
    return {'sb': 9, 'sl': 10, 'fp': 11, 'ip': 12, 'sp': 13, 'lr': 14, 'pc': 15}.get(name)


def merge(first, second):
    if first['sp'] != second['sp']:
        raise ValueError('inconsistent SP at source join')
    result = copy.deepcopy(first)
    for key in ('registers', 'memory'):
        result[key] = {k: v for k, v in first[key].items() if second[key].get(k) == v}
    return result


def analyze(rom, root, offsets, *, conditional_frame=False, budget=50000):
    if root not in offsets or type(budget) is not int or budget < 1:
        raise ValueError('invalid bounded callee inputs')
    decoded = {at: _decode(rom, at, 'thumb') for at in sorted(offsets)}
    occupied = set()
    for at, i in decoded.items():
        if not i['accepted']:
            raise ValueError('unsupported source instruction')
        bytes_ = set(range(at, at+i['size']))
        if occupied & bytes_:
            raise ValueError('overlapping source partition')
        occupied |= bytes_
    initial = {'sp': 0, 'registers': {r: ('entry_register', r) for r in range(15)}, 'memory': {}}
    initial['registers'][13] = ('entry_sp', 0)
    states, pending, queued = {root: initial}, deque([root]), {root}
    returns, frontiers, conditions, calls, stores = {}, {}, {}, set(), {}
    updates, minimum_sp = 0, 0

    def emit(collection, row):
        collection[json.dumps(row, sort_keys=True)] = row

    def set_sp(state, value):
        if not -4096 <= value <= 4096 or value % 4:
            raise ValueError('unbounded or misaligned frame')
        state['sp'] = value
        state['registers'][13] = ('entry_sp', value)

    def finish(at, state, value):
        if value != ('entry_register', 14) or state['sp'] != 0:
            emit(frontiers, {'kind': 'unproved_return_identity', 'at': at, 'sp_delta': state['sp']})
            return
        returns[at] = copy.deepcopy(state)

    while pending:
        at = pending.popleft()
        queued.remove(at)
        updates += 1
        if updates > budget:
            raise ValueError('callee identity budget exhausted')
        state = copy.deepcopy(states[at])
        old = dict(state['registers'])
        i = decoded[at]
        h = struct.unpack_from('<H', rom, at)[0]
        routes = None
        if h & 0xff00 == 0xdf00:
            emit(frontiers, {'kind': 'external_svc', 'at': at, 'number': h & 255})
            continue
        if i['flow_kind'] == 'call':
            target = next(e['file_offset'] for e in i['successors'] if e['kind'] == 'call_target')
            calls.add(target)
            if not conditional_frame:
                emit(frontiers, {'kind': 'opaque_child_call', 'at': at, 'target': target})
                continue
            emit(conditions, {'kind': 'child_returns_same_sp_and_private_frame_intact', 'at': at, 'target': target})
            state['registers'] = {13: ('entry_sp', state['sp'])}
            routes = [e['file_offset'] for e in i['successors'] if e['kind'] == 'fallthrough']
        elif h & 0xfe00 == 0xb400:
            regs = [r for r in range(8) if h & (1 << r)] + ([14] if h & 0x100 else [])
            set_sp(state, state['sp']-4*len(regs))
            for n, r in enumerate(regs):
                key = state['sp']+4*n
                state['memory'].pop(key, None)
                if r in old:
                    state['memory'][key] = old[r]
        elif h & 0xfe00 == 0xbc00:
            regs = [r for r in range(8) if h & (1 << r)] + ([15] if h & 0x100 else [])
            popped_pc = None
            for n, r in enumerate(regs):
                key = state['sp']+4*n
                state['registers'].pop(r, None)
                if key in state['memory']:
                    state['registers'][r] = state['memory'][key]
                if r == 15:
                    popped_pc = state['registers'].get(r)
                state['memory'].pop(key, None)
            set_sp(state, state['sp']+4*len(regs))
            if 15 in regs:
                finish(at, state, popped_pc)
                continue
        elif h & 0xff00 == 0xb000:
            delta = (h & 127)*4*(-1 if h & 128 else 1)
            set_sp(state, state['sp']+delta)
        elif h == 0x46f7:
            finish(at, state, old.get(14))
            continue
        elif h & 0xff87 == 0x4700:
            source = (h >> 3) & 15
            finish(at, state, old.get(source))
            continue
        elif i['flow_kind'] in ('conditional_branch', 'unconditional_branch'):
            pass
        elif i['flow_kind'] != 'linear':
            emit(frontiers, {'kind': 'opaque_control', 'at': at, 'flow_kind': i['flow_kind']})
            continue
        else:
            instruction = next(local.ENGINE.disasm(rom[at:at+i['size']], at, count=1))
            names = [instruction.reg_name(r) for r in instruction.regs_access()[1]]
            writes = {register(n) for n in names} - {None}
            if 13 in writes or 15 in writes:
                raise ValueError('dynamic SP or PC write')
            for r in writes:
                state['registers'].pop(r, None)
            group = h & 0xf800
            if group == 0x9000:
                r, key = (h >> 8) & 7, state['sp']+4*(h & 255)
                state['memory'].pop(key, None)
                if r in old:
                    state['memory'][key] = old[r]
            elif group == 0x9800:
                r, key = (h >> 8) & 7, state['sp']+4*(h & 255)
                if key in state['memory']:
                    state['registers'][r] = state['memory'][key]
            elif h & 0xff00 == 0x4600:
                dst, src = (h & 7) | ((h >> 4) & 8), (h >> 3) & 15
                if src in old:
                    state['registers'][dst] = old[src]
            elif h & 0xfe00 == 0x1c00 and (h >> 6) & 7 == 0:
                dst, src = h & 7, (h >> 3) & 7
                if src in old:
                    state['registers'][dst] = old[src]
            elif instruction.mnemonic.startswith('str') or instruction.mnemonic in ('stm', 'stmia'):
                emit(stores, {'at': at, 'raw_hex': rom[at:at+i['size']].hex(),
                              'mnemonic': instruction.mnemonic, 'operands': instruction.op_str})
                # An explicit SP-token address cannot be excused as a disjoint
                # store. Partial writes invalidate the overlapping saved word.
                address, source, width = None, None, None
                if instruction.mnemonic.startswith('str') and len(instruction.operands) == 2:
                    src, memory = instruction.operands
                    base = old.get(register(instruction.reg_name(memory.mem.base)))
                    index = old.get(register(instruction.reg_name(memory.mem.index)), 0) if memory.mem.index else 0
                    if isinstance(base, tuple) and base[0] == 'entry_sp' and isinstance(index, int):
                        address = base[1]+memory.mem.disp+index
                        source = old.get(register(instruction.reg_name(src.reg)))
                        width = 1 if instruction.mnemonic.startswith('strb') else 2 if instruction.mnemonic.startswith('strh') else 4
                if address is not None:
                    for key in list(state['memory']):
                        if key < address+width and address < key+4:
                            del state['memory'][key]
                    if width == 4 and address % 4 == 0 and source is not None:
                        state['memory'][address] = source
                elif instruction.mnemonic in ('stm', 'stmia') and instruction.operands:
                    base = old.get(register(instruction.reg_name(instruction.operands[0].reg)))
                    if isinstance(base, tuple) and base[0] == 'entry_sp':
                        state['memory'].clear()
                    elif conditional_frame:
                        emit(conditions, {'kind': 'non_sp_store_disjoint_from_saved_private_words', 'at': at})
                    else:
                        state['memory'].clear()
                elif conditional_frame:
                    emit(conditions, {'kind': 'non_sp_store_disjoint_from_saved_private_words', 'at': at})
                else:
                    state['memory'].clear()
            else:
                numeric = {r: v for r, v in old.items() if isinstance(v, int)}
                try:
                    out = local.argument_path(rom, at, at+i['size'], numeric)['registers']
                    for r in writes:
                        if r in out:
                            state['registers'][r] = out[r]
                except ValueError:
                    # Unknown data effects destroy written register identities;
                    # source membership was already raw-control-flow checked.
                    pass
        minimum_sp = min(minimum_sp, state['sp'])
        if routes is None:
            routes = [e['file_offset'] for e in i['successors'] if e['kind'] != 'call_target']
        for target in routes:
            if target not in offsets:
                emit(frontiers, {'kind': 'source_graph_boundary', 'at': at, 'target': target})
                continue
            new = merge(states[target], state) if target in states else copy.deepcopy(state)
            if target not in states or new != states[target]:
                states[target] = new
                if target not in queued:
                    queued.add(target)
                    pending.append(target)
    preserved = set(range(15))
    if frontiers or not returns:
        preserved.clear()
    else:
        for state in returns.values():
            current = {r for r, v in state['registers'].items() if v == ('entry_register', r)}
            if state['sp'] == 0:
                current.add(13)
            preserved &= current
    return {'root': root, 'rom_sha256': local.sha(rom),
            'source_instructions': [{'at': at, 'raw_hex': rom[at:at+decoded[at]['size']].hex()}
                                    for at in sorted(states)],
            'visited_instruction_count': len(states), 'updates': updates,
            'return_identity_proven': bool(returns) and not frontiers, 'return_count': len(returns),
            'preserved_registers': sorted(preserved), 'minimum_sp_delta': minimum_sp,
            'frontiers': [frontiers[k] for k in sorted(frontiers)],
            'preconditions': [conditions[k] for k in sorted(conditions)],
            'conditional': bool(conditions), 'child_call_targets': sorted(calls),
            'non_sp_stores': [stores[k] for k in sorted(stores)],
            'caller_stack_facts_preserved': False, 'natural_execution_proven': False,
            'scope': 'All edges of fixed bounded source graph; identities conditional on listed memory/return assumptions.',
            'promotion_bytes': 0}
