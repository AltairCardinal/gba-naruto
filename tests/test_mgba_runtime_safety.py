import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class MgbaRuntimeSafetyTests(unittest.TestCase):
    def setUp(self):
        from tools import mgba_runtime_safety

        self.safety = mgba_runtime_safety

    def test_non_mgba_command_has_no_launch_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(
                self.safety.prepare_mgba_launch(
                    ["python3", "-c", "print('ok')"],
                    crash_dir=root / "reports",
                    latch_path=root / "latch.json",
                )
            )

    def test_mgba_rejects_dangerous_actual_lua_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "replay.lua"
            reports = root / "reports"
            reports.mkdir()
            for payload in (
                "callbacks:add('frame', function() os.exit(0) end)",
                "os.execute('kill -9 123')",
                "local quit = os['exit']; quit(0)",
                "local o = os; o.exit(0)",
                "_G['os']['exit'](0)",
                "local i = io; i.popen('kill -9 123')",
                "local f = ffi; f.C.exit(0)",
                "local p = posix; p.kill(123)",
                "ffi.C.exit(0)",
            ):
                with self.subTest(payload=payload):
                    script.write_text(payload, encoding="utf-8")
                    with self.assertRaisesRegex(
                        self.safety.MgbaSafetyError, "dangerous Lua"
                    ):
                        self.safety.prepare_mgba_launch(
                            ["/Applications/mGBA.app/Contents/MacOS/mGBA", "--script", str(script), "game.gba"],
                            crash_dir=reports,
                            latch_path=root / "latch.json",
                        )

    def test_mgba_allows_fixed_script_and_snapshots_existing_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "replay.lua"
            script.write_text("callbacks:add('frame', function() return end)", encoding="utf-8")
            reports = root / "reports"
            reports.mkdir()
            old = reports / "mGBA-2026-07-19-000000.ips"
            old.write_text("old", encoding="utf-8")
            audit = self.safety.prepare_mgba_launch(
                ["mGBA", "--script=" + str(script), "game.gba"],
                crash_dir=reports,
                latch_path=root / "latch.json",
                settle_timeout_s=0,
            )
            self.assertIsNotNone(audit)
            self.assertIn(str(old.resolve()), audit.crash_reports_before)

    def test_late_crash_report_is_rejected_before_the_next_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            latch = root / "latch.json"
            summary = root / "summary.json"
            summary.write_text('{"reason":"completed","exit_code":0}', encoding="utf-8")
            first = self.safety.prepare_mgba_launch(
                ["mGBA", "game.gba"],
                crash_dir=reports,
                latch_path=latch,
                settle_timeout_s=0,
            )
            self.assertEqual(self.safety.finish_mgba_launch(first, summary, 0), 0)
            (reports / "mGBA-late.ips").write_text("late", encoding="utf-8")

            with self.assertRaisesRegex(self.safety.MgbaSafetyError, "unacknowledged"):
                self.safety.prepare_mgba_launch(
                    ["mGBA", "game.gba"],
                    crash_dir=reports,
                    latch_path=latch,
                    settle_timeout_s=0,
                )
            self.assertTrue(latch.exists())

    def test_crash_report_scan_error_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            with mock.patch.object(self.safety.os, "scandir", side_effect=OSError("denied")):
                with self.assertRaisesRegex(self.safety.MgbaSafetyError, "cannot inspect"):
                    self.safety.prepare_mgba_launch(
                        ["mGBA", "game.gba"],
                        crash_dir=reports,
                        latch_path=root / "latch.json",
                    )

    def test_existing_latch_rejects_mgba_but_not_other_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            latch = root / "latch.json"
            latch.write_text('{"reason":"previous-crash"}', encoding="utf-8")
            with self.assertRaisesRegex(self.safety.MgbaSafetyError, "latched"):
                self.safety.prepare_mgba_launch(
                    ["mGBA", "game.gba"], crash_dir=reports, latch_path=latch
                )
            self.assertIsNone(
                self.safety.prepare_mgba_launch(
                    ["python3", "job.py"], crash_dir=reports, latch_path=latch
                )
            )

    def test_new_crash_report_overrides_success_marker_and_writes_latch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            latch = root / "latch.json"
            summary = root / "summary.json"
            summary.write_text(
                json.dumps(
                    {
                        "reason": "completed",
                        "exit_code": 0,
                        "completion_trigger": "success-marker",
                    }
                ),
                encoding="utf-8",
            )
            audit = self.safety.prepare_mgba_launch(
                ["mGBA", "game.gba"],
                crash_dir=reports,
                latch_path=latch,
                settle_timeout_s=0,
            )
            crash = reports / "mGBA-2026-07-19-123456.ips"
            crash.write_text("crash", encoding="utf-8")

            self.assertEqual(
                self.safety.finish_mgba_launch(audit, summary, 0), 125
            )
            rewritten = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(rewritten["reason"], "mgba-crash-report")
            self.assertEqual(rewritten["exit_code"], 125)
            self.assertEqual(rewritten["pre_crash_reason"], "completed")
            self.assertEqual(rewritten["pre_crash_exit_code"], 0)
            self.assertTrue(latch.exists())
            self.assertEqual(
                json.loads(latch.read_text(encoding="utf-8"))["reports"][0]["path"],
                str(crash.resolve()),
            )

    def test_explicit_clear_removes_latch_and_appends_audit_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            latch = root / "mgba-crash-latch.json"
            latch.write_text('{"reason":"mgba-crash-report"}', encoding="utf-8")
            self.safety.clear_crash_latch(latch, reports)
            self.assertFalse(latch.exists())
            history = Path(f"{latch}.history.jsonl")
            event = json.loads(history.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(event["action"], "clear")
            self.assertEqual(event["previous"]["reason"], "mgba-crash-report")


if __name__ == "__main__":
    unittest.main()
