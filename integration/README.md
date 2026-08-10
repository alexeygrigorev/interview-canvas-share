# Integration tests

Tests that drive a *running* deployment over the network — the built image, the
frontend bundle it serves, PostgreSQL, and the WebSocket gateway. Nothing here
imports the backend package, so the suite only ever sees what the stack
publishes, exactly as a browser or another service would.

They sit between the two suites either side of them: `backend/tests` exercises
the application in-process with a temporary database, and `e2e/` drives the same
deployment through a real browser. This one covers the wiring in between, and
fails with an HTTP status rather than a screenshot when that wiring breaks.

| File | Covers |
| --- | --- |
| `test_deployment.py` | `/health`, the SPA shell and its bundled assets, the SPA fallback, JSON 404s for API typos, the OpenAPI document |
| `test_auth.py` | Login against the seeded demo user, bad credentials, `/v1/me` |
| `test_session_lifecycle.py` | Create, list, read, `draft → live → ended → archived`, settings round-tripping through the database |
| `test_guest_flow.py` | Guest links, unauthenticated token inspection, joining, the guest cookie, revocation, a candidate edit the owner can read back |
| `test_realtime.py` | WebSocket fan-out between two clients, REST saves broadcast to the room, lifecycle events, rejection of unauthenticated connections |

## Run

The stack must already be up — the suite starts nothing itself:

```sh
make up            # docker compose up -d --build --wait
make integration
make down
```

Or directly, which is what the Makefile target does:

```sh
uv run --project integration pytest integration/tests
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SDIP_BASE_URL` | `http://localhost:$APP_PORT` | Target any deployment, local or remote |
| `APP_PORT` | `8100` | Host port the compose stack publishes |
| `SDIP_STARTUP_TIMEOUT` | `180` | Seconds to wait for `/health` before failing the run |

Every test creates its own session and tags its data with a random marker, so
runs never collide with each other or with the seeded demo data. Nothing is
cleaned up afterwards: the sessions are cheap, and leaving them behind keeps a
failed run inspectable. `make down` drops the volume when you want a clean slate.

Pointing `SDIP_BASE_URL` at a shared environment writes real sessions into it —
the suite logs in as the seeded `avery@northwind.dev`, so a deployment without
the demo seed data will fail at the first fixture.
