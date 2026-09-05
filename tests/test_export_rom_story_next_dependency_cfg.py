"""TDD contract tests for the story-next dependency CFG packet."""

from __future__ import annotations

import ast
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StoryNextDependencyCfgContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_story_next_dependency_cfg as exporter
        from tools import rom_story_next_dependency_cfg_contract as contract
        from tools import verify_rom_story_next_dependency_cfg as verifier

        cls.exporter = exporter
        cls.contract = contract
        cls.verifier = verifier
        cls.rom = (ROOT / contract.ROM_PATH).read_bytes()
        cls.payload = exporter.build_payload(ROOT)

    def test_schema_root_and_rom_identity(self) -> None:
        self.assertEqual("rom-story-next-dependency-cfg-v1", self.payload["schema"])
        self.assertEqual(0x088F10, self.payload["root"]["file_offset"])
        self.assertEqual(self.contract.ROOT_ENTRY_SHA256, self.payload["root"]["entry_sha256"])
        self.assertEqual(self.contract.ROM_SHA256, self.payload["rom"]["sha256"])

    def test_exact_cfg_denominators(self) -> None:
        denominator = self.payload["target_local_denominator"]
        self.assertEqual(338, denominator["instruction_count"])
        self.assertEqual(96, denominator["basic_block_count"])
        self.assertEqual(21, denominator["literal_reference_count"])
        self.assertEqual(43, denominator["baseline_call_edge_count"])
        self.assertEqual(3, denominator["frontier_count"])
        self.assertEqual(self.contract.CODE_RANGES, tuple(map(tuple, denominator["code_ranges"])))
        self.assertEqual(self.contract.LITERAL_RANGES, tuple(map(tuple, denominator["literal_ranges"])))
        self.assertEqual(self.contract.OPAQUE_CALLS,
                         tuple((row["source"], row["target"]) for row in denominator["opaque_calls"]))

    def test_producer_denominator_and_owner_gate(self) -> None:
        denominator = self.payload["producer_denominator"]
        self.assertEqual(2, denominator["match_count"])
        self.assertEqual([0x08F61A, 0x08F928],
                         [row["file_offset"] for row in denominator["matches"]])
        self.assertEqual([0x08F928],
                         [row["file_offset"] for row in self.payload["accepted_producers"]])
        self.assertEqual([0x08F61A],
                         [row["file_offset"] for row in self.payload["rejected_producers"]])
        self.assertFalse(self.payload["rejected_producers"][0]["instruction_only"])

    def test_frontiers_literals_and_promotion(self) -> None:
        denominator = self.payload["target_local_denominator"]
        self.assertEqual([(0x0884CA, "0047", "r0"),
                          (0x088648, "0847", "r1"),
                          (0x089062, "0847", "r1")],
                         [(row["file_offset"], row["raw_hex"], row["register"])
                          for row in denominator["frontiers"]])
        promotion = self.payload["promotion"]
        self.assertEqual((770, 84, 854, 19, 7),
                         (promotion["code_bytes"], promotion["literal_bytes"],
                          promotion["promotion_bytes"], promotion["claim_count"],
                          len(promotion["union_ranges"])))
        self.assertEqual(self.contract.UNKNOWN_CODE_RANGES,
                         tuple(map(tuple, promotion["code_ranges"])))
        self.assertEqual(self.contract.UNKNOWN_LITERAL_RANGES,
                         tuple(map(tuple, promotion["literal_ranges"])))

    def test_dependency_overlays_and_projection(self) -> None:
        self.assertEqual((32, 1932, 0),
                         tuple(self.payload["story_overlay"][key]
                               for key in ("claim_count", "promotion_bytes", "overlap_bytes")))
        self.assertEqual((18, 1150, 0),
                         tuple(self.payload["v20_overlay"][key]
                               for key in ("claim_count", "promotion_bytes", "overlap_bytes")))
        self.assertEqual((6202283, 89173, 3936),
                         tuple(self.payload["coverage_projection"][key]
                               for key in ("classified_bytes", "remaining_unknown_bytes", "cumulative_promoted_bytes")))

    def test_representative_mutations_fail_closed(self) -> None:
        for offset in (0x08F61A, 0x08F928, 0x088F10, 0x088444, 0x0884CC, 0x0884CA):
            bad = bytearray(self.rom)
            bad[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.exporter.build_payload(ROOT, bytes(bad))

    def test_cfg_inventory_dependency_is_exact(self) -> None:
        self.assertEqual(self.contract.CFG_INVENTORY_MANIFEST_SHA256,
                         self.payload["cfg_inventory"]["manifest_sha256"])
        self.assertEqual(self.contract.CFG_INVENTORY_PAYLOAD_SHA256,
                         self.payload["cfg_inventory"]["payload_sha256"])
        self.assertEqual(self.contract.CFG_INVENTORY_VERIFIER_SHA256,
                         self.payload["cfg_inventory"]["verifier_sha256"])
        self.assertEqual(
            [
                {"id": "block-thumb-065404", "range": [0x065404, 0x0654A4],
                 "instruction_count": 79,
                 "bytes_sha256": self.contract.CFG_INVENTORY_BLOCK_BYTES_SHA256},
                {"id": "block-thumb-08cbf4", "range": [0x08CBF4, 0x08CC02],
                 "instruction_count": 6,
                 "bytes_sha256":
                     self.contract.CFG_INVENTORY_INTERNAL_BF4_BYTES_SHA256},
                {"id": "block-thumb-08cc18", "range": [0x08CC18, 0x08CC26],
                 "instruction_count": 6,
                 "bytes_sha256":
                     self.contract.CFG_INVENTORY_INTERNAL_BLOCK_BYTES_SHA256},
            ],
            self.payload["cfg_inventory"]["entry_blocks"],
        )
        owner = next(
            row for row in self.payload["target_local_denominator"]
            ["opaque_call_owners"]
            if row["source"] == 0x08862E and row["target"] == 0x08CC18
        )
        self.assertEqual(("block-thumb-08cc18",
                          self.contract.CFG_INVENTORY.as_posix()),
                         (owner["claim_id"], owner["owner_artifact"]))

    def test_atomic_candidate_passes_independent_verifier_deterministically(self) -> None:
        experiment = ROOT / self.contract.EXPERIMENT_OUTPUT_ROOT
        with tempfile.TemporaryDirectory(dir=experiment) as raw:
            artifact = Path(raw) / "candidate"
            self.exporter.export(ROOT, artifact)
            first = self.verifier.verify_root(ROOT, artifact)
            second = self.verifier.verify_root(ROOT, artifact)
            self.assertEqual(first, second)
            self.assertTrue(first["verified"])
            self.assertEqual(854, first["promotion_bytes"])
            with self.assertRaises(ValueError):
                self.exporter.export(ROOT, artifact)

    def test_verifier_is_raw_and_rejects_payload_and_extra_file(self) -> None:
        source = (ROOT / "tools/verify_rom_story_next_dependency_cfg.py").read_text()
        imports = [node for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("tools.export_rom_story_next" in ast.unparse(node)
                             for node in imports))
        experiment = ROOT / self.contract.EXPERIMENT_OUTPUT_ROOT
        with tempfile.TemporaryDirectory(dir=experiment) as raw:
            artifact = Path(raw) / "candidate"
            self.exporter.export(ROOT, artifact)
            payload_path = artifact / self.contract.PAYLOAD_NAME
            payload = json.loads(payload_path.read_text())
            payload["promotion"]["promotion_bytes"] += 2
            payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            self.assertFalse(self.verifier.verify_root(ROOT, artifact)["verified"])
            (artifact / "extra").write_text("forbidden")
            self.assertFalse(self.verifier.verify_root(ROOT, artifact)["verified"])

    def test_output_symlink_ancestor_is_rejected(self) -> None:
        experiment = ROOT / self.contract.EXPERIMENT_OUTPUT_ROOT
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory(dir=experiment) as raw:
            link = Path(raw) / "escape"
            os.symlink(outside, link)
            with self.assertRaises(ValueError):
                self.exporter.export(ROOT, link / "candidate")


if __name__ == "__main__":
    unittest.main()
