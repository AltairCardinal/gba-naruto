from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


class BattleEffectPhaseCaptureRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = importlib.import_module(
            "tools.run_macos_mgba_battle_effect_phase_capture"
        )

    def test_loads_group_identity_and_single_input_from_pinned_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "input.ss9"
            state.write_bytes(b"state")
            catalog = root / "animations.json"
            catalog.write_text(
                json.dumps(
                    {
                        "schema": "battle-effect-sprite-animations-v1",
                        "group_count": 1,
                        "groups": [
                            {
                                "group_id": 11,
                                "definition_pointer_table": "0x08345530",
                                "animation_pointer_table": "0x08345564",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            profile = root / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema": "battle-effect-pixel-ab-profile-v1",
                        "profile_id": "group-11",
                        "group_id": 11,
                        "input_state": str(state),
                        "input_state_sha256": self.runner.sha256_file(state),
                        "runtime_input": {
                            "key": "A",
                            "down_frame": 5,
                            "up_frame": 13,
                            "capture_frame": 106,
                        },
                    }
                ),
                encoding="utf-8",
            )
            loaded = self.runner.load_capture_profile(profile, catalog)
            self.assertEqual(loaded["group_id"], 11)
            self.assertEqual(loaded["definition_pointer"], 0x08345530)
            self.assertEqual(loaded["animation_pointer"], 0x08345564)
            self.assertEqual(loaded["input_schedule"], "A:5:13")
            self.assertEqual(loaded["capture_frames"], 106)
            self.assertEqual(loaded["timeout_frames"], 166)
            self.assertEqual(loaded["input_mode"], "explicit-single-input")

    def test_loads_zero_input_active_state_profile_without_synthetic_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "active.ss9"
            state.write_bytes(b"active-state")
            catalog = root / "animations.json"
            catalog.write_text(
                json.dumps(
                    {
                        "schema": "battle-effect-sprite-animations-v1",
                        "group_count": 1,
                        "groups": [{
                            "group_id": 11,
                            "definition_pointer_table": "0x08345530",
                            "animation_pointer_table": "0x08345564",
                        }],
                    }
                ),
                encoding="utf-8",
            )
            profile = root / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema": "battle-effect-phase-capture-profile-v1",
                        "profile_id": "group-11-active",
                        "group_id": 11,
                        "input_mode": "zero-input-active-state",
                        "input_state": str(state),
                        "input_state_sha256": self.runner.sha256_file(state),
                        "timeout_frames": 30,
                    }
                ),
                encoding="utf-8",
            )
            loaded = self.runner.load_capture_profile(profile, catalog)
            self.assertEqual(loaded["input_mode"], "zero-input-active-state")
            self.assertEqual(loaded["events"], [])
            self.assertEqual(loaded["input_schedule"], "")
            self.assertEqual(loaded["capture_frames"], 0)
            self.assertEqual(loaded["timeout_frames"], 30)

    def test_loads_explicit_input_sequence_phase_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "created.ss9"
            state.write_bytes(b"created-state")
            catalog = root / "animations.json"
            catalog.write_text(
                json.dumps(
                    {
                        "schema": "battle-effect-sprite-animations-v1",
                        "group_count": 1,
                        "groups": [{
                            "group_id": 18,
                            "definition_pointer_table": "0x0834819C",
                            "animation_pointer_table": "0x083481DC",
                        }],
                    }
                ),
                encoding="utf-8",
            )
            profile = root / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema": "battle-effect-phase-capture-profile-v1",
                        "profile_id": "group-18-sequence",
                        "group_id": 18,
                        "input_mode": "explicit-input-sequence",
                        "inputs": ["A:18:20", "Up:378:380"],
                        "capture_frame": 4520,
                        "input_state": str(state),
                        "input_state_sha256": self.runner.sha256_file(state),
                        "timeout_frames": 5000,
                    }
                ),
                encoding="utf-8",
            )
            loaded = self.runner.load_capture_profile(profile, catalog)
            self.assertEqual(loaded["input_mode"], "explicit-input-sequence")
            self.assertEqual(loaded["input_schedule"], "A:18:20,Up:378:380")
            self.assertEqual(len(loaded["events"]), 2)
            self.assertEqual(loaded["capture_frames"], 4520)
            self.assertEqual(loaded["timeout_frames"], 5000)

    def test_accepts_only_the_current_pinned_desktop_toolchain_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "mGBA"
            binary.write_bytes(b"current-desktop-mgba")
            binary_hash = self.runner.sha256_file(binary)
            profile = root / "toolchain-profile.json"
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
            validated = self.runner.validate_current_toolchain_profile(
                profile, binary, binary_hash
            )
            self.assertEqual(validated, payload)

            invalid_cases = (
                {**payload, "schema": "rom-expansion-cpu-read-probe-v1"},
                {
                    **payload,
                    "hardware_evidence": {
                        **payload["hardware_evidence"],
                        "mgba_source_commit": "0" * 40,
                    },
                },
                {
                    **payload,
                    "runtime_probe": {
                        **payload["runtime_probe"],
                        "owned_process_residue": True,
                    },
                },
            )
            for invalid in invalid_cases:
                profile.write_text(json.dumps(invalid), encoding="utf-8")
                with self.subTest(invalid=invalid), self.assertRaises(
                    self.runner.ReplayError
                ):
                    self.runner.validate_current_toolchain_profile(
                        profile, binary, binary_hash
                    )

    def test_parser_requires_exactly_one_toolchain_provenance_mode(self):
        parser = self.runner.build_parser()
        common = [
            "--binary", "mGBA",
            "--expected-binary-sha256", "0" * 64,
            "--rom", "base.gba",
            "--expected-rom-sha256", "1" * 64,
            "--profile", "profile.json",
            "--expected-profile-sha256", "2" * 64,
            "--staged-rom", "staged.gba",
            "--output-dir", "output",
            "--guard-summary", "guard.json",
        ]
        with self.assertRaises(SystemExit):
            parser.parse_args(common)
        with self.assertRaises(SystemExit):
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

    def test_rejects_mismatched_group_state_hash_or_implicit_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "input.ss9"
            state.write_bytes(b"state")
            catalog = root / "animations.json"
            catalog.write_text(
                json.dumps(
                    {
                        "schema": "battle-effect-sprite-animations-v1",
                        "group_count": 1,
                        "groups": [
                            {
                                "group_id": 1,
                                "definition_pointer_table": "0x08340AB0",
                                "animation_pointer_table": "0x08340AF4",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            base = {
                "schema": "battle-effect-pixel-ab-profile-v1",
                "profile_id": "bad",
                "group_id": 11,
                "input_state": str(state),
                "input_state_sha256": "0" * 64,
                "runtime_input": {
                    "key": "A+B",
                    "down_frame": 5,
                    "up_frame": 13,
                    "capture_frame": 106,
                },
            }
            profile = root / "profile.json"
            profile.write_text(json.dumps(base), encoding="utf-8")
            with self.assertRaises(self.runner.ReplayError):
                self.runner.load_capture_profile(profile, catalog)

    def test_phase_payload_requires_one_ordered_three_phase_transaction(self):
        expected = {
            "group_id": 11,
            "definition_pointer": 0x08345530,
            "animation_pointer": 0x08345564,
            "input_schedule": "A:5:13",
            "capture_frames": 106,
            "input_mode": "explicit-single-input",
        }
        payload = {
            "schema": "mgba-battle-effect-phase-capture-v1",
            "outcome": "three-phase-captured",
            "group_id": 11,
            "definition_pointer": "0x08345530",
            "animation_pointer": "0x08345564",
            "input_mode": "explicit-single-input",
            "inputs": [
                {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
            ],
            "automatic_inputs": [],
            "recovery_inputs": [],
            "phases": [
                {"name": "renderer-post", "address": "0x08063328", "cycle": "10"},
                {"name": "submit-post", "address": "0x08061126", "cycle": "20"},
                {"name": "ack-post", "address": "0x080612AA", "cycle": "30"},
            ],
        }
        self.runner.validate_phase_payload(payload, expected)
        for mutation in (
            {"phases": payload["phases"][:2]},
            {"phases": [payload["phases"][1], payload["phases"][0], payload["phases"][2]]},
            {"automatic_inputs": ["A"]},
            {"group_id": 12},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(
                self.runner.ReplayError
            ):
                self.runner.validate_phase_payload({**payload, **mutation}, expected)


if __name__ == "__main__":
    unittest.main()
