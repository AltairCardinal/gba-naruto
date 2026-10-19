#!/usr/bin/env python3
"""Replay pinned local AI gates; never authorize table bytes or live indices.

The domains describe individual branch predicates with unchanged input bytes.
They do not compose across callees, loop exhaustion, indirect entry or RAM writes.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROM_SHA256 = '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
COVERAGE_SHA256 = 'b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
COVERAGE_PATH = 'notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-after.json.gz'
V2_INPUTS = {
    'artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json':
        'a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba',
    'artifacts/rom-cfg-proven-roots-v2/manifest.json':
        'a3683f3d21ec5a162b4cdb97c70b639ff261d9ff5e0f3bb4941848205bb4d9ca',
}
# Exact compare/branch, exhaustion and call points from instruction-only owners.
POINTS = {
    0x74240: ('ff28', 'battle-controller-cfg-thumb-0028-0741dc'),
    0x74242: ('01d0', 'battle-controller-cfg-thumb-0028-0741dc'),
    0x74244: ('0028', 'battle-controller-cfg-thumb-0028-0741dc'),
    0x74246: ('04d1', 'battle-controller-cfg-thumb-0028-0741dc'),
    0x74250: ('dfd9', 'battle-controller-cfg-thumb-0028-0741dc'),
    0x74254: ('f2f780ff', 'battle-controller-cfg-thumb-0028-0741dc'),
    0x7425A: ('10f0cdff', 'cfg-proven-roots-v2-producer-01-07425a'),
    0x74322: ('10d8', 'battle-controller-cfg-thumb-0030-0742e4'),
    0x74348: ('f2f706ff', 'battle-controller-cfg-thumb-0030-0742e4'),
    0x7434E: ('10f053ff', 'cfg-proven-roots-v2-producer-02-07434e'),
    0x8521E: ('002a', 'cfg-proven-roots-v2-thumb-0073-0851f8'),
    0x85220: ('0cd1', 'cfg-proven-roots-v2-thumb-0073-0851f8'),
    0x85306: ('fef7b5ff', 'cfg-proven-roots-v2-thumb-0076-085304'),
}
OWNER_KINDS = {
    'battle_controller_cfg_reachable_instruction_bytes',
    'cfg_proven_roots_v2_reachable_instruction_bytes',
    'cfg_proven_roots_v2_direct_thumb_bl_producer',
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_coverage(root: Path) -> dict:
    raw = gzip.decompress((root / COVERAGE_PATH).read_bytes())
    if sha256(raw) != COVERAGE_SHA256:
        raise ValueError('historical coverage identity changed')
    return json.loads(raw)


def point_owner(coverage: dict, offset: int) -> dict:
    size = len(bytes.fromhex(POINTS[offset][0]))
    rows = [row for row in coverage['claims'] if row['role'] == 'primary'
            and row['range'][0] <= offset and offset + size <= row['range'][1]]
    if len(rows) != 1:
        raise ValueError(f'unique instruction owner missing at {offset:06x}')
    return rows[0]


def check_points(coverage: dict, rom: bytes) -> list[dict]:
    result = []
    for offset, (raw_hex, owner_id) in POINTS.items():
        raw = bytes.fromhex(raw_hex)
        if rom[offset:offset + len(raw)] != raw:
            raise ValueError(f'gate opcode changed at {offset:06x}')
        owner = point_owner(coverage, offset)
        if (owner['id'] != owner_id or owner['claim_kind'] not in OWNER_KINDS
                or owner.get('instruction_only_claimed') is False):
            raise ValueError(f'instruction owner mismatch at {offset:06x}')
        result.append({'offset': offset, 'raw_hex': raw_hex, 'owner': owner})
    return result


def local_domain(gate: str) -> tuple[int, ...]:
    if gate == 'primary_selected_candidate':
        return tuple(value for value in range(256) if value not in (0, 255))
    if gate == 'secondary_selected_candidate':
        return tuple(range(256))
    if gate == 'planner_nonzero':
        return tuple(value for value in range(256) if value != 0)
    raise ValueError('unknown local gate')


def historical_bl_reference(root: Path) -> dict:
    payload = None
    for path, expected in V2_INPUTS.items():
        raw = (root / path).read_bytes()
        if sha256(raw) != expected:
            raise ValueError(f'historical producer identity changed: {path}')
        if path.endswith('rom-cfg-proven-roots-v2.json'):
            payload = json.loads(raw)
    denominator = payload['producer_denominator']
    producers = [row['file_offset'] for row in denominator['producers']
                 if row['target_file_offset'] == 0x851F8]
    return {
        'inputs': V2_INPUTS, 'target_offset': 0x851F8,
        'producer_offsets': producers, 'scan_range': denominator['scan']['range'],
        'original_all_targets_denominator_sha256': denominator['denominator_sha256'],
        'raw_scan_replayed_here': False,
        'scope': 'historical Thumb BL-only fixed-target scan; excludes other incoming modes',
    }


def analyze(root: Path, *, rom_bytes: bytes | None = None) -> dict:
    rom = (root / 'rom/base.gba').read_bytes() if rom_bytes is None else rom_bytes
    if sha256(rom) != ROM_SHA256:
        raise ValueError('ROM identity changed')
    coverage = read_coverage(root)
    points = check_points(coverage, rom)
    historical_bl = historical_bl_reference(root)
    gates = {}
    for gate in ('primary_selected_candidate', 'secondary_selected_candidate', 'planner_nonzero'):
        domain = local_domain(gate)
        gates[gate] = {'domain': list(domain), 'count': len(domain),
                       'minimum': min(domain), 'maximum': max(domain),
                       'first_above_7': next(value for value in domain if value > 7)}
    return {
        'schema': 'rom-ai-entry-local-domains-preflight-v1', 'verified': True,
        'rom_sha256': ROM_SHA256, 'historical_coverage_sha256': COVERAGE_SHA256,
        'scope': 'individual fixed-byte predicates only; no cross-callee or lifecycle composition',
        'points': points, 'gates': gates, 'known_planner_producers': [0x7425A, 0x7434E],
        'historical_planner_direct_bl_denominator': historical_bl,
        'incoming_producer_denominator_complete': False,
        'scorer_index_domain_closed': False, 'natural_runtime_reachability_proved': False,
        'promotion_bytes': 0, 'decision': 'keep_unknown',
        'deferred_obligations': [
            'all scorer/planner incoming producers',
            'loop exhaustion slot 13 state',
            'callee 0x067158 and planner intermediate side effects',
            'all CD writers/copies and controlling state lifecycle',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        report = analyze(args.root)
    except (OSError, ValueError, KeyError) as error:
        report = {'schema': 'rom-ai-entry-local-domains-preflight-v1',
                  'verified': False, 'promotion_bytes': 0, 'decision': 'keep_unknown',
                  'errors': [str(error)]}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
