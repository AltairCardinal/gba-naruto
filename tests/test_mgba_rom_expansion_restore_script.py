import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_rom_expansion_restore_probe.lua"


class RomExpansionRestoreLuaContractTests(unittest.TestCase):
    def test_restore_probe_loads_state_and_rechecks_expanded_marker(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('required_env("MGBA_EXPANSION_RESTORE_STATE")', text)
        self.assertIn("assert(emu:loadStateFile(input_state)", text)
        self.assertIn("emu:read32(0x08600100)", text)
        self.assertIn("emu:read32(0x0203FFF0)", text)
        self.assertIn('write_file(done_marker, payload)', text)
        self.assertNotIn("os.exit", text)
        self.assertNotIn("emu:shutdown", text)


if __name__ == "__main__":
    unittest.main()
