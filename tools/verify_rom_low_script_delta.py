#!/usr/bin/env python3
"""Independently replay six frozen low-script consumers and two records."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from tools import verify_rom_fixed_renderer_script_records as legacy

SCHEMA = 'rom-low-script-delta-v1'
PAYLOAD_NAME = 'rom-low-script-delta.json'
MANIFEST_NAME = 'manifest.json'
POOLS = ((0x578C, 0x7554), (0x42AB, 0x542E), (0xCEA, 0x12F0))
VECTOR_SHA = 'b86267ae723b37f23a45fb11182a2931d02c9788c37ea6d5499653eeb6fd8359'
HELPERS = {
    'tools/verify_rom_fixed_renderer_script_records.py': 'c7f3eeaabc4a6755c7974838084aa7495f866924e40fd4ea2bb072d5db7f3927',
    'tools/export_rom_fixed_renderer_script_records.py': '1d0e785c87e0c5c71869ceffeecb54ef052f43d03a542c369ce66ced790dce21',
    'tools/export_rom_training_text_script_inventory.py': '97f8c8c6c6b18f52dd099939dd2342a610a62af663f582558d6c341eb55b4d10',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def check_inputs(root):
    for relative, digest in HELPERS.items():
        if sha(legacy._safe_file(root, Path(relative)).read_bytes()) != digest:
            raise ValueError('reused helper identity changed')
    # Check on every call, including when the legacy CFG loader is cached.
    for relative, digest in legacy.CFG_UPSTREAM:
        if sha(legacy._safe_file(root, relative).read_bytes()) != digest:
            raise ValueError('CFG upstream identity changed')


def rebuild(root, rom):
    check_inputs(root)
    if len(rom) != legacy.ROM_SIZE or sha(rom) != legacy.ROM_SHA256:
        raise ValueError('ROM identity changed')
    blocks, cfg = legacy._cfg_blocks(root)
    rows = []
    for block in blocks:
        if block.get('mode') != 'thumb':
            continue
        lo, hi = block['range']
        for site in range(lo, hi, 2):
            half = int.from_bytes(rom[site:site + 2], 'little')
            if half >> 11 != 9:
                continue
            literal = ((site + 4) & ~3) + (half & 255) * 4
            target = int.from_bytes(rom[literal:literal + 4], 'little') - legacy.ROM_BASE
            if not any(a <= target < b for a, b in POOLS):
                continue
            sink = legacy._prove_parameter_flow(rom, site, (half >> 8) & 7)
            rows.append({'site': site, 'target': target, 'literal_word': literal,
                         'interpreter_callsite': sink, 'path_sha256': sha(rom[site:sink + 4]),
                         'accepted': target != 0x42BD})
    rows.sort(key=lambda r: r['site'])
    vector = [[r['site'], r['target'], r['interpreter_callsite'], r['path_sha256']] for r in rows]
    if len(rows) != 6 or len({r['site'] for r in rows}) != 6 or sha(json.dumps(vector, separators=(',', ':')).encode()) != VECTOR_SHA:
        raise ValueError('consumer denominator changed')
    for a, b, digest in [legacy.INTERPRETER, legacy.PARSER, legacy.SJIS]:
        if sha(rom[a:b]) != digest:
            raise ValueError('parser semantics changed')
    ranges = tuple((struct.unpack_from('<H', rom, at)[0],
                    struct.unpack_from('<H', rom, at)[0] + rom[at + 2])
                   for at in range(0x53D644, 0x53D73C, 8))
    records = []
    for start, end, ops in [(0x42B5, 0x42BD, [1, 0]), (0x42C2, 0x42C6, [3, 4, 0])]:
        if legacy._parse(rom, start, 0x542E, ranges) != (end, ops):
            raise ValueError('record boundary changed')
        records.append({'range': [start, end], 'opcode_sequence': ops, 'bytes_sha256': sha(rom[start:end])})
    try:
        legacy._parse(rom, 0x42BD, 0x542E, ranges)
    except ValueError as error:
        if str(error) != 'unsupported opcode 2':
            raise ValueError('excluded root reason changed') from error
    else:
        raise ValueError('excluded root unexpectedly accepted')
    claims = [{'id': f'low-script-delta-{r["range"][0]:04x}', 'range': r['range'],
               'primary_class': legacy.PRIMARY_CLASS, 'claim_kind': legacy.CLAIM_KIND,
               'bytes_sha256': r['bytes_sha256']} for r in records]
    return {'schema': SCHEMA, 'rom_sha256': legacy.ROM_SHA256,
            'helper_inputs': HELPERS, 'upstream_cfg_contract': cfg,
            'upstream_training_contract': legacy._upstream(root),
            'pool_denominator': [list(p) for p in POOLS], 'consumers': rows,
            'consumer_vector_sha256': VECTOR_SHA, 'records': records, 'excluded_roots': [0x42BD],
            'promotion': {'claims': claims, 'claim_count': 2, 'promotion_bytes': 12,
                          'promotion_batch': SCHEMA, 'promoted_from_primary_class': 'unknown'},
            'scope': {'whole_rom_consumer_denominator': False, 'natural_runtime_reachability': False,
                      'context_lifecycle_closed': False, 'padding_or_free_space': False,
                      'editing_or_relocation_safety': False, 'new_opcode_semantics': False}}


def expected_manifest(root, relative, raw, *, accepted=True):
    scripts = ['tools/export_rom_low_script_delta.py', 'tools/verify_rom_low_script_delta.py',
               'tests/test_rom_low_script_delta.py']
    return {'schema': 'git-artifact-promotion-v1', 'artifact_schema': SCHEMA,
            'artifact_status': 'accepted' if accepted else 'candidate', 'files': {PAYLOAD_NAME: {'size': len(raw), 'sha256': sha(raw)}},
            'summary': {'consumer_site_count': 6, 'accepted_site_count': 4, 'record_count': 2, 'promotion_bytes': 12},
            'producer': {'command': ['python3', scripts[0], '--root', '.', '--output', relative]},
            'verifier': {'command': ['python3', scripts[1], '--root', '.', '--artifact', relative],
                         **({'exit_code': 0} if accepted else {})},
            'implementation': {key: sha(legacy._safe_file(root, Path(p)).read_bytes())
                               for key, p in zip(['exporter_sha256', 'verifier_sha256', 'test_sha256'], scripts)}}


def verify_artifact(root, artifact, *, allow_candidate=False):
    try:
        root = root.resolve(strict=True)
        directory = legacy._safe_artifact(root, artifact)
        if {p.name for p in directory.iterdir()} != {PAYLOAD_NAME, MANIFEST_NAME} or any(p.is_symlink() for p in directory.iterdir()):
            raise ValueError('artifact members changed')
        raw = (directory / PAYLOAD_NAME).read_bytes()
        mr = (directory / MANIFEST_NAME).read_bytes()
        payload, manifest = json.loads(raw), json.loads(mr)
        if raw != canonical(payload) or mr != canonical(manifest):
            raise ValueError('noncanonical JSON')
        if payload != rebuild(root, legacy._safe_file(root, legacy.ROM_PATH).read_bytes()):
            raise ValueError('payload contract changed')
        accepted = manifest.get('artifact_status') == 'accepted'
        if not accepted and not allow_candidate:
            raise ValueError('candidate not accepted')
        if manifest != expected_manifest(root, directory.relative_to(root).as_posix(), raw, accepted=accepted):
            raise ValueError('manifest contract changed')
        return {'verified': True, 'contract_ok': True, 'errors': [], 'record_count': 2, 'promotion_bytes': 12}
    except Exception as error:
        return {'verified': False, 'contract_ok': False, 'errors': [str(error)]}


def project_unknown_claims(root, artifact, segments):
    """Coverage adapter for a verified packet; reject overlaps and missing coverage."""
    report = verify_artifact(root, artifact)
    if not report['verified']:
        raise ValueError(f'unverified delta: {report["errors"]}')
    cursor = 0
    for segment in segments:
        start, end = segment['range']
        if start != cursor or not start < end <= legacy.ROM_SIZE:
            raise ValueError('invalid coverage segment denominator')
        cursor = end
    if cursor != legacy.ROM_SIZE:
        raise ValueError('incomplete coverage segment denominator')
    directory = legacy._safe_artifact(root.resolve(strict=True), artifact)
    claims = json.loads((directory / PAYLOAD_NAME).read_bytes())['promotion']['claims']
    for claim in claims:
        start, end = claim['range']
        hits = [s for s in segments if s['range'][0] < end and start < s['range'][1]]
        if any(s['primary_class'] != 'unknown' for s in hits):
            raise ValueError('delta intersects classified bytes')
        if sum(min(end, s['range'][1]) - max(start, s['range'][0]) for s in hits) != end - start:
            raise ValueError('delta has missing unknown coverage')
    return claims


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--artifact', type=Path, required=True)
    args = p.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
