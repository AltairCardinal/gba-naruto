from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from datetime import datetime

from database import get_db_connection

router = APIRouter(prefix="/api/skills", tags=["skills"])

class SkillCreate(BaseModel):
    unit_id: int
    name: str
    name_ja: Optional[str] = None
    name_zh: Optional[str] = None
    description: Optional[str] = None
    description_ja: Optional[str] = None
    description_zh: Optional[str] = None
    damage: Optional[int] = 0
    heal: Optional[int] = 0
    range_min: Optional[int] = 1
    range_max: Optional[int] = 1
    cost_hp: Optional[int] = 0
    cost_chakra: Optional[int] = 0
    effect_type: Optional[str] = None

class SkillUpdate(BaseModel):
    name: Optional[str] = None
    name_ja: Optional[str] = None
    name_zh: Optional[str] = None
    description: Optional[str] = None
    description_ja: Optional[str] = None
    description_zh: Optional[str] = None
    damage: Optional[int] = None
    heal: Optional[int] = None
    range_min: Optional[int] = None
    range_max: Optional[int] = None
    cost_hp: Optional[int] = None
    cost_chakra: Optional[int] = None
    effect_type: Optional[str] = None

class SkillResponse(BaseModel):
    id: int
    unit_id: int
    name: str
    name_ja: Optional[str]
    name_zh: Optional[str]
    description: Optional[str]
    description_ja: Optional[str]
    description_zh: Optional[str]
    damage: int
    heal: int
    range_min: int
    range_max: int
    cost_hp: int
    cost_chakra: int
    effect_type: Optional[str]
    created_at: str
    updated_at: str

@router.get("", response_model=List[SkillResponse])
async def get_skills(
    unit_id: Optional[int] = None
):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    where_sql = "1=1"
    params = []
    if unit_id is not None:
        where_sql = "unit_id = ?"
        params.append(unit_id)
    
    cursor = conn.execute(
        f"SELECT * FROM skills WHERE {where_sql} ORDER BY id",
        params
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "unit_id": row["unit_id"],
            "name": row["name"],
            "name_ja": row["name_ja"],
            "name_zh": row["name_zh"],
            "description": row["description"],
            "description_ja": row["description_ja"],
            "description_zh": row["description_zh"],
            "damage": row["damage"],
            "heal": row["heal"],
            "range_min": row["range_min"],
            "range_max": row["range_max"],
            "cost_hp": row["cost_hp"],
            "cost_chakra": row["cost_chakra"],
            "effect_type": row["effect_type"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]

@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(skill_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    return {
        "id": row["id"],
        "unit_id": row["unit_id"],
        "name": row["name"],
        "name_ja": row["name_ja"],
        "name_zh": row["name_zh"],
        "description": row["description"],
        "description_ja": row["description_ja"],
        "description_zh": row["description_zh"],
        "damage": row["damage"],
        "heal": row["heal"],
        "range_min": row["range_min"],
        "range_max": row["range_max"],
        "cost_hp": row["cost_hp"],
        "cost_chakra": row["cost_chakra"],
        "effect_type": row["effect_type"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.post("", response_model=SkillResponse)
async def create_skill(skill: SkillCreate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    now = datetime.now().isoformat()
    
    cursor = conn.execute(
        """INSERT INTO skills (unit_id, name, name_ja, name_zh, description, description_ja, description_zh, damage, heal, range_min, range_max, cost_hp, cost_chakra, effect_type, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (skill.unit_id, skill.name, skill.name_ja, skill.name_zh, skill.description, skill.description_ja, skill.description_zh,
         skill.damage, skill.heal, skill.range_min, skill.range_max, skill.cost_hp, skill.cost_chakra, skill.effect_type, now, now)
    )
    conn.commit()
    row_id = cursor.lastrowid
    
    cursor = conn.execute("SELECT * FROM skills WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "unit_id": row["unit_id"],
        "name": row["name"],
        "name_ja": row["name_ja"],
        "name_zh": row["name_zh"],
        "description": row["description"],
        "description_ja": row["description_ja"],
        "description_zh": row["description_zh"],
        "damage": row["damage"],
        "heal": row["heal"],
        "range_min": row["range_min"],
        "range_max": row["range_max"],
        "cost_hp": row["cost_hp"],
        "cost_chakra": row["cost_chakra"],
        "effect_type": row["effect_type"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(skill_id: int, skill: SkillUpdate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Skill not found")
    
    updates = []
    params = []
    
    for field in ["name", "name_ja", "name_zh", "description", "description_ja", "description_zh", "damage", "heal", "range_min", "range_max", "cost_hp", "cost_chakra", "effect_type"]:
        value = getattr(skill, field, None)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)
    
    if not updates:
        conn.close()
        return {
            "id": row["id"],
            "unit_id": row["unit_id"],
            "name": row["name"],
            "name_ja": row["name_ja"],
            "name_zh": row["name_zh"],
            "description": row["description"],
            "description_ja": row["description_ja"],
            "description_zh": row["description_zh"],
            "damage": row["damage"],
            "heal": row["heal"],
            "range_min": row["range_min"],
            "range_max": row["range_max"],
            "cost_hp": row["cost_hp"],
            "cost_chakra": row["cost_chakra"],
            "effect_type": row["effect_type"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(skill_id)
    
    conn.execute(f"UPDATE skills SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "unit_id": row["unit_id"],
        "name": row["name"],
        "name_ja": row["name_ja"],
        "name_zh": row["name_zh"],
        "description": row["description"],
        "description_ja": row["description_ja"],
        "description_zh": row["description_zh"],
        "damage": row["damage"],
        "heal": row["heal"],
        "range_min": row["range_min"],
        "range_max": row["range_max"],
        "cost_hp": row["cost_hp"],
        "cost_chakra": row["cost_chakra"],
        "effect_type": row["effect_type"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.delete("/{skill_id}")
async def delete_skill(skill_id: int):
    conn = get_db_connection()
    cursor = conn.execute("SELECT id FROM skills WHERE id = ?", (skill_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Skill not found")
    
    conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
    conn.commit()
    conn.close()
    
    return {"status": "deleted", "skill_id": skill_id}
