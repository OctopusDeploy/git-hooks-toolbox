"""Focused tests for source worktree detection fallback logic."""

import types
from importlib.machinery import SourceFileLoader
from pathlib import Path


def _load_hook_module() -> types.ModuleType:
    """Load git hook script as a Python module for direct function testing."""
    hook_path = Path(__file__).resolve().parents[1] / "post-checkout"
    loader = SourceFileLoader("post_checkout_hook", str(hook_path))
    module = types.ModuleType(loader.name)
    module.__file__ = str(hook_path)
    loader.exec_module(module)
    return module


def test_find_source_worktree_falls_back_to_main_when_process_detection_unavailable(monkeypatch):
    """If process detection is unavailable, source detection should return main worktree."""
    hook = _load_hook_module()

    fake_common_dir = Path("/tmp/example-repo/.git") / "worktrees" / "wt-new"

    monkeypatch.setattr(hook, "PSUTIL_AVAILABLE", False)
    monkeypatch.setattr(hook, "_get_git_common_dir", lambda cwd=None: fake_common_dir)

    detected = hook.find_source_worktree()

    assert detected == fake_common_dir.parent
