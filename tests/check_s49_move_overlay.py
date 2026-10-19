"""Runtime regression: preserve S49 movement grid during a confirmed right move.

Run as ``python3 -m tests.check_s49_move_overlay CAPTURE`` against the complete
96-frame recording (A after frame 8). These three unoccupied map cells isolate
the BG wiring regression; they do NOT replace the full-screen comparison.
"""

import json
import sys
from pathlib import Path

from PIL import Image

from tools.butano.compare_frame_sequences import _capture, _sha256


def check(directory: Path) -> dict:
    audit, frames = _capture(directory)
    assert (audit["key"], audit["input_after_frame"], audit["hold_frames"],
            audit["frame_count"]) == ("A", 8, 1, 96), "wrong input contract"
    rectangles = [(160, 112, 176, 128), (0, 80, 16, 96), (64, 32, 80, 48)]
    failures = []
    with Image.open(frames[8]) as image:
        references = [image.convert("RGB").crop(rect).tobytes() for rect in rectangles]
    for index in range(12, 34):
        with Image.open(frames[index]) as image:
            for rect, reference in zip(rectangles, references, strict=True):
                if image.convert("RGB").crop(rect).tobytes() != reference:
                    failures.append({"frame": index, "rectangle": rect})
    return {
        "capture": str(directory), "audit_sha256": _sha256(directory / "audit.json"),
        "scope": "movement BG persistence only; all-screen fidelity is separate",
        "checked_frames": 22, "checked_cells_per_frame": 3, "failures": failures,
        "frame_sha256": [_sha256(frame) for frame in frames],
    }


if __name__ == "__main__":
    result = check(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["failures"]))
