"""Content anchors: what the machine state says about each captured frame.

The frame *index* is not a game moment -- the two walks press different
buttons and therefore visit different moments (the pairing offsets drift from
+4 to -15 and jump back).  A content anchor is a value that identifies the
moment instead, and it has to be readable by a machine, not by an eye.

The bench reads three kinds of anchor:

``screen``
    The brightness facts of the frame itself (share of non-black pixels, mean
    RGB, number of distinct colours).  These separate a fade frame from a
    battle frame without anybody looking at it.

``registers``
    The IO register block of the savestate the frame was captured from:
    ``DISPCNT``, the four background control registers and the four
    horizontal scroll registers (the camera).  The vertical scroll registers
    are *not* read: the headless debugger answers them with a constant
    filler, so a camera anchor built from them would be fiction.

``overlay``
    The family of every lit cell of the overlay layer, decoded out of the
    overlay's own background map in VRAM.  This is the "which cells are
    painted, and with what" anchor, and it is also the second dimension of
    the residual.

Every anchor is derived from a *file*, so the whole record is reproducible.
"""

from __future__ import annotations

import hashlib
import pathlib

from . import overlay as overlay_module
from . import probe as probe_module
from .paths import BLACK_NON_BLACK_LIMIT, OUTLINE_REGION
from .pixels import outline_shades, pixel_digest, screen_stats

ANCHOR_SCHEMA = "s49-content-anchor/1"


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_path(cache_dir: pathlib.Path, side: str, state: pathlib.Path) -> pathlib.Path:
    return cache_dir / side / f"{state.stem}.state.bin"


def read_states(side: str, capture_dir: pathlib.Path, rom: pathlib.Path,
                cache_dir: pathlib.Path) -> dict:
    """The IO / PRAM / VRAM dumps of every captured step.

    The dumps are cached on disk; the cache key is the savestate's sha256 so
    a re-recorded walk is never read through a stale cache.
    """
    states = sorted(capture_dir.glob("step-*.ss9"))
    if not states:
        return {}
    result = {}
    pending = []
    for state in states:
        key = _sha256_file(state)
        target = _cache_path(cache_dir, side, state)
        marker = target.with_suffix(".sha256")
        if target.exists() and marker.exists() and marker.read_text(
                encoding="utf-8").strip() == key:
            result[state.name] = {"cache": target, "sha256": key}
        else:
            pending.append((state, target, marker, key))
    if pending:
        with probe_module.Probe(rom) as device:
            for state, target, marker, key in pending:
                data = device.read_state(state)
                target.parent.mkdir(parents=True, exist_ok=True)
                # Write through a temporary file and rename: two benches may
                # share one cache directory, and a reader must never see a
                # half written dump.
                temporary = target.with_suffix(".tmp")
                temporary.write_bytes(
                    data["io"] + data["pram"] + data["vram"])
                temporary.replace(target)
                temporary = marker.with_suffix(".tmp")
                temporary.write_text(key + "\n", encoding="utf-8", newline="\n")
                temporary.replace(marker)
                result[state.name] = {"cache": target, "sha256": key}
    return result


def _decode_state(path: pathlib.Path) -> dict:
    blob = path.read_bytes()
    io_length = probe_module.IO_LENGTH
    pram_length = probe_module.PRAM_LENGTH
    return {
        "io": blob[:io_length],
        "pram": blob[io_length:io_length + pram_length],
        "vram": blob[io_length + pram_length:],
    }


def side_anchors(side: str, capture_dir: pathlib.Path, rom: pathlib.Path | None,
                  images: dict, cache_dir: pathlib.Path,
                  use_probe: bool = True) -> dict:
    """The content anchor of every captured frame of one side.

    ``images`` maps the frame file name to its decoded RGB image; the
    brightness and outline facts come from the pixels, the rest from the
    savestate.
    """
    frames: dict[str, dict] = {}
    status = "ok"
    reason = None
    states: dict[str, dict] = {}
    if use_probe and rom is not None:
        try:
            states = read_states(side, capture_dir, rom, cache_dir)
        except (probe_module.ProbeError, OSError) as exc:
            status = "unavailable"
            reason = f"{type(exc).__name__}: {exc}"
            states = {}
    elif not use_probe:
        status = "skipped"
        reason = "the probe was not used"
    else:
        status = "unavailable"
        reason = "no rom given"

    for name in sorted(images):
        image = images[name]
        anchor = {
            "frame": name,
            "screen": screen_stats(image),
            "pixel_digest": pixel_digest(image),
            "outline_shades": outline_shades(image, OUTLINE_REGION),
        }
        state_name = name.replace(".png", ".ss9")
        entry = states.get(state_name)
        if entry is not None:
            data = _decode_state(entry["cache"])
            registers = probe_module.io_registers(data["io"])
            anchor["registers"] = {
                "dispcnt": registers["dispcnt"],
                "dispcnt_hex": f"0x{registers['dispcnt']:04X}",
                "bg_cnt": registers["bg_cnt"],
                "bg_hofs": registers["bg_hofs"],
                # ⭐ 2026-10-25 (wave 20 / E3): the scroll registers read back
                # as a per-frame constant filler (open bus) on this headless
                # debugger, so bg_hofs is **not** a camera reading.  The flag
                # tells the report to stop comparing it as one.
                "bg_hofs_readable": registers.get("bg_hofs_readable"),
            }
            anchor["palette_black"] = probe_module.pram_is_black(data["pram"])
            grid, info = _overlay_grid(side, data["vram"])
            if grid is not None:
                anchor["_grid"] = grid
                anchor["overlay"] = {
                    "map": info.get("overlay_map"),
                    "lit_cells": overlay_module.lit_cells(grid),
                    "family_counts": overlay_module.grid_counts(grid),
                    "family_digest": overlay_module.grid_digest(grid),
                }
        frames[name] = anchor

    return {
        "schema": ANCHOR_SCHEMA,
        "side": side,
        "status": status,
        "reason": reason,
        "frames": frames,
    }


