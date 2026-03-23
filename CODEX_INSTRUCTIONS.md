# CODEX INSTRUCTIONS — InterviewAce

> **This file is the single source of truth for any AI coding agent (Codex, Claude Code, etc.) working on this repo.**
> Read this ENTIRE file before writing any code. Every team member's Codex instance must follow these rules.

---

## PROJECT IDENTITY

- **App Name:** InterviewAce
- **What it is:** A stealth real-time AI interview copilot desktop app
- **What it does:** Listens to a live job interview (both interviewer and candidate audio), transcribes in real-time, and generates instant AI-powered answer suggestions using Claude — all invisible to screen share
- **Inspired by:** FinalRound.ai ($90+/month) — we're building this in-house, open-source, for ~$0.50/interview

---

## TEAM CONTEXT

Three developers are building this simultaneously using Codex connected to the same public GitHub repo.

| Role | Focus Area | Primary Files |
|------|-----------|---------------|
| **Dev 1 (Vineeth)** | Backend + AI Engine | `backend/`, `prompts/`, orchestrator, Claude integration |
| **Dev 2** | Audio Capture + Transcription | `backend/services/audio_capture.py`, `transcription.py`, `question_detector.py` |
| **Dev 3** | Frontend + Electron Stealth Shell | `electron/`, `frontend/`, overlay UI, WebSocket client |

### COLLABORATION RULES FOR CODEX:
1. **NEVER modify files outside your assigned focus area** without explicit instruction from the developer
2. **Always check `docs/APPROACH_LOG.md`** before implementing — a team member may have updated the approach
3. **When creating new files**, follow the project structure in `docs/ARCHITECTURE.md`
4. **When making decisions** about libraries, patterns, or approaches — check if the decision is already documented in `docs/DECISIONS.md`
5. **After completing a task**, update `docs/PROGRESS.md` with what was done
6. **If a task depends on another dev's work that doesn't exist yet**, create a clear interface/stub and document the contract in `docs/INTERFACES.md`

---

## THE 4 FEATURES WE'RE BUILDING (Nothing else)

### Feature 1: STEALTH MODE
- Electron desktop app with `setContentProtection(true)`
- Overlay window is invisible to screen share, screenshots, and recording
- Always-on-top, frameless, transparent, resizable
- Keyboard shortcuts for toggle, panic hide, reposition
- System tray integration

### Feature 2: DUAL AUDIO INTERVIEW COPILOT
- Captures system audio (interviewer voice from Zoom/Meet/Teams) via BlackHole (Mac) / VB-Cable (Windows)
- Captures microphone audio (candidate voice) separately
- Real-time transcription of both streams using faster-whisper (local, free)
- Speaker labeling: every transcript segment tagged as "interviewer" or "candidate"

### Feature 3: INSTANT AI ANSWERS (Zero Delay)
- Claude API with streaming enabled — tokens display as they generate
- First answer token visible within 1.5–2 seconds of question ending
- Uses Haiku for fast question-vs-statement classification
- Uses user's chosen model (Sonnet/Opus/Haiku) for full answer generation
- Conversation history maintained throughout interview for context continuity

### Feature 4: PRE-LOADED CONTEXT FOR ACCURACY
- Before interview: user uploads Resume (PDF/DOCX), Job Description, and optional context files
- AI pre-processes everything: extracts skills, maps resume→JD, builds STAR stories, predicts questions
- Builds a master system prompt that gets sent with every Claude call during the interview
- User selects which Claude model to use: `claude-sonnet-4-20250514`, `claude-opus-4-20250514`, or `claude-haiku-4-5-20251001`

---

## TECH STACK (Locked — do not change without team consensus)

