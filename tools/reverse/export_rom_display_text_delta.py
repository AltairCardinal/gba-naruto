#!/usr/bin/env python3
"""Build direct-display records and publish only inside active managed runs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools._vendor.capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from tools.export_rom_fixed_consumer_text_inventory import _renderer_record_end, _sjis_ranges
from tools import verify_rom_display_text_delta as verifier
from tools.export_rom_small_cfg_dependency_batch import output_parent
from tools.export_rom_cfg_proven_roots_v21 import _publish_exclusive_at, _write_file_at


def build_from_rom(root, rom, *, verify_identity=True):
    root = Path(root).resolve(strict=True)
    contract = verifier.load_contract(root)
    if len(rom) != contract['rom']['size']:
        raise ValueError('ROM size changed')
    verifier.semantic_windows(contract, rom)
    reports = verifier._source_reports(root)
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    engine.detail = True
    consumers = []
    for row in contract['consumers']:
        verifier.source_owner(root, contract, rom, row)
        site, sink = row['site'], row['sink']
        instructions = list(engine.disasm(rom[site:sink + 4], site))
        cursor = site
        for instruction in instructions:
            if instruction.address != cursor:
                raise ValueError('consumer instruction partition changed')
            cursor += instruction.size
            if instruction.address == site:
                half = int.from_bytes(instruction.bytes, 'little')
                if instruction.size != 2 or half & 0xFF00 != 0x4800:
                    raise ValueError('fixed argument must load r0')
                literal = ((site + 4) & ~3) + 4 * (half & 255)
                target = struct.unpack_from('<I', rom, literal)[0] - 0x08000000
                if literal != row['literal_word'] or target != row['target']:
                    raise ValueError('fixed literal parameter changed')
            elif instruction.address == sink:
                if (instruction.mnemonic != 'bl' or instruction.size != 4
                        or int(instruction.op_str[1:], 16) != row['callee']):
                    raise ValueError('display sink changed')
            else:
                if instruction.size != 2 or instruction.mnemonic not in {'ldr', 'movs', 'str', 'adds', 'mov'}:
                    raise ValueError('unsupported display parameter path')
                if 'r0' in [instruction.reg_name(r) for r in instruction.regs_access()[1]]:
                    raise ValueError('r0 parameter overwritten')
        if cursor != sink + 4 or not instructions or instructions[-1].address != sink:
            raise ValueError('display path truncated')
        consumers.append({**row, 'instruction_count': len(instructions),
                          'path_sha256': verifier.sha(rom[site:sink + 4])})
    sjis = _sjis_ranges(rom)
    records = []
    for row in contract['records']:
        start = row['range'][0]
        end = _renderer_record_end(rom, start, row['limit'], sjis)
        records.append({'range': [start, end], 'limit': row['limit'],
                        'bytes_sha256': verifier.sha(rom[start:end]), 'nul_inclusive': True})
    payload = verifier.assemble(contract, consumers, records, reports)
    verifier.assert_unknown(payload['promotion']['claims'], verifier._precoverage(root)['segments'])
    if verify_identity and verifier.sha(rom) != contract['rom']['sha256']:
        raise ValueError('ROM identity changed')
    return payload


def build_payload(root):
    root = Path(root).resolve(strict=True)
    return build_from_rom(root, verifier.read_regular(root / verifier.ROM_PATH))


def export_artifact(root, output):
    root = Path(root).resolve(strict=True)
    target, parent_fd = output_parent(root, output)
    stage_fd = None
    stage_name = '.display-text-stage-' + secrets.token_hex(12)
    try:
        relative = target.relative_to(root / 'build/experiments/active')
        if len(relative.parts) < 3:
            raise ValueError('output lacks managed run')
        run = root / 'build/experiments/active' / relative.parts[0] / relative.parts[1]
        metadata = json.loads(verifier.read_regular(run / '.experiment.json'))
        if (metadata.get('status') != 'active' or metadata.get('task') != relative.parts[0]
                or metadata.get('run_id') != relative.parts[1]):
            raise ValueError('output run is not active and initialized')
        raw = verifier.canonical(build_payload(root))
        os.mkdir(stage_name, 0o700, dir_fd=parent_fd)
        stage_fd = os.open(stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        identity = os.fstat(stage_fd)
        _write_file_at(stage_fd, verifier.PAYLOAD, raw)
        _write_file_at(stage_fd, 'manifest.json', verifier.canonical(verifier.intended_manifest(root, raw)))
        stage = target.parent / stage_name
        report = verifier.verify_artifact(root, stage, allow_candidate=True)
        if not report['verified']:
            raise ValueError(f'independent display verifier rejected candidate: {report}')
        _write_file_at(stage_fd, '.accepted-manifest', verifier.canonical(verifier.intended_manifest(root, raw, report)))
        os.replace('.accepted-manifest', 'manifest.json', src_dir_fd=stage_fd, dst_dir_fd=stage_fd)
        os.fsync(stage_fd)
        if verifier.verify_artifact(root, stage) != report:
            raise ValueError('accepted display replay changed')
        named = os.stat(stage_name, dir_fd=parent_fd, follow_symlinks=False)
        if (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError('verified staging directory replaced')
        _publish_exclusive_at(parent_fd, stage_name, target.name)
        named = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        if (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError('published directory differs from verified staging')
        if verifier.verify_artifact(root, target) != report:
            raise ValueError('published display replay changed')
        return target
    finally:
        # Preserve owned failed staging; do not delete a replaceable path.
        if stage_fd is not None:
            os.close(stage_fd)
        os.close(parent_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    export_artifact(args.root, args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
