"""Conservative constants over a fixed raw source graph, never natural execution.

Unknown callees kill every register/stack fact. Explicit raw callee summaries
may preserve only verified r4-r11 identities, with their frame preconditions; even then all caller stack facts are
discarded. Branch refinements only use actual, unmodified compare flags and live
SP-load origins. Opaque call fallthrough remains conditional context resumption.
"""
from __future__ import annotations

from collections import deque
import copy
import importlib.util
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path.cwd()))
from tools.verify_rom_cfg_inventory import _decode

OLD = Path('notes/evidence/rom-animation-pool-lifecycle-20261001-v1/analysis.py')
spec = importlib.util.spec_from_file_location('frozen_animation_local_analysis', OLD)
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


def allocator_contract(rom):
    start, end = 0x626B4, 0x62786
    digest = local.sha(rom[start:end])
    if digest != 'db4e7462e0ecd3ee06bcef0dde1e0934b54ab0f906b467e5cf3e5ebddae7fc57':
        raise ValueError('allocator full frame bytes changed')
    if rom[0x62774:end].hex() != '002002b038bc9846a146aa46f0bc02bc0847':
        raise ValueError('allocator restore/return changed')
    if rom[start:start + 12].hex() != 'f0b557464e464546e0b482b0':
        raise ValueError('allocator save/frame changed')
    return {'range': [start, end], 'sha256': digest, 'preserved_registers': list(range(4, 12)),
            'private_frame_bytes': 40, 'object_pool_range': [0x03003BB8, 0x030059B8],
            'caller_stack_facts_preserved': False,
            'precondition': 'private stack frame [entry_sp-40, entry_sp) disjoint from object pool',
            'private_stack_disjointness_proven_for_callers': False,
            'full_object_lifecycle_proven': False}


def empty():
    return {'registers': {}, 'stack': {}, 'origins': {}, 'predicate': None,
            'conditional_allocator_preservation': False,
            'unverified_call_continuation': False, 'conditional_callee_preservation': False}


def meet(first, second):
    merged = empty()
    for key in ('registers', 'stack', 'origins'):
        merged[key] = {r: v for r, v in first[key].items() if second[key].get(r) == v}
    merged['predicate'] = first['predicate'] if first['predicate'] == second['predicate'] else None
    for key in ('conditional_allocator_preservation', 'unverified_call_continuation', 'conditional_callee_preservation'):
        merged[key] = first[key] or second[key]
    return merged


def linear(rom, at, state):
    h = struct.unpack_from('<H', rom, at)[0]
    group = h & 0xF800
    result = copy.deepcopy(state)
    if h & 0xFF00 == 0xB000 or h & 0xFE00 in (0xB400, 0xBC00):
        result['stack'].clear()
        result['origins'].clear()
        result['predicate'] = None
        if h & 0xFE00 == 0xBC00:
            for r in range(8):
                if h & (1 << r):
                    result['registers'].pop(r, None)
        return result
    if group == 0x9000:
        register, offset = (h >> 8) & 7, 4 * (h & 255)
        result['stack'].pop(offset, None)
        result['origins'] = {r: o for r, o in result['origins'].items() if o != offset}
        if register in state['registers']:
            result['stack'][offset] = state['registers'][register]
        return result
    if group == 0x9800:
        register, offset = (h >> 8) & 7, 4 * (h & 255)
        result['registers'].pop(register, None)
        if result['predicate'] is not None and result['predicate']['register'] == register:
            result['predicate'] = None
        result['origins'][register] = offset
        if offset in state['stack']:
            result['registers'][register] = state['stack'][offset]
        return result
    i = next(local.ENGINE.disasm(rom[at:at + 2], at, count=1))
    writes = [i.reg_name(r) for r in i.regs_access()[1]]
    # Capstone omits CPSR for some Thumb MOVS/shift aliases. Raw Thumb-1
    # classes are authoritative; loads/stores/high MOV/ADD leave flags alone.
    raw_updates_flags = (h & 0xE000 in (0x0000, 0x2000)
                         or h & 0xFC00 == 0x4000 or h & 0xFF00 == 0x4500)
    compared = state['predicate']['register'] if state['predicate'] is not None else None
    compared_name = {9: 'sb', 10: 'sl', 11: 'fp', 12: 'ip'}.get(compared, f'r{compared}')
    if raw_updates_flags or 'cpsr' in writes or compared_name in writes:
        result['predicate'] = None
    old_registers = dict(state['registers'])
    try:
        one = local.argument_path(rom, at, at + 2, old_registers)
        result['registers'] = one['registers']
    except ValueError:
        result['registers'].clear()
        result['stack'].clear()
        result['origins'].clear()
        result['predicate'] = None
        return result
    # A possibly aliased store kills remembered origins as well as stack facts.
    if i.mnemonic.startswith('str') or i.mnemonic in ('stm', 'stmia'):
        result['stack'].clear()
        result['origins'].clear()
        result['predicate'] = None
    for r in list(result['origins']):
        name = {9: 'sb', 10: 'sl', 11: 'fp', 12: 'ip'}.get(r, f'r{r}')
        if name in writes:
            result['origins'].pop(r)
    if group == 0x2800:
        register, rhs = (h >> 8) & 7, h & 255
        result['predicate'] = {'register': register, 'rhs': rhs,
                               'origin': state['origins'].get(register),
                               'equal': old_registers[register] == rhs if register in old_registers else None}
    elif h & 0xFFC0 == 0x4280:
        lhs, rhs_register = h & 7, (h >> 3) & 7
        if rhs_register in old_registers:
            rhs = old_registers[rhs_register]
            result['predicate'] = {'register': lhs, 'rhs': rhs,
                                   'origin': state['origins'].get(lhs),
                                   'equal': old_registers[lhs] == rhs if lhs in old_registers else None}
    # Exact copies carry a live load origin. Other writes already discarded it.
    if h & 0xFF00 == 0x4600:
        dst, src = (h & 7) | ((h >> 4) & 8), (h >> 3) & 15
        if src in state['origins']:
            result['origins'][dst] = state['origins'][src]
    elif h & 0xFE00 == 0x1C00 and (h >> 6) & 7 == 0:
        dst, src = h & 7, (h >> 3) & 7
        if src in state['origins']:
            result['origins'][dst] = state['origins'][src]
    return result


