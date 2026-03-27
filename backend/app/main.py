"""
InterviewAce — FastAPI Application Entry Point
Serves REST endpoints and WebSocket for the live copilot.
"""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .logging_config import setup_logging
from .models.session import InterviewSession
from .services.audio_capture import DualAudioCapture
from .services.context_builder import prepare_session
from .services.model_registry import normalize_session_model
from .services.orchestrator import InterviewOrchestrator

setup_logging()
logger = logging.getLogger("interviewace.main")

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
UPLOADS_DIR = DATA_DIR / "uploads"

sessions: dict[str, InterviewSession] = {}
session_prep_state: dict[str, dict] = {}
session_connections: dict[str, set[WebSocket]] = {}
session_tasks: dict[str, asyncio.Task] = {}
live_orchestrators: dict[str, InterviewOrchestrator] = {}
live_session_tasks: dict[str, asyncio.Task] = {}

app = FastAPI(
    title="InterviewAce",
    description="Stealth AI Interview Copilot Backend",
    version="0.1.0",
)

# CORS — allow Electron and Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _save_upload(file: UploadFile, upload_dir: Path) -> str:
    """Persist an uploaded file and return the saved path."""
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload.bin").name
    target_path = upload_dir / f"{uuid.uuid4()}_{safe_name}"
    content = await file.read()

    async with aiofiles.open(target_path, "wb") as out_file:
        await out_file.write(content)

    await file.close()
    logger.info(
        "Saved upload | original_name=%s | path=%s | bytes=%s",
        safe_name,
        target_path,
        len(content),
    )
    return str(target_path)


def _build_prep_message(session_id: str) -> dict | None:
    """Build a websocket payload for the current prep state."""
    state = session_prep_state.get(session_id)
    if not state:
        return None

    status = state.get("status")
    if status == "preparing":
        return {
            "type": "prep_progress",
            "step": state.get("step", "Preparing..."),
            "percent": state.get("percent", 0),
        }
    if status == "ready":
        return {
            "type": "prep_complete",
            "predicted_questions": state.get("predicted_questions", []),
        }
    if status == "error":
        return {
            "type": "error",
            "message": state.get("message", "Session preparation failed."),
        }
    return None


async def _broadcast_to_session(session_id: str, payload: dict) -> None:
    """Broadcast a JSON payload to all connected websockets for a session."""
    sockets = session_connections.get(session_id, set()).copy()
    stale_sockets = []

    for socket in sockets:
        try:
            await socket.send_json(payload)
        except Exception:
            stale_sockets.append(socket)

    for socket in stale_sockets:
        session_connections.get(session_id, set()).discard(socket)


async def _update_prep_state(
    session_id: str,
    *,
    status: str,
    step: str,
    percent: int,
    predicted_questions: list[dict] | None = None,
    message: str | None = None,
) -> None:
    """Persist and broadcast prep state updates."""
    session_prep_state[session_id] = {
        "status": status,
        "step": step,
        "percent": percent,
        "predicted_questions": predicted_questions or [],
        "message": message,
    }

    payload = _build_prep_message(session_id)
    if payload:
        await _broadcast_to_session(session_id, payload)


async def _run_session_preparation(
    session_id: str,
    *,
    resume_path: str,
    jd_text: str,
    context_file_paths: list[str],
    model: str,
    system_audio_device: str,
    speaker_output_device: str,
    mic_device: str,
) -> None:
    """Run the prep pipeline in the background and push websocket updates."""
    logger.info("Session prep task started | session_id=%s", session_id)

    async def on_progress(step: str, percent: int) -> None:
        logger.info(
            "Prep progress | session_id=%s | percent=%s | step=%s",
            session_id,
            percent,
            step,
        )
        await _update_prep_state(
            session_id,
            status="preparing",
            step=step,
            percent=percent,
        )

    try:
        await _update_prep_state(
            session_id,
            status="preparing",
            step="Queued session preparation...",
            percent=5,
        )

        session = await prepare_session(
            session_id=session_id,
            resume_path=resume_path,
            jd_text=jd_text,
            context_file_paths=context_file_paths,
            model=model,
            system_audio_device=system_audio_device,
            speaker_output_device=speaker_output_device,
            mic_device=mic_device,
            on_progress=on_progress,
        )
        sessions[session_id] = session

        await _update_prep_state(
            session_id,
            status="ready",
            step="Ready!",
            percent=100,
            predicted_questions=session.predicted_questions,
        )
        logger.info("Session prep task completed | session_id=%s", session_id)
    except Exception as exc:
        logger.exception("Session prep task failed | session_id=%s", session_id)
        await _update_prep_state(
            session_id,
            status="error",
            step="Preparation failed",
            percent=100,
            message=f"Session preparation failed: {exc}",
        )
    finally:
        session_tasks.pop(session_id, None)


