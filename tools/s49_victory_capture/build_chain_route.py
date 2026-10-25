#!/usr/bin/env python3
"""Turn the wave-1 artifact chain into a replayable route.

The remake line's ``s49-original-victory-20261020-v1`` directory holds one
directory per recorded segment; each ``inputs.json`` names the savestate it
resumed from and the key sequence it pressed.  Chaining them gives the
wave-1 route that reached round 5 of battle 14.

This script rebuilds that chain in order (following the ``state`` links) and
writes it as a route JSON that ``tools/s49_victory_capture/shoot.py`` can
replay.

Usage::

    python tools/s49_victory_capture/tools_build_chain.py --out build/.../chain.json
"""

from __future__ import annotations

import argparse
import json
import pathlib

ARTIFACTS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-victory-20261020-v1")
ENTRY = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")


def load_segments(root: pathlib.Path) -> dict[str, dict]:
    segments: dict[str, dict] = {}
    for directory in sorted(root.iterdir()):
        inputs = directory / "inputs.json"
        if not directory.is_dir() or not inputs.exists():
            continue
        data = json.loads(inputs.read_text(encoding="utf-8"))
        data["dir"] = str(directory)
        segments[directory.name] = data
    return segments


def _key(path: str, root_name: str) -> tuple[str, str] | None:
    """Map a state path to a ``(segment dir, step file)`` key."""
    normalised = path.replace("\\", "/")
    marker = root_name + "/"
    if marker in normalised:
        normalised = normalised.split(marker, 1)[1]
    parts = normalised.split("/")
    if len(parts) < 2:
        return None
    return parts[-2], parts[-1]


def chain_order(segments: dict[str, dict], entry: pathlib.Path,
                root_name: str) -> list[dict]:
    """Order the segments by following the ``state`` links."""
    starts: dict[tuple[str, str], dict] = {}
    for segment in segments.values():
        key = _key(segment["state"], root_name)
        if key is None:
            continue
        starts[key] = segment
    entry_key = _key(str(entry), root_name)
    order: list[dict] = []
    seen: set[str] = set()
    current = entry_key
    while current is not None and current in starts:
        segment = starts[current]
        if segment["label"] in seen:
            break
        seen.add(segment["label"])
        order.append(segment)
        steps = json.loads(
            (pathlib.Path(segment["dir"]) / "steps.json").read_text(encoding="utf-8"))
        current = (pathlib.Path(segment["dir"]).name,
                   pathlib.Path(steps["steps"][-1]["state"]).name)
    return order


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", default=str(ARTIFACTS))
    parser.add_argument("--entry", default=str(ENTRY))
    parser.add_argument("--out", required=True)
    parser.add_argument("--from", dest="start_label", default=None,
                        help="start the chain at this segment label")
    args = parser.parse_args()

    segments = load_segments(pathlib.Path(args.artifacts))
    order = chain_order(segments, pathlib.Path(args.entry),
                        pathlib.Path(args.artifacts).name)
    if args.start_label:
        index = next((i for i, s in enumerate(order)
                      if s["label"] == args.start_label), None)
        if index is None:
            raise SystemExit(f"segment {args.start_label!r} not in the chain")
        order = order[index:]

    route = {
        "schema": "konoha.s49-victory-route.v1",
        "note": "wave-1 artifact chain (r01..u13), replayed on this machine",
        "start_state": str(args.entry),
        "segments": [
            {
                "label": segment["label"],
                "settle": segment["settle_frames"],
                "hold": segment["hold_frames"],
                "zero": segment["zero_input_frames"],
                "keys": segment["keys"],
            }
            for segment in order
        ],
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(route, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print(json.dumps({"segments": len(order),
                      "labels": [s["label"] for s in order]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
