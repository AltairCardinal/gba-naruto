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
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent

MGBA_SRC = pathlib.Path(os.environ.get("KONOHA_MGBA_SRC", r"D:\Shell\toolchain\mgba-dev"))
MGBA_BUILD = pathlib.Path(os.environ.get("KONOHA_MGBA_BUILD", r"D:\Shell\toolchain\mgba-build-d8bad14b"))
MGBA_LIB = MGBA_BUILD / "Release" / "mgba.lib"
MGBA_VCXPROJ = MGBA_BUILD / "mgba.vcxproj"
OUT_DIR = pathlib.Path(os.environ.get(
    "KONOHA_PROBE_OUT", str(REPO / "build" / "mgba-probe")))

# The mGBA commit the project pins everywhere else
# (tools/macos_mgba_toolchain_profile.py -> CURRENT_MGBA_SOURCE_COMMIT).
#
# It matters for more than provenance: this commit carries GBA savestate
# version 0x0000000A, which is the format the Butano line's existing .ss9
# evidence files are written in.  mGBA 0.10.5 (version 0x00000007) *rejects*
# them ("Invalid or too new savestate"), and current master (0x0000000B)
# would write files the Butano line cannot read back.
MGBA_PINNED_COMMIT = "d8bad14b4540f9114246c0281d74985cf81adc68"

# Lua 5.4 for the mGBA script engine (src/script/engines/lua.c).  Built from
# source by tools/build_lua_lib.ps1 because this machine has no Lua dev
# package and no admin rights.  The probe stays headless and silent: Lua is
# a scripting engine, it does not open a window or an audio device.
LUA_SRC = pathlib.Path(os.environ.get("KONOHA_LUA_SRC", r"D:\Shell\toolchain\lua-5.4.7\src"))
LUA_LIB = pathlib.Path(os.environ.get("KONOHA_LUA_LIB", r"D:\Shell\toolchain\lua-5.4.7-build\lua54.lib"))


