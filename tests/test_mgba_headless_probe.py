import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "mgba-headless-snapshot.py"
SPEC = importlib.util.spec_from_file_location("mgba_headless_snapshot", SCRIPT)
mgba = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mgba)


BREAKPOINT_OUTPUT = """Breakpoint 0 set at 0x08068FF0
Hit breakpoint 0 at 0x08068FF0
 r0: 00000003   r1: 00000000   r2: 00000000   r3: 00000001
 r4: 00000000   r5: 00000000   r6: 00000000   r7: 00000000
 r8: 00000000   r9: 00000000   r10: 00000000  r11: 00000000
 r12: 00000000  r13: 03007F00  r14: 08012345  r15: 08068FF0
 cpsr: 0000003F [-------T]
 Cycle: 123456
 08068FF0: 4804 ldr r0, [pc, #0x10]
0x0853D910: 00140014 08100001 08100002 08100003
0x02024290: 00000000 00040003 00000001 00000000
"""


class MgbaReadProbeTests(unittest.TestCase):
    def test_build_probe_commands_breaks_then_reads_rom_and_wram(self):
        commands = mgba.build_probe_commands(
            0x08068FF0,
            [(0x0853D910, 16), (0x02024290, 16)],
            frames=2,
        )
        self.assertEqual(
            [
                "frame",
                "frame",
                "b 0x08068FF0",
                "continue",
                "status",
                "x/4 0x0853D910",
                "x/4 0x02024290",
                "quit",
            ],
            commands,
        )

    def test_parse_probe_output_requires_breakpoint_hit_and_keeps_context(self):
        result = mgba.parse_probe_output(
            BREAKPOINT_OUTPUT,
            0x08068FF0,
            [(0x0853D910, 16), (0x02024290, 16)],
        )
        self.assertTrue(result["hit"])
        self.assertEqual("0x08068FF0", result["hit_pc"])
        self.assertEqual("0x08012345", result["registers"]["lr"])
        self.assertEqual(
            ["0x00140014", "0x08100001", "0x08100002", "0x08100003"],
            result["memory_reads"][0]["words"],
        )

    def test_parse_probe_output_does_not_treat_status_as_a_hit(self):
        status_only = BREAKPOINT_OUTPUT.replace("Hit breakpoint 0 at 0x08068FF0\n", "")
        result = mgba.parse_probe_output(status_only, 0x08068FF0, [])
        self.assertFalse(result["hit"])
        self.assertIsNone(result["hit_pc"])

    @patch.object(mgba, "run_mgba_commands")
    @patch.object(mgba, "find_mgba", return_value="/fake/mgba")
    def test_mode_probe_integrates_command_runner(self, _find, run):
        run.return_value = (BREAKPOINT_OUTPUT, "fixture warning")
        result = mgba.mode_probe(
            "fixture.gba", 0x08068FF0, [(0x0853D910, 16)], 2, 9
        )
        commands = run.call_args.args[2]
        self.assertEqual("b 0x08068FF0", commands[2])
        self.assertEqual(9, run.call_args.kwargs["timeout"])
        self.assertTrue(result["hit"])
        self.assertEqual("fixture warning", result["stderr"])

    @patch.object(mgba, "run_mgba_commands")
    @patch.object(mgba, "find_mgba", return_value="/fake/mgba")
    def test_mode_probe_returns_reproducible_timeout_evidence(self, _find, run):
        run.side_effect = subprocess.TimeoutExpired(
            cmd=["/fake/mgba"], timeout=9, output="Added breakpoint #1\n"
        )
        result = mgba.mode_probe(
            "fixture.gba", 0x08068FF0, [(0x0853D910, 16)], 0, 9
        )
        self.assertFalse(result["hit"])
        self.assertTrue(result["timed_out"])
        self.assertEqual("0x08068FF0", result["breakpoint"])


if __name__ == "__main__":
    unittest.main()
