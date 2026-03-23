# ARCHITECTURE — InterviewAce

> This document describes the system architecture. Codex agents should treat this as the implementation blueprint.
> **Always check `APPROACH_LOG.md` for updates before implementing — approaches may have changed.**

---

## 1. HIGH-LEVEL DATA FLOW

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRE-INTERVIEW PHASE                          │
│                                                                     │
│  User uploads:  Resume (PDF/DOCX)                                  │
│                 Job Description (text/file)                         │
│                 Context files (optional, any format)                │
│                 Selects Claude model                                │
│                          │                                          │
│                          ▼                                          │
│           ┌──────────────────────────────┐                         │
│           │     Context Builder          │                         │
│           │  1. Parse all files → text    │                         │
│           │  2. Claude extracts resume    │                         │
│           │  3. Claude analyzes JD        │                         │
│           │  4. Claude maps resume↔JD     │                         │
│           │  5. Claude builds STAR stories│                         │
│           │  6. Claude predicts questions │                         │
│           │  7. Build master system prompt│                         │
│           └──────────────┬───────────────┘                         │
│                          │                                          │
│                          ▼                                          │
│                 InterviewSession object                             │
│                 (cached, ready for live use)                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           │  User clicks "Go Live"
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        LIVE INTERVIEW PHASE                         │
│                                                                     │
│  ┌───────────────┐    ┌───────────────┐                            │
│  │ System Audio   │    │ Microphone    │                            │
│  │ (Interviewer)  │    │ (Candidate)   │                            │
│  │ via BlackHole  │    │ direct input  │                            │
│  └───────┬───────┘    └───────┬───────┘                            │
│          │                     │                                    │
│          ▼                     ▼                                    │
│  ┌─────────────────────────────────────┐                           │
│  │      DualAudioCapture               │                           │
│  │  • Two concurrent audio streams     │                           │
│  │  • Voice Activity Detection (VAD)   │                           │
│  │  • Silence detection → end of speech│                           │
│  └───────────────┬─────────────────────┘                           │
│                  │                                                   │
│                  ▼                                                   │
│  ┌─────────────────────────────────────┐                           │
│  │      TranscriptionService           │                           │
│  │  • faster-whisper (local)           │                           │
│  │  • base.en model (speed priority)   │                           │
│  │  • Returns: (speaker, text)         │                           │
│  └───────────────┬─────────────────────┘                           │
│                  │                                                   │
│                  ▼                                                   │
│  ┌─────────────────────────────────────┐                           │
│  │      QuestionDetector               │                           │
│  │  • Uses Haiku for fast classify     │                           │
│  │  • "Is this a question?" → yes/no   │                           │
│  │  • Waits for pause before triggering│                           │
│  └───────┬──────────────┬──────────────┘                           │
│          │              │                                           │
│     NOT a question   IS a question                                  │
│          │              │                                           │
│          ▼              ▼                                           │
│    [Send transcript  ┌─────────────────────────────┐               │
│     to UI only]      │      LiveAIEngine            │               │
│                      │  • Claude API (streaming)    │               │
│                      │  • system = master prompt    │               │
│                      │  • messages = conversation   │               │
│                      │  • Streams tokens via WS     │               │
│                      └──────────────┬──────────────┘               │
│                                     │                               │
│                                     ▼                               │
│                      ┌──────────────────────────────┐              │
│                      │  WebSocket → Electron Overlay │              │
│                      │  • Live transcript feed       │              │
│                      │  • Streamed answer tokens     │              │
│                      │  • Status indicators          │              │
│                      └──────────────────────────────┘              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. MODULE SPECIFICATIONS

### 2.1 Context Builder (`backend/app/services/context_builder.py`)

**Owner:** Dev 1 (Vineeth)

**Purpose:** Takes uploaded files, processes them through Claude, and produces an `InterviewSession` object containing the master system prompt and all pre-computed context.

**Input:**
```python
class PrepRequest(BaseModel):
    resume_path: str              # Path to uploaded resume file
    jd_text: str                  # Job description (raw text)
    context_files: list[str]      # Paths to optional context files
    model: str                    # "claude-sonnet-4-20250514" | "claude-opus-4-20250514" | "claude-haiku-4-5-20251001"
```

**Output:**
```python
class InterviewSession(BaseModel):
    session_id: str
    model: str
    system_prompt: str            # The big master prompt (~3000 tokens)
    resume_structured: dict       # Parsed resume data
    jd_structured: dict           # Parsed JD requirements
    skill_mapping: dict           # Resume↔JD alignment
    predicted_questions: list     # 20 predicted questions
    conversation_history: list    # Starts empty, grows during interview
    created_at: datetime
```

