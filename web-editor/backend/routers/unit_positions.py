from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from datetime import datetime

from database import get_db_connection
from .auth import get_current_user

router = APIRouter(prefix="/api/unit-positions", tags=["unit-positions"])

class UnitPositionCreate(BaseModel):
    unit_id: int
    map_id: str
    position_x: int
    position_y: int
    team: int

class UnitPositionUpdate(BaseModel):
    position_x: Optional[int] = None
    position_y: Optional[int] = None

class UnitPositionResponse(BaseModel):
    id: int
    unit_id: int
    map_id: str
    position_x: int
    position_y: int
    team: int
    created_at: str
    updated_at: str

@router.get("", response_model=List[UnitPositionResponse])
async def get_unit_positions(
    map_id: Optional[str] = None,
    team: Optional[int] = None
):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    where_clauses = []
    params = []
    
    if map_id:
        where_clauses.append("map_id = ?")
        params.append(map_id)
    
    if team is not None:
        where_clauses.append("team = ?")
        params.append(team)
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    cursor = conn.execute(
        f"SELECT * FROM unit_positions WHERE {where_sql} ORDER BY id",
        params
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "unit_id": row["unit_id"],
            "map_id": row["map_id"],
            "position_x": row["position_x"],
            "position_y": row["position_y"],
            "team": row["team"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]

@router.post("", response_model=UnitPositionResponse)
async def create_unit_position(pos: UnitPositionCreate, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    now = datetime.now().isoformat()
    
    cursor = conn.execute(
        """INSERT INTO unit_positions (unit_id, map_id, position_x, position_y, team, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (pos.unit_id, pos.map_id, pos.position_x, pos.position_y, pos.team, now, now)
    )
    conn.commit()
    row_id = cursor.lastrowid
    
    cursor = conn.execute("SELECT * FROM unit_positions WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "unit_id": row["unit_id"],
        "map_id": row["map_id"],
        "position_x": row["position_x"],
        "position_y": row["position_y"],
        "team": row["team"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.put("/{pos_id}", response_model=UnitPositionResponse)
async def update_unit_position(pos_id: int, pos: UnitPositionUpdate, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM unit_positions WHERE id = ?", (pos_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Unit position not found")
    
    updates = []
    params = []
    
    if pos.position_x is not None:
        updates.append("position_x = ?")
        params.append(pos.position_x)
    
    if pos.position_y is not None:
        updates.append("position_y = ?")
        params.append(pos.position_y)
    
    if not updates:
        conn.close()
        return {
            "id": row["id"],
            "unit_id": row["unit_id"],
            "map_id": row["map_id"],
            "position_x": row["position_x"],
            "position_y": row["position_y"],
            "team": row["team"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(pos_id)
    
    conn.execute(f"UPDATE unit_positions SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM unit_positions WHERE id = ?", (pos_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "unit_id": row["unit_id"],
        "map_id": row["map_id"],
        "position_x": row["position_x"],
        "position_y": row["position_y"],
        "team": row["team"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.delete("/{pos_id}")
async def delete_unit_position(pos_id: int, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.execute("SELECT id FROM unit_positions WHERE id = ?", (pos_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Unit position not found")
    
    conn.execute("DELETE FROM unit_positions WHERE id = ?", (pos_id,))
    conn.commit()
    conn.close()
    
    return {"status": "deleted", "pos_id": pos_id}
