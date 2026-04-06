"""
InterviewAce — Interview Orchestrator
The central controller that connects:
  Audio Capture → Transcription → Question Detection → AI Engine → WebSocket UI

Owner: Dev 1 (Vineeth)
Status: STUB — core flow implemented, needs integration testing
"""

import asyncio
import json
import logging
import time
from typing import Optional
from datetime import datetime

from fastapi import WebSocket

from ..config import settings
from ..models.session import InterviewSession, TranscriptEntry
from .audio_capture import DualAudioCapture
from .transcription import TranscriptionService
from .question_detector import QuestionDetector
from .ai_engine import LiveAIEngine
from .transcript_corrector import TranscriptCorrector

logger = logging.getLogger("interviewace.orchestrator")


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
            mic_device=session.mic_device if settings.capture_candidate_audio else None,
            silence_threshold=settings.silence_threshold,
            silence_duration=settings.silence_duration,
        )
        self.transcript_corrector = TranscriptCorrector(session)
        self.transcriber = TranscriptionService(
            vocabulary_hints=self.transcript_corrector.transcription_hints(),
        )
        self.question_detector = QuestionDetector()
        self.ai_engine = LiveAIEngine(session)

        # State
        self.interviewer_buffer = ""
        self.last_interviewer_utterance = ""
        self.candidate_buffer = ""
        self.last_interviewer_speech_time = 0.0
        self.interviewer_buffer_started_at = 0.0
        self.pending_interviewer_turn_type = ""
        self.pending_interviewer_turn_task: Optional[asyncio.Task] = None
        self.turn_queue: asyncio.Queue[dict] = asyncio.Queue()
        self.turn_queue_task: Optional[asyncio.Task] = None
        self.last_enqueued_turn_text = ""
        self.last_enqueued_turn_time = 0.0
        self.is_running = False
        self.transcript_log: list[TranscriptEntry] = []
        logger.info(
            "Orchestrator initialized | session_id=%s | model=%s | system_device=%s | mic_device=%s | candidate_capture=%s",
            session.session_id,
            session.model,
            session.system_audio_device,
            session.mic_device,
            settings.capture_candidate_audio,
        )

    def attach_websocket(self, websocket: WebSocket) -> None:
        """Attach the active websocket, supporting reconnects/dev reloads."""
        self.ws = websocket
        logger.info("Orchestrator websocket attached | session_id=%s", self.session.session_id)

    async def start(self):
        """
        Start the live interview copilot.
        Begins audio capture and processing pipeline.
        Blocks until stop() is called.
        """
        self.is_running = True
        self.session.status = "live"
        self.turn_queue_task = asyncio.create_task(self._process_turn_queue())
        logger.info("Live copilot starting | session_id=%s", self.session.session_id)

        await self._send_ws({"type": "status", "text": "🟢 Copilot is LIVE"})

        try:
            await self.audio.start(self._on_speech_segment)
        except Exception as e:
            logger.exception("Audio capture failed to start")
            await self._send_ws({
                "type": "error",
                "message": f"Audio capture error: {str(e)}"
            })
            self.is_running = False

    async def stop(self):
        """Stop all capture and processing. Save transcript."""
        self.is_running = False
        self._cancel_pending_interviewer_turn_task()
        self._cancel_turn_queue_task()
        await self.audio.stop()
        self.session.status = "ended"
        logger.info("Live copilot stopped | session_id=%s", self.session.session_id)
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
        logger.info("User action received | session_id=%s | type=%s", self.session.session_id, action_type)

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
            logger.info("Session model updated | session_id=%s | model=%s", self.session.session_id, new_model)
            await self._send_ws({
                "type": "status",
                "text": f"🔄 Model switched to {new_model}"
            })

        elif action_type == "force_answer":
            manual_question = self._resolve_manual_question(action.get("question_text"))
            if manual_question:
                normalized_manual_question = self.question_detector.normalize_turn(manual_question) or manual_question
                manual_turn_type = self.question_detector.classify_turn(normalized_manual_question)
                logger.info(
                    "Force answer requested with interviewer text | chars=%s",
                    len(normalized_manual_question),
                )
                await self._send_ws({
                    "type": "status",
                    "text": "⚡ Queueing answer from latest interviewer transcript...",
                })
                self._clear_interviewer_buffer_state()
                await self._enqueue_turn(
                    question=normalized_manual_question,
                    turn_type=manual_turn_type,
                    triggered_manually=True,
                    transcript_index=self._latest_interviewer_transcript_index(),
                )
            else:
                logger.info("Force answer requested but interviewer context was empty")
                await self._send_ws({
                    "type": "status",
                    "text": "⚪ No interviewer question heard yet.",
                })

    def _resolve_manual_question(self, override_text: Optional[str]) -> str:
        """Resolve the best available interviewer text for a manual answer trigger."""
        candidates = [
            (override_text or "").strip(),
            self.interviewer_buffer.strip(),
            self.last_interviewer_utterance.strip(),
            self._latest_interviewer_transcript(limit=1),
        ]
        for candidate in candidates:
            if candidate:
                return candidate
        return ""

    def _latest_interviewer_transcript(self, limit: int = 1) -> str:
        """Return the latest interviewer transcript snippets from the transcript log."""
        recent_chunks: list[str] = []
        for entry in reversed(self.transcript_log):
            if entry.speaker != "interviewer":
                if recent_chunks:
                    break
                continue

            text = entry.text.strip()
            if not text:
                continue

            recent_chunks.append(text)
            if len(recent_chunks) >= limit:
                break

        return " ".join(reversed(recent_chunks)).strip()

    def _latest_interviewer_transcript_index(self, *, before_index: Optional[int] = None) -> Optional[int]:
        start_index = len(self.transcript_log) - 1 if before_index is None else min(before_index - 1, len(self.transcript_log) - 1)
        for index in range(start_index, -1, -1):
            if self.transcript_log[index].speaker == "interviewer":
                return index
        return None

    def _clear_interviewer_buffer_state(self) -> None:
        self._cancel_pending_interviewer_turn_task()
        self.interviewer_buffer = ""
        self.pending_interviewer_turn_type = ""
        self.interviewer_buffer_started_at = 0.0
        self.last_interviewer_speech_time = 0.0

    def _cancel_turn_queue_task(self) -> None:
        task = self.turn_queue_task
        if task and not task.done():
            task.cancel()
        self.turn_queue_task = None

    async def _process_turn_queue(self) -> None:
        try:
            while self.is_running:
                turn = await self.turn_queue.get()
                try:
                    await self._handle_question(
                        question=turn.get("question", ""),
                        triggered_manually=bool(turn.get("triggered_manually", False)),
                        turn_type=str(turn.get("turn_type", "")),
                        transcript_index=turn.get("transcript_index"),
                    )
                finally:
                    self.turn_queue.task_done()
        except asyncio.CancelledError:
            logger.debug("Turn queue processor cancelled")
            return

    async def _enqueue_turn(
        self,
        *,
        question: str,
        turn_type: str,
        triggered_manually: bool,
        transcript_index: Optional[int] = None,
    ) -> None:
        normalized_question = " ".join(question.strip().split())
        if not normalized_question:
            return

        now = time.time()
        if (
            normalized_question == self.last_enqueued_turn_text
            and (now - self.last_enqueued_turn_time) <= 1.2
        ):
            logger.info(
                "Skipping duplicate interviewer turn | chars=%s | turn_type=%s",
                len(normalized_question),
                turn_type,
            )
            return

        self.last_enqueued_turn_text = normalized_question
        self.last_enqueued_turn_time = now
        await self.turn_queue.put(
            {
                "question": normalized_question,
                "turn_type": turn_type,
                "triggered_manually": triggered_manually,
                "transcript_index": transcript_index,
            }
        )
        logger.info(
            "Queued interviewer turn | chars=%s | turn_type=%s | queue_size=%s | trigger=%s",
            len(normalized_question),
            turn_type,
            self.turn_queue.qsize(),
            "manual" if triggered_manually else "automatic",
        )

    async def _commit_buffered_interviewer_turn(
        self,
        *,
        reason: str,
        transcript_index: Optional[int],
    ) -> None:
        question = self.interviewer_buffer.strip()
        if not question:
            return

        normalized_question = self.question_detector.normalize_turn(question) or question
        resolved_turn_type = self.pending_interviewer_turn_type or self.question_detector.classify_turn(normalized_question)
        raw_chars = len(question)
        normalized_chars = len(normalized_question)
        self._clear_interviewer_buffer_state()

        if resolved_turn_type == "statement":
            logger.info(
                "Discarding buffered interviewer turn as statement | reason=%s | raw_chars=%s",
                reason,
                raw_chars,
            )
            return

        logger.info(
            "Committing interviewer turn | reason=%s | raw_chars=%s | normalized_chars=%s | turn_type=%s",
            reason,
            raw_chars,
            normalized_chars,
            resolved_turn_type,
        )
        await self._enqueue_turn(
            question=normalized_question,
            turn_type=resolved_turn_type,
            triggered_manually=False,
            transcript_index=transcript_index,
        )

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
            logger.info("Speech segment ignored because transcription was empty | speaker=%s", speaker)
            return

        corrected_text = self.transcript_corrector.correct(text)
        if corrected_text and corrected_text != text:
            logger.info(
                "Transcript corrected | speaker=%s | before=%s | after=%s",
                speaker,
                text,
                corrected_text,
            )
        text = corrected_text or text

        timestamp = datetime.now().strftime("%H:%M:%S")

        # Log transcript
        entry = TranscriptEntry(speaker=speaker, text=text)
        self.transcript_log.append(entry)
        logger.info(
            "Transcript captured | speaker=%s | chars=%s | timestamp=%s",
            speaker,
            len(text),
            timestamp,
        )

        # Send transcript to UI
        await self._send_ws({
            "type": "transcript",
            "speaker": speaker,
            "text": text,
            "timestamp": timestamp,
        })

        if speaker == "interviewer":
            now = time.time()
            await self._flush_stale_interviewer_turn(now)

            normalized_segment = self.question_detector.normalize_turn(text) or text.strip()
            previous_turn_index = self._latest_interviewer_transcript_index(before_index=len(self.transcript_log) - 1)
            if (
                self.interviewer_buffer.strip()
                and self.question_detector.starts_new_prompt(self.interviewer_buffer, normalized_segment)
            ):
                logger.info(
                    "Incoming interviewer chunk starts a fresh prompt; committing previous buffered turn before merge"
                )
                await self._commit_buffered_interviewer_turn(
                    reason="new_prompt_boundary",
                    transcript_index=previous_turn_index,
                )

            self.interviewer_buffer = f"{self.interviewer_buffer.strip()} {text}".strip()
            self.last_interviewer_utterance = text.strip()
            self.last_interviewer_speech_time = now
            if not self.interviewer_buffer_started_at:
                self.interviewer_buffer_started_at = now

            turn_text = self.question_detector.normalize_turn(self.interviewer_buffer) or self.interviewer_buffer.strip()
            turn_type = self.question_detector.classify_turn(turn_text)
            logger.info("Interviewer buffer evaluated | turn_type=%s", turn_type)

            if turn_type != "statement":
                self.pending_interviewer_turn_type = turn_type
                self._schedule_interviewer_turn_finalization()

        elif speaker == "candidate":
            self.candidate_buffer += " " + text
            logger.info("Candidate buffer updated | chars=%s", len(self.candidate_buffer.strip()))

    def _cancel_pending_interviewer_turn_task(self) -> None:
        task = self.pending_interviewer_turn_task
        if task and not task.done():
            task.cancel()
        self.pending_interviewer_turn_task = None

    def _schedule_interviewer_turn_finalization(self) -> None:
        self._cancel_pending_interviewer_turn_task()
        scheduled_at = self.last_interviewer_speech_time
        turn_type = self.pending_interviewer_turn_type
        self.pending_interviewer_turn_task = asyncio.create_task(
            self._finalize_interviewer_turn_after_delay(scheduled_at, turn_type)
        )

    async def _finalize_interviewer_turn_after_delay(self, scheduled_at: float, turn_type: str) -> None:
        try:
            await asyncio.sleep(0.18)
            if not self.is_running:
                return
            if self.last_interviewer_speech_time > scheduled_at:
                return

            question = self.interviewer_buffer.strip()
            if not question:
                return

            if turn_type and self.pending_interviewer_turn_type != turn_type:
                self.pending_interviewer_turn_type = turn_type

            await self._commit_buffered_interviewer_turn(
                reason="quick_finalization",
                transcript_index=self._latest_interviewer_transcript_index(),
            )
        except asyncio.CancelledError:
            logger.debug("Pending interviewer turn finalization cancelled")
            return

    async def _flush_stale_interviewer_turn(self, now: float) -> None:
        question = self.interviewer_buffer.strip()
        if not question or not self.last_interviewer_speech_time:
            return

        age_seconds = now - self.last_interviewer_speech_time
        if age_seconds < 1.25:
            return

        logger.warning(
            "Flushing stale interviewer buffer before merging new speech | chars=%s | age_ms=%.0f",
            len(question),
            age_seconds * 1000,
        )

        await self._commit_buffered_interviewer_turn(
            reason="stale_buffer_flush",
            transcript_index=self._latest_interviewer_transcript_index(),
        )

    async def _handle_question(
        self,
        question: Optional[str] = None,
        triggered_manually: bool = False,
        turn_type: str = "",
        transcript_index: Optional[int] = None,
    ):
        """
        Called when a complete interviewer question is detected.
        Triggers AI answer generation with streaming.
        """
        question = (question or "").strip()

        if not question:
            logger.info("Question handling skipped because interviewer buffer was empty")
            return

        resolved_turn_type = turn_type or self.question_detector.classify_turn(question)
        self.last_interviewer_utterance = question

        if transcript_index is not None and 0 <= transcript_index < len(self.transcript_log):
            self.transcript_log[transcript_index].is_question = True

        # Notify UI that a question was detected
        await self._send_ws({
            "type": "question_detected",
            "text": question,
            "turn_type": resolved_turn_type,
        })
        logger.info(
            "Question detected | chars=%s | trigger=%s | turn_type=%s",
            len(question),
            "manual" if triggered_manually else "automatic",
            resolved_turn_type,
        )

        try:
            live_answer = await self.ai_engine.prepare_live_answer(
                interviewer_text=question,
                candidate_text=(self.candidate_buffer.strip() or None) if settings.capture_candidate_audio else None,
                turn_type=resolved_turn_type,
            )
        except asyncio.TimeoutError:
            logger.warning("Live answer timed out | session_id=%s", self.session.session_id)
            timeout_message = "Live model timed out before returning an answer. Try asking again or press Regenerate."
            await self._send_ws({
                "type": "answer_replace",
                "text": timeout_message,
                "source": "error",
            })
            await self._send_ws({
                "type": "error",
                "message": timeout_message,
            })
            await self._send_ws({
                "type": "status",
                "text": "⚠️ Live model timed out.",
            })
            await self._send_ws({"type": "answer_complete"})
            self.candidate_buffer = ""
            return
        except Exception as exc:
            logger.exception("Live answer generation failed | session_id=%s", self.session.session_id)
            failure_message = f"Live answer failed: {exc}"
            await self._send_ws({
                "type": "answer_replace",
                "text": failure_message,
                "source": "error",
            })
            await self._send_ws({
                "type": "error",
                "message": failure_message,
            })
            await self._send_ws({
                "type": "status",
                "text": "⚠️ Live answer failed.",
            })
            await self._send_ws({"type": "answer_complete"})
            self.candidate_buffer = ""
            return

        answer_text = live_answer.get("text", "").strip()
        answer_source = live_answer.get("source", "live-model")

        if answer_text:
            await self._send_ws({
                "type": "answer_replace",
                "text": answer_text,
                "source": answer_source,
            })
            await self._send_ws({
                "type": "status",
                "text": "⚡ Live answer ready.",
            })
            logger.info(
                "Live answer sent to overlay | chars=%s | source=%s",
                len(answer_text),
                answer_source,
            )
            self.ai_engine.record_live_answer(
                interviewer_text=question,
                candidate_text=(self.candidate_buffer.strip() or None) if settings.capture_candidate_audio else None,
                answer_text=answer_text,
            )
            await self._send_ws({"type": "answer_complete"})
            logger.info("Live answer completed without remote refinement")
        else:
            await self._send_ws({
                "type": "error",
                "message": "No answer could be prepared for this question yet. Try regenerate.",
            })

        # Reset candidate buffer after answer is generated
        self.candidate_buffer = ""
        logger.info("Candidate buffer reset after answer generation")

    async def _on_answer_token(self, token: str):
        """Send each streamed token to the UI."""
        logger.debug("Answer token sent | chars=%s", len(token))
        await self._send_ws({
            "type": "answer_token",
            "token": token,
            "source": self.session.model,
        })

    async def _regenerate_answer(self, modifier: Optional[str]):
        """Regenerate the last answer."""
        await self._send_ws({
            "type": "question_detected",
            "text": "(Regenerating...)",
        })
        logger.info("Regeneration requested | modifier=%s", modifier or "default")

        try:
            await self.ai_engine.regenerate(
                modifier=modifier,
                on_token=self._on_answer_token,
            )
            await self._send_ws({"type": "answer_complete"})
            logger.info("Regeneration completed")
        except Exception as e:
            logger.exception("Regeneration failed")
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
            logger.debug("WebSocket send skipped because connection is unavailable")
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
        logger.info("Transcript saved | path=%s | entries=%s", filepath, len(self.transcript_log))
