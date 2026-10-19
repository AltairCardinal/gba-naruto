#!/usr/bin/env python3
"""Inventory raw handler edges and stack stores with explicit call uncertainty.

BL return edges are conditional, including interpreter-internal targets. This
is an overapproximation conditional on external returns, not a return proof or
a handler/record promotion contract. Architectural PC writes remain frontiers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools._vendor.capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, arm_const
from tools.verify_rom_fixed_renderer_script_records import CFG_UPSTREAM, _cfg_blocks
from tools.verify_rom_prebattle_menu_controller_cfg import _direct_target
from tools.verify_rom_boot_interwork import _arm_b_target, _instruction_vector

ROM_SHA = '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
INPUTS = {
    'tools/verify_rom_boot_interwork.py':
        '66d34dc56f837e09c22fcebdd58e2e67b132c133ea7402e8d50f7e187d54984b',
    'artifacts/rom-boot-interwork-v1/rom-boot-interwork.json':
        '2f78132647235ca1c9fd155b950ff4128e4b01ca10d0fa0ae0fcfa4fdd37e30d',
    'artifacts/rom-boot-interwork-v1/manifest.json':
        'f2673837955194f35daab4f9fb7c0b2fe2dd5967231fcd6d982d0cacb9f749be',
    'tools/verify_rom_fixed_renderer_script_records.py':
        'c7f3eeaabc4a6755c7974838084aa7495f866924e40fd4ea2bb072d5db7f3927',
    'tools/verify_rom_prebattle_menu_controller_cfg.py':
        '387c1b00a1c38b424e6f30d567374329493c1d3309c32a29fd905b77a65b3d2f',
}
HANDLERS = ((7, 0x675E4, 0x68084), (8, 0x68090, 0x681AC))
STOPS = {0x68354, 0x6835E}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def walk_handler(rom: bytes, root: int, bounds: tuple[int, int], stops: set[int],
                 membership: dict[int, int] | None = None,
                 *, context_targets: set[int] | None = None) -> dict:
    lo, hi = bounds
    if not 0 <= lo <= root < hi <= len(rom) or (lo | hi | root) & 1:
        raise ValueError('invalid handler bounds')
    context_targets = set() if context_targets is None else context_targets
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    engine.detail = True
    work, seen, instructions, edges, calls, stores, frontiers = [root], set(), [], [], [], [], []

    def enqueue(source: int, target: int, kind: str) -> None:
        edges.append({'source': source, 'target': target, 'kind': kind})
        if target in stops:
            return
        if not lo <= target < hi or target & 1:
            frontiers.append({'offset': source, 'target': target, 'kind': 'outside_handler_bounds'})
            return
        work.append(target)

    while work:
        at = work.pop()
        if at in seen:
            continue
        seen.add(at)
        if len(seen) > 6000:
            raise ValueError('handler instruction budget exceeded')
        decoded = list(engine.disasm(rom[at:min(at + 4, hi)], at, count=1))
        if not decoded or decoded[0].size not in (2, 4):
            raise ValueError(f'unsupported instruction at {at:06x}')
        insn = decoded[0]
        size = insn.size
        if membership is not None and membership.get(at) != size:
            raise ValueError(f'instruction membership missing at {at:06x}')
        instructions.append({'offset': at, 'size': size, 'bytes': rom[at:at + size].hex(),
                             'mnemonic': insn.mnemonic, 'operands': insn.op_str})
        half = struct.unpack_from('<H', rom, at)[0]
        if half & 0xF800 == 0x9000:
            stores.append({'offset': at, 'source_register': (half >> 8) & 7,
                           'sp_relative_offset': (half & 255) * 4})
        branch = _direct_target(rom, at)
        if branch is not None:
            target, kind, branch_size = branch
            if branch_size != size:
                raise ValueError('raw branch decoder and instruction size disagree')
            if kind == 'bl':
                internal = lo <= target < hi
                context_switch = target in context_targets
                calls.append({'offset': at, 'target': target, 'internal': internal,
                              'return_proven': False, 'callee_side_effects_closed': False,
                              'context_switch_dependency': context_switch,
                              'same_context_resumption_proven': False})
                if internal:
                    enqueue(at, target, 'internal_call_target')
                enqueue(at, at + size, 'conditional_context_resumption' if context_switch
                        else 'conditional_call_return')
            else:
                enqueue(at, target, kind)
                if kind == 'bcond':
                    enqueue(at, at + size, 'conditional_fallthrough')
        elif arm_const.ARM_REG_PC in insn.regs_access()[1]:
            frontiers.append({'offset': at, 'kind': 'indirect_pc_target'})
        elif insn.id in (arm_const.ARM_INS_SVC, arm_const.ARM_INS_BKPT):
            frontiers.append({'offset': at, 'kind': 'exception_instruction'})
        else:
            enqueue(at, at + size, 'fallthrough')
    return {'root': root, 'bounds': [lo, hi], 'stops': sorted(stops),
            'instructions': sorted(instructions, key=lambda row: row['offset']),
            'edges': sorted(edges, key=lambda row: (row['source'], row['target'], row['kind'])),
            'calls': sorted(calls, key=lambda row: row['offset']),
            'direct_sp_word_stores': sorted(stores, key=lambda row: row['offset']),
            'frontiers': sorted(frontiers, key=lambda row: row['offset']),
            'structured_return_proven': False,
            'external_call_return_edges_are_conditional': True}



def context_switch_dependency(root: Path, rom: bytes) -> dict:
    expected = {0x9C574: '7847', 0x9C578: '3b8ffdea', 0x26C: 'ffdf2de9',
                0x320: '04d082e5', 0x32C: '4c2082e2', 0x39C: '04d092e5', 0x3A4: '1eff2fe1',
                0x3AC: '00d093e5', 0x3B8: '1eff2fe1'}
    for offset, hex_bytes in expected.items():
        if rom[offset:offset + len(bytes.fromhex(hex_bytes))].hex() != hex_bytes:
            raise ValueError('context switch raw witness changed')
    if _arm_b_target(rom, 0x9C578) != 0x26C:
        raise ValueError('interwork ARM target changed')
    boot = json.loads((root / 'artifacts/rom-boot-interwork-v1/rom-boot-interwork.json').read_bytes())
    if _instruction_vector(rom) != boot['instructions']:
        raise ValueError('independent boot instruction membership changed')
    arm_members = {row['file_offset']: row for row in boot['instructions']}
    for offset in [0x26C, 0x320, 0x32C, 0x39C, 0x3A4, 0x3AC, 0x3B8]:
        if offset not in arm_members or arm_members[offset]['mode'] != 'arm':
            raise ValueError('context witness lacks accepted ARM membership')
    return {'thumb_entry': 0x9C574, 'arm_veneer': 0x9C578, 'arm_target': 0x26C,
            'raw_points': [{'offset': offset, 'bytes': raw} for offset, raw in expected.items()],
            'record_stride_shape': 0x4C, 'saved_sp_field': 4,
            'observed_sp_store': 0x320, 'observed_sp_restores': [0x39C, 0x3AC],
            'indirect_resume_points': [0x3A4, 0x3B8],
            'same_context_resumption_proven': False,
            'task_record_domain_and_all_writers_closed': False,
            'sibling_veneer_promoted_here': False}


def analyze(root: Path) -> dict:
    rom = (root / 'rom/base.gba').read_bytes()
    if sha(rom) != ROM_SHA:
        raise ValueError('ROM identity changed')
    for path, digest in INPUTS.items():
        if sha((root / path).read_bytes()) != digest:
            raise ValueError(f'helper identity changed: {path}')
    # The shared block loader is cached; recheck its inputs on every invocation.
    for path, digest in CFG_UPSTREAM:
        if sha((root / path).read_bytes()) != digest:
            raise ValueError(f'upstream identity changed: {path}')
    blocks, cfg_contract = _cfg_blocks(root)
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    membership = {}
    for block in blocks:
        start, end = block['range']
        if block.get('mode') != 'thumb' or not any(start < hi and lo < end for _, lo, hi in HANDLERS):
            continue
        cursor = start
        for insn in engine.disasm(rom[start:end], start):
            if insn.address != cursor:
                raise ValueError('upstream instruction partition is discontinuous')
            membership[insn.address] = insn.size
            cursor += insn.size
        if cursor != end:
            raise ValueError('upstream block does not fully decode')
    context_dependency = context_switch_dependency(root, rom)
    handlers = [dict(opcode=opcode, **walk_handler(rom, start, (start, end), STOPS, membership,
                                                context_targets={0x9C574}))
                for opcode, start, end in HANDLERS]
    context_dependency['handler_callsites'] = sorted(call['offset'] for handler in handlers
                                                    for call in handler['calls']
                                                    if call['context_switch_dependency'])
    return {'schema': 'rom-renderer-handler-raw-graph-inventory-v1',
            'rom_sha256': ROM_SHA, 'helper_inputs': INPUTS, 'upstream_cfg_contract': cfg_contract,
            'handlers': handlers, 'context_switch_dependency': context_dependency,
            'complete_handler_semantics_proven': False,
            'natural_execution_proven': False, 'promotion_bytes': 0,
            'scope': 'Raw graph and direct SP-word-store inventory conditional on call returns; no global stack/RAM alias, callee or script progression closure.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps(analyze(args.root), sort_keys=True, indent=2))
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
