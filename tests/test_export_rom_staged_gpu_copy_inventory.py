import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportRomStagedGpuCopyInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_staged_gpu_copy_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_the_hash_bound_staged_consumer_denominator(self):
        self.assertEqual(
            {
                "consumer_family_count": 3,
                "staged_ram_slot_count": 5,
                "gpu_copy_route_count": 6,
                "metadata_excluded_family_count": 1,
                "procedural_excluded_family_count": 2,
                "accepted_raw_source_count": 0,
                "new_raw_source_count": 0,
            },
            self.payload["summary"],
        )
        self.assertEqual(
            [
                "oam_shadow_submit_v1",
                "overview_generated_bg0_v1",
                "battle_status_bar_dynamic_bg_v1",
            ],
            [family["id"] for family in self.payload["consumer_families"]],
        )

    def test_records_only_code_proven_slots_and_excludes_false_raw_sources(self):
        families = {
            family["id"]: family
            for family in self.payload["consumer_families"]
        }
        oam = families["oam_shadow_submit_v1"]
        self.assertEqual("metadata_excluded", oam["classification"])
        self.assertEqual("0x0300027C", oam["ram_slots"][0]["start"])
        self.assertEqual(1024, oam["ram_slots"][0]["size"])
        self.assertEqual(
            ["0x08061346", "0x08061386"],
            [route["callsite"] for route in oam["gpu_copy_routes"]],
        )

        overview = families["overview_generated_bg0_v1"]
        self.assertEqual("procedural_excluded", overview["classification"])
        self.assertEqual(
            [352, 32, 1200],
            [slot["size"] for slot in overview["ram_slots"]],
        )
        self.assertEqual(
            ["0x06002000", "0x050001A0", "0x06000000"],
            [route["destination"] for route in overview["gpu_copy_routes"]],
        )

        bars = families["battle_status_bar_dynamic_bg_v1"]
        self.assertEqual("procedural_excluded", bars["classification"])
        self.assertEqual(160, bars["ram_slots"][0]["size"])
        self.assertEqual(
            "dynamic_bg_vram",
            bars["gpu_copy_routes"][0]["destination_kind"],
        )
        self.assertTrue(
            all(not family["accepted_as_raw_rom_source"] for family in families.values())
        )
        serialized = json.dumps(self.payload["consumer_families"], sort_keys=True)
        self.assertNotIn("source_address", serialized)
        self.assertNotIn("bundle_offset", serialized)
        self.assertNotIn("dialogue", serialized)

    def test_scope_is_explicitly_limited_to_the_allowlisted_consumers(self):
        self.assertEqual(
            {
                "hash_bound_allowlisted_consumer_families_complete": True,
                "allowlisted_ram_slots_classified": True,
                "procedural_and_metadata_false_sources_excluded": True,
                "all_rom_to_ram_producers_complete": False,
                "all_ram_to_gpu_consumers_complete": False,
                "indirect_transfer_queue_abi_complete": False,
                "dialogue_tilemap_submit_complete": False,
                "custom_copy_loops_complete": False,
                "all_two_stage_copies_complete": False,
                "raw_uncompressed_graphics_complete": False,
                "generic_image_writeback_complete": False,
            },
            self.payload["scope"],
        )

    def test_export_is_deterministic_and_refuses_foreign_output(self):
        from tools.export_rom_staged_gpu_copy_inventory import export_artifact

        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
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
            foreign = Path(tmp) / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "foreign"):
                export_artifact(ROOT, foreign)

    def test_independent_verifier_rejects_rehashed_semantic_tamper(self):
        from tools.verify_rom_staged_gpu_copy_inventory import verify_artifact

        source = (
            ROOT / "tools/verify_rom_staged_gpu_copy_inventory.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(3, report["consumer_family_count"])
        self.assertEqual(0, report["accepted_raw_source_count"])

        mutations = {
            "slot": lambda payload: payload["consumer_families"][0]["ram_slots"][
                0
            ].update(start="0x03000280"),
            "classification": lambda payload: payload["consumer_families"][1].update(
                classification="raw_rom_source"
            ),
            "route size": lambda payload: payload["consumer_families"][1][
                "gpu_copy_routes"
            ][0].update(size=320),
            "scope": lambda payload: payload["scope"].update(
                all_two_stage_copies_complete=True
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                tampered = Path(tmp) / "artifact"
                shutil.copytree(self.output, tampered)
                payload_path = tampered / "rom-staged-gpu-copy-inventory.json"
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
                mutate(payload)
                payload_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                manifest_path = tampered / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["files"][payload_path.name] = hashlib.sha256(
                    payload_path.read_bytes()
                ).hexdigest()
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                rejected = verify_artifact(ROOT, tampered)
                self.assertFalse(rejected["verified"])
                self.assertTrue(rejected["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            (tampered / "extra.bin").write_bytes(b"foreign")
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "rom-staged-gpu-copy-inventory.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][payload_path.name] = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
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
