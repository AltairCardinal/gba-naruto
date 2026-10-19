import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.measure_reverse_throughput import (
    SCHEMA,
    classify_bottlenecks,
    render_markdown,
    run_stage,
    sample_host,
)


class HostSampleTests(unittest.TestCase):
    def test_sample_host_reports_every_measured_dimension(self):
        sample = sample_host(Path(__file__).resolve().parents[1])

        for key in (
            "at",
            "disk_total_gib",
            "disk_available_gib",
            "memory_available_mib",
            "memory_backend",
            "load_average_1m",
            "cpu_count",
        ):
            self.assertIn(key, sample)

        self.assertGreater(sample["disk_total_gib"], 0.0)
        self.assertGreaterEqual(sample["disk_available_gib"], 0.0)
        self.assertGreater(sample["memory_available_mib"], 0.0)
        self.assertGreaterEqual(sample["cpu_count"], 1)

    def test_sample_host_uses_a_real_memory_backend(self):
        sample = sample_host(Path(__file__).resolve().parents[1])
        self.assertIn(sample["memory_backend"], {"vm-stat", "proc-meminfo"})


class GuardedStageTests(unittest.TestCase):
    def test_run_stage_records_wall_clock_and_guard_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stage = {
                "label": "trivial-stage",
                "kind": "static",
                "command": ["-c", "print('stage-ok')"],
            }
            result = run_stage(
                stage,
                tmp_path,
                sys.executable,
                tmp_path / "heavy.lock",
                Path(__file__).resolve().parents[1],
            )

            self.assertEqual(result["exit_code"], 0)
            self.assertGreater(result["wall_seconds"], 0.0)
            self.assertEqual(result["guard_reason"], "completed")
            self.assertFalse(result["guard_degraded"])
            self.assertIn("stage-ok", result["stdout_tail"])
            self.assertTrue(Path(result["summary_path"]).exists())

            receipt = json.loads(Path(result["summary_path"]).read_text(encoding="utf-8"))
            self.assertEqual(receipt["exit_code"], 0)
            self.assertIn("peak_tree_rss_mib", receipt)

    def test_run_stage_reports_a_failing_stage_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stage = {
                "label": "failing-stage",
                "kind": "static",
                "command": ["-c", "raise SystemExit(3)"],
            }
            result = run_stage(
                stage,
                tmp_path,
                sys.executable,
                tmp_path / "heavy.lock",
                Path(__file__).resolve().parents[1],
            )

            self.assertEqual(result["exit_code"], 3)
            self.assertNotEqual(result["guard_reason"], "completed")


