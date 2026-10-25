#!/usr/bin/env python3
"""W20-E2: list the files the E2 lane changed relative to the shared tree.

Only the source directories are compared (``game/include``, ``game/src``,
``game/tests``) plus the build products.  ``graphics/`` is a 1852-file
asset tree that the lane copies verbatim, so comparing it buys nothing.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

LANE = pathlib.Path(r"D:\Github\gba-naruto\build\w20-e2\butano-sequel")
SHARED = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel"
)
SUBDIRS = ("game/include", "game/src", "game/tests")


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    identical = 0
    different: list[tuple[str, str, str]] = []
    lane_only: list[str] = []
    shared_only: list[str] = []

    for subdir in SUBDIRS:
        lane_files = {
            str(p.relative_to(LANE)).replace("\\", "/"): p
            for p in (LANE / subdir).rglob("*")
            if p.is_file()
        }
        shared_files = {
            str(p.relative_to(SHARED)).replace("\\", "/"): p
            for p in (SHARED / subdir).rglob("*")
            if p.is_file()
        }
        for key in sorted(set(lane_files) | set(shared_files)):
            if key not in shared_files:
                lane_only.append(key)
            elif key not in lane_files:
                shared_only.append(key)
            else:
                if sha256(lane_files[key]) == sha256(shared_files[key]):
                    identical += 1
                else:
                    different.append(
                        (key, sha256(lane_files[key])[:16], sha256(shared_files[key])[:16])
                    )

    print(f"identical source files : {identical}")
    print(f"DIFFERENT              : {len(different)}")
    for key, lane_hash, shared_hash in different:
        print(f"    {key}\n        lane  {lane_hash}\n        shared {shared_hash}")
    print(f"lane-only              : {len(lane_only)} {lane_only}")
    print(f"shared-only            : {len(shared_only)} {shared_only}")

    for name in ("butano-sequel.gba", "butano-sequel.elf"):
        lane_path = LANE / name
        shared_path = SHARED / name
        if lane_path.is_file() and shared_path.is_file():
            print(f"{name}: lane {sha256(lane_path)[:16]} "
                  f"shared {sha256(shared_path)[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
