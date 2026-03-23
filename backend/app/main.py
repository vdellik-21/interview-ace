"""
InterviewAce — FastAPI Application Entry Point
Serves REST endpoints and WebSocket for preparation and live copilot sessions.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .models.session import InterviewSession
from .services.audio_capture import DualAudioCapture
from .services.context_builder import prepare_session
from .services.orchestrator import InterviewOrchestrator

app = FastAPI(
    title="InterviewAce",
    description="Stealth AI Interview Copilot Backend",
    version="0.2.0",
)

# CORS — allow Electron and Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
UPLOADS_DIR = DATA_DIR / "uploads"

# In-memory live state (source of truth while backend process is running)
SESSION_STORE: dict[str, InterviewSession] = {}
SESSION_META: dict[str, dict[str, Any]] = {}
SESSION_CONNECTIONS: dict[str, set[WebSocket]] = {}
SESSION_ORCHESTRATORS: dict[str, InterviewOrchestrator] = {}
SESSION_ORCHESTRATOR_TASKS: dict[str, asyncio.Task] = {}


class SessionBroadcaster:
    """Minimal WebSocket-like adapter that broadcasts JSON payloads to all session clients."""

    def __init__(self, session_id: str):
        self.session_id = session_id

    async def send_json(self, data: dict[str, Any]) -> None:
        """Send a payload to all currently-connected websockets for a session."""
        await _broadcast(self.session_id, data)


async def _broadcast(session_id: str, payload: dict[str, Any]) -> None:
    """Broadcast one message to all active socket connections for a session."""
    sockets = list(SESSION_CONNECTIONS.get(session_id, set()))
    stale: list[WebSocket] = []

    for ws in sockets:
        try:
            await ws.send_json(payload)
        except Exception:
            stale.append(ws)

    if stale:
        active = SESSION_CONNECTIONS.get(session_id, set())
        for ws in stale:
            active.discard(ws)


def _json_path(session_id: str) -> Path:
    """Return the on-disk JSON path for one session."""
    return SESSIONS_DIR / f"{session_id}.json"


def _save_session(session: InterviewSession) -> None:
    """Persist a session snapshot to disk."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    _json_path(session.session_id).write_text(
        json.dumps(session.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )


def _load_session(session_id: str) -> InterviewSession | None:
    """Load session from memory or disk if available."""
    cached = SESSION_STORE.get(session_id)
    if cached is not None:
        return cached

    path = _json_path(session_id)
    if not path.exists():
        return None

    session = InterviewSession.model_validate_json(path.read_text(encoding="utf-8"))
    SESSION_STORE[session_id] = session
    return session


