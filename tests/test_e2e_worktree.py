"""
Integration tests for post-checkout hook behavior.

Most tests invoke the hook directly for deterministic setup; one smoke test keeps
the real git hook integration path (`git worktree add`).
"""

import subprocess
from pathlib import Path

import pytest


def _create_worktree_without_hooks(
    git_repo: Path, worktree_path: Path, branch_name: str, env: dict | None = None
) -> None:
    """
    Create a worktree while disabling hooks so tests can invoke the hook explicitly.
    """
    subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "worktree",
            "add",
            str(worktree_path),
            "-b",
            branch_name,
        ],
        cwd=git_repo,
        env=env,
        check=True,
        capture_output=True,
    )


def test_repo_specific_pattern_override(
    git_repo: Path, user_pattern_file: tuple[Path, dict], run_hook
):
    """
    Repo-specific .worktreeinclude should override user-wide ~/.worktreeinclude.
    """
    pattern_path, env = user_pattern_file

    # User-wide pattern would include json files.
    pattern_path.write_text(".env\n*.local.json\n")

    # Repo-specific pattern includes only .env.
    (git_repo / ".worktreeinclude").write_text(".env\n")
    pytest.create_test_files(git_repo, {"README.md": "Test"})
    pytest.commit_all(git_repo)

    pytest.create_test_files(
        git_repo,
        {
            ".env": "SECRET=value",
            "app.local.json": '{"k":"v"}',
        },
    )

    worktree_path = git_repo.parent / "test-wt-override"
    _create_worktree_without_hooks(git_repo, worktree_path, "feature-override", env=env)
    assert run_hook(worktree_path, git_repo) == 0

    assert (worktree_path / ".env").exists()
    assert not (worktree_path / "app.local.json").exists()


def test_no_overwrites_safety(git_repo: Path, user_pattern_file: tuple[Path, dict], run_hook):
    """
    Hook must never overwrite existing files in destination worktree.
    """
    pattern_path, env = user_pattern_file
    pattern_path.write_text(".env\n")

    pytest.create_test_files(git_repo, {"README.md": "Test"})
    pytest.commit_all(git_repo)

    pytest.create_test_files(git_repo, {".env": "ORIGINAL=from-main"})

    worktree_path = git_repo.parent / "test-wt-safety"
    _create_worktree_without_hooks(git_repo, worktree_path, "feature-safety", env=env)

    (worktree_path / ".env").write_text("MODIFIED=in-worktree\nUSER_CHANGE=important")
    assert run_hook(worktree_path, git_repo) == 0

    env_content = (worktree_path / ".env").read_text()
    assert "MODIFIED=in-worktree" in env_content
    assert "USER_CHANGE=important" in env_content


def test_no_pattern_file_skips_copying(git_repo: Path, run_hook):
    """
    Hook should no-op when no repo or user pattern file exists.
    """
    pytest.create_test_files(git_repo, {"README.md": "Test"})
    pytest.commit_all(git_repo)

    pytest.create_test_files(git_repo, {".env": "SECRET=value"})

    worktree_path = git_repo.parent / "test-wt-nopattern"
    _create_worktree_without_hooks(git_repo, worktree_path, "feature-nopattern")

    result = run_hook(worktree_path, git_repo)
    assert not (worktree_path / ".env").exists()
    assert result == 0


def test_copies_from_invoking_worktree_not_main(
    git_repo: Path, user_pattern_file: tuple[Path, dict], run_hook
):
    """
    Files should copy from invoking worktree, not always main worktree.
    """
    pattern_path, env = user_pattern_file
    pattern_path.write_text(".env\n")

    # Main has no .env.
    pytest.create_test_files(git_repo, {"README.md": "Main"})
    pytest.commit_all(git_repo)

    # Create worktree A from main.
    worktree_a = git_repo.parent / "test-wt-source-a"
    _create_worktree_without_hooks(git_repo, worktree_a, "feature-source-a", env=env)

    # Local file exists only in A.
    (worktree_a / ".env").write_text("SECRET=from-worktree-a")

    # Create worktree B and invoke hook as if A was detected as source.
    worktree_b = git_repo.parent / "test-wt-source-b"
    _create_worktree_without_hooks(git_repo, worktree_b, "feature-source-b", env=env)
    assert run_hook(worktree_b, worktree_a) == 0

    assert (worktree_b / ".env").exists(), "Expected copy from invoking worktree A"
    assert "from-worktree-a" in (worktree_b / ".env").read_text()
    assert not (git_repo / ".env").exists(), "Main should still not have .env"


