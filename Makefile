MUTMUT_MAX_CHILDREN ?= 8

.PHONY: \
	build-html \
	format \
	lint \
	mutation-test-renderer \
	post-ai-change \
	perf-test \
	test

build-html:
	uv run --extra dev python demo/main.py

format:
	uv run --extra dev ruff check . --fix
	uv run --extra dev ruff format .

lint:
	uv run --extra dev ruff check .
	uv run --extra dev ruff format --check .
	uv run --extra dev ty check ./src/fstache

mutation-test-renderer:
	rm -rf mutants/
	uv run --extra dev mutmut run --max-children $(MUTMUT_MAX_CHILDREN)
	uv run --extra dev mutmut results

post-ai-change: format
post-ai-change: lint
post-ai-change: test
post-ai-change: build-html

perf-test:
	uv run --extra dev python tests/perf_test.py

test:
	uv run --extra dev pytest tests/
