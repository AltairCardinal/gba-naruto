#!/usr/bin/env python3
"""Answer "where did this content bank come from?" for every content bank.

``docs/butano-wiring-roadmap.md`` (W3, action 2) asks that the 34 content
banks can each answer *which reverse family / which note* they came from, so
that the sink side stops being a gray zone.

Four different ways of answering it were measured, and only two of them hold
up:

* the reverse families' manifests do **not** carry the content banks' table
  addresses (address matching resolves 2 of 34, and both point at the same
  family, so it is not trustworthy);
* the notes index does not disambiguate either (a note-address search hits
  16 to 33 notes per bank).

What does hold up is per bank:

``reverse_family``
    the reverse family whose manifest declares **the same** table address
    (``source_table.gba_address``) -- an exact, checkable match;
``reverse_evidence``
    the note the bank itself cites;
``extractor``
    the tool that produced the bank -- for most banks the honest answer is
    "extracted straight from the ROM by this tree", and saying so is better
    than inventing a family.

Every bank therefore gets a ``_provenance`` block that answers the question
with what is actually known, and says so explicitly when nothing is.

The tool is idempotent: it rewrites the same bytes on a second run.

Usage::

    python3 tools/butano/annotate_content_bank_provenance.py \\
        --root . \\
        --reverse-root /Users/altair/github/gba-naruto-reverse \\
        --out-dir artifacts/butano-content-bank-provenance-v1
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

RECEIPT_SCHEMA = "konoha.butano-content-bank-provenance.v1"

EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_UNATTRIBUTED = 3

#: A note cited by a bank's own text, e.g. ``notes/evidence/x.md``.
_NOTE_RE = re.compile(r"notes/[A-Za-z0-9_./-]+\.md")

#: The key the block is stored under.
PROVENANCE_KEY = "_provenance"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def family_table_addresses(
    reverse_root: Path,
) -> dict[int, list[str]]:
    """The table addresses the reverse families declare in their manifests."""
    by_address: dict[int, list[str]] = {}
    for manifest_path in sorted((reverse_root / "artifacts").glob("*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        source_table = manifest.get("source_table")
        if not isinstance(source_table, dict):
            continue
        for key in ("gba_address", "file_offset", "offset"):
            value = source_table.get(key)
            address: int | None = None
            if isinstance(value, str) and value.lower().startswith("0x"):
                try:
                    address = int(value, 16)
                except ValueError:
                    address = None
            elif isinstance(value, int) and not isinstance(value, bool):
                address = value
            if address is not None:
                by_address.setdefault(address, []).append(manifest_path.parent.name)
    return by_address


def build_provenance(
    bank: dict[str, Any],
    root: Path,
    reverse_root: Path,
    by_address: dict[int, list[str]],
) -> dict[str, Any]:
    """The provenance block for one content bank."""
    offset = bank.get("table_offset")
    entry_count = bank.get("entry_count")
    entry_size = bank.get("entry_size")
    size = None
    if (
        isinstance(offset, int)
        and isinstance(entry_count, int)
        and isinstance(entry_size, int)
    ):
        size = entry_count * entry_size

    families = sorted(set(by_address.get(offset, []))) if isinstance(offset, int) else []
    notes = sorted(set(_NOTE_RE.findall(json.dumps(bank, ensure_ascii=False))))
    notes = [note for note in notes if (root / note).is_file()]

    extraction = bank.get("extraction")
    extractor = None
    if isinstance(extraction, dict):
        value = extraction.get("tool")
        if isinstance(value, str) and value:
            extractor = value

    if len(families) == 1:
        family = families[0]
        family_state = "unique"
    elif len(families) > 1:
        family = None
        family_state = "ambiguous"
    else:
        family = None
        family_state = "none"

    if family:
        reason = None
    elif family_state == "ambiguous":
        reason = (
            "several reverse families declare the same table address "
            f"({', '.join(families)}); the bank is not attributed to any one "
            "of them"
        )
    elif notes:
        reason = (
            "no reverse family declares this table's address; the bank's "
            f"provenance rests on its own note ({', '.join(notes)})"
        )
    elif extractor:
        reason = (
            "the table was extracted straight from the ROM by "
            f"{extractor}; no reverse family and no note claims it"
        )
    else:
        reason = (
            "the table's bytes come from the base ROM at offset "
            f"{offset} (size {size}); the bank records neither a reverse "
            "family, a note nor an extracting tool, so no further source is "
            "known"
        )

    return {
        "rom": {
            "sha256": sha256_file(root / "rom" / "base.gba"),
            "offset": offset,
            "size": size,
            "entry_count": entry_count,
            "entry_size": entry_size,
        },
        "extractor": extractor,
        "reverse_family": family,
        "reverse_family_candidates": families,
        "reverse_family_state": family_state,
        "reverse_evidence": notes,
        "unattributed_reason": reason,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--reverse-root",
        type=Path,
        default=Path("/Users/altair/github/gba-naruto-reverse"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/butano-content-bank-provenance-v1"),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the blocks instead of writing them",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    reverse_root = args.reverse_root.resolve()
    content_root = root / "sequel" / "content"
    if not content_root.is_dir():
        print(f"missing content root: {content_root}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    by_address = family_table_addresses(reverse_root)
    banks = sorted(content_root.glob("*/bank.json"))
    if not banks:
        print(f"no content banks under {content_root}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    rows: list[dict[str, Any]] = []
    unknown: list[str] = []
    for bank_path in banks:
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        expected = build_provenance(bank, root, reverse_root, by_address)
        relative = bank_path.relative_to(root).as_posix()
        if args.check:
            actual = bank.get(PROVENANCE_KEY)
            if actual != expected:
                print(f"PROBLEM: {relative} has no matching {PROVENANCE_KEY} block")
                return EXIT_UNATTRIBUTED
        else:
            bank[PROVENANCE_KEY] = expected
            bank_path.write_text(
                json.dumps(bank, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if expected["reverse_family"] is None and not expected["reverse_evidence"]:
            unknown.append(relative)
        rows.append(
            {
                "bank": relative,
                "reverse_family": expected["reverse_family"],
                "reverse_family_state": expected["reverse_family_state"],
                "reverse_evidence": expected["reverse_evidence"],
                "extractor": expected["extractor"],
                "rom_offset": expected["rom"]["offset"],
                "rom_size": expected["rom"]["size"],
                "unattributed_reason": expected["unattributed_reason"],
            }
        )

    summary = {
        "banks": len(rows),
        "with_reverse_family": sum(1 for r in rows if r["reverse_family"]),
        "with_reverse_evidence": sum(1 for r in rows if r["reverse_evidence"]),
        "with_extractor": sum(1 for r in rows if r["extractor"]),
        "without_any_source": len(unknown),
    }
    payload = {
        "schema": RECEIPT_SCHEMA,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mode": "check" if args.check else "write",
        "summary": summary,
        "rows": rows,
    }
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "provenance.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 内容库来源登记（自动生成）",
        "",
        "本文件由 `tools/butano/annotate_content_bank_provenance.py` 生成，"
        "不要手工编辑。",
        "",
        "| 项 | 值 |",
        "| --- | ---: |",
    ]
    for key, value in summary.items():
        lines.append(f"| {key} | {value} |")
    lines += ["", "| 内容库 | 逆向族 | note | 提取器 |", "| --- | --- | --- | --- |"]
    for row in rows:
        lines.append(
            f"| `{row['bank']}` | {row['reverse_family'] or '—'} | "
            f"{', '.join(row['reverse_evidence']) or '—'} | "
            f"{row['extractor'] or '—'} |"
        )
    lines.append("")
    (out_dir / "provenance.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
