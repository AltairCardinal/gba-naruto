#!/usr/bin/env python3
"""TDD tests for the frozen sprite component source packet."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-sprite-component-source-v1"
PAYLOAD_NAME = "rom-sprite-component-source.json"
BUNDLE_NAME = "rom-sprite-component-source.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "064370aa0eca861d99d96e4ee15be4b50c569bea86c67a279d4084517e543baa"
SOURCE_SHA256 = "896a1b46f36cd8ad7f5e1c95a048b9aca099eb03ba55c21d4a43730979edcafb"
COMPONENT_VECTOR_SHA256 = "7f08e6f16284550c29aba25734067d8664a16723c50d374e2ace69fd6cccb87a"
KEYFRAME_VECTOR_SHA256 = "40294acde5c027c8645af9b93fa1ee82ac0c520136205358d72731c75cb9811a"
CONSUMER_PATH_SHA256 = "978caa4e5f2f2960dd49144c4dc408548e5087e39d1de6d458258cf5f27a61b5"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True)


class ExportRomSpriteComponentSourceTests(unittest.TestCase):
    def test_minimal_frozen_source_payload_api(self) -> None:
        from tools import export_rom_sprite_component_source as exporter

        payload, packed = exporter.build_payload(ROOT)
        self.assertEqual("rom-sprite-component-source-v1", payload["schema"])
        self.assertEqual([0x12C904, 0x12D134], payload["source"]["range"])
        self.assertEqual(2096, len(packed))

    def test_frozen_denominators_and_consumer_hashes(self) -> None:
        from tools import export_rom_sprite_component_source as exporter

        payload, packed = exporter.build_payload(ROOT)
        self.assertEqual(ROM_SHA256, payload["rom"]["sha256"])
        self.assertEqual(COVERAGE_SHA256, payload["coverage_baseline"]["sha256"])
        self.assertEqual(SOURCE_SHA256, payload["source"]["packed_sha256"])
        self.assertEqual(COMPONENT_VECTOR_SHA256, payload["components"]["component_vector_sha256"])
        self.assertEqual(KEYFRAME_VECTOR_SHA256, payload["timelines"]["keyframe_vector_sha256"])
        self.assertEqual(CONSUMER_PATH_SHA256, payload["consumer"]["consumer_path_sha256"])
        self.assertEqual(12, payload["components"]["list_count"])
        self.assertEqual(96, payload["components"]["record_count"])
        self.assertEqual(4, payload["timelines"]["timeline_count"])
        self.assertEqual(12, payload["timelines"]["keyframe_count"])
        self.assertEqual([0x0812C904 + i * 0xA4 for i in range(12)], payload["components"]["pointer_values"])
        self.assertEqual([0x0812D0E4 + i * 0x10 for i in range(4)], payload["animation_table"]["pointer_values"])
        self.assertEqual(SOURCE_SHA256, _sha(packed))

    def test_consumer_slices_are_provenance_only_and_stride_stays_unknown(self) -> None:
        from tools import export_rom_sprite_component_source as exporter

        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(0, payload["summary"]["consumer_code_promoted_bytes"])
        self.assertFalse(payload["scope"]["consumer_code_promoted"])
        self.assertTrue(payload["scope"]["stride_terminator_current_unknown_preserved"])
        self.assertEqual("current_unknown_provenance_only", payload["consumer"]["stride_terminator_promotion"])
        self.assertEqual([0x12C901, 0x12C904], payload["coverage_baseline"]["excluded_adjacent_range"]["range"])
        self.assertEqual("unknown", payload["coverage_baseline"]["unknown_provenance_owner"]["primary_class"])

    def test_exporter_and_verifier_rebuild_identically_without_preflight_input(self) -> None:
        from tools import export_rom_sprite_component_source as exporter
        from tools import verify_rom_sprite_component_source as verifier

        payload, packed = exporter.build_payload(ROOT)
        rebuilt, rebuilt_packed = verifier.rebuild_payload(ROOT)
        self.assertEqual(payload, rebuilt)
        self.assertEqual(packed, rebuilt_packed)
        for path in (ROOT / "tools/export_rom_sprite_component_source.py", ROOT / "tools/verify_rom_sprite_component_source.py"):
            self.assertNotIn("build/experiments/active/sprite-component-source-preflight", path.read_text(encoding="utf-8"))
        tree = ast.parse((ROOT / "tools/verify_rom_sprite_component_source.py").read_text(encoding="utf-8"))
        imports = "\n".join(ast.unparse(node) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
        self.assertNotIn("export_rom_sprite_component_source", imports)

    def test_raw_pointer_terminator_consumer_mutations_fail_closed(self) -> None:
        from tools import export_rom_sprite_component_source as exporter
        from tools import verify_rom_sprite_component_source as verifier

        rom = (ROOT / "rom/base.gba").read_bytes()
        for label, helper_name, offset, error in (
            ("definition pointer", "_parse_source", 0x12D0B4, "definition pointer"),
            ("component terminator", "_parse_source", 0x12D0B0, "component terminator"),
            ("animation pointer", "_parse_source", 0x12D124, "animation pointer"),
            ("timeline terminator", "_parse_source", 0x12D0F0, "timeline terminator"),
            ("literal opcode", "_decode_consumer", 0x06F2AA, "literal-load"),
            ("literal value", "_decode_consumer", 0x06F350, "table-pointer literal"),
            ("BL opcode", "_decode_consumer", 0x06F2C4, "parser call"),
            ("allocator slice", "_decode_consumer", 0x0626B4, "allocator code slice"),
            ("selector slice", "_decode_consumer", 0x06298C, "selector code slice"),
            ("renderer slice", "_decode_consumer", 0x063122, "renderer code slice"),
            ("stride slice", "_decode_consumer", 0x0631F6, "stride_terminator code slice"),
            ("timing slice", "_decode_consumer", 0x063256, "timing code slice"),
        ):
            changed = bytearray(rom)
            changed[offset] ^= 1
            for product in (exporter, verifier):
                with self.subTest(label=label, product=product.__name__):
                    helper = getattr(product, helper_name)
                    if helper_name == "_parse_source":
                        source_sha = _sha(bytes(changed[0x12C904:0x12D134]))
                        with mock.patch.dict(
                            product.C.REPORT_HASHES,
                            {"source_packed_sha256": source_sha},
                        ):
                            with self.assertRaisesRegex(ValueError, error):
                                helper(bytes(changed))
                    else:
                        with self.assertRaisesRegex(ValueError, error):
                            helper(bytes(changed))

    def test_coverage_mutation_and_current_unknown_owner_are_rejected(self) -> None:
        from tools import export_rom_sprite_component_source as exporter
        from tools import verify_rom_sprite_component_source as verifier

        baseline = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        cases = (
            ([0x12C904, 0x12D134], "primary_claim_ids", "source current-unknown owner"),
            ([0x0631F6, 0x063210], "secondary_claim_ids", "stride/terminator current-unknown owner"),
        )
        for target, field, error in cases:
            changed = copy.deepcopy(baseline)
            owner = next(
                segment
                for segment in changed["segments"]
                if segment["range"][0] <= target[0] and target[1] <= segment["range"][1]
            )
            owner[field] = ["synthetic-owner"]
            raw = _canonical(changed)
            for product in (exporter, verifier):
                with self.subTest(target=target, product=product.__name__):
                    with mock.patch.object(product.C, "COVERAGE_SHA256", _sha(raw)):
                        with self.assertRaisesRegex(ValueError, error):
                            product._validate_coverage(ROOT, raw)

    def test_artifact_is_atomic_deterministic_and_exact(self) -> None:
        from tools import export_rom_sprite_component_source as exporter
        from tools import verify_rom_sprite_component_source as verifier

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            first, second = base / "first", base / "second"
            exporter.export_artifact(ROOT, first)
            exporter.export_artifact(ROOT, second)
            self.assertEqual(EXPECTED_FILES, {path.name for path in first.iterdir()})
            self.assertEqual(
                {path.name: _sha(path.read_bytes()) for path in first.iterdir()},
                {path.name: _sha(path.read_bytes()) for path in second.iterdir()},
            )
            report = verifier.verify_artifact(ROOT, first)
            self.assertTrue(report["verified"], report["errors"])
            self.assertEqual(2096, report["promoted_from_unknown_bytes"])

    def test_artifact_extra_missing_symlink_and_tamper_fail_closed(self) -> None:
        from tools import export_rom_sprite_component_source as exporter
        from tools import verify_rom_sprite_component_source as verifier

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            original = base / "original"
            exporter.export_artifact(ROOT, original)
            extra = base / "extra"
            shutil.copytree(original, extra)
            (extra / "extra.bin").write_bytes(b"x")
            self.assertFalse(verifier.verify_artifact(ROOT, extra)["verified"])
            missing = base / "missing"
            shutil.copytree(original, missing)
            (missing / BUNDLE_NAME).unlink()
            self.assertFalse(verifier.verify_artifact(ROOT, missing)["verified"])
            linked = base / "linked"
            shutil.copytree(original, linked)
            outside = base / "outside.bin"
            outside.write_bytes((linked / BUNDLE_NAME).read_bytes())
            (linked / BUNDLE_NAME).unlink()
            (linked / BUNDLE_NAME).symlink_to(outside)
            self.assertFalse(verifier.verify_artifact(ROOT, linked)["verified"])
            tampered = base / "tampered"
            shutil.copytree(original, tampered)
            payload_path = tampered / PAYLOAD_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["summary"]["promoted_from_unknown_bytes"] += 1
            payload_path.write_bytes(_canonical(payload))
            self.assertFalse(verifier.verify_artifact(ROOT, tampered)["verified"])

    def test_isolated_cli_works_with_python_i_s(self) -> None:
        exporter = ROOT / "tools/export_rom_sprite_component_source.py"
        verifier = ROOT / "tools/verify_rom_sprite_component_source.py"
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary).resolve() / SCHEMA
            exported = _run([sys.executable, "-I", "-S", str(exporter), "--root", str(ROOT), "--output-dir", str(artifact)])
            self.assertEqual(0, exported.returncode, exported.stdout + exported.stderr)
            verified = _run([sys.executable, "-I", "-S", str(verifier), "--root", str(ROOT), "--artifact-dir", str(artifact)])
            self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)

    def test_runtime_dependency_hashes_are_bound(self) -> None:
        from tools import export_rom_sprite_component_source as exporter

        payload, _ = exporter.build_payload(ROOT)
        dependencies = payload["implementation"]["runtime_dependency_sha256"]
        self.assertEqual(
            {
                "tools/rom_sprite_component_source_contract.py",
                "tools/export_rom_sprite_component_source.py",
                "tools/verify_rom_sprite_component_source.py",
                "tests/test_export_rom_sprite_component_source.py",
                "tests/test_verify_rom_sprite_component_source.py",
            },
            set(dependencies),
        )


if __name__ == "__main__":
    unittest.main()
