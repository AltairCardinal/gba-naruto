from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import json
from datetime import datetime

from database import get_db_connection

router = APIRouter()

class DialogueCreate(BaseModel):
    key: str
    speaker: Optional[str] = None
    text_ja: Optional[str] = None
    text_zh: Optional[str] = None
    chapter_id: Optional[int] = None
    max_bytes: Optional[int] = 255

class DialogueUpdate(BaseModel):
    speaker: Optional[str] = None
    text_ja: Optional[str] = None
    text_zh: Optional[str] = None
    chapter_id: Optional[int] = None
    max_bytes: Optional[int] = None

class DialogueResponse(BaseModel):
    id: int
    key: str
    speaker: Optional[str]
    text_ja: Optional[str]
    text_zh: Optional[str]
    chapter_id: Optional[int]
    byte_count: int
    max_bytes: int
    created_at: str
    updated_at: str

def calc_byte_count(text: Optional[str]) -> int:
    if not text:
        return 0
    return len(text.encode('utf-8'))

@router.get("/api/dialogues", response_model=List[DialogueResponse])
async def get_dialogues(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    chapter_id: Optional[int] = None
):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    offset = (page - 1) * limit
    
    where_clauses = []
    params = []
    
    if search:
        where_clauses.append("(key LIKE ? OR speaker LIKE ? OR text_ja LIKE ? OR text_zh LIKE ?)")
        search_pattern = f"%{search}%"
        params.extend([search_pattern] * 4)
    
    if chapter_id is not None:
        where_clauses.append("chapter_id = ?")
        params.append(chapter_id)
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    cursor = conn.execute(
        f"SELECT * FROM dialogues WHERE {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    )
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        text_ja = row["text_ja"] or ""
        text_zh = row["text_zh"] or ""
        byte_count = calc_byte_count(text_ja) + calc_byte_count(text_zh)
        results.append({
            "id": row["id"],
            "key": row["key"],
            "speaker": row["speaker"],
            "text_ja": row["text_ja"],
            "text_zh": row["text_zh"],
            "chapter_id": row["chapter_id"],
            "byte_count": byte_count,
            "max_bytes": row["max_bytes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })
    
    return results

@router.get("/api/dialogues/{key}", response_model=DialogueResponse)
async def get_dialogue(key: str):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM dialogues WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Dialogue not found")
    
    text_ja = row["text_ja"] or ""
    text_zh = row["text_zh"] or ""
    byte_count = calc_byte_count(text_ja) + calc_byte_count(text_zh)
    
    return {
        "id": row["id"],
        "key": row["key"],
        "speaker": row["speaker"],
        "text_ja": row["text_ja"],
        "text_zh": row["text_zh"],
        "chapter_id": row["chapter_id"],
        "byte_count": byte_count,
        "max_bytes": row["max_bytes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.post("/api/dialogues", response_model=DialogueResponse)
async def create_dialogue(dialogue: DialogueCreate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    now = datetime.now().isoformat()
    byte_count = calc_byte_count(dialogue.text_ja) + calc_byte_count(dialogue.text_zh)
    
    try:
        cursor = conn.execute(
            """INSERT INTO dialogues (key, speaker, text_ja, text_zh, chapter_id, byte_count, max_bytes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (dialogue.key, dialogue.speaker, dialogue.text_ja, dialogue.text_zh,
             dialogue.chapter_id, byte_count, dialogue.max_bytes, now, now)
        )
        conn.commit()
        row_id = cursor.lastrowid
        
        cursor = conn.execute("SELECT * FROM dialogues WHERE id = ?", (row_id,))
        row = cursor.fetchone()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Key already exists")
    finally:
        pass
    
    conn.close()
    
    return {
        "id": row["id"],
        "key": row["key"],
        "speaker": row["speaker"],
        "text_ja": row["text_ja"],
        "text_zh": row["text_zh"],
        "chapter_id": row["chapter_id"],
        "byte_count": byte_count,
        "max_bytes": row["max_bytes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.put("/api/dialogues/{key}", response_model=DialogueResponse)
async def update_dialogue(key: str, dialogue: DialogueUpdate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM dialogues WHERE key = ?", (key,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Dialogue not found")
    
    updates = []
    params = []
    
    for field in ["speaker", "text_ja", "text_zh", "chapter_id", "max_bytes"]:
        value = getattr(dialogue, field, None)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)
    
    if not updates:
        conn.close()
        return {
            "id": row["id"],
            "key": row["key"],
            "speaker": row["speaker"],
            "text_ja": row["text_ja"],
            "text_zh": row["text_zh"],
            "chapter_id": row["chapter_id"],
            "byte_count": row["byte_count"],
            "max_bytes": row["max_bytes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(key)
    
    conn.execute(f"UPDATE dialogues SET {', '.join(updates)} WHERE key = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM dialogues WHERE key = ?", (key,))
    row = cursor.fetchone()
    
    text_ja = row["text_ja"] or ""
    text_zh = row["text_zh"] or ""
    byte_count = calc_byte_count(text_ja) + calc_byte_count(text_zh)
    
    conn.close()
    
    return {
        "id": row["id"],
        "key": row["key"],
        "speaker": row["speaker"],
        "text_ja": row["text_ja"],
        "text_zh": row["text_zh"],
        "chapter_id": row["chapter_id"],
        "byte_count": byte_count,
        "max_bytes": row["max_bytes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

@router.delete("/api/dialogues/{key}")
async def delete_dialogue(key: str):
    conn = get_db_connection()
    cursor = conn.execute("SELECT id FROM dialogues WHERE key = ?", (key,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Dialogue not found")
    
    conn.execute("DELETE FROM dialogues WHERE key = ?", (key,))
    conn.commit()
    conn.close()
    
    return {"status": "deleted", "key": key}

@router.get("/api/dialogues/{key}/byte-count")
async def get_byte_count(key: str):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT text_ja, text_zh, max_bytes FROM dialogues WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Dialogue not found")
    
    text_ja = row["text_ja"] or ""
    text_zh = row["text_zh"] or ""
    byte_count = calc_byte_count(text_ja) + calc_byte_count(text_zh)
    
    return {
        "key": key,
        "byte_count": byte_count,
        "max_bytes": row["max_bytes"],
        "remaining": row["max_bytes"] - byte_count
    }