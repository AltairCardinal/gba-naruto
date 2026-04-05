from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from datetime import datetime

from database import get_db_connection

router = APIRouter(prefix="/api/battles", tags=["battles"])

class BattleConfigCreate(BaseModel):
    scene_key: str
    chapter_id: int
    tilemap_ptr_hex: str = "0x0"
    palette_ptr_hex: str = "0x0"
    enemy_formation: str = "[]"
    flags: int = 0

class BattleConfigUpdate(BaseModel):
    tilemap_ptr_hex: Optional[str] = None
    palette_ptr_hex: Optional[str] = None
    enemy_formation: Optional[str] = None
    flags: Optional[int] = None

class BattleConfigResponse(BaseModel):
    id: int
    scene_key: str
    chapter_id: int
    tilemap_ptr_hex: str
    palette_ptr_hex: str
    enemy_formation: str
    flags: int
    raw_bytes: Optional[str]
    created_at: str
    updated_at: str


BATTLE_CONFIG_ROM = {
    0: {"tilemap_ptr": 0x14D000, "palette_ptr": 0x150000},
    1: {"tilemap_ptr": 0x195000, "palette_ptr": 0x198000},
    2: {"tilemap_ptr": 0x1CB000, "palette_ptr": 0x1CE000},
    3: {"tilemap_ptr": 0x1C2000, "palette_ptr": 0x1C5000},
    4: {"tilemap_ptr": 0x1F1000, "palette_ptr": 0x1F4000},
    5: {"tilemap_ptr": 0x200000, "palette_ptr": 0x203000},
    6: {"tilemap_ptr": 0x210000, "palette_ptr": 0x213000},
    7: {"tilemap_ptr": 0x220000, "palette_ptr": 0x223000},
}


@router.get("", response_model=List[BattleConfigResponse])
async def list_battles(chapter_id: Optional[int] = None):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    where_clause = "WHERE 1=1"
    params = []
    if chapter_id is not None:
        where_clause = "WHERE chapter_id = ?"
        params = [chapter_id]
    
    cursor = conn.execute(
        f"SELECT * FROM battle_configs {where_clause} ORDER BY chapter_id",
        params
    )
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return [
            {
                "id": i,
                "scene_key": f"BATTLE_CHAPTER_{i+1}",
                "chapter_id": i + 1,
                "tilemap_ptr_hex": f"0{BATTLE_CONFIG_ROM[i]['tilemap_ptr']:X}",
                "palette_ptr_hex": f"0{BATTLE_CONFIG_ROM[i]['palette_ptr']:X}",
                "enemy_formation": "[]",
                "flags": 0,
                "raw_bytes": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            for i in range(8)
        ]
    
    return [
        {
            "id": row["id"],
            "scene_key": row["scene_key"],
            "chapter_id": row["chapter_id"],
            "tilemap_ptr_hex": row["tilemap_ptr_hex"],
            "palette_ptr_hex": row["palette_ptr_hex"],
            "enemy_formation": row["enemy_formation"],
            "flags": row["flags"],
            "raw_bytes": row["raw_bytes"].hex() if row["raw_bytes"] else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]


@router.get("/{scene_key}", response_model=BattleConfigResponse)
async def get_battle(scene_key: str):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM battle_configs WHERE scene_key = ?", (scene_key,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        try:
            chapter_num = int(scene_key.split("_")[-1])
            if 1 <= chapter_num <= 8:
                return {
                    "id": chapter_num,
                    "scene_key": scene_key,
                    "chapter_id": chapter_num,
                    "tilemap_ptr_hex": f"0{BATTLE_CONFIG_ROM[chapter_num-1]['tilemap_ptr']:X}",
                    "palette_ptr_hex": f"0{BATTLE_CONFIG_ROM[chapter_num-1]['palette_ptr']:X}",
                    "enemy_formation": "[]",
                    "flags": 0,
                    "raw_bytes": None,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
        except:
            pass
        raise HTTPException(status_code=404, detail="Battle config not found")
    
    return {
        "id": row["id"],
        "scene_key": row["scene_key"],
        "chapter_id": row["chapter_id"],
        "tilemap_ptr_hex": row["tilemap_ptr_hex"],
        "palette_ptr_hex": row["palette_ptr_hex"],
        "enemy_formation": row["enemy_formation"],
        "flags": row["flags"],
        "raw_bytes": row["raw_bytes"].hex() if row["raw_bytes"] else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }


@router.post("", response_model=BattleConfigResponse)
async def create_battle(battle: BattleConfigCreate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    now = datetime.now().isoformat()
    
    try:
        cursor = conn.execute(
            """INSERT INTO battle_configs (scene_key, chapter_id, tilemap_ptr_hex, palette_ptr_hex, enemy_formation, flags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (battle.scene_key, battle.chapter_id, battle.tilemap_ptr_hex, battle.palette_ptr_hex, battle.enemy_formation, battle.flags, now, now)
        )
        conn.commit()
        row_id = cursor.lastrowid
        
        cursor = conn.execute("SELECT * FROM battle_configs WHERE id = ?", (row_id,))
        row = cursor.fetchone()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Scene key already exists")
    
    conn.close()
    
    return {
        "id": row["id"],
        "scene_key": row["scene_key"],
        "chapter_id": row["chapter_id"],
        "tilemap_ptr_hex": row["tilemap_ptr_hex"],
        "palette_ptr_hex": row["palette_ptr_hex"],
        "enemy_formation": row["enemy_formation"],
        "flags": row["flags"],
        "raw_bytes": None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }


@router.put("/{scene_key}", response_model=BattleConfigResponse)
async def update_battle(scene_key: str, battle: BattleConfigUpdate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM battle_configs WHERE scene_key = ?", (scene_key,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Battle config not found")
    
    updates = []
    params = []
    
    for field in ["tilemap_ptr_hex", "palette_ptr_hex", "enemy_formation", "flags"]:
        value = getattr(battle, field, None)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)
    
    if not updates:
        conn.close()
        return {
            "id": row["id"],
            "scene_key": row["scene_key"],
            "chapter_id": row["chapter_id"],
            "tilemap_ptr_hex": row["tilemap_ptr_hex"],
            "palette_ptr_hex": row["palette_ptr_hex"],
            "enemy_formation": row["enemy_formation"],
            "flags": row["flags"],
            "raw_bytes": None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(scene_key)
    
    conn.execute(f"UPDATE battle_configs SET {', '.join(updates)} WHERE scene_key = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM battle_configs WHERE scene_key = ?", (scene_key,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "scene_key": row["scene_key"],
        "chapter_id": row["chapter_id"],
        "tilemap_ptr_hex": row["tilemap_ptr_hex"],
        "palette_ptr_hex": row["palette_ptr_hex"],
        "enemy_formation": row["enemy_formation"],
        "flags": row["flags"],
        "raw_bytes": None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }
