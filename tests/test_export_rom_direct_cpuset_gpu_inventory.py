import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEW_SOURCES = {
    "0x083F1E60": ("0x0808BC06", "0x05000120"),
    "0x083F1F08": ("0x0808BC26", "0x05000140"),
    "0x08406010": ("0x0808C260", "0x05000200"),
}


class ExportRomDirectCpusetGpuInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_direct_cpuset_gpu_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_the_direct_call_denominator(self):
        self.assertEqual(
            {
                "direct_call_count": 146,
                "cpuset_call_count": 126,
                "cpufastset_call_count": 20,
                "constant_rom_gpu_operation_count": 23,
                "not_proven_in_window_call_count": 123,
                "pram_operation_count": 23,
                "vram_operation_count": 0,
                "already_bound_operation_count": 20,
                "new_operation_count": 3,
                "unique_source_count": 15,
                "already_bound_source_count": 12,
                "new_source_count": 3,
                "lz77_overlap_operation_count": 1,
                "new_bundle_size": 96,
            },
            self.payload["summary"],
        )
        self.assertEqual(146, len(self.payload["direct_calls"]))
        self.assertEqual(
            23,
            sum(
                call["status"] == "constant_rom_gpu"
                for call in self.payload["direct_calls"]
            ),
        )
        self.assertEqual(
            123,
            sum(
                call["status"] == "not_proven_in_window"
                for call in self.payload["direct_calls"]
            ),
        )

    def test_exports_only_the_three_new_raw_palette_sources(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        bundle = (self.output / "new-raw-sources.bin").read_bytes()
        self.assertEqual(96, len(bundle))
        self.assertEqual(NEW_SOURCES, {
            item["source_address"]: (
                item["operations"][0]["callsite"],
                item["operations"][0]["destination"],
            )
            for item in self.payload["new_sources"]
        })
        cursor = 0
        for item in self.payload["new_sources"]:
            self.assertEqual(cursor, item["bundle_offset"])
            self.assertEqual(32, item["size"])
            offset = int(item["source_address"], 16) - 0x08000000
            expected = rom[offset : offset + 32]
            self.assertEqual(expected, bundle[cursor : cursor + 32])
            self.assertEqual(item["sha256"], hashlib.sha256(expected).hexdigest())
            cursor += 32

    def test_preserves_existing_bindings_and_lz77_overlap(self):
        self.assertEqual(20, len(self.payload["already_bound_operations"]))
        overlap = [
            operation
            for operation in self.payload["constant_rom_gpu_operations"]
            if operation["lz77_overlaps"]
        ]
        self.assertEqual(1, len(overlap))
        self.assertEqual("0x0808BFF4", overlap[0]["callsite"])
        self.assertEqual("0x08405FF0", overlap[0]["source_address"])
        self.assertEqual(256, overlap[0]["copy_size"])
        self.assertEqual(
            ["0x084060A8"],
            [item["source_address"] for item in overlap[0]["lz77_overlaps"]],
        )
        self.assertTrue(overlap[0]["already_bound"])

    def test_scope_does_not_promote_direct_calls_to_all_raw_graphics(self):
        self.assertEqual(
            {
                "all_static_direct_bl_encodings_audited": True,
                "literal_seeded_32_byte_rule_applied_to_full_rom": True,
                "new_raw_sources_losslessly_exported": True,
                "runtime_reachability_complete": False,
                "indirect_calls_complete": False,
                "cross_function_dataflow_complete": False,
                "dma_transfers_complete": False,
                "custom_copy_loops_complete": False,
                "raw_uncompressed_graphics_complete": False,
                "raw_palettes_complete": False,
                "generic_image_writeback_complete": False,
            },
            self.payload["scope"],
        )

    def test_export_is_deterministic_and_refuses_foreign_output(self):
        from tools.export_rom_direct_cpuset_gpu_inventory import export_artifact

        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            export_artifact(ROOT, first)
            export_artifact(ROOT, second)
            self.assertEqual(
                {
                    path.relative_to(first): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in first.rglob("*")
                    if path.is_file()
                },
                {
                    path.relative_to(second): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in second.rglob("*")
                    if path.is_file()
                },
            )
            foreign = Path(tmp) / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "foreign"):
                export_artifact(ROOT, foreign)

    def test_independent_verifier_accepts_and_rejects_tamper(self):
        from tools.verify_rom_direct_cpuset_gpu_inventory import verify_artifact

        source = (
            ROOT / "tools/verify_rom_direct_cpuset_gpu_inventory.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)
        self.assertNotIn("def _rebuild(", source)
        self.assertNotIn("def _scan_literal_user(", source)
        self.assertIn("def _resolve_call_inputs_backward(", source)
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(146, report["direct_call_count"])
        self.assertEqual(3, report["new_source_count"])

        mutations = {
            "source address": lambda payload: payload["new_sources"][0].update(
                source_address="0x083F1E62"
            ),
            "scope": lambda payload: payload["scope"].update(
                dma_transfers_complete=True
            ),
            "control": lambda payload: payload[
                "constant_rom_gpu_operations"
            ][0].update(control="0x00000011"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                tampered = Path(tmp) / "artifact"
                shutil.copytree(self.output, tampered)
                payload_path = (
                    tampered / "rom-direct-cpuset-gpu-inventory.json"
                )
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
                mutate(payload)
                payload_path.write_text(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                manifest_path = tampered / "manifest.json"
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )
                manifest["files"][payload_path.name] = hashlib.sha256(
                    payload_path.read_bytes()
                ).hexdigest()
                manifest_path.write_text(
                    json.dumps(
                        manifest,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                rejected = verify_artifact(ROOT, tampered)
                self.assertFalse(rejected["verified"])
                self.assertTrue(rejected["errors"])

    def test_independent_verifier_rejects_rehashed_bundle_tamper(self):
        from tools.verify_rom_direct_cpuset_gpu_inventory import verify_artifact

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            bundle_path = tampered / "new-raw-sources.bin"
            bundle = bytearray(bundle_path.read_bytes())
            bundle[32] ^= 1
            bundle_path.write_bytes(bundle)

            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][bundle_path.name] = hashlib.sha256(bundle).hexdigest()
            manifest_path.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])


if __name__ == "__main__":
    unittest.main()
