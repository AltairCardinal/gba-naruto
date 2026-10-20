#!/usr/bin/env python3
"""Every reverse note must land in exactly one disposition bucket, verifiably.

The reverse work tree holds 427 note files.  The gap measurement
(``tools/measure_butano_reverse_gap.py``) can only say whether a note is
*mentioned* somewhere in the remake tree; it cannot say what should happen
with it.  The M5 milestone needs that: each note either already landed in
code, has to become a gate, does not apply to this remake, or still lacks
evidence on the reverse side.

The rules this test pins down:

* every note file in the reverse tree gets exactly one bucket, and the bucket
  counts add up to the number of note files -- no note may fall through;
* a note that claims to be implemented must point at a file in this tree and
  at a line inside that file; a pointer that does not resolve is a problem,
  not a detail;
* a note that claims not to apply must say why, and a note that claims to
  lack evidence must say what is missing;
* the classification script must not hard-code note names.  It has to find
  the notes by walking the reverse tree, and its own source must not contain
  any note identifier -- otherwise the script would raise the ``build``
  count of the gap measurement by naming the conclusions it claims to
  classify;
* the script fails closed: no reverse tree, no notes, or a classification
  that does not add up is a non-zero exit with a named reason, never a
  silently shortened index.

The fixture reverse tree is built inside the test so the failure modes are
exercised without depending on another work tree.  The checks against the
real reverse tree are skipped when that tree is not present.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_reverse_notes_index import (  # noqa: E402
    BUCKETS,
    EXIT_INCONSISTENT,
    EXIT_NO_NOTES,
    EXIT_REVERSE_TREE_MISSING,
    NOTES_INDEX_SCHEMA,
    build_index,
    check_payload,
    main,
    note_identifiers,
)

REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")

# The token shape the gap measurement uses to find a note identifier in a
# file.  It is reproduced here so the "no hard-coded names" check matches
# what the gap tool would actually see.
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_reverse_tree(base: Path) -> Path:
    """A miniature reverse tree with one note of each interesting kind."""
    notes = base / "notes"
    _write(notes / "fixture-implemented-note.md", "# implemented\n\n本条已被本树消费。\n")
    _write(
        notes / "fixture-guard-note.md",
        "# guard\n\n原版在 0x08001234 处必须先做 X 再做 Y，不得跳过。\n",
    )
    _write(
        notes / "fixture-gap-note.md",
        "# gap\n\n结论未成立，仍缺证据：0x0800AAAA 的语义尚未取证。\n",
    )
    _write(
        notes / "fixture-process-note.md",
        "# process\n\n本轮只做子代理计时基准与守卫收据，不涉及 ROM 行为。\n",
    )
    _write(notes / "fixture-review-note.md", "# review\n\n一段没有任何可判定信号的说明文字。\n")
    _write(
        notes / "evidence" / "fixture-bundle-v1" / "implementation" / "docs" / "fixture-vendored-snapshot.md",
        "# vendored\n\n逆向树自身文件快照。\n",
    )
    return base


def _fixture_remake_tree(base: Path) -> Path:
    """A miniature remake tree with one consumer of one note."""
    _write(
        base / "tools" / "fixture_consumer.py",
        '"""Consumer."""\n\nFIXTURE = "fixture-implemented-note"\n',
    )
    _write(base / "docs" / "fixture.md", "mentions fixture-guard-note only\n")
    return base


class ClassificationShapeTest(unittest.TestCase):
    """The classification itself has to be complete and self-consistent."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.reverse = _fixture_reverse_tree(self.tmp / "reverse")
        self.remake = _fixture_remake_tree(self.tmp / "remake")
        self.payload = build_index(self.remake, self.reverse)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_every_note_gets_exactly_one_bucket(self) -> None:
        rows = self.payload["notes"]
        note_files = sorted((self.reverse / "notes").rglob("*.md"))
        self.assertEqual(len(rows), len(note_files))
        for row in rows:
            self.assertIn(row["bucket"], BUCKETS, row["path"])

    def test_bucket_counts_add_up_to_the_note_count(self) -> None:
        summary = self.payload["summary"]
        counted = sum(summary["by_bucket"].values())
        self.assertEqual(counted, summary["total"])
        self.assertEqual(summary["total"], len(self.payload["notes"]))
        for bucket in summary["by_bucket"]:
            self.assertIn(bucket, BUCKETS)

    def test_the_fixture_lands_in_the_expected_buckets(self) -> None:
        by_id = {row["id"]: row for row in self.payload["notes"]}
        self.assertEqual(by_id["fixture-implemented-note"]["bucket"], "implemented_in_code")
        self.assertEqual(by_id["fixture-guard-note"]["bucket"], "needs_guard")
        self.assertEqual(by_id["fixture-gap-note"]["bucket"], "missing_evidence")
        self.assertEqual(by_id["fixture-process-note"]["bucket"], "not_applicable")
        self.assertEqual(by_id["fixture-review-note"]["bucket"], "needs_human_review")
        self.assertEqual(
            by_id["fixture-vendored-snapshot"]["bucket"], "not_applicable"
        )

    def test_implemented_bucket_points_at_a_real_consumer(self) -> None:
        implemented = [
            row for row in self.payload["notes"] if row["bucket"] == "implemented_in_code"
        ]
        self.assertTrue(implemented, "the fixture consumer was not picked up")
        for row in implemented:
            self.assertTrue(row["consumers"], row["path"])
            for consumer in row["consumers"]:
                target = self.remake / consumer["path"]
                self.assertTrue(target.is_file(), consumer["path"])
                lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
                self.assertGreaterEqual(consumer["line"], 1)
                self.assertLessEqual(consumer["line"], len(lines), consumer["path"])

    def test_not_applicable_bucket_states_a_reason(self) -> None:
        for row in self.payload["notes"]:
            if row["bucket"] != "not_applicable":
                continue
            self.assertTrue(row["reason"].strip(), row["path"])
            self.assertTrue(row["evidence"].strip(), row["path"])

    def test_missing_evidence_bucket_states_what_is_missing(self) -> None:
        for row in self.payload["notes"]:
            if row["bucket"] != "missing_evidence":
                continue
            self.assertTrue(row["reason"].strip(), row["path"])
            self.assertTrue(row["missing"], row["path"])

    def test_every_row_carries_a_reason(self) -> None:
        for row in self.payload["notes"]:
            self.assertTrue(row["reason"].strip(), row["path"])

    def test_pre_index_status_is_recorded(self) -> None:
        for row in self.payload["notes"]:
            self.assertIn(
                row["pre_index_status"],
                ("build", "local_artifact", "test", "doc", "none"),
                row["path"],
            )

    def test_the_implemented_note_is_not_also_a_guard(self) -> None:
        by_id = {row["id"]: row for row in self.payload["notes"]}
        self.assertEqual(by_id["fixture-implemented-note"]["pre_index_status"], "build")
        self.assertEqual(by_id["fixture-guard-note"]["pre_index_status"], "doc")


