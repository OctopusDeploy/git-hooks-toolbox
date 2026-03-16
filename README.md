# git-hooks-toolbox

Cross-platform git hooks for Octopus Deploy developer workflows.

## Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

> **Windows:** Ensure `python3` (or `python`) is on your PATH in Git Bash. The hook bootstraps
> its own dependencies via `uv` automatically.

## Setup

```bash
git clone https://github.com/OctopusDeploy/git-hooks-toolbox ~/.git-hooks-toolbox
git config --global core.hooksPath ~/.git-hooks-toolbox
```

## Updating

```bash
git -C ~/.git-hooks-toolbox pull
```

## Hooks

### `post-checkout`

Automatically copies local files from source worktree to newly created worktrees.

- Runs on `git worktree add`.
- Copies matching local files from source worktree to new worktree.
- Uses patterns from repo `.worktreeinclude` or fallback `~/.worktreeinclude`.
- Never overwrites existing files.

See `example.worktreeinclude` for pattern file examples.

## Development

Run tests:

```bash
uv run --extra test pytest tests -q
```
