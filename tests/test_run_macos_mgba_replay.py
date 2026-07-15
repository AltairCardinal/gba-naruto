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
LUA = ROOT / "tools" / "mgba_checkpoint_replay.lua"


class ReplayLuaContractTests(unittest.TestCase):
    def test_zero_input_replay_captures_frame_from_explicit_environment(self):
        text = LUA.read_text(encoding="utf-8")
        for name in (
            "MGBA_REPLAY_INPUT_STATE",
            "MGBA_REPLAY_OUTPUT_STATE",
            "MGBA_REPLAY_OUTPUT_PNG",
            "MGBA_REPLAY_AUDIT",
            "MGBA_REPLAY_SENTINEL",
            "MGBA_REPLAY_CAPTURE_FRAME",
            "MGBA_REPLAY_RUN_ID",
        ):
            self.assertIn(name, text)
        self.assertIn('"inputs":[]', text)
        self.assertIn("emu:loadStateFile", text)
        self.assertIn("emu:saveStateFile", text)
        self.assertIn("assert(emu:loadStateFile(input_state)", text)
        self.assertIn("assert(emu:saveStateFile(output_state)", text)
        self.assertIn("emu:screenshot", text)
        self.assertIn("os.exit(0)", text)
        self.assertNotIn("emu:addKey", text)
        self.assertNotIn("emu:clearKey", text)


