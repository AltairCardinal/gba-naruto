"""Managed publication, independent replay and actual typed-bank CLI integration."""
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import uuid

from tools import export_menu_portrait_pointer_ab as exporter
from tools import verify_menu_portrait_pointer_ab as verifier
from tools.audit_reverse_engineering_proof import _check_bank, _execute_contract
from tools.experiment_workspace import init_run, complete_run, _validate_promotion_manifest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'notes/evidence/rom-menu-gfx-pointer-ab-20261001-v1/source'


class MenuPointerPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_id = 'tests-' + uuid.uuid4().hex
        cls.managed_run = init_run(ROOT, 'menu-portrait-pointer-ab', cls.run_id)

    @classmethod
    def tearDownClass(cls):
        complete_run(ROOT, 'menu-portrait-pointer-ab', cls.run_id)

    def publish(self, target):
        return exporter.export_artifact(ROOT, SOURCE, target)

    def test_managed_promotion_double_replay_and_no_replace(self):
        with tempfile.TemporaryDirectory(dir=self.managed_run) as directory:
            artifact = self.publish(Path(directory) / 'final')
            report = verifier.verify_artifact(ROOT, artifact)
            self.assertTrue(report['verified'], report)
            self.assertEqual(report, verifier.verify_artifact(ROOT, artifact))
            self.assertEqual(_validate_promotion_manifest(artifact)['artifact_status'], 'accepted')
            self.assertEqual((report['cells_total'], report['changed_pixel_count']), (630, 1))
            original = {p.name: p.read_bytes() for p in artifact.iterdir()}
            with self.assertRaises(FileExistsError):
                self.publish(artifact)
            self.assertEqual(original, {p.name: p.read_bytes() for p in artifact.iterdir()})

    def test_offline_relocation_keeps_exact_identity(self):
        with tempfile.TemporaryDirectory(dir=self.managed_run) as directory:
            artifact = self.publish(Path(directory) / 'final')
            clone = Path(directory) / 'clone'
            shutil.copytree(artifact, clone)
            self.assertEqual(verifier.verify_artifact(ROOT, artifact), verifier.verify_artifact(ROOT, clone))

    def test_resigned_pixel_or_scope_claim_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.managed_run) as directory:
            artifact = self.publish(Path(directory) / 'final')
            for key, value in [('changed_pixel_count', 779), ('exhaustive', True), ('record_ids_covered', ['1', '5'])]:
                with self.subTest(key=key):
                    clone = Path(directory) / key
                    shutil.copytree(artifact, clone)
                    data = {p.name: p.read_bytes() for p in clone.iterdir() if p.name != 'manifest.json'}
                    report = json.loads(data['evidence.json'])
                    report[key] = value
                    data['evidence.json'] = verifier.canonical(report)
                    (clone / 'evidence.json').write_bytes(data['evidence.json'])
                    (clone / 'manifest.json').write_bytes(verifier.canonical(verifier.intended_manifest(ROOT, data, report)))
                    self.assertFalse(verifier.verify_artifact(ROOT, clone)['verified'])

    def test_archive_traversal_duplicate_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.managed_run) as directory:
            artifact = self.publish(Path(directory) / 'final')
            for case in ['traversal', 'duplicate', 'symlink']:
                with self.subTest(case=case):
                    clone = Path(directory) / case
                    shutil.copytree(artifact, clone)
                    members = {n: (SOURCE / n).read_bytes() for n in sorted(verifier.RAW_FILES)}
                    payload = io.BytesIO()
                    with tarfile.open(fileobj=payload, mode='w', format=tarfile.USTAR_FORMAT) as archive:
                        for name, raw in members.items():
                            row = tarfile.TarInfo(name)
                            row.size = len(raw)
                            archive.addfile(row, io.BytesIO(raw))
                        row = tarfile.TarInfo('../outside' if case == 'traversal' else 'plan.json')
                        if case == 'symlink':
                            row.type, row.linkname = tarfile.SYMTYPE, '/tmp/outside'
                        archive.addfile(row)
                    (clone / 'raw.tar').write_bytes(payload.getvalue())
                    data = {p.name: p.read_bytes() for p in clone.iterdir() if p.name != 'manifest.json'}
                    report = json.loads(data['evidence.json'])
                    (clone / 'manifest.json').write_bytes(verifier.canonical(verifier.intended_manifest(ROOT, data, report)))
                    self.assertFalse(verifier.verify_artifact(ROOT, clone)['verified'])
                    self.assertFalse((Path(directory) / 'outside').exists())

    def test_cli_contract_is_partial_and_cannot_pass_full_bank_gate(self):
        with tempfile.TemporaryDirectory(dir=self.managed_run) as directory:
            artifact = self.publish(Path(directory) / 'final')
            result = verifier.verify_artifact(ROOT, artifact)
            proof = verifier.proof_binding(ROOT, artifact, result)
            row = proof['verifiers'][0]
            self.assertEqual(row['contract']['assertions'].get('/evidence_sha256'),
                             {e['path']: e['sha256'] for e in proof['evidence']})
            blockers = []
            replay = _execute_contract(ROOT, 'menu-ui', [sys.executable, *row['command'][1:]], row['contract'], blockers)
            self.assertTrue(replay['contract_ok'], blockers)
            wrong = copy.deepcopy(row['contract'])
            wrong['assertions']['/cells_total'] = 2
            self.assertFalse(_execute_contract(ROOT, 'menu-ui', [sys.executable, *row['command'][1:]], wrong, [])['contract_ok'])
            blockers, commands = [], []
            audited = _check_bank(ROOT, 'menu-ui', ROOT / verifier.BANK, proof, None, blockers, commands)
            self.assertFalse(audited['complete'])
            self.assertEqual(audited['contracted_verifier_count'], 1)
            self.assertTrue(any('not exhaustively ID-bound' in b for b in blockers), blockers)
            self.assertTrue(any('field coverage is not exhaustive' in b for b in blockers), blockers)
            forged = copy.deepcopy(result)
            forged['cells_total'] = 2
            with self.assertRaisesRegex(ValueError, 'result mismatch'):
                verifier.proof_binding(ROOT, artifact, forged)

    def test_exporter_cli_and_rejected_output_boundaries(self):
        with tempfile.TemporaryDirectory(dir=self.managed_run) as directory:
            target = Path(directory) / 'cli'
            proc = subprocess.run([sys.executable, 'tools/export_menu_portrait_pointer_ab.py', '--root', str(ROOT),
                                   '--source-dir', str(SOURCE), '--output', str(target)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(verifier.verify_artifact(ROOT, target)['verified'])
            with self.assertRaises(ValueError):
                self.publish(ROOT / 'artifacts/unauthorized-output')
            empty = init_run(ROOT, 'menu-portrait-pointer-ab', self.run_id + '-inactive')
            complete_run(ROOT, 'menu-portrait-pointer-ab', self.run_id + '-inactive')
            with self.assertRaises((ValueError, OSError)):
                self.publish(empty / 'final')
            alias = Path(directory) / 'alias'
            alias.symlink_to(target, target_is_directory=True)
            self.assertFalse(verifier.verify_artifact(ROOT, alias)['verified'])
            (target / 'extra').write_text('extra')
            self.assertFalse(verifier.verify_artifact(ROOT, target)['verified'])

    def test_bad_capture_cannot_be_published(self):
        with tempfile.TemporaryDirectory(dir=self.managed_run) as directory:
            source = Path(directory) / 'source'
            shutil.copytree(SOURCE, source)
            path = source / 'build-manifest.json'
            value = json.loads(path.read_text())
            value['edit']['record_id'] = '5'
            path.write_text(json.dumps(value))
            target = Path(directory) / 'final'
            with self.assertRaisesRegex(ValueError, 'build manifest'):
                exporter.export_artifact(ROOT, source, target)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
