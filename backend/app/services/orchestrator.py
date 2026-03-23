"""
InterviewAce — Interview Orchestrator
The central controller that connects:
  Audio Capture → Transcription → Question Detection → AI Engine → WebSocket UI

Owner: Dev 1 (Vineeth)
Status: STUB — core flow implemented, needs integration testing
"""

import asyncio
import time
import json
from typing import Optional
from datetime import datetime

from fastapi import WebSocket

from ..models.session import InterviewSession, TranscriptEntry
from .audio_capture import DualAudioCapture
from .transcription import TranscriptionService
from .question_detector import QuestionDetector
from .ai_engine import LiveAIEngine


class InterviewOrchestrator:
    """
    The brain of the live interview copilot.
    Coordinates all services and manages the real-time pipeline.
    """

    def __init__(self, session: InterviewSession, websocket: WebSocket):
        """
        Args:
            session: Pre-built InterviewSession (from context_builder)
            websocket: Active WebSocket connection to the Electron overlay
        """
        self.session = session
        self.ws = websocket

        # Initialize services
        self.audio = DualAudioCapture(
            system_device=session.system_audio_device,
            mic_device=session.mic_device,
        )
        self.transcriber = TranscriptionService()
        self.question_detector = QuestionDetector()
        self.ai_engine = LiveAIEngine(session)

        # State
        self.interviewer_buffer = ""
        self.candidate_buffer = ""
        self.last_interviewer_speech_time = 0.0
        self.is_running = False
        self.transcript_log: list[TranscriptEntry] = []

    async def start(self):
        """
        Start the live interview copilot.
        Begins audio capture and processing pipeline.
        Blocks until stop() is called.
        """
        self.is_running = True
        self.session.status = "live"

        await self._send_ws({"type": "status", "text": "🟢 Copilot is LIVE"})

        try:
            await self.audio.start(self._on_speech_segment)
        except Exception as e:
            await self._send_ws({
                "type": "error",
                "message": f"Audio capture error: {str(e)}"
            })
            self.is_running = False

    async def stop(self):
        """Stop all capture and processing. Save transcript."""
        self.is_running = False
        await self.audio.stop()
        self.session.status = "ended"
        await self._send_ws({"type": "status", "text": "🔴 Session ended"})

        # Save transcript to file
        await self._save_transcript()

    async def handle_user_action(self, action: dict):
        """
        Handle actions from the frontend overlay.
        
        Args:
            action: Parsed JSON message from WebSocket
        """
        action_type = action.get("type", "")

        if action_type == "stop_session":
            await self.stop()

        elif action_type == "regenerate":
            await self._regenerate_answer(modifier=None)

        elif action_type == "shorter":
            await self._regenerate_answer(modifier="shorter")

        elif action_type == "more_detail":
            await self._regenerate_answer(modifier="more_detail")

        elif action_type == "listening_mode":
            # TODO: Implement pause/resume of question detection
            pass

        elif action_type == "update_model":
            new_model = action.get("model", self.session.model)
            self.session.model = new_model
            await self._send_ws({
                "type": "status",
                "text": f"🔄 Model switched to {new_model}"
            })

    async def _on_speech_segment(self, speaker: str, audio_data):
        """
        Called by DualAudioCapture when a complete speech segment is detected.
        
        Args:
            speaker: "interviewer" or "candidate"
            audio_data: numpy array of audio (float32, 16000 Hz, mono)
        """
        # Transcribe the audio
        text = await self.transcriber.transcribe(audio_data)
        if not text:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")

        # Log transcript
        entry = TranscriptEntry(speaker=speaker, text=text)
        self.transcript_log.append(entry)

        # Send transcript to UI
        await self._send_ws({
            "type": "transcript",
            "speaker": speaker,
            "text": text,
            "timestamp": timestamp,
        })

        if speaker == "interviewer":
            self.interviewer_buffer += " " + text
            self.last_interviewer_speech_time = time.time()

            # Check if this is a question
            is_question = await self.question_detector.is_question(
                self.interviewer_buffer.strip()
            )

            if is_question:
                # Wait a bit for the question to fully complete
                await asyncio.sleep(1.0)

                # Verify interviewer stopped talking
                if time.time() - self.last_interviewer_speech_time >= 1.0:
                    await self._handle_question()

        elif speaker == "candidate":
            self.candidate_buffer += " " + text

    async def _handle_question(self):
        """
        Called when a complete interviewer question is detected.
        Triggers AI answer generation with streaming.
        """
        question = self.interviewer_buffer.strip()
        self.interviewer_buffer = ""

        if not question:
            return

        # Mark the last transcript entry as a question
        if self.transcript_log:
            self.transcript_log[-1].is_question = True

        # Notify UI that a question was detected
        await self._send_ws({
            "type": "question_detected",
            "text": question,
        })

        # Generate answer with streaming tokens
        try:
            await self.ai_engine.generate_answer(
                interviewer_text=question,
                candidate_text=self.candidate_buffer.strip() or None,
                on_token=self._on_answer_token,
            )
            await self._send_ws({"type": "answer_complete"})

        except Exception as e:
            await self._send_ws({
                "type": "error",
                "message": f"AI error: {str(e)}. Try regenerating."
            })

        # Reset candidate buffer after answer is generated
        self.candidate_buffer = ""

    async def _on_answer_token(self, token: str):
        """Send each streamed token to the UI."""
        await self._send_ws({
            "type": "answer_token",
            "token": token,
        })

    async def _regenerate_answer(self, modifier: Optional[str]):
        """Regenerate the last answer."""
        await self._send_ws({
            "type": "question_detected",
            "text": "(Regenerating...)",
        })

        try:
            await self.ai_engine.regenerate(
                modifier=modifier,
                on_token=self._on_answer_token,
            )
            await self._send_ws({"type": "answer_complete"})
        except Exception as e:
            await self._send_ws({
                "type": "error",
                "message": f"Regeneration failed: {str(e)}"
            })

    async def _send_ws(self, data: dict):
        """Send a JSON message to the frontend via WebSocket."""
        try:
            await self.ws.send_json(data)
        except Exception:
            # WebSocket might be closed
            pass

    async def _save_transcript(self):
        """Save the full transcript to a JSON file."""
        import os

        transcript_data = {
            "session_id": self.session.session_id,
            "model": self.session.model,
            "started_at": self.session.created_at.isoformat(),
            "ended_at": datetime.now().isoformat(),
            "transcript": [
                {
                    "speaker": e.speaker,
                    "text": e.text,
                    "timestamp": e.timestamp.isoformat(),
                    "is_question": e.is_question,
                }
                for e in self.transcript_log
            ],
        }

        filepath = os.path.join(
            "..", "data", "sessions", f"{self.session.session_id}.json"
        )
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w") as f:
            json.dump(transcript_data, f, indent=2)
