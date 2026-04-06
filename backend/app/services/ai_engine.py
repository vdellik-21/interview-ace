"""
InterviewAce — Live AI Engine
Manages OpenAI API calls for real-time interview answer generation.
"""

import asyncio
from difflib import SequenceMatcher
import logging
import re
import time
from typing import Callable, Awaitable, Optional

from ..config import settings
from ..models.session import InterviewSession
from .anthropic_messages_client import AnthropicMessagesClient
from .model_registry import normalize_session_model, provider_for_model
from .openai_responses_client import OpenAIResponsesClient
from .question_detector import QuestionDetector

logger = logging.getLogger("interviewace.ai_engine")

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "do", "for", "from",
    "have", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "our",
    "so", "that", "the", "this", "to", "we", "what", "when", "where", "which",
    "with", "would", "you", "your",
}

KNOWLEDGE_SNIPPETS = {
    "list in python": (
        "A list in Python is an ordered, mutable collection that stores multiple items in a single variable. "
        "It is useful when data needs to be indexed, iterated over, or updated by adding, removing, or changing elements."
    ),
    "rest api": (
        "A REST API is a way for systems to communicate over HTTP using resources and standard methods like GET, POST, PUT, and DELETE. "
        "A strong REST design focuses on clear endpoints, proper status codes, stateless communication, and clean request-response contracts."
    ),
    "agile": (
        "Agile is an iterative way of working where teams deliver in small increments, gather feedback quickly, and keep adapting as they go. "
        "Its main value is faster learning, better collaboration, and continuous improvement instead of rigid upfront planning."
    ),
    "oop": (
        "Object-oriented programming is a way of structuring code around objects that combine data and behavior. "
        "The core ideas are encapsulation, inheritance, and polymorphism, which help keep code reusable, modular, and easier to maintain."
    ),
    "oops": (
        "Object-oriented programming is a way of structuring code around objects that combine data and behavior. "
        "The core ideas are encapsulation, inheritance, and polymorphism, which help keep code reusable, modular, and easier to maintain."
    ),
    "microservices": (
        "Microservices means breaking an application into smaller services that each handle a specific responsibility and communicate through APIs or messaging. "
        "The benefit is better scalability and independent deployment, but it also adds complexity around communication, monitoring, and consistency."
    ),
    "jvm": (
        "The JVM is the runtime that executes Java bytecode and handles things like memory management, garbage collection, and platform independence. "
        "Its practical value is that Java code can run consistently across different environments."
    ),
    "exception handling": (
        "Exception handling is the process of managing runtime errors in a controlled way so an application can fail gracefully instead of crashing unexpectedly. "
        "It helps separate normal logic from error paths and makes recovery, logging, and debugging much clearer."
    ),
}

FIELD_KEYWORDS = {
    "api", "apis", "backend", "frontend", "fullstack", "full-stack", "microservice",
    "microservices", "database", "databases", "sql", "nosql", "cloud", "aws", "azure",
    "gcp", "docker", "kubernetes", "terraform", "jenkins", "cicd", "ci/cd", "deployment",
    "deployments", "testing", "unit", "integration", "performance", "scalability",
    "architecture", "system", "systems", "devops", "agile", "scrum", "java", "python",
    "javascript", "typescript", "react", "angular", "spring", "springboot", "hibernate",
    "jpa", "jwt", "security", "linux", "unix", "etl", "llm", "ai", "genai", "machine",
    "learning", "data", "schema", "mapping", "distributed", "cache", "caching", "queue",
    "messaging", "kafka", "redis", "graphql", "rest", "oauth", "thread", "jvm",
}

TECHNICAL_TOPIC_PATTERNS = {
    "adjacency list": ["adjacency list", "adjacency"],
    "graph": ["graph", "graphs"],
    "binary tree": ["binary tree"],
    "tree": ["tree", "trees"],
    "heap": ["heap", "heaps"],
    "list": ["list", "lists"],
    "linked list": ["linked list"],
    "array": ["array", "arrays"],
    "stack": ["stack", "stacks"],
    "queue": ["queue", "queues"],
    "hash map": ["hash map", "hashmap", "map"],
    "hash set": ["hash set", "hashset", "set"],
    "bfs": ["bfs", "breadth first search"],
    "dfs": ["dfs", "depth first search"],
    "rest api": ["rest api", "restful api", "api"],
}

TECHNICAL_LANGUAGES = {
    "java",
    "python",
    "javascript",
    "typescript",
    "react",
    "angular",
    "spring",
    "springboot",
}

IMPLEMENTATION_MARKERS = {
    "implement",
    "implemented",
    "implementation",
    "build",
    "built",
    "design",
    "model",
    "using",
    "create",
    "created",
    "write",
    "wrote",
}

UNCLEAR_REPEAT_RESPONSE = (
    '⚠️ Say: "I want to make sure I give you a solid answer on that — could you say that one more time?"'
)


