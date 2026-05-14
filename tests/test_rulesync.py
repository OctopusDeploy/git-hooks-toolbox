"""Tests for the shared rulesync regeneration logic."""

import importlib.util
import os
import sys
import types
from pathlib import Path
from typing import Optional

import pytest


@pytest.fixture
def rulesync_module() -> types.ModuleType:
    """Load rulesync_hook.py as a module."""
    module_path = Path(__file__).resolve().parents[1] / "rulesync_hook.py"
    spec = importlib.util.spec_from_file_location("rulesync_hook", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """A skeletal repo directory (no git init needed for unit tests)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def _write_rule(repo: Path, name: str = "rule.md", content: str = "rule") -> Path:
    rules_dir = repo / ".rulesync" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rule = rules_dir / name
    rule.write_text(content)
    return rule


def _set_mtime(path: Path, mtime: float) -> None:
    os.utime(path, (mtime, mtime))


def _stub_npx(monkeypatch, rulesync_module, calls: list, exit_code: int = 0):
    """Replace subprocess.run inside rulesync_hook with a recording stub.

    Records (cmd, cwd) tuples and writes a fake CLAUDE.md to simulate
    successful generation.
    """

    real_run = rulesync_module.subprocess.run

    def fake_run(cmd, **kwargs):
        calls.append((tuple(cmd), kwargs.get("cwd")))
        if exit_code == 0 and kwargs.get("cwd"):
            (Path(kwargs["cwd"]) / "CLAUDE.md").write_text("generated")

        class Result:
            returncode = exit_code
            stdout = ""
            stderr = "" if exit_code == 0 else "boom\n"

        return Result()

    monkeypatch.setattr(rulesync_module.subprocess, "run", fake_run)
    monkeypatch.setattr(rulesync_module.shutil, "which", lambda _: "/usr/bin/npx")
    return real_run


def test_no_op_when_rulesync_jsonc_missing(monkeypatch, rulesync_module, fake_repo: Path):
    calls: list = []
    _stub_npx(monkeypatch, rulesync_module, calls)

    rulesync_module.regenerate_if_needed(fake_repo)

    assert calls == []
    assert not (fake_repo / "CLAUDE.md").exists()


def test_regenerates_when_claude_md_missing(monkeypatch, rulesync_module, fake_repo: Path):
    (fake_repo / "rulesync.jsonc").write_text("{}")
    _write_rule(fake_repo)
    calls: list = []
    _stub_npx(monkeypatch, rulesync_module, calls)

    rulesync_module.regenerate_if_needed(fake_repo)

    assert len(calls) == 1
    cmd, cwd = calls[0]
    assert cmd[1:] == ("rulesync", "generate")
    assert cwd == fake_repo
    assert (fake_repo / ".rulesync" / ".last-regenerated").exists()


def test_skips_when_outputs_fresh(monkeypatch, rulesync_module, fake_repo: Path):
    (fake_repo / "rulesync.jsonc").write_text("{}")
    rule = _write_rule(fake_repo)
    (fake_repo / "CLAUDE.md").write_text("generated")
    marker = fake_repo / ".rulesync" / ".last-regenerated"
    marker.touch()
    # Marker newer than rule source.
    _set_mtime(rule, 1_000_000)
    _set_mtime(marker, 2_000_000)

    calls: list = []
    _stub_npx(monkeypatch, rulesync_module, calls)

    rulesync_module.regenerate_if_needed(fake_repo)

    assert calls == []


def test_regenerates_when_rule_source_newer(monkeypatch, rulesync_module, fake_repo: Path):
    (fake_repo / "rulesync.jsonc").write_text("{}")
    rule = _write_rule(fake_repo)
    (fake_repo / "CLAUDE.md").write_text("stale")
    marker = fake_repo / ".rulesync" / ".last-regenerated"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    # Rule newer than marker.
    _set_mtime(marker, 1_000_000)
    _set_mtime(rule, 2_000_000)

    calls: list = []
    _stub_npx(monkeypatch, rulesync_module, calls)

    rulesync_module.regenerate_if_needed(fake_repo)

    assert len(calls) == 1


def test_no_op_when_npx_missing(monkeypatch, rulesync_module, fake_repo: Path, capsys):
    (fake_repo / "rulesync.jsonc").write_text("{}")
    _write_rule(fake_repo)
    monkeypatch.setattr(rulesync_module.shutil, "which", lambda _: None)

    rulesync_module.regenerate_if_needed(fake_repo)

    captured = capsys.readouterr()
    assert "npx not on PATH" in captured.err
    assert not (fake_repo / ".rulesync" / ".last-regenerated").exists()


def test_swallows_generate_failure(monkeypatch, rulesync_module, fake_repo: Path, capsys):
    (fake_repo / "rulesync.jsonc").write_text("{}")
    _write_rule(fake_repo)
    calls: list = []
    _stub_npx(monkeypatch, rulesync_module, calls, exit_code=1)

    # Must not raise.
    rulesync_module.regenerate_if_needed(fake_repo)

    captured = capsys.readouterr()
    assert "generate failed" in captured.err
    # Marker not bumped on failure.
    assert not (fake_repo / ".rulesync" / ".last-regenerated").exists()