class NoHardCodedNamesTest(unittest.TestCase):
    """The script may not name the conclusions it classifies."""

    def _script_text(self) -> str:
        return (ROOT / "tools" / "build_reverse_notes_index.py").read_text(
            encoding="utf-8"
        )

    def test_script_contains_no_note_identifier(self) -> None:
        if not REVERSE_ROOT.is_dir():
            self.skipTest("reverse work tree is not present")
        script = self._script_text()
        tokens = {token.lower() for token in _TOKEN_RE.findall(script)}
        offenders = []
        for path in sorted((REVERSE_ROOT / "notes").rglob("*.md")):
            identifier = path.stem.lower()
            # The gap measurement only matches identifiers of at least this
            # length as bare tokens; shorter ones can never raise a status.
            if len(identifier) < 8:
                continue
            if identifier in tokens:
                offenders.append(identifier)
        self.assertEqual(
            offenders, [], "the classification script names notes it should discover"
        )

    def test_test_file_contains_no_note_identifier(self) -> None:
        if not REVERSE_ROOT.is_dir():
            self.skipTest("reverse work tree is not present")
        script = (ROOT / "tests" / "test_reverse_notes_index.py").read_text(
            encoding="utf-8"
        )
        tokens = {token.lower() for token in _TOKEN_RE.findall(script)}
        offenders = []
        for path in sorted((REVERSE_ROOT / "notes").rglob("*.md")):
            identifier = path.stem.lower()
            if len(identifier) < 8:
                continue
            if identifier in tokens:
                offenders.append(identifier)
        self.assertEqual(
            offenders, [], "the test names notes it should discover"
        )

    def test_script_does_not_contain_a_literal_name_list(self) -> None:
        script = self._script_text()
        # Most note names carry a date stamp, so a hard-coded roster would
        # show up as quoted date-stamped names, or as a literal list of
        # names.  Neither may appear.
        stamped = re.findall(r"[\"']([a-z0-9-]*\d{6,8})[\"']", script)
        self.assertEqual(stamped, [], "the script carries date stamped note names")
        literal_list = re.findall(r"\[\s*\"[a-z0-9-]{8,}\"\s*,", script)
        self.assertEqual(
            literal_list, [], "the script carries a literal list of note names"
        )

    def test_script_does_not_carry_a_date_stamped_roster(self) -> None:
        script = self._script_text()
        stamps = re.findall(r"\d{8}", script)
        self.assertLessEqual(
            len(stamps),
            0,
            "the script mentions dated note identifiers, which is a roster",
        )


