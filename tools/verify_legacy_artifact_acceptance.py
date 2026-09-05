#!/usr/bin/env python3
"""Verify frozen historical identities; never execute or replace ROM verifiers."""
from __future__ import annotations

import argparse
import base64
import binascii
import gzip
import hashlib
import io
import json
import os
import stat
from pathlib import Path, PurePosixPath
import shlex
from typing import Any

try:
    from tools.legacy_artifact_acceptance_contract import BUNDLE_IDENTITIES
except ModuleNotFoundError:  # Direct script execution.
    from legacy_artifact_acceptance_contract import BUNDLE_IDENTITIES

COVERAGE = 'sequel/rom-byte-coverage.json'
PROOF = 'sequel/reverse-engineering-proof.json'
PREFIX = 'notes/evidence/rom-evidence-selector-repair-20260905/'
FORMAL = PREFIX + 'formal-report.json'
GUARD = PREFIX + 'formal-guard.json'
AUDITOR = 'tools/audit_rom_byte_coverage.py'
FORMAL_AUDITOR = 'tools/audit_reverse_engineering_proof.py'
MAX_EXPANDED_BYTES = 160 * 1024 * 1024


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def safe_path(path: str) -> None:
    require(isinstance(path, str) and bool(path), 'empty/nonstring path')
    pure = PurePosixPath(path)
    require(not pure.is_absolute() and str(pure) == path and
            all(p not in ('.', '..') for p in pure.parts) and
            not any(c in path for c in ('\\', '\x00', '\n', '\r')), 'unsafe path: '+path)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: '+key)
        result[key] = value
    return result


def parse(raw: bytes) -> Any:
    def invalid(value: str) -> None:
        raise ValueError('invalid JSON constant: '+value)
    try:
        return json.loads(raw, object_pairs_hook=_object, parse_constant=invalid)
    except (UnicodeError, TypeError) as error:
        raise ValueError('invalid JSON') from error


def _inflate(raw: bytes, limit: int = MAX_EXPANDED_BYTES) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            expanded = stream.read(limit+1)
    except (OSError, EOFError) as error:
        raise ValueError('invalid gzip') from error
    require(len(expanded) <= limit, 'gzip expansion limit exceeded')
    return expanded


