from __future__ import annotations

import os
import re
from typing import List
import json
from typing import Any
from ollama import chat
from dotenv import load_dotenv

load_dotenv()

BULLET_PREFIX_PATTERN = re.compile(r"^\s*([-*•]|\d+\.)\s+")
KEYWORD_PREFIXES = (
    "todo:",
    "action:",
    "next:",
)


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


def extract_action_items_llm(text: str) -> List[str]:
    """
    Extract action items from text using an LLM (Ollama with mistral-nemo:12b).
    
    This function sends the text to a language model for intelligent action item
    extraction, which can better understand context and implicit action items.
    
    Args:
        text: The input text to extract action items from.
        
    Returns:
        A list of action items extracted by the LLM.
    """
    # Handle empty or whitespace-only input
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

    try:
        response = chat(
            model="mistral-nemo:12b",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            options={"temperature": 0},
        )
        
        # Extract the message content from the response
        response_text = response.get("message", {}).get("content", "").strip()
        
        # Parse the JSON array from the response
        try:
            action_items = json.loads(response_text)
            
            # Ensure it's a list of strings and deduplicate
            if isinstance(action_items, list):
                seen: set[str] = set()
                unique: List[str] = []
                for item in action_items:
                    item_str = str(item).strip()
                    lowered = item_str.lower()
                    if lowered not in seen:
                        seen.add(lowered)
                        unique.append(item_str)
                return unique
        except (json.JSONDecodeError, ValueError):
            # If JSON parsing fails, fallback to line-by-line splitting
            lines = [line.strip() for line in response_text.split('\n') if line.strip()]
            # Remove any markdown list formatting
            cleaned: List[str] = []
            for line in lines:
                cleaned_line = BULLET_PREFIX_PATTERN.sub("", line).strip()
                if cleaned_line:
                    cleaned.append(cleaned_line)
            return cleaned
    
    except Exception as e:
        # If LLM call fails, return empty list
        print(f"Error calling LLM: {e}")
        return []
    
    return []
