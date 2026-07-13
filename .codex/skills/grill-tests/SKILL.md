---
name: grill-tests
description: "Critically review and improve an existing test, test file, test directory, pytest node ID, or application package by removing redundant low-value coverage, strengthening behavior contracts, and validating the resulting suite. Use when the user asks to grill, audit, prune, consolidate, simplify, strengthen, or improve tests rather than merely add more tests."
---

# Grill Tests

Treat tests as a curated risk portfolio, not an append-only coverage target. Improve the
selected scope in place while preserving distinct, important behavior contracts.

## Core Standard

Require every retained test to justify its ownership cost:

1. Name a meaningful behavior, contract, regression class, boundary, or invariant.
2. Fail for a plausible defect that is not already detected clearly by another test.
3. Observe the most stable public surface that can faithfully expose that defect.

Strengthen, merge, replace, or delete a test that fails this standard. Do not optimize for
test count, line coverage, or a predetermined amount of deletion.

## Workflow

### 1. Resolve the target

- Accept a test path, directory, pytest node ID, production module, dotted package name, or
  named symbol.
- For a production target, find mirrored tests and tests that import or exercise it. Include
  adjacent integration coverage when it protects the same contracts.
- Ask for clarification only when multiple materially different targets remain plausible
  after searching the repository.
- Keep changes within the resolved test scope unless a nearby test must change to remove
  duplication. Do not change production code unless the user separately authorizes it.

### 2. Establish local truth

1. Inspect `git status --short` and preserve unrelated work.
2. Read every applicable `AGENTS.md`, including `tests/AGENTS.md` and narrower files.
3. Read the selected tests completely.
4. Read the production code and public contracts they exercise.
5. Search neighboring test layers for overlapping coverage, shared fixtures, and historical
   regression intent. Consult git history only when the purpose of a test is otherwise unclear.
6. Run the narrowest useful baseline test command and record pre-existing failures.

Do not judge a test from its name or assertions alone. Setup, fixtures, production behavior,
and coverage elsewhere determine its value.

### 3. Grill each test

Interrogate each test with these questions:

- What realistic defect or contract violation would this catch?
- Would a plausible wrong implementation still pass?
- Is it asserting behavior, or restating implementation structure and mock wiring?
- Does another test catch the same risk more directly or at a more faithful layer?
- Is every case materially distinct, or are inputs being multiplied without new risk?
- Does the assertion prove the outcome, including important negative effects, or merely that
  execution completed?
- Does the test make safe refactoring unnecessarily expensive?
- Is its setup, runtime, flakiness exposure, or readability disproportionate to its signal?

Classify each test internally as one of:

- `retain`: distinct, meaningful protection at an appropriate layer.
- `strengthen`: useful risk, but weak stimulus, oracle, boundary, or negative assertion.
- `merge`: useful risk obscured by redundant examples or setup.
- `replace`: important contract tested through the wrong surface or excessive mocking.
- `delete`: no distinct practical protection after considering the rest of the suite.

Use the classification to drive edits; do not add classification comments to test files.

### 4. Improve the portfolio

Prefer these transformations:

- Replace implementation-detail assertions with observable outcomes.
- Strengthen weak assertions so a plausible incorrect result cannot pass.
- Combine cases only when they protect the same risk and failures remain understandable.
- Remove a weaker test when a stronger test fully subsumes it.
- Reuse the nearest fixture instead of repeating elaborate setup.
- Reduce mocks that merely replay the implementation. Retain mocks at genuine boundaries and
  enforce collaborator contracts according to repository guidance.
- Prefer one focused invariant or property test over many examples only when the invariant is
  clear, the oracle is independent, and failure output remains actionable.
- Preserve separate tests for security, authorization, data integrity, destructive actions,
  externally consumed contracts, and historically costly regressions when they fail for
  meaningfully different reasons.
- Use behavior-focused test names. Let the test body demonstrate the contract.

Do not:

- Add cases merely to cover lines, branches, getters, constructors, framework behavior, or
  permutations without distinct risks.
- Duplicate lower-level parser, helper, cache, decorator, or deduplication coverage in broad
  orchestration tests.
- Weaken a contract just to reduce test volume or runtime.
- Reproduce production logic in the expected value.
- Introduce snapshots when focused semantic assertions express the contract better.
- Convert a discovered production defect into a skip, `xfail`, or weakened expectation.

If grilling exposes a likely production defect, verify the evidence, keep it separate from
test cleanup, and report it. Do not leave the suite failing or silently change application
behavior.

### 5. Validate the result

1. Run the focused tests after each coherent edit.
2. Inspect the diff for accidental production changes and loss of distinct contracts.
3. Run `make format` when test files changed.
4. Rerun the focused tests after formatting.
5. Run `make post-ai-change` before completion.

Treat fewer tests or faster execution as useful only when confidence is preserved or improved.
A green run proves compatibility with the current implementation; it does not by itself prove
that the tests are valuable.

## Final Report

Lead with the resulting test portfolio, then report:

- retained or strengthened risks and contracts;
- consolidated or deleted coverage and why it was redundant or weak;
- any production defect or unresolved ambiguity discovered;
- focused and full validation commands with results;
- before-and-after test counts or runtime only when measured reliably.

Be candid when the selected tests are already high-signal and should remain mostly unchanged.
