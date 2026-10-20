#!/usr/bin/env python3
"""Offline pre-flight for the three Tier-2 exception promotions.

Runs the three new producers against the *current* canonical ledger (the
chain-time baseline: every one of the 16,913 existing claims is already in
place) and checks, without writing anything:

  1. the new claims do not overlap any existing primary claim;
  2. the new bytes are exactly 3,361 (1,668 + 1,053 + 640);
  3. the new claim counts are exactly 29 / 85 / 1;
  4. the projected ledger summary is
     unknown=82,728 classified=6,208,728 claims=17,028 segments=18,882.

Fails closed: any mismatch raises.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools import audit_rom_byte_coverage as auditor  # noqa: E402

LEDGER = ROOT / "sequel/rom-byte-coverage.json"
EXPECTED_BYTES = 3_361
EXPECTED_CLAIMS = {
    "rom-renderer-records-delta-v1": (29, 1_668),
    "rom-display-text-delta-v1": (85, 1_053),
    "rom-animation-descriptor-pool-v2": (1, 640),
}
EXPECTED_SUMMARY = {
    "unknown_bytes": 82_728,
    "classified_bytes": 6_208_728,
    "claim_count": 17_028,
    "segment_count": 18_882,
}


def main() -> int:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    claims = ledger["claims"]
    rom = (ROOT / "rom/base.gba").read_bytes()
    print(f"baseline claims: {len(claims)}")

    produced = []
    for name, helper in (
        ("rom-renderer-records-delta-v1", auditor._renderer_records_delta_claims),
        ("rom-display-text-delta-v1", auditor._display_text_delta_claims),
        ("rom-animation-descriptor-pool-v2", auditor._animation_descriptor_pool_v2_claims),
    ):
        rows = helper(ROOT, rom, claims)
        produced.extend(rows)
        count = len(rows)
        size = sum(row["range"][1] - row["range"][0] for row in rows)
        want_count, want_size = EXPECTED_CLAIMS[name]
        if count != want_count or size != want_size:
            raise SystemExit(
                f"FAIL {name}: claims {count} != {want_count} or bytes {size} != {want_size}"
            )
        print(f"  {name}: {count} claims / {size} bytes  OK")

    # 1. no overlap with the existing primary claims
    intervals = sorted(
        (claim["range"][0], claim["range"][1])
        for claim in claims
        if claim.get("role") == "primary"
    )
    for row in produced:
        start, end = row["range"]
        for other_start, other_end in intervals:
            if start < other_end and other_start < end:
                raise SystemExit(
                    f"FAIL overlap: {row['id']} [{start},{end}) vs existing "
                    f"[{other_start},{other_end})"
                )
    for index, left in enumerate(produced):
        for right in produced[index + 1 :]:
            if left["range"][0] < right["range"][1] and right["range"][0] < left["range"][1]:
                raise SystemExit(f"FAIL new-claim overlap: {left['id']} {right['id']}")
    print(f"  overlap check: 0 conflicts against {len(intervals)} primary claims  OK")

    # 2. total bytes
    total = sum(row["range"][1] - row["range"][0] for row in produced)
    if total != EXPECTED_BYTES:
        raise SystemExit(f"FAIL total bytes {total} != {EXPECTED_BYTES}")
    print(f"  total promoted bytes: {total}  OK")

    # 3/4. projected ledger summary
    combined = [*claims, *produced]
    segments = auditor.atomize_claims(len(rom), combined)
    totals: dict[str, int] = {}
    for segment in segments:
        size = segment["range"][1] - segment["range"][0]
        totals[segment["primary_class"]] = totals.get(segment["primary_class"], 0) + size
    accounted = sum(totals.values())
    classified = accounted - totals.get("unknown", 0)
    projected = {
        "unknown_bytes": totals.get("unknown", 0),
        "classified_bytes": classified,
        "claim_count": len(combined),
        "segment_count": len(segments),
    }
    print("  projected summary:", json.dumps(projected, ensure_ascii=False))
    for key, want in EXPECTED_SUMMARY.items():
        if projected[key] != want:
            raise SystemExit(f"FAIL projected {key} = {projected[key]} != {want}")
    print("  projected summary matches the expected four-tuple  OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
