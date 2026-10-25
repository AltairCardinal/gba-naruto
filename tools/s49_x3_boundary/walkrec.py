#!/usr/bin/env python3
"""Walk recording helpers for the X3 boundary checks.

The helpers drive the headless mGBA probe with the remake tree's own boot
input sequence Lua script, so a walk is described by nothing but a list of
key presses.  Two things are needed on top of the recording itself:

* :func:`error_screen` -- the Butano fatal error screen (a black frame with
  the red ``ERROR in ...`` banner).  A walk that ends on that frame crashed;
  the assertion ``BN_ASSERT`` failures and the palette bank exhaustion both
  land there.
* :func:`status_bar_rows` -- the unit name / counter row of the status bar,
  the region the B5 pixel criterion is about.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
BOOT_SCRIPT = REMAKE_ROOT / "tools" / "butano" / "mgba_boot_input_sequence.lua"
PROBE_CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"
PRIVATE_PROBE = REPO / "build" / "mgba-probe-x3r" / "mgba-probe.exe"

WORK = REPO / "build" / "s49-x3-boundary"

#: The status bar band of a 240x160 GBA frame.
STATUS_BAR = (0, 144, 240, 160)

#: The unit name cell of the status bar.  The original draws the name in
#: columns 0..48, the remake in columns 0..52.
ORIGINAL_NAME_CELL = (0, 48)
REMAKE_NAME_CELL = (0, 52)

#: The far right counter column (the original's chakra point counter).
COUNTER_CELL = (216, 240)

#: The colours of the remake's and the original's status bar inks.
END_INK = (231, 24, 0)
STANDBY_INK = (115, 33, 255)


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def record_walk(
    rom: pathlib.Path,
    key_sequence: list[str],
    out_dir: pathlib.Path,
    *,
    zero_input_frames: int = 240,
    settle_frames: int = 90,
    hold_frames: int = 4,
    timeout: int = 900,
    frames: int = 6000,
) -> pathlib.Path:
    """Record one walk and return the directory that holds the frames."""

    rom = pathlib.Path(rom)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    done_marker = out_dir / "done.json"
    if done_marker.is_file():
        return out_dir
    environment = {
        "MGBA_BOOT_SEQUENCE_OUTPUT_DIR": str(out_dir),
        "MGBA_BOOT_SEQUENCE_DONE_MARKER": str(done_marker),
        "MGBA_BOOT_SEQUENCE_ROM_SHA256": sha256_file(rom),
        "MGBA_BOOT_SEQUENCE_KEY_SEQUENCE": ",".join(key_sequence),
        "MGBA_BOOT_SEQUENCE_ZERO_INPUT_FRAMES": str(zero_input_frames),
        "MGBA_BOOT_SEQUENCE_SETTLE_FRAMES": str(settle_frames),
        "MGBA_BOOT_SEQUENCE_HOLD_FRAMES": str(hold_frames),
    }
    command = [
        sys.executable,
        str(PROBE_CLIENT),
        "--rom", str(rom),
        "--exe", str(PRIVATE_PROBE),
        "--timeout", str(timeout),
        "--cmd", "script %s" % BOOT_SCRIPT,
        "--cmd", "frames %d 0x000" % frames,
        "--out", str(out_dir / "result.json"),
    ]
    completed = subprocess.run(
        command,
        env={**os.environ, **environment},
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not done_marker.is_file():
        raise RuntimeError(
            "walk failed (%s): %s"
            % (out_dir.name, (completed.stderr or completed.stdout)[-800:])
        )
    return out_dir


def frames_of(walk: pathlib.Path) -> list[pathlib.Path]:
    return sorted(pathlib.Path(walk).glob("step-*.png"))


def error_screen(path: pathlib.Path) -> dict[str, Any] | None:
    """Describe the frame if it is the Butano fatal error screen."""

    from PIL import Image

    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        return None
    pixels = list(image.getdata())
    black = sum(1 for colour in pixels if colour == (0, 0, 0))
    if black < 240 * 160 * 0.85:
        return None
    return {
        "frame": str(path),
        "black_fraction": round(black / (240 * 160), 4),
    }


def crash_step(walk: pathlib.Path) -> dict[str, Any] | None:
    """The first error screen of a walk, if there is one."""

    for path in frames_of(walk):
        found = error_screen(path)
        if found is not None:
            return found
    return None


def status_bar_rows(
    walk: pathlib.Path,
    name_cell: tuple[int, int],
) -> list[dict[str, Any]]:
    """One row per recorded frame: the name cell signature and the counter."""

    from PIL import Image

    rows: list[dict[str, Any]] = []
    for path in frames_of(walk):
        image = Image.open(path).convert("RGB")
        pixels = image.load()
        x0, y0, x1, y1 = STATUS_BAR
        cell = image.crop((name_cell[0], y0, name_cell[1], y1))
        background = pixels[name_cell[0], y0]
        ink = 0
        for x in range(name_cell[0], name_cell[1]):
            for y in range(y0, y1):
                if pixels[x, y] != background:
                    ink += 1
        counter = image.crop((COUNTER_CELL[0], y0, COUNTER_CELL[1], y1))
        rows.append(
            {
                "step": path.stem,
                "name_signature": hashlib.sha256(cell.tobytes()).hexdigest(),
                "name_ink_pixels": ink,
                "counter_signature": hashlib.sha256(
                    counter.tobytes()
                ).hexdigest(),
            }
        )
    return rows
