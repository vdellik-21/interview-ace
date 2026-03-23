# TECHNICAL DECISIONS — InterviewAce

> Locked decisions that the team has agreed on. Codex should follow these without deviation.
> To propose a change, add to `APPROACH_LOG.md` and get team consensus before modifying this file.

---

## D001 — Desktop Framework: Electron
**Decision:** Use Electron for the desktop shell.
**Reason:** Only Electron provides `setContentProtection(true)` for stealth screen capture exclusion. Tauri does not support this API. This is non-negotiable since stealth mode is a core feature.
**Alternatives considered:** Tauri (rejected — no content protection API), Flutter Desktop (rejected — immature, no content protection).

## D002 — AI Provider: Anthropic Claude Only
**Decision:** Use Claude API exclusively. No OpenAI, no Ollama, no local models for answer generation.
**Reason:** Team wants Claude specifically. Simplifies codebase — one provider, one SDK. User picks which Claude model (Sonnet/Opus/Haiku) per session.
**Exception:** Haiku is used for question classification regardless of the user's chosen model (speed + cost optimization).

## D003 — Transcription: Local Whisper Only
**Decision:** Use `faster-whisper` running locally. No cloud transcription APIs.
**Reason:** Zero cost, zero latency from network, and privacy — no audio leaves the machine (except text sent to Claude).
**Default model:** `base.en`. User can change in settings.

## D004 — Audio Routing: BlackHole (Mac) + VB-Cable (Windows)
**Decision:** Use free virtual audio devices for system audio capture.
**Reason:** Most reliable cross-platform approach. Both are free and well-maintained.
**Note:** If someone finds a way to capture system audio without virtual devices (e.g., WASAPI loopback on Windows), document it in APPROACH_LOG.md.

## D005 — Communication: WebSocket
**Decision:** Backend ↔ Frontend communication uses WebSocket for all real-time data.
**Reason:** Need bidirectional streaming for live transcripts and token-by-token answer display. HTTP polling would be too slow.

## D006 — No Database
**Decision:** No database (no SQLite, no PostgreSQL). Store session data as JSON files in `data/sessions/`.
**Reason:** Only 3 users. No need for a database. JSON files are simpler, portable, and easy to debug. Can add a DB later if needed.

## D007 — Python Backend, Not Node
**Decision:** Backend is Python + FastAPI, not Node.js.
**Reason:** `faster-whisper` and `sounddevice` are Python libraries. The entire audio + transcription pipeline is Python-native. FastAPI provides async WebSocket support.

## D008 — Single Repo (Monorepo)
**Decision:** Everything in one repo — backend, frontend, electron, docs.
**Reason:** 3 developers, one project. Monorepo is simpler. No need for separate repos.

## D009 — API Key Per User
**Decision:** Each user provides their own Anthropic API key in `.env`. No shared key.
**Reason:** Cost isolation. Each person pays for their own Claude usage (~$0.50/interview).

## D010 — English Only (For Now)
**Decision:** Only support English transcription and responses.
**Reason:** All 3 users interview in English. `base.en` model is faster and more accurate than multilingual. Can add language support later.
