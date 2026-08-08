from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_map_events_e4_trace.lua"


class MgbaMapEventsE4TraceScriptTests(unittest.TestCase):
    def test_traces_natural_expiry_table_dispatch_and_group3(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for token in (
            "MAP_EVENTS_E4_INPUT_STATE",
            "MAP_EVENTS_E4_INPUT_STATE_SHA256",
            "MAP_EVENTS_E4_OUTPUT_DIR",
            "MAP_EVENTS_E4_DONE_MARKER",
            "MAP_EVENTS_E4_ROM_SHA256",
            "MAP_EVENTS_E4_SCRIPT_SHA256",
            "MAP_EVENTS_E4_BINARY_SHA256",
            "MAP_EVENTS_E4_EXPECTED_HANDLER",
            "0x08081D74",
            "0x0807FD36",
            "0x0807FD38",
            "0x0807F208",
            "0x0809C114",
            "0x0853EDB8",
            "0x083425D8",
            "0x083426CC",
            '"recovery_inputs":[]',
            "emu:saveStateFile",
            "emu:screenshot",
        ):
            self.assertIn(token, text)
        self.assertNotIn("not expiry_seen", text)

    def test_waits_a_bounded_identical_post_dispatch_window(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for token in (
            "POST_DISPATCH_FRAMES = 3",
            "frame >= dispatch_frame + POST_DISPATCH_FRAMES",
            'finish("post-dispatch-window-complete")',
            "emu:setKeys(0)",
            '"inputs":[]',
            '"automatic_inputs":[]',
        ):
            self.assertIn(token, text)
        self.assertNotIn("while not complete do emu:frameAdvance() end", text)


if __name__ == "__main__":
    unittest.main()
