from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_map_sprites_trace.lua"


class MgbaMapSpritesTraceScriptTests(unittest.TestCase):
    def test_traces_the_generic_pair_install_and_render_chain(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for token in (
            "MAP_SPRITES_TRACE_INPUT_STATE",
            "MAP_SPRITES_TRACE_INPUT_STATE_SHA256",
            "MAP_SPRITES_TRACE_OUTPUT_DIR",
            "MAP_SPRITES_TRACE_DONE_MARKER",
            "MAP_SPRITES_TRACE_RUN_ID",
            "MAP_SPRITES_TRACE_ROM_SHA256",
            "MAP_SPRITES_TRACE_BINARY_SHA256",
            '"generic-loader", address = 0x08080B08',
            '"pair-install", address = 0x08062668',
            '"frame-select", address = 0x0806298C',
            '"oam-compose", address = 0x08063108',
            "0x0853F140",
            "0x03003BB8",
            "emu:saveStateFile",
            "emu:screenshot",
        ):
            self.assertIn(token, text)

    def test_supports_a_validated_input_schedule_and_has_no_recovery_input(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for token in (
            "MAP_SPRITES_TRACE_INPUT_SCHEDULE",
            "parse_schedule",
            "input intervals overlap",
            "C.GBA_KEY.A",
            "C.GBA_KEY.DOWN",
            '"recovery_inputs":[]',
            "frame_limit <= 900",
            "emu:setKeys(0)",
        ):
            self.assertIn(token, text)

    def test_supports_an_explicit_controlled_pair_materialization(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for token in (
            "MAP_SPRITES_TRACE_BOOTSTRAP_TASK_SLOT",
            "MAP_SPRITES_TRACE_BOOTSTRAP_ID",
            "MAP_SPRITES_TRACE_BOOTSTRAP_EXPECTED_DEFINITION",
            '"controlled-bootstrap"',
            'finish("all-downstream-boundaries-hit")',
            "CONTROLLED_POST_BOUNDARY_FRAMES = 2",
            "boundary_complete_frame",
            "emu:write8(target_task + 0x1C",
            "emu:write8(target_task, task_flags | 1)",
            '"controlled_task_materialization":',
            '"binary_sha256":',
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
