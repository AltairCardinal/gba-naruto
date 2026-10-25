#!/usr/bin/env python3
"""Build the mGBA audio recorder used to capture original MP2K cue PCM.

Stream L (S49 audio wiring).  The recorder source lives in the remake tree
(`tools/butano/mgba_audio_recorder.c`) and is reused **read only**; this
script only compiles it into a private output directory so the shared
`build/mgba-probe/mgba-probe.exe` is never touched.

The probe build script is imported (not modified) so the host always matches
the ABI of the mGBA static library that is already built on this machine.

Usage:
    python tools/s49_audio_l/build_recorder.py
"""
from __future__ import annotations

import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PROBE_DIR = REPO / "tools" / "mgba_probe"
REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
RECORDER_SOURCE = REMAKE_ROOT / "tools" / "butano" / "mgba_audio_recorder.c"
OUT_DIR = pathlib.Path(
    __import__("os").environ.get(
        "KONOHA_PROBE_OUT", str(REPO / "build" / "mgba-probe-l")))

if str(PROBE_DIR) not in sys.path:
    sys.path.insert(0, str(PROBE_DIR))

import build as probe_build  # noqa: E402  (shared probe build script)


def main() -> int:
    if not RECORDER_SOURCE.is_file():
        raise SystemExit(f"ERR recorder source missing: {RECORDER_SOURCE}")
    if not probe_build.MGBA_LIB.exists():
        raise SystemExit(
            f"ERR mgba static library missing: {probe_build.MGBA_LIB}")
    env = probe_build.find_vc_env()
    defines = probe_build.library_defines()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    obj = OUT_DIR / "mgba_audio_recorder.obj"
    exe = OUT_DIR / "mgba-audio-recorder.exe"
    cl = shutil.which("cl.exe", path=env.get("PATH", ""))
    link = shutil.which("link.exe", path=env.get("PATH", ""))
    if not cl or not link:
        raise SystemExit("ERR cl.exe / link.exe not found in the MSVC environment")
    compile_cmd = [
        cl, "/nologo", "/O2", "/std:c11", "/W3", "/utf-8", "/MD",
        "/D_CRT_SECURE_NO_WARNINGS",
    ] + [f"/D{d}" for d in defines] + [
        f"/I{probe_build.MGBA_SRC / 'include'}",
        f"/I{probe_build.MGBA_SRC / 'src'}",
    ]
    if "USE_LUA" in defines:
        compile_cmd.append(f"/I{probe_build.LUA_SRC}")
    compile_cmd += ["/c", str(RECORDER_SOURCE), f"/Fo{obj}"]
    if probe_build.run(compile_cmd, env=env) != 0:
        return 1
    link_cmd = [
        link, "/nologo", f"/OUT:{exe}", f"/MAP:{OUT_DIR / 'mgba-audio-recorder.map'}",
        str(obj), str(probe_build.MGBA_LIB),
    ]
    if "USE_LUA" in defines:
        link_cmd.append(str(probe_build.LUA_LIB))
    for extra in (probe_build.MGBA_BUILD / "libpng" / "Release" / "libpng16_static.lib",
                  probe_build.MGBA_BUILD / "zlib" / "Release" / "zlibstatic.lib"):
        if extra.is_file():
            link_cmd.append(str(extra))
    link_cmd += probe_build.MGBA_SYSTEM_LIBS
    if probe_build.run(link_cmd, env=env) != 0:
        return 1
    print(f"built {exe} ({exe.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
