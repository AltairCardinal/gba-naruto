"""The pairing table -- which remake frame is the *same game moment*.

The judgment bench pairs a frame with the remake frame that looks closest.
That is a **pixel** argument and it cannot answer the question the residual
actually asks: *are the two frames at the same moment?*  This module answers
it from the **content anchor** instead, and then reports the pixel residual of
the anchored pair as an independent check.

The anchor's comparable facts (both ROMs, both walks):

``scene``
    ``fade`` when the frame is (nearly) black, ``dialogue`` when the dialogue
    box is open, ``map`` otherwise.  Comparable everywhere, including the
    parts of the walk where the camera is not.

``camera_v``
    The vertical scroll of the layer that carries the map, masked to the nine
    bits the hardware keeps.  The two ROMs put the map on different
    background layers, so the layer is *measured* per side.  Comparable in the
    ``map`` scene, where the two sides follow the same sequence.

``acting``
    The acting unit pointer, normalised to a zero based index (the original
    counts from 1, the remake from 0).  Comparable in the ``map`` scene.

``bright_share``
    The share of "bright paper" pixels in the lower band of the frame -- the
    dialogue box.  Comparable in the ``dialogue`` scene, where the camera is
    not.

**The reachability bound.**  For an original frame ``o`` let ``S(o)`` be the
remake frames whose moment key equals ``o``'s.  If ``S(o)`` is empty then *no*
frame of the recorded game-time line shows the same moment as ``o``; the
residual of ``o`` therefore cannot be driven down by any walk, and the frame
is a product gap rather than a pairing gap.  The number of such frames is a
**lower bound** on the pairing diff that survives any walk.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from s49_fidelity_report.pixels import diff_mask  # noqa: E402

FIELD_AREA = (0, 0, 240, 128)
BLACK_LIMIT = 0.05


def fade_runs(anchors: dict) -> dict:
    """The fade run index of every fade frame of one side.

    A *fade run* is a maximal group of consecutive fade frames in capture
    order: the original fades the screen out, comes back and fades out again
    later, and those are two different moments.
    """
    runs = {}
    current = -1
    previous = None
    for name, anchor in anchors["frames"].items():
        if anchor["scene"] != "fade":
            previous = None
            continue
        if previous is None:
            current += 1
        runs[name] = current
        previous = name
    return runs


def moment_key(anchor: dict, layer: int, fade_run: int | None = None) -> tuple:
    """The comparable moment signature of a frame."""
    scene = anchor["scene"]
    if scene == "map":
        return (scene, anchor["registers"]["bg_vofs"][layer])
    if scene == "dialogue":
        return (scene, round(anchor["bright_share"], 3))
    return (scene, fade_run)


def moment_label(anchor: dict, layer: int, fade_run: int | None = None) -> str:
    """A human readable description of the moment a frame is at."""
    scene = anchor["scene"]
    families = "+".join(anchor["overlay"]["non_blank_families"]) or "no-overlay"
    acting = anchor.get("acting")
    acting_text = ("" if acting is None
                   else f", acting={acting['index']}")
    if scene == "map":
        camera = f"BG{layer}VOFS={anchor['registers']['bg_vofs'][layer]}"
    elif scene == "dialogue":
        camera = f"box={anchor['bright_share']:.3f}"
    else:
        camera = f"fade#{fade_run}"
    return (f"{scene}, {camera}, overlay={families} "
            f"({anchor['overlay']['lit_cells']} lit){acting_text}")


def moment_distance(left: dict, right: dict, layer: int,
                    left_fade: int | None, right_fade: int | None) -> tuple:
    """The anchor distance between two frames (no pixels involved).

    The distance is a tuple so it can be compared lexicographically: the
    scene class first (a fade frame is never the same moment as a battle
    frame), then the scene's own discriminator, then the acting pointer.
    """
    if left["scene"] != right["scene"]:
        return (1, 0, 0)
    if left["scene"] == "map":
        discriminator = abs(left["registers"]["bg_vofs"][layer]
                            - right["registers"]["bg_vofs"][layer])
    elif left["scene"] == "dialogue":
        discriminator = abs(round(left["bright_share"], 3)
                            - round(right["bright_share"], 3))
    else:
        discriminator = abs((left_fade or 0) - (right_fade or 0))
    left_acting = (left.get("acting") or {}).get("index")
    right_acting = (right.get("acting") or {}).get("index")
    if left_acting is None or right_acting is None:
        acting_penalty = 0
    else:
        acting_penalty = min(abs(left_acting - right_acting), 9)
    return (0, discriminator, acting_penalty)


def build_table(original_anchors: dict, remake_anchors: dict,
                original_layer: int, remake_layer: int) -> list[dict]:
    """The pairing table: one row per original frame."""
    original_frames = original_anchors["frames"]
    remake_frames = remake_anchors["frames"]
    left_fades = fade_runs(original_anchors)
    right_fades = fade_runs(remake_anchors)

    exact = {}
    for name, right in remake_frames.items():
        exact.setdefault(moment_key(right, remake_layer, right_fades.get(name)),
                          []).append(name)

    rows = []
    for name, left in original_frames.items():
        key = moment_key(left, original_layer, left_fades.get(name))
        candidates = exact.get(key, [])
        best_name = None
        best_distance = None
        for candidate, right in remake_frames.items():
            distance = moment_distance(left, right, remake_layer,
                                       left_fades.get(name),
                                       right_fades.get(candidate))
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_name = candidate
        right = remake_frames[best_name]
        rows.append({
            "original": name,
            "anchor_match": candidates[0] if candidates else None,
            "anchor_candidates": candidates,
            "anchor_match_candidates": len(candidates),
            "closest": best_name,
            "original_moment": moment_label(left, original_layer,
                                            left_fades.get(name)),
            "closest_moment": moment_label(right, remake_layer,
                                           right_fades.get(best_name)),
            "moment_key": list(key),
            "exact_moment": bool(candidates),
            "anchor_distance": list(best_distance),
        })
    return rows


def residual_of(original_dir: pathlib.Path, remake_dir: pathlib.Path,
                left_name: str, right_name: str) -> int:
    """The battlefield residual of one anchored pair."""
    from PIL import Image

    with Image.open(original_dir / left_name) as handle:
        left = handle.convert("RGB")
    with Image.open(remake_dir / right_name) as handle:
        right = handle.convert("RGB")
    count, _ = diff_mask(left, right, FIELD_AREA)
    return count


def reachability(original_anchors: dict, remake_anchors: dict,
                 original_layer: int, remake_layer: int) -> dict:
    """The reachability bound: which moments the remake never shows.

    For every original frame the *closest* moment key of the whole remake walk
    is computed.  A frame whose own key is not available at all has **no**
    counterpart in the remake's game-time line, so no walk can make its
    residual small: it is a product gap.
    """
    remake_frames = remake_anchors["frames"]
    left_fades = fade_runs(original_anchors)
    right_fades = fade_runs(remake_anchors)
    available = {}
    for name, anchor in remake_frames.items():
        available.setdefault(
            moment_key(anchor, remake_layer, right_fades.get(name)), []).append(name)

    rows = []
    for name, left in original_anchors["frames"].items():
        key = moment_key(left, original_layer, left_fades.get(name))
        if key in available:
            rows.append({"original": name, "moment_key": list(key),
                         "counterpart": True,
                         "remake_frames": sorted(available[key])[:8]})
        else:
            best = None
            best_name = None
            for candidate, right in remake_frames.items():
                distance = moment_distance(left, right, remake_layer,
                                           left_fades.get(name),
                                           right_fades.get(candidate))
                if best is None or distance < best:
                    best = distance
                    best_name = candidate
            rows.append({"original": name, "moment_key": list(key),
                         "counterpart": False,
                         "closest_distance": list(best),
                         "closest_remake": best_name})
    missing = [row for row in rows if not row["counterpart"]]
    return {
        "original_frames": len(rows),
        "frames_with_counterpart": len(rows) - len(missing),
        "frames_without_counterpart": len(missing),
        "pairing_diff_lower_bound": len(missing),
        "rows": rows,
    }


def beat_floor(original_dir: pathlib.Path, remake_dir: pathlib.Path,
               beats: int, per_beat: int) -> dict:
    """The provable floor of the residual under a same-semantics walk.

    The walk has two freedoms: the capture point inside a beat and the
    sampling density.  This computes, for every original beat, the smallest
    battlefield residual that ANY frame of that beat can reach against ANY
    frame of the remake's recording.  The sum is the floor: no walk built on
    these two recordings can go below it.
    """
    from PIL import Image

    original_files = sorted(original_dir.glob("step-*.png"))
    remake_files = sorted(remake_dir.glob("step-*.png"))
    if not original_files or not remake_files:
        raise SystemExit("ERR the dense walk is missing")

    remake_unique = {}
    for path in remake_files:
        with Image.open(path) as handle:
            image = handle.convert("RGB")
        digest = image.crop(FIELD_AREA).tobytes()
        remake_unique.setdefault(digest, image)

    original_images = {}
    for path in original_files:
        with Image.open(path) as handle:
            original_images[path.name] = handle.convert("RGB")

    canonical = [original_files[0]] + [original_files[per_beat * k]
                                       for k in range(1, beats + 1)]
    rows = []
    total_floor = 0
    total_canonical = 0
    for index, frame in enumerate(canonical):
        if index == 0:
            members = original_files[0:1]
        else:
            members = original_files[per_beat * (index - 1) + 1:
                                     per_beat * index + 1]
        best = None
        best_member = None
        canonical_px = None
        for member in members:
            image = original_images[member.name]
            for other in remake_unique.values():
                count, _ = diff_mask(image, other, FIELD_AREA)
                if best is None or count < best:
                    best = count
                    best_member = member.name
            if member.name == frame.name:
                for other in remake_unique.values():
                    count, _ = diff_mask(image, other, FIELD_AREA)
                    if canonical_px is None or count < canonical_px:
                        canonical_px = count
        total_floor += best
        total_canonical += canonical_px
        rows.append({"beat": index, "canonical": frame.name,
                     "canonical_px": canonical_px, "floor_px": best,
                     "floor_member": best_member})
    return {
        "remake_frames": len(remake_files),
        "remake_distinct": len(remake_unique),
        "per_beat": per_beat,
        "canonical_sum": total_canonical,
        "floor_sum": total_floor,
        "rows": rows,
    }
