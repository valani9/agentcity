"""
Robust JSON-array parsing for LLM responses.

LLMs return JSON imperfectly: sometimes wrapped in markdown fences,
sometimes with trailing commentary, sometimes truncated. This module
extracts JSON arrays from messy responses without trusting the LLM
to be well-behaved.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

log = logging.getLogger("vstack.aar.json")


_FENCE_RE = re.compile(
    r"```(?:json)?\s*(.*?)\s*```",
    re.DOTALL | re.IGNORECASE,
)


def extract_json_array(text: str) -> list[dict[str, Any]]:
    """Pull a JSON array of objects out of an LLM response.

    Tries in order:
      1. Treat the whole string as JSON.
      2. If the string contains a markdown ```json fence, parse the
         contents of the first fence.
      3. Find the first `[` and the matching last `]`, parse the slice.

    On any failure, logs at WARNING and returns an empty list. Callers
    should not raise on empty parse; they should let the caller decide.
    """
    candidates: list[str] = []

    text = text.strip()
    if text:
        candidates.append(text)

    for match in _FENCE_RE.finditer(text):
        body = match.group(1).strip()
        if body:
            candidates.append(body)

    start = text.find("[")
    end = text.rfind("]")
    if 0 <= start < end:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        # Permit the LLM returning a single object when the prompt asked
        # for an array — wrap it.
        if isinstance(value, dict):
            return [value]

    log.warning(
        "Failed to parse JSON array from LLM response (len=%d). "
        "Returning empty list; downstream caller decides whether to retry.",
        len(text),
    )
    return []
