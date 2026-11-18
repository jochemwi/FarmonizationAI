clean:
	sudo rm -rf output/* workspace/*

run: clean
	docker compose up -d --build
	docker compose exec harness python -m src.sync_embeddings
	docker compose exec harness python -m src.main

test:
	docker compose up -d
	docker compose exec harness python -m pytest tests/

test-fast:
	docker compose up -d
	docker compose exec harness python -m pytest tests/ -m "not slow"

.PHONY: obs
OBS_LABEL = $(or $(LABEL),Run)
obs:
	@mkdir -p observability
	@export $$(grep -E "^LANGFUSE_" .env | tr -d "\r" | xargs) && \
		python3 VibeCoded/fetch_trace.py $(if $(TRACE),--trace-id $(TRACE),--latest) -o observability/run_$(OBS_LABEL).json && \
		python3 VibeCoded/trace_actions.py observability/run_$(OBS_LABEL).json --label "$(OBS_LABEL)" -o observability/actions_$(OBS_LABEL).json && \
		python3 VibeCoded/build_viewer.py observability/actions_*.json -o observability/viewer.html
	@$(if $(NOOPEN),:,explorer.exe "$$(wslpath -w observability/viewer.html)") || true
