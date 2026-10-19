"""Frozen low-script consumers: independent replay and fail-closed publication."""
import importlib
import gzip
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class LowScriptDeltaTests(unittest.TestCase):
    def exporter(self):
        return importlib.import_module('tools.export_rom_low_script_delta')

    def verifier(self):
        return importlib.import_module('tools.verify_rom_low_script_delta')

    def test_actual_rom_two_records_and_excluded_gap(self):
        p = self.exporter().build_payload(ROOT)
        self.assertEqual(6, len(p['consumers']))
        self.assertEqual(4, sum(r['accepted'] for r in p['consumers']))
        self.assertEqual([[0x42B5, 0x42BD], [0x42C2, 0x42C6]],
                         [r['range'] for r in p['records']])
        self.assertEqual(12, p['promotion']['promotion_bytes'])
        self.assertFalse(p['scope']['natural_runtime_reachability'])
        self.assertEqual([0x42BD], p['excluded_roots'])

    def test_mutated_literal_sink_record_and_extra_site_fail_closed(self):
        e = self.exporter()
        original = (ROOT / 'rom/base.gba').read_bytes()
        mutations = [(0x79A8A, b'\x00\x20'), (0x79A8C, b'\x00\x20'),
                     (0x42B5, b'\x02'), (0x42BC, b'\x01'),
                     (0x42C5, b'\x03'), (0x79B80, struct.pack('<I', 0x080042BD)),
                     (0x70228, struct.pack('<I', 0x080042B5))]
        for at, replacement in mutations:
            with self.subTest(at=hex(at)):
                rom = bytearray(original)
                rom[at:at + len(replacement)] = replacement
                with self.assertRaises(ValueError):
                    e.build_from_rom(ROOT, bytes(rom), verify_identity=False)

    def test_both_parsers_reject_truncation_and_missing_terminator(self):
        from tools.export_rom_training_text_script_inventory import _parse_training_record
        from tools.verify_rom_fixed_renderer_script_records import _parse
        for data in [b'\x01\x00', b'\x03\x01', b'\x04']:
            for parser in [_parse_training_record, _parse]:
                with self.subTest(data=data, parser=parser.__name__), self.assertRaises(ValueError):
                    parser(data, 0, len(data), ())

    def test_export_verify_no_replace_extra_member_and_claim_tamper(self):
        e, v = self.exporter(), self.verifier()
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/experiments') as tmp:
            target = Path(tmp) / 'artifact'
            e.export_artifact(ROOT, target)
            self.assertTrue(v.verify_artifact(ROOT, target)['verified'])
            before = {p.name: p.read_bytes() for p in target.iterdir()}
            with self.assertRaises(FileExistsError):
                e.export_artifact(ROOT, target)
            self.assertEqual(before, {p.name: p.read_bytes() for p in target.iterdir()})
            payload = target / e.PAYLOAD_NAME
            data = json.loads(payload.read_bytes())
            data['promotion']['claims'][0]['range'][1] += 5
            payload.write_bytes(e.canonical(data))
            manifest_path = target / e.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_bytes())
            manifest['files'][e.PAYLOAD_NAME] = {'size': payload.stat().st_size,
                                                'sha256': v.sha(payload.read_bytes())}
            manifest_path.write_bytes(e.canonical(manifest))
            self.assertFalse(v.verify_artifact(ROOT, target)['verified'])
            payload.write_bytes(before[e.PAYLOAD_NAME])
            manifest_path.write_bytes(before[e.MANIFEST_NAME])
            (target / 'unexpected').write_text('extra')
            self.assertFalse(v.verify_artifact(ROOT, target)['verified'])

    def test_cli_integration_and_manifest(self):
        e = self.exporter()
        from tools.experiment_workspace import _validate_promotion_manifest
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/experiments') as tmp:
            target = Path(tmp) / 'artifact'
            command = [sys.executable, 'tools/export_rom_low_script_delta.py',
                       '--root', str(ROOT), '--output', str(target)]
            subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
            report = subprocess.run([sys.executable, 'tools/verify_rom_low_script_delta.py',
                                     '--root', str(ROOT), '--artifact', str(target)],
                                    cwd=ROOT, check=True, capture_output=True, text=True)
            self.assertTrue(json.loads(report.stdout)['verified'])
            self.assertEqual('accepted', _validate_promotion_manifest(target)['artifact_status'])
            (target / e.MANIFEST_NAME).write_text('{}')
            bad = subprocess.run([sys.executable, 'tools/verify_rom_low_script_delta.py',
                                  '--root', str(ROOT), '--artifact', str(target)],
                                 cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(1, bad.returncode)

    def test_paths_fail_before_publication(self):
        e = self.exporter()
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/experiments') as tmp:
            parent = Path(tmp)
            (parent / 'alias').symlink_to(parent, target_is_directory=True)
            with self.assertRaises(ValueError):
                e.export_artifact(ROOT, parent / 'alias' / 'artifact')
            self.assertFalse((parent / 'artifact').exists())

    def test_cached_cfg_still_rechecks_upstream_identity(self):
        e = self.exporter()
        e.build_payload(ROOT)
        from tools import verify_rom_fixed_renderer_script_records as legacy
        original = legacy._safe_file
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/experiments') as tmp:
            changed = Path(tmp) / 'manifest.json'
            changed.write_text('{}')
            def lookup(root, relative):
                return changed if relative == legacy.CFG_UPSTREAM[0][0] else original(root, relative)
            with patch.object(legacy, '_safe_file', side_effect=lookup):
                with self.assertRaisesRegex(ValueError, 'CFG upstream identity changed'):
                    e.build_payload(ROOT)
                with self.assertRaisesRegex(ValueError, 'CFG upstream identity changed'):
                    self.verifier().rebuild(ROOT, (ROOT / 'rom/base.gba').read_bytes())

    def test_coverage_consumer_projects_only_unknown_records(self):
        e, v = self.exporter(), self.verifier()
        baseline = json.loads(gzip.decompress((ROOT / 'notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-after.json.gz').read_bytes()))
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/experiments') as tmp:
            target = Path(tmp) / 'artifact'
            e.export_artifact(ROOT, target)
            claims = v.project_unknown_claims(ROOT, target, baseline['segments'])
            self.assertEqual([[0x42B5, 0x42BD], [0x42C2, 0x42C6]], [c['range'] for c in claims])
            self.assertEqual(12, sum(b - a for a, b in (c['range'] for c in claims)))
            for segments in [[], [{'range': [0x42B5, 0x42C6], 'primary_class': 'thumb_code'}],
                             [{'range': [0x42B5, 0x42BC], 'primary_class': 'unknown'}]]:
                with self.subTest(segments=segments), self.assertRaises(ValueError):
                    v.project_unknown_claims(ROOT, target, segments)


if __name__ == '__main__':
    unittest.main()
