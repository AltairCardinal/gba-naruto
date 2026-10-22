#!/usr/bin/env python3
"""Every wire between the reverse results and the remake must be enumerable.

``tools/audit_butano_reverse_provenance.py`` records the *declared* wires: a
generated product states which reverse family it consumes and which ROM bytes
it read.  That registry is the truth about the wires that exist, and it says
nothing about the wires that are missing.  This test pins down the rules that
make the missing ones enumerable:

* the source side is **every** reverse family, not only the ones that happen
  to be on the shelf -- a family that is consumed but not declared still has a
  state, and it is a different state from one that is consumed *and* declared;
* a **declared** wire is a fact (the product says so and the auditor re-hashes
  the manifest); a **mentioned** wire is only the gap tool's lower bound -- a
  family name showing up in the build chain is not a proven byte lineage, and
  the two must not be counted as the same thing;
* the sink side is censused, not judged: a hand-written header with no source
  declaration is a fact about the census, not a verdict that it is wrong;
* "has a gate" is an **upper bound**: a test that names a product may be a
  documentation test, so the count may only be used as "possibly gated".
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "measure_butano_wiring_coverage.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _index(families: list[str]) -> dict:
    return {
        "schema": "konoha.reverse-results-index.v1",
        "source": {"reverse_root": "/tmp/reverse", "commit": "0" * 40, "dirty": False},
        "categories": {},
        "entries": [
            {
                "id": family,
                "kind": "artifact",
                "category": "rom",
                "path": f"artifacts/{family}",
                "manifest": f"artifacts/{family}/manifest.json",
                "schema": "",
                "provides": [],
                "formulas": [],
                "addresses": [],
                "depends_on": [],
            }
            for family in families
        ],
        "ledger": [],
        "ledger_problems": [],
    }


def _backlog(rows: list[dict]) -> dict:
    return {
        "schema": "konoha.butano-usable-backlog.v1",
        "shelf": rows,
        "summary": {},
    }


class WiringCoverageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _run(
        self,
        index: dict,
        gap_status: dict[str, str],
        backlog_rows: list[dict],
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
                        {"id": family, "status": gap_status.get(family, "none")}
                        for family in (entry["id"] for entry in index["entries"])
                    ],
                }
            ),
        )
        backlog_path = self.root / "artifacts" / "butano-usable-backlog-v1" / "backlog.json"
        _write(backlog_path, json.dumps(_backlog(backlog_rows)))
        out_dir = self.root / "artifacts" / "butano-wiring-coverage-v1"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(self.root),
                "--backlog",
                str(backlog_path),
                "--gap",
                str(gap_path),
                "--index",
                str(index_path),
                "--reverse-root",
                str(self.root / "reverse"),
                "--out-dir",
                str(out_dir),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads((out_dir / "wiring.json").read_text(encoding="utf-8"))

    # -- tests -----------------------------------------------------------

    def test_a_family_nobody_consumes_is_on_the_shelf(self) -> None:
        payload = self._run(
            _index(["rom-a-v1"]),
            {"rom-a-v1": "doc"},
            [
                {
                    "id": "rom-a-v1",
                    "category": "rom",
                    "tier": "asset-direct",
                    "scope_closed": True,
                    "payload_bytes": 10,
                }
            ],
        )
        row = payload["source_rows"][0]
        self.assertEqual(row["state"], "on-shelf")
        self.assertEqual(row["consumers"], [])

    def test_a_family_the_build_chain_mentions_is_not_counted_as_declared(self) -> None:
        """A name match is the gap tool's lower bound, not a proven lineage.

        The provenance auditor's own contract says so: only a declaration
        binds a product to a family.  A family that is merely mentioned must
        get a state that is not "wired", or the matrix would overstate how
        much of the reverse work is actually wired in.
        """
        payload = self._run(
            _index(["rom-b-v1"]),
            {"rom-b-v1": "build"},
            [],
        )
        row = payload["source_rows"][0]
        self.assertNotIn(row["state"], ("wired-and-gated", "wired-ungated"))
        self.assertEqual(row["consumers"], [])

    def test_a_local_output_that_is_absent_is_reported_as_missing(self) -> None:
        """A remake-side exporter is not the same thing as a local copy.

        The exporter names the family as its schema tag and writes into this
        tree's own ``artifacts/<family>/``.  When that copy is not on disk,
        the family has a tool but no local result -- a different state from
        one that was re-derived and is present.
        """
        payload = self._run(
            _index(["rom-c-v1"]),
            {"rom-c-v1": "build"},
            [],
        )
        row = payload["source_rows"][0]
        self.assertEqual(row["state"], "local-derivation-missing")

    def test_a_local_copy_that_matches_the_original_is_reported_as_identical(self) -> None:
        (self.root / "artifacts" / "rom-d-v1").mkdir(parents=True)
        (self.root / "artifacts" / "rom-d-v1" / "manifest.json").write_text("{}\n")
        reverse = self.root / "reverse" / "artifacts" / "rom-d-v1"
        reverse.mkdir(parents=True)
        (reverse / "manifest.json").write_text("{}\n")
        payload = self._run(
            _index(["rom-d-v1"]),
            {"rom-d-v1": "build"},
            [],
        )
        row = payload["source_rows"][0]
        self.assertEqual(row["state"], "local-rederived-identical")

    def test_a_local_copy_that_diverged_is_reported_as_diverged(self) -> None:
        (self.root / "artifacts" / "rom-e-v1").mkdir(parents=True)
        (self.root / "artifacts" / "rom-e-v1" / "manifest.json").write_text('{"a": 1}\n')
        reverse = self.root / "reverse" / "artifacts" / "rom-e-v1"
        reverse.mkdir(parents=True)
        (reverse / "manifest.json").write_text('{"a": 2}\n')
        payload = self._run(
            _index(["rom-e-v1"]),
            {"rom-e-v1": "build"},
            [],
        )
        row = payload["source_rows"][0]
        self.assertEqual(row["state"], "local-rederived-diverged")

    def test_a_local_copy_with_the_same_manifest_but_a_changed_payload_is_diverged(self) -> None:
        """A manifest hash only proves the description matches.

        The payload is the evidence.  A local copy that keeps the manifest and
        changes a data file is a broken wire, so the state has to be decided
        on the content of the tree.
        """
        local = self.root / "artifacts" / "rom-f-v1"
        local.mkdir(parents=True)
        (local / "manifest.json").write_text('{"a": 1}\n')
        (local / "payload.bin").write_bytes(b"\x01")
        reverse = self.root / "reverse" / "artifacts" / "rom-f-v1"
        reverse.mkdir(parents=True)
        (reverse / "manifest.json").write_text('{"a": 1}\n')
        (reverse / "payload.bin").write_bytes(b"\x02")
        payload = self._run(
            _index(["rom-f-v1"]),
            {"rom-f-v1": "build"},
            [],
        )
        row = payload["source_rows"][0]
        self.assertEqual(row["state"], "local-rederived-diverged")
        self.assertEqual(row["local_copy"]["local_manifest_sha256"], row["local_copy"]["reverse_manifest_sha256"])
        self.assertNotEqual(row["local_copy"]["local_tree_sha256"], row["local_copy"]["reverse_tree_sha256"])

    def test_a_family_without_a_manifest_twin_is_decided_by_its_content(self) -> None:
        """Capture families have no manifest at all.

        They still have a twin, so the state must be decided by the bytes:
        a copy that matches is identical, a copy that does not is diverged.
        """
        local = self.root / "artifacts" / "rom-g-v1"
        local.mkdir(parents=True)
        (local / "state.ss9").write_bytes(b"same")
        reverse = self.root / "reverse" / "artifacts" / "rom-g-v1"
        reverse.mkdir(parents=True)
        (reverse / "state.ss9").write_bytes(b"same")
        payload = self._run(
            _index(["rom-g-v1"]),
            {"rom-g-v1": "build"},
            [],
        )
        row = payload["source_rows"][0]
        self.assertEqual(row["state"], "local-rederived-identical")
        self.assertIsNone(row["local_copy"]["local_manifest_sha256"])

        (local / "state.ss9").write_bytes(b"other")
        payload = self._run(
            _index(["rom-g-v1"]),
            {"rom-g-v1": "build"},
            [],
        )
        row = payload["source_rows"][0]
        self.assertEqual(row["state"], "local-rederived-diverged")

    def test_a_local_copy_with_a_different_file_set_is_diverged(self) -> None:
        local = self.root / "artifacts" / "rom-h-v1"
        local.mkdir(parents=True)
        (local / "manifest.json").write_text("{}\n")
        (local / "extra.bin").write_bytes(b"x")
        reverse = self.root / "reverse" / "artifacts" / "rom-h-v1"
        reverse.mkdir(parents=True)
        (reverse / "manifest.json").write_text("{}\n")
        payload = self._run(
            _index(["rom-h-v1"]),
            {"rom-h-v1": "build"},
            [],
        )
        row = payload["source_rows"][0]
        self.assertEqual(row["state"], "local-rederived-diverged")

    def test_a_family_with_no_material_and_no_consumer_is_reported(self) -> None:
        payload = self._run(
            _index(["rom-c-v1"]),
            {"rom-c-v1": "none"},
            [],
        )
        row = payload["source_rows"][0]
        self.assertEqual(row["state"], "no-material")

    def test_every_family_gets_exactly_one_state(self) -> None:
        families = ["rom-a-v1", "rom-b-v1", "rom-c-v1"]
        payload = self._run(
            _index(families),
            {"rom-b-v1": "build"},
            [
                {
                    "id": "rom-a-v1",
                    "category": "rom",
                    "tier": "table-direct",
                    "scope_closed": None,
                    "payload_bytes": 5,
                }
            ],
        )
        self.assertEqual(len(payload["source_rows"]), len(families))
        self.assertEqual(payload["summary"]["source_total"], len(families))
        self.assertEqual(
            sum(payload["summary"]["source_by_state"].values()), len(families)
        )

    def test_the_sink_surface_is_censused(self) -> None:
        _write(self.root / "butano-sequel" / "game" / "include" / "konoha" / "generated_a.h", "// x\n")
        _write(self.root / "butano-sequel" / "game" / "include" / "konoha" / "handwritten.h", "// x\n")
        _write(self.root / "sequel" / "content" / "units" / "bank.json", "{}\n")
        _write(self.root / "butano-sequel" / "graphics" / "a.bmp", "x")
        _write(self.root / "tests" / "test_x.py", "# x\n")
        payload = self._run(_index([]), {}, [])
        surface = payload["summary"]["sink_surface"]
        self.assertEqual(surface["generated_headers"], 1)
        self.assertEqual(surface["handwritten_headers"], 1)
        self.assertEqual(surface["content_banks"], 1)
        self.assertEqual(surface["graphic_assets"], 1)
        self.assertEqual(surface["test_modules"], 1)

    def test_a_missing_input_fails_closed(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(self.root),
                "--backlog",
                str(self.root / "missing.json"),
                "--gap",
                str(self.root / "missing-gap.json"),
                "--index",
                str(self.root / "missing-index.json"),
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


class DeclaredCoverageTest(unittest.TestCase):
    """The coverage assertion W3 asks for.

    *What the auditor can see as a declared wire* must equal *what the matrix
    counts as wired*.  The auditor reads two carriers -- the provenance
    header comment and the ROM importers' own constants -- so a wire that
    only one of them can see shows up as a difference instead of as a silent
    understatement.
    """

    def test_the_real_tree_has_no_difference(self) -> None:
        wiring_path = (
            ROOT / "artifacts" / "butano-wiring-coverage-v1" / "wiring.json"
        )
        if not wiring_path.is_file():
            self.skipTest("no wiring receipt in this tree")
        payload = json.loads(wiring_path.read_text(encoding="utf-8"))
        coverage = payload["summary"]["declared_coverage"]
        self.assertEqual(coverage["difference"], 0, coverage)
        self.assertEqual(
            coverage["declared_by_auditor"], coverage["declared_by_matrix"]
        )

    def test_the_auditor_and_the_matrix_see_the_same_families(self) -> None:
        sys.path.insert(0, str(ROOT))
        from tools.audit_butano_reverse_provenance import audit

        report = audit(ROOT, "/Users/altair/github/gba-naruto-reverse")
        header = {family for _product, family in report.mapping}
        importer = {wire.family for wire in report.importer_wires}
        self.assertTrue(header, "the header carrier must declare families")
        self.assertTrue(importer, "the importer carrier must declare families")
        self.assertEqual(report.declared_family_count, len(header | importer))
