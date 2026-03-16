# git-hooks-toolbox

Cross-platform git hooks for Octopus Deploy developer workflows.

## Setup

```bash
git clone https://github.com/OctopusDeploy/git-hooks-toolbox ~/Dev/Octo/git-hooks-toolbox
git config --global core.hooksPath ~/Dev/Octo/git-hooks-toolbox
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
