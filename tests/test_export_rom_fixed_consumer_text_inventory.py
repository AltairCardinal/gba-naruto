from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-fixed-consumer-text-inventory-v1"
EXPECTED_SUMMARY = {
    "pointer_table_count": 11,
    "pointer_slot_count": 750,
    "null_pointer_slot_count": 11,
    "pointer_table_bytes": 3_000,
    "unique_target_count": 735,
    "renderer_record_count": 735,
    "renderer_consumed_bytes": 11_177,
    "classified_range_count": 746,
    "classified_bytes": 14_177,
    "range_overlap_bytes": 0,
    "parse_failure_count": 0,
    "packed_bytes": 14_177,
}
EXPECTED_TABLES = (
    (
        "ui_summary_name_9",
        [0x5A65C8, 0x5A65EC],
        9,
        9,
        383,
        "5180da939a292991fdb3995bfad4179f9768f6d716b70db49f4367c970dea368",
    ),
    (
        "low_detail_action_name_87",
        [0x5A6D04, 0x5A6E60],
        87,
        86,
        728,
        "a9bd263418cf363d7ff4280490576c650a236b6ffe01497a01a79b2edc24e091",
    ),
    (
        "passive_auxiliary_text_45",
        [0x5A7060, 0x5A7114],
        45,
        44,
        364,
        "1231c8f3ac946f9138d1becab3a330aed1421bedc698c746471e7b4157206b71",
    ),
    (
        "passive_detail_name_45",
        [0x5A73E0, 0x5A7494],
        45,
        44,
        364,
        "3bb9d9c1e7d4d2d58c12a1167d3598c48fa693384d9746639e70a06a75d1e829",
    ),
    (
        "ninja_tool_detail_name_94",
        [0x5A7C50, 0x5A7DC8],
        94,
        93,
        917,
        "403cb842a3018e1da6fcbd8cbca9bb55f554cc17065499c76c7214088f932d65",
    ),
    (
        "unit_name_63",
        [0x599280, 0x59937C],
        63,
        63,
        447,
        "68e8c6fc03c6a321ef701611aea372dd88e22aa16bd795706ec6e8ddb6946a1d",
    ),
    (
        "active_action_name_87",
        [0x59937C, 0x5994D8],
        87,
        87,
        731,
        "72c9247c5660a892890fb85da8606d9d47a3d15e01d06aee53dff7f5189145ac",
    ),
    (
        "message_command_text_100",
        [0x599634, 0x5997C4],
        100,
        99,
        1_065,
        "cedf35c21b949aeacd8accf29a96856ed1595d3434f2b46bd2c893049fc6410f",
    ),
    (
        "passive_description_45",
        [0x5AAEDC, 0x5AAF90],
        45,
        45,
        1_781,
        "1c1d5f7bad33686bc3c0f51c2f057bb7778d8dccedfc65104720376dc5eb200f",
    ),
    (
        "active_action_description_87",
        [0x5994D8, 0x599634],
        87,
        77,
        1_837,
        "55eb1e146e7f3f77672fe9508571e3393280821e001f80493b61b4cb8c2207d0",
    ),
    (
        "ninja_tool_description_suffix_88",
        [0x5997C4, 0x599924],
        88,
        88,
        2_560,
        "f27b28abedfe7a437f4843ba6c824e4c761655892d0bc4978a5f757e6e4fbb8e",
    ),
)


class ExportRomFixedConsumerTextInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_fixed_consumer_text_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name).resolve() / SCHEMA
        cls.payload = export_artifact(ROOT, cls.output)
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_the_fixed_pointer_table_denominators(self):
        self.assertEqual(EXPECTED_SUMMARY, self.payload["summary"])
        actual = tuple(
            (
                table["table_id"],
                table["range"],
                table["entry_count"],
                table["unique_target_count"],
                table["renderer_consumed_bytes"],
                table["sha256"],
            )
            for table in self.payload["pointer_tables"]
        )
        self.assertEqual(EXPECTED_TABLES, actual)
        self.assertEqual(735, len(self.payload["records"]))
        self.assertEqual(
            "fa0faadae92918131418cf5ce089503550bbd87edc85e5dfa354b6fbe9f3d551",
            self.payload["record_range_denominator_sha256"],
        )
        self.assertFalse(self.payload["scope"]["runtime_index_bounds_proven"])
        self.assertFalse(
            self.payload["scope"]["natural_gameplay_index_coverage_complete"]
        )

    def test_closes_the_second_fixed_consumer_table_batch(self):
        expected = {
            (0x599280, 0x59937C): (63, 63, 447),
            (0x59937C, 0x5994D8): (87, 87, 731),
            (0x599634, 0x5997C4): (100, 99, 1_065),
            (0x5AAEDC, 0x5AAF90): (45, 45, 1_781),
        }
        actual = {
            tuple(table["range"]): (
                table["entry_count"],
                table["unique_target_count"],
                table["renderer_consumed_bytes"],
            )
            for table in self.payload["pointer_tables"]
            if tuple(table["range"]) in expected
        }
        self.assertEqual(expected, actual)
        self.assertEqual(11, self.payload["summary"]["pointer_table_count"])
        self.assertEqual(750, self.payload["summary"]["pointer_slot_count"])
        self.assertEqual(11, self.payload["summary"]["null_pointer_slot_count"])
        self.assertEqual(11_177, self.payload["summary"]["renderer_consumed_bytes"])
        message = next(
            table
            for table in self.payload["pointer_tables"]
            if table["table_id"] == "message_command_text_100"
        )
        self.assertEqual([94], message["null_slot_indices"])
        self.assertEqual("consumer_index_upper_bound", message["boundary_kind"])
        self.assertNotIn(
            [0x5A7FCC, 0x5A8014],
            [table["range"] for table in self.payload["pointer_tables"]],
        )

    def test_packs_only_tables_and_parser_consumed_records(self):
        bundle = (self.output / "fixed-consumer-text-bytes.bin").read_bytes()
        self.assertEqual(14_177, len(bundle))
        self.assertEqual(
            "e71eefd9ee1d98333fdd0cd72c6b67ce6335a6874bf5f92c072177807ca1168a",
            hashlib.sha256(bundle).hexdigest(),
        )
        ranges = self.payload["classified_ranges"]
        self.assertEqual(746, len(ranges))
        self.assertTrue(
            all(left["range"][1] <= right["range"][0] for left, right in zip(ranges, ranges[1:]))
        )
        expected = b"".join(self.rom[start:end] for start, end in (item["range"] for item in ranges))
        self.assertEqual(expected, bundle)
        self.assertEqual(
            {
                "fixed-consumer-text-inventory.json",
                "fixed-consumer-text-bytes.bin",
                "manifest.json",
            },
            {path.name for path in self.output.iterdir() if path.is_file()},
        )
        self.assertTrue(
            all(item["kind"] in {"pointer_table", "renderer_text_record"} for item in ranges)
        )

    def test_decodes_each_consumer_and_the_renderer_grammar(self):
        from tools.export_rom_fixed_consumer_text_inventory import (
            _decode_consumer_semantics,
            _renderer_record_end,
        )
        from tools.verify_rom_fixed_consumer_text_inventory import (
            _decode_consumer_contract,
            _independent_renderer_end,
        )

        expected = self.payload["consumer_evidence"]["decoded_semantics"]
        self.assertEqual(expected, _decode_consumer_semantics(self.rom))
        self.assertEqual(expected, _decode_consumer_contract(self.rom))
        self.assertEqual(
            {
                "ui_summary_name_9",
                "low_detail_action_name_87",
                "passive_auxiliary_text_45",
                "passive_detail_name_45",
                "ninja_tool_detail_name_94",
                "unit_name_63",
                "active_action_name_87",
                "message_command_text_100",
                "passive_description_45",
                "active_action_description_87",
                "ninja_tool_description_suffix_88",
            },
            set(expected["table_consumers"]),
        )
        self.assertEqual("0x0806626C", expected["renderer_path"]["parser"])
        self.assertEqual(31, expected["renderer_grammar"]["sjis_range_count"])

        synthetic = bytes.fromhex("017f02101181400a00")
        sjis_ranges = ((0x8140, 0x8141),)
        self.assertEqual(
            len(synthetic),
            _renderer_record_end(synthetic, 0, len(synthetic), sjis_ranges),
        )
        self.assertEqual(
            len(synthetic),
            _independent_renderer_end(synthetic, 0, len(synthetic), sjis_ranges),
        )
        for parser in (_renderer_record_end, _independent_renderer_end):
            for truncated in (b"\x01", b"\x02\x10", b"\x81", b"A"):
                with self.assertRaisesRegex(ValueError, "bounded|truncated|terminator"):
                    parser(truncated, 0, len(truncated), sjis_ranges)

        tampered = bytearray(self.rom)
        tampered[0x071178] ^= 1
        with self.assertRaisesRegex(ValueError, "consumer"):
            _decode_consumer_semantics(bytes(tampered))
        with self.assertRaisesRegex(ValueError, "consumer"):
            _decode_consumer_contract(bytes(tampered))

        tampered = bytearray(self.rom)
        tampered[0x079670] ^= 1
        with self.assertRaisesRegex(ValueError, "consumer"):
            _decode_consumer_semantics(bytes(tampered))
        with self.assertRaisesRegex(ValueError, "consumer"):
            _decode_consumer_contract(bytes(tampered))

    def test_export_is_deterministic_and_refuses_unsafe_outputs(self):
        from tools.export_rom_fixed_consumer_text_inventory import export_artifact

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

            fake = temporary_root / "fake"
            fake.mkdir()
            fake_payload = b"{}\n"
            fake_bundle = b"fake"
            (fake / "fixed-consumer-text-inventory.json").write_bytes(fake_payload)
            (fake / "fixed-consumer-text-bytes.bin").write_bytes(fake_bundle)
            (fake / "manifest.json").write_text(
                json.dumps(
                    {
                        "artifact_schema": SCHEMA,
                        "files": {
                            "fixed-consumer-text-inventory.json": hashlib.sha256(fake_payload).hexdigest(),
                            "fixed-consumer-text-bytes.bin": hashlib.sha256(fake_bundle).hexdigest(),
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "independent verification"):
                export_artifact(ROOT, fake)

            legacy = temporary_root / "legacy"
            shutil.copytree(ROOT / "artifacts" / SCHEMA, legacy)
            export_artifact(ROOT, legacy)
            from tools.verify_rom_fixed_consumer_text_inventory import verify_artifact
            self.assertTrue(verify_artifact(ROOT, legacy)["verified"])
        with self.assertRaisesRegex(ValueError, "repository root"):
            export_artifact(ROOT, ROOT)

    def test_independent_verifier_rejects_rehashed_tampering(self):
        from tools.verify_rom_fixed_consumer_text_inventory import verify_artifact

        source = (ROOT / "tools/verify_rom_fixed_consumer_text_inventory.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("from tools.export_rom_fixed_consumer_text_inventory", source)
        self.assertNotIn("import tools.export_rom_fixed_consumer_text_inventory", source)
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(EXPECTED_SUMMARY, {key: report[key] for key in EXPECTED_SUMMARY})

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / SCHEMA
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "fixed-consumer-text-inventory.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["records"][0]["range"][1] -= 1
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][payload_path.name] = hashlib.sha256(payload_path.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

    def test_verifier_binds_the_root_copy_and_repository_artifact(self):
        import tools.verify_rom_fixed_consumer_text_inventory as verifier

        with mock.patch.object(verifier, "__file__", "/tmp/copied-verifier.py"):
            report = verifier.verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        committed = verifier.verify_artifact(ROOT, ROOT / "artifacts" / SCHEMA)
        self.assertTrue(committed["verified"], committed["errors"])
        self.assertEqual(EXPECTED_SUMMARY, {key: committed[key] for key in EXPECTED_SUMMARY})


if __name__ == "__main__":
    unittest.main()
