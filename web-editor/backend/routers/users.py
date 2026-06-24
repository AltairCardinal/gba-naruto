"""Admin user management endpoints.

Mounted at /api/users. All endpoints require admin role.

Endpoints:
  GET    /api/users                       list all users + their permissions
  GET    /api/users/{username}            single user detail
  PUT    /api/users/{username}/permissions   overwrite a user's permission set
  DELETE /api/users/{username}            delete a user (admin can't delete self)

Note: the original /api/v1/users router is now superseded by this one; we
keep the v1 prefix-less path because the frontend (UserListView + the new
UserManagementView) calls `/api/users` directly.
"""
import re
from datetime import datetime
from typing import List, Optional

import bcrypt
import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from database import get_db_connection
from dependencies import ALL_PERMISSIONS, get_user_permissions
from .auth import User, get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


# ── Pydantic schemas ────────────────────────────────────────────────────────

class PermissionsUpdate(BaseModel):
    """Body of PUT /api/users/{username}/permissions. The permissions list
    is treated as the *complete* desired set — any existing permission not
    in this list is removed (rather than a delta update)."""
    permissions: List[str] = Field(default_factory=list)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class UserCreate(BaseModel):
    """Optional body for admin-driven user creation. The public flow is
    POST /api/auth/register; this is kept for completeness / scripted admin ops."""
    username: str
    password: str
    role: Optional[str] = "editor"
    permissions: List[str] = Field(default_factory=list)


# ── helpers ─────────────────────────────────────────────────────────────────

def _require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _fetch_user(username: str) -> Optional[UserOut]:
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, username, role, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row:
            return None
        # For non-admin users we read the actual table; admin gets all 4 by
        # policy and we don't store perms for admin (would just be clutter).
        if row["role"] == "admin":
            perms = list(ALL_PERMISSIONS)
        else:
            perm_rows = conn.execute(
                "SELECT permission FROM user_permissions WHERE user_id = ?", (row["id"],),
            ).fetchall()
            perms = [p["permission"] for p in perm_rows]
    finally:
        conn.close()
    return UserOut(
        id=row["id"],
        username=row["username"],
        role=row["role"],
        created_at=row["created_at"],
        permissions=perms,
    )


def _validate_perms(perms: List[str]) -> None:
    """Reject unknown permission tokens with a 400 so a stale client gets a
    clear error rather than silently writing garbage into the DB."""
    bad = [p for p in perms if p not in ALL_PERMISSIONS]
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown permission(s): {bad}. Valid: {ALL_PERMISSIONS}",
        )


# ── routes ──────────────────────────────────────────────────────────────────

@router.get("", response_model=List[UserOut])
async def list_users(_: User = Depends(_require_admin)):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    out: List[UserOut] = []
    for row in rows:
        # admin → all 4 (per design); others → read stored perms
        if row["role"] == "admin":
            perms = list(ALL_PERMISSIONS)
        else:
            conn2 = get_db_connection()
            conn2.row_factory = sqlite3.Row
            try:
                prow = conn2.execute(
                    "SELECT permission FROM user_permissions WHERE user_id = ?", (row["id"],),
                ).fetchall()
                perms = [p["permission"] for p in prow]
            finally:
                conn2.close()
        out.append(UserOut(
            id=row["id"], username=row["username"], role=row["role"],
            created_at=row["created_at"], permissions=perms,
        ))
    return out


@router.get("/{username}", response_model=UserOut)
async def get_user(username: str, _: User = Depends(_require_admin)):
    user = _fetch_user(username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate, _: User = Depends(_require_admin)):
    """Admin-driven user creation (mostly for scripts; end users sign up via
    POST /api/auth/register)."""
    if not re.match(r"^[A-Za-z0-9_]{2,64}$", body.username):
        raise HTTPException(status_code=400, detail="Invalid username format")
    if len(body.password) < 4:
        raise HTTPException(status_code=400, detail="Password too short")
    _validate_perms(body.permissions)
    role = body.role if body.role in ("admin", "editor") else "editor"

    conn = get_db_connection()
    try:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (body.username,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Username already exists")

        pw_hash = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (body.username, pw_hash, role, now, now),
        )
        new_id = cursor.lastrowid
        # Grant permissions only for non-admin; admin has all by default.
        if role != "admin":
            for perm in body.permissions:
                conn.execute(
                    "INSERT OR REPLACE INTO user_permissions (user_id, permission, granted_at) VALUES (?, ?, ?)",
                    (new_id, perm, now),
                )
        conn.commit()
    finally:
        conn.close()

    return _fetch_user(body.username)


@router.put("/{username}/permissions", response_model=UserOut)
async def update_permissions(
    username: str,
    body: PermissionsUpdate,
    admin: User = Depends(_require_admin),
):
    """Replace the user's permission set. Sends the full list (idempotent):
    any permission not in the new list is removed; any in the list not
    currently granted is added. Admin role is preserved (you can't demote
    yourself or another admin via this endpoint)."""
    _validate_perms(body.permissions)

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id, role FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        # If target is admin, permissions are virtual — we don't store them.
        # We just confirm admin role and return the all-4 view.
        if row["role"] == "admin":
            return _fetch_user(username)

        # Wipe and re-insert. Using INSERT OR REPLACE on a fresh slate is
        # simpler than a delta diff and the row count is tiny (≤ 4).
        conn.execute("DELETE FROM user_permissions WHERE user_id = ?", (row["id"],))
        now = datetime.utcnow().isoformat()
        for perm in body.permissions:
            conn.execute(
                "INSERT INTO user_permissions (user_id, permission, granted_by, granted_at) VALUES (?, ?, ?, ?)",
                (row["id"], perm, None, now),
            )
        # Best-effort: record the admin's id as grantor (only if it exists).
        # Don't fail the request if it doesn't — auth resolution may use
        # username only.
        conn.commit()
    finally:
        conn.close()

    return _fetch_user(username)


@router.delete("/{username}")
async def delete_user(username: str, admin: User = Depends(_require_admin)):
    """Delete a user. Admin cannot delete themselves (would lock out the
    system if it's the only admin) — returns 400 in that case."""
    if username == admin.username:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        # ON DELETE CASCADE on user_permissions handles the perms cleanup,
        # but only if PRAGMA foreign_keys=ON is set on this connection
        # (done in database.get_db_connection).
        conn.execute("DELETE FROM users WHERE id = ?", (row["id"],))
        conn.commit()
    finally:
        conn.close()

    return {"status": "deleted", "username": username}
