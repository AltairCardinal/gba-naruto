from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-training-text-script-inventory-v1"
EXPECTED_SUMMARY = {
    "pointer_table_count": 1,
    "pointer_slot_count": 45,
    "pointer_table_bytes": 180,
    "null_slot_count": 1,
    "non_null_slot_count": 44,
    "unique_target_count": 44,
    "command_record_count": 44,
    "command_count": 264,
    "embedded_renderer_text_count": 44,
    "embedded_renderer_text_bytes": 1_889,
    "record_bytes": 2_505,
    "classified_range_count": 44,
    "classified_bytes": 2_505,
    "inter_record_gap_bytes": 0,
    "range_overlap_bytes": 0,
    "parse_failure_count": 0,
    "packed_bytes": 2_505,
}


class ExportRomTrainingTextScriptInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_training_text_script_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name).resolve() / SCHEMA
        cls.payload = export_artifact(ROOT, cls.output)
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_the_fixed_training_slot_denominator(self):
        self.assertEqual(EXPECTED_SUMMARY, self.payload["summary"])
        table = self.payload["pointer_table"]
        self.assertEqual([0x59A104, 0x59A1B8], table["range"])
        self.assertEqual(45, table["entry_count"])
        self.assertEqual([0], table["null_slot_indices"])
        self.assertEqual(list(range(1, 45)), table["non_null_slot_indices"])
        self.assertEqual(
            "98b063cc49b8ab7b036b612bd81fb3f564187b54fd963e36c9cdc78909d9876b",
            table["sha256"],
        )
        self.assertEqual(44, len(self.payload["records"]))
        self.assertEqual([0x7554, 0x7587], self.payload["records"][0]["range"])
        self.assertEqual([0x7EE4, 0x7F1D], self.payload["records"][-1]["range"])
        self.assertEqual(
            "d4658b515cf3f02813546f9ae909a0a00a646a70096470f1475695f9b46ede94",
            self.payload["record_range_denominator_sha256"],
        )
        self.assertEqual(
            {"0": 44, "1": 44, "3": 44, "4": 44, "5": 44, "12": 44},
            self.payload["command_opcode_counts"],
        )
        self.assertTrue(
            all(
                record["opcode_sequence"] == [1, 5, 4, 12, 3, 0]
                for record in self.payload["records"]
            )
        )
        self.assertTrue(self.payload["scope"]["all_45_slots_classified"])
        self.assertTrue(self.payload["scope"]["all_non_null_records_parsed"])
        self.assertFalse(self.payload["scope"]["natural_gameplay_all_ids_proven"])
        self.assertFalse(self.payload["scope"]["unicode_decoding_complete"])

    def test_packs_only_interpreter_consumed_records(self):
        bundle = (self.output / "training-text-script-bytes.bin").read_bytes()
        self.assertEqual(2_505, len(bundle))
        self.assertEqual(
            "fa9991353e99ecd63d8e0617fb078198b62527d548c8c5eb5fbac173d0302da0",
            hashlib.sha256(bundle).hexdigest(),
        )
        ranges = self.payload["classified_ranges"]
        self.assertEqual(44, len(ranges))
        self.assertTrue(
            all(left["range"][1] == right["range"][0] for left, right in zip(ranges, ranges[1:]))
        )
        expected = b"".join(
            self.rom[start:end] for start, end in (item["range"] for item in ranges)
        )
        self.assertEqual(expected, bundle)
        self.assertEqual(
            {
                "manifest.json",
                "training-text-script-inventory.json",
                "training-text-script-bytes.bin",
            },
            {path.name for path in self.output.iterdir() if path.is_file()},
        )
        self.assertTrue(
            all(item["kind"] == "training_text_command_script" for item in ranges)
        )

    def test_decodes_consumer_interpreter_and_nested_renderer_grammar(self):
        from tools.export_rom_training_text_script_inventory import (
            _decode_training_contract,
            _parse_training_record,
        )
        from tools.verify_rom_training_text_script_inventory import (
            _independent_consumer_contract,
            _independent_parse_record,
        )

        expected = self.payload["consumer_evidence"]["decoded_semantics"]
        self.assertEqual(expected, _decode_training_contract(self.rom))
        self.assertEqual(expected, _independent_consumer_contract(self.rom))
        self.assertEqual("0x08067158", expected["training_consumer"]["call_target"])
        self.assertEqual(
            {
                "0": "terminate",
                "1": "fixed_7",
                "3": "fixed_2",
                "4": "fixed_1",
                "5": "renderer_text_from_plus_2",
                "12": "fixed_1",
            },
            expected["training_interpreter"]["used_opcode_contract"],
        )

        synthetic = bytes.fromhex("0107090a0c06000507814000040c030700")
        sjis_ranges = ((0x8140, 0x8141),)
        for parser in (_parse_training_record, _independent_parse_record):
            parsed = parser(synthetic, 0, len(synthetic), sjis_ranges)
            self.assertEqual(len(synthetic), parsed["end"])
            self.assertEqual([1, 5, 4, 12, 3, 0], parsed["opcode_sequence"])
            self.assertEqual([[9, 12]], parsed["embedded_renderer_ranges"])
            for malformed in (
                b"\x01",
                bytes.fromhex("0107090a0c0600050781"),
                bytes.fromhex("0107090a0c060005074100040c0307"),
                b"\x06\x00",
            ):
                with self.assertRaisesRegex(
                    ValueError, "bounded|truncated|terminator|unsupported"
                ):
                    parser(malformed, 0, len(malformed), sjis_ranges)

        tampered_consumer = bytearray(self.rom)
        tampered_consumer[0x932DE] ^= 1
        for decoder in (_decode_training_contract, _independent_consumer_contract):
            with self.assertRaisesRegex(ValueError, "consumer"):
                decoder(bytes(tampered_consumer))
        tampered_dispatch = bytearray(self.rom)
        tampered_dispatch[0x67194] ^= 1
        for decoder in (_decode_training_contract, _independent_consumer_contract):
            with self.assertRaisesRegex(ValueError, "interpreter|dispatch"):
                decoder(bytes(tampered_dispatch))

    def test_export_is_deterministic_and_refuses_unsafe_outputs(self):
        from tools.export_rom_training_text_script_inventory import export_artifact

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
            fake_manifest = {
                "artifact_schema": SCHEMA,
                "files": {
                    "training-text-script-inventory.json": hashlib.sha256(
                        fake_payload
                    ).hexdigest(),
                    "training-text-script-bytes.bin": hashlib.sha256(
                        fake_bundle
                    ).hexdigest(),
                },
            }
            (fake / "training-text-script-inventory.json").write_bytes(fake_payload)
            (fake / "training-text-script-bytes.bin").write_bytes(fake_bundle)
            (fake / "manifest.json").write_text(
                json.dumps(fake_manifest), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "verification|foreign"):
                export_artifact(ROOT, fake)

        with self.assertRaisesRegex(ValueError, "repository root"):
            export_artifact(ROOT, ROOT)
        with self.assertRaisesRegex(ValueError, "ancestor"):
            export_artifact(ROOT, ROOT.parent)

    def test_independent_verifier_rebuilds_and_rejects_rehashed_tampering(self):
        from tools.verify_rom_training_text_script_inventory import verify_artifact

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(EXPECTED_SUMMARY, report["summary"])

        verifier_source = (
            ROOT / "tools/verify_rom_training_text_script_inventory.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("import_rom_training_text_script_inventory", verifier_source)
        self.assertNotIn("from tools.export_rom_training", verifier_source)
        self.assertNotIn("import tools.export_rom_training", verifier_source)

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary).resolve()
            tampered = temporary_root / "tampered"
            shutil.copytree(self.output, tampered)
            bundle_path = tampered / "training-text-script-bytes.bin"
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

            copied_root = temporary_root / "root-copy"
            for relative in (
                "rom/base.gba",
                "tools/export_rom_training_text_script_inventory.py",
                "tools/verify_rom_training_text_script_inventory.py",
                "tests/test_export_rom_training_text_script_inventory.py",
            ):
                destination = copied_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            copied_artifact = copied_root / f"artifacts/{SCHEMA}"
            shutil.copytree(self.output, copied_artifact)
            self.assertTrue(
                verify_artifact(copied_root, copied_artifact)["verified"]
            )

    def test_repository_artifact_is_current(self):
        from tools.verify_rom_training_text_script_inventory import verify_artifact

        report = verify_artifact(ROOT, ROOT / f"artifacts/{SCHEMA}")
        self.assertTrue(report["verified"], report["errors"])


if __name__ == "__main__":
    unittest.main()
