import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "mgba_dump_gpu_state.lua"


class DumpGpuStateScriptTest(unittest.TestCase):
    def test_script_loads_one_state_and_dumps_component_memory(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")
        for token in (
            "MGBA_GPU_STATE_INPUT",
            "MGBA_GPU_STATE_OUTPUT_DIR",
            "MGBA_GPU_STATE_DONE_MARKER",
            "emu:loadStateFile",
            "emu:screenshot",
            '"io", 0x400',
            '"vram", 0x18000',
            '"oam", 0x400',
            '"pram", 0x400',
            "read_absolute_range",
            '"wb"',
            '"status":"capture-complete"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertNotIn("os.exit", source)


if __name__ == "__main__":
    unittest.main()
