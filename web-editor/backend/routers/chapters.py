from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from datetime import datetime

from database import get_db_connection
from .auth import get_current_user, User

router = APIRouter(prefix="/api/v1/chapters", tags=["chapters"])

# Fields that map to the DB schema in database.py:
#   chapter_number, title, title_ja, title_zh, description, map_id, sequence_order
# Note: the original router referenced tilemap_entry_ptr, start_map_key, start_x,
# start_y, episode_id — but database.py's CREATE TABLE never added those columns.
# We strip them here so the schema (router ↔ DB) stays in sync.

class ChapterCreate(BaseModel):
    chapter_number: int
    title: str
    title_ja: Optional[str] = None
    title_zh: Optional[str] = None
    description: Optional[str] = None
    map_id: Optional[str] = None
    sequence_order: Optional[int] = None

class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    title_ja: Optional[str] = None
    title_zh: Optional[str] = None
    description: Optional[str] = None
    map_id: Optional[str] = None
    sequence_order: Optional[int] = None

class ChapterResponse(BaseModel):
    id: int
    chapter_number: int
    title: Optional[str] = None
    title_ja: Optional[str] = None
    title_zh: Optional[str] = None
    description: Optional[str] = None
    map_id: Optional[str] = None
    sequence_order: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.get("", response_model=List[ChapterResponse])
async def list_chapters(episode_id: Optional[int] = None):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM chapters ORDER BY chapter_number")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        # DB has no rows yet — return synthetic default chapters 1..8
        default_chapters = [
            {
                "id": i,
                "chapter_number": i,
                "title": f"Chapter {i}",
                "title_ja": f"第{i}章",
                "title_zh": f"第{i}章",
                "description": None,
                "map_id": None,
                "sequence_order": i,
                "created_at": None,
                "updated_at": None,
            }
            for i in range(1, 9)
        ]
        return default_chapters
    
    return [dict(row) for row in rows]


@router.get("/{chapter_num}", response_model=ChapterResponse)
async def get_chapter(chapter_num: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM chapters WHERE chapter_number = ?", (chapter_num,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        if 1 <= chapter_num <= 8:
            return {
                "id": chapter_num,
                "chapter_number": chapter_num,
                "title": f"Chapter {chapter_num}",
                "title_ja": f"第{chapter_num}章",
                "title_zh": f"第{chapter_num}章",
                "description": None,
                "map_id": None,
                "sequence_order": chapter_num,
                "created_at": None,
                "updated_at": None,
            }
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    return dict(row)


@router.post("", response_model=ChapterResponse)
async def create_chapter(chapter: ChapterCreate, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    now = datetime.now().isoformat()
    
    cursor = conn.execute(
        """INSERT INTO chapters (chapter_number, title, title_ja, title_zh, description, map_id, sequence_order, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (chapter.chapter_number, chapter.title, chapter.title_ja, chapter.title_zh,
         chapter.description, chapter.map_id, chapter.sequence_order, now, now)
    )
    conn.commit()
    row_id = cursor.lastrowid
    
    cursor = conn.execute("SELECT * FROM chapters WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row)


@router.put("/{chapter_num}", response_model=ChapterResponse)
async def update_chapter(chapter_num: int, chapter: ChapterUpdate, _: User = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM chapters WHERE chapter_number = ?", (chapter_num,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    updates = []
    params = []
    
    for field in ["title", "title_ja", "title_zh", "description", "map_id", "sequence_order"]:
        value = getattr(chapter, field, None)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)
    
    if not updates:
        conn.close()
        return dict(row)
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(chapter_num)
    
    conn.execute(f"UPDATE chapters SET {', '.join(updates)} WHERE chapter_number = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM chapters WHERE chapter_number = ?", (chapter_num,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row)