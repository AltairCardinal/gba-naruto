#!/usr/bin/env python3
"""Independently rebuild the fixed direct-display text delta."""
from __future__ import annotations

import argparse
from functools import lru_cache
import gzip
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.rom_display_text_parameter_flow import prove_parameter_flow
from tools.rom_small_cfg_callback_gaps_independent_verifier import canonical, sha, read_regular, read_pinned
from tools.verify_rom_fixed_consumer_text_inventory import _independent_renderer_end, _independent_sjis_ranges, _half, _thumb_call
from tools.verify_rom_cfg_inventory import _decode
from tools.verify_rom_renderer_records_delta import assert_unknown

CONTRACT = Path('tools/data/rom-display-text-delta-contract-v1.json')
CONTRACT_SHA = 'ca0f7e4e384fdaffd7c7ae5dd73da1c6ff9bcc9ff5d5a0f211a8810f5f76e390'
SCHEMA = 'rom-display-text-delta-v1'
PAYLOAD = 'rom-display-text-delta.json'
ARTIFACT = Path('artifacts/rom-display-text-delta-v1')
ROM_PATH = Path('rom/base.gba')


def load_contract(root):
    raw = read_regular(root / CONTRACT)
    if sha(raw) != CONTRACT_SHA:
        raise ValueError('public display contract identity changed')
    contract = json.loads(raw)
    for row in contract['inputs']:
        read_pinned(root, row)
    return contract


@lru_cache(maxsize=1)
def _precoverage(root):
    # Every caller rechecks all frozen inputs before using this cache.
    contract = load_contract(root)
    raw = gzip.decompress(read_regular(root / contract['precoverage']['path']))
    if sha(raw) != contract['precoverage']['raw_sha256']:
        raise ValueError('immutable precoverage identity changed')
    coverage = json.loads(raw)
    assert_unknown([], coverage['segments'])
    return coverage


@lru_cache(maxsize=1)
def _source_reports(root):
    contract = load_contract(root)
    reports = {}
    functions = {'inventory-v2': 'verify_rom_cfg_inventory',
                 'inventory-v3': 'verify_rom_cfg_inventory_v3',
                 'roots-v6': 'verify_rom_cfg_proven_roots_v6',
                 'roots-v17': 'verify_root', 'roots-v18': 'verify_root',
                 'battle-controller': 'verify_rom_battle_controller_cfg'}
    for source in contract['sources']:
        module = importlib.import_module(source['verifier_module'])
        directory = root / source['artifact_dir']
        report = getattr(module, functions[source['label']])(root, directory)
        if not report.get('verified') or report.get('errors'):
            raise ValueError(f"source CFG rejected: {source['label']}: {report}")
        reports[source['label']] = report
    if reports != contract['source_reports']:
        raise ValueError('source CFG report denominator changed')
    return reports


@lru_cache(maxsize=6)
def _source_ranges(root, path):
    source = json.loads(read_regular(root / path))
    blocks = source.get('blocks', source.get('extension', {}).get('blocks'))
    if blocks is not None:
        return tuple(tuple(b['range']) for b in blocks if b['mode'] == 'thumb')
    return tuple(tuple(r['range']) for r in source['promotion']['claims']
                 if r['kind'] == 'reachable_thumb_code')


def source_owner(root, contract, rom, row):
    coverage = _precoverage(root)
    claim = next(c for c in coverage['claims'] if c['id'] == row['claim_id'])
    if (claim['range'] != row['owner_range'] or claim['evidence_path'] != row['evidence_path']
            or 'reachable_instruction_bytes' not in claim['claim_kind']
            or not claim['primary_class'].endswith('reachable_thumb_code')):
        raise ValueError('source instruction owner changed')
    identities = {r['path']: r['sha256'] for r in contract['inputs']}
    if (claim['evidence_sha256'] != identities[row['evidence_path']]
            or claim['promotion_manifest_sha256'] != identities[claim['promotion_manifest_path']]
            or claim['independent_verifier_sha256'] != identities[claim['independent_verifier_path']]):
        raise ValueError('source claim evidence binding changed')
    a, b = claim['range']
    if sha(rom[a:b]) != claim['bytes_sha256']:
        raise ValueError('source instruction bytes changed')
    # Decode from actual verified CFG block/range starts, never a coarse envelope.
    addresses = {}
    for start, end in _source_ranges(root, row['evidence_path']):
        if start >= row['sink'] + 4 or end <= row['site']:
            continue
        cursor = start
        while cursor < end:
            instruction = _decode(rom, cursor, 'thumb')
            if not instruction['accepted'] or cursor + instruction['size'] > end:
                raise ValueError('source instruction partition changed')
            addresses[cursor] = instruction['size']
            cursor += instruction['size']
    expected = {at: 2 for at in range(row['site'], row['sink'], 2)}
    expected[row['sink']] = 4
    if any(addresses.get(at) != size for at, size in expected.items()):
        raise ValueError('source site/path is not CFG instruction membership')
    return claim['range']


