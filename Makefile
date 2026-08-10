.DEFAULT_GOAL := help

UV ?= uv
HOST ?= 127.0.0.1
PORT ?= 8091

.PHONY: help sync run test frontend-test up down integration e2e

help:
	@printf '%s\n' \
		'make sync           Install or update backend dependencies' \
		'make run            Start the backend with auto-reload' \
		'make test           Run the backend test suite' \
		'make frontend-test  Run the frontend unit tests' \
		'make up             Build and start the docker compose stack' \
		'make down           Stop the stack and drop its database volume' \
		'make integration    Run the integration tests against the running stack' \
		'make e2e            Run the Playwright tests against docker compose'

sync:
	$(UV) sync --project backend

run:
	$(UV) run --project backend uvicorn backend.main:app --reload --host $(HOST) --port $(PORT)

test:
	$(UV) run --project backend pytest backend/tests

frontend-test:
	cd frontend && npm install && npm test

up:
	docker compose up -d --build --wait

down:
	docker compose down -v

# Expects the stack to be running - `make up` first, or point it elsewhere with
# SDIP_BASE_URL=https://interviews.example.com.
integration:
	$(UV) run --project integration pytest integration/tests

e2e:
	cd e2e && npm install && npx playwright install chromium && npm test
