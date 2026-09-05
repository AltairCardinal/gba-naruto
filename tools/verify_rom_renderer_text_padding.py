#!/usr/bin/env python3
"""Rebuild exact zero gaps between records owned by the same renderer table."""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD = Path("artifacts/rom-renderer-text-inventory-v1/renderer-text-inventory.json")
PAYLOAD_SHA256 = "75be06e4b1c38d81d9a229dd1134177709706aa470a3d533bef07253079bfdbb"

def _sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()

def rebuild_renderer_text_padding(root: Path, rom: bytes) -> dict[str, Any]:
    ranges = []; errors = []
    try:
        root = Path(root).resolve(strict=True)
        if len(rom) != 6_291_456 or _sha(rom) != ROM_SHA256: raise ValueError("ROM identity changed")
        raw = (root / PAYLOAD).read_bytes()
        if _sha(raw) != PAYLOAD_SHA256: raise ValueError("renderer payload identity changed")
        payload = json.loads(raw); records = payload["records"]
        for left, right in zip(records, records[1:]):
            if left["candidate_ids"] != right["candidate_ids"]: continue
            start, end = left["range"][1], right["range"][0]
            if start >= end: continue
            gap = rom[start:end]
            if any(gap): continue
            ranges.append({"range": [start,end], "size": end-start, "bytes_sha256": _sha(gap), "candidate_ids": left["candidate_ids"]})
        if len(ranges) != 548 or sum(x["size"] for x in ranges) != 12_431:
            raise ValueError("renderer zero-gap denominator changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {"schema": "rom-renderer-text-padding-verification-v1", "verified": not errors, "errors": errors, "padding_range_count": len(ranges), "padding_bytes": sum(x["size"] for x in ranges), "zero_byte_count": sum(x["size"] for x in ranges), "ranges": ranges}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    rom_path = args.rom if args.rom.is_absolute() else root / args.rom
    report = rebuild_renderer_text_padding(root, rom_path.read_bytes())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
