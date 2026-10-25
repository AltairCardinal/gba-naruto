#!/usr/bin/env python3
"""Normalise the settlement assets' JSON sidecars to the project's one-line form.

The project's regular_bg sidecars are a single line of compact JSON; the
authoring tools wrote them pretty-printed, which made the diff noisier than
it needed to be.  This restores the project's convention.

Usage:
    python tools/s49_w19b/normalize_sidecars.py --graphics <dir>
"""

from __future__ import annotations

import argparse
import io
import os
import sys


LINE = '{"type":"regular_bg","bpp_mode":"bpp_8","colors_count":256}\n'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graphics", required=True)
    args = parser.parse_args()

    names = ["scenario_41_postbattle_bg", "scenario_41_postbattle_ui"]
    names += ["scenario_41_postbattle_dialogue_page_%d" % page
              for page in range(1, 8)]
    for name in names:
        path = os.path.join(args.graphics, name + ".json")
        if not os.path.exists(path):
            continue
        with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(LINE)
        print("normalised " + path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