class FailClosedTest(unittest.TestCase):
    """Broken inputs must be named, never silently shortened."""

    def test_missing_reverse_tree_exits_non_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = main(
                [
                    "--root",
                    str(ROOT),
                    "--reverse-root",
                    str(Path(tmp) / "does-not-exist"),
                    "--out-dir",
                    str(Path(tmp) / "out"),
                    "--doc",
                    str(Path(tmp) / "out" / "notes-index.md"),
                ]
            )
        self.assertEqual(code, EXIT_REVERSE_TREE_MISSING)

    def test_reverse_tree_without_notes_exits_non_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "reverse"
            (empty / "notes").mkdir(parents=True)
            code = main(
                [
                    "--root",
                    str(ROOT),
                    "--reverse-root",
                    str(empty),
                    "--out-dir",
                    str(Path(tmp) / "out"),
                    "--doc",
                    str(Path(tmp) / "out" / "notes-index.md"),
                ]
            )
        self.assertEqual(code, EXIT_NO_NOTES)

    def test_inconsistent_classification_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reverse = _fixture_reverse_tree(Path(tmp) / "reverse")
            remake = _fixture_remake_tree(Path(tmp) / "remake")
            out = Path(tmp) / "out"
            code = main(
                [
                    "--root",
                    str(remake),
                    "--reverse-root",
                    str(reverse),
                    "--out-dir",
                    str(out),
                    "--doc",
                    str(out / "notes-index.md"),
                ]
            )
            self.assertEqual(code, 0)
            payload = json.loads((out / "notes-index.json").read_text(encoding="utf-8"))
        self.assertEqual(check_payload(payload), [])
        # Break the counts and make sure the checker notices.
        payload["summary"]["by_bucket"]["needs_guard"] += 1
        problems = check_payload(payload)
        self.assertTrue(problems)
        self.assertTrue(any("add up" in problem for problem in problems), problems)

    def test_a_row_without_a_reason_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reverse = _fixture_reverse_tree(Path(tmp) / "reverse")
            remake = _fixture_remake_tree(Path(tmp) / "remake")
            payload = build_index(remake, reverse)
        payload["notes"][0]["reason"] = "  "
        problems = check_payload(payload)
        self.assertTrue(problems)
        self.assertTrue(any("no reason" in problem for problem in problems), problems)


