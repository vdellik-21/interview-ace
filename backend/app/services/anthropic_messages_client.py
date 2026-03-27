"""
InterviewAce — Anthropic Messages API integration
Runs Anthropic Claude models directly for prep and live-answer generation.
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
from .model_registry import ANTHROPIC_DEFAULT_MODEL, is_anthropic_model

logger = logging.getLogger("interviewace.anthropic")


@dataclass
class AnthropicResponseResult:
    """Normalized response payload from the Anthropic Messages API."""

    text: str
    message_id: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class AnthropicMessagesError(RuntimeError):
    """Raised when a direct Anthropic Messages API request fails."""


class AnthropicMessagesClient:
    """Async wrapper around the Anthropic Messages API."""

    DEFAULT_MODEL = ANTHROPIC_DEFAULT_MODEL
    MAX_RETRIES = 3

    def __init__(self):
        self.base_url = settings.anthropic_base_url.rstrip("/")
        self.api_key = settings.anthropic_api_key
        self.api_version = settings.anthropic_version

    @classmethod
    def normalize_model(cls, model: str | None, fallback: str | None = None) -> str:
        candidates = [model, fallback, settings.default_model, cls.DEFAULT_MODEL]
        for candidate in candidates:
            value = str(candidate or "").strip()
            if is_anthropic_model(value):
                return value
        return cls.DEFAULT_MODEL

    @classmethod
    def supports_model(cls, model: str | None) -> bool:
        return is_anthropic_model(model)

    @staticmethod
    def build_system_block(text: str, *, cache: bool = False) -> dict[str, Any]:
        block: dict[str, Any] = {
            "type": "text",
            "text": text,
        }
        if cache:
            block["cache_control"] = {"type": "ephemeral"}
        return block

    async def run_prompt(
        self,
        prompt: str,
        model: str,
        *,
        system_blocks: list[dict[str, Any]] | None = None,
        prompt_cache_key: str | None = None,
    ) -> str:
        result = await self.create_message(
            prompt=prompt,
            model=model,
            system_blocks=system_blocks,
            prompt_cache_key=prompt_cache_key,
        )
        return result.text

    async def create_message(
        self,
        *,
        prompt: str,
        model: str,
        system_blocks: list[dict[str, Any]] | None = None,
        prompt_cache_key: str | None = None,
    ) -> AnthropicResponseResult:
        self._ensure_api_key()
        model_name = self.normalize_model(model)
        payload: dict[str, Any] = {
            "model": model_name,
            "max_tokens": settings.anthropic_max_output_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        }
                    ],
                }
            ],
        }
        if system_blocks:
            payload["system"] = system_blocks

        logger.info("Starting Anthropic request | model=%s", model_name)
        started_at = time.perf_counter()
        data = await asyncio.to_thread(self._post_json, "/messages", payload)

        text = self._extract_output_text(data)
        if not text:
            raise AnthropicMessagesError("Anthropic Messages API returned an empty response.")

        message_id = str(data.get("id", "")).strip()
        logger.info(
            "Anthropic request completed | model=%s | message_id=%s | chars=%s | duration_ms=%.0f",
            model_name,
            message_id or "none",
            len(text),
            (time.perf_counter() - started_at) * 1000,
        )
        return AnthropicResponseResult(
            text=text,
            message_id=message_id,
            usage=data.get("usage", {}) if isinstance(data.get("usage"), dict) else {},
        )

    def _ensure_api_key(self) -> None:
        if self.api_key:
            return
        raise AnthropicMessagesError(
            "ANTHROPIC_API_KEY is missing. Add it to your .env file to use Claude Sonnet for prep and live answers."
        )

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = ""
        for attempt in range(self.MAX_RETRIES + 1):
            req = request.Request(
                f"{self.base_url}{endpoint}",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key or "",
                    "anthropic-version": self.api_version,
                },
                method="POST",
            )

            try:
                with request.urlopen(req, timeout=settings.anthropic_timeout_seconds) as response:
                    body = response.read().decode("utf-8")
                    break
            except error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
                should_retry = exc.code in {429, 500, 502, 503, 504, 529} and attempt < self.MAX_RETRIES
                if should_retry:
                    delay = self._retry_delay_seconds(exc, attempt)
                    logger.warning(
                        "Anthropic request failed; retrying | status=%s | attempt=%s/%s | delay_s=%.1f",
                        exc.code,
                        attempt + 1,
                        self.MAX_RETRIES + 1,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise AnthropicMessagesError(self._format_http_error(exc.code, details)) from exc
            except error.URLError as exc:
                raise AnthropicMessagesError(
                    "Could not reach the Anthropic API. Check your network connection and try again."
                ) from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise AnthropicMessagesError("Anthropic API returned invalid JSON.") from exc

        if not isinstance(data, dict):
            raise AnthropicMessagesError("Anthropic API returned an unexpected response shape.")
        return data

    def _extract_output_text(self, data: dict[str, Any]) -> str:
        content = data.get("content", [])
        chunks: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    chunks.append(text)
        return "\n".join(chunks).strip()

    def _format_http_error(self, status_code: int, details: str) -> str:
        if status_code == 401:
            return (
                "Anthropic API authentication failed. Set a valid ANTHROPIC_API_KEY in .env, then restart the app."
            )
        if status_code == 429:
            if details:
                return (
                    "Anthropic API rate limit hit. Your Claude account or tier is rejecting this request right now. "
                    f"Details: {details}"
                )
            return (
                "Anthropic API rate limit hit. Your Claude account or tier is rejecting this request right now. "
                "Please wait a moment and try again."
            )
        if status_code >= 500:
            return "Anthropic API is temporarily unavailable. Please try again shortly."
        if details:
            return f"Anthropic API failed ({status_code}): {details}"
        return f"Anthropic API failed with HTTP {status_code}."

    def _retry_delay_seconds(self, exc: error.HTTPError, attempt: int) -> float:
        retry_after = ""
        if getattr(exc, "headers", None):
            retry_after = str(exc.headers.get("retry-after", "")).strip()

        if retry_after:
            try:
                return max(1.0, float(retry_after))
            except ValueError:
                pass

        backoff_schedule = [1.5, 3.0, 6.0, 10.0]
        return backoff_schedule[min(attempt, len(backoff_schedule) - 1)]
