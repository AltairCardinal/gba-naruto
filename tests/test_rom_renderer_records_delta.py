"""Managed publication, raw consumer replay and precise coverage projection."""
import copy
import gzip
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'build/experiments/active/renderer-records-delta/combined-tier1-20261001-v1'


class RendererRecordsDeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global RUN
        from tools.experiment_workspace import init_run
        cls.run_id = 'tests-' + uuid.uuid4().hex
        RUN = init_run(ROOT, 'renderer-records-delta', cls.run_id)

    @classmethod
    def tearDownClass(cls):
        from tools.experiment_workspace import complete_run
        complete_run(ROOT, 'renderer-records-delta', cls.run_id)

    def exporter(self):
        return importlib.import_module('tools.export_rom_renderer_records_delta')

    def verifier(self):
        return importlib.import_module('tools.verify_rom_renderer_records_delta')

    def test_actual_rom_combines_old_and_later_consumers(self):
        p = self.exporter().build_payload(ROOT)
        self.assertEqual((47, 34, 13), (len(p['consumers']), sum(r['accepted'] for r in p['consumers']),
                                      sum(not r['accepted'] for r in p['consumers'])))
        self.assertEqual(29, len(p['records']))
        self.assertEqual(1668, p['promotion']['promotion_bytes'])
        self.assertEqual(29, p['promotion']['claim_count'])
        self.assertFalse(p['scope']['natural_runtime_reachability'])
        self.assertFalse(p['scope']['editing_or_relocation_safety'])
        for gap in [0x42BD, 0x1968, 0x19B4, 0x1AE7]:
            self.assertFalse(any(a <= gap < b for a, b in (r['range'] for r in p['records'])))

    def test_mutated_literal_parameter_record_and_terminator_fail_closed(self):
        e = self.exporter()
        original = (ROOT / 'rom/base.gba').read_bytes()
        for at, raw in [(0x79A8A, b'\x00\x20'), (0x79A8C, b'\x00\x20'),
                        (0x42B6, b'\x05'), (0x42BC, b'\x01'), (0x1967, b'\x01'),
                        (0x42BD, b'\x00'), (0x70228, b'\xb5\x42\x00\x08')]:
            with self.subTest(at=hex(at)):
                mutated = bytearray(original)
                mutated[at:at + len(raw)] = raw
                with self.assertRaises(ValueError):
                    e.build_from_rom(ROOT, bytes(mutated), verify_identity=False)

    def test_mutated_interpreter_semantics_rejected_before_identity_gate(self):
        e = self.exporter()
        original = (ROOT / 'rom/base.gba').read_bytes()
        mutated = bytearray(original)
        mutated[0x671D4] = 8  # opcode 1 advances 7 bytes in the frozen ROM.
        with self.assertRaises(ValueError):
            e.build_from_rom(ROOT, bytes(mutated), verify_identity=False)

    def test_managed_publication_replay_and_no_replace(self):
        e, v = self.exporter(), self.verifier()
        from tools.experiment_workspace import _validate_promotion_manifest
        with tempfile.TemporaryDirectory(dir=RUN) as tmp:
            target = Path(tmp) / 'final'
            e.export_artifact(ROOT, target)
            first = v.verify_artifact(ROOT, target)
            self.assertTrue(first['verified'])
            self.assertEqual(first, v.verify_artifact(ROOT, target))
            self.assertEqual('accepted', _validate_promotion_manifest(target)['artifact_status'])
            before = {p.name: p.read_bytes() for p in target.iterdir()}
            with self.assertRaises(FileExistsError):
                e.export_artifact(ROOT, target)
            self.assertEqual(before, {p.name: p.read_bytes() for p in target.iterdir()})

    def test_relocated_final_remains_verifiable_without_manifest_rewrite(self):
        e, v = self.exporter(), self.verifier()
        import shutil
        with tempfile.TemporaryDirectory(dir=RUN) as tmp:
            target = Path(tmp) / 'final'
            e.export_artifact(ROOT, target)
            before = v.verify_artifact(ROOT, target)
            relocated = Path(tmp) / 'relocated'
            shutil.copytree(target, relocated)
            self.assertEqual(before, v.verify_artifact(ROOT, relocated))
            self.assertEqual((target / 'manifest.json').read_bytes(),
                             (relocated / 'manifest.json').read_bytes())

    def test_self_consistent_hash_tampering_and_extra_member_rejected(self):
        e, v = self.exporter(), self.verifier()
        with tempfile.TemporaryDirectory(dir=RUN) as tmp:
            target = Path(tmp) / 'final'
            e.export_artifact(ROOT, target)
            payload = target / v.PAYLOAD
            original = payload.read_bytes()
            manifest_path = target / 'manifest.json'
            manifest_raw = manifest_path.read_bytes()
            data = json.loads(original)
            data['promotion']['claims'][0]['range'][1] += 1
            payload.write_bytes(v.canonical(data))
            manifest = json.loads(manifest_raw)
            manifest['files'][v.PAYLOAD] = {'size': payload.stat().st_size,
                                          'sha256': v.sha(payload.read_bytes())}
            manifest_path.write_bytes(v.canonical(manifest))
            self.assertFalse(v.verify_artifact(ROOT, target)['verified'])
            payload.write_bytes(original)
            manifest_path.write_bytes(manifest_raw)
            (target / 'extra').write_text('unexpected')
            self.assertFalse(v.verify_artifact(ROOT, target)['verified'])

    def test_publication_forbids_direct_artifacts_and_symlink(self):
        e = self.exporter()
        with self.assertRaises(ValueError):
            e.export_artifact(ROOT, ROOT / 'artifacts/forbidden-renderer-records')
        with tempfile.TemporaryDirectory(dir=RUN) as tmp:
            parent = Path(tmp)
            (parent / 'alias').symlink_to(parent, target_is_directory=True)
            with self.assertRaises((ValueError, OSError)):
                e.export_artifact(ROOT, parent / 'alias/final')
            self.assertFalse((parent / 'final').exists())

    def test_completed_managed_run_rejected_before_creating_stage(self):
        e, v = self.exporter(), self.verifier()
        original = v.read_regular
        metadata_path = RUN / '.experiment.json'
        def read(path):
            raw = original(path)
            if Path(path) == metadata_path:
                data = json.loads(raw)
                data['status'] = 'completed'
                return v.canonical(data)
            return raw
        with tempfile.TemporaryDirectory(dir=RUN) as tmp:
            parent = Path(tmp)
            with patch.object(v, 'read_regular', side_effect=read):
                with self.assertRaisesRegex(ValueError, 'not active'):
                    e.export_artifact(ROOT, parent / 'final')
            self.assertEqual([], list(parent.iterdir()))

    def test_coverage_adapter_rejects_overlap_and_preserves_gaps(self):
        e, v = self.exporter(), self.verifier()
        segments = json.loads(gzip.decompress((ROOT / v.PRECOVERAGE).read_bytes()))['segments']
        with tempfile.TemporaryDirectory(dir=RUN) as tmp:
            target = Path(tmp) / 'final'
            e.export_artifact(ROOT, target)
            claims = v.project_unknown_claims(ROOT, target, segments)
            self.assertEqual(1668, sum(b - a for a, b in (c['range'] for c in claims)))
            changed = copy.deepcopy(segments)
            for s in changed:
                if s['range'][0] <= 0x42B5 < s['range'][1]:
                    s['primary_class'] = 'thumb_code'
            with self.assertRaises(ValueError):
                v.project_unknown_claims(ROOT, target, changed)
            self.assertTrue(v.verify_artifact(ROOT, target)['verified'])
            with self.assertRaises(ValueError):
                v.project_unknown_claims(ROOT, target, [])

    def test_cached_sources_recheck_input_hashes(self):
        e, v = self.exporter(), self.verifier()
        e.build_payload(ROOT)
        from tools import rom_small_cfg_callback_gaps_independent_verifier as io
        original = io.read_regular
        bad = ROOT / 'artifacts/rom-cfg-proven-roots-v6/manifest.json'
        def read(path):
            return b'{}' if Path(path) == bad else original(path)
        with patch.object(io, 'read_regular', side_effect=read):
            with self.assertRaises(ValueError):
                e.build_payload(ROOT)
            with self.assertRaises(ValueError):
                v.rebuild(ROOT, (ROOT / 'rom/base.gba').read_bytes())

    def test_real_cli_integration(self):
        with tempfile.TemporaryDirectory(dir=RUN) as tmp:
            target = Path(tmp) / 'final'
            subprocess.run([sys.executable, 'tools/export_rom_renderer_records_delta.py',
                            '--root', str(ROOT), '--output', str(target)], cwd=ROOT,
                           check=True, capture_output=True)
            report = subprocess.run([sys.executable, 'tools/verify_rom_renderer_records_delta.py',
                                     '--root', str(ROOT), '--artifact-dir', str(target)], cwd=ROOT,
                                    check=True, capture_output=True, text=True)
            self.assertTrue(json.loads(report.stdout)['verified'])
            (target / 'extra').write_text('unexpected')
            rejected = subprocess.run([sys.executable, 'tools/verify_rom_renderer_records_delta.py',
                                       '--root', str(ROOT), '--artifact-dir', str(target)], cwd=ROOT,
                                      capture_output=True)
            self.assertEqual(1, rejected.returncode)


if __name__ == '__main__':
    unittest.main()
