.PHONY: install dev test eval seed docker lint format
install:
	python -m pip install -e ".[dev]"
	cd frontend && npm ci --ignore-scripts
dev:
	python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
test:
	python -m pytest -q
eval:
	python scripts/evaluate.py
seed:
	python scripts/seed_demo_data.py
docker:
	docker compose up --build
lint:
	python -m ruff check backend evals scripts
	cd frontend && npm run lint
format:
	python -m ruff format backend evals scripts
	cd frontend && npm run format
