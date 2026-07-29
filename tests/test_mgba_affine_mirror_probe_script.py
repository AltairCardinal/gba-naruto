from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "mgba_affine_mirror_probe.lua"


class MgbaAffineMirrorProbeScriptTests(unittest.TestCase):
    def test_captures_one_frame_with_task_and_oam_provenance(self):
        text = SCRIPT.read_text(encoding="utf-8")

        for name in (
            "MGBA_AFFINE_MIRROR_INPUT_STATE",
            "MGBA_AFFINE_MIRROR_INPUT_STATE_SHA256",
            "MGBA_AFFINE_MIRROR_OUTPUT_DIR",
            "MGBA_AFFINE_MIRROR_DONE_MARKER",
            "MGBA_AFFINE_MIRROR_RUN_ID",
            "MGBA_AFFINE_MIRROR_ROM_SHA256",
            "MGBA_AFFINE_MIRROR_CAPTURE_FRAME",
        ):
            self.assertIn(name, text)
        self.assertIn("emu:loadStateFile", text)
        self.assertIn("emu:saveStateFile", text)
        self.assertIn("emu:screenshot", text)
        self.assertIn("0x03005940", text)
        self.assertIn("0xC000B681", text)
        self.assertIn("0x07000000", text)
        self.assertIn("0xFF10", text)
        self.assertIn("frame < capture_frame", text)
        self.assertIn("horizontal_mirror", text)
        self.assertIn(',"success":', text)
        self.assertIn('success and "true" or "false"', text)
        self.assertLess(
            text.index("write_file(output_dir .. \"/audit.json\""),
            text.index("write_file(done_marker"),
        )
        self.assertNotIn("os.exit", text)

    def test_persists_all_gpu_domains_and_reusable_savestate(self):
        text = SCRIPT.read_text(encoding="utf-8")

        for name in ("io", "pram", "vram", "oam"):
            self.assertIn(f'{{ "{name}",', text)
        self.assertIn('output_dir .. "/mirrored.ss9"', text)
        self.assertIn('output_dir .. "/mirrored.png"', text)


if __name__ == "__main__":
    unittest.main()
