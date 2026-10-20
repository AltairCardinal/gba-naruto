#!/usr/bin/env python3
"""The rebuild ledger must be closed: no gap may be left behind.

``docs/reverse-results-index/ledger.json`` records, for every thing the S49
remake needed, where the evidence came from.  A ledger that quietly keeps a
``missing`` entry is a promise the remake cannot keep, and a ledger that
claims a source that is not on disk is a claim nobody can check.

The rules this test pins down:

* the shipped ledger has no ``missing`` entry -- every item is either taken
  from the reverse results, re-derived from the original, or explicitly
  judged not applicable, with the reason written down;
* every entry that declares a source must have that source on disk, in the
  reverse work tree or in this one.  A pointer that does not resolve is
  reported as a problem and demotes the entry to ``missing``;
* ``not-applicable`` is an answer, not a gap, but it is held to the same
  source check as everything else;
* an entry that is still ``missing`` is itself reported as a problem, so the
  tool cannot be run against a half finished ledger without saying so.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_reverse_results_index import (  # noqa: E402
    LEDGER_SCHEMA,
    STATUSES,
    audit_ledger,
    main,
)

LEDGER = ROOT / "docs" / "reverse-results-index" / "ledger.json"
REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")


def _entry(**overrides) -> dict:
    entry = {
        "id": "sample",
        "category": "sample",
        "title": "sample entry",
        "status": "reused",
        "source": "",
        "evidence": "sample evidence",
    }
    entry.update(overrides)
    return entry


class ShippedLedgerTest(unittest.TestCase):
    """The ledger that ships with the repository must be closed."""

    def setUp(self) -> None:
        self.ledger = json.loads(LEDGER.read_text(encoding="utf-8"))

    def test_ledger_schema_is_the_known_one(self) -> None:
        self.assertEqual(self.ledger["schema"], LEDGER_SCHEMA)

    def test_no_entry_is_missing(self) -> None:
        missing = [
            entry["id"]
            for entry in self.ledger["entries"]
            if entry["status"] == "missing"
        ]
        self.assertEqual(missing, [])

    def test_every_entry_has_a_known_status(self) -> None:
        for entry in self.ledger["entries"]:
            self.assertIn(entry["status"], STATUSES, entry["id"])

    def test_every_entry_carries_evidence(self) -> None:
        for entry in self.ledger["entries"]:
            self.assertTrue(entry.get("evidence"), entry["id"])
            self.assertTrue(entry.get("title"), entry["id"])

    def test_not_applicable_entries_state_a_reason(self) -> None:
        entries = [
            entry
            for entry in self.ledger["entries"]
            if entry["status"] == "not-applicable"
        ]
        self.assertTrue(entries, "the roadmap milestones need verdicts")
        for entry in entries:
            self.assertIn("不适用", entry["evidence"], entry["id"])

    def test_audit_of_the_shipped_ledger_reports_no_problem(self) -> None:
        entries, problems = audit_ledger(self.ledger, REVERSE_ROOT)
        self.assertEqual(problems, [])
        self.assertTrue(entries)
        for entry in entries:
            self.assertNotEqual(entry["status"], "missing", entry["id"])


class AuditRuleTest(unittest.TestCase):
    """The audit fails closed on every kind of broken claim."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.present = self.workspace / "present.txt"
        self.present.write_text("evidence\n", encoding="utf-8")

    def _audit(self, entry: dict):
        return audit_ledger(
            {"schema": LEDGER_SCHEMA, "entries": [entry]},
            self.workspace,
        )

    def test_not_applicable_with_a_real_source_is_kept(self) -> None:
        entries, problems = self._audit(
            _entry(status="not-applicable", source="present.txt")
        )
        self.assertEqual(problems, [])
        self.assertEqual(entries[0]["status"], "not-applicable")
        self.assertEqual(entries[0]["audit"], "source found")

    def test_not_applicable_with_a_broken_source_is_reported(self) -> None:
        entries, problems = self._audit(
            _entry(status="not-applicable", source="absent.txt")
        )
        self.assertTrue(problems)
        self.assertIn("absent.txt", problems[0])
        self.assertEqual(entries[0]["status"], "missing")

    def test_reused_with_a_broken_source_is_reported(self) -> None:
        entries, problems = self._audit(
            _entry(status="reused", source="absent.txt")
        )
        self.assertTrue(problems)
        self.assertEqual(entries[0]["status"], "missing")

    def test_reconstructed_with_a_broken_source_is_reported(self) -> None:
        entries, problems = self._audit(
            _entry(status="reconstructed", source="absent.txt")
        )
        self.assertTrue(problems)
        self.assertEqual(entries[0]["status"], "missing")

    def test_a_missing_entry_is_a_problem(self) -> None:
        _entries, problems = self._audit(_entry(status="missing"))
        self.assertTrue(problems)
        self.assertIn("missing", problems[0])

    def test_an_unknown_status_is_a_problem(self) -> None:
        entries, problems = self._audit(_entry(status="guessed"))
        self.assertTrue(problems)
        self.assertEqual(entries[0]["status"], "missing")

    def test_an_entry_without_a_source_is_allowed(self) -> None:
        entries, problems = self._audit(
            _entry(status="not-applicable", source="")
        )
        self.assertEqual(problems, [])
        self.assertEqual(entries[0]["audit"], "no source declared")


class IndexBuilderTest(unittest.TestCase):
    """The builder writes the index and reports the ledger it found."""

    def test_builder_runs_and_writes_the_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            out_dir = Path(temporary) / "index"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "build_reverse_results_index.py"),
                    "--out-dir",
                    str(out_dir),
                    "--reverse-root",
                    str(REVERSE_ROOT),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            index = json.loads(
                (out_dir / "index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index["ledger_problems"], [])
            self.assertTrue(index["ledger"])
            for entry in index["ledger"]:
                self.assertNotEqual(entry["status"], "missing", entry["id"])
            readme = (out_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn("台账", readme)


if __name__ == "__main__":
    unittest.main()
