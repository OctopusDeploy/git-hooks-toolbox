# git-hooks-toolbox

Seamless, non-intrusive git hooks for worktree-heavy workflows.

Works out of the box — no changes to your existing `git worktree` commands. AI tools like Claude Code and Codex use normal git operations and benefit automatically. Supports macOS and Windows.

## Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Setup

```bash
git clone https://github.com/OctopusDeploy/git-hooks-toolbox ~/.git-hooks-toolbox
git config --global core.hooksPath ~/.git-hooks-toolbox
```

## Updating

```bash
git -C ~/.git-hooks-toolbox pull
```

## Configuration

Hooks use a `.worktreeinclude` file (gitignore syntax) to determine which local files to copy when creating a new worktree.

**Priority order:**

1. `.worktreeinclude` in the repo root (checked in or local)
2. `~/.worktreeinclude` (user-wide fallback)

See [`example.worktreeinclude`](./example.worktreeinclude) for common patterns (`.env`, `appsettings.Local.json`, Terraform vars, etc.).

**Override source worktree** (optional):

If automatic source detection doesn't pick the right worktree, set `GIT_WORKTREE_SOURCE` to the path of the worktree to copy from:

```bash
GIT_WORKTREE_SOURCE=/path/to/source git worktree add ../my-branch
```

**AI tools (Claude Code, Codex, etc.):**

AI agents invoke git from subprocesses, which breaks the process ancestry detection. Add the following to your `CLAUDE.md` or `AGENTS.md` so the agent always passes the correct source worktree:

```
When creating git worktrees, always prefix the command with GIT_WORKTREE_SOURCE="$PWD":

GIT_WORKTREE_SOURCE="$PWD" git worktree add ../<branch> -b <branch> main
```

## Hooks

### `post-checkout`

Automatically copies local files from the source worktree to a newly created worktree.

- Triggers on `git worktree add`
- Detects the source worktree automatically (by process ancestry, then by most recently modified matching file, then falls back to main worktree)
- Never overwrites existing files in the destination
- Skips gracefully when no pattern file is found

Also regenerates [rulesync](https://github.com/dyoshikawa/rulesync) outputs on branch/worktree checkout — see below.

### `post-merge`, `post-rewrite`

Regenerate rulesync outputs after `git pull`, `git merge`, `git rebase`, or `git commit --amend`. Same logic as `post-checkout`'s rulesync block.

### Rulesync regeneration

When a repo contains `rulesync.jsonc`, the hooks run `npx rulesync generate` to refresh editor-specific outputs (`CLAUDE.md`, `.cursor/`, `.github/copilot-instructions.md`, …) on every HEAD-moving git operation.

- **Auto opt-in:** only fires when `rulesync.jsonc` is present at the repo root. Repos without it are unaffected.
- **Idempotent:** compares `.rulesync/rules/*.md` mtimes against `.rulesync/.last-regenerated`; no-op when outputs are already fresh.
- **Non-blocking:** any failure (missing `npx`, generate error) prints to stderr but exits 0 — git operations never break.

Requires `npx` (Node.js) on PATH. Install rulesync via `npm install -g rulesync` or rely on `npx`'s package cache.

## Development

```bash
uv run --extra test pytest tests -q
```
