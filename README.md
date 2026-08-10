# System Design Interview Platform

A browser-based collaborative workspace for conducting live system-design
interviews. An interviewer creates a session and shares a link; candidates and
other interviewers join and work together on the same infinite canvas in real
time — placing architecture components, connecting them with arrows, adding
labels and notes, and drawing freehand. Edits are broadcast over WebSockets so
every participant sees updates immediately, and the final canvas is preserved
for later review.

- **Backend** — FastAPI (Python 3.12), SQLAlchemy over SQLite, JWT auth,
  WebSocket realtime updates. Lives in `backend/`.
- **Frontend** — TanStack Start / React + Vite. Lives in `frontend/`.
- **Spec** — `docs/spec.md`. **API contract** — `openapi.yaml`.

## Run with Docker

The `Dockerfile` is a two-stage build: the frontend is compiled with Node and
the resulting static bundle is copied into the Python image, so a single
container serves both the API and the UI.

### Build

From the repository root:

```sh
docker build -t sdip:latest .
```

### Run

```sh
docker run --rm -p 8000:8000 --name sdip sdip:latest
```

The app listens on port `8000` inside the container. Open
<http://localhost:8000> for the UI and <http://localhost:8000/docs> for the
interactive API documentation. If port 8000 is already taken on your machine,
map a different host port, for example `-p 8100:8000`.

To run it in the background and follow the logs:

```sh
docker run -d -p 8000:8000 --name sdip sdip:latest
docker logs -f sdip
docker rm -f sdip   # stop and remove
```

The seeded demo users (`avery@northwind.dev`, `jordan@northwind.dev`,
`priya@northwind.dev`) all use the password `demo-password`; log in through the
UI or with `POST /v1/auth/login`.

### Configuration

All settings are environment variables passed with `-e`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SDIP_DATABASE_URL` | `sqlite:///./sdip.db` | Any SQLAlchemy database URL |
| `SDIP_JWT_SECRET` | `local-development-secret-change-me` | JWT signing secret — **set this outside local development** |
| `SDIP_ACCESS_TOKEN_MINUTES` | `60` | Access token lifetime |
| `SDIP_CORS_ORIGINS` | localhost dev origins | Comma-separated allowed origins |
| `SDIP_STATIC_DIR` | `app/static` | Directory the frontend bundle is served from |

By default the SQLite database lives inside the container and disappears when
the container is removed. Mount a volume and point the database URL at it to
keep data between runs:

```sh
docker run --rm -p 8000:8000 \
  -v sdip-data:/data \
  -e SDIP_DATABASE_URL=sqlite:////data/sdip.db \
  -e SDIP_JWT_SECRET=change-me \
  --name sdip sdip:latest
```

Note the four slashes in `sqlite:////data/sdip.db` — that is an absolute path.

## Run locally without Docker

The backend uses [uv](https://docs.astral.sh/uv/) for dependency management:

```sh
make sync   # install backend dependencies
make run    # start the API with auto-reload on http://127.0.0.1:8091
make test   # run the backend test suite
```

Override the bind address with `make run HOST=0.0.0.0 PORT=8080`.

The frontend dev server runs separately:

```sh
cd frontend
npm install
npm run dev
```

See `backend/README.md` for more backend detail.
