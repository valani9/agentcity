"""Self-contained demo of the Plus/Delta Feedback Generator.

Synthetic scenario: a senior-eng agent reviews a junior-eng agent's
refactor of an auth middleware. Default agent-on-agent review would
produce 'LGTM' or 'looks good' — useless for the junior. Plus/Delta
output produces specific behavioral feedback the junior can act on
next time: 'keep doing the spec-first structure', 'change the error-
handling to surface the original exception'.

Run with the stub client (no API key required):

    python demo/01_self_contained_demo.py

Run with a real LLM:

    AGENTCITY_LLM=anthropic python demo/01_self_contained_demo.py
"""

from __future__ import annotations

import json
import os

try:
    from agentcity.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from agentcity.plus_delta import (
        FeedbackRequest,
        PlusDeltaFeedbackGenerator,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_request() -> FeedbackRequest:
    artifact = """
# Refactor of auth middleware

## Module 1: token_validator.py
def validate_token(token: str) -> bool:
    try:
        decode_jwt(token, secret=SECRET, algorithms=["HS256"])
        return True
    except Exception:
        return False

## Module 2: session_loader.py
def load_session(token: str) -> Session:
    if not validate_token(token):
        raise AuthError("Invalid token")
    payload = decode_jwt(token, secret=SECRET, algorithms=["HS256"])
    return Session(user_id=payload["sub"], expires=payload["exp"])

## Module 3: middleware.py
def auth_middleware(request, next_handler):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not token:
        return Response(401, "Missing token")
    try:
        session = load_session(token)
    except AuthError:
        return Response(401, "Invalid session")
    request.session = session
    return next_handler(request)
"""
    return FeedbackRequest(
        feedback_id="auth-refactor-2026-05-22",
        reviewer_agent="senior-eng",
        subject_agent="junior-eng",
        task_context="Refactor the auth middleware for clarity. Junior's first big PR.",
        contribution_summary=(
            "Junior split the auth middleware into 3 modules: token_validator, "
            "session_loader, middleware. Cleaner than the original monolith."
        ),
        contribution_artifact=artifact,
        success_criteria=[
            "Code is readable by a new engineer in <10 minutes",
            "No new dependencies",
            "Tests still pass",
            "Errors surface the underlying cause (not just 'invalid token')",
        ],
        style="balanced",
        max_items_per_category=4,
    )


def stub_response() -> str:
    return json.dumps(
        {
            "plus_items": [
                {
                    "statement": (
                        "Splitting the middleware into validator / session_loader / "
                        "middleware modules gave each function ONE responsibility."
                    ),
                    "evidence": (
                        "Module 1 only validates; Module 2 only loads; Module 3 only routes."
                    ),
                    "impact": (
                        "A new engineer can find the validation logic without reading "
                        "the routing logic. This is the clearest aspect of the PR."
                    ),
                    "keep_doing": (
                        "Always lead with module-level single responsibility on auth code."
                    ),
                },
                {
                    "statement": (
                        "Using removeprefix('Bearer ') correctly handles the optional "
                        "Bearer scheme without manually slicing."
                    ),
                    "evidence": "Module 3 line: token = request.headers.get(...).removeprefix('Bearer ')",
                    "impact": (
                        "Cleaner than the previous implementation's manual string slice "
                        "(which had an off-by-one bug)."
                    ),
                    "keep_doing": "Prefer stdlib string methods over manual indexing.",
                },
            ],
            "delta_items": [
                {
                    "statement": (
                        "validate_token swallows the underlying exception, so errors "
                        "lose information that would help debug."
                    ),
                    "evidence": (
                        "Module 1: except Exception: return False. The original "
                        "decode_jwt error (token expired vs signature wrong vs malformed) "
                        "is lost."
                    ),
                    "impact": (
                        "Violates success criterion #4 (errors surface underlying cause). "
                        "When tokens fail in prod, ops can't tell if it's expiration vs "
                        "signature vs malformed payload."
                    ),
                    "alternative": (
                        "Catch jwt.ExpiredSignatureError, jwt.InvalidSignatureError, "
                        "jwt.DecodeError separately and raise typed AuthError subclasses "
                        "carrying the underlying cause."
                    ),
                    "severity": "critical",
                },
                {
                    "statement": (
                        "load_session calls decode_jwt twice — once in validate_token, "
                        "once directly — doubling the work and risking divergence."
                    ),
                    "evidence": (
                        "Module 2 calls validate_token() (which decodes) then calls "
                        "decode_jwt() again."
                    ),
                    "impact": (
                        "Performance hit on every authenticated request; risk that future "
                        "edits to one call diverge from the other."
                    ),
                    "alternative": (
                        "Have validate_token return the decoded payload (or None on "
                        "failure); load_session uses the returned payload directly."
                    ),
                    "severity": "moderate",
                },
                {
                    "statement": (
                        "Module 3 doesn't handle the case where 'Authorization' header "
                        "exists but is empty (e.g. 'Authorization: ')."
                    ),
                    "evidence": (
                        "request.headers.get('Authorization', '').removeprefix('Bearer ') "
                        "produces an empty string for both missing-header and empty-header "
                        "cases."
                    ),
                    "impact": (
                        "Edge case: empty Authorization header bypasses the 'missing token' "
                        "branch and gets to validate_token, which then returns False. "
                        "Final behavior is correct but the path is wasteful."
                    ),
                    "alternative": (
                        "After removeprefix, also strip whitespace and check 'if not "
                        "token.strip()'."
                    ),
                    "severity": "nit",
                },
            ],
            "commitments": [
                {
                    "by_agent": "junior-eng",
                    "commitment": (
                        "Next round: rewrite validate_token to return Payload | None and "
                        "add typed AuthError subclasses."
                    ),
                },
                {
                    "by_agent": "senior-eng",
                    "commitment": "Will pair on the typed AuthError pattern.",
                },
            ],
            "overall_assessment": "iterate",
            "feedback_quality_score": 0.85,
        }
    )


def pick_client() -> object:
    choice = os.environ.get("AGENTCITY_LLM", "stub").lower()
    if choice == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if choice == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if choice == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient([stub_response()])


def main() -> None:
    request = build_request()
    client = pick_client()
    generator = PlusDeltaFeedbackGenerator(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    feedback = generator.run(request)
    print(feedback.to_markdown())
    print("\n\n--- Inline form (for chat returns) ---\n")
    print(feedback.to_inline_feedback())


if __name__ == "__main__":
    main()
