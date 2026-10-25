"""The original's dialogue timeline: the typewriter and the per-line wait.

The capture -> GBA frame mapping comes from the recorder's own lua script
(``tools/s49_pairing/lua/record_walk.lua``):

* the base capture is the frame ``zero_input_frames`` (90),
* beat ``b`` presses the confirm key at frame ``90 + 94 * (b - 1)``,
* the key is released 4 frames later, which starts the settle,
* the 22 inner captures of beat ``b`` are at ``press + 8 .. press + 90``,
  4 frames apart,
* the beat capture is at ``press + 94``, which is the frame the **next**
  beat's key is pressed.

For every capture it reports the frame, the ink of every text row of the
dialogue box and whether the advance icon is on screen.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

INK = (57, 66, 57)
BOX_TOP = 103
BOX_BOTTOM = 153
# The advance icon: the bottom right corner of the dialogue box.
ICON_BOX = (180, 136, 240, 160)
ICON_DARK_LIMIT = 160

ZERO_INPUT_FRAMES = 90
HOLD_FRAMES = 4
SETTLE_FRAMES = 90
BEAT_FRAMES = HOLD_FRAMES + SETTLE_FRAMES
INNER_CAPTURES = BEAT_FRAMES // 4 - 1


def capture_frame(index: int) -> int:
    """The GBA frame a capture index stands for."""
    if index == 0:
        return ZERO_INPUT_FRAMES
    beat = (index - 1) // (INNER_CAPTURES + 1) + 1
    inner = (index - 1) % (INNER_CAPTURES + 1)
    press = ZERO_INPUT_FRAMES + BEAT_FRAMES * (beat - 1)
    if inner < INNER_CAPTURES:
        return press + HOLD_FRAMES + 4 + 4 * inner
    return press + BEAT_FRAMES


def press_frames(count: int) -> dict[int, int]:
    """The frame every beat's confirm key is pressed on."""
    return {ZERO_INPUT_FRAMES + BEAT_FRAMES * (beat - 1): beat
            for beat in range(1, count + 1)}


def open_frame(index: int) -> pathlib.Path:
    for suffix in ("in", "beat", "base"):
        png = index and None
    return None


def find_png(src: pathlib.Path, index: int) -> pathlib.Path | None:
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:04d}-{suffix}.png"
        if png.exists():
            return png
    return None


def text_bands(image: Image.Image) -> list[tuple[int, int, int, int]]:
    """The (top, bottom, first column, last column) of every text row band."""
    pixels = image.load()
    rows = []
    for y in range(BOX_TOP, min(BOX_BOTTOM + 1, image.height)):
        columns = [x for x in range(image.width) if pixels[x, y] == INK]
        rows.append((y, columns))
    bands = []
    for top, (y, columns) in enumerate(rows):
        if not columns:
            continue
        if bands and bands[-1][1] == y - 1:
            bands[-1] = (bands[-1][0], y, bands[-1][2], columns)
        else:
            bands.append((y, y, columns, columns))
    out = []
    for top, bottom, first, last in bands:
        out.append((top, bottom, first[0], last[-1], len(first)))
    return out


def icon_dark(image: Image.Image) -> int:
    pixels = image.load()
    count = 0
    for y in range(ICON_BOX[1], min(ICON_BOX[3], image.height)):
        for x in range(ICON_BOX[0], ICON_BOX[2]):
            if max(pixels[x, y]) < ICON_DARK_LIMIT:
                count += 1
    return count


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    first = int(sys.argv[2])
    last = int(sys.argv[3])
    presses = press_frames(64)
    for index in range(first, last + 1):
        png = find_png(src, index)
        if png is None:
            continue
        with Image.open(png) as handle:
            image = handle.convert("RGB")
        frame = capture_frame(index)
        mark = ""
        if frame in presses:
            mark = f" PRESS(beat {presses[frame]})"
        bands = text_bands(image)
        parts = [f"y{top}-{bottom}:{count}c[{first}..{last}]"
                 for top, bottom, first, last, count in bands]
        print(f"{index:04d} f={frame:5d} icon={icon_dark(image):4d}{mark} "
              + " ".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
