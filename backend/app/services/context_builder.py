"""
InterviewAce — Context Builder Service
Pre-interview pipeline: parses files, extracts data, builds the master system prompt.

Owner: Dev 1 (Vineeth)
Status: STUB — implement the full pipeline
"""

import json
from pathlib import Path
from typing import Optional, Callable, Awaitable

import anthropic

from ..config import settings
from ..models.session import InterviewSession
from .file_parser import parse_file


# Load prompt templates
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


async def prepare_session(
    resume_path: str,
    jd_text: str,
    context_file_paths: list[str],
    model: str,
    system_audio_device: str,
    mic_device: str,
    on_progress: Optional[Callable[[str, int], Awaitable[None]]] = None,
) -> InterviewSession:
    """
    Run the full pre-interview preparation pipeline.
    
    This is called ONCE before the interview starts. It:
    1. Parses all uploaded files into text
    2. Sends resume to Claude for structured extraction
    3. Sends JD to Claude for requirement analysis
    4. Maps resume skills to JD requirements
    5. Generates predicted interview questions
    6. Builds the master system prompt
    
    Args:
        resume_path: Path to uploaded resume file
        jd_text: Job description text
        context_file_paths: Paths to optional context files
        model: Claude model to use for this session
        system_audio_device: Selected system audio device name
        mic_device: Selected microphone device name
        on_progress: Optional callback for progress updates (step_name, percent)
    
    Returns:
        Fully prepared InterviewSession ready for live use
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # ─── Step 1: Parse files ─────────────────────────
    if on_progress:
        await on_progress("Parsing resume...", 10)

    resume_text = await parse_file(resume_path)

    context_texts = []
    for path in context_file_paths:
        text = await parse_file(path)
        context_texts.append(text)

    # ─── Step 2: Extract structured resume data ──────
    if on_progress:
        await on_progress("Analyzing resume...", 25)

    resume_prompt = _load_prompt("resume_extract.txt").format(resume_text=resume_text)
    resume_response = await client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": resume_prompt}],
    )
    resume_structured = _safe_parse_json(resume_response.content[0].text)

    # ─── Step 3: Analyze JD requirements ─────────────
    if on_progress:
        await on_progress("Analyzing job description...", 40)

    jd_prompt = _load_prompt("jd_analyze.txt").format(jd_text=jd_text)
    jd_response = await client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": jd_prompt}],
    )
    jd_structured = _safe_parse_json(jd_response.content[0].text)

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

    mapping_response = await client.messages.create(
        model=model,
        max_tokens=3000,
        messages=[{"role": "user", "content": mapping_prompt}],
    )
    skill_mapping = _safe_parse_json(mapping_response.content[0].text)

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

    questions_response = await client.messages.create(
        model=model,
        max_tokens=3000,
        messages=[{"role": "user", "content": questions_prompt}],
    )
    predicted_questions = _safe_parse_json(questions_response.content[0].text)

    # ─── Step 6: Build master system prompt ──────────
    if on_progress:
        await on_progress("Building AI context...", 95)

    system_prompt_template = _load_prompt("system_prompt.txt")
    system_prompt = system_prompt_template.format(
        resume_structured=json.dumps(resume_structured, indent=2),
        jd_structured=json.dumps(jd_structured, indent=2),
        skill_mapping=json.dumps(skill_mapping.get("matches", []), indent=2),
        star_stories=json.dumps(skill_mapping.get("star_stories", []), indent=2),
        context_texts="\n---\n".join(context_texts) if context_texts else "No additional context provided.",
        predicted_questions=json.dumps(predicted_questions[:10], indent=2),
    )

    # ─── Build session object ────────────────────────
    session = InterviewSession(
        model=model,
        system_prompt=system_prompt,
        resume_text=resume_text,
        resume_structured=resume_structured,
        jd_text=jd_text,
        jd_structured=jd_structured,
        skill_mapping=skill_mapping,
        predicted_questions=predicted_questions if isinstance(predicted_questions, list) else [],
        context_texts=context_texts,
        conversation_history=[],
        system_audio_device=system_audio_device,
        mic_device=mic_device,
        status="ready",
    )

    if on_progress:
        await on_progress("Ready!", 100)

    return session


def _safe_parse_json(text: str) -> dict | list:
    """
    Parse JSON from Claude's response, handling markdown fences.
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
        # If parsing fails, return a dict with the raw text
        return {"raw_text": text, "parse_error": True}
