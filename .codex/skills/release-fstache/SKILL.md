---
name: release-fstache
description: Release the standalone fstache package to PyPI from the local repository by bumping the version, committing, pushing main, tagging, watching GitHub Actions, verifying PyPI, and reporting the result. Use when asked to publish, release, slice, or cut a new fstache version.
---

# Release Fstache

Use this skill only from the repository root of the standalone `fstache` checkout.
It is meant for real PyPI releases through the repo's tag-triggered GitHub Actions
workflow.

## Command

For the default patch bump:

```bash
uv run python .codex/skills/release-fstache/scripts/release.py
```

For an exact version:

```bash
uv run python .codex/skills/release-fstache/scripts/release.py 2.0.0
```

For an explicit semantic bump:

```bash
uv run python .codex/skills/release-fstache/scripts/release.py --bump minor
```

## Required Behavior

The script enforces the release preconditions:

- Current branch must be `main`.
- Working tree must be clean before the bump.
- Local `main` must match `origin/main` after fetching.
- `.github/workflows/publish.yml` must exist.
- The target `vX.Y.Z` tag must not already exist locally or remotely.

The script performs the release:

- Reads the current version from `pyproject.toml`.
- Computes the next patch version unless the user supplied an exact `X.Y.Z`
  version or an explicit `--bump`.
- Updates `pyproject.toml` and `uv.lock` with `uv version`.
- Runs `make post-ai-change`.
- Builds release artifacts with `uv build`.
- Commits `pyproject.toml` and `uv.lock` as `Release X.Y.Z`.
- Pushes `main`, creates `vX.Y.Z`, and pushes the tag.
- Watches the tag-triggered `publish.yml` GitHub Actions run.
- Polls PyPI JSON and verifies installation with `uv run --no-project --refresh
  --with fstache==X.Y.Z`.
- Prints a final release report.

If the script refuses to run because the checkout is dirty, on the wrong branch,
behind/ahead of `origin/main`, or the tag already exists, stop and report that
condition. Do not clean, reset, move, delete, or recreate tags unless the user
explicitly asks for that recovery.

If the GitHub Actions publish run fails after the tag was pushed, report the run
URL and failure. Do not try to overwrite the PyPI release or retag the same
version.
