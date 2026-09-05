"""TDD contract for the story-callback direct dependency closures."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class StoryCallbackDependencyClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_story_callback_dependency_closures as exporter
        from tools import verify_rom_story_callback_dependency_closures as verifier

        cls.exporter = exporter
        cls.verifier = verifier
        cls.payload = exporter.build_payload(ROOT)

    def test_exact_recursive_root_and_producer_denominators(self) -> None:
        closure = self.payload["target_closure"]
        self.assertEqual(9, closure["root_count"])
        self.assertEqual(6, closure["upstream_root_count"])
        self.assertEqual(3, closure["recursive_root_count"])
        producers = self.payload["producer_denominator"]
        self.assertEqual(9, producers["root_match_count"])
        self.assertEqual(6, producers["upstream_story_call_count"])
        self.assertEqual(3, producers["recursive_dependency_call_count"])
        self.assertEqual(1, producers["match_count_per_root"])

    def test_exact_code_literal_hole_and_exit_denominators(self) -> None:
        closure = self.payload["target_closure"]
        self.assertEqual(762, closure["instruction_count"])
        self.assertEqual(156, closure["basic_block_count"])
        self.assertEqual(18, len(closure["code_ranges"]))
        self.assertEqual(1656, closure["code_bytes"])
        self.assertEqual(71, closure["literal_reference_count"])
        self.assertEqual(69, closure["unique_literal_word_count"])
        self.assertEqual(14, len(closure["literal_ranges"]))
        self.assertEqual(276, closure["literal_bytes"])
        self.assertEqual(63, closure["opaque_accepted_exit_count"])
        owners = self.payload["upstream_evidence"]["opaque_target_owners"]
        self.assertEqual(37, len(owners))
        self.assertTrue(all(row["primary_class"] != "unknown" for row in owners))
        self.assertEqual(1, closure["accepted_boundary_continuation_count"])
        self.assertEqual(8, closure["structured_return_count"])
        self.assertEqual(
            [
                [0x068AF0, 0x068C10],
                [0x068DFC, 0x068E40],
                [0x0752D0, 0x075340],
                [0x086A54, 0x086C28],
                [0x08A69C, 0x08A6AA],
                [0x08B65C, 0x08B6EC],
                [0x08F68C, 0x08F6F4],
                [0x08F710, 0x08F738],
            ],
            [[row["root"], row["terminal"]]
             for row in closure["structured_return_contracts"]],
        )
        self.assertEqual(0x0861C8, closure["boundary_continuation_root"])
        self.assertEqual(0, closure["frontier_count"])
        self.assertEqual(6, len(closure["preserved_unknown_holes"]))
        self.assertEqual(12, closure["preserved_unknown_bytes"])

    def test_exact_promotion_and_narrow_scope(self) -> None:
        promotion = self.payload["promotion"]
        self.assertEqual(32, promotion["claim_count"])
        self.assertEqual(1656, promotion["target_code_bytes"])
        self.assertEqual(276, promotion["target_literal_bytes"])
        self.assertEqual(1932, promotion["promotion_bytes"])
        baseline = self.payload["coverage_baseline"]
        self.assertEqual(
            "artifacts/rom-story-callback-dependency-closures-precoverage-v1",
            baseline["identity"]["artifact"],
        )
        self.assertEqual(
            "b14d1778bc9961356cca7f319c9d2ae85a07a6811276f9ee0cd1bc2070e96b82",
            baseline["identity"]["coverage_sha256"],
        )
        self.assertEqual(1932, baseline["validated_current_unknown_bytes"])
        self.assertEqual(12, baseline["preserved_unknown_hole_bytes"])
        self.assertEqual(6_200_279, baseline["projected_classified_bytes"])
        self.assertEqual(91_177, baseline["projected_unknown_bytes"])
        for key in (
            "natural_runtime_reachability",
            "all_callback_dependencies_exhausted",
            "indirect_or_computed_producer_exhaustiveness",
            "business_semantics_or_abi",
            "alignment_holes_or_free_space",
            "editing_or_relocation_safety",
        ):
            self.assertFalse(self.payload["scope"][key])

    def test_roundtrip_and_independent_verifier(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            report = self.verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertTrue(report["contract_ok"], report)
            self.assertEqual(1932, report["promotion_bytes"])
            self.assertEqual(0, report["frontier_count"])

            original_safe_file = self.verifier._safe_file

            def reject_live_coverage(root: Path, relative: Path) -> Path:
                if relative == Path("sequel/rom-byte-coverage.json"):
                    raise AssertionError("verifier read mutable live coverage")
                return original_safe_file(root, relative)

            with mock.patch.object(self.verifier, "_safe_file", reject_live_coverage):
                post_advance_report = self.verifier.verify_artifact(ROOT, output)
            self.assertTrue(post_advance_report["verified"], post_advance_report)

    def test_verifier_does_not_import_exporter(self) -> None:
        path = ROOT / "tools/verify_rom_story_callback_dependency_closures.py"
        imports = [
            ast.unparse(node)
            for node in ast.walk(ast.parse(path.read_text()))
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        self.assertFalse(
            any("export_rom_story_callback_dependency_closures" in row for row in imports)
        )
        rebuilt = self.verifier._rebuild((ROOT / "rom/base.gba").read_bytes())
        self.assertEqual(762, rebuilt["target_closure"]["instruction_count"])
        self.assertEqual(9, rebuilt["producer_denominator"]["root_match_count"])

    def test_producer_code_literal_hole_and_boundary_mutations_fail_closed(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        cases = (
            (0x08F80E, "producer"),
            (0x068E1E, "producer"),
            (0x086B0A, "producer"),
            (0x08B65C, "closure"),
            (0x08F72A, "closure"),
            (0x08F6F8, "literal"),
            (0x08F6F6, "hole"),
            (0x0863FC, "boundary"),
            (0x0863FE, "boundary"),
        )
        for offset, pattern in cases:
            with self.subTest(offset=hex(offset)):
                changed = bytearray(rom)
                changed[offset] ^= 1
                with self.assertRaisesRegex(ValueError, pattern):
                    self.exporter._build_from_rom(ROOT, bytes(changed), verify_identity=False)
                with self.assertRaisesRegex(ValueError, pattern):
                    self.verifier._rebuild(bytes(changed), verify_identity=False)

    def test_artifact_and_exclusive_publish_guards(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            base = Path(directory)
            original = base / "original"
            self.exporter.export_artifact(ROOT, original)
            with self.assertRaises(FileExistsError):
                self.exporter.export_artifact(ROOT, original)
            mutated = base / "mutated"
            shutil.copytree(original, mutated)
            payload_path = mutated / self.exporter.PAYLOAD_NAME
            payload = json.loads(payload_path.read_text())
            payload["promotion"]["promotion_bytes"] += 1
            raw = (
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode()
            payload_path.write_bytes(raw)
            manifest_path = mutated / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][self.exporter.PAYLOAD_NAME] = {
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
            self.assertFalse(self.verifier.verify_artifact(ROOT, mutated)["verified"])

            alias = base / "alias"
            alias.symlink_to(base, target_is_directory=True)
            self.assertFalse(
                self.verifier.verify_artifact(ROOT, alias / "original")["verified"]
            )
            with self.assertRaisesRegex(ValueError, "staging output"):
                self.exporter.export_artifact(ROOT, ROOT / "notes/bad-story-dependency")


if __name__ == "__main__":
    unittest.main()
