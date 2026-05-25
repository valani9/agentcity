"""Tests for ``vstack.learnings``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import vstack.learnings as learnings
from vstack.learnings._store import LearningRecord, LearningStore
from vstack.learnings.cli import main as cli_main


@pytest.fixture
def tmp_home(monkeypatch, tmp_path: Path) -> Path:
    home = tmp_path / "vstack-home"
    monkeypatch.setenv("VSTACK_HOME", str(home))
    return home


def _store(tmp_home: Path) -> LearningStore:
    return LearningStore(path=tmp_home / "learnings.jsonl")


def test_record_then_recall(tmp_home: Path) -> None:
    store = _store(tmp_home)
    store.record(
        LearningRecord(
            pattern="lewin",
            agent_id="qa-bot",
            severity="high",
            interventions_applied=["change_rag_index"],
            dominant_finding="environmental: stale RAG",
        )
    )
    store.record(
        LearningRecord(
            pattern="schein_culture",
            crew_id="campaign-team",
            interventions_applied=["surface_hidden_assumption"],
        )
    )
    records = store.recall(limit=10)
    assert len(records) == 2
    # newest-first ordering
    assert records[0].pattern == "schein_culture"
    assert records[1].pattern == "lewin"

    lewin_only = store.recall(pattern="lewin")
    assert len(lewin_only) == 1
    assert lewin_only[0].agent_id == "qa-bot"


def test_update_outcome_marks_latest_open_record(tmp_home: Path) -> None:
    store = _store(tmp_home)
    store.record(LearningRecord(pattern="lewin", agent_id="a", interventions_applied=["fix-1"]))
    store.record(LearningRecord(pattern="lewin", agent_id="a", interventions_applied=["fix-2"]))

    updated = store.update_outcome(
        pattern="lewin", agent_id="a", outcome="improved", notes="next run passed"
    )
    assert updated is not None
    assert updated.follow_up_outcome == "improved"
    assert updated.interventions_applied == ["fix-2"]  # the most recent open record

    # Re-running marks the earlier record (the first record is still open).
    again = store.update_outcome(pattern="lewin", agent_id="a", outcome="no_change")
    assert again is not None
    assert again.interventions_applied == ["fix-1"]

    # Once both are marked, no open records remain.
    third = store.update_outcome(pattern="lewin", agent_id="a", outcome="worse")
    assert third is None


def test_outcomes_aggregate(tmp_home: Path) -> None:
    store = _store(tmp_home)
    for _ in range(3):
        store.record(
            LearningRecord(
                pattern="lewin",
                interventions_applied=["change_rag_index"],
                follow_up_outcome="improved",
            )
        )
    store.record(
        LearningRecord(
            pattern="lewin",
            interventions_applied=["change_rag_index"],
            follow_up_outcome="no_change",
        )
    )
    rows = store.outcomes(pattern="lewin")
    assert len(rows) == 1
    row = rows[0]
    assert row.runs == 4
    assert row.improved == 3
    assert row.no_change == 1
    assert row.improvement_rate == 0.75


def test_iter_records_skips_malformed_lines(tmp_home: Path) -> None:
    store = _store(tmp_home)
    store.record(LearningRecord(pattern="lewin"))
    # corrupt the file
    with store.path.open("a", encoding="utf-8") as f:
        f.write("not json at all\n")
    store.record(LearningRecord(pattern="aar"))
    records = list(store.iter_records())
    assert [r.pattern for r in records] == ["lewin", "aar"]


def test_default_store_points_to_vstack_home(tmp_home: Path) -> None:
    store = learnings.default_store()
    assert store.path == tmp_home / "learnings.jsonl"


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_cli_record_and_recall(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(
        [
            "record",
            "lewin",
            "--agent-id",
            "qa-bot",
            "--severity",
            "high",
            "--intervention",
            "change_rag_index",
        ]
    )
    assert rc == 0
    capsys.readouterr()

    rc = cli_main(["recall", "--pattern", "lewin", "--json"])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert len(body) == 1
    assert body[0]["pattern"] == "lewin"
    assert body[0]["agent_id"] == "qa-bot"


def test_cli_outcome_and_outcomes(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli_main(["record", "lewin", "--intervention", "fix-x"])
    capsys.readouterr()
    rc = cli_main(["outcome", "lewin", "improved"])
    assert rc == 0
    capsys.readouterr()
    rc = cli_main(["outcomes", "--json"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["improved"] == 1


def test_cli_outcome_without_open_record_returns_1(
    tmp_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli_main(["outcome", "lewin", "improved"])
    assert rc == 1


def test_cli_path_prints_learnings_file(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["path"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("learnings.jsonl")


def test_cli_clear_deletes_file(tmp_home: Path) -> None:
    cli_main(["record", "lewin"])
    store = learnings.default_store()
    assert store.path.exists()
    cli_main(["clear"])
    assert not store.path.exists()
