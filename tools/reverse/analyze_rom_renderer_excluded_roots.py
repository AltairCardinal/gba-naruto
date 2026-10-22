#!/usr/bin/env python3
"""Pinned syntax candidates for five excluded renderer roots.

Opcode 7/8 widths are candidate rules supported by local advance shapes. This
report does not certify the complete handlers, opaque callees, wait-state RAM,
actual execution, or promotion. Keep the historical parser/artifact unchanged.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verify_rom_fixed_renderer_script_records import _rebuild, _renderer_end

ROM_SHA = '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
COVERAGE_SHA = 'b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
COVERAGE_PATH = 'notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-after.json.gz'
OLD_PAYLOAD = 'artifacts/rom-fixed-renderer-script-records-v1/rom-fixed-renderer-script-records.json'
PINNED = {
    OLD_PAYLOAD: '7b56a9a05d8ea7d78bddd68dba874f0c7cae2ae3fa5d1aa6c2ab3a3949ec7698',
    'tools/verify_rom_fixed_renderer_script_records.py':
        'c7f3eeaabc4a6755c7974838084aa7495f866924e40fd4ea2bb072d5db7f3927',
}
# Exact local pointer-load/advance/store witnesses; not a complete handler CFG.
POINTS = {
    0x67164: '0590', 0x675E4: '059c', 0x675E6: '6078', 0x675EE: 'a178',
    0x67F2C: '059b', 0x67F4E: '0333', 0x67F50: '0593',
    0x67F80: '059d', 0x67F82: '0335', 0x67F84: '0595',
    0x68090: '059d', 0x68092: '6878',
    0x68170: '059e', 0x68172: '0236', 0x68174: '0596',
    0x68190: '0598', 0x68192: '0230', 0x68194: '0590',
}
WIDTHS = {1: 7, 3: 2, 4: 1, 7: 3, 8: 2, 12: 1}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_candidate(data: bytes, start: int, limit: int,
                    ranges: tuple[tuple[int, int], ...]) -> tuple[int, list[int]]:
    if not 0 <= start < limit <= len(data):
        raise ValueError('invalid candidate bounds')
    cursor, opcodes = start, []
    while cursor < limit:
        opcode = data[cursor]
        opcodes.append(opcode)
        if opcode == 0:
            return cursor + 1, opcodes
        if opcode in WIDTHS:
            cursor += WIDTHS[opcode]
        elif opcode == 5:
            if cursor + 2 > limit:
                raise ValueError('truncated renderer command')
            cursor = _renderer_end(data, cursor + 2, limit, ranges)
        else:
            raise ValueError(f'unsupported candidate opcode {opcode}')
        if cursor > limit:
            raise ValueError('truncated fixed command')
    raise ValueError('record terminator missing')


def merged_ranges(rows: list[list[int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(rows):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return merged


def analyze(root: Path) -> dict:
    rom = (root / 'rom/base.gba').read_bytes()
    if sha(rom) != ROM_SHA:
        raise ValueError('ROM identity changed')
    for path, digest in PINNED.items():
        if sha((root / path).read_bytes()) != digest:
            raise ValueError(f'upstream identity changed: {path}')
    coverage_raw = gzip.decompress((root / COVERAGE_PATH).read_bytes())
    if sha(coverage_raw) != COVERAGE_SHA:
        raise ValueError('immutable coverage identity changed')
    coverage = json.loads(coverage_raw)
    witnesses = []
    for offset, hex_bytes in POINTS.items():
        size = len(bytes.fromhex(hex_bytes))
        if rom[offset:offset + size].hex() != hex_bytes:
            raise ValueError('local advance witness changed')
        owners = [row for row in coverage['claims'] if row['role'] == 'primary'
                  and row['range'][0] <= offset and offset + size <= row['range'][1]]
        if len(owners) != 1 or owners[0]['claim_kind'] not in {
                'cfg_reachable_instruction_bytes', 'cfg_v3_reachable_instruction_bytes'}:
            raise ValueError('local advance witness lacks instruction owner')
        witnesses.append({'offset': offset, 'bytes': hex_bytes, 'owner': owners[0]['id']})
    # Reuse the independent verifier's full block-derived 41-site denominator.
    rebuilt = _rebuild(rom, root)
    old = json.loads((root / OLD_PAYLOAD).read_bytes())
    if rebuilt['consumer_denominator'] != old['consumer_denominator']:
        raise ValueError('historical consumer denominator mismatch')
    excluded = [row for row in rebuilt['consumer_denominator']['sites'] if not row['accepted']]
    if len(excluded) != 5:
        raise ValueError('excluded denominator changed')
    sjis_base = 0x53D644
    ranges = tuple((int.from_bytes(rom[p:p + 2], 'little'),
                    int.from_bytes(rom[p:p + 2], 'little') + rom[p + 2])
                   for p in range(sjis_base, sjis_base + 31 * 8, 8))
    candidates = []
    for start in sorted({row['target'] for row in excluded}):
        end, opcodes = parse_candidate(rom, start, 0x1CD0, ranges)
        candidates.append({'range': [start, end], 'opcode_sequence': opcodes,
                           'bytes_sha256': sha(rom[start:end])})
    merged = merged_ranges([row['range'] for row in candidates])
    unknown_bytes = sum(max(0, min(end, segment['range'][1]) - max(start, segment['range'][0]))
                        for start, end in merged for segment in coverage['segments']
                        if segment['primary_class'] == 'unknown')
    return {
        'schema': 'rom-renderer-excluded-root-syntax-preflight-v1',
        'rom_sha256': ROM_SHA, 'immutable_coverage_sha256': COVERAGE_SHA,
        'upstream_files': PINNED, 'upstream_cfg_contract': rebuilt['upstream_cfg_contract'],
        'consumer_site_count': rebuilt['consumer_denominator']['site_count'],
        'consumer_denominator_scope': rebuilt['consumer_denominator']['denominator_scope'],
        'excluded_consumers': excluded, 'local_advance_witnesses': witnesses,
        'candidate_width_rules': {'7': 3, '8': 2},
        'candidates': candidates, 'candidate_merged_ranges': merged,
        'candidate_unique_bytes': sum(end - start for start, end in merged),
        'candidate_unknown_intersection_bytes': unknown_bytes,
        'promotion_bytes': 0, 'handler_semantics_closed': False,
        'opaque_callee_and_wait_state_invariants_proven': False,
        'natural_reachability_proven': False, 'tier1_accepted': False,
        'next_gate': 'Independently prove complete 7/8 handler consumption and continuation contract before packet acceptance.',
    }


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
