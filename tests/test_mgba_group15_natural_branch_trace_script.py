from __future__ import annotations

import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_group15_natural_branch_trace.lua"


class Group15NaturalBranchTraceScriptTests(unittest.TestCase):
    def test_script_is_the_exact_observer_used_by_the_runtime_run(self):
        self.assertEqual(
            hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
            "782cfd0c2125ef4753b2504271ed67c9438fe119d7a384dd961d07d7ccbb4f83",
        )
        source = SCRIPT.read_text(encoding="utf-8")
        for address in (
            "0x0807A222",
            "0x0807F064",
            "0x0807F09E",
            "0x0807F0FC",
            "0x0807F10C",
            "0x0807C5E8",
        ):
            self.assertIn(address, source)
        self.assertIn("frame == 60", source)
        self.assertIn("frame == 68", source)
        self.assertIn('os.getenv("NATURAL_TRACE_ROM_SHA256")', source)
        self.assertIn('os.getenv("NATURAL_TRACE_INPUT_STATE_SHA256")', source)
        self.assertIn('os.getenv("NATURAL_TRACE_SCRIPT_SHA256")', source)
        self.assertNotIn("os.exit", source)


if __name__ == "__main__":
    unittest.main()
