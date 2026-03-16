"""
Pytest fixtures for post-checkout hook tests.

Provides isolated git repositories, a deterministic home directory, and
helpers to invoke the hook directly under controlled conditions.
"""

import os
import subprocess
import sys
import types
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Generator

import pytest


def _get_env_with_home(fake_home: Path) -> dict:
    """
    Get environment dict with custom HOME for subprocess.

    Args:
        fake_home: Path to fake home directory

    Returns:
        Environment dict with HOME set
    """
    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    env["USERPROFILE"] = str(fake_home)
    return env


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch) -> Path:
    """
    Isolate home per test so user-wide ~/.worktreeinclude does not leak in.
    """
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    return fake_home


@pytest.fixture
def git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """
    Create an isolated git repository in a temporary directory.

    Yields:
        Path to git repository root
    """
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo_path,
        check=True,
        capture_output=True
    )

    # Configure git (required for commits)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True
    )

    # Set hooks path to our git-hooks directory
    hooks_path = Path(__file__).resolve().parents[1]
    subprocess.run(
        ["git", "config", "core.hooksPath", str(hooks_path)],
        cwd=repo_path,
        check=True
    )

    yield repo_path

    # Cleanup: Remove all worktrees
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            wt_path = Path(line.split()[1])
            if wt_path != repo_path:
                subprocess.run(
                    ["git", "worktree", "remove", str(wt_path), "--force"],
                    cwd=repo_path,
                    capture_output=True
                )


@pytest.fixture
def pattern_file(tmp_path: Path) -> Generator[Path, None, None]:
    """
    Create a temporary .worktreeinclude pattern file.

    Yields:
        Path to pattern file
    """
    pattern_path = tmp_path / ".worktreeinclude"
    yield pattern_path

    # Cleanup happens automatically via tmp_path


@pytest.fixture
def user_pattern_file(isolated_home: Path) -> tuple[Path, dict]:
    """
    Create a temporary user-wide .worktreeinclude file.

    Yields:
        Tuple of (pattern_file_path, env_dict_for_subprocess)
    """
    pattern_path = isolated_home / ".worktreeinclude"
    env = _get_env_with_home(isolated_home)
    return (pattern_path, env)


@pytest.fixture
def hook_module() -> types.ModuleType:
    """
    Load the post-checkout hook script as an importable module.
    """
    hook_path = Path(__file__).resolve().parents[1] / "post-checkout"
    loader = SourceFileLoader("post_checkout_hook", str(hook_path))
    module = types.ModuleType(loader.name)
    loader.exec_module(module)
    return module


@pytest.fixture
def run_hook(monkeypatch, hook_module):
    """
    Invoke hook main() directly with controlled cwd and source worktree.
    """

    def _run(destination_worktree: Path, source_worktree: Path, prev_ref: str = "0" * 40) -> int:
        monkeypatch.chdir(destination_worktree)
        monkeypatch.setattr(hook_module, "find_source_worktree", lambda: source_worktree)
        monkeypatch.setattr(sys, "argv", ["post-checkout", prev_ref])
        return hook_module.main()

    return _run


def create_test_files(repo_path: Path, files: dict[str, str]) -> None:
    """
    Helper to create test files in repository.

    Args:
        repo_path: Repository root path
        files: Dict mapping file paths to contents
    """
    for file_path, content in files.items():
        full_path = repo_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)


def commit_all(repo_path: Path, message: str = "Test commit") -> None:
    """
    Helper to stage and commit all files.

    Args:
        repo_path: Repository root path
        message: Commit message
    """
    subprocess.run(
        ["git", "add", "-A"],
        cwd=repo_path,
        check=True
    )
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_path,
        check=True
    )


# Make helpers available to tests
pytest.create_test_files = create_test_files
pytest.commit_all = commit_all
