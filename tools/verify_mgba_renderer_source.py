#!/usr/bin/env python3
"""Verify the pinned mGBA software-renderer source used by screenshot goldens."""

from __future__ import annotations

import argparse
import hashlib
import json
from urllib.request import urlopen


MGBA_COMMIT = "1d65391d3531f9338300f306c4e1d76c258ce657"
SOURCE_PATH = "src/gba/renderers/software-private.h"
SOURCE_SHA256 = "7bd0201cbd81aa74186121c91bf830ff3e33591a241f5ac5dd66d4842fe7b3aa"
SOURCE_URL = (
    f"https://raw.githubusercontent.com/mgba-emu/mgba/"
    f"{MGBA_COMMIT}/{SOURCE_PATH}"
)
REQUIRED_FRAGMENTS = (
    b"static inline unsigned _brighten(unsigned color, int y)",
    b"static inline unsigned _darken(unsigned color, int y)",
    b"a = color & 0xFF;",
    b"a = color & 0xFF00;",
    b"a = color & 0xFF0000;",
    b"c |= (a - (a * y) / 16) & 0xFF;",
    b"c |= (a - (a * y) / 16) & 0xFF00;",
    b"c |= (a - (a * y) / 16) & 0xFF0000;",
)


def verify_source(source: bytes) -> dict[str, object]:
    errors = []
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != SOURCE_SHA256:
        errors.append("software-private.h SHA-256 mismatch")
    for fragment in REQUIRED_FRAGMENTS:
        if fragment not in source:
            errors.append(f"missing source fragment: {fragment.decode()}")
    return {
        "schema": "mgba-renderer-source-verification-v1",
        "verified": not errors,
        "commit": MGBA_COMMIT,
        "path": SOURCE_PATH,
        "url": SOURCE_URL,
        "expected_sha256": SOURCE_SHA256,
        "actual_sha256": actual_sha256,
        "packed_mcolor_fragments_verified": not errors,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    try:
        with urlopen(SOURCE_URL, timeout=args.timeout) as response:
            source = response.read()
        report = verify_source(source)
    except Exception as error:
        report = {
            "schema": "mgba-renderer-source-verification-v1",
            "verified": False,
            "commit": MGBA_COMMIT,
            "path": SOURCE_PATH,
            "url": SOURCE_URL,
            "expected_sha256": SOURCE_SHA256,
            "actual_sha256": None,
            "packed_mcolor_fragments_verified": False,
            "errors": [f"source fetch failed: {error}"],
        }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
