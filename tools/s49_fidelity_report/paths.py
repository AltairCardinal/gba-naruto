"""Repository paths and the constants the judgment bench shares.

Every path is derived from the location of this file so the bench keeps
working through the directory junction the repository is reached by.
"""

from __future__ import annotations

import os
import pathlib

# os.path.abspath, not Path.resolve(): the repository is reached through a
# directory junction (D:\\Github\\gba-naruto -> D:\\Shell\\Github\\gba-naruto) and
# resolving it would report the junction target instead of the path the user
# actually invoked.
HERE = pathlib.Path(os.path.abspath(__file__)).parent
REPO = HERE.parent.parent

TOOLS = REPO / "tools"
PROBE_CLIENT = TOOLS / "mgba_probe" / "probe_client.py"
PROBE_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
OVERLAY_ALIGN = TOOLS / "s49_overlay_align"
RULE_PROBE = TOOLS / "s49_rule_probe"

DEFAULT_BIOS = REPO / "recomp" / "bios" / "gba_bios.bin"

# --- battlefield geometry --------------------------------------------------
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 160
FIELD_AREA = (0, 0, 240, 128)

# --- classifier constants (calibration documented in the report) ------------
BLOCK = 16
STRUCT_TOLERANCE = 8
STRUCT_THRESHOLD = 0.70
OCCUPANCY_THRESHOLD = 0.40
ROW_SPREAD_THRESHOLD = 0.85
HIGH_CONFIDENCE_MARGIN = 0.20
MIN_CONFIDENCE_MARGIN = 0.05
DISSENT_CONFIDENCE_MARGIN = 0.10

# --- the black transition --------------------------------------------------
# A frame whose non-black pixel fraction is below this is a fade frame, not a
# battle frame.  Measured on the 2026-10-23 baseline: the original's two
# fade frames sit at 0.79 % and 0.00 %, every other frame at >= 85 %.
BLACK_NON_BLACK_LIMIT = 0.05

# --- the outline wave ------------------------------------------------------
# The 32 phase outline wave of the original's unit outline (5 bit green).
OUTLINE_WAVE = (
    19, 17, 15, 13, 11, 9, 7, 5, 3, 1, 1, 3, 5, 7, 9, 11,
    13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 31, 29, 27, 25, 23, 21,
)
# The two phases where the quantised wave repeats its shade.  A frame pair
# may only be identical there.
FLAT_SPOT_SHADES = frozenset({1, 31})
FLAT_SPOT_PHASES = ((9, 10), (25, 26))
OUTLINE_REGION = (112, 24, 144, 88)
