from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-value-range-text-inventory-v1"
EXPECTED_SUMMARY = {
    "pointer_table_count": 1,
    "pointer_slot_count": 38,
    "pointer_table_bytes": 152,
    "value_range_map_count": 1,
    "value_range_entry_count": 38,
    "value_range_map_bytes": 152,
    "renderer_record_count": 38,
    "renderer_consumed_bytes": 862,
    "classified_range_count": 39,
    "classified_bytes": 1_014,
    "inter_record_gap_bytes": 0,
    "range_overlap_bytes": 0,
    "parse_failure_count": 0,
    "packed_bytes": 1_014,
}


class ExportRomValueRangeTextInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_value_range_text_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name).resolve() / SCHEMA
        cls.payload = export_artifact(ROOT, cls.output)
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_the_fixed_value_range_text_denominator(self):
        self.assertEqual(EXPECTED_SUMMARY, self.payload["summary"])
        table = self.payload["pointer_table"]
        self.assertEqual([0x599F5C, 0x599FF4], table["range"])
        self.assertEqual(38, table["entry_count"])
        self.assertEqual(
            "70e722a0521ed49bf2ac43cbbee960295332d4b857115b595163da29f7731110",
            table["sha256"],
        )
        range_map = self.payload["value_range_map"]
        self.assertEqual([0x542204, 0x54229C], range_map["range"])
        self.assertEqual([0, 9], range_map["entries"][0]["inclusive_range"])
        self.assertEqual([0x172, 0x17B], range_map["entries"][-1]["inclusive_range"])
        self.assertEqual(38, len(self.payload["records"]))
        self.assertEqual([0x542E, 0x5445], self.payload["records"][0]["range"])
        self.assertEqual([0x5779, 0x578C], self.payload["records"][-1]["range"])
        self.assertEqual(
            "90be672576fa1ecba130596da7304d92283f5f77e7b89ee8a42ac41e46f42ef0",
            self.payload["record_range_denominator_sha256"],
        )
        self.assertEqual(
            "b8a6f9ab5543d67b301a0bc41d2fba960f5d2aaecd9dd9c52455d81670510873",
            self.payload["classified_range_denominator_sha256"],
        )
        self.assertFalse(self.payload["scope"]["runtime_input_bounds_proven"])
        self.assertFalse(self.payload["scope"]["natural_gameplay_all_ranges_proven"])

    def test_packs_only_the_range_map_and_renderer_consumed_records(self):
        bundle = (self.output / "value-range-text-bytes.bin").read_bytes()
        self.assertEqual(1_014, len(bundle))
        self.assertEqual(
            "88f201f21194087ff7643f1822d0b89c309feff497fbef6155ff5ae6ce6bc3d0",
            hashlib.sha256(bundle).hexdigest(),
        )
        ranges = self.payload["classified_ranges"]
        self.assertEqual(39, len(ranges))
        self.assertEqual(38, sum(item["kind"] == "renderer_text_record" for item in ranges))
        self.assertEqual(1, sum(item["kind"] == "value_range_map" for item in ranges))
        expected = b"".join(
            self.rom[start:end] for start, end in (item["range"] for item in ranges)
        )
        self.assertEqual(expected, bundle)
        self.assertFalse(any(item["range"] == [0x599F5C, 0x599FF4] for item in ranges))
        self.assertEqual(
            {
                "manifest.json",
                "value-range-text-inventory.json",
                "value-range-text-bytes.bin",
            },
            {path.name for path in self.output.iterdir() if path.is_file()},
        )

    def test_decodes_consumer_bridge_and_renderer_grammar(self):
        from tools.export_rom_value_range_text_inventory import (
            _decode_consumer_contract,
            _renderer_end,
        )
        from tools.verify_rom_value_range_text_inventory import (
            _independent_consumer_contract,
            _independent_renderer_end,
        )

        expected = self.payload["consumer_evidence"]["decoded_semantics"]
        self.assertEqual(expected, _decode_consumer_contract(self.rom))
        self.assertEqual(expected, _independent_consumer_contract(self.rom))
        self.assertEqual(38, expected["value_range_selector"]["entry_count"])
        self.assertEqual(
            "0x08066758", expected["value_range_selector"]["bridge_call_target"]
        )
        self.assertEqual(
            "0x0806626C", expected["renderer_bridge"]["parser_call_target"]
        )

        synthetic = bytes.fromhex("090a017f028140814000")
        sjis_ranges = ((0x8140, 0x8141),)
        for parser in (_renderer_end, _independent_renderer_end):
            self.assertEqual(
                len(synthetic), parser(synthetic, 0, len(synthetic), sjis_ranges)
            )
            for malformed in (b"\x01", b"\x02\x01", b"\x81", b"abc"):
                with self.assertRaisesRegex(ValueError, "bounded|truncated|terminator"):
                    parser(malformed, 0, len(malformed), sjis_ranges)

        tampered = bytearray(self.rom)
        tampered[0x8749E] ^= 1
        for decoder in (_decode_consumer_contract, _independent_consumer_contract):
            with self.assertRaisesRegex(ValueError, "consumer|selector"):
                decoder(bytes(tampered))

    def test_export_is_deterministic_and_refuses_unsafe_outputs(self):
        from tools.export_rom_value_range_text_inventory import export_artifact

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary).resolve()
            first = temporary_root / "first"
            second = temporary_root / "second"
            export_artifact(ROOT, first)
            export_artifact(ROOT, second)
            export_artifact(ROOT, first)
            first_hashes = {
                path.relative_to(first): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in first.rglob("*")
                if path.is_file()
            }
            second_hashes = {
                path.relative_to(second): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in second.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_hashes, second_hashes)

            foreign = temporary_root / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "foreign"):
                export_artifact(ROOT, foreign)

            real_parent = temporary_root / "real-parent"
            real_parent.mkdir()
            linked_parent = temporary_root / "linked-parent"
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                export_artifact(ROOT, linked_parent / "artifact")

        with self.assertRaisesRegex(ValueError, "repository root"):
            export_artifact(ROOT, ROOT)
        with self.assertRaisesRegex(ValueError, "ancestor"):
            export_artifact(ROOT, ROOT.parent)

    def test_independent_verifier_rebuilds_and_rejects_rehashed_tampering(self):
        from tools.verify_rom_value_range_text_inventory import verify_artifact

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(EXPECTED_SUMMARY, report["summary"])

        verifier_source = (
            ROOT / "tools/verify_rom_value_range_text_inventory.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools.export_rom_value_range", verifier_source)
        self.assertNotIn("import tools.export_rom_value_range", verifier_source)

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "tampered"
            shutil.copytree(self.output, tampered)
            bundle_path = tampered / "value-range-text-bytes.bin"
            bundle = bytearray(bundle_path.read_bytes())
            bundle[0] ^= 1
            bundle_path.write_bytes(bundle)
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][bundle_path.name] = hashlib.sha256(bundle).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verify_artifact(ROOT, tampered)["verified"])


if __name__ == "__main__":
    unittest.main()
