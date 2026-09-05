#!/usr/bin/env python3
"""Verify zero gaps between adjacent records of the same fixed consumer table."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD = Path(
    "artifacts/rom-fixed-consumer-text-inventory-v1/"
    "fixed-consumer-text-inventory.json"
)
PAYLOAD_SHA256 = "fd73b9dedf34aee5a4537c451f30d8479dd43f849dfb3ab81c18360a0883e461"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _table_ids(record: dict[str, Any]) -> set[str]:
    sources = record["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("fixed-consumer record sources changed")
    result = set()
    for source in sources:
        table_id = source["table_id"]
        if not isinstance(table_id, str) or not table_id:
            raise ValueError("fixed-consumer table id changed")
        result.add(table_id)
    return result


def rebuild_fixed_consumer_text_padding(
    root: Path, rom: bytes
) -> dict[str, Any]:
    ranges: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        root = Path(root).resolve(strict=True)
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("ROM identity changed")
        raw = (root / PAYLOAD).read_bytes()
        if _sha(raw) != PAYLOAD_SHA256:
            raise ValueError("fixed-consumer payload identity changed")
        payload = json.loads(raw)
        records = payload["records"]
        if not isinstance(records, list) or len(records) != 735:
            raise ValueError("fixed-consumer record denominator changed")

        for left, right in zip(records, records[1:]):
            shared_tables = sorted(_table_ids(left) & _table_ids(right))
            if not shared_tables:
                continue
            start = left["range"][1]
            end = right["range"][0]
            if not isinstance(start, int) or not isinstance(end, int):
                raise ValueError("fixed-consumer record range changed")
            if start >= end:
                continue
            gap = rom[start:end]
            if any(gap):
                continue
            ranges.append(
                {
                    "range": [start, end],
                    "size": end - start,
                    "bytes_sha256": _sha(gap),
                    "table_ids": shared_tables,
                }
            )

        if len(ranges) != 590 or sum(item["size"] for item in ranges) != 6_738:
            raise ValueError("fixed-consumer zero-gap denominator changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))

    padding_bytes = sum(item["size"] for item in ranges)
    return {
        "schema": "rom-fixed-consumer-text-padding-verification-v1",
        "verified": not errors,
        "errors": errors,
        "padding_range_count": len(ranges),
        "padding_bytes": padding_bytes,
        "zero_byte_count": padding_bytes,
        "ranges": ranges,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--rom", type=Path, default=ROM_PATH)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    rom_path = args.rom if args.rom.is_absolute() else root / args.rom
    report = rebuild_fixed_consumer_text_padding(root, rom_path.read_bytes())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
