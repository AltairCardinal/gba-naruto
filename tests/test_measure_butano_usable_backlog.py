#!/usr/bin/env python3
"""The usable-but-unused backlog must be measured, not asserted.

``tools/measure_butano_reverse_gap.py`` measures *reachability*: is a reverse
result referenced by the remake's build chain?  That is not the question the
roadmap needs.  The roadmap needs to know how many closed results the remake
could pick up right now, and how far each one is from being imported.

This test pins down the rules that make that number trustworthy:

* the population is the **artifact families** of the index -- signed results
  with a manifest, not prose;
* only ``accepted`` families count.  That is the flag the importers enforce
  (``tools/butano/import_rom_reverse_families.py``), so a ``candidate`` is
  not a result;
* a family with no payload has nothing to import and is not on the shelf;
* a family that is already ``build``-referenced is consumed, not on the shelf;
* the shelf is split by **how directly** each family can be used, and the
  verdict is recorded per family so a reader can audit it;
* a payload that matches neither vocabulary is reported as ``unclassified``
  rather than being forced into a bucket -- a forced verdict is the kind of
  guess this tool exists to avoid;
* the numbers in the summary must agree with the rows.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "measure_butano_usable_backlog.py"


def _write(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


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


def _note(note_id: str) -> dict:
    return {
        "id": note_id,
        "kind": "note",
        "category": "other",
        "path": f"notes/{note_id}.md",
        "schema": "",
        "provides": [],
        "formulas": [],
        "addresses": [],
        "depends_on": [],
    }


class UsableBacklogTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.reverse = self.root / "reverse"
        self.reverse.mkdir()

    # -- helpers ---------------------------------------------------------

    def _family_dir(self, family_id: str, *, status: str = "accepted") -> Path:
        base = self.reverse / "artifacts" / family_id
        base.mkdir(parents=True, exist_ok=True)
        _write(
            base / "manifest.json",
            json.dumps({"schema": family_id, "artifact_status": status}),
        )
        return base

    def _index(self, entries: list[dict]) -> dict:
        return {
            "schema": "konoha.reverse-results-index.v1",
            "source": {
                "reverse_root": str(self.reverse),
                "commit": "0" * 40,
                "dirty": False,
                "rom_sha256": "1" * 64,
            },
            "categories": {},
            "entries": entries,
            "ledger": [],
            "ledger_problems": [],
        }

    def _run(
        self,
        index: dict,
        *,
        statuses: dict[str, str] | None = None,
        notes_index: dict | None = None,
    ) -> dict:
        index_path = self.root / "artifacts" / "reverse-results-index-v1" / "index.json"
        _write(index_path, json.dumps(index))
        gap_path = self.root / "artifacts" / "butano-reverse-gap-v1" / "gap.json"
        _write(
            gap_path,
            json.dumps(
                {
                    "schema": "konoha.butano-reverse-gap.v1",
                    "rows": [
                        {"id": entry["id"], "status": (statuses or {}).get(entry["id"], "none")}
                        for entry in index["entries"]
                    ],
                }
            ),
        )
        notes_path = self.root / "artifacts" / "reverse-notes-index-v1" / "notes-index.json"
        if notes_index is not None:
            _write(notes_path, json.dumps(notes_index))
        out_dir = self.root / "artifacts" / "butano-usable-backlog-v1"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(self.root),
                "--index",
                str(index_path),
                "--gap",
                str(gap_path),
                "--notes-index",
                str(notes_path),
                "--out-dir",
                str(out_dir),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads((out_dir / "backlog.json").read_text(encoding="utf-8"))

    # -- tests -----------------------------------------------------------

    def test_accepted_family_with_payload_is_on_the_shelf(self) -> None:
        base = self._family_dir("rom-something-v1")
        _write(base / "payload.bin", b"\x00\x01")
        payload = self._run(self._index([_family("rom-something-v1")]))
        self.assertEqual(payload["summary"]["shelf_total"], 1)
        row = payload["shelf"][0]
        self.assertTrue(row["accepted"])
        self.assertFalse(row["consumed"])
        self.assertTrue(row["has_payload"])

    def test_candidate_family_is_not_on_the_shelf(self) -> None:
        """Only ``accepted`` results may be imported; a candidate is not one."""
        base = self._family_dir("rom-candidate-v1", status="candidate")
        _write(base / "payload.bin", b"\x00\x01")
        payload = self._run(self._index([_family("rom-candidate-v1")]))
        self.assertEqual(payload["summary"]["shelf_total"], 0)
        self.assertEqual(payload["summary"]["families_accepted"], 0)

    def test_consumed_family_is_not_on_the_shelf(self) -> None:
        base = self._family_dir("rom-consumed-v1")
        _write(base / "payload.bin", b"\x00\x01")
        payload = self._run(
            self._index([_family("rom-consumed-v1")]),
            statuses={"rom-consumed-v1": "build"},
        )
        self.assertEqual(payload["summary"]["shelf_total"], 0)
        self.assertEqual(payload["summary"]["families_consumed"], 1)

    def test_family_without_payload_is_not_on_the_shelf(self) -> None:
        self._family_dir("rom-empty-v1")
        payload = self._run(self._index([_family("rom-empty-v1")]))
        self.assertEqual(payload["summary"]["shelf_total"], 0)
        row = payload["rows"][0]
        self.assertEqual(row["tier"], "no-payload")

    def test_manifest_and_inputs_are_not_payload(self) -> None:
        base = self._family_dir("rom-bookkeeping-v1")
        _write(base / "inputs.json", "{}")
        payload = self._run(self._index([_family("rom-bookkeeping-v1")]))
        self.assertEqual(payload["summary"]["shelf_total"], 0)

    def test_compressed_coverage_receipt_is_not_payload(self) -> None:
        """``.gz`` holds the reverse project's coverage projection, not content.

        The byte-coverage projections are gzipped JSON.  Counting them as
        payload would put eleven coverage receipts on the shelf and make the
        backlog look like it holds renderable content.
        """
        base = self._family_dir("rom-precoverage-v1")
        _write(base / "rom-byte-coverage.json.gz", b"\x1f\x8b")
        payload = self._run(self._index([_family("rom-precoverage-v1")]))
        self.assertEqual(payload["summary"]["shelf_total"], 0)
        self.assertEqual(payload["rows"][0]["tier"], "no-payload")

    def test_notes_are_not_part_of_the_family_population(self) -> None:
        self._family_dir("rom-real-v1")
        payload = self._run(self._index([_family("rom-real-v1"), _note("some-note")]))
        self.assertEqual(payload["summary"]["families_total"], 1)

    def test_asset_payload_is_classified_as_asset_direct(self) -> None:
        base = self._family_dir("rom-graphics-v1")
        _write(base / "sheet.png", b"\x89PNG")
        payload = self._run(self._index([_family("rom-graphics-v1")]))
        row = payload["shelf"][0]
        self.assertEqual(row["tier"], "asset-direct")
        self.assertIn(".png", row["evidence"]["asset_suffixes"])

    def test_baseline_png_is_reported_as_a_baseline(self) -> None:
        base = self._family_dir("rom-ab-v1")
        _write(base / "baseline.png", b"\x89PNG")
        payload = self._run(self._index([_family("rom-ab-v1")]))
        self.assertEqual(
            payload["shelf"][0]["evidence"]["baseline_files"], ["baseline.png"]
        )

    def test_table_payload_is_classified_as_table_direct(self) -> None:
        base = self._family_dir("rom-bindings-v1")
        _write(base / "bindings.json", json.dumps({"bindings": [], "records": []}))
        payload = self._run(self._index([_family("rom-bindings-v1")]))
        row = payload["shelf"][0]
        self.assertEqual(row["tier"], "table-direct")
        self.assertIn("records", row["evidence"]["table_markers"])

    def test_code_flow_payload_is_classified_as_analysis_only(self) -> None:
        base = self._family_dir("rom-cfg-v1")
        _write(base / "cfg.json", json.dumps({"cfg": {}, "roots": [], "code_ranges": []}))
        payload = self._run(self._index([_family("rom-cfg-v1")]))
        row = payload["shelf"][0]
        self.assertEqual(row["tier"], "analysis-only")
        self.assertIn("cfg", row["evidence"]["structural_markers"])

    def test_boilerplate_keys_do_not_decide_the_verdict(self) -> None:
        """``scope``/``rom``/``summary`` are on every result; they carry no signal."""
        base = self._family_dir("rom-boilerplate-v1")
        _write(
            base / "payload.json",
            json.dumps({"schema": "x", "rom": {}, "scope": {}, "summary": "s"}),
        )
        payload = self._run(self._index([_family("rom-boilerplate-v1")]))
        self.assertEqual(payload["shelf"][0]["tier"], "unclassified")

    def test_mixed_payload_is_decided_by_the_larger_vocabulary(self) -> None:
        """A content table that also carries coverage denominators is a table.

        The dialogue table family holds 80 text records under ``gaps`` and
        describes the table under ``table``; the coverage keys around it are
        bookkeeping.  The verdict follows the larger vocabulary.
        """
        base = self._family_dir("rom-mixed-v1")
        _write(
            base / "payload.json",
            json.dumps({"table": {}, "targets": [], "consumer": {}, "gaps": []}),
        )
        payload = self._run(self._index([_family("rom-mixed-v1")]))
        row = payload["shelf"][0]
        self.assertEqual(row["tier"], "table-direct")
        self.assertIn("table", row["evidence"]["table_markers"])

    def test_a_tie_between_the_vocabularies_is_not_forced(self) -> None:
        base = self._family_dir("rom-tie-v1")
        _write(base / "payload.json", json.dumps({"records": [], "cfg": {}}))
        payload = self._run(self._index([_family("rom-tie-v1")]))
        row = payload["shelf"][0]
        self.assertEqual(row["tier"], "unclassified")
        self.assertIn("records", row["evidence"]["table_markers"])
        self.assertIn("cfg", row["evidence"]["structural_markers"])

    def test_a_list_payload_is_probed_through_its_first_record(self) -> None:
        base = self._family_dir("rom-list-v1")
        _write(base / "payload.json", json.dumps([{"bindings": [], "slot": 1}]))
        payload = self._run(self._index([_family("rom-list-v1")]))
        row = payload["shelf"][0]
        self.assertEqual(row["tier"], "table-direct")
        self.assertIn("bindings", row["evidence"]["table_markers"])

    def test_scope_open_claims_are_reported(self) -> None:
        """A family may ship an importable table and still not be closed.

        The manifest's ``scope`` block states what the result does not claim
        -- most often that natural runtime reachability is unproven.  That
        difference decides whether the remake may rely on the result, so it
        is measured, not assumed.
        """
        base = self._family_dir("rom-open-scope-v1")
        _write(
            base / "manifest.json",
            json.dumps(
                {
                    "schema": "rom-open-scope-v1",
                    "artifact_status": "accepted",
                    "scope": {
                        "natural_runtime_reachability": False,
                        "index_domain_closed": True,
                    },
                }
            ),
        )
        _write(base / "payload.bin", b"\x00")
        payload = self._run(self._index([_family("rom-open-scope-v1")]))
        row = payload["shelf"][0]
        self.assertFalse(row["scope_closed"])
        self.assertEqual(row["scope_open_claims"], ["natural_runtime_reachability"])
        self.assertEqual(payload["summary"]["shelf_scope_open"], 1)

    def test_a_closed_scope_is_reported_as_closed(self) -> None:
        base = self._family_dir("rom-closed-scope-v1")
        _write(
            base / "manifest.json",
            json.dumps(
                {
                    "schema": "rom-closed-scope-v1",
                    "artifact_status": "accepted",
                    "scope": {"natural_runtime_reachability": True},
                }
            ),
        )
        _write(base / "payload.bin", b"\x00")
        payload = self._run(self._index([_family("rom-closed-scope-v1")]))
        self.assertTrue(payload["shelf"][0]["scope_closed"])
        self.assertEqual(payload["summary"]["shelf_scope_closed"], 1)

    def test_summary_counts_agree_with_the_rows(self) -> None:
        for family_id, status in (
            ("rom-a-v1", "accepted"),
            ("rom-b-v1", "accepted"),
            ("rom-c-v1", "candidate"),
        ):
            base = self._family_dir(family_id, status=status)
            _write(base / "payload.bin", b"\x00")
        payload = self._run(
            self._index([_family("rom-a-v1"), _family("rom-b-v1"), _family("rom-c-v1")]),
            statuses={"rom-b-v1": "build"},
        )
        summary = payload["summary"]
        self.assertEqual(summary["families_total"], len(payload["rows"]))
        self.assertEqual(summary["shelf_total"], len(payload["shelf"]))
        self.assertEqual(
            summary["shelf_total"], sum(summary["shelf_by_tier"].values())
        )
        self.assertEqual(summary["families_accepted"], 2)

    def test_notes_index_buckets_are_carried_through(self) -> None:
        base = self._family_dir("rom-a-v1")
        _write(base / "payload.bin", b"\x00")
        notes_index = {
            "schema": "konoha.reverse-notes-index.v1",
            "summary": {
                "total": 3,
                "by_bucket": {"needs_guard": 2, "implemented_in_code": 1},
                "needs_guard_without_any_test_reference": 2,
            },
        }
        payload = self._run(
            self._index([_family("rom-a-v1")]), notes_index=notes_index
        )
        notes = payload["summary"]["notes"]
        self.assertIsNotNone(notes)
        self.assertEqual(notes["by_bucket"]["needs_guard"], 2)

    def test_missing_input_fails_closed(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(self.root),
                "--index",
                str(self.root / "missing.json"),
                "--gap",
                str(self.root / "missing-gap.json"),
                "--out-dir",
                str(self.root / "out"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("error", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()


class VerifierOnlyReferenceTest(unittest.TestCase):
    """A family that only a verifier names is **verified against**, not consumed.

    A tool that reads a family's manifest to check its identity proves the
    result is real; it does not make the remake use the payload.  Counting
    that as consumption moves the family off the shelf and inflates the
    consumed count, so the rule has to be pinned.
    """

    def test_a_verifier_only_reference_does_not_consume_the_family(self) -> None:
        payload = {
            "schema": "konoha.butano-usable-backlog.v1",
            "shelf": [],
            "summary": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / "artifacts" / "butano-usable-backlog-v1" / "backlog.json",
                json.dumps(payload),
            )
            _write(
                root / "artifacts" / "butano-reverse-gap-v1" / "gap.json",
                json.dumps(
                    {
                        "rows": [
                            {
                                "id": "rom-demo-v1",
                                "status": "build",
                                "hits": [
                                    "build:tools/verify_rom_demo.py",
                                ],
                            },
                            {
                                "id": "rom-used-v1",
                                "status": "build",
                                "hits": [
                                    "build:tools/generate_demo_content.py",
                                ],
                            },
                        ]
                    }
                ),
            )
            index = {
                "schema": "konoha.reverse-results-index.v1",
                "source": {"reverse_root": str(root / "reverse")},
                "entries": [
                    {
                        "id": "rom-demo-v1",
                        "kind": "artifact",
                        "category": "rom",
                        "path": "artifacts/rom-demo-v1",
                        "manifest": "artifacts/rom-demo-v1/manifest.json",
                    },
                    {
                        "id": "rom-used-v1",
                        "kind": "artifact",
                        "category": "rom",
                        "path": "artifacts/rom-used-v1",
                        "manifest": "artifacts/rom-used-v1/manifest.json",
                    },
                ],
            }
            _write(
                root / "artifacts" / "reverse-results-index-v1" / "index.json",
                json.dumps(index),
            )
            reverse = root / "reverse"
            for family in ("rom-demo-v1", "rom-used-v1"):
                artifact = reverse / "artifacts" / family
                artifact.mkdir(parents=True)
                # A table-shaped payload so the family lands on the shelf, and
                # the manifest has to hash it correctly or the artifact is
                # not accepted at all.
                payload = json.dumps({"table": [1, 2]})
                _write(artifact / "payload.json", payload)
                _write(
                    artifact / "manifest.json",
                    json.dumps(
                        {
                            "artifact_status": "accepted",
                            "files": {
                                "payload.json": hashlib.sha256(
                                    payload.encode("utf-8")
                                ).hexdigest()
                            },
                        }
                    ),
                )
            out = root / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(root),
                    "--index",
                    str(root / "artifacts" / "reverse-results-index-v1" / "index.json"),
                    "--gap",
                    str(root / "artifacts" / "butano-reverse-gap-v1" / "gap.json"),
                    "--out-dir",
                    str(out),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(
                (out / "backlog.json").read_text(encoding="utf-8")
            )
            rows = {row["id"]: row for row in result["shelf"]}
            self.assertIn("rom-demo-v1", rows)
            self.assertEqual(rows["rom-demo-v1"]["consumption_evidence"], "verifier-only")
            self.assertNotIn("rom-used-v1", rows)
