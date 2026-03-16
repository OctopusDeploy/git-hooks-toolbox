# Tests

Run from repo root:

```bash
uv run --project git-hooks --extra test pytest git-hooks/tests -q
```

GitHub Actions:
- Tests run on Linux, macOS, and Windows via `.github/workflows/git-hooks-tests.yml`.

What is covered:
- Source detection copies from invoking worktree (not always main).
- Fallback/no-pattern behavior is non-fatal.
- Safety: existing files are not overwritten.
- Pattern behavior: repo override and simple negation.
