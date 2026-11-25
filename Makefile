.PHONY: all ingest validate build-warehouse test lint clean help

PYTHON ?= python

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

all: ## Run the full pipeline: ingest → validate → build warehouse → export marts
	$(PYTHON) -m fleetsense.cli all

ingest: ## Download and verify raw data files
	$(PYTHON) -m fleetsense.cli ingest

validate: ## Validate raw data and quarantine bad rows
	$(PYTHON) -m fleetsense.cli validate

build-warehouse: ## Build DuckDB warehouse and export analytical marts
	$(PYTHON) -m fleetsense.cli build-warehouse

add-month: ## Ingest a single new month idempotently (usage: make add-month MONTH=2024-01)
	$(PYTHON) -m fleetsense.cli add-month --month $(MONTH)

test: ## Run all tests
	$(PYTHON) -m pytest tests/ -v

lint: ## Run ruff linter
	$(PYTHON) -m ruff check src/ tests/ app/

format: ## Auto-format code with ruff
	$(PYTHON) -m ruff format src/ tests/ app/

clean: ## Remove generated data (keeps reference/ and marts/)
	rm -rf data/raw/ data/quarantine/ data/warehouse/
	@echo "Cleaned raw, quarantine, and warehouse data."
