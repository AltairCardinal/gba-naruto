from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import json
from datetime import datetime

from database import get_db_connection
from .auth import get_current_user

router = APIRouter(prefix="/api/story-beats", tags=["story-beats"])

class StoryBeatCreate(BaseModel):
    chapter_id: int
    beat_index: int
    beat_type: str
    title: Optional[str] = None
    title_ja: Optional[str] = None
    title_zh: Optional[str] = None
    description: Optional[str] = None
    description_ja: Optional[str] = None
    description_zh: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_param: Optional[str] = None
    dialogue_key: Optional[str] = None
    battle_config_id: Optional[int] = None
    map_id: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    next_beat_id: Optional[int] = None

class StoryBeatUpdate(BaseModel):
    beat_index: Optional[int] = None
    beat_type: Optional[str] = None
    title: Optional[str] = None
    title_ja: Optional[str] = None
    title_zh: Optional[str] = None
    description: Optional[str] = None
    description_ja: Optional[str] = None
    description_zh: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_param: Optional[str] = None
    dialogue_key: Optional[str] = None
    battle_config_id: Optional[int] = None
    map_id: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    next_beat_id: Optional[int] = None

class StoryBeatResponse(BaseModel):
    id: int
    chapter_id: int
    beat_index: int
    beat_type: str
    title: Optional[str]
    title_ja: Optional[str]
    title_zh: Optional[str]
    description: Optional[str]
    description_ja: Optional[str]
    description_zh: Optional[str]
    trigger_type: Optional[str]
    trigger_param: Optional[str]
    dialogue_key: Optional[str]
    battle_config_id: Optional[int]
    map_id: Optional[str]
    position_x: Optional[int]
    position_y: Optional[int]
    next_beat_id: Optional[int]
    created_at: str
    updated_at: str