async def _send_current_session_state(websocket: WebSocket, session_id: str) -> None:
    """Send the latest known session state to a new websocket client."""
    payload = _build_prep_message(session_id)
    if payload:
        await websocket.send_json(payload)
    elif session_id in live_orchestrators and live_session_tasks.get(session_id):
        await websocket.send_json({"type": "status", "text": "🟢 Copilot is LIVE"})
    elif session_id in sessions:
        await websocket.send_json({"type": "status", "text": "🟢 Session ready. Overlay connected."})


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    """Preserve first occurrence order while removing duplicates."""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


async def _run_live_session(session_id: str, orchestrator: InterviewOrchestrator) -> None:
    """Run a live interview orchestrator and clean up when it ends."""
    try:
        await orchestrator.start()
    except Exception as exc:
        logger.exception("Live session crashed | session_id=%s", session_id)
        await _broadcast_to_session(
            session_id,
            {"type": "error", "message": f"Live session failed: {exc}"},
        )
    finally:
        live_session_tasks.pop(session_id, None)
        live_orchestrators.pop(session_id, None)
        logger.info("Live session cleaned up | session_id=%s", session_id)


# ─── Health Check ─────────────────────────────────
@app.get("/api/health")
async def health():
    logger.info("Health check requested")
    return {"status": "ok", "app": "InterviewAce"}


# ─── Audio Devices ────────────────────────────────
@app.get("/api/devices")
async def list_audio_devices():
    """List available audio input devices."""
    logger.info("Listing audio devices")
    try:
        devices = DualAudioCapture.list_devices()
        input_names = [device["name"] for device in devices["input"]]
        output_names = [device["name"] for device in devices["output"]]
        warnings = []

        system_keywords = [
            "blackhole",
            "vb-audio",
            "vb audio",
            "loopback",
            "soundflower",
            "stereo mix",
            "cable",
        ]
        mic_keywords = [
            "microphone",
            "mic",
            "macbook",
            "headset",
            "airpods",
            "webcam",
        ]

        system_devices = [
            name for name in input_names
            if any(keyword in name.lower() for keyword in system_keywords)
        ]
        mic_devices = [
            name for name in input_names
            if name not in system_devices and any(keyword in name.lower() for keyword in mic_keywords)
        ]

        if not system_devices:
            warnings.append(
                "No virtual system-audio capture device detected. Install and route BlackHole 2ch "
                "or another loopback device to capture interviewer audio. Your speakers can be selected "
                "below as playback output, but speakers alone cannot be captured directly on macOS."
            )
        if not mic_devices:
            mic_devices = [name for name in input_names if name not in system_devices] or input_names.copy()

        response = {
            "system_devices": _dedupe_preserve_order(system_devices),
            "mic_devices": _dedupe_preserve_order(mic_devices),
            "output_devices": _dedupe_preserve_order(output_names),
            "default_output_device": devices.get("default_output", ""),
            "all_input_devices": input_names,
            "warnings": warnings,
        }
        logger.info(
            "Audio devices found | system_devices=%s | mic_devices=%s | warnings=%s",
            len(response["system_devices"]),
            len(response["mic_devices"]),
            len(warnings),
        )
        return response
    except Exception as exc:
        logger.exception("Failed to list audio devices")
        return {
            "system_devices": ["BlackHole 2ch"],
            "mic_devices": ["MacBook Pro Microphone"],
            "error": str(exc),
        }


# ─── Session Management ──────────────────────────
@app.post("/api/session/create")
async def create_session(
    resume: UploadFile = File(...),
    jd_text: str = Form(...),
    model: str = Form(settings.default_model),
    system_audio_device: str = Form("BlackHole 2ch"),
    speaker_output_device: str = Form(""),
    mic_device: str = Form("MacBook Pro Microphone"),
    context_files: list[UploadFile] | None = File(default=None),
):
    """
    Create a new interview session.
    Uploads resume, receives JD text, triggers context building.
    """
    model = normalize_session_model(model)
    logger.info(
        "Create session requested | resume=%s | jd_chars=%s | model=%s | system_device=%s | speaker_output=%s | mic_device=%s",
        getattr(resume, "filename", "unknown"),
        len(jd_text),
        model,
        system_audio_device,
        speaker_output_device,
        mic_device,
    )
    session_id = str(uuid.uuid4())
    upload_dir = UPLOADS_DIR / session_id

    resume_path = await _save_upload(resume, upload_dir)
    context_paths = []
    for context_file in context_files or []:
        context_paths.append(await _save_upload(context_file, upload_dir))

    prep_task = asyncio.create_task(
        _run_session_preparation(
            session_id,
            resume_path=resume_path,
            jd_text=jd_text,
            context_file_paths=context_paths,
            model=model,
            system_audio_device=system_audio_device,
            speaker_output_device=speaker_output_device,
            mic_device=mic_device,
        )
    )
    session_tasks[session_id] = prep_task

    return {"session_id": session_id, "status": "preparing"}


