"""Tests for ``vstack.memory`` -- home resolution, config IO, baseline paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import vstack.memory as memory
from vstack.memory._config import KNOWN_KEYS
from vstack.memory.cli import main as cli_main


@pytest.fixture
def tmp_home(monkeypatch, tmp_path: Path) -> Path:
    """Point VSTACK_HOME at a fresh temp dir for every test."""
    monkeypatch.setenv("VSTACK_HOME", str(tmp_path / "vstack-home"))
    return tmp_path / "vstack-home"


def test_get_home_creates_dir(tmp_home: Path) -> None:
    home = memory.get_home()
    assert home == tmp_home
    assert home.is_dir()


def test_get_home_no_create(tmp_home: Path) -> None:
    home = memory.get_home(create=False)
    assert home == tmp_home
    assert not home.exists()


def test_subdirs_created_lazily(tmp_home: Path) -> None:
    assert memory.get_baselines_dir().is_dir()
    assert memory.get_sessions_dir().is_dir()
    assert memory.get_analytics_dir().is_dir()
    assert memory.get_config_path() == tmp_home / "config.json"


def test_baseline_path_safe_name(tmp_home: Path) -> None:
    path = memory.baseline_path_for("schein_culture")
    assert path == tmp_home / "baselines" / "schein_culture.json"


@pytest.mark.parametrize(
    "bad",
    ["", "../escape", "foo/bar", "spaces here", "with;semicolon"],
)
def test_baseline_path_rejects_unsafe(tmp_home: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        memory.baseline_path_for(bad)


def test_config_roundtrip(tmp_home: Path) -> None:
    cfg = memory.load_config()
    assert cfg.values == {}
    cfg.set("default_mode", "forensic")
    cfg.set("custom_key", 42)
    memory.save_config(cfg)

    again = memory.load_config()
    assert again.get("default_mode") == "forensic"
    assert again.get("custom_key") == 42
    # Unset known key falls back to the default.
    assert again.get("default_model") == KNOWN_KEYS["default_model"][0]


def test_config_merged_with_defaults(tmp_home: Path) -> None:
    memory.set_key("default_mode", "quick")
    snapshot = memory.list_config()
    assert snapshot["default_mode"] == "quick"
    # Every known key surfaces in the snapshot.
    for key in KNOWN_KEYS:
        assert key in snapshot


def test_config_delete(tmp_home: Path) -> None:
    memory.set_key("default_mode", "forensic")
    removed = memory.delete_key("default_mode")
    assert removed is True
    again = memory.load_config()
    assert "default_mode" not in again.values
    # Re-delete is a no-op.
    assert memory.delete_key("default_mode") is False


def test_config_malformed_raises(tmp_home: Path) -> None:
    memory.get_config_path().write_text("not json", encoding="utf-8")
    with pytest.raises(memory.ConfigError):
        memory.load_config()


# ----------------------------------------------------------------------
# CLI surface
# ----------------------------------------------------------------------


def test_cli_get_set_list(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["set", "default_mode", "quick"]) == 0
    capsys.readouterr()  # drain

    assert cli_main(["get", "default_mode"]) == 0
    out = capsys.readouterr().out.strip()
    assert out == "quick"

    assert cli_main(["list"]) == 0
    out = capsys.readouterr().out
    assert "default_mode" in out
    assert "quick" in out


def test_cli_set_coerces_numbers(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["set", "api_port", "9000"]) == 0
    cfg = memory.load_config()
    assert cfg.values["api_port"] == 9000


def test_cli_unset_returns_1_when_missing(tmp_home: Path) -> None:
    assert cli_main(["unset", "default_mode"]) == 1


def test_cli_get_unknown_returns_1(tmp_home: Path) -> None:
    assert cli_main(["get", "does_not_exist"]) == 1


def test_cli_get_unknown_with_default(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["get", "missing", "--default", "fallback"]) == 0
    assert capsys.readouterr().out.strip() == "fallback"


def test_cli_path_subcommand(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["path", "baselines"]) == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("/baselines")


def test_cli_keys_lists_known_keys(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["keys"]) == 0
    out = capsys.readouterr().out
    for key in KNOWN_KEYS:
        assert key in out


def test_cli_set_value_persists_to_json(tmp_home: Path) -> None:
    assert cli_main(["set", "custom_flag", "true"]) == 0
    raw = json.loads(memory.get_config_path().read_text(encoding="utf-8"))
    assert raw == {"custom_flag": True}


def test_baseline_path_is_under_baselines_dir(tmp_home: Path) -> None:
    path = memory.baseline_path_for("aar")
    assert path.parent == memory.get_baselines_dir()


# ----------------------------------------------------------------------
# install-skills subcommand
# ----------------------------------------------------------------------


def test_install_skills_dry_run(
    tmp_home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "src_skills"
    src.mkdir()
    (src / "vstack").mkdir()
    (src / "vstack" / "SKILL.md").write_text("# vstack\n", encoding="utf-8")
    (src / "vstack-baseline").mkdir()
    (src / "vstack-baseline" / "SKILL.md").write_text("# baseline\n", encoding="utf-8")

    dest = tmp_path / "skills-dest"
    memory.set_key("skills_install_path", str(dest))

    rc = cli_main(["install-skills", "--source", str(src), "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRYRUN" in out
    assert not dest.exists()


def test_install_skills_copies_then_skips(
    tmp_home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "src_skills"
    (src / "vstack").mkdir(parents=True)
    (src / "vstack" / "SKILL.md").write_text("# vstack\n", encoding="utf-8")

    dest = tmp_path / "skills-dest"
    memory.set_key("skills_install_path", str(dest))

    rc = cli_main(["install-skills", "--source", str(src)])
    assert rc == 0
    capsys.readouterr()  # drain
    assert (dest / "vstack" / "SKILL.md").read_text() == "# vstack\n"

    # Re-running without --force skips (no overwrite).
    (src / "vstack" / "SKILL.md").write_text("# vstack updated\n", encoding="utf-8")
    rc = cli_main(["install-skills", "--source", str(src)])
    assert rc == 0
    assert (dest / "vstack" / "SKILL.md").read_text() == "# vstack\n"  # unchanged

    # --force overwrites.
    rc = cli_main(["install-skills", "--source", str(src), "--force"])
    assert rc == 0
    assert (dest / "vstack" / "SKILL.md").read_text() == "# vstack updated\n"


def test_install_skills_missing_source_returns_2(
    tmp_home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bogus = tmp_path / "does_not_exist"
    rc = cli_main(["install-skills", "--source", str(bogus)])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


# ----------------------------------------------------------------------
# gen-platform subcommand
# ----------------------------------------------------------------------


def test_gen_platform_list(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["gen-platform", "--list"])
    assert rc == 0
    out = capsys.readouterr().out
    for name in (
        "cursor",
        "cline",
        "continue",
        "roo-code",
        "windsurf",
        "zed",
        "aider",
        "goose",
        "kiro",
        "openclaw",
        "codex-cli",
        "opencode",
        "docker-compose",
        "claude-desktop",
    ):
        assert name in out


def test_gen_platform_no_arg_lists(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["gen-platform"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "cursor" in out


def test_gen_platform_prints_body(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["gen-platform", "cursor"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "mcpServers" in out
    assert "vstack-mcp" in out


def test_gen_platform_unknown_returns_2(tmp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["gen-platform", "does-not-exist"])
    assert rc == 2
    assert "Unknown platform" in capsys.readouterr().err


def test_gen_platform_write_to_explicit_out(
    tmp_home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "mcp.json"
    rc = cli_main(["gen-platform", "cursor", "--write", "--out", str(dest)])
    assert rc == 0
    assert dest.exists()
    assert "mcpServers" in dest.read_text()


def test_gen_platform_write_refuses_overwrite(tmp_home: Path, tmp_path: Path) -> None:
    dest = tmp_path / "mcp.json"
    dest.write_text("existing\n", encoding="utf-8")
    rc = cli_main(["gen-platform", "cursor", "--write", "--out", str(dest)])
    assert rc == 2
    assert dest.read_text() == "existing\n"
    rc = cli_main(["gen-platform", "cursor", "--write", "--out", str(dest), "--force"])
    assert rc == 0
    assert "mcpServers" in dest.read_text()
