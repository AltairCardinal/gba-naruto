from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import hashlib
from datetime import datetime

from database import get_db_connection

router = APIRouter(prefix="/api/users", tags=["users"])

class UserCreate(BaseModel):
    username: str
    password: str
    role: Optional[str] = "editor"

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@router.get("", response_model=List[UserResponse])
async def get_users():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT id, username, role, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "created_at": row["created_at"]
    }

@router.post("", response_model=UserResponse)
async def create_user(user: UserCreate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT id FROM users WHERE username = ?", (user.username,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")
    
    now = datetime.now().isoformat()
    password_hash = hash_password(user.password)
    
    cursor = conn.execute(
        """INSERT INTO users (username, password_hash, role, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (user.username, password_hash, user.role, now, now)
    )
    conn.commit()
    row_id = cursor.lastrowid
    
    cursor = conn.execute("SELECT id, username, role, created_at FROM users WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "created_at": row["created_at"]
    }

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user: UserUpdate):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    updates = []
    params = []
    
    if user.username is not None:
        updates.append("username = ?")
        params.append(user.username)
    
    if user.password is not None:
        updates.append("password_hash = ?")
        params.append(hash_password(user.password))
    
    if user.role is not None:
        updates.append("role = ?")
        params.append(user.role)
    
    if not updates:
        conn.close()
        return {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "created_at": row["created_at"]
        }
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(user_id)
    
    conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    
    cursor = conn.execute("SELECT id, username, role, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "created_at": row["created_at"]
    }

@router.delete("/{user_id}")
async def delete_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    return {"status": "deleted", "user_id": user_id}
