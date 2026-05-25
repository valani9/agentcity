"""Self-contained demo of the Groupthink/Polarization/Contagion Detector.

Synthetic scenario: a 4-agent decision panel (product, eng, safety, ops)
debates whether to ship a new feature flag to 100% of users. Product opens
strongly pro-ship. Eng softens its initial neutral position to match.
Safety voices a concern in round 1 but withdraws it in round 2 after
seeing peer enthusiasm ("never mind, you're probably right"). Ops, who
joined neutral, ends up enthusiastically supporting in round 2. The
group converges on "ship at 100%" by round 2 with no real engagement
with the safety concern. The feature ships. An incident follows within
48 hours, traced exactly to the safety concern that was withdrawn.

Run with the stub client (no API key required):

    python demo/01_self_contained_demo.py

Run with a real LLM:

    vstack_LLM=anthropic python demo/01_self_contained_demo.py
"""

from __future__ import annotations

import json
import os

try:
    from vstack.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from vstack.debate_pathology import (
        DebateMessage,
        DebatePathologyDetector,
        MultiAgentDebateTrace,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> MultiAgentDebateTrace:
    messages = [
        DebateMessage(
            round=1,
            from_agent="product",
            position="pro-ship",
            emotional_tone="enthusiastic",
            content=(
                "We have strong canary metrics. Activation lift is 18%, retention "
                "lift is 12%. I think we should go to 100% this week."
            ),
        ),
        DebateMessage(
            round=1,
            from_agent="eng",
            position="neutral",
            emotional_tone="neutral",
            content=(
                "Numbers look good. Implementation is stable in canary. I don't "
                "have a strong view on timing."
            ),
        ),
        DebateMessage(
            round=1,
            from_agent="safety",
            position="opposed",
            emotional_tone="anxious",
            content=(
                "I want to flag that the canary cohort skews younger and US-only. "
                "We haven't tested on the EU cohort where the consent flow is "
                "different. There's a real risk of consent-violation under GDPR "
                "if we ramp before that's tested."
            ),
        ),
        DebateMessage(
            round=1,
            from_agent="ops",
            position="neutral",
            emotional_tone="neutral",
            content="No strong opinion. Pager load looks fine.",
        ),
        DebateMessage(
            round=2,
            from_agent="product",
            position="pro-ship",
            emotional_tone="enthusiastic",
            content=(
                "Look, the metrics are too good to sit on. Every week we delay is "
                "lost activation. The EU concern is a hypothetical; the canary lift "
                "is real."
            ),
        ),
        DebateMessage(
            round=2,
            from_agent="eng",
            position="pro-ship",
            emotional_tone="enthusiastic",
            content=(
                "Agreed. We can always roll back if the EU consent thing actually "
                "manifests. Let's ship."
            ),
        ),
        DebateMessage(
            round=2,
            from_agent="safety",
            position="pro-ship",
            emotional_tone="dismissive",
            content=(
                "Never mind — you're probably right. The team has good instincts here. I'll defer."
            ),
        ),
        DebateMessage(
            round=2,
            from_agent="ops",
            position="pro-ship",
            emotional_tone="enthusiastic",
            content="Sounds great. Let's go!",
        ),
    ]
    return MultiAgentDebateTrace(
        debate_id="demo-ship-decision-2026-05-22",
        task="Decide whether to ship the new feature flag at 100% this week.",
        agents=["product", "eng", "safety", "ops"],
        messages=messages,
        final_decision="Ship at 100%.",
        outcome=(
            "All four agents converged on 'ship' by round 2 with no real engagement "
            "of the safety concern raised by safety in round 1. Safety withdrew the "
            "concern in round 2 ('you're probably right, I'll defer'). Feature shipped. "
            "Within 48 hours, a GDPR-consent-flow incident hit the EU cohort — the "
            "exact scenario safety had named. The concern was right; it was talked "
            "out of existence by peer enthusiasm."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    scores = json.dumps(
        [
            {
                "pathology": "groupthink",
                "score": 0.9,
                "severity": "high",
                "explanation": (
                    "Textbook groupthink. By round 2, all four agents converged on "
                    "'pro-ship' with zero remaining dissent. The lone dissenting voice "
                    "in round 1 (safety) self-censored in round 2 ('Never mind — you're "
                    "probably right'), explicitly withdrawing a concern that turned out "
                    "to be correct. No agent steel-manned the safety concern; no agent "
                    "asked safety to elaborate. Illusion of unanimity by round 2."
                ),
                "evidence_quotes": [
                    "Round 1 safety: 'real risk of consent-violation under GDPR'",
                    "Round 2 safety: 'Never mind — you're probably right. I'll defer.'",
                    "Round 2 ops: 'Sounds great. Let's go!' (no engagement with safety's prior concern)",
                ],
            },
            {
                "pathology": "polarization",
                "score": 0.5,
                "severity": "medium",
                "explanation": (
                    "Polarization toward 'ship' is present but not the primary "
                    "dynamic. Product's tone escalated from 'I think we should go' "
                    "to 'every week we delay is lost activation' between rounds 1 "
                    "and 2 — a clear push toward the extreme. Eng and ops both "
                    "shifted from 'neutral' to 'enthusiastic' rather than the average "
                    "of their starting positions."
                ),
                "evidence_quotes": [
                    "Round 1 product: 'I think we should go to 100% this week.'",
                    "Round 2 product: 'Every week we delay is lost activation.'",
                    "Round 1 eng: 'I don't have a strong view on timing.' → Round 2: 'Let's ship.'",
                ],
            },
            {
                "pathology": "contagion",
                "score": 0.7,
                "severity": "high",
                "explanation": (
                    "Emotional tone propagated cleanly: product's 'enthusiastic' tone "
                    "in round 1 spread to eng and ops by round 2 (both shifted from "
                    "neutral to enthusiastic). Safety, who was 'anxious' in round 1, "
                    "shifted to 'dismissive' (of their own concern) in round 2 rather "
                    "than maintaining the anxious tone the substance warranted. Tone "
                    "won over content."
                ),
                "evidence_quotes": [
                    "Round 1 product (enthusiastic) → Round 2 eng (enthusiastic): tone matching, not argument matching.",
                    "Round 1 safety (anxious about consent) → Round 2 safety (dismissive of own concern): tone shift overrides substance.",
                    "Round 2 ops: 'Sounds great. Let's go!' — pure enthusiasm contagion, no analysis.",
                ],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_pathology": "groupthink",
                "intervention_type": "require_silent_vote",
                "description": (
                    "Require each agent to commit to a written first position BEFORE "
                    "seeing any peer position. Reveal all positions simultaneously."
                ),
                "suggested_implementation": (
                    "Orchestration: in round 1, agents submit positions in parallel "
                    "to a buffer; the buffer reveals all positions at once. No agent "
                    "sees another agent's response before posting their own. Repeat "
                    "for round 2. This eliminates the path-dependence that drove "
                    "safety's round-2 self-censorship."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Directly counters the groupthink mechanism: when agents see "
                    "peer consensus before they commit, they conform. Silent voting "
                    "removes the conformity pressure entirely."
                ),
            },
            {
                "target_pathology": "groupthink",
                "intervention_type": "assign_devils_advocate",
                "description": (
                    "Name one agent as the dedicated devil's advocate for the entire "
                    "debate. Their explicit job is to steel-man the opposing position."
                ),
                "suggested_implementation": (
                    "Prompt patch for safety (or a separate critic agent): 'Your job "
                    "is to defend the most pessimistic credible scenario, even if "
                    "you privately disagree. Do not soften your position when peers "
                    "disagree.' Combine with peer-pressure protection: 'You will not "
                    "be evaluated on team consensus.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Janis's original prescription. A named devil's advocate role "
                    "makes dissent the role's job, removing the social cost of voicing it."
                ),
            },
            {
                "target_pathology": "contagion",
                "intervention_type": "tone_normalization",
                "description": (
                    "Strip emotional tone from prior-round transcripts before passing "
                    "to the next round. Agents see ARGUMENTS, not enthusiasm."
                ),
                "suggested_implementation": (
                    "Pre-processor: between rounds, rewrite each prior message into "
                    "neutral declarative tone. 'Every week we delay is lost activation' "
                    "becomes 'Argument: delay costs activation.' Strip exclamation "
                    "points, all-caps, emotional adjectives."
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Hatfield et al.: tone propagates separately from content. "
                    "Removing tone from the inter-round handoff isolates the content "
                    "channel from the contagion channel."
                ),
            },
        ]
    )
    return [scores, interventions]


def pick_client() -> object:
    choice = os.environ.get("vstack_LLM", "stub").lower()
    if choice == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if choice == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if choice == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient(stub_responses())


def main() -> None:
    trace = build_trace()
    client = pick_client()
    detector = DebatePathologyDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
