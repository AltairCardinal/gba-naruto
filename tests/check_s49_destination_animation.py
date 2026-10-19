"""Diagnose the four original ground-cursor shapes and their stable cycle.

This does not align or exclude pixels in the separate full-screen comparison.
The detected cycle offset is reported, never used to claim input-phase parity.
"""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from tools.butano.compare_frame_sequences import _capture, _sha256
from tools.butano.generate_battle_scenario_49_scenery import SOURCE_STATE, SOURCE_STATE_SHA256
from tools.extract_tileset import decode_4bpp_tiles
from tools.inspect_mgba_savestate import load_gba_state


def check(capture: Path, first_frame: int = 0) -> dict:
    _, frames = _capture(capture)
    source = Path(SOURCE_STATE)
    assert _sha256(source) == SOURCE_STATE_SHA256
    state = load_gba_state(source)
    tiles = decode_4bpp_tiles(state.read_memory(0x06017060, 64))
    raw_palette = state.read_memory(0x050003E0, 32)
    palette = []
    for i in range(16):
        rgb5 = int.from_bytes(raw_palette[2 * i:2 * i + 2], "little")
        channels = [(rgb5 >> shift) & 31 for shift in (0, 5, 10)]
        palette.append(tuple((v << 3) | (v >> 2) for v in channels))
    shapes = []
    for distance in range(4):
        shape = []
        tile = tiles[distance == 3]
        for vertical in range(2):
            for horizontal in range(2):
                left = 168 + distance if horizontal else 144 - distance
                top = 80 + distance if vertical else 72 - distance
                for y in range(8):
                    for x in range(8):
                        index = tile[(7 - y if vertical else y) * 8 + (7 - x if horizontal else x)]
                        if index:
                            shape.append((left + x, top + y, palette[index]))
        shapes.append(shape)
    samples = []
    for frame in frames[first_frame:]:
        with Image.open(frame) as image:
            pixels = image.convert("RGB")
            matches = [i for i, shape in enumerate(shapes)
                       if all(pixels.getpixel((x, y)) == color for x, y, color in shape)]
        samples.append(matches[0] if len(matches) == 1 else None)
    cycle = [3] * 4 + [2] * 5 + [1] * 7 + [0] * 15 + [1] * 8 + [2] * 5
    offsets = [offset for offset in range(44)
               if all(sample == cycle[(index + offset) % 44] for index, sample in enumerate(samples))]
    return {
        "capture": str(capture), "source_state_sha256": _sha256(source),
        "scope": "104 nontransparent corner pixels; shape/cadence only, not full-screen or initial-phase parity",
        "first_frame": first_frame, "checked_frames": len(samples),
        "shape_failures": [first_frame + i for i, value in enumerate(samples) if value is None],
        "distances": samples, "stable_cycle_offsets": offsets,
        "frame_sha256": [_sha256(f) for f in frames],
        "passed": len(samples) >= 44 and None not in samples and len(offsets) == 1,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--first-frame", type=int, default=0)
    args = parser.parse_args()
    result = check(args.capture, args.first_frame)
    print(json.dumps(result, indent=2))
    raise SystemExit(not result["passed"])
