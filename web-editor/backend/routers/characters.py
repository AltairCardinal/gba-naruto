from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from datetime import datetime
import json

from database import get_db_connection
from .auth import get_current_user

router = APIRouter(prefix="/api/characters", tags=["characters"])

class CharacterCreate(BaseModel):
    char_id: int
    name: str
    name_ja: Optional[str] = None
    name_zh: Optional[str] = None
    hp: int = 100
    attack: int = 10
    defense: int = 5
    speed: int = 5
    chapter_id: Optional[int] = None
    map_id: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    team: int = 0

class CharacterUpdate(BaseModel):
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

class CharacterResponse(BaseModel):
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


@router.get("", response_model=List[CharacterResponse])
async def list_characters(team: Optional[int] = None):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    where_clause = "WHERE 1=1"
    params = []
    if team is not None:
        where_clause = "WHERE team = ?"
        params = [team]
    
    cursor = conn.execute(
        f"SELECT * FROM units {where_clause} ORDER BY char_id",
        params
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


@router.get("/{char_id}", response_model=CharacterResponse)
async def get_character(char_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM units WHERE char_id = ?", (char_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Character not found")
    
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


@router.post("", response_model=CharacterResponse)
async def create_character(char: CharacterCreate, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    now = datetime.now().isoformat()
    
    try:
        cursor = conn.execute(
            """INSERT INTO units (char_id, name, name_ja, name_zh, hp, attack, defense, speed, chapter_id, map_id, position_x, position_y, team, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (char.char_id, char.name, char.name_ja, char.name_zh, char.hp, char.attack, char.defense, char.speed, char.chapter_id, char.map_id, char.position_x, char.position_y, char.team, now, now)
        )
        conn.commit()
        row_id = cursor.lastrowid
        
        cursor = conn.execute("SELECT * FROM units WHERE id = ?", (row_id,))
        row = cursor.fetchone()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Character ID already exists")
    
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


@router.put("/{char_id}", response_model=CharacterResponse)
async def update_character(char_id: int, char: CharacterUpdate, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM units WHERE char_id = ?", (char_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Character not found")
    
    updates = []
    params = []
    
    for field in ["name", "name_ja", "name_zh", "hp", "attack", "defense", "speed", "chapter_id", "map_id", "position_x", "position_y", "team"]:
        value = getattr(char, field, None)
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
    params.append(char_id)
    
    conn.execute(f"UPDATE units SET {', '.join(updates)} WHERE char_id = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM units WHERE char_id = ?", (char_id,))
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


@router.delete("/{char_id}")
async def delete_character(char_id: int, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.execute("SELECT id FROM units WHERE char_id = ?", (char_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Character not found")
    
    conn.execute("DELETE FROM units WHERE char_id = ?", (char_id,))
    conn.commit()
    conn.close()
    
    return {"status": "deleted", "char_id": char_id}