class LiveAIEngine:
    """
    Manages OpenAI responses for live interview answer generation.
    
    Pre-loaded with the session's system prompt containing resume, JD,
    skill mapping, and STAR stories. Maintains conversation history
    throughout the interview for context continuity.
    """

    def __init__(self, session: InterviewSession):
        """
        Args:
            session: Pre-built InterviewSession with system_prompt and model.
        """
        self.anthropic_client = AnthropicMessagesClient()
        self.openai_client = OpenAIResponsesClient()
        self.question_detector = QuestionDetector()
        self.session = session
        self.session.model = normalize_session_model(session.model)
        self.is_processing = False
        self.last_answer = ""
        self.last_question = ""

    def generate_instant_answer(self, interviewer_text: str) -> str:
        """
        Build a local first-draft answer from prepared session data.
        This avoids waiting on a full remote round-trip before showing anything.
        """
        question = interviewer_text.strip()
        if not question:
            return ""

        started_at = time.perf_counter()
        question_lower = question.lower()
        predicted_match = self._pick_predicted_question(question)
        predicted_type = str((predicted_match or {}).get("type", "")).lower()
        prepared_match = self._pick_prepared_answer(question)
        question_case = self._classify_question_case(question, prepared_match, predicted_match)

        if question_case == "concept_knowledge":
            skill = self._pick_skill(question)
            answer = self._build_concept_or_knowledge_answer(question, skill)
        elif question_case == "unrelated":
            answer = self._build_unrelated_professional_answer(question)
        elif self._matches_any(
            question_lower,
            [
                "tell me about yourself",
                "walk me through your background",
                "introduce yourself",
                "give me a quick overview of your background",
            ],
        ):
            answer = self._build_intro_answer()
        elif self._matches_any(
            question_lower,
            [
                "why this role",
                "why are you interested",
                "why do you want",
                "why this company",
                "why should we hire you",
            ],
        ):
            answer = self._build_why_role_answer()
        elif "weakness" in question_lower:
            answer = self._build_weakness_answer()
        elif "strength" in question_lower or "biggest strength" in question_lower:
            answer = self._build_strength_answer()
        elif self._is_behavioral_question(question_lower) or predicted_type == "behavioral":
            answer = self._build_behavioral_answer(question)
        else:
            skill = self._pick_skill(question) or self._extract_experience_topic(question)
            if question_case == "field_related_missing":
                answer = self._build_field_related_bridge_answer(
                    question=question,
                    skill=skill,
                    prepared_match=prepared_match,
                    predicted_match=predicted_match,
                )
            else:
                answer = self._build_skill_or_experience_answer(question, skill)

        cleaned = self._clean_model_answer(answer)
        logger.info(
            "Instant answer generated | chars=%s | case=%s | duration_ms=%.0f",
            len(cleaned),
            question_case,
            (time.perf_counter() - started_at) * 1000,
        )
        return cleaned

    async def prepare_live_answer(
        self,
        interviewer_text: str,
        candidate_text: Optional[str] = None,
        turn_type: Optional[str] = None,
    ) -> dict[str, str]:
        """
        Build the answer that should be shown live directly from the selected model.
        The prep-created OpenAI conversation is reused so live turns benefit
        from the same conversation state and cache-friendly prompt prefix.
        """
        metadata = self._question_metadata(interviewer_text, turn_type=turn_type)
        effective_question = metadata["effective_question"]

        if self._should_request_repeat(
            interviewer_text,
            effective_question,
            follow_up_context=metadata.get("follow_up_context", ""),
            turn_type=turn_type or metadata.get("turn_type", ""),
        ):
            logger.info("Low-confidence question detected; asking for repeat instead of guessing")
            return {
                "text": UNCLEAR_REPEAT_RESPONSE,
                "source": "unclear",
            }

        model_answer = await asyncio.wait_for(
            self._generate_fast_model_answer(
                interviewer_text=interviewer_text,
                effective_question=effective_question,
                candidate_text=candidate_text,
                follow_up_context=metadata.get("follow_up_context", ""),
                turn_type=turn_type or "",
            ),
            timeout=self._live_model_timeout_seconds(),
        )
        if not model_answer:
            raise RuntimeError("Live model returned an empty answer.")
        return {
            "text": model_answer,
            "source": self._live_model_source(),
        }

    def record_live_answer(
        self,
        interviewer_text: str,
        candidate_text: Optional[str],
        answer_text: str,
    ) -> None:
        """Persist the live Q/A turn so regenerate stays context-aware."""
        self.last_question = interviewer_text.strip()
        self.last_answer = answer_text.strip()
        metadata = self._question_metadata(interviewer_text)
        if self._should_store_turn(metadata["question_case"], metadata["question_intent"]):
            self._append_live_turn(interviewer_text=interviewer_text, candidate_text=candidate_text)
            self.session.conversation_history.append({
                "role": "assistant",
                "content": answer_text.strip(),
            })
            self._trim_history()

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
        full_response = await self.generate_answer_text(
            interviewer_text=interviewer_text,
            candidate_text=candidate_text,
        )
        if full_response:
            await self._stream_text(full_response, on_token)
        return full_response

    async def generate_answer_text(
        self,
        interviewer_text: str,
        candidate_text: Optional[str],
    ) -> str:
        """Generate the final refined answer text with the OpenAI API."""
        if self.is_processing:
            logger.warning("generate_answer_text skipped because a response is already in progress")
            return ""

        self.is_processing = True
        self.last_question = interviewer_text.strip()
        logger.info(
            "Generating refined answer | interviewer_chars=%s | candidate_chars=%s | model=%s",
            len(interviewer_text),
            len(candidate_text or ""),
            self.session.model,
        )

        try:
            metadata = self._question_metadata(interviewer_text)
            effective_question = metadata["effective_question"]
            question_case = metadata["question_case"]
            question_intent = metadata["question_intent"]
            should_store_turn = self._should_store_turn(question_case, question_intent)
            if should_store_turn:
                self._append_live_turn(interviewer_text=interviewer_text, candidate_text=candidate_text)

            full_response = await self._run_model_prompt(
                prompt=self._build_answer_prompt(
                    interviewer_text,
                    effective_question=effective_question,
                    question_case=question_case,
                    question_intent=question_intent,
                    include_history=self._should_include_recent_history(
                        question_case=question_case,
                        question_intent=question_intent,
                        question=effective_question,
                    ),
                    follow_up_context=metadata.get("follow_up_context", ""),
                ),
                model=self.session.model,
                use_shared_conversation=self._should_use_shared_conversation(
                    question_case=question_case,
                    question_intent=question_intent,
                    question=effective_question,
                ),
            )
            full_response = self._clean_model_answer(full_response)

            if should_store_turn:
                self.session.conversation_history.append({
                    "role": "assistant",
                    "content": full_response,
                })
                self._trim_history()

            self.last_answer = full_response
            logger.info("Refined answer generated successfully | chars=%s", len(full_response))
            return full_response
        finally:
            self.is_processing = False
            logger.info("Answer generation finished")

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
        if not self.session.conversation_history and not self.last_question:
            logger.warning("regenerate skipped because there is no previous question")
            return ""

        # Remove the last assistant response
        if (self.session.conversation_history
                and self.session.conversation_history[-1].get("role") == "assistant"):
            self.session.conversation_history.pop()

        # Add modifier instruction if provided
        modifier_instruction = ""
        if modifier == "shorter":
            modifier_instruction = "[CANDIDATE INSTRUCTION]: Make the answer SHORTER — 2-3 sentences max. Keep only the most important point."
        elif modifier == "more_detail":
            modifier_instruction = "[CANDIDATE INSTRUCTION]: Give MORE DETAIL — expand with additional examples, metrics, and context from the resume."
        else:
            modifier_instruction = "[CANDIDATE INSTRUCTION]: Regenerate the answer with a different angle or approach."

        # Stream new response
        self.is_processing = True
        logger.info("Regenerating answer | modifier=%s | model=%s", modifier or "default", self.session.model)
        try:
            last_question = self.last_question or "Regenerate the previous answer."
            metadata = self._question_metadata(last_question)
            effective_question = metadata["effective_question"]
            question_case = metadata["question_case"]
            question_intent = metadata["question_intent"]
            should_store_turn = self._should_store_turn(question_case, question_intent)
            if should_store_turn:
                self.session.conversation_history.append({
                    "role": "user",
                    "content": modifier_instruction,
                })
            full_response = await self._run_model_prompt(
                prompt=self._build_answer_prompt(
                    last_question,
                    effective_question=effective_question,
                    question_case=question_case,
                    question_intent=question_intent,
                    include_history=self._should_include_recent_history(
                        question_case=question_case,
                        question_intent=question_intent,
                        question=effective_question,
                    ),
                    follow_up_context=metadata.get("follow_up_context", ""),
                ) + (f"\n\n{modifier_instruction}" if not should_store_turn else ""),
                model=self.session.model,
                use_shared_conversation=self._should_use_shared_conversation(
                    question_case=question_case,
                    question_intent=question_intent,
                    question=effective_question,
                ),
            )
            full_response = self._clean_model_answer(full_response)
            await self._stream_text(full_response, on_token)

            if should_store_turn:
                self.session.conversation_history.append({
                    "role": "assistant",
                    "content": full_response
                })

            self.last_answer = full_response
            logger.info("Regenerated answer successfully | chars=%s", len(full_response))
            return full_response
        finally:
            self.is_processing = False
            logger.info("Regeneration finished")

    def _append_live_turn(self, interviewer_text: str, candidate_text: Optional[str]) -> None:
        if candidate_text and candidate_text.strip():
            self.session.conversation_history.append({
                "role": "user",
                "content": f"[CANDIDATE SAID]: {candidate_text.strip()}",
            })

        self.session.conversation_history.append({
            "role": "user",
            "content": f"[INTERVIEWER ASKED]: {interviewer_text.strip()}",
        })

    def _trim_history(self) -> None:
        max_hist = settings.max_conversation_history
        if len(self.session.conversation_history) > max_hist:
            self.session.conversation_history = self.session.conversation_history[-max_hist:]

    def _question_metadata(self, question: str, turn_type: Optional[str] = None) -> dict[str, str]:
        follow_up_context = ""
        normalized_question = self.question_detector.normalize_turn(question) or question.strip()
        effective_question = self._recover_technical_question(normalized_question) or normalized_question
        resolved_turn_type = turn_type or ("follow_up" if self._is_follow_up_question(effective_question) else "")
        if resolved_turn_type == "follow_up" and self.last_question.strip():
            follow_up_context = self.last_question.strip()
        prepared_match = self._pick_prepared_answer(effective_question)
        predicted_match = self._pick_predicted_question(effective_question)
        question_case = self._classify_question_case(
            effective_question,
            prepared_match,
            predicted_match,
        )
        question_intent = self._classify_question_intent(effective_question)
        if follow_up_context and question_intent in {"general", "unclear"}:
            previous_question = follow_up_context
            previous_prepared = self._pick_prepared_answer(previous_question)
            previous_predicted = self._pick_predicted_question(previous_question)
            question_case = self._classify_question_case(
                previous_question,
                previous_prepared,
                previous_predicted,
            )
            previous_intent = self._classify_question_intent(previous_question)
            if previous_intent != "unclear":
                question_intent = previous_intent
        turn_route = self._determine_turn_route(
            question_case=question_case,
            question_intent=question_intent,
            turn_type=resolved_turn_type,
            follow_up_context=follow_up_context,
        )
        return {
            "effective_question": effective_question,
            "question_case": question_case,
            "question_intent": question_intent,
            "follow_up_context": follow_up_context,
            "turn_type": resolved_turn_type,
            "turn_route": turn_route,
        }

    def _determine_turn_route(
        self,
        *,
        question_case: str,
        question_intent: str,
        turn_type: str,
        follow_up_context: str,
    ) -> str:
        if question_intent == "small_talk":
            return "small_talk"
        if question_intent == "reverse_interview":
            return "reverse_interview"
        if question_intent == "salary":
            return "salary"
        if question_intent == "logistical":
            return "logistical"
        if follow_up_context or turn_type == "follow_up":
            return "follow_up"
        if question_case == "concept_knowledge":
            return "concept"
        if question_case in {"personal_experience", "field_related_missing"}:
            return "experience"
        if turn_type == "answer_prompt":
            return "interview_prompt"
        if question_intent in {"behavioral", "experience", "motivational", "gap_or_weakness"}:
            return "experience"
        if question_intent == "general":
            return "interview_prompt"
        return "generic"

    def _should_store_turn(self, question_case: str, question_intent: str) -> bool:
        if question_case in {"personal_experience", "field_related_missing"}:
            return True
        return question_intent in {"behavioral", "gap_or_weakness"}

    def _build_answer_prompt(
        self,
        interviewer_text: str,
        effective_question: Optional[str] = None,
        *,
        question_case: Optional[str] = None,
        question_intent: Optional[str] = None,
        include_history: Optional[bool] = None,
        follow_up_context: str = "",
        turn_type: str = "",
        turn_route: Optional[str] = None,
    ) -> str:
        effective_question = (effective_question or interviewer_text).strip()
        prepared_match = self._pick_prepared_answer(effective_question)
        predicted_match = self._pick_predicted_question(effective_question)
        question_case = question_case or self._classify_question_case(
            effective_question,
            prepared_match,
            predicted_match,
        )
        question_intent = question_intent or self._classify_question_intent(effective_question)
        relevant_context = self._build_relevant_context(effective_question, question_case)
        bridge_context = self._build_bridge_context(effective_question)
        include_history = (
            self._should_include_recent_history(
                question_case=question_case,
                question_intent=question_intent,
                question=effective_question,
            )
            if include_history is None
            else include_history
        )
        history_block = self._build_recent_history_block() if include_history else ""
        prepared_reference = self._build_prepared_reference(effective_question, question_case)

        history_lines = []
        if history_block:
            history_lines.append(f"RECENT CONVERSATION:\n{history_block}")

        transcript_note = ""
        if interviewer_text.strip() != effective_question:
            transcript_note = (
                "TRANSCRIPT NOTE:\n"
                "The raw transcript likely contains one or more garbled words from speech recognition. "
                "Use the likely intended question below as the source of truth. Do not anchor on obviously garbled tokens.\n\n"
            )

        follow_up_note = ""
        if follow_up_context:
            follow_up_note = (
                "FOLLOW-UP CONTEXT:\n"
                f"The interviewer is asking a follow-up on this earlier topic: {follow_up_context}\n"
                "Answer the latest turn in continuity with that earlier topic instead of treating it like a brand-new unrelated question.\n\n"
            )

        turn_route = turn_route or self._determine_turn_route(
            question_case=question_case,
            question_intent=question_intent,
            turn_type=turn_type,
            follow_up_context=follow_up_context,
        )

        if turn_route == "concept":
            return self._build_concept_answer_prompt(
                interviewer_text=interviewer_text,
                effective_question=effective_question,
                question_intent=question_intent,
                relevant_context=relevant_context,
                bridge_context=bridge_context,
                transcript_note=transcript_note + follow_up_note,
                history_lines=history_lines,
            )

        if turn_route in {"experience", "follow_up"}:
            return self._build_experience_answer_prompt(
                interviewer_text=interviewer_text,
                effective_question=effective_question,
                question_intent=question_intent,
                question_case=question_case,
                relevant_context=relevant_context,
                bridge_context=bridge_context,
                prepared_reference=prepared_reference,
                transcript_note=transcript_note + follow_up_note,
                history_lines=history_lines,
                turn_route=turn_route,
            )

        return self._build_general_interview_prompt(
            interviewer_text=interviewer_text,
            effective_question=effective_question,
            question_intent=question_intent,
            question_case=question_case,
            relevant_context=relevant_context,
            bridge_context=bridge_context,
            transcript_note=transcript_note + follow_up_note,
            history_lines=history_lines,
            turn_route=turn_route,
        )

    def _build_experience_answer_prompt(
        self,
        *,
        interviewer_text: str,
        effective_question: str,
        question_intent: str,
        question_case: str,
        relevant_context: str,
        bridge_context: str,
        prepared_reference: str,
        transcript_note: str,
        history_lines: list[str],
        turn_route: str,
    ) -> str:
        history_block = "\n".join(history_lines)
        history_section = f"\n\n{history_block}" if history_block else ""
        return f"""You are InterviewAce's live experience answer engine for a job interview.

This turn is an {turn_route} turn. Answer like a strong interview candidate speaking naturally out loud.
Use the uploaded resume, JD, company research, and prepared dossier as source-of-truth context.
Never fabricate employers, timelines, tools, or results. If the interviewer asks about a related area not directly documented, bridge from the closest real experience instead of pretending.
If this is a follow-up, stay consistent with the earlier topic and deepen the answer instead of starting over.

OUTPUT FORMAT
- 🎯 OPEN WITH: 1 short first-person sentence that frames the answer clearly.
- 💬 THE ANSWER: 3-5 conversational sentences with specific tools, systems, responsibilities, and measurable outcomes when available.
- 🔗 BRIDGE: 1 short sentence tying the answer back to the target role or company.

RULES
- Sound like a candidate in a live interview, not like a resume or textbook.
- Use first person naturally.
- Prefer the single best role/project/story instead of dumping every prepared fact.
- If the interviewer asks about a company, role, project, or prior experience, stay anchored to that exact documented experience.
- If the interviewer asks for more detail, expand only that thread and keep continuity with previous answers.
- Never repeat the prepared reference verbatim; use it only as supporting context.

{transcript_note}RAW TRANSCRIPT QUESTION:
{interviewer_text.strip()}

LIKELY INTENDED QUESTION:
{effective_question}

QUESTION INTENT:
{question_intent}

QUESTION CASE:
{question_case}

DOCUMENT FACTS TO USE FIRST:
{relevant_context}

ROLE / COMPANY BRIDGE CONTEXT:
{bridge_context}

PREPARED SUPPORT CONTEXT:
{prepared_reference}{history_section}"""

    def _build_general_interview_prompt(
        self,
        *,
        interviewer_text: str,
        effective_question: str,
        question_intent: str,
        question_case: str,
        relevant_context: str,
        bridge_context: str,
        transcript_note: str,
        history_lines: list[str],
        turn_route: str,
    ) -> str:
        history_block = "\n".join(history_lines)
        history_section = f"\n\n{history_block}" if history_block else ""
        special_case_rules = {
            "small_talk": 'Output only a short warm response the candidate can say immediately.',
            "reverse_interview": 'Output 2-3 smart questions for the interviewer grounded in company research or the JD.',
            "salary": 'Stay professional, concise, and flexible. Discuss range only if documented.',
            "logistical": 'Answer directly and clearly with any documented facts available; otherwise stay practical and concise.',
            "interview_prompt": 'Answer naturally in interview mode, even if the wording is conversational rather than a clean direct question.',
            "generic": 'Answer in a practical, interview-ready way without forcing resume facts that do not belong.',
        }
        return f"""You are InterviewAce's live interview answer engine.

Answer this turn in natural interview mode.
{special_case_rules.get(turn_route, 'Answer naturally and directly.')}

RULES
- Keep the answer concise, speakable, and high-confidence.
- Use resume/JD facts only when they genuinely belong.
- Do not force a personal story into a generic or conceptual turn.
- If the question is general but interview-related, answer like a strong candidate speaking in conversation.
- If the transcript is slightly garbled, use the likely intended question rather than copying the noise.

OUTPUT FORMAT
- 🎯 OPEN WITH: 1 short opening sentence.
- 💬 THE ANSWER: 2-4 conversational sentences.
- 🔗 BRIDGE: 1 short line tying it back to the role when relevant.

{transcript_note}RAW TRANSCRIPT QUESTION:
{interviewer_text.strip()}

LIKELY INTENDED QUESTION:
{effective_question}

TURN ROUTE:
{turn_route}

QUESTION INTENT:
{question_intent}

QUESTION CASE:
{question_case}

OPTIONAL CONTEXT:
{relevant_context}

ROLE / COMPANY BRIDGE:
{bridge_context}{history_section}"""

    def _build_concept_answer_prompt(
        self,
        *,
        interviewer_text: str,
        effective_question: str,
        question_intent: str,
        relevant_context: str,
        bridge_context: str,
        transcript_note: str,
        history_lines: list[str],
    ) -> str:
        history_block = "\n".join(history_lines)
        history_section = f"\n\n{history_block}" if history_block else ""
        return f"""You are InterviewAce's live technical answer engine for a software interview.

This question is a concept or technical knowledge question.
Answer the likely intended question in interview mode: direct, clear, technically correct, and naturally speakable.
Do not force an unrelated resume story, but do make the answer sound like something a candidate would actually say out loud in an interview.
It is fine to use light first-person phrasing like "The way I think about it is..." or "In practice, I'd..." when it helps the answer sound natural.
Do not invent experience, projects, or tools the candidate has not actually used.
If the raw transcript contains one garbled technical token, ignore it and answer the likely intended question.
If the intent is still unclear, output only:
⚠️ Say: "I want to make sure I give you a solid answer on that — could you say that one more time?"

OUTPUT FORMAT
- 🎯 OPEN WITH: 1 direct sentence that frames the concept the way a strong candidate would begin answering it.
- 💬 THE ANSWER: 3-5 conversational technical sentences with concrete terminology, examples, implementation details, or tradeoffs.
- 🔗 BRIDGE: 1 short sentence connecting the concept to practical engineering work or the target role.

RULES
- Be technically correct first.
- Keep the tone interview-ready, not textbook-only and not resume-bullet style.
- Use first person only when it makes the answer sound more natural; never use it to fake experience.
- No fabricated experience.
- Keep the answer concise, natural, and easy to speak.
- If the question is about implementation, explain the data structure, core steps, tradeoffs, and time/space complexity when relevant.
- If the question is a simple concept question, answer it directly first, then briefly make it practical.

{transcript_note}RAW TRANSCRIPT QUESTION:
{interviewer_text.strip()}

LIKELY INTENDED QUESTION:
{effective_question}

QUESTION INTENT:
{question_intent}

TECHNICAL CONTEXT:
{relevant_context}

ROLE / PRACTICAL BRIDGE:
{bridge_context}{history_section}"""

    async def _generate_fast_model_answer(
        self,
        interviewer_text: str,
        effective_question: Optional[str],
        candidate_text: Optional[str],
        follow_up_context: str = "",
        turn_type: str = "",
    ) -> str:
        effective_question = (effective_question or interviewer_text).strip()
        metadata = self._question_metadata(interviewer_text, turn_type=turn_type or None)
        question_case = metadata["question_case"]
        question_intent = metadata["question_intent"]
        follow_up_context = follow_up_context or metadata.get("follow_up_context", "")
        turn_route = metadata.get("turn_route", "")
        prompt = self._build_answer_prompt(
            interviewer_text=interviewer_text,
            effective_question=effective_question,
            question_case=question_case,
            question_intent=question_intent,
            include_history=self._should_include_recent_history(
                question_case=question_case,
                question_intent=question_intent,
                question=effective_question,
            ),
            follow_up_context=follow_up_context,
            turn_type=turn_type or metadata.get("turn_type", ""),
            turn_route=turn_route,
        )
        if candidate_text and candidate_text.strip():
            prompt += f"\n\nLATEST CANDIDATE CONTEXT:\n{candidate_text.strip()}"
        result = await self._run_model_prompt(
            prompt=prompt,
            model=self.session.model,
            use_shared_conversation=self._should_use_shared_conversation(
                question_case=question_case,
                question_intent=question_intent,
                question=effective_question,
            ),
        )
        return self._clean_model_answer(result)

    async def _run_model_prompt(
        self,
        prompt: str,
        model: str,
        *,
        use_shared_conversation: bool = True,
    ) -> str:
        normalized_model = normalize_session_model(model, fallback=self.session.model)
        provider = provider_for_model(normalized_model, fallback=self.session.model)

        if provider == "anthropic":
            return await self.anthropic_client.run_prompt(
                prompt=prompt,
                model=normalized_model,
                system_blocks=self._anthropic_system_blocks(),
            )

        normalized_openai_model = OpenAIResponsesClient.normalize_model(
            normalized_model,
            fallback=self.session.model,
        )
        return await self.openai_client.run_prompt(
            prompt=prompt,
            model=normalized_openai_model,
            conversation_id=(self.session.openai_conversation_id or None) if use_shared_conversation else None,
            prompt_cache_key=self.session.openai_prompt_cache_key or None,
        )

    def _uses_openai_model(self, model: Optional[str] = None) -> bool:
        return provider_for_model(model or self.session.model, fallback=self.session.model) == "openai"

    def _live_model_timeout_seconds(self) -> float:
        return 5.5

    def _live_model_source(self) -> str:
        return self.session.model

    def _anthropic_system_blocks(self) -> list[dict]:
        stable_rules = (
            "You are InterviewAce's live interview answer engine. "
            "Use the prep dossier as the primary source of truth, keep answers concise and speakable, "
            "and never contradict documented facts."
        )
        dossier = self.session.system_prompt.strip() or "No prep dossier was generated for this session."
        return [
            AnthropicMessagesClient.build_system_block(stable_rules),
            AnthropicMessagesClient.build_system_block(dossier, cache=True),
        ]

    def _build_recent_history_block(self) -> str:
        recent_messages = self.session.conversation_history[-10:]
        lines = []
        for message in recent_messages:
            role = message.get("role", "user").upper()
            content = message.get("content", "").strip()
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _is_follow_up_question(self, question: str) -> bool:
        question_lower = question.lower().strip()
        follow_up_markers = [
            "tell me more",
            "can you elaborate",
            "elaborate",
            "walk me through that",
            "walk me through it",
            "more detail",
            "what specifically",
            "what did you mean",
            "why did",
            "why was",
            "what happened next",
            "how did that",
            "what didn't work",
            "what would you do differently",
            "in more detail",
        ]
        return any(marker in question_lower for marker in follow_up_markers)

    def _should_include_recent_history(
        self,
        *,
        question_case: str,
        question_intent: str,
        question: str,
    ) -> bool:
        if self._is_follow_up_question(question):
            return True
        if question_case == "concept_knowledge":
            return False
        return question_intent in {"behavioral", "experience", "motivational", "gap_or_weakness"}

    def _should_use_shared_conversation(
        self,
        *,
        question_case: str,
        question_intent: str,
        question: str,
    ) -> bool:
        if not self._uses_openai_model():
            return False
        if question_case == "concept_knowledge" and not self._is_follow_up_question(question):
            return False
        if question_intent == "unclear":
            return False
        if self._is_follow_up_question(question):
            return True
        return question_intent in {"behavioral", "experience", "motivational", "gap_or_weakness", "reverse_interview", "salary"}

    def _classify_question_intent(self, question: str) -> str:
        question_lower = question.lower().strip()

        if not question_lower:
            return "unclear"

        if any(phrase in question_lower for phrase in ["how are you", "nice to meet you", "can you hear me", "good morning", "good afternoon", "good evening"]):
            return "small_talk"

        if any(phrase in question_lower for phrase in ["any questions for us", "do you have any questions for us", "what questions do you have for us"]):
            return "reverse_interview"

        if any(phrase in question_lower for phrase in ["salary", "compensation", "pay range", "expected salary", "current ctc", "expected ctc"]):
            return "salary"

        if any(phrase in question_lower for phrase in ["weakness", "gap in", "missing experience", "haven't worked with", "don't have experience with"]):
            return "gap_or_weakness"

        if self._is_behavioral_question(question_lower):
            return "behavioral"

        if self._is_personal_experience_question(question_lower):
            return "experience"

        if self._matches_any(
            question_lower,
            [
                "why this company",
                "why this role",
                "why are you interested",
                "where do you see yourself",
                "what are you looking for",
            ],
        ):
            return "motivational"

        if self._is_technical_knowledge_question(question_lower):
            return "technical_or_knowledge"

        if any(phrase in question_lower for phrase in ["availability", "notice period", "work authorization", "visa", "relocation", "location"]):
            return "logistical"

        if len(self._normalize_tokens(question)) <= 2:
            return "unclear"

        return "general"

    def _build_bridge_context(self, interviewer_text: str) -> str:
        jd = self._jd_data()
        title = self._clean_sentence(jd.get("title", ""))
        company = self._clean_sentence(jd.get("company", ""))
        required_skills = jd.get("required_skills", [])

        lines = []
        if title or company:
            lines.append(f"Target: {title or 'Role'}{f' at {company}' if company else ''}")

        mirrored_skills = []
        if isinstance(required_skills, list):
            for item in required_skills[:6]:
                if isinstance(item, dict):
                    skill = self._clean_sentence(item.get("skill", ""))
                    if skill:
                        mirrored_skills.append(skill)
                else:
                    skill = self._clean_sentence(str(item))
                    if skill:
                        mirrored_skills.append(skill)
        if mirrored_skills:
            lines.append(f"JD keywords to mirror: {', '.join(mirrored_skills[:5])}")

        context_snippets = self._pick_context_snippets(interviewer_text, limit=2)
        if context_snippets:
            lines.append("Company research / extra context:")
            for snippet in context_snippets:
                lines.append(f"- {snippet}")

        return "\n".join(lines) if lines else "Use the specific company name or target role in the bridge when relevant."

    def _build_relevant_context(self, interviewer_text: str, question_case: str) -> str:
        resume = self._resume_data()
        jd = self._jd_data()
        role = self._pick_best_role(interviewer_text)
        project = self._pick_best_project(interviewer_text)
        story = self._pick_best_story(interviewer_text)
        skill = self._pick_skill(interviewer_text)
        matches = self._pick_best_matches(interviewer_text, limit=2)
        predicted_match = self._pick_predicted_question(interviewer_text)

        lines = []
        summary = self._clean_sentence(resume.get("summary", ""))
        if summary and question_case != "concept_knowledge":
            lines.append(f"Candidate summary: {summary}")

        title = self._clean_sentence(jd.get("title", ""))
        company = self._clean_sentence(jd.get("company", ""))
        if title or company:
            lines.append(f"Target role: {title or 'Role'}{f' at {company}' if company else ''}")

        if skill:
            lines.append(f"Question-related skill: {skill}")

        relevant_skills = self._collect_skills()[:8]
        if relevant_skills:
            lines.append(f"Core skills: {', '.join(relevant_skills)}")

        if question_case == "concept_knowledge":
            knowledge_reference = self._knowledge_reference(interviewer_text, skill)
            if knowledge_reference:
                lines.append(f"Technical reference: {knowledge_reference}")
            lines.append(
                "This is a concept or technical knowledge question. Answer directly, accurately, and clearly. Do not frame it as personal experience unless the interviewer explicitly asks about your experience."
            )
            return "\n".join(lines)

        if role:
            role_title = self._clean_sentence(role.get("title", "Relevant role"))
            role_company = self._clean_sentence(role.get("company", ""))
            role_duration = self._clean_sentence(role.get("duration", ""))
            role_line = f"Relevant experience: {role_title}"
            if role_company:
                role_line += f" at {role_company}"
            if role_duration:
                role_line += f" ({role_duration})"
            lines.append(role_line)
            for achievement in role.get("achievements", [])[:2]:
                cleaned = self._clean_sentence(achievement)
                if cleaned:
                    lines.append(f"Exact role proof: {cleaned}")

        if project:
            project_name = self._clean_sentence(project.get("name", "Relevant project"))
            project_desc = self._clean_sentence(project.get("description", ""))
            project_outcome = self._clean_sentence(project.get("outcome", ""))
            project_bits = [bit for bit in [project_name, project_desc, project_outcome] if bit]
            if project_bits:
                lines.append(f"Relevant project proof: {' | '.join(project_bits)}")

        if story:
            theme = self._clean_sentence(story.get("theme", ""))
            situation = self._clean_sentence(story.get("situation", ""))
            action = self._clean_sentence(story.get("action", ""))
            result = self._clean_sentence(story.get("result", ""))
            story_bits = [bit for bit in [theme, situation, action, result] if bit]
            if story_bits:
                lines.append(f"Relevant STAR proof: {' | '.join(story_bits)}")

        if matches:
            lines.append("Best resume-to-JD evidence:")
            for match in matches:
                requirement = self._clean_sentence(match.get("jd_requirement", ""))
                evidence = self._clean_sentence(match.get("resume_evidence", ""))
                if requirement or evidence:
                    lines.append(f"- {requirement}: {evidence}".strip(": "))

        if predicted_match:
            predicted_question = self._clean_sentence(predicted_match.get("question", ""))
            predicted_resume_match = self._clean_sentence(predicted_match.get("best_resume_match", ""))
            if predicted_question:
                lines.append(f"Closest predicted question: {predicted_question}")
            if predicted_resume_match:
                lines.append(f"Closest predicted resume angle: {predicted_resume_match}")

        context_snippets = self._pick_context_snippets(interviewer_text, limit=2)
        if context_snippets:
            lines.append("Uploaded context snippets:")
            for snippet in context_snippets:
                lines.append(f"- {snippet}")

        if question_case == "unrelated":
            lines.append(
                "This is not grounded in the resume or JD. Answer generically and confidently, but use the target role/company in the bridge when relevant."
            )

        return "\n".join(lines) if lines else "Use the candidate's prepared resume context."

    def _pick_context_snippets(self, question: str, limit: int = 2) -> list[str]:
        scored_chunks = []
        for chunk in self._context_snippet_chunks():
            score = self._score_text(question, chunk)
            if score > 0:
                scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        selected = []
        for _, chunk in scored_chunks:
            shortened = " ".join(chunk.split())
            if len(shortened) > 220:
                shortened = f"{shortened[:217].rstrip()}..."
            if shortened not in selected:
                selected.append(shortened)
            if len(selected) >= limit:
                break
        return selected

    def _context_snippet_chunks(self) -> list[str]:
        chunks = []
        for text in self.session.context_texts:
            if not isinstance(text, str):
                continue
            for raw_chunk in re.split(r"\n\s*\n+", text):
                cleaned = " ".join(raw_chunk.split()).strip()
                if cleaned and len(cleaned) >= 40:
                    chunks.append(cleaned)
        return chunks

    def _resume_data(self) -> dict:
        return self.session.resume_structured if isinstance(self.session.resume_structured, dict) else {}

    def _jd_data(self) -> dict:
        return self.session.jd_structured if isinstance(self.session.jd_structured, dict) else {}

    def _mapping_data(self) -> dict:
        return self.session.skill_mapping if isinstance(self.session.skill_mapping, dict) else {}

    def _roles(self) -> list[dict]:
        roles = self._resume_data().get("roles", [])
        return roles if isinstance(roles, list) else []

    def _projects(self) -> list[dict]:
        projects = self._resume_data().get("projects", [])
        return projects if isinstance(projects, list) else []

    def _star_stories(self) -> list[dict]:
        stories = self._mapping_data().get("star_stories", [])
        return stories if isinstance(stories, list) else []

    def _matches(self) -> list[dict]:
        matches = self._mapping_data().get("matches", [])
        return matches if isinstance(matches, list) else []

    def _prepared_answers(self) -> list[dict]:
        prepared_answers = self.session.prepared_answers
        return prepared_answers if isinstance(prepared_answers, list) else []

    def _predicted_questions(self) -> list[dict]:
        questions = self.session.predicted_questions
        return questions if isinstance(questions, list) else []

    def _gaps(self) -> list[dict]:
        gaps = self._mapping_data().get("gaps", [])
        return gaps if isinstance(gaps, list) else []

    def _collect_skills(self) -> list[str]:
        resume = self._resume_data()
        skills = []
        skill_groups = resume.get("skills", {}) if isinstance(resume.get("skills", {}), dict) else {}
        for key in ["technical", "tools"]:
            values = skill_groups.get(key, [])
            if isinstance(values, list):
                skills.extend(str(value).strip() for value in values if str(value).strip())

        jd_skills = self._jd_data().get("required_skills", [])
        if isinstance(jd_skills, list):
            for item in jd_skills:
                if isinstance(item, dict):
                    skill = str(item.get("skill", "")).strip()
                    if skill:
                        skills.append(skill)

        deduped = []
        seen = set()
        for skill in skills:
            lowered = skill.lower()
            if lowered not in seen:
                deduped.append(skill)
                seen.add(lowered)
        return deduped

    def _matches_any(self, text: str, phrases: list[str]) -> bool:
        return any(phrase in text for phrase in phrases)

    def _is_behavioral_question(self, question_lower: str) -> bool:
        behavioral_markers = [
            "tell me about a time",
            "describe a time",
            "walk me through a time",
            "challenge",
            "conflict",
            "deadline",
            "mistake",
            "failure",
            "difficult",
            "proud",
            "led",
            "leadership",
            "team",
            "pressure",
            "feedback",
            "ambiguity",
        ]
        return any(marker in question_lower for marker in behavioral_markers)

    def _is_opinion_or_personal_question(self, question_lower: str) -> bool:
        markers = [
            "what do you think",
            "what's your opinion",
            "what is your opinion",
            "do you prefer",
            "which do you prefer",
            "what matters most to you",
            "how would you approach",
            "how would you handle",
            "how do you approach",
            "how do you handle",
            "what would you do",
        ]
        return any(marker in question_lower for marker in markers)

    def _is_profile_question(self, question_lower: str) -> bool:
        profile_markers = [
            "tell me about yourself",
            "walk me through your background",
            "introduce yourself",
            "give me a quick overview of your background",
            "why this role",
            "why are you interested",
            "why do you want",
            "why this company",
            "why should we hire you",
            "what makes you a fit",
            "biggest strength",
            "greatest strength",
            "biggest weakness",
            "greatest weakness",
            "your strength",
            "your weakness",
        ]
        return any(marker in question_lower for marker in profile_markers)

    def _is_personal_experience_question(self, question_lower: str) -> bool:
        experience_markers = [
            "tell me about a time",
            "describe a time",
            "walk me through a time",
            "give me an example",
            "tell me about yourself",
            "walk me through your background",
            "introduce yourself",
            "tell me about your experience",
            "tell me about your previous experience",
            "tell me about your past experience",
            "your experience previously",
            "experience previously",
            "describe a project",
            "tell me about a project",
            "walk me through a project",
            "project you worked on",
            "project you've worked on",
            "what did you work on",
            "what was your role",
            "what experience do you have",
            "what is your experience",
            "what's your experience",
            "your experience with",
            "your experience in",
            "your previous experience",
            "your past experience",
            "experience working with",
            "experience with",
            "experience in",
            "work using",
            "your work",
            "your work there",
            "work there",
            "work with",
            "background with",
            "background in",
            "walk me through your",
            "tell me about your work",
            "how did you handle",
            "how have you handled",
            "how did you deal",
            "how did you solve",
            "how have you used",
            "where have you used",
            "have you worked with",
            "have you used",
            "did you use",
            "did you work with",
            "did you work on",
            "when did you use",
            "have you ever",
            "what challenges did you face",
            "what did you do",
        ]
        if self._has_resume_named_anchor(question_lower):
            anchored_markers = [
                "experience",
                "role",
                "worked",
                "work",
                "used",
                "using",
                "project",
                "projects",
                "previous",
                "previously",
                "background",
                "tell me about",
                "walk me through",
                "explain",
                "describe",
                "have you",
                "did you",
                "can you tell me",
            ]
            if any(marker in question_lower for marker in anchored_markers):
                return True
        return self._is_profile_question(question_lower) or any(
            marker in question_lower for marker in experience_markers
        )

    def _is_resume_story_question(self, question_lower: str) -> bool:
        story_markers = [
            "tell me about a project",
            "describe a project",
            "walk me through a project",
            "project you worked on",
            "project you've worked on",
            "what did you work on",
            "what was your role",
            "tell me about yourself",
            "walk me through your background",
            "introduce yourself",
            "previous experience",
            "past experience",
            "tell me about your experience",
            "tell me about your previous experience",
            "experience previously",
            "tell me more about",
            "tell me about a time",
            "describe a time",
            "give me an example",
            "how did you handle",
            "how did you solve",
            "what challenges did you face",
            "what did you do",
        ]
        return any(marker in question_lower for marker in story_markers)

    def _is_technical_knowledge_question(self, question_lower: str) -> bool:
        if self._has_resume_named_anchor(question_lower):
            anchored_experience_markers = [
                "experience",
                "role",
                "worked",
                "work",
                "used",
                "using",
                "project",
                "projects",
                "previous",
                "previously",
                "background",
                "at ",
                "in ",
                "there",
            ]
            if any(marker in question_lower for marker in anchored_experience_markers):
                return False

        experience_context_markers = [
            "your role",
            "your background",
            "your experience",
            "your work",
            "your work there",
            "work there",
            "experience at",
            "worked on",
            "project",
            "company",
            "walk me through your",
            "at morgan stanley",
            "at illinois state university",
            "at marketing dollar",
            "tell me about your",
            "tell me about the project",
            "tell me about the work",
            "tell me about your experience",
        ]
        if any(marker in question_lower for marker in experience_context_markers):
            return False

        technical_markers = [
            "what is ",
            "what's ",
            "what are ",
            "define ",
            "how does ",
            "difference between",
            "compare ",
            "explain ",
            "can you explain",
            "walk me through",
            "concept",
            "concepts",
            "feature",
            "features",
            "command",
            "commands",
            "syntax",
            "why use",
            "why would you use",
            "when would you use",
            "purpose of",
            "benefits of",
            "advantages of",
            "api",
            "rest",
            "microservice",
            "oops",
            "exception",
            "thread",
            "jvm",
            "spring",
            "hibernate",
            "react",
            "angular",
            "docker",
            "jenkins",
            "sql",
            "database",
            "encapsulation",
            "inheritance",
            "polymorphism",
            "abstraction",
            "constructor",
            "graph",
            "adjacency",
            "arraylist",
            "linked list",
            "hashmap",
            "hash map",
            "queue",
            "stack",
            "tree",
            "bfs",
            "dfs",
        ]
        if any(marker in question_lower for marker in technical_markers):
            return True

        for aliases in TECHNICAL_TOPIC_PATTERNS.values():
            if any(alias in question_lower for alias in aliases):
                return True

        return False

    def _resume_anchor_phrases(self) -> list[str]:
        phrases: list[str] = []
        for role in self._roles():
            for raw_value in [role.get("company", ""), role.get("title", "")]:
                cleaned = self._clean_sentence(raw_value).lower()
                if cleaned:
                    phrases.append(cleaned)
                simplified = re.sub(r"\([^)]*\)", "", cleaned).strip()
                if simplified and simplified != cleaned:
                    phrases.append(simplified)

        for project in self._projects():
            name = self._clean_sentence(project.get("name", "")).lower()
            if name:
                phrases.append(name)

        deduped = []
        seen = set()
        for phrase in phrases:
            normalized = " ".join(phrase.split()).strip()
            if len(normalized) < 3:
                continue
            if normalized not in seen:
                deduped.append(normalized)
                seen.add(normalized)
        return deduped

    def _has_resume_named_anchor(self, question_lower: str) -> bool:
        return any(phrase in question_lower for phrase in self._resume_anchor_phrases())

    def _looks_like_interview_prompt(self, question_lower: str) -> bool:
        prompt_markers = [
            "can you",
            "could you",
            "would you",
            "will you",
            "do you",
            "did you",
            "have you",
            "are you",
            "tell me",
            "walk me through",
            "walk us through",
            "explain",
            "help me understand",
            "talk to me about",
            "describe",
            "what is",
            "what are",
            "what's",
            "how do",
            "how did",
            "how would",
            "why",
            "where",
            "when",
        ]
        return any(marker in question_lower for marker in prompt_markers)

    def _question_lexicon(self) -> set[str]:
        lexicon = set(STOPWORDS)
        lexicon.update(FIELD_KEYWORDS)
        lexicon.update(TECHNICAL_LANGUAGES)
        lexicon.update(IMPLEMENTATION_MARKERS)
        lexicon.update({"tell", "walk", "through", "about", "using", "used", "with", "java", "python"})

        for canonical, aliases in TECHNICAL_TOPIC_PATTERNS.items():
            lexicon.update(self._normalize_tokens(canonical))
            for alias in aliases:
                lexicon.update(self._normalize_tokens(alias))

        for skill in self._collect_skills():
            lexicon.update(self._normalize_tokens(skill))

        lexicon.update(self._normalize_tokens(self._resume_reference_text()))
        lexicon.update(self._normalize_tokens(" ".join(self.session.context_texts)))
        return lexicon

    def _should_request_repeat(
        self,
        raw_question: str,
        effective_question: str,
        *,
        follow_up_context: str = "",
        turn_type: str = "",
    ) -> bool:
        if follow_up_context or turn_type in {"follow_up", "answer_prompt"}:
            return False

        question_lower = effective_question.lower()

        if self._looks_like_interview_prompt(question_lower):
            return False

        if self._has_resume_named_anchor(question_lower):
            return False

        question_intent = self._classify_question_intent(effective_question)
        if question_intent == "unclear":
            raw_tokens = list(self._normalize_tokens(raw_question))
            if len(raw_tokens) <= 1:
                return True
            if not self._looks_like_interview_prompt(raw_question.lower()):
                return True
            return False

        prepared_match = self._pick_prepared_answer(effective_question)
        predicted_match = self._pick_predicted_question(effective_question)
        question_case = self._classify_question_case(
            effective_question,
            prepared_match,
            predicted_match,
        )

        # If the app has already identified a plausible interview question shape,
        # prefer answering instead of forcing a repeat.
        if question_case in {"personal_experience", "field_related_missing", "concept_knowledge"}:
            return False

        if question_intent in {"behavioral", "experience", "motivational", "salary", "gap_or_weakness", "logistical"}:
            return False

        if self._is_profile_question(question_lower) or self._is_personal_experience_question(question_lower):
            return False

        if self._question_has_resume_anchor(effective_question, prepared_match, predicted_match):
            return False

        raw_tokens = list(self._normalize_tokens(raw_question))
        if question_intent == "technical_or_knowledge":
            skill = self._pick_skill(effective_question)
            if self._knowledge_reference(effective_question, skill):
                return False
            if self._recover_technical_question(raw_question):
                return False
            if len(self._normalize_tokens(effective_question)) >= 1:
                return False

        if len(raw_tokens) < 2:
            return True

        lexicon = self._question_lexicon()
        known = [token for token in raw_tokens if token in lexicon]
        unknown = [token for token in raw_tokens if token not in lexicon]

        if len(raw_tokens) >= 5 and len(unknown) >= 3 and len(known) <= 2:
            return True

        if len(raw_tokens) >= 6 and (len(unknown) / max(len(raw_tokens), 1)) >= 0.5:
            return True

        if (
            question_intent == "technical_or_knowledge"
            and len(raw_tokens) <= 6
            and unknown
            and len(known) <= 3
            and effective_question == raw_question
        ):
            return True

        return False

    def _recover_technical_question(self, question: str) -> str:
        question_lower = question.lower()
        tokens = self._normalize_tokens(question)
        if not tokens:
            return ""

        language = ""
        for item in TECHNICAL_LANGUAGES:
            if item in tokens or item in question_lower:
                language = item
                break

        topic = ""
        for canonical, aliases in TECHNICAL_TOPIC_PATTERNS.items():
            if canonical in question_lower:
                topic = canonical
                break
            if any(alias in question_lower for alias in aliases):
                topic = canonical
                break

        has_impl_marker = bool(tokens & IMPLEMENTATION_MARKERS) or any(
            phrase in question_lower
            for phrase in [
                "how would you implement",
                "explain how you would implement",
                "built a",
                "implemented a",
                "implemented an",
                "using java",
                "using python",
            ]
        )

        if topic and language and has_impl_marker:
            return f"Explain how to implement a {topic} in {language}."

        if topic and has_impl_marker:
            return f"Explain how to implement a {topic}."

        if topic and language and self._is_technical_knowledge_question(question_lower):
            return f"Explain {topic} in {language}."

        return ""

    def _question_has_resume_anchor(
        self,
        question: str,
        prepared_match: dict | None,
        predicted_match: dict | None,
    ) -> bool:
        prepared_score = float((prepared_match or {}).get("_score", 0.0))
        predicted_score = self._score_text(
            question,
            " ".join(
                [
                    str((predicted_match or {}).get("question", "")),
                    str((predicted_match or {}).get("best_resume_match", "")),
                    str((predicted_match or {}).get("why_likely", "")),
                ]
            ),
        ) if predicted_match else 0.0
        role = self._pick_best_role(question)
        role_score = self._score_text(
            question,
            " ".join(
                [
                    str((role or {}).get("title", "")),
                    str((role or {}).get("company", "")),
                    " ".join((role or {}).get("achievements", [])),
                ]
            ),
        )
        project = self._pick_best_project(question)
        project_score = self._score_text(
            question,
            " ".join(
                [
                    str((project or {}).get("name", "")),
                    str((project or {}).get("description", "")),
                    str((project or {}).get("outcome", "")),
                    " ".join((project or {}).get("skills_used", [])),
                ]
            ),
        ) if project else 0.0
        best_match_score = 0.0
        for match in self._pick_best_matches(question, limit=2):
            best_match_score = max(
                best_match_score,
                self._score_text(
                    question,
                    " ".join(
                        [
                            str(match.get("jd_requirement", "")),
                            str(match.get("resume_evidence", "")),
                            str(match.get("strength", "")),
                        ]
                    ),
                ),
            )

        skill = self._pick_skill(question)
        explicit_skill_match = bool(skill and skill.lower() in question.lower())
        return any(
            score >= threshold
            for score, threshold in [
                (prepared_score, 0.30),
                (predicted_score, 0.24),
                (role_score, 0.24),
                (project_score, 0.24),
                (best_match_score, 0.24),
            ]
        ) or explicit_skill_match

    def _resume_reference_text(self) -> str:
        resume = self._resume_data()
        role_lines = []
        for role in self._roles():
            role_lines.extend(
                [
                    str(role.get("title", "")),
                    str(role.get("company", "")),
                    str(role.get("location", "")),
                    " ".join(role.get("achievements", [])),
                ]
            )

        project_lines = []
        for project in self._projects():
            project_lines.extend(
                [
                    str(project.get("name", "")),
                    str(project.get("description", "")),
                    str(project.get("outcome", "")),
                    " ".join(project.get("skills_used", [])),
                ]
            )

        match_lines = []
        for match in self._matches():
            match_lines.extend(
                [
                    str(match.get("jd_requirement", "")),
                    str(match.get("resume_evidence", "")),
                    str(match.get("strength", "")),
                ]
            )

        skill_lines = []
        for skill in self._collect_skills():
            skill_lines.append(skill)

        return " ".join(
            [
                str(resume.get("summary", "")),
                *role_lines,
                *project_lines,
                *match_lines,
                *skill_lines,
            ]
        )

    def _extract_experience_topic(self, question: str) -> str:
        cleaned = re.sub(r"[?]", "", question).strip()
        patterns = [
            r"(?i)\bexperience with (.+)$",
            r"(?i)\bworked with (.+)$",
            r"(?i)\bused (.+)$",
            r"(?i)\busing (.+)$",
            r"(?i)\bhands-on with (.+)$",
            r"(?i)\bbackground in (.+)$",
            r"(?i)\bexposure to (.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned)
            if match:
                topic = self._clean_sentence(match.group(1))
                if topic:
                    return re.split(r"(?i)\b(in production|at work|on the job|professionally)\b", topic)[0].strip()
        return ""

    def _asks_about_missing_field_topic(self, question: str) -> bool:
        topic = self._extract_experience_topic(question)
        if not topic:
            return False

        topic_tokens = self._normalize_tokens(topic)
        if not topic_tokens:
            return False

        resume_corpus = self._resume_reference_text()
        resume_tokens = self._normalize_tokens(resume_corpus)
        if topic_tokens & resume_tokens:
            return False

        return self._is_field_related_question(question)

    def _should_use_first_person_for_generic_answer(self, question: str) -> bool:
        question_lower = question.lower()
        personal_markers = [
            "how would you",
            "what would you do",
            "what do you think",
            "what's your opinion",
            "what is your opinion",
            "do you prefer",
            "which do you prefer",
            "how do you handle",
            "how would you handle",
            "what matters most to you",
            "how do you approach",
            "how would you approach",
            "have you ever",
            "tell me about yourself",
            "tell me about a time",
            "describe a time",
            "what experience do you have",
        ]
        return any(marker in question_lower for marker in personal_markers)

    def _is_field_related_question(self, question: str) -> bool:
        question_tokens = self._normalize_tokens(question)
        skill_tokens = set()
        for skill in self._collect_skills():
            skill_tokens.update(self._normalize_tokens(skill))

        jd_tokens = set()
        jd = self._jd_data()
        jd_tokens.update(self._normalize_tokens(str(jd.get("title", ""))))
        for item in jd.get("required_skills", []):
            if isinstance(item, dict):
                jd_tokens.update(self._normalize_tokens(str(item.get("skill", ""))))
            else:
                jd_tokens.update(self._normalize_tokens(str(item)))

        return bool(
            question_tokens & (skill_tokens | jd_tokens | FIELD_KEYWORDS)
        )

    def _normalize_tokens(self, text: str) -> set[str]:
        tokens = re.findall(r"[a-z0-9+#.]+", text.lower())
        return {token for token in tokens if token not in STOPWORDS and len(token) > 1}

    def _score_text(self, query: str, candidate: str) -> float:
        if not query or not candidate:
            return 0.0
        query_tokens = self._normalize_tokens(query)
        candidate_tokens = self._normalize_tokens(candidate)
        overlap = 0.0
        if query_tokens and candidate_tokens:
            overlap = len(query_tokens & candidate_tokens) / len(query_tokens)
        ratio = SequenceMatcher(None, query.lower(), candidate.lower()).ratio()
        return overlap * 0.7 + ratio * 0.3

    def _pick_best_role(self, question: str) -> dict | None:
        best_role = None
        best_score = 0.0
        for role in self._roles():
            haystack = " ".join(
                [
                    str(role.get("title", "")),
                    str(role.get("company", "")),
                    str(role.get("location", "")),
                    " ".join(role.get("achievements", [])),
                ]
            )
            score = self._score_text(question, haystack)
            if score > best_score:
                best_role = role
                best_score = score
        return best_role or (self._roles()[0] if self._roles() else None)

    def _pick_best_project(self, question: str) -> dict | None:
        best_project = None
        best_score = 0.0
        for project in self._projects():
            haystack = " ".join(
                [
                    str(project.get("name", "")),
                    str(project.get("description", "")),
                    str(project.get("outcome", "")),
                    " ".join(project.get("skills_used", [])),
                ]
            )
            score = self._score_text(question, haystack)
            if score > best_score:
                best_project = project
                best_score = score
        return best_project if best_score >= 0.18 else None

    def _pick_best_story(self, question: str) -> dict | None:
        best_story = None
        best_score = 0.0
        for story in self._star_stories():
            haystack = " ".join(
                [
                    str(story.get("theme", "")),
                    str(story.get("situation", "")),
                    str(story.get("task", "")),
                    str(story.get("action", "")),
                    str(story.get("result", "")),
                    " ".join(story.get("best_for_questions", [])),
                ]
            )
            score = self._score_text(question, haystack)
            if score > best_score:
                best_story = story
                best_score = score
        return best_story or (self._star_stories()[0] if self._star_stories() else None)

    def _pick_best_matches(self, question: str, limit: int) -> list[dict]:
        scored = []
        for match in self._matches():
            haystack = " ".join(
                [
                    str(match.get("jd_requirement", "")),
                    str(match.get("resume_evidence", "")),
                    str(match.get("strength", "")),
                ]
            )
            scored.append((self._score_text(question, haystack), match))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [match for score, match in scored[:limit] if score > 0]

    def _pick_predicted_question(self, question: str) -> dict | None:
        best_item = None
        best_score = 0.0
        for item in self._predicted_questions():
            if not isinstance(item, dict):
                continue
            haystack = " ".join(
                [
                    str(item.get("question", "")),
                    str(item.get("best_resume_match", "")),
                    str(item.get("why_likely", "")),
                    str(item.get("type", "")),
                ]
            )
            score = self._score_text(question, haystack)
            if score > best_score:
                best_item = item
                best_score = score
        return best_item if best_score >= 0.18 else None

    def _pick_prepared_answer(self, question: str) -> dict | None:
        best_item = None
        best_score = 0.0
        for item in self._prepared_answers():
            if not isinstance(item, dict):
                continue
            haystack = " ".join(
                [
                    str(item.get("question", "")),
                    str(item.get("best_resume_match", "")),
                    str(item.get("type", "")),
                    str(item.get("answer", "")),
                ]
            )
            score = self._score_text(question, haystack)
            if score > best_score:
                best_item = dict(item)
                best_score = score
        if best_item and best_score >= 0.22:
            best_item["_score"] = best_score
            return best_item
        return None

    def _classify_question_case(
        self,
        question: str,
        prepared_match: dict | None,
        predicted_match: dict | None,
    ) -> str:
        question_lower = question.lower()

        has_resume_anchor = self._question_has_resume_anchor(
            question,
            prepared_match,
            predicted_match,
        )
        is_experience_question = self._is_personal_experience_question(question_lower)
        is_field_related = self._is_field_related_question(question)

        if self._is_profile_question(question_lower):
            return "personal_experience"

        if is_experience_question and self._asks_about_missing_field_topic(question):
            return "field_related_missing"

        if is_experience_question and self._is_resume_story_question(question_lower):
            return "personal_experience"

        if is_experience_question and has_resume_anchor:
            return "personal_experience"

        if is_experience_question and is_field_related:
            return "field_related_missing"

        if self._is_technical_knowledge_question(question_lower):
            return "concept_knowledge"

        if has_resume_anchor:
            return "personal_experience"

        if self._is_opinion_or_personal_question(question_lower):
            return "unrelated"

        if is_field_related:
            return "field_related_missing"

        return "unrelated"

    def _build_prepared_reference(self, question: str, question_case: str) -> str:
        if question_case in {"concept_knowledge", "unrelated"}:
            return "Do not use a prepared resume answer for this question type."

        prepared_match = self._pick_prepared_answer(question)
        if not prepared_match:
            return "No close prepared answer found. Use the actual question and candidate context."

        question_text = self._clean_sentence(prepared_match.get("question", ""))
        resume_match = self._clean_sentence(prepared_match.get("best_resume_match", ""))
        answer_text = self._clean_model_answer(str(prepared_match.get("answer", "")))
        reference_lines = [
            f"Closest prepared question: {question_text}" if question_text else "",
            f"Best resume anchor: {resume_match}" if resume_match else "",
            "Use the prepared answer only as support context; do not repeat it verbatim.",
            f"Prepared reference answer: {answer_text}" if answer_text else "",
        ]
        return "\n".join(line for line in reference_lines if line)

    def _pick_skill(self, question: str) -> str:
        question_lower = question.lower()
        skills = sorted(self._collect_skills(), key=len, reverse=True)
        for skill in skills:
            if skill.lower() in question_lower:
                return skill

        query_tokens = self._normalize_tokens(question)
        for skill in skills:
            skill_tokens = self._normalize_tokens(skill)
            if query_tokens & skill_tokens:
                return skill
        return ""

    def _build_intro_answer(self) -> str:
        resume = self._resume_data()
        roles = self._roles()
        jd = self._jd_data()
        summary = self._clean_sentence(resume.get("summary", ""))
        current_role = roles[0] if roles else {}
        previous_role = roles[1] if len(roles) > 1 else {}
        role_title = self._clean_sentence(current_role.get("title", ""))
        role_company = self._clean_sentence(current_role.get("company", ""))
        role_achievement = self._clean_sentence(next(iter(current_role.get("achievements", [])), ""))
        previous_company = self._clean_sentence(previous_role.get("company", ""))
        previous_achievement = self._clean_sentence(next(iter(previous_role.get("achievements", [])), ""))
        target_title = self._clean_sentence(jd.get("title", ""))

        parts = []
        if summary:
            parts.append(summary)
        elif role_title:
            parts.append(f"I'm a software engineer with hands-on experience across backend, frontend, and AI-driven workflows.")

        if role_title or role_company or role_achievement:
            role_bits = [bit for bit in [role_title, role_company] if bit]
            sentence = f"Most recently, I've been working as {' at '.join(role_bits) if len(role_bits) == 2 else (role_bits[0] if role_bits else 'a software engineer')}"
            if role_achievement:
                sentence += f", where I {self._lowercase_first(role_achievement)}"
            parts.append(f"{sentence}.")

        if previous_company or previous_achievement:
            sentence = "Before that"
            if previous_company:
                sentence += f", at {previous_company}"
            if previous_achievement:
                sentence += f", I {self._lowercase_first(previous_achievement)}"
            parts.append(f"{sentence}.")

        if target_title:
            parts.append(f"That mix of engineering depth and practical execution is why this {target_title} role feels like a strong fit for me.")

        return " ".join(self._dedupe_sentences(parts[:4]))

    def _build_why_role_answer(self) -> str:
        jd = self._jd_data()
        matches = self._pick_best_matches("why this role company fit", limit=2)
        title = self._clean_sentence(jd.get("title", "role"))
        company = self._clean_sentence(jd.get("company", ""))

        parts = []
        opening = f"I'm interested in this {title}" if title else "I'm interested in this opportunity"
        if company:
            opening += f" at {company}"
        opening += " because it lines up well with the work I've been strongest in."
        parts.append(opening)

        for match in matches[:2]:
            evidence = self._clean_sentence(match.get("resume_evidence", ""))
            if evidence:
                parts.append(f"For example, {self._lowercase_first(evidence)}.")

        parts.append("I also like that it lets me bring both full-stack engineering experience and strong problem-solving in fast-moving environments.")
        return " ".join(self._dedupe_sentences(parts[:4]))

    def _build_behavioral_answer(self, question: str) -> str:
        story = self._pick_best_story(question)
        if story:
            situation = self._clean_sentence(story.get("situation", ""))
            task = self._clean_sentence(story.get("task", ""))
            action = self._clean_sentence(story.get("action", ""))
            result = self._clean_sentence(story.get("result", ""))
            parts = []
            if situation:
                parts.append(f"One good example was {self._lowercase_first(situation)}.")
            if task:
                parts.append(f"My responsibility there was to {self._lowercase_first(task)}.")
            if action:
                parts.append(f"I {self._lowercase_first(action)}.")
            if result:
                parts.append(f"As a result, {self._lowercase_first(result)}.")
            if parts:
                return " ".join(self._dedupe_sentences(parts[:4]))

        role = self._pick_best_role(question)
        achievement = self._clean_sentence(next(iter((role or {}).get("achievements", [])), ""))
        if achievement:
            return (
                f"A relevant example was during my time at {self._clean_sentence(role.get('company', 'work'))}. "
                f"I {self._lowercase_first(achievement)}, which is the kind of situation where I stay structured, collaborative, and focused on the outcome."
            )
        return self._build_generic_answer()

    def _build_strength_answer(self) -> str:
        matches = self._matches()
        if matches:
            top_match = matches[0]
            requirement = self._clean_sentence(top_match.get("jd_requirement", "executing on complex engineering work"))
            evidence = self._clean_sentence(top_match.get("resume_evidence", ""))
            sentence = f"One of my biggest strengths is {self._lowercase_first(requirement)}."
            if evidence:
                sentence += f" A good example is that I {self._lowercase_first(evidence)}."
            sentence += " I think that combination of ownership and practical execution helps me contribute quickly."
            return sentence

        skills = self._collect_skills()
        if skills:
            return (
                f"One of my biggest strengths is my ability to apply {skills[0]} in real projects and connect it to broader product needs. "
                "I tend to pick things up quickly, stay structured, and focus on shipping reliable outcomes."
            )
        return self._build_generic_answer()

    def _build_weakness_answer(self) -> str:
        gaps = self._gaps()
        if gaps:
            gap = gaps[0]
            requirement = self._clean_sentence(gap.get("jd_requirement", "an area I have been strengthening"))
            mitigation = self._clean_sentence(gap.get("mitigation", "I have been closing that gap through recent hands-on work and focused learning"))
            return (
                f"One area I've been intentionally strengthening is {self._lowercase_first(requirement)}. "
                f"It hasn't always been my deepest area, so I've been working on it by {self._lowercase_first(mitigation)}. "
                "What gives me confidence is that I ramp quickly and turn learning into practical output."
            )

        return (
            "One thing I've been very intentional about is continuing to deepen my expertise in newer areas as my scope grows. "
            "When I notice a gap, I usually close it by taking on hands-on work, building something real, and getting feedback quickly."
        )

    def _build_skill_or_experience_answer(self, question: str, skill: str) -> str:
        role = self._pick_best_role(question)
        project = self._pick_best_project(question)
        evidence = self._find_relevant_evidence(question, skill, role, project)
        predicted_match = self._pick_predicted_question(question)
        predicted_resume_match = self._clean_sentence((predicted_match or {}).get("best_resume_match", ""))

        if skill:
            parts = [f"Yes, I've worked quite a bit with {skill} in real projects."]
            if evidence:
                parts.append(f"For example, I {self._lowercase_first(evidence)}.")
            elif predicted_resume_match:
                parts.append(
                    f"The strongest example from my background is {self._lowercase_first(predicted_resume_match)}."
                )
            if project:
                project_name = self._clean_sentence(project.get("name", ""))
                outcome = self._clean_sentence(project.get("outcome", ""))
                if project_name or outcome:
                    project_line = "I also applied it"
                    if project_name:
                        project_line += f" in my {project_name} project"
                    if outcome:
                        project_line += f", where I {self._lowercase_first(outcome)}"
                    parts.append(f"{project_line}.")
            parts.append("So I can speak to both the implementation details and the practical impact.")
            return " ".join(self._dedupe_sentences(parts[:4]))

        if evidence:
            return (
                f"A strong example from my experience is that I {self._lowercase_first(evidence)}. "
                "That gave me hands-on exposure to designing, building, and improving production-facing systems."
            )
        if predicted_resume_match:
            return (
                f"The strongest angle from my background here is {self._lowercase_first(predicted_resume_match)}. "
                "I’d answer by tying that experience to the exact problems this role is trying to solve."
            )

        return self._build_generic_answer()

    def _build_concept_or_knowledge_answer(
        self,
        question: str,
        skill: str,
    ) -> str:
        question_lower = question.lower()

        for key, snippet in KNOWLEDGE_SNIPPETS.items():
            if key in question_lower:
                return snippet

        if "command" in question_lower and skill:
            examples = self._command_examples_for_skill(skill)
            if examples:
                parts = [f"Common {skill} commands include {examples}."]
                parts.append(
                    "The main thing is understanding when to use them for building, running, testing, debugging, and shipping code reliably."
                )
                return " ".join(self._dedupe_sentences(parts[:3]))

        topic = skill or self._extract_topic_from_question(question)
        parts = []
        if topic:
            parts.append(
                f"{topic} can be explained clearly by focusing on what it is, why it matters, and when it is used."
            )
        else:
            parts.append(
                "A strong answer explains what it is, why it matters, and where it fits in practice."
            )
        parts.append(
            "The explanation should stay clear, technically correct, and practical rather than sounding like a memorized definition."
        )
        return " ".join(self._dedupe_sentences(parts[:3]))

    def _build_field_related_bridge_answer(
        self,
        question: str,
        skill: str,
        prepared_match: dict | None,
        predicted_match: dict | None,
    ) -> str:
        role = self._pick_best_role(question)
        project = self._pick_best_project(question)
        evidence = self._find_relevant_evidence(question, skill, role, project)
        bridge_anchor = self._clean_sentence((prepared_match or {}).get("best_resume_match", "")) or self._clean_sentence(
            (predicted_match or {}).get("best_resume_match", "")
        ) or self._clean_sentence(evidence)

        parts = []
        if skill:
            parts.append(
                f"I haven't used {skill} as a primary tool in my background yet, but I can connect it to very similar work I've already done."
            )
        else:
            parts.append(
                "I haven't had that exact scenario directly in my background yet, but I can connect it to closely related work from my background."
            )

        if bridge_anchor:
            parts.append(
                f"The closest experience I can draw from is {self._lowercase_first(bridge_anchor)}."
            )

        role = self._pick_best_role(question)
        company = self._clean_sentence((role or {}).get("company", ""))
        if company and bridge_anchor:
            parts.append(
                f"At {company}, that gave me exposure to similar engineering decisions, tradeoffs, and delivery expectations."
            )

        parts.append(
            "So even if the exact tool is new, I can still speak to the same kind of problem-solving approach and ramp up quickly in a real project environment."
        )
        return " ".join(self._dedupe_sentences(parts[:4]))

    def _build_unrelated_professional_answer(self, question: str) -> str:
        role_topic = self._extract_quality_topic(question)
        question_lower = question.lower()
        if role_topic:
            return (
                f"I think a good {role_topic} combines strong fundamentals, clear communication, ownership, and the ability to keep learning as the work changes. "
                "The biggest difference usually comes from balancing technical quality with collaboration and consistent follow-through."
            )

        if self._should_use_first_person_for_generic_answer(question):
            if (
                "what do you think" in question_lower
                or "what's your opinion" in question_lower
                or "what is your opinion" in question_lower
            ):
                return (
                    "I think the strongest answer usually comes down to sound judgment, clear communication, and staying practical about the outcome. "
                    "I generally value structured thinking, adaptability, and consistency more than overcomplicating things."
                )
            return (
                "I would approach that by first understanding what matters most in the situation, then responding in a practical and structured way. "
                "I usually focus on clear communication, sound judgment, and getting to a solid outcome without overcomplicating things."
            )
        return (
            "A strong professional answer would focus on understanding the situation clearly, responding in a practical and structured way, and keeping communication clear throughout. "
            "The goal is good judgment, professionalism, and a solid outcome without unnecessary complexity."
        )

    def _build_generic_answer(self) -> str:
        resume = self._resume_data()
        roles = self._roles()
        summary = self._clean_sentence(resume.get("summary", ""))
        role = roles[0] if roles else {}
        company = self._clean_sentence(role.get("company", ""))
        achievement = self._clean_sentence(next(iter(role.get("achievements", [])), ""))

        parts = []
        if summary:
            parts.append(summary)
        if company and achievement:
            parts.append(f"Most recently, at {company}, I {self._lowercase_first(achievement)}.")
        parts.append("The way I'd answer this is by connecting that experience to the kind of impact this role needs.")
        return " ".join(self._dedupe_sentences(parts[:3]))

    def _find_relevant_evidence(
        self,
        question: str,
        skill: str,
        role: dict | None,
        project: dict | None,
    ) -> str:
        skill_lower = skill.lower() if skill else ""
        best_role_overlap = ""
        if role:
            for achievement in role.get("achievements", []):
                achievement_text = str(achievement)
                achievement_lower = achievement_text.lower()
                if skill_lower and skill_lower in achievement_lower:
                    return achievement_text
                if not skill_lower and self._score_text(question, achievement_text) > 0.2:
                    return achievement_text
                if skill_lower and self._score_text(question, achievement_text) > 0.2 and not best_role_overlap:
                    best_role_overlap = achievement_text

        if project:
            project_haystack = " ".join(
                [
                    str(project.get("name", "")),
                    str(project.get("description", "")),
                    str(project.get("outcome", "")),
                    " ".join(project.get("skills_used", [])),
                ]
            )
            project_score = self._score_text(question, project_haystack)
            project_skill_match = bool(
                skill_lower and skill_lower in project_haystack.lower()
            )
            if project_skill_match or project_score >= 0.22:
                description = str(project.get("description", "")).strip()
                if description:
                    return description
                outcome = str(project.get("outcome", "")).strip()
                if outcome:
                    return outcome

        for match in self._pick_best_matches(question, limit=2):
            evidence = str(match.get("resume_evidence", "")).strip()
            if evidence:
                return evidence

        if best_role_overlap:
            return best_role_overlap
        return ""

    def _command_examples_for_skill(self, skill: str) -> str:
        skill_lower = skill.lower()
        examples = {
            "java": "javac, java, mvn test, mvn clean install, and mvn spring-boot:run",
            "spring boot": "mvn spring-boot:run, mvn test, and mvn clean package",
            "react": "npm install, npm run dev, and npm run build",
            "angular": "ng serve, ng build, and ng test",
            "docker": "docker build, docker run, and docker compose up",
            "git": "git status, git add, git commit, and git push",
            "jenkins": "pipeline build, test, and deploy stages triggered through Jenkins jobs",
            "sql": "commands like SELECT, JOIN, GROUP BY, and UPDATE in day-to-day querying",
        }
        for key, value in examples.items():
            if key in skill_lower:
                return value
        return ""

    def _extract_topic_from_question(self, question: str) -> str:
        cleaned = re.sub(r"[?]", "", question).strip()
        patterns = [
            r"(?i)^what(?:'s| is) (.+)$",
            r"(?i)^explain (.+)$",
            r"(?i)^define (.+)$",
            r"(?i)^difference between (.+)$",
            r"(?i)^compare (.+)$",
            r"(?i)^how does (.+) work$",
            r"(?i)^what are (.+)$",
        ]
        for pattern in patterns:
            match = re.match(pattern, cleaned)
            if match:
                topic = self._clean_sentence(match.group(1))
                if topic:
                    return topic
        return ""

    def _extract_quality_topic(self, question: str) -> str:
        cleaned = re.sub(r"[?]", "", question).strip()
        patterns = [
            r"(?i)^what do you think makes a good (.+)$",
            r"(?i)^what makes a good (.+)$",
            r"(?i)^what are the qualities of a good (.+)$",
            r"(?i)^what makes someone a good (.+)$",
        ]
        for pattern in patterns:
            match = re.match(pattern, cleaned)
            if match:
                topic = self._clean_sentence(match.group(1))
                if topic:
                    return topic
        return ""

    def _knowledge_reference(self, question: str, skill: str) -> str:
        question_lower = question.lower()

        for key, snippet in KNOWLEDGE_SNIPPETS.items():
            if key in question_lower:
                return snippet

        topic = skill or self._extract_topic_from_question(question)
        recovered = self._recover_technical_question(question)
        if recovered and recovered != question:
            return f"Likely intended technical question: {recovered}"

        if topic:
            return f"Explain {topic} directly with correct terminology, a short implementation/framework if needed, and no invented personal experience."

        return ""

    def _clean_model_answer(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return ""

        cleaned = re.sub(r"(?is)^```(?:\w+)?\s*", "", cleaned).strip()
        cleaned = re.sub(r"(?is)\s*```$", "", cleaned).strip()

        upper = cleaned.upper()
        if "## ANSWER" in upper:
            cleaned = re.sub(r"(?is)^.*?##\s*ANSWER\s*", "", cleaned).strip()
            cleaned = re.split(r"(?im)^##\s*(KEY POINTS|CAUTION)\s*$", cleaned)[0].strip()

        cleaned = re.sub(r"(?im)^##\s*[A-Z ].*$", "", cleaned).strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _clean_sentence(self, text: str) -> str:
        cleaned = " ".join(str(text).strip().split())
        return cleaned.rstrip(".")

    def _lowercase_first(self, text: str) -> str:
        cleaned = self._clean_sentence(text)
        if not cleaned:
            return ""
        return cleaned[0].lower() + cleaned[1:]

    def _dedupe_sentences(self, sentences: list[str]) -> list[str]:
        result = []
        seen = set()
        for sentence in sentences:
            normalized = " ".join(sentence.split()).strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key not in seen:
                seen.add(key)
                result.append(normalized)
        return result

    async def _stream_text(
        self,
        text: str,
        on_token: Callable[[str], Awaitable[None]],
    ) -> None:
        for chunk in self._chunk_text(text):
            logger.debug("Streaming answer chunk | chars=%s", len(chunk))
            await on_token(chunk)

    def _chunk_text(self, text: str) -> list[str]:
        words = text.split()
        if not words:
            return []

        chunks = []
        current = []
        for word in words:
            current.append(word)
            if len(" ".join(current)) >= 24:
                chunks.append(" ".join(current) + " ")
                current = []
        if current:
            chunks.append(" ".join(current))
        return chunks