def check_mgba_commit() -> None:
    """Fail closed unless the toolchain checkout is the pinned commit."""
    if not MGBA_SRC.is_dir():
        return
    head = subprocess.run(
        ["git", "-C", str(MGBA_SRC), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    if head.returncode != 0:
        print(f"NOTE: {MGBA_SRC} is not a git checkout; skipping the commit check")
        return
    actual = head.stdout.strip()
    if actual != MGBA_PINNED_COMMIT:
        raise SystemExit(
            f"ERR mGBA checkout is {actual}, expected the pinned "
            f"{MGBA_PINNED_COMMIT}.\n"
            f"    git -C {MGBA_SRC} checkout --detach {MGBA_PINNED_COMMIT}"
        )
    print(f"mGBA checkout: {actual} (pinned)")


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
    # LIBMGBA_ONLY is deliberately NOT set: in the 0.11 development line it
    # also turns off ENABLE_DEBUGGERS, USE_LUA, USE_PNG and USE_ZLIB, and the
    # probe needs the debugger (breakpoints) and the script engine.  The
    # graphical frontends are excluded individually below instead.
    "-DBUILD_QT=OFF", "-DBUILD_SDL=OFF", "-DBUILD_LIBRETRO=OFF",
    "-DBUILD_SHARED=OFF", "-DBUILD_STATIC=ON",
    "-DM_CORE_GB=OFF", "-DM_CORE_GBA=ON",
    "-DENABLE_DEBUGGERS=ON", "-DUSE_EDITLINE=OFF", "-DENABLE_GDB_STUB=OFF",
    "-DUSE_FFMPEG=OFF", "-DUSE_PNG=ON", "-DUSE_ZLIB=ON", "-DUSE_LZMA=OFF",
    "-DUSE_SQLITE3=OFF", "-DUSE_ELF=OFF", "-DUSE_LIBZIP=OFF",
    "-DUSE_MINIZIP=OFF", "-DUSE_JSON_C=OFF", "-DUSE_FREETYPE=OFF",
    "-DUSE_DISCORD_RPC=OFF",
]

# Lua scripting is optional: without it the probe still records and dumps, it
# just cannot run the `mgba --script` style Lua probes.  It is enabled
# whenever the static library from tools/build_lua_lib.ps1 is present.
if LUA_LIB.is_file() and (LUA_SRC / "lua.h").is_file():
    MGBA_CMAKE_ARGS += [
        "-DENABLE_SCRIPTING=ON",
        "-DUSE_LUA=ON",
        f"-DLUA_INCLUDE_DIR={LUA_SRC}",
        f"-DLUA_LIBRARY={LUA_LIB}",
        f"-DLUA_LIBRARIES={LUA_LIB}",
    ]
else:
    MGBA_CMAKE_ARGS += ["-DUSE_LUA=OFF", "-DENABLE_SCRIPTING=OFF"]
    print("NOTE: Lua static library not found; building without scripting support")


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


def patch_mgba_for_lua() -> None:
    """Make mGBA's Lua lookup actually work on this machine.

    Two defects in mGBA 0.10.5 have to be worked around:

    1. ``find_feature(USE_LUA "Lua" ${USE_LUA})`` expands to
       ``find_package(Lua ON EXACT)`` with the default ``USE_LUA=ON``, and
       CMake rejects "ON" as a version string, so the feature is disabled.

    2. ``find_feature`` checks ``if(${REQUIRE}_FOUND)`` -- i.e. ``Lua_FOUND``
       -- but CMake's FindLua only sets the upper-case ``LUA_FOUND`` from
       inside a function scope, so the check never succeeds and the feature is
       disabled a second time, silently.

    The patches are applied to the toolchain checkout outside the repository
    and are idempotent: running them twice is a no-op.
    """
    cmake = MGBA_SRC / "CMakeLists.txt"
    feature = MGBA_SRC / "src" / "platform" / "cmake" / "FindFeature.cmake"
    if not cmake.is_file():
        print(f"NOTE: {cmake} missing; skipping the Lua lookup patch")
        return

    text = cmake.read_text(encoding="utf-8", errors="replace")
    # (1) `find_feature(USE_LUA "Lua" ${USE_LUA})` expands to
    #     `find_package(Lua ON EXACT)` with the default USE_LUA=ON, and CMake
    #     rejects "ON" as a version string, so the feature is disabled.
    #     Pass a version only when one was actually asked for.  The guard
    #     differs between mGBA releases (if / elseif), so match either.
    version_guard = 'USE_LUA MATCHES "^[0-9]+(\\\\.[0-9]+)*$"'
    if "NOT USE_LUA VERSION_LESS 5.1" in text:
        text = text.replace(
            "NOT USE_LUA VERSION_LESS 5.1", version_guard
        )
        cmake.write_text(text, encoding="utf-8", newline="")
        print("patched mGBA CMakeLists for version-less USE_LUA")
    else:
        print("mGBA CMakeLists Lua lookup already patched or not needed")

    if feature.is_file():
        ftext = feature.read_text(encoding="utf-8", errors="replace")

        # (2) An explicitly requested feature must not be skipped just because
        #     LIBMGBA_ONLY sets DISABLE_DEPS.
        dold = "\tif (DISABLE_DEPS)\n\t\tset(${FEATURE_NAME} OFF PARENT_SCOPE)\n\t\treturn()\n\tendif()"
        dnew = "\tif (DISABLE_DEPS AND NOT ${FEATURE_NAME})\n\t\tset(${FEATURE_NAME} OFF PARENT_SCOPE)\n\t\treturn()\n\tendif()"
        if dnew not in ftext:
            if dold in ftext:
                ftext = ftext.replace(dold, dnew)
                print("patched mGBA FindFeature.cmake: DISABLE_DEPS no longer blocks an explicit feature")
            else:
                print("NOTE: FindFeature.cmake DISABLE_DEPS block not found; leaving it alone")

        # (3) find_package() inside a function only sets the upper-case
        #     LUA_FOUND, so the lower-case check never succeeded and the
        #     feature was silently disabled.
        fold = '\t\tforeach(REQUIRE ${NAMELIST})\n\t\t\tif(NOT ${REQUIRE}_FOUND)\n\t\t\t\tfind_package(${REQUIRE} ${FIND_VERSION} QUIET)\n\t\t\t\tif(NOT ${REQUIRE}_FOUND)\n\t\t\t\t\tpkg_search_module(${REQUIRE} "${REQUIRE}${PKG_CONFIG_VERSION_CHECK}")\n\t\t\t\tendif()\n\t\t\tendif()\n\t\t\tif(${REQUIRE}_FOUND)\n\t\t\t\tstring(TOUPPER ${REQUIRE} UREQUIRE)'
        fnew = '\t\tforeach(REQUIRE ${NAMELIST})\n\t\t\tstring(TOUPPER ${REQUIRE} UREQUIRE)\n\t\t\tif(NOT ${REQUIRE}_FOUND AND NOT ${UREQUIRE}_FOUND)\n\t\t\t\tfind_package(${REQUIRE} ${FIND_VERSION} QUIET)\n\t\t\t\tif(NOT ${REQUIRE}_FOUND AND NOT ${UREQUIRE}_FOUND)\n\t\t\t\t\tpkg_search_module(${REQUIRE} "${REQUIRE}${PKG_CONFIG_VERSION_CHECK}")\n\t\t\t\tendif()\n\t\t\tendif()\n\t\t\tif(${REQUIRE}_FOUND OR ${UREQUIRE}_FOUND)'
        if fnew not in ftext:
            if fold in ftext:
                ftext = ftext.replace(fold, fnew)
                print("patched mGBA FindFeature.cmake for the upper-case _FOUND variable")
            else:
                print("NOTE: FindFeature.cmake block not found; leaving it alone")
        else:
            print("mGBA FindFeature.cmake already patched")
        feature.write_text(ftext, encoding="utf-8", newline="")

        # (4) PNG and ZLIB must survive the DISABLE_DEPS block: the probe's
        #     `shot` command writes PNG through mCoreTakeScreenshotVF().
        #     Patch the block by shape, not by literal text -- the set of
        #     features it disables differs between mGBA releases.
        ctext = cmake.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"if\(DISABLE_DEPS\)\n(.*?)\nendif\(\)", ctext, re.S)
        if match:
            body = match.group(1)
            new_body = body
            for name in ("USE_PNG", "USE_ZLIB"):
                needle = f"\tset({name} OFF)"
                guard = f"\tif(NOT {name})\n\t\tset({name} OFF)\n\tendif()"
                if needle in new_body:
                    new_body = new_body.replace(needle, guard)
            if new_body != body:
                ctext = ctext[:match.start(1)] + new_body + ctext[match.end(1):]
                cmake.write_text(ctext, encoding="utf-8", newline="")
                print("patched mGBA CMakeLists: PNG/ZLIB survive DISABLE_DEPS when requested")
        else:
            print("NOTE: mGBA DISABLE_DEPS block not found; leaving it alone")


