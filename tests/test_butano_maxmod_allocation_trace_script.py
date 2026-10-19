import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "tools"
    / "butano"
    / "mgba_maxmod_allocation_trace.lua"
)


class ButanoMaxmodAllocationTraceScriptTest(unittest.TestCase):
    def test_traces_note_allocation_entry_and_result(self):
        self.assertTrue(SCRIPT.is_file())
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_MAXMOD_ALLOCATION_OUTPUT_DIR",
            "MGBA_MAXMOD_ALLOCATION_DONE_MARKER",
            "MGBA_MAXMOD_FRAME_ADDRESS",
            "MGBA_MAXMOD_NEW_NOTE_VENEER_TARGET_ADDRESS",
            "0x03000B04",
            "0x030004AC",
            "0x03000B78",
            "0x08042610",
            '"mm-frame"',
            '"new-note"',
            '"alloc-entry"',
            '"alloc-result"',
            "maxmod-allocation-trace.jsonl",
            "local function install_breakpoints()",
            "install_breakpoints()",
            "emu:reset()",
            "MAXMOD_NEW_NOTE_VENEER_TARGET_ADDRESS",
            "new_note_veneer_target",
            '"veneer-write"',
            "emu:setRangeWatchpoint",
            "C.WATCHPOINT_TYPE.WRITE_CHANGE",
            "emu:setBreakpoint",
            "emu:clearBreakpoint",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)


if __name__ == "__main__":
    unittest.main()