def decode_snapshot(raw: bytes) -> dict[str, tuple[str, bytes]]:
    document = parse(_inflate(raw))
    require(isinstance(document, dict) and set(document) == {'schema', 'files'} and
            document['schema'] == 'legacy-artifact-snapshot-v1' and
            isinstance(document['files'], dict), 'snapshot schema mismatch')
    files = {}
    for path, row in document['files'].items():
        safe_path(path)
        require(isinstance(row, dict) and set(row) == {'mode', 'data_base64'} and
                row['mode'] in ('100644', '100755') and
                isinstance(row['data_base64'], str), 'invalid snapshot member')
        try:
            value = base64.b64decode(row['data_base64'], validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError('invalid base64 member') from error
        require(base64.b64encode(value).decode('ascii') == row['data_base64'],
                'noncanonical base64 member')
        files[path] = (row['mode'], value)
    return files


def identities(files: dict[str, tuple[str, bytes]]) -> dict[str, dict[str, Any]]:
    return {p: {'mode': mode, 'size': len(raw), 'sha256': sha(raw)}
            for p, (mode, raw) in sorted(files.items())}


def _pointer(value: Any, pointer: str) -> Any:
    require(isinstance(pointer, str) and pointer.startswith('/'), 'invalid selector')
    try:
        for token in pointer[1:].split('/'):
            token = token.replace('~1', '/').replace('~0', '~')
            if isinstance(value, list):
                require(token.isdigit() and str(int(token)) == token, 'invalid list selector')
                value = value[int(token)]
            else:
                value = value[token]
        return value
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError('unresolved evidence selector: '+pointer) from error


def _command(command: list[str]) -> tuple[str, ...]:
    require(isinstance(command, list) and len(command) >= 2 and
            all(isinstance(s, str) and s for s in command), 'invalid verifier command')
    require(PurePosixPath(command[0]).name.startswith('python'), 'unexpected interpreter')
    _script(tuple(command[1:]))
    # Only the interpreter location varies in the recorded formal execution.
    return tuple(command[1:])


def _script(key: tuple[str, ...]) -> str:
    offset = 2 if key[:2] == ('-I', '-S') else 0
    require(len(key) > offset and key[offset].startswith('tools/') and
            key[offset].endswith('.py'), 'unexpected Python flags or script')
    safe_path(key[offset])
    return key[offset]


def inspect_snapshot(files: dict[str, tuple[str, bytes]], root_names: list[str]) -> dict[str, Any]:
    """Reconstruct bridges from archived bytes without importing the producer."""
    require(isinstance(root_names, list) and len(root_names) == len(set(root_names)) and
            bool(root_names), 'duplicate/empty root denominator')
    for path, (mode, value) in files.items():
        safe_path(path)
        require(mode in ('100644', '100755') and isinstance(value, bytes), 'nonregular member')
    for root in root_names:
        safe_path(root)
        require(len(PurePosixPath(root).parts) == 2 and root.startswith('artifacts/'),
                'invalid artifact root')

    def raw(path: str) -> bytes:
        require(path in files, 'missing snapshot member: '+path)
        return files[path][1]

    input_ids = identities(files)
    parsed = {}

    def document(path: str) -> Any:
        if path not in parsed:
            parsed[path] = parse(raw(path))
        return parsed[path]

    def identity(path: str, expected: str) -> None:
        raw(path)
        require(isinstance(expected, str) and len(expected) == 64 and input_ids[path]['sha256'] == expected,
                'identity mismatch: '+path)

    coverage, proof, formal, guard = [document(p) for p in (COVERAGE, PROOF, FORMAL, GUARD)]
    raw(FORMAL_AUDITOR)
    require(coverage['schema'] == 'rom-byte-coverage-v1' and
            formal['schema'] == 'reverse-engineering-proof-audit-v2', 'evidence schema mismatch')
    require(formal['trust_anchor']['spec_sha256'] == sha(raw(PROOF)), 'formal/proof identity mismatch')
    require(formal['trust_anchor']['verified'] is False and
            formal['trust_anchor']['externally_supplied'] is False,
            'historical external trust status changed')
    gate = proof['gates']['rom_byte_coverage']
    coverage_evidence = [e for e in gate['evidence'] if e.get('path') == COVERAGE]
    require(len(coverage_evidence) == 1, 'coverage evidence denominator mismatch')
    identity(COVERAGE, coverage_evidence[0]['sha256'])
    require(proof['base_rom'] == coverage['base_rom'], 'ROM identity mismatch')
    require(type(guard['exit_code']) is int and guard['exit_code'] == 0 and
            guard['degraded'] is False and guard['reason'] == 'completed', 'failed/degraded guard')
    require(guard['command'][:2] == ['/bin/sh', '-c'] and len(guard['command']) == 3,
            'unexpected guard command')
    command = shlex.split(guard['command'][2])
    prefix = ['python3', '-u', FORMAL_AUDITOR, '--root', '.', '--spec', PROOF,
              '--execute-verifiers', '--allow-incomplete', '--output']
    require(command[:len(prefix)] == prefix and len(command) == len(prefix)+4 and
            PurePosixPath(command[len(prefix)]).name == 'formal-report.json' and
            command[len(prefix)+1] == '>' and
            PurePosixPath(command[len(prefix)+2]).name == 'formal.log' and command[-1] == '2>&1',
            'guard does not bind the formal invocation')
    executed = {}
    for row in formal['verifiers_executed']:
        key = _command(row['command'])
        require(key not in executed and row['contract_ok'] is True and
                type(row['exit_code']) is int and row['exit_code'] == 0,
                'duplicate or failed formal verifier')
        executed[key] = row
    specs = gate['verifiers']
    keys = [_command(v['command']) for v in specs]
    require(len(set(keys)) == len(keys), 'duplicate proof verifier')
    for spec, key in zip(specs, keys):
        identity(_script(key), spec['script_sha256'])
        require(key in executed and spec['contract']['format'] == 'json' and
                bool(spec['contract']['assertions']), 'missing structured verifier receipt')
    audits = [v for v in specs if _command(v['command']) == (AUDITOR, '--root', '.')]
    require(len(audits) == 1 and executed[(AUDITOR, '--root', '.')].get('execution') == 'reused-in-process',
            'aggregate audit execution denominator mismatch')
    gate_result = formal['gate_results']['rom_byte_coverage']
    require(gate_result['evidence_valid'] is True and
            gate_result['contracted_verifier_count'] == len(specs) and
            gate_result['hash_bound_verifier_count'] == len(specs), 'ROM gate receipt mismatch')
    audit = gate_result['rom_coverage_audit']
    require(audit['verified'] is True and audit['errors'] == [] and
            audit['summary'] == coverage['summary'] and
            audit['state_inventory_complete'] is coverage['state_inventory_complete'] is True and
            audit['semantic_classification_complete'] is coverage['semantic_classification_complete'] is False,
            'formal/coverage summary or status mismatch')
    for pointer, expected in audits[0]['contract']['assertions'].items():
        actual = _pointer(audit, pointer)
        require(type(actual) is type(expected) and actual == expected, 'aggregate contract assertion mismatch')
    require(formal['complete'] is False and bool(formal['blockers']), 'historical completion status changed')

    result = {}
    claims = coverage['claims']
    require(len({c['id'] for c in claims}) == len(claims), 'duplicate coverage claim')
    for root in sorted(root_names):
        members = {p[len(root)+1:]: receipt for p, receipt in input_ids.items() if p.startswith(root+'/')}
        manifest = document(root+'/manifest.json')
        direct = [i for i, key in enumerate(keys) if any(
            arg == root or arg.startswith(root+'/') for arg in key[1:])]
        for index in direct:
            require(specs[index]['contract']['assertions'].get('/verified') is True,
                    'direct bridge lacks explicit success contract')
        owned = [c for c in claims if c.get('promotion_manifest_path') == root+'/manifest.json' or
                 str(c.get('evidence_path', '')).startswith(root+'/')]
        gz = [name for name in members if name.endswith('.gz')]
        baseline_binding = None
        claim_verifiers = {}
        if gz:
            require(len(gz) == 1 and not owned and not direct, 'ambiguous baseline bridge')
            name = gz[0]
            require(set(members) == {'manifest.json', name}, 'baseline member denominator mismatch')
            if 'coverage' in manifest:
                archived = manifest['coverage']['archive']; expanded = manifest['coverage']['raw']
                require(archived['file'] == name, 'baseline archive path mismatch')
            else:
                archived = manifest['files'][name]
                expanded = {'sha256': archived['uncompressed_sha256'], 'size': archived['uncompressed_size']}
            require(archived['compression'] == 'gzip', 'baseline compression mismatch')
            identity(root+'/'+name, archived['sha256'])
            packed = raw(root+'/'+name)
            require(type(archived['size']) is int and archived['size'] == len(packed), 'archive size mismatch')
            require(type(expanded['size']) is int and 0 <= expanded['size'] <= MAX_EXPANDED_BYTES,
                    'invalid baseline raw size')
            unpacked = _inflate(packed, expanded['size'])
            require(len(unpacked) == expanded['size'] and sha(unpacked) == expanded['sha256'],
                    'baseline raw identity mismatch')
            baseline_binding = {'archive_path': root+'/'+name, 'archive_sha256': sha(packed),
                                'archive_size': len(packed), 'raw_sha256': sha(unpacked),
                                'raw_size': len(unpacked), 'per_root_semantic_verifier': False}
            kind = 'immutable_precoverage_binding'
        else:
            require(bool(direct or owned), 'root has no historical evidence bridge: '+root)
            kind = 'direct_proof_verifier' if direct else 'aggregate_coverage_verifier'
            for claim in owned:
                for path_key, hash_key in [('promotion_manifest_path', 'promotion_manifest_sha256'),
                                           ('evidence_path', 'evidence_sha256')]:
                    if claim.get(path_key) and str(claim[path_key]).startswith(root+'/'):
                        identity(claim[path_key], claim[hash_key])
                if claim.get('evidence_selector'):
                    _pointer(document(claim['evidence_path']), claim['evidence_selector'])
                path = claim.get('independent_verifier_path')
                if kind == 'aggregate_coverage_verifier':
                    require(bool(path), 'aggregate claim missing independent verifier')
                if path:
                    identity(path, claim['independent_verifier_sha256'])
                    receipt = {'path': path, 'sha256': claim['independent_verifier_sha256'],
                               'report_sha256': claim.get('independent_verifier_report_sha256')}
                    if receipt['report_sha256'] is not None:
                        h = receipt['report_sha256']
                        require(isinstance(h, str) and len(h) == 64 and all(c in '0123456789abcdef' for c in h),
                                'invalid claim verifier report identity')
                    claim_verifiers[json.dumps(receipt, sort_keys=True)] = receipt
        result[root] = {'members': members, 'bridge_kind': kind,
                        'proof_verifier_indices': direct,
                        'coverage_claim_ids': [c['id'] for c in owned],
                        'claim_verifiers': [claim_verifiers[k] for k in sorted(claim_verifiers)],
                        'baseline_binding': baseline_binding}
    return {'roots': result, 'summary': {
        'root_count': len(result), 'member_count': sum(len(r['members']) for r in result.values()),
        'bridge_counts': {k: sum(r['bridge_kind'] == k for r in result.values()) for k in
                          ('direct_proof_verifier', 'aggregate_coverage_verifier', 'immutable_precoverage_binding')},
        'formal_contracts': len(executed), 'rom_contracts': len(specs),
        'classified_bytes': coverage['summary']['classified_bytes'],
        'unknown_bytes': coverage['summary']['unknown_bytes'],
        'newly_classified_bytes': 0, 'semantic_verifiers_reexecuted': False,
        'global_complete': False, 'global_blockers': len(formal['blockers']),
        'external_trust_anchor_verified': False}}


def verify_archive(catalog_raw: bytes, snapshot_raw: bytes) -> dict[str, Any]:
    catalog = parse(catalog_raw)
    require(isinstance(catalog, dict) and set(catalog) == {'schema', 'input_files', 'roots', 'summary'} and
            catalog['schema'] == 'legacy-artifact-acceptance-catalog-v1', 'catalog schema mismatch')
    files = decode_snapshot(snapshot_raw)
    require(catalog['input_files'] == identities(files), 'snapshot input inventory mismatch')
    try:
        inspected = inspect_snapshot(files, list(catalog['roots']))
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('malformed historical evidence') from error
    require(inspected['roots'] == catalog['roots'] and inspected['summary'] == catalog['summary'],
            'historical bridge or member denominator mismatch')
    return {'schema': 'legacy-artifact-acceptance-verification-v1', 'verified': True,
            'contract_ok': True, 'artifact_status': 'candidate', 'summary': inspected['summary'],
            'catalog_sha256': sha(catalog_raw), 'snapshot_sha256': sha(snapshot_raw),
            'authorizations': {r: v['members'] for r, v in inspected['roots'].items()}}


def verify_bundle_members(members: dict[str, tuple[str, bytes]]) -> dict[str, Any]:
    """Only a code-pinned complete package can authorize historical roots."""
    require(bool(BUNDLE_IDENTITIES) and identities(members) == BUNDLE_IDENTITIES,
            'frozen acceptance bundle identity mismatch')
    report = verify_archive(members['catalog.json'][1], members['snapshot.json.gz'][1])
    report['artifact_status'] = 'accepted'
    return report


def read_bundle(directory: Path) -> dict[str, tuple[str, bytes]]:
    require(not directory.is_symlink() and directory.is_dir(), 'nonregular bundle directory')
    members = {}
    for path in sorted(directory.iterdir()):
        require(not path.is_symlink() and path.is_file(), 'nonregular bundle member')
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, 'rb') as stream:
            metadata = os.fstat(stream.fileno())
            require(stat.S_ISREG(metadata.st_mode), 'nonregular bundle member')
            members[path.name] = ('100755' if metadata.st_mode & 0o111 else '100644', stream.read())
    return members


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify_bundle_members(read_bundle(args.artifact))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'verified': False, 'error': str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
