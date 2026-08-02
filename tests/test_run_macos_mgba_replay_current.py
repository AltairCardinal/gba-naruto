from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "tools/run_macos_mgba_replay.py"


class CurrentZeroInputRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = importlib.import_module("tools.run_macos_mgba_replay_current")

    def test_keeps_the_historical_runner_byte_identical(self):
        self.assertEqual(
            hashlib.sha256(LEGACY.read_bytes()).hexdigest(),
            "44a117c53d272cbac8a62beb749d331927e4f3f043c20f3eb78681ceb7591bbc",
        )

    def test_parser_is_zero_input_and_current_toolchain_only(self):
        parser = self.runner.build_parser()
        help_text = parser.format_help()
        self.assertIn("--toolchain-profile", help_text)
        for forbidden in (
            "--build-manifest",
            "--expected-build-manifest-sha256",
            "--pre-script",
            "--replay-script",
            "--evidence-mode",
        ):
            self.assertNotIn(forbidden, help_text)
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser.parse_args([forbidden, "forbidden"])

    def test_readme_example_uses_the_accepted_profile_binary_hash(self):
        profile = json.loads(
            (ROOT / "artifacts/rom-expansion-profile-v1/profile.json").read_text(
                encoding="utf-8"
            )
        )
        expected = profile["hardware_evidence"]["mgba_binary_sha256"]
        readme = (ROOT / "tools/README.md").read_text(encoding="utf-8")
        self.assertIn(f"--expected-binary-sha256 {expected}", readme)

    def _fixture(self, root: Path):
        runner = self.runner
        binary = root / "mGBA"
        binary.write_bytes(b"current-desktop-mgba")
        os.chmod(binary, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        binary_sha = runner.sha256_file(binary)
        profile = root / "profile.json"
        profile.write_text(
            json.dumps(
                {
                    "schema": "rom-expansion-profile-v1",
                    "identity": "agb_standard_16mib_sequel_rom_profile",
                    "hardware_evidence": {
                        "mgba_source_commit": runner.CURRENT_MGBA_SOURCE_COMMIT,
                        "mgba_binary_sha256": binary_sha,
                    },
                    "runtime_probe": {
                        "guard_reason": "completed",
                        "guard_completion_trigger": "success-marker",
                        "guard_exit_code": 0,
                        "guard_degraded": False,
                        "new_mgba_crash_report": False,
                        "owned_process_residue": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        source = root / "source"
        source.mkdir()
        rom = source / "base.gba"
        state = source / "input.ss9"
        rom.write_bytes(b"rom")
        state.write_bytes(b"state")
        out = root / "out"
        paths = {
            "binary": binary,
            "profile": profile,
            "rom": rom,
            "input_state": state,
            "staged": out / "staged.gba",
            "staged_save": out / "staged.sav",
            "state": out / "after.ss9",
            "png": out / "after.png",
            "audit": out / "audit.json",
            "sentinel": out / "sentinel.json",
            "summary": out / "guard.json",
            "marker": out / "guard.json.done.json",
            "finalization_marker": out / "audit.json.finalized.json",
        }
        argv = [
            "--binary", str(binary),
            "--toolchain-profile", str(profile),
            "--expected-binary-sha256", binary_sha,
            "--rom", str(rom),
            "--state", str(state),
            "--expected-rom-sha256", runner.sha256_file(rom),
            "--expected-state-sha256", runner.sha256_file(state),
            "--capture-frame", "600",
            "--staged-rom", str(paths["staged"]),
            "--output-state", str(paths["state"]),
            "--output-png", str(paths["png"]),
            "--audit", str(paths["audit"]),
            "--sentinel", str(paths["sentinel"]),
            "--guard-summary", str(paths["summary"]),
        ]
        return paths, argv

    def _fake_wrapper(self, paths, *, mutate=None):
        runner = self.runner

        def run(command, **kwargs):
            env = kwargs["env"]
            child = command[command.index("--") + 1 :]
            self.assertEqual(
                child,
                [
                    str(paths["binary"].resolve()),
                    "--script",
                    str(runner.DEFAULT_REPLAY_SCRIPT.resolve()),
                    str(paths["staged"].resolve()),
                ],
            )
            self.assertEqual(env["QT_QPA_PLATFORM"], "offscreen")
            self.assertEqual(env["MGBA_REPLAY_CAPTURE_FRAME"], "600")
            self.assertFalse(paths["staged_save"].exists())
            payload = {
                "run_id": env["MGBA_REPLAY_RUN_ID"],
                "frame": 600,
                "capture_frame": 600,
                "inputs": [],
                "success": True,
                "status": "capture-complete",
                "input_state": str(paths["input_state"].resolve()),
                "output_state": str(paths["state"].resolve()),
                "output_png": str(paths["png"].resolve()),
                "audit": str(paths["audit"].resolve()),
                "sentinel": str(paths["sentinel"].resolve()),
                "rom_sha256": runner.sha256_file(paths["rom"]),
                "input_state_sha256": runner.sha256_file(paths["input_state"]),
            }
            for name in ("state", "png"):
                paths[name].write_bytes(b"\x89PNG\r\n\x1a\nnew")
            paths["audit"].write_text(json.dumps(payload), encoding="utf-8")
            paths["sentinel"].write_text(json.dumps(payload), encoding="utf-8")
            paths["marker"].write_text(
                json.dumps(
                    {
                        "run_id": env["MGBA_REPLAY_RUN_ID"],
                        "capture_frame": 600,
                        "status": "capture-complete",
                    }
                ),
                encoding="utf-8",
            )
            paths["summary"].write_text(
                json.dumps(
                    {
                        "reason": "completed",
                        "exit_code": 0,
                        "child_pid": 987,
                        "peak_tree_rss_mib": 12.5,
                        "protection_backend": "posix-process-group",
                        "degraded": False,
                        "completion_trigger": "success-marker",
                        "command": child,
                    }
                ),
                encoding="utf-8",
            )
            if mutate is not None:
                mutate()
            return subprocess.CompletedProcess(command, 0)

        return run

    def test_main_wires_zero_input_current_profile_residue_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, argv = self._fixture(Path(tmp))
            profile_sha = self.runner.sha256_file(paths["profile"])
            clean = {
                "checked_pgid": 987,
                "pgid_clean": True,
                "mgba_listener_clean": True,
            }
            with mock.patch.object(
                self.runner.subprocess,
                "run",
                side_effect=self._fake_wrapper(paths),
            ), mock.patch.object(
                self.runner, "read_ps_snapshot", return_value="1 1\n"
            ), mock.patch.object(
                self.runner, "probe_runtime_residue", return_value=clean
            ) as residue, mock.patch.object(
                self.runner, "CURRENT_TOOLCHAIN_PROFILE_SHA256", profile_sha
            ), redirect_stdout(io.StringIO()):
                self.assertEqual(self.runner.main(argv), 0)
            residue.assert_called_once_with(987)
            finalized = json.loads(paths["audit"].read_text(encoding="utf-8"))
            self.assertEqual(finalized["inputs"], [])
            self.assertEqual(finalized["evidence_mode"], "zero-input")
            self.assertIs(finalized["zero_input_verified"], True)
            self.assertEqual(finalized["runtime_residue"], clean)
            self.assertEqual(
                finalized["toolchain"],
                {
                    "kind": "current-desktop-runtime-profile",
                    "path": str(paths["profile"].resolve()),
                    "sha256": profile_sha,
                    "source_commit": self.runner.CURRENT_MGBA_SOURCE_COMMIT,
                    "patch_sha256": None,
                },
            )
            self.assertNotIn("build_manifest", finalized)
            self.assertNotIn("pre_scripts", finalized)
            self.assertNotIn("patch_sha256", finalized)
            marker = json.loads(
                paths["finalization_marker"].read_text(encoding="utf-8")
            )
            self.assertEqual(marker["status"], "finalized")
            self.assertEqual(marker["run_id"], finalized["run_id"])
            self.assertEqual(
                marker["audit_sha256"], self.runner.sha256_file(paths["audit"])
            )
            self.assertEqual(
                marker["sentinel_sha256"],
                self.runner.sha256_file(paths["sentinel"]),
            )

    def test_source_save_fails_before_output_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, argv = self._fixture(Path(tmp))
            paths["audit"].parent.mkdir(parents=True)
            paths["audit"].write_text("must-survive", encoding="utf-8")
            paths["rom"].with_suffix(".sav").write_bytes(b"source-save")
            with self.assertRaisesRegex(self.runner.ReplayError, "source ROM save"):
                self.runner.main(argv)
            self.assertEqual(
                paths["audit"].read_text(encoding="utf-8"), "must-survive"
            )

    def test_post_run_source_save_fails_without_finalizing(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, argv = self._fixture(Path(tmp))
            profile_sha = self.runner.sha256_file(paths["profile"])

            def create_source_save():
                paths["rom"].with_suffix(".sav").write_bytes(b"runtime-save")

            clean = {"pgid_clean": True, "mgba_listener_clean": True}
            with mock.patch.object(
                self.runner.subprocess,
                "run",
                side_effect=self._fake_wrapper(paths, mutate=create_source_save),
            ), mock.patch.object(
                self.runner, "read_ps_snapshot", return_value="1 1\n"
            ), mock.patch.object(
                self.runner, "probe_runtime_residue", return_value=clean
            ), mock.patch.object(
                self.runner, "CURRENT_TOOLCHAIN_PROFILE_SHA256", profile_sha
            ):
                with self.assertRaisesRegex(self.runner.ReplayError, "source ROM save"):
                    self.runner.main(argv)
            raw = json.loads(paths["audit"].read_text(encoding="utf-8"))
            self.assertNotIn("zero_input_verified", raw)
            self.assertFalse(paths["finalization_marker"].exists())

    def test_post_run_staged_save_is_hashed_removed_and_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, argv = self._fixture(Path(tmp))
            profile_sha = self.runner.sha256_file(paths["profile"])
            save_raw = b"runtime-staged-save"

            def create_staged_save():
                paths["staged_save"].write_bytes(save_raw)

            clean = {"pgid_clean": True, "mgba_listener_clean": True}
            with mock.patch.object(
                self.runner.subprocess,
                "run",
                side_effect=self._fake_wrapper(paths, mutate=create_staged_save),
            ), mock.patch.object(
                self.runner, "read_ps_snapshot", return_value="1 1\n"
            ), mock.patch.object(
                self.runner, "probe_runtime_residue", return_value=clean
            ), mock.patch.object(
                self.runner, "CURRENT_TOOLCHAIN_PROFILE_SHA256", profile_sha
            ), redirect_stdout(io.StringIO()):
                self.assertEqual(self.runner.main(argv), 0)
            self.assertFalse(paths["staged_save"].exists())
            finalized = json.loads(paths["audit"].read_text(encoding="utf-8"))
            self.assertEqual(
                finalized["staged_save_sidecar"],
                {
                    "created": True,
                    "path": str(paths["staged_save"].resolve()),
                    "removed": True,
                    "sha256": hashlib.sha256(save_raw).hexdigest(),
                    "size": len(save_raw),
                },
            )

    def test_finalize_failure_rolls_back_both_payloads_and_has_no_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, argv = self._fixture(Path(tmp))
            profile_sha = self.runner.sha256_file(paths["profile"])
            clean = {"pgid_clean": True, "mgba_listener_clean": True}
            original_replace = self.runner._replace_file
            failed = False

            def fail_first_sentinel_replace(source, target):
                nonlocal failed
                if Path(target) == paths["sentinel"].resolve() and not failed:
                    failed = True
                    raise OSError("synthetic sentinel replace failure")
                return original_replace(source, target)

            with mock.patch.object(
                self.runner.subprocess,
                "run",
                side_effect=self._fake_wrapper(paths),
            ), mock.patch.object(
                self.runner, "read_ps_snapshot", return_value="1 1\n"
            ), mock.patch.object(
                self.runner, "probe_runtime_residue", return_value=clean
            ), mock.patch.object(
                self.runner, "CURRENT_TOOLCHAIN_PROFILE_SHA256", profile_sha
            ), mock.patch.object(
                self.runner,
                "_replace_file",
                side_effect=fail_first_sentinel_replace,
            ):
                with self.assertRaisesRegex(self.runner.ReplayError, "finalize"):
                    self.runner.main(argv)

            for payload_path in (paths["audit"], paths["sentinel"]):
                raw = json.loads(payload_path.read_text(encoding="utf-8"))
                self.assertNotIn("zero_input_verified", raw)
                self.assertNotIn("toolchain", raw)
            self.assertFalse(paths["finalization_marker"].exists())

    def test_second_staging_failure_leaves_no_temporary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, argv = self._fixture(Path(tmp))
            profile_sha = self.runner.sha256_file(paths["profile"])
            clean = {"pgid_clean": True, "mgba_listener_clean": True}
            original_stage = self.runner._stage_bytes
            call_count = 0

            def fail_second_stage(target, raw):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("synthetic second staging failure")
                return original_stage(target, raw)

            with mock.patch.object(
                self.runner.subprocess,
                "run",
                side_effect=self._fake_wrapper(paths),
            ), mock.patch.object(
                self.runner, "read_ps_snapshot", return_value="1 1\n"
            ), mock.patch.object(
                self.runner, "probe_runtime_residue", return_value=clean
            ), mock.patch.object(
                self.runner, "CURRENT_TOOLCHAIN_PROFILE_SHA256", profile_sha
            ), mock.patch.object(
                self.runner, "_stage_bytes", side_effect=fail_second_stage
            ):
                with self.assertRaisesRegex(self.runner.ReplayError, "finalize"):
                    self.runner.main(argv)

            leftovers = [
                path.name
                for path in paths["audit"].parent.iterdir()
                if path.name.startswith(".") and path.name.endswith(".tmp")
            ]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
