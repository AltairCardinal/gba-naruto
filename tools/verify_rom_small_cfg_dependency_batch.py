#!/usr/bin/env python3
"""Verify publication identities and replay four independent raw CFG verifiers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import rom_small_cfg_dependency_packets as packets
from tools.rom_small_cfg_callback_gaps_independent_verifier import read_regular, read_pinned
from tools.experiment_workspace import PROMOTION_SCHEMA

CONTRACT = Path('tools/data/rom-small-cfg-dependency-publication-v1.json')
CONTRACT_SHA256 = '9f8390a6db4c32add3d723e57483f94b7f3d70cb5c483eb2cd6983818cd3fc6a'
ARTIFACT = Path('artifacts/rom-small-cfg-dependency-batch-v1')
PAYLOAD = 'rom-small-cfg-dependency-batch.json'
SCHEMA = 'rom-small-cfg-dependency-batch-v1'


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_contract(root):
    raw = read_regular(root / CONTRACT)
    if sha(raw) != CONTRACT_SHA256:
        raise ValueError('publication contract identity changed')
    contract = json.loads(raw)
    for pin in contract['inputs']:
        read_pinned(root, pin)
    return contract


def aggregate(packet_payloads, contract):
    if set(packet_payloads) != set(packets.PACKETS):
        raise ValueError('packet denominator changed')
    claims = []
    for key in packets.PACKETS:
        payload = packet_payloads[key]
        frozen = contract['packets'][key]
        promotion = payload['promotion']
        if (sha(canonical(payload)) != frozen['payload_sha256']
                or promotion['promotion_bytes'] != frozen['promotion_bytes']
                or promotion['claim_count'] != frozen['claim_count']):
            raise ValueError('packet payload identity changed')
        claims.extend({**row, 'packet': key, 'packet_claim_index': index}
                      for index, row in enumerate(promotion['claims']))
    claims.sort(key=lambda row: (row['range'], row['id']))
    if (len(claims) != 21 or sum(b-a for a,b in (r['range'] for r in claims)) != 118
            or len({r['id'] for r in claims}) != 21
            or any(a['range'][1] > b['range'][0] for a,b in zip(claims, claims[1:]))):
        raise ValueError('cross-packet range denominator changed')
    return {'schema': SCHEMA, 'publication_contract_sha256': CONTRACT_SHA256,
            'packets': packet_payloads, 'promotion': {'claims': claims,
            'claim_count': 21, 'promotion_bytes': 118}, 'scope': contract['scope']}


def intended_manifest(root, payload_raw, report=None):
    paths = ['tools/export_rom_small_cfg_dependency_batch.py',
             'tools/verify_rom_small_cfg_dependency_batch.py']
    tools = [{'path': path, 'sha256': sha(read_regular(root/path)),
              'size': len(read_regular(root/path))} for path in paths]
    manifest = {'schema': PROMOTION_SCHEMA,
                'artifact_status': 'candidate' if report is None else 'accepted',
                'files': {PAYLOAD: {'sha256': sha(payload_raw), 'size': len(payload_raw)}},
                'publication_contract_sha256': CONTRACT_SHA256,
                'implementation_inputs': tools}
    if report is not None:
        manifest['verifier'] = {'command': ['python3', paths[1], '--root', '.',
                                '--artifact-dir', ARTIFACT.as_posix()],
                                'exit_code': 0, 'report': report}
    return manifest


def verify_artifact(root, artifact, *, allow_candidate=False):
    root = Path(root).absolute()
    artifact = Path(artifact)
    if not artifact.is_absolute():
        artifact = root / artifact
    fd = None
    try:
        if '..' in artifact.parts or not artifact.is_relative_to(root):
            raise ValueError('unsafe artifact path')
        # read_regular anchors and rejects every symlink component.
        manifest_raw = read_regular(artifact/'manifest.json')
        payload_raw = read_regular(artifact/PAYLOAD)
        fd = os.open(artifact, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        identity = os.fstat(fd)
        if set(os.listdir(fd)) != {'manifest.json', PAYLOAD}:
            raise ValueError('artifact member denominator changed')
        contract = load_contract(root)
        payload = json.loads(payload_raw)
        reports = {}
        for key in packets.PACKETS:
            reports[key] = packets.verify_candidate(root, key, payload['packets'][key])
            if (not reports[key]['verified']
                    or sha(canonical(reports[key])) != contract['packets'][key]['report_sha256']):
                raise ValueError('independent packet verification changed')
        expected = aggregate(payload['packets'], contract)
        if canonical(expected) != payload_raw:
            raise ValueError('batch differs from independent packet reconstruction')
        report = {'schema': SCHEMA+'-verification-v1', 'verified': True,
                  'promotion_bytes': 118, 'claim_count': 21, 'packet_count': 4,
                  'payload_sha256': sha(payload_raw), 'packet_reports': reports,
                  'natural_runtime_reachability_claimed': False,
                  'full_upstream_lifecycle_replayed_here': False,
                  'canonical_promoted': False, 'errors': []}
        accepted = intended_manifest(root, payload_raw, report)
        candidate = intended_manifest(root, payload_raw)
        if manifest_raw != canonical(accepted) and not (
                allow_candidate and manifest_raw == canonical(candidate)):
            raise ValueError('publication manifest or verification receipt changed')
        load_contract(root)
        if (read_regular(artifact/'manifest.json') != manifest_raw
                or read_regular(artifact/PAYLOAD) != payload_raw):
            raise ValueError('artifact member changed during verification')
        named = os.stat(artifact, follow_symlinks=False)
        if (identity.st_dev, identity.st_ino) != (named.st_dev, named.st_ino):
            raise ValueError('artifact directory replaced')
        return report
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'schema': SCHEMA+'-verification-v1', 'verified': False, 'errors': [str(error)]}
    finally:
        if fd is not None:
            os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--artifact-dir', type=Path, default=ARTIFACT)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
