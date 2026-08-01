from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_controlled_battle_effect_capture.lua"


class MgbaControlledBattleEffectCaptureScriptTests(unittest.TestCase):
    def test_captures_binder_return_then_global_renderer_submission_and_ack(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for address in (
            "0x0809E85A",
            "0x08063328",
            "0x08061126",
            "0x080612AA",
        ):
            self.assertIn(address, source)
        for phase in (
            '"binder-return"',
            '"renderer-post"',
            '"submit-post"',
            '"ack-post"',
        ):
            self.assertIn(phase, source)
        self.assertIn("scratch_before == 0", source)
        self.assertIn("scratch_after == 1", source)
        self.assertIn("matching_active_task", source)
        self.assertIn('capture_phase("binder-return", BINDER_RETURN, false)', source)
        self.assertIn('"automatic_inputs":[]', source)
        self.assertIn('"recovery_inputs":[]', source)
        self.assertNotIn("os.exit", source)
