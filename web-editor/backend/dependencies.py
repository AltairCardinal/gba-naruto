"""FastAPI dependencies for permission checks.

`require_permission(perm)` returns a FastAPI dependency that:
  1. Authenticates the request via `get_current_user` (JWT in Authorization header).
  2. If the user is `admin`, always passes.
  3. Otherwise, looks up `user_permissions` table for an explicit grant.

Returns 403 (not 401) when authenticated but unauthorised — distinguishes
"you need to log in" from "you logged in but can't do this".
"""
from typing import List

from fastapi import Depends, HTTPException, status
import sqlite3

from database import get_db_connection
from routers.auth import get_current_user, User


# The canonical 4 permission tokens. UI gates and DB CHECK constraint both
# reference this list, so adding a 5th permission needs updates in:
#   - this list
#   - user_permissions CHECK constraint in database.py
#   - the admin UI checkboxes
ALL_PERMISSIONS: List[str] = [
    "create_file",
    "modify_file",
    "delete_file",
    "trigger_build",
]


def get_user_permissions(user: User) -> List[str]:
    """Resolve the effective permission list for a user.

    - admin → all 4 (returned from memory, not DB, so the DB stays clean)
    - others → read from user_permissions table
    """
    if user.role == "admin":
        return list(ALL_PERMISSIONS)

    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "SELECT permission FROM user_permissions WHERE user_id = (SELECT id FROM users WHERE username = ?)",
            (user.username,),
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def require_permission(permission: str):
    """Build a FastAPI dependency that enforces a single permission.

    Usage:
        @router.post("/", dependencies=[Depends(require_permission("create_file"))])
    """
    if permission not in ALL_PERMISSIONS:
        raise ValueError(f"Unknown permission: {permission!r}. Valid: {ALL_PERMISSIONS}")

    def _checker(user: User = Depends(get_current_user)) -> User:
        # Admin is always allowed — checked first so we don't even hit the DB.
        if user.role == "admin":
            return user

        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                SELECT 1 FROM user_permissions up
                JOIN users u ON u.id = up.user_id
                WHERE u.username = ? AND up.permission = ?
                """,
                (user.username, permission),
            )
            if cursor.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: missing '{permission}'",
                )
        finally:
            conn.close()
        return user

    return _checker
