"""TDD contract tests for the story-selector dependency CFG packet."""

from __future__ import annotations

import ast
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class StorySelectorDependencyCfgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_story_selector_dependency_cfg as exporter
        from tools import rom_story_selector_dependency_cfg_contract as contract
        from tools import verify_rom_story_selector_dependency_cfg as verifier

        cls.exporter = exporter
        cls.contract = contract
        cls.verifier = verifier
        cls.rom = (ROOT / contract.ROM_PATH).read_bytes()
        cls.payload = exporter.build_payload(ROOT)

    def test_frozen_root_and_exact_cfg_denominator(self) -> None:
        self.assertEqual("rom-story-selector-dependency-cfg-v1", self.payload["schema"])
        self.assertEqual([0x08F544, 0x08F594], self.payload["root"]["range"])
        self.assertEqual(self.contract.ROOT_BYTES_SHA256, self.payload["root"]["bytes_sha256"])
        denominator = self.payload["target_local_denominator"]
        self.assertEqual((37, 80, 0, 0), tuple(denominator[key] for key in (
            "instruction_count", "instruction_bytes", "hole_count", "frontier_count")))
        self.assertEqual(self.contract.INSTRUCTION_VECTOR_SHA256,
                         denominator["instruction_vector_sha256"])

    def test_complete_direct_entry_denominator_and_owner_gate(self) -> None:
        rows = self.payload["producer_denominator"]["matches"]
        self.assertEqual([0x08F676, 0x08F8DE], [row["file_offset"] for row in rows])
        self.assertEqual([0x08F8DE], [row["file_offset"] for row in self.payload["accepted_producers"]])
        self.assertEqual([0x08F676], [row["file_offset"] for row in self.payload["rejected_producers"]])
        self.assertEqual("source_owner_not_instruction_only", rows[0]["rejection_reason"])
        self.assertEqual("story-callback-reachable_thumb_code-04-08f872",
                         rows[1]["coverage_owner_claim_ids"][0])

    def test_opaque_calls_preowned_literal_and_fallthrough(self) -> None:
        denominator = self.payload["target_local_denominator"]
        self.assertEqual(self.contract.OPAQUE_CALLS,
                         tuple((row["source"], row["target"]) for row in denominator["opaque_calls"]))
        self.assertEqual(1, denominator["preowned_literal_count"])
        self.assertEqual([0x08F5B0, 0x08F5B4], denominator["preowned_literals"][0]["range"])
        self.assertEqual(0x08F594, denominator["fallthrough"]["file_offset"])
        self.assertEqual("consumer_code_slice", denominator["fallthrough"]["coverage_owner_class"])

    def test_tier_one_promotion_is_only_the_root(self) -> None:
        promotion = self.payload["promotion"]
        self.assertEqual((1, 80, [[0x08F544, 0x08F594]]),
                         (promotion["claim_count"], promotion["promotion_bytes"], promotion["ranges"]))
        self.assertEqual((80, 0, 0), tuple(self.payload["coverage_projection"][key] for key in (
            "target_promoted_bytes", "hole_bytes", "frontier_count")))

    def test_raw_cfg_denominator_is_rebuilt_instead_of_trusting_constants(self) -> None:
        segments, starts = self.verifier._coverage(ROOT)
        for module, operation in (
                (self.exporter, lambda: self.exporter._root_denominator(
                    self.rom, segments, starts)),
                (self.verifier, lambda: self.verifier._denominator(
                    self.rom, segments, starts))):
            with self.subTest(module=module.__name__, field="instruction-vector"), \
                    mock.patch.object(module, "INSTRUCTION_VECTOR_SHA256", "0" * 64), \
                    self.assertRaises(ValueError):
                operation()
            with self.subTest(module=module.__name__, field="opaque-call-denominator"), \
                    mock.patch.object(module, "OPAQUE_CALLS", module.OPAQUE_CALLS[:-1]), \
                    self.assertRaises(ValueError):
                operation()

    def test_representative_rom_mutations_fail_closed(self) -> None:
        for offset in (0x08F544, 0x08F552, 0x08F582, 0x08F588, 0x08F590,
                       0x08F5B0, 0x08F676, 0x08F8DE):
            bad = bytearray(self.rom)
            bad[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.exporter.build_payload(ROOT, bytes(bad))

    def test_atomic_export_and_independent_verifier_are_deterministic(self) -> None:
        experiment = ROOT / self.contract.EXPERIMENT_OUTPUT_ROOT
        experiment.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=experiment) as raw:
            artifact = Path(raw) / "candidate"
            self.exporter.export(ROOT, artifact)
            first = self.verifier.verify_root(ROOT, artifact)
            second = self.verifier.verify_root(ROOT, artifact)
            self.assertEqual(first, second)
            self.assertTrue(first["verified"])
            self.assertEqual(80, first["promotion_bytes"])
            with self.assertRaises(ValueError):
                self.exporter.export(ROOT, artifact)

    def test_verifier_rejects_payload_mutation_extra_member_and_symlink(self) -> None:
        source = (ROOT / "tools/verify_rom_story_selector_dependency_cfg.py").read_text()
        imports = [node for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_story_selector" in ast.unparse(node) for node in imports))
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
        with tempfile.TemporaryDirectory(dir=experiment) as raw:
            artifact = Path(raw) / "candidate"
            self.exporter.export(ROOT, artifact)
            payload_path = artifact / self.contract.PAYLOAD_NAME
            payload_path.unlink()
            os.symlink(ROOT / self.contract.ROM_PATH, payload_path)
            self.assertFalse(self.verifier.verify_root(ROOT, artifact)["verified"])

    def test_output_traversal_and_symlink_ancestor_are_rejected(self) -> None:
        experiment = ROOT / self.contract.EXPERIMENT_OUTPUT_ROOT
        with self.assertRaises(ValueError):
            self.exporter.export(ROOT, experiment / ".." / "escape")
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory(dir=experiment) as raw:
            link = Path(raw) / "escape"
            os.symlink(outside, link)
            with self.assertRaises(ValueError):
                self.exporter.export(ROOT, link / "candidate")

    def test_publish_uses_true_atomic_no_replace(self) -> None:
        source = (ROOT / "tools/export_rom_story_selector_dependency_cfg.py").read_text()
        self.assertIn("renameatx_np", source)
        self.assertIn("renameat2", source)
        experiment = ROOT / self.contract.EXPERIMENT_OUTPUT_ROOT
        with tempfile.TemporaryDirectory(dir=experiment) as raw:
            parent = Path(raw)
            stage = parent / "stage"
            target = parent / "target"
            stage.mkdir()
            target.mkdir()
            with self.assertRaises(FileExistsError):
                self.exporter._publish_exclusive(stage, target)
            self.assertTrue(stage.is_dir())
            self.assertTrue(target.is_dir())


if __name__ == "__main__":
    unittest.main()
