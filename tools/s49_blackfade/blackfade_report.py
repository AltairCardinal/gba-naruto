#!/usr/bin/env python3
"""Build the black-field truth table from a frame capture.

Reads the PNG frames written by ``blackfade_capture.py`` (or any directory of
``frame-*.png``) and segments every *black field event* into the three phases
the original's entry performance actually uses:

* **fade-out** -- the picture gets darker (the palette is faded step by step),
* **black hold** -- the frame is fully black (one colour: 0,0,0),
* **fade-in** -- the picture comes back.

That split is the answer to "is the black field one frame or a gradient?": a
gradient fade shows a monotone run of intermediate mean values, a single black
frame does not.

Every event is reported with the frame index, the sha256 of the first / last
black frame, the duration in frames and the frames on both sides (the
"前后帧关系").

Usage::

    python tools/s49_blackfade/blackfade_report.py \
        --frames build/s49-blackfade/original-entry-v2/frames \
        --out build/s49-blackfade/original-entry-v2/blackfade.json \
        --markdown build/s49-blackfade/original-entry-v2/blackfade.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

from PIL import Image

WIDTH = 240
HEIGHT = 160
NORMAL_MEAN = 40.0      # a frame whose red mean is below this is "dark"


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile(path: pathlib.Path) -> dict:
    image = Image.open(path).convert("RGB")
    histogram: dict[tuple[int, int, int], int] = {}
    total = WIDTH * HEIGHT
    sum_r = sum_g = sum_b = 0
    black = 0
    dark = 0
    for r, g, b in image.get_flattened_data():
        sum_r += r
        sum_g += g
        sum_b += b
        key = (r, g, b)
        histogram[key] = histogram.get(key, 0) + 1
        peak = r if r > g else g
        if b > peak:
            peak = b
        if peak <= 8:
            black += 1
        elif peak <= 32:
            dark += 1
    top = max(histogram.items(), key=lambda item: item[1])
    return {
        "mean": [round(sum_r / total, 3), round(sum_g / total, 3),
                 round(sum_b / total, 3)],
        "unique_colors": len(histogram),
        "black_pct": round(100.0 * black / total, 3),
        "dark_pct": round(100.0 * (black + dark) / total, 3),
        "top_color": list(top[0]),
        "top_color_pct": round(100.0 * top[1] / total, 3),
    }


def is_pure_black(row: dict) -> bool:
    return row["unique_colors"] == 1 and row["top_color"] == [0, 0, 0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frames", required=True,
                        help="directory with frame-*.png")
    parser.add_argument("--out", required=True)
    parser.add_argument("--normal-mean", type=float, default=NORMAL_MEAN,
                        help="red mean below this counts as a dark frame")
    parser.add_argument("--markdown", default="",
                        help="also write the table as markdown here")
    args = parser.parse_args(argv)

    directory = pathlib.Path(args.frames)
    paths = sorted(directory.glob("frame-*.png"))
    if not paths:
        raise SystemExit(f"no frames in {directory}")

    rows = []
    for path in paths:
        row = {"frame": path.name, "sha256": sha256_file(path)}
        row.update(profile(path))
        row["pure_black"] = is_pure_black(row)
        rows.append(row)

    # a black field event = a maximal run of frames darker than normal
    events: list[list[int]] = []
    current: list[int] = []
    for index, row in enumerate(rows):
        if row["mean"][0] < args.normal_mean:
            current.append(index)
            continue
        if current:
            events.append(current)
            current = []
    if current:
        events.append(current)

    event_rows = []
    for number, indices in enumerate(events, start=1):
        first = indices[0]
        last = indices[-1]
        blacks = [index for index in indices if rows[index]["pure_black"]]
        black_first = blacks[0] if blacks else None
        black_last = blacks[-1] if blacks else None
        fade_out = [index for index in indices
                    if black_first is None or index < black_first]
        fade_in = [index for index in indices
                   if black_last is None or index > black_last]
        previous = rows[first - 1] if first > 0 else None
        following = rows[last + 1] if last + 1 < len(rows) else None
        means = [rows[index]["mean"][0] for index in indices]
        distinct = sorted({rows[index]["sha256"] for index in indices})
        event_rows.append({
            "event": number,
            "first_frame": rows[first]["frame"],
            "last_frame": rows[last]["frame"],
            "total_frames": len(indices),
            "distinct_frames": len(distinct),
            "fade_out_frames": len(fade_out),
            "fade_out_range": [rows[fade_out[0]]["frame"],
                               rows[fade_out[-1]]["frame"]] if fade_out else None,
            "black_hold_frames": len(blacks),
            "black_hold_range": [rows[black_first]["frame"],
                                 rows[black_last]["frame"]] if blacks else None,
            "first_black_sha256": rows[black_first]["sha256"] if blacks else None,
            "last_black_sha256": rows[black_last]["sha256"] if blacks else None,
            "fade_in_frames": len(fade_in),
            "fade_in_range": [rows[fade_in[0]]["frame"],
                              rows[fade_in[-1]]["frame"]] if fade_in else None,
            "previous_frame": previous["frame"] if previous else None,
            "previous_frame_sha256": previous["sha256"] if previous else None,
            "previous_frame_mean": previous["mean"] if previous else None,
            "next_frame": following["frame"] if following else None,
            "next_frame_sha256": following["sha256"] if following else None,
            "next_frame_mean": following["mean"] if following else None,
            "mean_min": min(means),
            "mean_max": max(means),
            "mean_sequence": means,
            "frames": [{"frame": rows[index]["frame"],
                        "sha256": rows[index]["sha256"],
                        "mean": rows[index]["mean"],
                        "unique_colors": rows[index]["unique_colors"],
                        "black_pct": rows[index]["black_pct"],
                        "pure_black": rows[index]["pure_black"]}
                       for index in indices],
        })

    document = {
        "schema": "konoha.s49-blackfade-report.v2",
        "frames_dir": str(directory),
        "frame_count": len(rows),
        "normal_mean_threshold": args.normal_mean,
        "event_count": len(event_rows),
        "events": event_rows,
        "frames": rows,
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")

    print(f"{len(rows)} frames, {len(event_rows)} black field event(s)")
    for event in event_rows:
        print(f"  event {event['event']}: {event['first_frame']} .. "
              f"{event['last_frame']}  total {event['total_frames']} frame(s) "
              f"({event['distinct_frames']} distinct)")
        print(f"    fade-out  {event['fade_out_range']} ({event['fade_out_frames']}f)")
        print(f"    black     {event['black_hold_range']} "
              f"({event['black_hold_frames']}f) "
              f"sha256 {event['first_black_sha256'][:16] if event['first_black_sha256'] else '-'}")
        print(f"    fade-in   {event['fade_in_range']} ({event['fade_in_frames']}f)")
        print(f"    prev {event['previous_frame']} mean={event['previous_frame_mean']}"
              f"   next {event['next_frame']} mean={event['next_frame_mean']}")
    print("->", out)

    if args.markdown:
        lines = [
            "| # | black field | total frames | fade-out | black hold | fade-in |"
            " first black sha256 | prev frame | next frame |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for event in event_rows:
            lines.append(
                f"| {event['event']} | {event['first_frame']} .. {event['last_frame']} | "
                f"{event['total_frames']} | {event['fade_out_frames']} | "
                f"{event['black_hold_frames']} | {event['fade_in_frames']} | "
                f"`{(event['first_black_sha256'] or '-')[:16]}...` | "
                f"{event['previous_frame']} | {event['next_frame']} |")
        pathlib.Path(args.markdown).write_text("\n".join(lines) + "\n",
                                                encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
