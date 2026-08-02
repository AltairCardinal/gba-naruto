from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_battle_effect_phase_capture.lua"


class MgbaBattleEffectPhaseCaptureScriptTests(unittest.TestCase):
    def test_captures_renderer_copy_and_ack_posts_for_one_expected_group(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for address in (
            "0x08063328",
            "0x08061126",
            "0x080612AA",
        ):
            self.assertIn(address, source)
        for address in (
            "0x03003BB8",
            "0x0300027C",
            "0x07000000",
            "0x0300067C",
        ):
            self.assertIn(address, source)
        self.assertIn("emu:setBreakpoint", source)
        self.assertIn("emu:setRangeWatchpoint", source)
        self.assertIn("C.WATCHPOINT_TYPE.WRITE_CHANGE", source)
        self.assertIn("emu:clearBreakpoint", source)
        self.assertIn("emu:saveStateFile", source)
        self.assertIn("emu:screenshot", source)
        self.assertIn('"renderer-post"', source)
        self.assertIn('"submit-post"', source)
        self.assertIn('"ack-post"', source)
        self.assertNotIn("os.exit", source)

    def test_uses_only_explicit_profile_input_and_requires_group_identity_pair(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for name in (
            "MGBA_EFFECT_PHASE_INPUT_STATE",
            "MGBA_EFFECT_PHASE_INPUT_SCHEDULE",
            "MGBA_EFFECT_PHASE_INPUT_MODE",
            "MGBA_EFFECT_PHASE_GROUP_ID",
            "MGBA_EFFECT_PHASE_DEFINITION_POINTER",
            "MGBA_EFFECT_PHASE_ANIMATION_POINTER",
            "MGBA_EFFECT_PHASE_CAPTURE_FRAMES",
            "MGBA_EFFECT_PHASE_TIMEOUT_FRAMES",
            "MGBA_EFFECT_PHASE_OUTPUT_DIR",
            "MGBA_EFFECT_PHASE_DONE_MARKER",
        ):
            self.assertIn(name, source)
        self.assertIn("definition == expected_definition", source)
        self.assertIn("animation == expected_animation", source)
        self.assertIn("emu:setKeys(active_keys)", source)
        self.assertIn('"automatic_inputs":[]', source)
        self.assertIn('"recovery_inputs":[]', source)
        self.assertIn('input_mode == "zero-input-active-state"', source)
        self.assertIn('input_mode == "explicit-input-sequence"', source)
        self.assertLess(source.index("emu:loadStateFile"), source.index("emu:setBreakpoint"))
        self.assertIn("frame >= timeout_frames", source)
        self.assertNotIn("frame >= capture_frames then\n\t\tfinish", source)
        for diagnostic in (
            "renderer_hit_count",
            "submission_watch_hit_count",
            "ack_hit_count",
            "timeout-task-pool.bin",
            "timeout.ss9",
            "startup-environment.json",
            "startup-state.json",
            "startup-breakpoints.json",
            "startup-renderer-breakpoint.json",
            "startup-submission-watchpoint.json",
        ):
            self.assertIn(diagnostic, source)
        self.assertIn("install_ack_breakpoint()", source)
        submission_start = source.index("local function install_submit_breakpoint")
        self.assertGreater(
            source.index("install_ack_breakpoint()", submission_start),
            source.index('phase_index = 2', submission_start),
        )


if __name__ == "__main__":
    unittest.main()
