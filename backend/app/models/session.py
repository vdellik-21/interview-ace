"""
InterviewAce — Session Data Models
Pydantic models for interview session state.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid


class InterviewSession(BaseModel):
    """Complete state for one interview session."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model: str = "gpt-5-mini"
    system_prompt: str = ""
    resume_text: str = ""
    resume_structured: dict = Field(default_factory=dict)
    jd_text: str = ""
    jd_structured: dict = Field(default_factory=dict)
    skill_mapping: dict = Field(default_factory=dict)
    predicted_questions: list[dict] = Field(default_factory=list)
    prepared_answers: list[dict] = Field(default_factory=list)
    context_texts: list[str] = Field(default_factory=list)
    conversation_history: list[dict] = Field(default_factory=list)
    openai_conversation_id: str = ""
    openai_prompt_cache_key: str = ""
    system_audio_device: str = "BlackHole 2ch"
    speaker_output_device: str = ""
    mic_device: str = "MacBook Pro Microphone"
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "preparing"  # preparing | ready | live | ended


class TranscriptEntry(BaseModel):
    """Single transcript segment."""

    speaker: str  # "interviewer" or "candidate"
    text: str
    timestamp: datetime = Field(default_factory=datetime.now)
    is_question: bool = False


class AnswerEntry(BaseModel):
    """AI-generated answer for a detected question."""

    question: str
    answer: str
    model_used: str
    timestamp: datetime = Field(default_factory=datetime.now)
