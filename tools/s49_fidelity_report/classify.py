"""The attribution: what the residual on a frame actually means.

The bench has three top level classes, decided exactly as before:

``identical``     -- zero residual on the battlefield area.
``product_diff`` -- the two frames are the *same game moment*; the residual
                     is a real rendering difference and the product code is
                     wrong.
``pairing_diff`` -- the two frames are *different game moments*; the
                     residual says nothing about the product code.

Whether two frames are the same game moment is a majority vote of three
content signals (see ``vote`` below).

``pairing_diff`` used to be one bucket, but it mixes three mechanisms, so it
is now refined into three, each with a machine readable test:

``black_transition``
    The *original* frame is a fade frame: the share of its non-black pixels
    is below the limit and the palette it is rendered with is black.  The
    original fades the screen out for a moment and the remake never does.

``static_frame``
    The *remake* side is holding a still frame at that moment: the remake
    frame the original was paired with is a frame the remake repeats (its
    pixels occur more than once in the remake walk), or the pairing stalled
    on it (the same remake frame is the best match for the neighbouring
    original step as well, so the remake did not advance while the original
    did).

``moment_mismatch``
    Neither of the above: the two sides really are at different game
    moments and nothing about the product code can be concluded.
"""

from __future__ import annotations

from .paths import (DISSENT_CONFIDENCE_MARGIN, HIGH_CONFIDENCE_MARGIN,
                    MIN_CONFIDENCE_MARGIN, OCCUPANCY_THRESHOLD,
                    ROW_SPREAD_THRESHOLD, STRUCT_THRESHOLD,
                    STRUCT_TOLERANCE)

CLASS_NAMES = {
    "identical": "一致",
    "product_diff": "产品差",
    "pairing_diff": "配对差",
}

SUBCLASS_NAMES = {
    "black_transition": "黑场过渡",
    "static_frame": "静止帧",
    "moment_mismatch": "时刻不一致",
}

SUBCLASS_RULES = {
    "black_transition": (
        "the original frame is a fade frame: its non-black pixel share is "
        "below the limit (0.79 % and 0.00 % on the baseline, every battle "
        "frame at 85 % or more)"),
    "static_frame": (
        "the remake side holds a still frame: the paired remake frame is "
        "repeated in the remake walk, or the pairing stalled on it (the "
        "previous original step was paired to the same remake frame, so the "
        "remake's screen did not advance while the original's did)"),
    "moment_mismatch": (
        "neither of the above: the two sides are at different game moments"),
}


def vote(structure: float, occupancy: float, spread: float) -> dict:
    """Majority vote of the three content signals, plus margin and confidence."""
    signals = {
        "structure_match": {
            "value": structure,
            "threshold": STRUCT_THRESHOLD,
            "tolerance": STRUCT_TOLERANCE,
            "margin": (structure - STRUCT_THRESHOLD) / (1.0 - STRUCT_THRESHOLD)
            if structure >= STRUCT_THRESHOLD
            else (structure - STRUCT_THRESHOLD) / STRUCT_THRESHOLD,
        },
        "diff_block_occupancy": {
            "value": occupancy,
            "threshold": OCCUPANCY_THRESHOLD,
            "margin": (OCCUPANCY_THRESHOLD - occupancy) / OCCUPANCY_THRESHOLD
            if occupancy <= OCCUPANCY_THRESHOLD
            else (OCCUPANCY_THRESHOLD - occupancy) / (1.0 - OCCUPANCY_THRESHOLD),
        },
        "diff_row_spread": {
            "value": spread,
            "threshold": ROW_SPREAD_THRESHOLD,
            "margin": (ROW_SPREAD_THRESHOLD - spread) / ROW_SPREAD_THRESHOLD
            if spread <= ROW_SPREAD_THRESHOLD
            else (ROW_SPREAD_THRESHOLD - spread) / (1.0 - ROW_SPREAD_THRESHOLD),
        },
    }
    votes_same = sum(1 for signal in signals.values() if signal["margin"] > 0)
    same_moment = votes_same >= 2
    agreeing = [signal for signal in signals.values()
                if (signal["margin"] > 0) == same_moment]
    dissenting = [signal for signal in signals.values()
                  if (signal["margin"] > 0) != same_moment]
    support = min((abs(signal["margin"]) for signal in agreeing), default=0.0)
    dissent = min((abs(signal["margin"]) for signal in dissenting), default=None)

    if dissent is None:
        if support >= HIGH_CONFIDENCE_MARGIN:
            confidence = "high"
        elif support >= MIN_CONFIDENCE_MARGIN:
            confidence = "medium"
        else:
            confidence = "low"
    elif dissent >= DISSENT_CONFIDENCE_MARGIN:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "same_moment": same_moment,
        "votes": {"same": votes_same, "different": 3 - votes_same},
        "signals": signals,
        "support_margin": round(support, 6),
        "dissent_margin": None if dissent is None else round(dissent, 6),
        "confidence": confidence,
    }


def refine_pairing_diff(original_anchor: dict | None,
                         remake_anchor: dict | None,
                         remake_repeated: bool,
                         pairing_stalled: bool) -> dict:
    """The three buckets inside ``pairing_diff``."""
    from .anchors import is_black_transition

    evidence = {
        "original_is_black_transition": bool(
            original_anchor is not None
            and is_black_transition(original_anchor)),
        "remake_frame_is_repeated": bool(remake_repeated),
        "pairing_stalled": bool(pairing_stalled),
    }
    if evidence["original_is_black_transition"]:
        subclass = "black_transition"
    elif evidence["remake_frame_is_repeated"] or evidence["pairing_stalled"]:
        subclass = "static_frame"
    else:
        subclass = "moment_mismatch"
    return {
        "subclass": subclass,
        "subclass_label": SUBCLASS_NAMES[subclass],
        "subclass_rule": SUBCLASS_RULES[subclass],
        "evidence": evidence,
    }