| Component | Technology | Version | Notes |
|-----------|-----------|---------|-------|
| Desktop Shell | Electron | Latest stable | For stealth window management |
| Frontend | React + Vite | React 18+, Vite 5+ | Overlay UI + prep dashboard |
| Styling | Tailwind CSS | v3+ | Utility-first, dark theme |
| State Management | Zustand | Latest | Lightweight stores |
| Backend | Python + FastAPI | Python 3.11+, FastAPI 0.100+ | Async, WebSocket support |
| AI Engine | Anthropic Claude API | Latest SDK | Streaming responses |
| Transcription | faster-whisper | Latest | Local Whisper, base.en model |
| Audio Capture | sounddevice | Latest | Cross-platform audio I/O |
| Audio Routing (Mac) | BlackHole 2ch | Latest | Virtual audio device |
| Audio Routing (Win) | VB-Audio Cable | Latest | Virtual audio device |
| File Parsing | pdfplumber + python-docx | Latest | Resume/JD parsing |
| IPC | WebSocket | Native | Backend ↔ Frontend real-time |
| Package Manager | npm (frontend), pip (backend) | — | — |

---

## PROJECT STRUCTURE

```
interview-ace/
├── CODEX_INSTRUCTIONS.md          ← YOU ARE HERE (Codex reads this first)
├── README.md                      ← Public repo readme
├── .env.example                   ← Environment variables template
├── package.json                   ← Root-level scripts
├── docker-compose.yml             ← Optional containerization
│
├── docs/                          ← Living documentation (team updates)
│   ├── ARCHITECTURE.md            ← System design & data flow
│   ├── APPROACH_LOG.md            ← Updated approaches per feature
│   ├── DECISIONS.md               ← Locked technical decisions
│   ├── INTERFACES.md              ← API contracts between modules
│   └── PROGRESS.md                ← What's done, what's in progress
│
├── backend/                       ← Python FastAPI server
│   ├── app/
│   │   ├── main.py                ← FastAPI app entry + WebSocket endpoint
│   │   ├── config.py              ← Settings from .env
│   │   ├── routers/
│   │   │   ├── session.py         ← Create/manage interview sessions
│   │   │   └── devices.py         ← List audio devices
│   │   ├── services/
│   │   │   ├── audio_capture.py   ← DualAudioCapture (system + mic)
│   │   │   ├── transcription.py   ← faster-whisper wrapper
│   │   │   ├── ai_engine.py       ← Claude API streaming client
│   │   │   ├── orchestrator.py    ← Ties audio → transcription → AI → WS
│   │   │   ├── file_parser.py     ← PDF/DOCX/TXT parsing
│   │   │   ├── context_builder.py ← Pre-interview AI prep pipeline
│   │   │   └── question_detector.py ← Is this a question or statement?
│   │   ├── prompts/
│   │   │   ├── system_prompt.txt      ← Master prompt template
│   │   │   ├── resume_extract.txt     ← Resume extraction prompt
│   │   │   ├── jd_analyze.txt         ← JD analysis prompt
│   │   │   └── question_classify.txt  ← Question detection prompt
│   │   └── models/
│   │       └── session.py         ← Pydantic models for session data
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                      ← React UI
│   ├── src/
│   │   ├── pages/
│   │   │   ├── PrepDashboard.jsx      ← File upload + model select + start
│   │   │   ├── StealthOverlay.jsx     ← Live interview overlay panel
│   │   │   ├── Settings.jsx           ← Audio device config
│   │   │   └── SessionHistory.jsx     ← Past transcripts
│   │   ├── components/
│   │   │   ├── FileUploader.jsx       ← Drag-drop file upload
│   │   │   ├── ModelSelector.jsx      ← Claude model picker
│   │   │   ├── AudioDevicePicker.jsx  ← System audio + mic selector
│   │   │   ├── TranscriptFeed.jsx     ← Live scrolling transcript
│   │   │   ├── AnswerPanel.jsx        ← Streaming AI answer display
│   │   │   └── StatusIndicator.jsx    ← Connection status dot
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js        ← WS connection manager
│   │   │   └── useAudioDevices.js     ← Fetch device list from backend
│   │   ├── stores/
│   │   │   └── sessionStore.js        ← Zustand session state
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── package.json
│
├── electron/                      ← Electron desktop shell
│   ├── main.js                    ← Main process (stealth window)
│   ├── preload.js                 ← Secure renderer bridge
│   ├── assets/
│   │   ├── icon.png               ← App icon
│   │   └── tray-icon.png          ← System tray icon (16x16)
│   └── package.json
│
├── scripts/
│   ├── setup_audio_mac.sh         ← Auto-install BlackHole + configure
│   ├── setup_audio_win.ps1        ← Auto-install VB-Cable + configure
│   ├── dev.sh                     ← Start all services for development
│   └── build.sh                   ← Build Electron app for distribution
│
└── data/
    ├── sessions/                  ← Saved interview session data (JSON)
    └── uploads/                   ← Uploaded resumes/JDs/context files
```

