from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT))
from tools.experiment_workspace import complete_run
from tools.verify_cutscene_obj_secondary_ptr_ab import canonical, RAW_FILES, IMPLEMENTATION_PATHS, CONTRACT, CONTRACT_SHA

capture = ROOT / 'build/experiments/active/cutscene-secondary-ptr-ab/runtime-shared-lock-20261001-v1'
contract = ROOT / 'build/experiments/active/cutscene-secondary-ptr-contract/tier1-20261001-v1'
receipt = ROOT / 'notes/evidence/rom-cutscene-secondary-ptr-shared-lock-20261001-v1'
assert {p.name for p in receipt.iterdir()} == {'source'}, 'receipt already sealed or unexpected member'
result = json.loads((contract / 'verification.json').read_text())
assert result['verified'] and result == json.loads((contract / 'verification-repeated.json').read_text())
assert {p.relative_to(receipt / 'source').as_posix() for p in (receipt / 'source').rglob('*') if p.is_file()} == RAW_FILES

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

for name, expected in result['raw_sha256'].items():
    assert digest(receipt / 'source' / name) == expected, name
closed = {}
for identifier in ['tests-07846968a8df4cb59c0c91d2e48b4a3c', 'tests-09954a66823c4d9eb6242a94c1ed7f1d']:
    closed[identifier] = complete_run(ROOT, 'cutscene-secondary-ptr-contract', identifier)
(contract / 'owned-test-runs-closed.json').write_bytes(canonical(closed))
(contract / 'note.md').write_bytes((ROOT / 'notes/rom-cutscene-secondary-ptr-contract-20261001.md').read_bytes())
complete_run(ROOT, 'cutscene-secondary-ptr-ab', 'runtime-shared-lock-20261001-v1')
complete_run(ROOT, 'cutscene-secondary-ptr-contract', 'tier1-20261001-v1')
omitted = {}
for label, origin in [('runtime-shared-lock-20261001-v1', capture), ('contract-tier1-20261001-v1', contract)]:
    for path in sorted(origin.rglob('*')):
        assert not path.is_symlink(), path
        if not path.is_file():
            continue
        relative = f'{label}/{path.relative_to(origin).as_posix()}'
        if path.suffix in {'.gba', '.sav'}:
            omitted[relative] = {'size': path.stat().st_size, 'sha256': digest(path),
                                 'reason': 'derived ROM/save; rebuild from frozen input or irrelevant sidecar'}
            continue
        destination = receipt / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        assert not destination.exists(), destination
        shutil.copy2(path, destination)
for name in [*IMPLEMENTATION_PATHS, CONTRACT]:
    destination = receipt / 'implementation' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert not destination.exists(), destination
    shutil.copy2(ROOT / name, destination)
(receipt / 'omitted-derived-inputs.json').write_bytes(canonical(omitted))
files = {p.relative_to(receipt).as_posix(): {'size': p.stat().st_size, 'sha256': digest(p)}
         for p in sorted(receipt.rglob('*')) if p.is_file()}
manifest = {'schema': 'reverse-work-receipt-v1', 'status': 'verified_partial_natural_victory_load',
            'task_mode': 'frozen-resource-pointer-single-field-ab-natural-runtime-contract',
            'run_ids': ['cutscene-secondary-ptr-ab/runtime-shared-lock-20261001-v1',
                        'cutscene-secondary-ptr-contract/tier1-20261001-v1'],
            'files': files, 'raw_members': 43, 'runtime_samples': 5, 'related_tests': 31,
            'cells_covered': 1, 'cells_total': 16, 'changed_pixel_count': 778,
            'contract_sha256': CONTRACT_SHA, 'canonical_written': False,
            'live_bank_catalog_written': False, 'formal_rerun': False,
            'supersedes_wrong_lock_capture': 'runtime-recovery-20261001-v1',
            'omitted_derived_member_count': len(omitted)}
(receipt / 'manifest.json').write_bytes(canonical(manifest))
print(json.dumps({'sealed': True, 'member_count': len(files), 'omitted': len(omitted),
                  'manifest_sha256': digest(receipt / 'manifest.json')}))
