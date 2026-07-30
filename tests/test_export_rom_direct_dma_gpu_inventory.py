import hashlib
import json
import shutil
import struct
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportRomDirectDmaGpuInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_direct_dma_gpu_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_the_direct_dma_literal_user_denominator(self):
        self.assertEqual(
            {
                "dma_register_literal_user_count": 21,
                "dma0_literal_user_count": 2,
                "dma1_literal_user_count": 7,
                "dma2_literal_user_count": 2,
                "dma3_literal_user_count": 10,
                "constant_rom_gpu_transfer_count": 0,
                "not_proven_in_window_count": 21,
                "new_source_count": 0,
            },
            self.payload["summary"],
        )
        self.assertEqual(21, len(self.payload["literal_users"]))
        self.assertTrue(
            all(
                row["status"] == "not_proven_in_window"
                for row in self.payload["literal_users"]
            )
        )

    def test_preserves_register_addresses_and_representative_negative_routes(self):
        users = {
            row["instruction_address"]: row
            for row in self.payload["literal_users"]
        }
        self.assertEqual("0x040000D4", users["0x080611CA"]["literal_value"])
        self.assertEqual("DMA3", users["0x080611CA"]["dma_channel"])
        self.assertEqual("0x040000D4", users["0x08061628"]["literal_value"])
        self.assertEqual("0x040000B0", users["0x080645C2"]["literal_value"])
        self.assertEqual(
            {
                "source_not_rom",
                "destination_not_gpu",
                "no_complete_transfer",
                "control_not_proven",
            },
            set(self.payload["rejection_reason_counts"]),
        )

    def test_recognizes_split_halfword_count_and_control_writes(self):
        from tools.export_rom_direct_dma_gpu_inventory import _scan_user

        rom = bytearray(0x1000)
        instructions = (
            0x4807,  # ldr r0, [pc, #0x1c] -> source @ 0x20
            0x4908,  # ldr r1, [pc, #0x20] -> destination @ 0x24
            0x4A08,  # ldr r2, [pc, #0x20] -> DMA0 base @ 0x28
            0x6010,  # str r0, [r2]
            0x6051,  # str r1, [r2, #4]
            0x2310,  # movs r3, #0x10
            0x8113,  # strh r3, [r2, #8] -> count
            0x4B07,  # ldr r3, [pc, #0x1c] -> CNT_H @ 0x2c
            0x8153,  # strh r3, [r2, #10] -> enable
            0x4770,  # bx lr
        )
        struct.pack_into("<10H", rom, 0, *instructions)
        struct.pack_into(
            "<4I",
            rom,
            0x20,
            0x08000100,
            0x06000000,
            0x040000B0,
            0x00008400,
        )

        transfers, reasons = _scan_user(bytes(rom), 0)

        self.assertEqual(
            [
                {
                    "control_write": "0x08000010",
                    "dma_channel": "DMA0",
                    "source": "0x08000100",
                    "destination": "0x06000000",
                    "control": "0x84000010",
                }
            ],
            transfers,
        )
        self.assertEqual([], reasons)

    def test_scope_does_not_promote_literal_users_to_all_dma_or_raw_graphics(self):
        self.assertEqual(
            {
                "all_thumb_shaped_dma_register_literal_users_audited": True,
                "literal_seeded_96_byte_rule_applied_to_full_rom": True,
                "runtime_reachability_complete": False,
                "non_literal_dma_base_derivations_complete": False,
                "cross_function_dataflow_complete": False,
                "indirect_dma_wrappers_complete": False,
                "custom_copy_loops_complete": False,
                "two_stage_copies_complete": False,
                "raw_uncompressed_graphics_complete": False,
                "generic_image_writeback_complete": False,
            },
            self.payload["scope"],
        )

    def test_export_is_deterministic_and_refuses_foreign_output(self):
        from tools.export_rom_direct_dma_gpu_inventory import export_artifact

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

    def test_independent_verifier_accepts_and_rejects_rehashed_tamper(self):
        from tools.verify_rom_direct_dma_gpu_inventory import verify_artifact

        source = (
            ROOT / "tools/verify_rom_direct_dma_gpu_inventory.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(21, report["dma_register_literal_user_count"])
        self.assertEqual(0, report["constant_rom_gpu_transfer_count"])

        mutations = {
            "literal value": lambda payload: payload["literal_users"][0].update(
                literal_value="0x040000D0"
            ),
            "scope": lambda payload: payload["scope"].update(
                cross_function_dataflow_complete=True
            ),
            "status": lambda payload: payload["literal_users"][0].update(
                status="constant_rom_gpu"
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                tampered = Path(tmp) / "artifact"
                shutil.copytree(self.output, tampered)
                payload_path = tampered / "rom-direct-dma-gpu-inventory.json"
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


if __name__ == "__main__":
    unittest.main()