**Pipeline Steps:**
1. `file_parser.parse()` — Convert PDF/DOCX to plain text
2. Claude call #1 — Extract structured resume data (JSON)
3. Claude call #2 — Analyze JD requirements (JSON)
4. Claude call #3 — Map resume to JD + build STAR stories (JSON)
5. Claude call #4 — Predict 20 likely questions
6. `build_system_prompt()` — Assemble the master prompt from all outputs

**Performance:** Should complete in 15–30 seconds. Show progress via WebSocket.

---

### 2.2 Dual Audio Capture (`backend/app/services/audio_capture.py`)

**Owner:** Dev 2

**Purpose:** Simultaneously captures two audio streams — system audio (interviewer) and microphone (candidate) — with Voice Activity Detection.

**Dependencies:**
- `sounddevice` — Cross-platform audio I/O
- BlackHole 2ch (Mac) or VB-Cable (Windows) for system audio routing

**Interface:**
```python
class DualAudioCapture:
    def __init__(self, system_device: str, mic_device: str, sample_rate: int = 16000):
        """
        Args:
            system_device: Name of virtual audio device (e.g., "BlackHole 2ch")
            mic_device: Name of microphone device (e.g., "MacBook Pro Microphone")
            sample_rate: Audio sample rate (16000 Hz for Whisper)
        """

    async def start(self, on_speech_segment: Callable[[str, np.ndarray], Awaitable[None]]):
        """
        Start capturing both streams.

        Args:
            on_speech_segment: Called when a complete speech segment is detected.
                               Params: (speaker: "interviewer"|"candidate", audio: numpy array)
        """

    async def stop(self):
        """Stop both capture streams."""

    def list_devices(self) -> dict:
        """Return available system audio and mic devices."""
```

**Voice Activity Detection (VAD) Logic:**
- Compute RMS energy for each audio chunk (500ms)
- If RMS > threshold → speech is happening
- Track silence duration after speech starts
- If silence > 1.5 seconds → speech segment is complete
- Pass complete segment (as numpy array) to callback

**Critical Notes:**
- Both streams must run concurrently (use `asyncio.gather`)
- Audio format: 16-bit, 16000 Hz, mono (what Whisper expects)
- Buffer up to 30 seconds of audio per segment max
- If no speech detected for 60 seconds, send a heartbeat to UI

---

### 2.3 Transcription Service (`backend/app/services/transcription.py`)

**Owner:** Dev 2

**Purpose:** Converts audio numpy arrays to text using faster-whisper running locally.

**Interface:**
```python
class TranscriptionService:
    def __init__(self, model_size: str = "base.en", device: str = "cpu"):
        """
        Args:
            model_size: Whisper model. "base.en" recommended for speed.
                        Options: "tiny.en", "base.en", "small.en"
            device: "cpu" or "cuda"
        """

    async def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe a speech segment.

        Args:
            audio: numpy array of audio data (16000 Hz, mono, float32)

        Returns:
            Transcribed text string. Empty string if no speech detected.
        """
```

**Performance Targets:**
| Model | Speed (10s audio on M1 Mac) | Accuracy |
|-------|-----------------------------|----------|
| tiny.en | ~0.15s | Good enough for clear audio |
| base.en | ~0.4s | **Recommended default** |
| small.en | ~1.0s | Best accuracy, slower |

---

### 2.4 Question Detector (`backend/app/services/question_detector.py`)

**Owner:** Dev 2

**Purpose:** Determines whether the interviewer's speech is a question requiring an answer or just a statement/explanation/small talk.

**Interface:**
```python
class QuestionDetector:
    def __init__(self):
        """Uses Haiku for fast classification."""

    async def is_question(self, text: str) -> bool:
        """
        Returns True if the text is a question the candidate should answer.
        Returns False for:
          - Interviewer explaining the role/company
          - Small talk / greetings
          - Transition phrases ("Let's move on to...")
          - Interviewer thinking out loud
        """

    async def classify(self, text: str) -> dict:
        """
        Detailed classification.
        Returns: {
            "is_question": bool,
            "question_type": "behavioral"|"technical"|"situational"|"greeting"|"none",
            "confidence": float (0-1)
        }
        """
```

**Implementation Notes:**
- Always use `claude-haiku-4-5-20251001` for this — speed is critical
- Keep the prompt very short (< 100 tokens) for fast inference
- Can also use simple heuristics as a fast first-pass:
  - Ends with "?" → likely a question
  - Starts with "Tell me", "Describe", "How", "What", "Why" → likely a question
  - Short utterance < 5 words → probably not a question worth answering
