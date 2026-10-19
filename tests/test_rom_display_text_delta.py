"""Display records: independent raw replay and managed CLI integration."""
import copy
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class DisplayTextDeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.experiment_workspace import init_run
        cls.run_id = 'tests-' + uuid.uuid4().hex
        cls.managed_run = init_run(ROOT, 'display-text-delta', cls.run_id)

    @classmethod
    def tearDownClass(cls):
        from tools.experiment_workspace import complete_run
        complete_run(ROOT, 'display-text-delta', cls.run_id)

    def exporter(self):
        return importlib.import_module('tools.export_rom_display_text_delta')

    def verifier(self):
        return importlib.import_module('tools.verify_rom_display_text_delta')

    def test_real_rom_92_consumers_85_records_1053_bytes(self):
        e, v = self.exporter(), self.verifier()
        p = e.build_payload(ROOT)
        self.assertEqual(p, v.rebuild(ROOT, (ROOT / 'rom/base.gba').read_bytes()))
        self.assertEqual((92, 85, 1053), (len(p['consumers']), len(p['records']), p['promotion']['promotion_bytes']))
        self.assertEqual(85, p['promotion']['claim_count'])
        self.assertEqual(6, len(p['source_verification']))
        for flag in ('natural_runtime_reachability', 'editing_or_relocation_safety', 'whole_rom_consumer_denominator', 'padding_or_free_space', 'command_script_semantics'):
            self.assertFalse(p['scope'][flag])
        self.assertTrue(p['scope']['raw_parameter_paths_verified'])
        records = sorted(r['range'] for r in p['records'])
        self.assertTrue(all(a[1] <= b[0] for a, b in zip(records, records[1:])))
        # The last records end before their enclosing unknown pools; no suffix claim.
        for gap in (0x463B16, 0x458757, 0x12F293):
            self.assertFalse(any(a <= gap < b for a, b in records))

    def test_parameter_literal_semantic_and_terminator_mutations_fail_closed(self):
        e = self.exporter()
        p = e.build_payload(ROOT)
        rom = (ROOT / 'rom/base.gba').read_bytes()
        c, r = p['consumers'][0], p['records'][0]
        mutations = [(c['site'] + 2, b'\x00\x20'), (c['literal_word'], b'\x00\x00\x00\x08'),
                     (c['sink'], b'\x00\x20'), (r['range'][1] - 1, b'\x01'),
                     (0x66788, b'\x00\x21'), (0x667B8, b'\x00\x21'), (0x66284, b'\x00\x20')]
        for at, data in mutations:
            with self.subTest(at=hex(at)):
                changed = bytearray(rom)
                changed[at:at + len(data)] = data
                with self.assertRaises(ValueError):
                    e.build_from_rom(ROOT, bytes(changed), verify_identity=False)

    def test_managed_publication_stable_replay_and_no_replace(self):
        e, v = self.exporter(), self.verifier()
        from tools.experiment_workspace import _validate_promotion_manifest
        with tempfile.TemporaryDirectory(dir=self.managed_run) as tmp:
            target = Path(tmp) / 'final'
            e.export_artifact(ROOT, target)
            report = v.verify_artifact(ROOT, target)
            self.assertTrue(report['verified'], report)
            self.assertEqual(report, v.verify_artifact(ROOT, target))
            self.assertEqual('accepted', _validate_promotion_manifest(target)['artifact_status'])
            self.assertTrue(report['immutable_unknown_projection_checked'])
            self.assertFalse(report['current_unknown_checked'])
            before = {p.name: p.read_bytes() for p in target.iterdir()}
            with self.assertRaises(FileExistsError):
                e.export_artifact(ROOT, target)
            self.assertEqual(before, {p.name: p.read_bytes() for p in target.iterdir()})

    def test_relocation_is_identity_preserving(self):
        import shutil
        e, v = self.exporter(), self.verifier()
        with tempfile.TemporaryDirectory(dir=self.managed_run) as tmp:
            target = Path(tmp) / 'final'
            e.export_artifact(ROOT, target)
            second = Path(tmp) / 'copied'
            shutil.copytree(target, second)
            self.assertEqual(v.verify_artifact(ROOT, target), v.verify_artifact(ROOT, second))
            self.assertEqual((target / 'manifest.json').read_bytes(), (second / 'manifest.json').read_bytes())

    def test_self_consistent_tampering_extra_file_and_symlink_rejected(self):
        e, v = self.exporter(), self.verifier()
        with tempfile.TemporaryDirectory(dir=self.managed_run) as tmp:
            target = Path(tmp) / 'final'
            e.export_artifact(ROOT, target)
            payload_path = target / v.PAYLOAD
            original = payload_path.read_bytes()
            payload = json.loads(original)
            payload['scope']['natural_runtime_reachability'] = True
            altered = v.canonical(payload)
            payload_path.write_bytes(altered)
            manifest_path = target / 'manifest.json'
            old_manifest = manifest_path.read_bytes()
            manifest = json.loads(old_manifest)
            manifest['files'][v.PAYLOAD] = {'size': len(altered), 'sha256': v.sha(altered)}
            manifest_path.write_bytes(v.canonical(manifest))
            self.assertFalse(v.verify_artifact(ROOT, target)['verified'])
            payload_path.write_bytes(original)
            manifest_path.write_bytes(old_manifest)
            (target / 'extra').write_text('unaccepted')
            self.assertFalse(v.verify_artifact(ROOT, target)['verified'])
            (target / 'extra').unlink()
            alias = Path(tmp) / 'alias'
            alias.symlink_to(target, target_is_directory=True)
            self.assertFalse(v.verify_artifact(ROOT, alias)['verified'])
            self.assertTrue(v.verify_artifact(ROOT, target)['verified'])

    def test_current_unknown_projection_separate_from_stable_verification(self):
        e, v = self.exporter(), self.verifier()
        with tempfile.TemporaryDirectory(dir=self.managed_run) as tmp:
            target = Path(tmp) / 'final'
            e.export_artifact(ROOT, target)
            stable = v.verify_artifact(ROOT, target)
            segments = json.loads((ROOT / 'sequel/rom-byte-coverage.json').read_text())['segments']
            claims = v.project_unknown_claims(ROOT, target, segments)
            self.assertEqual((85, 1053), (len(claims), sum(c['range'][1] - c['range'][0] for c in claims)))
            changed = copy.deepcopy(segments)
            first = claims[0]['range'][0]
            next(s for s in changed if s['range'][0] <= first < s['range'][1])['primary_class'] = 'already_promoted'
            with self.assertRaisesRegex(ValueError, 'classified'):
                v.project_unknown_claims(ROOT, target, changed)
            self.assertEqual(stable, v.verify_artifact(ROOT, target))
            self.assertEqual('b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2', json.loads((target / v.PAYLOAD).read_text())['immutable_precoverage']['raw_sha256'])

    def test_publication_rejects_unmanaged_and_inactive_runs(self):
        e = self.exporter()
        with self.assertRaises(ValueError):
            e.export_artifact(ROOT, ROOT / 'artifacts/forbidden-display-text')
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/experiments/active') as tmp:
            with self.assertRaises((ValueError, FileNotFoundError)):
                e.export_artifact(ROOT, Path(tmp) / 'not-initialized' / 'final')
        from tools.experiment_workspace import init_run, complete_run
        name = 'inactive-' + uuid.uuid4().hex
        run = init_run(ROOT, 'display-text-delta', name)
        complete_run(ROOT, 'display-text-delta', name)
        with self.assertRaisesRegex(ValueError, 'active'):
            e.export_artifact(ROOT, run / 'final')
        self.assertFalse((run / 'final').exists())

    def test_reused_projection_helper_identity_is_checked(self):
        from tools import rom_small_cfg_callback_gaps_independent_verifier as infrastructure
        v = self.verifier()
        original = infrastructure.read_regular
        dependency = ROOT / 'tools/verify_rom_renderer_records_delta.py'

        def changed(path):
            raw = original(path)
            return raw + b'changed projection' if Path(path) == dependency else raw

        with patch.object(infrastructure, 'read_regular', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'input identity'):
                v.load_contract(ROOT)

    def test_real_export_and_independent_verify_cli(self):
        with tempfile.TemporaryDirectory(dir=self.managed_run) as tmp:
            target = Path(tmp) / 'final'
            for tool, option in [('tools/export_rom_display_text_delta.py', '--output'), ('tools/verify_rom_display_text_delta.py', '--artifact-dir')]:
                result = subprocess.run([sys.executable, tool, '--root', str(ROOT), option, str(target)], cwd=ROOT, capture_output=True, text=True, timeout=360)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                if option == '--artifact-dir':
                    report = json.loads(result.stdout)
                    self.assertTrue(report['verified'])
                    self.assertEqual((92, 85, 1053), (report['consumer_count'], report['record_count'], report['promotion_bytes']))


if __name__ == '__main__':
    unittest.main()
