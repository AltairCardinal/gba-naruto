#!/usr/bin/env python3
"""Build the headless mGBA probe (tools/mgba_probe/host_main.c).

The probe links mGBA's static library and mounts extra CLI commands on top of
mGBA's own debugger:

    key <mask>             set the key state (GBA bit mask)
    keyoff                 release all keys
    frames <count> <mask>  set keys, run N frames, release keys
    dump <addr> <len>      hex dump an arbitrary region
    save <path>            write a savestate to <path>
    load <path>            read a savestate from <path>

Everything else (breakpoints, watchpoints, memory, registers, frame advance,
print, disassemble) is mGBA's own CLI debugger.

Toolchain
---------
MSVC Build Tools 2022 (already installed on this machine) builds both the
mGBA static library and the host.  CMake's Visual Studio generator is used for
mGBA; the host is compiled with cl.exe and linked with link.exe.

mGBA's source lives outside the repository (``$KONOHA_MGBA_SRC``, default
``D:/Shell/toolchain/mgba-0.10.5``) so the repository keeps its file size and
SHA-256 identity.

ABI
---
``struct mCore`` embeds ``#ifdef USE_DEBUGGERS`` members, so the host has to
be compiled with *exactly* the preprocessor defines the library was built
with.  Rather than copying that list by hand (which silently breaks the
host), this script reads the defines out of the generated ``mgba.vcxproj``
that CMake produced for the very same library and passes them to cl.exe.

Usage:
    python tools/mgba_probe/build.py
    python tools/mgba_probe/build.py --rebuild-mgba
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent

MGBA_SRC = pathlib.Path(os.environ.get("KONOHA_MGBA_SRC", r"D:\Shell\toolchain\mgba-0.10.5"))
MGBA_BUILD = pathlib.Path(os.environ.get("KONOHA_MGBA_BUILD", r"D:\Shell\toolchain\mgba-build"))
MGBA_LIB = MGBA_BUILD / "Release" / "mgba.lib"
MGBA_VCXPROJ = MGBA_BUILD / "mgba.vcxproj"
OUT_DIR = REPO / "build" / "mgba-probe"

VSWHERE = pathlib.Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")


def _find_cmake() -> pathlib.Path:
    """Locate the portable CMake.

    The toolchain lives outside the repository and has moved between drives
    (D: -> C:), so the path is searched rather than hard-coded.
    """
    env = os.environ.get("KONOHA_CMAKE")
    candidates = [pathlib.Path(env)] if env else []
    candidates += [
        pathlib.Path(r"D:\Shell\toolchain\cmake-3.31.7-windows-x86_64\bin\cmake.exe"),
        pathlib.Path(r"C:\Shell\toolchain\cmake-3.31.7-windows-x86_64\bin\cmake.exe"),
    ]
    for root in ("D:/Shell/toolchain", "C:/Shell/toolchain"):
        base = pathlib.Path(root)
        if base.exists():
            candidates += [p / "bin" / "cmake.exe"
                           for p in sorted(base.glob("cmake-*")) if p.is_dir()]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit("ERR cmake not found; set KONOHA_CMAKE to the cmake.exe path")


CMAKE = _find_cmake()

MGBA_CMAKE_ARGS = [
    "-DLIBMGBA_ONLY=ON",
    "-DBUILD_QT=OFF", "-DBUILD_SDL=OFF", "-DBUILD_LIBRETRO=OFF",
    "-DBUILD_SHARED=OFF", "-DBUILD_STATIC=ON",
    "-DM_CORE_GB=OFF", "-DM_CORE_GBA=ON",
    "-DUSE_DEBUGGERS=ON", "-DUSE_EDITLINE=OFF", "-DUSE_GDB_STUB=OFF",
    "-DUSE_LUA=OFF", "-DENABLE_SCRIPTING=OFF",
    "-DUSE_FFMPEG=OFF", "-DUSE_PNG=ON", "-DUSE_ZLIB=ON", "-DUSE_LZMA=OFF",
    "-DUSE_SQLITE3=OFF", "-DUSE_ELF=OFF", "-DUSE_LIBZIP=OFF",
    "-DUSE_MINIZIP=OFF", "-DUSE_DISCORD_RPC=OFF",
]

# Libraries mGBA's own CMake link line pulls in on Windows.
MGBA_SYSTEM_LIBS = [
    "ws2_32.lib", "user32.lib", "advapi32.lib", "shell32.lib", "ole32.lib",
    # mCoreConfigPortablePath() calls PathRemoveFileSpecW
    "shlwapi.lib",
]


def find_vc_env() -> dict[str, str]:
    """Environment with the MSVC x64 toolchain on PATH."""
    if not VSWHERE.exists():
        raise SystemExit("ERR vswhere not found; install MSVC Build Tools")
    out = subprocess.run(
        [str(VSWHERE), "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
         "-property", "installationPath", "-latest", "-utf8"],
        capture_output=True, text=True,
    )
    install = out.stdout.strip()
    if not install:
        raise SystemExit("ERR MSVC build tools not found")
    vcvars = pathlib.Path(install) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    if not vcvars.exists():
        raise SystemExit(f"ERR vcvars64.bat missing: {vcvars}")
    # NOTE: cmd.exe does not understand the backslash-escaped quotes that
    # subprocess' list form produces, so the batch file has to be invoked
    # through a single shell string.
    cmd = subprocess.run(
        f'call "{vcvars}" >nul 2>&1 && set',
        shell=True, capture_output=True, text=True,
    )
    env = dict(os.environ)
    for line in cmd.stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            env[key] = value
    # vcvars64 sets INCLUDE/LIB but not always the toolchain bin directory.
    tools_dir = pathlib.Path(install) / "VC" / "Tools" / "MSVC"
    if tools_dir.exists():
        newest = sorted(tools_dir.iterdir())[-1]
        bin_dir = newest / "bin" / "Hostx64" / "x64"
        if bin_dir.exists():
            env["PATH"] = f"{bin_dir};{env.get('PATH', '')}"
    if not shutil.which("cl.exe", path=env.get("PATH", "")):
        raise SystemExit("ERR cl.exe not on PATH after vcvars64")
    return env


def run(cmd: list[str], cwd: pathlib.Path | None = None, env=None) -> int:
    print("$", " ".join(str(c) for c in cmd))
    result = subprocess.run(
        [str(c) for c in cmd], cwd=cwd, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for stream in (result.stdout, result.stderr):
        if stream:
            sys.stdout.write(stream)
    return result.returncode


def build_mgba() -> int:
    if not MGBA_SRC.exists():
        print(f"ERR mGBA source missing: {MGBA_SRC}")
        return 1
    if not CMAKE.exists():
        print(f"ERR cmake missing: {CMAKE}")
        return 1
    args = [
        CMAKE, "-S", MGBA_SRC, "-B", MGBA_BUILD,
        "-DCMAKE_BUILD_TYPE=Release",
    ] + MGBA_CMAKE_ARGS
    if run(args) != 0:
        return 1
    if run([CMAKE, "--build", MGBA_BUILD, "--config", "Release",
            "--target", "mgba", "-j", "8"]) != 0:
        return 1
    return 0 if MGBA_LIB.exists() else 1


def library_defines() -> list[str]:
    """The preprocessor defines the mGBA library was compiled with.

    Read straight out of the CMake-generated vcxproj so the host can never
    drift away from the library's ABI.
    """
    if not MGBA_VCXPROJ.exists():
        raise SystemExit(
            f"ERR {MGBA_VCXPROJ} missing; run with --rebuild-mgba first")
    ns = {"m": "http://schemas.microsoft.com/developer/msbuild/2003"}
    tree = ET.parse(MGBA_VCXPROJ)
    defines: list[str] = []
    for group in tree.iter("{http://schemas.microsoft.com/developer/msbuild/2003}ItemDefinitionGroup"):
        condition = group.get("Condition", "")
        if "Release" not in condition:
            continue
        for node in group.iter("{http://schemas.microsoft.com/developer/msbuild/2003}PreprocessorDefinitions"):
            raw = (node.text or "").strip()
            for item in raw.split(";"):
                item = item.strip()
                if not item or item.startswith("%("):
                    continue
                if item.startswith("CMAKE_INTDIR"):
                    # Quoting this one through the command line is pointless
                    # and it has no effect on the structures we share.
                    continue
                if item not in defines:
                    defines.append(item)
            if defines:
                break
        if defines:
            break
    if not defines:
        raise SystemExit(f"ERR could not read defines from {MGBA_VCXPROJ}")
    for required in ("USE_DEBUGGERS", "M_CORE_GBA"):
        if required not in defines:
            raise SystemExit(
                f"ERR {required} missing from the mGBA defines - the host "
                "would not match the library's ABI")
    return defines


def build_host(env: dict[str, str]) -> int:
    if not MGBA_LIB.exists():
        print(f"ERR mgba static library missing: {MGBA_LIB}")
        return 1
    defines = library_defines()
    print("mGBA library defines:", " ".join(defines))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    obj = OUT_DIR / "host_main.obj"
    exe = OUT_DIR / "mgba-probe.exe"
    # CreateProcess resolves the executable against the *parent's* PATH, so the
    # tools have to be referenced by absolute path, not just by name.
    cl = shutil.which("cl.exe", path=env.get("PATH", ""))
    link = shutil.which("link.exe", path=env.get("PATH", ""))
    if not cl or not link:
        raise SystemExit("ERR cl.exe / link.exe not found in the MSVC environment")
    compile_cmd = [
        cl, "/nologo", "/O2", "/std:c11", "/W3", "/utf-8", "/MD",
        "/D_CRT_SECURE_NO_WARNINGS",
    ] + [f"/D{d}" for d in defines] + [
        f"/I{MGBA_SRC / 'include'}", f"/I{MGBA_SRC / 'src'}",
        "/c", str(HERE / "host_main.c"), f"/Fo{obj}",
    ]
    if run(compile_cmd, env=env) != 0:
        return 1
    link_cmd = [
        link, "/nologo", f"/OUT:{exe}", f"/MAP:{OUT_DIR / 'mgba-probe.map'}",
        str(obj), str(MGBA_LIB),
    ] + MGBA_SYSTEM_LIBS
    if run(link_cmd, env=env) != 0:
        return 1
    print(f"built {exe} ({exe.stat().st_size} bytes)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rebuild-mgba", action="store_true",
                    help="reconfigure and rebuild the mGBA static library")
    args = ap.parse_args()

    if args.rebuild_mgba or not MGBA_LIB.exists():
        if build_mgba() != 0:
            return 1
    env = find_vc_env()
    return build_host(env)


if __name__ == "__main__":
    raise SystemExit(main())
