from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-dialogue-text-inventory-v1"
EXPECTED_SUMMARY = {
    "table_row_count": 305,
    "table_byte_count": 6_100,
    "sentinel_count": 305,
    "direct_pointer_slot_count": 1_220,
    "direct_target_count": 1_220,
    "unique_target_count": 1_220,
    "duplicate_target_count": 0,
    "overlapping_target_range_count": 0,
    "direct_target_bytes": 18_207,
    "target_payload_bytes": 16_987,
    "newline_target_count": 170,
    "newline_count": 203,
}


class ExportRomDialogueTextInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_dialogue_text_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / SCHEMA
        cls.payload = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_exports_the_fixed_305_by_5_table_denominator(self):
        self.assertEqual(EXPECTED_SUMMARY, self.payload["summary"])
        self.assertEqual(
            {
                "file_range": [0x461CE4, 0x4634B8],
                "gba_range": ["0x08461CE4", "0x084634B8"],
                "row_size": 20,
                "row_count": 305,
                "word_layout": [
                    "zero_sentinel",
                    "primary_text_pointer",
                    "label_0_text_pointer",
                    "label_1_text_pointer",
                    "label_2_text_pointer",
                ],
                "sha256": "5b36c67620030d5ccc8795a2a260aca604d90fad4a49f7c7cb9d4c7cdc63c73f",
            },
            self.payload["table"],
        )
        self.assertEqual(305, len(self.payload["rows"]))
        self.assertTrue(
            all(row["sentinel"] == 0 for row in self.payload["rows"])
        )
        self.assertTrue(
            all(len(row["targets"]) == 4 for row in self.payload["rows"])
        )

    def test_exports_lossless_table_and_packed_nul_targets(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        table = (self.output / "pointer-table.bin").read_bytes()
        bundle = (self.output / "direct-nul-targets.bin").read_bytes()
        self.assertEqual(rom[0x461CE4:0x4634B8], table)
        self.assertEqual(6_100, len(table))
        self.assertEqual(18_207, len(bundle))
        self.assertEqual(
            "7509a63b2f892ea9f2892ed4cc703da72457247df148a1435edbbee8b2d95569",
            hashlib.sha256(bundle).hexdigest(),
        )

        targets = [
            target
            for row in self.payload["rows"]
            for target in row["targets"]
        ]
        self.assertEqual(1_220, len(targets))
        self.assertEqual(list(range(1_220)), [item["target_id"] for item in targets])
        for target in targets:
            start, end = target["range"]
            packed_start, packed_end = target["packed_range"]
            raw = rom[start:end]
            self.assertEqual(b"\0", raw[-1:])
            self.assertEqual(raw, bundle[packed_start:packed_end])
            self.assertEqual(target["bytes_sha256"], hashlib.sha256(raw).hexdigest())

    def test_binds_the_consumer_parser_and_honest_runtime_limit(self):
        evidence = self.payload["consumer_evidence"]
        self.assertEqual("0x080917B0", evidence["table_literal_load"])
        self.assertEqual("0x080918E8", evidence["table_literal"])
        self.assertEqual("0x08461CE4", evidence["table_base"])
        self.assertEqual("0x08091950", evidence["row_index_formula"])
        self.assertEqual("0x080919DA", evidence["primary_pointer_load"])
        self.assertEqual("0x0806626C", evidence["nul_terminated_parser"])
        self.assertEqual(
            [
                "one confirmed group-selection path uses u8; no path-level evidence proves runtime reachability of every row 0..304",
                "label selector values 0..2 are an upstream invariant not checked in this function",
                "raw game glyph codes are not claimed to be correctly decoded natural-language text",
            ],
            self.payload["limitations"],
        )

    def test_export_is_deterministic_and_refuses_foreign_output(self):
        from tools.export_rom_dialogue_text_inventory import export_artifact

        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            export_artifact(ROOT, first)
            export_artifact(ROOT, second)
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
            foreign = Path(temporary) / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "foreign"):
                export_artifact(ROOT, foreign)

    def test_independent_verifier_rebuilds_and_rejects_tamper(self):
        from tools.verify_rom_dialogue_text_inventory import verify_artifact

        verifier_source = (
            ROOT / "tools/verify_rom_dialogue_text_inventory.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_rom_dialogue_text_inventory", verifier_source
        )
        self.assertNotIn(
            "import tools.export_rom_dialogue_text_inventory", verifier_source
        )
        self.assertNotIn("def _rebuild(", verifier_source)
        self.assertIn("def _verify_rows_against_rom(", verifier_source)
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(EXPECTED_SUMMARY, {
            key: report[key] for key in EXPECTED_SUMMARY
        })

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / SCHEMA
            shutil.copytree(self.output, tampered)
            inventory_path = tampered / "dialogue-text-inventory.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["rows"][0]["targets"][0]["range"][1] -= 1
            inventory_path.write_text(
                json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][inventory_path.name] = hashlib.sha256(
                inventory_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

    def test_independent_verifier_rejects_rehashed_binary_tamper(self):
        from tools.verify_rom_dialogue_text_inventory import verify_artifact

        for relative in ("pointer-table.bin", "direct-nul-targets.bin"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                tampered = Path(temporary) / SCHEMA
                shutil.copytree(self.output, tampered)
                target = tampered / relative
                raw = bytearray(target.read_bytes())
                raw[len(raw) // 2] ^= 1
                target.write_bytes(raw)

                manifest_path = tampered / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["files"][relative] = hashlib.sha256(raw).hexdigest()
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )

                rejected = verify_artifact(ROOT, tampered)
                self.assertFalse(rejected["verified"])
                self.assertTrue(rejected["errors"])


if __name__ == "__main__":
    unittest.main()
