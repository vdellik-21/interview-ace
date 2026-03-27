"""
InterviewAce — Question Detector
Determines if interviewer speech is a question requiring an answer
or just a statement/explanation.
"""

import logging

logger = logging.getLogger("interviewace.question_detector")


class QuestionDetector:
    """
    Fast heuristic question detection for interviewer speech.
    We keep this local so the reusable OpenAI answer conversation is not polluted
    with meta-classification turns.
    """

    async def is_question(self, text: str) -> bool:
        """
        Returns True if the text is a question the candidate should answer.
        
        Args:
            text: Transcribed interviewer speech
            
        Returns:
            True if this needs an answer, False if it's just a statement
        """
        logger.info("Question detection started | chars=%s", len(text))
        # Stage 1: Fast heuristic
        heuristic = self._heuristic_check(text)
        if heuristic is not None:
            logger.info("Question detection resolved by heuristic | is_question=%s", heuristic)
            return heuristic

        result = self._fallback_bias(text)
        logger.info("Question detection resolved by fallback bias | is_question=%s", result)
        return result

    def _heuristic_check(self, text: str) -> bool | None:
        """
        Fast rule-based check. Returns None if ambiguous.
        
        Definite questions: ends with "?", starts with question words
        Definite not questions: very short, filler phrases
        Ambiguous: everything else → defer to a local fallback bias
        """
        text_clean = text.strip().lower()
        text_padded = f" {text_clean} "
        words = text_clean.split()

        # Too short to be a meaningful question
        if len(words) < 4:
            return False

        # Obvious question markers
        if text_clean.endswith("?"):
            return True

        # Common question markers can appear anywhere in live transcripts.
        inline_question_markers = [
            " can you ",
            " could you ",
            " would you ",
            " will you ",
            " do you ",
            " have you ",
            " are you ",
            " tell me ",
            " walk me through ",
            " explain ",
            " what ",
            " why ",
            " how ",
            " when ",
            " where ",
            " please let me know ",
        ]
        if any(marker in text_padded for marker in inline_question_markers):
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

        # In live interviews, longer interviewer utterances are more useful to
        # answer than to ignore, so bias ambiguous long speech toward True.
        if len(words) >= 10:
            return True

        if len(words) <= 6:
            return False

        # Ambiguous — defer to local fallback bias
        return None

    def _fallback_bias(self, text: str) -> bool:
        """
        Favor answering ambiguous interviewer speech instead of missing a prompt.
        """
        text_clean = text.strip().lower()
        words = text_clean.split()

        conversational_prompts = [
            "share",
            "talk to me about",
            "help me understand",
            "let's say",
            "suppose",
            "imagine",
        ]
        if any(phrase in text_clean for phrase in conversational_prompts):
            return True

        return len(words) >= 7
