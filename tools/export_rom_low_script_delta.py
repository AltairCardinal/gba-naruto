#!/usr/bin/env python3
"""Export a frozen two-record delta using the existing renderer contract."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from tools import export_rom_fixed_renderer_script_records as legacy
from tools.export_rom_training_text_script_inventory import _parse_training_record, _sjis_ranges
from tools import verify_rom_low_script_delta as contract

PAYLOAD_NAME = contract.PAYLOAD_NAME
MANIFEST_NAME = contract.MANIFEST_NAME
canonical = contract.canonical


def build_from_rom(root, rom, *, verify_identity=True):
    root = root.resolve(strict=True)
    contract.check_inputs(root)
    if len(rom) != legacy.ROM_SIZE:
        raise ValueError('ROM size changed')
    blocks, cfg = legacy._cfg_blocks(root)
    rows = []
    for block in blocks:
        if block.get('mode') != 'thumb':
            continue
        start, end = block['range']
        for site in range(start, end, 2):
            half = struct.unpack_from('<H', rom, site)[0]
            if half & 0xF800 != 0x4800:
                continue
            literal = ((site + 4) & ~3) + 4 * (half & 255)
            target = struct.unpack_from('<I', rom, literal)[0] - legacy.ROM_BASE
            if not any(a <= target < b for a, b in contract.POOLS):
                continue
            sink = legacy._prove_parameter_flow(rom, site, (half >> 8) & 7)
            rows.append({'site': site, 'target': target, 'literal_word': literal,
                         'interpreter_callsite': sink, 'path_sha256': legacy._sha(rom[site:sink + 4]),
                         'accepted': target != 0x42BD})
    rows.sort(key=lambda r: r['site'])
    vector = [[r['site'], r['target'], r['interpreter_callsite'], r['path_sha256']] for r in rows]
    if len(rows) != 6 or len({r['site'] for r in rows}) != 6 or legacy._sha(json.dumps(vector, separators=(',', ':')).encode()) != contract.VECTOR_SHA:
        raise ValueError('consumer denominator changed')
    for interval, digest in [(legacy.INTERPRETER_RANGE, legacy.INTERPRETER_SHA256),
                             (legacy.PARSER_RANGE, legacy.PARSER_SHA256), (legacy.SJIS_RANGE, legacy.SJIS_SHA256)]:
        if legacy._sha(rom[interval[0]:interval[1]]) != digest:
            raise ValueError('parser semantics changed')
    sjis = _sjis_ranges(rom)
    records = []
    for start, end, ops in [(0x42B5, 0x42BD, [1, 0]), (0x42C2, 0x42C6, [3, 4, 0])]:
        parsed = _parse_training_record(rom, start, 0x542E, sjis)
        if (parsed['end'], parsed['opcode_sequence']) != (end, ops):
            raise ValueError('record boundary changed')
        records.append({'range': [start, end], 'opcode_sequence': ops, 'bytes_sha256': legacy._sha(rom[start:end])})
    # The unsupported root is deliberately not interpreted by a new grammar.
    if rom[0x42BD] != 2:
        raise ValueError('excluded root changed')
    if verify_identity and legacy._sha(rom) != legacy.ROM_SHA256:
        raise ValueError('ROM identity changed')
    claims = [{'id': f'low-script-delta-{r["range"][0]:04x}', 'range': r['range'],
               'primary_class': legacy.PRIMARY_CLASS, 'claim_kind': legacy.CLAIM_KIND,
               'bytes_sha256': r['bytes_sha256']} for r in records]
    return {'schema': contract.SCHEMA, 'rom_sha256': legacy.ROM_SHA256,
            'helper_inputs': contract.HELPERS, 'upstream_cfg_contract': cfg,
            'upstream_training_contract': legacy._upstream(root),
            'pool_denominator': [list(p) for p in contract.POOLS], 'consumers': rows,
            'consumer_vector_sha256': contract.VECTOR_SHA, 'records': records, 'excluded_roots': [0x42BD],
            'promotion': {'claims': claims, 'claim_count': 2, 'promotion_bytes': 12,
                          'promotion_batch': contract.SCHEMA, 'promoted_from_primary_class': 'unknown'},
            'scope': {'whole_rom_consumer_denominator': False, 'natural_runtime_reachability': False,
                      'context_lifecycle_closed': False, 'padding_or_free_space': False,
                      'editing_or_relocation_safety': False, 'new_opcode_semantics': False}}


def build_payload(root):
    return build_from_rom(root, legacy._safe_file(root, legacy.ROM_PATH).read_bytes())


def export_artifact(root, output):
    root = root.resolve(strict=True)
    output = output if output.is_absolute() else root / output
    try:
        relative = output.relative_to(root)
    except ValueError as error:
        raise ValueError('output escapes root') from error
    if '..' in relative.parts:
        raise ValueError('output traversal')
    cursor = root
    for part in relative.parts[:-1]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError('output symlink ancestor')
    parent = output.parent.resolve(strict=True)
    if not parent.is_relative_to(root):
        raise ValueError('output escapes root')
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    payload = build_payload(root)
    stage = Path(tempfile.mkdtemp(dir=parent, prefix=f'.{output.name}.'))
    try:
        raw = canonical(payload)
        (stage / PAYLOAD_NAME).write_bytes(raw)
        stage_relative = stage.relative_to(root).as_posix()
        (stage / MANIFEST_NAME).write_bytes(canonical(contract.expected_manifest(root, stage_relative, raw, accepted=False)))
        report = contract.verify_artifact(root, stage, allow_candidate=True)
        if not report['verified']:
            raise ValueError(f'independent replay rejected candidate: {report}')
        (stage / MANIFEST_NAME).write_bytes(canonical(contract.expected_manifest(root, stage_relative, raw)))
        if contract.verify_artifact(root, stage) != report:
            raise ValueError('accepted staging replay changed')
        (stage / MANIFEST_NAME).write_bytes(canonical(contract.expected_manifest(root, relative.as_posix(), raw)))
        for path in stage.iterdir():
            with path.open('rb') as handle:
                os.fsync(handle.fileno())
        fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        legacy._publish_exclusive(stage, output)
        if contract.verify_artifact(root, output) != report:
            raise ValueError('published replay changed')
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--output', type=Path, default=Path('artifacts/rom-low-script-delta-v1'))
    args = p.parse_args()
    export_artifact(args.root, args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
