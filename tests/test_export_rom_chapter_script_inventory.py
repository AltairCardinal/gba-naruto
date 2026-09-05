from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-chapter-script-inventory-v1"
EXPECTED_SUMMARY = {
    "pointer_table_slot_count": 204,
    "non_null_script_slots": 200,
    "unique_script_roots": 188,
    "unique_instruction_nodes": 18_994,
    "dynamic_opcode_06_nodes": 42,
    "observed_opcode_count": 43,
    "terminal_node_count": 590,
    "parse_failure_count": 0,
    "raw_node_bytes": 334_060,
    "node_overlap_bytes": 0,
    "merged_range_count": 92,
    "merged_range_bytes": 334_060,
    "internal_gap_count": 91,
    "internal_gap_bytes": 3_769,
    "packed_script_bytes": 334_060,
}
SPEAKER_LABEL_IDS = [
    *range(1, 32),
    35,
    36,
    37,
    41,
    *range(43, 55),
    56,
    61,
]


class ExportRomChapterScriptInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_chapter_script_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / SCHEMA
        cls.payload = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_traverses_the_fixed_four_table_denominator_without_parse_failures(self):
        self.assertEqual(EXPECTED_SUMMARY, self.payload["summary"])
        self.assertEqual(
            [
                {
                    "name": "primary",
                    "file_range": [0x60C74, 0x60D54],
                    "gba_range": ["0x08060C74", "0x08060D54"],
                    "entry_count": 56,
                    "null_sentinel_count": 1,
                    "non_null_slot_count": 55,
                    "sha256": "f6c872afd0b653ae2e0e04407bdbc059719eb823801d165e22a1d7e5c98aa099",
                },
                {
                    "name": "alternate",
                    "file_range": [0x60D54, 0x60E34],
                    "gba_range": ["0x08060D54", "0x08060E34"],
                    "entry_count": 56,
                    "null_sentinel_count": 1,
                    "non_null_slot_count": 55,
                    "sha256": "767308a8e78947f7795c61965155d27925265327466c9df9d5d547b2f0368b5c",
                },
                {
                    "name": "runtime_state",
                    "file_range": [0x60E34, 0x60EF0],
                    "gba_range": ["0x08060E34", "0x08060EF0"],
                    "entry_count": 47,
                    "null_sentinel_count": 1,
                    "non_null_slot_count": 46,
                    "sha256": "d0abb00332b73cd36637dbfcf5a7811622438f9c6382dc8c8ff45b00455d00ae",
                },
                {
                    "name": "positions_formation",
                    "file_range": [0x60EF0, 0x60FA4],
                    "gba_range": ["0x08060EF0", "0x08060FA4"],
                    "entry_count": 45,
                    "null_sentinel_count": 1,
                    "non_null_slot_count": 44,
                    "sha256": "d5f04183747f3a68bc9c6e087c89b18a4b71e7a12cf85f6eec589050338594ed",
                },
            ],
            self.payload["pointer_tables"],
        )
        self.assertEqual(43, len(self.payload["observed_opcodes"]))
        self.assertEqual(5_895, self.payload["observed_opcodes"]["0x01"]["nodes"])
        self.assertEqual(286_373, self.payload["observed_opcodes"]["0x01"]["bytes"])

    def test_exports_only_the_exact_merged_ranges_and_a_single_packed_bundle(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        bundle = (self.output / "chapter-script-bytes.bin").read_bytes()
        ranges = self.payload["ranges"]

        self.assertEqual(92, len(ranges))
        self.assertEqual([0x009F2E, 0x00BFC8], ranges[0]["range"])
        self.assertEqual([0x05C5DD, 0x05C6D3], ranges[-1]["range"])
        self.assertEqual(334_060, len(bundle))
        self.assertEqual(
            {"chapter-script-bytes.bin", "chapter-script-inventory.json", "manifest.json"},
            {path.name for path in self.output.iterdir() if path.is_file()},
        )

        packed_cursor = 0
        for record in ranges:
            start, end = record["range"]
            packed_start, packed_end = record["packed_range"]
            self.assertEqual(packed_cursor, packed_start)
            self.assertEqual(end - start, record["size"])
            self.assertEqual(rom[start:end], bundle[packed_start:packed_end])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(),
                record["bytes_sha256"],
            )
            packed_cursor = packed_end
        self.assertEqual(len(bundle), packed_cursor)

    def test_binds_table_selector_interpreter_and_text_boundary_evidence(self):
        evidence = self.payload["consumer_evidence"]
        self.assertEqual(
            {
                "file_range": [0x08F594, 0x08F5D4],
                "gba_range": ["0x0808F594", "0x0808F5D4"],
                "sha256": "0c586c11a8c452e4096d4cf444bb5c75628d099020ff8e5642f99634ea022efd",
            },
            evidence["table_selector"],
        )
        self.assertEqual(
            {
                "file_range": [0x0977B8, 0x097E34],
                "gba_range": ["0x080977B8", "0x08097E34"],
                "dispatch_table_range": [0x0977F4, 0x0978DC],
                "dispatch_table_sha256": "a3d2eb7489c851b040b87afeb6c2a020e15e5b6d9086c57f036be4893b12792d",
                "sha256": "1e0c0550c08d7bbdd3395085112ccc864caffbd10db9d840a86294454f6cd249",
            },
            evidence["interpreter"],
        )
        self.assertEqual(
            "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1",
            evidence["sjis_range_table"]["sha256"],
        )
        self.assertEqual(
            [
                {
                    "name": "runtime_state",
                    "function_range": [0x08A534, 0x08A588],
                    "function_sha256": "2eebdb3fecb96d74024180c6c3ff764d9ed0af2a25860a985f714cc9da8d57ad",
                    "table_literal_offset": 0x08A578,
                    "lookup_range": [0x08A55C, 0x08A564],
                    "lookup_sha256": "200db68d2ac056a78c92cfc0632cb954c1b93e3fbb2d4dce158df31ca9ad2ef0",
                    "interpreter_call_offset": 0x08A566,
                    "typed_script_slot_count": 46,
                    "runtime_index_evidence": "47-entry structural domain 0..46; runtime maximum is not statically bounded",
                    "runtime_index_domain_complete": False,
                },
                {
                    "name": "positions_formation",
                    "function_range": [0x08A588, 0x08A630],
                    "function_sha256": "316b38ca78b84f67eb88df86531dbdc5e179b031067692acbdcd6372d0d195e0",
                    "table_literal_offset": 0x08A5E4,
                    "lookup_range": [0x08A5CE, 0x08A5D6],
                    "lookup_sha256": "d352f62a2053c30c684ca055c5c5d77a34d05f6192f0c5b7b1f6b84a09d118b1",
                    "interpreter_call_offset": 0x08A5FC,
                    "typed_script_slot_count": 44,
                    "runtime_index_evidence": "positions headers enumerate indices {0,6,8,10,11,12,14}",
                    "runtime_index_domain_complete": False,
                },
            ],
            evidence["auxiliary_table_consumers"],
        )
        self.assertEqual(
            [
                "Only records statically reachable from the 200 non-null slots in the four fixed-ROM interpreter pointer tables are classified; internal gaps and bytes outside the reachable union remain unknown.",
                "Merged ranges contain bytecode records and their interpreter-consumed inline text or pointer operands; they are not asserted to be natural-language decoded text.",
                "Opcode 0x06 has no runtime bounds check; the fixed-ROM corpus proves only its two in-record pointer branches.",
                "All non-null auxiliary slots are structurally typed by direct table-lookup-to-interpreter consumers; this does not assert every auxiliary index or chapter root is reached during natural gameplay.",
            ],
            self.payload["limitations"],
        )

    def test_tracks_only_renderer_consumed_speaker_label_bytes(self):
        labels = self.payload["referenced_resources"]["speaker_labels"]
        self.assertEqual(
            {
                "reference_node_counts": {"0x08": 5_701, "0x0E": 7},
                "operand_reference_count": 5_715,
                "referenced_label_ids": SPEAKER_LABEL_IDS,
                "structural_record_count": 49,
                "structural_record_bytes": 588,
                "renderer_consumed_record_count": 49,
                "renderer_consumed_bytes": 251,
                "post_nul_padding_bytes": 337,
                "renderer_length_distribution": {"3": 9, "5": 28, "7": 12},
                "semantic_range_denominator_sha256": "118e9d300bded69407cfe4fe7a8625654af6532ba5a4da3058ca8542fa5e1779",
                "semantic_bundle_sha256": "07c5281f03633aea88c4b70a4a0f755da92707aa2ab6e1a205a20252f8e78831",
            },
            labels["summary"],
        )
        self.assertEqual(
            {
                "dispatch_entries": [
                    {
                        "opcode": "0x08",
                        "entry_offset": 0x097814,
                        "handler_address": "0x080979E8",
                    },
                    {
                        "opcode": "0x0E",
                        "entry_offset": 0x09782C,
                        "handler_address": "0x080979E8",
                    },
                ],
                "handler_address": "0x080979E8",
                "formula_range": [0x097A0A, 0x097A38],
                "formula_sha256": "69b08531ec43f96019787e6b559f50cebe585200224f85a7137e564187d60226",
                "record_base_literal_offset": 0x097A40,
                "record_base_address": "0x085A57C4",
                "record_stride": 12,
                "renderer_address": "0x0806626C",
            },
            labels["consumer_evidence"],
        )
        self.assertEqual(49, len(labels["records"]))
        self.assertEqual(
            {
                "label_id": 1,
                "slot_range": [0x5A57D0, 0x5A57DC],
                "renderer_range": [0x5A57D0, 0x5A57D5],
                "gba_renderer_range": ["0x085A57D0", "0x085A57D5"],
                "size": 5,
                "bytes_sha256": "4c35d13dd4a28dc03c6a5c15abe1e9a706af8141358000e7015fb6ded4b2706a",
            },
            labels["records"][0],
        )
        self.assertEqual(61, labels["records"][-1]["label_id"])
        self.assertEqual([0x5A5AA0, 0x5A5AA3], labels["records"][-1]["renderer_range"])
        self.assertFalse(labels["scope"]["natural_gameplay_reference_coverage_complete"])

    def test_export_is_deterministic_and_refuses_foreign_output(self):
        from tools.export_rom_chapter_script_inventory import export_artifact

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

    def test_independent_verifier_rewalks_nodes_and_rejects_rehashed_tamper(self):
        from tools.verify_rom_chapter_script_inventory import verify_artifact

        verifier_source = (
            ROOT / "tools/verify_rom_chapter_script_inventory.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_rom_chapter_script_inventory", verifier_source
        )
        self.assertNotIn(
            "import tools.export_rom_chapter_script_inventory", verifier_source
        )
        self.assertIn("def _walk_scripts(", verifier_source)
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(
            EXPECTED_SUMMARY,
            {key: report[key] for key in EXPECTED_SUMMARY},
        )

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / SCHEMA
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "chapter-script-inventory.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["ranges"][0]["range"][1] -= 1
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

    def test_independent_verifier_rejects_rehashed_bundle_tamper(self):
        from tools.verify_rom_chapter_script_inventory import verify_artifact

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / SCHEMA
            shutil.copytree(self.output, tampered)
            bundle_path = tampered / "chapter-script-bytes.bin"
            raw = bytearray(bundle_path.read_bytes())
            raw[len(raw) // 2] ^= 1
            bundle_path.write_bytes(raw)
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][bundle_path.name] = hashlib.sha256(raw).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])


if __name__ == "__main__":
    unittest.main()
