"""TDD contract tests for the chapter-selector code-slice packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-chapter-selector-code-slice-v1"
PAYLOAD_NAME = "rom-chapter-selector-code-slice.json"
RANGE = (0x08F594, 0x08F5D4)
EXPECTED_SIZE = 64
EXPECTED_SHA256 = "0c586c11a8c452e4096d4cf444bb5c75628d099020ff8e5642f99634ea022efd"
EXPECTED_PACKED_SHA256 = EXPECTED_SHA256
EXPECTED_COVERAGE_SHA256 = "24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True)


class ExportRomChapterSelectorCodeSliceTests(unittest.TestCase):
    def test_isolated_cli_export_and_verify(self) -> None:
        exporter = ROOT / "tools/export_rom_chapter_selector_code_slice.py"
        verifier = ROOT / "tools/verify_rom_chapter_selector_code_slice.py"
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary).resolve() / SCHEMA
            exported = _run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    str(exporter),
                    "--root",
                    str(ROOT),
                    "--output-dir",
                    str(artifact),
                ]
            )
            self.assertEqual(exported.returncode, 0, exported.stdout + exported.stderr)
            verified = _run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    str(verifier),
                    "--root",
                    str(ROOT),
                    "--artifact-dir",
                    str(artifact),
                ]
            )
            self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
            self.assertTrue(json.loads(verified.stdout)["verified"])

    def test_export_and_independent_rebuild_close_the_exact_range(self) -> None:
        from tools import export_rom_chapter_selector_code_slice as exporter
        from tools import verify_rom_chapter_selector_code_slice as verifier

        payload, packed = exporter.build_payload(ROOT)
        rebuilt, rebuilt_packed = verifier.rebuild_payload(ROOT)
        self.assertEqual(payload, rebuilt)
        self.assertEqual(packed, rebuilt_packed)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["range"]["range"], list(RANGE))
        self.assertEqual(payload["range"]["size"], EXPECTED_SIZE)
        self.assertEqual(payload["summary"], {"bytes": 64, "current_unknown_bytes": 64, "packed_bytes": 64, "primary_overlap_bytes": 0, "range_count": 1, "secondary_overlap_bytes": 0})
        self.assertEqual(payload["range"]["bytes_sha256"], EXPECTED_SHA256)
        self.assertEqual(payload["packed_bytes_sha256"], EXPECTED_PACKED_SHA256)
        self.assertEqual(_sha(packed), EXPECTED_PACKED_SHA256)

    def test_range_rebuild_is_raw_and_not_a_label_alias(self) -> None:
        from tools import export_rom_chapter_selector_code_slice as exporter

        payload, packed = exporter.build_payload(ROOT)
        raw = (ROOT / "rom/base.gba").read_bytes()[RANGE[0] : RANGE[1]]
        self.assertEqual(payload["range"]["bytes_hex"], raw.hex())
        self.assertEqual(payload["packed_bytes"], packed.hex())
        self.assertEqual(payload["range"]["packed_range"], [0, 64])
        self.assertEqual(payload["range"]["packed_sha256"], EXPECTED_PACKED_SHA256)

    def test_source_and_coverage_identities_are_frozen(self) -> None:
        from tools import export_rom_chapter_selector_code_slice as exporter

        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(payload["coverage"], {"path": "sequel/rom-byte-coverage.json", "sha256": EXPECTED_COVERAGE_SHA256})
        source = payload["source"]
        self.assertEqual(source["manifest"]["sha256"], "ad77f775f927b89e4a499ddff82e077c38b2767cd86348b65053cb8ca4136f0e")
        self.assertEqual(source["payload"]["sha256"], "813cd10394e5fac239aefd6043437796b1a63f95d8d068d714871b8dd3edcabc")
        self.assertEqual(source["exporter"]["sha256"], "707a00b57c6dbbfb3da22f5ef385a0243c600ef1b30f8b70527446c290ddba42")
        self.assertEqual(source["verifier"]["sha256"], "b9bf0203bddd8ca85981bd7957d95171c11187a117447bc5a0e92e384777911c")
        self.assertEqual(source["test"]["sha256"], "95f7d1eb1aa22efc6f6cb4e183af3564ef644831b6468dde0d00e0cad368e941")
        self.assertEqual(source["consumer_evidence"], {"json_pointer": "/consumer_evidence/table_selector", "range": list(RANGE), "sha256": EXPECTED_SHA256})

    def test_artifact_is_deterministic_and_has_only_manifest_and_payload(self) -> None:
        from tools import export_rom_chapter_selector_code_slice as exporter
        from tools import verify_rom_chapter_selector_code_slice as verifier

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            first, second = base / "first", base / "second"
            exporter.export_artifact(ROOT, first)
            exporter.export_artifact(ROOT, second)
            self.assertEqual({p.name: _sha(p.read_bytes()) for p in first.iterdir()}, {p.name: _sha(p.read_bytes()) for p in second.iterdir()})
            self.assertEqual({"manifest.json", PAYLOAD_NAME}, {p.name for p in first.iterdir()})
            report = verifier.verify_artifact(ROOT, first)
            self.assertTrue(report["verified"], report["errors"])

    def test_single_byte_raw_rom_mutation_fails_closed(self) -> None:
        from tools import verify_rom_chapter_selector_code_slice as verifier

        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[RANGE[0]] ^= 1
        with self.assertRaises(ValueError):
            verifier.rebuild_payload(ROOT, bytes(rom))

    def test_payload_range_and_manifest_mutations_fail_closed(self) -> None:
        from tools import export_rom_chapter_selector_code_slice as exporter
        from tools import verify_rom_chapter_selector_code_slice as verifier

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary).resolve() / SCHEMA
            exporter.export_artifact(ROOT, artifact)
            payload_path = artifact / PAYLOAD_NAME
            payload = json.loads(payload_path.read_text())
            payload["range"]["range"][1] -= 1
            payload_path.write_bytes(_canonical(payload))
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][PAYLOAD_NAME] = _sha(payload_path.read_bytes())
            manifest_path.write_bytes(_canonical(manifest))
            report = verifier.verify_artifact(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def test_coverage_single_byte_mutation_fails_closed(self) -> None:
        from tools import verify_rom_chapter_selector_code_slice as verifier

        coverage = bytearray((ROOT / "sequel/rom-byte-coverage.json").read_bytes())
        coverage[-1] ^= 1
        with self.assertRaises(ValueError):
            verifier.rebuild_payload(ROOT, coverage=bytes(coverage))

    def test_independent_verifier_contains_no_exporter_import(self) -> None:
        source = (ROOT / "tools/verify_rom_chapter_selector_code_slice.py").read_text()
        self.assertNotIn("from tools import export_rom_chapter_selector_code_slice", source)
        self.assertNotIn("import tools.export_rom_chapter_selector_code_slice", source)


if __name__ == "__main__":
    unittest.main()
