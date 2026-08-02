from __future__ import annotations

import copy
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlefieldObjectProducerVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analyzer = importlib.import_module("tools.analyze_battlefield_object_producers")
        cls.verifier = importlib.import_module("tools.verify_battlefield_object_producers")
        cls.payload = cls.analyzer.analyze(ROOT)

    def test_accepts_fresh_independently_reconstructed_analysis(self):
        result = self.verifier.verify(ROOT, self.payload)
        self.assertEqual(
            result,
            {
                "errors": [],
                "verified_direct_allocator_calls": 7,
                "verified_group_18_paths": 3,
            },
        )

    def test_rejects_fabricated_type_2_producer(self):
        tampered = copy.deepcopy(self.payload)
        fake = copy.deepcopy(tampered["direct_allocator_calls"][0])
        fake["object_type"] = 2
        tampered["direct_allocator_calls"].append(fake)
        tampered["type_2_direct_producers"] = [fake]
        tampered["direct_object_types"].append(2)
        tampered["counts"]["direct_allocator_calls"] += 1
        tampered["counts"]["immediate_type_calls"] += 1
        tampered["counts"]["direct_type_2_calls"] = 1
        with self.assertRaisesRegex(ValueError, "direct allocator call denominator"):
            self.verifier.verify(ROOT, tampered)

    def test_rejects_sequence_18_mislabeled_as_sequence_7(self):
        tampered = copy.deepcopy(self.payload)
        tampered["group_18_selector_paths"][0]["sequence_id"] = 7
        with self.assertRaisesRegex(ValueError, "group 18 selector paths"):
            self.verifier.verify(ROOT, tampered)

    def test_cli_runs_from_the_repository_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "producers.json"
            artifact.write_text(json.dumps(self.payload), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/verify_battlefield_object_producers.py",
                    str(artifact),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(completed.stdout)["errors"], [])


if __name__ == "__main__":
    unittest.main()
