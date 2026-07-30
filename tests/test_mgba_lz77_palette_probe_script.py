import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_lz77_palette_probe.lua"


class MgbaLz77PaletteProbeScriptTests(unittest.TestCase):
    def test_probe_has_only_the_two_verified_routes_and_load_boundaries(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('route_name == "scenario-41-target-confirmation"', text)
        self.assertIn('route_name == "profile-browser-init"', text)
        self.assertIn("0x08071BD0", text)
        self.assertIn("0x0808B5EE", text)
        self.assertIn("C.GBA_KEY.UP", text)
        self.assertIn("C.GBA_KEY.DOWN", text)
        self.assertIn("C.GBA_KEY.A", text)
        self.assertIn("target_tile_first = 800", text)
        self.assertIn("target_tile_last = 841", text)
        self.assertIn("target_tile_first = 940", text)
        self.assertIn("target_tile_last = 943", text)

    def test_probe_captures_exact_hit_domains_and_watches_both_oam_copies(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for name in ["pram.bin", "vram.bin", "oam.bin", "shadow-oam.bin"]:
            self.assertIn(name, text)
        self.assertIn("0x05000000", text)
        self.assertIn("0x06000000", text)
        self.assertIn("0x07000000", text)
        self.assertIn("0x0300027C", text)
        self.assertIn("post_hit_watch_frames = 240", text)
        self.assertIn('scan_oam(0x07000000, "hardware")', text)
        self.assertIn('scan_oam(0x0300027C, "shadow")', text)

    def test_probe_records_provenance_and_finishes_without_exiting_mgba(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for name in [
            "MGBA_LZ77_INPUT_STATE",
            "MGBA_LZ77_INPUT_STATE_SHA256",
            "MGBA_LZ77_ROM_SHA256",
            "MGBA_LZ77_BINARY_SHA256",
            "MGBA_LZ77_OUTPUT_DIR",
            "MGBA_LZ77_DONE_MARKER",
            "MGBA_LZ77_RUN_ID",
            "MGBA_LZ77_ROUTE",
        ]:
            self.assertIn(name, text)
        self.assertIn("emu:setBreakpoint", text)
        self.assertIn("emu:clearBreakpoint", text)
        self.assertIn("emu:saveStateFile", text)
        self.assertIn("write_file(done_marker, payload)", text)
        self.assertNotIn("os.exit", text)


if __name__ == "__main__":
    unittest.main()