class BottleneckClassificationTests(unittest.TestCase):
    def _payload(self, **overrides):
        base = {
            "stages": [],
            "cpu_probe": {"workers": 4, "speedup": 3.9, "parallel_efficiency": 0.97},
            "lock_probe": {"results": [{}, {}], "rejected": 1},
            "host": {
                "disk_available_gib": 6.6,
                "memory_available_mib": 6400.0,
                "cpu_count": 12,
            },
        }
        base.update(overrides)
        return base

    def test_lock_contention_is_reported_as_a_hard_bottleneck(self):
        findings = classify_bottlenecks(
            self._payload()["stages"],
            self._payload()["cpu_probe"],
            self._payload()["lock_probe"],
            self._payload()["host"],
        )

        names = [finding["bottleneck"] for finding in findings]
        self.assertIn("heavy-work-lock-serialization", names)
        serialization = next(
            finding
            for finding in findings
            if finding["bottleneck"] == "heavy-work-lock-serialization"
        )
        self.assertEqual(serialization["severity"], "hard")

    def test_low_disk_headroom_is_reported(self):
        findings = classify_bottlenecks(
            [], self._payload()["cpu_probe"], {"results": [], "rejected": 0}, self._payload()["host"]
        )

        names = [finding["bottleneck"] for finding in findings]
        self.assertIn("disk-headroom", names)

    def test_poor_parallel_efficiency_is_reported(self):
        cpu_probe = {"workers": 8, "speedup": 2.0, "parallel_efficiency": 0.25}
        findings = classify_bottlenecks(
            [], cpu_probe, {"results": [], "rejected": 0}, self._payload()["host"]
        )

        names = [finding["bottleneck"] for finding in findings]
        self.assertIn("cpu-parallel-headroom", names)

    def test_idle_timeout_is_reported_as_a_hard_gate(self):
        stages = [
            {
                "label": "coverage-audit",
                "kind": "static",
                "wall_seconds": 60.8,
                "guard_reason": "idle-timeout",
            }
        ]
        findings = classify_bottlenecks(
            stages,
            {"workers": 4, "speedup": 3.9, "parallel_efficiency": 0.97},
            {"results": [], "rejected": 0},
            {
                "disk_available_gib": 120.0,
                "memory_available_mib": 12000.0,
                "cpu_count": 12,
            },
        )

        names = [finding["bottleneck"] for finding in findings]
        self.assertIn("guard-idle-timeout-gate", names)
        gate = next(
            finding
            for finding in findings
            if finding["bottleneck"] == "guard-idle-timeout-gate"
        )
        self.assertEqual(gate["severity"], "hard")
        self.assertIn("coverage-audit", gate["evidence"])

    def test_healthy_host_does_not_invent_bottlenecks(self):
        findings = classify_bottlenecks(
            [],
            {"workers": 4, "speedup": 3.9, "parallel_efficiency": 0.97},
            {"results": [], "rejected": 0},
            {
                "disk_available_gib": 120.0,
                "memory_available_mib": 12000.0,
                "cpu_count": 12,
            },
        )

        names = [finding["bottleneck"] for finding in findings]
        self.assertNotIn("heavy-work-lock-serialization", names)
        self.assertNotIn("disk-headroom", names)
        self.assertNotIn("cpu-parallel-headroom", names)

    def test_slowest_heavy_stage_is_reported(self):
        stages = [
            {"label": "fast", "kind": "heavy", "wall_seconds": 12.0},
            {"label": "slow", "kind": "heavy", "wall_seconds": 900.0},
        ]
        findings = classify_bottlenecks(
            stages,
            {"workers": 4, "speedup": 3.9, "parallel_efficiency": 0.97},
            {"results": [], "rejected": 0},
            {
                "disk_available_gib": 120.0,
                "memory_available_mib": 12000.0,
                "cpu_count": 12,
            },
        )

        latency = [
            finding
            for finding in findings
            if finding["bottleneck"] == "single-heavy-stage-latency"
        ]
        self.assertEqual(len(latency), 1)
        self.assertIn("slow", latency[0]["evidence"])


class RenderTests(unittest.TestCase):
    def test_markdown_contains_stage_table_and_bottleneck_sections(self):
        payload = {
            "host": {
                "at": "2026-10-19T00:00:00+00:00",
                "disk_available_gib": 6.6,
                "memory_available_mib": 6400.0,
                "cpu_count": 12,
                "load_average_1m": 10.2,
            },
            "interpreter": "/usr/local/bin/python3",
            "stages": [
                {
                    "label": "coverage-audit",
                    "kind": "static",
                    "wall_seconds": 61.0,
                    "peak_tree_rss_mib": 210.0,
                    "exit_code": 0,
                    "guard_reason": "completed",
                }
            ],
            "cpu_probe": {
                "workers": 4,
                "serial_seconds": 10.0,
                "parallel_seconds": 3.0,
                "speedup": 3.3,
                "parallel_efficiency": 0.83,
            },
            "lock_probe": {"results": [{}, {}], "rejected": 2},
            "bottlenecks": [
                {
                    "rank": 0,
                    "bottleneck": "heavy-work-lock-serialization",
                    "severity": "hard",
                    "evidence": "2/2 rejected",
                    "impact": "serialized",
                    "mitigation": "queue it",
                }
            ],
        }

        markdown = render_markdown(payload)

        self.assertIn("| 阶段 |", markdown)
        self.assertIn("coverage-audit", markdown)
        self.assertIn("heavy-work-lock-serialization", markdown)
        self.assertIn("lock-busy", markdown)
        self.assertIn("并行效率", markdown)


class SchemaTests(unittest.TestCase):
    def test_schema_name_is_pinned(self):
        self.assertEqual(SCHEMA, "reverse-throughput-measurement-v1")


if __name__ == "__main__":
    unittest.main()
