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


class CompletedProcessFixture:
    stdout = ""
    stderr = ""


class MgbaReadProbeTests(unittest.TestCase):
    def test_build_mgba_command_loads_savestate_before_rom(self):
        self.assertEqual(
            [
                "/fake/mgba",
                "-d",
                "-C",
                "mute=1",
                "-C",
                "volume=0",
                "--savestate",
                "battle.ss0",
                "fixture.gba",
            ],
            mgba.build_mgba_command("/fake/mgba", "fixture.gba", "battle.ss0"),
        )

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
            "fixture.gba", 0x08068FF0, [(0x0853D910, 16)], 2, 9, "battle.ss0"
        )
        commands = run.call_args.args[2]
        self.assertEqual("b 0x08068FF0", commands[2])
        self.assertEqual(9, run.call_args.kwargs["timeout"])
        self.assertEqual("battle.ss0", run.call_args.kwargs["savestate"])
        self.assertTrue(result["hit"])
        self.assertEqual("battle.ss0", result["savestate"])
        self.assertEqual("fixture warning", result["stderr"])

    @patch.object(mgba.subprocess, "run", return_value=CompletedProcessFixture())
    @patch.object(mgba, "find_mgba", return_value="/fake/mgba")
    def test_all_runtime_modes_pass_savestate_to_mgba_command(self, _find, run):
        mgba.mode_snapshot("fixture.gba", [(0x02000000, 16)], 0, "battle.ss0")
        mgba.mode_diff("fixture.gba", 0x02000000, 16, 0, "battle.ss0")
        mgba.mode_watch("fixture.gba", 0x02000000, 1, 0, 1, "battle.ss0")

        for call in run.call_args_list:
            cmd = call.args[0]
            self.assertIn("--savestate", cmd)
            self.assertEqual("battle.ss0", cmd[cmd.index("--savestate") + 1])
            self.assertLess(cmd.index("--savestate"), len(cmd) - 1)

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

    @patch.object(mgba.subprocess, "run")
    @patch.object(mgba, "find_mgba", return_value="/fake/mgba")
    def test_mode_snapshot_keeps_memory_emitted_before_process_timeout(self, _find, run):
        run.side_effect = subprocess.TimeoutExpired(
            cmd=["/fake/mgba"],
            timeout=60,
            output="0x02026804: 00002900 00000000 00000000 00000000\n",
            stderr="fixture timeout",
        )
        result = mgba.mode_snapshot(
            "fixture.gba", [(0x02026804, 16)], 0, "battle.ss9", timeout=3
        )
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["memory_dumps"][0]["words"][0], "0x00002900")
        self.assertEqual(result["stderr"], "fixture timeout")
        self.assertEqual(run.call_args.kwargs["timeout"], 3)


if __name__ == "__main__":
    unittest.main()
