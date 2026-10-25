#!/usr/bin/env python3
"""Probe the original's GPU state while its star shaped black mask is up.

Why this tool exists
--------------------
The original's black field is not a brightness ramp: it is a four pointed
star shaped window that rotates and shrinks (stream Y2's finding).  To
reproduce it in the remake we have to know *how* the original draws it, and
the answer is in the original's own GPU state at one of the fade frames:

  * DISPCNT / BGCNTx  -- is the mask a background layer or sprites?
  * OAM               -- how many sprites, which shapes, which rotation and
                         which affine scale?

The experiment is self checking: the tool replays the *exact* key schedule
that produced the project's own frame capture and compares its own
screenshot of the target frame with the stored PNG.  Only if the two are
byte identical does it trust the register dump.

Usage::

    python tools/s49_starfield/probe_original_mask.py \
        --frames build/s49-blackfade/original-entry-v2/frames \
        --out build/s49-starfield/original-mask-gpu.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
VICTORY = REPO / "tools" / "s49_victory_capture"
if str(VICTORY) not in sys.path:
    sys.path.insert(0, str(VICTORY))

import probe as probe_module  # noqa: E402

DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")
DEFAULT_EXE = REPO / "build" / "mgba-probe-z2" / "mgba-probe.exe"

DISPCNT = 0x04000000
REG_SIZE = 0x60
OAM = 0x06000000
OAM_SIZE = 0x400        # 128 sprites x 8 bytes

# The key schedule of tools/s49_blackfade/capture_frames.lua for
# "A*20", hold 4, settle 90, zero 0:
#   the key is added inside the frame callback of frame 1 + (k-1)*94 and
#   released inside the callback of frame 5 + (k-1)*94, so the button is
#   held while the frames 2..5, 96..99, 190..193, ... are rendered.
KEY_STEP = 94
KEY_HOLD = 4
KEY_GAP = 90

# GBA sprite sizes, indexed by the size bits (attr1 bits 14-15).
OBJ_SIZES = {
    0: (8, 8), 1: (16, 16), 2: (32, 32), 3: (64, 64),
    4: (16, 8), 5: (32, 8), 6: (32, 16), 7: (32, 32),
    8: (16, 32), 9: (32, 64),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_registers(data: bytes) -> dict:
    def u16(offset: int) -> int:
        return data[offset] | (data[offset + 1] << 8)

    dispcnt = u16(0)
    bgs = []
    for index in range(4):
        value = u16(8 + index * 2)
        bgs.append({
            "bg": index,
            "bgcnt": value,
            "hex": f"0x{value:04X}",
            "priority": value & 3,
            "char_base_block": (value >> 2) & 3,
            "screen_base_block": (value >> 8) & 0x1F,
            "size": (value >> 14) & 3,
            "bpp": 8 if (value >> 7) & 1 else 4,
            "overflow": bool((value >> 14) & 1),
        })
    return {
        "dispcnt": dispcnt,
        "dispcnt_hex": f"0x{dispcnt:04X}",
        "mode": (dispcnt >> 14) & 3,
        "obj_enable": bool((dispcnt >> 4) & 1),
        "obj_1d_mapping": bool((dispcnt >> 6) & 1),
        "obj_2d_mapping": bool((dispcnt >> 5) & 1),
        "forced_blank": bool((dispcnt >> 7) & 1),
        "bgs": bgs,
    }


def decode_oam(data: bytes) -> list[dict]:
    sprites = []
    for index in range(128):
        offset = index * 8
        attr0, attr1, attr2 = struct.unpack_from("<HHH", data, offset)
        y = attr0 & 0x1FF
        rotation = (attr0 >> 9) & 0x1F
        double_size = bool((attr0 >> 15) & 1)
        disabled = bool((attr0 >> 9) & 1) and False  # bit 9 is the rotation
        # A disabled sprite has the "disable" bit (attr0 bit 9) cleared in
        # the *double size* configuration; in the normal configuration the
        # sprite is disabled when attr0 == 0 and attr1 == 0 and attr2 == 0.
        x = attr1 & 0x1FF
        size_bits = (attr1 >> 14) & 3
        width, height = OBJ_SIZES.get(size_bits, (0, 0))
        tile = attr2 & 0x3FF
        bank = (attr2 >> 10) & 3
        colour_mode = (attr2 >> 12) & 1
        priority = (attr2 >> 14) & 3
        if attr0 == 0 and attr1 == 0 and attr2 == 0:
            continue
        sprites.append({
            "index": index,
            "attr0": attr0,
            "attr1": attr1,
            "attr2": attr2,
            "x": x,
            "y": y,
            "rotation_param": rotation,
            "double_size": double_size,
            "size_bits": size_bits,
            "width": width,
            "height": height,
            "tile": tile,
            "bank": bank,
            "colour_mode": "16/16" if colour_mode else "256/1",
            "priority": priority,
        })
    return sprites


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", required=True,
                        help="directory with the project's frame-XXXXX.png capture")
    parser.add_argument("--out", required=True)
    parser.add_argument("--target", type=int, default=1013)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    args = parser.parse_args(argv)

    frames_dir = pathlib.Path(args.frames)
    reference = frames_dir / f"frame-{args.target:05d}.png"
    if not reference.exists():
        raise SystemExit(f"reference frame missing: {reference}")

    mask_a = probe_module.key_mask(["A"])

    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        # frame 1 without any key
        probe.frames(1, 0)
        frame = 1
        key_index = 1
        while frame + KEY_HOLD + KEY_GAP <= args.target:
            probe.frames(KEY_HOLD, mask_a)
            frame += KEY_HOLD
            probe.frames(KEY_GAP, 0)
            frame += KEY_GAP
            key_index += 1
        remaining = args.target - frame
        if remaining > 0:
            probe.frames(remaining, 0)
            frame += remaining
        shot_path = pathlib.Path(args.out).with_suffix(".raw")
        shot_path.parent.mkdir(parents=True, exist_ok=True)
        probe.shot(str(shot_path))
        registers = probe.dump(DISPCNT, REG_SIZE)
        oam = probe.dump(OAM, OAM_SIZE)

    from PIL import Image
    captured = Image.open(shot_path).convert("RGB")
    stored = Image.open(reference).convert("RGB")
    same = list(captured.get_flattened_data()) == list(stored.get_flattened_data())

    report = {
        "schema": "konoha.s49-original-mask-gpu.v1",
        "target_frame": args.target,
        "keys_pressed": key_index - 1,
        "screenshot_matches_reference": same,
        "screenshot_sha256": sha256_bytes(shot_path.read_bytes()),
        "reference_sha256": sha256_bytes(reference.read_bytes()),
        "registers": decode_registers(registers),
        "sprites": decode_oam(oam),
    }
    out = pathlib.Path(args.out)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")

    registers_out = report["registers"]
    print("DISPCNT", registers_out["dispcnt_hex"],
          "mode", registers_out["mode"],
          "obj", registers_out["obj_enable"])
    for bg in registers_out["bgs"]:
        print("  BG%d %s prio=%d char=%d screen=%d bpp=%d"
              % (bg["bg"], bg["hex"], bg["priority"],
                 bg["char_base_block"], bg["screen_base_block"], bg["bpp"]))
    print("sprites in use:", len(report["sprites"]))
    for sprite in report["sprites"]:
        print("  #%3d x=%3d y=%3d %2dx%2d rot=%2d dbl=%s tile=%4d bank=%d prio=%d"
              % (sprite["index"], sprite["x"], sprite["y"], sprite["width"],
                 sprite["height"], sprite["rotation_param"],
                 sprite["double_size"], sprite["tile"], sprite["bank"],
                 sprite["priority"]))
    print("screenshot matches reference:", same)
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
