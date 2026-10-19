import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "mgba_trace_action_presentation.lua"


class ActionPresentationTraceScriptTest(unittest.TestCase):
    def test_trace_binds_action_execution_to_presentation_runtime(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_ACTION_PRESENTATION_INPUT_STATE",
            "MGBA_ACTION_PRESENTATION_OUTPUT_DIR",
            "MGBA_ACTION_PRESENTATION_DONE_MARKER",
            "MGBA_ACTION_PRESENTATION_GPU_CAPTURE_START",
            "MGBA_ACTION_PRESENTATION_GPU_CAPTURE_END",
            "MGBA_ACTION_PRESENTATION_CAPTURE_FRAMES",
            "MGBA_ACTION_PRESENTATION_CONFIRM_FRAME",
            "MGBA_ACTION_PRESENTATION_CONFIRM_HOLD_FRAMES",
            "MGBA_ACTION_PRESENTATION_KEY_SEQUENCE",
            "parse_key_sequence",
            "scheduled_presses",
            "scheduled_releases",
            "input key intervals overlap",
            "unknown input key",
            "0x0806D85C",
            "0x0806D910",
            '"tool_initializer_hits":%d',
            "0x080754A8",
            "0x0807B8B8",
            "0x0807C5E8",
            "0x0807FDCC",
            "0x0807FE2C",
            "0x08080108",
            "0x08061E6C",
            "0x0809C0DC",
            "0x0809C0E0",
            "0x0809C0E8",
            "0x0809C0EC",
            "presentation-trace.jsonl",
            "state_frames",
            "gpu_capture_start",
            "gpu_capture_end",
            "gpu_capture_start <= gpu_capture_end",
            "gpu_capture_end <= capture_frames",
            "confirm_frame + confirm_hold_frames <= capture_frames",
            "frame == capture_frames",
            'dump_gpu_domains("gpu-frame-" .. gpu_tag)',
            "[146] = true",
            "[148] = true",
            "[150] = true",
            "[154] = true",
            "[158] = true",
            "[360] = true",
            "[480] = true",
            "[720] = true",
            "[960] = true",
            "[1200] = true",
            "emu:readRegister",
            "emu:screenshot",
            "emu:saveStateFile",
            "dump_gpu_domains",
            'dump_gpu_domains("state-" .. state_tag)',
            'emu:screenshot(output_dir .. "/state-" .. state_tag .. ".png")',
            '"io", 0x400',
            '"vram", 0x18000',
            '"oam", 0x400',
            '"pram", 0x400',
            "0x05000000",
            "read_absolute_range",
            '"wb"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

        self.assertNotIn("os.exit", source)


if __name__ == "__main__":
    unittest.main()
