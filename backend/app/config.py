"""
InterviewAce — Configuration
Loads settings from .env file and environment variables.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Required
    anthropic_api_key: str

    # Audio devices
    system_audio_device: str = "BlackHole 2ch"
    mic_device: str = "MacBook Pro Microphone"

    # AI
    default_model: str = "claude-sonnet-4-20250514"

    # Whisper
    whisper_model: str = "base.en"
    whisper_device: str = "cpu"

    # Server
    backend_port: int = 8000
    frontend_port: int = 5173

    # Audio tuning
    silence_threshold: float = 0.01
    silence_duration: float = 1.5

    # Conversation history
    max_conversation_history: int = 40

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


# Singleton
settings = Settings()
