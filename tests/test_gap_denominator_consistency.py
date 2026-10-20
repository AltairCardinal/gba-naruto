#!/usr/bin/env python3
"""The published gap figures must agree with the machine receipt that produced them.

The measurement itself was never wrong: ``tools/measure_butano_reverse_gap.py``
derives every count from the rows it emits.  What went wrong was the *label*
around it.  A hard-coded divisor (``100*c['build']/262``) kept a stale
denominator alive in prose and reports while the very same command printed a
breakdown that summed to 264.  The reverse work tree made it worse: promoting
two new artifact families into ``artifacts/`` moved the denominator from 262 to
264 without changing a single numerator, so a report that had been right an
hour earlier became wrong with no edit to the measurement.

That failure mode is invisible to a test that only checks the tool.  These
tests pin the two seams where the number is copied out of the machine:

* the published receipt must still describe the published index (hash and
  denominator), so a stale receipt cannot quietly pass as a fresh one;
* the "current state" sections of the documents must quote the live
  denominator, and any claim that pairs the current build count with a
  different denominator has to be marked as a correction.

When the reverse tree advances and the receipt is rebuilt, these tests turn
red on purpose: the documents have to be refreshed to the new figures.  That
red is the signal, not a regression.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "artifacts" / "reverse-results-index-v1" / "index.json"
RECEIPT = ROOT / "artifacts" / "butano-reverse-gap-v1" / "gap.json"

# A percentage claim of the shape ``92/264 = 34.8%`` and its mirror image
# ``34.8% = 92/264``.  Both are read as (numerator, denominator, percent).
CLAIM = re.compile(r"(\d+)\s*/\s*(\d+)\s*=\s*([\d.]+)\s*%")
MIRRORED_CLAIM = re.compile(r"([\d.]+)\s*%\s*=\s*(\d+)\s*/\s*(\d+)")

# A claim may keep a denominator that is not the live one only when the line
# says out loud that it is wrong -- that is how the correction sections are
# allowed to quote the mistake they are correcting, and how a mutation test
# is allowed to name the value it injects.
CORRECTION_MARKERS = (
    "是错的",
    "（错）",
    "更正",
    "原写",
    "已更正",
    "改回",
    "变异",
    "旧值",
)

# The documents that state the *current* figures, and the anchor that starts
# the current-state part of each one.  Everything from the anchor onwards is
# checked; the parts before it are historical snapshots that are allowed to
# quote the denominator that was live at the time.
CURRENT_STATE_REGIONS: tuple[tuple[str, str, str, str | None], ...] = (
    (
        "docs/butano-reverse-gap-roadmap.md",
        "### 7.7",
        "roadmap current state",
        None,
    ),
    (
        "notes/butano-reverse-gap-verification-20261020.md",
        "### 11.10",
        "verification note correction",
        None,
    ),
    (
        "docs/konoha-senki/README.md",
        "逆向成果索引与复刻台账",
        "konoha-senki index row",
        "\n",
    ),
    (
        "docs/sequel-roadmap.md",
        # The timestamp in this heading changes every round by design, so the
        # locator anchors on the stable prefix instead of one reading.
        "最新实测（",
        "sequel roadmap pointer",
        "\n\n",
    ),
)


def _live_figures() -> tuple[int, int, float]:
    """The denominator, the build count and the percentage, straight from disk."""
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    denominator = sum(1 for entry in index["entries"] if entry.get("kind") == "artifact")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    build = sum(
        1
        for row in receipt["rows"]
        if row.get("kind") == "artifact" and row.get("status") == "build"
    )
    return denominator, build, round(100 * build / denominator, 1)


def _region(path: str, anchor: str, stop: str | None) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    self_contained = text[text.index(anchor) :]
    if stop is None:
        return self_contained
    return self_contained[: self_contained.index(stop)]


class GapDenominatorConsistencyTest(unittest.TestCase):
    def test_the_published_receipt_still_describes_the_published_index(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        index = json.loads(INDEX.read_text(encoding="utf-8"))
        digest = hashlib.sha256(INDEX.read_bytes()).hexdigest()
        self.assertEqual(
            receipt["index"]["sha256"],
            digest,
            "the receipt was produced from a different index than the published one",
        )
        self.assertEqual(
            receipt["index"]["reverse_commit"],
            index["source"]["commit"],
            "the receipt and the published index disagree about the reverse commit",
        )
        self.assertFalse(
            receipt["index"]["reverse_dirty"],
            "the receipt was built against a dirty reverse work tree",
        )

    def test_the_receipt_denominator_equals_the_index_denominator(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        index = json.loads(INDEX.read_text(encoding="utf-8"))
        index_families = sum(
            1 for entry in index["entries"] if entry.get("kind") == "artifact"
        )
        receipt_families = sum(
            1 for row in receipt["rows"] if row.get("kind") == "artifact"
        )
        self.assertEqual(receipt_families, index_families)
        by_kind = receipt["summary"]["by_kind"]["artifact"]
        self.assertEqual(sum(by_kind.values()), index_families)

    def test_the_current_documents_quote_the_live_denominator(self) -> None:
        denominator, build, percent = _live_figures()
        for path, anchor, label, stop in CURRENT_STATE_REGIONS:
            with self.subTest(document=label):
                region = _region(path, anchor, stop)
                self.assertIn(
                    str(denominator),
                    region,
                    f"{label} does not state the live denominator {denominator}",
                )
                self.assertIn(
                    f"{percent}%",
                    region,
                    f"{label} does not state the live build percentage {percent}%",
                )
                self.assertIn(
                    f"{build}/{denominator}",
                    region,
                    f"{label} does not state the live build count {build}/{denominator}",
                )

    def test_a_claim_against_a_foreign_denominator_must_be_marked_wrong(self) -> None:
        denominator, build, percent = _live_figures()
        for path, anchor, label, stop in CURRENT_STATE_REGIONS:
            with self.subTest(document=label):
                region = _region(path, anchor, stop)
                for line in region.splitlines():
                    claims = [
                        (int(a), int(b), float(c)) for a, b, c in CLAIM.findall(line)
                    ] + [
                        (int(b), int(c), float(a))
                        for a, b, c in MIRRORED_CLAIM.findall(line)
                    ]
                    for numerator, claimed_denominator, claimed_percent in claims:
                        if claimed_denominator == denominator:
                            self.assertEqual(
                                numerator,
                                build,
                                f"{label} claims {numerator}/{claimed_denominator} "
                                "but the live build count is "
                                f"{build}",
                            )
                            self.assertAlmostEqual(
                                claimed_percent,
                                percent,
                                places=1,
                                msg=f"{label} states {claimed_percent}% for "
                                f"{numerator}/{claimed_denominator}, the live "
                                f"percentage is {percent}%",
                            )
                            continue
                        self.assertTrue(
                            any(marker in line for marker in CORRECTION_MARKERS),
                            f"{label} pairs the live build count with a stale "
                            f"denominator ({numerator}/{claimed_denominator}) "
                            "without marking it as a correction",
                        )


if __name__ == "__main__":
    unittest.main()