- Use Haiku only for ambiguous cases (save cost)

---

### 2.5 AI Engine (`backend/app/services/ai_engine.py`)

**Owner:** Dev 1 (Vineeth)

**Purpose:** Manages Claude API calls for live interview answer generation. Streams tokens for instant display.

**Interface:**
```python
class LiveAIEngine:
    def __init__(self, session: InterviewSession):
        """
        Args:
            session: Pre-built InterviewSession with system_prompt and model selection
        """

    async def generate_answer(
        self,
        interviewer_text: str,
        candidate_text: str | None,
        on_token: Callable[[str], Awaitable[None]]
    ) -> str:
        """
        Generate a streamed answer to the interviewer's question.

        Args:
            interviewer_text: What the interviewer just said
            candidate_text: What the candidate said recently (for context), or None
            on_token: Callback fired for each streamed token

        Returns:
            Full completed response text
        """

    async def regenerate(self, modifier: str | None = None) -> AsyncGenerator[str, None]:
        """
        Regenerate the last answer, optionally with a modifier.

        Args:
            modifier: "shorter", "more_detail", or None for straight regen
        """
```

**Streaming Implementation:**
```python
async with client.messages.stream(
    model=session.model,
    max_tokens=1024,
    system=session.system_prompt,
    messages=session.conversation_history,
) as stream:
    async for token in stream.text_stream:
        await on_token(token)
```

**Conversation History Management:**
- Append every interviewer question and AI answer to `conversation_history`
- Keep a sliding window of last 20 exchanges (40 messages)
- When trimming, always keep the first exchange (establishes context)

---

### 2.6 Orchestrator (`backend/app/services/orchestrator.py`)

**Owner:** Dev 1 (Vineeth)

**Purpose:** The central controller that wires audio → transcription → question detection → AI → WebSocket. This is the "brain" that coordinates all services during a live interview.

**Interface:**
```python
class InterviewOrchestrator:
    def __init__(self, session: InterviewSession, websocket: WebSocket):
        """
        Args:
            session: Pre-built InterviewSession
            websocket: Active WebSocket connection to the frontend
        """

    async def start(self):
        """Start the live copilot. Blocks until stop() is called."""

    async def stop(self):
        """Stop all capture and processing."""

    async def handle_user_action(self, action: dict):
        """Handle actions from frontend (regenerate, shorter, etc.)"""
```

**Internal Flow:**
1. `DualAudioCapture.start()` begins capturing both streams
2. On each speech segment → `TranscriptionService.transcribe()`
3. If speaker is interviewer → `QuestionDetector.is_question()`
4. If question detected → wait for question to complete (1.5s silence)
5. Fire `LiveAIEngine.generate_answer()` with streaming
6. Stream tokens to frontend via WebSocket

---

### 2.7 Stealth Electron Shell (`electron/main.js`)

**Owner:** Dev 3

**Purpose:** Electron wrapper that creates the invisible overlay window and manages system tray, keyboard shortcuts, and window positioning.

**Key Electron APIs:**
```javascript
// Make window invisible to screen capture — THIS IS THE CORE STEALTH MECHANISM
stealthWindow.setContentProtection(true);

// Window properties
new BrowserWindow({
    frame: false,           // No title bar
    transparent: true,      // Transparent background
    alwaysOnTop: true,      // Stays above Zoom/Meet
    skipTaskbar: true,      // Not visible in taskbar/dock
    hasShadow: false,       // No window shadow
});

// Not visible in Mission Control / app switcher
stealthWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
```

**Keyboard Shortcuts (register via `globalShortcut`):**
| Shortcut | Action | Implementation |
|----------|--------|---------------|
| `Ctrl+Shift+H` | Toggle overlay | `stealthWindow.isVisible() ? hide() : show()` |
| `Ctrl+Shift+P` | Panic hide | `stealthWindow.hide()` |
| `Ctrl+Shift+L` | Move left/right | Toggle x position |
| `Ctrl+Shift+=` | Font size up | Send IPC to renderer |
| `Ctrl+Shift+-` | Font size down | Send IPC to renderer |

---

### 2.8 Stealth Overlay UI (`frontend/src/pages/StealthOverlay.jsx`)

**Owner:** Dev 3

**Purpose:** The React component that renders inside the Electron stealth window. Shows live transcript, detected questions, and streaming AI answers.

