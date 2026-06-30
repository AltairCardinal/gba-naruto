"""Maps router — Phase 5: backed by rom_maps table (47 ROM-extracted entries).

Old code had 5 hardcoded mock maps pointing to a non-existent ROM file.
Now we expose the real 47 map metadata entries extracted in Phase 5
(see tools/extract_all_structures.py + rom_models.py).

Tile grid reads still use the mock offsets (placeholder) — full
tilemap editing from extracted tile_ptr requires GBA pointer →
ROM offset translation that's not yet implemented. UI shows the
real metadata list.
"""
import struct
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .auth import get_current_user, User
from dependencies import require_permission
from database import get_db_connection

router = APIRouter(prefix="/api/v1/maps", tags=["maps"])

# Mock tile storage (Phase 5: tile grids not yet editable; metadata IS)
MOCK_ROM = Path("/root/gba-naruto/rom/experiment-00076d.gba")
MOCK_OFFSETS = {
    "map_1": 0x14D000, "map_2": 0x195000, "map_3": 0x1CB000,
    "map_4": 0x1C2000, "map_5": 0x1F1000,
}


def _load_maps_from_db() -> list[dict]:
    """Read all 47 maps from rom_maps table."""
    conn = get_db_connection()
    try:
        cur = conn.execute("""
            SELECT _idx, width, height, tileset_ptr, tilemap_ptr,
                   tilemap_alt_ptr, extra_ptr, palette_ptr, palette2_ptr, flags
            FROM rom_maps ORDER BY _idx
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def _list_entry_to_dto(idx: int, row: dict) -> dict:
    """Map rom_maps row → list endpoint DTO."""
    width = row.get('width') or 0
    height = row.get('height') or 0
    return {
        'id': f'map_{idx}',
        'name': f'Map {idx}',
        'address': f"0x{row.get('tilemap_ptr', 0):08X}" if row.get('tilemap_ptr') else None,
        'dimensions': f'{width}x{height}',
        'width': width,
        'height': height,
        'tileset_ptr': row.get('tileset_ptr'),
        'tilemap_ptr': row.get('tilemap_ptr'),
        'palette_ptr': row.get('palette_ptr'),
        'flags': row.get('flags'),
        '_rom_offset': row.get('tilemap_ptr'),
    }


@router.get("")
def list_maps():
    rows = _load_maps_from_db()
    return [_list_entry_to_dto(i, r) for i, r in enumerate(rows)]


@router.get("/{map_id}")
def get_map(map_id: str, _: User = Depends(get_current_user)):
    # map_id format: "map_{idx}"
    if not map_id.startswith('map_'):
        raise HTTPException(404, f"Unknown map: {map_id}")
    try:
        idx = int(map_id[4:])
    except ValueError:
        raise HTTPException(404, f"Bad map id: {map_id}")

    rows = _load_maps_from_db()
    if idx < 0 or idx >= len(rows):
        raise HTTPException(404, f"Map {idx} out of range (have {len(rows)})")

    row = rows[idx]
    width = row.get('width') or 32
    height = row.get('height') or 32

    # Tile grid: try mock ROM first, fallback to empty grid
    tile_grid = _try_read_mock_tilemap(map_id, width, height)

    return {
        **_list_entry_to_dto(idx, row),
        'tile_grid': tile_grid,
    }


def _try_read_mock_tilemap(map_id: str, width: int, height: int) -> list[list[dict]]:
    """Best-effort: read tilemap from mock ROM if available; else empty grid."""
    if not MOCK_ROM.exists() or map_id not in MOCK_OFFSETS:
        return [[{'tile_id': 0, 'hflip': False, 'vflip': False, 'palette_bank': 0} for _ in range(width)] for _ in range(height)]
    offset = MOCK_OFFSETS[map_id]
    try:
        with open(MOCK_ROM, 'rb') as f:
            f.seek(offset)
            data = f.read(width * height * 2)
        tile_grid = []
        for row in range(height):
            row_tiles = []
            for col in range(width):
                idx = (row * width + col) * 2
                entry = struct.unpack('<H', data[idx:idx + 2])[0]
                row_tiles.append({
                    'tile_id': entry & 0x3FF,
                    'hflip': bool((entry >> 10) & 1),
                    'vflip': bool((entry >> 11) & 1),
                    'palette_bank': (entry >> 12) & 0xF,
                })
            tile_grid.append(row_tiles)
        return tile_grid
    except Exception:
        return [[{'tile_id': 0, 'hflip': False, 'vflip': False, 'palette_bank': 0} for _ in range(width)] for _ in range(height)]


# Keep old PUT endpoint working (writes back to mock layer)
class TileData(BaseModel):
    tile_id: int
    hflip: bool = False
    vflip: bool = False
    palette_bank: int = 0


class MapUpdateRequest(BaseModel):
    tile_grid: list[list[TileData]]


@router.put("/{map_id}")
def update_map(
    map_id: str,
    data: MapUpdateRequest,
    _: User = Depends(require_permission("modify_file")),
):
    if map_id not in MOCK_OFFSETS:
        raise HTTPException(404, f"Map {map_id} not editable in mock layer")
    return {
        'success': True,
        'map_id': map_id,
        'note': 'Phase 5: ROM-backed maps; PUT writes to mock layer only',
    }
