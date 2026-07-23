import argparse
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
LUA = ROOT / "tools" / "mgba_single_input_replay.lua"


class SingleInputLuaContractTests(unittest.TestCase):
    def test_lua_has_one_explicit_input_event_and_one_capture(self):
        text = LUA.read_text(encoding="utf-8")
        self.assertEqual(text.count("emu:addKey"), 1)
        self.assertEqual(text.count("emu:clearKey"), 1)
        self.assertEqual(text.count('callbacks:add("frame"'), 1)
        self.assertEqual(text.count("emu:saveStateFile"), 1)
        self.assertEqual(text.count("emu:screenshot"), 1)
        self.assertIn("C.GBA_KEY.DOWN", text)
        self.assertIn("C.GBA_KEY.A", text)
        self.assertIn("C.GBA_KEY.B", text)
        self.assertIn("L = C.GBA_KEY.L", text)
        self.assertIn("R = C.GBA_KEY.R", text)
        self.assertIn("Up = C.GBA_KEY.UP", text)
        self.assertIn("Right = C.GBA_KEY.RIGHT", text)
        self.assertIn("Left = C.GBA_KEY.LEFT", text)
        for forbidden in (
            "adaptive",
            "settle",
        ):
            self.assertNotIn(forbidden, text.lower() if forbidden.islower() else text)
        for loop in ("while ", "repeat\n", "for "):
            self.assertNotIn(loop, text)
        self.assertIn("down_frame > 0", text)
        self.assertIn("down_frame < up_frame", text)
        self.assertIn("up_frame < capture_frame", text)
        self.assertIn("emu:saveStateFile", text)
        self.assertIn("emu:screenshot", text)
        self.assertIn("write_file(audit_path", text)
        self.assertIn("write_file(sentinel_path", text)
        self.assertNotIn("os.exit", text)
        self.assertIn("capture_complete", text)
        self.assertLess(text.index("write_file(audit_path"), text.index("write_file(done_marker_path"))
        self.assertLess(text.index("write_file(sentinel_path"), text.index("write_file(done_marker_path"))

    def test_lua_uses_only_fixed_environment_contract(self):
        text = LUA.read_text(encoding="utf-8")
        for name in (
            "MGBA_REPLAY_INPUT_STATE",
            "MGBA_REPLAY_OUTPUT_STATE",
            "MGBA_REPLAY_OUTPUT_PNG",
            "MGBA_REPLAY_AUDIT",
            "MGBA_REPLAY_SENTINEL",
            "MGBA_REPLAY_CAPTURE_FRAME",
            "MGBA_REPLAY_RUN_ID",
            "MGBA_REPLAY_ROM_SHA256",
            "MGBA_REPLAY_INPUT_STATE_SHA256",
            "MGBA_REPLAY_DONE_MARKER",
            "MGBA_SINGLE_INPUT_KEY",
            "MGBA_SINGLE_INPUT_DOWN_FRAME",
            "MGBA_SINGLE_INPUT_UP_FRAME",
        ):
            self.assertIn(name, text)
        self.assertIn('"evidence_mode":"single-input"', text)
        self.assertIn('"zero_input_verified":false', text)
        self.assertIn('"automatic_inputs":[]', text)
        self.assertIn('"recovery_inputs":[]', text)


class SingleInputValidationTests(unittest.TestCase):
    def setUp(self):
        self.runner = importlib.import_module("tools.run_macos_mgba_single_input")

    def test_only_closed_single_key_set_and_strict_frame_order(self):
        for key in ("Down+L", "Up+A", ""):
            with self.subTest(key=key), self.assertRaises(self.runner.ReplayError):
                self.runner.validate_single_input(key, 5, 13, 80)
        for frames in ((13, 5, 80), (5, 5, 80), (5, 80, 80), (0, 13, 80)):
            with self.subTest(frames=frames), self.assertRaises(self.runner.ReplayError):
                self.runner.validate_single_input("Down", *frames)
        self.runner.validate_single_input("Down", 5, 13, 80)
        self.runner.validate_single_input("A", 5, 13, 80)
        self.runner.validate_single_input("B", 5, 13, 80)
        self.runner.validate_single_input("L", 5, 13, 80)
        self.runner.validate_single_input("R", 5, 13, 80)
        self.runner.validate_single_input("Up", 5, 13, 80)
        self.runner.validate_single_input("Right", 5, 13, 80)
        self.runner.validate_single_input("Left", 5, 13, 80)

    def test_right_payload_has_one_exact_explicit_event(self):
        payload = {
            "evidence_mode": "single-input",
            "zero_input_verified": False,
            "inputs": [
                {"key": "Right", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
            ],
            "automatic_inputs": [],
            "recovery_inputs": [],
            "frame": 80,
            "capture_frame": 80,
        }
        self.runner.validate_single_input_payload(
            payload, key="Right", down_frame=5, up_frame=13, capture_frame=80
        )
        self.assertIn("Right", self.runner.__doc__)
        self.assertIn("Right", self.runner.build_parser().format_help())

    def test_up_payload_has_one_exact_explicit_event_and_closed_set_help(self):
        payload = {
            "evidence_mode": "single-input",
            "zero_input_verified": False,
            "inputs": [
                {"key": "Up", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
            ],
            "automatic_inputs": [],
            "recovery_inputs": [],
            "frame": 80,
            "capture_frame": 80,
        }
        self.runner.validate_single_input_payload(
            payload, key="Up", down_frame=5, up_frame=13, capture_frame=80
        )
        self.assertIn("Down, Up, Left, Right, A, B, L, R, or Start", self.runner.__doc__)
        self.assertIn("Down, Up, Left, Right, A, B, L, R, or Start", self.runner.build_parser().format_help())

    def test_l_payload_has_one_explicit_event_and_closed_set_help(self):
        payload = {
            "evidence_mode": "single-input",
            "zero_input_verified": False,
            "inputs": [
                {"key": "L", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
            ],
            "automatic_inputs": [],
            "recovery_inputs": [],
            "frame": 80,
            "capture_frame": 80,
        }
        self.runner.validate_single_input_payload(
            payload, key="L", down_frame=5, up_frame=13, capture_frame=80
        )
        self.assertIn("Down, Up, Left, Right, A, B, L, R, or Start", self.runner.__doc__)
        self.assertIn("Down, Up, Left, Right, A, B, L, R, or Start", self.runner.build_parser().format_help())

    def test_r_payload_has_one_explicit_event_and_fixed_lua_mapping(self):
        payload = {
            "evidence_mode": "single-input",
            "zero_input_verified": False,
            "inputs": [
                {"key": "R", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
            ],
            "automatic_inputs": [],
            "recovery_inputs": [],
            "frame": 80,
            "capture_frame": 80,
        }
        self.runner.validate_single_input_payload(
            payload, key="R", down_frame=5, up_frame=13, capture_frame=80
        )
        self.assertIn("R = C.GBA_KEY.R", LUA.read_text(encoding="utf-8"))

    def test_start_payload_is_supported_by_fixed_lua(self):
        payload = {
            "evidence_mode": "single-input",
            "zero_input_verified": False,
            "inputs": [
                {"key": "Start", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
            ],
            "automatic_inputs": [],
            "recovery_inputs": [],
            "frame": 80,
            "capture_frame": 80,
        }
        self.runner.validate_single_input_payload(
            payload, key="Start", down_frame=5, up_frame=13, capture_frame=80
        )
        lua = LUA.read_text(encoding="utf-8")
        self.assertIn("Start = C.GBA_KEY.START", lua)
        self.assertIn("Start", self.runner.__doc__)
        self.assertIn("Start", self.runner.build_parser().format_help())

    def test_single_and_zero_input_lua_hashes_are_pinned_independently(self):
        zero_runner = importlib.import_module("tools.run_macos_mgba_replay")
        self.assertEqual(
            self.runner.sha256_file(LUA),
            self.runner.EXPECTED_SINGLE_INPUT_SCRIPT_SHA256,
        )
        self.assertEqual(
            zero_runner.sha256_file(zero_runner.DEFAULT_REPLAY_SCRIPT),
            "1481f10cd8f72c7635326e8d3233c2466b76c7a4b812cefe1220fe43c29f9659",
        )
        self.assertNotEqual(
            self.runner.EXPECTED_SINGLE_INPUT_SCRIPT_SHA256,
            zero_runner.EXPECTED_REPLAY_SCRIPT_SHA256,
        )

    def test_rejects_bool_float_or_non_integer_frames(self):
        for frames in ((True, 13, 80), (5.0, 13, 80), (5, "13", 80)):
            with self.subTest(frames=frames), self.assertRaises(self.runner.ReplayError):
                self.runner.validate_single_input("Down", *frames)

    def test_payload_has_one_explicit_event_and_no_automatic_inputs(self):
        payload = {
            "evidence_mode": "single-input",
            "zero_input_verified": False,
            "inputs": [
                {"key": "Down", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
            ],
            "automatic_inputs": [],
            "recovery_inputs": [],
            "frame": 80,
            "capture_frame": 80,
        }
        self.runner.validate_single_input_payload(
            payload, key="Down", down_frame=5, up_frame=13, capture_frame=80
        )
        self.assertEqual(
            payload["inputs"],
            [{"key": "Down", "down_frame": 5, "up_frame": 13, "hold_frames": 8}],
        )
        self.assertEqual(payload["automatic_inputs"], [])
        self.assertEqual(payload["recovery_inputs"], [])
        self.assertFalse(payload["zero_input_verified"])

    def test_payload_rejects_second_wrong_or_implicit_event(self):
        good = {
            "evidence_mode": "single-input",
            "zero_input_verified": False,
            "inputs": [
                {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
            ],
            "automatic_inputs": [],
            "recovery_inputs": [],
            "frame": 80,
            "capture_frame": 80,
        }
        mutations = (
            {"inputs": good["inputs"] * 2},
            {"inputs": [{**good["inputs"][0], "key": "B"}]},
            {"inputs": [{**good["inputs"][0], "up_frame": 14}]},
            {"automatic_inputs": ["A"]},
            {"recovery_inputs": ["Down"]},
            {"zero_input_verified": True},
            {"evidence_mode": "zero-input"},
            {"capture_frame": 81},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                payload = {**good, **mutation}
                with self.assertRaises(self.runner.ReplayError):
                    self.runner.validate_single_input_payload(
                        payload,
                        key="A",
                        down_frame=5,
                        up_frame=13,
                        capture_frame=80,
                    )

    def test_cli_has_no_custom_lua_or_pre_script_surface(self):
        parser = self.runner.build_parser()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--pre-script", "/tmp/a.lua"])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--replay-script", "/tmp/a.lua"])


class SingleInputRunnerIntegrationTests(unittest.TestCase):
    def _fixture(self, root: Path):
        runner = importlib.import_module("tools.run_macos_mgba_single_input")
        binary = root / "mGBA"
        binary.write_bytes(b"binary")
        os.chmod(binary, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        binary_sha = runner.sha256_file(binary)
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "label": runner.EXPECTED_LABEL,
                    "version": "0.10.5",
                    "source_commit": runner.SOURCE_COMMIT,
                    "backport_commit": runner.BACKPORT_COMMIT,
                    "patch_sha256": runner.EXPECTED_PATCH_SHA256,
                    "binary_sha256": binary_sha,
                    "architecture": "x86_64",
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
            "manifest": manifest,
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
        }
        argv = [
            "--binary", str(binary),
            "--build-manifest", str(manifest),
            "--expected-build-manifest-sha256", runner.sha256_file(manifest),
            "--expected-binary-sha256", binary_sha,
            "--rom", str(rom),
            "--state", str(state),
            "--expected-rom-sha256", runner.sha256_file(rom),
            "--expected-state-sha256", runner.sha256_file(state),
            "--key", "Down",
            "--down-frame", "5",
            "--up-frame", "13",
            "--capture-frame", "80",
            "--staged-rom", str(paths["staged"]),
            "--output-state", str(paths["state"]),
            "--output-png", str(paths["png"]),
            "--audit", str(paths["audit"]),
            "--sentinel", str(paths["sentinel"]),
            "--guard-summary", str(paths["summary"]),
        ]
        return runner, paths, argv

    def _fake_wrapper(self, runner, paths, *, mutate=None):
        def run(command, **kwargs):
            env = kwargs["env"]
            self.assertEqual(env["QT_QPA_PLATFORM"], "offscreen")
            child = command[command.index("--") + 1 :]
            self.assertEqual(
                child,
                [
                    str(paths["binary"].resolve()),
                    "--script",
                    str(runner.DEFAULT_SINGLE_INPUT_SCRIPT.resolve()),
                    str(paths["staged"].resolve()),
                ],
            )
            self.assertFalse(paths["staged_save"].exists())
            self.assertEqual(paths["staged"].read_bytes(), b"rom")
            self.assertEqual(env["MGBA_SINGLE_INPUT_KEY"], "Down")
            self.assertEqual(env["MGBA_SINGLE_INPUT_DOWN_FRAME"], "5")
            self.assertEqual(env["MGBA_SINGLE_INPUT_UP_FRAME"], "13")
            event = {"key": "Down", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
            payload = {
                "run_id": env["MGBA_REPLAY_RUN_ID"],
                "frame": 80,
                "capture_frame": 80,
                "inputs": [event],
                "automatic_inputs": [],
                "recovery_inputs": [],
                "evidence_mode": "single-input",
                "zero_input_verified": False,
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
            paths["marker"].write_text(json.dumps({
                "run_id": env["MGBA_REPLAY_RUN_ID"],
                "capture_frame": 80,
                "status": "capture-complete",
            }), encoding="utf-8")
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
            if mutate:
                mutate()
            self.assertEqual(env["MGBA_REPLAY_DONE_MARKER"], str(paths["marker"].resolve()))
            self.assertEqual(command[command.index("--success-marker") + 1], str(paths["marker"].resolve()))
            return subprocess.CompletedProcess(command, 0)

        return run

    def test_main_rejects_missing_or_wrong_completion_marker(self):
        cases = (
            ("missing", lambda paths: paths["marker"].unlink()),
            ("wrong-frame", lambda paths: paths["marker"].write_text(json.dumps({
                "run_id": json.loads(paths["audit"].read_text(encoding="utf-8"))["run_id"],
                "capture_frame": 81,
                "status": "capture-complete",
            }), encoding="utf-8")),
        )
        for name, mutate_marker in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                runner, paths, argv = self._fixture(Path(tmp))
                with mock.patch.object(
                    runner.subprocess,
                    "run",
                    side_effect=self._fake_wrapper(
                        runner, paths, mutate=lambda: mutate_marker(paths)
                    ),
                ), mock.patch.object(
                    runner, "read_ps_snapshot", return_value="1 1\n"
                ), mock.patch.object(
                    runner,
                    "probe_runtime_residue",
                    return_value={"pgid_clean": True, "mgba_listener_clean": True},
                ):
                    with self.assertRaises(runner.ReplayError):
                        runner.main(argv)

    def test_main_wires_single_lua_guard_hashes_residue_and_final_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, paths, argv = self._fixture(Path(tmp))
            paths["staged_save"].parent.mkdir(parents=True)
            paths["staged_save"].write_text("stale", encoding="utf-8")
            clean = {"pgid_clean": True, "mgba_listener_clean": True, "checked_pgid": 987}
            with mock.patch.object(
                runner.subprocess, "run", side_effect=self._fake_wrapper(runner, paths)
            ), mock.patch.object(
                runner, "read_ps_snapshot", return_value="1 1\n"
            ), mock.patch.object(
                runner, "probe_runtime_residue", return_value=clean
            ) as probe, redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(argv), 0)
            probe.assert_called_once_with(987)
            final = json.loads(paths["audit"].read_text(encoding="utf-8"))
            self.assertEqual(final["evidence_mode"], "single-input")
            self.assertIs(final["zero_input_verified"], False)
            self.assertEqual(len(final["inputs"]), 1)
            self.assertEqual(final["automatic_inputs"], [])
            self.assertEqual(final["recovery_inputs"], [])
            self.assertEqual(final["runtime_residue"], clean)
            self.assertEqual(final["binary_sha256"], runner.sha256_file(paths["binary"]))
            self.assertEqual(final["patch_sha256"], runner.EXPECTED_PATCH_SHA256)
            self.assertEqual(final["replay_script_sha256"], runner.EXPECTED_SINGLE_INPUT_SCRIPT_SHA256)
            self.assertNotIn("pre_scripts", final)

    def test_post_run_drift_or_residue_failure_does_not_finalize_payload(self):
        cases = ("binary-drift", "residue")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                runner, paths, argv = self._fixture(Path(tmp))
                mutate = (
                    (lambda: paths["binary"].write_bytes(b"drift"))
                    if case == "binary-drift"
                    else None
                )
                probe = (
                    mock.Mock(side_effect=runner.RuntimeResidueError("listener residue"))
                    if case == "residue"
                    else mock.Mock(return_value={"pgid_clean": True, "mgba_listener_clean": True})
                )
                with mock.patch.object(
                    runner.subprocess,
                    "run",
                    side_effect=self._fake_wrapper(runner, paths, mutate=mutate),
                ), mock.patch.object(
                    runner, "read_ps_snapshot", return_value="1 1\n"
                ), mock.patch.object(runner, "probe_runtime_residue", probe):
                    with self.assertRaises((runner.ReplayError, runner.RuntimeResidueError)):
                        runner.main(argv)
                raw = json.loads(paths["audit"].read_text(encoding="utf-8"))
                self.assertNotIn("build_manifest_sha256", raw)
                self.assertNotIn("runtime_residue", raw)

    def test_post_run_source_save_creation_fails_without_finalizing_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, paths, argv = self._fixture(Path(tmp))

            def create_source_save():
                paths["rom"].with_suffix(".sav").write_text(
                    "runtime-source-save", encoding="utf-8"
                )

            clean = {"pgid_clean": True, "mgba_listener_clean": True}
            with mock.patch.object(
                runner.subprocess,
                "run",
                side_effect=self._fake_wrapper(
                    runner, paths, mutate=create_source_save
                ),
            ), mock.patch.object(
                runner, "read_ps_snapshot", return_value="1 1\n"
            ), mock.patch.object(
                runner, "probe_runtime_residue", return_value=clean
            ):
                with self.assertRaisesRegex(runner.ReplayError, "source ROM save"):
                    runner.main(argv)

            for payload_path in (paths["audit"], paths["sentinel"]):
                raw = json.loads(payload_path.read_text(encoding="utf-8"))
                self.assertNotIn("build_manifest_sha256", raw)
                self.assertNotIn("runtime_residue", raw)

    def test_guard_failure_does_not_finalize(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, paths, argv = self._fixture(Path(tmp))

            def failed(command, **kwargs):
                child = command[command.index("--") + 1 :]
                paths["summary"].parent.mkdir(parents=True, exist_ok=True)
                paths["summary"].write_text(
                    json.dumps(
                        {
                            "reason": "memory-limit",
                            "exit_code": 125,
                            "child_pid": 987,
                            "peak_tree_rss_mib": 1600,
                            "protection_backend": "posix-process-group",
                            "degraded": False,
                            "command": child,
                        }
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 125)

            with mock.patch.object(runner.subprocess, "run", side_effect=failed):
                with self.assertRaises(runner.ReplayError):
                    runner.main(argv)
            self.assertFalse(paths["audit"].exists())

    def test_repeated_key_or_source_rom_save_fails_before_output_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, paths, argv = self._fixture(Path(tmp))
            paths["audit"].parent.mkdir(parents=True)
            paths["audit"].write_text("must-survive", encoding="utf-8")
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.build_parser().parse_args([*argv, "--key", "A"])
            self.assertEqual(paths["audit"].read_text(encoding="utf-8"), "must-survive")

            paths["rom"].with_suffix(".sav").write_text("source-save", encoding="utf-8")
            with self.assertRaisesRegex(runner.ReplayError, "source ROM.*save"):
                runner.validate_args(runner.build_parser().parse_args(argv))
            self.assertEqual(paths["audit"].read_text(encoding="utf-8"), "must-survive")


if __name__ == "__main__":
    unittest.main()
