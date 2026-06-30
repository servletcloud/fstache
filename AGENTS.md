# Repository Guidelines

## Project Structure & Module Organization
Library code lives in the `src/fstache/` package. Tests live in `tests/`, and
demo assets live in `demo/`.

Keep new runtime Python modules under `src/fstache/` rather than at the
repository root, and mirror that structure in tests where practical. Keep
benchmark and diagnostic code in `tests/perf_test.py` or another clearly named
test/diagnostic file rather than mixing it into the library package.

## Build, Test, and Development Commands
Use `uv` to manage the Python environment.

Prefer the `Makefile` targets for full-repo formatting and verification, and
use direct `uv run ...` commands for narrower checks.

- `make format` runs Ruff autofix and formatting.
- `make lint` runs Ruff checks and format verification.
- `make test` runs the Fstache test suite.
- `make build-html` renders the demo HTML output.
- `make perf-test` runs the renderer performance diagnostics.
- `make post-ai-change` runs formatting, linting, tests, and demo rendering; run
  it after code changes.

For targeted test work, prefer commands such as:

```bash
uv run --extra dev pytest tests/test_render_variables.py -k <pattern>
```

## Coding Style & Naming Conventions
- Target Python `3.12+`, as declared in `pyproject.toml` and `.python-version`.
- Naming: `snake_case` for functions, variables, and modules; `PascalCase` for
  classes; `UPPER_SNAKE_CASE` for constants.
- Prefer `typing.Final` for module-level constants, for example
  `_TAG_START: Final[bytes] = b"{{"`.
- Avoid hardcoding non-obvious numeric literals in logic. Use named constants
  with short human-readable comments for units or meaning.
- Write modules in a top-down order: public API and high-level code first,
  supporting helpers below it when practical.
- Avoid introducing tiny private helpers that are only 1-2 lines and used once
  unless they make the calling code meaningfully clearer.
- Prefer bounded iteration over open-ended loops when a reasonable safety cap
  exists.
- With Python 3.12+, prefer direct annotation syntax like `-> CompiledTemplate`
over quoted string-literal annotations.
- Prefer `match/case` over long `if`/`elif` chains when dispatching on a small
  closed set of variants and it clearly reduces nesting.
- Keep imports at the beginning of the file. Do not place imports inside
  functions, methods, or test cases.
- Prefer explicit member imports over module namespaces for frequently used
  types and functions.
- Group imports from the same package on a single line or in a parenthesized
  block to reduce vertical noise.
- Do not use `from __future__ import annotations`.
- Always add a blank line before any `return` statement, unless it is the only
  statement in the function or code block.

## Testing Guidelines
Add or update focused compiler/parser tests in `tests/test_compiler.py`. Use
`tests/test_mustache_specs.py` for upstream Mustache JSON spec parity, including
explicit exclusions for intentionally unsupported fixtures. Add or update local
render behavior tests in the most specific render or partial test file for
Fstache-specific regressions that the upstream specs do not cover.

When implementing Mustache behavior, prefer small spec-backed increments with
tests that describe the exact supported subset. If a feature is intentionally
unsupported, make the error behavior explicit in tests when practical.

Keep performance comparisons separate from correctness tests. Use
`make perf-test` only when the task involves renderer performance or regression
investigation.

## Commit & Pull Request Guidelines
Commit messages should use short, sentence-case summaries without prefixes, for
example `Add dynamic parent support`.

PRs should include a concise summary, the relevant test commands run, and any
known compatibility or performance risks.

## Security & Configuration Tips
Do not commit secrets, `.env` files, `.env.local`, service credentials, or
machine-local benchmark output.

Review dependency additions carefully. Keep runtime dependencies minimal for the
library package, and place test-only or benchmark-only dependencies under the
`dev` optional dependency group.

## Agent Maintenance
Treat this `AGENTS.md` file as living contributor guidance. Agents may update it
when a task reveals repository-specific workflow guidance that would make future
sessions faster, safer, or more consistent. Keep edits concise, practical, and
tied to this standalone Fstache repository.
