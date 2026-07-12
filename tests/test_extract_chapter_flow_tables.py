import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from extract_chapter_flow_tables import build_bank


class ChapterFlowTablesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_primary_runtime_scenario_points_to_live_script(self):
        bank = build_bank(self.rom, "story")
        self.assertEqual(bank["table_offset"], 0x60C74)
        self.assertEqual(len(bank["entries"]), 56)
        self.assertEqual(bank["entries"][0]["script_ptr"], 0)
        self.assertEqual(bank["entries"][39]["script_ptr"], 0x08031020)
        self.assertEqual(self.rom[0x31070:0x31074].hex(), "1a280200")
        self.assertEqual(bank["runtime_sample"]["script_bytes"], "1a280200")
        self.assertEqual(bank["runtime_sample"]["semantic_commands"][0]["length"], 3)
        self.assertEqual(bank["runtime_sample"]["semantic_commands"][1]["name"], "end")
        self.assertEqual(bank["verification"], "runtime_verified")

    def test_alternate_table_has_same_scenario_domain(self):
        bank = build_bank(self.rom, "story-b")
        self.assertEqual(bank["table_offset"], 0x60D54)
        self.assertEqual(len(bank["entries"]), 56)
        self.assertEqual(bank["entries"][39]["script_ptr"], 0x08031281)
        self.assertEqual(bank["verification"], "runtime_verified")
        self.assertEqual(bank["runtime_sample"]["terminal_opcode_address"], "0x0803142E")
        self.assertEqual(bank["runtime_sample"]["dispatch_hit_count"], 25)


if __name__ == "__main__":
    unittest.main()
