"""
InterviewAce — Question Detector
Determines if interviewer speech is a question requiring an answer
or just a statement/explanation.
"""

from difflib import SequenceMatcher
import logging
import re

logger = logging.getLogger("interviewace.question_detector")

PROMPT_STARTERS = [
    "can you",
    "could you",
    "would you",
    "will you",
    "tell me",
    "walk me through",
    "walk us through",
    "help me understand",
    "talk to me about",
    "share more about",
    "share with me",
    "go deeper on",
    "start with",
    "let's start with",
    "let's talk about",
    "what is",
    "what are",
    "what's",
    "how do",
    "how did",
    "how would",
    "why",
    "when",
    "where",
    "did you",
    "have you",
    "explain",
    "describe",
]

PROMPT_STARTER_PATTERN = r"\b(" + "|".join(
    re.escape(starter) for starter in sorted(PROMPT_STARTERS, key=len, reverse=True)
) + r")\b"

PROMPT_STARTER_RE = re.compile(r"(?i)" + PROMPT_STARTER_PATTERN)
PROMPT_BOUNDARY_RE = re.compile(
    r"(?i)(?:,\s+|(?<=[?.!])\s+|\band also\b\s+|\balso\b\s+|\band\b\s+)(?="
    + PROMPT_STARTER_PATTERN
    + r")"
)

LEADING_FILLER_PATTERNS = [
    r"^(?:okay|ok|alright|all right|great|awesome|perfect|right|yeah|yep|sure|so|well|got it|sounds good|nice)\b[\s,.:;-]*",
    r"^(?:thanks|thank you)\b[\s,.:;-]*",
    r"^(?:mm[- ]?hmm|uh|um|hmm)\b[\s,.:;-]*",
]

