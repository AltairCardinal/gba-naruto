import os
import re
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import bcrypt
import jwt
import sqlite3

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24h to make dev life easier

security = HTTPBearer(auto_error=False)


class User(BaseModel):
    username: str
    role: str = "editor"


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=256)


class RegisterResponse(BaseModel):
    id: int
    username: str
    role: str


class MeResponse(BaseModel):
    username: str
    role: str
    permissions: List[str]


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> User:
    """Decode one JWT for both HTTPBearer and WebSocket first-frame auth."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
        return User(username=username, role=payload.get("role", "editor"))
    except jwt.PyJWTError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from error


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_access_token(credentials.credentials)


def _get_db_path() -> str:
    """Resolve DB path the same way database.py does (4 levels up from
    routers/auth.py → web-editor/backend → web-editor → gba-naruto)."""
    return os.environ.get("DB_PATH") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "sequel",
        "editor.db",
    )


# Public router (no auth dependency) — for the login endpoint.
# main.py imports this as `auth.router`.
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Username/password login. Returns a JWT access token.

    NOTE: This is intentionally minimal — the editor is a single-team
    dev tool, not a multi-tenant SaaS. The frontend stores the token in
    localStorage and sends it as `Authorization: Bearer <token>` for
    every authenticated request.
    """
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (req.username,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    pw_hash = row["password_hash"] or ""
    if not pw_hash or not bcrypt.checkpw(req.password.encode("utf-8"), pw_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": row["username"], "role": row["role"]})
    return LoginResponse(access_token=token, username=row["username"], role=row["role"])


# Username format used by /register: alphanumeric + underscore, 2-64 chars.
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{2,64}$")


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(req: RegisterRequest):
    """Public self-service signup. New users are role=editor with **no
    permissions** — they can log in, view, and that's it until an admin
    grants them the specific permissions they need.

    Returns 409 if the username is already taken.
    """
    username = req.username.strip()
    password = req.password

    if not _USERNAME_RE.match(username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 2-64 chars, letters/digits/underscore only",
        )
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Username already exists")

        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at, updated_at) VALUES (?, ?, 'editor', ?, ?)",
            (username, pw_hash, now, now),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()

    return RegisterResponse(id=new_id, username=username, role="editor")


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user + their effective permission
    list. Admin always sees all 4; others get the rows from user_permissions.

    The frontend calls this once after login so the auth store knows which
    buttons to show / which API calls will succeed.
    """
    # Lazy import to avoid circular dependency between auth ↔ dependencies.
    from dependencies import get_user_permissions
    permissions = get_user_permissions(user)
    return MeResponse(username=user.username, role=user.role, permissions=permissions)
