"""Build the X2 pairing receipt: the pairing table and the reachability bound.

    python tools/s49_pairing/pairing_report.py \
        --walk build/s49-pairing/walk5 \
        --bench-report build/s49-pairing/x2/dense5/report.json \
        --out build/s49-pairing/x2/pairing5

The receipt has three parts:

1. the **pairing table** -- one row per original canonical frame: the remake
   frame that is at the *same game moment* (by content anchor, not by
   pixels), the closest remake frame, and the moment description of both.
2. the **reachability bound** -- how many of the original's moments the
   remake's recorded game-time line never shows.  Those frames cannot be
   fixed by any walk: they are product gaps.
3. the **pixel floor** -- the smallest residual sum any walk built on these
   two recordings can reach.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from s49_pairing import anchors as anchors_module  # noqa: E402
from s49_pairing import pair as pair_module  # noqa: E402


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def beat_stride(directory: pathlib.Path) -> int:
    """How many captures one beat contributes (measured from the file names)."""
    files = sorted(directory.glob("step-*.png"))
    indices = [index for index, path in enumerate(files)
               if path.name.endswith("-beat.png")]
    if len(indices) < 2:
        raise SystemExit(f"ERR {directory} has no beat frames")
    return indices[1] - indices[0]


def canonical_names(directory: pathlib.Path, beats: int) -> list[str]:
    """The canonical frames of one side, in beat order, in the dense names."""
    files = sorted(directory.glob("step-*.png"))
    bases = [path.name for path in files if path.name.endswith("-base.png")]
    beat_frames = [path.name for path in files if path.name.endswith("-beat.png")]
    names = bases + beat_frames
    return names[:beats + 1]


def bench_name(index: int) -> str:
    """The pinned baseline's name of the canonical frame ``index``."""
    return ("step-00-base.png" if index == 0 else f"step-{index:02d}-A.png")


def load_anchors(side: str, directory: pathlib.Path, cache: pathlib.Path) -> dict:
    """The content anchors of one side, cached on disk."""
    if cache.exists():
        document = json.loads(cache.read_text(encoding="utf-8"))
        if document.get("status") == "ok" and document.get("frames"):
            return document
    document = anchors_module.side_anchors(side, directory)
    write_text(cache, json.dumps(document, ensure_ascii=False, indent=1) + "\n")
    return document


