from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import asyncio
import os
import subprocess
import threading
import uuid
from pathlib import Path

from .auth import get_current_user, User
from dependencies import require_permission

router = APIRouter(tags=["build"])

# Where build outputs land. Per-build subdirs are created underneath this.
# build/users/<user_id>/<build_id>/naruto-sequel-dev.gba
BUILD_ROOT = Path(os.environ.get("BUILD_ROOT", "/root/gba-naruto/build/users"))


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
    candidates = [
        (bid, st) for bid, st in build_states.items()
        if st.user_id == user_id and st.status in ("running", "done")
    ]
    if not candidates:
        return None
    # Build ids are UUIDs; lex order == creation order for v4 in practice
    return sorted(candidates, key=lambda kv: kv[0])[-1][0]


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
    # Pass through so build_mod.py can find sequel/project.json etc.
    env.setdefault("PYTHONUNBUFFERED", "1")

    try:
        process = subprocess.Popen(
            ["python3", "tools/automated_test.py"],
            cwd="/root/gba-naruto",
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
            if rom_path.exists():
                state.rom_path = str(rom_path)
                state.status = "done"
                state.progress = 100
                state.logs.append(f"[BUILD {state.build_id}] success: {state.rom_path}")
            else:
                state.status = "error"
                state.error = f"ROM file not produced at {rom_path}"
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
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            subs.remove(ws)
        except ValueError:
            pass


@router.post("/api/build/trigger")
async def trigger_build(user: User = Depends(require_permission("trigger_build"))):
    """Start a new build. Each call returns a fresh build_id (UUID v4 — 122
    bits of entropy). The same user can fire multiple builds in parallel and
    each gets its own state + ROM path."""
    build_id = str(uuid.uuid4())
    state = BuildState(build_id=build_id, user_id=user.username)
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
    if state is None or state.status != "done" or not state.rom_path:
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
async def websocket_build(websocket: WebSocket, build_id: Optional[str] = None):
    """Per-build log/status stream. If build_id is omitted, subscribes to the
    latest build across all users (best-effort, used by the legacy frontend)."""
    await websocket.accept()

    if build_id is None:
        # Fallback: pick any running build, else the most recent.
        running = [bid for bid, st in build_states.items() if st.status == "running"]
        if running:
            build_id = running[0]
        elif build_states:
            build_id = sorted(build_states.keys())[-1]
        else:
            await websocket.send_json({"type": "error", "detail": "no builds available"})
            await websocket.close()
            return

    state = build_states.get(build_id)
    if state is None:
        await websocket.send_json({"type": "error", "detail": f"unknown build_id {build_id}"})
        await websocket.close()
        return

    build_websockets.setdefault(build_id, []).append(websocket)

    try:
        # Initial snapshot
        await websocket.send_json({
            "type": "status",
            "build_id": state.build_id,
            "status": state.status,
            "logs": state.logs,
            "progress": state.progress,
            "rom_path": state.rom_path,
            "error": state.error,
        })

        last_log_count = len(state.logs)
        while True:
            await asyncio.sleep(0.5)
            # Only send a delta if something changed
            if len(state.logs) != last_log_count or state.status in ("done", "error"):
                last_log_count = len(state.logs)
                await websocket.send_json({
                    "type": "log",
                    "build_id": state.build_id,
                    "status": state.status,
                    "logs": state.logs[-50:],
                    "progress": state.progress,
                    "rom_path": state.rom_path,
                    "error": state.error,
                })
                if state.status in ("done", "error"):
                    # Send one more terminal snapshot and stop polling
                    await websocket.send_json({
                        "type": "status",
                        "build_id": state.build_id,
                        "status": state.status,
                        "logs": state.logs,
                        "progress": state.progress,
                        "rom_path": state.rom_path,
                        "error": state.error,
                    })
                    break
    except WebSocketDisconnect:
        pass
    finally:
        subs = build_websockets.get(build_id, [])
        if websocket in subs:
            subs.remove(websocket)