class ReplayRunnerContractTests(unittest.TestCase):
    def test_runner_module_exists_with_pinned_guard_boundaries(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        self.assertEqual(runner.MIN_AVAILABLE_MIB, 4096)
        self.assertEqual(runner.MAX_TREE_RSS_MIB, 1536)
        self.assertEqual(
            runner.EXPECTED_PATCH_SHA256,
            "e76c8fc4f5451bdffe28b7f3595cd441bbb90fb1aa88a926cfbe4f1254d3d2a6",
        )

    def test_manifest_binds_binary_patch_and_pinned_build_identity(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "mGBA"
            binary.write_bytes(b"binary")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "label": "mGBA 0.10.5 + Qt script backport",
                        "version": "0.10.5",
                        "source_commit": runner.SOURCE_COMMIT,
                        "backport_commit": runner.BACKPORT_COMMIT,
                        "patch_sha256": runner.EXPECTED_PATCH_SHA256,
                        "binary_sha256": hashlib.sha256(b"binary").hexdigest(),
                        "architecture": "x86_64",
                    }
                ),
                encoding="utf-8",
            )
            payload = runner.validate_build_manifest(manifest, binary)
            self.assertEqual(payload["binary_sha256"], hashlib.sha256(b"binary").hexdigest())

            mutations = {
                "label": "official mGBA",
                "source_commit": "0" * 40,
                "backport_commit": "1" * 40,
                "patch_sha256": "2" * 64,
                "binary_sha256": "3" * 64,
                "architecture": "arm64",
            }
            original = json.loads(manifest.read_text(encoding="utf-8"))
            for key, value in mutations.items():
                with self.subTest(key=key):
                    bad = dict(original)
                    bad[key] = value
                    manifest.write_text(json.dumps(bad), encoding="utf-8")
                    with self.assertRaises(runner.ReplayError):
                        runner.validate_build_manifest(manifest, binary)

    def test_input_hashes_fail_closed_before_launch(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.bin"
            path.write_bytes(b"current")
            actual = hashlib.sha256(b"current").hexdigest()
            self.assertEqual(runner.validate_expected_hash(path, actual, "ROM"), actual)
            with self.assertRaisesRegex(runner.ReplayError, "ROM SHA-256"):
                runner.validate_expected_hash(path, "0" * 64, "ROM")
            with self.assertRaisesRegex(runner.ReplayError, "64 lowercase"):
                runner.validate_expected_hash(path, "BAD", "state")

    def test_multiple_script_options_preserve_cli_order_and_replay_is_last(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        command = runner.emulator_command(
            Path("/bin/mgba"),
            [Path("/scripts/first.lua"), Path("/scripts/second.lua")],
            Path("/scripts/replay.lua"),
            Path("/stage/base.gba"),
        )
        self.assertEqual(
            command,
            [
                "/bin/mgba",
                "--script",
                "/scripts/first.lua",
                "--script",
                "/scripts/second.lua",
                "--script",
                "/scripts/replay.lua",
                "/stage/base.gba",
            ],
        )

    def test_guard_command_has_one_lock_strict_limits_and_no_degraded_mode(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        child = ["/bin/mgba", "--script", "/replay.lua", "/stage.gba"]
        wrapped = runner.guarded_command(Path("/summary.json"), child, 120, 30)
        self.assertEqual(wrapped[:2], [runner.sys.executable, str(runner.GUARD_SCRIPT)])
        self.assertEqual(wrapped.count("--lock-file"), 1)
        self.assertIn(str(runner.HEAVY_LOCK), wrapped)
        self.assertIn("4096", wrapped)
        self.assertIn("1536", wrapped)
        self.assertNotIn("--allow-degraded", wrapped)
        self.assertEqual(wrapped[wrapped.index("--") + 1 :], child)

    def test_canonical_paths_reject_alias_overlap_and_unsafe_existing_outputs(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.gba"
            source.write_bytes(b"rom")
            alias = root / "alias.gba"
            alias.symlink_to(source)
            with self.assertRaisesRegex(runner.ReplayError, "symlink"):
                runner.canonical_input(alias, "ROM")

            first = root / "first.out"
            second_alias = root / "second.out"
            second_alias.symlink_to(first)
            with self.assertRaisesRegex(runner.ReplayError, "symlink"):
                runner.validate_output_paths([first, second_alias])

            directory = root / "directory"
            directory.mkdir()
            with self.assertRaisesRegex(runner.ReplayError, "regular file"):
                runner.prepare_fresh_output(directory, "state")

            fifo = root / "fifo"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(runner.ReplayError, "regular file"):
                runner.prepare_fresh_output(fifo, "state")

    def test_staged_save_sidecar_is_reserved_in_output_alias_checks(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged = root / "staged.gba"
            state_collision = root / "staged.sav"
            with self.assertRaisesRegex(runner.ReplayError, "overlap"):
                runner.validate_output_paths(
                    [staged, state_collision],
                    derived=[staged.with_suffix(".sav")],
                )

    def test_post_run_revalidation_rejects_binary_or_input_drift(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "mGBA"
            rom = root / "base.gba"
            state = root / "input.ss9"
            staged = root / "staged.gba"
            for path, data in (
                (binary, b"binary"), (rom, b"rom"), (state, b"state"), (staged, b"rom")
            ):
                path.write_bytes(data)
            args = argparse.Namespace(
                binary=binary,
                build_manifest=root / "manifest.json",
                rom=rom,
                state=state,
                staged_rom=staged,
                replay_script=root / "replay.lua",
                pre_script=[],
                expected_pre_script_sha256=[],
                expected_build_manifest_sha256="",
                expected_binary_sha256=runner.sha256_file(binary),
                expected_rom_sha256=runner.sha256_file(rom),
                expected_state_sha256=runner.sha256_file(state),
            )
            args.build_manifest.write_bytes(b"manifest")
            args.replay_script.write_bytes(b"replay")
            args.expected_build_manifest_sha256 = runner.sha256_file(args.build_manifest)
            args.expected_replay_script_sha256 = runner.sha256_file(args.replay_script)
            runner.revalidate_critical_inputs(args)
            for path in (binary, args.build_manifest, rom, state, staged, args.replay_script):
                with self.subTest(path=path.name):
                    original = path.read_bytes()
                    path.write_bytes(b"drift")
                    with self.assertRaises(runner.ReplayError):
                        runner.revalidate_critical_inputs(args)
                    path.write_bytes(original)

    def test_stale_regular_output_is_removed_and_cannot_be_reused(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "old.json"
            output.write_text("old", encoding="utf-8")
            runner.prepare_fresh_output(output, "audit")
            self.assertFalse(output.exists())
            with self.assertRaisesRegex(runner.ReplayError, "missing"):
                runner.require_fresh_regular_file(output, "audit")

    def test_guard_summary_rejects_wrapper_child_and_protection_failures(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        command = ["/bin/mgba", "/stage.gba"]
        good = {
            "reason": "completed",
            "exit_code": 0,
            "child_pid": 123,
            "peak_tree_rss_mib": 4.5,
            "protection_backend": "posix-process-group",
            "degraded": False,
            "command": command,
        }
        runner.validate_guard_summary(good, command, 0)
        cases = (
            (9, good),
            (1, {**good, "reason": "child-exit", "exit_code": 1}),
            (124, {**good, "reason": "wall-timeout", "exit_code": 124}),
            (124, {**good, "reason": "idle-timeout", "exit_code": 124}),
            (125, {**good, "reason": "memory-limit", "exit_code": 125}),
            (125, {**good, "reason": "protection-failure", "exit_code": 125}),
            (0, {**good, "degraded": True}),
            (0, {**good, "command": ["wrong"]}),
            (0, {**good, "peak_tree_rss_mib": 1537}),
        )
        for wrapper_rc, payload in cases:
            with self.subTest(wrapper_rc=wrapper_rc, reason=payload.get("reason")):
                with self.assertRaises(runner.ReplayError):
                    runner.validate_guard_summary(payload, command, wrapper_rc)

    def test_exact_owned_pgid_query_must_be_clean(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        runner.validate_owned_pgid_clean(321, "1 1\n2 2\n")
        with self.assertRaisesRegex(runner.ReplayError, "PGID 321"):
            runner.validate_owned_pgid_clean(321, "321 321\n400 321\n")
        with self.assertRaisesRegex(runner.ReplayError, "malformed"):
            runner.validate_owned_pgid_clean(321, "not-ps-output\n")

    def test_payload_requires_current_run_frame_paths_hashes_and_zero_inputs(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        expected = {
            "run_id": "fresh",
            "frame": 80,
            "capture_frame": 80,
            "inputs": [],
            "success": True,
            "status": "capture-complete",
            "input_state": "/in.ss9",
            "output_state": "/out.ss9",
            "output_png": "/out.png",
            "audit": "/audit.json",
            "sentinel": "/sentinel.json",
            "rom_sha256": "1" * 64,
            "input_state_sha256": "2" * 64,
        }
        runner.validate_replay_payload(expected, expected)
        for key, value in (
            ("run_id", "old"),
            ("frame", 79),
            ("capture_frame", 79),
            ("inputs", ["A"]),
            ("success", False),
            ("output_png", "/old.png"),
            ("rom_sha256", "0" * 64),
        ):
            with self.subTest(key=key):
                bad = dict(expected)
                bad[key] = value
                with self.assertRaisesRegex(runner.ReplayError, key):
                    runner.validate_replay_payload(bad, expected)

    def test_output_bundle_requires_nonempty_png_state_and_matching_json(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "out.ss9"
            png = root / "out.png"
            audit = root / "audit.json"
            sentinel = root / "sentinel.json"
            expected = {
                "run_id": "fresh",
                "frame": 80,
                "capture_frame": 80,
                "inputs": [],
                "success": True,
                "status": "capture-complete",
                "input_state": "/in.ss9",
                "output_state": str(state),
                "output_png": str(png),
                "audit": str(audit),
                "sentinel": str(sentinel),
                "rom_sha256": "1" * 64,
                "input_state_sha256": "2" * 64,
            }
            for path in (state, png):
                path.write_bytes(b"\x89PNG\r\n\x1a\nbytes")
            audit.write_text(json.dumps(expected), encoding="utf-8")
            sentinel.write_text(json.dumps(expected), encoding="utf-8")
            bundle = runner.validate_output_bundle(state, png, audit, sentinel, expected)
            self.assertEqual(bundle["state_sha256"], runner.sha256_file(state))
            sentinel.unlink()
            with self.assertRaisesRegex(runner.ReplayError, "sentinel.*missing"):
                runner.validate_output_bundle(state, png, audit, sentinel, expected)

    def test_main_wiring_stages_rom_orders_scripts_and_forces_offscreen(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "mGBA"
            binary.write_bytes(b"binary")
            os.chmod(binary, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "label": "mGBA 0.10.5 + Qt script backport",
                        "version": "0.10.5",
                        "source_commit": runner.SOURCE_COMMIT,
                        "backport_commit": runner.BACKPORT_COMMIT,
                        "patch_sha256": runner.EXPECTED_PATCH_SHA256,
                        "binary_sha256": runner.sha256_file(binary),
                        "architecture": "x86_64",
                    }
                ), encoding="utf-8"
            )
            rom = root / "source" / "base.gba"
            state = root / "source" / "input.ss9"
            rom.parent.mkdir()
            rom.write_bytes(b"rom")
            state.write_bytes(b"state")
            pre1 = root / "pre1.lua"
            pre2 = root / "pre2.lua"
            replay = root / "replay.lua"
            for path in (pre1, pre2, replay):
                path.write_text("-- script\n", encoding="utf-8")
            out = root / "out"
            paths = {
                "staged": out / "staged.gba",
                "state": out / "frame80.ss9",
                "png": out / "frame80.png",
                "audit": out / "audit.json",
                "sentinel": out / "sentinel.json",
                "summary": out / "guard.json",
            }

            def fake_wrapper(command, **kwargs):
                self.assertEqual(kwargs["env"]["QT_QPA_PLATFORM"], "offscreen")
                child = command[command.index("--") + 1 :]
                self.assertEqual(
                    child,
                    [
                        str(binary.resolve()), "--script", str(pre1.resolve()),
                        "--script", str(pre2.resolve()), "--script", str(replay.resolve()),
                        str(paths["staged"].resolve()),
                    ],
                )
                self.assertEqual(paths["staged"].read_bytes(), b"rom")
                env = kwargs["env"]
                payload = {
                    "run_id": env["MGBA_REPLAY_RUN_ID"],
                    "frame": 80,
                    "capture_frame": 80,
                    "inputs": [],
                    "success": True,
                    "status": "capture-complete",
                    "input_state": str(state.resolve()),
                    "output_state": str(paths["state"].resolve()),
                    "output_png": str(paths["png"].resolve()),
                    "audit": str(paths["audit"].resolve()),
                    "sentinel": str(paths["sentinel"].resolve()),
                    "rom_sha256": runner.sha256_file(rom),
                    "input_state_sha256": runner.sha256_file(state),
                }
                for name in ("state", "png"):
                    paths[name].write_bytes(b"\x89PNG\r\n\x1a\nnew")
                paths["audit"].write_text(json.dumps(payload), encoding="utf-8")
                paths["sentinel"].write_text(json.dumps(payload), encoding="utf-8")
                paths["summary"].write_text(json.dumps({
                    "reason": "completed", "exit_code": 0, "child_pid": 987,
                    "peak_tree_rss_mib": 12.5, "protection_backend": "posix-process-group",
                    "degraded": False, "command": child,
                }), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0)

            argv = [
                "--binary", str(binary), "--build-manifest", str(manifest),
                "--expected-build-manifest-sha256", runner.sha256_file(manifest),
                "--expected-binary-sha256", runner.sha256_file(binary),
                "--rom", str(rom), "--state", str(state),
                "--expected-rom-sha256", runner.sha256_file(rom),
                "--expected-state-sha256", runner.sha256_file(state),
                "--staged-rom", str(paths["staged"]), "--output-state", str(paths["state"]),
                "--output-png", str(paths["png"]), "--audit", str(paths["audit"]),
                "--sentinel", str(paths["sentinel"]), "--guard-summary", str(paths["summary"]),
                "--capture-frame", "80", "--pre-script", str(pre1),
                "--pre-script", str(pre2), "--replay-script", str(replay),
                "--evidence-mode", "script-order-diagnostic",
            ]
            with mock.patch.object(runner.subprocess, "run", side_effect=fake_wrapper), \
                    mock.patch.object(runner, "read_ps_snapshot", return_value="1 1\n"), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(argv), 0)
            self.assertFalse(rom.with_suffix(".sav").exists())
            finalized = json.loads(paths["audit"].read_text(encoding="utf-8"))
            self.assertTrue(finalized["pgid_clean"])
            self.assertEqual(finalized["guard_summary_sha256"], runner.sha256_file(paths["summary"]))
            self.assertEqual(finalized["binary_sha256"], runner.sha256_file(binary))
            self.assertEqual(finalized["patch_sha256"], runner.EXPECTED_PATCH_SHA256)
            self.assertEqual(finalized["build_manifest"], str(manifest.resolve()))
            self.assertEqual(finalized["replay_script"], str(replay.resolve()))
            self.assertEqual(finalized["replay_script_sha256"], runner.sha256_file(replay))
            self.assertEqual(finalized["pre_scripts"], [
                {"path": str(pre1.resolve()), "sha256": runner.sha256_file(pre1)},
                {"path": str(pre2.resolve()), "sha256": runner.sha256_file(pre2)},
            ])
            self.assertEqual(finalized["staged_rom_sha256"], runner.sha256_file(paths["staged"]))

    def test_main_rejects_missing_scripts_before_any_output_side_effect(self):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "mGBA"
            manifest = root / "manifest.json"
            rom = root / "base.gba"
            state = root / "input.ss9"
            replay = root / "replay.lua"
            for path in (binary, manifest, rom, state, replay):
                path.write_bytes(b"input")
            os.chmod(binary, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            output_state = root / "out.ss9"
            output_state.write_text("must-survive", encoding="utf-8")
            base = [
                "--binary", str(binary), "--build-manifest", str(manifest),
                "--expected-build-manifest-sha256", "0" * 64,
                "--expected-binary-sha256", "0" * 64,
                "--rom", str(rom), "--state", str(state),
                "--expected-rom-sha256", "0" * 64,
                "--expected-state-sha256", "0" * 64,
                "--staged-rom", str(root / "staged.gba"),
                "--output-state", str(output_state),
                "--output-png", str(root / "out.png"),
                "--audit", str(root / "audit.json"),
                "--sentinel", str(root / "sentinel.json"),
                "--guard-summary", str(root / "guard.json"),
            ]
            cases = (
                (["--replay-script", str(root / "missing-replay.lua")], "replay script"),
                (["--pre-script", str(root / "missing-pre.lua"), "--replay-script", str(replay)], "pre-script 1"),
            )
            for script_args, label in cases:
                with self.subTest(label=label):
                    args = runner.build_parser().parse_args([*base, *script_args])
                    with self.assertRaisesRegex(runner.ReplayError, label):
                        runner.validate_args(args)
                    self.assertEqual(output_state.read_text(encoding="utf-8"), "must-survive")


class ReplayRunnerReviewFixIntegrationTests(unittest.TestCase):
    def _fixture(self, root: Path, *, mode: str = "zero-input"):
        runner = importlib.import_module("tools.run_macos_mgba_replay")
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
        manifest_sha = runner.sha256_file(manifest)
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
            "replay": runner.DEFAULT_REPLAY_SCRIPT.resolve(),
            "staged": out / "staged.gba",
            "staged_save": out / "staged.sav",
            "state": out / "frame80.ss9",
            "png": out / "frame80.png",
            "audit": out / "audit.json",
            "sentinel": out / "sentinel.json",
            "summary": out / "guard.json",
        }
        argv = [
            "--binary", str(binary),
            "--build-manifest", str(manifest),
            "--expected-build-manifest-sha256", manifest_sha,
            "--expected-binary-sha256", binary_sha,
            "--rom", str(rom),
            "--state", str(state),
            "--expected-rom-sha256", runner.sha256_file(rom),
            "--expected-state-sha256", runner.sha256_file(state),
            "--staged-rom", str(paths["staged"]),
            "--output-state", str(paths["state"]),
            "--output-png", str(paths["png"]),
            "--audit", str(paths["audit"]),
            "--sentinel", str(paths["sentinel"]),
            "--guard-summary", str(paths["summary"]),
            "--capture-frame", "80",
            "--evidence-mode", mode,
        ]
        return runner, paths, argv, manifest_sha, binary_sha

    def _fake_wrapper(
        self,
        runner,
        paths,
        *,
        reason="completed",
        summary_rc=0,
        wrapper_rc=0,
        mutate=None,
    ):
        def run(command, **kwargs):
            self.assertFalse(
                paths["staged_save"].exists(),
                "stale staged .sav must be removed before launching mGBA",
            )
            child = command[command.index("--") + 1 :]
            env = kwargs["env"]
            payload = {
                "run_id": env["MGBA_REPLAY_RUN_ID"],
                "frame": 80,
                "capture_frame": 80,
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
            paths["state"].write_bytes(b"\x89PNG\r\n\x1a\nnew")
            paths["png"].write_bytes(b"\x89PNG\r\n\x1a\nnew")
            paths["audit"].write_text(json.dumps(payload), encoding="utf-8")
            paths["sentinel"].write_text(json.dumps(payload), encoding="utf-8")
            paths["summary"].write_text(
                json.dumps(
                    {
                        "reason": reason,
                        "exit_code": summary_rc,
                        "child_pid": 987,
                        "peak_tree_rss_mib": 12.5,
                        "protection_backend": "posix-process-group",
                        "degraded": reason == "protection-failure",
                        "command": child,
                    }
                ),
                encoding="utf-8",
            )
            if mutate is not None:
                mutate()
            return subprocess.CompletedProcess(command, wrapper_rc)

        return run

    def _run(self, runner, argv, fake_wrapper, *, ps="1 1\n"):
        with mock.patch.object(runner.subprocess, "run", side_effect=fake_wrapper), \
                mock.patch.object(runner, "read_ps_snapshot", return_value=ps), \
                redirect_stdout(io.StringIO()):
            return runner.main(argv)

    def _assert_not_enriched(self, path: Path):
        if not path.exists():
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("build_manifest_sha256", payload)

    def test_cli_requires_manifest_and_binary_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, _, argv, _, _ = self._fixture(Path(tmp))
            for option in (
                "--expected-build-manifest-sha256",
                "--expected-binary-sha256",
            ):
                with self.subTest(option=option):
                    shortened = list(argv)
                    index = shortened.index(option)
                    del shortened[index:index + 2]
                    with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        runner.build_parser().parse_args(shortened)

    def test_forged_manifest_and_arbitrary_binary_fail_before_output_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, paths, argv, _, _ = self._fixture(Path(tmp))
            paths["audit"].parent.mkdir(parents=True)
            paths["audit"].write_text("must-survive", encoding="utf-8")
            index = argv.index("--expected-build-manifest-sha256") + 1
            argv[index] = "0" * 64
            with self.assertRaisesRegex(runner.ReplayError, "build manifest SHA-256"):
                runner.main(argv)
            self.assertEqual(paths["audit"].read_text(encoding="utf-8"), "must-survive")

    def test_zero_input_mode_rejects_pre_or_custom_replay_before_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner, paths, argv, _, _ = self._fixture(root)
            paths["audit"].parent.mkdir(parents=True)
            paths["audit"].write_text("must-survive", encoding="utf-8")
            key_script = root / "key.lua"
            key_script.write_text('emu:addKey("A")\n', encoding="utf-8")
            cases = (
                ["--pre-script", str(key_script)],
                ["--replay-script", str(key_script)],
            )
            for extra in cases:
                with self.subTest(extra=extra):
                    with self.assertRaises(runner.ReplayError):
                        runner.main([*argv, *extra])
                    self.assertEqual(paths["audit"].read_text(encoding="utf-8"), "must-survive")

    def test_zero_input_main_finalizes_all_pinned_hashes_and_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, paths, argv, manifest_sha, binary_sha = self._fixture(Path(tmp))
            paths["staged_save"].parent.mkdir(parents=True)
            paths["staged_save"].write_text("stale-save", encoding="utf-8")
            fake = self._fake_wrapper(runner, paths)
            self.assertEqual(self._run(runner, argv, fake), 0)
            final = json.loads(paths["audit"].read_text(encoding="utf-8"))
            self.assertEqual(final["evidence_mode"], "zero-input")
            self.assertIs(final["zero_input_verified"], True)
            self.assertEqual(final["inputs"], [])
            self.assertEqual(final["build_manifest_sha256"], manifest_sha)
            self.assertEqual(final["binary_sha256"], binary_sha)
            self.assertEqual(
                final["replay_script_sha256"], runner.EXPECTED_REPLAY_SCRIPT_SHA256
            )
            self.assertEqual(final["pre_scripts"], [])

    def test_script_order_diagnostic_is_explicitly_not_zero_input_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner, paths, argv, _, _ = self._fixture(
                root, mode="script-order-diagnostic"
            )
            pre = root / "pre.lua"
            pre.write_text("-- diagnostic marker only\n", encoding="utf-8")
            argv.extend(("--pre-script", str(pre)))
            fake = self._fake_wrapper(runner, paths)
            self.assertEqual(self._run(runner, argv, fake), 0)
            final = json.loads(paths["audit"].read_text(encoding="utf-8"))
            self.assertEqual(final["evidence_mode"], "script-order-diagnostic")
            self.assertIs(final["zero_input_verified"], False)
            self.assertEqual(
                final["pre_scripts"],
                [{"path": str(pre.resolve()), "sha256": runner.sha256_file(pre)}],
            )

    def test_main_rejects_every_critical_input_drift_without_finalizing(self):
        drift_names = ("binary", "manifest", "rom", "input_state", "replay")
        for name in drift_names:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                runner, paths, argv, _, _ = self._fixture(Path(tmp))
                original = paths[name].read_bytes()
                fake = self._fake_wrapper(
                    runner,
                    paths,
                    mutate=lambda path=paths[name]: path.write_bytes(b"drift"),
                )
                try:
                    with self.assertRaises(runner.ReplayError):
                        self._run(runner, argv, fake)
                finally:
                    paths[name].write_bytes(original)
                self._assert_not_enriched(paths["audit"])

    def test_main_rejects_pre_script_drift_without_finalizing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner, paths, argv, _, _ = self._fixture(
                root, mode="script-order-diagnostic"
            )
            pre = root / "pre.lua"
            pre.write_text("-- diagnostic marker only\n", encoding="utf-8")
            argv.extend(("--pre-script", str(pre)))
            fake = self._fake_wrapper(
                runner, paths, mutate=lambda: pre.write_text("-- drift\n", encoding="utf-8")
            )
            with self.assertRaises(runner.ReplayError):
                self._run(runner, argv, fake)
            self._assert_not_enriched(paths["audit"])

    def test_main_failure_paths_never_finalize_enriched_audit(self):
        cases = (
            ("completed", 0, 9),
            ("child-exit", 1, 1),
            ("wall-timeout", 124, 124),
            ("idle-timeout", 124, 124),
            ("memory-limit", 125, 125),
            ("protection-failure", 125, 125),
        )
        for reason, summary_rc, wrapper_rc in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp:
                runner, paths, argv, _, _ = self._fixture(Path(tmp))
                fake = self._fake_wrapper(
                    runner,
                    paths,
                    reason=reason,
                    summary_rc=summary_rc,
                    wrapper_rc=wrapper_rc,
                )
                with self.assertRaises(runner.ReplayError):
                    self._run(runner, argv, fake)
                self._assert_not_enriched(paths["audit"])

    def test_main_owned_pgid_residual_never_finalizes_enriched_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, paths, argv, _, _ = self._fixture(Path(tmp))
            fake = self._fake_wrapper(runner, paths)
            with self.assertRaisesRegex(runner.ReplayError, "PGID 987"):
                self._run(runner, argv, fake, ps="987 987\n")
            self._assert_not_enriched(paths["audit"])


if __name__ == "__main__":
    unittest.main()
