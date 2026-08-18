.PHONY: sync quality test up down seed reset smoke
sync:
	uv sync
quality:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy apps packages
test:
	uv run pytest -q
up:
	docker compose up -d --build
down:
	docker compose down
seed:
	uv run python scripts/seed.py
reset:
	uv run python scripts/reset_local.py
smoke:
	uv run python scripts/smoke_test.py

