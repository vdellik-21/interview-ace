"""
InterviewAce — Question Detector
Determines if interviewer speech is a question requiring an answer
or just a statement/explanation.

Owner: Dev 2
Status: STUB — heuristic + Haiku hybrid implemented
"""

from pathlib import Path

import anthropic

from ..config import settings


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class QuestionDetector:
    """
    Two-stage question detection:
    1. Fast heuristic check (instant, free)
    2. If ambiguous → Claude Haiku classification (fast, cheap)
    """

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.classify_prompt = (PROMPTS_DIR / "question_classify.txt").read_text()

    async def is_question(self, text: str) -> bool:
        """
        Returns True if the text is a question the candidate should answer.
        
        Args:
            text: Transcribed interviewer speech
            
        Returns:
            True if this needs an answer, False if it's just a statement
        """
        # Stage 1: Fast heuristic
        heuristic = self._heuristic_check(text)
        if heuristic is not None:
            return heuristic

        # Stage 2: Haiku classification (for ambiguous cases)
        return await self._haiku_classify(text)

    def _heuristic_check(self, text: str) -> bool | None:
        """
        Fast rule-based check. Returns None if ambiguous.
        
        Definite questions: ends with "?", starts with question words
        Definite not questions: very short, filler phrases
        Ambiguous: everything else → defer to Haiku
        """
        text_clean = text.strip().lower()

        # Too short to be a meaningful question
        if len(text_clean.split()) < 4:
            return False

        # Obvious question markers
        if text_clean.endswith("?"):
            return True

        # Common interview question starters
        question_starters = [
            "tell me about",
            "describe a time",
            "give me an example",
            "how would you",
            "how did you",
            "what is your",
            "what are your",
            "what do you",
            "what would you",
            "why do you",
            "why did you",
            "why should we",
            "where do you see",
            "can you walk me through",
            "can you tell me",
            "what experience do you have",
            "how do you handle",
            "what's your approach",
            "walk me through",
        ]
        for starter in question_starters:
            if text_clean.startswith(starter):
                return True

        # Filler / transition phrases (not questions)
        non_questions = [
            "let me tell you",
            "so basically",
            "what we do here",
            "our team is",
            "the role involves",
            "i want to explain",
            "let me give you some context",
            "thanks for",
            "great answer",
            "that's interesting",
            "okay so",
            "alright",
            "perfect",
            "sounds good",
        ]
        for phrase in non_questions:
            if text_clean.startswith(phrase):
                return False

        # Ambiguous — defer to Haiku
        return None

    async def _haiku_classify(self, text: str) -> bool:
        """
        Use Claude Haiku for fast question classification.
        ~50-100ms response time.
        """
        try:
            prompt = self.classify_prompt.format(text=text)
            response = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}],
            )
            result = response.content[0].text.strip().upper()
            return "QUESTION" in result
        except Exception as e:
            print(f"[QuestionDetector] Haiku error: {e}. Defaulting to True.")
            # If Haiku fails, assume it's a question (better to show an answer than miss one)
            return True