---

## CRITICAL IMPLEMENTATION RULES

### Code Style
- **Python:** Use type hints everywhere. Use `async/await` for all I/O. Follow PEP 8.
- **JavaScript/React:** Functional components only. Use hooks. No class components.
- **Naming:** snake_case for Python, camelCase for JS, PascalCase for React components.
- **Comments:** Every function needs a docstring/JSDoc explaining what it does, its params, and return value.

### Error Handling
- **Audio failures:** If a device disconnects mid-interview, show a warning in the overlay but DON'T crash. Try to reconnect.
- **Claude API failures:** If the API call fails, show "⚠️ AI temporarily unavailable — try regenerating" in the overlay. Retry once automatically.
- **Whisper failures:** If transcription fails for a chunk, skip it and continue. Don't block the pipeline.
- **WebSocket disconnects:** Auto-reconnect with exponential backoff (1s, 2s, 4s, max 10s).

### Performance Targets
- **First answer token:** < 2 seconds after interviewer finishes speaking
- **Transcription latency:** < 1 second per utterance
- **Question detection:** < 0.5 seconds
- **UI responsiveness:** Overlay must never freeze or lag

### Security
- **API keys:** NEVER hardcode. Always from `.env` or environment variables.
- **Audio data:** Transcripts stored locally only. No external transmission except Claude API calls.
- **Uploads:** Stored in `data/uploads/` locally. No cloud storage.

---

## HOW TO RUN (Development)

```bash
# 1. Clone repo
git clone https://github.com/<your-repo>/interview-ace.git
cd interview-ace

# 2. Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Frontend setup
cd ../frontend
npm install

# 4. Electron setup
cd ../electron
npm install

# 5. Environment
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and audio device names

# 6. Audio setup (one-time)
# Mac:
bash scripts/setup_audio_mac.sh
# Windows:
powershell scripts/setup_audio_win.ps1

# 7. Start all services
bash scripts/dev.sh
# This starts: FastAPI (port 8000) + Vite (port 5173) + Electron
```

---

## WEBSOCKET MESSAGE PROTOCOL

All communication between backend and frontend uses WebSocket JSON messages.

### Backend → Frontend (downstream)

```jsonc
// Connection status
{"type": "status", "text": "🟢 Copilot is LIVE"}
{"type": "status", "text": "🟡 Preparing session..."}
{"type": "status", "text": "🔴 Disconnected"}

// Live transcript segments
{"type": "transcript", "speaker": "interviewer", "text": "Tell me about yourself", "timestamp": "14:32:05"}
{"type": "transcript", "speaker": "candidate", "text": "Thank you for having me", "timestamp": "14:32:08"}

// Question detected — answer incoming
{"type": "question_detected", "text": "Tell me about a time you used data to drive a marketing decision"}

// Streaming answer tokens (one message per token)
{"type": "answer_token", "token": "At"}
{"type": "answer_token", "token": " Ard"}
{"type": "answer_token", "token": "ent"}
// ... continues until:
{"type": "answer_complete"}

// Session prep progress
{"type": "prep_progress", "step": "Parsing resume...", "percent": 20}
{"type": "prep_progress", "step": "Analyzing JD...", "percent": 40}
{"type": "prep_progress", "step": "Building STAR stories...", "percent": 60}
{"type": "prep_progress", "step": "Predicting questions...", "percent": 80}
{"type": "prep_complete", "predicted_questions": [...]}

// Errors
{"type": "error", "message": "Claude API rate limited. Retrying in 2s..."}

// Audio device info
{"type": "devices", "system_devices": [...], "mic_devices": [...]}
```

