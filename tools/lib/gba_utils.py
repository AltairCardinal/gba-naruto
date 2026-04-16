"""Shared GBA utility functions."""
from __future__ import annotations

import json
from pathlib import Path


def parse_int(value: str) -> int:
    """Parse a string as an integer (handles 0x hex, decimal, etc.)."""
    return int(value, 0)


def read_u32_le(buf: bytes, offset: int) -> int:
    """Read a little-endian u32 from a buffer at the given offset."""
    return int.from_bytes(buf[offset : offset + 4], "little")


def load_json(path: Path) -> dict:
    """Load a JSON file as UTF-8 text."""
    return json.loads(path.read_text(encoding="utf-8"))
