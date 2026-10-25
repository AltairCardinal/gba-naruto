#!/usr/bin/env python3
"""Measure the *relative* idle cadence of the original and of the remake.

The question this answers is the one the S49 plan could not settle with
absolute counters: "does the remake keep up with the original's idle
rhythm?"  Absolute counts cannot be compared across emulators, so every
number here is derived from **one recording** and reported in that
recording's own units, plus the conversion into GBA frames that the local
probe's capture duplication makes necessary.

What the instrument reports per recording:

  duplicate pairs        how many captured frames are byte identical to
                         their neighbour.  The local probe fires the Lua
                         "frame" callback twice per GBA frame, so this is
                         2 on this machine and 1 elsewhere.
  distinct images       how many different pictures a window of N captured
                         frames holds.
  pose sequence          the ROM frame index per captured frame, identified
                         by matching the exported frame art in palette index
                         space (true mismatch must be 0).
  outline ramp phase     the phase of the original's 32 step triangle wave
                         over the outline's 5 bit green channel, read out of
                         the outline colour (0, g, g) on screen.

Usage::

    python tools/s49_idle_cadence.py --sweep <dir> [--pose]
    python tools/s49_idle_cadence.py --compare <original-dir> <remake-dir>

The sweep directories are produced by the headless probe with
``tools/butano/mgba_original_input_frame_sequence.lua`` in record-all mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_VISUALS = Path(
    r"D:\Shell\Github\gba-naruto-reverse\artifacts\character-battle-visuals-v1")
SCREEN = (240, 160)


# ----------------------------------------------------------------- helpers

def load_palette(path: Path) -> list[tuple[int, int, int]]:
    raw = Path(path).read_bytes()
    return [
        (((entry >> 10 & 0x1F) << 3) | ((entry >> 10 & 0x1F) >> 2),
         ((entry >> 5 & 0x1F) << 3) | ((entry >> 5 & 0x1F) >> 2),
         ((entry & 0x1F) << 3) | ((entry & 0x1F) >> 2))
        for entry in
        (int.from_bytes(raw[offset:offset + 2], "little")
         for offset in range(0, len(raw), 2))
    ]


def screen_index_map(image, palette):
    lookup = {colour: index for index, colour in enumerate(palette)}
    raw = image.convert("RGB").tobytes()
    return [
        lookup.get((raw[o], raw[o + 1], raw[o + 2]), -1)
        for o in range(0, len(raw), 3)
    ]


def outline_phase(colour) -> int | None:
    """Phase of the outline's triangle wave from its (0, g, g) colour.

    The original writes OBJ palette index 15 with g = 1, 3, ... 31, so the
    5 bit value is 1 + 2 * step and the step is the wave's phase.
    """
    r, g, b = colour
    if r != 0 or g != b or g == 0:
        return None
    for value in range(1, 32, 2):
        if (value << 3) | (value >> 2) == g:
            return (value - 1) // 2
    return None


def resource_for(visuals: Path, character_id: int, slot: int) -> Path:
    manifest = json.loads((visuals / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["slots"]:
        if (item.get("character_id") == character_id
                and item.get("visual_slot") == slot
                and item.get("populated")):
            return visuals / f"resource-{item['resource_id']:03d}"
    raise SystemExit(f"no populated slot {slot} for character {character_id}")


# ------------------------------------------------------------------ measure

def measure(directory: Path, pattern: str, pose: bool,
            visuals: Path, character_id: int, slot: int,
            region: tuple[int, int, int, int]) -> dict[str, Any]:
    from PIL import Image

    paths = sorted(directory.glob(pattern))
    if not paths:
        raise SystemExit(f"no frames matching {pattern} in {directory}")
    images = [Image.open(path).convert("RGB") for path in paths]
    digests = [hashlib.sha256(image.tobytes()).hexdigest()
               for image in images]
    duplicates = sum(1 for index in range(0, len(digests) - 1, 2)
                     if digests[index] == digests[index + 1])

    result: dict[str, Any] = {
        "directory": str(directory),
        "frames": len(images),
        "duplicate_pairs": duplicates,
        "captured_frames_per_game_frame": 2 if duplicates * 2 >= len(digests) else 1,
        "distinct_images": {
            str(window): len(set(digests[:window]))
            for window in (16, 32, 64) if window <= len(digests)
        },
    }

    # The outline ramp, read out of the unit's own pixels.
    x0, y0, x1, y1 = region
    ramp = []
    for image in images:
        crop = image.crop(region)
        counter = Counter(
            colour for colour in crop.getdata()
            if colour[0] == 0 and colour[1] == colour[2] and colour[1] > 0
        )
        phase = None
        for colour, _count in counter.most_common():
            phase = outline_phase(colour)
            if phase is not None:
                break
        ramp.append(phase)
    result["outline_phase_first_32"] = ramp[:32]
    result["outline_phase_advances"] = [
        (ramp[i] - ramp[i - 1]) % 32
        for i in range(1, len(ramp))
        if ramp[i] is not None and ramp[i - 1] is not None
    ][:32]

    if pose:
        resource = resource_for(visuals, character_id, slot)
        palette = load_palette(resource / "palette-bgr555.bin")
        exported = []
        for path in sorted(resource.glob("frame-*.png")):
            with Image.open(path) as image:
                exported.append((int(path.stem.split("-")[-1]),
                                list(image.tobytes()), image.size))
        width, height = SCREEN
        sequence = []
        for image in images:
            screen = screen_index_map(image, palette)
            best = None
            for index, frame, (fw, fh) in exported:
                for ox in range(max(0, x0 - 8), x1):
                    for oy in range(max(0, y0 - 8), y1):
                        if ox + fw > width or oy + fh > height:
                            continue
                        mismatch = 0
                        matched = 0
                        for index_of, value in enumerate(frame):
                            if value == 0:
                                continue
                            dx, dy = index_of % fw, index_of // fw
                            got = screen[(oy + dy) * width + ox + dx]
                            if got == -1:
                                continue
                            if got == value:
                                matched += 1
                            else:
                                mismatch += 1
                                if mismatch > 3:
                                    break
                        if mismatch == 0 and (best is None or matched > best[1]):
                            best = (index, matched)
                            break
                    if best is not None:
                        break
                if best is not None:
                    break
            sequence.append(best[0] if best else None)
        result["pose_sequence"] = sequence
        runs = []
        start = 0
        for index in range(1, len(sequence)):
            if sequence[index] != sequence[index - 1]:
                runs.append([sequence[index - 1], start, index - start])
                start = index
        if sequence:
            runs.append([sequence[-1], start, len(sequence) - start])
        result["pose_runs"] = runs
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", type=Path)
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("ORIG", "REMAKE"))
    parser.add_argument("--pattern", default="frame-*.png")
    parser.add_argument("--pose", action="store_true")
    parser.add_argument("--visuals", type=Path, default=DEFAULT_VISUALS)
    parser.add_argument("--character", type=int, default=1)
    parser.add_argument("--slot", type=int, default=0)
    parser.add_argument("--region", default="112,24,144,88")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    parts = [int(value) for value in args.region.split(",")]
    region = (parts[0], parts[1], parts[2], parts[3])

    if args.sweep:
        payload = measure(args.sweep, args.pattern, args.pose, args.visuals,
                          args.character, args.slot, region)
    elif args.compare:
        payload = {
            "original": measure(args.compare[0], args.pattern, args.pose,
                                args.visuals, args.character, args.slot, region),
            "remake": measure(args.compare[1], args.pattern, args.pose,
                              args.visuals, args.character, args.slot, region),
        }
        original = payload["original"]
        remake = payload["remake"]
        per_game = original["captured_frames_per_game_frame"]
        payload["summary"] = {
            "captured_frames_per_game_frame": per_game,
            "distinct_per_32_captured_frames": {
                "original": original["distinct_images"].get("32"),
                "remake": remake["distinct_images"].get("32"),
            },
            "distinct_per_32_game_frames": {
                "original": original["distinct_images"].get("32"),
                "remake": remake["distinct_images"].get("32"),
            },
            "note": "divide the captured-frame counts by "
                    "captured_frames_per_game_frame to compare in game frames",
        }
    else:
        parser.error("give --sweep or --compare")

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
