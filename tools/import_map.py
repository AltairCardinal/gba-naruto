#!/usr/bin/env python3
"""
Map patch generator for Naruto: GBA Power.

Supports generating map layout patches based on discovered tilemap format:
- ROM offset format: 0x14D000, 0x195000, 0x1CB000, etc.
- Grid size: 32x32 = 1024 entries
- Entry format: 2-byte u16, lower 10 bits = tile ID (0-311)
- Attributes: bits 10-15 = flip/palette bank
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent

import sys
sys.path.insert(0, str(ROOT))

from tools.lib import load_json

TILEMAP_REGIONS = {
    "map_1": {"rom_offset": 0x14D000, "arm_addr": 0x0814D000, "name": "Battle Map A"},
    "map_2": {"rom_offset": 0x195000, "arm_addr": 0x08195000, "name": "Battle Map B"},
    "map_3": {"rom_offset": 0x1CB000, "arm_addr": 0x081CB000, "name": "Battle Map C"},
    "map_4": {"rom_offset": 0x1C2000, "arm_addr": 0x081C2000, "name": "Battle Map D"},
    "map_5": {"rom_offset": 0x1F1000, "arm_addr": 0x081F1000, "name": "Battle Map E"},
}

def resolve_map_patches(spec_path: Path, patch_id: str) -> list[dict[str, Any]]:
    spec = load_json(spec_path)
    if spec.get("patch_ready") is True and spec.get("patches"):
        return spec["patches"]
    return []


def summarize_map(path: Path) -> dict:
    data = load_json(path)
    return {
        "map_id": data["map_id"],
        "status": data["status"],
        "reference": data.get("reference"),
        "layout_notes": data.get("layout_notes", []),
        "reverse_engineering_dependency": data.get(
            "reverse_engineering_dependency", []
        ),
        "patch_ready": False,
    }


def generate_map_patch(
    map_name: str,
    tile_grid: list[list[int]],
    hflip: Optional[list[list[bool]]] = None,
    vflip: Optional[list[list[bool]]] = None,
    palette_bank: Optional[list[list[int]]] = None,
) -> dict[str, Any]:
    """Generate a map patch from a 32x32 tile grid.
    
    Args:
        map_name: One of map_1 through map_5
        tile_grid: 32x32 list of tile IDs (0-311)
        hflip: 32x32 optional horizontal flip flags
        vflip: 32x32 optional vertical flip flags
        palette_bank: 32x32 optional palette bank (0-15)
    
    Returns:
        Patch dictionary compatible with build_mod.py
    """
    if map_name not in TILEMAP_REGIONS:
        raise ValueError(f"Unknown map: {map_name}. Valid: {list(TILEMAP_REGIONS.keys())}")
    
    region = TILEMAP_REGIONS[map_name]
    rom_offset = region["rom_offset"]
    
    if len(tile_grid) != 32 or len(tile_grid[0]) != 32:
        raise ValueError("Tile grid must be 32x32")
    
    data = bytearray()
    for row in range(32):
        for col in range(32):
            tile_id = tile_grid[row][col]
            
            if not (0 <= tile_id <= 311):
                raise ValueError(f"Invalid tile ID {tile_id} at ({row}, {col}). Must be 0-311.")
            
            entry = tile_id & 0x3FF
            
            if hflip and hflip[row][col]:
                entry |= (1 << 10)
            if vflip and vflip[row][col]:
                entry |= (1 << 11)
            if palette_bank:
                entry |= (palette_bank[row][col] & 0xF) << 12
            
            data.extend(struct.pack('<H', entry))
    
    return {
        "type": "map",
        "map_id": map_name,
        "description": f"Replace tilemap {region['name']}",
        "rom_offset": rom_offset,
        "data": data.hex(),
        "verify": {
            "method": "bytes_equal",
            "original_file": "rom/experiment-00076d.gba",
            "original_offset": rom_offset,
            "original_length": len(data),
        },
    }


def read_map_from_rom(rom_path: Path, map_name: str) -> tuple[list[list[dict]], dict]:
    """Read tilemap data from a ROM file.
    
    Returns:
        Tuple of (32x32 tile grid with metadata, raw metadata dict)
    """
    if map_name not in TILEMAP_REGIONS:
        raise ValueError(f"Unknown map: {map_name}")
    
    region = TILEMAP_REGIONS[map_name]
    rom_offset = region["rom_offset"]
    
    with open(rom_path, 'rb') as f:
        f.seek(rom_offset)
        data = f.read(2048)
    
    tile_grid = []
    for row in range(32):
        row_tiles = []
        for col in range(32):
            entry = struct.unpack('<H', data[row * 64 + col * 2: row * 64 + col * 2 + 2])[0]
            tile_id = entry & 0x3FF
            hflip = (entry >> 10) & 1
            vflip = (entry >> 11) & 1
            pbank = (entry >> 12) & 0xF
            row_tiles.append({
                "tile_id": tile_id,
                "hflip": bool(hflip),
                "vflip": bool(vflip),
                "palette_bank": pbank,
            })
        tile_grid.append(row_tiles)
    
    raw_metadata = {
        "map_name": map_name,
        "name": region["name"],
        "rom_offset": f"0x{rom_offset:06X}",
        "arm_addr": f"0x{region['arm_addr']:08X}",
        "dimensions": "32x32",
        "format": "2-byte u16 (tile ID in lower 10 bits)",
    }
    
    return tile_grid, raw_metadata


def extract_map(rom_path: str, map_name: str, output_path: Optional[str] = None) -> dict:
    """Extract a map from ROM and save as JSON."""
    tile_grid, metadata = read_map_from_rom(Path(rom_path), map_name)
    
    output = {
        "metadata": metadata,
        "tile_grid": tile_grid,
    }
    
    json_str = json.dumps(output, ensure_ascii=False, indent=2)
    
    if output_path:
        Path(output_path).write_text(json_str)
        print(f"Map extracted to {output_path}")
    else:
        print(json_str)
    
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate, extract, or generate sequel map patches."
    )
    parser.add_argument("map_spec", nargs="?", help="Map spec JSON file")
    parser.add_argument("--extract", choices=list(TILEMAP_REGIONS.keys()), 
                        help="Extract map from ROM")
    parser.add_argument("--rom", default="rom/experiment-00076d.gba",
                        help="ROM file for extraction")
    parser.add_argument("--output")
    parser.add_argument("--generate", nargs=2, metavar=("MAP_NAME", "TILE_GRID_JSON"),
                        help="Generate patch: MAP_NAME (e.g., map_1) + TILE_GRID_JSON file")
    args = parser.parse_args()
    
    if args.extract:
        extract_map(args.rom, args.extract, args.output)
        return 0
    
    if args.generate:
        map_name, tile_grid_path = args.generate
        tile_grid_data = load_json(Path(tile_grid_path))
        tile_grid = tile_grid_data["tile_grid"]
        
        hflip = tile_grid_data.get("hflip")
        vflip = tile_grid_data.get("vflip")
        palette_bank = tile_grid_data.get("palette_bank")
        
        patch = generate_map_patch(
            map_name, 
            tile_grid, 
            hflip if hflip else None, 
            vflip if vflip else None, 
            palette_bank if palette_bank else None
        )
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(patch, f, indent=2)
            print(f"Patch written to {args.output}")
        else:
            print(json.dumps(patch, indent=2))
        return 0
    
    if args.map_spec:
        spec_path = ROOT / args.map_spec
        summary = summarize_map(spec_path)

        if summary.get("patch_ready"):
            patches = resolve_map_patches(spec_path, f"map.{summary['map_id']}")
            if args.output:
                report = {"summary": summary, "patches": patches}
                (ROOT / args.output).write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8"
                )
            else:
                print(json.dumps({"summary": summary, "patches": patches}, ensure_ascii=False, indent=2))
        else:
            text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                (ROOT / args.output).write_text(text, encoding="utf-8")
            else:
                print(text, end="")
        return 0
    
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())