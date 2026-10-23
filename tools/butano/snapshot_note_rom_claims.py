#!/usr/bin/env python3
"""Pin the ROM bytes that the open notes claim about.

``docs/butano-wiring-roadmap.md`` (W5) wants the notes that already state a
verifiable conclusion about the original turned into gates.  332 of them are in
the ``needs_guard`` bucket, and the notes index records how many ROM addresses
each of them cites -- 1,992 in total.

A semantic gate ("this instruction is a ``mov``") has to be written per note.
A **byte-level** gate does not: if a note says "at 0x0809AE76 ...", then the
bytes at that address are part of what the note claims, and they can be pinned
against the base ROM.

This tool does exactly that and no more:

* it extracts the same addresses the notes index counts
  (``0x[0-9A-Fa-f]{4,}``);
* an address inside the cartridge window (0x08000000..0x09FFFFFF) is pinned to
  the four bytes the base ROM holds there;
* every other address is **listed, not pinned** -- it belongs to EWRAM, PRAM
  or I/O, which the base ROM does not contain, and pretending otherwise would
  be a lie;
* the pins live in a fixture, and the gate re-derives them, so a note edit
  or a ROM change is reported by note and address.

Usage::

    python3 tools/butano/snapshot_note_rom_claims.py \\
        --root . \\
        --out-dir artifacts/butano-note-rom-claims-v1
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

RECEIPT_SCHEMA = "konoha.butano-note-rom-claims.v1"

EXIT_OK = 0
EXIT_INPUT_ERROR = 2

#: The same address rule the notes index uses to count a note's ROM evidence.
ADDR_RE = re.compile(r"0x[0-9A-Fa-f]{4,}")

#: The cartridge window: the GBA ROM is mapped at 0x08000000.
ROM_BASE = 0x08000000
ROM_LIMIT = 0x0A000000
PIN_BYTES = 4


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_claims(
    root: Path,
    index: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Every address the open notes cite, split into pinnable and not."""
    rom = (root / "rom" / "base.gba").read_bytes()
    pinnable: list[dict[str, Any]] = []
    not_pinnable: list[dict[str, Any]] = []
    counts = {"notes": 0, "addresses": 0, "pinnable": 0, "not_pinnable": 0}
    for note in index.get("notes") or []:
        if note.get("bucket") != "needs_guard":
            continue
        counts["notes"] += 1
        path = root / str(note.get("path") or "")
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        seen: set[int] = set()
        for match in ADDR_RE.finditer(text):
            try:
                address = int(match.group(0), 16)
            except ValueError:
                continue
            if address in seen:
                continue
            seen.add(address)
            counts["addresses"] += 1
            if ROM_BASE <= address < ROM_LIMIT:
                offset = address - ROM_BASE
                if offset + PIN_BYTES > len(rom):
                    counts["not_pinnable"] += 1
                    not_pinnable.append(
                        {
                            "note": note.get("id"),
                            "address": match.group(0),
                            "reason": "the address is past the end of the base ROM",
                        }
                    )
                    continue
                counts["pinnable"] += 1
                pinnable.append(
                    {
                        "note": note.get("id"),
                        "path": note.get("path"),
                        "address": match.group(0),
                        "offset": offset,
                        "bytes": rom[offset : offset + PIN_BYTES].hex(),
                    }
                )
            else:
                counts["not_pinnable"] += 1
                not_pinnable.append(
                    {
                        "note": note.get("id"),
                        "address": match.group(0),
                        "reason": "not a cartridge address (EWRAM/PRAM/IO)",
                    }
                )
    return pinnable, not_pinnable, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--index",
        type=Path,
        default=Path("artifacts/reverse-notes-index-v1/notes-index.json"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/butano-note-rom-claims-v1"),
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    index_path = args.index if args.index.is_absolute() else root / args.index
    if not index_path.is_file():
        print(f"missing notes index: {index_path}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    index = json.loads(index_path.read_text(encoding="utf-8"))
    pinnable, not_pinnable, counts = collect_claims(root, index)
    rom_path = root / "rom" / "base.gba"
    payload = {
        "schema": RECEIPT_SCHEMA,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "rom_sha256": sha256_file(rom_path),
        "rom_base": ROM_BASE,
        "pin_bytes": PIN_BYTES,
        "summary": counts,
        "claims": pinnable,
        "not_pinnable": not_pinnable,
    }
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "claims.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 未转门禁 note 的 ROM 字节钉点（自动生成）",
        "",
        "本文件由 `tools/butano/snapshot_note_rom_claims.py` 生成，不要手工编辑。",
        "",
        "| 项 | 值 |",
        "| --- | ---: |",
    ]
    for key, value in counts.items():
        lines.append(f"| {key} | {value} |")
    lines += [
        "",
        "> 这是**字节级**钉点，不是语义门禁：它保证 note 引用的那些地址上的 ROM 字节没变，",
        "> 但不证明 note 关于这些字节的**解读**仍成立。",
        f"> 非卡带地址（EWRAM/PRAM/IO）共 {len(not_pinnable)} 处，**只列不钉**。",
        "",
    ]
    (out_dir / "claims.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
