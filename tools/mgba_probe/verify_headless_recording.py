#!/usr/bin/env python3
"""Prove that the local recording chain is headless and silent.

The requirement for this toolchain is that recording never pops a window and
never makes the machine play a sound.  Both properties are checked here by
evidence rather than by configuration:

1. **Import table.**  The probe links libmgba's *core* only.  If the binary
   does not import USER32 (window creation) or an audio backend (winmm,
   avrt, SDL, OpenAL), the process *cannot* present a window or open an audio
   device, whatever the scripts ask for.  Lua and PNG are linked statically
   and add no new dependency.

2. **Live window enumeration.**  While a real recording runs, every
   top-level window belonging to the probe process is enumerated.  A console
   application inherits its console from the OS; the emulator itself must not
   own any additional window.

3. **Output sanity.**  The frames the recording produced are real PNGs of the
   right size, so the check above is not passing on an empty recording.

Usage::

    python tools/mgba_probe/verify_headless_recording.py
    python tools/mgba_probe/verify_headless_recording.py --keep
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import threading
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
PROBE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
ROM = REPO / "rom" / "base.gba"

# A window-creating or audio-capable dependency.  None of these may appear in
# the probe's import table.
FORBIDDEN_IMPORTS = {
    "user32.dll": "window creation / message loop",
    "gdi32.dll": "GDI drawing",
    "winmm.dll": "Windows multimedia (audio) API",
    "avrt.dll": "audio session API",
    "dsound.dll": "DirectSound",
    "sdl2.dll": "SDL (window + audio)",
    "openal32.dll": "OpenAL (audio)",
    "xaudio2_9.dll": "XAudio2 (audio)",
    "mf.dll": "Media Foundation",
    "mfplat.dll": "Media Foundation",
}

LUA_SCRIPT = r"""
local out_dir = os.getenv("VERIFY_OUT_DIR")
assert(out_dir and out_dir ~= "", "missing VERIFY_OUT_DIR")
local frames = 0
callbacks:add("frame", function()
	frames = frames + 1
	if frames == 5 then
		assert(emu:screenshot(out_dir .. "/frame-005.png"), "screenshot failed")
	end
end)
"""


def pe_imports(path: pathlib.Path) -> list[str]:
    """Return the DLL names in a PE file's import directory."""
    data = path.read_bytes()
    if data[:2] != b"MZ":
        raise ValueError(f"{path} is not a PE file")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ValueError(f"{path} has no PE signature")
    machine, section_count = struct.unpack_from("<HH", data, pe_offset + 4)
    optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    optional = pe_offset + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    if magic == 0x20B:  # PE32+
        dir_offset = optional + 112
    else:  # PE32
        dir_offset = optional + 96
    # Data directory 0 is the export table; the import table is directory 1.
    import_rva, import_size = struct.unpack_from("<II", data, dir_offset + 8)
    if not import_rva:
        return []

    sections = []
    section_table = optional + optional_size
    for i in range(section_count):
        base = section_table + i * 40
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
            "<IIII", data, base + 8
        )
        sections.append((virtual_address, max(virtual_size, raw_size), raw_pointer))

    def to_offset(rva: int) -> int:
        for virtual_address, size, raw_pointer in sections:
            if virtual_address <= rva < virtual_address + size:
                return raw_pointer + (rva - virtual_address)
        raise ValueError(f"RVA 0x{rva:x} is not inside any section")

    names: list[str] = []
    cursor = to_offset(import_rva)
    while True:
        entry = data[cursor : cursor + 20]
        if len(entry) < 20 or entry == b"\0" * 20:
            break
        name_rva = struct.unpack_from("<I", entry, 12)[0]
        if not name_rva:
            break
        offset = to_offset(name_rva)
        end = data.index(b"\0", offset)
        names.append(data[offset:end].decode("ascii", "replace").lower())
        cursor += 20
    return names