def _overlay_grid(side: str, vram: bytes):
    if side == "original":
        return overlay_module.original_grid(vram), {
            "overlay_map": overlay_module.ORIGINAL_OVERLAY_OFFSET}
    return overlay_module.remake_grid(vram)


def is_black_transition(anchor: dict) -> bool:
    """True when the frame is a fade frame rather than a battle frame.

    The test is the frame's own brightness: a fade frame is (nearly) black,
    every battle frame is not.  Measured on the 2026-10-23 baseline the two
    fade frames of the original sit at 0.79 % and 0.00 % non-black pixels,
    every other frame at >= 85 %.

    The display configuration is the corroborating evidence: on the original
    the two fade frames are exactly the two frames whose ``DISPCNT`` differs
    from the walk's usual value (see ``dispcnt_variation``).  The palette is
    *not* blacked out during the fade, so the palette cannot be used as the
    test -- it is reported as a fact instead.
    """
    return anchor["screen"]["non_black_fraction"] < BLACK_NON_BLACK_LIMIT


def dispcnt_variation(anchors: dict) -> dict:
    """The frames whose display configuration differs from the usual one."""
    counts: dict[int, int] = {}
    for frame in anchors.get("frames", {}).values():
        registers = frame.get("registers")
        if not registers:
            continue
        counts[registers["dispcnt"]] = counts.get(registers["dispcnt"], 0) + 1
    if not counts:
        return {"modal_dispcnt_hex": None, "distinct_dispcnt": [],
                "deviating_frames": []}
    modal = max(counts.items(), key=lambda item: (item[1], -item[0]))[0]
    deviating = sorted(
        name for name, frame in anchors.get("frames", {}).items()
        if frame.get("registers")
        and frame["registers"]["dispcnt"] != modal)
    return {
        "modal_dispcnt_hex": f"0x{modal:04X}",
        "distinct_dispcnt": [f"0x{value:04X}" for value in sorted(counts)],
        "deviating_frames": deviating,
    }


def pairing_quality(rows: list[dict], anchors: dict) -> dict:
    """How well the content anchors back up the pairing.

    ``rows`` are the per frame rows of the report (each carries the overlay
    residual of its pair).  The anchors are the per frame records of both
    sides.

    * ``frames_with_anchor`` -- the frames whose pair has an anchor record on
      both sides.
    * ``blank_state_agrees`` -- the frames where the two sides agree on
      whether the screen is a fade frame.
    * ``anchor_supports_pairing`` -- the frames where the anchors *back* the
      pairing: the blank state agrees **and** the two overlay layers share a
      lit cell after the alignment.
    * ``overlay_exact`` -- the frames whose two overlay family maps are
      identical (overlay residual 0).
    """
    total = len(rows)
    with_anchor = 0
    with_overlay = 0
    blank_agrees = 0
    supports = 0
    exact = 0
    overlap: list[int] = []
    details = {}
    for row in rows:
        original_name = row["original"]
        remake_name = row["best_match"]
        left = anchors["original"]["frames"].get(original_name)
        right = anchors["remake"]["frames"].get(remake_name)
        if left is None or right is None:
            continue
        with_anchor += 1
        dark_left = left["screen"]["non_black_fraction"] < BLACK_NON_BLACK_LIMIT
        dark_right = (right["screen"]["non_black_fraction"]
                      < BLACK_NON_BLACK_LIMIT)
        agrees = dark_left == dark_right
        if agrees:
            blank_agrees += 1
        overlay_result = row.get("overlay_residual")
        shared = 0
        if overlay_result:
            with_overlay += 1
            shared = overlay_result["both_lit"]
            overlap.append(shared)
            if overlay_result["residual"] == 0:
                exact += 1
        if agrees and shared > 0:
            supports += 1
        details[original_name] = {
            "remake": remake_name,
            "blank_state_agrees": agrees,
            "overlay_shared_cells": shared,
        }
    return {
        "frames": total,
        "frames_with_anchor": with_anchor,
        "frames_with_overlay": with_overlay,
        "blank_state_agrees": blank_agrees,
        "anchor_supports_pairing": supports,
        "overlay_exact": exact,
        "overlay_shared_cells": {
            "min": min(overlap) if overlap else 0,
            "max": max(overlap) if overlap else 0,
            "sum": sum(overlap),
        },
        "coverage": round(with_anchor / total, 4) if total else 0.0,
        "details": details,
    }
