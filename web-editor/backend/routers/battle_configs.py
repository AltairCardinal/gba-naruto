from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import json
from datetime import datetime

from database import get_db_connection

router = APIRouter(prefix="/api/battle-configs", tags=["battle-configs"])

class BattleConfigCreate(BaseModel):
    name: str
    chapter_id: Optional[int] = None
    scenario_id: Optional[int] = None
    player_units: Optional[List[dict]] = None
    enemy_units: Optional[List[dict]] = None
    terrain_mod: Optional[dict] = None
    turn_limit: Optional[int] = None
    win_condition: Optional[str] = None
    lose_condition: Optional[str] = None

class BattleConfigUpdate(BaseModel):
    name: Optional[str] = None
    chapter_id: Optional[int] = None
    scenario_id: Optional[int] = None
    player_units: Optional[List[dict]] = None
    enemy_units: Optional[List[dict]] = None
    terrain_mod: Optional[dict] = None
    turn_limit: Optional[int] = None
    win_condition: Optional[str] = None
    lose_condition: Optional[str] = None

class BattleConfigResponse(BaseModel):
    id: int
    name: str
    chapter_id: Optional[int]
    scenario_id: Optional[int]
    player_units: Optional[List[dict]]
    enemy_units: Optional[List[dict]]
    terrain_mod: Optional[dict]
    turn_limit: Optional[int]
    win_condition: Optional[str]
    lose_condition: Optional[str]
    created_at: str
    updated_at: str

def _parse_json(val):
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except:
            return None
    return val

