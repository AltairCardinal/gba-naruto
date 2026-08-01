from __future__ import annotations

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
LUA = ROOT / "tools/mgba_input_sequence_replay.lua"


class InputSequenceLuaContractTests(unittest.TestCase):
    def test_lua_replays_only_the_explicit_schedule_and_captures_once(self):
        source = LUA.read_text(encoding="utf-8")
        for name in (
            "MGBA_REPLAY_INPUT_STATE",
            "MGBA_REPLAY_OUTPUT_STATE",
            "MGBA_REPLAY_OUTPUT_PNG",
            "MGBA_REPLAY_AUDIT",
            "MGBA_REPLAY_SENTINEL",
            "MGBA_REPLAY_CAPTURE_FRAME",
            "MGBA_INPUT_SEQUENCE_SCHEDULE",
        ):
            self.assertIn(name, source)
        self.assertIn("emu:addKey", source)
        self.assertIn("emu:clearKey", source)
        self.assertIn("emu:loadStateFile", source)
        self.assertIn("emu:saveStateFile", source)
        self.assertNotIn("os.exit", source)


class InputSequenceRunnerContractTests(unittest.TestCase):
    def setUp(self):
        self.runner = importlib.import_module(
            "tools.run_macos_mgba_input_sequence"
        )

    def test_parses_and_validates_nonoverlapping_ordered_events(self):
        events = self.runner.parse_input_events(
            ["A:5:13", "Down:120:128", "Start:200:208"],
            capture_frame=240,
        )
        self.assertEqual(
            events,
            [
                {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8},
                {
                    "key": "Down",
                    "down_frame": 120,
                    "up_frame": 128,
                    "hold_frames": 8,
                },
                {
                    "key": "Start",
                    "down_frame": 200,
                    "up_frame": 208,
                    "hold_frames": 8,
                },
            ],
        )

    def test_rejects_unknown_overlapping_or_out_of_range_events(self):
        cases = (
            (["Select:5:13"], 80),
            (["A:0:13"], 80),
            (["A:13:5"], 80),
            (["A:5:13", "B:12:20"], 80),
            (["A:5:80"], 80),
            (["A:5:true"], 80),
            ([], 80),
        )
        for raw, capture in cases:
            with self.subTest(raw=raw), self.assertRaises(
                self.runner.ReplayError
            ):
                self.runner.parse_input_events(raw, capture)

    def test_payload_binds_every_explicit_event_and_no_hidden_inputs(self):
        events = self.runner.parse_input_events(
            ["A:5:13", "Down:40:48"], 80
        )
        payload = {
            "evidence_mode": "input-sequence",
            "zero_input_verified": False,
            "inputs": events,
            "automatic_inputs": [],
            "recovery_inputs": [],
            "frame": 80,
            "capture_frame": 80,
        }
        self.runner.validate_input_sequence_payload(
            payload,
            events=events,
            capture_frame=80,
        )
        for mutation in (
            {"inputs": events[:-1]},
            {"automatic_inputs": ["A"]},
            {"recovery_inputs": ["B"]},
            {"evidence_mode": "single-input"},
            {"capture_frame": 81},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(
                self.runner.ReplayError
            ):
                self.runner.validate_input_sequence_payload(
                    {**payload, **mutation},
                    events=events,
                    capture_frame=80,
                )

    def test_schedule_encoding_round_trips_without_json_or_shell_parsing(self):
        events = self.runner.parse_input_events(
            ["A:5:13", "Right:120:128"], 160
        )
        encoded = self.runner.encode_schedule(events)
        self.assertEqual("A:5:13,Right:120:128", encoded)

    def test_fixed_lua_hash_is_pinned(self):
        self.assertEqual(
            self.runner.sha256_file(LUA),
            self.runner.EXPECTED_INPUT_SEQUENCE_SCRIPT_SHA256,
        )

    def test_cli_does_not_expose_custom_lua_or_pre_scripts(self):
        parser = self.runner.build_parser()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--pre-script", "/tmp/a.lua"])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--replay-script", "/tmp/a.lua"])

    def test_parser_requires_exactly_one_toolchain_provenance_mode(self):
        parser = self.runner.build_parser()
        common = [
            "--binary", "mGBA",
            "--expected-binary-sha256", "0" * 64,
            "--rom", "base.gba",
            "--state", "input.ss9",
            "--expected-rom-sha256", "1" * 64,
            "--expected-state-sha256", "2" * 64,
            "--input-event", "A:5:13",
            "--capture-frame", "20",
            "--staged-rom", "staged.gba",
            "--output-state", "after.ss9",
            "--output-png", "after.png",
            "--audit", "audit.json",
            "--sentinel", "sentinel.json",
            "--guard-summary", "guard.json",
        ]
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(common)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(
                common
                + [
                    "--toolchain-profile", "runtime-profile.json",
                    "--build-manifest", "legacy-manifest.json",
                ]
            )
        current = parser.parse_args(
            common + ["--toolchain-profile", "runtime-profile.json"]
        )
        legacy = parser.parse_args(
            common
            + [
                "--build-manifest", "legacy-manifest.json",
                "--expected-build-manifest-sha256", "3" * 64,
            ]
        )
        self.assertEqual(current.toolchain_profile, Path("runtime-profile.json"))
        self.assertIsNone(current.build_manifest)
        self.assertEqual(legacy.build_manifest, Path("legacy-manifest.json"))
        self.assertIsNone(legacy.toolchain_profile)

    def test_current_profile_mode_validates_and_records_pinned_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "mGBA"
            binary.write_bytes(b"current-desktop-mgba")
            os.chmod(binary, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            binary_sha = self.runner.sha256_file(binary)
            profile = root / "runtime-profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema": "rom-expansion-profile-v1",
                        "identity": "agb_standard_16mib_sequel_rom_profile",
                        "hardware_evidence": {
                            "mgba_source_commit": self.runner.CURRENT_MGBA_SOURCE_COMMIT,
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
            rom = root / "source" / "base.gba"
            state = root / "source" / "input.ss9"
            rom.parent.mkdir()
            rom.write_bytes(b"rom")
            state.write_bytes(b"state")
            out = root / "out"
            argv = [
                "--binary", str(binary),
                "--toolchain-profile", str(profile),
                "--expected-binary-sha256", binary_sha,
                "--rom", str(rom),
                "--state", str(state),
                "--expected-rom-sha256", self.runner.sha256_file(rom),
                "--expected-state-sha256", self.runner.sha256_file(state),
                "--input-event", "A:5:13",
                "--capture-frame", "20",
                "--staged-rom", str(out / "staged.gba"),
                "--output-state", str(out / "after.ss9"),
                "--output-png", str(out / "after.png"),
                "--audit", str(out / "audit.json"),
                "--sentinel", str(out / "sentinel.json"),
                "--guard-summary", str(out / "guard.json"),
            ]
            profile_sha = self.runner.sha256_file(profile)
            with mock.patch.object(
                self.runner, "CURRENT_TOOLCHAIN_PROFILE_SHA256", profile_sha
            ):
                args = self.runner.validate_args(
                    self.runner.build_parser().parse_args(argv)
                )
            self.assertEqual(args.toolchain_kind, "current-desktop-runtime-profile")
            self.assertEqual(args.toolchain_artifact, profile.resolve())
            self.assertEqual(args.toolchain_artifact_sha256, profile_sha)
            self.assertIsNone(args.toolchain_patch_sha256)


class InputSequenceRunnerIntegrationTests(unittest.TestCase):
    def test_main_wires_exact_schedule_guard_and_finalized_evidence(self):
        runner = importlib.import_module("tools.run_macos_mgba_input_sequence")
        replay = importlib.import_module("tools.run_macos_mgba_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "mGBA"
            binary.write_bytes(b"binary")
            os.chmod(binary, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            binary_sha = runner.sha256_file(binary)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "label": replay.EXPECTED_LABEL,
                        "version": "0.10.5",
                        "source_commit": replay.SOURCE_COMMIT,
                        "backport_commit": replay.BACKPORT_COMMIT,
                        "patch_sha256": replay.EXPECTED_PATCH_SHA256,
                        "binary_sha256": binary_sha,
                        "architecture": "x86_64",
                    }
                ),
                encoding="utf-8",
            )
            source = root / "source"
            source.mkdir()
            rom = source / "base.gba"
            input_state = source / "input.ss9"
            rom.write_bytes(b"rom")
            input_state.write_bytes(b"state")
            out = root / "out"
            paths = {
                "staged": out / "staged.gba",
                "staged_save": out / "staged.sav",
                "state": out / "after.ss9",
                "png": out / "after.png",
                "audit": out / "audit.json",
                "sentinel": out / "sentinel.json",
                "summary": out / "guard.json",
                "marker": out / "guard.json.done.json",
            }
            paths["staged_save"].parent.mkdir(parents=True)
            paths["staged_save"].write_text("stale", encoding="utf-8")
            argv = [
                "--binary", str(binary),
                "--build-manifest", str(manifest),
                "--expected-build-manifest-sha256", runner.sha256_file(manifest),
                "--expected-binary-sha256", binary_sha,
                "--rom", str(rom),
                "--state", str(input_state),
                "--expected-rom-sha256", runner.sha256_file(rom),
                "--expected-state-sha256", runner.sha256_file(input_state),
                "--input-event", "A:5:13",
                "--input-event", "Down:120:128",
                "--capture-frame", "160",
                "--staged-rom", str(paths["staged"]),
                "--output-state", str(paths["state"]),
                "--output-png", str(paths["png"]),
                "--audit", str(paths["audit"]),
                "--sentinel", str(paths["sentinel"]),
                "--guard-summary", str(paths["summary"]),
            ]
            expected_events = [
                {
                    "key": "A",
                    "down_frame": 5,
                    "up_frame": 13,
                    "hold_frames": 8,
                },
                {
                    "key": "Down",
                    "down_frame": 120,
                    "up_frame": 128,
                    "hold_frames": 8,
                },
            ]

            def fake_run(command, **kwargs):
                env = kwargs["env"]
                child = command[command.index("--") + 1 :]
                self.assertEqual(
                    child,
                    [
                        str(binary.resolve()),
                        "--script",
                        str(runner.DEFAULT_INPUT_SEQUENCE_SCRIPT.resolve()),
                        str(paths["staged"].resolve()),
                    ],
                )
                self.assertEqual(
                    env["MGBA_INPUT_SEQUENCE_SCHEDULE"],
                    "A:5:13,Down:120:128",
                )
                self.assertFalse(paths["staged_save"].exists())
                payload = {
                    "run_id": env["MGBA_REPLAY_RUN_ID"],
                    "frame": 160,
                    "capture_frame": 160,
                    "inputs": expected_events,
                    "automatic_inputs": [],
                    "recovery_inputs": [],
                    "evidence_mode": "input-sequence",
                    "zero_input_verified": False,
                    "success": True,
                    "status": "capture-complete",
                    "input_state": str(input_state.resolve()),
                    "output_state": str(paths["state"].resolve()),
                    "output_png": str(paths["png"].resolve()),
                    "audit": str(paths["audit"].resolve()),
                    "sentinel": str(paths["sentinel"].resolve()),
                    "rom_sha256": runner.sha256_file(rom),
                    "input_state_sha256": runner.sha256_file(input_state),
                }
                for name in ("state", "png"):
                    paths[name].write_bytes(runner.PNG_SIGNATURE + b"new")
                for name in ("audit", "sentinel"):
                    paths[name].write_text(json.dumps(payload), encoding="utf-8")
                paths["marker"].write_text(
                    json.dumps(
                        {
                            "run_id": env["MGBA_REPLAY_RUN_ID"],
                            "capture_frame": 160,
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
                return subprocess.CompletedProcess(command, 0)

            clean = {
                "pgid_clean": True,
                "mgba_listener_clean": True,
                "checked_pgid": 987,
            }
            with mock.patch.object(
                runner.subprocess,
                "run",
                side_effect=fake_run,
            ), mock.patch.object(
                runner,
                "read_ps_snapshot",
                return_value="1 1\n",
            ), mock.patch.object(
                runner,
                "probe_runtime_residue",
                return_value=clean,
            ), redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(argv), 0)

            final = json.loads(paths["audit"].read_text(encoding="utf-8"))
            self.assertEqual(final["inputs"], expected_events)
            self.assertEqual(final["runtime_residue"], clean)
            self.assertEqual(final["replay_script_sha256"], runner.sha256_file(LUA))
            self.assertEqual(final["staged_rom_sha256"], runner.sha256_file(rom))
            self.assertEqual(
                paths["sentinel"].read_text(encoding="utf-8"),
                paths["audit"].read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
