"""The static frame criterion.

The original's unit outline is rewritten every frame, so two neighbouring
frames of the original differ by the outline colour.  The wave is quantised
to sixteen shades, and the darkest shade (phase 9 -> 10) and the brightest
one (phase 25 -> 26) each span two phases; there the original's own frame
repeats.  Measured on the original's dense sweep: **four** identical GBA
frame pairs per hundred frames, all of them at a wave flat spot.

So the rule is *not* "never identical" but:

    two consecutive frames may only be identical when the outline wave is at
    one of its flat spots.

The flat spot is read out of the frame itself: the outline is the only
colour of the shape ``(0, g, g)`` in the unit's pixel region, so the shade
of a frame says whether that frame sits on a flat spot (shade 1 or 31) or
not.  Two conditions have to hold for a repeat to be excused:

* the capture shows **more than one** outline shade -- a side whose outline
  never changes is not "at a flat spot", it is frozen, and every repeat it
  produces is a defect; and
* the repeated frame's own shade is a flat spot shade.

When a pose identification is supplied (the phase map of the original's
dense sweep) the phase test is used instead: it is the authoritative one,
because it names the phase pair the repeat happened at.
"""

from __future__ import annotations

from .paths import FLAT_SPOT_PHASES, FLAT_SPOT_SHADES
from .pixels import outline_shades, pixel_digest

STATIC_RULE = (
    "two consecutive frames may only be identical at the outline wave's "
    "flat spots (shade 1 or 31, phase 9->10 and 25->26), and only when the "
    "capture shows the outline wave actually animating"
)


def cycle_positions(poses: list[int], stride: int) -> list[int] | None:
    """The pose cycle position of every sampled frame, or None."""
    start = None
    for index, pose in enumerate(poses):
        if pose == 9:
            start = index
            break
    if start is None:
        return None
    start_game = start // stride
    return [(index - start_game) % 32
            for index in range(len(poses) // stride)]


def check_capture(images: dict[str, object], order: list[str], *,
                  stride: int = 1, poses: list[int] | None = None,
                  region=None, shades_of=None) -> dict:
    """Every consecutive identical pair of one capture.

    ``images`` maps a frame name to its decoded RGB image, ``order`` is the
    sampled frame order.  ``poses`` is the optional phase identification.
    """
    from .paths import OUTLINE_REGION

    region = region or OUTLINE_REGION
    if shades_of is None:
        def shades_of(name):
            return outline_shades(images[name], region)

    sampled = order[::stride]
    digests = [pixel_digest(images[name]) for name in sampled]
    shades = [shades_of(name) for name in sampled]
    distinct_shades = sorted({shade for row in shades for shade in row})
    positions = None
    if poses is not None:
        positions = cycle_positions(poses, stride)

    pairs = []
    for index in range(1, len(digests)):
        if digests[index] != digests[index - 1]:
            continue
        frame_shades = shades[index]
        phase_before = phase_after = None
        flat_spot = None
        reason = ""
        if positions is not None:
            phase_before = positions[index - 1]
            phase_after = positions[index]
            flat_spot = (phase_before, phase_after) in FLAT_SPOT_PHASES
            reason = ("phase pair" if flat_spot else "phase pair is not a flat spot")
        else:
            wave_animates = len(distinct_shades) > 1
            at_flat_shade = bool(set(frame_shades) & FLAT_SPOT_SHADES)
            flat_spot = wave_animates and at_flat_shade
            if not wave_animates:
                reason = ("the outline wave never changes in this capture "
                          f"(shades {distinct_shades}), so the frame is "
                          "frozen, not at a flat spot")
            elif not at_flat_shade:
                reason = (f"outline shade {frame_shades} is not a flat spot "
                          f"shade {sorted(FLAT_SPOT_SHADES)}")
            else:
                reason = "outline shade is a flat spot shade"
        pairs.append({
            "previous": sampled[index - 1],
            "current": sampled[index],
            "sha256": digests[index],
            "outline_shades": frame_shades,
            "phase_before": phase_before,
            "phase_after": phase_after,
            "wave_flat_spot": flat_spot,
            "reason": reason,
        })

    unexpected = [pair for pair in pairs if not pair["wave_flat_spot"]]
    return {
        "frames": len(sampled),
        "stride": stride,
        "distinct_outline_shades": distinct_shades,
        "outline_wave_animates": len(distinct_shades) > 1,
        "consecutive_identical_pairs": len(pairs),
        "unexpected_pairs": len(unexpected),
        "pairs": pairs,
    }
