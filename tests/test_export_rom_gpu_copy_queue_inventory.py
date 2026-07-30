import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportRomGpuCopyQueueInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_gpu_copy_queue_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_all_direct_enqueue_callers_and_the_status_one_abi(self):
        self.assertEqual(
            [
                "0x08063168",
                "0x0808812E",
                "0x0808D9C6",
                "0x0808DA0E",
                "0x080962EE",
                "0x080962FE",
                "0x08096536",
                "0x0809655C",
                "0x080965A4",
                "0x08096DBA",
                "0x08096E00",
                "0x08096E44",
                "0x08098B6C",
                "0x08098D90",
            ],
            [caller["callsite"] for caller in self.payload["direct_callers"]],
        )
        self.assertEqual(
            {
                "direct_caller_count": 14,
                "existing_rom_source_caller_count": 5,
                "existing_rom_derived_ram_caller_count": 1,
                "known_ram_source_caller_count": 6,
                "unknown_ram_producer_caller_count": 1,
                "dynamic_unresolved_source_caller_count": 1,
                "new_rom_source_count": 0,
            },
            self.payload["summary"],
        )
        abi = self.payload["queue_abi"]
        self.assertEqual("0x03005BBC", abi["queue_start"])
        self.assertEqual(16, abi["slot_count"])
        self.assertEqual(16, abi["slot_stride"])
        self.assertEqual(
            [
                {"offset": 0, "name": "flags", "type": "u32"},
                {"offset": 4, "name": "source", "type": "u32"},
                {"offset": 8, "name": "destination", "type": "u32"},
                {"offset": 12, "name": "size_bytes", "type": "u16"},
            ],
            abi["status_1_fields"],
        )
        self.assertEqual(
            "CpuSet(source,destination,u16(size_bytes)>>1)",
            abi["status_1_consumer"],
        )

    def test_binds_existing_rom_sources_without_duplicate_exports(self):
        callers = {
            caller["callsite"]: caller for caller in self.payload["direct_callers"]
        }
        self.assertEqual(
            "battle_effect_dynamic_obj_queue_model",
            callers["0x08063168"]["existing_artifact_overlap"]["id"],
        )
        self.assertEqual(
            "dynamic_unresolved_source",
            callers["0x08063168"]["classification"],
        )
        self.assertEqual(
            "menu_ui_palette_records",
            callers["0x080962FE"]["resource_binding"]["id"],
        )
        for callsite in [
            "0x0809655C",
            "0x080965A4",
            "0x08096DBA",
            "0x08096E00",
        ]:
            self.assertEqual(
                "menu_ui_palette_records",
                callers[callsite]["resource_binding"]["id"],
            )
            self.assertEqual(
                "existing_rom_source",
                callers[callsite]["classification"],
            )
        self.assertEqual(
            "menu_ui_graphics_transformed_in_ram",
            callers["0x080962EE"]["resource_binding"]["id"],
        )
        self.assertEqual(
            "existing_rom_derived_ram",
            callers["0x080962EE"]["classification"],
        )
        self.assertEqual(
            "unknown_ram_producer",
            callers["0x08096536"]["classification"],
        )
        self.assertEqual([], self.payload["new_rom_sources"])

    def test_classifications_are_grounded_in_thumb_instruction_evidence(self):
        evidence = self.payload["instruction_evidence"]
        self.assertEqual(
            {
                "table_base": "0x085A4DEC",
                "special_variant": "0x085A4DE4",
                "record_stride": 40,
                "variant_stride": 8,
                "palette_field_offset": 4,
            },
            evidence["menu_pair_selector"],
        )
        self.assertEqual(
            [
                "0x080962FE",
                "0x0809655C",
                "0x080965A4",
                "0x08096DBA",
                "0x08096E00",
            ],
            [row["enqueue_callsite"] for row in evidence["menu_palette_routes"]],
        )
        self.assertTrue(
            all(
                row["selector_target"] == "0x08096138"
                and row["palette_load_offset"] == 4
                and row["size_bytes"] == 128
                for row in evidence["menu_palette_routes"]
            )
        )
        self.assertEqual(
            {
                "source": "stack_arg_6_graphics_work_buffer",
                "lz77_source": "Pair(r1_in,r2_in).gfx_ptr",
                "lz77_target": "0x0809C0EC",
                "enqueue_callsite": "0x080962EE",
                "size_bytes": 6400,
            },
            evidence["menu_graphics_staged_route"],
        )
        self.assertEqual(
            {
                "0x0808812E": "0x02002BC0",
                "0x08096536": "0x02002880",
                "0x08096E44": "0x02002880",
                "0x08098B6C": "0x02002880",
            },
            evidence["fixed_ram_source_literals"],
        )

    def test_scope_does_not_overclaim_indirect_queues_or_all_graphics(self):
        self.assertEqual(
            {
                "queue_status_1_abi_complete": True,
                "queue_status_3_enqueue_shape_complete": True,
                "queue_status_3_lifecycle_complete": False,
                "direct_thumb_bl_callers_complete": True,
                "direct_caller_resource_classification_complete": True,
                "indirect_enqueue_callers_complete": False,
                "runtime_reachability_complete": False,
                "all_async_transfer_queues_complete": False,
                "dialogue_tilemap_submit_complete": False,
                "raw_uncompressed_graphics_complete": False,
                "all_game_visual_states_complete": False,
                "generic_image_writeback_complete": False,
            },
            self.payload["scope"],
        )

    def test_export_is_deterministic_and_refuses_foreign_output(self):
        from tools.export_rom_gpu_copy_queue_inventory import export_artifact

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
        from tools.verify_rom_gpu_copy_queue_inventory import verify_artifact

        source = (
            ROOT / "tools/verify_rom_gpu_copy_queue_inventory.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(14, report["direct_caller_count"])
        self.assertEqual(0, report["new_rom_source_count"])

        mutations = {
            "callsite": lambda payload: payload["direct_callers"][0].update(
                callsite="0x08063166"
            ),
            "source class": lambda payload: payload["direct_callers"][5].update(
                classification="new_rom_source"
            ),
            "queue size": lambda payload: payload["queue_abi"].update(slot_count=15),
            "scope": lambda payload: payload["scope"].update(
                indirect_enqueue_callers_complete=True
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                tampered = Path(tmp) / "artifact"
                shutil.copytree(self.output, tampered)
                payload_path = tampered / "rom-gpu-copy-queue-inventory.json"
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
            payload_path = tampered / "rom-gpu-copy-queue-inventory.json"
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
