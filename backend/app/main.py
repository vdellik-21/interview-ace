"""
InterviewAce — FastAPI Application Entry Point
Serves REST endpoints and WebSocket for the live copilot.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import json
import os

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


# ─── Health Check ─────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "InterviewAce"}


# ─── Audio Devices ────────────────────────────────
@app.get("/api/devices")
async def list_audio_devices():
    """List available audio input devices."""
    # TODO: Implement — Dev 2
    # Use sounddevice.query_devices() to list all devices
    # Return separate lists for system audio and mic devices
    return {
        "system_devices": ["BlackHole 2ch"],
        "mic_devices": ["MacBook Pro Microphone"],
    }


# ─── Session Management ──────────────────────────
@app.post("/api/session/create")
async def create_session(
    resume: UploadFile = File(...),
    jd_text: str = Form(...),
    model: str = Form("claude-sonnet-4-20250514"),
    system_audio_device: str = Form("BlackHole 2ch"),
    mic_device: str = Form("MacBook Pro Microphone"),
):
    """
    Create a new interview session.
    Uploads resume, receives JD text, triggers context building.
    """
    # TODO: Implement — Dev 1
    # 1. Save uploaded files to data/uploads/
    # 2. Call context_builder.prepare_session()
    # 3. Return session_id
    return {"session_id": "stub-session-id", "status": "preparing"}


@app.get("/api/session/{session_id}/status")
async def session_status(session_id: str):
    """Get the current status of a session (preparing/ready/live/ended)."""
    # TODO: Implement — Dev 1
    return {"session_id": session_id, "status": "ready", "prep_progress": 100}


# ─── Live Copilot WebSocket ──────────────────────
@app.websocket("/api/copilot/{session_id}")
async def copilot_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for the live interview copilot.
    Handles bidirectional communication between backend and overlay UI.
    """
    await websocket.accept()

    try:
        await websocket.send_json({"type": "status", "text": "🟡 Connecting..."})

        # TODO: Implement — Dev 1
        # 1. Load the InterviewSession for this session_id
        # 2. Create InterviewOrchestrator(session, websocket)
        # 3. Start orchestrator (blocks until session ends)
        # For now, echo back messages as a stub:

        await websocket.send_json({"type": "status", "text": "🟢 Copilot is LIVE (stub mode)"})

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "stop_session":
                await websocket.send_json({"type": "status", "text": "🔴 Session ended"})
                break

            # Stub: echo back
            await websocket.send_json({
                "type": "transcript",
                "speaker": "interviewer",
                "text": f"[STUB] Received: {message.get('type', 'unknown')}",
                "timestamp": "00:00:00",
            })

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session {session_id}")


# ─── Startup ──────────────────────────────────────
@app.on_event("startup")
async def startup():
    """Create required directories on startup."""
    os.makedirs("../data/sessions", exist_ok=True)
    os.makedirs("../data/uploads", exist_ok=True)
    print("🎯 InterviewAce backend started")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
