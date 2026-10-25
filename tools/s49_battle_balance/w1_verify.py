#!/usr/bin/env python3
"""W1 (wave 11): verify that two independent recordings are byte identical.

The remake ROM is deterministic, so the same ROM + the same boot prefix + the
same victory key script must produce exactly the same frames.  This tool
compares two run directories frame by frame and writes a machine readable
receipt (the same shape ``w4_verify.py`` uses for the original, minus the
``play.json`` statistics the remake recorder does not produce).

Usage::

    python tools/s49_battle_balance/w1_verify.py \\
        --a build/s49-battle-balance/w1/runA \\
        --b build/s49-battle-balance/w1/runB \\
        --out build/s49-battle-balance/w1/verify.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--a", type=pathlib.Path, required=True)
    parser.add_argument("--b", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)

    frames_a = sorted((args.a / "frames").glob("frame-*.png"))
    frames_b = sorted((args.b / "frames").glob("frame-*.png"))
    names_a = [path.name for path in frames_a]
    names_b = [path.name for path in frames_b]

    only_a = sorted(set(names_a) - set(names_b))
    only_b = sorted(set(names_b) - set(names_a))
    differing: list[str] = []
    for path_a, path_b in zip(frames_a, frames_b):
        if path_a.name != path_b.name:
            continue
        if sha256_file(path_a) != sha256_file(path_b):
            differing.append(path_a.name)

    record_a = json.loads((args.a / "record.json").read_text(encoding="utf-8"))
    record_b = json.loads((args.b / "record.json").read_text(encoding="utf-8"))

    receipt = {
        "schema": "konoha.s49-w1-verify.v1",
        "a": str(args.a),
        "b": str(args.b),
        "frames_a": len(frames_a),
        "frames_b": len(frames_b),
        "only_in_a": only_a[:20],
        "only_in_b": only_b[:20],
        "differing_frames": differing[:20],
        "differing_count": len(differing),
        "rom_sha256_a": record_a.get("rom_sha256"),
        "rom_sha256_b": record_b.get("rom_sha256"),
        "script_sha256_a": record_a.get("script_sha256"),
        "script_sha256_b": record_b.get("script_sha256"),
        "identical": (not only_a and not only_b and not differing
                      and record_a.get("rom_sha256") == record_b.get("rom_sha256")
                      and record_a.get("script_sha256")
                      == record_b.get("script_sha256")),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
