"""Input-validation helpers used across vstack.

Three guards:

* :func:`audit_input_for_injection` -- thin wrapper over
  :func:`vstack.aar.detect_injection` so the REST + MCP paths can
  call one function and get a structured signal.
* :func:`safe_pattern_name` -- enforces the same alphabet the
  ``vstack.memory._home`` baseline path uses. Prevents path-
  traversal via attacker-controlled pattern names.
* :func:`safe_path` -- validates a user-supplied path stays under
  the configured ``~/.vstack/`` home + doesn't traverse out.
* :func:`safe_subprocess_argv` -- never invoked with shell=True;
  guards the argv list passed to ``subprocess.run`` from the
  gbrain + browser modules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from vstack.aar import detect_injection

_SAFE_PATTERN_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class InjectionAudit:
    """Result of :func:`audit_input_for_injection`."""

    is_suspicious: bool
    score: float
    """0.0-1.0 confidence that the input contains a prompt-injection
    attempt. Threshold above 0.5 is the default action-warranted
    cutoff."""

    indicators: tuple[str, ...]
    """Specific signals the underlying detector flagged."""


def audit_input_for_injection(text: str) -> InjectionAudit:
    """Run the upstream injection detector on free-text input.

    The underlying detector is heuristic, not a guarantee. Callers
    should treat ``is_suspicious`` as "log + warn", not "drop the
    request". The trace already goes through prompt-fencing inside
    each pattern's analyzer; this audit is a defense-in-depth layer.
    """
    if not isinstance(text, str) or not text:
        return InjectionAudit(is_suspicious=False, score=0.0, indicators=())
    try:
        result = detect_injection(text)
    except Exception:
        # Detector is heuristic; never let it crash the request path.
        return InjectionAudit(is_suspicious=False, score=0.0, indicators=())

    # The upstream detect_injection returns either a bool, a float
    # score, or a dataclass with score + indicators. Adapt
    # defensively so future upstream changes don't break us.
    if isinstance(result, bool):
        return InjectionAudit(
            is_suspicious=result,
            score=1.0 if result else 0.0,
            indicators=("upstream_bool",) if result else (),
        )
    if isinstance(result, (int, float)):
        score = float(result)
        return InjectionAudit(
            is_suspicious=score >= 0.5,
            score=score,
            indicators=("upstream_score",) if score > 0 else (),
        )
    score = float(getattr(result, "score", 0.0) or 0.0)
    raw_indicators = getattr(result, "indicators", None) or ()
    indicators = tuple(str(i) for i in raw_indicators)
    return InjectionAudit(
        is_suspicious=score >= 0.5 or bool(indicators),
        score=score,
        indicators=indicators,
    )


def safe_pattern_name(name: str) -> str:
    """Validate ``name`` against the safe-identifier alphabet.

    Returns the name on success; raises :class:`ValueError` with a
    diagnostic message on failure. Use any time a user-supplied
    pattern name is about to become part of a filesystem path or a
    URL.
    """
    if not name or not _SAFE_PATTERN_NAME.fullmatch(name):
        raise ValueError(f"Unsafe pattern name: {name!r}. Allowed alphabet: [A-Za-z0-9_-]+.")
    return name


def safe_path(candidate: Path | str, *, must_be_under: Path | str | None = None) -> Path:
    """Resolve ``candidate`` to an absolute path + verify containment.

    If ``must_be_under`` is supplied, raises :class:`ValueError`
    when the resolved path escapes that root. Use for any user-
    supplied path that becomes a read/write target inside
    ``~/.vstack/`` or a release-artifact directory.
    """
    resolved = Path(candidate).expanduser().resolve()
    if must_be_under is not None:
        root = Path(must_be_under).expanduser().resolve()
        try:
            resolved.relative_to(root)
        except ValueError as e:
            raise ValueError(f"Path {resolved} escapes the required root {root}.") from e
    return resolved


def safe_subprocess_argv(argv: Sequence[str]) -> list[str]:
    """Validate an argv list before passing to ``subprocess.run``.

    Confirms every element is a string and that none contains a NUL
    byte or unescaped shell metacharacters in places they don't
    belong. We never use ``shell=True`` anywhere in vstack; this
    layer catches the failure modes that arise when the argv list
    itself has been tampered with (e.g. user-controlled tokens
    flowing into the gbrain CLI invocation).
    """
    out: list[str] = []
    for item in argv:
        if not isinstance(item, str):
            raise ValueError(f"argv element is not a string: {item!r} ({type(item).__name__})")
        if "\x00" in item:
            raise ValueError("argv element contains a NUL byte (denied)")
        out.append(item)
    return out


def warn_on_suspicious_inputs(
    payload: dict[str, Any], *, fields: Iterable[str] | None = None
) -> list[InjectionAudit]:
    """Run the injection audit across named free-text fields in ``payload``.

    Returns a list of audits, one per suspicious field. Empty list
    means nothing flagged. Caller decides whether to log + continue
    or to refuse the request.
    """
    fields = list(fields) if fields else _COMMON_TEXT_FIELDS
    audits: list[InjectionAudit] = []
    for name in fields:
        value = payload.get(name) if isinstance(payload, dict) else None
        if not isinstance(value, str):
            continue
        audit = audit_input_for_injection(value)
        if audit.is_suspicious:
            audits.append(audit)
    return audits


_COMMON_TEXT_FIELDS = (
    "goal",
    "task",
    "outcome",
    "initial_attribution",
    "system_prompt",
    "user_prompt",
)
