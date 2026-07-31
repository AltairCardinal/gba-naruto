from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_wram_tilemap_single_input_probe.lua"


class MgbaWramTilemapSingleInputProbeScriptTests(unittest.TestCase):
    def test_probe_loads_checkpoint_then_installs_targets_and_one_input(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertLess(text.index("emu:loadStateFile"), text.index("emu:setBreakpoint"))
        self.assertIn('required_env("MGBA_WRAM_INPUT_KEY")', text)
        self.assertIn('required_env("MGBA_WRAM_INPUT_DOWN_FRAME")', text)
        self.assertIn('required_env("MGBA_WRAM_INPUT_UP_FRAME")', text)
        self.assertIn("emu:addKey(key)", text)
        self.assertIn("emu:clearKey(key)", text)
        self.assertEqual(1, text.count("emu:addKey(key)"))
        self.assertEqual(1, text.count("emu:clearKey(key)"))
        self.assertIn('"automatic_inputs":[]', text)
        self.assertIn('"recovery_inputs":[]', text)
        for address in (
            "0x0808AD3A",
            "0x0808BAB0",
            "0x0808BBD8",
            "0x0808BBFC",
            "0x0808BC2E",
            "0x0808BECC",
            "0x080914D8",
            "0x0809182E",
            "0x08091BF6",
            "0x08091000",
            "0x08090B5C",
            "0x08090CB0",
            "0x08090D56",
            "0x08090DC4",
            "0x08090F3C",
            "0x0806365C",
        ):
            self.assertIn(address, text)

    def test_probe_persists_breakpoint_queue_vram_and_reusable_states(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"schema":"mgba-wram-tilemap-single-input-probe-v1"', text)
        self.assertIn('register_hex("r6")', text)
        self.assertIn('register_hex("r8")', text)
        self.assertIn('target.name .. "-queue.bin"', text)
        self.assertIn('target.name .. "-vram.bin"', text)
        self.assertIn('target.name .. "-hit.ss9"', text)
        self.assertIn('target.name .. "-hit.png"', text)
        self.assertIn('"/final-queue.bin"', text)
        self.assertIn('"/final-vram.bin"', text)
        self.assertIn('"/hit.ss9"', text)
        self.assertIn('"/final.ss9"', text)
        self.assertIn("write_file(done_marker", text)
        self.assertNotIn("os.exit", text)


if __name__ == "__main__":
    unittest.main()
