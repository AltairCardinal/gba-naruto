from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from datetime import datetime

from database import get_db_connection
from .auth import get_current_user

router = APIRouter(prefix="/api/units", tags=["units"])

class UnitCreate(BaseModel):
    char_id: int
    name: str
    name_ja: Optional[str] = None
    name_zh: Optional[str] = None
    hp: Optional[int] = 100
    attack: Optional[int] = 10
    defense: Optional[int] = 5
    speed: Optional[int] = 5
    chapter_id: Optional[int] = None
    map_id: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    team: Optional[int] = 0

class UnitUpdate(BaseModel):
    char_id: Optional[int] = None
    name: Optional[str] = None
    name_ja: Optional[str] = None
    name_zh: Optional[str] = None
    hp: Optional[int] = None
    attack: Optional[int] = None
    defense: Optional[int] = None
    speed: Optional[int] = None
    chapter_id: Optional[int] = None
    map_id: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    team: Optional[int] = None

class UnitResponse(BaseModel):
    id: int
    char_id: int
    name: str
    name_ja: Optional[str]
    name_zh: Optional[str]
    hp: int
    attack: int
    defense: int
    speed: int
    chapter_id: Optional[int]
    map_id: Optional[str]
    position_x: Optional[int]
    position_y: Optional[int]
    team: int
    created_at: str
    updated_at: str

@router.get("", response_model=List[UnitResponse])
async def get_units(
    page: int = 1,
    limit: int = 50,
    chapter_id: Optional[int] = None,
    team: Optional[int] = None,
    map_id: Optional[str] = None
):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    offset = (page - 1) * limit
    where_clauses = []
    params = []
    
    if chapter_id is not None:
        where_clauses.append("chapter_id = ?")
        params.append(chapter_id)
    
    if team is not None:
        where_clauses.append("team = ?")
        params.append(team)
    
    if map_id:
        where_clauses.append("map_id = ?")
        params.append(map_id)
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    cursor = conn.execute(
        f"SELECT * FROM units WHERE {where_sql} ORDER BY id LIMIT ? OFFSET ?",
        params + [limit, offset]
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "char_id": row["char_id"],
            "name": row["name"],
            "name_ja": row["name_ja"],
            "name_zh": row["name_zh"],
            "hp": row["hp"],
            "attack": row["attack"],
            "defense": row["defense"],
            "speed": row["speed"],
            "chapter_id": row["chapter_id"],
            "map_id": row["map_id"],
            "position_x": row["position_x"],
            "position_y": row["position_y"],
            "team": row["team"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]

@router.get("/{unit_id}", response_model=UnitResponse)
async def get_unit(unit_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM units WHERE id = ?", (unit_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    return {
        "id": row["id"],
        "char_id": row["char_id"],
        "name": row["name"],
        "name_ja": row["name_ja"],
        "name_zh": row["name_zh"],
        "hp": row["hp"],
        "attack": row["attack"],
        "defense": row["defense"],
        "speed": row["speed"],
        "chapter_id": row["chapter_id"],
        "map_id": row["map_id"],
        "position_x": row["position_x"],
        "position_y": row["position_y"],
        "team": row["team"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.post("", response_model=UnitResponse)
async def create_unit(unit: UnitCreate, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    now = datetime.now().isoformat()
    
    cursor = conn.execute(
        """INSERT INTO units (char_id, name, name_ja, name_zh, hp, attack, defense, speed, chapter_id, map_id, position_x, position_y, team, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (unit.char_id, unit.name, unit.name_ja, unit.name_zh, unit.hp, unit.attack, unit.defense, unit.speed,
         unit.chapter_id, unit.map_id, unit.position_x, unit.position_y, unit.team, now, now)
    )
    conn.commit()
    row_id = cursor.lastrowid
    
    cursor = conn.execute("SELECT * FROM units WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "char_id": row["char_id"],
        "name": row["name"],
        "name_ja": row["name_ja"],
        "name_zh": row["name_zh"],
        "hp": row["hp"],
        "attack": row["attack"],
        "defense": row["defense"],
        "speed": row["speed"],
        "chapter_id": row["chapter_id"],
        "map_id": row["map_id"],
        "position_x": row["position_x"],
        "position_y": row["position_y"],
        "team": row["team"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.put("/{unit_id}", response_model=UnitResponse)
async def update_unit(unit_id: int, unit: UnitUpdate, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM units WHERE id = ?", (unit_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Unit not found")
    
    updates = []
    params = []
    
    for field in ["char_id", "name", "name_ja", "name_zh", "hp", "attack", "defense", "speed", "chapter_id", "map_id", "position_x", "position_y", "team"]:
        value = getattr(unit, field, None)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)
    
    if not updates:
        conn.close()
        return {
            "id": row["id"],
            "char_id": row["char_id"],
            "name": row["name"],
            "name_ja": row["name_ja"],
            "name_zh": row["name_zh"],
            "hp": row["hp"],
            "attack": row["attack"],
            "defense": row["defense"],
            "speed": row["speed"],
            "chapter_id": row["chapter_id"],
            "map_id": row["map_id"],
            "position_x": row["position_x"],
            "position_y": row["position_y"],
            "team": row["team"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(unit_id)
    
    conn.execute(f"UPDATE units SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM units WHERE id = ?", (unit_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "char_id": row["char_id"],
        "name": row["name"],
        "name_ja": row["name_ja"],
        "name_zh": row["name_zh"],
        "hp": row["hp"],
        "attack": row["attack"],
        "defense": row["defense"],
        "speed": row["speed"],
        "chapter_id": row["chapter_id"],
        "map_id": row["map_id"],
        "position_x": row["position_x"],
        "position_y": row["position_y"],
        "team": row["team"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.delete("/{unit_id}")
async def delete_unit(unit_id: int, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.execute("SELECT id FROM units WHERE id = ?", (unit_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Unit not found")
    
    conn.execute("DELETE FROM units WHERE id = ?", (unit_id,))
    conn.execute("DELETE FROM skills WHERE unit_id = ?", (unit_id,))
    conn.commit()
    conn.close()
    
    return {"status": "deleted", "unit_id": unit_id}
