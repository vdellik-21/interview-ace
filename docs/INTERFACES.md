# INTERFACES — InterviewAce

> Contracts between modules. When Dev 2 builds audio capture, Dev 1 builds AI engine, and Dev 3 builds the UI, they all need to agree on the data shapes flowing between them. This file is that agreement.
> **If you change an interface, update this file AND notify the other devs.**

---

## Interface 1: Audio Capture → Transcription

**Producer:** `DualAudioCapture` (Dev 2)
**Consumer:** `TranscriptionService` (Dev 2)

```python
# Callback signature that DualAudioCapture calls when a speech segment completes
async def on_speech_segment(speaker: str, audio: np.ndarray) -> None:
    """
    Args:
        speaker: "interviewer" or "candidate"
        audio: numpy array, dtype=float32, sample_rate=16000, mono
               Duration: 0.5s to 30s (variable, depends on how long person spoke)
    """
```

---

## Interface 2: Transcription → Orchestrator

**Producer:** `TranscriptionService` (Dev 2)
**Consumer:** `InterviewOrchestrator` (Dev 1)

```python
# Callback signature for transcription results
async def on_transcription(speaker: str, text: str) -> None:
    """
    Args:
        speaker: "interviewer" or "candidate"
        text: Transcribed text. Always non-empty (empty results are filtered out).
              Minimum 3 characters.
    """
```

---

## Interface 3: Orchestrator → AI Engine

**Producer:** `InterviewOrchestrator` (Dev 1)
**Consumer:** `LiveAIEngine` (Dev 1)

```python
# Call when a question is detected and ready for answering
await ai_engine.generate_answer(
    interviewer_text="Tell me about a time you used data to drive a marketing decision",
    candidate_text="Thank you, that's a great question",  # or None
    on_token=async_callback  # Called with each streamed token (str)
)
```

---

## Interface 4: Backend → Frontend (WebSocket Messages)

**Producer:** Backend (Dev 1 + Dev 2)
**Consumer:** Frontend/Electron (Dev 3)

Full protocol documented in `CODEX_INSTRUCTIONS.md` → "WEBSOCKET MESSAGE PROTOCOL" section.

**Summary of message types (Backend → Frontend):**
| type | payload | sent when |
|------|---------|-----------|
| `status` | `{text: str}` | Connection state changes |
| `transcript` | `{speaker: str, text: str, timestamp: str}` | Every transcription result |
| `question_detected` | `{text: str}` | Interviewer asks a question |
| `answer_token` | `{token: str}` | Each streamed token from Claude |
| `answer_complete` | `{}` | Answer generation finished |
| `prep_progress` | `{step: str, percent: int}` | During session preparation |
| `prep_complete` | `{predicted_questions: list}` | Prep finished |
| `error` | `{message: str}` | Any error |
| `devices` | `{system_devices: list, mic_devices: list}` | Audio device listing |

**Summary of message types (Frontend → Backend):**
| type | payload | sent when |
|------|---------|-----------|
| `start_session` | `{session_id: str}` | User clicks "Go Live" |
| `stop_session` | `{}` | User ends interview |
| `regenerate` | `{}` | User wants new answer |
| `shorter` | `{}` | User wants shorter answer |
| `more_detail` | `{}` | User wants more detail |
| `listening_mode` | `{}` | Pause suggestions |
| `update_model` | `{model: str}` | Change model mid-session |

---

## Interface 5: Context Builder → Session

**Producer:** `ContextBuilder` (Dev 1)
**Consumer:** `InterviewSession` model (shared)

```python
# ContextBuilder.prepare_session() returns:
InterviewSession(
    session_id="uuid4-string",
    model="claude-sonnet-4-20250514",
    system_prompt="You are an elite real-time interview assistant...",  # ~3000 tokens
    resume_text="raw resume text...",
    resume_structured={
        "roles": [...],
        "skills": {"technical": [...], "soft": [...]},
        "education": [...],
        "certifications": [...],
        "projects": [...]
    },
    jd_text="raw JD text...",
    jd_structured={
        "title": "Digital Marketing Manager",
        "required_skills": [...],
        "responsibilities": [...],
        "nice_to_have": [...],
        "culture_signals": [...]
    },
    skill_mapping={
        "matches": [{"jd_req": "...", "resume_exp": "...", "strength": "strong"}],
        "gaps": [...],
        "star_stories": [{"theme": "...", "situation": "...", "task": "...", "action": "...", "result": "..."}]
    },
    predicted_questions=[
        {"question": "...", "type": "behavioral", "best_resume_match": "..."},
        ...
    ],
    context_texts=["additional context file 1 text...", ...],
    conversation_history=[],
    system_audio_device="BlackHole 2ch",
    mic_device="MacBook Pro Microphone",
    created_at=datetime.now(),
    status="ready"
)
```

---

## Interface 6: File Upload → Backend

**Producer:** Frontend `FileUploader.jsx` (Dev 3)
**Consumer:** Backend `/api/session/create` (Dev 1)

```
POST /api/session/create
Content-Type: multipart/form-data

Fields:
  resume: File (required) — PDF or DOCX
  jd_text: string (required) — Job description text
  context_files: File[] (optional) — Additional context files
  model: string (required) — "claude-sonnet-4-20250514" | "claude-opus-4-20250514" | "claude-haiku-4-5-20251001"
  system_audio_device: string (required) — Device name
  mic_device: string (required) — Device name

Response: 200
{
  "session_id": "abc-123-def",
  "status": "preparing"
}
```

---

## Stub Pattern

When a module depends on another module that doesn't exist yet, create a stub:

```python
# Example: AI Engine stub (Dev 1 creates this so Dev 3 can test the UI)
class LiveAIEngineStub:
    """Stub for testing. Returns fake streamed answers."""

    async def generate_answer(self, interviewer_text, candidate_text, on_token):
        fake_answer = f"Great question about '{interviewer_text[:30]}...'. Based on my experience at Ardent Technologies, I led a project that resulted in 34% improvement..."
        for word in fake_answer.split():
            await on_token(word + " ")
            await asyncio.sleep(0.05)  # Simulate streaming delay
        return fake_answer
```

**Rule:** When creating a stub, add a comment `# STUB — replace with real implementation` and log it in `PROGRESS.md`.
