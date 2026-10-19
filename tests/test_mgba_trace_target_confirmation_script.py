import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "mgba_trace_target_confirmation.lua"


class TargetConfirmationTraceScriptTest(unittest.TestCase):
    def test_trace_records_original_range_builder_and_confirmation_branches(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_TARGET_CONFIRMATION_INPUT_STATE",
            "MGBA_TARGET_CONFIRMATION_OUTPUT_DIR",
            "MGBA_TARGET_CONFIRMATION_DONE_MARKER",
            "0x0806A4AC",
            "0x0807181A",
            "0x08071922",
            "0x08071926",
            "0x080719A0",
            "0x0807165E",
            "0x02026A78",
            "0x02026A79",
            "area_builder_result",
            "accepted_confirmation",
            "rejected_confirmation",
            "target-confirmation-trace.jsonl",
            "emu:readRegister",
            "emu:setBreakpoint",
            "emu:saveStateFile",
            "emu:screenshot",
            "C.GBA_KEY.A",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

        self.assertNotIn("os.exit", source)


if __name__ == "__main__":
    unittest.main()
