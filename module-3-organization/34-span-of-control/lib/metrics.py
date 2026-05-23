"""Deterministic metric computation for the Span-of-Control diagnostic.

All five core metrics are computed locally in Python from the
CrewLoadTrace. The LLM does NOT touch the numbers — it only generates
qualitative interventions on top of these computed values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .schema import AgentNode

if TYPE_CHECKING:
    from .schema import CrewLoadTrace


def compute_span_counts(agents: list[AgentNode]) -> dict[str, int]:
    """For each agent, count how many other agents have them in reports_to.

    Agents not mentioned in any reports_to edge get a count of 0.
    """
    counts: dict[str, int] = {a.agent_id: 0 for a in agents}
    for agent in agents:
        for supervisor_id in agent.reports_to:
            if supervisor_id in counts:
                counts[supervisor_id] += 1
            else:
                # Edge references an agent not in the roster — still count it
                # so the metric reflects the declared structure
                counts[supervisor_id] = 1
    return counts


def max_span(agents: list[AgentNode]) -> int:
    counts = compute_span_counts(agents)
    if not counts:
        return 0
    return max(counts.values(), default=0)


def mean_span(agents: list[AgentNode]) -> float:
    """Mean span across agents that have at least one subordinate.

    Returns 0.0 when no agent has any subordinate (pure flat-peer crew).
    """
    counts = compute_span_counts(agents)
    supervisors = [c for c in counts.values() if c > 0]
    if not supervisors:
        return 0.0
    return sum(supervisors) / len(supervisors)


def centralization_index(agents: list[AgentNode]) -> float:
    """Fraction of total decision authority concentrated in the top-K
    supervisors (here: top 20% by subordinate count).

    Combines two signals:
      (a) Authority weight: full=1.0, partial=0.5, advisory=0.25, none=0.0
      (b) Subordinate count: more subordinates → more concentration weight

    Returns a value in [0, 1].
    """
    if not agents:
        return 0.0
    weights = {"full": 1.0, "partial": 0.5, "advisory": 0.25, "none": 0.0}
    counts = compute_span_counts(agents)
    auth_x_count = []
    for agent in agents:
        w = weights[agent.decision_authority]
        c = counts.get(agent.agent_id, 0)
        # +1 to give every agent a baseline; multiplied by authority weight
        auth_x_count.append(w * (c + 1))
    total = sum(auth_x_count)
    if total == 0.0:
        return 0.0
    # Top 20% (at least 1) — proxy for "the supervisors"
    k = max(1, len(auth_x_count) // 5)
    top = sum(sorted(auth_x_count, reverse=True)[:k])
    return round(top / total, 4)


def hierarchy_depth(agents: list[AgentNode]) -> int:
    """Longest reports_to chain in the graph.

    Uses iterative DFS with cycle detection. Cycles return depth 1 for
    safety rather than infinite recursion.
    """
    id_to_agent = {a.agent_id: a for a in agents}
    cache: dict[str, int] = {}

    def depth_from(start: str) -> int:
        if start in cache:
            return cache[start]
        stack: list[tuple[str, int]] = [(start, 1)]
        seen = {start}
        best = 1
        while stack:
            current, d = stack.pop()
            best = max(best, d)
            agent = id_to_agent.get(current)
            if agent is None:
                continue
            for parent in agent.reports_to:
                if parent in seen:
                    continue  # cycle — bail out of that branch
                seen.add(parent)
                stack.append((parent, d + 1))
        cache[start] = best
        return best

    if not agents:
        return 0
    return max((depth_from(a.agent_id) for a in agents), default=1)


def span_gini(agents: list[AgentNode]) -> float:
    """Gini coefficient over the span distribution.

    0 = perfectly balanced (every supervisor has same span).
    1 = single supervisor holds all subordinates.

    Empty / all-zero distributions return 0.0.
    """
    counts = compute_span_counts(agents)
    values = sorted(counts.values())
    n = len(values)
    if n == 0:
        return 0.0
    total = sum(values)
    if total == 0:
        return 0.0
    cum = 0.0
    for i, v in enumerate(values, start=1):
        cum += i * v
    return round((2 * cum) / (n * total) - (n + 1) / n, 4)


def decision_bottleneck_score(
    agents: list[AgentNode], incoming_request_rate: float
) -> tuple[float, list[str]]:
    """Identify agents that combine:
      - high span (many subordinates depend on them)
      - full decision authority (must commit personally)
      - load amplification from incoming_request_rate

    Returns (score in [0,1], list of bottleneck agent_ids).
    """
    counts = compute_span_counts(agents)
    if not agents:
        return 0.0, []
    bottlenecks: list[tuple[str, float]] = []
    for agent in agents:
        c = counts.get(agent.agent_id, 0)
        if c == 0 and agent.decision_authority != "full":
            continue
        auth_weight = 1.0 if agent.decision_authority == "full" else 0.3
        # Risk = (span normalized to 10 max) * authority * load factor
        span_norm = min(1.0, c / 10.0)
        load_factor = min(2.0, 1.0 + incoming_request_rate / 10.0)
        risk = span_norm * auth_weight * load_factor
        if risk >= 0.3:
            bottlenecks.append((agent.agent_id, risk))

    if not bottlenecks:
        return 0.0, []
    bottlenecks.sort(key=lambda x: x[1], reverse=True)
    top_risk = bottlenecks[0][1]
    score = min(1.0, top_risk)
    ids = [aid for aid, _ in bottlenecks]
    return round(score, 4), ids


def normalize_span(value: int) -> float:
    """Wide spans (>10) start hurting; 0 spans are also wrong unless flat-peer."""
    if value <= 0:
        return 0.0
    if value <= 7:
        return value / 14.0  # mild signal up to ~0.5 at span=7
    return min(1.0, 0.5 + (value - 7) / 10.0)


def normalize_mean_span(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value <= 5.0:
        return value / 20.0
    return min(1.0, 0.25 + (value - 5.0) / 10.0)


def normalize_hierarchy_depth(value: int) -> float:
    """Depth 1-2 is fine; depth 5+ is severe."""
    if value <= 2:
        return 0.0
    return min(1.0, (value - 2) / 5.0)


def normalize_centralization(value: float) -> float:
    """Centralization index above 0.6 starts being problematic."""
    if value <= 0.5:
        return value * 0.5
    return min(1.0, 0.25 + (value - 0.5) * 1.5)


def compute_all_metrics_payload(
    trace: CrewLoadTrace,
) -> tuple[dict[str, tuple[float, float, str]], list[str]]:
    """Returns ({metric_name: (raw_value, normalized_score, explanation)}, bottleneck_ids)."""
    agents = trace.agents
    counts = compute_span_counts(agents)
    supervisor_counts = [c for c in counts.values() if c > 0]

    max_s = max_span(agents)
    mean_s = mean_span(agents)
    cent_idx = centralization_index(agents)
    depth = hierarchy_depth(agents)
    gini = span_gini(agents)
    bottleneck_score, bottleneck_ids = decision_bottleneck_score(
        agents, trace.incoming_request_rate
    )

    n_supervisors = len(supervisor_counts)

    metrics: dict[str, tuple[float, float, str]] = {
        "max_span": (
            float(max_s),
            normalize_span(max_s),
            (
                f"Widest span = {max_s} subordinates. "
                + (
                    "Healthy."
                    if max_s <= 7
                    else "Wide span — supervisor at risk of becoming a bottleneck."
                )
            ),
        ),
        "mean_span": (
            mean_s,
            normalize_mean_span(mean_s),
            (
                f"Mean span across {n_supervisors} supervisors = {mean_s:.2f}."
                if n_supervisors > 0
                else "No supervisors (pure flat-peer)."
            ),
        ),
        "centralization_index": (
            cent_idx,
            normalize_centralization(cent_idx),
            (f"Top supervisors hold {cent_idx * 100:.0f}% of weighted decision authority."),
        ),
        "hierarchy_depth": (
            float(depth),
            normalize_hierarchy_depth(depth),
            (
                f"Longest reports_to chain = {depth} levels."
                + ("" if depth <= 2 else " Deep hierarchy adds latency.")
            ),
        ),
        "span_gini": (
            gini,
            min(1.0, gini),
            (
                f"Span distribution Gini = {gini:.2f}. "
                + (
                    "Balanced."
                    if gini < 0.4
                    else "Imbalanced — load concentrates on a few supervisors."
                )
            ),
        ),
        "decision_bottleneck": (
            bottleneck_score,
            bottleneck_score,
            (
                f"Bottleneck risk = {bottleneck_score:.2f} "
                f"(incoming rate = {trace.incoming_request_rate:.1f}/min)."
                + (f" Bottleneck agents: {', '.join(bottleneck_ids)}." if bottleneck_ids else "")
            ),
        ),
    }
    return metrics, bottleneck_ids


def composite_load_score(metrics: dict[str, tuple[float, float, str]]) -> float:
    """Weighted composite of normalized metric scores.

    Weights favor decision_bottleneck and span_gini because those are the
    failure modes that escalate under load.
    """
    weights = {
        "max_span": 0.15,
        "mean_span": 0.10,
        "centralization_index": 0.15,
        "hierarchy_depth": 0.10,
        "span_gini": 0.20,
        "decision_bottleneck": 0.30,
    }
    total = 0.0
    weight_sum = 0.0
    for name, (_, norm, _) in metrics.items():
        w = weights.get(name, 0.0)
        total += w * norm
        weight_sum += w
    if weight_sum == 0.0:
        return 0.0
    return round(total / weight_sum, 4)
