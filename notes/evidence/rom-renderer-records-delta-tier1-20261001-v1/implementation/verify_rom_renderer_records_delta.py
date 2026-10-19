#!/usr/bin/env python3
"""Independently rebuild the combined fixed-consumer renderer record delta."""
from __future__ import annotations

import argparse
from functools import lru_cache
import gzip
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import verify_rom_fixed_renderer_script_records as legacy
from tools._vendor.capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from tools.rom_small_cfg_callback_gaps_independent_verifier import canonical, sha, read_regular, read_pinned
from tools.verify_rom_cfg_proven_roots import verify_rom_cfg_proven_roots
from tools.verify_rom_cfg_proven_roots_v3 import verify_rom_cfg_proven_roots_v3
from tools.verify_rom_cfg_proven_roots_v6 import verify_rom_cfg_proven_roots_v6

CONTRACT = Path('tools/data/rom-renderer-records-delta-contract-v1.json')
CONTRACT_SHA = '59b4c53393c58fb0f3f25f78a3963908fe10984afa0e26036981dffaddc1eec6'
SCHEMA = 'rom-renderer-records-delta-v1'
PAYLOAD = 'rom-renderer-records-delta.json'
PRECOVERAGE = Path('notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-after.json.gz')
ARTIFACT = Path('artifacts/rom-renderer-records-delta-v1')


def load_contract(root):
    raw = read_regular(root / CONTRACT)
    if sha(raw) != CONTRACT_SHA:
        raise ValueError('public contract identity changed')
    contract = json.loads(raw)
    for identity in contract['inputs']:
        read_pinned(root, identity)
    return contract


def precoverage(root, contract):
    raw = gzip.decompress(read_regular(root / contract['precoverage']['path']))
    if sha(raw) != contract['precoverage']['raw_sha256']:
        raise ValueError('immutable precoverage identity changed')
    segments = json.loads(raw)['segments']
    validate_segments(segments)
    return segments


def validate_segments(segments):
    cursor = 0
    for segment in segments:
        start, end = segment['range']
        if type(start) is not int or type(end) is not int or start != cursor or not start < end <= legacy.ROM_SIZE:
            raise ValueError('invalid coverage segment denominator')
        cursor = end
    if cursor != legacy.ROM_SIZE:
        raise ValueError('incomplete coverage segment denominator')


def assert_unknown(claims, segments):
    validate_segments(segments)
    for row in claims:
        a, b = row['range']
        hits = [s for s in segments if s['range'][0] < b and a < s['range'][1]]
        if any(s['primary_class'] != 'unknown' for s in hits):
            raise ValueError('record intersects classified bytes')
        if sum(min(b, s['range'][1]) - max(a, s['range'][0]) for s in hits) != b - a:
            raise ValueError('record has missing unknown coverage')


@lru_cache(maxsize=1)
def verified_sources(root):
    # Caller rechecks every frozen input before accessing this cache.
    contract = load_contract(root)
    base, base_report = legacy._cfg_blocks(root)
    groups = [('inventory-v2-v3', base)]
    reports = {'inventory-v2-v3': base_report}
    for label, path, verify in zip(['proven-roots-v1', 'proven-roots-v3', 'proven-roots-v6'],
                                    contract['later_cfg_payloads'],
                                    [verify_rom_cfg_proven_roots, verify_rom_cfg_proven_roots_v3,
                                     verify_rom_cfg_proven_roots_v6]):
        directory = (root / path).parent
        report = verify(root, directory)
        if not report['verified']:
            raise ValueError(f'source CFG rejected: {label}: {report}')
        reports[label] = report
        groups.append((label, json.loads(read_regular(root / path))['extension']['blocks']))
    return groups, reports


def exclusion(error):
    match = re.search(r'unsupported opcode (\d+)', str(error))
    if not match:
        raise ValueError(f'unexpected parser failure: {error}') from error
    return int(match.group(1))


def assemble(contract, consumers, records, source_reports):
    consumers.sort(key=lambda r: r['site'])
    records.sort(key=lambda r: r['range'])
    if consumers != contract['consumers'] or records != contract['records']:
        raise ValueError('consumer or record denominator changed')
    if len({r['site'] for r in consumers}) != len(consumers):
        raise ValueError('duplicate consumer site')
    if any(a['range'][1] > b['range'][0] for a, b in zip(records, records[1:])):
        raise ValueError('record ranges overlap')
    claims = [{'id': f'renderer-records-delta-{r["range"][0]:04x}', 'range': r['range'],
               'primary_class': legacy.PRIMARY_CLASS, 'claim_kind': legacy.CLAIM_KIND,
               'bytes_sha256': r['bytes_sha256']} for r in records]
    return {'schema': SCHEMA, 'public_contract_sha256': CONTRACT_SHA,
            'rom': {'sha256': legacy.ROM_SHA256, 'size': legacy.ROM_SIZE},
            'immutable_precoverage': contract['precoverage'], 'source_verification': source_reports,
            'consumers': consumers, 'records': records,
            'promotion': {'claims': claims, 'claim_count': len(claims),
                          'promotion_bytes': sum(b-a for a,b in (r['range'] for r in claims)),
                          'promotion_batch': SCHEMA, 'promoted_from_primary_class': 'unknown'},
            'scope': contract['scope']}


