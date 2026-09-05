"""TDD contract for the dependency-gated text-BG task closure packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import export_rom_text_bg_task_closure as exporter
from tools import verify_rom_text_bg_task_closure as verifier


ROOT = Path(__file__).resolve().parents[1]


class TextBgTaskClosureTests(unittest.TestCase):
    def test_builds_exact_dependency_gated_closure(self) -> None:
        payload = exporter.build_payload(ROOT)
        self.assertEqual(exporter.SCHEMA, payload["schema"])
        closure = payload["closure"]
        self.assertEqual(10, len(closure["roots"]))
        self.assertEqual(1330, closure["instruction_count"])
        self.assertEqual(2782, closure["code_bytes"])
        self.assertEqual(20, len(closure["code_ranges"]))
        self.assertEqual(80, closure["literal_reference_count"])
        self.assertEqual(65, closure["unique_literal_word_count"])
        self.assertEqual(260, closure["literal_bytes"])
        self.assertEqual(13, len(closure["literal_ranges"]))
        self.assertEqual(
            "e838c91e123f085650bd0618c8404be31651a2596c9f461cb912b093a88c5d59",
            closure["code_bytes_sha256"],
        )
        self.assertEqual(
            "f94d37c6c3e101caf1b284db2f7bdcc43ab87c67f210b7aa9e1e5974dfa8a2bc",
            closure["literal_bytes_sha256"],
        )

    def test_freezes_callback_registration_and_dispatch(self) -> None:
        callback = exporter.build_payload(ROOT)["callback_registration"]
        self.assertEqual("0x0808AA51", callback["callback_pointer"])
        self.assertEqual("0x080626B4", callback["allocator_variant"])
        self.assertEqual("0x28", callback["task_callback_field"])
        self.assertEqual("0x0806294C", callback["dispatch_field_load"])
        self.assertEqual("0x0809C114", callback["dispatch_bx_r1_wrapper"])
        self.assertTrue(callback["upstream_task_binding_verified"])

    def test_promotion_excludes_queued_and_canonical_dependencies(self) -> None:
        promotion = exporter.build_payload(ROOT)["promotion"]
        self.assertEqual(2940, promotion["promotion_bytes"])
        self.assertEqual(2692, promotion["code_bytes"])
        self.assertEqual(248, promotion["literal_bytes"])
        self.assertEqual(21, len(promotion["code_ranges"]))
        self.assertEqual(13, len(promotion["literal_ranges"]))
        self.assertEqual(
            "08bfc04a19934023b26625f1334733a8a22ac539c7f3e8624677b90cdbdcb9bf",
            promotion["code_bytes_sha256"],
        )
        self.assertEqual(
            "3f24f548c7eea5ee66c6014eddb53a925ad675c25c30114375b699b3e22a15a9",
            promotion["literal_bytes_sha256"],
        )
        excluded = promotion["excluded_dependencies"]
        self.assertIn([0x08ACC8, 0x08ACF2], excluded["queued_code_ranges"])
        self.assertIn([0x08AEB4, 0x08AEC0], excluded["queued_literal_ranges"])
        self.assertIn([0x08ACF2, 0x08AD08], excluded["canonical_owner_ranges"])
        self.assertIn([0x08AD30, 0x08AD4A], excluded["canonical_owner_ranges"])

    def test_export_roundtrip_and_independent_verifier(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            exporter.export_artifact(ROOT, output)
            report = verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertTrue(report["contract_ok"])
            self.assertEqual(2940, report["promotion_bytes"])
            for name in (exporter.PAYLOAD_NAME, exporter.MANIFEST_NAME):
                raw = (output / name).read_bytes()
                expected = (json.dumps(json.loads(raw), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
                self.assertEqual(expected, raw)

    def test_verifier_is_independent_and_raw_decodes_cfg(self) -> None:
        source = (ROOT / "tools/verify_rom_text_bg_task_closure.py").read_text()
        self.assertNotIn("export_rom_text_bg_task_closure", source)
        self.assertNotIn("build_payload", source)
        rebuilt = verifier._rebuild_closure((ROOT / exporter.ROM_PATH).read_bytes())
        self.assertEqual(1330, rebuilt["instruction_count"])
        self.assertEqual(2782, rebuilt["code_bytes"])
        self.assertEqual(260, rebuilt["literal_bytes"])

    def test_low_level_mutations_fail_closed(self) -> None:
        rom = bytearray((ROOT / exporter.ROM_PATH).read_bytes())
        cases = [
            (0x08ACC8, "closure"),
            (0x08AEB4, "literal"),
            (0x08AF0C, "callback pointer"),
            (0x08ADD0, "callback stack"),
            (0x062760, "callback field"),
            (0x06294C, "dispatch field"),
            (0x09C114, "dispatch wrapper"),
        ]
        for offset, message in cases:
            with self.subTest(offset=hex(offset)):
                mutated = bytearray(rom)
                mutated[offset] ^= 1
                with self.assertRaisesRegex(ValueError, message):
                    exporter._build_from_rom(ROOT, bytes(mutated), verify_rom_identity=False)

    def test_artifact_payload_tampering_fails(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            exporter.export_artifact(ROOT, output)
            payload_path = output / exporter.PAYLOAD_NAME
            manifest_path = output / exporter.MANIFEST_NAME
            payload = json.loads(payload_path.read_text())
            payload["promotion"]["promotion_bytes"] += 1
            raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
            payload_path.write_bytes(raw)
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][exporter.PAYLOAD_NAME] = {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            self.assertFalse(verifier.verify_artifact(ROOT, output)["verified"])

    def test_existing_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            exporter.export_artifact(ROOT, output)
            with self.assertRaises(FileExistsError):
                exporter.export_artifact(ROOT, output)

    def test_scope_is_narrow_and_failed_closed(self) -> None:
        scope = exporter.build_payload(ROOT)["scope"]
        self.assertTrue(scope["dependency_gated_local_thumb_closure"])
        self.assertTrue(scope["consumed_literal_words"])
        for key in (
            "whole_program_natural_runtime",
            "business_semantics",
            "adjacent_bytes",
            "padding_or_free_space",
            "editing_or_relocation_safety",
        ):
            self.assertFalse(scope[key])


if __name__ == "__main__":
    unittest.main()
