from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_wram_tilemap_probe.lua"


class MgbaWramTilemapProbeScriptTests(unittest.TestCase):
    def test_probe_restores_checkpoint_before_breakpoints_and_has_no_inputs(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertLess(
            text.index("emu:loadStateFile"),
            text.index("emu:setBreakpoint"),
        )
        self.assertIn("emu:setKeys(0)", text)
        self.assertNotIn("emu:addKey", text)
        self.assertNotIn("emu:clearKey", text)
        for address in (
            "0x0808B640",
            "0x0808B2C8",
            "0x0808AD3A",
            "0x0808BAB0",
            "0x0808BBD8",
            "0x0808BBFC",
            "0x0808BC2E",
            "0x08090B5C",
            "0x08090CB0",
            "0x08090D56",
            "0x08090DC4",
            "0x08090F3C",
            "0x0806365C",
        ):
            self.assertIn(address, text)

    def test_probe_persists_reusable_hit_and_final_evidence(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"schema":"mgba-wram-tilemap-probe-v1"', text)
        self.assertIn('"inputs":[]', text)
        self.assertIn('"/queue.bin"', text)
        self.assertIn('"/vram.bin"', text)
        self.assertIn('target.name .. "-queue.bin"', text)
        self.assertIn('target.name .. "-vram.bin"', text)
        self.assertIn('"/final-queue.bin"', text)
        self.assertIn('"/final-vram.bin"', text)
        self.assertIn('"/hit.ss9"', text)
        self.assertIn('"/final.ss9"', text)
        self.assertIn('"/final.png"', text)
        self.assertIn("MGBA_WRAM_DONE_MARKER", text)
        self.assertIn("write_file(done_marker", text)
        self.assertNotIn("os.exit", text)


if __name__ == "__main__":
    unittest.main()
