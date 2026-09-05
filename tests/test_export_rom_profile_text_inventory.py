from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-profile-text-inventory-v1"
EXPECTED_SUMMARY = {
    "pointer_table_count": 1,
    "pointer_slot_count": 46,
    "unique_target_count": 46,
    "profile_text_record_count": 46,
    "profile_text_bytes": 6_798,
    "alignment_padding_range_count": 19,
    "alignment_padding_bytes": 38,
    "claimed_region_bytes": 6_836,
    "parse_failure_count": 0,
}


class ExportRomProfileTextInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_profile_text_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name).resolve() / SCHEMA
        cls.payload = export_artifact(ROOT, cls.output)
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_the_fixed_forty_six_slot_denominator(self):
        payload = self.payload
        self.assertEqual(EXPECTED_SUMMARY, payload["summary"])
        self.assertEqual([0x5A143C, 0x5A14F4], payload["pointer_table"]["range"])
        self.assertEqual(
            "e372c37fc5d41e2118ebee5feeb81967dd2f8413cc70d01ff7dc493197771410",
            payload["pointer_table"]["sha256"],
        )
        self.assertEqual(46, len(payload["records"]))
        self.assertEqual(46, len({record["range"][0] for record in payload["records"]}))
        self.assertEqual([0x59F988, 0x59FA18], payload["records"][0]["range"])
        self.assertEqual([0x5A13AC, 0x5A143C], payload["records"][-1]["range"])
        self.assertTrue(
            all(
                left["range"][0] < right["range"][0]
                for left, right in zip(payload["records"], payload["records"][1:])
            )
        )

    def test_exports_a_complete_record_and_padding_partition(self):
        payload = self.payload
        region = (self.output / "profile-text-region.bin").read_bytes()
        self.assertEqual(self.rom[0x59F988:0x5A143C], region)
        self.assertEqual(6_836, len(region))
        self.assertEqual(
            "b3b663177a39e60f691fde0ff9272df69e875a116abc5a08647c4ec5d17c142d",
            hashlib.sha256(region).hexdigest(),
        )
        self.assertEqual(
            {
                "manifest.json",
                "profile-text-inventory.json",
                "profile-text-region.bin",
            },
            {path.name for path in self.output.iterdir() if path.is_file()},
        )

        partitions = sorted(
            [record["range"] for record in payload["records"]]
            + [padding["range"] for padding in payload["alignment_padding"]]
        )
        cursor = 0x59F988
        for start, end in partitions:
            self.assertEqual(cursor, start)
            self.assertLess(start, end)
            cursor = end
        self.assertEqual(0x5A143C, cursor)
        self.assertTrue(
            all(
                self.rom[start:end] == b"\0" * (end - start)
                for start, end in (
                    padding["range"] for padding in payload["alignment_padding"]
                )
            )
        )

    def test_binds_profile_reader_renderer_and_runtime_ab(self):
        evidence = self.payload["consumer_evidence"]
        self.assertEqual("0x085A143C", evidence["pointer_table_address"])
        self.assertEqual(
            ["0x0808A704", "0x0808B214"], evidence["table_base_literals"]
        )
        self.assertEqual("0x0808D1A4", evidence["profile_line_wrapper"]["address"])
        self.assertEqual("0x08066758", evidence["profile_line_wrapper"]["call_target"])
        self.assertEqual("0x0806626C", evidence["renderer_bridge"]["call_target"])
        runtime = evidence["runtime_ab"]
        self.assertEqual(1, runtime["control"]["hit_count"])
        self.assertEqual("0x0859F988", runtime["control"]["selected_pointer"])
        self.assertEqual("0x0859FDE8", runtime["variant"]["selected_pointer"])
        self.assertEqual(4, runtime["single_factor_patch"]["size"])
        self.assertFalse(self.payload["scope"]["natural_gameplay_all_ids_complete"])
        self.assertFalse(self.payload["scope"]["unicode_decoding_complete"])
        self.assertEqual(
            {
                "id_load_offset": 0x08B1A0,
                "index_scale": 4,
                "pointer_load_offset": 0x08B1A6,
                "table_literal_offset": 0x08B214,
                "wrapper_call_offset": 0x08B1B2,
                "wrapper_call_target": "0x0808D1A4",
            },
            evidence["decoded_semantics"]["profile_pointer_selector"],
        )
        self.assertEqual(
            {
                "pair_width": 2,
                "pair_copy_range": [0x08D1DC, 0x08D1F4],
                "line_break_value": 0x0A,
                "line_break_compare_offset": 0x08D1F6,
                "terminator_value": 0,
                "terminator_compare_offset": 0x08D1FA,
                "line_advance_offset": 0x08D1C8,
            },
            evidence["decoded_semantics"]["profile_record_grammar"],
        )

    def test_decoded_semantics_and_bounded_parser_fail_closed(self):
        from tools.export_rom_profile_text_inventory import (
            _decode_consumer_semantics,
            _profile_text_end,
        )
        from tools.verify_rom_profile_text_inventory import (
            _bounded_profile_end,
            _decode_consumer_contract,
        )

        expected = self.payload["consumer_evidence"]["decoded_semantics"]
        self.assertEqual(expected, _decode_consumer_semantics(self.rom))
        self.assertEqual(expected, _decode_consumer_contract(self.rom))
        synthetic = bytes.fromhex("81400a824100")
        self.assertEqual((len(synthetic), 1), _profile_text_end(synthetic, 0, 6))
        self.assertEqual((len(synthetic), 1), _bounded_profile_end(synthetic, 0, 6))
        for parser in (_profile_text_end, _bounded_profile_end):
            with self.assertRaisesRegex(ValueError, "terminator"):
                parser(bytes.fromhex("81400a82"), 0, 4)
        tampered = bytearray(self.rom)
        tampered[0x08B1A2] ^= 1
        with self.assertRaisesRegex(ValueError, "selector"):
            _decode_consumer_semantics(bytes(tampered))
        with self.assertRaisesRegex(ValueError, "selector"):
            _decode_consumer_contract(bytes(tampered))

    def test_export_is_deterministic_and_refuses_unsafe_outputs(self):
        from tools.export_rom_profile_text_inventory import export_artifact

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary).resolve()
            first = temporary_root / "first"
            second = temporary_root / "second"
            export_artifact(ROOT, first)
            export_artifact(ROOT, second)
            export_artifact(ROOT, first)
            self.assertEqual(
                {
                    path.relative_to(first): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in first.rglob("*")
                    if path.is_file()
                },
                {
                    path.relative_to(second): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in second.rglob("*")
                    if path.is_file()
                },
            )
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
            fake_region = b"fake"
            (fake / "profile-text-inventory.json").write_bytes(fake_payload)
            (fake / "profile-text-region.bin").write_bytes(fake_region)
            (fake / "manifest.json").write_text(
                json.dumps(
                    {
                        "artifact_schema": SCHEMA,
                        "files": {
                            "profile-text-inventory.json": hashlib.sha256(
                                fake_payload
                            ).hexdigest(),
                            "profile-text-region.bin": hashlib.sha256(
                                fake_region
                            ).hexdigest(),
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "independent verification"):
                export_artifact(ROOT, fake)
        with self.assertRaisesRegex(ValueError, "repository root"):
            export_artifact(ROOT, ROOT)

    def test_independent_verifier_rejects_rehashed_payload_tamper(self):
        from tools.verify_rom_profile_text_inventory import verify_artifact

        source = (ROOT / "tools/verify_rom_profile_text_inventory.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("from tools.export_rom_profile_text_inventory", source)
        self.assertNotIn("import tools.export_rom_profile_text_inventory", source)
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(EXPECTED_SUMMARY, {key: report[key] for key in EXPECTED_SUMMARY})

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / SCHEMA
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "profile-text-inventory.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["records"][0]["range"][1] -= 2
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][payload_path.name] = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

            tampered_padding = Path(temporary) / f"{SCHEMA}-padding"
            shutil.copytree(self.output, tampered_padding)
            padding_payload_path = tampered_padding / "profile-text-inventory.json"
            padding_payload = json.loads(
                padding_payload_path.read_text(encoding="utf-8")
            )
            padding_payload["alignment_padding"][0]["after_record_index"] += 1
            padding_payload_path.write_text(
                json.dumps(
                    padding_payload, ensure_ascii=False, indent=2, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )
            padding_manifest_path = tampered_padding / "manifest.json"
            padding_manifest = json.loads(
                padding_manifest_path.read_text(encoding="utf-8")
            )
            padding_manifest["files"][padding_payload_path.name] = hashlib.sha256(
                padding_payload_path.read_bytes()
            ).hexdigest()
            padding_manifest_path.write_text(
                json.dumps(
                    padding_manifest, ensure_ascii=False, indent=2, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
            )
            rejected_padding = verify_artifact(ROOT, tampered_padding)
            self.assertFalse(rejected_padding["verified"])
            self.assertTrue(rejected_padding["errors"])

    def test_verifier_binds_the_root_copy_not_its_import_location(self):
        import tools.verify_rom_profile_text_inventory as verifier

        with mock.patch.object(verifier, "__file__", "/tmp/copied-verifier.py"):
            report = verifier.verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])

    def test_repository_artifact_is_independently_verified(self):
        from tools.verify_rom_profile_text_inventory import verify_artifact

        report = verify_artifact(ROOT, ROOT / "artifacts" / SCHEMA)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(EXPECTED_SUMMARY, {key: report[key] for key in EXPECTED_SUMMARY})


if __name__ == "__main__":
    unittest.main()