def validate_callees(rom, offsets, callees):
    callees = callees or {}
    if callees:
        from callee_effects import analyze

        def check_source(target, summary, ancestors=()):
            if target in ancestors or len(ancestors) >= 32:
                raise ValueError('cyclic or excessive child source binding')
            nodes = {row['at'] for row in summary['source_instructions']}
            if summary['root'] != target or not nodes <= offsets:
                raise ValueError('callee source binding mismatch')
            for child in summary.get('children', []):
                check_source(child['target'], child['summary'], ancestors+(target,))
            return nodes

        for target, summary in callees.items():
            nodes = check_source(target, summary)
            children = {row['target']:row['summary'] for row in summary.get('children', [])}
            expected = analyze(rom, target, nodes,
                               conditional_frame=summary.get('frame_mode', summary['conditional']),
                               children=children)
            if summary != expected or not expected['return_identity_proven']:
                raise ValueError('unverified callee summary')
    return callees


def run_flow(rom, instruction_offsets, roots, *, allocator=None, callees=None, budget=1000000):
    if allocator is not None and allocator != allocator_contract(rom):
        raise ValueError('unverified allocator contract')
    offsets = set(instruction_offsets)
    if not roots <= offsets or type(budget) is not int or budget < 1:
        raise ValueError('invalid fixed graph inputs')
    callees = validate_callees(rom, offsets, callees)
    decoded = {at: _decode(rom, at, 'thumb') for at in sorted(offsets)}
    if any(not i['accepted'] for i in decoded.values()):
        raise ValueError('unsupported source instruction')
    occupied = set()
    for at, instruction in decoded.items():
        byte_range = set(range(at, at + instruction['size']))
        if byte_range & occupied:
            raise ValueError('source instruction overlap')
        occupied |= byte_range
    states = {at: empty() for at in roots}
    queue = deque(sorted(roots))
    queued = set(roots)
    updates = 0
    while queue:
        at = queue.popleft()
        queued.remove(at)
        updates += 1
        if updates > budget:
            raise ValueError('source constant-flow budget exhausted')
        state = states[at]
        instruction = decoded[at]
        kind = instruction['flow_kind']
        routes = []
        if kind == 'call':
            target = next(e['file_offset'] for e in instruction['successors'] if e['kind'] == 'call_target')
            new = empty()
            new['unverified_call_continuation'] = True
            new['conditional_allocator_preservation'] = state['conditional_allocator_preservation']
            new['conditional_callee_preservation'] = state['conditional_callee_preservation']
            if target == 0x626B4 and allocator is not None:
                new['registers'] = {r: value for r, value in state['registers'].items()
                                    if r in allocator['preserved_registers']}
                new['conditional_allocator_preservation'] = True
            elif target in callees:
                summary = callees[target]
                new['registers'] = {r: value for r, value in state['registers'].items()
                                    if 4 <= r <= 11 and r in summary['preserved_registers']}
                new['conditional_callee_preservation'] |= summary['conditional']
            routes = [(e['file_offset'], new) for e in instruction['successors'] if e['kind'] == 'fallthrough']
        elif kind == 'conditional_branch':
            condition = (struct.unpack_from('<H', rom, at)[0] >> 8) & 15
            predicate = state['predicate']
            for edge in instruction['successors']:
                new = copy.deepcopy(state)
                if condition in (0, 1) and predicate is not None:
                    equal_edge = (edge['kind'] == 'branch_target') == (condition == 0)
                    if predicate['equal'] is not None and predicate['equal'] != equal_edge:
                        continue
                    if equal_edge:
                        register, rhs, origin = predicate['register'], predicate['rhs'], predicate['origin']
                        new['registers'][register] = rhs
                        if origin is not None and state['origins'].get(register) == origin:
                            new['stack'][origin] = rhs
                new['predicate'] = None
                routes.append((edge['file_offset'], new))
        elif kind == 'unconditional_branch':
            routes = [(e['file_offset'], state) for e in instruction['successors']]
        elif kind == 'linear':
            new = linear(rom, at, state)
            routes = [(e['file_offset'], new) for e in instruction['successors']]
        # Returns, BX, context switches and unsupported PC targets are opaque.
        for target, new in routes:
            if target not in offsets:
                continue
            merged = meet(states[target], new) if target in states else copy.deepcopy(new)
            if target not in states or merged != states[target]:
                states[target] = merged
                if target not in queued:
                    queue.append(target)
                    queued.add(target)
    return {'states': states, 'updates': updates, 'instruction_count': len(decoded),
            'root_count': len(roots), 'scope': 'fixed source graph; opaque call continuation only',
            'natural_execution': False, 'promotion_bytes': 0}
