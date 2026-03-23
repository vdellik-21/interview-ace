"""
InterviewAce — Transcription Service
Converts audio numpy arrays to text using faster-whisper (local, free).

Owner: Dev 2
Status: STUB — core logic implemented, needs latency testing
"""

import numpy as np
from faster_whisper import WhisperModel

from ..config import settings


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

        print(f"[Transcription] Loading Whisper model: {model_size} on {device} ({compute_type})")
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )
        print(f"[Transcription] Model loaded successfully")

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

        # Run Whisper transcription
        segments, info = self.model.transcribe(
            audio,
            beam_size=1,             # Fastest decoding
            language="en",           # English only (faster than auto-detect)
            vad_filter=True,         # Filter non-speech segments
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
        )

        # Collect all segment texts
        text_parts = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                text_parts.append(text)

        result = " ".join(text_parts).strip()

        # Filter out tiny fragments (noise, breathing, etc.)
        if len(result) < 3:
            return ""

        return result