def enum_windows(pid: int) -> list[tuple[int, str]]:
    """Every top-level window owned by `pid` (handle, class name)."""
    user32 = ctypes.windll.user32
    found: list[tuple[int, str]] = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)
    )

    def callback(hwnd, _lparam):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buffer, 256)
            found.append((int(hwnd), buffer.value))
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", action="store_true", help="keep the scratch output")
    args = ap.parse_args()

    problems: list[str] = []
    if not PROBE.is_file():
        print(f"ERR probe not built: {PROBE}\n    python tools/mgba_probe/build.py")
        return 2
    if not ROM.is_file():
        print(f"ERR ROM missing: {ROM}")
        return 2

    # ---- 1. import table -------------------------------------------------
    imports = pe_imports(PROBE)
    bad = sorted(
        {n for n in imports if n in FORBIDDEN_IMPORTS}
    )
    print("probe imports:", ", ".join(sorted(imports)))
    for name in bad:
        problems.append(
            f"probe imports {name} ({FORBIDDEN_IMPORTS[name]}) - it could "
            "present a window or open an audio device"
        )

    # ---- 2. live recording + window enumeration --------------------------
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = pathlib.Path(tmp)
        script = out_dir / "verify.lua"
        script.write_text(LUA_SCRIPT, encoding="utf-8", newline="\n")

        env = dict(os.environ)
        env["VERIFY_OUT_DIR"] = out_dir.as_posix()

        child = subprocess.Popen(
            [
                str(PROBE),
                str(ROM),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        windows: list[tuple[int, str]] = []
        stop = threading.Event()

        def watch():
            while not stop.is_set():
                try:
                    windows.extend(enum_windows(child.pid))
                except OSError:
                    pass
                time.sleep(0.05)

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()

        try:
            assert child.stdin is not None and child.stdout is not None
            child.stdin.write(f"script {script.as_posix()}\n")
            child.stdin.write("frames 30 0x000\n")
            child.stdin.write("echo DONE\n")
            child.stdin.flush()
            child.stdin.close()
            out, _err = child.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            child.kill()
            problems.append("the probe did not finish within 120 s")
            out = ""
        finally:
            stop.set()
            watcher.join(timeout=2)

        print("probe stdout:", out.strip()[:400])
        if "OK script" not in out:
            problems.append("the probe did not accept the Lua script")
        if "DONE" not in out:
            problems.append("the probe did not reach the end of the command list")

        # ---- 3. window check ---------------------------------------------
        # The console window belongs to the OS console host, not to the
        # emulator; mGBA's own video window would show up as a second window.
        console_like = {"ConsoleWindowClass", "PseudoConsoleWindow"}
        emulator_windows = [
            (hwnd, cls) for hwnd, cls in windows if cls not in console_like
        ]
        if emulator_windows:
            problems.append(
                "the probe owned top-level windows during the recording: "
                + ", ".join(f"{cls}#{hwnd}" for hwnd, cls in emulator_windows)
            )
        else:
            print("windows owned by the probe during the recording: none")

        # ---- 4. output sanity ---------------------------------------------
        frame = out_dir / "frame-005.png"
        if not frame.is_file():
            problems.append("the recording produced no frame-005.png")
        else:
            blob = frame.read_bytes()
            if blob[:8] != b"\x89PNG\r\n\x1a\n":
                problems.append("frame-005.png is not a PNG")
            else:
                width, height = struct.unpack_from(">II", blob, 16)
                print(f"recorded frame: {width}x{height}, {len(blob)} bytes")
                if (width, height) != (240, 160):
                    problems.append(f"frame is {width}x{height}, expected 240x160")

        if args.keep:
            keep = REPO / "build" / "headless-recording-verify"
            keep.mkdir(parents=True, exist_ok=True)
            for item in out_dir.iterdir():
                (keep / item.name).write_bytes(item.read_bytes())
            print("kept scratch output in", keep)

    if problems:
        print("\nFAILED:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("\nOK: the recording chain is headless and silent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
