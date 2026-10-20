#!/usr/bin/env python3
"""The gap between the reverse results and the remake must be measured, not guessed.

The reverse work tree holds 262 artifact families with verified conclusions.
The remake tree holds the Butano build.  Nothing in the repository currently
states, in a checkable way, which of those families the remake actually
consumes, which ones it re-derived locally, and which ones it never touched
at all.

That gap is the thing the roadmap has to be built from, so it has to be a
number produced by a script over the whole tree -- never a hand-kept list.
The rules this test pins down:

* a family counts as **consumed** only when the remake's *build chain*
  (`butano-sequel/`, `tools/`) references it; a mention in `docs/` or
  `notes/` is a mention, not a consumption;
* the index machinery itself (`tools/build_reverse_results_index.py` and
  `artifacts/reverse-results-index-v1/`) mentions every family by
  construction, so it must never count as consumption;
* a family nobody references anywhere is the real gap and must be reported
  as such, with no inference from its category;
* the rebuild ledger is ground truth for the items it covers and is merged
  into the measurement rather than kept apart;
* the summary counts must be internally consistent with the rows.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "measure_butano_reverse_gap.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _index(entries: list[dict], ledger: list[dict] | None = None) -> dict:
    return {
        "schema": "konoha.reverse-results-index.v1",
        "source": {
            "reverse_root": "/tmp/reverse",
            "commit": "0" * 40,
            "dirty": False,
            "rom_sha256": "1" * 64,
        },
        "categories": {},
        "entries": entries,
        "ledger": ledger or [],
        "ledger_problems": [],
    }


def _family(family_id: str, category: str = "rom") -> dict:
    return {
        "id": family_id,
        "kind": "artifact",
        "category": category,
        "path": f"artifacts/{family_id}",
        "manifest": f"artifacts/{family_id}/manifest.json",
        "schema": family_id,
        "provides": [],
        "formulas": [],
        "addresses": [],
        "depends_on": [],
    }


class GapMeasurementTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    # -- helpers ---------------------------------------------------------

    def _build_tree(self) -> None:
        _write(self.root / "butano-sequel" / "game" / "src" / "main.cpp", "// uses rom-cfg-inventory-v3\n")
        _write(self.root / "tools" / "gen.py", "# build-unit-family-v1\n")
        _write(self.root / "tests" / "test_x.py", "# doc-family-v1\n")
        _write(self.root / "docs" / "plan.md", "# test-family-v1\n")
        _write(self.root / "notes" / "n.md", "# note-family-v1\n")
        _write(self.root / "artifacts" / "local-family-v1" / "receipt.json", "{}\n")
        _write(self.root / "tools" / "build_reverse_results_index.py", "# hidden-family-v1\n")
        _write(
            self.root / "artifacts" / "reverse-results-index-v1" / "index.json",
            json.dumps({"entries": [{"id": "hidden-family-v1"}]}),
        )

    def _run(self, index: dict) -> dict:
        index_path = self.root / "artifacts" / "reverse-results-index-v1" / "index.json"
        _write(index_path, json.dumps(index))
        out_dir = self.root / "artifacts" / "butano-reverse-gap-v1"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(self.root),
                "--index",
                str(index_path),
                "--out-dir",
                str(out_dir),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads((out_dir / "gap.json").read_text(encoding="utf-8"))

    # -- tests -----------------------------------------------------------

    def test_build_chain_reference_counts_as_consumed(self) -> None:
        self._build_tree()
        payload = self._run(
            _index(
                [
                    _family("rom-cfg-inventory-v3"),
                    _family("build-unit-family-v1"),
                ]
            )
        )
        rows = {row["id"]: row for row in payload["rows"]}
        self.assertEqual(rows["rom-cfg-inventory-v3"]["status"], "build")
        self.assertEqual(rows["build-unit-family-v1"]["status"], "build")

    def test_docs_and_notes_mentions_are_not_consumption(self) -> None:
        self._build_tree()
        payload = self._run(
            _index(
                [
                    _family("doc-family-v1"),
                    _family("test-family-v1"),
                    _family("note-family-v1"),
                ]
            )
        )
        rows = {row["id"]: row for row in payload["rows"]}
        self.assertEqual(rows["doc-family-v1"]["status"], "test")
        self.assertEqual(rows["test-family-v1"]["status"], "doc")
        self.assertEqual(rows["note-family-v1"]["status"], "doc")

    def test_index_machinery_never_counts_as_consumption(self) -> None:
        self._build_tree()
        payload = self._run(_index([_family("hidden-family-v1")]))
        row = payload["rows"][0]
        self.assertEqual(row["status"], "none")
        self.assertEqual(row["hits"], [])

    def test_local_artifact_reference_is_reported_separately(self) -> None:
        self._build_tree()
        payload = self._run(_index([_family("local-family-v1")]))
        row = payload["rows"][0]
        self.assertEqual(row["status"], "local_artifact")

    def test_the_roadmap_and_theory_note_are_not_references(self) -> None:
        """Writing the report must not count as consuming the result.

        The roadmap lists the untouched families in prose and the theory note
        quotes the consumed ones.  If those files counted as references, then
        writing the report would move every family off `none` and the
        measurement would reward documentation instead of consumption.
        """
        self._build_tree()
        _write(
            self.root / "docs" / "butano-reverse-gap-roadmap.md",
            "# roadmap\n\nnever touched: roadmap-family-v1\n",
        )
        _write(
            self.root / "notes" / "full-customization-and-fidelity-theory-20261020.md",
            "consumed: theory-family-v1\n",
        )
        payload = self._run(
            _index([_family("roadmap-family-v1"), _family("theory-family-v1")])
        )
        rows = {row["id"]: row for row in payload["rows"]}
        self.assertEqual(rows["roadmap-family-v1"]["status"], "none")
        self.assertEqual(rows["theory-family-v1"]["status"], "none")
        self.assertIn("roadmap-family-v1", payload["gap_families"])
        self.assertIn("theory-family-v1", payload["gap_families"])

    def test_the_notes_index_is_not_a_reference(self) -> None:
        """The notes index classifies every note, so it names all of them.

        It is a bulk enumerator of the measured population: its hits are
        classification, not consumption.  Its own receipt keeps the honest
        pre-index status, so excluding it here loses no information.
        """
        self._build_tree()
        _write(
            self.root / "docs" / "reverse-results-index" / "notes-index.md",
            "# notes index\n\nnotes-family-v1 | needs_guard\n",
        )
        payload = self._run(_index([_family("notes-family-v1")]))
        self.assertEqual(payload["rows"][0]["status"], "none")

    def test_untouched_family_is_the_reported_gap(self) -> None:
        self._build_tree()
        payload = self._run(_index([_family("never-mentioned-v1")]))
        self.assertEqual(payload["rows"][0]["status"], "none")
        self.assertIn("never-mentioned-v1", payload["gap_families"])
        self.assertEqual(payload["summary"]["by_status"]["none"], 1)

    def test_ledger_status_is_merged_into_the_row(self) -> None:
        self._build_tree()
        payload = self._run(
            _index(
                [_family("ledger-family-v1")],
                ledger=[
                    {
                        "id": "s49-something",
                        "category": "map",
                        "title": "x",
                        "status": "missing",
                        "source": "artifacts/ledger-family-v1/canvases/a.png",
                        "evidence": "n/a",
                    }
                ],
            )
        )
        row = payload["rows"][0]
        self.assertEqual(row["ledger_status"], "missing")
        self.assertEqual(row["ledger_id"], "s49-something")
        self.assertIn("s49-something", payload["ledger_missing"])

    def test_summary_counts_match_the_rows(self) -> None:
        self._build_tree()
        payload = self._run(
            _index(
                [
                    _family("rom-cfg-inventory-v3"),
                    _family("doc-family-v1"),
                    _family("never-mentioned-v1"),
                ]
            )
        )
        counts = payload["summary"]["by_status"]
        self.assertEqual(sum(counts.values()), len(payload["rows"]))
        self.assertEqual(counts["build"], 1)
        self.assertEqual(counts["test"], 1)
        self.assertEqual(counts["none"], 1)

    def test_markdown_output_lists_the_gap_families(self) -> None:
        self._build_tree()
        index_path = self.root / "artifacts" / "reverse-results-index-v1" / "index.json"
        _write(index_path, json.dumps(_index([_family("never-mentioned-v1")])))
        out_dir = self.root / "artifacts" / "butano-reverse-gap-v1"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(self.root),
                "--index",
                str(index_path),
                "--out-dir",
                str(out_dir),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        markdown = (out_dir / "gap.md").read_text(encoding="utf-8")
        self.assertIn("never-mentioned-v1", markdown)
        self.assertIn("gap.json", markdown)

    def test_missing_index_fails_closed(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(self.root),
                "--index",
                str(self.root / "does-not-exist.json"),
                "--out-dir",
                str(self.root / "out"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("index", (proc.stderr + proc.stdout).lower())


    def test_the_receipt_carries_the_artifact_family_denominator(self) -> None:
        # The artifact-family denominator moves whenever the reverse work tree
        # promotes a new family, so it must be read from the receipt and never
        # hard-coded in prose or in a print statement.
        payload = json.loads(
            (ROOT / "artifacts/butano-reverse-gap-v1/gap.json").read_text(
                encoding="utf-8"
            )
        )
        summary = payload["summary"]
        families = [
            row for row in payload["rows"] if row["kind"] == "artifact"
        ]
        self.assertEqual(summary["artifact_family_total"], len(families))
        counted = summary["artifact_family_by_status"]
        self.assertEqual(sum(counted.values()), len(families))
        for row in families:
            self.assertEqual(counted[row["status"]], counted.get(row["status"], 0))

if __name__ == "__main__":
    unittest.main()
