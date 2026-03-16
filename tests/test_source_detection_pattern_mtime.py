"""Tests for .worktreeinclude mtime-based source worktree detection."""

import os
import subprocess
import time
from pathlib import Path

import pytest


def _add_worktree(repo_path: Path, branch: str) -> Path:
    """Create a new git worktree branch and return its path."""
    wt_path = repo_path.parent / branch
    subprocess.run(
        ["git", "worktree", "add", str(wt_path), "-b", branch],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    return wt_path


def test_picks_worktree_with_newest_matching_file(git_repo, hook_module, monkeypatch):
    """
    When psutil is unavailable, find_source_worktree picks the worktree whose
    .worktreeinclude-matched file has the most recent mtime.
    """
    # Bootstrap the repo with a tracked file so we can create worktrees
    pytest.create_test_files(git_repo, {"README.md": "init"})
    pytest.commit_all(git_repo)

    older_wt = _add_worktree(git_repo, "older-branch")
    newer_wt = _add_worktree(git_repo, "newer-branch")

    # Create pattern file in the main repo (used by find_pattern_file)
    pattern_file = git_repo / ".worktreeinclude"
    pattern_file.write_text(".env\n")

    # Place .env in both worktrees; touch the newer one last
    (older_wt / ".env").write_text("OLD=1")
    time.sleep(0.05)
    (newer_wt / ".env").write_text("NEW=1")

    # Destination worktree is git_repo; disable psutil so we reach the mtime fallback
    monkeypatch.setattr(hook_module, "PSUTIL_AVAILABLE", False)
    monkeypatch.delenv("GIT_WORKTREE_SOURCE", raising=False)
    monkeypatch.chdir(git_repo)

    result = hook_module.find_source_worktree()

    assert result == newer_wt.resolve()


def test_falls_through_to_main_when_no_matching_files(git_repo, hook_module, monkeypatch):
    """
    When no worktree has files matching the pattern, detection should fall through
    to the git-common-dir (main worktree) fallback without raising an error.
    """
    pytest.create_test_files(git_repo, {"README.md": "init"})
    pytest.commit_all(git_repo)

    _add_worktree(git_repo, "branch-a")

    # Pattern file exists but matches nothing (no .env file anywhere)
    pattern_file = git_repo / ".worktreeinclude"
    pattern_file.write_text(".env\n")

    monkeypatch.setattr(hook_module, "PSUTIL_AVAILABLE", False)
    monkeypatch.delenv("GIT_WORKTREE_SOURCE", raising=False)
    monkeypatch.chdir(git_repo)

    result = hook_module.find_source_worktree()

    # Should fall through to main-worktree fallback (common-dir parent)
    common_dir = hook_module._get_git_common_dir()
    assert result == common_dir.parent


def test_logs_source_file_explicitly(git_repo, hook_module, monkeypatch, capsys):
    """
    When mtime detection succeeds, stderr should include both the winning
    worktree path and the specific file that drove the decision.
    """
    pytest.create_test_files(git_repo, {"README.md": "init"})
    pytest.commit_all(git_repo)

    newer_wt = _add_worktree(git_repo, "logging-branch")

    pattern_file = git_repo / ".worktreeinclude"
    pattern_file.write_text(".env\n")

    env_file = newer_wt / ".env"
    env_file.write_text("LOG=1")

    monkeypatch.setattr(hook_module, "PSUTIL_AVAILABLE", False)
    monkeypatch.delenv("GIT_WORKTREE_SOURCE", raising=False)
    monkeypatch.chdir(git_repo)

    hook_module.find_source_worktree()

    captured = capsys.readouterr()
    assert str(newer_wt.resolve()) in captured.err
    assert str(env_file.resolve()) in captured.err
