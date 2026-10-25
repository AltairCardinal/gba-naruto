#!/usr/bin/env python3
"""Step 3 of the S49 packaging pipeline: the ROM runs, and the title renders.

What it does
------------
1. boots the remake ROM from power-on with the headless mGBA probe,
2. runs ``--frames`` GBA frames (4096 by default), pressing ``A`` once after
   the title screen appeared,
3. takes four screenshots -- the blank boot screen, the title screen, the
   frame after the key press and the last frame,
4. decides whether the ROM *ran* and whether the *title screen* rendered.

The success criterion
---------------------
``ok`` is true only when **all** of the following hold:

* the probe accepted every command (no ``ERR`` line, no broken pipe),
* the probe's output carries no crash marker (``illegal``, ``crash``,
  ``segmentation``, ``assert``),
* the emulator is still responsive after the last frame (a memory read works),
* the title frame exists, is 240x160 and is **not** the blank boot screen:
  it differs from the boot frame, it has at least ``--min-non-black``
  non-black pixels and at least ``--min-colors`` distinct colours,
* the title band carries **text**: at least ``--min-glyphs`` separated ink
  components and at least ``--min-ink-pixels`` ink pixels.  The remake's title
  screen carries Chinese characters only, so a line of separated glyphs is the
  machine signal for "the Chinese text rendered",
* the game **reacted to a key press**: the frame after the ``A`` press differs
  from the title frame.  The title screen waits for the player, so "the screen
  does not change on its own" is *not* a crash -- "the game does not react"
  is,
* the title frame differs from the pinned reference by at most
  ``--max-reference-diff`` of its pixels (skipped on the first run, which is
  the run that pins the reference).

Every number is written to ``smoke.json`` so a reader can re-derive the
verdict instead of trusting it.

Usage::

    python tools/s49_package/smoke_rom.py \
        --rom "D:\\Shell\\Github\\gba-naruto-butano\\butano-sequel\\butano-sequel.gba" \
        --out build/s49-package/evidence/smoke
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import threading

# os.path.abspath, not Path.resolve(): the repository is reached through
# a directory junction (D:\Github\gba-naruto -> D:\Shell\Github\gba-naruto)
# and resolving it would report the junction target instead of the path the
# user actually invoked.
HERE = pathlib.Path(os.path.abspath(__file__)).parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_victory_capture"))

from probe import Probe, ProbeError  # noqa: E402  (read-only reuse)

# The probe is a **private** build of this stream.  The shared
# ``build/mgba-probe/mgba-probe.exe`` belongs to another stream and must not be
# overwritten (LNK1104); it is also an older revision whose ``framedump``
# argument order differs, so it is only the last resort.
DEFAULT_PROBE = REPO / "build" / "mgba-probe-z4" / "mgba-probe.exe"
FALLBACK_PROBE = REPO / "build" / "mgba-probe-x4r" / "mgba-probe.exe"
LAST_RESORT_PROBE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"

SCREEN_WIDTH = 240
SCREEN_HEIGHT = 160
# The remake draws its Chinese title screen from about frame 30 on; before
# that the screen is blank white (measured on the 2026-10-24 build).
TITLE_FRAME = 30
BOOT_FRAME = 5
# The key press that proves the game is alive, and the settle after it.
PRESS_FRAMES = 4
SETTLE_FRAMES = 90
KEY_A = 0x001
CRASH_MARKERS = ("illegal", "crash", "segmentation", "assert")


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rgb(path: pathlib.Path) -> list[tuple[int, int, int]]:
    from PIL import Image

    with Image.open(path) as image:
        return list(image.convert("RGB").get_flattened_data())


def screen_stats(pixels: list[tuple[int, int, int]]) -> dict:
    total = len(pixels)
    non_black = sum(1 for r, g, b in pixels if r > 8 or g > 8 or b > 8)
    colors = len(set(pixels))
    return {
        "pixels": total,
        "non_black": non_black,
        "non_black_fraction": round(non_black / total, 6) if total else 0.0,
        "distinct_colors": colors,
    }


def differing_pixels(left: list[tuple[int, int, int]],
                     right: list[tuple[int, int, int]]) -> int:
    if len(left) != len(right):
        return max(len(left), len(right))
    return sum(1 for a, b in zip(left, right) if a != b)


def ink_components(pixels: list[tuple[int, int, int]], width: int,
                   rows: int) -> dict:
    """Count the separated ink blobs of the top ``rows`` lines.

    The background is the most common colour of the band, everything else is
    ink.  A line of Chinese characters shows up as several small, separated
    blobs; a solid rectangle shows up as one.
    """
    band = pixels[:width * rows]
    if not band:
        return {"band_rows": rows, "components": 0, "ink_pixels": 0,
                "background": None}
    counts: dict[tuple[int, int, int], int] = {}
    for pixel in band:
        counts[pixel] = counts.get(pixel, 0) + 1
    background = max(counts.items(), key=lambda item: item[1])[0]
    ink = [[band[y * width + x] != background for x in range(width)]
           for y in range(rows)]
    seen = [[False] * width for _ in range(rows)]
    components = 0
    ink_pixels = 0
    for y in range(rows):
        for x in range(width):
            if not ink[y][x] or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            size = 0
            while stack:
                cx, cy = stack.pop()
                size += 1
                for nx, ny in ((cx - 1, cy), (cx + 1, cy),
                               (cx, cy - 1), (cx, cy + 1)):
                    if not (0 <= nx < width and 0 <= ny < rows):
                        continue
                    if ink[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if size >= 2:
                components += 1
                ink_pixels += size
    return {"band_rows": rows, "components": components,
            "ink_pixels": ink_pixels, "background": list(background)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--frames", type=int, default=4096)
    parser.add_argument("--probe", type=pathlib.Path, default=None)
    parser.add_argument("--title-frame", type=int, default=TITLE_FRAME)
    parser.add_argument("--boot-frame", type=int, default=BOOT_FRAME)
    parser.add_argument("--band-rows", type=int, default=16)
    parser.add_argument("--min-non-black", type=float, default=0.20,
                        help="minimum share of non-black pixels of the title")
    parser.add_argument("--min-colors", type=int, default=8)
    parser.add_argument("--min-glyphs", type=int, default=4)
    parser.add_argument("--min-ink-pixels", type=int, default=400)
    parser.add_argument("--probe-timeout", type=float, default=180.0,
                        help="seconds the boot may take before the run is "
                             "called a hang (a ROM that locks up never "
                             "answers)")
    parser.add_argument("--reference", type=pathlib.Path, default=None,
                        help="a pinned reference title frame to compare against")
    parser.add_argument("--max-reference-diff", type=float, default=0.10,
                        help="maximum share of pixels that may differ from "
                             "the reference")
    parser.add_argument("--pin-reference", type=pathlib.Path, default=None,
                        help="write the title frame here as the reference")
    args = parser.parse_args()

    rom = args.rom
    if not rom.is_file():
        print(f"ERR rom missing: {rom}", file=sys.stderr)
        return 2
    probe_exe = args.probe
    if probe_exe is None:
        for candidate in (DEFAULT_PROBE, FALLBACK_PROBE, LAST_RESORT_PROBE):
            if candidate.is_file():
                probe_exe = candidate
                break
        else:
            probe_exe = DEFAULT_PROBE
    if not probe_exe.is_file():
        print(f"ERR probe missing: {probe_exe}", file=sys.stderr)
        return 2

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    shots = {
        "boot": out / "frame-boot.png",
        "title": out / "frame-title.png",
        "after_input": out / "frame-after-input.png",
        "last": out / "frame-last.png",
    }
    for path in shots.values():
        if path.exists():
            path.unlink()

    problems: list[str] = []
    frames_run = 0
    stderr_tail: list[str] = []
    stdout_tail: list[str] = []
    responsive = False
    holder: dict = {}

    def drive() -> None:
        """Run the boot in the probe (on its own thread, so it can be cut off)."""
        nonlocal frames_run, responsive, stderr_tail, stdout_tail
        device = Probe(rom, exe=probe_exe, timeout=30.0)
        holder["device"] = device
        try:
            device.start()
            device.frames(args.boot_frame)
            frames_run += args.boot_frame
            stdout_tail += device.shot(shots["boot"])

            device.frames(args.title_frame - args.boot_frame)
            frames_run = args.title_frame
            stdout_tail += device.shot(shots["title"])

            # One key press proves the game is alive: the title screen waits
            # for the player, so only the reaction to a key can tell a waiting
            # screen from a crashed one.
            device.frames(PRESS_FRAMES, KEY_A)
            frames_run += PRESS_FRAMES
            device.frames(SETTLE_FRAMES)
            frames_run += SETTLE_FRAMES
            stdout_tail += device.shot(shots["after_input"])

            remaining = args.frames - frames_run
            if remaining > 0:
                device.frames(remaining)
                frames_run = args.frames
            stdout_tail += device.shot(shots["last"])

            # The emulator is still alive and answering after the last frame.
            device.dump(0x04000000, 0x40)
            responsive = True
            stderr_tail = device.stderr[-8:]
        except ProbeError as error:
            holder["error"] = str(error)
        finally:
            device.close()

    worker = threading.Thread(target=drive, daemon=True)
    worker.start()
    worker.join(args.probe_timeout)
    if worker.is_alive():
        # The emulator did not come back.  A ROM that hangs the emulator
        # must be a failure, not a stall.
        device = holder.get("device")
        process = getattr(device, "_proc", None)
        if process is not None:
            try:
                process.kill()
            except OSError:
                pass
        problems.append(
            f"the emulator did not finish the boot within "
            f"{args.probe_timeout:.0f}s: the ROM hangs the emulator")
    else:
        try:
            drive_error = holder.get("error")
        except Exception:  # pragma: no cover - defensive
            drive_error = None
        if drive_error:
            problems.append(f"the probe failed: {drive_error}")

    for name, path in shots.items():
        if not path.is_file():
            problems.append(f"the {name} screenshot was not written")

    metrics: dict = {}
    pixels: dict[str, list] = {}
    for name, path in shots.items():
        if not path.is_file():
            continue
        pixels[name] = load_rgb(path)
        metrics[name] = screen_stats(pixels[name])
        metrics[name]["sha256"] = sha256_file(path)
        metrics[name]["bytes"] = path.stat().st_size

    if "title" in pixels:
        title = pixels["title"]
        if len(title) != SCREEN_WIDTH * SCREEN_HEIGHT:
            problems.append(f"the title frame has {len(title)} pixels, expected "
                            f"{SCREEN_WIDTH * SCREEN_HEIGHT}")
        stats = metrics["title"]
        if stats["non_black_fraction"] < args.min_non_black:
            problems.append(
                f"the title frame is nearly blank: only "
                f"{stats['non_black_fraction']:.4f} of the pixels are non-black "
                f"(need >= {args.min_non_black})")
        if stats["distinct_colors"] < args.min_colors:
            problems.append(
                f"the title frame has only {stats['distinct_colors']} distinct "
                f"colours (need >= {args.min_colors})")
        if "boot" in pixels and differing_pixels(title, pixels["boot"]) == 0:
            problems.append("the title frame is identical to the blank boot "
                            "screen: the title never rendered")
        glyphs = ink_components(title, SCREEN_WIDTH, args.band_rows)
        metrics["title"]["glyphs"] = glyphs
        if glyphs["components"] < args.min_glyphs:
            problems.append(
                f"the title band carries {glyphs['components']} separated ink "
                f"components (need >= {args.min_glyphs}): the Chinese title "
                f"text did not render")
        if glyphs["ink_pixels"] < args.min_ink_pixels:
            problems.append(
                f"the title band carries {glyphs['ink_pixels']} ink pixels "
                f"(need >= {args.min_ink_pixels})")
        if "after_input" in pixels:
            different = differing_pixels(title, pixels["after_input"])
            metrics["title"]["differs_from_after_input"] = different
            if different == 0:
                problems.append("the game did not react to the A press: the "
                                "ROM is not running")
        if args.reference and args.reference.is_file():
            reference = load_rgb(args.reference)
            different = differing_pixels(title, reference)
            ratio = different / len(title) if title else 1.0
            metrics["title"]["reference"] = str(args.reference)
            metrics["title"]["reference_diff_pixels"] = different
            metrics["title"]["reference_diff_fraction"] = round(ratio, 6)
            if ratio > args.max_reference_diff:
                problems.append(
                    f"the title frame differs from the pinned reference in "
                    f"{ratio:.4%} of its pixels (limit {args.max_reference_diff:.2%})")
        elif args.reference:
            metrics["title"]["reference"] = str(args.reference)
            metrics["title"]["reference_diff_fraction"] = None

    if not responsive:
        problems.append("the emulator stopped answering after the last frame")

    noise = " ".join(stdout_tail + stderr_tail).lower()
    markers = [marker for marker in CRASH_MARKERS if marker in noise]
    if markers:
        problems.append("the probe output carries a crash marker: "
                         + ", ".join(markers))

    receipt = {
        "schema": "konoha.s49-package.smoke.v1",
        "rom": str(rom),
        "rom_sha256": sha256_file(rom),
        "probe": str(probe_exe),
        "probe_sha256": sha256_file(probe_exe),
        "frames_requested": args.frames,
        "frames_run": frames_run,
        "title_frame": args.title_frame,
        "boot_frame": args.boot_frame,
        "press": {"key": "A", "frames": PRESS_FRAMES, "settle": SETTLE_FRAMES},
        "criterion": (
            "the probe accepted every command and printed no crash marker, "
            "the emulator still answered after the last frame, the title "
            "frame is not the blank boot screen (>= "
            f"{args.min_non_black:.2%} non-black, >= {args.min_colors} "
            f"colours), the title band carries >= {args.min_glyphs} separated "
            f"ink components and >= {args.min_ink_pixels} ink pixels (the "
            "Chinese glyphs), the game reacted to the A press, and the title "
            "frame matches the pinned reference within "
            f"{args.max_reference_diff:.2%}"),
        "metrics": metrics,
        "problems": problems,
        "ok": not problems,
        "probe_stderr": stderr_tail,
    }
    (out / "smoke.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")

    if args.pin_reference and (out / "frame-title.png").is_file():
        args.pin_reference.parent.mkdir(parents=True, exist_ok=True)
        args.pin_reference.write_bytes((out / "frame-title.png").read_bytes())
        print(f"pinned the reference title frame: {args.pin_reference}")

    print(f"frames run        : {frames_run}")
    for name in ("boot", "title", "after_input", "last"):
        if name in metrics:
            stats = metrics[name]
            print(f"  {name:12s} non-black {stats['non_black_fraction']:.4f}  "
                  f"colours {stats['distinct_colors']}  "
                  f"sha {stats['sha256'][:12]}")
    if "title" in metrics and "glyphs" in metrics["title"]:
        glyphs = metrics["title"]["glyphs"]
        print(f"  title glyphs    : {glyphs['components']} ink components, "
              f"{glyphs['ink_pixels']} ink pixels")
    print(f"problems          : {len(problems)}")
    for problem in problems:
        print(f"  - {problem}")
    print("->", out / "smoke.json")
    if problems:
        print("FAIL: the ROM smoke test did not pass", file=sys.stderr)
        return 1
    print("OK: the ROM ran and the Chinese title screen rendered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