def build_mgba() -> int:
    if not MGBA_SRC.exists():
        print(f"ERR mGBA source missing: {MGBA_SRC}")
        return 1
    if not CMAKE.exists():
        print(f"ERR cmake missing: {CMAKE}")
        return 1
    check_mgba_commit()
    if LUA_LIB.is_file() and (LUA_SRC / "lua.h").is_file():
        patch_mgba_for_lua()
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
    # M_CORE_GBA is mandatory.  USE_DEBUGGERS used to be optional (mGBA 0.10.x
    # built the debugger only when it was asked for); from the 0.11 development
    # line onwards the debugger is part of the core and the define is gone.
    if "M_CORE_GBA" not in defines:
        raise SystemExit(
            "ERR M_CORE_GBA missing from the mGBA defines - the host would "
            "not match the library's ABI")
    if "USE_DEBUGGERS" not in defines:
        print("NOTE: the library has no USE_DEBUGGERS define; in this mGBA "
              "revision the debugger is part of the core")
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
    ]
    if "USE_LUA" in defines:
        compile_cmd.append(f"/I{LUA_SRC}")
    compile_cmd += ["/c", str(HERE / "host_main.c"), f"/Fo{obj}"]
    if run(compile_cmd, env=env) != 0:
        return 1
    link_cmd = [
        link, "/nologo", f"/OUT:{exe}", f"/MAP:{OUT_DIR / 'mgba-probe.map'}",
        str(obj), str(MGBA_LIB),
    ]
    if "USE_LUA" in defines:
        link_cmd.append(str(LUA_LIB))
    # mGBA's PNG/ZLIB support is compiled into mgba.lib but the actual
    # implementations live in these vendored static libraries.  Without them
    # the link fails on png_create_info_struct / deflate.
    for extra in (MGBA_BUILD / "libpng" / "Release" / "libpng16_static.lib",
                  MGBA_BUILD / "zlib" / "Release" / "zlibstatic.lib"):
        if extra.is_file():
            link_cmd.append(str(extra))
    link_cmd += MGBA_SYSTEM_LIBS
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
