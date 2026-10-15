# delay-stats-analysis. Targets mirror CLAUDE.md "Commands".
# Stubs exit 1 with the phase that implements them, so nothing silently "succeeds".

SHELL := /bin/sh

define not_implemented
	@echo "make $@: not implemented (BUILD_PLAN $(1))" >&2; exit 1
endef

.PHONY: setup lint typecheck test ingest tf-apply teardown crawl cost-compare notebooks memo-pdf

setup:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy src

test:
	uv run pytest -q

ingest tf-apply crawl:
	$(call not_implemented,Phase 1)

cost-compare:
	$(call not_implemented,Phase 2)

notebooks:
	$(call not_implemented,Phase 4)

memo-pdf:
	$(call not_implemented,Phase 5)

teardown:
	$(call not_implemented,Phase 7)
