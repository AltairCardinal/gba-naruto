#!/usr/bin/env python3
"""Print the pixel signature of captured frames.

The driver's screen classifier is built on these numbers, so they have to be
measured on real frames instead of guessed.  Run it on any set of PNGs to see
which screen each one shows.

Usage::

    python tools/s49_victory_capture/measure_frames.py \\
        build/s49-report/capture-original/step-24-A.png \\
        build/s49-victory-capture/aim5/aim5.png
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from PIL import Image  # noqa: E402

import battle_obs  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    if not paths:
        print(__doc__)
        return 2
    header = (f"{'frame':<44} {'level?':<7} {'menu':<9} {'border':>6} "
              f"{'dark':>5} {'panel':>6} {'dlg':>5} {'err':>5} {'cfm':>5}")
    print(header)
    print("-" * len(header))
    for item in paths:
        path = pathlib.Path(item)
        if not path.exists():
            print(f"{path}  MISSING")
            continue
        image = Image.open(path).convert("RGB")
        sig = battle_obs.signature(image)
        for level in (3, 4):
            name = battle_obs.classify(image, level)
            print(f"{path.name:<44} {level:<7} {name:<9} "
                  f"{sig['border_rows']:>6} {sig['menu_dark']:>5} "
                  f"{sig['panel_light']:>6} {sig['dialogue_light']:>5} "
                  f"{sig['error_light']:>5} {sig['confirm_light']:>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
