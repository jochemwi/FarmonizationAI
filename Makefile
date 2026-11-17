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