import struct
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/maps", tags=["maps"])

ROM_PATH = Path("/root/gba-naruto/rom/experiment-00076d.gba")

MAP_METADATA = {
    "map_1": {"id": "map_1", "name": "Battle Map A", "rom_offset": 0x14D000, "width": 32, "height": 32},
    "map_2": {"id": "map_2", "name": "Battle Map B", "rom_offset": 0x195000, "width": 32, "height": 32},
    "map_3": {"id": "map_3", "name": "Battle Map C", "rom_offset": 0x1CB000, "width": 32, "height": 32},
    "map_4": {"id": "map_4", "name": "Battle Map D", "rom_offset": 0x1C2000, "width": 32, "height": 32},
    "map_5": {"id": "map_5", "name": "Battle Map E", "rom_offset": 0x1F1000, "width": 32, "height": 32},
}

class TileData(BaseModel):
    tile_id: int
    hflip: bool = False
    vflip: bool = False
    palette_bank: int = 0

class MapUpdateRequest(BaseModel):
    tile_grid: list[list[TileData]]


def read_tilemap(map_id: str) -> list[list[dict]]:
    if map_id not in MAP_METADATA:
        raise HTTPException(status_code=404, detail=f"Map {map_id} not found")
    
    meta = MAP_METADATA[map_id]
    offset = meta["rom_offset"]
    width = meta["width"]
    height = meta["height"]
    
    if not ROM_PATH.exists():
        raise HTTPException(status_code=500, detail="ROM file not found")
    
    with open(ROM_PATH, "rb") as f:
        f.seek(offset)
        data = f.read(width * height * 2)
    
    tile_grid = []
    for row in range(height):
        row_tiles = []
        for col in range(width):
            entry = struct.unpack('<H', data[row * width * 2 + col * 2: row * width * 2 + col * 2 + 2])[0]
            tile_id = entry & 0x3FF
            hflip = bool((entry >> 10) & 1)
            vflip = bool((entry >> 11) & 1)
            palette_bank = (entry >> 12) & 0xF
            row_tiles.append({
                "tile_id": tile_id,
                "hflip": hflip,
                "vflip": vflip,
                "palette_bank": palette_bank
            })
        tile_grid.append(row_tiles)
    
    return tile_grid


def write_tilemap(map_id: str, tile_grid: list[list[dict]]) -> bytes:
    if map_id not in MAP_METADATA:
        raise HTTPException(status_code=404, detail=f"Map {map_id} not found")
    
    meta = MAP_METADATA[map_id]
    offset = meta["rom_offset"]
    width = meta["width"]
    height = meta["height"]
    
    data = bytearray()
    for row in range(height):
        for col in range(width):
            tile = tile_grid[row][col]
            tile_id = tile.get("tile_id", 0) & 0x3FF
            hflip = 1 if tile.get("hflip", False) else 0
            vflip = 1 if tile.get("vflip", False) else 0
            pbank = tile.get("palette_bank", 0) & 0xF
            
            entry = tile_id | (hflip << 10) | (vflip << 11) | (pbank << 12)
            data.extend(struct.pack('<H', entry))
    
    return bytes(data)


@router.get("")
def list_maps() -> list[dict]:
    return [
        {
            "id": meta["id"],
            "name": meta["name"],
            "address": f"0x{meta['rom_offset']:X}",
            "dimensions": f"{meta['width']}x{meta['height']}"
        }
        for meta in MAP_METADATA.values()
    ]


@router.get("/{map_id}")
def get_map(map_id: str) -> dict:
    if map_id not in MAP_METADATA:
        raise HTTPException(status_code=404, detail=f"Map {map_id} not found")
    
    meta = MAP_METADATA[map_id]
    tile_grid = read_tilemap(map_id)
    
    return {
        "id": meta["id"],
        "name": meta["name"],
        "address": f"0x{meta['rom_offset']:X}",
        "dimensions": f"{meta['width']}x{meta['height']}",
        "tile_grid": tile_grid
    }


@router.put("/{map_id}")
def update_map(map_id: str, data: MapUpdateRequest) -> dict:
    if map_id not in MAP_METADATA:
        raise HTTPException(status_code=404, detail=f"Map {map_id} not found")
    
    meta = MAP_METADATA[map_id]
    tile_grid = [row for row in data.tile_grid]
    
    patch_data = write_tilemap(map_id, tile_grid)
    
    patch_hex = patch_data.hex()
    offset = meta["rom_offset"]
    
    return {
        "success": True,
        "map_id": map_id,
        "patch": {
            "type": "map",
            "rom_offset": offset,
            "data": patch_hex,
            "length": len(patch_data)
        }
    }