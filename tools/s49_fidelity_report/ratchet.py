"""The ratchet gate: the residual is only allowed to get smaller.

The bench is the acceptance instrument of the whole project, so it has to be
able to say "this change made the residual bigger".  The gate compares two
report documents and fails when any residual metric got worse.

The metrics are deliberately few and coarse, so that a change in the
*attribution* (how a residual is explained) can never be mistaken for a
change in the residual itself.

Three verdicts (wave 15 / W2)
------------------------------
``pass``          the two readings are comparable (same ROM on both sides)
                  and nothing got worse.
``fail``          something got worse.  **Always** a failure, even when the
                  ROM changed: a residual that grew is exactly the
                  regression this gate exists to catch (wave 14 lost a
                  +9,359 px regression this way).
``incomparable``  the ROM changed and nothing got worse.  The two numbers
                  are on the same scale but they are not the same
                  measurement, so the verdict is "not comparable" -- and
                  **not** a pass.  A silent pass here is the instrument
                  defect wave 14 was hit by.

``ok`` keeps its old meaning ("nothing got worse"); ``status`` is the
full verdict.
"""

from __future__ import annotations

RATCHET_METRICS = (
    # (report path, label, "higher_is_worse" or "lower_is_worse")
    (("summary", "field_residual", "sum"), "战场区残差总和", "higher"),
    (("summary", "field_residual", "max"), "战场区残差峰值", "higher"),
    (("summary", "field_residual", "median"), "战场区残差中位", "higher"),
    (("summary", "field_residual", "zero_frames"), "战场区全 0 帧数", "lower"),
    (("summary", "full_residual", "sum"), "整屏残差总和", "higher"),
    (("summary", "overlay_residual", "sum"), "覆盖层族名残差总和", "higher"),
)


def _dig(document: dict, path: tuple[str, ...]):
    node = document
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _rom_identity(document: dict) -> dict:
    """Which ROM each side of the comparison was measured on."""
    captures = document.get("captures") or {}
    return {
        side: (captures.get(side) or {}).get("rom_sha256")
        for side in ("original", "remake")
    }


def compare(baseline: dict, candidate: dict) -> dict:
    """Compare the residual of two reports.

    Returns a dictionary with ``ok`` (True when the candidate is not worse),
    ``status`` (``pass`` / ``fail`` / ``incomparable``), one entry per metric
    and the per frame deltas.

    The ratchet compares two *readings*.  When the ROM changed between them
    the residual delta belongs to the ROM change, not to the bench, so the
    ROM identity of both sides is reported next to the verdict.

    The ROM change does **not** switch the metric comparison off: the
    residual is counted in pixels on both sides, so "it got bigger" stays a
    meaningful statement and is reported as ``fail``.  Only when nothing got
    worse does the ROM change turn the verdict into ``incomparable`` --
    which is explicitly *not* a pass.
    """
    checks = []
    for path, label, direction in RATCHET_METRICS:
        before = _dig(baseline, path)
        after = _dig(candidate, path)
        if before is None or after is None:
            checks.append({
                "label": label, "path": list(path),
                "baseline": before, "candidate": after,
                "direction": direction, "ok": True,
                "note": "metric missing, not compared",
            })
            continue
        if direction == "higher":
            ok = after <= before
        else:
            ok = after >= before
        checks.append({
            "label": label, "path": list(path),
            "baseline": before, "candidate": after,
            "direction": direction, "ok": ok,
            "delta": after - before,
        })

    baseline_frames = {row["original"]: row for row in baseline.get("frames", [])}
    frame_deltas = []
    for row in candidate.get("frames", []):
        name = row["original"]
        old = baseline_frames.get(name)
        if old is None:
            continue
        before = old.get("field_residual_px")
        after = row.get("field_residual_px")
        if before is None or after is None:
            continue
        frame_deltas.append({
            "original": name,
            "baseline": before,
            "candidate": after,
            "delta": after - before,
        })
    worsened = [item for item in frame_deltas if item["delta"] > 0]
    improved = [item for item in frame_deltas if item["delta"] < 0]

    baseline_rom = _rom_identity(baseline)
    candidate_rom = _rom_identity(candidate)
    rom_changed = baseline_rom != candidate_rom

    worsened_checks = [check for check in checks if not check.get("ok")]
    ok = not worsened_checks
    if not ok:
        status = "fail"
        note = ("the residual got bigger"
                + (" (the ROM changed as well, so the delta belongs to the "
                   "ROM change -- but a bigger residual is still a bigger "
                   "residual and has to be looked at)"
                   if rom_changed else ""))
    elif rom_changed:
        status = "incomparable"
        note = ("the baseline ROM differs from this run's ROM => the two "
                "residual numbers are not the same measurement => NOT "
                "comparable, and therefore NOT a pass")
    else:
        status = "pass"
        note = "both readings were taken on the same ROM and nothing got worse"

    return {
        "ok": ok,
        "status": status,
        "comparable": not rom_changed,
        "note": note,
        "checks": checks,
        "rom": {
            "baseline": baseline_rom,
            "candidate": candidate_rom,
            "changed": rom_changed,
            "note": ("the ROM changed between the two readings: the residual "
                     "delta belongs to the ROM change, not to the bench"
                     if rom_changed else
                     "both readings were taken on the same ROM"),
        },
        "frames": {
            "compared": len(frame_deltas),
            "worsened": len(worsened),
            "improved": len(improved),
            "deltas": frame_deltas,
        },
    }
