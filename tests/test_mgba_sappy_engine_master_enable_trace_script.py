import tempfile
import unittest
from pathlib import Path

from tools.mgba_runtime_safety import prepare_mgba_launch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_sappy_engine_master_enable_trace.lua"


class MgbaSappyEngineMasterEnableTraceScriptTests(unittest.TestCase):
    def test_traces_initializer_dispatch_and_first_soundmain(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for address in (
            "0x0809AE3C",
            "0x0809AEF2",
            "0x0809AAC0",
            "0x0809AABA",
            "0x04000084",
            "0x040000BC",
            "0x040000C8",
        ):
            self.assertIn(address, source)
        self.assertIn("right_hex", source)
        self.assertIn("left_hex", source)
        self.assertIn("SAPPY_TRACE_DONE_MARKER", source)
        self.assertIn("SAPPY_TRACE_ROM_SHA256", source)
        self.assertIn("SAPPY_TRACE_INPUT_STATE_SHA256", source)
        self.assertIn("emu:loadStateFile", source)
        self.assertIn("emu:saveStateFile", source)

    def test_is_callback_driven_and_bounded(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('callbacks:add("frame"', source)
        self.assertIn("frame_limit", source)
        self.assertIn("frame == 5", source)
        self.assertIn("frame == 13", source)
        self.assertNotIn("emu:frameAdvance()", source)
        self.assertNotIn("while not complete", source)

    def test_passes_repository_mgba_lua_safety_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            self.assertIsNotNone(
                prepare_mgba_launch(
                    ["mGBA", "--script", str(SCRIPT), "game.gba"],
                    crash_dir=reports,
                    latch_path=root / "latch.json",
                    settle_timeout_s=0,
                )
            )


if __name__ == "__main__":
    unittest.main()
