"""
InterviewAce — Context Builder Service
Pre-interview pipeline: parses files, extracts data, builds the master system prompt.

Owner: Dev 1 (Vineeth)
Status: STUB — implement the full pipeline
"""

import json
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable

from ..config import settings
from ..models.session import InterviewSession
from .anthropic_messages_client import AnthropicMessagesClient
from .file_parser import parse_file
from .model_registry import normalize_session_model, provider_for_model
from .openai_responses_client import OpenAIResponsesClient


# Load prompt templates
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
logger = logging.getLogger("interviewace.context_builder")


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _coerce_prepared_answers(data: dict | list) -> list[dict]:
    """Normalize prepared answers into a safe list of question/answer items."""
    if not isinstance(data, list):
        return []

    prepared_answers = []
    for item in data:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if not question or not answer:
            continue
        prepared_answers.append(
            {
                "question": question,
                "type": str(item.get("type", "")).strip() or "general",
                "best_resume_match": str(item.get("best_resume_match", "")).strip(),
                "answer": answer,
            }
        )
    return prepared_answers


def _resolve_api_model(candidate: str | None, fallback: str | None = None) -> str:
    """Normalize the selected session model into a supported provider model."""
    return normalize_session_model(candidate, fallback=fallback)


def _build_live_conversation_seed_items(
    *,
    resume_structured: dict | list,
    jd_structured: dict | list,
    skill_mapping: dict | list,
    predicted_questions: list,
    prepared_answers: list[dict],
    context_texts: list[str],
) -> list[dict]:
    """Build the static interview dossier that seeds the reusable OpenAI conversation."""
    developer_text = """You are InterviewAce's live answer engine for one candidate.

Treat the interview dossier already in this conversation as the primary source of truth for the entire interview.
Use exact facts from that dossier whenever available.
Never fabricate employers, job titles, timelines, companies, tools, metrics, certifications, or achievements not present in the dossier.
When later user messages arrive, they will contain the latest interviewer question plus runtime guidance for how to answer.
Keep continuity across follow-up questions and never contradict prior grounded details once they are established."""

    dossier_text = "\n\n".join([
        "INTERVIEW DOSSIER",
        f"RESUME STRUCTURED:\n{json.dumps(resume_structured, indent=2)}",
        f"JOB DESCRIPTION STRUCTURED:\n{json.dumps(jd_structured, indent=2)}",
        f"JD MATCHES AND STAR STORIES:\n{json.dumps(skill_mapping, indent=2)}",
        f"PREDICTED QUESTIONS:\n{json.dumps(predicted_questions[:12], indent=2) if isinstance(predicted_questions, list) else '[]'}",
        f"PREPARED ANSWER REFERENCES:\n{json.dumps(prepared_answers[:12], indent=2)}",
        "UPLOADED CONTEXT FILES / COMPANY RESEARCH:\n"
        + ("\n---\n".join(context_texts) if context_texts else "No additional context provided."),
    ])

    return [
        OpenAIResponsesClient.build_message("developer", developer_text),
        OpenAIResponsesClient.build_message("user", dossier_text),
    ]


