import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "mgba_breakpoint_frame_trace.lua"


class BreakpointFrameTraceLuaContractTests(unittest.TestCase):
    def read_script(self) -> str:
        self.assertTrue(
            SCRIPT.is_file(),
            "tools/mgba_breakpoint_frame_trace.lua must exist",
        )
        return SCRIPT.read_text(encoding="utf-8")

    def test_requires_strict_target_and_output_environment(self):
        lua = self.read_script()

        self.assertIn('required_env("MGBA_BREAKPOINT_TRACE_TARGET")', lua)
        self.assertIn('required_env("MGBA_BREAKPOINT_TRACE_OUTPUT")', lua)
        self.assertRegex(lua, r'target_text:match\("\^0x(?:%x){8}\$"\)')
        self.assertIn('os.getenv("MGBA_BREAKPOINT_TRACE_MAX_HITS") or "256"', lua)
        self.assertRegex(lua, r"max_hits\s*>\s*0")
        self.assertRegex(lua, r"max_hits\s*==\s*math\.floor\(max_hits\)")
        self.assertRegex(lua, r'assert\(io\.open\(output_path,\s*"a"\)')

    def test_registers_start_and_frame_callbacks_with_read_only_roles(self):
        lua = self.read_script()

        start_callback = re.search(
            r'callbacks:add\("start", function\(\)(.*?)end\)', lua, re.DOTALL
        )
        frame_callback = re.search(
            r'callbacks:add\("frame", function\(\)(.*?)end\)', lua, re.DOTALL
        )
        self.assertIsNotNone(start_callback)
        self.assertIsNotNone(frame_callback)
        self.assertIn("emu:setBreakpoint", start_callback.group(1))
        self.assertRegex(frame_callback.group(1), r"^\s*frame\s*=\s*frame\s*\+\s*1\s*$")

    def test_appends_jsonl_with_required_hit_context(self):
        lua = self.read_script()

        self.assertIn('io.open(output_path, "a")', lua)
        for json_field in (
            '"schema_version":1',
            '"hit":',
            '"frame":',
            '"cycle":',
            '"target":',
            '"pc":',
            '"lr":',
            '"sp":',
        ):
            self.assertIn(json_field, lua)
        self.assertIn('emu:readRegister("pc")', lua)
        self.assertIn('emu:readRegister("lr")', lua)
        self.assertIn('emu:readRegister("sp")', lua)
        self.assertIn("emu:currentCycle()", lua)
        self.assertRegex(lua, r'f:write\(line,\s*"\\n"\)')

    def test_max_hits_clears_breakpoint_without_terminating_process(self):
        lua = self.read_script()

        self.assertRegex(lua, r"hit_count\s*>=\s*max_hits")
        self.assertIn("emu:clearBreakpoint(breakpoint_id)", lua)
        self.assertNotIn("os.exit", lua)

    def test_contains_no_input_api_or_hard_coded_trace_configuration(self):
        lua = self.read_script()

        for forbidden in ("emu:setKeys", "addKey", "clearKey"):
            self.assertNotIn(forbidden, lua)
        self.assertNotRegex(lua, r'/Users/|/home/|[A-Za-z]:\\\\')
        self.assertNotRegex(lua, r"0x0[238][0-9A-Fa-f]{6}")


if __name__ == "__main__":
    unittest.main()
