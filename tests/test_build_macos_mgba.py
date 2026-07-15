import base64
import contextlib
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import build_macos_mgba as builder


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "tools" / "patches" / "mgba-0.10.5-qt-script-cli.patch"


class BuildMacosMgbaTests(unittest.TestCase):
    def test_run_phase_cannot_reuse_stale_summary_when_wrapper_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            summary = evidence / "probe.json"
            summary.write_text(
                json.dumps(
                    {
                        "reason": "completed",
                        "exit_code": 0,
                        "child_pid": 123,
                        "peak_tree_rss_mib": 1,
                        "protection_backend": "posix-process-group",
                        "degraded": False,
                        "command": ["fresh-command"],
                    }
                ),
                encoding="utf-8",
            )

            def failed_wrapper(*args, **kwargs):
                self.assertFalse(summary.exists(), "stale summary survived before launch")
                return subprocess.CompletedProcess(args[0], 9)

            with mock.patch.object(builder.subprocess, "run", side_effect=failed_wrapper):
                with self.assertRaisesRegex(builder.BuildError, "wrapper.*9"):
                    builder._run_phase(
                        "probe",
                        ["fresh-command"],
                        cwd=evidence,
                        evidence_dir=evidence,
                    )

    def test_run_phase_preserves_admission_rejected_as_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)

            def rejected_wrapper(*args, **kwargs):
                (evidence / "probe.json").write_text(
                    json.dumps(
                        {
                            "reason": "admission-rejected",
                            "exit_code": 75,
                            "command": ["fresh-command"],
                        }
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(args[0], 75)

            with mock.patch.object(builder.subprocess, "run", side_effect=rejected_wrapper):
                with self.assertRaisesRegex(builder.BuildError, "BLOCKED.*4096"):
                    builder._run_phase(
                        "probe",
                        ["fresh-command"],
                        cwd=evidence,
                        evidence_dir=evidence,
                    )

    def test_verified_patch_bytes_bind_inspection_check_apply_and_manifest_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied_patch = Path(tmp) / "backport.patch"
            original = PATCH.read_bytes()
            copied_patch.write_bytes(original)
            verified = builder.load_verified_patch(copied_patch)
            copied_patch.write_bytes(b"changed after verification")

            calls = []

            def record_run(command, **kwargs):
                calls.append((command, kwargs))
                return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

            with mock.patch.object(builder.subprocess, "run", side_effect=record_run):
                builder.apply_patch_checked(Path(tmp), verified.data)

            self.assertEqual([call[1]["input"] for call in calls], [original, original])
            self.assertEqual(verified.metadata.sha256, hashlib.sha256(original).hexdigest())

    def test_invocation_paths_are_canonical_disjoint_before_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            rom = root / "rom" / "base.gba"
            rom.parent.mkdir()
            rom.write_bytes(b"rom")
            patch = root / "patch.diff"
            patch.write_bytes(b"patch")
            workspace = root / "cache" / "workspace"
            build = root / "cache" / "build"
            evidence = root / "repo-build" / "evidence"
            manifest = root / "repo-build" / "manifest.json"
            builder.validate_invocation_paths(
                source=source,
                workspace=workspace,
                build=build,
                evidence=evidence,
                manifest=manifest,
                rom=rom,
                patch=patch,
            )
            alias = root / "source-alias"
            alias.symlink_to(source, target_is_directory=True)
            with self.assertRaisesRegex(builder.BuildError, "overlap"):
                builder.validate_invocation_paths(
                    source=source,
                    workspace=alias,
                    build=build,
                    evidence=evidence,
                    manifest=manifest,
                    rom=rom,
                    patch=patch,
                )
            with self.assertRaisesRegex(builder.BuildError, "overlap"):
                builder.validate_invocation_paths(
                    source=source,
                    workspace=workspace,
                    build=workspace / "nested-build",
                    evidence=evidence,
                    manifest=manifest,
                    rom=rom,
                    patch=patch,
                )

    def test_sentinel_marker_must_match_the_current_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "sentinel.json"
            marker.write_text(
                json.dumps(
                    {
                        "script_loaded": True,
                        "frame": 1,
                        "pc": "0x08000000",
                        "run_id": "old-run",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(builder.BuildError, "current run"):
                builder.validate_sentinel(marker, "fresh-run")

    def test_only_versioned_patch_disables_git_whitespace_diagnostics(self):
        patch_attr = subprocess.run(
            ["git", "check-attr", "whitespace", "--", str(PATCH.relative_to(ROOT))],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout
        builder_attr = subprocess.run(
            ["git", "check-attr", "whitespace", "--", "tools/build_macos_mgba.py"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout
        self.assertTrue(patch_attr.rstrip().endswith("whitespace: unset"), patch_attr)
        self.assertTrue(builder_attr.rstrip().endswith("whitespace: unspecified"), builder_attr)

    def test_rejects_wrong_commit_and_tag(self):
        with self.assertRaisesRegex(builder.BuildError, "commit"):
            builder.validate_git_identity("deadbeef", "0.10.5", "")
        with self.assertRaisesRegex(builder.BuildError, "tag"):
            builder.validate_git_identity(builder.SOURCE_COMMIT, "0.10.4", "")

    def test_rejects_dirty_source(self):
        with self.assertRaisesRegex(builder.BuildError, "dirty"):
            builder.validate_git_identity(
                builder.SOURCE_COMMIT,
                builder.SOURCE_TAG,
                " M src/platform/qt/Window.cpp\n",
            )

    def test_versioned_patch_has_upstream_commit_and_exactly_two_paths(self):
        metadata = builder.inspect_patch(PATCH.read_text(encoding="utf-8"))
        self.assertEqual(metadata.commit, builder.BACKPORT_COMMIT)
        self.assertEqual(
            metadata.paths,
            (
                "src/platform/qt/ConfigController.cpp",
                "src/platform/qt/Window.cpp",
            ),
        )
        self.assertEqual(metadata.sha256, hashlib.sha256(PATCH.read_bytes()).hexdigest())

    def test_rejects_tampered_patch_even_when_commit_header_and_paths_remain(self):
        tampered = PATCH.read_text(encoding="utf-8").replace(
            "Script file to load on start",
            "Tampered script description",
        )
        with self.assertRaisesRegex(builder.BuildError, "SHA-256"):
            builder.inspect_patch(tampered)

    def test_versioned_patch_is_valid_unified_diff(self):
        completed = subprocess.run(
            ["git", "apply", "--numstat", str(PATCH)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            [line.split("\t", 2)[2] for line in completed.stdout.splitlines()],
            list(builder.EXPECTED_PATCH_PATHS),
        )

    def test_patch_must_apply_cleanly_before_it_is_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            target = root / "sample.txt"
            target.write_text("old\n", encoding="utf-8")
            patch = root / "change.patch"
            patch.write_text(
                "diff --git a/sample.txt b/sample.txt\n"
                "--- a/sample.txt\n+++ b/sample.txt\n"
                "@@ -1 +1 @@\n-old\n+new\n",
                encoding="utf-8",
            )
            builder.apply_patch_checked(root, patch.read_bytes())
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
            with self.assertRaisesRegex(builder.BuildError, "apply --check"):
                builder.apply_patch_checked(root, patch.read_bytes())
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")

    def test_guard_command_pins_heavy_lock_and_resource_limits(self):
        command = builder.guarded_command(
            Path("build/resource-guard/phase.json"),
            Path("/work"),
            ["cmake", "--build", "/build", "--parallel", "2"],
        )
        self.assertEqual(command[:2], [builder.sys.executable, str(builder.GUARD_SCRIPT)])
        self.assertIn(str(builder.HEAVY_LOCK), command)
        self.assertIn("4096", command)
        self.assertIn("1536", command)
        self.assertEqual(command[-5:], ["cmake", "--build", "/build", "--parallel", "2"])
        self.assertNotIn("--allow-degraded", command)

    def test_cmake_and_build_commands_have_required_fingerprint(self):
        configure = builder.cmake_configure_command(Path("/src"), Path("/build"))
        self.assertEqual(configure[:5], ["cmake", "-S", "/src", "-B", "/build"])
        for flag in (
            "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_PREFIX_PATH=/usr/local/opt/qt@5",
            "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
            "-DENABLE_SCRIPTING=ON",
            "-DBUILD_QT=ON",
            "-DBUILD_SDL=OFF",
        ):
            self.assertIn(flag, configure)
        self.assertEqual(
            builder.cmake_build_command(Path("/build")),
            ["cmake", "--build", "/build", "--parallel", "2"],
        )

    def test_rejects_unpatched_help_without_script_option(self):
        with self.assertRaisesRegex(builder.BuildError, "--script"):
            builder.validate_help("Usage: mGBA [option ...] file\n  --ecard FILE\n")
        builder.validate_help("Usage: mGBA\n  --script FILE  Script file to load on start\n")

    def test_summary_validation_requires_completed_owned_clean_run(self):
        expected = ["cmake", "--build", "/build", "--parallel", "2"]
        good = {
            "reason": "completed",
            "exit_code": 0,
            "child_pid": 123,
            "peak_tree_rss_mib": 800.0,
            "protection_backend": "posix-process-group",
            "degraded": False,
            "command": expected,
        }
        builder.validate_guard_summary(good, expected)
        for key, value in (
            ("reason", "child-exit"),
            ("exit_code", 1),
            ("degraded", True),
            ("peak_tree_rss_mib", 1536.1),
            ("command", ["wrong"]),
        ):
            bad = dict(good)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(builder.BuildError):
                builder.validate_guard_summary(bad, expected)

    def test_real_sentinel_contract_requires_loaded_script_frame_and_clean_exit_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "sentinel.json"
            lua = builder.sentinel_lua(marker, "current-run")
            self.assertIn('callbacks:add("frame"', lua)
            self.assertIn("emu:readRegister", lua)
            self.assertIn("os.exit(0)", lua)
            with self.assertRaisesRegex(builder.BuildError, "sentinel"):
                builder.validate_sentinel(marker, "current-run")
            marker.write_text(
                json.dumps(
                    {
                        "script_loaded": True,
                        "frame": 1,
                        "pc": "0x08000000",
                        "run_id": "current-run",
                    }
                ),
                encoding="utf-8",
            )
            builder.validate_sentinel(marker, "current-run")

    def test_sentinel_stages_base_rom_without_writing_save_next_to_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "input" / "base.gba"
            original.parent.mkdir()
            original.write_bytes(b"rom")
            fake_mgba = root / "fake_mgba.py"
            fake_mgba.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "rom = pathlib.Path(sys.argv[-1])\n"
                "rom.with_suffix('.sav').write_bytes(b'save')\n",
                encoding="utf-8",
            )
            os.chmod(fake_mgba, 0o755)
            staged = root / "evidence" / "sentinel-base.gba"
            staged.parent.mkdir()
            staged.with_suffix(".sav").write_bytes(b"stale-save")
            exit_code = builder._run_staged_sentinel(
                fake_mgba,
                root / "sentinel.lua",
                original,
                staged,
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(original.read_bytes(), b"rom")
            self.assertFalse(original.with_suffix(".sav").exists())
            self.assertEqual(staged.read_bytes(), b"rom")
            self.assertEqual(staged.with_suffix(".sav").read_bytes(), b"save")

    def test_main_wires_fresh_run_id_through_guarded_staged_sentinel_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            workspace = root / "cache" / "workspace"
            build = root / "cache" / "build"
            rom = root / "input" / "base.gba"
            rom.parent.mkdir()
            rom.write_bytes(b"fresh-rom")
            evidence = root / "repo-build" / "evidence"
            evidence.mkdir(parents=True)
            (evidence / "help.txt").write_text(
                "--script FILE stale help", encoding="utf-8"
            )
            (evidence / "version.txt").write_text(
                f"mGBA 0.10.5 ({builder.SOURCE_COMMIT}) stale", encoding="utf-8"
            )
            (evidence / "sentinel-result.json").write_text(
                json.dumps(
                    {
                        "script_loaded": True,
                        "frame": 99,
                        "pc": "old",
                        "run_id": "old-run",
                    }
                ),
                encoding="utf-8",
            )
            manifest = root / "repo-build" / "manifest.json"
            rom_log = root / "invoked-rom.txt"
            fake_guard = root / "fake_guard.py"
            fake_guard.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, pathlib, subprocess, sys\n"
                "args = sys.argv[1:]\n"
                "summary = pathlib.Path(args[args.index('--summary') + 1])\n"
                "command = args[args.index('--') + 1:]\n"
                "result = subprocess.run(command)\n"
                "summary.write_text(json.dumps({'reason': 'completed' if result.returncode == 0 else 'child-exit', 'exit_code': result.returncode, 'child_pid': os.getpid(), 'peak_tree_rss_mib': 1, 'protection_backend': 'posix-process-group', 'degraded': False, 'command': command}))\n"
                "raise SystemExit(result.returncode)\n",
                encoding="utf-8",
            )
            fake_guard.chmod(0o755)
            original_run_phase = builder._run_phase
            source_validations = []
            manifest_inputs = {}

            def fake_phase(name, command, *, cwd, evidence_dir):
                if name == "prepare":
                    self.assertEqual(base64.b64decode(command[-1]), PATCH.read_bytes())
                    workspace.mkdir(parents=True)
                elif name == "configure":
                    build.mkdir(parents=True)
                elif name == "build":
                    binary = build / "qt" / "mGBA.app" / "Contents" / "MacOS" / "mGBA"
                    binary.parent.mkdir(parents=True)
                    binary.write_text(
                        "#!/usr/bin/env python3\n"
                        "import json, os, pathlib, re, sys\n"
                        "if '--help' in sys.argv: print('--script FILE Script file to load on start'); raise SystemExit(0)\n"
                        f"if '--version' in sys.argv: print('mGBA 0.10.5 ({builder.SOURCE_COMMIT})'); raise SystemExit(0)\n"
                        "script = pathlib.Path(sys.argv[sys.argv.index('--script') + 1]).read_text()\n"
                        "marker = pathlib.Path(json.loads(re.search(r'^local marker = (.+)$', script, re.M).group(1)))\n"
                        "run_id = json.loads(re.search(r'^local run_id = (.+)$', script, re.M).group(1))\n"
                        "marker.write_text(json.dumps({'script_loaded': True, 'frame': 1, 'pc': 'fake-pc', 'run_id': run_id}))\n"
                        "pathlib.Path(os.environ['FAKE_MGBA_ROM_LOG']).write_text(sys.argv[-1])\n",
                        encoding="utf-8",
                    )
                    binary.chmod(0o755)
                elif name in {"help", "version"}:
                    self.assertFalse(Path(command[3]).exists(), f"stale {name} was reused")
                    self.assertEqual(builder._internal_main(command[2:]), 0)
                elif name == "sentinel":
                    return original_run_phase(
                        name,
                        command,
                        cwd=cwd,
                        evidence_dir=evidence_dir,
                    )
                return {
                    "reason": "completed",
                    "exit_code": 0,
                    "child_pid": 1,
                    "peak_tree_rss_mib": 1,
                    "protection_backend": "posix-process-group",
                    "degraded": False,
                    "command": list(command),
                }

            def record_source_validation(path):
                source_validations.append(path)

            def fake_manifest(**kwargs):
                manifest_inputs.update(kwargs)
                self.assertEqual(
                    kwargs["patch_metadata"].sha256,
                    hashlib.sha256(PATCH.read_bytes()).hexdigest(),
                )
                return {
                    "sentinel": dict(kwargs["sentinel_result"]),
                    "guard": {"summaries": dict(kwargs["summaries"])},
                }

            file_result = subprocess.CompletedProcess(
                ["file"], 0, stdout="Mach-O 64-bit executable x86_64\n"
            )
            real_subprocess_run = subprocess.run
            with (
                mock.patch.object(builder, "GUARD_SCRIPT", fake_guard),
                mock.patch.object(builder, "_run_phase", side_effect=fake_phase),
                mock.patch.object(builder, "validate_source_checkout", side_effect=record_source_validation),
                mock.patch.object(builder, "make_manifest", side_effect=fake_manifest),
                mock.patch.object(builder.subprocess, "run", wraps=subprocess.run) as run_mock,
                mock.patch.dict(os.environ, {"FAKE_MGBA_ROM_LOG": str(rom_log)}),
            ):
                run_mock.side_effect = lambda command, **kwargs: (
                    file_result if command[0] == "file" else real_subprocess_run(command, **kwargs)
                )
                with contextlib.redirect_stdout(io.StringIO()):
                    result = builder.main(
                        [
                            "--source-cache", str(source),
                            "--workspace", str(workspace),
                            "--build-dir", str(build),
                            "--rom", str(rom),
                            "--evidence-dir", str(evidence),
                            "--manifest", str(manifest),
                        ]
                    )
            self.assertEqual(result, 0)
            staged = evidence / "sentinel-base.gba"
            self.assertEqual(Path(rom_log.read_text()).resolve(), staged.resolve())
            self.assertEqual(staged.read_bytes(), rom.read_bytes())
            current_run_id = manifest_inputs["sentinel_result"]["run_id"]
            self.assertNotEqual(current_run_id, "old-run")
            self.assertEqual(
                manifest_inputs["summaries"]["sentinel"]["sentinel_run_id"],
                current_run_id,
            )
            self.assertEqual(source_validations, [source.resolve(), source.resolve()])

    def test_manifest_identifies_backport_and_binary_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "mGBA"
            binary.write_bytes(b"binary")
            patch_metadata = builder.PatchMetadata(
                commit=builder.BACKPORT_COMMIT,
                paths=builder.EXPECTED_PATCH_PATHS,
                sha256=hashlib.sha256(b"patch").hexdigest(),
            )
            manifest = builder.make_manifest(
                binary=binary,
                patch_metadata=patch_metadata,
                version_output=f"mGBA 0.10.5 ({builder.SOURCE_COMMIT})",
                file_output="Mach-O 64-bit executable x86_64",
                summaries={"build": {"peak_tree_rss_mib": 1.5}},
                sentinel_result={"run_id": "current-run", "frame": 1},
            )
            self.assertEqual(manifest["label"], "mGBA 0.10.5 + Qt script backport")
            self.assertEqual(manifest["source_commit"], builder.SOURCE_COMMIT)
            self.assertEqual(manifest["backport_commit"], builder.BACKPORT_COMMIT)
            self.assertEqual(manifest["binary_sha256"], hashlib.sha256(b"binary").hexdigest())
            self.assertEqual(manifest["patch_sha256"], hashlib.sha256(b"patch").hexdigest())
            self.assertEqual(manifest["architecture"], "x86_64")
            with self.assertRaisesRegex(builder.BuildError, "version"):
                builder.make_manifest(
                    binary=binary,
                    patch_metadata=patch_metadata,
                    version_output="mGBA 0.11",
                    file_output="Mach-O arm64",
                    summaries={},
                    sentinel_result={},
                )


if __name__ == "__main__":
    unittest.main()
