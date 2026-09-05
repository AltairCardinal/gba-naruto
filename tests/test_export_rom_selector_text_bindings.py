from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-selector-text-bindings-v1"
EXPECTED_DIRECT_NAME_SLOTS = [
    1,
    2,
    3,
    7,
    44,
    43,
    4,
    5,
    6,
    45,
    8,
    9,
    10,
    46,
    11,
    12,
    13,
    47,
    48,
    30,
    51,
    52,
    14,
    15,
    16,
    17,
    18,
    19,
    22,
    23,
    24,
    29,
    61,
    20,
    21,
    31,
    49,
    56,
    50,
    25,
    26,
    27,
    28,
    53,
    54,
    62,
]
EXPECTED_SUMMARY = {
    "direct_source_record_count": 46,
    "direct_source_record_bytes": 920,
    "direct_text_candidate_slot_count": 46,
    "direct_text_consumed_bytes": 324,
    "direct_text_unclassified_suffix_bytes": 550,
    "configured_physical_slot_count": 55,
    "configured_referenced_slot_count": 38,
    "configured_text_consumed_bytes": 316,
    "configured_text_unclassified_suffix_bytes": 368,
    "configured_unreferenced_slot_bytes": 306,
    "config_list_count": 3,
    "config_record_count": 38,
    "config_terminator_count": 3,
    "config_bytes": 164,
    "config_pointer_slot_count": 3,
    "config_pointer_bytes": 12,
    "classified_range_count": 86,
    "classified_bytes": 816,
    "parse_failure_count": 0,
    "range_overlap_bytes": 0,
    "packed_bytes": 816,
}


class ExportRomSelectorTextBindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_selector_text_bindings import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name).resolve() / SCHEMA
        cls.payload = export_artifact(ROOT, cls.output)
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_only_fixed_source_enumerated_and_config_denominators(self):
        self.assertEqual(EXPECTED_SUMMARY, self.payload["summary"])

        source = self.payload["direct_source_table"]
        self.assertEqual([0x59F5F0, 0x59F988], source["range"])
        self.assertEqual(46, source["record_count"])
        self.assertEqual(20, source["record_size"])
        self.assertEqual(
            EXPECTED_DIRECT_NAME_SLOTS,
            [record["name_slot"] for record in source["records"]],
        )
        self.assertEqual(list(range(46)), [record["source_id"] for record in source["records"]])
        self.assertEqual(46, len(set(EXPECTED_DIRECT_NAME_SLOTS)))

        direct = self.payload["direct_text_candidates"]
        self.assertEqual([0x5A5AB8, 0x5A5F65], direct["physical_range_observed"])
        self.assertEqual(63, direct["physical_slot_count_observed"])
        self.assertFalse(direct["physical_denominator_complete"])
        self.assertEqual(46, len(direct["records"]))
        self.assertEqual(324, sum(record["consumed_size"] for record in direct["records"]))
        self.assertEqual(550, sum(record["unclassified_suffix_size"] for record in direct["records"]))
        self.assertTrue(all(record["consumed_range"][1] <= record["physical_range"][1] for record in direct["records"]))

        configured = self.payload["configured_text_table"]
        self.assertEqual([0x5A5F65, 0x5A6343], configured["physical_range"])
        self.assertEqual(55, configured["physical_slot_count"])
        self.assertEqual(
            list(range(1, 32)) + [39, 46, 50, 51, 52, 53, 54],
            configured["referenced_slot_ids"],
        )
        self.assertEqual(38, len(configured["referenced_records"]))
        self.assertEqual(316, sum(record["consumed_size"] for record in configured["referenced_records"]))
        self.assertFalse(configured["unreferenced_slots_classified"])
        self.assertFalse(configured["nul_suffixes_classified"])

        config = self.payload["config_lists"]
        self.assertEqual([0x5A6344, 0x5A63E8], config["range"])
        self.assertEqual([21, 8, 9], config["record_counts"])
        self.assertEqual(38, len(config["records"]))
        self.assertEqual([0x5A63E8, 0x5A63F4], config["pointer_table"]["range"])
        self.assertEqual(
            [0x5A6344, 0x5A639C, 0x5A63C0],
            [item["file_offset"] for item in config["pointer_table"]["entries"]],
        )
        self.assertFalse(self.payload["scope"]["direct_63_slot_physical_denominator_complete"])
        self.assertFalse(self.payload["scope"]["natural_gameplay_all_records_proven"])

    def test_packs_only_parser_consumed_prefixes_and_fixed_config_structures(self):
        ranges = self.payload["classified_ranges"]
        self.assertEqual(86, len(ranges))
        self.assertEqual(46, sum(item["kind"] == "direct_renderer_text_prefix" for item in ranges))
        self.assertEqual(38, sum(item["kind"] == "configured_copy_text_prefix" for item in ranges))
        self.assertEqual(1, sum(item["kind"] == "selector_configuration_lists" for item in ranges))
        self.assertEqual(1, sum(item["kind"] == "selector_configuration_pointer_table" for item in ranges))
        self.assertTrue(all(left["range"][1] <= right["range"][0] for left, right in zip(ranges, ranges[1:])))

        bundle = (self.output / "selector-text-bytes.bin").read_bytes()
        self.assertEqual(816, len(bundle))
        self.assertEqual(
            "1bc1df2046811a0399226edc53895b3c3359779d9407a6555dc0e7810d11e869",
            hashlib.sha256(bundle).hexdigest(),
        )
        self.assertEqual(
            b"".join(self.rom[start:end] for start, end in (item["range"] for item in ranges)),
            bundle,
        )
        for group in (
            self.payload["direct_text_candidates"]["records"],
            self.payload["configured_text_table"]["referenced_records"],
        ):
            for record in group:
                self.assertIn(record["consumed_range"], [item["range"] for item in ranges])
                suffix_start, suffix_end = record["unclassified_suffix_range"]
                self.assertFalse(any(start < suffix_end and suffix_start < end for start, end in (item["range"] for item in ranges)))
        self.assertFalse(any(start <= 0x5A6343 < end for start, end in (item["range"] for item in ranges)))

    def test_decodes_producer_consumers_and_parser_boundaries(self):
        from tools.export_rom_selector_text_bindings import (
            _decode_consumer_contract,
            _decode_direct_producer_contract,
            _direct_text_records,
            _nul_end,
        )
        from tools.verify_rom_selector_text_bindings import (
            _independent_consumer_contract,
            _independent_direct_producer_contract,
            _independent_direct_text_records,
            _independent_nul_end,
        )

        expected = self.payload["consumer_evidence"]["decoded_semantics"]
        self.assertEqual(expected, _decode_consumer_contract(self.rom))
        self.assertEqual(expected, _independent_consumer_contract(self.rom))
        producer = self.payload["consumer_evidence"]["direct_producer"]
        self.assertEqual(producer, _decode_direct_producer_contract(self.rom))
        self.assertEqual(producer, _independent_direct_producer_contract(self.rom))
        self.assertEqual(46, producer["source_record_count"])
        self.assertEqual([0x8B420, 0x8B51A], producer["direct_consumer_callsites"])

        for parser in (_nul_end, _independent_nul_end):
            self.assertEqual(3, parser(b"ab\x00tail", 0, 7))
            with self.assertRaisesRegex(ValueError, "NUL|terminator"):
                parser(b"abcdef", 0, 6)

        for offset in (0x8B02C, 0x8CD5A, 0x8CC80):
            tampered = bytearray(self.rom)
            tampered[offset] ^= 1
            for decoder in (_decode_consumer_contract, _independent_consumer_contract):
                with self.assertRaisesRegex(ValueError, "selector-text"):
                    decoder(bytes(tampered))

        tampered = bytearray(self.rom)
        tampered[0x8A6F6] ^= 1
        for decoder in (_decode_direct_producer_contract, _independent_direct_producer_contract):
            with self.assertRaisesRegex(ValueError, "selector-text"):
                decoder(bytes(tampered))

        tampered = bytearray(self.rom)
        tampered[0x59F5F1] = 0x3F
        for decoder in (_decode_direct_producer_contract, _independent_direct_producer_contract):
            with self.assertRaisesRegex(ValueError, "selector-text"):
                decoder(bytes(tampered))

        tampered = bytearray(self.rom)
        first_slot = 0x5A5AB8 + 19
        tampered[first_slot : first_slot + 19] = b"A" * 19
        records = self.payload["direct_source_table"]["records"]
        for parser in (_direct_text_records, _independent_direct_text_records):
            with self.assertRaisesRegex(ValueError, "NUL|terminator"):
                parser(bytes(tampered), records)

    def test_export_is_deterministic_and_refuses_unsafe_outputs(self):
        from tools.export_rom_selector_text_bindings import export_artifact

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary).resolve()
            first = temporary_root / "first"
            second = temporary_root / "second"
            export_artifact(ROOT, first)
            export_artifact(ROOT, second)
            export_artifact(ROOT, first)
            hashes = lambda root: {
                path.relative_to(root): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(hashes(first), hashes(second))

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
        from tools.verify_rom_selector_text_bindings import verify_artifact

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(EXPECTED_SUMMARY, report["summary"])

        verifier_source = (ROOT / "tools/verify_rom_selector_text_bindings.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("from tools.export_rom_selector", verifier_source)
        self.assertNotIn("import tools.export_rom_selector", verifier_source)

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "tampered"
            shutil.copytree(self.output, tampered)
            bundle_path = tampered / "selector-text-bytes.bin"
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
