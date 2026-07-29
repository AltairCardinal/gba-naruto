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
SOURCES = (
    {
        "path": SOURCE_PATH,
        "sha256": SOURCE_SHA256,
        "fragments": REQUIRED_FRAGMENTS,
        "role": "packed-mcolor-effects",
    },
    {
        "path": "src/gba/renderers/software-mode0.c",
        "sha256": "1e4104200fa1c068ff4ff17c24d8f99f9e1aed112d75e5088773e1bb6a318783",
        "fragments": (
            b"background->mosaic && GBAMosaicControlGetBgH(renderer->mosaic)",
            b"int mosaicH = GBAMosaicControlGetBgH(renderer->mosaic) + 1;",
            b"y -= y % mosaicV;",
        ),
        "role": "mode0-text-bg-mosaic",
    },
    {
        "path": "src/gba/renderers/software-obj.c",
        "sha256": "b737ba2372054156fd987f95ed9350e3370f469cb38b40367657c70c02667fe9",
        "fragments": (
            b"int localX = inX - xOffset * (outX % mosaicH);",
            b"if (outX % mosaicH == 0)",
            b"mosaicH = GBAMosaicControlGetObjH(renderer->mosaic) + 1;",
        ),
        "role": "normal-and-affine-obj-horizontal-mosaic",
    },
    {
        "path": "src/gba/renderers/video-software.c",
        "sha256": "39a03b64a3fe9ab384a17de7d92d215298e9f5b64415f7c550d33779c2bbaf70",
        "fragments": (
            b"int mosaicY = y - (y % mosaicV);",
            b"localY = sprite->y;",
            b"localY = sprite->endY - 1;",
        ),
        "role": "obj-vertical-mosaic",
    },
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


def verify_sources(sources: dict[str, bytes]) -> dict[str, object]:
    errors = []
    records = []
    for expected in SOURCES:
        path = expected["path"]
        source = sources.get(path)
        source_errors = []
        actual_sha256 = None
        if source is None:
            source_errors.append("source missing")
        else:
            actual_sha256 = hashlib.sha256(source).hexdigest()
            if actual_sha256 != expected["sha256"]:
                source_errors.append("SHA-256 mismatch")
            for fragment in expected["fragments"]:
                if fragment not in source:
                    source_errors.append(
                        f"missing source fragment: {fragment.decode()}"
                    )
        errors.extend(f"{path}: {error}" for error in source_errors)
        records.append(
            {
                "path": path,
                "url": (
                    "https://raw.githubusercontent.com/mgba-emu/mgba/"
                    f"{MGBA_COMMIT}/{path}"
                ),
                "role": expected["role"],
                "expected_sha256": expected["sha256"],
                "actual_sha256": actual_sha256,
                "fragments_verified": not source_errors,
                "errors": source_errors,
            }
        )
    return {
        "schema": "mgba-renderer-source-verification-v2",
        "verified": not errors,
        "commit": MGBA_COMMIT,
        "sources": records,
        "packed_mcolor_fragments_verified": not records[0]["errors"],
        "mosaic_fragments_verified": not any(
            record["errors"] for record in records[1:]
        ),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    try:
        sources = {}
        for expected in SOURCES:
            path = expected["path"]
            url = (
                "https://raw.githubusercontent.com/mgba-emu/mgba/"
                f"{MGBA_COMMIT}/{path}"
            )
            with urlopen(url, timeout=args.timeout) as response:
                sources[path] = response.read()
        report = verify_sources(sources)
    except Exception as error:
        report = {
            "schema": "mgba-renderer-source-verification-v2",
            "verified": False,
            "commit": MGBA_COMMIT,
            "sources": [],
            "packed_mcolor_fragments_verified": False,
            "mosaic_fragments_verified": False,
            "errors": [f"source fetch failed: {error}"],
        }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
