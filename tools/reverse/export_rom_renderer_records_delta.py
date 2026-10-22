#!/usr/bin/env python3
"""Build a combined renderer delta, publishing only to an active managed run."""
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
from tools import export_rom_fixed_renderer_script_records as legacy
from tools.export_rom_training_text_script_inventory import _parse_training_record, _sjis_ranges
from tools import verify_rom_renderer_records_delta as verifier
from tools.export_rom_small_cfg_dependency_batch import output_parent
from tools.export_rom_cfg_proven_roots_v21 import _publish_exclusive_at, _write_file_at


def build_from_rom(root, rom, *, verify_identity=True):
    root = Path(root).resolve(strict=True)
    contract = verifier.load_contract(root)
    if len(rom) != legacy.ROM_SIZE:
        raise ValueError('ROM size changed')
    for interval, digest in [(legacy.INTERPRETER_RANGE, legacy.INTERPRETER_SHA256),
                             (legacy.PARSER_RANGE, legacy.PARSER_SHA256),
                             (legacy.SJIS_RANGE, legacy.SJIS_SHA256)]:
        if verifier.sha(rom[interval[0]:interval[1]]) != digest:
            raise ValueError('frozen interpreter/parser semantics changed')
    segments = verifier.precoverage(root, contract)
    unknown = [s['range'] for s in segments if s['primary_class'] == 'unknown']
    groups, reports = verifier.verified_sources(root)
    sjis = _sjis_ranges(rom)
    consumers, records = [], {}
    for source, blocks in groups:
        for block in blocks:
            if block.get('mode') != 'thumb':
                continue
            start, end = block['range']
            for site in range(start, end, 2):
                half = struct.unpack_from('<H', rom, site)[0]
                if half & 0xF800 != 0x4800:
                    continue
                literal = ((site + 4) & ~3) + (half & 255) * 4
                target = struct.unpack_from('<I', rom, literal)[0] - legacy.ROM_BASE
                pool = next((p for p in contract['target_pools'] if p[0] <= target < p[1]), None)
                if pool is None or not any(a <= target < b for a,b in unknown):
                    continue
                sink = legacy._prove_parameter_flow(rom, site, (half >> 8) & 7)
                row = {'source': source, 'block_id': block['id'], 'site': site,
                       'literal_word': literal, 'target': target, 'interpreter_callsite': sink,
                       'path_sha256': verifier.sha(rom[site:sink + 4])}
                try:
                    parsed = _parse_training_record(rom, target, pool[1], sjis)
                    row['accepted'] = True
                    stop = parsed['end']
                    records[target] = {'range': [target, stop], 'opcode_sequence': parsed['opcode_sequence'],
                                       'bytes_sha256': verifier.sha(rom[target:stop])}
                except ValueError as error:
                    row.update(accepted=False, excluded_opcode=verifier.exclusion(error))
                consumers.append(row)
    payload = verifier.assemble(contract, consumers, list(records.values()), reports)
    verifier.assert_unknown(payload['promotion']['claims'], segments)
    if verify_identity and verifier.sha(rom) != legacy.ROM_SHA256:
        raise ValueError('ROM identity changed')
    return payload


def build_payload(root):
    root = Path(root).resolve(strict=True)
    return build_from_rom(root, verifier.read_regular(root / legacy.ROM_PATH))


def export_artifact(root, output):
    root = Path(root).resolve(strict=True)
    target, parent_fd = output_parent(root, output)
    stage_fd = None
    stage_name = '.renderer-records-stage-' + secrets.token_hex(12)
    try:
        relative = target.relative_to(root / 'build/experiments/active')
        if len(relative.parts) < 3:
            raise ValueError('output lacks managed run')
        run = root / 'build/experiments/active' / relative.parts[0] / relative.parts[1]
        metadata = json.loads(verifier.read_regular(run / '.experiment.json'))
        if metadata.get('status') != 'active' or metadata.get('task') != relative.parts[0] or metadata.get('run_id') != relative.parts[1]:
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
            raise ValueError(f'independent verifier rejected candidate: {report}')
        _write_file_at(stage_fd, '.accepted-manifest', verifier.canonical(verifier.intended_manifest(root, raw, report)))
        os.replace('.accepted-manifest', 'manifest.json', src_dir_fd=stage_fd, dst_dir_fd=stage_fd)
        os.fsync(stage_fd)
        if verifier.verify_artifact(root, stage) != report:
            raise ValueError('accepted replay changed')
        named = os.stat(stage_name, dir_fd=parent_fd, follow_symlinks=False)
        if (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError('verified staging directory replaced')
        _publish_exclusive_at(parent_fd, stage_name, target.name)
        named = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        if (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError('published directory differs from verified staging')
        if verifier.verify_artifact(root, target) != report:
            raise ValueError('published replay changed')
        return target
    finally:
        # Retain owned failed staging for evidence; never delete a replaceable path.
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
