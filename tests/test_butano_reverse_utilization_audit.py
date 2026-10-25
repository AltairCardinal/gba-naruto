#!/usr/bin/env python3
"""Tests for the Butano remake / reverse-result utilization audit.

The audit answers "how much of the finished reverse corpus should the Butano
remake be using, and how much is it not using".  The number is only worth
anything if it cannot be produced from a broken input, so the failure modes
matter more than the happy path:

* a missing receipt must fail closed with a named reason, not report zeroes;
* the three receipts must agree on the family set -- if they disagree, the
  join would silently drop families and understate the gap;
* the notes buckets must add up to the notes total;
* the ratios must be derived, never hard coded.

The last test checks the real Butano work tree when it is present.  It is
skipped otherwise so the suite still runs on a machine that only has the
master line checked out.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.butano_reverse_utilization_audit import (
    GAP_RECEIPT,
    NOTES_INDEX,
    AuditError,
    audit,
)

BUTANO_ROOT = Path("D:/Shell/Github/gba-naruto-butano")


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fixture(root: Path, families, notes_buckets) -> None:
    """Build a minimal but internally consistent set of four receipts."""
    _write(
        root / GAP_RECEIPT,
        {
            "schema": "konoha.butano-reverse-gap.v1",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "index": {"reverse_commit": "deadbeef", "reverse_dirty": False},
            "rows": [
                {
                    "id": fid,
                    "kind": "artifact",
                    "category": "rom",
                    "status": status,
                }
                for fid, status, _tier, _accepted, _consumed in families
            ],
        },
    )
    _write(
        root / "artifacts/butano-usable-backlog-v1/backlog.json",
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "rows": [
                {
                    "id": fid,
                    "tier": tier,
                    "accepted": accepted,
                    "has_payload": True,
                    "consumed": consumed,
                }
                for fid, _status, tier, accepted, consumed in families
            ],
        },
    )
    _write(
        root / "artifacts/butano-wiring-coverage-v1/wiring.json",
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "source_rows": [
                {
                    "id": fid,
                    "state": "imported-and-gated" if status == "build" else "no-material",
                }
                for fid, status, _tier, _accepted, _consumed in families
            ],
        },
    )
    _write(
        root / NOTES_INDEX,
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "summary": {
                "total": sum(notes_buckets.values()),
                "by_bucket": notes_buckets,
            },
            "notes": [],
        },
    )


class UtilizationAuditTests(unittest.TestCase):
    def test_counts_and_ratios_are_derived_from_the_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(
                root,
                [
                    ("fam-a", "build", "asset-direct", True, True),
                    ("fam-b", "doc", "analysis-only", True, False),
                    ("fam-c", "doc", "asset-direct", True, False),
                ],
                {"implemented_in_code": 1, "needs_guard": 2, "not_applicable": 1},
            )
            report = audit(root)

        af = report["artifact_families"]
        self.assertEqual(3, af["total"])
        self.assertEqual(1, af["in_build_chain"])
        self.assertEqual(2, af["not_in_build_chain"])
        # all three fixture families are accepted (closed)
        self.assertEqual(3, af["accepted_closed"])
        # fam-c is accepted, carries payload, is not consumed and is not even
        # read as evidence -> it is the one genuinely unused closed family.
        self.assertEqual(
            ["fam-c"], report["ratios"]["R1b_importable_closed_never_touched"]["family_ids"]
        )
        self.assertEqual(
            33.3, report["ratios"]["R1b_importable_closed_never_touched"]["percent"]
        )

        nt = report["notes"]
        self.assertEqual(4, nt["total"])
        self.assertEqual(2, nt["needs_guard"])
        self.assertEqual(3, nt["decided_total"])

    def test_a_missing_receipt_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(
                root,
                [("fam-a", "build", "asset-direct", True, True)],
                {"implemented_in_code": 1},
            )
            (root / GAP_RECEIPT).unlink()
            with self.assertRaises(AuditError) as ctx:
                audit(root)
        self.assertIn("receipt not found", str(ctx.exception))

    def test_receipts_that_disagree_on_the_family_set_fail_closed(self):
        """A silent drop would understate the gap, so it must be an error."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(
                root,
                [
                    ("fam-a", "build", "asset-direct", True, True),
                    ("fam-b", "doc", "analysis-only", True, False),
                ],
                {"implemented_in_code": 1},
            )
            wiring = json.loads(
                (root / "artifacts/butano-wiring-coverage-v1/wiring.json").read_text(
                    encoding="utf-8"
                )
            )
            wiring["source_rows"] = wiring["source_rows"][:1]
            _write(root / "artifacts/butano-wiring-coverage-v1/wiring.json", wiring)
            with self.assertRaises(AuditError) as ctx:
                audit(root)
        self.assertIn("missing from a sibling receipt", str(ctx.exception))

    def test_notes_buckets_that_do_not_add_up_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(
                root,
                [("fam-a", "build", "asset-direct", True, True)],
                {"implemented_in_code": 1, "needs_guard": 1},
            )
            notes = json.loads((root / NOTES_INDEX).read_text(encoding="utf-8"))
            notes["summary"]["total"] = 99
            _write(root / NOTES_INDEX, notes)
            with self.assertRaises(AuditError) as ctx:
                audit(root)
        self.assertIn("do not add up", str(ctx.exception))

    def test_real_butano_tree_reproduces_the_published_reading(self):
        """The live numbers must match what the notes claim.

        Anchor: reverse commit 821d0937, receipts generated 2026-10-23T09:12Z.
        """
        if not (BUTANO_ROOT / GAP_RECEIPT).is_file():
            self.skipTest("Butano work tree not present on this machine")
        report = audit(BUTANO_ROOT)
        af = report["artifact_families"]
        nt = report["notes"]
        self.assertEqual(264, af["total"])
        self.assertEqual(164, af["in_build_chain"])
        self.assertEqual(100, af["not_in_build_chain"])
        self.assertEqual(201, af["accepted_closed"])
        self.assertEqual(436, nt["total"])
        self.assertEqual(332, nt["needs_guard"])
        self.assertEqual(0, len(report["ratios"]["R1b_importable_closed_never_touched"]["family_ids"]))
        self.assertEqual(
            76.1, report["ratios"]["R2_finished_conclusions_not_gated"]["percent"]
        )


if __name__ == "__main__":
    unittest.main()
