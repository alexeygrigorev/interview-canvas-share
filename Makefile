.DEFAULT_GOAL := help

UV ?= uv
HOST ?= 127.0.0.1
PORT ?= 8091

.PHONY: help sync run test

help:
	@printf '%s\n' \
		'make sync  Install or update backend dependencies' \
		'make run   Start the backend with auto-reload' \
		'make test  Run the backend test suite'

sync:
	$(UV) sync --project backend

run:
	$(UV) run --project backend uvicorn backend.main:app --reload --host $(HOST) --port $(PORT)

test:
	$(UV) run --project backend pytest backend/tests
