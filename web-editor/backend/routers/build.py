from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import asyncio
import os
import sqlite3
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from .auth import decode_access_token, get_current_user, User
from dependencies import require_permission
from database import _get_db_path

router = APIRouter(tags=["build"])

# Where build outputs land. Per-build subdirs are created underneath this.
# build/users/<user_id>/<build_id>/naruto-sequel-dev.gba
BUILD_ROOT = Path(os.environ.get("BUILD_ROOT", "/root/gba-naruto/build/users"))


def _resolve_build_cwd() -> Path:
    configured = os.environ.get("BUILD_CWD") or os.environ.get("PROJECT_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3]


class BuildState:
    """Per-build state. Each build gets its own instance — no shared singleton,
    so multiple users (and the same user repeatedly) can build concurrently
    without overwriting each other."""

    def __init__(self, build_id: str, user_id: str):
        self.build_id = build_id
        self.user_id = user_id
        self.status: str = "idle"
        self.logs: List[str] = []
        self.progress: int = 0
        self.rom_path: Optional[str] = None
        self.output_dir: str = str(BUILD_ROOT / user_id / build_id)
        self.db_path: Optional[str] = None
        self.error: Optional[str] = None


# Build registry keyed by build_id. Lives for the lifetime of the process —
# so any browser tab / emulator instance that knows the build_id can poll
# the status / download the ROM.
build_states: Dict[str, BuildState] = {}

# Per-build websocket subscriber lists. Each connected client watches one build.
build_websockets: Dict[str, List[WebSocket]] = {}


class BuildStatusResponse(BaseModel):
    build_id: str
    status: str
    logs: List[str]
    progress: int
    rom_path: Optional[str]
    error: Optional[str] = None


def _resolve_latest_build_for_user(user_id: str) -> Optional[str]:
    """Most-recently-created build_id for this user. Used as a default when
    callers don't pass a build_id (e.g. legacy `?` checks)."""
    # ``dict`` preserves insertion order; UUID v4 lexical order is random and
    # cannot represent creation time.
    for build_id, state in reversed(build_states.items()):
        if state.user_id == user_id and state.status in ("running", "done"):
            return build_id
    return None


def _require_build_owner(state: BuildState, user: User) -> None:
    """Keep authenticated private build endpoints scoped to their creator."""
    if state.user_id != user.username:
        raise HTTPException(status_code=403, detail="Build belongs to another user")


def _snapshot_editor_db(source: Path, destination: Path) -> None:
    """Take a transactionally consistent SQLite snapshot for one build ID."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    destination_conn = sqlite3.connect(destination)
    try:
        source_conn.backup(destination_conn)
    finally:
        destination_conn.close()
        source_conn.close()


async def run_build(state: BuildState):
    """Run automated_test.py in a subprocess. Writes ROM into the per-build
    output dir so concurrent users never collide. Reads BUILD_OUTPUT_DIR from
    env so tools/build_mod.py can honour it."""
    state.status = "running"
    state.logs.append(f"[BUILD {state.build_id}] starting (user={state.user_id})")

    # Per-build output dir
    Path(state.output_dir).mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["BUILD_OUTPUT_DIR"] = state.output_dir
    if state.db_path:
        env["DB_PATH"] = state.db_path
    # Pass through so build_mod.py can find sequel/project.json etc.
    env.setdefault("PYTHONUNBUFFERED", "1")

    try:
        automated_report = Path(state.output_dir) / "automated-test-report.json"
        process = subprocess.Popen(
            [
                sys.executable,
                "tools/automated_test.py",
                "--json-output",
                str(automated_report),
            ],
            cwd=str(_resolve_build_cwd()),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        for line in process.stdout:
            if line:
                state.logs.append(line.rstrip())
                # Forward to any subscribed websocket clients
                await _broadcast(state.build_id, {
                    "type": "log",
                    "status": state.status,
                    "logs": state.logs[-50:],  # last 50 lines to keep payload small
                    "progress": state.progress,
                    "rom_path": state.rom_path,
                })

        process.wait()

        if process.returncode == 0:
            rom_path = Path(state.output_dir) / "naruto-sequel-dev.gba"
            build_report = Path(state.output_dir) / "naruto-sequel-build-report.json"
            missing = [
                path for path in (rom_path, build_report, automated_report)
                if not path.exists()
            ]
            if not missing:
                state.rom_path = str(rom_path)
                state.status = "done"
                state.progress = 100
                state.logs.append(f"[BUILD {state.build_id}] success: {state.rom_path}")
            else:
                state.status = "error"
                state.error = "build artifact(s) not produced: " + ", ".join(
                    str(path) for path in missing
                )
                state.logs.append(f"[BUILD {state.build_id}] ERROR: {state.error}")
        else:
            state.status = "error"
            state.error = f"exit code {process.returncode}"
            state.logs.append(f"[BUILD {state.build_id}] FAILED ({process.returncode})")
    except Exception as e:
        state.status = "error"
        state.error = str(e)
        state.logs.append(f"[BUILD {state.build_id}] ERROR: {e}")

    # Final broadcast so any subscribers see done/error
    await _broadcast(state.build_id, {
        "type": "status",
        "status": state.status,
        "logs": state.logs,
        "progress": state.progress,
        "rom_path": state.rom_path,
        "error": state.error,
    })


async def _broadcast(build_id: str, payload: dict):
    """Push a payload to every websocket subscribed to this build_id.
    Silently drops disconnected clients."""
    subs = build_websockets.get(build_id, [])
    dead = []
    for ws in subs:
        try:
            await ws.send_json(_websocket_payload(payload))
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            subs.remove(ws)
        except ValueError:
            pass


def _websocket_payload(payload: dict) -> dict:
    """Expose browser-relevant build state without leaking server paths."""
    return {key: value for key, value in payload.items() if key != "rom_path"}


@router.post("/api/build/trigger")
async def trigger_build(user: User = Depends(require_permission("trigger_build"))):
    """Start a new build. Each call returns a fresh build_id (UUID v4 — 122
    bits of entropy). The same user can fire multiple builds in parallel and
    each gets its own state + ROM path."""
    build_id = str(uuid.uuid4())
    state = BuildState(build_id=build_id, user_id=user.username)
    source_db = Path(_get_db_path())
    if not source_db.exists():
        raise HTTPException(status_code=500, detail="Editor database is unavailable")
    snapshot_path = Path(state.output_dir) / "editor.db"
    _snapshot_editor_db(source_db, snapshot_path)
    state.db_path = str(snapshot_path)
    build_states[build_id] = state

    # Background thread for the subprocess. We use a fresh event loop in the
    # thread so run_build's awaits work without conflicting with the main
    # loop (matches the original behaviour).
    def _thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_build(state))
        finally:
            loop.close()

    threading.Thread(target=_thread_target, daemon=True).start()

    return {
        "build_id": build_id,
        "status": "triggered",
        "user_id": user.username,
    }


@router.get("/api/build/status", response_model=BuildStatusResponse)
async def get_build_status(build_id: Optional[str] = None, user: User = Depends(get_current_user)):
    """Return status for a specific build_id. If build_id is omitted,
    returns the latest build for the authenticated user."""
    if build_id is None:
        build_id = _resolve_latest_build_for_user(user.username)
        if build_id is None:
            raise HTTPException(status_code=404, detail="No builds found for user")
    state = build_states.get(build_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"build_id {build_id} not found")
    _require_build_owner(state, user)
    return BuildStatusResponse(
        build_id=state.build_id,
        status=state.status,
        logs=state.logs,
        progress=state.progress,
        rom_path=state.rom_path,
        error=state.error,
    )


@router.get("/api/build/download")
async def download_rom(build_id: Optional[str] = None, user: User = Depends(get_current_user)):
    """Download the ROM for a specific build_id. Defaults to the latest build
    for the calling user."""
    if build_id is None:
        build_id = _resolve_latest_build_for_user(user.username)
        if build_id is None:
            raise HTTPException(status_code=400, detail="No builds found for user")
    state = build_states.get(build_id)
    if state is None:
        raise HTTPException(status_code=400, detail="ROM not ready")
    _require_build_owner(state, user)
    if state.status != "done" or not state.rom_path:
        raise HTTPException(status_code=400, detail="ROM not ready")
    return FileResponse(
        state.rom_path,
        media_type="application/octet-stream",
        filename="naruto-sequel-dev.gba",
    )


# ────────────────────────────────────────────────────────────────────────────
# Public ROM endpoint — the link editor → emulator
#
# This is intentionally **unauthenticated**: build_id is a 122-bit random UUID
# that doubles as the access token. Anyone with the URL can fetch the ROM,
# which is fine because the editor is a single-team dev tool and the ROMs
# are the team's own builds. If you ever ship this to untrusted users, gate
# this behind an auth check or signed URL.
# ────────────────────────────────────────────────────────────────────────────
@router.get("/api/public/rom/{build_id}")
async def public_get_rom(build_id: str):
    """Fetch the ROM bytes for a finished build. No auth header required —
    the build_id itself is the access token (122 bits of entropy)."""
    state = build_states.get(build_id)
    if state is None or state.status != "done" or not state.rom_path:
        raise HTTPException(status_code=404, detail="ROM not found or build not done")
    if not Path(state.rom_path).exists():
        raise HTTPException(status_code=404, detail="ROM file missing on disk")
    return FileResponse(
        state.rom_path,
        media_type="application/octet-stream",
        filename="naruto-sequel-dev.gba",
    )


# ────────────────────────────────────────────────────────────────────────────
# Per-build websocket — the editor's BuildView subscribes so the log stream
# updates in real time.
# ────────────────────────────────────────────────────────────────────────────
@router.websocket("/ws/build")
async def websocket_build(websocket: WebSocket):
    """Authenticate the first frame, then stream only the caller's build."""
    await websocket.accept()

    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError):
        await websocket.close(code=4401, reason="authentication required")
        return

    build_id = auth_message.get("build_id") if isinstance(auth_message, dict) else None
    if not isinstance(build_id, str) or not build_id:
        await websocket.close(code=4400, reason="explicit build_id required")
        return
    token = auth_message.get("token")
    if not isinstance(token, str) or not token:
        await websocket.close(code=4401, reason="authentication required")
        return
    try:
        user = decode_access_token(token)
    except HTTPException:
        await websocket.close(code=4401, reason="invalid or expired token")
        return

    state = build_states.get(build_id)
    if state is None:
        await websocket.close(code=4404, reason="unknown build_id")
        return
    if state.user_id != user.username:
        await websocket.close(code=4403, reason="build belongs to another user")
        return

    build_websockets.setdefault(build_id, []).append(websocket)

    try:
        # Initial snapshot
        await websocket.send_json(_websocket_payload({
            "type": "status",
            "build_id": state.build_id,
            "status": state.status,
            "logs": state.logs,
            "progress": state.progress,
            "rom_path": state.rom_path,
            "error": state.error,
        }))

        last_log_count = len(state.logs)
        while True:
            await asyncio.sleep(0.5)
            # Only send a delta if something changed
            if len(state.logs) != last_log_count or state.status in ("done", "error"):
                last_log_count = len(state.logs)
                await websocket.send_json(_websocket_payload({
                    "type": "log",
                    "build_id": state.build_id,
                    "status": state.status,
                    "logs": state.logs[-50:],
                    "progress": state.progress,
                    "rom_path": state.rom_path,
                    "error": state.error,
                }))
                if state.status in ("done", "error"):
                    # Send one more terminal snapshot and stop polling
                    await websocket.send_json(_websocket_payload({
                        "type": "status",
                        "build_id": state.build_id,
                        "status": state.status,
                        "logs": state.logs,
                        "progress": state.progress,
                        "rom_path": state.rom_path,
                        "error": state.error,
                    }))
                    break
    except WebSocketDisconnect:
        pass
    finally:
        subs = build_websockets.get(build_id, [])
        if websocket in subs:
            subs.remove(websocket)
