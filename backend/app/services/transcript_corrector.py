"""
InterviewAce — Transcript Corrector
Lightweight post-processing for Whisper output using session-specific vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from ..models.session import InterviewSession

COMMON_WORDS = {
    "a", "about", "after", "all", "also", "an", "and", "any", "are", "as", "at",
    "be", "because", "but", "by", "can", "company", "data", "did", "do", "for",
    "from", "get", "give", "go", "good", "have", "how", "i", "if", "in", "into",
    "is", "it", "its", "just", "like", "me", "more", "my", "of", "on", "or",
    "our", "role", "so", "some", "tell", "that", "the", "their", "them", "there",
    "they", "this", "time", "to", "use", "used", "using", "want", "was", "we",
    "what", "when", "where", "which", "with", "work", "worked", "working", "would",
    "you", "your",
}

TECH_ALIASES = {
    "javascript": ["java script"],
    "typescript": ["type script"],
    "postgresql": ["postgres", "postgre sql", "postgressql", "postgress"],
    "mysql": ["my sql", "mysequel"],
    "mongodb": ["mongo db", "mongo d b"],
    "springboot": ["spring boot"],
    "restapi": ["rest api", "restful api"],
    "microservices": ["micro services"],
    "kubernetes": ["kuber netes", "kubernetties", "cubeernetes"],
    "jenkins": ["genkins", "jenkin"],
    "jira": ["jeera", "gira"],
    "hibernate": ["hybernate", "highbernate"],
    "jwt": ["j w t", "jay double u tee"],
    "cicd": ["ci cd", "c i c d"],
    "devops": ["dev ops"],
    "qlora": ["q lora", "cue lora"],
    "llama": ["lama"],
    "reactjs": ["react js"],
    "nodejs": ["node js"],
    "dotnet": [". net", "dot net"],
    "bfs": ["b f s", "breadth first"],
    "dfs": ["d f s", "depth first"],
    "btree": ["b tree", "bee tree"],
    "binarytree": ["binary tree"],
    "adjacencylist": ["adjacency list", "agency list", "adjacent list"],
    "hashmap": ["hash map"],
    "hashset": ["hash set"],
    "linkedlist": ["linked list"],
    "arraylist": ["array list"],
    "priorityqueue": ["priority queue"],
    "arraydeque": ["array deque"],
    "concurrenthashmap": ["concurrent hash map"],
    "oop": ["o o p", "oops", "oops concept"],
    "encapsulation": ["in capsulation", "encap sulation"],
    "inheritance": ["in heritance"],
    "polymorphism": ["poly morphism"],
    "abstraction": ["abstract shun"],
    "constructor": ["constructer", "constructors"],
}

INTERVIEW_TERMS = {
    "OOP",
    "Encapsulation",
    "Inheritance",
    "Polymorphism",
    "Abstraction",
    "Constructor",
    "Adjacency List",
    "Hash Map",
    "Hash Set",
    "Linked List",
    "ArrayList",
    "Queue",
    "Stack",
    "Graph",
    "Binary Tree",
    "REST API",
    "Microservices",
}


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
    normalized: str
    token_count: int
    specific: bool


class TranscriptCorrector:
    """
    Correct likely transcription mistakes with session-grounded terminology.

    The goal is not to rewrite all text. It only nudges likely misheard
    skills, company names, tools, and branded phrases toward known
    resume/JD/context vocabulary.
    """

    def __init__(self, session: InterviewSession):
        self.entries_by_len: dict[int, list[GlossaryEntry]] = {1: [], 2: [], 3: [], 4: []}
        self.entries_by_normalized: dict[str, GlossaryEntry] = {}
        self._build_glossary(session)

    def correct(self, text: str) -> str:
        if not text or not self.entries_by_normalized:
            return text.strip()

        words = re.findall(r"[A-Za-z0-9+#./'-]+", text)
        if not words:
            return text.strip()

        corrected: list[str] = []
        index = 0
        while index < len(words):
            replacement = self._find_best_replacement(words, index)
            if replacement is None:
                corrected.append(words[index])
                index += 1
                continue

            token_count, entry = replacement
            corrected.extend(entry.term.split())
            index += token_count

        return " ".join(corrected).strip()

    def _find_best_replacement(self, words: list[str], index: int) -> tuple[int, GlossaryEntry] | None:
        max_len = min(4, len(words) - index)

        for token_count in range(max_len, 0, -1):
            heard_phrase = " ".join(words[index:index + token_count]).strip()
            normalized_heard = self._normalize(heard_phrase)
            if not normalized_heard:
                continue

            exact = self.entries_by_normalized.get(normalized_heard)
            if exact and exact.token_count == token_count:
                return token_count, exact

            best_match: GlossaryEntry | None = None
            best_score = 0.0
            for entry in self.entries_by_len.get(token_count, []):
                if not self._is_length_compatible(normalized_heard, entry.normalized):
                    continue

                score = SequenceMatcher(None, normalized_heard, entry.normalized).ratio()
                if score > best_score:
                    best_score = score
                    best_match = entry

            if best_match and self._should_replace(normalized_heard, best_match, best_score):
                return token_count, best_match

        return None

    def _should_replace(self, normalized_heard: str, entry: GlossaryEntry, score: float) -> bool:
        if normalized_heard == entry.normalized:
            return True

        if entry.token_count == 1:
            if normalized_heard in COMMON_WORDS:
                return False
            return entry.specific and score >= 0.90

        threshold = 0.84 if entry.specific else 0.90
        return score >= threshold

    def _is_length_compatible(self, heard: str, candidate: str) -> bool:
        return abs(len(heard) - len(candidate)) <= max(2, int(len(candidate) * 0.45))

    def _build_glossary(self, session: InterviewSession) -> None:
        raw_terms: set[str] = set()

        resume = session.resume_structured if isinstance(session.resume_structured, dict) else {}
        jd = session.jd_structured if isinstance(session.jd_structured, dict) else {}

        for role in resume.get("roles", []) if isinstance(resume.get("roles"), list) else []:
            if isinstance(role, dict):
                raw_terms.update(self._safe_values(role, "title", "company", "location"))

        for project in resume.get("projects", []) if isinstance(resume.get("projects"), list) else []:
            if isinstance(project, dict):
                raw_terms.update(self._safe_values(project, "name"))
                skills_used = project.get("skills_used", [])
                if isinstance(skills_used, list):
                    raw_terms.update(str(item).strip() for item in skills_used if str(item).strip())

        skills = resume.get("skills", {}) if isinstance(resume.get("skills"), dict) else {}
        for key in ("technical", "tools"):
            values = skills.get(key, [])
            if isinstance(values, list):
                raw_terms.update(str(item).strip() for item in values if str(item).strip())

        raw_terms.update(self._safe_values(jd, "title", "company"))
        raw_terms.update(INTERVIEW_TERMS)
        required_skills = jd.get("required_skills", [])
        if isinstance(required_skills, list):
            for item in required_skills:
                if isinstance(item, dict):
                    skill = str(item.get("skill", "")).strip()
                    if skill:
                        raw_terms.add(skill)
                else:
                    value = str(item).strip()
                    if value:
                        raw_terms.add(value)

        for text in [session.resume_text, session.jd_text, *session.context_texts]:
            raw_terms.update(self._extract_terms_from_text(text))

        for term in raw_terms:
            cleaned = " ".join(str(term).split()).strip()
            normalized = self._normalize(cleaned)
            token_count = len(cleaned.split())
            if not cleaned or not normalized or token_count < 1 or token_count > 4:
                continue
            if normalized in COMMON_WORDS:
                continue

            canonical_entry = GlossaryEntry(
                term=cleaned,
                normalized=normalized,
                token_count=token_count,
                specific=self._is_specific_term(cleaned),
            )
            self._register_entry(canonical_entry)

            for alias in self._alias_terms(cleaned):
                alias_cleaned = " ".join(alias.split()).strip()
                alias_normalized = self._normalize(alias_cleaned)
                alias_token_count = len(alias_cleaned.split())
                if (
                    not alias_cleaned
                    or not alias_normalized
                    or alias_normalized == normalized
                    or alias_token_count < 1
                    or alias_token_count > 4
                ):
                    continue

                alias_entry = GlossaryEntry(
                    term=cleaned,
                    normalized=alias_normalized,
                    token_count=alias_token_count,
                    specific=True,
                )
                self._register_entry(alias_entry)

        self.entries_by_len = {1: [], 2: [], 3: [], 4: []}
        for entry in self.entries_by_normalized.values():
            self.entries_by_len.setdefault(entry.token_count, []).append(entry)

    def _register_entry(self, entry: GlossaryEntry) -> None:
        existing = self.entries_by_normalized.get(entry.normalized)
        if existing and len(existing.term) >= len(entry.term):
            return
        self.entries_by_normalized[entry.normalized] = entry

    def _alias_terms(self, term: str) -> set[str]:
        aliases = set()
        normalized = self._normalize(term)

        static_aliases = TECH_ALIASES.get(normalized, [])
        aliases.update(static_aliases)

        spaced_camel = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", term).strip()
        if spaced_camel != term:
            aliases.add(spaced_camel)

        compact = term.replace("/", " ").replace("-", " ")
        if compact != term:
            aliases.add(compact)

        if term.isupper() and len(term) <= 6:
            aliases.add(" ".join(term))

        return {alias for alias in aliases if alias.strip()}

    def _extract_terms_from_text(self, text: str) -> set[str]:
        if not isinstance(text, str) or not text.strip():
            return set()

        extracted: set[str] = set()

        branded_pattern = re.compile(
            r"\b(?:[A-Z][A-Za-z0-9+#./-]*|[A-Z]{2,}[A-Za-z0-9+#./-]*)(?:\s+(?:[A-Z][A-Za-z0-9+#./-]*|[A-Z]{2,}[A-Za-z0-9+#./-]*)){0,3}\b"
        )
        tech_pattern = re.compile(r"\b[A-Za-z][A-Za-z0-9+#./-]{2,}\b")

        for match in branded_pattern.findall(text):
            cleaned = " ".join(match.split()).strip()
            if cleaned:
                extracted.add(cleaned)

        for match in tech_pattern.findall(text):
            if self._is_specific_term(match):
                extracted.add(match.strip())

        return extracted

    def _safe_values(self, data: dict, *keys: str) -> set[str]:
        values = set()
        for key in keys:
            value = str(data.get(key, "")).strip()
            if value:
                values.add(value)
        return values

    def _is_specific_term(self, term: str) -> bool:
        stripped = term.strip()
        if not stripped:
            return False

        if any(char.isdigit() for char in stripped):
            return True
        if any(char in "+#./-" for char in stripped):
            return True
        if any(char.isupper() for char in stripped[1:]):
            return True

        words = stripped.split()
        if len(words) > 1:
            return True

        lowered = stripped.lower()
        return len(lowered) >= 5 and lowered not in COMMON_WORDS

    def _normalize(self, value: str) -> str:
        lowered = value.lower().strip()
        return re.sub(r"[^a-z0-9]+", "", lowered)

    def transcription_hints(self, limit: int = 36) -> list[str]:
        unique_terms: list[str] = []
        seen: set[str] = set()
        ranked_entries = sorted(
            self.entries_by_normalized.values(),
            key=lambda entry: (
                entry.specific,
                entry.token_count,
                len(entry.term),
            ),
            reverse=True,
        )

        for entry in ranked_entries:
            canonical = entry.term.strip()
            normalized = self._normalize(canonical)
            if not canonical or normalized in seen:
                continue
            seen.add(normalized)
            unique_terms.append(canonical)
            if len(unique_terms) >= limit:
                break

        return unique_terms
