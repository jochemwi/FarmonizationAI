# Benchmark settings (override on the command line)
CONFIG ?= icasa
MODEL  ?= openai:gpt-5.6-sol

# exported so docker compose and evaluate.py see the same values
export FARMONIZER_CONFIG = $(CONFIG)
export FARMONIZER_MODEL  = $(MODEL)

COMPOSE_BENCH = -f docker-compose.yml -f docker-compose.benchmark.yml

ifeq ($(CONFIG),base)
COMPOSE_FILES = $(COMPOSE_BENCH)
else ifeq ($(CONFIG),icasa)
COMPOSE_FILES = $(COMPOSE_BENCH) -f docker-compose.icasa.yml
else
$(error CONFIG '$(CONFIG)' is not runnable yet, use base or icasa)
endif

# Normal development
clean:
	sudo rm -rf output/* workspace/*

run: clean
	docker compose up -d
	docker compose exec harness python -m src.main

test:
	docker compose up -d
	docker compose exec harness python -m pytest tests/

test-fast:
	docker compose up -d
	docker compose exec harness python -m pytest tests/ -m "not slow"

# Generate the (seeded) benchmark data once per batch
bench-prep:
	rm -f benchmark/ground_truth.xlsx benchmark/data/synthetic_messy.xlsx
	python benchmark/scripts/generate_ground_truth.py
	python benchmark/scripts/corrupt_dataset.py

# One run of one config with one model, then score and log it
bench-run:
	rm -f benchmark/output/*.xlsx
	docker compose $(COMPOSE_FILES) run --rm --no-deps --entrypoint "" harness sh -c 'rm -rf /app/workspace/*'
	docker compose $(COMPOSE_FILES) up --abort-on-container-exit --exit-code-from harness
	python benchmark/scripts/evaluate.py

# 5 repeats x 2 models x 2 configs = 20 runs, repeats in the outer loop
bench-all: bench-prep
	for i in 1 2 3 4 5; do \
	  for model in openai:gpt-5.6-luna openai:gpt-5.6-sol; do \
	    for cfg in base icasa; do \
	      $(MAKE) bench-run CONFIG=$$cfg MODEL=$$model || true; \
	    done; \
	  done; \
	done