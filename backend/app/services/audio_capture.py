"""
InterviewAce — Dual Audio Capture Service
Captures two audio streams simultaneously:
  - Stream A: System audio (interviewer) via BlackHole/VB-Cable
  - Stream B: Microphone (candidate) via direct input

Owner: Dev 2
Status: STUB — implement the capture loops and VAD logic

IMPORTANT: This module requires platform-specific audio routing:
  - macOS: Install BlackHole 2ch (brew install blackhole-2ch)
  - Windows: Install VB-Audio Cable (https://vb-audio.com/Cable/)
  See scripts/setup_audio_mac.sh or scripts/setup_audio_win.ps1
"""

import asyncio
from collections import deque
import logging
from typing import Callable, Awaitable, Optional

import numpy as np
import sounddevice as sd

from ..config import settings

try:
    import webrtcvad
except ImportError:  # pragma: no cover - fallback path when dependency isn't installed yet
    webrtcvad = None


logger = logging.getLogger("interviewace.audio_capture")


class DualAudioCapture:
    """
    Simultaneously captures system audio (interviewer) and mic audio (candidate).
    
    Uses Voice Activity Detection (VAD) to detect speech boundaries and
    delivers complete speech segments to the callback.
    """

    def __init__(
        self,
        system_device: str,
        mic_device: Optional[str],
        sample_rate: int = 16000,
        silence_threshold: float | None = None,
        silence_duration: float | None = None,
    ):
        """
        Args:
            system_device: Name of virtual audio device (e.g., "BlackHole 2ch")
            mic_device: Name of microphone (e.g., "MacBook Pro Microphone")
            sample_rate: Audio sample rate in Hz (16000 for Whisper)
            silence_threshold: RMS energy below this = silence
            silence_duration: Seconds of silence to mark end of utterance
        """
        self.system_device_idx = self._find_device(system_device)
        self.mic_device_idx = self._find_device(mic_device) if mic_device else None
        self.sample_rate = sample_rate
        self.silence_threshold = (
            settings.silence_threshold if silence_threshold is None else silence_threshold
        )
        self.silence_duration = (
            settings.silence_duration if silence_duration is None else silence_duration
        )
        self.vad_frame_ms = 20
        self.vad_frame_size = int(self.sample_rate * self.vad_frame_ms / 1000)
        self.vad_enabled = webrtcvad is not None and self.sample_rate in {8000, 16000, 32000, 48000}
        self.vad = webrtcvad.Vad(2) if self.vad_enabled else None
        self.pre_roll_frames = max(1, int(0.18 / (self.vad_frame_ms / 1000)))
        self.max_silence_frames = max(4, int(min(self.silence_duration, 0.42) / (self.vad_frame_ms / 1000)))
        self.chunk_duration = 0.1 if self.vad_enabled else 0.25
        self.is_running = False
        logger.info(
            "Audio capture initialized | sample_rate=%s | chunk_duration=%.2f | vad_enabled=%s",
            self.sample_rate,
            self.chunk_duration,
            self.vad_enabled,
        )

    def _find_device(self, name: str) -> int:
        """
        Find audio device index by name.

        Args:
            name: Partial name match for the device

        Returns:
            Device index for sounddevice

        Raises:
            ValueError: If device not found
        """
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if name.lower() in d["name"].lower():
                return i
        available = [d["name"] for d in devices]
        raise ValueError(
            f"Audio device '{name}' not found.\n"
            f"Available devices: {available}\n"
            f"Run: python -c \"import sounddevice; print(sounddevice.query_devices())\""
        )

    async def start(
        self,
        on_speech_segment: Callable[[str, np.ndarray], Awaitable[None]],
    ):
        """
        Start capturing both audio streams.

        Args:
            on_speech_segment: Called when a complete speech segment is detected.
                Params: (speaker: "interviewer"|"candidate", audio: np.ndarray)
                Audio format: float32, 16000 Hz, mono
        """
        self.is_running = True

        tasks = [
            self._capture_stream("interviewer", self.system_device_idx, on_speech_segment),
        ]
        if self.mic_device_idx is not None:
            tasks.append(
                self._capture_stream("candidate", self.mic_device_idx, on_speech_segment)
            )

        await asyncio.gather(*tasks)

    async def _capture_stream(
        self,
        speaker: str,
        device_idx: int,
        callback: Callable[[str, np.ndarray], Awaitable[None]],
    ):
        """
        Capture loop for a single audio stream with VAD.

        Accumulates audio chunks while speech is detected.
        When silence exceeds silence_duration, the complete segment
        is passed to the callback.

        TODO (Dev 2): Test and tune these parameters:
        - silence_threshold: May need adjustment per mic/environment
        - silence_duration: shorter values improve responsiveness
        - chunk_duration: 0.25s keeps latency lower for live use
        """
        if self.vad_enabled:
            await self._capture_stream_with_vad(speaker, device_idx, callback)
            return

        logger.warning("WebRTC VAD unavailable; falling back to RMS speech detection | speaker=%s", speaker)
        speech_started = False
        silence_time = 0.0
        audio_chunks: list[np.ndarray] = []
        loop = asyncio.get_event_loop()

        def audio_callback(indata, frames, time_info, status):
            nonlocal speech_started, silence_time, audio_chunks

            if status:
                print(f"[AudioCapture] {speaker} stream status: {status}")

            audio_data = indata[:, 0].copy().astype(np.float32)
            rms = float(np.sqrt(np.mean(audio_data ** 2)))

            if rms > self.silence_threshold:
                # Speech detected
                speech_started = True
                silence_time = 0.0
                audio_chunks.append(audio_data)

            elif speech_started:
                # Silence after speech
                silence_time += self.chunk_duration
                audio_chunks.append(audio_data)

                if silence_time >= self.silence_duration:
                    # End of utterance — send to callback
                    full_audio = np.concatenate(audio_chunks)
                    audio_chunks = []
                    speech_started = False
                    silence_time = 0.0

                    # Schedule callback on the event loop
                    loop.call_soon_threadsafe(
                        asyncio.ensure_future,
                        callback(speaker, full_audio),
                    )

        blocksize = int(self.sample_rate * self.chunk_duration)

        try:
            with sd.InputStream(
                device=device_idx,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=blocksize,
                dtype="float32",
                callback=audio_callback,
            ):
                while self.is_running:
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[AudioCapture] Error on {speaker} stream: {e}")
            # Don't crash — just log and stop this stream

    async def _capture_stream_with_vad(
        self,
        speaker: str,
        device_idx: int,
        callback: Callable[[str, np.ndarray], Awaitable[None]],
    ):
        """
        Capture loop using WebRTC VAD for cleaner/faster utterance boundaries.

        This is tuned for quiet-room live interview use:
        - 20ms frames for low latency
        - small pre-roll so we don't clip the first word
        - short silence hangover for faster question pickup
        """
        loop = asyncio.get_event_loop()
        pre_roll: deque[np.ndarray] = deque(maxlen=self.pre_roll_frames)
        speech_started = False
        silence_frames = 0
        utterance_frames: list[np.ndarray] = []
        pending = np.empty(0, dtype=np.float32)

        def finalize_utterance() -> None:
            nonlocal speech_started, silence_frames, utterance_frames
            if not utterance_frames:
                speech_started = False
                silence_frames = 0
                return

            full_audio = np.concatenate(utterance_frames)
            utterance_frames = []
            speech_started = False
            silence_frames = 0

            loop.call_soon_threadsafe(
                asyncio.ensure_future,
                callback(speaker, full_audio),
            )

        def audio_callback(indata, frames, time_info, status):
            nonlocal pending, speech_started, silence_frames, utterance_frames

            if status:
                logger.warning("Audio stream status | speaker=%s | status=%s", speaker, status)

            audio_data = indata[:, 0].copy().astype(np.float32)
            if pending.size:
                audio_data = np.concatenate((pending, audio_data))

            total_frames = len(audio_data) // self.vad_frame_size
            if total_frames <= 0:
                pending = audio_data
                return

            consumed = total_frames * self.vad_frame_size
            pending = audio_data[consumed:]

            for start in range(0, consumed, self.vad_frame_size):
                frame = audio_data[start:start + self.vad_frame_size]
                pcm_frame = np.clip(frame, -1.0, 1.0)
                pcm_bytes = (pcm_frame * 32767).astype(np.int16).tobytes()
                is_speech = self.vad.is_speech(pcm_bytes, self.sample_rate)

                if is_speech:
                    if not speech_started:
                        speech_started = True
                        utterance_frames = list(pre_roll)
                    utterance_frames.append(frame.copy())
                    silence_frames = 0
                    continue

                if speech_started:
                    utterance_frames.append(frame.copy())
                    silence_frames += 1
                    if silence_frames >= self.max_silence_frames:
                        finalize_utterance()
                else:
                    pre_roll.append(frame.copy())

        blocksize = int(self.sample_rate * self.chunk_duration)

        try:
            with sd.InputStream(
                device=device_idx,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=blocksize,
                dtype="float32",
                callback=audio_callback,
            ):
                while self.is_running:
                    await asyncio.sleep(0.05)
        except Exception as e:
            logger.exception("Audio capture failed on VAD stream | speaker=%s", speaker)
            print(f"[AudioCapture] Error on {speaker} stream: {e}")

    async def stop(self):
        """Stop both capture streams."""
        self.is_running = False

    @staticmethod
    def list_devices() -> dict:
        """
        List available audio devices.

        Returns:
            {
                "all": [list of all devices],
                "input": [list of input-capable devices with names and indices],
                "output": [list of output-capable devices with names and indices],
                "default_input": "Default input device name or empty string",
                "default_output": "Default output device name or empty string",
            }
        """
        devices = sd.query_devices()
        input_devices = []
        output_devices = []
        for i, d in enumerate(devices):
            if d.get("max_input_channels", 0) > 0:
                input_devices.append({
                    "index": i,
                    "name": d["name"],
                    "channels": d["max_input_channels"],
                    "sample_rate": d["default_samplerate"],
                })
            if d.get("max_output_channels", 0) > 0:
                output_devices.append({
                    "index": i,
                    "name": d["name"],
                    "channels": d["max_output_channels"],
                    "sample_rate": d["default_samplerate"],
                })

        default_input_name = ""
        default_output_name = ""
        try:
            default_input_idx, default_output_idx = sd.default.device
            if isinstance(default_input_idx, int) and default_input_idx >= 0:
                default_input_name = devices[default_input_idx]["name"]
            if isinstance(default_output_idx, int) and default_output_idx >= 0:
                default_output_name = devices[default_output_idx]["name"]
        except Exception:
            pass

        return {
            "all": [d["name"] for d in devices],
            "input": input_devices,
            "output": output_devices,
            "default_input": default_input_name,
            "default_output": default_output_name,
        }
