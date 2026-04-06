"""
InterviewAce — Transcription Service
Converts audio numpy arrays to text using faster-whisper (local, free).

Owner: Dev 2
Status: STUB — core logic implemented, needs latency testing
"""

import asyncio
import logging
import time

import numpy as np
from faster_whisper import WhisperModel

from ..config import settings

logger = logging.getLogger("interviewace.transcription")


class TranscriptionService:
    """
    Local speech-to-text using faster-whisper.
    Runs entirely on-device — no audio sent to external APIs.
    
    Model options (speed vs accuracy on M1 Mac, 10s audio):
        tiny.en  → ~0.15s  (good enough for clear audio)
        base.en  → ~0.4s   (RECOMMENDED — best balance)
        small.en → ~1.0s   (most accurate, slower)
    """

    def __init__(
        self,
        model_size: str = None,
        device: str = None,
        vocabulary_hints: list[str] | None = None,
    ):
        """
        Args:
            model_size: Whisper model size. Default from settings.
            device: "cpu" or "cuda". Default from settings.
        """
        model_size = model_size or settings.whisper_model
        device = device or settings.whisper_device

        # Use int8 quantization for speed on CPU
        compute_type = "int8" if device == "cpu" else "float16"

        logger.info(
            "Loading Whisper model | model=%s | device=%s | compute_type=%s",
            model_size,
            device,
            compute_type,
        )
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )
        cleaned_hints = [
            hint.strip()
            for hint in (vocabulary_hints or [])
            if isinstance(hint, str) and hint.strip()
        ]
        if cleaned_hints:
            prompt_terms = ", ".join(cleaned_hints[:40])
            self.initial_prompt = (
                "Technical interview terms, tools, and names that may appear: "
                f"{prompt_terms}."
            )
        else:
            self.initial_prompt = None
        self._transcribe_lock = asyncio.Lock()
        logger.info(
            "Whisper model loaded successfully | hint_terms=%s",
            len(cleaned_hints),
        )

    async def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe a speech segment.

        Args:
            audio: numpy array of audio data
                   Expected: float32, 16000 Hz, mono

        Returns:
            Transcribed text. Empty string if no speech detected.
        """
        if audio is None or len(audio) == 0:
            return ""

        # Ensure float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        started_at = time.perf_counter()

        # Keep the full Whisper decode off the event loop and avoid running
        # multiple CPU-heavy transcriptions in parallel on the same model.
        def _transcribe_sync() -> str:
            segments, _info = self.model.transcribe(
                audio,
                beam_size=1,             # Fastest decoding
                language="en",           # English only (faster than auto-detect)
                temperature=0.0,
                initial_prompt=self.initial_prompt,
                condition_on_previous_text=False,
                vad_filter=False,
            )

            text_parts = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    text_parts.append(text)

            return " ".join(text_parts).strip()

        async with self._transcribe_lock:
            result = await asyncio.to_thread(_transcribe_sync)

        # Filter out tiny fragments (noise, breathing, etc.)
        if len(result) < 3:
            return ""

        logger.info(
            "Transcription completed | chars=%s | duration_ms=%.0f",
            len(result),
            (time.perf_counter() - started_at) * 1000,
        )
        return result