class RealTreeTest(unittest.TestCase):
    """The shipped index must cover the real reverse tree."""

    @classmethod
    def setUpClass(cls) -> None:
        if not REVERSE_ROOT.is_dir():
            raise unittest.SkipTest("reverse work tree is not present")
        cls._tmp = tempfile.TemporaryDirectory()
        out = Path(cls._tmp.name) / "out"
        code = main(
            [
                "--root",
                str(ROOT),
                "--reverse-root",
                str(REVERSE_ROOT),
                "--out-dir",
                str(out),
                "--doc",
                str(out / "notes-index.md"),
            ]
        )
        if code != 0:
            raise AssertionError(f"the index builder failed with {code}")
        cls.payload = json.loads((out / "notes-index.json").read_text(encoding="utf-8"))
        cls.note_files = sorted((REVERSE_ROOT / "notes").rglob("*.md"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_index_covers_every_note_file(self) -> None:
        self.assertEqual(self.payload["schema"], NOTES_INDEX_SCHEMA)
        self.assertEqual(len(self.payload["notes"]), len(self.note_files))
        self.assertEqual(self.payload["summary"]["total"], len(self.note_files))

    def test_no_note_is_left_without_a_bucket(self) -> None:
        paths = {row["path"] for row in self.payload["notes"]}
        expected = {
            path.relative_to(REVERSE_ROOT).as_posix() for path in self.note_files
        }
        self.assertEqual(paths, expected)

    def test_summary_matches_the_rows(self) -> None:
        counted: dict[str, int] = {}
        for row in self.payload["notes"]:
            counted[row["bucket"]] = counted.get(row["bucket"], 0) + 1
        self.assertEqual(self.payload["summary"]["by_bucket"], counted)

    def test_needs_guard_split_is_recomputed_from_the_rows(self) -> None:
        # M5's goal is "turn every conclusion into a gate", so the size of the
        # `needs_guard` bucket alone would misstate what is left to do: some of
        # those notes are already referenced from a test.  The split is
        # recomputed here so the shipped number cannot drift.
        summary = self.payload["summary"]
        referenced = [
            row
            for row in self.payload["notes"]
            if row["bucket"] == "needs_guard"
            and any(
                str(reference).startswith("test:")
                for reference in row.get("pre_index_references", [])
            )
        ]
        self.assertEqual(
            summary["needs_guard_already_referenced_from_tests"],
            len(referenced),
        )
        self.assertEqual(
            summary["needs_guard_without_any_test_reference"],
            summary["by_bucket"]["needs_guard"] - len(referenced),
        )

    def test_identifiers_are_derived_not_declared(self) -> None:
        # The identifier of a note is its file stem, so the index can be
        # rebuilt from the tree alone.
        for row in self.payload["notes"]:
            stem = Path(row["path"]).stem
            self.assertEqual(row["id"], stem)
            self.assertIn(stem, note_identifiers(row["id"]))

    def test_the_index_is_self_consistent(self) -> None:
        self.assertEqual(check_payload(self.payload), [])

    def test_human_review_stays_small(self) -> None:
        review = self.payload["summary"]["by_bucket"].get("needs_human_review", 0)
        self.assertLess(
            review,
            max(1, self.payload["summary"]["total"] // 10),
            "the bucket for notes that cannot be decided automatically is too large",
        )


class ShippedIndexTest(unittest.TestCase):
    """The index that ships with the repository must be the one the script makes."""

    def test_shipped_artifact_matches_a_fresh_build(self) -> None:
        artifact = ROOT / "artifacts" / "reverse-notes-index-v1" / "notes-index.json"
        if not artifact.is_file():
            self.skipTest("the notes index has not been built yet")
        if not REVERSE_ROOT.is_dir():
            self.skipTest("reverse work tree is not present")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            code = main(
                [
                    "--root",
                    str(ROOT),
                    "--reverse-root",
                    str(REVERSE_ROOT),
                    "--out-dir",
                    str(out),
                    "--doc",
                    str(out / "notes-index.md"),
                ]
            )
            self.assertEqual(code, 0)
            fresh = json.loads((out / "notes-index.json").read_text(encoding="utf-8"))
        shipped = json.loads(artifact.read_text(encoding="utf-8"))
        self.assertEqual(
            shipped["summary"]["by_bucket"], fresh["summary"]["by_bucket"]
        )
        self.assertEqual(
            [(row["path"], row["bucket"]) for row in shipped["notes"]],
            [(row["path"], row["bucket"]) for row in fresh["notes"]],
        )


if __name__ == "__main__":
    unittest.main()
