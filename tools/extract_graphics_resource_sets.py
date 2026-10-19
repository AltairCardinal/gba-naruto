#!/usr/bin/env python3
"""Compatibility wrapper for the corrected audio resource-set extractor.

The old filename is retained so existing commands fail neither silently nor by
import error. New code must use :mod:`extract_audio_resource_sets`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from tools.extract_audio_resource_sets import extract
except ImportError:
    from extract_audio_resource_sets import extract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = extract(args.rom.read_bytes())
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
