from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "mgba_character_fbff_probe.lua"


class MgbaCharacterFbffProbeScriptTests(unittest.TestCase):
    def test_injects_the_exact_resource_and_persists_runtime_evidence(self):
        text = SCRIPT.read_text(encoding="utf-8")

        for name in (
            "MGBA_FBFF_INPUT_STATE",
            "MGBA_FBFF_INPUT_STATE_SHA256",
            "MGBA_FBFF_OUTPUT_DIR",
            "MGBA_FBFF_DONE_MARKER",
            "MGBA_FBFF_RUN_ID",
            "MGBA_FBFF_ROM_SHA256",
            "MGBA_FBFF_CAPTURE_FRAME",
            "MGBA_FBFF_EXPECTED_TRAILER",
        ):
            self.assertIn(name, text)
        for address in (
            "0x03005940",
            "0x080631FE",
            "0x0825A918",
            "0x0825A948",
            "0x08258CA0",
        ):
            self.assertIn(address, text)
        self.assertIn("emu:loadStateFile", text)
        self.assertIn("assert(emu:read32(task_address) == injected_flags)", text)
        self.assertIn("assert(emu:read16(task_address + 0x16) == 2)", text)
        self.assertIn("assert(emu:read32(task_address + 0x28) == 0)", text)
        self.assertNotIn("emu:write", text)
        self.assertIn('output_dir .. "/task-before.bin"', text)
        self.assertIn('output_dir .. "/task-after.bin"', text)
        self.assertIn('output_dir .. "/oam.bin"', text)
        self.assertIn('output_dir .. "/renderer-loop.json"', text)
        self.assertIn('output_dir .. "/output.ss9"', text)
        self.assertIn('output_dir .. "/frame.png"', text)
        self.assertLess(
            text.index('write_file(output_dir .. "/audit.json"'),
            text.index("write_file(done_marker"),
        )
        self.assertNotIn("os.exit", text)

    def test_uses_a_unique_tile_palette_signature_and_bounded_capture(self):
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("0x0300", text)
        self.assertIn("0x0E", text)
        self.assertIn("0xE340", text)
        self.assertIn("0xFEFF", text)
        self.assertIn("frame < capture_frame", text)
        self.assertIn("emu:currentCycle()", text)
        self.assertIn(',"cycles":', text)
        self.assertIn('expected_trailer == "FBFF"', text)
        self.assertIn('expected_trailer == "FFFF"', text)
        self.assertIn("emu:setBreakpoint", text)
        self.assertIn('emu:readRegister("r8")', text)
        self.assertIn("relevant_renderer_pointer", text)
        self.assertIn("anomalous_trailer_address + 0x3C", text)
        self.assertIn('"renderer_continues_past_fbff"', text)
        self.assertIn('"renderer_stops_at_ffff"', text)
        self.assertIn("0x0825A8E4", text)
        self.assertIn("0xFBFF", text)
        self.assertIn("0xFFFF", text)
        self.assertIn('"mgba-character-fbff-probe-v1"', text)


if __name__ == "__main__":
    unittest.main()
