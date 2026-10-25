#!/usr/bin/env python3
"""Wave 18 lane integration helper.

Every wave-18 stream worked inside its own isolated copy of the remake tree
(see notes/s49-fidelity/WAVE18-TASKS.md section 0.4) so that concurrent builds
could not overwrite each other's .gba.  At the end of the wave the parent has
to copy every stream's **owned** files back into the shared tree, build once,
and run the 12 step package pipeline.

This script does the copy deterministically and -- more importantly -- it
*detects* a stream that touched a file it does not own, which is exactly the
class of mistake that silently corrupts a wave.

Usage:
    python tools/s49_wave18/integrate.py                 # report only
    python tools/s49_wave18/integrate.py --apply         # copy owned files back
    python tools/s49_wave18/integrate.py --apply --lane w18-w1

Exit codes:
    0  ok
    2  an out-of-lane modification was detected (with --apply the copy is
       refused for that lane, because the parent has to decide first)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

SKIP_DIRS = {"build", ".git", "third_party"}
SKIP_SUFFIXES = {".gba", ".elf", ".o", ".s", ".bin", ".map"}
TEXT_SUFFIXES = {".h", ".hpp", ".cpp", ".c", ".cc", ".json", ".py", ".md", ".sh", ".json"}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_files(root: str) -> set[str]:
    out: set[str] = set()
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1].lower() in SKIP_SUFFIXES:
                continue
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            # graphics/audio are symlinks into the shared tree on purpose
            if rel.startswith("graphics/") or rel.startswith("audio/"):
                continue
            out.add(rel)
    return out


def load_manifest(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def describe(delta: str, shared: str, lane: str) -> str:
    if delta == "missing-in-lane":
        return "MISSING in lane copy"
    if delta == "missing-in-shared":
        return "NEW file (lane only)"
    if shared == lane:
        return "unchanged"
    return "CHANGED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "lanes.json"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--lane", default=None)
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help=(
            "relative path to exclude from the out-of-lane check.  Use it for "
            "files the parent has already moved into the shared tree from "
            "another lane: the other lane's copy still holds the old bytes, "
            "which would otherwise look like an out-of-lane edit."
        ),
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    shared_root = manifest["shared_tree"]
    lane_root = manifest["lane_root"]

    if not os.path.isdir(shared_root):
        print(f"shared tree not found: {shared_root}", file=sys.stderr)
        return 2

    lanes = manifest["lanes"]
    if args.lane:
        if args.lane not in lanes:
            print(f"unknown lane: {args.lane}", file=sys.stderr)
            return 2
        lanes = {args.lane: lanes[args.lane]}

    shared_files = rel_files(shared_root)
    parent_owned = set(manifest.get("parent_owned", []))
    # an --ignore entry matches the file itself or anything under it
    ignored = tuple(args.ignore) + tuple(manifest.get("ignore", []))

    def is_ignored(rel: str) -> bool:
        return any(rel == ig or rel.startswith(ig.rstrip("/") + "/") for ig in ignored)

    out_of_lane_total = 0
    copied = 0

    for lane_name, spec in lanes.items():
        lane_proj = os.path.join(lane_root, lane_name, "butano-sequel")
        print(f"\n=== {lane_name} ({spec.get('topic', '?')}) ===")
        if not os.path.isdir(lane_proj):
            print(f"  lane copy missing: {lane_proj}")
            out_of_lane_total += 1
            continue

        owned = set(spec["owned"])
        lane_files = rel_files(lane_proj)

        # 1. the owned files: what actually changed?
        changed = []
        for rel in sorted(owned):
            lane_file = os.path.join(lane_proj, rel)
            shared_file = os.path.join(shared_root, rel)
            if not os.path.exists(lane_file):
                print(f"  [owned] {rel}: MISSING in lane copy")
                continue
            if not os.path.exists(shared_file):
                print(f"  [owned] {rel}: NEW (not in shared tree yet)")
                changed.append((rel, "missing-in-shared"))
                continue
            a = sha256(shared_file)
            b = sha256(lane_file)
            if a == b:
                print(f"  [owned] {rel}: unchanged")
            else:
                print(f"  [owned] {rel}: CHANGED  {a[:12]} -> {b[:12]}")
                changed.append((rel, "changed"))

        # 2. everything else the lane touched: that is a boundary violation
        touched = sorted((lane_files & shared_files) - owned)
        extra = sorted(lane_files - shared_files)
        violations = []
        for rel in touched:
            if rel in parent_owned or is_ignored(rel):
                # the parent edits these directly in the shared tree (the
                # wave 18 ratchet red fix); the lane copies are stale copies
                # of them and the shared tree is authoritative.
                continue
            a = sha256(os.path.join(shared_root, rel))
            b = sha256(os.path.join(lane_proj, rel))
            if a != b:
                violations.append(rel)
        for rel in extra:
            if rel in parent_owned or is_ignored(rel):
                continue
            # ⭐ 2026-10-25 (wave 20): a file the lane **owns** but that does
            # not exist in the shared tree yet is a legitimate NEW deliverable
            # (a new test, a new header), not a boundary violation.  Flagging
            # it used to refuse the whole lane for doing exactly what its
            # task book asked.
            if rel in owned:
                continue
            violations.append(rel + " (new file)")

        if violations:
            print(f"  [OUT-OF-LANE] {len(violations)} file(s) outside the manifest:")
            for rel in violations[:40]:
                print(f"      - {rel}")
            if len(violations) > 40:
                print(f"      ... and {len(violations) - 40} more")
            out_of_lane_total += len(violations)
        else:
            print("  [OUT-OF-LANE] none")

        if args.apply:
            if violations:
                print(f"  -> refused to apply {lane_name}: out-of-lane files need a decision")
                continue
            for rel, _kind in changed:
                src = os.path.join(lane_proj, rel)
                dst = os.path.join(shared_root, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  -> applied {rel}  sha256={sha256(dst)[:16]}")
                copied += 1

    if args.apply:
        print(f"\napplied {copied} file(s)")
    if out_of_lane_total:
        print(f"\nout-of-lane modifications: {out_of_lane_total}")
        return 2
    print("\nno out-of-lane modifications")
    return 0


if __name__ == "__main__":
    sys.exit(main())
