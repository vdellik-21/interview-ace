"""
InterviewAce — Live AI Engine
Manages Claude API calls for real-time interview answer generation.
Uses streaming to display tokens as they arrive for zero-delay UX.

Owner: Dev 1 (Vineeth)
Status: STUB — core structure implemented, needs integration testing
"""

from typing import Callable, Awaitable, Optional

import anthropic

from ..config import settings
from ..models.session import InterviewSession


class LiveAIEngine:
    """
    Manages Claude API streaming for live interview answer generation.
    
    Pre-loaded with the session's system prompt containing resume, JD,
    skill mapping, and STAR stories. Maintains conversation history
    throughout the interview for context continuity.
    """

    def __init__(self, session: InterviewSession):
        """
        Args:
            session: Pre-built InterviewSession with system_prompt and model.
        """
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.session = session
        self.is_processing = False
        self.last_answer = ""

    async def generate_answer(
        self,
        interviewer_text: str,
        candidate_text: Optional[str],
        on_token: Callable[[str], Awaitable[None]],
    ) -> str:
        """
        Generate a streamed answer to the interviewer's question.

        Args:
            interviewer_text: What the interviewer just said (the question)
            candidate_text: What the candidate said recently (for context), or None
            on_token: Async callback fired for each streamed token

        Returns:
            Full completed response text
        """
        # Don't overlap — drop if already generating
        if self.is_processing:
            return ""
        self.is_processing = True

        try:
            # Add candidate context if available
            if candidate_text and candidate_text.strip():
                self.session.conversation_history.append({
                    "role": "user",
                    "content": f"[CANDIDATE SAID]: {candidate_text.strip()}"
                })

            # Add interviewer question
            self.session.conversation_history.append({
                "role": "user",
                "content": f"[INTERVIEWER ASKED]: {interviewer_text}\n\nGenerate your response NOW."
            })

            # Stream response from Claude
            full_response = ""
            async with self.client.messages.stream(
                model=self.session.model,
                max_tokens=1024,
                system=self.session.system_prompt,
                messages=self.session.conversation_history,
            ) as stream:
                async for token in stream.text_stream:
                    full_response += token
                    await on_token(token)

            # Save to history for context continuity
            self.session.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })

            # Trim history if too long (sliding window)
            max_hist = settings.max_conversation_history
            if len(self.session.conversation_history) > max_hist:
                # Keep first 2 messages (initial context) + last (max_hist - 2)
                self.session.conversation_history = (
                    self.session.conversation_history[:2]
                    + self.session.conversation_history[-(max_hist - 2):]
                )

            self.last_answer = full_response
            return full_response

        finally:
            self.is_processing = False

    async def regenerate(
        self,
        modifier: Optional[str],
        on_token: Callable[[str], Awaitable[None]],
    ) -> str:
        """
        Regenerate the last answer with an optional modifier.

        Args:
            modifier: "shorter", "more_detail", or None for straight regen
            on_token: Async callback for streamed tokens

        Returns:
            New response text
        """
        if not self.session.conversation_history:
            return ""

        # Remove the last assistant response
        if (self.session.conversation_history
                and self.session.conversation_history[-1].get("role") == "assistant"):
            self.session.conversation_history.pop()

        # Add modifier instruction if provided
        if modifier == "shorter":
            self.session.conversation_history.append({
                "role": "user",
                "content": "[CANDIDATE INSTRUCTION]: Make the answer SHORTER — 2-3 sentences max. Keep only the most important point."
            })
        elif modifier == "more_detail":
            self.session.conversation_history.append({
                "role": "user",
                "content": "[CANDIDATE INSTRUCTION]: Give MORE DETAIL — expand with additional examples, metrics, and context from the resume."
            })
        else:
            self.session.conversation_history.append({
                "role": "user",
                "content": "[CANDIDATE INSTRUCTION]: Regenerate the answer with a different angle or approach."
            })

        # Stream new response
        full_response = ""
        self.is_processing = True
        try:
            async with self.client.messages.stream(
                model=self.session.model,
                max_tokens=1024,
                system=self.session.system_prompt,
                messages=self.session.conversation_history,
            ) as stream:
                async for token in stream.text_stream:
                    full_response += token
                    await on_token(token)

            self.session.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })

            self.last_answer = full_response
            return full_response
        finally:
            self.is_processing = False
