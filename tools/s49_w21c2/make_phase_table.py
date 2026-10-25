#!/usr/bin/env python3
"""W21-C2: build the "one A press at a time" phase comparison table.

What it does
------------
For each captured step of the two walks it records:

* **remake side** -- the battle telemetry the remake publishes in EWRAM
  (``battle_runtime_scene_telemetry``): phase / round / cursor / selected
  unit / scene frame, plus the sha256 of the rendered frame.
* **original side** -- the sha256 of the rendered frame plus a *pixel level*
  phase proxy (the original game has no telemetry at all).

The two walks have different starting points, so the table also carries the
anchor table: the frame pairs that are byte identical across the two sides
are the only moments where "the same thing is on screen" is provable, and
they are what the divergence is measured against.

Usage::

    python tools/s49_w21c2/make_phase_table.py \\
        --remake-dir build/s49-package-w20/work/s49-report/capture-remake \\
        --remake-rom build/s49-package-w20/work/pinned-rom/measured.gba \\
        --original-dir build/s49-package-w20/work/s49-report/capture-original \\
        --exe build/mgba-probe-w21c2/mgba-probe.exe \\
        --out build/w21-c2/press-phase-table.json
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_battle_balance"))

import w1_probe as probe_module  # noqa: E402
import x1_telemetry as telemetry_module  # noqa: E402

STEP_RE = re.compile(r"^step-(\d+)-([A-Za-z]+)$")


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def step_entries(directory: pathlib.Path) -> list[tuple[int, str, pathlib.Path]]:
    """``[(index, key, png_path), ...]`` ordered by the step index."""
    entries = []
    for png in sorted(directory.glob("step-*.png")):
        match = STEP_RE.match(png.stem)
        if not match:
            continue
        entries.append((int(match.group(1)), match.group(2), png))
    entries.sort()
    return entries


def phase_label(raw: int) -> str:
    """The scene's phase enum, with the two deployment sentinels named."""
    if raw == 0xFFFFFFFE:
        return "deployment_unit"
    if raw == 0xFFFFFFFD:
        return "deployment_start"
    return telemetry_module.phase_name(raw)


REMOTE_KEYS = (
    "phase", "round", "current_side", "selected_unit", "active_unit_count",
    "unit_count", "selected_command", "player_completed", "enemy_completed",
    "scene_frame", "cursor_x", "cursor_y", "last_control_error",
    "last_player_error", "render_stage", "presentation_busy",
    "action_count", "action_index", "selected_action_id",
    "selected_action_error", "last_resolved_action_id",
    "background_chunk_index", "background_chunk_count",
    "selected_action_kind", "selected_action_tool_slot",
    "map_movement_active", "map_movement_sequence", "map_movement_elapsed",
    "condition_outcome", "script_phase", "map_visual_facing",
    "map_graphics_frame", "pickup_sequence",
)


def read_remake(rom: pathlib.Path, exe: pathlib.Path,
                states: list[pathlib.Path]) -> list[dict]:
    """Read the telemetry out of every captured remake savestate."""
    rows: list[dict] = []
    with probe_module.Probe(rom, exe=exe) as probe:
        telemetry = telemetry_module.Telemetry(probe)
        address = None
        for state in states:
            probe.load(state)
            if address is None:
                # The boot state has no battle running, so the struct is not
                # published yet.  Find it in the first state that has it and
                # then read every state at that fixed address.
                try:
                    address = telemetry.locate()
                except RuntimeError:
                    rows.append(None)
                    continue
                print(f"telemetry at 0x{address:08X}")
            blob = probe.dump(address, telemetry_module.BYTE_COUNT)
            words = __import__("struct").unpack(
                f"<{telemetry_module.WORD_COUNT}I", blob)
            values = dict(zip(telemetry_module.FIELDS, words))
            rows.append(values)
    return rows


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remake-dir", type=pathlib.Path, required=True)
    parser.add_argument("--remake-rom", type=pathlib.Path, required=True)
    parser.add_argument("--original-dir", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--align", type=pathlib.Path, default=None,
                        help="align-e3.json, for the anchor table")
    args = parser.parse_args(argv)

    remake_entries = step_entries(args.remake_dir)
    original_entries = step_entries(args.original_dir)
    remake_states = [args.remake_dir / f"step-{index:02d}-{key}.ss9"
                     for index, key, _ in remake_entries]
    missing = [str(p) for p in remake_states if not p.is_file()]
    if missing:
        raise SystemExit("ERR missing remake states: " + ", ".join(missing))

    telemetry_rows = read_remake(args.remake_rom, args.exe, remake_states)

    remake = []
    for (index, key, png), values in zip(remake_entries, telemetry_rows):
        row = {
            "step": index,
            "key": key,
            "press_index": index - 2 if index >= 2 else 0,
            "sha256": sha256_file(png),
            "png_bytes": png.stat().st_size,
        }
        if values is None:
            row.update({
                "phase": "no_battle_telemetry",
                "phase_raw": None,
                "round": None,
                "cursor": None,
                "selected_unit": None,
                "selected_command": None,
                "scene_frame": None,
            })
            remake.append(row)
            continue
        row.update({
            "phase": phase_label(values["phase"]),
            "phase_raw": values["phase"],
            "round": values["round"],
            "cursor": [values["cursor_x"], values["cursor_y"]],
            "selected_unit": values["selected_unit"],
            "selected_command": values["selected_command"],
            "scene_frame": values["scene_frame"],
        })
        for name in REMOTE_KEYS:
            if name in ("phase", "round", "cursor_x", "cursor_y",
                        "selected_unit", "selected_command", "scene_frame"):
                continue
            row[name] = values[name]
        remake.append(row)

    original = []
    for index, key, png in original_entries:
        original.append({
            "step": index,
            "key": key,
            "press_index": index,
            "sha256": sha256_file(png),
            "png_bytes": png.stat().st_size,
        })

    document = {
        "schema": "konoha.s49-press-phase-table.v1",
        "generated_by": "tools/s49_w21c2/make_phase_table.py",
        "roms": {
            "remake": {
                "path": str(args.remake_rom),
                "sha256": sha256_file(args.remake_rom),
            },
        },
        "captures": {
            "remake": str(args.remake_dir),
            "original": str(args.original_dir),
        },
        "step_semantics": {
            "remake": ("step-NN is the frame 90 frames after the NN-th key of "
                       "the sequence Down,Down,A*32 was released; "
                       "press_index counts the A presses only"),
            "original": ("step-NN is the frame 90 frames after the NN-th A of "
                         "A*24 was released"),
        },
        "original": original,
        "remake": remake,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False)
        + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out} "
          f"(original {len(original)} steps, remake {len(remake)} steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
