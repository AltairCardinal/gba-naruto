import contextlib
import hashlib
import json
from pathlib import Path
import sys
import traceback

root = Path.cwd().resolve()
sys.path.insert(0, str(root))
from tools.export_menu_portrait_pixel_ab_evidence import export_evidence
from tools.verify_menu_portrait_pixel_ab_evidence import verify_evidence, IMPLEMENTATION_PATHS

run = root / 'build/experiments/active/menu-portrait-refresh/replay-20261001-v1'
old = root / 'artifacts/menu-portrait-pixel-ab-v1'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(name, value):
    (run / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

with (run / 'replay.log').open('w', buffering=1) as log:
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            before = {p.relative_to(old).as_posix(): sha(p) for p in sorted(old.rglob('*')) if p.is_file()}
            original = json.loads((old / 'manifest.json').read_text())
            assert before['manifest.json'] == 'c09b4784e18db4177cc44a089501ccea29699a666bcf969555ba331d916d91ae'
            for name, digest in original['files'].items():
                assert sha(old / name) == digest, name
            identities = {name: sha(root / name) for name in IMPLEMENTATION_PATHS}
            drift = {name: {'expected': digest, 'actual': identities[name]}
                     for name, digest in original['implementation_sha256'].items() if identities[name] != digest}
            assert set(drift) == {'tools/render_mode0_checkpoint.py'}, drift
            frozen = {name: sha(root / name) for name in ['rom/base.gba', 'sequel/content/menu-ui/bank.json',
                'artifacts/menu-portraits-v1/manifest.json', 'artifacts/menu-portraits-v1/portrait_01_variant_0.png',
                'artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-9.ss9',
                'sequel/rom-layout.json', 'sequel/image-resource-regions.json', *IMPLEMENTATION_PATHS]}
            write('plan.json', {'task_mode': 'frozen-runtime-archive-semantic-reissue-after-dependency-drift',
                                'old_members': before, 'inputs': frozen, 'drift': drift, 'runtime_launch': False})
            rejected = verify_evidence(root, old)
            assert rejected == {'verified': False, 'errors': ['portrait independent implementation hash mismatch']}, rejected
            evidence = export_evidence(root, old / 'raw', run / 'reissued')
            first = verify_evidence(root, run / 'reissued')
            second = verify_evidence(root, run / 'reissued')
            assert first == second == {'verified': True, 'errors': []}, first
            assert evidence == json.loads((old / 'runtime-evidence.json').read_text()), 'semantic result changed'
            assert before == {p.relative_to(old).as_posix(): sha(p) for p in sorted(old.rglob('*')) if p.is_file()}
            assert frozen == {name: sha(root / name) for name in frozen}
            write('result.json', {'old_result': rejected, 'reissued_result': first, 'repeated_result': second,
                                 'semantic_payload_identical': True, 'old_members_unchanged': True,
                                 'runtime_launch': False, 'pixel_changes': evidence['runtime']['pixels'],
                                 'pointer_field_ab_proven': False, 'typed_cells_promoted': 0,
                                 'source_capture_guard_identity': 'historical 0.10.5-script-backport receipt, not a new c16 capture'})
        except BaseException:
            traceback.print_exc()
            raise