PROMPT_TRAILING_FILLER = {
    "tell me",
    "can you",
    "could you",
    "would you",
    "walk me through",
    "walk us through",
    "help me understand",
    "talk to me about",
    "share more about",
    "what is",
    "what are",
    "what's",
    "how do",
    "how did",
    "how would",
    "why",
    "when",
    "where",
}


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
        turn_type = self.classify_turn(text)
        logger.info("Question detection resolved | turn_type=%s | is_question=%s", turn_type, turn_type != "statement")
        return turn_type != "statement"

    def classify_turn(self, text: str) -> str:
        """
        Classify interviewer speech into one of:
        - question
        - follow_up
        - statement
        """
        normalized = self.normalize_turn(text) or text
        heuristic = self._heuristic_check(normalized)
        if heuristic == "question":
            return "question"
        if heuristic == "follow_up":
            return "follow_up"
        if heuristic == "answer_prompt":
            return "answer_prompt"
        if heuristic == "statement":
            return "statement"

        return self._fallback_bias(normalized)

    def normalize_turn(self, text: str) -> str:
        """
        Reduce a messy interviewer turn to the single strongest answerable prompt.

        This is intentionally conservative: it strips filler, removes repeated
        conversational fragments, and when multiple prompt clauses appear, it
        chooses the best prompt to answer rather than passing the whole merged
        transcript blob downstream.
        """
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return ""

        working = self._strip_leading_filler(cleaned)
        working = self._dedupe_repeated_fragments(working)
        candidates = self._candidate_prompt_fragments(working)
        if not candidates:
            return working or cleaned

        best_index = 0
        best_score: tuple[int, int, int] | None = None
        for index, candidate in enumerate(candidates):
            score = self._score_prompt_candidate(candidate)
            tie_break = (score, index, len(candidate))
            if best_score is None or tie_break > best_score:
                best_score = tie_break
                best_index = index

        best = candidates[best_index].strip(" ,.:;-")
        best = self._collapse_direct_repetition(best)
        best = self._unwrap_nested_prompt(best)
        return best or working or cleaned

    def extract_answerable_text(self, text: str) -> str:
        """
        Remove common conversational filler from the front of an interviewer turn
        while preserving the actual prompt.
        """
        return self.normalize_turn(text)

    def starts_new_prompt(self, existing_turn: str, incoming_text: str) -> bool:
        """
        Decide whether a fresh transcript chunk likely starts a brand-new prompt
        and therefore should not be merged into the current interviewer buffer.
        """
        current = self.normalize_turn(existing_turn)
        incoming = self.normalize_turn(incoming_text)
        if not current or not incoming:
            return False

        if self.classify_turn(incoming) == "statement":
            return False

        current_lower = current.lower()
        incoming_lower = incoming.lower()

        incoming_is_strong_prompt = bool(PROMPT_STARTER_RE.match(incoming_lower)) or incoming_lower.endswith("?")
        if not incoming_is_strong_prompt:
            return False

        if len(current.split()) < 4:
            return False

        if SequenceMatcher(None, self._comparison_key(current), self._comparison_key(incoming)).ratio() >= 0.84:
            return False

        current_has_prompt = bool(PROMPT_STARTER_RE.search(current_lower)) or current_lower.endswith("?")
        return current_has_prompt

    def _heuristic_check(self, text: str) -> str | None:
        """
        Fast rule-based check. Returns None if ambiguous.
        
        Definite questions: ends with "?", starts with question words
        Definite not questions: very short, filler phrases
        Ambiguous: everything else → defer to a local fallback bias
        """
        text_clean = text.strip().lower()
        text_padded = f" {text_clean} "
        words = text_clean.split()

        # Obvious question markers
        if text_clean.endswith("?"):
            if self._is_follow_up_phrase(text_clean):
                return "follow_up"
            return "question"

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
            if self._is_follow_up_phrase(text_clean):
                return "follow_up"
            return "question"

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
                if self._is_follow_up_phrase(text_clean):
                    return "follow_up"
                return "question"

        if self._is_follow_up_phrase(text_clean):
            return "follow_up"

        if self._is_answer_prompt(text_clean):
            return "answer_prompt"

        # Short questions are common in technical interviews: "What is BFS",
        # "Explain REST", "Why Java", etc. Only reject if they are extremely
        # short and still have no question signal.
        if len(words) <= 1:
            return "statement"

        if len(words) <= 3:
            if words and words[0] in {"what", "why", "how", "when", "where", "who", "define", "explain"}:
                if self._is_follow_up_phrase(text_clean):
                    return "follow_up"
                return "question"
            return "statement"

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
                return "statement"

        # In live interviews, longer interviewer utterances are more useful to
        # answer than to ignore, so bias ambiguous long speech toward True.
        if len(words) >= 10:
            return "question"

        if len(words) <= 6:
            return "statement"

        # Ambiguous — defer to local fallback bias
        return None

    def _is_answer_prompt(self, text_clean: str) -> bool:
        answer_prompt_markers = [
            "talk to me about",
            "help me understand",
            "i'd love to hear about",
            "i would love to hear about",
            "i'm curious about",
            "curious about",
            "speak to",
            "share more about",
            "share with me",
            "take me through",
            "go deeper on",
            "start with",
            "let's start with",
            "let's talk about",
            "walk me through",
        ]
        return any(marker in text_clean for marker in answer_prompt_markers)

    def _is_follow_up_phrase(self, text_clean: str) -> bool:
        follow_up_markers = [
            "tell me more",
            "more detail",
            "more about that",
            "elaborate",
            "expand on that",
            "walk me through that",
            "walk me through it",
            "what happened next",
            "what specifically",
            "why that",
            "why so",
            "why was that",
            "how so",
            "what did you do next",
            "what would you do differently",
            "in that role",
            "in that project",
            "at that company",
            "on that",
            "for that",
        ]
        short_follow_up_starts = [
            "why",
            "how so",
            "and then",
            "then what",
            "after that",
            "what next",
            "go on",
        ]
        return any(marker in text_clean for marker in follow_up_markers) or any(
            text_clean.startswith(marker) for marker in short_follow_up_starts
        )

    def _fallback_bias(self, text: str) -> str:
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
            return "answer_prompt"

        return "question" if len(words) >= 7 else "statement"

    def _strip_leading_filler(self, text: str) -> str:
        updated = text
        for _ in range(4):
            changed = False
            for pattern in LEADING_FILLER_PATTERNS:
                newer = re.sub(pattern, "", updated, flags=re.IGNORECASE).strip()
                if newer and newer != updated:
                    updated = newer
                    changed = True
            if not changed:
                break
        return updated or text

    def _dedupe_repeated_fragments(self, text: str) -> str:
        fragments = self._split_prompt_fragments(text)
        cleaned_fragments: list[str] = []
        seen_keys: list[str] = []

        for fragment in fragments:
            candidate = fragment.strip(" ,.:;-")
            if not candidate:
                continue

            key = self._comparison_key(candidate)
            if not key:
                continue

            duplicate = any(
                key == existing
                or SequenceMatcher(None, key, existing).ratio() >= 0.9
                for existing in seen_keys
            )
            if duplicate:
                continue

            cleaned_fragments.append(candidate)
            seen_keys.append(key)

        return " ".join(cleaned_fragments).strip() or text

    def _candidate_prompt_fragments(self, text: str) -> list[str]:
        working = text.strip()
        if not working:
            return []

        candidates = self._split_prompt_fragments(working) or [working]

        normalized_candidates: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = self._comparison_key(candidate)
            if not key or key in seen:
                continue
            seen.add(key)
            normalized_candidates.append(candidate)
        return normalized_candidates

    def _score_prompt_candidate(self, candidate: str) -> int:
        lowered = candidate.lower().strip()
        words = lowered.split()
        word_count = len(words)
        content_words = [word for word in words if word not in {"and", "or", "the", "a", "an", "so", "okay", "well"}]
        starter_matches = list(PROMPT_STARTER_RE.finditer(lowered))

        score = 0
        if lowered.endswith("?"):
            score += 35
        if starter_matches and starter_matches[0].start() == 0:
            score += 50
        if self._is_follow_up_phrase(lowered):
            score += 28
        if self._is_answer_prompt(lowered):
            score += 24
        if any(token in lowered for token in ["experience", "role", "project", "company", "work", "using", "used"]):
            score += 16
        if any(token in lowered for token in ["java", "python", "api", "rest", "graph", "list", "tree", "oops", "oop"]):
            score += 16

        score += min(len(content_words), 14) * 3
        score -= max(word_count - 26, 0) * 3
        score -= max(len(starter_matches) - 1, 0) * 32

        trailing = lowered.rstrip(" ?!.,:;-")
        if trailing in PROMPT_TRAILING_FILLER or word_count <= 2:
            score -= 40

        diversity = len(set(words)) / max(word_count, 1)
        if word_count >= 8 and diversity < 0.55:
            score -= 20

        return score

    def _comparison_key(self, text: str) -> str:
        lowered = text.lower().strip()
        lowered = re.sub(r"[^a-z0-9\s]+", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    def _split_prompt_fragments(self, text: str) -> list[str]:
        working = text.strip()
        if not working:
            return []

        starts = [0]
        for match in PROMPT_BOUNDARY_RE.finditer(working):
            boundary_index = match.end()
            if 0 < boundary_index < len(working):
                starts.append(boundary_index)

        starts = sorted(set(starts))
        fragments: list[str] = []
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else len(working)
            fragment = working[start:end].strip(" ,.:;-")
            if fragment:
                fragments.append(fragment)
        return fragments

    def _collapse_direct_repetition(self, text: str) -> str:
        words = text.split()
        if len(words) < 6:
            return text

        for size in range(len(words) // 2, 2, -1):
            first = " ".join(words[:size])
            second = " ".join(words[size:size * 2])
            if not second:
                continue
            if SequenceMatcher(None, self._comparison_key(first), self._comparison_key(second)).ratio() >= 0.96:
                remainder = " ".join(words[size * 2:]).strip()
                collapsed = first if not remainder else f"{first} {remainder}"
                return collapsed.strip()
        return text

    def _unwrap_nested_prompt(self, text: str) -> str:
        nested_patterns = [
            r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:tell\s+me|explain(?:\s+to\s+me)?)\s+(?=(?:what|how|why|when|where|who)\b)",
            r"^tell\s+me\s+(?=(?:what|how|why|when|where|who)\b)",
        ]
        updated = text.strip()
        for pattern in nested_patterns:
            newer = re.sub(pattern, "", updated, flags=re.IGNORECASE).strip()
            if newer and newer != updated:
                updated = newer
        return updated or text