@app.get("/api/session/{session_id}/status")
async def session_status(session_id: str):
    """Get the current status of a session (preparing/ready/live/ended)."""
    logger.info("Session status requested | session_id=%s", session_id)
    state = session_prep_state.get(session_id)
    if state:
        response = {
            "session_id": session_id,
            "status": state.get("status", "preparing"),
            "prep_progress": state.get("percent", 0),
            "prep_step": state.get("step", ""),
        }
        if state.get("status") == "ready":
            response["predicted_questions"] = state.get("predicted_questions", [])
        if state.get("status") == "error":
            response["message"] = state.get("message", "Session preparation failed.")
        return response

    session = sessions.get(session_id)
    if session:
        return {
            "session_id": session_id,
            "status": session.status,
            "prep_progress": 100,
            "predicted_questions": session.predicted_questions,
        }

    return {"session_id": session_id, "status": "missing", "prep_progress": 0}


# ─── Live Copilot WebSocket ──────────────────────
@app.websocket("/api/copilot/{session_id}")
async def copilot_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for the live interview copilot.
    Handles bidirectional communication between backend and overlay UI.
    """
    await websocket.accept()
    logger.info("WebSocket connected | session_id=%s", session_id)
    session_connections.setdefault(session_id, set()).add(websocket)

    try:
        await websocket.send_json({"type": "status", "text": "🟡 Connecting..."})
        await _send_current_session_state(websocket, session_id)

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            logger.info(
                "WebSocket message received | session_id=%s | type=%s",
                session_id,
                message.get("type", "unknown"),
            )

            if message.get("type") == "stop_session":
                orchestrator = live_orchestrators.get(session_id)
                if orchestrator:
                    orchestrator.attach_websocket(websocket)
                    await orchestrator.handle_user_action(message)
                else:
                    await websocket.send_json({"type": "status", "text": "🔴 Session ended"})
                logger.info("WebSocket session stop requested | session_id=%s", session_id)
                break

            if message.get("type") == "start_session":
                state = session_prep_state.get(session_id)
                if state and state.get("status") == "preparing":
                    await websocket.send_json({"type": "status", "text": "🟡 Session is still preparing..."})
                    payload = _build_prep_message(session_id)
                    if payload:
                        await websocket.send_json(payload)
                    continue

                if state and state.get("status") == "error":
                    await websocket.send_json({
                        "type": "error",
                        "message": state.get("message", "Session preparation failed."),
                    })
                    continue

                if session_id in sessions:
                    existing_orchestrator = live_orchestrators.get(session_id)
                    existing_task = live_session_tasks.get(session_id)

                    if existing_orchestrator and existing_task and not existing_task.done():
                        existing_orchestrator.attach_websocket(websocket)
                        await websocket.send_json({
                            "type": "status",
                            "text": "🟢 Copilot is LIVE",
                        })
                        continue

                    await websocket.send_json({
                        "type": "status",
                        "text": "🟡 Starting live audio + transcription...",
                    })

                    orchestrator = InterviewOrchestrator(sessions[session_id], websocket)
                    live_orchestrators[session_id] = orchestrator
                    live_session_tasks[session_id] = asyncio.create_task(
                        _run_live_session(session_id, orchestrator)
                    )

                    await websocket.send_json({
                        "type": "status",
                        "text": "🟢 Session ready. Listening for audio...",
                    })
                    continue

                await websocket.send_json({
                    "type": "status",
                    "text": "⚪ Waiting for a valid session...",
                })
                continue

            orchestrator = live_orchestrators.get(session_id)
            if orchestrator:
                orchestrator.attach_websocket(websocket)
                await orchestrator.handle_user_action(message)
                continue

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected | session_id=%s", session_id)
    finally:
        session_connections.get(session_id, set()).discard(websocket)


# ─── Startup ──────────────────────────────────────
@app.on_event("startup")
async def startup():
    """Create required directories on startup."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    logger.info("InterviewAce backend started")
    logger.info("Data directories ready | sessions=%s | uploads=%s", SESSIONS_DIR, UPLOADS_DIR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
