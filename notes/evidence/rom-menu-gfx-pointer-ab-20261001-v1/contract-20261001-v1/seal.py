from pathlib import Path
import hashlib
import json
import shutil
import sys

root = Path.cwd().resolve()
sys.path.insert(0, str(root))
from tools.experiment_workspace import complete_run
from tools.verify_menu_portrait_pointer_ab import canonical, RAW_FILES, IMPLEMENTATION_PATHS, CONTRACT, CONTRACT_SHA

workspace = root / 'build/experiments/active'
contract = workspace / 'menu-portrait-pointer-ab/contract-20261001-v1'
receipt = root / 'notes/evidence/rom-menu-gfx-pointer-ab-20261001-v1'
assert {p.name for p in receipt.iterdir()} == {'source'}
result = json.loads((contract / 'verification.json').read_text())
assert result == json.loads((contract / 'verification-repeated.json').read_text()) and result['verified']

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

for n, expected in result['raw_sha256'].items():
    assert digest(receipt / 'source' / n) == expected, n
assert {p.relative_to(receipt / 'source').as_posix() for p in (receipt / 'source').rglob('*') if p.is_file()} == RAW_FILES
for p in (workspace / 'menu-portrait-pointer-ab').glob('tests-*/.experiment.json'):
    value = json.loads(p.read_text())
    # Only this turn's publication tests own this task namespace.
    if value['status'] == 'active':
        complete_run(root, 'menu-portrait-pointer-ab', value['run_id'])
(contract / 'note.md').write_bytes((root / 'notes/rom-menu-gfx-pointer-ab-20261001.md').read_bytes())
for task, identifier in [('menu-portrait-pointer-ab', 'build-20261001-v1'),
                         ('menu-portrait-pointer-ab', 'runtime-20261001-v1'),
                         ('menu-portrait-pointer-ab', 'contract-20261001-v1'),
                         ('menu-portrait-refresh', 'replay-20261001-v1')]:
    complete_run(root, task, identifier)

def copy_owned(origin, destination):
    omissions = {}
    for p in sorted(origin.rglob('*')):
        assert not p.is_symlink(), p
        if not p.is_file():
            continue
        name = p.relative_to(origin).as_posix()
        if p.suffix in {'.gba', '.sav'}:
            omissions[name] = {'size': p.stat().st_size, 'sha256': digest(p), 'reason': 'reproducible derived ROM or irrelevant save sidecar'}
            continue
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists(), target
        shutil.copy2(p, target)
    return omissions

omitted = {}
for identifier in ['build-20261001-v1', 'runtime-20261001-v1', 'contract-20261001-v1']:
    rows = copy_owned(workspace / 'menu-portrait-pointer-ab' / identifier, receipt / identifier)
    omitted.update({f'{identifier}/{name}': row for name, row in rows.items()})
for name in [*IMPLEMENTATION_PATHS, CONTRACT]:
    target = receipt / 'implementation' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists()
    shutil.copy2(root / name, target)
(receipt / 'omitted-derived-inputs.json').write_bytes(canonical(omitted))
files = {p.relative_to(receipt).as_posix(): {'size': p.stat().st_size, 'sha256': digest(p)}
         for p in sorted(receipt.rglob('*')) if p.is_file()}
manifest = {'schema': 'reverse-work-receipt-v1', 'status': 'verified_partial_natural_show_portrait_load',
            'task_mode': 'frozen-resource-pointer-single-field-ab-natural-runtime-contract',
            'files': files, 'related_tests': 26, 'runtime_samples': 5, 'raw_members': 43,
            'contract_sha256': CONTRACT_SHA, 'cells_covered': 1, 'cells_total': 630,
            'changed_pixel_count': 1, 'scratch_prefix_semantics_verified': False,
            'canonical_written': False, 'live_bank_catalog_written': False, 'formal_rerun': False,
            'omitted_derived_member_count': len(omitted)}
(receipt / 'manifest.json').write_bytes(canonical(manifest))
refresh = root / 'notes/evidence/rom-menu-portrait-refresh-20261001-v1'
assert not refresh.exists()
refresh.mkdir()
assert not copy_owned(workspace / 'menu-portrait-refresh/replay-20261001-v1', refresh)
files_refresh = {p.relative_to(refresh).as_posix(): {'size': p.stat().st_size, 'sha256': digest(p)}
                 for p in sorted(refresh.rglob('*')) if p.is_file()}
(refresh / 'manifest.json').write_bytes(canonical({'schema': 'reverse-work-receipt-v1',
    'status': 'verified_semantic_reissue', 'task_mode': 'frozen-runtime-archive-semantic-reissue-after-dependency-drift',
    'files': files_refresh, 'runtime_launch': False, 'canonical_written': False, 'live_bank_catalog_written': False}))
print(json.dumps({'sealed': True, 'pointer_members': len(files), 'refresh_members': len(files_refresh),
                  'omitted': len(omitted), 'pointer_receipt_sha256': digest(receipt / 'manifest.json'),
                  'refresh_receipt_sha256': digest(refresh / 'manifest.json')}))
