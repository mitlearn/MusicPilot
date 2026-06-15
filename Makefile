.PHONY: install test lint dev smoke

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install -e ".[dev]"

test:
	.venv/bin/python -m pytest tests

lint:
	.venv/bin/python -m ruff check musicpilot tests

dev:
	.venv/bin/uvicorn musicpilot.infra.api.app:create_app --factory --reload

smoke:
	.venv/bin/python -m compileall musicpilot tests
	.venv/bin/python -m pytest tests
	.venv/bin/python -m ruff check musicpilot tests
