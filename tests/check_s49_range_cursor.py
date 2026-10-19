"""Runtime regression for S49's orange destination cell after one Right input.

Run as a module with ORIGINAL CURRENT capture directories. This diagnostic
isolates the overwritten range tiles; the full-screen comparison stays required.
"""

import json
import sys
from pathlib import Path

from PIL import Image

from tools.butano.compare_frame_sequences import _capture, _sha256


def check(original: Path, current: Path) -> dict:
    left_audit, left = _capture(original)
    right_audit, right = _capture(current)
    for audit in (left_audit, right_audit):
        assert (audit["key"], audit["input_after_frame"], audit["hold_frames"],
                audit["frame_count"]) == ("Right", 8, 1, 64)
    failures = []
    for frame in range(12, 64):
        with Image.open(left[frame]) as a, Image.open(right[frame]) as b:
            rectangle = (144, 72, 176, 88)
            if a.convert("RGB").crop(rectangle).tobytes() != b.convert("RGB").crop(rectangle).tobytes():
                failures.append(frame)
    return {
        "original": str(original), "current": str(current),
        "scope": "destination-cell pixels only; full-screen comparison is separate",
        "checked_frames": 52, "failures": failures,
        "original_frame_sha256": [_sha256(p) for p in left],
        "current_frame_sha256": [_sha256(p) for p in right],
    }


if __name__ == "__main__":
    result = check(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["failures"]))
