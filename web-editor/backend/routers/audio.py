from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from datetime import datetime

from database import get_db_connection

router = APIRouter(prefix="/api/audio", tags=["audio"])

class AudioFileCreate(BaseModel):
    name: str
    type: str
    rom_offset: Optional[int] = None
    size: Optional[int] = None
    duration_seconds: Optional[float] = None
    format: Optional[str] = None

class AudioFileUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    rom_offset: Optional[int] = None
    size: Optional[int] = None
    duration_seconds: Optional[float] = None
    format: Optional[str] = None

class AudioFileResponse(BaseModel):
    id: int
    name: str
    type: str
    rom_offset: Optional[int]
    size: Optional[int]
    duration_seconds: Optional[float]
    format: Optional[str]
    created_at: str
    updated_at: str

@router.get("", response_model=List[AudioFileResponse])
async def get_audio_files(
    type: Optional[str] = None
):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    where_sql = "1=1"
    params = []
    if type:
        where_sql = "type = ?"
        params.append(type)
    
    cursor = conn.execute(
        f"SELECT * FROM audio_files WHERE {where_sql} ORDER BY id",
        params
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "rom_offset": row["rom_offset"],
            "size": row["size"],
            "duration_seconds": row["duration_seconds"],
            "format": row["format"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]

@router.get("/{audio_id}", response_model=AudioFileResponse)
async def get_audio_file(audio_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM audio_files WHERE id = ?", (audio_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "rom_offset": row["rom_offset"],
        "size": row["size"],
        "duration_seconds": row["duration_seconds"],
        "format": row["format"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.post("", response_model=AudioFileResponse)
async def create_audio_file(audio: AudioFileCreate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    now = datetime.now().isoformat()
    
    cursor = conn.execute(
        """INSERT INTO audio_files (name, type, rom_offset, size, duration_seconds, format, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (audio.name, audio.type, audio.rom_offset, audio.size, audio.duration_seconds, audio.format, now, now)
    )
    conn.commit()
    row_id = cursor.lastrowid
    
    cursor = conn.execute("SELECT * FROM audio_files WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "rom_offset": row["rom_offset"],
        "size": row["size"],
        "duration_seconds": row["duration_seconds"],
        "format": row["format"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.put("/{audio_id}", response_model=AudioFileResponse)
async def update_audio_file(audio_id: int, audio: AudioFileUpdate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM audio_files WHERE id = ?", (audio_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    updates = []
    params = []
    
    for field in ["name", "type", "rom_offset", "size", "duration_seconds", "format"]:
        value = getattr(audio, field, None)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)
    
    if not updates:
        conn.close()
        return {
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "rom_offset": row["rom_offset"],
            "size": row["size"],
            "duration_seconds": row["duration_seconds"],
            "format": row["format"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(audio_id)
    
    conn.execute(f"UPDATE audio_files SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM audio_files WHERE id = ?", (audio_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "rom_offset": row["rom_offset"],
        "size": row["size"],
        "duration_seconds": row["duration_seconds"],
        "format": row["format"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.delete("/{audio_id}")
async def delete_audio_file(audio_id: int):
    conn = get_db_connection()
    cursor = conn.execute("SELECT id FROM audio_files WHERE id = ?", (audio_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    conn.execute("DELETE FROM audio_files WHERE id = ?", (audio_id,))
    conn.commit()
    conn.close()
    
    return {"status": "deleted", "audio_id": audio_id}

@router.get("/types")
async def get_audio_types():
    return {
        "types": ["bgm", "se", "voice", "ambient"]
    }
