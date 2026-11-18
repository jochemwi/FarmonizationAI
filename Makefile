CONFIG ?= icasa
include configs/$(CONFIG).env
export CONFIG PLAYBOOK EMBEDDINGS

clean:
	sudo rm -rf output/* workspace/*

snapshot:
	mkdir -p memory_snapshots/$(CONFIG)
	docker compose build snapshot
	docker compose run --rm snapshot

run: clean snapshot
	docker compose up -d --build
	docker compose exec harness python -m src.main

test:
	mkdir -p memory_snapshots/$(CONFIG)
	docker compose up -d
	docker compose exec harness python -m pytest tests/

test-fast:
	mkdir -p memory_snapshots/$(CONFIG)
	docker compose up -d
	docker compose exec harness python -m pytest tests/ -m"not slow"