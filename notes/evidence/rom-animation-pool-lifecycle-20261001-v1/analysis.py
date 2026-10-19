"""Reproducible bounded investigation; no byte claims or global lifecycle proof."""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from tools._vendor.capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from tools.verify_rom_cfg_inventory import _decode

POOL = (0x45832C, 0x458794)
BASE = 0x08000000
ROM_SHA = '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
COVERAGE_SHA = 'b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
ENGINE = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
ENGINE.detail = True


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def freeze_mask(rom, at):
    if rom[at:at + 4] != bytes.fromhex('08200840'):
        raise ValueError('freeze mask opcode changed')
    return 8


def descriptor(rom, at, limit):
    start = at
    entries = []
    while at + 2 <= limit <= len(rom):
        if struct.unpack_from('<h', rom, at)[0] == -1:
            return {'entry_ranges': entries, 'sentinel_head_range': [at, at + 2],
                    'consumed_range': [start, at + 2],
                    'bytes_sha256': sha(rom[start:at + 2])}
        if at + 20 > limit:
            break
        entries.append([at, at + 20])
        at += 20
    raise ValueError('descriptor lacks a bounded sentinel')


def argument_path(rom, start, end, initial=None):
    """Constant effects in one independently delimited straight-line path.

    Unknown register reads remain unknown. Unbounded stores discard stack facts;
    control is rejected. Callers must prove membership and initial predicates.
    """
    if not 0 <= start <= end <= len(rom) or (start | end) & 1:
        raise ValueError('invalid path bounds')
    registers = dict(initial or {})
    stack = {}
    trace = []
    cursor = start
    for i in ENGINE.disasm(rom[start:end], start):
        if i.address != cursor or i.size != 2:
            raise ValueError('unsupported instruction partition')
        h = int.from_bytes(i.bytes, 'little')
        if (i.mnemonic.startswith('b') or i.mnemonic in ('pop', 'push', 'svc')
                or h & 0xFF00 == 0xB000):
            raise ValueError('control or stack adjustment inside argument path')
        old = dict(registers)
        names = [i.reg_name(r) for r in i.regs_access()[1]]
        if any(r in ('sp', 'pc') for r in names):
            raise ValueError('stack or PC overwritten')
        for name in names:
            aliases = {'sb': 9, 'sl': 10, 'fp': 11, 'ip': 12, 'lr': 14}
            reg = int(name[1:]) if re.fullmatch(r'r\d+', name) else aliases.get(name)
            if reg is not None:
                registers.pop(reg, None)
        group = h & 0xF800
        if group == 0x2000:
            registers[(h >> 8) & 7] = h & 255
        elif group == 0x4800:
            word = ((cursor + 4) & ~3) + 4 * (h & 255)
            if word + 4 > len(rom):
                raise ValueError('literal outside ROM')
            registers[(h >> 8) & 7] = struct.unpack_from('<I', rom, word)[0]
        elif group == 0x9000:
            key, reg = 4 * (h & 255), (h >> 8) & 7
            stack.pop(key, None)
            if reg in old:
                stack[key] = old[reg]
        elif group == 0x9800:
            reg, key = (h >> 8) & 7, 4 * (h & 255)
            if key in stack:
                registers[reg] = stack[key]
        elif h & 0xE000 == 0 and group != 0x1800:
            dst, src, shift, operation = h & 7, (h >> 3) & 7, (h >> 6) & 31, (h >> 11) & 3
            if src in old:
                value = old[src]
                if operation == 0:
                    registers[dst] = (value << shift) & 0xFFFFFFFF
                elif operation == 1:
                    registers[dst] = value >> (shift or 32)
                elif operation == 2:
                    signed = value if value < 0x80000000 else value - 0x100000000
                    registers[dst] = (signed >> (shift or 32)) & 0xFFFFFFFF
        elif group == 0x1800:
            dst, src = h & 7, (h >> 3) & 7
            operand = (h >> 6) & 7
            value = operand if h & 0x400 else old.get(operand)
            if src in old and value is not None:
                registers[dst] = (old[src] + (-value if h & 0x200 else value)) & 0xFFFFFFFF
        elif group in (0x3000, 0x3800):
            dst = (h >> 8) & 7
            if dst in old:
                registers[dst] = (old[dst] + (-(h & 255) if group == 0x3800 else h & 255)) & 0xFFFFFFFF
        elif h & 0xFF00 == 0x4600:
            dst, src = (h & 7) | ((h >> 4) & 8), (h >> 3) & 15
            if src in old:
                registers[dst] = old[src]
        elif i.mnemonic.startswith('str') or i.mnemonic in ('stm', 'stmia'):
            stack.clear()
        trace.append({'at': cursor, 'raw_hex': i.bytes.hex(), 'mnemonic': i.mnemonic,
                      'operands': i.op_str, 'known_registers': dict(registers),
                      'known_stack': dict(stack)})
        cursor += i.size
    if cursor != end:
        raise ValueError('path truncated')
    return {'registers': registers, 'stack': stack, 'trace': trace}


