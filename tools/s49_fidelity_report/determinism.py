"""Is the judgment bench's reading deterministic?

The bench is the project's yardstick: "the residual may only get smaller" is
judged by comparing two readings.  That rule is only meaningful when the bench
reads the **same** number twice on the same input.  A bench that jitters would
make the ratchet fire on noise, and -- worse -- could hide a real regression
behind a lucky low reading.

This module compares several readings of the same bench and reports, in
machine readable form, whether they agree.  It compares the *measurement*, not
the provenance:

* the residual summaries (field / full / overlay),
* the attribution and the three bucket counts,
* the per frame pairing (which remake frame each original frame was paired
  to, and with how many differing pixels),
* the sha256 of every captured PNG -- this is what makes the comparison a
  statement about the **capture** as well, not only about the arithmetic.

The ROM identity is compared too, but it is reported separately: a ROM that
changed between two readings makes the comparison **void**, not "failed".
That distinction is the whole point -- wave 10 measured a +/-9,520 px "jitter"
that was in fact the remake ROM being rebuilt between the two runs.
"""

from __future__ import annotations

import hashlib

# The summary keys that have to agree for two readings to be the same reading.
COMPARED_SUMMARIES = (
    "field_residual",
    "full_residual",
    "overlay_residual",
    "attribution",
    "pairing_diff_subclasses",
    "confidence",
    "identical_frames",
)


def _captures_digest(report: dict) -> str:
    """One digest over every captured frame's sha256, both sides."""
    digest = hashlib.sha256()
    for side in ("original", "remake"):
        frames = ((report.get("captures") or {}).get(side) or {}).get("frames") or []
        digest.update(side.encode("utf-8"))
        for entry in frames:
            digest.update(f"{entry.get('name')}:{entry.get('sha256')}\n".encode("utf-8"))
    return digest.hexdigest()


def _rom_identity(report: dict) -> dict:
    captures = report.get("captures") or {}
    return {
        side: (captures.get(side) or {}).get("rom_sha256")
        for side in ("original", "remake")
    }


def _pairing(report: dict) -> dict:
    return {
        row.get("original"): (row.get("best_match"), row.get("field_residual_px"))
        for row in report.get("frames", [])
    }


def describe(report: dict, iteration: int) -> dict:
    """One line per reading: the numbers a reader compares by hand."""
    summary = report.get("summary") or {}
    field = summary.get("field_residual") or {}
    return {
        "iteration": iteration,
        "rom_sha256": _rom_identity(report),
        "field_residual_sum": field.get("sum"),
        "field_residual_median": field.get("median"),
        "field_residual_max": field.get("max"),
        "zero_frames": field.get("zero_frames"),
        "attribution": summary.get("attribution"),
        "pairing_diff_subclasses": summary.get("pairing_diff_subclasses"),
        "overlay_residual_sum": (summary.get("overlay_residual") or {}).get("sum"),
        "capture_digest": _captures_digest(report),
    }


def compare(reports: list[dict]) -> dict:
    """Compare several readings of the same bench.

    ``reports`` is a list of report documents (at least one).  The result
    carries one description per reading, the list of differences (empty when
    the readings agree) and the verdict.
    """
    readings = [describe(report, index)
                for index, report in enumerate(reports, start=1)]
    if len(reports) < 2:
        return {
            "runs": readings,
            "identical": True,
            "differences": [],
            "rom_changed": False,
            "note": "only one reading was taken; nothing to compare",
        }

    reference = reports[0]
    reference_summary = reference.get("summary") or {}
    reference_pairing = _pairing(reference)
    differences: list[str] = []

    for index, report in enumerate(reports[1:], start=2):
        summary = report.get("summary") or {}
        for key in COMPARED_SUMMARIES:
            if summary.get(key) != reference_summary.get(key):
                differences.append(
                    f"reading {index}: summary.{key}: "
                    f"{reference_summary.get(key)!r} -> {summary.get(key)!r}")
        pairing = _pairing(report)
        for name in sorted(set(reference_pairing) | set(pairing)):
            if reference_pairing.get(name) != pairing.get(name):
                differences.append(
                    f"reading {index}: frame {name}: "
                    f"{reference_pairing.get(name)} -> {pairing.get(name)}")
        digest = _captures_digest(report)
        if digest != _captures_digest(reference):
            differences.append(
                f"reading {index}: the captured frames differ "
                "(the capture itself is not reproducible)")

    rom_changed = any(
        reading["rom_sha256"] != readings[0]["rom_sha256"]
        for reading in readings[1:]
    )
    identical = not differences
    if rom_changed:
        note = ("the ROM changed between the readings: the comparison is VOID "
                "(the residual delta belongs to the ROM change, not to the "
                "bench)")
    elif identical:
        note = ("the bench read the same numbers on the same ROM: the "
                "residual is a reproducible reading, so a change in it is a "
                "change in the product")
    else:
        note = ("the bench read different numbers on the same ROM: the "
                "reading is NOT deterministic, the ratchet cannot be trusted "
                "until this is fixed")

    return {
        "runs": readings,
        "identical": identical,
        "rom_changed": rom_changed,
        "differences": differences,
        "note": note,
    }
