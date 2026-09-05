"""TDD contract tests for the frozen sprite-loader terminal-tail packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-sprite-loader-tail-v1"
PAYLOAD_NAME = "rom-sprite-loader-tail.json"
RANGE = (0x080B58, 0x080B7C)
EXPECTED_SIZE = 36
EXPECTED_SHA256 = "a318a3e999a3a89c53f42fd3fec03c7608ab325d01061136e2915fe9e4e6af5c"
EXPECTED_PACKED_SHA256 = EXPECTED_SHA256
EXPECTED_COVERAGE_SHA256 = "24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True)


class ExportRomSpriteLoaderTailTests(unittest.TestCase):
    def test_isolated_cli_export_and_verify(self) -> None:
        exporter = ROOT / "tools/export_rom_sprite_loader_tail.py"
        verifier = ROOT / "tools/verify_rom_sprite_loader_tail.py"
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
        from tools import export_rom_sprite_loader_tail as exporter
        from tools import verify_rom_sprite_loader_tail as verifier

        payload, packed = exporter.build_payload(ROOT)
        rebuilt, rebuilt_packed = verifier.rebuild_payload(ROOT)
        self.assertEqual(payload, rebuilt)
        self.assertEqual(packed, rebuilt_packed)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["range"]["range"], list(RANGE))
        self.assertEqual(payload["range"]["size"], EXPECTED_SIZE)
        self.assertEqual(
            payload["summary"],
            {
                "bytes": 36,
                "current_unknown_bytes": 36,
                "packed_bytes": 36,
                "primary_overlap_bytes": 0,
                "range_count": 1,
                "secondary_overlap_bytes": 0,
            },
        )
        self.assertEqual(payload["range"]["bytes_sha256"], EXPECTED_SHA256)
        self.assertEqual(payload["packed_bytes_sha256"], EXPECTED_PACKED_SHA256)
        self.assertEqual(_sha(packed), EXPECTED_PACKED_SHA256)

    def test_range_rebuild_is_raw_and_not_a_label_alias(self) -> None:
        from tools import export_rom_sprite_loader_tail as exporter

        payload, packed = exporter.build_payload(ROOT)
        raw = (ROOT / "rom/base.gba").read_bytes()[RANGE[0] : RANGE[1]]
        self.assertEqual(payload["range"]["bytes_hex"], raw.hex())
        self.assertEqual(payload["packed_bytes"], packed.hex())
        self.assertEqual(payload["range"]["packed_range"], [0, EXPECTED_SIZE])
        self.assertEqual(payload["range"]["packed_sha256"], EXPECTED_PACKED_SHA256)

    def test_source_loader_denominator_and_coverage_identities_are_frozen(self) -> None:
        from tools import export_rom_sprite_loader_tail as exporter

        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(
            payload["coverage"],
            {"path": "sequel/rom-byte-coverage.json", "sha256": EXPECTED_COVERAGE_SHA256},
        )
        source = payload["source"]
        self.assertEqual(source["manifest"]["sha256"], "e432003728c8ea28b95723eeb4f68f9a8cf95b74185eb39fdd6075c71c16b583")
        self.assertEqual(source["exporter"]["sha256"], "23677a3ea2b4d6753218358c6e53eee2745b46e3c691480a1385d5a2f036846a")
        self.assertEqual(source["verifier"]["sha256"], "bffa6e52426b1ad716f81a77770826ce33dc3deb6496a912040457f048aae90e")
        self.assertEqual(source["test"]["sha256"], "06a999de6556a4d49bd1afd7d181785290d306c3b1e4dd9b9b08d0be608b2f0e")
        self.assertEqual(source["verifier_report"]["sha256"], "ca8e829cb3ba3d927d8b427af5bd4a5be0d758daca979ac2ce6958e4d3066a27")
        self.assertEqual(source["entry_count"], 43)
        self.assertEqual(
            source["consumer_evidence"],
            {
                "json_pointer": "/code_slices/0",
                "name": "generic_sprite_loader",
                "file_range": [0x080B08, 0x080B7C],
                "gba_range": ["0x08080B08", "0x08080B7C"],
                "sha256": "ff28fa10e4606f706a4fd4986126d8a14fe2baf66f1cc2621c5fe6b15d2ff8c2",
                "entry_count": 43,
            },
        )

    def test_artifact_is_deterministic_and_has_only_manifest_and_payload(self) -> None:
        from tools import export_rom_sprite_loader_tail as exporter
        from tools import verify_rom_sprite_loader_tail as verifier

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            first, second = base / "first", base / "second"
            exporter.export_artifact(ROOT, first)
            exporter.export_artifact(ROOT, second)
            self.assertEqual(
                {p.name: _sha(p.read_bytes()) for p in first.iterdir()},
                {p.name: _sha(p.read_bytes()) for p in second.iterdir()},
            )
            self.assertEqual({"manifest.json", PAYLOAD_NAME}, {p.name for p in first.iterdir()})
            report = verifier.verify_artifact(ROOT, first)
            self.assertTrue(report["verified"], report["errors"])

    def test_single_byte_raw_rom_mutation_fails_closed(self) -> None:
        from tools import verify_rom_sprite_loader_tail as verifier

        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[RANGE[0]] ^= 1
        with self.assertRaises(ValueError):
            verifier.rebuild_payload(ROOT, bytes(rom))

    def test_payload_range_and_manifest_mutations_fail_closed(self) -> None:
        from tools import export_rom_sprite_loader_tail as exporter
        from tools import verify_rom_sprite_loader_tail as verifier

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
        from tools import verify_rom_sprite_loader_tail as verifier

        coverage = bytearray((ROOT / "sequel/rom-byte-coverage.json").read_bytes())
        coverage[-1] ^= 1
        with self.assertRaises(ValueError):
            verifier.rebuild_payload(ROOT, coverage=bytes(coverage))

    def test_independent_verifier_contains_no_exporter_import(self) -> None:
        source = (ROOT / "tools/verify_rom_sprite_loader_tail.py").read_text()
        self.assertNotIn("from tools import export_rom_sprite_loader_tail", source)
        self.assertNotIn("import tools.export_rom_sprite_loader_tail", source)


if __name__ == "__main__":
    unittest.main()
