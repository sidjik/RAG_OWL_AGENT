.PHONY: sync test lint hooks pre-commit demo qdrant

sync:
	uv sync --locked

test:
	uv run pytest -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

hooks:
	uv run pre-commit install

pre-commit:
	uv run pre-commit run --all-files

demo:
	uv run owl-inspect examples/ontologies/minimal.owl --entity Hardware

qdrant:
	docker compose up -d qdrant
