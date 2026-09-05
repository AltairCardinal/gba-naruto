"""Reproduce committed evidence from an owned clean detached checkout."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

RUN = Path(__file__).resolve().parent
CLEAN = RUN / 'clean-checkout'
A = '47d9a60e668a5c3fe6e1123524864d21a2c93545'
B = '80faaebd2d441e94afbe7f0c7921609659f4d0fe'
sha = lambda raw: hashlib.sha256(raw).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=CLEAN)

assert git('rev-parse', 'HEAD').decode().strip() == A
assert not git('status', '--porcelain').strip()
subprocess.run(['git', 'switch', '--detach', B], cwd=CLEAN, check=True)
assert git('rev-parse', 'HEAD').decode().strip() == B
assert not git('status', '--porcelain').strip()
env = dict(os.environ)
env.pop('PYTHONPATH', None)
env['PYTHONDONTWRITEBYTECODE'] = '1'
bundle = 'artifacts/rom-legacy-acceptance-20260905-v1'
commands = [
    ('clean-b-tests', ['python3', '-m', 'unittest',
        'tests.test_staged_legacy_artifact_acceptance',
        'tests.test_verify_legacy_artifact_acceptance',
        'tests.test_rebuild_legacy_artifact_acceptance',
        'tests.test_coverage_evidence_selector_repairs.SelectorRepairCanonicalBindingTests',
        'tests.test_coverage_evidence_selector_repairs.SelectorRepairReceiptTests',
        'tests.test_rom_cfg_proven_roots_v21_coverage.PostStoryFourPacketCanonicalTests',
        'tests.test_rom_cfg_proven_roots_v21_coverage.PostStoryFourPacketProofSpecTests', '-v']),
    ('clean-b-bundle', ['python3', 'tools/verify_legacy_artifact_acceptance.py', '--artifact', bundle]),
    ('clean-b-rebuild', ['python3', 'tools/rebuild_legacy_artifact_acceptance.py', '--root', '.',
        '--catalog', bundle + '/catalog.json', '--output', str(RUN / 'clean-b-snapshot.json.gz')]),
]
results = []
for label, command in commands:
    done = subprocess.run(command, cwd=CLEAN, env=env, capture_output=True)
    for suffix, raw in (('.stdout', done.stdout), ('.stderr', done.stderr)):
        with (RUN / (label + suffix)).open('xb') as stream:
            stream.write(raw)
    assert done.returncode == 0, (label, done.stderr.decode(errors='replace'))
    results.append({'label': label, 'command': command, 'exit_code': done.returncode,
                    'stdout_sha256': sha(done.stdout), 'stderr_sha256': sha(done.stderr)})
report_raw = (RUN / 'clean-b-bundle.stdout').read_bytes()
assert sha(report_raw) == '42e1d5628834efdf871a175d20feeba66d915b63daae66d669ac710f9821577c'
report = json.loads(report_raw)
assert report['artifact_status'] == 'accepted' and report['verified'] is True
assert (RUN / 'clean-b-snapshot.json.gz').read_bytes() == (CLEAN / bundle / 'snapshot.json.gz').read_bytes()
tree = {}
for record in git('ls-tree', '-r', '-z', B).split(b'\0'):
    if not record:
        continue
    meta, path = record.split(b'\t', 1)
    mode, kind, oid = meta.decode().split()
    assert kind == 'blob'
    tree[path.decode()] = (mode, oid)
checked = []
for root, members in sorted(report['authorizations'].items()):
    assert {path[len(root)+1:] for path in tree if path.startswith(root + '/')} == set(members)
    for name, expected in sorted(members.items()):
        path = root + '/' + name
        mode, oid = tree[path]
        raw = git('cat-file', 'blob', oid)
        assert {'mode': mode, 'size': len(raw), 'sha256': sha(raw)} == expected, path
        checked.append(path)
assert len(report['authorizations']) == 64 and len(checked) == 160
authority_paths = [bundle, 'tools/check_staged_artifact_policy.py',
                   'tools/verify_legacy_artifact_acceptance.py',
                   'tools/legacy_artifact_acceptance_contract.py']
assert not git('diff', '--name-only', A, B, '--', *authority_paths).strip()
identities = {
    'rom/base.gba': '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b',
    'sequel/rom-byte-coverage.json': '1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6',
    'sequel/reverse-engineering-proof.json': 'c2862ea520a39432c94fa2634f2ae5650077738c9474aa96ca15d387a4857cbb',
    'tools/audit_rom_byte_coverage.py': 'e4c1f07efd2673d9229da8a7532d7874e615cbf1d7705ccd32171558df028509',
    'notes/evidence/rom-evidence-selector-repair-20260905/formal-report.json':
        'aa125c7e80ea4364522698c04557b3d6a819f77000c28c58871bc74cf13938bc',
}
for path, expected in identities.items():
    assert sha(git('cat-file', 'blob', tree[path][1])) == expected, path
assert not git('status', '--porcelain').strip()
receipt = {'status': 'clean_committed_evidence_verified', 'authority_commit': A,
    'evidence_commit': B, 'evidence_tree': git('rev-parse', B + '^{tree}').decode().strip(),
    'commands': results, 'independent_bundle_report_sha256': sha(report_raw),
    'snapshot_sha256': sha((RUN / 'clean-b-snapshot.json.gz').read_bytes()),
    'legacy_roots_verified': 64, 'legacy_git_members_verified': checked,
    'catalog_input_count': len(json.loads((CLEAN / bundle / 'catalog.json').read_bytes())['input_files']),
    'authority_unchanged_from_a': True, 'committed_identities': identities,
    'clean_checkout_status': 'clean', 'unknown_bytes': 87749, 'global_complete': False,
    'formal_contracts': 106, 'rom_contracts': 96, 'global_blockers': 175,
    'formal_reexecuted': False, 'formal_scope': 'Previously completed raw execution; exact committed inputs and receipts verified.'}
with (RUN / 'clean-b-receipt.json').open('x') as stream:
    json.dump(receipt, stream, sort_keys=True, indent=2)
    stream.write('\n')
print(json.dumps({k: v for k, v in receipt.items() if k not in ('commands', 'legacy_git_members_verified', 'committed_identities')}))
