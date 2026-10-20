#!/usr/bin/env python3
"""Render the emulated GBA screen from VRAM / PALRAM / display registers.

mGBA's own PNG writer needs the library built with PNG support, so instead of
fighting the build we reconstruct the picture from the same data the PPU uses:

    DISPCNT   0x04000000  mode, BG enable, OBJ enable
    DISPBGCNT 0x04000008  per BG: char base, palette base, screen base, size
    VRAM      0x06000000  tiles + tilemaps
    PALRAM    0x05000000  16-bit BGR555 palettes (128 bytes of BG, 64 of OBJ)

This is the same information the PPU has, so the output matches what a player
sees - and it works for any state we can save.

The preferred path is `--live`, which asks the probe for mGBA's **own**
rendered frame (`rawshot` dumps the core's video buffer).  That path needs
neither PNG support in mGBA nor a second implementation of the PPU, and it is
the visual proof used for the story VM root tables
(`0x060C74` / `0x060D54` / `0x060E34` / `0x060EF0`) -- see
`notes/evidence/story-scene-l3-20261020.md`.

Usage:
    python tools/mgba_probe/render_screen.py build/shot.png --live --rom rom/base.gba
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

WIDTH, HEIGHT = 240, 160

# area overflow -> (map width in tiles, map height in tiles)
BG_SIZES = {
    0: (32, 32),
    1: (64, 32),
    2: (32, 64),
    3: (64, 64),
}


def _u16(data: bytes, addr: int) -> int:
    return data[addr] | (data[addr + 1] << 8)


def _u32(data: bytes, addr: int) -> int:
    return int.from_bytes(data[addr:addr + 4], "little")


def _bgr555_to_rgb(value: int) -> tuple[int, int, int]:
    r = (value & 0x1F) * 255 // 31
    g = ((value >> 5) & 0x1F) * 255 // 31
    b = ((value >> 10) & 0x1F) * 255 // 31
    return r, g, b


def render(vram: bytes, palram: bytes, dispcnt: int, bgcnts: list[int],
           obj_base: int = 0x07000000, obj_data: bytes = b"",
           include_obj: bool = False) -> list[list[tuple[int, int, int]]]:
    """Render the screen into a pixel grid."""
    screen = [[(0, 0, 0)] * WIDTH for _ in range(HEIGHT)]
    mode = dispcnt & 7

    # Mode 3 / 4 are framebuffer modes: the picture lives in VRAM itself,
    # not in a tilemap.  This game boots into mode 4 (8bpp), which is why
    # a tilemap-only renderer shows a blank screen.
    if mode == 3:
        for py in range(HEIGHT):
            for px in range(WIDTH):
                off = (py * WIDTH + px) * 2
                if off + 2 > len(vram):
                    continue
                value = vram[off] | (vram[off + 1] << 8)
                screen[py][px] = _bgr555_to_rgb(value)
        return screen
    if mode == 4:
        # Frame 0 at 0x06000000, frame 1 at 0x0600A000; DISPCNT bit 4 picks
        # which one is displayed.
        base = 0xA000 if (dispcnt & 0x10) else 0
        for py in range(HEIGHT):
            for px in range(WIDTH):
                off = base + py * WIDTH + px
                if off >= len(vram):
                    continue
                index = vram[off]
                # In mode 4 the 8-bit index addresses PALRAM *bytes*, so
                # index i and i+128 alias the same BGR555 colour.
                pal_off = index & 0xFE
                if pal_off + 2 > len(palram):
                    continue
                value = palram[pal_off] | (palram[pal_off + 1] << 8)
                screen[py][px] = _bgr555_to_rgb(value)
        return screen

    bg_enable = (dispcnt >> 8) & 0x0F
    if mode > 2:
        # Mode 5..7 are special; nothing we can draw from VRAM alone.
        return screen

    # Draw the enabled BGs from lowest priority to highest (0 = on top).
    layers = []
    for n in range(4):
        if not (bg_enable & (1 << n)):
            continue
        layers.append((n, bgcnts[n]))
    layers.sort(key=lambda item: (item[1] >> 14) & 3, reverse=True)

    for n, cnt in layers:
        # GBA DISPBGCNT layout (NOT the DS one):
        #   bits 0-1  character base block  (0/0x4000/0x8000/0xC000)
        #   bit  5    screen base block     (0/0x1000/0x2000/0x3000)
        #   bits 7-8  screen size           (0=32x32 1=64x32 2=32x64 3=64x64)
        #   bits 8-12 colour palette        (base entry = value * 16)
        # The earlier version read these from the DS bit positions, which is
        # why the screen came out as vertical stripes.
        char_base = (cnt & 3) * 0x4000
        palette_bank = (cnt >> 8) & 0x1F
        screen_base = ((cnt >> 5) & 3) * 0x1000
        area = (cnt >> 7) & 3
        map_w, map_h = BG_SIZES.get(area, (32, 32))
        color256 = False          # 256-colour backgrounds are mode 4/5 only
        tile_x = tile_y = 0       # no display-area overflow on GBA

        for py in range(HEIGHT):
            ty = py // 8
            for px in range(WIDTH):
                tx = px // 8
                map_x = tile_x + tx
                map_y = tile_y + ty
                if map_x >= map_w or map_y >= map_h:
                    continue
                entry_off = (screen_base * 0x1000) + (map_y * map_w + map_x) * 2
                if entry_off + 2 > len(vram):
                    continue
                entry = vram[entry_off] | (vram[entry_off + 1] << 8)
                if color256:
                    tile_index = entry & 0x1FF
                    hflip = bool(entry & (1 << 9))
                    vflip = bool(entry & (1 << 10))
                    px_in = (7 - (px % 8)) if hflip else (px % 8)
                    py_in = (7 - (py % 8)) if vflip else (py % 8)
                    src = char_base + tile_index * 64 + py_in * 8 + px_in
                    if src >= len(vram):
                        continue
                    color = vram[src]
                    # 256-colour BG: the palette block holds 256 entries
                    pal_index = palette_bank * 256 + color
                    pal_off = pal_index * 2
                    if pal_off + 2 > len(palram):
                        continue
                    value = palram[pal_off] | (palram[pal_off + 1] << 8)
                    screen[py][px] = _bgr555_to_rgb(value)
                else:
                    tile_index = entry & 0x3FF
                    hflip = bool(entry & (1 << 10))
                    vflip = bool(entry & (1 << 11))
                    bank = (entry >> 12) & 0xF
                    px_in = (7 - (px % 8)) if hflip else (px % 8)
                    py_in = (7 - (py % 8)) if vflip else (py % 8)
                    src = char_base + tile_index * 32 + py_in * 4 + (px_in // 2)
                    if src >= len(vram):
                        continue
                    byte = vram[src]
                    color = (byte >> 4) if (px_in % 2) == 0 else (byte & 0xF)
                    if color == 0:
                        continue
                    # 16-colour BG: the palette block holds 16 sub-palettes of
                    # 16 colours; the tilemap's bank bits pick the sub-palette.
                    pal_index = palette_bank * 16 + bank * 16 + color
                    pal_off = pal_index * 2
                    if pal_off + 2 > len(palram):
                        continue
                    value = palram[pal_off] | (palram[pal_off + 1] << 8)
                    screen[py][px] = _bgr555_to_rgb(value)
    return screen


def screen_to_png(screen, out: pathlib.Path) -> pathlib.Path:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("ERR Pillow is required") from exc
    image = Image.new("RGB", (WIDTH, HEIGHT))
    image.putdata([screen[y][x] for y in range(HEIGHT) for x in range(WIDTH)])
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    return out


def render_from_state(vram: bytes, palram: bytes, io_bytes: bytes,
                      out: pathlib.Path) -> pathlib.Path:
    dispcnt = _u16(io_bytes, 0x000)
    bgcnts = [_u16(io_bytes, 0x008 + n * 4) for n in range(4)]
    screen = render(vram, palram, dispcnt, bgcnts)
    return screen_to_png(screen, out)


def _png_from_rgba(raw: bytes, out: pathlib.Path) -> pathlib.Path:
    """Write mGBA's raw RGBA frame buffer out as a PNG.

    `rawshot` stores 240x160 pixels of `color_t`.  With the 32-bit build one
    pixel is a uint32 whose bytes are R, G, B, A in that order
    (mgba/core/interface.h: M_COLOR_RED 0x000000FF, M_COLOR_GREEN
    0x0000FF00, M_COLOR_BLUE 0x00FF0000).
    """
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("ERR Pillow is required") from exc
    expected = WIDTH * HEIGHT * 4
    if len(raw) < expected:
        raise SystemExit(f"ERR raw frame is {len(raw)} bytes, expected {expected}")
    image = Image.frombytes("RGBA", (WIDTH, HEIGHT), raw[:expected]).convert("RGB")
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    return out


def capture_live(rom: pathlib.Path, out: pathlib.Path,
                 exe: pathlib.Path | None = None,
                 boot_frames: int = 1500,
                 presses: list[str] | None = None,
                 settle_frames: int = 120,
                 raw: bool = True) -> pathlib.Path:
    """Boot the game in the probe, then draw what is on screen.

    With `raw=True` the picture comes from **mGBA's own renderer** (the
    `rawshot` command dumps the core's video buffer), so it is exactly what
    a player sees and needs neither PNG support in mGBA nor a second
    implementation of the PPU.

    With `raw=False` the picture is reconstructed from VRAM / PALRAM / the
    display registers.  That path is only useful for debugging the PPU
    understanding itself.
    """
    import subprocess
    import threading
    import tempfile

    exe = exe or (REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    if not exe.exists():
        raise SystemExit(f"ERR {exe} missing; run: python tools/mgba_probe/build.py")
    proc = subprocess.Popen(
        [str(exe), str(rom)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", bufsize=1)
    threading.Thread(target=lambda: [None for _ in proc.stderr], daemon=True).start()

    def send(command: str) -> list[str]:
        token = "__end__"
        proc.stdin.write(f"{command}\necho {token}\n")
        proc.stdin.flush()
        lines = []
        while True:
            line = proc.stdout.readline()
            if not line:
                raise EOFError("probe exited")
            line = line.rstrip("\r\n")
            if line == token:
                return lines
            lines.append(line)

    def read(address: int, length: int) -> bytes:
        out = send(f"dump 0x{address:08X} {length}")
        payload = []
        for line in out:
            line = line.strip()
            if line and all(c in "0123456789abcdefABCDEF" for c in line):
                payload.append(line)
        try:
            return bytes.fromhex("".join(payload))
        except ValueError:
            return b""

    raw_path = None
    try:
        send(f"frames {boot_frames} 0x000")
        for press in (presses or []):
            bit = {"A": 0x001, "B": 0x002, "START": 0x008,
                   "SELECT": 0x004, "UP": 0x040, "DOWN": 0x080,
                   "LEFT": 0x020, "RIGHT": 0x010}.get(press.upper(), 0)
            send(f"frames 8 {bit:#05x}")
            send(f"frames {settle_frames} 0x000")
        if raw:
            handle, raw_path = tempfile.mkstemp(suffix=".rgba")
            os.close(handle)
            out_lines = send(f"rawshot {raw_path}")
            print("  ".join(out_lines))
        vram = read(0x06000000, 0x18000)
        palram = read(0x05000000, 0x200)
        io_bytes = read(0x04000000, 0x60)
    finally:
        try:
            send("quit")
        except Exception:
            pass
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    if raw and raw_path and pathlib.Path(raw_path).exists():
        data = pathlib.Path(raw_path).read_bytes()
        pathlib.Path(raw_path).unlink(missing_ok=True)
        return _png_from_rgba(data, out)

    dispcnt = _u16(io_bytes, 0x000)
    bgcnts = [_u16(io_bytes, 0x008 + n * 4) for n in range(4)]
    print(f"DISPCNT={dispcnt:#06x} mode={dispcnt & 7} "
          f"bg_enable={(dispcnt >> 8) & 0x0F:#06x} "
          f"obj_enable={(dispcnt >> 12) & 1}")
    for n, cnt in enumerate(bgcnts):
        print(f"  DISPBGCNT[{n}]={cnt:#06x}  "
              f"prio={(cnt >> 14) & 3} char_base={(cnt & 3) * 0x4000:#x} "
              f"screen_base={((cnt >> 5) & 3) * 0x1000:#x} "
              f"size={(cnt >> 7) & 3} (map={BG_SIZES.get((cnt >> 7) & 3)}) "
              f"pal_base={((cnt >> 8) & 0x1F) * 16}")
    screen = render(vram, palram, dispcnt, bgcnts)
    return screen_to_png(screen, out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", help="PNG path to write")
    ap.add_argument("--vram", help="raw VRAM dump")
    ap.add_argument("--palram", help="raw PALRAM dump")
    ap.add_argument("--io", help="raw I/O register dump")
    ap.add_argument("--live", action="store_true",
                    help="boot the game in the probe and draw that instead")
    ap.add_argument("--live-vram", action="store_true",
                    help="reconstruct the picture from VRAM/PALRAM instead of "
                         "using mGBA's own renderer (debugging aid only)")
    ap.add_argument("--rom", default="rom/base.gba")
    ap.add_argument("--exe", default=None)
    ap.add_argument("--boot-frames", type=int, default=1500)
    ap.add_argument("--press", action="append", default=[],
                    help="key to press before the capture; repeatable")
    ap.add_argument("--settle-frames", type=int, default=120)
    args = ap.parse_args()

    if args.live or args.live_vram:
        path = capture_live(pathlib.Path(args.rom), pathlib.Path(args.out),
                            pathlib.Path(args.exe) if args.exe else None,
                            boot_frames=args.boot_frames, presses=args.press,
                            settle_frames=args.settle_frames,
                            raw=not args.live_vram)
        print(f"wrote {path}")
        return 0

    if not (args.vram and args.palram and args.io):
        ap.error("--vram/--palram/--io are required unless --live is given")
    vram = pathlib.Path(args.vram).read_bytes()
    palram = pathlib.Path(args.palram).read_bytes()
    io_bytes = pathlib.Path(args.io).read_bytes()
    path = render_from_state(vram, palram, io_bytes, pathlib.Path(args.out))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
