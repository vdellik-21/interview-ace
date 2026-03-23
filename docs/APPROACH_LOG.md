# APPROACH LOG — InterviewAce

> **Codex: ALWAYS read this file before implementing any feature.**
> If an entry exists for the feature you're working on, follow the updated approach — NOT the original architecture doc.
> Entries are newest-first.

---

## How to add an entry

```markdown
## [YYYY-MM-DD] — [Feature/Module Name] — [Your Name]
### What changed
[Description of the new approach]
### Why
[Why the old approach didn't work or the new one is better]
### Impact on other modules
[List any files/modules that need corresponding changes]
### Status
[Proposed | Approved | Implemented]
```

---

## Log Entries

_No entries yet. Add the first one when you discover a better approach during development._

<!--
EXAMPLE ENTRY (delete when real entries are added):

## 2026-03-25 — Audio Capture — Dev 2
### What changed
Switched from `sounddevice` to `pyaudiowpatch` for Windows system audio capture.
WASAPI loopback on Windows doesn't need VB-Cable at all — `pyaudiowpatch` can capture
system audio directly.
### Why
VB-Cable setup was too complicated for Windows users. pyaudiowpatch provides direct
WASAPI loopback capture without any virtual audio device.
### Impact on other modules
- `backend/app/services/audio_capture.py` — Add Windows-specific capture path
- `scripts/setup_audio_win.ps1` — Simplify (no VB-Cable needed)
- `docs/ARCHITECTURE.md` §2.2 — Update dependencies table
### Status
Proposed
-->
