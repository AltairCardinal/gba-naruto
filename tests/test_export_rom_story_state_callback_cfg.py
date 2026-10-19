#!/usr/bin/env python3
"""TDD contract tests for the story-state scheduler callback CFG packet."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/story-state-callback-cfg-20260902/luna-r1"
SCHEMA = "rom-story-state-callback-cfg-v1"
PAYLOAD_NAME = "rom-story-state-callback-cfg.json"
MANIFEST_NAME = "manifest.json"
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "b71a91d1e3c469a884f6d434a82ce23e751e201e83728e6ffc040a6226bfed52"
ROOT_OFFSET = 0x08F73C
ROOT_POINTER = 0x0808F73D
CODE_RANGES = [
    [0x08F73C, 0x08F77A],
    [0x08F784, 0x08F8EE],
    [0x08F8F4, 0x08F974],
    [0x08F978, 0x08F99A],
    [0x08F9A0, 0x08FA00],
    [0x08FA04, 0x08FA32],
]
LITERAL_RANGES = [
    [0x08F77C, 0x08F784],
    [0x08F8F0, 0x08F8F4],
    [0x08F974, 0x08F978],
    [0x08F99C, 0x08F9A0],
    [0x08FA00, 0x08FA04],
]
PROMOTION_CODE_RANGES = [
    [0x08F73C, 0x08F77A],
    [0x08F784, 0x08F844],
    [0x08F848, 0x08F866],
    [0x08F872, 0x08F8EE],
    [0x08F8F4, 0x08F974],
    [0x08F978, 0x08F99A],
    [0x08F9A0, 0x08F9E2],
    [0x08FA08, 0x08FA32],
]
PROMOTION_LITERAL_RANGES = LITERAL_RANGES
EXCLUDED_GAPS = [
    [0x08F77A, 0x08F77C],
    [0x08F8EE, 0x08F8F0],
    [0x08F99A, 0x08F99C],
    [0x08FA32, 0x08FA34],
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


class StoryStateCallbackCfgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_story_state_callback_cfg as exporter
        from tools import verify_rom_story_state_callback_cfg as verifier

        cls.exporter = exporter
        cls.verifier = verifier
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_payload_closes_identity_scheduler_and_producers(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual(SCHEMA, payload["schema"])
        self.assertEqual(
            {"path": "rom/base.gba", "size": ROM_SIZE, "sha256": ROM_SHA256},
            payload["rom"],
        )
        self.assertEqual(
            {"path": "sequel/rom-byte-coverage.json", "sha256": COVERAGE_SHA256},
            payload["coverage_baseline"]["identity"],
        )
        self.assertEqual(ROOT_OFFSET, payload["root"]["file_offset"])
        self.assertEqual(ROOT_POINTER, payload["root"]["thumb_pointer"])
        producers = payload["producer_denominator"]
        self.assertEqual([], producers["callback_root_direct_branches"])
        self.assertEqual(
            [[0x08F7F4, 0x08FA26, "b"], [0x08F80A, 0x08FA2C, "b"]],
            producers["internal_handler_direct_branches"],
        )
        self.assertEqual([[0x08FA26, 0x08C4CC, "bl"]], producers["consumer_direct_bl"])
        self.assertEqual([], producers["target_pointer_occurrences"]["0x0808FA2C"])
        self.assertEqual([], producers["target_even_u32_occurrences"]["0x0808FA2C"])

    def test_cfg_metrics_ranges_and_literal_bindings_are_frozen(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        cfg = payload["target_local_denominator"]
        self.assertEqual(336, cfg["instruction_count"])
        self.assertEqual(728, cfg["code_bytes"])
        self.assertEqual(6, cfg["code_range_count"])
        self.assertEqual(28, cfg["opaque_external_call_count"])
        self.assertEqual(0, cfg["frontier_count"])
        self.assertEqual(CODE_RANGES, cfg["code_ranges"])
        self.assertEqual(LITERAL_RANGES, cfg["literal_ranges"])
        self.assertEqual(
            [
                [0x08F746, 0x08F77C, "0x03000075"],
                [0x08F74E, 0x08F780, "0x020311D4"],
                [0x08F8E4, 0x08F8F0, "0x000003E7"],
                [0x08F93A, 0x08F974, "0x02026804"],
                [0x08F962, 0x08F974, "0x02026804"],
                [0x08F98A, 0x08F99C, "0x020311D4"],
                [0x08F9F8, 0x08FA00, "0x020240AC"],
            ],
            cfg["literal_bindings"],
        )

    def test_promotion_is_current_unknown_only_and_keeps_four_gaps(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        promotion = payload["promotion"]
        self.assertEqual(PROMOTION_CODE_RANGES, promotion["code_ranges"])
        self.assertEqual(PROMOTION_LITERAL_RANGES, promotion["literal_ranges"])
        self.assertEqual(EXCLUDED_GAPS, promotion["preserved_unknown_gaps"])
        self.assertEqual(678, promotion["code_bytes"])
        self.assertEqual(24, promotion["literal_bytes"])
        self.assertEqual(702, promotion["promotion_bytes"])
        self.assertEqual(8, promotion["preserved_unknown_bytes"])
        self.assertTrue(all(row["baseline_unknown_only"] for row in promotion["claims"]))

    def test_state_compare_chain_and_rom_mutations_fail_closed(self) -> None:
        for offset in (0x08F7EC, 0x08F802, 0x08FA26, 0x08F746, 0x08F77C):
            mutated = bytearray(self.rom)
            mutated[offset] ^= 1
            with self.subTest(offset=hex(offset)), self.assertRaises(ValueError):
                self.exporter.build_payload(ROOT, bytes(mutated))

    def test_verifier_rebuild_is_independent_and_mutations_fail_closed(self) -> None:
        source = (ROOT / "tools/verify_rom_story_state_callback_cfg.py").read_text()
        imports = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_story_state_callback_cfg" in ast.unparse(node) for node in imports))
        rebuilt = self.verifier.rebuild_payload(ROOT, self.rom)
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual(payload, rebuilt)
        mutated = bytearray(self.rom)
        mutated[0x08FA26] ^= 1
        with self.assertRaises(ValueError):
            self.verifier.rebuild_payload(ROOT, bytes(mutated))

    def test_artifact_has_only_manifest_and_payload_and_is_noreplace(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "candidate"
            manifest = self.exporter.export_artifact(ROOT, output)
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual({MANIFEST_NAME, PAYLOAD_NAME}, {item.name for item in output.iterdir()})
            self.assertTrue(self.verifier.verify_artifact(ROOT, output)["verified"])
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, output)

    def test_unsafe_output_and_nested_members_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw, tempfile.TemporaryDirectory() as outside:
            parent = Path(raw)
            linked = parent / "linked"
            linked.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, linked / "candidate")
            output = parent / "candidate"
            self.exporter.export_artifact(ROOT, output)
            (output / "nested").mkdir()
            self.assertFalse(self.verifier.verify_artifact(ROOT, output)["verified"])

    def test_baseline_and_post_promotion_owner_states_are_explicit(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual("baseline_unknown", payload["coverage_baseline"]["state"])
        self.assertEqual("exact_owner_required", payload["coverage_projection"]["post_promotion_gate"])
        self.assertTrue(payload["scope"]["post_promotion_owner_verification_supported"])
        replay = self.verifier.rebuild_payload(
            ROOT,
            self.rom,
            validate_live_coverage=False,
        )
        self.assertEqual(payload, replay)
        self.assertEqual(
            "historical_build_receipt_replay",
            replay["coverage_baseline"]["replay_mode"],
        )


if __name__ == "__main__":
    unittest.main()
