"""TDD contract tests for the dependency-gated CFG proven-roots v20 packet."""

from __future__ import annotations

import ast
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CfgProvenRootsV20ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_cfg_proven_roots_v20 as exporter
        from tools import rom_cfg_proven_roots_v20_contract as contract

        cls.exporter = exporter
        cls.contract = contract
        from tools import verify_rom_cfg_proven_roots_v20 as verifier
        cls.verifier = verifier
        cls.rom = (ROOT / contract.ROM_PATH).read_bytes()
        cls.payload = exporter.build_payload(ROOT)

    def test_frozen_schema_and_root(self) -> None:
        payload = self.payload
        self.assertEqual("rom-cfg-proven-roots-v20", payload["schema"])
        self.assertEqual(0x062924, payload["root"]["file_offset"])
        self.assertEqual(
            self.contract.ROOT_ENTRY_SHA256, payload["root"]["entry_sha256"]
        )

    def test_exact_closure_and_promotion_denominators(self) -> None:
        payload = self.payload
        denominator = payload["target_local_denominator"]
        promotion = payload["promotion"]
        self.assertEqual(1_405, denominator["instruction_count"])
        self.assertEqual(249, denominator["basic_block_count"])
        self.assertEqual(39, denominator["literal_reference_count"])
        self.assertEqual(17, denominator["baseline_call_edge_count"])
        self.assertEqual(3, denominator["frontier_count"])
        self.assertEqual(1_150, promotion["promotion_bytes"])
        self.assertEqual(18, promotion["claim_count"])

    def test_complete_producer_denominator_accepts_only_instruction_owner(self) -> None:
        denominator = self.payload["producer_denominator"]
        self.assertEqual(2, denominator["match_count"])
        self.assertEqual([0x06108E, 0x061320],
                         [row["file_offset"] for row in denominator["matches"]])
        self.assertEqual([0x06108E],
                         [row["file_offset"] for row in self.payload["accepted_producers"]])
        rejected = self.payload["rejected_producers"]
        self.assertEqual([0x061320], [row["file_offset"] for row in rejected])
        self.assertFalse(rejected[0]["instruction_only"])
        self.assertEqual("coverage_owner_not_instruction_only",
                         rejected[0]["rejection_reason"])

    def test_full_ranges_literals_frontiers_and_opaque_owners(self) -> None:
        denominator = self.payload["target_local_denominator"]
        self.assertEqual(self.contract.CODE_RANGES,
                         tuple(map(tuple, denominator["code_ranges"])))
        self.assertEqual(self.contract.LITERAL_RANGES,
                         tuple(map(tuple, denominator["literal_ranges"])))
        self.assertEqual(39, len(denominator["literal_bindings"]))
        self.assertEqual(self.contract.OPAQUE_CALLS,
                         tuple((row["source"], row["target"])
                               for row in denominator["opaque_calls"]))
        self.assertEqual(
            [(0x062918, "0047", "r0"), (0x063336, "0047", "r0"),
             (0x063602, "0847", "r1")],
            [(row["file_offset"], row["raw_hex"], row["register"])
             for row in denominator["frontiers"]],
        )
        self.assertEqual(set(self.contract.OPAQUE_OWNERS),
                         {row["entry_file_offset"]
                          for row in denominator["opaque_target_owners"]})

    def test_story_overlay_and_exact_current_unknown_promotion(self) -> None:
        self.assertEqual((32, 1932, 0),
                         tuple(self.payload["story_overlay"][key]
                               for key in ("claim_count", "promotion_bytes", "overlap_bytes")))
        promotion = self.payload["promotion"]
        self.assertEqual(self.contract.UNKNOWN_CODE_RANGES,
                         tuple(map(tuple, promotion["code_ranges"])))
        self.assertEqual(self.contract.UNKNOWN_LITERAL_RANGES,
                         tuple(map(tuple, promotion["literal_ranges"])))
        self.assertEqual((1070, 80, 1150, 18, 10),
                         (promotion["code_bytes"], promotion["literal_bytes"],
                          promotion["promotion_bytes"], promotion["claim_count"],
                          len(promotion["union_ranges"])))
        self.assertEqual((91177, 90027, 6201429, 3082),
                         tuple(self.payload["coverage_projection"][key] for key in
                               ("unknown_after_story_overlay", "remaining_unknown_bytes",
                                "classified_bytes", "cumulative_promoted_bytes")))

    def test_representative_rom_mutations_fail_closed(self) -> None:
        for offset in (0x06108E, 0x061320, 0x062924, 0x0627F4, 0x062918):
            bad = bytearray(self.rom)
            bad[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.exporter.build_payload(ROOT, bytes(bad))

    def test_atomic_candidate_passes_independent_verifier_deterministically(self) -> None:
        experiment = ROOT / self.contract.EXPERIMENT_OUTPUT_ROOT
        with tempfile.TemporaryDirectory(dir=experiment) as raw:
            artifact = Path(raw) / "candidate"
            self.exporter.export(ROOT, artifact)
            first = self.verifier.verify_root(ROOT, artifact)
            second = self.verifier.verify_root(ROOT, artifact)
            self.assertEqual(first, second)
            self.assertTrue(first["verified"])
            self.assertEqual(1150, first["promotion_bytes"])
            with self.assertRaises(ValueError):
                self.exporter.export(ROOT, artifact)

    def test_verifier_is_raw_and_rejects_payload_and_extra_file(self) -> None:
        source = (ROOT / "tools/verify_rom_cfg_proven_roots_v20.py").read_text()
        imports = [node for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("tools.export_rom_cfg" in ast.unparse(node)
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
