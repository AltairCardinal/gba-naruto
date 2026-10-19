"""Compare every pixel of every input-anchored GBA video frame, without masks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from tools.butano.compare_s49_prebattle import compare_full_screen_images


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture(path: Path) -> tuple[dict, list[Path]]:
    audit = json.loads((path / "audit.json").read_text())
    if audit.get("status") != "capture-complete" or audit.get("record_all") is not True:
        raise ValueError(f"{path}: complete record_all capture required")
    count = audit.get("frame_count")
    if type(count) is not int or count < 1:
        raise ValueError(f"{path}: positive frame_count required")
    expected = [path / f"frame-{index:03d}.png" for index in range(count)]
    if set(path.glob("frame-*.png")) != set(expected):
        raise ValueError(f"{path}: frame set differs from declared complete denominator")
    return audit, expected


def compare_sequences(original: Path, current: Path) -> dict:
    original, current = Path(original), Path(current)
    left_audit, left_frames = _capture(original)
    right_audit, right_frames = _capture(current)
    for field in ("key", "hold_frames", "input_after_frame", "frame_count"):
        if left_audit.get(field) != right_audit.get(field):
            raise ValueError(f"input timing/length mismatch: {field}")
    frames = []
    for index, (left, right) in enumerate(zip(left_frames, right_frames, strict=True)):
        with Image.open(left) as left_image, Image.open(right) as right_image:
            comparison = compare_full_screen_images(left_image, right_image)
        frames.append({"frame": index, **comparison,
                       "original_sha256": _sha256(left), "current_sha256": _sha256(right)})
    different_frames = sum(frame["different_pixels"] > 0 for frame in frames)
    return {
        "schema": "konoha.full-frame-comparison.v1",
        "status": "different" if different_frames else "identical",
        "alignment": "same-index-no-exclusions",
        "original": str(original), "current": str(current),
        "original_audit": left_audit, "current_audit": right_audit,
        "original_audit_sha256": _sha256(original / "audit.json"),
        "current_audit_sha256": _sha256(current / "audit.json"),
        "compared_frames": len(frames), "compared_pixels": len(frames) * 240 * 160,
        "different_frames": different_frames,
        "different_pixels": sum(frame["different_pixels"] for frame in frames),
        "frames": frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare_sequences(args.original, args.current)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    # Preserve prior evidence: callers choose a new path for each comparison.
    with args.output.open("x") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "compared_frames", "different_frames", "different_pixels")}))
    return int(result["different_frames"] != 0)


if __name__ == "__main__":
    raise SystemExit(main())
