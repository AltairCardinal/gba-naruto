#!/usr/bin/env python3
"""Y1 gate: does the remake ROM survive a long run without the Butano error screen?

The walk is described by a key sequence; the probe then keeps the ROM running
for ``--frames`` frames and the final frame is dumped and checked.

The Butano fatal error screen is a black frame with a red ``ERROR in ...``
banner (the crash X3r recorded has a black fraction of 0.955 and 334 red
pixels).  A plain fade to black has a black fraction of 1.0 and no red pixel
at all, so the red pixels are what separates a crash from a fade.

Usage::

    python tools/s49_y1/check_rom_smoke_long.py --frames 4096 \
        --keys "Down,Down,A,A"
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
X3 = REPO / "tools" / "s49_x3_boundary"
if str(X3) not in sys.path:
    sys.path.insert(0, str(X3))

import walkrec  # noqa: E402

walkrec.PRIVATE_PROBE = REPO / "build" / "mgba-probe-y1" / "mgba-probe.exe"
walkrec.WORK = REPO / "build" / "s49-y1"

REMAKE_ROM = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba"
)


def load_frame(path: pathlib.Path):
    """Load the final frame.

    ``rawshot`` writes mGBA's own RGBA frame buffer (240x160x4 bytes, R in the
    low byte), not a PNG, so the buffer is turned into an image here.
    """

    from PIL import Image

    data = pathlib.Path(path).read_bytes()
    if len(data) >= 240 * 160 * 4:
        return Image.frombytes("RGBA", (240, 160), data[:240 * 160 * 4]).convert("RGB")
    return Image.open(path).convert("RGB")


def error_screen(path: pathlib.Path) -> dict[str, object] | None:
    image = load_frame(path)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default=str(REMAKE_ROM))
    parser.add_argument("--frames", type=int, default=4096)
    parser.add_argument("--keys", default="Down,Down,A,A")
    parser.add_argument("--label", default="long")
    args = parser.parse_args(argv)

    rom = pathlib.Path(args.rom)
    if not rom.is_file():
        print("ERR missing ROM: %s" % rom, file=sys.stderr)
        return 2
    keys = [token.strip() for token in args.keys.split(",") if token.strip()]

    out_dir = walkrec.WORK / ("long-" + args.label)
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / "final.png"
    environment = {
        "MGBA_BOOT_SEQUENCE_OUTPUT_DIR": str(out_dir),
        "MGBA_BOOT_SEQUENCE_DONE_MARKER": str(out_dir / "done.json"),
        "MGBA_BOOT_SEQUENCE_ROM_SHA256": walkrec.sha256_file(rom),
        "MGBA_BOOT_SEQUENCE_KEY_SEQUENCE": ",".join(keys),
        "MGBA_BOOT_SEQUENCE_ZERO_INPUT_FRAMES": "240",
        "MGBA_BOOT_SEQUENCE_SETTLE_FRAMES": "90",
        "MGBA_BOOT_SEQUENCE_HOLD_FRAMES": "4",
    }
    command = [
        sys.executable,
        str(walkrec.PROBE_CLIENT),
        "--rom", str(rom),
        "--exe", str(walkrec.PRIVATE_PROBE),
        "--timeout", "900",
        "--cmd", "script %s" % walkrec.BOOT_SCRIPT,
        "--cmd", "frames %d 0x000" % args.frames,
        "--cmd", "rawshot %s" % final,
        "--out", str(out_dir / "result.json"),
    ]
    completed = subprocess.run(
        command,
        env={**os.environ, **environment},
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        print("ERR probe failed: %s" % (completed.stderr or completed.stdout)[-600:])
        return 2
    crash = error_screen(final) if final.is_file() else None
    receipt = {
        "schema_version": 1,
        "identity": "y1_rom_smoke_long",
        "label": args.label,
        "rom": str(rom),
        "rom_sha256": walkrec.sha256_file(rom),
        "frames": args.frames,
        "keys": keys,
        "final_frame": str(final) if final.is_file() else None,
        "crash": crash,
    }
    receipt_path = out_dir / "receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("frames: %d, final: %s" % (args.frames, receipt["final_frame"]))
    if crash is None:
        print("RESULT: no error screen")
    else:
        print("RESULT: CRASH (%s)" % crash)
    print("receipt: %s" % receipt_path)
    return 0 if crash is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
