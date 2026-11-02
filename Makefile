# Benchmark settings (override on the command line)
CONFIG ?= base
MODEL  ?= openai:gpt-5.6-sol

# exported so docker compose sees the same values
export FARMONIZER_CONFIG = $(CONFIG)
export FARMONIZER_MODEL  = $(MODEL)

COMPOSE_BENCH = -f docker-compose.yml -f docker-compose.benchmark.yml

ifeq ($(CONFIG),base)
COMPOSE_FILES = $(COMPOSE_BENCH)
else ifeq ($(CONFIG),storage)
COMPOSE_FILES = $(COMPOSE_BENCH) -f docker-compose.storage.yml
else
$(error CONFIG '$(CONFIG)' is not runnable yet, use base or storage)
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

# One run of one config with one model (scoring happens in the bundle, outside the repo)
bench-run:
	docker compose $(COMPOSE_FILES) run --rm --no-deps --entrypoint "" harness sh -c 'rm -rf /app/workspace/* /app/output/*'
	docker compose $(COMPOSE_FILES) up --abort-on-container-exit --exit-code-from harness

# 5 repeats x 2 models x 2 configs = 20 runs, repeats in the outer loop
bench-all:
	for i in 1 2 3 4 5; do \
	  for model in openai:gpt-5.6-luna openai:gpt-5.6-sol; do \
	    for cfg in base storage; do \
	      $(MAKE) bench-run CONFIG=$$cfg MODEL=$$model || true; \
	    done; \
	  done; \
	done
