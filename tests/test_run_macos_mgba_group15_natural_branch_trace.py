from __future__ import annotations

import importlib
from pathlib import Path
import tempfile
import unittest


class Group15NaturalBranchTraceRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = importlib.import_module(
            "tools.run_macos_mgba_group15_natural_branch_trace"
        )

    def valid_payload(self) -> dict[str, object]:
        events = [
            {"name": name, "address": address, "frame": 1546, "cycle": str(index + 2)}
            for index, (name, address) in enumerate(
                (
                    ("runtime-copy-b", "0x0807A222"),
                    ("presentation-entry", "0x0807F064"),
                    ("classification-cmp", "0x0807F09E"),
                    ("dynamic-selector", "0x0807F0FC"),
                    ("dynamic-binder-call", "0x0807F10C"),
                    ("binder-entry", "0x0807C5E8"),
                )
            )
        ]
        events[0].update(frame=1087, r4="0x02026CB8")
        events[1]["r0"] = "0x02026CB8"
        events[2]["r0"] = "0x00000000"
        events[3]["r4"] = "0x02026CB8"
        for row in events[4:]:
            row.update(r0="0x00000001", r1="0x00000011", r2="0x00000770")
        return {
            "schema": "natural-battle-effect-branch-trace-experiment-v1",
            "run_id": "0123456789abcdef0123456789abcdef",
            "frame": 1800,
            "capture_frame": 1800,
            "rom_sha256": "a" * 64,
            "input_state_sha256": "b" * 64,
            "script_sha256": "c" * 64,
            "inputs": [
                {"key": "A", "down_frame": 60, "up_frame": 68, "hold_frames": 8}
            ],
            "automatic_inputs": [],
            "recovery_inputs": [],
            "events": events,
        }

    def test_validates_exact_hash_run_and_input_contract(self):
        payload = self.valid_payload()
        self.runner.validate_trace_payload(
            payload,
            run_id=str(payload["run_id"]),
            rom_sha256="a" * 64,
            input_state_sha256="b" * 64,
            script_sha256="c" * 64,
        )

    def test_rejects_hidden_input_or_identity_mismatch(self):
        payload = self.valid_payload()
        payload["automatic_inputs"] = [{"key": "B"}]
        with self.assertRaisesRegex(self.runner.ReplayError, "implicit inputs"):
            self.runner.validate_trace_payload(
                payload,
                run_id=str(payload["run_id"]),
                rom_sha256="a" * 64,
                input_state_sha256="b" * 64,
                script_sha256="c" * 64,
            )
        payload = self.valid_payload()
        with self.assertRaisesRegex(self.runner.ReplayError, "ROM identity"):
            self.runner.validate_trace_payload(
                payload,
                run_id=str(payload["run_id"]),
                rom_sha256="d" * 64,
                input_state_sha256="b" * 64,
                script_sha256="c" * 64,
            )

    def test_parser_is_current_profile_only_and_has_no_custom_script(self):
        parser = self.runner.build_parser()
        destinations = {action.dest for action in parser._actions}
        self.assertIn("toolchain_profile", destinations)
        self.assertNotIn("build_manifest", destinations)
        self.assertNotIn("script", destinations)

    def test_output_overlap_with_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("binary", "profile.json", "route.gba", "input.ss9"):
                (root / name).write_bytes(b"x")
            (root / "binary").chmod(0o755)
            parser = self.runner.build_parser()
            args = parser.parse_args(
                [
                    "--binary", str(root / "binary"),
                    "--toolchain-profile", str(root / "profile.json"),
                    "--expected-binary-sha256", "a" * 64,
                    "--rom", str(root / "route.gba"),
                    "--expected-rom-sha256", "b" * 64,
                    "--state", str(root / "input.ss9"),
                    "--expected-state-sha256", "c" * 64,
                    "--staged-rom", str(root / "route.gba"),
                    "--output-dir", str(root / "output"),
                    "--guard-summary", str(root / "guard.json"),
                ]
            )
            with self.assertRaises(self.runner.ReplayError):
                self.runner.validate_args(args)


if __name__ == "__main__":
    unittest.main()
