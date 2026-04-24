"""Tests for clone detection and cross-repo safety gate."""

import os
import subprocess
from pathlib import Path

import pytest


def _get_hooks_path() -> str:
    return str(Path(__file__).resolve().parents[1])


def _init_repo(path: Path, env: dict) -> None:
    """Initialize a git repo with a commit, .worktreeinclude, and .env."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=path, env=env, check=True, capture_output=True,
    )
    for key, val in [
        ("user.email", "test@test.com"),
        ("user.name", "Test"),
        ("core.hooksPath", _get_hooks_path()),
    ]:
        subprocess.run(
            ["git", "config", key, val],
            cwd=path, env=env, check=True, capture_output=True,
        )
    (path / "file.txt").write_text("hello")
    (path / ".worktreeinclude").write_text(".env\n")
    subprocess.run(
        ["git", "add", "file.txt", ".worktreeinclude"],
        cwd=path, env=env, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=path, env=env, check=True, capture_output=True,
    )
    (path / ".env").write_text("SECRET=from_source")


def test_clone_does_not_trigger_file_copy(
    tmp_path: Path, isolated_home: Path
):
    """
    git clone triggers post-checkout with all-zeros prev_ref, but the hook
    should detect it's a clone (not a worktree) and skip file copying.
    """
    env = os.environ.copy()
    env["HOME"] = str(isolated_home)
    (isolated_home / ".worktreeinclude").write_text(".env\n")

    source = tmp_path / "source-repo"
    _init_repo(source, env)

    clone_path = tmp_path / "cloned-repo"
    subprocess.run(
        ["git", "clone", str(source), str(clone_path)],
        env=env, check=True, capture_output=True,
    )

    assert not (clone_path / ".env").exists(), (
        ".env should NOT be copied during git clone"
    )


def test_cross_repo_worktree_rejects_source_and_logs_warning(
    tmp_path: Path, isolated_home: Path
):
    """
    When GIT_WORKTREE_SOURCE points to a different repository, the hook
    should reject it (log a warning) and fall back to same-repo detection.
    Files from the cross-repo source must never be copied.
    """
    env = os.environ.copy()
    env["HOME"] = str(isolated_home)
    (isolated_home / ".worktreeinclude").write_text(".env\n")

    repo_a = tmp_path / "repo-a"
    _init_repo(repo_a, env)
    (repo_a / ".env").write_text("SECRET=from_repo_a")

    repo_b = tmp_path / "repo-b"
    _init_repo(repo_b, env)
    # repo-b has no .env — so if anything is copied, it came from repo-a
    (repo_b / ".env").unlink()

    worktree_path = tmp_path / "repo-b-worktree"
    env_with_source = env.copy()
    env_with_source["GIT_WORKTREE_SOURCE"] = str(repo_a)

    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "-b", "cross-test"],
        cwd=repo_b, env=env_with_source,
        check=True, capture_output=True, text=True,
    )

    assert not (worktree_path / ".env").exists(), (
        ".env from repo-a should NOT be copied into repo-b worktree"
    )
    assert "Ignoring invalid GIT_WORKTREE_SOURCE" in result.stderr


def test_worktree_in_path_named_worktrees_still_works(
    tmp_path: Path, isolated_home: Path
):
    """
    A repo whose filesystem path contains 'worktrees' should still work
    correctly for both worktree creation (copy) and clone (skip).
    """
    env = os.environ.copy()
    env["HOME"] = str(isolated_home)
    (isolated_home / ".worktreeinclude").write_text(".env\n")

    repo = tmp_path / "worktrees" / "myrepo"
    _init_repo(repo, env)

    # Worktree creation should copy
    wt_path = tmp_path / "worktrees" / "myrepo-wt"
    env_with_source = env.copy()
    env_with_source["GIT_WORKTREE_SOURCE"] = str(repo)
    subprocess.run(
        ["git", "worktree", "add", str(wt_path), "-b", "test-wt"],
        cwd=repo, env=env_with_source,
        check=True, capture_output=True,
    )
    assert (wt_path / ".env").exists(), (
        ".env should be copied for worktree even in 'worktrees' path"
    )

    # Clone should NOT copy
    clone_path = tmp_path / "worktrees" / "cloned"
    subprocess.run(
        ["git", "clone", str(repo), str(clone_path)],
        env=env, check=True, capture_output=True,
    )
    assert not (clone_path / ".env").exists(), (
        ".env should NOT be copied during clone even in 'worktrees' path"
    )
