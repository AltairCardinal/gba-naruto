import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import build_macos_mgba as builder


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "tools" / "patches" / "mgba-0.10.5-qt-script-cli.patch"


class BuildMacosMgbaTests(unittest.TestCase):
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
            builder.apply_patch_checked(root, patch)
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
            with self.assertRaisesRegex(builder.BuildError, "apply --check"):
                builder.apply_patch_checked(root, patch)
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
            lua = builder.sentinel_lua(marker)
            self.assertIn('callbacks:add("frame"', lua)
            self.assertIn("emu:readRegister", lua)
            self.assertIn("os.exit(0)", lua)
            with self.assertRaisesRegex(builder.BuildError, "sentinel"):
                builder.validate_sentinel(marker)
            marker.write_text(
                json.dumps({"script_loaded": True, "frame": 1, "pc": "0x08000000"}),
                encoding="utf-8",
            )
            builder.validate_sentinel(marker)

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

    def test_manifest_identifies_backport_and_binary_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "mGBA"
            binary.write_bytes(b"binary")
            patch = Path(tmp) / "backport.patch"
            patch.write_bytes(b"patch")
            manifest = builder.make_manifest(
                binary=binary,
                patch=patch,
                version_output=f"mGBA 0.10.5 ({builder.SOURCE_COMMIT})",
                file_output="Mach-O 64-bit executable x86_64",
                summaries={"build": {"peak_tree_rss_mib": 1.5}},
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
                    patch=patch,
                    version_output="mGBA 0.11",
                    file_output="Mach-O arm64",
                    summaries={},
                )


if __name__ == "__main__":
    unittest.main()
