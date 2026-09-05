"""Prepare a private Git tree only after the selector-repair formal has succeeded."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/Users/altair/github/gba-naruto-reverse')
RUN = Path(__file__).parent
RECEIPTS = 'notes/evidence/rom-evidence-selector-repair-20260905/'
OLD_RECEIPTS = 'notes/evidence/rom-post-story-four-packet-tier2-20260905/'
EXPECTED = {
    'sequel/rom-byte-coverage.json': '1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6',
    'sequel/reverse-engineering-proof.json': 'c2862ea520a39432c94fa2634f2ae5650077738c9474aa96ca15d387a4857cbb',
    'tools/audit_rom_byte_coverage.py': 'e4c1f07efd2673d9229da8a7532d7874e615cbf1d7705ccd32171558df028509',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args, env=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=env)


def write_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


assert not git('diff', '--cached', '--name-only').strip(), 'main index must remain empty'
for path, expected in EXPECTED.items():
    assert sha((ROOT/path).read_bytes()) == expected, path
assert sha((ROOT/OLD_RECEIPTS/'manifest.json').read_bytes()) == '6d67fe676550276bff5f13b044b9cc3657adacdba432472672e42ef5d222d7a5'
formal = json.loads((ROOT/RECEIPTS/'formal-report.json').read_bytes())
guard = json.loads((ROOT/RECEIPTS/'formal-guard.json').read_bytes())
assert guard['exit_code'] == 0 and guard['degraded'] is False and guard['reason'] == 'completed'
assert formal['trust_anchor']['spec_sha256'] == EXPECTED['sequel/reverse-engineering-proof.json']
assert len(formal['verifiers_executed']) == 106
assert all(v['exit_code'] == 0 and v['contract_ok'] is True for v in formal['verifiers_executed'])
gate = formal['gate_results']['rom_byte_coverage']
assert gate['evidence_valid'] is True and gate['contracted_verifier_count'] == 96
assert gate['rom_coverage_audit']['verified'] is True and gate['rom_coverage_audit']['errors'] == []
assert gate['rom_coverage_audit']['summary']['unknown_bytes'] == 87749
assert formal['complete'] is False

old_closure = json.loads((RUN/'commit-closure-candidate-v4.json').read_bytes())
paths = {r['path'] for r in old_closure['files']}
paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/RECEIPTS).rglob('*') if p.is_file())
paths.update({
    'tools/verify_legacy_artifact_acceptance.py', 'tools/legacy_artifact_acceptance_contract.py',
    'tools/rebuild_legacy_artifact_acceptance.py', 'tools/check_staged_artifact_policy.py',
    'tests/test_verify_legacy_artifact_acceptance.py', 'tests/test_staged_legacy_artifact_acceptance.py',
    'tests/test_rebuild_legacy_artifact_acceptance.py', 'tests/test_coverage_evidence_selector_repairs.py',
    'tests/test_rom_cfg_proven_roots_v21_coverage.py',
    'docs/legacy-artifact-acceptance-contract-v1.md', 'docs/reverse-engineering-handoff-current-20260905.md',
    'notes/legacy-artifact-acceptance-20260905.md', 'notes/rom-evidence-selector-repair-20260905.md',
})
tracked = set(git('ls-files', '-z').decode().split('\0'))
modified = set(git('ls-files', '--modified', '-z').decode().split('\0'))
changed = sorted(p for p in paths if p not in tracked or p in modified)
index = RUN/'candidate-index-v6'
assert not index.exists()
env = dict(os.environ, GIT_INDEX_FILE=str(index))
git('read-tree', 'HEAD', env=env)
pathspec = RUN/'candidate-changed-pathspec-v6.nul'
with pathspec.open('xb') as stream:
    stream.write(b'\0'.join(p.encode() for p in changed) + b'\0')
git('add', '--pathspec-from-file='+str(pathspec), '--pathspec-file-nul', env=env)
tree = git('write-tree', env=env).decode().strip()
inventory = json.loads((RUN/'input-inventory-v3.json').read_bytes())
inventory.update(source_tree=tree, source_head=git('rev-parse', 'HEAD').decode().strip())
inventory['identities'] = {
    path.replace(OLD_RECEIPTS, RECEIPTS): sha((ROOT/path.replace(OLD_RECEIPTS, RECEIPTS)).read_bytes())
    for path in inventory['identities']}
for path, expected in inventory['identities'].items():
    assert sha(git('show', tree+':'+path)) == expected, path
for row in inventory['roots']:
    root = row['root']
    actual = {}
    for entry in git('ls-tree', '-r', '-z', tree, '--', root).split(b'\0'):
        if not entry:
            continue
        metadata, path = entry.split(b'\t')
        mode, kind, oid = metadata.split()
        assert kind == b'blob' and mode in (b'100644', b'100755')
        raw = git('cat-file', 'blob', oid.decode())
        actual[path.decode()[len(root)+1:]] = {'mode': mode.decode(), 'size': len(raw), 'sha256': sha(raw)}
    assert actual == row['members'], root
assert len(inventory['roots']) == 64 and sum(len(r['members']) for r in inventory['roots']) == 160
write_new(RUN/'input-inventory-v4.json', inventory)
write_new(RUN/'candidate-tree-v6.json', {'status': 'private_tree_only_not_accepted',
          'tree': tree, 'changed_paths': changed, 'formal_blockers': len(formal['blockers']),
          'source_closure': 'commit-closure-candidate-v4.json', 'added_paths': sorted(paths - {r['path'] for r in old_closure['files']})})
source = (RUN/'build_candidate_v3.py').read_text()
source = source.replace('input-inventory-v3.json', 'input-inventory-v4.json')
source = source.replace("candidate-v3';out.mkdir()", "candidate-v4';out.mkdir()")
source = source.replace(OLD_RECEIPTS, RECEIPTS)
source = source.replace("'global_blockers':177", "'global_blockers':len(formal['blockers'])")
with (RUN/'build_candidate_v4.py').open('x') as stream:
    stream.write(source)
assert not git('diff', '--cached', '--name-only').strip()
print(json.dumps({'status': 'prepared_only_not_accepted', 'tree': tree, 'changes': len(changed)}))
