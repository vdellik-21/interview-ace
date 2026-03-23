# PROGRESS TRACKER — InterviewAce

> **Codex: Update this file after completing any task.**
> Format: Check the box, add the date and who completed it.

---

## Phase 1: Foundation & Scaffolding

- [x] Project structure created — 2026-03-22, Vineeth
- [x] CODEX_INSTRUCTIONS.md written — 2026-03-22, Vineeth
- [x] ARCHITECTURE.md written — 2026-03-22, Vineeth
- [x] INTERFACES.md defined — 2026-03-22, Vineeth
- [x] DECISIONS.md locked — 2026-03-22, Vineeth
- [ ] `requirements.txt` finalized
- [ ] `package.json` (frontend) finalized
- [ ] `package.json` (electron) finalized
- [ ] `.env.example` created
- [ ] `dev.sh` script working

## Phase 2: Backend Core

- [ ] `config.py` — Load env vars, validate settings
- [ ] `file_parser.py` — Parse PDF/DOCX/TXT to plain text
- [ ] `context_builder.py` — Full prep pipeline (parse → extract → map → prompt)
- [ ] `system_prompt.txt` — Master prompt template
- [ ] `ai_engine.py` — Claude streaming client
- [ ] `question_detector.py` — Haiku-based question classification
- [ ] `audio_capture.py` — Dual stream capture (system + mic)
- [ ] `transcription.py` — faster-whisper wrapper
- [x] `orchestrator.py` — Wire everything together — 2026-03-23, Codex
- [x] `main.py` — FastAPI app with REST + WebSocket endpoints — 2026-03-23, Codex
- [ ] `session.py` (router) — Session CRUD endpoints
- [ ] `devices.py` (router) — Audio device listing endpoint

## Phase 3: Frontend

- [ ] React + Vite + Tailwind scaffolding
- [ ] `PrepDashboard.jsx` — File upload + model select + audio config
- [ ] `FileUploader.jsx` — Drag-drop component
- [ ] `ModelSelector.jsx` — Claude model dropdown
- [ ] `AudioDevicePicker.jsx` — Device selection dropdowns
- [ ] `StealthOverlay.jsx` — Live interview panel
- [ ] `TranscriptFeed.jsx` — Scrolling transcript
- [ ] `AnswerPanel.jsx` — Streaming answer display
- [ ] `StatusIndicator.jsx` — Connection status
- [ ] `useWebSocket.js` — WebSocket hook
- [ ] `sessionStore.js` — Zustand store

## Phase 4: Electron Shell

- [ ] `main.js` — Electron main process with stealth window
- [ ] `preload.js` — Secure bridge
- [ ] `setContentProtection(true)` verified working
- [ ] Keyboard shortcuts registered and working
- [ ] System tray integration
- [ ] Window positioning (left/right toggle)
- [ ] Panic hide working

## Phase 5: Integration & Testing

- [ ] End-to-end: Upload resume+JD → prep → go live → detect question → stream answer
- [ ] Stealth verified: overlay invisible on Zoom screen share
- [ ] Stealth verified: overlay invisible on Meet screen share
- [ ] Stealth verified: overlay invisible on Teams screen share
- [ ] Audio: Both streams captured correctly on Mac
- [ ] Audio: Both streams captured correctly on Windows (if applicable)
- [ ] Latency: First token < 2 seconds measured
- [ ] Error recovery: API failure → graceful degradation
- [ ] Error recovery: Audio device disconnect → warning + reconnect

## Phase 6: Polish

- [ ] Audio setup wizard (first-time user guide)
- [ ] Session history (view past interview transcripts)
- [ ] Settings page (default model, whisper model, audio devices)
- [ ] Build script for Mac (.dmg)
- [ ] Build script for Windows (.exe)
- [ ] README polished with screenshots

---

## Known Issues

_Track bugs and issues here as they're discovered._

| # | Issue | Severity | Assigned To | Status |
|---|-------|----------|-------------|--------|
| — | _None yet_ | — | — | — |
