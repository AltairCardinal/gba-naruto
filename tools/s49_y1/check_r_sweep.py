#!/usr/bin/env python3
"""Y1 gate: how far can the player walk the unit selection roster?

The unit selection phase of S49 lets the player press ``R`` to move the
roster cursor to the next unit.  Before the palette bank leak was fixed the
remake ROM crashed on the ninth unit: every visited unit kept one of Butano's
sixteen hardware sprite palette banks alive.

The gate answers one yes/no question per run: *does the ROM reach the end of
the walk without landing on the Butano fatal error screen?*

Usage::

    python tools/s49_y1/check_r_sweep.py
    python tools/s49_y1/check_r_sweep.py --counts 1 2 3
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
X3 = REPO / "tools" / "s49_x3_boundary"
if str(X3) not in sys.path:
    sys.path.insert(0, str(X3))

import walkrec  # noqa: E402

# The private probe of this stream: the shared one under build/mgba-probe must
# not be overwritten (it is linked by every other stream).
walkrec.PRIVATE_PROBE = REPO / "build" / "mgba-probe-y1" / "mgba-probe.exe"
walkrec.WORK = REPO / "build" / "s49-y1"

REMAKE_ROM = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba"
)


def error_screen(path: pathlib.Path) -> dict[str, object] | None:
    """Describe the frame if it is the Butano fatal error screen.

    The Butano fatal error screen is a black frame with a red ``ERROR in ...``
    banner: the crash X3r recorded has a black fraction of 0.955 and 334 red
    pixels.  A plain fade to black has a black fraction of 1.0 and no red
    pixel at all, so the red pixels are what separates a crash from a fade.
    """

    from PIL import Image

    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        return None
    pixels = list(image.getdata())
    black = sum(1 for colour in pixels if colour == (0, 0, 0))
    red = sum(
        1
        for colour in pixels
        if colour[0] > 100 and colour[1] < 60 and colour[2] < 60
    )
    if black < 240 * 160 * 0.85 or red < 20:
        return None
    return {
        "frame": str(path),
        "black_fraction": round(black / (240 * 160), 4),
        "red_pixels": red,
    }


def crash_step(walk: pathlib.Path) -> dict[str, object] | None:
    """The first error screen of a walk, if there is one."""

    for path in walkrec.frames_of(walk):
        found = error_screen(path)
        if found is not None:
            return found
    return None


def expansion(count: int) -> list[str]:
    """The S49 walk prefix: two ``Down`` and sixteen ``A`` presses."""

    return ["Down", "Down"] + ["A"] * 16


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--counts",
        type=int,
        nargs="+",
        default=list(range(1, 10)),
        help="the number of R presses to try",
    )
    parser.add_argument("--rom", default=str(REMAKE_ROM))
    parser.add_argument("--prefix-a", type=int, default=16)
    parser.add_argument(
        "--tag",
        default="",
        help="a suffix for the walk directories (one per ROM under test)",
    )
    parser.add_argument(
        "--out",
        default=str(walkrec.WORK / "receipts" / "r-sweep.json"),
    )
    args = parser.parse_args(argv)

    rom = pathlib.Path(args.rom)
    if not rom.is_file():
        print("ERR missing ROM: %s" % rom, file=sys.stderr)
        return 2

    prefix = ["Down", "Down"] + ["A"] * args.prefix_a
    results = []
    for count in args.counts:
        keys = prefix + ["R"] * count
        label = "r%d" % count
        walk = walkrec.WORK / ("smoke-%s%s" % (label, args.tag))
        walkrec.record_walk(rom, keys, walk)
        frames = walkrec.frames_of(walk)
        crash = crash_step(walk)
        results.append(
            {
                "r_presses": count,
                "keys": len(keys),
                "frames": len(frames),
                "last_frame": frames[-1].name if frames else None,
                "crash": crash,
                "alive": crash is None,
            }
        )
        print(
            "R x%d: %s (%d frames)"
            % (count, "ALIVE" if crash is None else "CRASH", len(frames))
        )

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "identity": "y1_r_sweep",
                "rom": str(rom),
                "rom_sha256": walkrec.sha256_file(rom),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("receipt: %s" % out)
    return 0 if all(item["alive"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