def render_markdown(document: dict) -> str:
    lines = []
    lines.append("# X2 pairing table\n")
    lines.append(f"* original frames: {document['summary']['original_frames']}")
    lines.append(f"* remake frames: {document['summary']['remake_frames']}")
    lines.append(f"* exact moment: {document['summary']['exact_moment']}"
                 f"/{document['summary']['original_frames']}")
    lines.append(f"* pairing diff lower bound: "
                 f"{document['reachability']['pairing_diff_lower_bound']}\n")
    lines.append("| original | remake (same moment) | closest | residual@match | "
                 "residual@closest | moment |")
    lines.append("|---|---|---|---:|---:|---|")
    for row in document["table"]:
        lines.append(
            f"| {row['original']} | {row['anchor_match'] or '-'} | "
            f"{row['closest']} | {row['residual_at_match']} | "
            f"{row['residual_at_closest']} | {row['original_moment']} |")
    lines.append("")
    lines.append("## the moments the remake never shows\n")
    for row in document["reachability"]["rows"]:
        if not row["counterpart"]:
            lines.append(f"* `{row['original']}` key={row['moment_key']} "
                         f"closest={row['closest_remake']} "
                         f"distance={row['closest_distance']}")
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--walk", type=pathlib.Path,
                    default=REPO / "build" / "s49-pairing" / "walk")
    ap.add_argument("--out", type=pathlib.Path,
                    default=REPO / "build" / "s49-pairing" / "x2" / "pairing")
    ap.add_argument("--bench-report", type=pathlib.Path, default=None)
    ap.add_argument("--beats", type=int, default=24)
    ap.add_argument("--no-floor", action="store_true",
                    help="skip the (slow) pixel floor computation")
    args = ap.parse_args(argv)

    original_dir = args.walk / "dense-original"
    remake_dir = args.walk / "dense-remake"
    for required in (original_dir, remake_dir):
        if not required.is_dir():
            raise SystemExit(f"ERR missing the dense walk: {required}")

    original_anchors = load_anchors("original", original_dir,
                                     args.out / "anchors-original.json")
    remake_anchors = load_anchors("remake", remake_dir,
                                   args.out / "anchors-remake.json")
    original_layer = anchors_module.camera_layer(original_anchors)
    remake_layer = anchors_module.camera_layer(remake_anchors)

    table = pair_module.build_table(original_anchors, remake_anchors,
                                     original_layer, remake_layer)
    canonical = canonical_names(original_dir, args.beats)
    rows_by_dense = {row["original"]: row for row in table}
    table = []
    for index, dense_name in enumerate(canonical):
        row = rows_by_dense.get(dense_name)
        if row is None:
            continue
        row["dense_original"] = dense_name
        row["original"] = bench_name(index)
        table.append(row)

    bench_rows = {}
    if args.bench_report and args.bench_report.exists():
        bench = json.loads(args.bench_report.read_text(encoding="utf-8"))
        bench_rows = {row["original"]: row for row in bench.get("frames", [])}

    for row in table:
        candidates = row.get("anchor_candidates") or []
        best = None
        for candidate in candidates:
            residual = pair_module.residual_of(
                original_dir, remake_dir, row["dense_original"], candidate)
            if best is None or residual < best[0]:
                best = (residual, candidate)
        if best is not None:
            row["anchor_match"] = best[1]
            row["residual_at_match"] = best[0]
        else:
            row["residual_at_match"] = None
        row["residual_at_closest"] = pair_module.residual_of(
            original_dir, remake_dir, row["dense_original"], row["closest"])
        bench_row = bench_rows.get(row["original"])
        row["bench_best_match"] = bench_row["best_match"] if bench_row else None
        row["bench_residual_px"] = (bench_row["field_residual_px"]
                                    if bench_row else None)
        row["bench_class"] = (bench_row["verdict"]["class"]
                              if bench_row else None)

    bound = pair_module.reachability(original_anchors, remake_anchors,
                                      original_layer, remake_layer)
    dense_index = {name: index for index, name in enumerate(canonical)}
    bound["rows"] = []
    for row in pair_module.reachability(
            original_anchors, remake_anchors, original_layer,
            remake_layer)["rows"]:
        index = dense_index.get(row["original"])
        if index is None:
            continue
        row["dense_original"] = row["original"]
        row["original"] = bench_name(index)
        bound["rows"].append(row)
    missing = [row for row in bound["rows"] if not row["counterpart"]]
    bound["frames_with_counterpart"] = len(bound["rows"]) - len(missing)
    bound["frames_without_counterpart"] = len(missing)
    bound["pairing_diff_lower_bound"] = len(missing)

    for row in table:
        row["anchor_candidates"] = (row.get("anchor_candidates") or [])[:8]
        row["anchor_match_candidates"] = row.get("anchor_match_candidates", 0)

    floor = None
    if not args.no_floor:
        floor = pair_module.beat_floor(
            original_dir, remake_dir, args.beats,
            beat_stride(original_dir))

    exact = sum(1 for row in table if row["exact_moment"])
    document = {
        "schema": "s49-pairing-report/1",
        "walk": {
            "original": str(original_dir),
            "remake": str(remake_dir),
            "original_camera_layer": original_layer,
            "remake_camera_layer": remake_layer,
        },
        "summary": {
            "original_frames": len(table),
            "remake_frames": len(remake_anchors["frames"]),
            "exact_moment": exact,
            "exact_moment_share": round(exact / len(table), 4) if table else 0,
            "residual_at_match_sum": sum(
                row["residual_at_match"] for row in table
                if row["residual_at_match"] is not None),
            "residual_at_closest_sum": sum(row["residual_at_closest"]
                                           for row in table),
            "bench_residual_sum": sum(row["bench_residual_px"] for row in table
                                      if row["bench_residual_px"] is not None),
            "pairing_diff_lower_bound":
                bound["pairing_diff_lower_bound"],
        },
        "table": table,
        "reachability": bound,
        "floor": floor,
    }
    write_text(args.out / "pairing.json",
               json.dumps(document, ensure_ascii=False, indent=1) + "\n")
    write_text(args.out / "pairing.md", render_markdown(document))

    print(json.dumps(document["summary"], ensure_ascii=False, indent=1))
    if floor:
        print(f"pixel floor sum: {floor['floor_sum']} "
              f"(canonical {floor['canonical_sum']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
