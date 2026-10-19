from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "mgba_s41_telemetry_trace.lua"


class ButanoS41TelemetryTraceTests(unittest.TestCase):
    def test_records_deployment_progress_and_finishes(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('required_env("MGBA_S41_TRACE_OUTPUT_DIR")', source)
        self.assertIn('required_env("MGBA_S41_TRACE_DONE_MARKER")', source)
        self.assertIn(
            'required_env("MGBA_S41_TRACE_TELEMETRY_ADDRESS")',
            source,
        )
        self.assertIn('callbacks:add("frame"', source)
        self.assertIn("emu:read32(telemetry_address)", source)
        self.assertIn("emu:addKey(C.GBA_KEY.A)", source)
        self.assertIn('"trace-complete"', source)
