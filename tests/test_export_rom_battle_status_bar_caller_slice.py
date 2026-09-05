"""TDD contract tests for the frozen battle status-bar caller slice."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-battle-status-bar-caller-slice-v1"
PAYLOAD_NAME = "rom-battle-status-bar-caller-slice.json"
RANGE = (0x07A34C, 0x07AA8C)
EXPECTED_SIZE = 1856
EXPECTED_SHA256 = "f400ef9501381b6e005e7d9c51add8ac5fe3dc4217a3fa6397e1ccdf3dc64c51"
EXPECTED_PACKED_SHA256 = EXPECTED_SHA256
EXPECTED_COVERAGE_SHA256 = "24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987"
EXPECTED_BL_TARGET = "0x08068370"
EXPECTED_BL_MATCHES = [
    {"gba_address": "0x0806F0D6", "file_offset": 0x06F0D6, "raw_hex": "f9f74bf9"},
    {"gba_address": "0x0806F0EC", "file_offset": 0x06F0EC, "raw_hex": "f9f740f9"},
    {"gba_address": "0x0807A83C", "file_offset": 0x07A83C, "raw_hex": "edf798fd"},
    {"gba_address": "0x0807A8A6", "file_offset": 0x07A8A6, "raw_hex": "edf763fd"},
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True)


class ExportRomBattleStatusBarCallerSliceTests(unittest.TestCase):
    def test_isolated_cli_export_and_verify(self) -> None:
        exporter = ROOT / "tools/export_rom_battle_status_bar_caller_slice.py"
        verifier = ROOT / "tools/verify_rom_battle_status_bar_caller_slice.py"
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
        from tools import export_rom_battle_status_bar_caller_slice as exporter
        from tools import verify_rom_battle_status_bar_caller_slice as verifier

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
                "bytes": EXPECTED_SIZE,
                "current_unknown_bytes": EXPECTED_SIZE,
                "packed_bytes": EXPECTED_SIZE,
                "primary_overlap_bytes": 0,
                "range_count": 1,
                "secondary_overlap_bytes": 0,
            },
        )
        self.assertEqual(payload["range"]["bytes_sha256"], EXPECTED_SHA256)
        self.assertEqual(payload["packed_bytes_sha256"], EXPECTED_PACKED_SHA256)
        self.assertEqual(_sha(packed), EXPECTED_PACKED_SHA256)

    def test_range_rebuild_is_raw_and_not_a_label_alias(self) -> None:
        from tools import export_rom_battle_status_bar_caller_slice as exporter

        payload, packed = exporter.build_payload(ROOT)
        raw = (ROOT / "rom/base.gba").read_bytes()[RANGE[0] : RANGE[1]]
        self.assertEqual(payload["range"]["bytes_hex"], raw.hex())
        self.assertEqual(payload["packed_bytes"], packed.hex())
        self.assertEqual(payload["range"]["packed_range"], [0, EXPECTED_SIZE])

    def test_source_coverage_and_full_rom_bl_denominator_are_frozen(self) -> None:
        from tools import export_rom_battle_status_bar_caller_slice as exporter

        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(
            payload["coverage"],
            {"path": "sequel/rom-byte-coverage.json", "sha256": EXPECTED_COVERAGE_SHA256},
        )
        source = payload["source"]
        self.assertEqual(source["manifest"]["sha256"], "d88242fa88213b96d8fe48430a0758a3bb79adf7dd6bb6d22e7d00da9711c0d0")
        self.assertEqual(source["payload"]["sha256"], "c8ff2c231c5a0ac111f10c7ca545d285cde0e23c4fca706815ee40277086d4eb")
        self.assertEqual(source["exporter"]["sha256"], "1118ff63553ee1e31606a96b0d6564609beada3a42a37e8118a4e16103b55102")
        self.assertEqual(source["verifier"]["sha256"], "53202cb452c25c762ff6fbface0705c31bb01392177d66f168628919c8b77d32")
        self.assertEqual(source["test"]["sha256"], "4a84c9eb211874b0d216bf061f18f213b2bfa3893e10307d76c3e9bc6fb7007e")
        self.assertEqual(source["verifier_report"]["sha256"], "5e767d4d73caa72fa61ec11cd186f5f5aa4976424c33debd2e23bad689addfcd")
        self.assertEqual(source["generator_gba_address"], EXPECTED_BL_TARGET)
        self.assertEqual(source["target_caller"], {"file_range": list(RANGE), "gba_range": ["0x0807A34C", "0x0807AA8C"], "sha256": EXPECTED_SHA256})
        self.assertEqual(source["bl_denominator"]["target_gba_address"], EXPECTED_BL_TARGET)
        self.assertEqual(source["bl_denominator"]["alignment"], 2)
        self.assertEqual(source["bl_denominator"]["match_count"], 4)
        self.assertEqual(source["bl_denominator"]["matches"], EXPECTED_BL_MATCHES)

    def test_artifact_is_deterministic_and_has_only_manifest_and_payload(self) -> None:
        from tools import export_rom_battle_status_bar_caller_slice as exporter
        from tools import verify_rom_battle_status_bar_caller_slice as verifier

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

    def test_raw_rom_and_bl_source_mutations_fail_closed(self) -> None:
        from tools import verify_rom_battle_status_bar_caller_slice as verifier

        for offset in (RANGE[0], 0x06F0D6):
            with self.subTest(offset=hex(offset)):
                rom = bytearray((ROOT / "rom/base.gba").read_bytes())
                rom[offset] ^= 1
                with self.assertRaises(ValueError):
                    verifier.rebuild_payload(ROOT, bytes(rom))

    def test_payload_range_and_manifest_mutations_fail_closed(self) -> None:
        from tools import export_rom_battle_status_bar_caller_slice as exporter
        from tools import verify_rom_battle_status_bar_caller_slice as verifier

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary).resolve() / SCHEMA
            exporter.export_artifact(ROOT, artifact)
            payload_path = artifact / PAYLOAD_NAME
            payload = json.loads(payload_path.read_text())
            payload["source"]["bl_denominator"]["matches"][0]["raw_hex"] = "00" * 4
            payload_path.write_bytes(_canonical(payload))
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][PAYLOAD_NAME] = _sha(payload_path.read_bytes())
            manifest_path.write_bytes(_canonical(manifest))
            report = verifier.verify_artifact(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def test_coverage_and_target_range_mutations_fail_closed(self) -> None:
        from tools import verify_rom_battle_status_bar_caller_slice as verifier

        payload, packed = verifier.rebuild_payload(ROOT)
        mutated_payload = json.loads(json.dumps(payload))
        mutated_payload["range"]["range"][0] += 2
        with self.assertRaises(ValueError):
            verifier.verify_rebuilt_payload(ROOT, mutated_payload, packed)

        coverage = bytearray((ROOT / "sequel/rom-byte-coverage.json").read_bytes())
        coverage[100] ^= 1
        with self.assertRaises(ValueError):
            verifier.rebuild_payload(ROOT, coverage=bytes(coverage))

    def test_independent_verifier_contains_no_exporter_import_or_call(self) -> None:
        source = (ROOT / "tools/verify_rom_battle_status_bar_caller_slice.py").read_text()
        self.assertNotIn("from tools import export_rom_battle_status_bar_caller_slice", source)
        self.assertNotIn("import tools.export_rom_battle_status_bar_caller_slice", source)
        self.assertNotIn("export_rom_battle_status_bar_caller_slice.build_payload", source)


if __name__ == "__main__":
    unittest.main()
