from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-battle-message-text-inventory-v1"
EXPECTED_SUMMARY = {
    "pointer_table_count": 1,
    "pointer_slot_count": 79,
    "pointer_table_bytes": 316,
    "renderer_record_count": 79,
    "renderer_consumed_bytes": 1_411,
    "zero_padding_range_count": 79,
    "zero_padding_bytes": 1_329,
    "classified_range_count": 158,
    "classified_bytes": 2_740,
    "range_overlap_bytes": 0,
    "parse_failure_count": 0,
    "packed_bytes": 2_740,
}


class ExportRomBattleMessageTextInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_battle_message_text_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name).resolve() / SCHEMA
        cls.payload = export_artifact(ROOT, cls.output)
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_the_fixed_79_slot_message_denominator(self):
        self.assertEqual(EXPECTED_SUMMARY, self.payload["summary"])
        table = self.payload["pointer_table"]
        self.assertEqual([0x5A2034, 0x5A2170], table["range"])
        self.assertEqual(79, table["entry_count"])
        self.assertEqual(
            "c6dc43fda3044405fec144561fb76b3e684aa974a0c5633ec990ba5532b47ce3",
            table["sha256"],
        )
        self.assertEqual(
            "5b8bf5e464c52dac97cd5522c079dea6e31527beb51ed4c0f8b07f934e2a7059",
            self.payload["source_bank"]["sha256"],
        )
        self.assertEqual(79, len(self.payload["records"]))
        self.assertEqual([0x5A1580, 0x5A1593], self.payload["records"][0]["range"])
        self.assertEqual([0x5A200C, 0x5A2021], self.payload["records"][-1]["range"])
        self.assertEqual(
            "d397dcf693ddcfedccaeb56efba1eeb2e646adfdfcea116254b41ad6898110cf",
            self.payload["record_range_denominator_sha256"],
        )
        self.assertEqual(
            "2170a4fffa02b01884c4633470fae48d24594e0083dfeebfb7b1dc52d41bd6e5",
            self.payload["zero_padding_range_denominator_sha256"],
        )
        self.assertTrue(self.payload["scope"]["fixed_79_slot_denominator_complete"])
        self.assertTrue(self.payload["scope"]["all_inter_record_bytes_accounted"])
        self.assertFalse(self.payload["scope"]["runtime_index_bounds_proven"])
        self.assertFalse(self.payload["scope"]["zero_padding_safe_allocatable"])

    def test_classifies_only_parser_records_and_verified_zero_padding(self):
        bundle = (self.output / "battle-message-text-bytes.bin").read_bytes()
        self.assertEqual(2_740, len(bundle))
        self.assertEqual(
            "e0be9ff986140ae489c88769e483d98eab06febcf9f26ebf5fc6395fb428e0b9",
            hashlib.sha256(bundle).hexdigest(),
        )
        ranges = self.payload["classified_ranges"]
        self.assertEqual(158, len(ranges))
        self.assertEqual(79, sum(item["kind"] == "renderer_text_record" for item in ranges))
        self.assertEqual(79, sum(item["kind"] == "inter_record_zero_padding" for item in ranges))
        cursor = 0x5A1580
        for item in ranges:
            self.assertEqual(cursor, item["range"][0])
            cursor = item["range"][1]
        self.assertEqual(0x5A2034, cursor)
        self.assertFalse(any(item["range"] == [0x5A2034, 0x5A2170] for item in ranges))
        expected = b"".join(
            self.rom[start:end] for start, end in (item["range"] for item in ranges)
        )
        self.assertEqual(expected, bundle)
        self.assertEqual(
            "24f1684e150bed11571cfa2f35fbb77d4e44c952d58fbcd5ec15d3e70f8eb8af",
            self.payload["record_content_sha256"],
        )
        self.assertEqual(
            "738f09bb312878c2a990ac9af0ef31be3d3935a34233802f11b8bf10d1a47479",
            self.payload["zero_padding_content_sha256"],
        )

    def test_decodes_both_consumers_wrapper_and_renderer_grammar(self):
        from tools.export_rom_battle_message_text_inventory import (
            _decode_consumer_contract,
            _renderer_end,
            _verify_zero_padding,
        )
        from tools.verify_rom_battle_message_text_inventory import (
            _independent_consumer_contract,
            _independent_renderer_end,
            _independent_verify_zero_padding,
        )

        expected = self.payload["consumer_evidence"]["decoded_semantics"]
        self.assertEqual(expected, _decode_consumer_contract(self.rom))
        self.assertEqual(expected, _independent_consumer_contract(self.rom))
        self.assertEqual(2, len(expected["table_consumers"]))
        self.assertEqual(
            ["0x08098624", "0x08099D58"],
            [item["pointer_table_literal"] for item in expected["table_consumers"]],
        )
        self.assertTrue(
            all(item["wrapper_call_target"] == "0x08098290" for item in expected["table_consumers"])
        )
        self.assertEqual("0x08066758", expected["message_wrapper"]["bridge_call_target"])
        self.assertEqual("0x0806626C", expected["renderer_bridge"]["parser_call_target"])

        synthetic = bytes.fromhex("090a017f028140814000")
        sjis_ranges = ((0x8140, 0x8141),)
        for parser in (_renderer_end, _independent_renderer_end):
            self.assertEqual(len(synthetic), parser(synthetic, 0, len(synthetic), sjis_ranges))
            for malformed in (b"\x01", b"\x02\x01", b"\x81", b"abc"):
                with self.assertRaisesRegex(ValueError, "bounded|truncated|terminator"):
                    parser(malformed, 0, len(malformed), sjis_ranges)

        for checker in (_verify_zero_padding, _independent_verify_zero_padding):
            checker(b"\0\0", 0, 2)
            with self.assertRaisesRegex(ValueError, "zero padding"):
                checker(b"\0\1", 0, 2)

        tampered = bytearray(self.rom)
        tampered[0x985DE] ^= 1
        for decoder in (_decode_consumer_contract, _independent_consumer_contract):
            with self.assertRaisesRegex(ValueError, "consumer|message"):
                decoder(bytes(tampered))

    def test_export_is_deterministic_and_refuses_unsafe_outputs(self):
        from tools.export_rom_battle_message_text_inventory import export_artifact

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

    def test_independent_verifier_rebuilds_committed_and_temporary_artifacts(self):
        from tools.verify_rom_battle_message_text_inventory import verify_artifact

        for artifact in (self.output, ROOT / "artifacts" / SCHEMA):
            report = verify_artifact(ROOT, artifact)
            self.assertTrue(report["verified"], report["errors"])
            self.assertEqual(EXPECTED_SUMMARY, report["summary"])

        verifier_source = (
            ROOT / "tools/verify_rom_battle_message_text_inventory.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools.export_rom_battle_message", verifier_source)
        self.assertNotIn("import tools.export_rom_battle_message", verifier_source)

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "tampered"
            shutil.copytree(self.output, tampered)
            bundle_path = tampered / "battle-message-text-bytes.bin"
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
