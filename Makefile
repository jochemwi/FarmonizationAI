CONFIG ?= icasa
include configs/$(CONFIG).env
export CONFIG PLAYBOOK EMBEDDINGS

clean:
	sudo rm -rf output/* workspace/*

snapshot:
	mkdir -p memory_snapshots/$(CONFIG)
	docker compose build snapshot
	docker compose run --rm snapshot

ARCHIVE_DIR := runs/$(CONFIG)_$(shell date +%Y%m%d_%H%M%S)

archive:
	mkdir -p $(ARCHIVE_DIR)
	cp -r output/submission output/run_info.json $(ARCHIVE_DIR)/
	-cp output/questions.json output/playbook_proposals.json $(ARCHIVE_DIR)/
	-cp memory_snapshots/$(CONFIG)/playbook.json $(ARCHIVE_DIR)/playbook_used.json
	@echo "archived to $(ARCHIVE_DIR)"

run: clean snapshot
	docker compose build harness
	docker compose up -d --no-build
	docker compose exec harness python -m src.main
	$(MAKE) archive

test:
	mkdir -p memory_snapshots/$(CONFIG)
	docker compose up -d
	docker compose exec harness python -m pytest tests/

test-fast:
	mkdir -p memory_snapshots/$(CONFIG)
	docker compose up -d
	docker compose exec harness python -m pytest tests/ -m"not slow"