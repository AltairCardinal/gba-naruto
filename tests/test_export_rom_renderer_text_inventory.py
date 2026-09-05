from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-renderer-text-inventory-v1"
EXPECTED_SUMMARY = {
    "pointer_table_count": 11,
    "pointer_slot_count": 704,
    "unique_target_count": 625,
    "renderer_record_count": 625,
    "renderer_consumed_bytes": 22_588,
    "target_overlap_bytes": 0,
    "parse_failure_count": 0,
    "packed_text_bytes": 22_588,
}
EXPECTED_TABLES = {
    94: (112, 86, 1_388, "aec0c65cba13e896577ef6cc91252383bc9c896194cf05605d9450bf7980b908", "0e8afd4439cc16d004004dfa6c42304fb516625cba9cafa914e358cb658e0a8a"),
    95: (112, 86, 5_971, "54558c6230e22bf836a67be87c4b4c543459e679cda38d2e7745a5e509b1f34a", "bc56317c6a0caad2ec580cae9c34e8bcd6cbb52eab5c76eec31c25a0e0b9f5ce"),
    96: (112, 86, 3_576, "e63e4a021a1dc30611157c49bec44062fe7c6e366a094537cc926602db7bfdeb", "71415af5246f7bee17ebf5e2c446b818d90e0dfa572ca9f026dcd0cb0d89e073"),
    105: (16, 15, 99, "c8fdad326683e3a99af0920e3908010666fa80fa786b7b7cf8995e5499c0e711", "34c2e71bb2233b8db3e20c0c273109f6f257e5d6e083134ca46ad8a4702e8aec"),
    107: (24, 24, 630, "370f2f35e24f591a7f50079f44ba13985c07c817d9d04f88859933724ba2ee7a", "50ff8ecf8a83ff56522499ee8b6bf12ddaef84405e8efefb6aece0d59a442485"),
    108: (24, 24, 590, "90f29589834f2d8685b6946b6cad4adfe89d322d55c476b6ed0d7c76d92cef11", "b7aee19087b891ea77b426df3c0fe24d89c72734e33341814280f9bbe07a2c2b"),
    109: (84, 84, 3_326, "afde88d7b2f6ca2209b75f6396fd474cca7cd50c326b529a92c9294382017e2d", "6696738c27283cfb8cc504d546f76a560d2d2ef8c22a36147f8f41884e45ecc8"),
    111: (92, 92, 3_965, "1b474f922eaf379ebea5058195b1945286254f1fb309a60c596d9d83167b6dba", "c56690de773116a7c03c4a26cb67f3b466afb315fd901d7426bb4956e5c3bbcf"),
    112: (16, 16, 806, "26c3da0f98d529b5a243079b9ff2712aea8dd551604e5d01692d989e658ff7e3", "bf7b5f860cc5fb5754f3a3266b7a337ccc7a8506b38e301f6e3c8e8d766c5000"),
    113: (68, 68, 1_692, "764b975c2bc6bf2d5aed2ede14a3ce5d0f54fbd38c0b7f2f02fdb8b021bcc055", "f9456aa250b6f79dc2df03c9af7972d1ff5af337eed645ea4edc182314ba6f48"),
    114: (44, 44, 545, "b6ac3d64a52e98c8aa0d812dc4f01bbce27064edd66b300fdaeb5b898a755ad0", "7e75ad0e81a5a856ae20daea2e9428af3e99ba2b5a4b32970a6b340c3057e08a"),
}


class ExportRomRendererTextInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_renderer_text_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / SCHEMA
        cls.payload = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_the_fixed_eleven_table_denominator(self):
        self.assertEqual(EXPECTED_SUMMARY, self.payload["summary"])
        self.assertEqual(11, len(self.payload["pointer_tables"]))
        for table in self.payload["pointer_tables"]:
            slots, unique, byte_count, range_hash, content_hash = EXPECTED_TABLES[
                table["candidate_id"]
            ]
            self.assertEqual(slots, table["entry_count"])
            self.assertEqual(unique, table["unique_target_count"])
            self.assertEqual(byte_count, table["renderer_consumed_bytes"])
            self.assertEqual(range_hash, table["range_denominator_sha256"])
            self.assertEqual(content_hash, table["content_sha256"])

    def test_exports_only_parser_bounded_targets_in_one_bundle(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        bundle = (self.output / "renderer-text-targets.bin").read_bytes()
        records = self.payload["records"]
        self.assertEqual(625, len(records))
        self.assertEqual([0x59A1B8, 0x59A1BB], records[0]["range"])
        self.assertEqual([0x5AE260, 0x5AE261], records[-1]["range"])
        self.assertEqual(22_588, len(bundle))
        self.assertEqual(
            {"manifest.json", "renderer-text-inventory.json", "renderer-text-targets.bin"},
            {path.name for path in self.output.iterdir() if path.is_file()},
        )
        cursor = 0
        for record in records:
            start, end = record["range"]
            packed_start, packed_end = record["packed_range"]
            self.assertEqual(cursor, packed_start)
            self.assertEqual(rom[start:end], bundle[packed_start:packed_end])
            self.assertEqual(end - start, record["size"])
            cursor = packed_end
        self.assertEqual(len(bundle), cursor)

    def test_binds_lookup_paths_and_the_control_aware_renderer(self):
        evidence = self.payload["consumer_evidence"]
        self.assertEqual(
            {
                "file_range": [0x06626C, 0x066736],
                "gba_range": ["0x0806626C", "0x08066736"],
                "sha256": "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be",
            },
            evidence["renderer_parser"],
        )
        self.assertEqual("0x0806626C", evidence["renderer_bridge"]["call_target"])
        self.assertEqual(11, len(evidence["table_consumers"]))
        self.assertTrue(
            all(record["call_target"] in {"0x08066758", "0x0809822C"} for record in evidence["table_consumers"])
        )
        self.assertFalse(self.payload["scope"]["natural_gameplay_index_coverage_complete"])
        self.assertFalse(self.payload["scope"]["unicode_decoding_complete"])

    def test_export_is_deterministic_and_refuses_foreign_output(self):
        from tools.export_rom_renderer_text_inventory import export_artifact

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

    def test_independent_verifier_rejects_rehashed_payload_tamper(self):
        from tools.verify_rom_renderer_text_inventory import verify_artifact

        source = (ROOT / "tools/verify_rom_renderer_text_inventory.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("from tools.export_rom_renderer_text_inventory", source)
        self.assertNotIn("import tools.export_rom_renderer_text_inventory", source)
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(EXPECTED_SUMMARY, {key: report[key] for key in EXPECTED_SUMMARY})

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / SCHEMA
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "renderer-text-inventory.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["records"][0]["range"][1] -= 1
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


if __name__ == "__main__":
    unittest.main()
