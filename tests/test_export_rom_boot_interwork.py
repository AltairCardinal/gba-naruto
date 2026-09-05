from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-boot-interwork-v1"
EXPECTED_SUMMARY = {
    "root_count": 1,
    "closed_root_count": 1,
    "producer_instruction_count": 3,
    "producer_instruction_bytes": 10,
    "arm_instruction_count": 92,
    "arm_instruction_bytes": 368,
    "basic_block_count": 8,
    "edge_count": 10,
    "frontier_count": 0,
    "literal_binding_count": 9,
    "literal_pool_bytes": 36,
    "coverage_claim_count": 5,
    "classified_bytes": 414,
    "range_overlap_bytes": 0,
}


class ExportRomBootInterworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_boot_interwork import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name).resolve() / SCHEMA
        cls.payload = export_artifact(ROOT, cls.output)
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_fixed_interwork_producer_proves_one_closed_arm_root(self):
        payload = self.payload
        self.assertEqual(SCHEMA, payload["schema"])
        self.assertEqual(EXPECTED_SUMMARY, payload["summary"])
        self.assertEqual(
            {
                "root_id": "root-arm-00024c",
                "mode": "arm",
                "file_offset": 0x24C,
                "gba_address": "0x0800024C",
                "entry_size": 4,
                "entry_sha256": "8a04c2e346e7375c2cf164f2b0e91ba8c325ffdd38c50e62ec922b266aa6c4dd",
                "traversal_status": "closed",
                "reachable_instruction_count": 92,
                "reachable_instruction_bytes": 368,
                "reachable_block_count": 8,
                "frontier_count": 0,
            },
            payload["root"],
        )
        spine = payload["producer_chain"]["interwork_spine"]
        self.assertEqual(
            [
                [0x061086, 0x06108A],
                [0x09C56C, 0x09C56E],
                [0x09C570, 0x09C574],
            ],
            [item["range"] for item in spine],
        )
        self.assertEqual(
            ["thumb_bl", "thumb_bx_pc", "arm_b"],
            [item["kind"] for item in spine],
        )
        self.assertEqual("0x0809C56C", spine[0]["target"])
        self.assertEqual("0x0809C570", spine[1]["target"])
        self.assertEqual("0x0800024C", spine[2]["target"])
        self.assertEqual([0x09C56E, 0x09C570], payload["producer_chain"]["skipped_padding_range"])
        self.assertEqual("0x0800026C", payload["producer_chain"]["excluded_sibling"]["target"])
        self.assertFalse(payload["scope"]["runtime_reachability_complete"])
        self.assertFalse(payload["scope"]["reset_to_root_path_complete"])

    def test_rebuilds_exact_armv4t_blocks_edges_and_literals(self):
        blocks = self.payload["blocks"]
        self.assertEqual(
            [
                ([0x24C, 0x294], 18, "123c770a668e6b87544ed2fc9f36fa1041a1d47c0c4f29ba928f8e6a2d3da94e"),
                ([0x294, 0x328], 37, "1e524d95806cd937ff1d584da9cd9ed1cf8390972c2ca31f9d5aef66888dfd7e"),
                ([0x328, 0x32C], 1, "c402c7ed1b0cac28463ca441dd5574cba9696725ae979ce47d0b71d0dab45da2"),
                ([0x32C, 0x340], 5, "2b4f130de6415bf8acb6a2c7a469ca2c601052c2c9cb4712f81811cd3f52b520"),
                ([0x340, 0x34C], 3, "1a972be8ec46452326d2110ffba4b7f0060fd000051b1963b9058aba729794e0"),
                ([0x34C, 0x35C], 4, "fa989bd3ac9a381c64256ab842a5608c0b7099f5770028f089d0f5eb3946a8ef"),
                ([0x35C, 0x3A8], 19, "9f8d955826095ddba631e62378b39e3bf5a5e40f996e637789e08dc7dc0beeaf"),
                ([0x3A8, 0x3BC], 5, "ea608c8186d4d96305bb37df4131edb195646868103b578c209328e2da9317a1"),
            ],
            [(item["range"], item["instruction_count"], item["bytes_sha256"]) for item in blocks],
        )
        self.assertEqual(10, len(self.payload["edges"]))
        self.assertEqual(
            [0x3BC, 0x3C0, 0x3C4, 0x3C8, 0x3CC, 0x3D0, 0x3D4, 0x3D8, 0x3DC],
            [item["literal_offset"] for item in self.payload["literal_bindings"]],
        )
        self.assertEqual(
            [
                "0x03000D18",
                "0x03000A88",
                "0x03002E1C",
                "0x03002E20",
                "0x03000D18",
                "0x03000A84",
                "0xFFFFFFFF",
                "0x03002E20",
                "0x03002E1C",
            ],
            [item["value"] for item in self.payload["literal_bindings"]],
        )
        denominators = self.payload["denominators"]
        self.assertEqual(
            "c25c738607397cb60f90d73d7a6efe079ef52c89c11f787b0cc7d896101beebf",
            denominators["instruction_vector_sha256"],
        )
        self.assertEqual(
            "1c9d08d16c2f4c3b5cdb4123d8ae94b6fd3bb4f7921c9a28a55b77f279c3af50",
            denominators["block_vector_sha256"],
        )
        self.assertEqual(
            "ba298a7c1f9f7811e7dd2ac899c7faa42d013599d9e94a6c41e129b34e7176e7",
            denominators["edge_vector_sha256"],
        )
        self.assertEqual(
            "1e812f886d0e0abe614780f0c4a94af1c789831fd966c59e85e0a6ef690f4e9f",
            denominators["literal_binding_vector_sha256"],
        )

    def test_claims_only_414_proven_bytes_and_keeps_skipped_padding_unknown(self):
        claims = self.payload["coverage_claims"]
        self.assertEqual(
            [
                [0x00024C, 0x0003BC],
                [0x0003BC, 0x0003E0],
                [0x061086, 0x06108A],
                [0x09C56C, 0x09C56E],
                [0x09C570, 0x09C574],
            ],
            [item["range"] for item in claims],
        )
        self.assertEqual(414, sum(item["size"] for item in claims))
        self.assertFalse(any(start <= 0x09C56E and end >= 0x09C570 for start, end in (item["range"] for item in claims)))
        self.assertFalse(any(end > 0x3E0 for start, end in (item["range"] for item in claims) if start < 0x3E0))
        self.assertTrue(self.payload["scope"]["fixed_interwork_spine_verified"])
        self.assertTrue(self.payload["scope"]["arm_root_static_cfg_closed"])
        self.assertFalse(self.payload["scope"]["surrounding_40k_region_classified"])
        self.assertFalse(self.payload["scope"]["ram_targets_classified_as_code"])

    def test_export_is_deterministic_and_refuses_unsafe_outputs(self):
        from tools.export_rom_boot_interwork import export_artifact

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
        from tools.verify_rom_boot_interwork import verify_artifact

        for artifact in (self.output, ROOT / "artifacts" / SCHEMA):
            report = verify_artifact(ROOT, artifact)
            self.assertTrue(report["verified"], report["errors"])
            self.assertEqual(EXPECTED_SUMMARY, report["summary"])

        verifier_source = (ROOT / "tools/verify_rom_boot_interwork.py").read_text(encoding="utf-8")
        self.assertNotIn("from tools.export_rom_boot_interwork", verifier_source)
        self.assertNotIn("import tools.export_rom_boot_interwork", verifier_source)

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "tampered"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "rom-boot-interwork.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["scope"]["runtime_reachability_complete"] = True
            payload_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][payload_path.name]["size"] = payload_path.stat().st_size
            manifest["files"][payload_path.name]["sha256"] = hashlib.sha256(payload_path.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verify_artifact(ROOT, tampered)["verified"])

    def test_verifier_rejects_mismatched_loaded_project_root(self):
        from tools.verify_rom_boot_interwork import verify_artifact

        with tempfile.TemporaryDirectory() as other_root:
            report = verify_artifact(Path(other_root), self.output)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("loaded project root" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
