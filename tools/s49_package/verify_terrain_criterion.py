#!/usr/bin/env python3
"""Independent review of wave 10 / U4's **terrain criterion** in ``find_overlay_map``.

What is under review
--------------------
Wave 10's U4 stream added a *terrain criterion* to
``tools/s49_overlay_align/compare_overlay_families.py::find_overlay_map``:
when a terrain is supplied, a candidate window only wins the search if at
least one of its ``solid`` cells lands on blocked terrain.  U4 itself reported
this as an **overrun** (it was only authorised to change the anchor).

This script re-derives the answer **independently** of U4's own report.  It
answers three questions, each with a number:

Q1  Does the ``terrain=None`` path still return **exactly** what the
    pre-change implementation returned?  (``max(candidates)[1]`` is
    re-implemented here from scratch and compared on every dump.)

Q2  On the walk's dumps, **which** dumps does the terrain criterion change,
    and what does it change them to?

Q3  Does the criterion change the **numbers** the shared tool reports (the
    per-moment overlay table), and does it change the **judgment bench**
    (which calls ``find_overlay_map`` without a terrain)?

The shared tool is **read-only** here: the "without terrain" run is produced
by monkey-patching the module attribute *in this process only*.  No file
under ``tools/s49_overlay_align/`` is written.

Usage::

    python tools/s49_package/verify_terrain_criterion.py \
        --vram-dir build/s49-package/evidence/overlay/vram \
        --out build/s49-package/evidence/terrain-review.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys
import tempfile
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
OVERLAY_ALIGN = REPO / "tools" / "s49_overlay_align"
FIDELITY_REPORT = REPO / "tools" / "s49_fidelity_report"

for _extra in (str(REPO / "tools"), str(OVERLAY_ALIGN), str(FIDELITY_REPORT)):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

import compare_overlay_families as cof  # noqa: E402

TILE_MAX = 77


# --------------------------------------------------------------------------
# the pre-change implementation, re-derived here from the candidate scan
# --------------------------------------------------------------------------
def pre_change_find_overlay_map(vram: bytes, tile_max: int = TILE_MAX) -> int:
    """``find_overlay_map`` as it was **before** the terrain criterion.

    Re-implemented from the candidate scan so that the comparison is not a
    tautology against the shipped function's own ``terrain is None`` branch.
    """
    candidates = []
    for base in range(0, len(vram) - 2048 + 1, 0x800):
        entries = struct.unpack_from("<1024H", vram, base)
        non_zero = [entry & 0x3FF for entry in entries if (entry & 0x3FF)]
        if not non_zero:
            continue
        if any(cof.remake_family(tile)[0] == "blank" or tile > tile_max
               for tile in non_zero):
            continue
        candidates.append((len(non_zero), base))
    if not candidates:
        return -1
    return max(candidates)[1]


def candidate_windows(vram: bytes, tile_max: int = TILE_MAX) -> list[dict]:
    """Every window the signature scan accepts, with its non-zero entry count."""
    candidates = []
    for base in range(0, len(vram) - 2048 + 1, 0x800):
        entries = struct.unpack_from("<1024H", vram, base)
        non_zero = [entry & 0x3FF for entry in entries if (entry & 0x3FF)]
        if not non_zero:
            continue
        if any(cof.remake_family(tile)[0] == "blank" or tile > tile_max
               for tile in non_zero):
            continue
        candidates.append({"base": base, "base_hex": f"0x{base:05X}",
                           "non_zero": len(non_zero)})
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vram-dir", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    dumps = sorted(args.vram_dir.glob("*.vram-*.bin"))
    if not dumps:
        print(f"ERR no VRAM dumps in {args.vram_dir}")
        return 2

    terrain = cof.remake_terrain()

    # --- the judgment bench's own overlay reader (read-only import) -------
    # ``overlay`` uses relative imports, so it has to come in as a package.
    from s49_fidelity_report import overlay as bench_overlay  # noqa: E402

    rows = []
    none_mismatch = 0
    bench_mismatch = 0
    changed = []
    categories = {"no_candidate": 0, "false_window_0x00800": 0,
                  "real_overlay_0x09800": 0, "other": 0}
    for path in dumps:
        vram = path.read_bytes()
        pre = pre_change_find_overlay_map(vram, TILE_MAX)
        shipped_none = cof.find_overlay_map(vram, TILE_MAX)
        with_terrain = cof.find_overlay_map(vram, TILE_MAX, terrain=terrain)
        # ``remake_grid`` reports "no overlay" as ``None``; ``find_overlay_map``
        # reports it as ``-1``.  Normalise so the comparison is about the
        # behaviour and not about the two spellings of the same answer.
        bench_base = bench_overlay.remake_grid(vram)[1].get("overlay_map")
        bench_base = -1 if bench_base is None else bench_base
        if pre != shipped_none:
            none_mismatch += 1
        if bench_base != pre:
            bench_mismatch += 1
        if pre < 0:
            categories["no_candidate"] += 1
        elif pre == 0x00800:
            categories["false_window_0x00800"] += 1
        elif pre == 0x09800:
            categories["real_overlay_0x09800"] += 1
        else:
            categories["other"] += 1
        row = {
            "dump": path.name,
            "pre_change": pre,
            "pre_change_hex": f"0x{pre:05X}" if pre >= 0 else "-1",
            "shipped_no_terrain": shipped_none,
            "with_terrain": with_terrain,
            "with_terrain_hex": f"0x{with_terrain:05X}" if with_terrain >= 0 else "-1",
            "bench_overlay_map": bench_base,
            "changed": pre != with_terrain,
            "candidates": candidate_windows(vram, TILE_MAX),
        }
        rows.append(row)
        if row["changed"]:
            changed.append(row)

    # --- Q3a: the shared tool's own table, with and without the criterion --
    with_criterion = _run_tool(args.vram_dir, None)
    without_criterion = _run_tool(args.vram_dir, "pre_change")
    moment_delta = {}
    for name, row in (with_criterion.get("moments") or {}).items():
        other = (without_criterion.get("moments") or {}).get(name)
        if other is None:
            moment_delta[name] = {"with_criterion": _moment_row(row),
                                  "without_criterion": None,
                                  "changed": True}
            continue
        fields = ("both_lit", "original_only", "remake_only",
                  "family_mismatches", "residual", "exact", "frame",
                  "overlay_map")
        delta = {field: [row.get(field), other.get(field)]
                 for field in fields if row.get(field) != other.get(field)}
        moment_delta[name] = {
            "with_criterion": _moment_row(row),
            "without_criterion": _moment_row(other),
            "changed": bool(delta),
            "changed_fields": delta,
        }

    frames_changed = sum(
        1 for name, row in (with_criterion.get("frames") or {}).items()
        if (without_criterion.get("frames") or {}).get(name, {}).get("overlay_map")
        != row.get("overlay_map"))

    report = {
        "schema": "konoha.s49-package.terrain-review.v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "label": args.label,
        "vram_dir": str(args.vram_dir),
        "dump_count": len(dumps),
        "terrain_grid": {"rows": len(terrain), "cols": len(terrain[0])},
        "q1_none_path_equals_pre_change": {
            "dumps_checked": len(dumps),
            "mismatches": none_mismatch,
            "verdict": "identical" if none_mismatch == 0 else "DIFFERENT",
        },
        "q1_bench_reader_equals_pre_change": {
            "dumps_checked": len(dumps),
            "mismatches": bench_mismatch,
            "verdict": "identical" if bench_mismatch == 0 else "DIFFERENT",
            "note": "the judgment bench calls find_overlay_map(vram, 77) with "
                    "no terrain, so the criterion cannot reach it",
        },
        "q2_dumps_changed_by_the_criterion": {
            "changed": len(changed),
            "unchanged": len(dumps) - len(changed),
            "pre_change_categories": categories,
            "rows": changed,
        },
        "q3_shared_tool_table": {
            "frames_with_a_different_overlay_map": frames_changed,
            "moments": moment_delta,
        },
        "rows": rows,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1)
                            + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    print(f"dumps                 : {len(dumps)}")
    print(f"Q1 none-path != pre   : {none_mismatch}")
    print(f"Q1 bench != pre       : {bench_mismatch}")
    print(f"Q2 changed by criterion: {len(changed)} "
          f"(unchanged {len(dumps) - len(changed)})")
    for row in changed:
        print(f"     {row['dump']}: {row['pre_change_hex']} -> "
              f"{row['with_terrain_hex']}")
    print(f"Q3 frames with a different overlay map: {frames_changed}")
    for name, row in moment_delta.items():
        if row["changed"]:
            print(f"     moment {name}: {row['changed_fields']}")
    return 0


def _moment_row(row: dict) -> dict:
    return {key: row.get(key) for key in
            ("frame", "overlay_map", "original_lit", "remake_lit", "both_lit",
             "original_only", "remake_only", "family_mismatches", "residual",
             "exact")}


def _run_tool(vram_dir: pathlib.Path, mode: str | None) -> dict:
    """Run the shared tool's ``main()``; ``mode='pre_change'`` disables the
    criterion by patching the module attribute *in this process only*."""
    original = cof.find_overlay_map
    if mode == "pre_change":
        cof.find_overlay_map = (
            lambda vram, tile_max=TILE_MAX, terrain=None:
            pre_change_find_overlay_map(vram, tile_max))
    with tempfile.TemporaryDirectory() as scratch:
        out = pathlib.Path(scratch) / "tool.json"
        argv = sys.argv
        sys.argv = ["compare_overlay_families.py", "--vram-dir",
                    str(vram_dir), "--out", str(out)]
        try:
            cof.main()
        finally:
            sys.argv = argv
            cof.find_overlay_map = original
        return json.loads(out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
