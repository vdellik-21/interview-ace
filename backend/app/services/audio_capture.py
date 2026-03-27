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
from typing import Callable, Awaitable, Optional

import numpy as np
import sounddevice as sd

from ..config import settings


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
        self.chunk_duration = 0.25  # 250ms chunks for faster segment detection
        self.is_running = False

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
