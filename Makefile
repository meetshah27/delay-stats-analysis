# delay-stats-analysis. Targets mirror CLAUDE.md "Commands".
# Stubs exit 1 with the phase that implements them, so nothing silently "succeeds".
# Analysis targets run on DELAYSTATS_BACKEND=local (DuckDB over data/curated) by default and
# on Athena with DELAYSTATS_BACKEND=athena.

SHELL := /bin/sh
-include .env
ENV_KEYS := AWS_PROFILE AWS_REGION DELAYSTATS_BACKEND GLUE_DATABASE ATHENA_WORKGROUP
$(foreach key,$(ENV_KEYS),$(if $($(key)),$(eval export $(key))))

TF := terraform
YEARS ?= 2023,2024,2025,2026

define not_implemented
	@echo "make $@: not implemented (BUILD_PLAN $(1))" >&2; exit 1
endef

.PHONY: setup lint typecheck test ingest verify-counts tf-bootstrap tf-init tf-apply upload \
	crawl cost-compare drop-csv notebooks memo memo-pdf teardown

setup:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy src

test:
	uv run pytest -q

# Download (or --local-dir), validate headers, write typed Parquet to data/curated.
ingest:
	uv run python -m delaystats.ingest --years $(YEARS) $(if $(LOCAL_DIR),--local-dir $(LOCAL_DIR))

# Rows per month: source lines vs the table on the selected backend.
verify-counts:
	uv run python -m delaystats.storage verify-counts

# ---------------------------------------------------------------- AWS (free plan)

tf-bootstrap:
	cd infra/bootstrap && $(TF) init -input=false && $(TF) apply

tf-init:
	$(TF) -chdir=infra init -input=false -reconfigure \
		-backend-config=bucket=$$($(TF) -chdir=infra/bootstrap output -raw state_bucket) \
		-backend-config=dynamodb_table=$$($(TF) -chdir=infra/bootstrap output -raw lock_table) \
		-backend-config=region=$${AWS_REGION:-us-west-2}

tf-apply:
	$(TF) -chdir=infra apply

# Glue tables are declared in Terraform with explicit schemas and partition projection, so
# there is no crawler: this applies just the catalog.
crawl:
	$(TF) -chdir=infra apply -target=aws_glue_catalog_table.ontime -target=aws_glue_catalog_table.ontime_csv[0]

upload:
	uv run python -m delaystats.storage upload

# Athena bytes scanned and cost, raw CSV vs partitioned Parquet (needs the CSV landing data).
cost-compare:
	uv run python -m delaystats.cost_compare

# After cost-compare: remove the CSV table and its S3 prefix so they stop costing storage.
drop-csv:
	$(TF) -chdir=infra apply -var keep_csv_table=false
	aws s3 rm s3://$$($(TF) -chdir=infra output -raw bucket)/landing/csv/ --recursive --only-show-errors

# Every notebook, headless, top to bottom (no hidden state): fills reports/results.csv and
# reports/figures/.
notebooks:
	for nb in notebooks/0*.ipynb; do 		uv run jupyter nbconvert --to notebook --execute --inplace $$nb || exit 1; 	done

# Regenerate the memo's appendix tables, then fail if any memo number is untraceable.
memo:
	uv run python -m delaystats.build_appendix
	uv run python -m delaystats.check_memo_numbers

memo-pdf:
	$(call not_implemented,Phase 5)

teardown:
	$(call not_implemented,Phase 7)
