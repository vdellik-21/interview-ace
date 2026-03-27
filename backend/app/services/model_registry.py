"""
InterviewAce — Model Registry
Helpers for routing the selected session model to the correct API provider.
"""

from __future__ import annotations

from ..config import settings

OPENAI_DEFAULT_MODEL = "gpt-5-mini"
ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5"


def is_anthropic_model(model: str | None) -> bool:
    value = str(model or "").strip().lower()
    return value.startswith("claude-")


def is_openai_model(model: str | None) -> bool:
    value = str(model or "").strip().lower()
    return bool(value) and not value.startswith("claude-") and "codex" not in value


def normalize_session_model(model: str | None, fallback: str | None = None) -> str:
    """
    Normalize a user-selected model into a supported provider model.
    Anthropic models win if they are explicitly selected; otherwise OpenAI.
    """
    candidates = [model, fallback, settings.default_model, OPENAI_DEFAULT_MODEL]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if is_anthropic_model(value):
            return value
        if is_openai_model(value):
            return value
    return OPENAI_DEFAULT_MODEL


def provider_for_model(model: str | None, fallback: str | None = None) -> str:
    normalized = normalize_session_model(model, fallback=fallback)
    return "anthropic" if is_anthropic_model(normalized) else "openai"


def display_name_for_model(model: str | None) -> str:
    normalized = normalize_session_model(model)
    if normalized == "gpt-5-mini":
        return "GPT-5 mini"
    if normalized == "claude-haiku-4-5":
        return "Claude Haiku 4.5"
    return normalized
