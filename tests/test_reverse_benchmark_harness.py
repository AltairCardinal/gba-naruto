#!/usr/bin/env python3
"""Guarded attempt lifecycle tests for the reverse benchmark harness."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.reverse_benchmark.harness import (
    _child_environment,
    _guard_command,
    run_smoke_attempt,
)
from tools.reverse_benchmark.matrix import benchmark_matrix
from tools.reverse_benchmark.runner import openai_proxy_provider_contract


ROOT = Path(__file__).resolve().parents[1]


class ReverseBenchmarkHarnessTests(unittest.TestCase):
    def test_plan_bound_attempt_requires_compatibility_receipt_id_before_writing(self):
        configuration = benchmark_matrix()[0]
        plan_binding = {
            "plan_id": "a" * 64,
            "case_id": "case",
            "sequence": 1,
            "attempt_index": 1,
            "provider_contract_sha256": "b" * 64,
            "retry_of": None,
        }
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "runs"
            with self.assertRaisesRegex(ValueError, "compatibility_receipt_id"):
                run_smoke_attempt(
                    repo_root=ROOT,
                    output_root=output_root,
                    configuration=configuration,
                    challenge_id="fixed-pointer-table",
                    seed=1,
                    run_id="6" * 32,
                    plan_binding=plan_binding,
                    command_override=[sys.executable, "-c", "pass"],
                )
            self.assertFalse(output_root.exists())

    def test_guard_rejects_credential_shaped_argv(self):
        credential_shapes = (
            "Authorization: Bearer argv-sentinel-token-1234567890",
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhcmd2LXNlbnRpbmVsIn0.signature1234567890",
        )
        for index, shaped in enumerate(credential_shapes):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaisesRegex(ValueError, "credential material"):
                    _guard_command(
                        repo_root=ROOT,
                        workspace=root,
                        run_dir=root / "run",
                        child_command=[sys.executable, "-c", f"print({shaped!r})"],
                        wall_timeout_s=10,
                        idle_timeout_s=5,
                    )

    def test_attempt_rejects_credential_shaped_override_before_writing(self):
        configuration = benchmark_matrix()[0]
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "runs"
            with self.assertRaisesRegex(ValueError, "credential material"):
                run_smoke_attempt(
                    repo_root=ROOT,
                    output_root=output_root,
                    configuration=configuration,
                    challenge_id="fixed-pointer-table",
                    seed=1,
                    run_id="8" * 32,
                    command_override=[
                        sys.executable,
                        "-c",
                        "print('Bearer override-sentinel-token-1234567890')",
                    ],
                )
            self.assertFalse(output_root.exists())

    def test_benchmark_specific_codex_home_is_inherited_without_other_secrets(self):
        with mock.patch.dict(
            os.environ,
            {
                "CODEX_HOME": "/tmp/reverse-benchmark-codex-home",
                "BENCH_UNRELATED_SECRET": "must-not-be-inherited",
                "OPENAI_API_KEY": "must-not-be-inherited-either",
                "CODEX_API_KEY": "must-not-be-inherited-either",
                "CODEX_ACCESS_TOKEN": "must-not-be-inherited-either",
            },
        ):
            environment = _child_environment(None)

        self.assertEqual(
            "/tmp/reverse-benchmark-codex-home", environment["CODEX_HOME"]
        )
        self.assertNotIn("BENCH_UNRELATED_SECRET", environment)
        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertNotIn("CODEX_API_KEY", environment)
        self.assertNotIn("CODEX_ACCESS_TOKEN", environment)

    def test_turn_aggregate_above_threshold_is_partial_not_long_request_priced(self):
        configuration = benchmark_matrix()[0]
        fake_event = json.dumps(
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 300_000, "output_tokens": 1_000},
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            manifest = run_smoke_attempt(
                repo_root=ROOT,
                output_root=Path(directory),
                configuration=configuration,
                challenge_id="fixed-pointer-table",
                seed=7,
                run_id="1" * 32,
                wall_timeout_s=15,
                idle_timeout_s=10,
                command_override=[sys.executable, "-c", f"print({fake_event!r})"],
            )

        self.assertEqual("turn-aggregate", manifest["telemetry"]["usage_granularity"])
        self.assertEqual(
            "turn-aggregate",
            manifest["telemetry"]["requests"][0]["usage_granularity"],
        )
        self.assertEqual("partial-known", manifest["billing"]["status"])
        self.assertIsNone(manifest["billing"]["totals"]["api_cost_usd"])
        self.assertEqual(
            "38.25",
            manifest["billing"]["totals"]["codex_credits_estimate"],
        )

    def test_guarded_attempt_persists_failure_evidence_and_cleans_workspace(self):
        configuration = benchmark_matrix()[0]
        fake_event = json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 10,
                    "cached_input_tokens": 0,
                    "output_tokens": 2,
                    "reasoning_output_tokens": 0,
                },
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "runs"
            manifest = run_smoke_attempt(
                repo_root=ROOT,
                output_root=output_root,
                configuration=configuration,
                challenge_id="fixed-pointer-table",
                seed=11,
                run_id="0" * 32,
                wall_timeout_s=15,
                idle_timeout_s=10,
                command_override=[
                    sys.executable,
                    "-c",
                    f"print({fake_event!r})",
                ],
            )
            run_dir = output_root / ("0" * 32)
            persisted = json.loads((run_dir / "manifest.json").read_text())

            self.assertEqual(manifest, persisted)
            self.assertEqual("verified-failed", persisted["status"])
            self.assertEqual(
                openai_proxy_provider_contract(),
                persisted["provider_contract"],
            )
            self.assertEqual(10, persisted["telemetry"]["usage"]["uncached_input"])
            self.assertEqual(2, persisted["telemetry"]["usage"]["output"])
            self.assertEqual("complete", persisted["billing"]["status"])
            self.assertEqual(
                "all-agent-threads", persisted["telemetry"]["usage_scope"]
            )
            self.assertEqual(0, persisted["verification"]["score"])
            self.assertTrue((run_dir / "events.jsonl").is_file())
            self.assertTrue((run_dir / "stderr.jsonl").is_file())
            self.assertTrue((run_dir / "guard-summary.json").is_file())
            self.assertTrue((run_dir / "prompt.txt").is_file())
            self.assertFalse(Path(persisted["workspace"]["ephemeral_path"]).exists())
            self.assertEqual("removed", persisted["workspace"]["final_state"])

    def test_existing_run_directory_is_never_overwritten(self):
        configuration = benchmark_matrix()[0]
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            (output_root / ("a" * 32)).mkdir()
            with self.assertRaisesRegex(FileExistsError, "run directory already exists"):
                run_smoke_attempt(
                    repo_root=ROOT,
                    output_root=output_root,
                    configuration=configuration,
                    challenge_id="fixed-pointer-table",
                    seed=1,
                    run_id="a" * 32,
                    command_override=[sys.executable, "-c", "pass"],
                )

    def test_dangling_run_symlink_is_treated_as_existing(self):
        configuration = benchmark_matrix()[0]
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            run_id = "b" * 32
            (output_root / run_id).symlink_to(output_root / "missing-target")

            with self.assertRaisesRegex(FileExistsError, "run directory already exists"):
                run_smoke_attempt(
                    repo_root=ROOT,
                    output_root=output_root,
                    configuration=configuration,
                    challenge_id="fixed-pointer-table",
                    seed=1,
                    run_id=run_id,
                    command_override=[sys.executable, "-c", "pass"],
                )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_untrusted_symlink_is_rejected_without_copying_target(self):
        configuration = benchmark_matrix()[0]
        helper = (
            "from pathlib import Path; "
            "root=Path('submission'); root.mkdir(); "
            f"(root / 'leak').symlink_to({str(ROOT / 'AGENTS.md')!r})"
        )
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            run_id = "c" * 32
            manifest = run_smoke_attempt(
                repo_root=ROOT,
                output_root=output_root,
                configuration=configuration,
                challenge_id="fixed-pointer-table",
                seed=1,
                run_id=run_id,
                command_override=[sys.executable, "-c", helper],
            )
            run_dir = output_root / run_id

            self.assertEqual("infrastructure-failed", manifest["status"])
            self.assertIn("submission/leak", manifest["archive"]["rejected_paths"])
            self.assertFalse((run_dir / "packet/submission/leak").exists())
            self.assertFalse((run_dir / "packet/submission/leak").is_symlink())

    def test_arbitrary_parent_secret_is_not_inherited_or_persisted(self):
        configuration = benchmark_matrix()[0]
        secret = "benchmark-parent-secret-do-not-persist"
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {"BENCH_TEST_SECRET": secret},
        ):
            output_root = Path(directory)
            run_id = "d" * 32
            run_smoke_attempt(
                repo_root=ROOT,
                output_root=output_root,
                configuration=configuration,
                challenge_id="fixed-pointer-table",
                seed=1,
                run_id=run_id,
                command_override=[
                    sys.executable,
                    "-c",
                    (
                        "import os; "
                        "print(os.environ.get('BENCH_TEST_SECRET', 'not-inherited'))"
                    ),
                ],
            )
            persisted_text = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in (output_root / run_id).rglob("*")
                if path.is_file()
            )

        self.assertNotIn(secret, persisted_text)

    def test_ultra_without_verified_closure_is_incomplete_and_not_billed(self):
        configuration = next(
            item
            for item in benchmark_matrix()
            if item.model == "gpt-5.6-sol" and item.effort == "ultra"
        )
        root_only_event = json.dumps(
            {
                "type": "turn.completed",
                "turn_id": "root-only",
                "usage": {"input_tokens": 10, "output_tokens": 2},
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            manifest = run_smoke_attempt(
                repo_root=ROOT,
                output_root=Path(directory),
                configuration=configuration,
                challenge_id="fixed-pointer-table",
                seed=1,
                run_id="e" * 32,
                wall_timeout_s=15,
                idle_timeout_s=10,
                command_override=[sys.executable, "-c", f"print({root_only_event!r})"],
            )

        self.assertEqual("infrastructure-failed", manifest["status"])
        self.assertEqual("root-thread-only", manifest["telemetry"]["usage_scope"])
        self.assertFalse(manifest["telemetry"]["usage_complete"])
        self.assertEqual("unknown", manifest["billing"]["status"])

    def test_injected_minimax_secret_is_redacted_from_all_evidence(self):
        configuration = next(
            item for item in benchmark_matrix() if item.provider == "minimax"
        )
        secret = "minimax-benchmark-secret-sentinel"
        helper = (
            "import json, os, sys; "
            "from pathlib import Path; "
            "s=os.environ['BENCH_MINIMAX_API_KEY']; "
            "Path('submission').mkdir(); "
            "Path('submission/secret.txt').write_text(s); "
            "print(s); print(s, file=sys.stderr); "
            "print(json.dumps({'type':'turn.completed','usage':"
            "{'input_tokens':10,'output_tokens':2}}))"
        )
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            run_id = "f" * 32
            manifest = run_smoke_attempt(
                repo_root=ROOT,
                output_root=output_root,
                configuration=configuration,
                challenge_id="fixed-pointer-table",
                seed=1,
                run_id=run_id,
                wall_timeout_s=15,
                idle_timeout_s=10,
                command_override=[sys.executable, "-c", helper],
                child_environment={"BENCH_MINIMAX_API_KEY": secret},
            )
            evidence = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in (output_root / run_id).rglob("*")
                if path.is_file()
            )

        self.assertEqual("infrastructure-failed", manifest["status"])
        self.assertTrue(manifest["security"]["credential_material_detected"])
        self.assertIn("capture-stream", manifest["security"]["surfaces"])
        self.assertNotIn(secret, evidence)
        self.assertIn("[REDACTED]", evidence)
        self.assertIn("security.credential-material-redacted", evidence)
        self.assertIn("submission/secret.txt", manifest["archive"]["rejected_paths"])

    def test_openai_style_secret_shape_is_redacted_without_loading_the_key(self):
        configuration = benchmark_matrix()[0]
        fake_secret = "sk-openai-shaped-test-sentinel-1234567890"
        helper = (
            "import json, sys; "
            "from pathlib import Path; "
            "s='sk-'+'openai-shaped-test-sentinel-1234567890'; "
            "Path('submission').mkdir(); "
            "Path('submission/secret.txt').write_text(s); "
            "print(s); print(s, file=sys.stderr); "
            "print(json.dumps({'type':'turn.completed','usage':"
            "{'input_tokens':10,'output_tokens':2}}))"
        )
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            run_id = "9" * 32
            manifest = run_smoke_attempt(
                repo_root=ROOT,
                output_root=output_root,
                configuration=configuration,
                challenge_id="fixed-pointer-table",
                seed=1,
                run_id=run_id,
                wall_timeout_s=15,
                idle_timeout_s=10,
                command_override=[sys.executable, "-c", helper],
            )
            evidence = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in (output_root / run_id).rglob("*")
                if path.is_file()
            )

        self.assertEqual("infrastructure-failed", manifest["status"])
        self.assertTrue(manifest["security"]["credential_material_detected"])
        self.assertIn("capture-stream", manifest["security"]["surfaces"])
        self.assertNotIn(fake_secret, evidence)
        self.assertIn("[REDACTED]", evidence)
        self.assertIn("submission/secret.txt", manifest["archive"]["rejected_paths"])

    def test_bearer_and_jwt_shapes_are_rejected_from_streams_and_archive(self):
        configuration = benchmark_matrix()[0]
        bearer = "Bearer archive-sentinel-token-1234567890"
        jwt = (
            "eyJhbGciOiJIUzI1NiJ9."
            "eyJzdWIiOiJhcmNoaXZlLXNlbnRpbmVsIn0."
            "signature1234567890"
        )
        helper = (
            "import json; from pathlib import Path; "
            "b='Bearer '+'archive-sentinel-token-1234567890'; "
            "j='eyJhbGciOiJIUzI1NiJ9.'+'eyJzdWIiOiJhcmNoaXZlLXNlbnRpbmVsIn0.'+"
            "'signature1234567890'; "
            "Path('submission').mkdir(); "
            "Path('submission/bearer.txt').write_text(b); "
            "Path('submission/jwt.txt').write_text(j); "
            "print(b); print(j); "
            "print(json.dumps({'type':'turn.completed','usage':"
            "{'input_tokens':10,'output_tokens':2}}))"
        )
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            run_id = "7" * 32
            manifest = run_smoke_attempt(
                repo_root=ROOT,
                output_root=output_root,
                configuration=configuration,
                challenge_id="fixed-pointer-table",
                seed=1,
                run_id=run_id,
                wall_timeout_s=15,
                idle_timeout_s=10,
                command_override=[sys.executable, "-c", helper],
            )
            evidence = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in (output_root / run_id).rglob("*")
                if path.is_file()
            )

        self.assertEqual("infrastructure-failed", manifest["status"])
        self.assertTrue(manifest["security"]["credential_material_detected"])
        self.assertNotIn(bearer, evidence)
        self.assertNotIn(jwt, evidence)
        self.assertIn("submission/bearer.txt", manifest["archive"]["rejected_paths"])
        self.assertIn("submission/jwt.txt", manifest["archive"]["rejected_paths"])


if __name__ == "__main__":
    unittest.main()