def test_uses_git_worktree_source_env_for_copy_and_logs_method(
    git_repo: Path, user_pattern_file: tuple[Path, dict]
):
    """
    With GIT_WORKTREE_SOURCE set, hook should copy from that worktree and log method.
    """
    pattern_path, env = user_pattern_file
    pattern_path.write_text(".env\n")

    # Main has no .env.
    pytest.create_test_files(git_repo, {"README.md": "Main"})
    pytest.commit_all(git_repo)

    # Create source worktree A and add local-only file.
    worktree_a = git_repo.parent / "test-wt-env-source-a"
    _create_worktree_without_hooks(git_repo, worktree_a, "feature-env-source-a", env=env)
    (worktree_a / ".env").write_text("SECRET=from-env-source-worktree")

    # Create destination worktree B via real hook path, explicitly setting source.
    worktree_b = git_repo.parent / "test-wt-env-source-b"
    env_with_source = env.copy()
    env_with_source["GIT_WORKTREE_SOURCE"] = str(worktree_a)
    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_b), "-b", "feature-env-source-b"],
        cwd=git_repo,
        env=env_with_source,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (worktree_b / ".env").exists(), "Expected copy from GIT_WORKTREE_SOURCE worktree"
    assert "from-env-source-worktree" in (worktree_b / ".env").read_text()
    assert "Info: Source worktree detection method: GIT_WORKTREE_SOURCE" in result.stderr
    assert not (git_repo / ".env").exists(), "Main should still not have .env"


def test_pattern_negation(git_repo: Path, run_hook):
    """
    Simple negation pattern should exclude explicitly negated file.
    """
    (git_repo / ".worktreeinclude").write_text("*.local.json\n!exclude.local.json\n")
    pytest.create_test_files(git_repo, {"README.md": "Test"})
    pytest.commit_all(git_repo)

    pytest.create_test_files(
        git_repo,
        {
            "app.local.json": '{"ok":true}',
            "exclude.local.json": '{"skip":true}',
        },
    )

    worktree_path = git_repo.parent / "test-wt-negation"
    _create_worktree_without_hooks(git_repo, worktree_path, "feature-negation")
    assert run_hook(worktree_path, git_repo) == 0

    assert (worktree_path / "app.local.json").exists()
    assert not (worktree_path / "exclude.local.json").exists()


def test_rejects_symlink_source_file(git_repo: Path, run_hook, capsys):
    """
    Symlinked source files must be rejected to prevent out-of-tree copying.
    """
    (git_repo / ".worktreeinclude").write_text(".env\n")
    pytest.create_test_files(git_repo, {"README.md": "Test"})
    pytest.commit_all(git_repo)

    # Keep secret outside repo to simulate sensitive local file.
    secret_file = git_repo.parent / "secret-outside-repo.txt"
    secret_file.write_text("TOP_SECRET")

    source_link = git_repo / ".env"
    try:
        source_link.symlink_to(secret_file)
    except OSError as exc:
        pytest.skip(f"Symlink creation is not supported in this environment: {exc}")

    worktree_path = git_repo.parent / "test-wt-symlink-reject"
    _create_worktree_without_hooks(git_repo, worktree_path, "feature-symlink-reject")
    assert run_hook(worktree_path, git_repo) == 0

    captured = capsys.readouterr()
    assert not (worktree_path / ".env").exists()
    assert "Skipping symlink source" in captured.err


@pytest.mark.e2e
def test_hook_smoke_via_git_worktree_add(git_repo: Path, user_pattern_file: tuple[Path, dict]):
    """
    Smoke test for real hook integration path through `git worktree add`.
    """
    pattern_path, env = user_pattern_file
    pattern_path.write_text(".env\n")

    pytest.create_test_files(git_repo, {"README.md": "Main"})
    pytest.commit_all(git_repo)
    pytest.create_test_files(git_repo, {".env": "SECRET=from-main"})

    worktree_path = git_repo.parent / "test-wt-smoke"
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "-b", "feature-smoke"],
        cwd=git_repo,
        env=env,
        check=True,
        capture_output=True,
    )

    assert (worktree_path / ".env").exists()
    assert "from-main" in (worktree_path / ".env").read_text()
