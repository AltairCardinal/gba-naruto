"""Scratch: is the remake's title drawn at the wrong place?

Answers one question: if the title's sprites were placed with the Butano
coordinates the runtime actually passes, would the title's ink land on the
remake's screen at the spot the probe finds?

The test takes the original's own title art out of an original frame, puts it
where the runtime's Butano coordinates put it (the screen centre is added to
them), and compares that with the remake's pixels.

Usage:
    python tools/s49_v3_dialogue/verify_title_offset.py <original-dir> <remake-dir>
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

GREYS = {(33, 33, 33), (107, 107, 107), (181, 181, 181), (255, 255, 255)}

# The original's title art, measured from the original's own frames.
ART = {
    "kai": (41, 49, 100, 111),
    "shi": (135, 42, 205, 112),
}
# The Butano positions the runtime passes (battle_runtime_scene.cpp, the
# battle_opening_title_view class).
BUTANO = {
    "kai": (73, 81),
    "shi_top": (167, 74),
    "shi_right": (215, 74),
    "shi_bottom": (167, 122),
    "shi_corner": (215, 122),
}
# The screen centre of the 240x160 screen.
CENTRE = (120, 80)


def greys(image: Image.Image, box) -> int:
    return sum(1 for pixel in image.convert("RGB").crop(box).getdata()
               if pixel in GREYS)


def main() -> int:
    original_dir = pathlib.Path(sys.argv[1])
    remake_dir = pathlib.Path(sys.argv[2])
    original = Image.open(original_dir / "step-0205-in.png").convert("RGB")
    remake = Image.open(remake_dir / "step-0147-in.png").convert("RGB")

    # The art as the original shows it.
    print("original title art:")
    for name, box in ART.items():
        print(f"  {name:<6} screen box {box}  greys={greys(original, box)}")

    # Where the runtime puts the sprites: the Butano position plus the centre.
    print("\nwhere the runtime puts the kai sprite:")
    x, y = BUTANO["kai"]
    print(f"  butano ({x}, {y}) -> screen ({x + CENTRE[0]}, {y + CENTRE[1]})")
    print(f"  should be at screen {ART['kai'][:2]} .. "
          f"({ART['kai'][0] + 63}, {ART['kai'][1] + 63})")

    # The whole title, placed the way the runtime places it.
    shifted = Image.new("RGB", (240, 160), (0, 0, 0))
    placed = {
        "kai": (BUTANO["kai"][0] + CENTRE[0] - 32,
                BUTANO["kai"][1] + CENTRE[1] - 32),
        "shi_top": (BUTANO["shi_top"][0] + CENTRE[0] - 32,
                    BUTANO["shi_top"][1] + CENTRE[1] - 32),
        "shi_right": (BUTANO["shi_right"][0] + CENTRE[0] - 16,
                      BUTANO["shi_right"][1] + CENTRE[1] - 32),
        "shi_bottom": (BUTANO["shi_bottom"][0] + CENTRE[0] - 32,
                       BUTANO["shi_bottom"][1] + CENTRE[1] - 16),
        "shi_corner": (BUTANO["shi_corner"][0] + CENTRE[0] - 16,
                       BUTANO["shi_corner"][1] + CENTRE[1] - 16),
    }
    for name, (left, top) in placed.items():
        box = ART["kai"] if name == "kai" else ART["shi"]
        art = original.crop(box)
        shifted.paste(art, (left, top))
    shifted.save("build/s49-v3/title-as-placed.png")

    print("\nthe art placed the way the runtime places it:")
    print(f"  greys on the whole screen: {greys(shifted, (0, 0, 240, 160))}")
    print(f"  greys at the original's title box: "
          f"{greys(shifted, (41, 42, 226, 125))}")
    print(f"  greys in the remake's own frame at the original's title box: "
          f"{greys(remake, (41, 42, 226, 125))}")
    print("\n-> build/s49-v3/title-as-placed.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
