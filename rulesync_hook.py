"""
Shared rulesync regeneration logic for git hooks.

Mirrors the staleness check used by Claude Code's session-start hook so that
generated outputs (CLAUDE.md, .cursor/, etc.) stay in sync with the rule
sources whenever git rewrites the working tree.

Triggered from post-checkout, post-merge, and post-rewrite. Auto-opt-in: only
runs when `rulesync.jsonc` exists at the repo root, so teammates without
rulesync feel nothing.

Never raises — git hooks must not break git operations. Errors go to stderr
and the hook exits 0.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def regenerate_if_needed(repo_root: Path) -> None:
    """Regenerate rulesync outputs when sources are newer than the last regen.

    Gates (cheap → expensive):
    1. `rulesync.jsonc` exists in repo_root (auto opt-in).
    2. `npx` is on PATH (rulesync ships via npm).
    3. CLAUDE.md missing OR any `.rulesync/rules/*.md` newer than
       `.rulesync/.last-regenerated`.

    Idempotent: if nothing changed since the last regen, this is a no-op.
    """
    if not (repo_root / "rulesync.jsonc").is_file():
        return

    if not _needs_regen(repo_root):
        return

    npx = shutil.which("npx")
    if not npx:
        print(
            "[rulesync] npx not on PATH, skipping regeneration",
            file=sys.stderr,
        )
        return

    try:
        result = subprocess.run(
            [npx, "rulesync", "generate"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("[rulesync] generate timed out after 120s, skipping", file=sys.stderr)
        return
    except OSError as exc:
        print(f"[rulesync] failed to invoke npx: {exc}", file=sys.stderr)
        return

    if result.returncode != 0:
        # Print the tail of stderr so users can see what went wrong.
        tail = result.stderr.strip().splitlines()[-5:] if result.stderr else []
        print("[rulesync] generate failed:", file=sys.stderr)
        for line in tail:
            print(f"  {line}", file=sys.stderr)
        return

    _touch(repo_root / ".rulesync" / ".last-regenerated")
    print("[rulesync] regenerated")


def repo_root_from_cwd() -> Path | None:
    """Resolve the current repo's top-level directory, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    path = result.stdout.strip()
    return Path(path) if path else None


def _needs_regen(repo_root: Path) -> bool:
    if not (repo_root / "CLAUDE.md").exists():
        return True

    marker = repo_root / ".rulesync" / ".last-regenerated"
    rules_dir = repo_root / ".rulesync" / "rules"

    if not marker.exists():
        # No marker yet — regenerate if any rule sources exist to generate from.
        return rules_dir.is_dir() and any(rules_dir.glob("*.md"))

    marker_mtime = marker.stat().st_mtime
    if not rules_dir.is_dir():
        return False

    for rule in rules_dir.glob("*.md"):
        try:
            if rule.stat().st_mtime > marker_mtime:
                return True
        except OSError:
            continue
    return False


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Path.touch(exist_ok=True) bumps mtime even when the file already exists.
    path.touch(exist_ok=True)
