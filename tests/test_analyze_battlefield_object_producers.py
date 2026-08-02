from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlefieldObjectProducerAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = importlib.import_module("tools.analyze_battlefield_object_producers")
        cls.result = cls.module.analyze(ROOT)

    def test_enumerates_every_direct_allocator_call(self):
        self.assertEqual(self.result["schema"], "battlefield-object-producers-v1")
        self.assertEqual(
            self.result["counts"],
            {
                "direct_allocator_calls": 7,
                "immediate_type_calls": 7,
                "direct_type_2_calls": 0,
            },
        )
        self.assertEqual(
            [row["callsite"] for row in self.result["direct_allocator_calls"]],
            [
                "0x0806E892",
                "0x0806E8F2",
                "0x0806E906",
                "0x0806E91E",
                "0x0806E932",
                "0x0806E940",
                "0x0807752C",
            ],
        )

    def test_classifies_immediate_object_types_without_inventing_type_2(self):
        self.assertEqual(
            [row["object_type"] for row in self.result["direct_allocator_calls"]],
            [3, 3, 4, 5, 4, 6, 1],
        )
        self.assertEqual(self.result["direct_object_types"], [1, 3, 4, 5, 6])
        self.assertEqual(self.result["type_2_direct_producers"], [])

    def test_preserves_the_sequence_7_and_sequence_18_callsite_boundary(self):
        self.assertEqual(
            self.result["group_18_selector_paths"],
            [
                {
                    "selector_callsite": "0x0806C5BA",
                    "sequence_id": 18,
                    "spawn_callsite": "0x0806C5D8",
                    "source": "natural hardcoded selector path",
                },
                {
                    "selector_callsite": "0x08081BDA",
                    "sequence_id": 7,
                    "spawn_callsite": "0x08081BF4",
                    "source": "type-2 battlefield-object expiry branch",
                },
                {
                    "selector_callsite": "0x08081FB8",
                    "sequence_id": 7,
                    "spawn_callsite": "0x08081FD2",
                    "source": "type-1 battlefield-object expiry zero-event branch",
                },
            ],
        )

    def test_scope_keeps_type_2_natural_producer_unresolved(self):
        self.assertEqual(
            self.result["scope"],
            {
                "direct_allocator_call_denominator_complete": True,
                "direct_type_2_producer_found": False,
                "indirect_or_post_allocation_type_2_producer_proven_absent": False,
                "natural_group_18_route_proven": False,
                "modified_rom_pixel_ab_proven": False,
            },
        )

    def test_cli_runs_from_the_repository_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "producers.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/analyze_battlefield_object_producers.py",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(output.read_text()), json.loads(completed.stdout))


if __name__ == "__main__":
    unittest.main()
