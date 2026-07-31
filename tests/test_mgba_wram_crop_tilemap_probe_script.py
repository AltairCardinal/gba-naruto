from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_wram_crop_tilemap_probe.lua"


class MgbaWramCropTilemapProbeScriptTests(unittest.TestCase):
    def test_probe_is_zero_input_and_targets_load_and_consumer(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertLess(text.index("emu:loadStateFile"), text.index("emu:setBreakpoint"))
        self.assertIn("0x0808BC2E", text)
        self.assertIn("0x0808B79C", text)
        self.assertIn("emu:setKeys(0)", text)
        self.assertNotIn("emu:addKey", text)
        self.assertNotIn("emu:clearKey", text)
        self.assertIn('"inputs":[]', text)

    def test_probe_persists_target_specific_vram_and_reusable_boundaries(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"schema":"mgba-wram-crop-tilemap-probe-v1"', text)
        self.assertIn('target.name .. "-vram.bin"', text)
        self.assertIn('"/crop_consumer-wram.bin"', text)
        self.assertIn("read_range(0x02002880, 0x320)", text)
        self.assertIn('target.name .. "-hit.ss9"', text)
        self.assertIn('target.name .. "-hit.png"', text)
        self.assertIn('"/final-vram.bin"', text)
        self.assertIn('"/final.ss9"', text)
        self.assertIn('"/final.png"', text)
        self.assertIn("write_file(done_marker", text)
        self.assertNotIn("os.exit", text)


if __name__ == "__main__":
    unittest.main()
