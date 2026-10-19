"""Publication and coverage wiring for the four frozen dependency packets."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'build/experiments/active/small-cfg-tier2/resume-20260930-v1'


class BatchPublicationTests(unittest.TestCase):
    def publisher(self):
        spec = importlib.util.find_spec('tools.export_rom_small_cfg_dependency_batch')
        self.assertIsNotNone(spec, 'four validated packets lack a publication entry point')
        return importlib.import_module(spec.name)

    def verifier(self):
        return importlib.import_module('tools.verify_rom_small_cfg_dependency_batch')

    def test_publication_replays_stably_and_refuses_overwrite(self):
        publisher = self.publisher()
        with tempfile.TemporaryDirectory(dir=RUN) as temporary:
            target = Path(temporary) / 'final'
            publisher.export_batch(ROOT, target)
            first = self.verifier().verify_artifact(ROOT, target)
            second = self.verifier().verify_artifact(ROOT, target)
            self.assertEqual(first, second)
            self.assertTrue(first['verified'])
            self.assertEqual((first['promotion_bytes'], first['claim_count']), (118, 21))
            self.assertFalse(first['natural_runtime_reachability_claimed'])
            self.assertEqual(first['packet_count'], 4)
            before = {p.name: p.read_bytes() for p in target.iterdir()}
            with self.assertRaises(FileExistsError):
                publisher.export_batch(ROOT, target)
            self.assertEqual(before, {p.name: p.read_bytes() for p in target.iterdir()})

    def test_unknown_packet_mutation_and_extra_member_fail_closed(self):
        publisher = self.publisher()
        with tempfile.TemporaryDirectory(dir=RUN) as temporary:
            target = Path(temporary) / 'final'
            publisher.export_batch(ROOT, target)
            payload = target / 'rom-small-cfg-dependency-batch.json'
            original = payload.read_bytes()
            data = json.loads(original)
            data['packets']['wrappers']['promotion']['claims'][0]['range'][1] += 2
            payload.write_text(json.dumps(data))
            self.assertFalse(self.verifier().verify_artifact(ROOT, target)['verified'])
            payload.write_bytes(original)
            (target / 'unexpected').write_text('extra')
            self.assertFalse(self.verifier().verify_artifact(ROOT, target)['verified'])

    def test_paths_are_rejected_before_creating_output(self):
        publisher = self.publisher()
        with tempfile.TemporaryDirectory(dir=RUN) as temporary:
            parent = Path(temporary)
            for target in [parent / 'missing' / '..' / 'escape', ROOT / 'unsafe-batch-output']:
                with self.subTest(target=target), self.assertRaises(ValueError):
                    publisher.export_batch(ROOT, target)
            self.assertFalse((parent / 'missing').exists())
            (parent / 'alias').symlink_to(parent, target_is_directory=True)
            with self.assertRaises((OSError, ValueError)):
                publisher.export_batch(ROOT, parent / 'alias' / 'final')
            self.assertFalse((parent / 'final').exists())

    def test_coverage_projection_is_wired_after_v21(self):
        source = (ROOT / 'tools/audit_rom_byte_coverage.py').read_text()
        call = 'claims += _small_cfg_dependency_batch_claims(root, rom, claims)'
        self.assertIn(call, source, 'validated four-packet batch is absent from canonical rebuild')
        self.assertGreater(source.index(call), source.index('claims += _cfg_proven_roots_v21_claims(root, rom, claims)'))

    def test_final_manifest_matches_existing_promotion_contract(self):
        publisher = self.publisher()
        from tools.experiment_workspace import _validate_promotion_manifest
        with tempfile.TemporaryDirectory(dir=RUN) as temporary:
            target = Path(temporary) / 'final'
            publisher.export_batch(ROOT, target)
            self.assertEqual(_validate_promotion_manifest(target)['artifact_status'], 'accepted')


if __name__ == '__main__':
    unittest.main()