def semantic_windows(contract, rom):
    for window in contract['semantic_windows']:
        a, b = window['range']
        if sha(rom[a:b]) != window['sha256']:
            raise ValueError('display bridge/parser semantics changed')
    # Bind source capture, forwarding and the parser target for both bridges.
    for at, half in ((0x66760, 0x4681), (0x66788, 0x4649),
                     (0x667A2, 0x1C06), (0x667B8, 0x1C31)):
        if _half(rom, at) != half:
            raise ValueError('display source forwarding changed')
    if any(_thumb_call(rom, at) != 0x6626C for at in (0x6678A, 0x667BA)):
        raise ValueError('display bridge target changed')


def assemble(contract, consumers, records, reports):
    consumers.sort(key=lambda r: r['site'])
    records.sort(key=lambda r: r['range'])
    if consumers != contract['consumers'] or records != contract['records']:
        raise ValueError('display consumer/record denominator changed')
    if reports != contract['source_reports']:
        raise ValueError('unverified source report')
    if (len({r['site'] for r in consumers}) != len(consumers)
            or any(a['range'][1] > b['range'][0] for a, b in zip(records, records[1:]))):
        raise ValueError('display site duplication or record overlap')
    claims = [{'id': f"display-text-delta-{r['range'][0]:06x}", 'range': r['range'],
               'primary_class': 'fixed_cfg_consumer_renderer_display_text',
               'claim_kind': 'fixed_cfg_consumer_renderer_display_text_bytes',
               'bytes_sha256': r['bytes_sha256']} for r in records]
    return {'schema': SCHEMA, 'public_contract_sha256': CONTRACT_SHA,
            'rom': contract['rom'], 'immutable_precoverage': contract['precoverage'],
            'source_verification': reports, 'consumers': consumers, 'records': records,
            'promotion': {'claims': claims, 'claim_count': len(claims),
                          'promotion_bytes': sum(r['range'][1] - r['range'][0] for r in claims),
                          'promotion_batch': SCHEMA, 'promoted_from_primary_class': 'unknown'},
            'scope': contract['scope']}


def rebuild(root, rom):
    root = Path(root).resolve(strict=True)
    contract = load_contract(root)
    if len(rom) != contract['rom']['size'] or sha(rom) != contract['rom']['sha256']:
        raise ValueError('ROM identity changed')
    semantic_windows(contract, rom)
    reports = _source_reports(root)
    consumers = []
    for row in contract['consumers']:
        owner = source_owner(root, contract, rom, row)
        proof = prove_parameter_flow(rom, site=row['site'], sink=row['sink'],
                                     target=row['target'], owner_range=owner)
        consumers.append({key: proof[key] if key in proof else row[key] for key in row})
    ranges = _independent_sjis_ranges(rom)
    records = []
    for row in contract['records']:
        start = row['range'][0]
        end = _independent_renderer_end(rom, start, row['limit'], ranges)
        records.append({'range': [start, end], 'limit': row['limit'],
                        'bytes_sha256': sha(rom[start:end]), 'nul_inclusive': True})
    payload = assemble(contract, consumers, records, reports)
    assert_unknown(payload['promotion']['claims'], _precoverage(root)['segments'])
    return payload


def intended_manifest(root, raw, report=None):
    paths = ['tools/export_rom_display_text_delta.py', 'tools/verify_rom_display_text_delta.py',
             'tools/rom_display_text_parameter_flow.py', 'tests/test_rom_display_text_delta.py']
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
        directory = Path(artifact)
        directory = directory if directory.is_absolute() else root / directory
        if '..' in directory.parts or not directory.is_relative_to(root):
            raise ValueError('unsafe artifact path')
        raw = read_regular(directory / PAYLOAD)
        manifest_raw = read_regular(directory / 'manifest.json')
        if {p.name for p in directory.iterdir()} != {PAYLOAD, 'manifest.json'}:
            raise ValueError('artifact member denominator changed')
        payload, manifest = json.loads(raw), json.loads(manifest_raw)
        if raw != canonical(payload) or manifest_raw != canonical(manifest):
            raise ValueError('artifact JSON not canonical')
        if payload != rebuild(root, read_regular(root / ROM_PATH)):
            raise ValueError('display payload contract changed')
        report = {'verified': True, 'contract_ok': True, 'errors': [], 'consumer_count': 92,
                  'record_count': 85, 'promotion_bytes': 1053, 'source_verifier_count': 6,
                  'natural_runtime_reachability': False, 'current_unknown_checked': False,
                  'immutable_unknown_projection_checked': True}
        accepted = manifest.get('artifact_status') == 'accepted'
        if not accepted and not allow_candidate:
            raise ValueError('candidate not accepted')
        if manifest != intended_manifest(root, raw, report if accepted else None):
            raise ValueError('manifest contract changed')
        return report
    except Exception as error:
        return {'verified': False, 'contract_ok': False, 'errors': [str(error)]}


def project_unknown_claims(root, artifact, segments):
    root = Path(root).resolve(strict=True)
    report = verify_artifact(root, artifact)
    if not report['verified']:
        raise ValueError(f"unverified display packet: {report['errors']}")
    directory = Path(artifact)
    directory = directory if directory.is_absolute() else root / directory
    claims = json.loads(read_regular(directory / PAYLOAD))['promotion']['claims']
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
