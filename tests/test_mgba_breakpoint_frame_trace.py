import json
import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "mgba_breakpoint_frame_trace.lua"


class BreakpointFrameTraceLuaContractTests(unittest.TestCase):
    def run_lua(
        self,
        *,
        target="0x08012345",
        max_hits=None,
        frame_count=0,
        hit_attempts=0,
        set_result=17,
        clear_result=True,
        include_target=True,
        include_output=True,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "trace.jsonl"
            lua = textwrap.dedent(
                f"""
                local registered = {{}}
                local breakpoint_callback = nil
                local open_calls = 0
                local close_calls = 0
                local clear_calls = 0
                local last_clear_id = "nil"
                local callback_failures = 0
                local first_callback_error = ""
                local real_open = io.open

                callbacks = {{}}
                function callbacks:add(name, callback)
                    registered[name] = callback
                end

                emu = {{}}
                function emu:setBreakpoint(callback, address)
                    breakpoint_callback = callback
                    return {set_result}
                end
                function emu:clearBreakpoint(id)
                    clear_calls = clear_calls + 1
                    last_clear_id = tostring(id)
                    if {str(clear_result).lower()} then breakpoint_callback = nil end
                    return {str(clear_result).lower()}
                end
                function emu:currentCycle() return 123456 end
                function emu:readRegister(name)
                    local values = {{ pc = 0x08012345, lr = 0x08023457, sp = 0x03007F00 }}
                    return values[name]
                end

                io.open = function(path, mode)
                    open_calls = open_calls + 1
                    local real_file, err = real_open(path, mode)
                    if not real_file then return nil, err end
                    local proxy = {{}}
                    function proxy:write(...) return real_file:write(...) end
                    function proxy:flush() return real_file:flush() end
                    function proxy:close()
                        close_calls = close_calls + 1
                        return real_file:close()
                    end
                    return proxy
                end

                local load_ok, load_error = pcall(dofile, {json.dumps(str(SCRIPT))})
                local start_ok = false
                local start_error = ""
                if load_ok and registered.start then
                    start_ok, start_error = pcall(registered.start)
                end
                if start_ok then
                    for _ = 1, {frame_count} do registered.frame() end
                    for _ = 1, {hit_attempts} do
                        if breakpoint_callback then
                            local ok, err = pcall(breakpoint_callback)
                            if not ok then
                                callback_failures = callback_failures + 1
                                if first_callback_error == "" then first_callback_error = tostring(err) end
                            end
                        end
                    end
                end

                local function result(name, value)
                    print("HARNESS_" .. name .. "=" .. tostring(value):gsub("[\\r\\n]", " "))
                end
                result("LOAD_OK", load_ok)
                result("LOAD_ERROR", load_error or "")
                result("START_OK", start_ok)
                result("START_ERROR", start_error or "")
                result("OPEN_CALLS", open_calls)
                result("CLOSE_CALLS", close_calls)
                result("CLEAR_CALLS", clear_calls)
                result("LAST_CLEAR_ID", last_clear_id)
                result("CALLBACK_FAILURES", callback_failures)
                result("CALLBACK_ERROR", first_callback_error)
                """
            )
            env = os.environ.copy()
            if include_target:
                env["MGBA_BREAKPOINT_TRACE_TARGET"] = target
            else:
                env.pop("MGBA_BREAKPOINT_TRACE_TARGET", None)
            if include_output:
                env["MGBA_BREAKPOINT_TRACE_OUTPUT"] = str(output)
            else:
                env.pop("MGBA_BREAKPOINT_TRACE_OUTPUT", None)
            if max_hits is None:
                env.pop("MGBA_BREAKPOINT_TRACE_MAX_HITS", None)
            else:
                env["MGBA_BREAKPOINT_TRACE_MAX_HITS"] = max_hits

            completed = subprocess.run(
                ["lua", "-"],
                input=lua,
                text=True,
                capture_output=True,
                env=env,
                check=True,
            )
            metrics = {
                match.group(1): match.group(2)
                for match in re.finditer(
                    r"^HARNESS_([A-Z_]+)=(.*)$", completed.stdout, re.MULTILINE
                )
            }
            rows = []
            if output.exists():
                rows = [json.loads(line) for line in output.read_text().splitlines()]
            return metrics, rows

    def test_missing_required_environment_fails_before_opening_output(self):
        for missing in ("target", "output"):
            with self.subTest(missing=missing):
                metrics, rows = self.run_lua(
                    include_target=missing != "target",
                    include_output=missing != "output",
                )
                self.assertEqual("false", metrics["LOAD_OK"])
                self.assertEqual("0", metrics["OPEN_CALLS"])
                self.assertEqual([], rows)

    def test_missing_max_hits_uses_the_default(self):
        metrics, rows = self.run_lua(max_hits=None, hit_attempts=1)

        self.assertEqual("true", metrics["LOAD_OK"])
        self.assertEqual("true", metrics["START_OK"])
        self.assertEqual(1, len(rows))
        self.assertEqual("0", metrics["CLEAR_CALLS"])

    def test_invalid_max_hits_fails_before_opening_output(self):
        invalid_values = (
            "",
            "0",
            "-1",
            "1.5",
            "1e3",
            "0x10",
            "+1",
            "01",
            "inf",
            "nan",
            "1e309",
        )
        for value in invalid_values:
            with self.subTest(value=value):
                metrics, rows = self.run_lua(max_hits=value)
                self.assertEqual("false", metrics["LOAD_OK"])
                self.assertIn("positive integer", metrics["LOAD_ERROR"])
                self.assertEqual("0", metrics["OPEN_CALLS"])
                self.assertEqual([], rows)

    def test_hits_emit_parseable_json_and_frames_progress(self):
        metrics, rows = self.run_lua(max_hits="3", frame_count=2, hit_attempts=2)

        self.assertEqual("true", metrics["START_OK"])
        self.assertEqual([1, 2], [row["hit"] for row in rows])
        self.assertEqual([2, 2], [row["frame"] for row in rows])
        self.assertEqual(123456, rows[0]["cycle"])
        self.assertEqual("0x08012345", rows[0]["target"])
        self.assertEqual("0x08012345", rows[0]["pc"])
        self.assertEqual("0x08023457", rows[0]["lr"])
        self.assertEqual("0x03007F00", rows[0]["sp"])

    def test_exact_hit_limit_clears_once_and_closes_without_exiting(self):
        metrics, rows = self.run_lua(max_hits="2", frame_count=1, hit_attempts=4)

        self.assertEqual([1, 2], [row["hit"] for row in rows])
        self.assertEqual("1", metrics["CLEAR_CALLS"])
        self.assertEqual("17", metrics["LAST_CLEAR_ID"])
        self.assertEqual("1", metrics["CLOSE_CALLS"])
        self.assertEqual("0", metrics["CALLBACK_FAILURES"])

    def test_set_breakpoint_failure_closes_output_and_fails_explicitly(self):
        metrics, rows = self.run_lua(max_hits="2", set_result=-1)

        self.assertEqual("true", metrics["LOAD_OK"])
        self.assertEqual("false", metrics["START_OK"])
        self.assertIn("set breakpoint", metrics["START_ERROR"].lower())
        self.assertEqual("1", metrics["CLOSE_CALLS"])
        self.assertEqual([], rows)

    def test_clear_failure_is_explicit_and_keeps_id_for_retry(self):
        metrics, rows = self.run_lua(max_hits="1", hit_attempts=2, clear_result=False)

        self.assertEqual([1], [row["hit"] for row in rows])
        self.assertEqual("2", metrics["CLEAR_CALLS"])
        self.assertEqual("17", metrics["LAST_CLEAR_ID"])
        self.assertEqual("2", metrics["CALLBACK_FAILURES"])
        self.assertIn("clear breakpoint", metrics["CALLBACK_ERROR"].lower())
        self.assertEqual("0", metrics["CLOSE_CALLS"])

    def test_contains_no_input_api_exit_or_hard_coded_trace_configuration(self):
        lua = SCRIPT.read_text(encoding="utf-8")

        for forbidden in ("emu:setKeys", "addKey", "clearKey", "os.exit"):
            self.assertNotIn(forbidden, lua)
        self.assertNotRegex(lua, r"/Users/|/home/|[A-Za-z]:\\\\")
        self.assertNotRegex(lua, r"0x0[238][0-9A-Fa-f]{6}")


if __name__ == "__main__":
    unittest.main()
