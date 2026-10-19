import importlib
import subprocess
import unittest
from unittest import mock


class RuntimeResidueTests(unittest.TestCase):
    def setUp(self):
        self.residue = importlib.import_module("tools.macos_mgba_runtime_residue")

    def test_clean_exact_pgid_and_no_listener(self):
        result = self.residue.validate_runtime_residue(
            20050,
            "  10   999 Python\n",
            "",
            lsof_exit_code=1,
        )
        self.assertTrue(result["pgid_clean"])
        self.assertTrue(result["mgba_listener_clean"])
        self.assertEqual(result["checked_pgid"], 20050)

    def test_rejects_owned_pgid_or_mgba_listener(self):
        with self.assertRaises(self.residue.RuntimeResidueError):
            self.residue.validate_runtime_residue(
                20050, "22 20050 mGBA\n", "", lsof_exit_code=1
            )
        with self.assertRaises(self.residue.RuntimeResidueError):
            self.residue.validate_runtime_residue(
                20050, "", "p22\ncmGBA\nn*:2345\n", lsof_exit_code=0
            )

    def test_rejects_invalid_pgid_malformed_ps_and_lsof_failure(self):
        for pgid in (0, -1, True, "20050"):
            with self.subTest(pgid=pgid), self.assertRaises(
                self.residue.RuntimeResidueError
            ):
                self.residue.validate_runtime_residue(
                    pgid, "", "", lsof_exit_code=1
                )
        with self.assertRaisesRegex(self.residue.RuntimeResidueError, "ps"):
            self.residue.validate_runtime_residue(
                20050, "malformed\n", "", lsof_exit_code=1
            )
        with self.assertRaisesRegex(self.residue.RuntimeResidueError, "lsof"):
            self.residue.validate_runtime_residue(
                20050, "", "permission denied", lsof_exit_code=2
            )

    def test_probe_is_read_only_and_fail_closed(self):
        responses = [
            subprocess.CompletedProcess(
                ["ps"], 0, stdout="  10 999 Python\n", stderr=""
            ),
            subprocess.CompletedProcess(["lsof"], 1, stdout="", stderr=""),
        ]
        with mock.patch.object(
            self.residue.subprocess, "run", side_effect=responses
        ) as run:
            result = self.residue.probe_runtime_residue(20050)
        self.assertTrue(result["pgid_clean"])
        self.assertIn("checked_at", result)
        self.assertEqual(run.call_count, 2)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0], ["ps", "-axo", "pid=,pgid=,comm="])
        self.assertEqual(
            commands[1],
            [
                "lsof",
                "-nP",
                "-iTCP",
                "-sTCP:LISTEN",
                "-a",
                "-c",
                "mGBA",
                "-Fpcn",
            ],
        )
        self.assertFalse(any(command[0] in ("kill", "pkill", "killall") for command in commands))

        with mock.patch.object(
            self.residue.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["ps"], 5),
        ):
            with self.assertRaisesRegex(self.residue.RuntimeResidueError, "ps"):
                self.residue.probe_runtime_residue(20050)


if __name__ == "__main__":
    unittest.main()
