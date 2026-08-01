from __future__ import annotations

import hashlib
import importlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "tools/run_macos_mgba_single_input.py"


class CurrentSingleInputRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = importlib.import_module(
            "tools.run_macos_mgba_single_input_current"
        )

    def test_keeps_the_historical_runner_byte_identical(self):
        self.assertEqual(
            hashlib.sha256(LEGACY.read_bytes()).hexdigest(),
            "aa94c3f540d9a18a898de2bf0f41809bf9a1073bc9b2b56ed250f179a124a057",
        )

    def test_accepts_only_the_current_desktop_toolchain_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "mGBA"
            binary.write_bytes(b"current-desktop-mgba")
            binary_hash = self.runner.sha256_file(binary)
            profile = root / "profile.json"
            payload = {
                "schema": "rom-expansion-profile-v1",
                "identity": "agb_standard_16mib_sequel_rom_profile",
                "hardware_evidence": {
                    "mgba_source_commit": self.runner.CURRENT_MGBA_SOURCE_COMMIT,
                    "mgba_binary_sha256": binary_hash,
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
            profile.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(
                self.runner.validate_current_toolchain_profile(
                    profile, binary, binary_hash
                ),
                payload,
            )

    def test_parser_requires_current_toolchain_profile_without_legacy_flags(self):
        help_text = self.runner.build_parser().format_help()
        self.assertIn("--toolchain-profile", help_text)
        self.assertNotIn("--build-manifest", help_text)
        self.assertNotIn("--expected-build-manifest-sha256", help_text)


if __name__ == "__main__":
    unittest.main()
