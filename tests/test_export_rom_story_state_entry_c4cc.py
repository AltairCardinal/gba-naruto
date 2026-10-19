#!/usr/bin/env python3
"""TDD contract for the target-local story-state entry at 0x0808C4CC."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/story-state-entry-c4cc-20260902/sol-r1"
SCHEMA = "rom-story-state-entry-c4cc-v1"
PAYLOAD = "rom-story-state-entry-c4cc.json"
MANIFEST = "manifest.json"
CODE_RANGE = [0x08C4CC, 0x08C584]
LITERAL_RANGE = [0x08C584, 0x08C5A8]
REMAINING_RANGE = [0x08C5A8, 0x08CBB4]
LITERAL_BINDINGS = [
    [0x08C4D6, 0x08C584, "0x0300004C"],
    [0x08C50E, 0x08C588, "0x08405EA4"],
    [0x08C510, 0x08C58C, "0x06006800"],
    [0x08C516, 0x08C590, "0x08405F10"],
    [0x08C520, 0x08C594, "0x08405FF0"],
    [0x08C522, 0x08C598, "0x05000100"],
    [0x08C52A, 0x08C59C, "0x04000008"],
    [0x08C530, 0x08C5A0, "0x03000054"],
    [0x08C548, 0x08C5A4, "0x08408BC4"],
]


class StoryStateEntryC4ccTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_story_state_entry_c4cc as exporter
        from tools import verify_rom_story_state_entry_c4cc as verifier

        cls.exporter = exporter
        cls.verifier = verifier
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_dependency_and_unique_producer_are_frozen(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual(SCHEMA, payload["schema"])
        dependency = payload["upstream_dependency"]
        self.assertTrue(dependency["verified"])
        self.assertEqual([0x08FA26, 0x08FA2A], dependency["required_source_range"])
        self.assertEqual(
            "armv4t_story_state_callback_cfg", dependency["required_primary_class"]
        )
        denominator = payload["producer_denominator"]
        self.assertEqual([[0x08FA26, 0x08C4CC, "bl"]], denominator["direct"])
        self.assertEqual([], denominator["thumb_pointer_occurrences"])
        self.assertEqual([], denominator["even_u32_occurrences"])

    def test_target_local_cfg_and_strict_return_are_exact(self) -> None:
        cfg = self.exporter.build_payload(ROOT)["target_local_cfg"]
        self.assertEqual(CODE_RANGE, cfg["code_range"])
        self.assertEqual(78, cfg["instruction_count"])
        self.assertEqual(184, cfg["instruction_bytes"])
        self.assertEqual(15, cfg["basic_block_count"])
        self.assertEqual(14, cfg["opaque_external_call_count"])
        self.assertEqual(0, cfg["local_branch_count"])
        self.assertEqual(0, cfg["hole_count"])
        self.assertEqual(0, cfg["frontier_count"])
        self.assertEqual(
            [0x08C57C, 0x08C57E, 0x08C580, 0x08C582],
            cfg["strict_return"]["instruction_offsets"],
        )
        self.assertEqual("pop_r0_then_bx_r0", cfg["strict_return"]["proof"])

    def test_literals_boundary_and_projection_are_exact(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        cfg = payload["target_local_cfg"]
        self.assertEqual(LITERAL_RANGE, cfg["literal_range"])
        self.assertEqual(LITERAL_BINDINGS, cfg["literal_bindings"])
        self.assertEqual([0x08C5A8, "10b5"], cfg["next_entry_excluded"])
        promotion = payload["promotion"]
        self.assertEqual([CODE_RANGE], promotion["code_ranges"])
        self.assertEqual([LITERAL_RANGE], promotion["literal_ranges"])
        self.assertEqual(184, promotion["code_bytes"])
        self.assertEqual(36, promotion["literal_bytes"])
        self.assertEqual(220, promotion["promotion_bytes"])
        self.assertEqual(REMAINING_RANGE, promotion["remaining_unknown_range"])
        self.assertEqual(1548, promotion["remaining_unknown_bytes"])
        self.assertEqual("projection_deferred_to_coverage_auditor", payload["coverage_projection"]["gate"])

    def test_verifier_is_independent_and_rebuilds_same_payload(self) -> None:
        source = (ROOT / "tools/verify_rom_story_state_entry_c4cc.py").read_text()
        imports = [
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        self.assertFalse(
            any("export_rom_story_state_entry_c4cc" in ast.unparse(node) for node in imports)
        )
        self.assertEqual(
            self.exporter.build_payload(ROOT),
            self.verifier.rebuild_payload(ROOT, self.rom, validate_live_coverage=False),
        )

    def test_rom_producer_epilogue_ldr_literal_and_boundary_mutations_fail(self) -> None:
        offsets = [
            0x08FA26,
            0x08C4CC,
            0x08C57C,
            0x08C580,
            0x08C582,
            0x08C5A8,
        ]
        offsets.extend(row[0] for row in LITERAL_BINDINGS)
        offsets.extend(row[1] for row in LITERAL_BINDINGS)
        for offset in offsets:
            mutated = bytearray(self.rom)
            mutated[offset] ^= 1
            with self.subTest(offset=hex(offset)), self.assertRaises(ValueError):
                self.exporter.build_payload(ROOT, bytes(mutated))
            with self.subTest(verifier_offset=hex(offset)), self.assertRaises(ValueError):
                self.verifier.rebuild_payload(ROOT, bytes(mutated))

    def test_artifact_noreplace_and_member_contract(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "candidate"
            manifest = self.exporter.export_artifact(ROOT, output)
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual({PAYLOAD, MANIFEST}, {item.name for item in output.iterdir()})
            self.assertTrue(self.verifier.verify_artifact(ROOT, output)["verified"])
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, output)
            alias = Path(raw) / "alias"
            alias.symlink_to(output, target_is_directory=True)
            self.assertFalse(self.verifier.verify_artifact(ROOT, alias)["verified"])
            (output / "nested").mkdir()
            self.assertFalse(self.verifier.verify_artifact(ROOT, output)["verified"])

    def test_symlink_and_path_escape_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw, tempfile.TemporaryDirectory() as outside:
            linked = Path(raw) / "linked"
            linked.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, linked / "candidate")
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, Path(outside) / "candidate")

    def test_replay_uses_historical_receipt_without_live_coverage(self) -> None:
        payload = self.verifier.rebuild_payload(ROOT, self.rom, validate_live_coverage=False)
        receipt = payload["coverage_baseline"]
        self.assertEqual("historical_build_receipt_replay", receipt["replay_mode"])
        self.assertFalse(receipt["live_coverage_verified_on_replay"])
        self.assertTrue(receipt["observed_during_artifact_build"])


if __name__ == "__main__":
    unittest.main()