### Frontend → Backend (upstream)

```jsonc
// Start interview session
{"type": "start_session", "session_id": "abc123"}

// Stop interview
{"type": "stop_session"}

// User actions on answer
{"type": "regenerate"}          // Regenerate last answer
{"type": "shorter"}             // Regenerate but shorter
{"type": "more_detail"}         // Regenerate with more detail
{"type": "listening_mode"}      // Pause suggestions temporarily

// Change settings mid-interview
{"type": "update_model", "model": "claude-opus-4-20250514"}
{"type": "update_sensitivity", "silence_threshold": 0.015}
```

---

## PROMPT TEMPLATES

All prompts live in `backend/app/prompts/` as `.txt` files. They use `{variable}` placeholders that get filled at runtime.

### Master System Prompt (`system_prompt.txt`)
This is sent as the `system` parameter in every Claude API call during the live interview. It contains ALL the pre-processed context. See `docs/ARCHITECTURE.md` for the full template.

### Resume Extraction (`resume_extract.txt`)
Used during prep phase to extract structured data from the candidate's resume.

### JD Analysis (`jd_analyze.txt`)
Used during prep phase to extract requirements, skills, and focus areas from the job description.

### Question Classification (`question_classify.txt`)
Used with Haiku during live interview to quickly determine if the interviewer's speech is a question requiring an answer or just a statement/explanation.

---

## TESTING

### Manual Testing Protocol
Since this app requires live audio, automated testing covers unit logic only. For integration:

1. **Audio Test:** Run `python -m sounddevice` to verify devices are detected
2. **Transcription Test:** Record a 10-second clip → feed to Whisper → verify output
3. **AI Test:** Send a sample question to Claude with a test system prompt → verify response quality
4. **Stealth Test:** Open Zoom → share screen → verify overlay is NOT visible in the shared view
5. **End-to-End Test:** Run a mock interview with a friend on Zoom and test the full pipeline

### Unit Tests
```
backend/tests/
├── test_file_parser.py        ← Test PDF/DOCX parsing
├── test_context_builder.py    ← Test prompt generation with sample data
├── test_question_detector.py  ← Test question vs statement classification
└── test_ai_engine.py          ← Test Claude streaming with mock responses
```

---

## UPDATING APPROACHES

As the team discovers better ways to implement features, update `docs/APPROACH_LOG.md` with:

```markdown
## [DATE] — [Feature] — [Who updated]
### What changed
[Description of the new approach]
### Why
[Reason the old approach didn't work or the new one is better]
### Impact on other modules
[Which other files/modules need to change]
```

**Codex: ALWAYS check `docs/APPROACH_LOG.md` before implementing any feature. If an entry exists for the feature you're building, follow the updated approach — NOT the original architecture doc.**

---

## QUICK REFERENCE: Key files Codex should read

| When working on... | Read these files first |
|--------------------|----------------------|
| Any task | `CODEX_INSTRUCTIONS.md` (this file) + `docs/APPROACH_LOG.md` |
| Backend audio | `docs/ARCHITECTURE.md` §4.2 + `docs/INTERFACES.md` |
| AI engine | `docs/ARCHITECTURE.md` §4.3 + `backend/app/prompts/` |
| Context builder | `docs/ARCHITECTURE.md` §4.1 + `backend/app/prompts/` |
| Frontend overlay | `docs/ARCHITECTURE.md` §4.4 + `docs/INTERFACES.md` (WS protocol) |
| Electron stealth | `docs/ARCHITECTURE.md` §4.4 + `electron/main.js` |
| Adding a new feature | `docs/DECISIONS.md` + this file's "4 Features" section |
