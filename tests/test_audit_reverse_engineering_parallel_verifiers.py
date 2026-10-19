"""The verifier replay must be parallelisable without changing the report.

107 independent verifier subprocesses used to run one after another and
dominated the formal audit's wall clock.  They now run in a bounded thread
pool.  Two properties have to hold:

* the report order (and therefore the report digest) must not depend on which
  verifier happened to finish first;
* the concurrency must shrink when the host has little memory free, because
  every worker holds a native trace replay in memory.
"""

import time
import unittest
import unittest.mock as mock

from tools import audit_reverse_engineering_proof as auditor
from tools import project_resource_guard as guard


def _group(name: str) -> dict:
    return {
        "labels": [name],
        "command": ["python3", f"tools/{name}.py", "--root", "."],
        "contract": {"format": "json", "assertions": {"/verified": True}},
    }


class JobCountTests(unittest.TestCase):
    def test_pool_shrinks_when_memory_is_short(self):
        cases = ((512, 1), (3000, 2), (9000, 4), (10**6, 4))
        for available, expected in cases:
            with mock.patch.object(
                guard,
                "available_physical_memory_mib",
                return_value=guard.MemorySnapshot(float(available), "vm-stat"),
            ):
                self.assertEqual(expected, auditor._verifier_job_count(8))

    def test_at_least_one_job_is_always_allowed(self):
        with mock.patch.object(
            guard,
            "available_physical_memory_mib",
            return_value=guard.MemorySnapshot(1.0, "vm-stat"),
        ):
            self.assertEqual(1, auditor._verifier_job_count(0))
            self.assertEqual(1, auditor._verifier_job_count(-5))

    def test_requested_count_is_capped_at_four(self):
        with mock.patch.object(
            guard,
            "available_physical_memory_mib",
            return_value=guard.MemorySnapshot(10**6, "vm-stat"),
        ):
            self.assertEqual(4, auditor._verifier_job_count(64))


class GroupExecutionOrderTests(unittest.TestCase):
    def _fake_execute(self, root, label, command, contract, blockers):
        # Finish in reverse order so completion order differs from group order.
        delay = 0.05 * (10 - int(label.rsplit("-", 1)[1]))
        time.sleep(delay)
        return {
            "label": label,
            "command": command,
            "exit_code": 0,
            "contract_ok": True,
        }

    def test_report_order_is_independent_of_completion_order(self):
        groups = [_group(f"group-{index}") for index in range(8)]
        with mock.patch.object(
            auditor, "_execute_contract", side_effect=self._fake_execute
        ):
            prepared = auditor._execute_groups(
                __import__("pathlib").Path("."), groups, None, 4
            )

        labels = [group["labels"][0] for _index, group, _blockers, _execution in prepared]
        self.assertEqual([f"group-{index}" for index in range(8)], labels)

    def test_a_failing_verifier_keeps_its_place_in_the_order(self):
        groups = [_group(f"group-{index}") for index in range(6)]

        def failing(root, label, command, contract, blockers):
            if label == "group-3":
                blockers.append("boom")
                return {
                    "label": label,
                    "command": command,
                    "exit_code": 1,
                    "contract_ok": False,
                }
            return {
                "label": label,
                "command": command,
                "exit_code": 0,
                "contract_ok": True,
            }

        with mock.patch.object(auditor, "_execute_contract", side_effect=failing):
            prepared = auditor._execute_groups(
                __import__("pathlib").Path("."), groups, None, 4
            )

        labels = [group["labels"][0] for _index, group, _blockers, _execution in prepared]
        self.assertEqual([f"group-{index}" for index in range(6)], labels)
        failing_entry = prepared[3]
        self.assertFalse(failing_entry[3]["contract_ok"])
        self.assertEqual(["boom"], failing_entry[2])

    def test_the_coverage_verifier_is_reused_in_process(self):
        coverage_command = [
            "python3",
            "tools/audit_rom_byte_coverage.py",
            "--root",
            ".",
        ]
        groups = [
            {
                "labels": ["gate rom_byte_coverage"],
                "command": coverage_command,
                "contract": {
                    "format": "json",
                    "assertions": {"/verified": True, "/errors": []},
                },
            },
            _group("group-0"),
        ]
        report = {
            "schema": "rom-byte-coverage-audit-v1",
            "verified": True,
            "errors": [],
        }
        with mock.patch.object(auditor, "_execute_contract") as execute:
            prepared = auditor._execute_groups(
                __import__("pathlib").Path("."), groups, report, 4
            )

        self.assertEqual(1, execute.call_count)
        reused = [
            entry
            for entry in prepared
            if entry[3].get("execution") == "reused-in-process"
        ]
        self.assertEqual(1, len(reused))
        self.assertEqual(coverage_command, reused[0][1]["command"])


if __name__ == "__main__":
    unittest.main()