@router.get("", response_model=List[BattleConfigResponse])
async def get_battle_configs(
    chapter_id: Optional[int] = None,
    scenario_id: Optional[int] = None
):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    where_clauses = []
    params = []
    
    if chapter_id is not None:
        where_clauses.append("chapter_id = ?")
        params.append(chapter_id)
    
    if scenario_id is not None:
        where_clauses.append("scenario_id = ?")
        params.append(scenario_id)
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    cursor = conn.execute(
        f"SELECT * FROM battle_configs WHERE {where_sql} ORDER BY id",
        params
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "chapter_id": row["chapter_id"],
            "scenario_id": row["scenario_id"],
            "player_units": _parse_json(row["player_units"]),
            "enemy_units": _parse_json(row["enemy_units"]),
            "terrain_mod": _parse_json(row["terrain_mod"]),
            "turn_limit": row["turn_limit"],
            "win_condition": row["win_condition"],
            "lose_condition": row["lose_condition"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]

@router.get("/{config_id}", response_model=BattleConfigResponse)
async def get_battle_config(config_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM battle_configs WHERE id = ?", (config_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Battle config not found")
    
    return {
        "id": row["id"],
        "name": row["name"],
        "chapter_id": row["chapter_id"],
        "scenario_id": row["scenario_id"],
        "player_units": _parse_json(row["player_units"]),
        "enemy_units": _parse_json(row["enemy_units"]),
        "terrain_mod": _parse_json(row["terrain_mod"]),
        "turn_limit": row["turn_limit"],
        "win_condition": row["win_condition"],
        "lose_condition": row["lose_condition"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.post("", response_model=BattleConfigResponse)
async def create_battle_config(config: BattleConfigCreate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    now = datetime.now().isoformat()
    
    cursor = conn.execute(
        """INSERT INTO battle_configs (name, chapter_id, scenario_id, player_units, enemy_units, terrain_mod, turn_limit, win_condition, lose_condition, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (config.name, config.chapter_id, config.scenario_id,
         json.dumps(config.player_units) if config.player_units else None,
         json.dumps(config.enemy_units) if config.enemy_units else None,
         json.dumps(config.terrain_mod) if config.terrain_mod else None,
         config.turn_limit, config.win_condition, config.lose_condition,
         now, now)
    )
    conn.commit()
    row_id = cursor.lastrowid
    
    cursor = conn.execute("SELECT * FROM battle_configs WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "name": row["name"],
        "chapter_id": row["chapter_id"],
        "scenario_id": row["scenario_id"],
        "player_units": _parse_json(row["player_units"]),
        "enemy_units": _parse_json(row["enemy_units"]),
        "terrain_mod": _parse_json(row["terrain_mod"]),
        "turn_limit": row["turn_limit"],
        "win_condition": row["win_condition"],
        "lose_condition": row["lose_condition"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.put("/{config_id}", response_model=BattleConfigResponse)
async def update_battle_config(config_id: int, config: BattleConfigUpdate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM battle_configs WHERE id = ?", (config_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Battle config not found")
    
    updates = []
    params = []
    
    for field, field_name in [
        ("name", "name"), ("chapter_id", "chapter_id"), ("scenario_id", "scenario_id"),
        ("turn_limit", "turn_limit"), ("win_condition", "win_condition"), ("lose_condition", "lose_condition")
    ]:
        value = getattr(config, field, None)
        if value is not None:
            updates.append(f"{field_name} = ?")
            params.append(value)
    
    if config.player_units is not None:
        updates.append("player_units = ?")
        params.append(json.dumps(config.player_units))
    
    if config.enemy_units is not None:
        updates.append("enemy_units = ?")
        params.append(json.dumps(config.enemy_units))
    
    if config.terrain_mod is not None:
        updates.append("terrain_mod = ?")
        params.append(json.dumps(config.terrain_mod))
    
    if not updates:
        conn.close()
        return {
            "id": row["id"],
            "name": row["name"],
            "chapter_id": row["chapter_id"],
            "scenario_id": row["scenario_id"],
            "player_units": _parse_json(row["player_units"]),
            "enemy_units": _parse_json(row["enemy_units"]),
            "terrain_mod": _parse_json(row["terrain_mod"]),
            "turn_limit": row["turn_limit"],
            "win_condition": row["win_condition"],
            "lose_condition": row["lose_condition"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(config_id)
    
    conn.execute(f"UPDATE battle_configs SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM battle_configs WHERE id = ?", (config_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "name": row["name"],
        "chapter_id": row["chapter_id"],
        "scenario_id": row["scenario_id"],
        "player_units": _parse_json(row["player_units"]),
        "enemy_units": _parse_json(row["enemy_units"]),
        "terrain_mod": _parse_json(row["terrain_mod"]),
        "turn_limit": row["turn_limit"],
        "win_condition": row["win_condition"],
        "lose_condition": row["lose_condition"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.delete("/{config_id}")
async def delete_battle_config(config_id: int):
    conn = get_db_connection()
    cursor = conn.execute("SELECT id FROM battle_configs WHERE id = ?", (config_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Battle config not found")
    
    conn.execute("DELETE FROM battle_configs WHERE id = ?", (config_id,))
    conn.commit()
    conn.close()
    
    return {"status": "deleted", "config_id": config_id}

@router.post("/{config_id}/export")
async def export_battle_config_rom(config_id: int):
    import struct
    import subprocess
    from datetime import datetime
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM battle_configs WHERE id = ?", (config_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Battle config not found")
    
    patches = []
    
    if row["player_units"] or row["enemy_units"]:
        all_units = []
        if row["player_units"]:
            all_units.extend(_parse_json(row["player_units"]))
        if row["enemy_units"]:
            all_units.extend(_parse_json(row["enemy_units"]))
        
        if all_units:
            unit_data = struct.pack(f"<{len(all_units)}H", *[u.get("char_id", 0) for u in all_units][:64])
            patches.append({
                "type": "bytes",
                "offset": 0x53F298,
                "after_hex": unit_data.hex(),
                "description": f"Battle config {config_id}: Unit IDs"
            })
    
    if row["scenario_id"] is not None:
        scenario_id = row["scenario_id"]
        scenario_offset = 0x53D914 + scenario_id * 32
        patches.append({
            "type": "bytes",
            "offset": scenario_offset,
            "after_hex": "0100000000000000000000000000000002000000".decode("hex") if hasattr(__builtins__, 'decode') else bytes.fromhex("0100000000000000000000000000000002000000").hex(),
            "description": f"Battle config {config_id}: Scenario {scenario_id}"
        })
    
    patch_file = f"/root/gba-naruto/build/battle-config-{config_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    import os
    os.makedirs("/root/gba-naruto/build", exist_ok=True)
    
    with open(patch_file, "w") as f:
        json.dump({"patches": patches}, f, indent=2)
    
    return {
        "status": "exported",
        "config_id": config_id,
        "patch_file": patch_file,
        "patches_count": len(patches)
    }
