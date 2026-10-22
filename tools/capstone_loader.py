"""Load capstone from wherever this machine actually has it.

Why this module exists
----------------------
The repository vendors capstone under `tools/_vendor/capstone`, but that
copy cannot load its native library on this Windows host (the wheel ships a
DLL that does not resolve from the vendored path).  A working copy lives in
`build/python-deps/capstone/capstone/lib/capstone.dll`, and the loader there
is found through `LIBCAPSTONE_PATH`.

So the lookup order is:

1. `LIBCAPSTONE_PATH` (explicit override),
2. `build/python-deps/**/capstone.dll` (the copy that works here),
3. `tools/_vendor` (the vendored wheel),
4. whatever is already importable.

Tools that need capstone should call `load_capstone()` instead of importing
it directly, otherwise they fail with
`ImportError: ERROR: fail to load the dynamic library.` on this host.

Usage:
    from capstone_loader import load_capstone
    capstone = load_capstone()
"""
from __future__ import annotations

import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]


def _candidate_dirs() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    env = os.environ.get("LIBCAPSTONE_PATH")
    if env:
        out.append(pathlib.Path(env))
    deps = REPO / "build" / "python-deps"
    if deps.exists():
        for dll in deps.rglob("capstone.dll"):
            out.append(dll.parent)
        for dll in deps.rglob("libcapstone.dll"):
            out.append(dll.parent)
    out.append(REPO / "tools" / "_vendor")
    return out


def load_capstone():
    """Import and return the capstone module, or raise SystemExit."""
    for cand in _candidate_dirs():
        if not cand.exists():
            continue
        if str(cand) not in sys.path:
            sys.path.insert(0, str(cand))
        os.environ.setdefault("LIBCAPSTONE_PATH", str(cand))
        try:
            import capstone  # noqa: F401
            return capstone
        except Exception:
            continue
    raise SystemExit(
        "capstone is unavailable: set LIBCAPSTONE_PATH to the folder that "
        "holds capstone.dll (see notes/windows-migration-20261020.md 2.2)"
    )