@router.get("", response_model=List[StoryBeatResponse])
async def get_story_beats(
    chapter_id: Optional[int] = None
):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    where_sql = "1=1"
    params = []
    if chapter_id is not None:
        where_sql = "chapter_id = ?"
        params.append(chapter_id)
    
    cursor = conn.execute(
        f"SELECT * FROM story_beats WHERE {where_sql} ORDER BY chapter_id, beat_index",
        params
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "chapter_id": row["chapter_id"],
            "beat_index": row["beat_index"],
            "beat_type": row["beat_type"],
            "title": row["title"],
            "title_ja": row["title_ja"],
            "title_zh": row["title_zh"],
            "description": row["description"],
            "description_ja": row["description_ja"],
            "description_zh": row["description_zh"],
            "trigger_type": row["trigger_type"],
            "trigger_param": row["trigger_param"],
            "dialogue_key": row["dialogue_key"],
            "battle_config_id": row["battle_config_id"],
            "map_id": row["map_id"],
            "position_x": row["position_x"],
            "position_y": row["position_y"],
            "next_beat_id": row["next_beat_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]

@router.get("/{beat_id}", response_model=StoryBeatResponse)
async def get_story_beat(beat_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM story_beats WHERE id = ?", (beat_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Story beat not found")
    
    return {
        "id": row["id"],
        "chapter_id": row["chapter_id"],
        "beat_index": row["beat_index"],
        "beat_type": row["beat_type"],
        "title": row["title"],
        "title_ja": row["title_ja"],
        "title_zh": row["title_zh"],
        "description": row["description"],
        "description_ja": row["description_ja"],
        "description_zh": row["description_zh"],
        "trigger_type": row["trigger_type"],
        "trigger_param": row["trigger_param"],
        "dialogue_key": row["dialogue_key"],
        "battle_config_id": row["battle_config_id"],
        "map_id": row["map_id"],
        "position_x": row["position_x"],
        "position_y": row["position_y"],
        "next_beat_id": row["next_beat_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.post("", response_model=StoryBeatResponse)
async def create_story_beat(beat: StoryBeatCreate, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    now = datetime.now().isoformat()
    
    cursor = conn.execute(
        """INSERT INTO story_beats (chapter_id, beat_index, beat_type, title, title_ja, title_zh, description, description_ja, description_zh, trigger_type, trigger_param, dialogue_key, battle_config_id, map_id, position_x, position_y, next_beat_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (beat.chapter_id, beat.beat_index, beat.beat_type, beat.title, beat.title_ja, beat.title_zh,
         beat.description, beat.description_ja, beat.description_zh, beat.trigger_type, beat.trigger_param,
         beat.dialogue_key, beat.battle_config_id, beat.map_id, beat.position_x, beat.position_y,
         beat.next_beat_id, now, now)
    )
    conn.commit()
    row_id = cursor.lastrowid
    
    cursor = conn.execute("SELECT * FROM story_beats WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "chapter_id": row["chapter_id"],
        "beat_index": row["beat_index"],
        "beat_type": row["beat_type"],
        "title": row["title"],
        "title_ja": row["title_ja"],
        "title_zh": row["title_zh"],
        "description": row["description"],
        "description_ja": row["description_ja"],
        "description_zh": row["description_zh"],
        "trigger_type": row["trigger_type"],
        "trigger_param": row["trigger_param"],
        "dialogue_key": row["dialogue_key"],
        "battle_config_id": row["battle_config_id"],
        "map_id": row["map_id"],
        "position_x": row["position_x"],
        "position_y": row["position_y"],
        "next_beat_id": row["next_beat_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.put("/{beat_id}", response_model=StoryBeatResponse)
async def update_story_beat(beat_id: int, beat: StoryBeatUpdate, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM story_beats WHERE id = ?", (beat_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Story beat not found")
    
    updates = []
    params = []
    
    for field in ["beat_index", "beat_type", "title", "title_ja", "title_zh", "description", "description_ja", "description_zh", "trigger_type", "trigger_param", "dialogue_key", "battle_config_id", "map_id", "position_x", "position_y", "next_beat_id"]:
        value = getattr(beat, field, None)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)
    
    if not updates:
        conn.close()
        return {
            "id": row["id"],
            "chapter_id": row["chapter_id"],
            "beat_index": row["beat_index"],
            "beat_type": row["beat_type"],
            "title": row["title"],
            "title_ja": row["title_ja"],
            "title_zh": row["title_zh"],
            "description": row["description"],
            "description_ja": row["description_ja"],
            "description_zh": row["description_zh"],
            "trigger_type": row["trigger_type"],
            "trigger_param": row["trigger_param"],
            "dialogue_key": row["dialogue_key"],
            "battle_config_id": row["battle_config_id"],
            "map_id": row["map_id"],
            "position_x": row["position_x"],
            "position_y": row["position_y"],
            "next_beat_id": row["next_beat_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(beat_id)
    
    conn.execute(f"UPDATE story_beats SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM story_beats WHERE id = ?", (beat_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "chapter_id": row["chapter_id"],
        "beat_index": row["beat_index"],
        "beat_type": row["beat_type"],
        "title": row["title"],
        "title_ja": row["title_ja"],
        "title_zh": row["title_zh"],
        "description": row["description"],
        "description_ja": row["description_ja"],
        "description_zh": row["description_zh"],
        "trigger_type": row["trigger_type"],
        "trigger_param": row["trigger_param"],
        "dialogue_key": row["dialogue_key"],
        "battle_config_id": row["battle_config_id"],
        "map_id": row["map_id"],
        "position_x": row["position_x"],
        "position_y": row["position_y"],
        "next_beat_id": row["next_beat_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.delete("/{beat_id}")
async def delete_story_beat(beat_id: int, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.execute("SELECT id FROM story_beats WHERE id = ?", (beat_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Story beat not found")
    
    conn.execute("DELETE FROM story_beats WHERE id = ?", (beat_id,))
    conn.commit()
    conn.close()
    
    return {"status": "deleted", "beat_id": beat_id}
