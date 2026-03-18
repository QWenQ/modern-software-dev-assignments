from __future__ import annotations

from dataclasses import dataclass
import logging
import re
import json
from typing import Any, List

BULLET_PREFIX_PATTERN = re.compile(r"^\s*([-*•]|\d+\.)\s+")
KEYWORD_PREFIXES = (
    "todo:",
    "action:",
    "next:",
)
JSON_ARRAY_PATTERN = re.compile(r"\[[\s\S]*\]")


logger = logging.getLogger(__name__)


class ExtractionServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExtractionResult:
    items: list[str]
    extractor: str


def _is_action_line(line: str) -> bool:
    stripped = line.strip().lower()
    if not stripped:
        return False
    if BULLET_PREFIX_PATTERN.match(stripped):
        return True
    if any(stripped.startswith(prefix) for prefix in KEYWORD_PREFIXES):
        return True
    if "[ ]" in stripped or "[todo]" in stripped:
        return True
    return False


def extract_action_items(text: str) -> List[str]:
    lines = text.splitlines()
    extracted: List[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if _is_action_line(line):
            cleaned = BULLET_PREFIX_PATTERN.sub("", line)
            cleaned = cleaned.strip()
            # Trim common checkbox markers
            cleaned = cleaned.removeprefix("[ ]").strip()
            cleaned = cleaned.removeprefix("[todo]").strip()
            extracted.append(cleaned)
    # Fallback: if nothing matched, heuristically split into sentences and pick imperative-like ones
    if not extracted:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for sentence in sentences:
            s = sentence.strip()
            if not s:
                continue
            if _looks_imperative(s):
                extracted.append(s)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: List[str] = []
    for item in extracted:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(item)
    return unique


def _looks_imperative(sentence: str) -> bool:
    words = re.findall(r"[A-Za-z']+", sentence)
    if not words:
        return False
    first = words[0]
    # Crude heuristic: treat these as imperative starters
    imperative_starters = {
        "add",
        "create",
        "implement",
        "fix",
        "update",
        "write",
        "check",
        "verify",
        "refactor",
        "document",
        "design",
        "investigate",
    }
    return first.lower() in imperative_starters


def _normalize_action_items(items: list[Any]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for raw_item in items:
        item = str(raw_item).strip()
        if not item:
            continue
        cleaned = BULLET_PREFIX_PATTERN.sub("", item).strip()
        cleaned = cleaned.removeprefix("[ ]").strip()
        cleaned = cleaned.removeprefix("[todo]").strip()
        lowered = cleaned.lower()
        if not cleaned or lowered in seen:
            continue
        seen.add(lowered)
        unique.append(cleaned)
    return unique


def _parse_action_items_response(response_text: str) -> list[str]:
    if not response_text:
        return []

    candidate = response_text.strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        match = JSON_ARRAY_PATTERN.search(candidate)
        if match is not None:
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                parsed = None
        else:
            parsed = None

    if isinstance(parsed, list):
        return _normalize_action_items(parsed)

    lines = [line.strip() for line in candidate.splitlines() if line.strip()]
    return _normalize_action_items(lines)


def _call_ollama(prompt: str, model_name: str) -> str:
    try:
        from ollama import chat
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise ExtractionServiceError("Ollama client is not installed") from exc

    try:
        response = chat(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            options={"temperature": 0},
        )
    except Exception as exc:  # pragma: no cover - depends on local environment
        raise ExtractionServiceError("Failed to call Ollama") from exc

    if isinstance(response, dict):
        content = response.get("message", {}).get("content", "")
        if content is None:
            return ""
        return str(content).strip()

    message = getattr(response, "message", None)
    content = getattr(message, "content", "")
    if content is None:
        return ""
    return str(content).strip()


def _extract_action_items_llm(text: str, model_name: str) -> list[str]:
    if not text or not text.strip():
        return []

    prompt = f"""You are an expert at extracting action items from text.
Extract all action items (tasks that need to be done) from the following text.
Return the results as a valid JSON array of strings.
If there are no action items, return an empty array: []

Text:
{text}

Return ONLY a valid JSON array like: ["action1", "action2", "action3"]
Do not include any explanation or additional text."""

    response_text = _call_ollama(prompt, model_name)
    return _parse_action_items_response(response_text)


def extract_action_items_llm(
    text: str, model_name: str = "mistral-nemo:12b"
) -> List[str]:
    try:
        return _extract_action_items_llm(text, model_name=model_name)
    except ExtractionServiceError as exc:
        logger.warning(
            "Falling back to heuristic extraction after LLM failure: %s",
            exc,
        )
        return extract_action_items(text)


class ActionItemExtractor:
    def __init__(self, model_name: str, allow_fallback: bool = True) -> None:
        self.model_name = model_name
        self.allow_fallback = allow_fallback

    def extract(self, text: str) -> ExtractionResult:
        try:
            items = _extract_action_items_llm(text, model_name=self.model_name)
            return ExtractionResult(items=items, extractor="llm")
        except ExtractionServiceError as exc:
            if not self.allow_fallback:
                raise
            logger.warning(
                "Falling back to heuristic extraction after LLM failure: %s",
                exc,
            )
            items = extract_action_items(text)
            return ExtractionResult(items=items, extractor="heuristic")