**UI Layout:**
```
┌─────────────────────────────────────┐
│ 🔴 LIVE  │  Ctrl+Shift+P to hide   │  ← Header (status + help)
├─────────────────────────────────────┤
│ LIVE TRANSCRIPT                     │  ← Scrolling feed (last 5)
│ 🎤 Them: "Tell me about..."        │
│ 🗣️ You: "Thank you for..."         │
├─────────────────────────────────────┤
│ ❓ QUESTION DETECTED                │  ← Blue highlighted box
│ "Tell me about a time you used     │
│  data to drive a marketing..."      │
├─────────────────────────────────────┤
│ 💡 SUGGESTED ANSWER                 │  ← Main area (scrollable)
│ At Ardent Technologies, I led a     │
│ campaign optimization project...    │     ← Streams in live
│                                     │
│ KEY POINTS:                         │
│ • Mention 34% improvement           │
│ • Reference Google Analytics        │
│ • Tie to $45K revenue impact        │
├─────────────────────────────────────┤
│ [🔄 Regen] [✂️ Shorter] [📝 Detail]│  ← Action buttons
└─────────────────────────────────────┘
```

**Design Specs:**
- Width: 420px, Height: screen height - 100px
- Background: `rgba(0, 0, 0, 0.85)` with `backdrop-blur`
- Text: White, system font
- Theme: Dark only (less noticeable if any edge is visible)
- Font size: 14px default, adjustable via shortcuts
- Auto-scroll answer panel as tokens stream in

---

### 2.9 Prep Dashboard UI (`frontend/src/pages/PrepDashboard.jsx`)

**Owner:** Dev 3

**Purpose:** The setup screen shown before the interview. User uploads files, selects model, configures audio, and starts the session.

**UI Sections:**
1. **File Upload Area** — Drag-drop zones for Resume, JD, Context files
2. **Model Selector** — Dropdown: Sonnet (recommended) / Opus / Haiku
3. **Audio Device Config** — Dropdowns for system audio device + mic device
4. **Prep Progress** — Progress bar showing AI prep steps (parsing, analyzing, etc.)
5. **Predicted Questions** — Preview of AI-predicted interview questions
6. **"Go Live" Button** — Launches the stealth overlay and starts capture

---

## 3. DATA MODELS

### Session Data (`backend/app/models/session.py`)

```python
from pydantic import BaseModel
from datetime import datetime

class InterviewSession(BaseModel):
    session_id: str
    model: str                        # Claude model string
    system_prompt: str                # Master prompt (pre-built)
    resume_text: str                  # Raw resume text
    resume_structured: dict           # Parsed resume (JSON)
    jd_text: str                      # Raw JD text
    jd_structured: dict               # Parsed JD requirements (JSON)
    skill_mapping: dict               # Resume↔JD mapping (JSON)
    predicted_questions: list[dict]   # Predicted questions
    context_texts: list[str]          # Additional context file contents
    conversation_history: list[dict]  # Running chat history
    system_audio_device: str          # Selected system audio device name
    mic_device: str                   # Selected mic device name
    created_at: datetime
    status: str = "preparing"         # "preparing" | "ready" | "live" | "ended"

class TranscriptEntry(BaseModel):
    speaker: str                      # "interviewer" | "candidate"
    text: str
    timestamp: datetime
    is_question: bool = False

class AnswerEntry(BaseModel):
    question: str
    answer: str
    timestamp: datetime
```

---

## 4. API ENDPOINTS

### REST Endpoints

```
POST /api/session/create
  Body: { resume: File, jd: str, context_files: File[], model: str }
  Returns: { session_id: str }
  Triggers: Pre-interview context building pipeline

GET /api/session/{session_id}/status
  Returns: { status: str, prep_progress: int }

GET /api/devices
  Returns: { system_devices: str[], mic_devices: str[] }

POST /api/session/{session_id}/end
  Saves transcript and ends session
```

### WebSocket Endpoint

```
WS /api/copilot/{session_id}
  Bidirectional communication for live interview.
  See CODEX_INSTRUCTIONS.md for full message protocol.
```

---

## 5. ENVIRONMENT VARIABLES

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Audio (device names — run `python -c "import sounddevice; print(sounddevice.query_devices())"`)
SYSTEM_AUDIO_DEVICE=BlackHole 2ch
MIC_DEVICE=MacBook Pro Microphone

# Optional (have defaults)
DEFAULT_MODEL=claude-sonnet-4-20250514
WHISPER_MODEL=base.en
WHISPER_DEVICE=cpu
BACKEND_PORT=8000
FRONTEND_PORT=5173
SILENCE_THRESHOLD=0.01
SILENCE_DURATION=1.5
MAX_CONVERSATION_HISTORY=40
```
