# 🎯 InterviewAce — Stealth AI Interview Copilot

> An open-source, self-hosted alternative to FinalRound.ai. Real-time AI interview assistance that's invisible to screen share.

[![Built with Codex](https://img.shields.io/badge/AI-Codex%20CLI-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()
[![Status](https://img.shields.io/badge/status-In%20Development-yellow)]()

---

## What is InterviewAce?

InterviewAce is a desktop app that acts as your invisible AI co-pilot during live job interviews. It:

- **Listens** to both the interviewer (system audio) and you (microphone) simultaneously
- **Transcribes** in real-time with speaker separation
- **Generates live answers** from full resume/JD context using `gpt-5-mini`, with prep artifacts used as support context
- **Displays suggestions** in a stealth overlay that's completely invisible during screen share

**Cost:** ~$0.50 per interview vs $90+/month on FinalRound.ai

---

## Features

| Feature | Description |
|---------|-------------|
| 🔇 **Stealth Mode** | Overlay is invisible to Zoom/Meet/Teams screen share, screenshots, and recordings |
| 🎙️ **Dual Audio Capture** | Separately captures interviewer (system audio) and your voice (mic) |
| ⚡ **Instant AI Answers** | Prepared answer bank + optional local Ollama for fast live responses |
| 📄 **Context-Aware** | Upload resume + JD + notes → AI uses YOUR experience in every answer |
| 🧠 **Smart Detection** | Automatically detects when the interviewer asks a question vs just talking |
| ⌨️ **Keyboard Shortcuts** | Panic hide, toggle visibility, regenerate, resize — all via hotkeys |

---

## Quick Start

### Prerequisites
- Node.js 18+ and npm
- Python 3.11+
- [BlackHole 2ch](https://existential.audio/blackhole/) (Mac) or [VB-Audio Cable](https://vb-audio.com/Cable/) (Windows)
- OpenAI API key in `.env`

### Setup

```bash
# Clone
git clone https://github.com/<your-username>/interview-ace.git
cd interview-ace

# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend && npm install

# Electron
cd ../electron && npm install

# Configure
cp .env.example .env
# Add your audio device names to .env if you want to override defaults
# Add OPENAI_API_KEY for prep + live answers

# Audio routing (one-time)
bash scripts/setup_audio_mac.sh   # Mac
# or
powershell scripts/setup_audio_win.ps1   # Windows

# Run
bash scripts/dev.sh
```

---

## How It Works

```
Before Interview:
  Upload Resume + JD + Context Files
  → AI pre-processes and builds a master context prompt
  → Predicts likely questions, maps your skills to JD
  → Builds an answer bank grounded in your resume and JD

During Interview:
  System Audio (Interviewer) ──→ Whisper Transcription ──→ Question Detected?
  Mic Audio (You) ─────────────→ Whisper Transcription     │
                                                            ▼ YES
                                      Prepared Answer Bank / gpt-5-mini / Codex
                                                            │
                                                            ▼
                                                    Stealth Overlay
                                                    ┌─────────────────┐
                                                    │ Suggested Answer │
                                                    │ Key Points       │
                                                    │ Caution          │
                                                    └─────────────────┘
```

---

## Team

Built by 3 friends who got tired of paying $90/month for interview prep tools.

| Developer | Focus |
|-----------|-------|
| Vineeth | Backend + AI Engine |
| Dev 2 | Audio Capture + Transcription |
| Dev 3 | Frontend + Electron Shell |

---

## Contributing

This is currently a private build for our friend group, but the repo is public for transparency. If you want to fork and build your own — go for it!

---

## Tech Stack

- **Electron** — Desktop shell with stealth window (`setContentProtection`)
- **React + Vite + Tailwind** — UI (prep dashboard + stealth overlay)
- **Python + FastAPI** — Backend server with WebSocket support
- **OpenAI Responses API (`gpt-5-mini`)** — prep pipeline + live answers
- **faster-whisper** — Local speech-to-text (free, no API cost)
- **BlackHole / VB-Cable** — Virtual audio routing for system audio capture

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+H` | Toggle overlay visibility |
| `Ctrl+Shift+P` | **PANIC** — instant hide |
| `Ctrl+Shift+L` | Move overlay left ↔ right |
| `Ctrl+Shift+R` | Regenerate last answer |
| `Ctrl+Shift+S` | Shorter answer |
| `Ctrl+Shift+D` | More detailed answer |
| `Ctrl+Shift+=/-` | Increase/decrease font |

---

## License

MIT — Use it however you want.
