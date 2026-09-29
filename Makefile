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

messy:
	docker compose -f docker-compose.yml -f docker-compose.benchmark.yml up