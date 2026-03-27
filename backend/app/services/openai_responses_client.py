"""
InterviewAce — OpenAI Responses API integration
Runs OpenAI models directly for prep and live-answer generation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request

from ..config import settings
from .model_registry import OPENAI_DEFAULT_MODEL, is_openai_model

logger = logging.getLogger("interviewace.openai")


@dataclass
class OpenAIResponseResult:
    """Normalized response payload from the OpenAI Responses API."""

    text: str
    response_id: str = ""
    conversation_id: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)


class OpenAIResponsesError(RuntimeError):
    """Raised when a direct OpenAI Responses API request fails."""


class OpenAIResponsesClient:
    """Async wrapper around the OpenAI Responses and Conversations APIs."""

    DEFAULT_MODEL = OPENAI_DEFAULT_MODEL

    def __init__(self):
        self.base_url = settings.openai_base_url.rstrip("/")
        self.api_key = settings.openai_api_key

    @classmethod
    def normalize_model(cls, model: str | None, fallback: str | None = None) -> str:
        """Return the best OpenAI API model name, skipping Claude and legacy Codex values."""
        candidates = [model, fallback, settings.default_model, cls.DEFAULT_MODEL]
        for candidate in candidates:
            value = str(candidate or "").strip()
            if is_openai_model(value):
                return value
        return cls.DEFAULT_MODEL

    @classmethod
    def supports_model(cls, model: str | None) -> bool:
        return is_openai_model(model)

    @staticmethod
    def build_message(role: str, text: str) -> dict[str, Any]:
        """Build a Responses/Conversations message item."""
        return {
            "type": "message",
            "role": role,
            "content": [
                {
                    "type": "input_text",
                    "text": text,
                }
            ],
        }

    async def create_conversation(
        self,
        *,
        items: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a reusable OpenAI conversation for prep + live follow-ups."""
        self._ensure_api_key()
        payload: dict[str, Any] = {}
        if items:
            payload["items"] = items
        if metadata:
            payload["metadata"] = metadata

        logger.info("Creating OpenAI conversation")
        started_at = time.perf_counter()
        data = await asyncio.to_thread(self._post_json, "/conversations", payload)
        conversation_id = str(data.get("id", "")).strip()
        if not conversation_id:
            raise OpenAIResponsesError("OpenAI Conversations API did not return a conversation id.")
        logger.info(
            "OpenAI conversation created | conversation_id=%s | duration_ms=%.0f",
            conversation_id,
            (time.perf_counter() - started_at) * 1000,
        )
        return conversation_id

    async def add_conversation_items(
        self,
        conversation_id: str,
        items: list[dict[str, Any]],
    ) -> None:
        """Append context items to an existing OpenAI conversation."""
        if not conversation_id:
            raise OpenAIResponsesError("Conversation id is required before adding items.")
        if not items:
            return

        self._ensure_api_key()
        logger.info(
            "Adding OpenAI conversation items | conversation_id=%s | items=%s",
            conversation_id,
            len(items),
        )
        await asyncio.to_thread(
            self._post_json,
            f"/conversations/{conversation_id}/items",
            {"items": items},
        )

    async def run_prompt(
        self,
        prompt: str | list[dict[str, Any]],
        model: str,
        *,
        conversation_id: str | None = None,
        previous_response_id: str | None = None,
        prompt_cache_key: str | None = None,
        instructions: str | None = None,
        store: bool = False,
    ) -> str:
        """Execute a prompt and return only the assistant text."""
        result = await self.create_response(
            prompt=prompt,
            model=model,
            conversation_id=conversation_id,
            previous_response_id=previous_response_id,
            prompt_cache_key=prompt_cache_key,
            instructions=instructions,
            store=store,
        )
        return result.text

    async def create_response(
        self,
        *,
        prompt: str | list[dict[str, Any]],
        model: str,
        conversation_id: str | None = None,
        previous_response_id: str | None = None,
        prompt_cache_key: str | None = None,
        instructions: str | None = None,
        store: bool = False,
    ) -> OpenAIResponseResult:
        """Execute a prompt and return normalized response metadata."""
        self._ensure_api_key()

        model_name = self.normalize_model(model)
        payload: dict[str, Any] = {
            "model": model_name,
            "input": prompt,
            "max_output_tokens": settings.openai_max_output_tokens,
            "store": store,
            "reasoning": {
                "effort": settings.openai_reasoning_effort,
            },
            "text": {
                "format": {"type": "text"},
                "verbosity": settings.openai_text_verbosity,
            },
        }
        if conversation_id:
            payload["conversation"] = conversation_id
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id
        if prompt_cache_key:
            payload["prompt_cache_key"] = prompt_cache_key
        if instructions:
            payload["instructions"] = instructions

        logger.info(
            "Starting OpenAI Responses request | model=%s | conversation_id=%s",
            model_name,
            conversation_id or "none",
        )
        started_at = time.perf_counter()
        data = await asyncio.to_thread(self._post_json, "/responses", payload)

        text = self._extract_output_text(data)
        if not text:
            raise OpenAIResponsesError("OpenAI Responses API returned an empty response.")

        response_id = str(data.get("id", "")).strip()
        response_conversation_id = self._extract_conversation_id(data) or conversation_id
        logger.info(
            "OpenAI Responses request completed | model=%s | response_id=%s | chars=%s | duration_ms=%.0f",
            model_name,
            response_id or "none",
            len(text),
            (time.perf_counter() - started_at) * 1000,
        )
        return OpenAIResponseResult(
            text=text,
            response_id=response_id,
            conversation_id=response_conversation_id,
            usage=data.get("usage", {}) if isinstance(data.get("usage"), dict) else {},
        )

    def _ensure_api_key(self) -> None:
        if self.api_key:
            return
        raise OpenAIResponsesError(
            "OPENAI_API_KEY is missing. Add it to your .env file to use an OpenAI model for prep and live answers."
        )

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(
            f"{self.base_url}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=settings.openai_timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
            raise OpenAIResponsesError(self._format_http_error(exc.code, details)) from exc
        except error.URLError as exc:
            raise OpenAIResponsesError(
                "Could not reach the OpenAI API. Check your network connection and try again."
            ) from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise OpenAIResponsesError("OpenAI API returned invalid JSON.") from exc

        if not isinstance(data, dict):
            raise OpenAIResponsesError("OpenAI API returned an unexpected response shape.")
        return data

    def _extract_output_text(self, data: dict[str, Any]) -> str:
        output = data.get("output", [])
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                if content.get("type") == "output_text":
                    text = str(content.get("text", "")).strip()
                    if text:
                        return text
                if content.get("type") == "refusal":
                    refusal = str(content.get("refusal", "")).strip()
                    if refusal:
                        return refusal
        return ""

    def _extract_conversation_id(self, data: dict[str, Any]) -> str | None:
        conversation = data.get("conversation")
        if isinstance(conversation, str) and conversation.strip():
            return conversation.strip()
        if isinstance(conversation, dict):
            conversation_id = str(conversation.get("id", "")).strip()
            if conversation_id:
                return conversation_id
        conversation_id = str(data.get("conversation_id", "")).strip()
        return conversation_id or None

    def _format_http_error(self, status_code: int, details: str) -> str:
        if status_code == 401:
            return (
                "OpenAI API authentication failed. Set a valid OPENAI_API_KEY in .env, then restart the app."
            )
        if status_code == 429:
            return "OpenAI API rate limit hit. Please wait a moment and try again."
        if status_code >= 500:
            return "OpenAI API is temporarily unavailable. Please try again shortly."
        if details:
            return f"OpenAI API failed ({status_code}): {details}"
        return f"OpenAI API failed with HTTP {status_code}."