def source_ranges(source):
    blocks = source.get('blocks', source.get('extension', {}).get('blocks'))
    if blocks is not None:
        return [(b['range'], b.get('bytes_sha256')) for b in blocks if b['mode'] == 'thumb']
    promotion = source['promotion']
    if 'claims' in promotion:
        return [(r['range'], r.get('bytes_sha256')) for r in promotion['claims']
                if r.get('kind', r.get('claim_kind')) == 'reachable_thumb_code']
    return [(r, None) for r in promotion['code_ranges']]


def bl_target(rom, at):
    first, second = struct.unpack_from('<HH', rom, at)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    delta = ((first & 2047) << 12) | ((second & 2047) << 1)
    if delta & 0x400000:
        delta -= 0x800000
    return at + 4 + delta


def main(output):
    inputs = {}

    def read(path, expected=None):
        raw = Path(path).read_bytes()
        if expected is not None and sha(raw) != expected:
            raise ValueError(f'input identity changed: {path}')
        inputs[str(path)] = {'size': len(raw), 'sha256': sha(raw)}
        return raw

    rom = read('rom/base.gba', ROM_SHA)
    coverage = json.loads(read('sequel/rom-byte-coverage.json', COVERAGE_SHA))
    prior_path = 'notes/evidence/rom-animation-pool-caller-screen-20261001-v1/callers-v3.json'
    prior = json.loads(read(prior_path))
    read('tools/verify_rom_cfg_inventory.py')
    raw_shapes = [a for a in range(0, len(rom) - 3, 2) if bl_target(rom, a) == 0x626B4]
    assert raw_shapes == prior['all_rom_bl_encoding_shapes']
    sources = {}
    rows = []
    for at in raw_shapes:
        owners = [c for c in coverage['claims'] if c['role'] == 'primary'
                  and c['range'][0] <= at and at + 4 <= c['range'][1]]
        row = {'site': at, 'raw_hex': rom[at:at + 4].hex(), 'target': 0x626B4,
               'historical_44_member': at in prior['candidate_calls'],
               'source_cfg_independently_replayed': False}
        rows.append(row)
        if len(owners) != 1:
            row['exclusion'] = 'no_unique_primary_owner'
            continue
        owner = owners[0]
        row['owner'] = owner
        if 'reachable_instruction_bytes' not in owner['claim_kind']:
            row['exclusion'] = 'primary_owner_not_instruction_only'
            continue
        path = owner['evidence_path']
        if path not in sources:
            source = json.loads(read(path, owner['evidence_sha256']))
            ranges = source_ranges(source)
            sources[path] = ranges
        read(owner['independent_verifier_path'], owner['independent_verifier_sha256'])
        if 'promotion_manifest_path' in owner:
            read(owner['promotion_manifest_path'], owner['promotion_manifest_sha256'])
        a, b = owner['range']
        assert sha(rom[a:b]) == owner['bytes_sha256']
        matches = [r for r in sources[path] if r[0][0] <= at and at + 4 <= r[0][1]]
        if len(matches) != 1:
            row['exclusion'] = 'no_unique_source_cfg_range'
            continue
        (lo, hi), digest = matches[0]
        if digest:
            assert sha(rom[lo:hi]) == digest
        instructions = []
        cursor = lo
        while cursor < hi:
            i = _decode(rom, cursor, 'thumb')
            assert i['accepted'] and cursor + i['size'] <= hi
            instructions.append(i)
            cursor += i['size']
        target = next((i for i in instructions if i['file_offset'] == at), None)
        if target is None or target['size'] != 4 or target['flow_kind'] != 'call':
            row['exclusion'] = 'shape_not_source_instruction_boundary'
            continue
        row['source_instruction_membership_checked'] = True
        row['source_range'] = [lo, hi]
        # Start after the last control transfer; never jump across one silently.
        controls = [i for i in instructions if i['file_offset'] < at
                    and (i['flow_kind'] != 'linear'
                         or (struct.unpack_from('<H', rom, i['file_offset'])[0] & 0xFF00 == 0xB000)
                         or i['mnemonic'] in ('push', 'pop'))]
        start = controls[-1]['file_offset'] + controls[-1]['size'] if controls else lo
        row['argument_path_range'] = [start, at + 4]
        try:
            state = argument_path(rom, start, at)
        except ValueError as error:
            row['exclusion'] = 'unsupported_local_argument_path'
            row['path_error'] = str(error)
            continue
        row['local_arguments'] = state
        regs = state['registers']
        pair = [regs.get(0, 0) - BASE, regs.get(1, 0) - BASE]
        if not all(POOL[0] <= p < POOL[1] for p in pair):
            row['exclusion'] = 'base_pair_not_both_fixed_in_pool'
            continue
        row['base_pair'] = pair
        row['group'] = regs.get(2)
        row['flags_stack_argument'] = state['stack'].get(12)
        row['callback_stack_argument'] = state['stack'].get(16)
        row['exclusion'] = ('group_not_locally_fixed' if 2 not in regs else
                            'flags_or_callback_not_locally_fixed' if not {12, 16} <= state['stack'].keys()
                            else 'external_object_writers_and_full_lifecycle_open')
    pair_rows = []
    for first, second in sorted({tuple(r['base_pair']) for r in rows if 'base_pair' in r}):
        sequence = struct.unpack_from('<I', rom, second)[0] - BASE
        record, duration, next_head = struct.unpack_from('<HHh', rom, sequence)
        assert POOL[0] <= sequence and sequence + 6 <= POOL[1]
        ptr = struct.unpack_from('<I', rom, first + 4 * record)[0] - BASE
        assert POOL[0] <= ptr < POOL[1]
        pair_rows.append({'base_pair': [first, second], 'group0_sequence_range': [sequence, sequence + 6],
                          'record_id': record, 'duration': duration, 'next_head': next_head,
                          'descriptor': descriptor(rom, ptr, POOL[1]),
                          'group_domain_complete': False, 'slot_lifecycle_complete': False})
    windows = []
    for name, lo, hi in [('allocator', 0x626B4, 0x62786), ('group_reset', 0x62798, 0x627AA),
                         ('sort_render_list', 0x627B0, 0x62924),
                         ('callback_and_select', 0x62924, 0x62A0A),
                         ('descriptor_stop', 0x631CC, 0x63238),
                         ('advance_full', 0x63238, 0x63344)]:
        windows.append({'name': name, 'range': [lo, hi], 'sha256': sha(rom[lo:hi]),
                        'raw_hex': rom[lo:hi].hex(),
                        'halfword_start_decodes_not_instruction_partition': [
                            {'at': a, 'decode': _decode(rom, a, 'thumb')}
                            for a in range(lo, hi, 2)]})
    for name, lo, hi in [('nonzero_callback_complex', 0x8AA50, 0x8ACC6),
                         ('nonzero_callback_disable', 0x8EE40, 0x8EE5C),
                         ('disable_helper', 0x62788, 0x62798)]:
        windows.append({'name': name, 'range': [lo, hi], 'sha256': sha(rom[lo:hi]),
                        'raw_hex': rom[lo:hi].hex(), 'callback_effects_closed': False})
    assert freeze_mask(rom, 0x63244) == 8
    read(Path(__file__).resolve().relative_to(Path.cwd()))
    result = {'schema': 'animation-pool-lifecycle-local-audit-v1', 'inputs': inputs,
              'pool_range': list(POOL), 'raw_bl_shape_count': len(raw_shapes), 'rows': rows,
              'pair_rows': pair_rows, 'consumer_windows': windows,
              'freeze_mask': 8, 'freeze_bit_index': 3,
              'summary': {'exclusions': dict(sorted(Counter(r['exclusion'] for r in rows).items())),
                          'local_fixed_pool_pairs': len(pair_rows),
                          'local_pool_calls': sum('base_pair' in r for r in rows),
                          'instruction_members': sum(r.get('source_instruction_membership_checked', False) for r in rows)},
              'scope': 'Raw target-limited BL denominator and source-bound local parameters only. '
                       'Does not prove all logical callers, predecessor domains, callback/writer closure, '
                       'natural execution, renderer buffer safety, Unicode or editing safety.',
              'promotion_bytes': 0}
    Path(output).write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    with Path(sys.argv[2]).open('x') as stream:
        import contextlib
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            main(sys.argv[1])