async def _save_upload_file(upload: UploadFile, destination: Path) -> None:
    """Save one uploaded file to disk in chunks."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("wb") as f:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)


async def _prepare_session_task(
    *,
    session_id: str,
    resume_path: Path,
    jd_text: str,
    context_paths: list[Path],
    model: str,
    system_audio_device: str,
    mic_device: str,
) -> None:
    """Background worker that builds interview context and notifies clients."""

    async def on_progress(step: str, percent: int) -> None:
        SESSION_META.setdefault(session_id, {})
        SESSION_META[session_id]["prep_step"] = step
        SESSION_META[session_id]["prep_progress"] = percent
        await _broadcast(session_id, {"type": "prep_progress", "step": step, "percent": percent})

    try:
        session = await prepare_session(
            resume_path=str(resume_path),
            jd_text=jd_text,
            context_file_paths=[str(p) for p in context_paths],
            model=model,
            system_audio_device=system_audio_device,
            mic_device=mic_device,
            on_progress=on_progress,
        )
        session.session_id = session_id
        session.status = "ready"

        SESSION_STORE[session_id] = session
        SESSION_META[session_id].update({
            "status": "ready",
            "prep_step": "Ready!",
            "prep_progress": 100,
        })

        _save_session(session)

        await _broadcast(
            session_id,
            {
                "type": "prep_complete",
                "predicted_questions": session.predicted_questions,
            },
        )
        await _broadcast(session_id, {"type": "status", "text": "🟢 Session ready"})

    except Exception as exc:
        SESSION_META.setdefault(session_id, {})
        SESSION_META[session_id].update({
            "status": "error",
            "error": str(exc),
        })
        await _broadcast(
            session_id,
            {
                "type": "error",
                "message": f"Failed to prepare session: {exc}",
            },
        )


async def _start_orchestrator(session_id: str) -> None:
    """Start orchestrator loop for a session if not already running."""
    if session_id in SESSION_ORCHESTRATOR_TASKS:
        return

    session = _load_session(session_id)
    if session is None:
        await _broadcast(session_id, {"type": "error", "message": "Session not found"})
        return

    if session.status != "ready":
        await _broadcast(session_id, {"type": "error", "message": "Session is not ready yet"})
        return

    orchestrator = InterviewOrchestrator(session, SessionBroadcaster(session_id))
    SESSION_ORCHESTRATORS[session_id] = orchestrator

    async def runner() -> None:
        try:
            await orchestrator.start()
        finally:
            _save_session(orchestrator.session)
            SESSION_ORCHESTRATOR_TASKS.pop(session_id, None)
            SESSION_ORCHESTRATORS.pop(session_id, None)

    task = asyncio.create_task(runner())
    SESSION_ORCHESTRATOR_TASKS[session_id] = task


# ─── Health Check ─────────────────────────────────
@app.get("/api/health")
async def health() -> dict[str, str]:
    """Backend health endpoint."""
    return {"status": "ok", "app": "InterviewAce"}


# ─── Audio Devices ────────────────────────────────
@app.get("/api/devices")
async def list_audio_devices() -> dict[str, list[str]]:
    """List available audio input devices for system/mic pickers."""
    discovered = DualAudioCapture.list_devices().get("input", [])
    names = [d["name"] for d in discovered]

    # Heuristic split: populate both selectors with the same discovered list,
    # preferring likely loopback/virtual devices for "system" list first.
    system_first = sorted(
        names,
        key=lambda n: 0 if any(k in n.lower() for k in ["blackhole", "vb", "cable", "loopback"]) else 1,
    )

    return {
        "system_devices": system_first,
        "mic_devices": names,
    }


# ─── Session Management ──────────────────────────
@app.post("/api/session/create")
async def create_session(
    resume: UploadFile = File(...),
    jd_text: str = Form(...),
    context_files: list[UploadFile] = File(default=[]),
    model: str = Form("claude-sonnet-4-20250514"),
    system_audio_device: str = Form("BlackHole 2ch"),
    mic_device: str = Form("MacBook Pro Microphone"),
) -> dict[str, str]:
    """
    Create and prepare a new interview session in the background.

    Returns immediately with a session_id while preparation continues.
    """
    session_id = str(uuid4())
    session_upload_dir = UPLOADS_DIR / session_id

    resume_name = resume.filename or "resume.pdf"
    resume_path = session_upload_dir / resume_name
    await _save_upload_file(resume, resume_path)

    context_paths: list[Path] = []
    for idx, file in enumerate(context_files):
        file_name = file.filename or f"context_{idx + 1}.txt"
        path = session_upload_dir / file_name
        await _save_upload_file(file, path)
        context_paths.append(path)

    SESSION_META[session_id] = {
        "status": "preparing",
        "prep_progress": 0,
        "prep_step": "Queued",
        "error": None,
    }

    asyncio.create_task(
        _prepare_session_task(
            session_id=session_id,
            resume_path=resume_path,
            jd_text=jd_text,
            context_paths=context_paths,
            model=model,
            system_audio_device=system_audio_device,
            mic_device=mic_device,
        )
    )

    return {"session_id": session_id, "status": "preparing"}


@app.get("/api/session/{session_id}/status")
async def session_status(session_id: str) -> dict[str, Any]:
    """Get current preparation/live status for a session."""
    meta = SESSION_META.get(session_id)
    if meta is None:
        session = _load_session(session_id)
        if session is None:
            return {"session_id": session_id, "status": "not_found"}
        return {
            "session_id": session_id,
            "status": session.status,
            "prep_progress": 100 if session.status in {"ready", "live", "ended"} else 0,
            "prep_step": "Ready" if session.status in {"ready", "live", "ended"} else "Unknown",
        }

    return {
        "session_id": session_id,
        "status": meta.get("status", "preparing"),
        "prep_progress": meta.get("prep_progress", 0),
        "prep_step": meta.get("prep_step", "Preparing"),
        "error": meta.get("error"),
    }


# ─── Live Copilot WebSocket ──────────────────────
@app.websocket("/api/copilot/{session_id}")
async def copilot_websocket(websocket: WebSocket, session_id: str) -> None:
    """
    WebSocket endpoint for prep progress + live session traffic.

    Supports:
      - prep progress events for PrepDashboard
      - start_session + live stream events for StealthOverlay
    """
    await websocket.accept()
    SESSION_CONNECTIONS.setdefault(session_id, set()).add(websocket)

    # Send immediate status snapshot
    meta = SESSION_META.get(session_id)
    if meta is not None:
        await websocket.send_json({"type": "status", "text": f"🟡 {meta.get('status', 'preparing').capitalize()}"})
        if meta.get("status") == "preparing":
            await websocket.send_json(
                {
                    "type": "prep_progress",
                    "step": meta.get("prep_step", "Preparing"),
                    "percent": meta.get("prep_progress", 0),
                }
            )
        if meta.get("status") == "ready":
            session = _load_session(session_id)
            await websocket.send_json(
                {
                    "type": "prep_complete",
                    "predicted_questions": session.predicted_questions if session else [],
                }
            )

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            message_type = message.get("type", "")

            if message_type == "start_session":
                await _start_orchestrator(session_id)

            elif message_type in {"stop_session", "regenerate", "shorter", "more_detail", "listening_mode", "update_model"}:
                orchestrator = SESSION_ORCHESTRATORS.get(session_id)
                if orchestrator is None:
                    await websocket.send_json({"type": "error", "message": "Session is not live yet"})
                else:
                    await orchestrator.handle_user_action(message)

    except WebSocketDisconnect:
        pass
    finally:
        SESSION_CONNECTIONS.get(session_id, set()).discard(websocket)


# ─── Startup ──────────────────────────────────────
@app.on_event("startup")
async def startup() -> None:
    """Create required directories on startup."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    print("🎯 InterviewAce backend started")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
