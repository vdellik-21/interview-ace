"""
InterviewAce — Configuration
Loads settings from .env file and environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Audio devices
    system_audio_device: str = "BlackHole 2ch"
    mic_device: str = "MacBook Pro Microphone"

    # AI
    prep_model: str = "gpt-5-mini"
    default_model: str = "gpt-5-mini"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: int = 20
    openai_reasoning_effort: str = "minimal"
    openai_text_verbosity: str = "low"
    openai_max_output_tokens: int = 220
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_version: str = "2023-06-01"
    anthropic_timeout_seconds: int = 20
    anthropic_max_output_tokens: int = 220

    # Whisper
    whisper_model: str = "base.en"
    whisper_device: str = "cpu"

    # Server
    backend_port: int = 8000
    frontend_port: int = 5173

    # Audio tuning
    silence_threshold: float = 0.01
    silence_duration: float = 0.8
    capture_candidate_audio: bool = False

    # Conversation history
    max_conversation_history: int = 40


# Singleton
settings = Settings()