def rebuild(root, rom):
    root = Path(root).resolve(strict=True)
    contract = load_contract(root)
    if len(rom) != legacy.ROM_SIZE or sha(rom) != legacy.ROM_SHA256:
        raise ValueError('ROM identity changed')
    segments = precoverage(root, contract)
    unknown = [s['range'] for s in segments if s['primary_class'] == 'unknown']
    groups, reports = verified_sources(root)
    ranges = tuple((struct.unpack_from('<H', rom, at)[0],
                    struct.unpack_from('<H', rom, at)[0] + rom[at + 2])
                   for at in range(0x53D644, 0x53D73C, 8))
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    consumers, records = [], {}
    for source, blocks in groups:
        for block in blocks:
            if block.get('mode') != 'thumb':
                continue
            start, end = block['range']
            cursor = start
            for insn in engine.disasm(rom[start:end], start):
                if insn.address != cursor:
                    raise ValueError('instruction partition discontinuous')
                cursor += insn.size
                if insn.size != 2:
                    continue
                site = insn.address
                half = int.from_bytes(insn.bytes, 'little')
                if half >> 11 != 9:
                    continue
                literal = ((site + 4) & ~3) + (half & 255) * 4
                target = int.from_bytes(rom[literal:literal + 4], 'little') - legacy.ROM_BASE
                pool = next((p for p in contract['target_pools'] if p[0] <= target < p[1]), None)
                if pool is None or not any(a <= target < b for a,b in unknown):
                    continue
                sink = legacy._prove_parameter_flow(rom, site, (half >> 8) & 7)
                row = {'source': source, 'block_id': block['id'], 'site': site,
                       'literal_word': literal, 'target': target, 'interpreter_callsite': sink,
                       'path_sha256': sha(rom[site:sink + 4])}
                try:
                    stop, ops = legacy._parse(rom, target, pool[1], ranges)
                    row['accepted'] = True
                    records[target] = {'range': [target, stop], 'opcode_sequence': ops,
                                       'bytes_sha256': sha(rom[target:stop])}
                except ValueError as error:
                    row.update(accepted=False, excluded_opcode=exclusion(error))
                consumers.append(row)
            if cursor != end:
                raise ValueError('source block not fully decoded')
    payload = assemble(contract, consumers, list(records.values()), reports)
    assert_unknown(payload['promotion']['claims'], segments)
    return payload


def intended_manifest(root, raw, report=None):
    paths = ['tools/export_rom_renderer_records_delta.py', 'tools/verify_rom_renderer_records_delta.py',
             'tests/test_rom_renderer_records_delta.py']
    manifest = {'schema': 'git-artifact-promotion-v1', 'artifact_schema': SCHEMA,
                'artifact_status': 'candidate' if report is None else 'accepted',
                'public_contract_sha256': CONTRACT_SHA,
                'files': {PAYLOAD: {'size': len(raw), 'sha256': sha(raw)}},
                'implementation_inputs': [{'path': p, 'size': len(read_regular(root / p)),
                                           'sha256': sha(read_regular(root / p))} for p in paths]}
    if report is not None:
        manifest['verifier'] = {'command': ['python3', paths[1], '--root', '.',
                                           '--artifact-dir', ARTIFACT.as_posix()],
                                'exit_code': 0, 'report': report}
    return manifest


def verify_artifact(root, artifact, *, allow_candidate=False):
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact)
        directory = artifact if artifact.is_absolute() else root / artifact
        if '..' in directory.parts or not directory.is_relative_to(root):
            raise ValueError('unsafe artifact path')
        # read_regular rejects ancestor and leaf symlinks and special files.
        raw = read_regular(directory / PAYLOAD)
        mr = read_regular(directory / 'manifest.json')
        if {p.name for p in directory.iterdir()} != {PAYLOAD, 'manifest.json'}:
            raise ValueError('artifact member denominator changed')
        payload, manifest = json.loads(raw), json.loads(mr)
        if raw != canonical(payload) or mr != canonical(manifest):
            raise ValueError('artifact JSON not canonical')
        if payload != rebuild(root, read_regular(root / legacy.ROM_PATH)):
            raise ValueError('payload contract changed')
        report = {'verified': True, 'contract_ok': True, 'errors': [], 'consumer_count': 47,
                  'accepted_site_count': 34, 'excluded_site_count': 13, 'record_count': 29,
                  'promotion_bytes': 1668, 'natural_runtime_reachability': False,
                  'current_unknown_checked': False, 'immutable_unknown_projection_checked': True}
        accepted = manifest.get('artifact_status') == 'accepted'
        if not accepted and not allow_candidate:
            raise ValueError('candidate not accepted')
        if manifest != intended_manifest(root, raw, report if accepted else None):
            raise ValueError('manifest contract changed')
        return report
    except Exception as error:
        return {'verified': False, 'contract_ok': False, 'errors': [str(error)]}


def project_unknown_claims(root, artifact, segments):
    report = verify_artifact(root, artifact)
    if not report['verified']:
        raise ValueError(f'unverified packet: {report["errors"]}')
    directory = artifact if Path(artifact).is_absolute() else root / artifact
    claims = json.loads(read_regular(Path(directory) / PAYLOAD))['promotion']['claims']
    assert_unknown(claims, segments)
    return claims


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--artifact-dir', type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, sort_keys=True))
    return 0 if report['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