async def prepare_session(
    session_id: str,
    resume_path: str,
    jd_text: str,
    context_file_paths: list[str],
    model: str,
    system_audio_device: str,
    speaker_output_device: str,
    mic_device: str,
    on_progress: Optional[Callable[[str, int], Awaitable[None]]] = None,
) -> InterviewSession:
    """
    Run the full pre-interview preparation pipeline.
    
    This is called once before the interview starts. It:
    1. Parses all uploaded files into text
    2. Sends resume to the OpenAI API for structured extraction
    3. Sends JD to the OpenAI API for requirement analysis
    4. Maps resume skills to JD requirements
    5. Generates predicted interview questions
    6. Seeds a reusable OpenAI conversation for live answers
    
    Args:
        resume_path: Path to uploaded resume file
        jd_text: Job description text
        context_file_paths: Paths to optional context files
        model: OpenAI model selected for this session
        system_audio_device: Selected system audio device name
        mic_device: Selected microphone device name
        on_progress: Optional callback for progress updates (step_name, percent)
    
    Returns:
        Fully prepared InterviewSession ready for live use
    """
    selected_model = _resolve_api_model(model, fallback=settings.default_model)
    provider = provider_for_model(selected_model, fallback=settings.default_model)
    client = AnthropicMessagesClient() if provider == "anthropic" else OpenAIResponsesClient()
    prep_model = _resolve_api_model(model, fallback=settings.prep_model)
    live_model = _resolve_api_model(model, fallback=settings.default_model)
    prompt_cache_key = f"interviewace-session:{session_id}"
    conversation_id = ""
    if provider == "openai":
        conversation_id = await client.create_conversation(
            metadata={
                "app": "InterviewAce",
                "session_id": session_id,
                "phase": "prep",
            }
        )
    logger.info(
        "Preparing session | session_id=%s | provider=%s | resume_path=%s | context_files=%s | live_model=%s | prep_model=%s | conversation_id=%s | system_device=%s | speaker_output=%s | mic_device=%s",
        session_id,
        provider,
        resume_path,
        len(context_file_paths),
        live_model,
        prep_model,
        conversation_id or "n/a",
        system_audio_device,
        speaker_output_device,
        mic_device,
    )

    # ─── Step 1: Parse files ─────────────────────────
    if on_progress:
        await on_progress("Parsing resume...", 10)

    resume_text = await parse_file(resume_path)
    logger.info("Resume parsed | chars=%s", len(resume_text))

    context_texts = []
    for path in context_file_paths:
        text = await parse_file(path)
        context_texts.append(text)
        logger.info("Context file parsed | path=%s | chars=%s", path, len(text))

    # ─── Step 2: Extract structured resume data ──────
    if on_progress:
        await on_progress("Analyzing resume...", 25)

    resume_prompt = _load_prompt("resume_extract.txt").format(resume_text=resume_text)
    resume_structured = _safe_parse_json(
        await client.run_prompt(
            prompt=resume_prompt,
            model=prep_model,
            prompt_cache_key=f"{prompt_cache_key}:prep",
        )
    )
    logger.info("Resume analysis complete | type=%s", type(resume_structured).__name__)

    # ─── Step 3: Analyze JD requirements ─────────────
    if on_progress:
        await on_progress("Analyzing job description...", 40)

    jd_prompt = _load_prompt("jd_analyze.txt").format(jd_text=jd_text)
    jd_structured = _safe_parse_json(
        await client.run_prompt(
            prompt=jd_prompt,
            model=prep_model,
            prompt_cache_key=f"{prompt_cache_key}:prep",
        )
    )
    logger.info("Job description analysis complete | type=%s", type(jd_structured).__name__)

    # ─── Step 4: Map resume to JD + build STAR stories
    if on_progress:
        await on_progress("Mapping skills and building stories...", 60)

    mapping_prompt = f"""Given this candidate's resume and the job description, create a detailed mapping.

RESUME DATA:
{json.dumps(resume_structured, indent=2)}

JD REQUIREMENTS:
{json.dumps(jd_structured, indent=2)}

ADDITIONAL CONTEXT:
{chr(10).join(context_texts) if context_texts else 'None provided'}

Return ONLY valid JSON:
{{
  "matches": [
    {{"jd_requirement": "...", "resume_evidence": "...", "strength": "strong|moderate|weak"}}
  ],
  "gaps": [
    {{"jd_requirement": "...", "mitigation": "How to address this in the interview"}}
  ],
  "star_stories": [
    {{
      "theme": "Leadership / Data-Driven / Problem Solving / etc.",
      "situation": "...",
      "task": "...",
      "action": "...",
      "result": "... (with metrics)",
      "best_for_questions": ["What type of questions this story answers"]
    }}
  ]
}}"""

    skill_mapping = _safe_parse_json(
        await client.run_prompt(
            prompt=mapping_prompt,
            model=prep_model,
            prompt_cache_key=f"{prompt_cache_key}:prep",
        )
    )
    logger.info("Skill mapping complete | type=%s", type(skill_mapping).__name__)

    # ─── Step 5: Predict likely interview questions ──
    if on_progress:
        await on_progress("Predicting interview questions...", 80)

    questions_prompt = f"""Based on this job description and candidate profile, generate the 20 most likely interview questions.

JD: {json.dumps(jd_structured, indent=2)}
CANDIDATE: {json.dumps(resume_structured, indent=2)}

Return ONLY valid JSON — an array of objects:
[
  {{
    "question": "The interview question",
    "type": "behavioral|technical|situational|culture_fit|intro",
    "why_likely": "Why this question will probably be asked",
    "best_resume_match": "Which resume experience/skill maps to this"
  }}
]"""

    predicted_questions = _safe_parse_json(
        await client.run_prompt(
            prompt=questions_prompt,
            model=prep_model,
            prompt_cache_key=f"{prompt_cache_key}:prep",
        )
    )
    logger.info(
        "Predicted questions complete | type=%s | count=%s",
        type(predicted_questions).__name__,
        len(predicted_questions) if isinstance(predicted_questions, list) else "n/a",
    )

    # ─── Step 6: Build instant answer bank ──────────
    if on_progress:
        await on_progress("Building instant answer bank...", 90)

    answer_bank_prompt = _load_prompt("answer_bank.txt").format(
        resume_structured=json.dumps(resume_structured, indent=2),
        jd_structured=json.dumps(jd_structured, indent=2),
        skill_mapping=json.dumps(skill_mapping.get("matches", []), indent=2),
        star_stories=json.dumps(skill_mapping.get("star_stories", []), indent=2),
        context_texts="\n---\n".join(context_texts) if context_texts else "No additional context provided.",
        predicted_questions=json.dumps(
            predicted_questions[:12] if isinstance(predicted_questions, list) else [],
            indent=2,
        ),
    )
    prepared_answers = _coerce_prepared_answers(
        _safe_parse_json(
            await client.run_prompt(
                prompt=answer_bank_prompt,
                model=prep_model,
                prompt_cache_key=f"{prompt_cache_key}:prep",
            )
        )
    )
    logger.info("Prepared answer bank complete | count=%s", len(prepared_answers))

    # ─── Step 7: Build master system prompt ──────────
    if on_progress:
        await on_progress("Building AI context...", 95)

    system_prompt_template = _load_prompt("system_prompt.txt")
    system_prompt = system_prompt_template.format(
        resume_structured=json.dumps(resume_structured, indent=2),
        jd_structured=json.dumps(jd_structured, indent=2),
        skill_mapping=json.dumps(skill_mapping.get("matches", []), indent=2),
        star_stories=json.dumps(skill_mapping.get("star_stories", []), indent=2),
        context_texts="\n---\n".join(context_texts) if context_texts else "No additional context provided.",
        predicted_questions=json.dumps(
            predicted_questions[:10] if isinstance(predicted_questions, list) else [],
            indent=2,
        ),
    )

    if provider == "openai":
        await client.add_conversation_items(
            conversation_id,
            _build_live_conversation_seed_items(
                resume_structured=resume_structured,
                jd_structured=jd_structured,
                skill_mapping=skill_mapping,
                predicted_questions=predicted_questions if isinstance(predicted_questions, list) else [],
                prepared_answers=prepared_answers,
                context_texts=context_texts,
            ),
        )
        logger.info(
            "Seeded OpenAI conversation for live interview reuse | session_id=%s | conversation_id=%s",
            session_id,
            conversation_id,
        )
    else:
        logger.info(
            "Prepared Anthropic-backed session | session_id=%s | reusable cache anchor comes from the prep dossier",
            session_id,
        )

    # ─── Build session object ────────────────────────
    session = InterviewSession(
        session_id=session_id,
        model=live_model,
        system_prompt=system_prompt,
        resume_text=resume_text,
        resume_structured=resume_structured,
        jd_text=jd_text,
        jd_structured=jd_structured,
        skill_mapping=skill_mapping,
        predicted_questions=predicted_questions if isinstance(predicted_questions, list) else [],
        prepared_answers=prepared_answers,
        context_texts=context_texts,
        conversation_history=[],
        openai_conversation_id=conversation_id,
        openai_prompt_cache_key=prompt_cache_key,
        system_audio_device=system_audio_device,
        speaker_output_device=speaker_output_device,
        mic_device=mic_device,
        status="ready",
    )

    if on_progress:
        await on_progress("Ready!", 100)

    logger.info("Session preparation completed | session_id=%s", session.session_id)
    return session


def _safe_parse_json(text: str) -> dict | list:
    """
    Parse JSON from the model response, handling markdown fences.
    """
    cleaned = text.strip()
    # Remove markdown code fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Model response was not valid JSON; returning raw_text wrapper")
        # If parsing fails, return a dict with the raw text
        return {"raw_text": text, "parse_error": True}
