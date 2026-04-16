from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import subprocess
import threading
import asyncio

from .auth import get_current_user

router = APIRouter()

class BuildState:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.status = "idle"
            cls._instance.logs: List[str] = []
            cls._instance.progress = 0
            cls._instance.rom_path: Optional[str] = None
        return cls._instance
    
    def reset(self):
        self.status = "idle"
        self.logs = []
        self.progress = 0
        self.rom_path = None

build_state = BuildState()

class BuildStatusResponse(BaseModel):
    status: str
    logs: List[str]
    progress: int
    rom_path: Optional[str]

async def run_build():
    build_state.reset()
    build_state.status = "running"
    build_state.logs.append("[BUILD] Starting build...")
    
    try:
        process = subprocess.Popen(
            ["python3", "tools/automated_test.py"],
            cwd="/root/gba-naruto",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        for line in process.stdout:
            if line:
                build_state.logs.append(line.rstrip())
        
        process.wait()
        
        if process.returncode == 0:
            build_state.status = "done"
            build_state.progress = 100
            build_state.rom_path = "/root/gba-naruto/build/naruto-sequel-dev.gba"
            build_state.logs.append("[BUILD] Build completed successfully!")
        else:
            build_state.status = "error"
            build_state.logs.append(f"[BUILD] Build failed with exit code {process.returncode}")
    except Exception as e:
        build_state.status = "error"
        build_state.logs.append(f"[BUILD] Error: {str(e)}")

@router.post("/api/build/trigger")
async def trigger_build(_: User = Depends(get_current_user)):
    if build_state.status == "running":
        raise HTTPException(status_code=400, detail="Build already running")
    
    threading.Thread(target=lambda: asyncio.run(run_build()), daemon=True).start()
    
    return {"status": "triggered"}

@router.get("/api/build/status", response_model=BuildStatusResponse)
async def get_build_status():
    return {
        "status": build_state.status,
        "logs": build_state.logs,
        "progress": build_state.progress,
        "rom_path": build_state.rom_path
    }

@router.get("/api/build/download")
async def download_rom():
    if not build_state.rom_path or build_state.status != "done":
        raise HTTPException(status_code=400, detail="No ROM available")
    
    from fastapi.responses import FileResponse
    
    return FileResponse(
        build_state.rom_path,
        media_type="application/octet-stream",
        filename="naruto-sequel-dev.gba"
    )

active_websockets: List[WebSocket] = []

@router.websocket("/ws/build")
async def websocket_build(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    
    try:
        await websocket.send_json({
            "type": "status",
            "status": build_state.status,
            "logs": build_state.logs,
            "progress": build_state.progress,
            "rom_path": build_state.rom_path
        })
        
        while True:
            await asyncio.sleep(0.5)
            if build_state.logs:
                await websocket.send_json({
                    "type": "log",
                    "status": build_state.status,
                    "logs": build_state.logs,
                    "progress": build_state.progress,
                    "rom_path": build_state.rom_path
                })
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)