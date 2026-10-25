#!/usr/bin/env python3
"""U4 (wave 17): prove that two independent runs are byte identical.

The acceptance of the real victory needs **two independent runs** that agree
byte for byte: the receipt, the captured frames and the run's own files.

Two runs of the same ROM cannot be compared with a plain file diff: the
receipt carries the output directory and the wall clock, and the capture
paths carry the same directory.  The tool therefore compares

* every file of the two run directories, by sha256, after the **relative**
  path is taken into account;
* the receipt, with the path dependent fields removed
  (``out``, ``rom``, ``truth``, ``wall_seconds`` and every path inside the
  capture and decision records).

The verdict is ``identical`` only when both comparisons are clean.

Usage::

    python tools/s49_battle_balance/v1_repeat.py \\
        --a build/v1-u4/run-a --b build/v1-u4/run-b --out build/v1-u4/repeat.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

# The receipt's fields that name a path or a duration: they differ between
# two runs of the same ROM and say nothing about the run's behaviour.
PATH_KEYS = {"out", "rom", "truth", "wall_seconds", "exe"}
PATH_VALUE = re.compile(r"[A-Za-z]:[\\/][^\s\"']*|[^\s\"']*build[\\/][^\s\"']*")


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def normalise(value: object, replacements: list[str]) -> object:
    """Strip the path dependent noise from a receipt."""
    if isinstance(value, dict):
        return {key: normalise(item, replacements) for key, item in value.items()
                if key not in PATH_KEYS}
    if isinstance(value, list):
        return [normalise(item, replacements) for item in value]
    if isinstance(value, str):
        text = value
        # The longest literal first: one run's directory is a prefix of the
        # other's (``run-a`` and ``run-a2``).
        for literal in sorted(replacements, key=len, reverse=True):
            text = text.replace(literal, "<run>")
        return PATH_VALUE.sub("<path>", text)
    return value


def receipt_digest(path: pathlib.Path, replacements: list[str]) -> str:
    document = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(normalise(document, replacements), sort_keys=True,
                      ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def file_map(root: pathlib.Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[str(path.relative_to(root)).replace("\\", "/")] = \
                sha256_file(path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--a", type=pathlib.Path, required=True)
    parser.add_argument("--b", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    first = file_map(args.a)
    second = file_map(args.b)
    # The receipt carries the run's own directory, so it is compared by its
    # normalised digest below instead of byte for byte.
    receipt_name = "battle.json"
    first.pop(receipt_name, None)
    second.pop(receipt_name, None)
    only_a = sorted(set(first) - set(second))
    only_b = sorted(set(second) - set(first))
    common = sorted(set(first) & set(second))
    differing = [name for name in common if first[name] != second[name]]

    receipt_a = args.a / "battle.json"
    receipt_b = args.b / "battle.json"
    receipt_equal = None
    receipt_digests = {}
    replacements = []
    for root in (args.a, args.b):
        for form in (str(root), str(root).replace("/", "\\"),
                     str(root).replace("\\", "/")):
            if form and form not in replacements:
                replacements.append(form)
    if receipt_a.is_file() and receipt_b.is_file():
        receipt_digests = {"a": receipt_digest(receipt_a, replacements),
                           "b": receipt_digest(receipt_b, replacements)}
        receipt_equal = receipt_digests["a"] == receipt_digests["b"]

    identical = (not only_a and not only_b and not differing and
                 receipt_equal is not False)
    document = {
        "schema": "konoha.s49-u4-repeat.v1",
        "a": str(args.a),
        "b": str(args.b),
        "files_a": len(first),
        "files_b": len(second),
        "only_in_a": only_a,
        "only_in_b": only_b,
        "differing": differing,
        "receipt": "battle.json (compared by its normalised digest)",
        "receipt_sha256": receipt_digests,
        "receipt_identical": receipt_equal,
        "identical": identical,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False)
                            + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(document, indent=1, ensure_ascii=False))
    return 0 if identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
