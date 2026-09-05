#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image

from tools.export_rom_boot_framebuffers import (
    _validate_output_dir,
    export_rom_boot_framebuffers,
)
from tools.verify_rom_boot_framebuffers import (
    analyze_arm_display_routine,
    analyze_arm_startup_chain,
    verify_rom_boot_framebuffers,
)


ROOT = Path(__file__).resolve().parents[1]


class RomBootFramebufferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.artifact_dir = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_rom_boot_framebuffers(ROOT, cls.artifact_dir)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_exports_two_exact_mode3_bgr555_framebuffers_and_code_boundaries(self):
        manifest = self.manifest
        self.assertEqual("rom-boot-framebuffers-v1", manifest["schema"])
        self.assertEqual(155_188, manifest["summary"]["byte_count"])
        self.assertEqual(14, manifest["summary"]["claim_count"])
        self.assertEqual(584, manifest["summary"]["startup_byte_count"])
        self.assertEqual(7, manifest["summary"]["startup_claim_count"])
        self.assertEqual(2, manifest["summary"]["framebuffer_count"])
        self.assertEqual(38_400, manifest["summary"]["pixels_per_framebuffer"])
        self.assertEqual(
            [
                [0x000000, 0x000004],
                [0x000004, 0x0000C0],
                [0x0000C0, 0x0000C4],
                [0x0000C8, 0x0000F4],
                [0x0000F4, 0x000104],
                [0x000104, 0x000244],
                [0x000244, 0x00024C],
                [0x5BA000, 0x5CCC00],
                [0x5CCC00, 0x5CCD40],
                [0x5CCD40, 0x5CCDEC],
                [0x5CCDEC, 0x5CCE00],
                [0x5CCE00, 0x5DFA00],
                [0x5DFA00, 0x5DFB40],
                [0x5DFB40, 0x5DFBEC],
            ],
            [item["range"] for item in manifest["claims"]],
        )
        self.assertEqual(
            [
                "arm_code",
                "gba_header",
                "arm_code",
                "arm_code",
                "literal_pool",
                "arm_code",
                "literal_pool",
                "boot_mode3_framebuffer_bgr555",
                "arm_code",
                "literal_pool",
                "alignment_ff",
                "boot_mode3_framebuffer_bgr555",
                "arm_code",
                "literal_pool",
            ],
            [item["semantic_class"] for item in manifest["claims"]],
        )

        for framebuffer in manifest["framebuffers"]:
            self.assertEqual("mode3_bgr555_le", framebuffer["pixel_storage"])
            self.assertEqual([240, 160], framebuffer["dimensions"])
            self.assertEqual(76_800, framebuffer["size"])
            self.assertTrue(framebuffer["all_bit15_clear"])
            self.assertEqual(38_400, framebuffer["pixel_count"])
            self.assertEqual(
                76_800,
                (self.artifact_dir / framebuffer["source_bin"]).stat().st_size,
            )
            with Image.open(self.artifact_dir / framebuffer["preview_png"]) as image:
                image.load()
                self.assertEqual("RGB", image.mode)
                self.assertEqual((240, 160), image.size)

    def test_startup_chain_binds_header_bootstrap_literals_and_irq_callback(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        facts = analyze_arm_startup_chain(rom)

        self.assertEqual("NARUTOKONOHA", facts["header"]["title"])
        self.assertEqual("AUEJ", facts["header"]["game_code"])
        self.assertEqual("DA", facts["header"]["maker_code"])
        self.assertTrue(facts["header"]["complement_check_valid"])
        self.assertEqual("0x080000C0", facts["reset_vector"]["target"])
        self.assertEqual("0x085CCC04", facts["display_handoff"]["target"])
        self.assertEqual("0x03007FFC", facts["irq_install"]["slot"])
        self.assertEqual("0x08000104", facts["irq_install"]["callback"])
        self.assertEqual("0x08060FAD", facts["thumb_handoff"]["target"])
        self.assertEqual([0xC4, 0xC8], facts["unclaimed_gap"])
        self.assertEqual("0x08000240", facts["irq_callback"]["return_instruction"])

    def test_static_arm_chain_proves_dma_mode3_and_blend_register_identity(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        first = analyze_arm_display_routine(
            rom,
            0x5CCC00,
            source_offset=0x5BA000,
            terminal_target=0x085DFA00,
        )
        second = analyze_arm_display_routine(
            rom,
            0x5DFA00,
            source_offset=0x5CCE00,
            terminal_target=0x080000C8,
        )

        for facts in (first, second):
            self.assertEqual("DMA3", facts["dma"]["channel"])
            self.assertEqual("0x06000000", facts["dma"]["destination"])
            self.assertEqual("0x84004B00", facts["dma"]["control"])
            self.assertEqual(76_800, facts["dma"]["byte_count"])
            self.assertEqual("0x04000000", facts["display"]["register"])
            self.assertEqual("0x00000403", facts["display"]["value"])
            self.assertEqual("mode3_bgr555_bg2", facts["display"]["decoded"])
            self.assertEqual("0x04000050", facts["blend"]["register"])
            self.assertEqual(
                ["0x000004C4", "0x00000484"],
                facts["blend"]["values"],
            )
        self.assertEqual("0x085BA000", first["dma"]["source"])
        self.assertEqual("0x085CCE00", second["dma"]["source"])

    def test_rejects_mode3_literal_changed_to_a_different_display_mode(self):
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0x5CCC00 + 0x17C : 0x5CCC00 + 0x180] = (0x404).to_bytes(
            4, "little"
        )

        with self.assertRaisesRegex(ValueError, "DISPCNT"):
            analyze_arm_display_routine(
                bytes(rom),
                0x5CCC00,
                source_offset=0x5BA000,
                terminal_target=0x085DFA00,
            )

    def test_independent_verifier_rebuilds_every_file_and_semantic_fact(self):
        report = verify_rom_boot_framebuffers(ROOT, self.artifact_dir)

        self.assertEqual(
            {
                "schema": "rom-boot-framebuffers-verification-v1",
                "verified": True,
                "claim_count": 14,
                "byte_count": 155_188,
                "startup_claim_count": 7,
                "startup_byte_count": 584,
                "framebuffer_count": 2,
                "arm_routine_count": 2,
                "errors": [],
            },
            report,
        )

    def test_output_validator_refuses_repository_and_foreign_directory(self):
        with self.assertRaisesRegex(ValueError, "repository root or ancestor"):
            _validate_output_dir(ROOT, ROOT)
        with self.assertRaisesRegex(ValueError, "repository root or ancestor"):
            _validate_output_dir(ROOT, ROOT.parent)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "foreign"
            output.mkdir()
            keep = output / "keep.txt"
            keep.write_text("user data\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "replaceable boot artifact"):
                _validate_output_dir(ROOT, output)
            self.assertEqual("user data\n", keep.read_text(encoding="utf-8"))

    def test_exporter_refuses_repository_before_writing(self):
        rom_path = ROOT / "rom/base.gba"
        rom_before = rom_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "repository root or ancestor"):
            export_rom_boot_framebuffers(ROOT, ROOT)
        self.assertEqual(rom_before, rom_path.read_bytes())
        self.assertTrue((ROOT / "tools/export_rom_boot_framebuffers.py").is_file())

    def test_verifier_rejects_tampered_binary_and_overclaimed_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "binary"
            shutil.copytree(self.artifact_dir, artifact)
            path = artifact / "boot-frame-a.bin"
            raw = bytearray(path.read_bytes())
            raw[0] ^= 1
            path.write_bytes(raw)
            report = verify_rom_boot_framebuffers(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(any("boot-frame-a.bin" in item for item in report["errors"]))

        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "scope"
            shutil.copytree(self.artifact_dir, artifact)
            path = artifact / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["scope"] = copy.deepcopy(manifest["scope"])
            manifest["scope"]["physical_gba_verified"] = True
            path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = verify_rom_boot_framebuffers(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(any("manifest" in item for item in report["errors"]))

    def test_startup_analyzer_rejects_header_or_irq_literal_tampering(self):
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0xBD] ^= 1
        with self.assertRaisesRegex(ValueError, "header complement"):
            analyze_arm_startup_chain(bytes(rom))

        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0xF4] ^= 1
        with self.assertRaisesRegex(ValueError, "IRQ callback slot"):
            analyze_arm_startup_chain(bytes(rom))


if __name__ == "__main__":
    unittest.main()
