"""Tests for ``vstack.gbrain``."""

from __future__ import annotations

import json
import subprocess
from unittest import mock

import pytest

import vstack.gbrain as gbrain
from vstack.gbrain._search import (
    _keyword_search,
    _tokenize,
    indexed_corpus,
    is_available,
    search_patterns,
    sync_corpus,
)
from vstack.gbrain.cli import main as cli_main


# ----------------------------------------------------------------------
# corpus
# ----------------------------------------------------------------------


def test_indexed_corpus_one_doc_per_pattern() -> None:
    docs = indexed_corpus()
    assert len(docs) == 34
    names = {doc["metadata"]["pattern"] for doc in docs}
    assert "lewin" in names
    assert "schein_culture" in names


def test_indexed_corpus_doc_shape() -> None:
    docs = indexed_corpus()
    doc = next(d for d in docs if d["metadata"]["pattern"] == "lewin")
    assert doc["id"].startswith("vstack/patterns/")
    assert doc["title"] == "Lewin Attribution"
    assert "Summary:" in doc["body"]
    assert doc["metadata"]["tool"] == "vstack_lewin"
    assert isinstance(doc["metadata"]["modes"], list)


# ----------------------------------------------------------------------
# is_available
# ----------------------------------------------------------------------


def test_is_available_when_gbrain_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: "/usr/local/bin/gbrain")
    assert is_available() is True


def test_is_available_when_gbrain_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: None)
    assert is_available() is False


# ----------------------------------------------------------------------
# sync_corpus
# ----------------------------------------------------------------------


def test_sync_corpus_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: None)
    result = sync_corpus(dry_run=True)
    assert result["dry_run"] is True
    assert result["would_sync"] == 34
    assert result["available"] is False


def test_sync_corpus_no_gbrain_returns_dry_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: None)
    result = sync_corpus()
    assert result["available"] is False
    assert result["would_sync"] == 34


def test_sync_corpus_when_gbrain_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: "/bin/gbrain")
    run_mock = mock.MagicMock(
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    )
    monkeypatch.setattr("vstack.gbrain._search.subprocess.run", run_mock)
    result = sync_corpus()
    assert result["synced"] == 34
    assert result["errors"] == []


def test_sync_corpus_handles_gbrain_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: "/bin/gbrain")
    monkeypatch.setattr(
        "vstack.gbrain._search.subprocess.run",
        mock.MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=2, stdout="", stderr="boom"
            )
        ),
    )
    result = sync_corpus()
    # All 34 fail to put -> 34 errors recorded
    assert result["synced"] == 0
    assert len(result["errors"]) == 34


# ----------------------------------------------------------------------
# search_patterns
# ----------------------------------------------------------------------


def test_search_falls_back_to_keyword_when_no_gbrain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: None)
    results = search_patterns("agent confidently wrong attribution", limit=3)
    assert results
    assert all(r.source == "keyword_fallback" for r in results)
    # Lewin should rank high for an attribution query.
    assert any(r.name == "lewin" for r in results)


def test_search_returns_empty_for_garbage_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: None)
    assert search_patterns("zzzzzzzzz xxxxxxx wwwww", limit=3) == []


def test_search_uses_gbrain_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: "/bin/gbrain")
    fake_response = {
        "results": [
            {
                "id": "vstack/patterns/lewin",
                "score": 0.94,
                "metadata": {
                    "pattern": "lewin",
                    "friendly": "Lewin Attribution",
                    "summary": "Attribution between INTERNAL vs ENVIRONMENTAL.",
                    "tool": "vstack_lewin",
                },
            },
            {
                "id": "vstack/patterns/aar",
                "score": 0.72,
                "metadata": {
                    "pattern": "aar",
                    "friendly": "After-Action Review",
                    "summary": "Wharton 4-step AAR.",
                    "tool": "vstack_aar",
                },
            },
        ]
    }
    run_mock = mock.MagicMock(
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(fake_response), stderr=""
        )
    )
    monkeypatch.setattr("vstack.gbrain._search.subprocess.run", run_mock)

    results = search_patterns("model is bad at facts", limit=5)
    assert len(results) == 2
    assert results[0].name == "lewin"
    assert results[0].source == "gbrain"
    assert results[0].score == 0.94


def test_search_falls_back_when_gbrain_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: "/bin/gbrain")
    run_mock = mock.MagicMock(
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"results": []}), stderr=""
        )
    )
    monkeypatch.setattr("vstack.gbrain._search.subprocess.run", run_mock)
    results = search_patterns("agent confidently wrong attribution")
    # Falls back to keyword scan; should still produce hits.
    assert results
    assert all(r.source == "keyword_fallback" for r in results)


# ----------------------------------------------------------------------
# internals
# ----------------------------------------------------------------------


def test_tokenize_drops_short_tokens() -> None:
    assert _tokenize("a bb ccc the lewin") == ["ccc", "the", "lewin"]


def test_keyword_search_ranks_by_overlap() -> None:
    results = _keyword_search("lewin attribution", limit=5)
    assert results
    assert results[0].name == "lewin"


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_cli_status(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: None)
    rc = cli_main(["status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "gbrain on PATH: no" in out
    assert "34 patterns" in out


def test_cli_status_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: "/bin/gbrain")
    rc = cli_main(["status", "--json"])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["gbrain_available"] is True
    assert body["patterns_in_corpus"] == 34


def test_cli_sync_dry_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: "/bin/gbrain")
    rc = cli_main(["sync", "--dry-run", "--json"])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["would_sync"] == 34


def test_cli_search_keyword_fallback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("vstack.gbrain._search.shutil.which", lambda _: None)
    rc = cli_main(["search", "lewin attribution", "--json"])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body
    assert body[0]["name"] == "lewin"
    assert body[0]["source"] == "keyword_fallback"


def test_cli_corpus_dumps_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["corpus"])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert len(body) == 34


def test_module_exports() -> None:
    assert "search_patterns" in gbrain.__all__
    assert "sync_corpus" in gbrain.__all__
    assert "is_available" in gbrain.__all__
