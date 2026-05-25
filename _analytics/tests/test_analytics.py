"""Tests for ``vstack.analytics``."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import vstack.analytics as analytics
from vstack.aar import TelemetryEvent
from vstack.analytics import CostEstimator, FileTelemetrySink, TelemetryAggregator
from vstack.analytics.cli import main as cli_main


@pytest.fixture
def tmp_home(monkeypatch, tmp_path: Path) -> Path:
    home = tmp_path / "vstack-home"
    monkeypatch.setenv("VSTACK_HOME", str(home))
    return home


def _event(
    *,
    pattern: str = "lewin",
    model: str = "claude-sonnet-4-6",
    input_tokens: int = 1000,
    output_tokens: int = 200,
    elapsed_ms: float = 1200.0,
    ts: datetime | None = None,
    run_id: str = "r",
) -> TelemetryEvent:
    return TelemetryEvent(
        event_type="llm_call",
        pattern=pattern,
        run_id=run_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        elapsed_ms=elapsed_ms,
        extra={},
        timestamp=ts or datetime.now(timezone.utc),
    )


def test_file_sink_writes_jsonl(tmp_home: Path) -> None:
    sink = FileTelemetrySink()
    sink.record(_event())
    sink.record(_event(pattern="aar", model="gpt-4o"))
    assert sink.path.exists()
    lines = [json.loads(line) for line in sink.path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["pattern"] == "lewin"
    assert lines[1]["pattern"] == "aar"


def test_cost_estimator_known_models() -> None:
    est = CostEstimator()
    # Sonnet at $0.003 input + $0.015 output per 1k.
    cost = est.cost("claude-sonnet-4-6", 1000, 1000)
    assert pytest.approx(cost, rel=1e-6) == 0.003 + 0.015
    # Unknown model -> zero cost.
    assert est.cost("totally-unknown", 1000, 1000) == 0.0
    # Stub-model is free (used by tests).
    assert est.cost("stub-model", 100000, 100000) == 0.0


def test_cost_estimator_prefix_match() -> None:
    est = CostEstimator(rates={"my-custom-": (0.001, 0.002)})
    cost = est.cost("my-custom-7b", 1000, 1000)
    assert pytest.approx(cost, rel=1e-6) == 0.003


def test_aggregator_per_pattern(tmp_home: Path) -> None:
    sink = FileTelemetrySink()
    sink.record(_event(pattern="lewin", input_tokens=1000, output_tokens=200))
    sink.record(_event(pattern="lewin", input_tokens=500, output_tokens=100))
    sink.record(_event(pattern="aar", input_tokens=2000, output_tokens=400))

    agg = TelemetryAggregator()
    rows = agg.per_pattern()
    by_name = {r.pattern: r for r in rows}
    assert by_name["lewin"].calls == 2
    assert by_name["lewin"].input_tokens == 1500
    assert by_name["aar"].input_tokens == 2000


def test_aggregator_per_model(tmp_home: Path) -> None:
    sink = FileTelemetrySink()
    sink.record(_event(model="claude-sonnet-4-6"))
    sink.record(_event(model="gpt-4o"))
    rows = TelemetryAggregator().per_model()
    models = {r.model for r in rows}
    assert {"claude-sonnet-4-6", "gpt-4o"} <= models


def test_aggregator_per_day(tmp_home: Path) -> None:
    sink = FileTelemetrySink()
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    sink.record(_event(ts=now))
    sink.record(_event(ts=now + timedelta(days=1)))
    rows = TelemetryAggregator().per_day()
    days = {r.day for r in rows}
    assert "2026-05-25" in days
    assert "2026-05-26" in days


def test_top_costs(tmp_home: Path) -> None:
    sink = FileTelemetrySink()
    # Big sonnet call: expensive
    sink.record(_event(input_tokens=10000, output_tokens=5000, model="claude-sonnet-4-6"))
    # Small one: cheap
    sink.record(_event(input_tokens=100, output_tokens=50, model="claude-sonnet-4-6"))
    top = TelemetryAggregator().top_costs(n=2)
    assert len(top) == 2
    assert top[0]["estimated_cost_usd"] >= top[1]["estimated_cost_usd"]


def test_total_cost_aggregates(tmp_home: Path) -> None:
    sink = FileTelemetrySink()
    sink.record(_event(input_tokens=1000, output_tokens=1000))
    sink.record(_event(input_tokens=1000, output_tokens=1000))
    total = TelemetryAggregator().total_cost()
    assert total > 0  # sonnet rates × 2 events


def test_aggregator_handles_missing_file(tmp_home: Path) -> None:
    agg = TelemetryAggregator()
    assert agg.per_pattern() == []
    assert agg.per_model() == []
    assert agg.per_day() == []
    assert agg.top_costs() == []
    assert agg.total_cost() == 0.0


def test_aggregator_skips_malformed_lines(tmp_home: Path) -> None:
    sink = FileTelemetrySink()
    sink.record(_event())
    with sink.path.open("a", encoding="utf-8") as f:
        f.write("not json\n")
    sink.record(_event())
    events = list(TelemetryAggregator().iter_events())
    assert len(events) == 2


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_cli_summary_pattern(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sink = FileTelemetrySink()
    sink.record(_event())
    rc = cli_main(["summary"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "lewin" in out


def test_cli_summary_json(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sink = FileTelemetrySink()
    sink.record(_event(model="gpt-4o"))
    rc = cli_main(["summary", "--by", "model", "--json"])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert any(r["model"] == "gpt-4o" for r in body)


def test_cli_top_costs(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sink = FileTelemetrySink()
    sink.record(_event())
    rc = cli_main(["top-costs", "-n", "1"])
    assert rc == 0


def test_cli_cost(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sink = FileTelemetrySink()
    sink.record(_event())
    rc = cli_main(["cost", "--json"])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert "total_cost_usd" in body


def test_cli_path(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["path"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("telemetry.jsonl")


def test_cli_summary_no_events(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["summary"])
    assert rc == 0
    assert "(no telemetry events" in capsys.readouterr().out


def test_enable_file_telemetry_installs_default_sink(tmp_home: Path) -> None:
    from vstack.aar import get_default_sink

    analytics.enable_file_telemetry()
    sink = get_default_sink()
    assert isinstance(sink, FileTelemetrySink)
