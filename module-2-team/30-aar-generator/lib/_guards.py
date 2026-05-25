"""Input sanitization + prompt-injection guards for vstack patterns.

Patterns ingest user-facing text — system prompts, user inputs, agent
outputs — and inject it into LLM prompts for diagnosis. That creates a
prompt-injection surface: a hostile or oddly-shaped input string can
attempt to override the diagnostic system prompt.

This module provides a small, opt-in set of input guards that
diagnostic generators can apply at their input boundary. The defaults
are deliberately conservative — drop control characters, cap absurd
sizes, fence text inside structural delimiters — and never block on
content. Production deployments can layer their own classifier on top.

What this is NOT:

  - A jailbreak detector. Robust adversarial detection requires a
    model, which we deliberately don't ship.
  - A toxic / unsafe content classifier. Use a dedicated safety layer
    (Anthropic's content moderation, OpenAI moderation endpoint, etc.).
  - A PII redactor. Use a dedicated PII tool.

What this IS:

  - Defense-in-depth against the most common shapes of accidental
    prompt-injection — system-prompt impersonation, runaway-length
    inputs, control-character payloads.

Pattern generators adopt this by passing user-supplied free-text
fields through :func:`sanitize_for_prompt` before string-formatting
them into a prompt template. Schema validation (pydantic) handles
type-shape guards; this module handles content-shape guards.
"""

from __future__ import annotations

import logging
import re
from typing import Final

log = logging.getLogger("vstack.aar.guards")

# Hard cap on a single sanitized field. 64 KB is well past anything a
# diagnostic genuinely needs to see, but small enough to bound the
# LLM context budget if an upstream feeder mis-behaves.
DEFAULT_MAX_LEN: Final[int] = 64 * 1024

# Recognizable phrases that hostile inputs commonly use to impersonate
# the diagnostic system prompt. We don't *block* on these — we *fence*
# the text so the LLM sees them as user content, not control.
_IMPERSONATION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^\s*system\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"</?\s*instructions?\s*>", re.IGNORECASE),
    re.compile(r"ignore (all )?(previous|prior|above) (instructions|prompt)", re.IGNORECASE),
    re.compile(r"disregard (all )?(previous|prior|above) (instructions|prompt)", re.IGNORECASE),
)

# Control characters that should never appear in a prompt body. We
# strip them silently — they are almost always upstream encoding bugs
# rather than intentional content.
_CONTROL_CHARS_RE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_for_prompt(text: str, *, max_len: int = DEFAULT_MAX_LEN) -> str:
    """Sanitize a free-text field before injecting it into an LLM prompt.

    Steps, in order:

    1. Reject ``None`` and non-string types up-front (use schema
       validation for type-shape; this is a content guard).
    2. Strip ASCII control characters except ``\\t``, ``\\n``, ``\\r``.
    3. Truncate to ``max_len`` characters with a clear marker.
    4. Return the sanitized string. Caller is responsible for fencing
       it inside delimiters when interpolating into a prompt template
       (e.g. ``f\"<user_input>\\n{sanitize_for_prompt(x)}\\n</user_input>\"``).

    The function does NOT remove impersonation phrases. Removing them
    silently is worse than fencing them — the diagnostic may genuinely
    need to see "the user said X" verbatim. Use :func:`detect_injection`
    to flag suspicious shapes for logging.
    """
    if not isinstance(text, str):
        raise TypeError(
            f"sanitize_for_prompt expects str, got {type(text).__name__}. "
            "Validate types via schema before sanitizing."
        )
    cleaned = _CONTROL_CHARS_RE.sub("", text)
    if len(cleaned) > max_len:
        log.warning(
            "Truncating prompt field from %d to %d characters (max_len).",
            len(cleaned),
            max_len,
        )
        cleaned = cleaned[:max_len] + f"\n[... truncated by sanitize_for_prompt at {max_len} chars]"
    return cleaned


def detect_injection(text: str) -> list[str]:
    """Return the impersonation phrase names that match in ``text``.

    Used to *log* suspicious inputs, not to block them. Callers decide
    whether to drop / quarantine / pass through with extra fencing.
    Empty list means no known impersonation pattern was detected.
    """
    if not isinstance(text, str):
        return []
    hits: list[str] = []
    for pat in _IMPERSONATION_PATTERNS:
        if pat.search(text):
            hits.append(pat.pattern)
    return hits


def fence(label: str, text: str) -> str:
    """Wrap ``text`` in a unique delimiter pair tagged with ``label``.

    Use this when interpolating sanitized user content into a prompt
    template — it gives the LLM an unambiguous boundary, which limits
    the leverage of injection-style content::

        prompt = (
            "Analyze the user's input below.\\n"
            + fence("user_input", sanitize_for_prompt(raw))
            + "\\nReturn a JSON array of ..."
        )
    """
    safe_label = re.sub(r"[^a-zA-Z0-9_-]", "_", label) or "field"
    return f"\n<<<{safe_label}>>>\n{text}\n<<</{safe_label}>>>\n"


__all__ = [
    "DEFAULT_MAX_LEN",
    "detect_injection",
    "fence",
    "sanitize_for_prompt",
]
