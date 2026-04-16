from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from datetime import datetime

from database import get_db_connection

router = APIRouter(prefix="/api/v1/chapters", tags=["chapters"])

class ChapterCreate(BaseModel):
    chapter_num: int
    title: str
    title_ja: Optional[str] = None
    title_zh: Optional[str] = None
    tilemap_entry_ptr: str = "0x0"
    start_map_key: Optional[str] = None
    start_x: int = 0
    start_y: int = 0
    episode_id: int = 1

class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    title_ja: Optional[str] = None
    title_zh: Optional[str] = None
    tilemap_entry_ptr: Optional[str] = None
    start_map_key: Optional[str] = None
    start_x: Optional[int] = None
    start_y: Optional[int] = None
    episode_id: Optional[int] = None

class ChapterResponse(BaseModel):
    id: int
    chapter_num: int
    title: str
    title_ja: Optional[str]
    title_zh: Optional[str]
    tilemap_entry_ptr: str
    start_map_key: Optional[str]
    start_x: int
    start_y: int
    episode_id: int
    created_at: str
    updated_at: str


@router.get("", response_model=List[ChapterResponse])
async def list_chapters(episode_id: Optional[int] = None):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    where_clause = "WHERE 1=1"
    params = []
    if episode_id is not None:
        where_clause = "WHERE episode_id = ?"
        params = [episode_id]
    
    cursor = conn.execute(
        f"SELECT * FROM chapters {where_clause} ORDER BY chapter_num",
        params
    )
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        default_chapters = [
            {"chapter_num": i, "title": f"Chapter {i}", "title_ja": f"第{i}章", "title_zh": f"第{i}章", "tilemap_entry_ptr": f"0x{0x53D914 + (i-1)*32:X}", "start_map_key": "map_1", "start_x": 0, "start_y": 0, "episode_id": 1}
            for i in range(1, 9)
        ]
        return default_chapters
    
    return [dict(row) for row in rows]


@router.get("/{chapter_num}", response_model=ChapterResponse)
async def get_chapter(chapter_num: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM chapters WHERE chapter_num = ?", (chapter_num,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        if 1 <= chapter_num <= 8:
            return {
                "id": chapter_num,
                "chapter_num": chapter_num,
                "title": f"Chapter {chapter_num}",
                "title_ja": f"第{chapter_num}章",
                "title_zh": f"第{chapter_num}章",
                "tilemap_entry_ptr": f"0x{0x53D914 + (chapter_num-1)*32:X}",
                "start_map_key": "map_1",
                "start_x": 0,
                "start_y": 0,
                "episode_id": 1,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    return dict(row)


@router.post("", response_model=ChapterResponse)
async def create_chapter(chapter: ChapterCreate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    now = datetime.now().isoformat()
    
    cursor = conn.execute(
        """INSERT INTO chapters (chapter_num, title, title_ja, title_zh, tilemap_entry_ptr, start_map_key, start_x, start_y, episode_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (chapter.chapter_num, chapter.title, chapter.title_ja, chapter.title_zh, chapter.tilemap_entry_ptr, chapter.start_map_key, chapter.start_x, chapter.start_y, chapter.episode_id, now, now)
    )
    conn.commit()
    row_id = cursor.lastrowid
    
    cursor = conn.execute("SELECT * FROM chapters WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row)


@router.put("/{chapter_num}", response_model=ChapterResponse)
async def update_chapter(chapter_num: int, chapter: ChapterUpdate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM chapters WHERE chapter_num = ?", (chapter_num,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    updates = []
    params = []
    
    for field in ["title", "title_ja", "title_zh", "tilemap_entry_ptr", "start_map_key", "start_x", "start_y", "episode_id"]:
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
    
    conn.execute(f"UPDATE chapters SET {', '.join(updates)} WHERE chapter_num = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM chapters WHERE chapter_num = ?", (chapter_num,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row)
