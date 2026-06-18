.PHONY: install dev-setup test lint typecheck clean run

install:
	pip install -e ".[dev]"

dev-setup: install
	python scripts/setup_data.py

test:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

lint:
	ruff check .

typecheck:
	mypy .

clean:
	rm -rf data/olist.duckdb data/chroma/

run:
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
