.DEFAULT_GOAL := help

UV ?= uv
HOST ?= 127.0.0.1
PORT ?= 8091

.PHONY: help sync run test e2e

help:
	@printf '%s\n' \
		'make sync  Install or update backend dependencies' \
		'make run   Start the backend with auto-reload' \
		'make test  Run the backend test suite' \
		'make e2e   Run the Playwright tests against docker compose'

sync:
	$(UV) sync --project backend

run:
	$(UV) run --project backend uvicorn backend.main:app --reload --host $(HOST) --port $(PORT)

test:
	$(UV) run --project backend pytest backend/tests

e2e:
	cd e2e && npm install && npx playwright install chromium && npm test
