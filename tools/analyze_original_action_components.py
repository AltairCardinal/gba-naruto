#!/usr/bin/env python3
"""Recover component resources loaded by the original action renderer.

The mGBA action-presentation trace records calls into the game's BIOS transfer
wrappers.  This tool resolves ROM-backed LZ77 sources, decompresses them, links
each transfer to the nearest preceding semantic presentation event, and can
verify the result against captured GPU memory.  It deliberately operates on
tiles, palettes, and maps; screenshots are not accepted as source assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

try:
    from tools.extract_tileset import ROM_BASE, lz77_decompress
except ModuleNotFoundError:
    from extract_tileset import ROM_BASE, lz77_decompress


ROM_LIMIT = ROM_BASE + 0x02000000
MEMORY_DOMAINS = (
    ("pram", 0x05000000, 0x400),
    ("vram", 0x06000000, 0x18000),
)
SEMANTIC_TARGETS = frozenset(
    {
        "active_action_initializer",
        "action_event_builder",
        "effect_resource_builder",
        "effect_sequence_selector",
        "bind_effect_sequence",
        "hit_presentation",
        "visual_object_create",
    }
)


def load_trace(path: Path) -> list[dict[str, Any]]:
    """Load a JSON-lines trace and reject ambiguous non-object records."""
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(
                f"{path}:{line_number}: trace record must be a JSON object"
            )
        records.append(record)
    return records


def _address(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise ValueError(f"expected address, got {value!r}")


def _cycle(record: dict[str, Any]) -> int:
    return int(record.get("cycle", 0))


def _destination(address: int) -> tuple[str, int] | None:
    for name, base, size in MEMORY_DOMAINS:
        if base <= address < base + size:
            return name, address - base
    return None


def _component_kind(domain: str, offset: int, payload_size: int) -> str:
    if domain == "pram":
        return "bg_palette" if offset < 0x200 else "obj_palette"
    if offset >= 0x10000:
        return "obj_tiles"
    if payload_size in {32 * 20, 32 * 20 * 2} and offset % 0x800 == 0:
        return "bg_tilemap"
    return "bg_tiles"


def _nearest_phase_anchor(
    records: Iterable[dict[str, Any]],
    transfer_cycle: int,
) -> dict[str, Any] | None:
    anchor: dict[str, Any] | None = None
    for record in records:
        if (
            record.get("target") in SEMANTIC_TARGETS
            and _cycle(record) <= transfer_cycle
            and (anchor is None or _cycle(record) >= _cycle(anchor))
        ):
            anchor = record
    if anchor is None:
        return None
    return {
        "target": anchor["target"],
        "frame": anchor.get("frame"),
        "cycle": str(anchor.get("cycle", "0")),
    }


def analyze_lz77_transfers(
    rom: bytes,
    records: list[dict[str, Any]],
    *,
    memory_dumps: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    """Return a reproducible manifest of ROM-backed LZ77 GPU components."""
    dumps = memory_dumps or {}
    components: list[dict[str, Any]] = []
    ignored_non_gpu_transfer_count = 0

    for record in records:
        if record.get("target") not in {"lz77_vram", "lz77_wram"}:
            continue
        source = _address(record["r0"])
        if not (ROM_BASE <= source < min(ROM_LIMIT, ROM_BASE + len(rom))):
            continue

        source_offset = source - ROM_BASE
        payload = lz77_decompress(rom, source_offset)
        destination_address = _address(record["r1"])
        destination = _destination(destination_address)
        if destination is None:
            ignored_non_gpu_transfer_count += 1
            continue

        domain, destination_offset = destination
        dump = dumps.get(domain)
        if dump is None:
            matches_dump = None
        else:
            end = destination_offset + len(payload)
            matches_dump = (
                end <= len(dump)
                and dump[destination_offset:end] == payload
            )

        components.append(
            {
                "frame": record.get("frame"),
                "cycle": str(record.get("cycle", "0")),
                "transfer": record["target"],
                "source_address": f"0x{source:08X}",
                "source_file_offset": f"0x{source_offset:08X}",
                "destination_address": f"0x{destination_address:08X}",
                "destination_domain": domain,
                "destination_offset": f"0x{destination_offset:08X}",
                "component_kind": _component_kind(
                    domain,
                    destination_offset,
                    len(payload),
                ),
                "decompressed_size": len(payload),
                "decompressed_sha256": hashlib.sha256(payload).hexdigest(),
                "destination_matches_dump": matches_dump,
                "phase_anchor": _nearest_phase_anchor(
                    records,
                    _cycle(record),
                ),
            }
        )

    return {
        "schema": "original-action-components-v1",
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "component_count": len(components),
        "ignored_non_gpu_transfer_count": ignored_non_gpu_transfer_count,
        "components": components,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--vram", type=Path)
    parser.add_argument("--pram", type=Path)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    rom = args.rom.read_bytes()
    dumps = {
        name: path.read_bytes()
        for name, path in (("vram", args.vram), ("pram", args.pram))
        if path is not None
    }
    manifest = analyze_lz77_transfers(
        rom,
        load_trace(args.trace),
        memory_dumps=dumps,
    )
    manifest["trace_sha256"] = hashlib.sha256(
        args.trace.read_bytes()
    ).hexdigest()
    manifest["memory_dump_sha256"] = {
        name: hashlib.sha256(payload).hexdigest()
        for name, payload in dumps.items()
    }
    if args.input_state is not None:
        manifest["input_state_sha256"] = hashlib.sha256(
            args.input_state.read_bytes()
        ).hexdigest()
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
