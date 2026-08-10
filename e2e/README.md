# End-to-end tests

Playwright tests that drive the real deployment from `docker-compose.yaml` —
the built frontend, the FastAPI backend, the WebSocket gateway, and PostgreSQL.

`tests/realtime-canvas.spec.ts` covers the core collaboration loop with two
isolated browser contexts standing in for two people at two machines:

1. Log in as the interviewer (session 1, a seeded demo account).
2. Create an interview session.
3. Share the candidate join link.
4. Join from a second client as the candidate (session 2, a guest).
5. Change the canvas as the candidate.
6. Verify the interviewer sees the change — and that it survives a reload.

## Run

```sh
cd e2e
npm install
npx playwright install chromium   # once, downloads the browser
npm test
```

Playwright starts the stack itself (`docker compose up --build` from the
repository root) and stops it when the run ends. If something is already
listening on the app port, that deployment is reused instead — handy while
iterating, since the image is not rebuilt each time. Under `CI=1` an existing
server is never reused.

Useful variations:

```sh
npm test -- --headed        # watch both browsers work
npm test -- --debug         # step through with the inspector
npm run report              # open the HTML report from the last CI-style run
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_PORT` | `8100` | Host port the compose stack publishes, matching `docker-compose.yaml` |
| `E2E_BASE_URL` | `http://localhost:$APP_PORT` | Test an already-running deployment elsewhere |
| `E2E_EXTERNAL_STACK` | unset | Someone else owns the stack: do not start or stop it |
| `CI` | unset | Enables retries, the HTML report, and forbids reusing a running server |

Pointing `E2E_BASE_URL` at a remote deployment still runs the compose
`webServer` command locally unless that URL already answers — for a purely
remote target, set `E2E_EXTERNAL_STACK=1` as well, which drops the `webServer`
block entirely. That is what CI does: it brings the stack up once, runs the
integration suite against it, and then runs this one, so Playwright must not
start a second deployment on the same port.

## Notes on the fixtures

- The interviewer signs in as `avery@northwind.dev` / `demo-password`, one of
  the accounts seeded on first boot (`backend/app/store.py`). The token is
  fetched over the API and seeded into `sessionStorage`, which is where the SPA
  looks for it.
- The candidate never authenticates. It holds only the join link, and the
  backend identifies it by the guest cookie set at join time — so the two
  contexts must stay separate, which is Playwright's default.
- Assertions target the canvas SVG rather than the page as a whole: component
  labels also appear in the palette, and only the SVG proves the element was
  actually drawn.
- Each run creates its own session and tags the canvas node with a random
  marker, so runs do not interfere with each other or with seeded data.
