"""TDD contract for the fixed renderer-script record packet.

The first RED phase intentionally imports the not-yet-created exporter and
independent verifier.  The complete contract is filled in as the packet is
implemented.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-fixed-renderer-script-records-v1"


class FixedRendererScriptRecordsRedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # RED: both modules are intentionally absent before implementation.
        from tools import export_rom_fixed_renderer_script_records as exporter
        from tools import verify_rom_fixed_renderer_script_records as verifier

        cls.exporter = exporter
        cls.verifier = verifier

    def test_modules_expose_packet_entry_points(self) -> None:
        self.assertTrue(callable(self.exporter.build_payload))
        self.assertTrue(callable(self.exporter.export_artifact))
        self.assertTrue(callable(self.verifier.verify_artifact))

    def test_exact_consumer_and_record_denominators(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual(SCHEMA, payload["schema"])
        consumers = payload["consumer_denominator"]
        self.assertEqual(41, consumers["site_count"])
        self.assertEqual(36, consumers["accepted_site_count"])
        self.assertEqual(5, consumers["excluded_site_count"])
        self.assertEqual(
            [0x0BC9, 0x0C2E, 0x0C34, 0x14B4, 0x15FC],
            consumers["excluded_targets"],
        )
        self.assertEqual(6, len(payload["upstream_cfg_contract"]["files"]))
        self.assertTrue(payload["upstream_cfg_contract"]["verified"])
        records = payload["records"]
        self.assertEqual(30, records["record_count"])
        self.assertEqual(1124, records["record_bytes"])
        self.assertEqual(
            "6fa95454d60ccbfa2680dc286114190f52a9226b72c82e368cbae02bc7ad8df3",
            records["record_vector_sha256"],
        )
        self.assertEqual(
            "badb4ac6c49ea2250909065b2deb5d19cbd8d9768c761447fef6ab92916a60b9",
            records["packed_bytes_sha256"],
        )

    def test_exact_merged_ranges_and_narrow_scope(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual(
            [[0x0A65, 0x0ABB], [0x0B9A, 0x0BC9], [0x0BF5, 0x0C2E],
             [0x0C6C, 0x0CEA], [0x12F0, 0x14B4], [0x15B0, 0x15C4],
             [0x1631, 0x1781]],
            payload["records"]["merged_ranges"],
        )
        self.assertEqual(
            "a781ac704199e1412224376289d705c1ed4e2766065bcb3334d1495d3297b9ce",
            payload["records"]["merged_range_vector_sha256"],
        )
        self.assertEqual(30, len(payload["promotion"]["claims"]))
        self.assertEqual(1124, payload["promotion"]["promotion_bytes"])
        for key in ("whole_rom_consumer_denominator", "startup_semantics",
                    "opcode_7_or_8_semantics", "natural_runtime_reachability",
                    "unicode_complete", "padding_or_free_space",
                    "editing_or_relocation_safety"):
            self.assertFalse(payload["scope"][key])

    def test_export_roundtrip_and_independent_verifier(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            report = self.verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual(1124, report["promotion_bytes"])
            self.assertEqual(30, report["record_count"])

    def test_verifier_does_not_import_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_fixed_renderer_script_records.py").read_text()
        self.assertNotIn("export_rom_fixed_renderer_script_records", source)
        self.assertNotIn("build_payload", source)
        rebuilt = self.verifier._rebuild((ROOT / self.exporter.ROM_PATH).read_bytes())
        self.assertEqual(41, rebuilt["consumer_denominator"]["site_count"])
        self.assertEqual(30, rebuilt["records"]["record_count"])

    def test_mutations_fail_closed(self) -> None:
        rom = bytearray((ROOT / self.exporter.ROM_PATH).read_bytes())
        for offset, reason in ((0x06C7A2, "literal site|denominator"), (0x06C7A4, "interpreter path|parameter flow"),
                               (0x0671D4, "interpreter semantics"), (0x0A65, "record"),
                               (0x0A92, "record")):
            with self.subTest(offset=hex(offset)):
                mutated = bytearray(rom); mutated[offset] ^= 1
                with self.assertRaisesRegex(ValueError, reason):
                    self.exporter._build_from_rom(ROOT, bytes(mutated), verify_identity=False)

    def test_parameter_register_rewrite_fails_closed(self) -> None:
        rom = bytearray((ROOT / self.exporter.ROM_PATH).read_bytes())
        # Change the 0x8179C literal destination from r6 to r5 while preserving
        # its literal word.  The later `adds r0, r6, #0` must no longer prove
        # that this record pointer reaches the interpreter's r0 argument.
        halfword = int.from_bytes(rom[0x8179C:0x8179E], "little")
        halfword = (halfword & ~0x0700) | 0x0500
        rom[0x8179C:0x8179E] = halfword.to_bytes(2, "little")
        with self.assertRaisesRegex(ValueError, "does not reach interpreter r0"):
            self.exporter._build_from_rom(ROOT, bytes(rom), verify_identity=False)

    def test_artifact_tamper_and_existing_target_fail(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            with self.assertRaises(FileExistsError):
                self.exporter.export_artifact(ROOT, output)
            payload_path = output / self.exporter.PAYLOAD_NAME
            manifest_path = output / self.exporter.MANIFEST_NAME
            payload = json.loads(payload_path.read_text())
            payload["promotion"]["promotion_bytes"] += 1
            raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
            payload_path.write_bytes(raw)
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][self.exporter.PAYLOAD_NAME] = {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            self.assertFalse(self.verifier.verify_artifact(ROOT, output)["verified"])


if __name__ == "__main__":
    unittest.main()
