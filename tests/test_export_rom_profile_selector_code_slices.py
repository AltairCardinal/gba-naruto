"""TDD contract tests for the profile-selector code-slice packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import export_rom_profile_selector_code_slices as exporter
from tools import verify_rom_profile_selector_code_slices as verifier


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-profile-selector-code-slices-v1"
PAYLOAD_NAME = "rom-profile-selector-code-slices.json"
MANIFEST_NAME = "manifest.json"
ROM_BASE = 0x08000000
RANGES = [(0x08B19E, 0x08B1B6), (0x08D1A4, 0x08D230)]
ROLES = ["profile_table_selector", "renderer_line_wrapper"]
EXPECTED_BYTES = 164
EXPECTED_PACKED_SHA256 = "2d0175a6ea9e98f379c4f6e92f2baa0b1272592648c944f12827a51b154615ca"
EXPECTED_RANGE_SHA256 = [
    "a85145a1f4f5342a07dda4175aa93de57ea55d5b1bb514c55ea65a1a47acf625",
    "7646f12d2cdcbeb8b86bb39d491906bb112ac92afd0730ae5b56ac96a7f5c552",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


class ExportRomProfileSelectorCodeSlicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_export_and_independent_rebuild_close_the_two_ranges(self) -> None:
        payload, packed = exporter.build_payload(ROOT)
        rebuilt, rebuilt_packed = verifier.rebuild_payload(ROOT)
        self.assertEqual(payload, rebuilt)
        self.assertEqual(packed, rebuilt_packed)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual([tuple(row["range"]) for row in payload["ranges"]], RANGES)
        self.assertEqual([row["role"] for row in payload["ranges"]], ROLES)
        self.assertEqual(payload["summary"]["range_count"], 2)
        self.assertEqual(payload["summary"]["bytes"], EXPECTED_BYTES)
        self.assertEqual(payload["summary"]["current_unknown_bytes"], EXPECTED_BYTES)
        self.assertEqual(payload["summary"]["primary_overlap_bytes"], 0)
        self.assertEqual(payload["packed_bytes_sha256"], EXPECTED_PACKED_SHA256)
        self.assertEqual(_sha(packed), EXPECTED_PACKED_SHA256)
        self.assertEqual(
            [row["bytes_sha256"] for row in payload["ranges"]], EXPECTED_RANGE_SHA256
        )

    def test_ranges_are_exact_raw_rom_slices_and_packed_in_order(self) -> None:
        payload, packed = exporter.build_payload(ROOT)
        cursor = 0
        for row, (start, end) in zip(payload["ranges"], RANGES):
            raw = self.rom[start:end]
            self.assertEqual(row["range"], [start, end])
            self.assertEqual(row["gba_range"], [f"0x{ROM_BASE + start:08X}", f"0x{ROM_BASE + end:08X}"])
            self.assertEqual(row["size"], end - start)
            self.assertEqual(row["bytes_hex"], raw.hex())
            self.assertEqual(row["bytes_sha256"], _sha(raw))
            self.assertEqual(row["packed_range"], [cursor, cursor + len(raw)])
            self.assertEqual(row["packed_sha256"], _sha(packed[cursor : cursor + len(raw)]))
            cursor += len(raw)
        self.assertEqual(cursor, EXPECTED_BYTES)
        self.assertEqual(payload["packed_bytes"], packed.hex())
        self.assertEqual(len(bytes.fromhex(payload["packed_bytes"])), EXPECTED_BYTES)

    def test_artifact_is_deterministic_and_independently_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary).resolve()
            first = temporary_root / "first"
            second = temporary_root / "second"
            exporter.export_artifact(ROOT, first)
            exporter.export_artifact(ROOT, second)
            self.assertEqual(
                {p.name: _sha(p.read_bytes()) for p in first.iterdir()},
                {p.name: _sha(p.read_bytes()) for p in second.iterdir()},
            )
            self.assertEqual({MANIFEST_NAME, PAYLOAD_NAME}, {p.name for p in first.iterdir()})
            report = verifier.verify_artifact(ROOT, first)
            self.assertTrue(report["verified"], report["errors"])

    def test_source_and_coverage_identities_are_frozen(self) -> None:
        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(
            payload["coverage"],
            {
                "path": "sequel/rom-byte-coverage.json",
                "sha256": "24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987",
            },
        )
        source = payload["source"]
        self.assertEqual(source["manifest"]["sha256"], "57979c4355a182f219702d48055ff21b3b81d132ffb5240c64e152ecb54503f8")
        self.assertEqual(source["payload"]["sha256"], "592c34ae72ec4ad2ebaa4847fdbc700d0ecf2e995ef1c3cec6b13aedc09646e9")
        self.assertEqual(source["exporter"]["sha256"], "bb6c5c259ab8caa822c266e7674a4642b2850e0b45764d299b66bf2d23f2e223")
        self.assertEqual(source["verifier"]["sha256"], "87830893bf507866e6966c8f9bda558bee094be890d442f3375970f2d3084009")
        self.assertEqual(source["test"]["sha256"], "e95918f1ee0e085c513e0e4fe34056ff4fc1a7f758c6cd1c7302dac5fe30ce6e")

    def test_source_verifier_is_not_exporter_and_mutations_fail_closed(self) -> None:
        source = (ROOT / "tools/verify_rom_profile_selector_code_slices.py").read_text()
        self.assertNotIn("from tools import export_rom_profile_selector_code_slices", source)
        self.assertNotIn("import tools.export_rom_profile_selector_code_slices", source)
        mutated = bytearray(self.rom)
        mutated[RANGES[0][0]] ^= 1
        with self.assertRaises(ValueError):
            verifier.rebuild_payload(ROOT, bytes(mutated))

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary).resolve() / SCHEMA
            exporter.export_artifact(ROOT, artifact)
            payload_path = artifact / PAYLOAD_NAME
            payload = json.loads(payload_path.read_text())
            payload["ranges"][0]["bytes_hex"] = "00" * (RANGES[0][1] - RANGES[0][0])
            payload_path.write_bytes(_canonical(payload))
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

    def test_repository_artifact_is_verified(self) -> None:
        report = verifier.verify_artifact(ROOT, ROOT / "artifacts" / SCHEMA)
        self.assertTrue(report["verified"], report["errors"])


if __name__ == "__main__":
    unittest.main()
