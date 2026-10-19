#!/usr/bin/env python3
"""Read the original ROM's live unit pool out of an mGBA savestate.

The pool address, stride and field offsets come from the reverse-engineering
notes; `+0xCC` is the affiliation byte (0 = player, 1 = enemy) and `+0xC1` is the
"this unit is acting right now" marker. Reading them beats counting sprites on
screen, which only shows what the camera happens to frame.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

try:
    from tools.inspect_mgba_savestate import (
        GBA_STATE_SIZE,
        GbaState,
        _gbas_payload,
        _strict_zlib_decompress,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from inspect_mgba_savestate import (
        GBA_STATE_SIZE,
        GbaState,
        _gbas_payload,
        _strict_zlib_decompress,
    )

POOL_ADDRESS = 0x020240C0
POOL_STRIDE = 0x1D4
OFFSET_X = 0xC4
OFFSET_Y = 0xC5
OFFSET_BACKUP_X = 0xC7
OFFSET_BACKUP_Y = 0xC8
OFFSET_AFFILIATION = 0xCC
OFFSET_ACTING = 0xC1
SIDE_NAMES = {0: "player", 1: "enemy"}

# The action-order table the A-key handler walks. `0x030059B8` is a *pointer*
# array whose entries are in action order, NOT address order; dereferenced, the
# records are uniform 60-byte records starting at 0x030056AC. The count lives at
# ORDER_COUNT_ADDRESS. Which record field means what is not yet established, so
# the reader reports raw bytes rather than labels.
ORDER_POINTERS_ADDRESS = 0x030059B8
ORDER_POINTER_STRIDE = 4
ORDER_RECORD_SIZE = 0x3C
ORDER_COUNT_ADDRESS = 0x03005BB8



class PoolError(RuntimeError):
    """The savestate did not yield a trustworthy unit pool."""


def load_state(path: Path) -> GbaState:
    container = Path(path).read_bytes()
    return GbaState(
        _strict_zlib_decompress(
            _gbas_payload(container),
            expected_size=GBA_STATE_SIZE,
            label="savestate",
        )
    )


def read_pool(
    state: GbaState,
    pool_address: int = POOL_ADDRESS,
    stride: int = POOL_STRIDE,
    slots: int = 16,
) -> list[dict[str, object]]:
    """Return every populated slot, skipping all-zero records."""
    units: list[dict[str, object]] = []
    for slot in range(slots):
        record = state.read_memory(pool_address + slot * stride, stride)
        if not any(record):
            continue
        side = record[OFFSET_AFFILIATION]
        units.append(
            {
                "slot": slot,
                "acting": bool(record[OFFSET_ACTING]),
                "address": pool_address + slot * stride,
                "x": record[OFFSET_X],
                "y": record[OFFSET_Y],
                "backup_x": record[OFFSET_BACKUP_X],
                "backup_y": record[OFFSET_BACKUP_Y],
                "affiliation": side,
                "side": SIDE_NAMES.get(side, f"unknown-{side}"),
            }
        )
    return units


def read_action_order(state: GbaState) -> list[dict[str, object]]:
    """Dump the action-order table without inventing field semantics."""
    count = state.read_memory(ORDER_COUNT_ADDRESS, 1)[0]
    records = []
    for index in range(count):
        pointer = int.from_bytes(
            state.read_memory(
                ORDER_POINTERS_ADDRESS + index * ORDER_POINTER_STRIDE,
                ORDER_POINTER_STRIDE),
            "little")
        records.append({
            "index": index,
            "address": pointer,
            "head": state.read_memory(pointer, 6).hex(),
            "tag_a": state.read_memory(pointer + 1, 1)[0],
            "tag_b": state.read_memory(pointer + 2, 1)[0],
        })
    records.append({
        "index": None,
        "count": count,
        "record_size": ORDER_RECORD_SIZE,
        "records_are_uniform_stride": all(
            sorted(r["address"] for r in records if r["index"] is not None)[i + 1]
            - sorted(r["address"] for r in records if r["index"] is not None)[i]
            == ORDER_RECORD_SIZE
            for i in range(count - 1)),
    })
    return records


def summarize(units: Sequence[dict[str, object]]) -> dict[str, object]:
    counts: dict[str, int] = {}
    for unit in units:
        counts[str(unit["side"])] = counts.get(str(unit["side"]), 0) + 1
    acting = [
        {"slot": unit["slot"], "side": unit["side"], "x": unit["x"],
         "y": unit["y"]}
        for unit in units
        if unit.get("acting")
    ]
    return {
        "unit_count": len(units),
        "by_side": counts,
        "acting": acting,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("savestate", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pool-address", type=lambda v: int(v, 0), default=POOL_ADDRESS)
    parser.add_argument("--stride", type=lambda v: int(v, 0), default=POOL_STRIDE)
    parser.add_argument("--slots", type=int, default=16)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        units = read_pool(
            load_state(args.savestate), args.pool_address, args.stride, args.slots)
    except (OSError, ValueError, PoolError) as error:
        print(f"read_rom_unit_pool: {error}", file=sys.stderr)
        return 2
    payload = {"savestate": str(args.savestate), **summarize(units), "units": units}
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
