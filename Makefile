clean:
	rm -rf output/* data/* __pycache__ .pytest_cache

run: clean
	docker compose up -d
	docker compose exec harness python -m src.main

test:
	docker compose up -d
	docker compose exec harness python -m pytest tests/

test-fast:
	docker compose up -d
	docker compose exec harness python -m pytest tests/ -m "not slow"