# System Design Interview Platform

A browser-based collaborative workspace for conducting live system-design
interviews. An interviewer creates a session and shares a link; candidates and
other interviewers join and work together on the same infinite canvas in real
time — placing architecture components, connecting them with arrows, adding
labels and notes, and drawing freehand. Edits are broadcast over WebSockets so
every participant sees updates immediately, and the final canvas is preserved
for later review.

- **Backend** — FastAPI (Python 3.12), SQLAlchemy over SQLite or PostgreSQL,
  JWT auth, WebSocket realtime updates. Lives in `backend/`.
- **Frontend** — TanStack Start / React + Vite. Lives in `frontend/`.
- **Spec** — `docs/spec.md`. **API contract** — `openapi.yaml`.
- **End-to-end tests** — Playwright against the compose stack. Lives in `e2e/`.

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
docker run --rm -p 8000:8000 \
  -v sdip-data:/data \
  -e SDIP_DATABASE_URL=sqlite:////data/sdip.db \
  --name sdip sdip:latest
```

The app listens on port `8000` inside the container. Open
<http://localhost:8000> for the UI and <http://localhost:8000/docs> for the
interactive API documentation. If port 8000 is already taken on your machine,
map a different host port, for example `-p 8100:8000`.

The `-v sdip-data:/data` flag keeps your data. It stores the SQLite database in
a named Docker volume outside the container, so sessions and canvases survive
restarts and you pick up where you left off every time you run the container.
Without it the database lives inside the container and is thrown away the
moment the container is removed, so every run starts from the seed data again.

Note the four slashes in `sqlite:////data/sdip.db` — that is an absolute path
to `/data/sdip.db`, the mounted volume. Three slashes would make it relative
and write inside the container instead.

The volume persists until you delete it explicitly. To inspect it or start over
from a clean database:

```sh
docker volume ls                # list volumes
docker volume rm sdip-data      # wipe the data and reseed on next run
```

To run it in the background and follow the logs:

```sh
docker run -d -p 8000:8000 \
  -v sdip-data:/data \
  -e SDIP_DATABASE_URL=sqlite:////data/sdip.db \
  --name sdip sdip:latest
docker logs -f sdip
docker rm -f sdip   # stop and remove (the volume survives)
```

The seeded demo users (`avery@northwind.dev`, `jordan@northwind.dev`,
`priya@northwind.dev`) all use the password `demo-password`; log in through the
UI or with `POST /v1/auth/login`.

### Run with Docker Compose

`docker-compose.yaml` wires the app to a PostgreSQL container so both start with
one command — the app waits for the database healthcheck before booting, then
creates its tables and seeds the demo data:

```sh
docker compose up --build
```

Open <http://localhost:8100>. Stop with `docker compose down`; add `-v` to wipe
the database and reseed on the next start.

The database is not published to the host — the app reaches it over the compose
network. Uncomment the `ports` block under `postgres` to connect with `psql`
from your machine.

Every value has a working default, so no `.env` file is required. Override any
of them in the environment or an `.env` file next to the compose file:

| Variable | Default |
| --- | --- |
| `APP_PORT` | `8100` — host port the UI and API are published on |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `sdip` |
| `SDIP_JWT_SECRET` | the local development secret — **set this outside local development** |

```sh
APP_PORT=9000 SDIP_JWT_SECRET=some-long-random-string docker compose up --build
```

### Run against PostgreSQL

SQLite is the zero-setup default; PostgreSQL is supported for anything with more
than one writer or a need to keep data outside the app. Start a database:

```sh
docker run -d \
  --name interview-canvas-db \
  -e POSTGRES_USER=sdip \
  -e POSTGRES_PASSWORD=sdip \
  -e POSTGRES_DB=sdip \
  -p 5432:5432 \
  -v interview-canvas-pgdata:/var/lib/postgresql/data \
  postgres:16-alpine
```

The app creates its tables and seeds the demo data on first start, so there is
no migration step. Put both containers on the same Docker network so the app can
reach the database by container name:

```sh
docker network create sdip-net
docker network connect sdip-net interview-canvas-db

docker run --rm -p 8000:8000 \
  --network sdip-net \
  -e SDIP_DATABASE_URL=postgresql://sdip:sdip@interview-canvas-db:5432/sdip \
  --name sdip sdip:latest
```

No `-v` is needed here — the data now lives in the database container's
`interview-canvas-pgdata` volume. Running outside Docker, point at the published
port instead:

```sh
SDIP_DATABASE_URL=postgresql://sdip:sdip@localhost:5432/sdip make run
```

`postgres://` and `postgresql://` URLs are both accepted and routed to the
installed psycopg 3 driver, so a URL copied from a hosted provider works as is.
To wipe the database and start over from the seed data:

```sh
docker rm -f interview-canvas-db
docker volume rm interview-canvas-pgdata
```

### Configuration

All settings are environment variables passed with `-e`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SDIP_DATABASE_URL` | `sqlite:///./sdip.db` | Any SQLAlchemy database URL — SQLite or PostgreSQL |
| `SDIP_JWT_SECRET` | `local-development-secret-change-me` | JWT signing secret — **set this outside local development** |
| `SDIP_ACCESS_TOKEN_MINUTES` | `60` | Access token lifetime |
| `SDIP_CORS_ORIGINS` | localhost dev origins | Comma-separated allowed origins |
| `SDIP_STATIC_DIR` | `app/static` | Directory the frontend bundle is served from |
| `SDIP_DB_POOL_SIZE` | `5` | PostgreSQL connection pool size (ignored on SQLite) |
| `SDIP_DB_MAX_OVERFLOW` | `10` | Extra PostgreSQL connections allowed under burst |
| `SDIP_DB_POOL_RECYCLE` | `1800` | Seconds before a pooled connection is reopened |

Set `SDIP_JWT_SECRET` to a real secret before running this anywhere but your
own machine:

```sh
docker run --rm -p 8000:8000 \
  -v sdip-data:/data \
  -e SDIP_DATABASE_URL=sqlite:////data/sdip.db \
  -e SDIP_JWT_SECRET=some-long-random-string \
  --name sdip sdip:latest
```

If you would rather keep the database as a plain file in the project directory
instead of a named volume, bind-mount a host directory:

```sh
docker run --rm -p 8000:8000 \
  -v "$(pwd)/data:/data" \
  -e SDIP_DATABASE_URL=sqlite:////data/sdip.db \
  --name sdip sdip:latest
```

## Deploy to AWS

`deploy/aws/sdip-stack.yaml` is a CloudFormation template that stands up the
whole thing on one EC2 instance: a VPC with a single public subnet, an Elastic
IP, a security group open only on 80 and 443, and an instance that clones this
repository on boot and starts `docker-compose.prod.yaml`. That compose file adds
[Caddy](https://caddyserver.com/) in front of the app, which obtains and renews
a Let's Encrypt certificate automatically and proxies HTTPS and WebSocket
traffic to the app container. Neither the app nor PostgreSQL is published to the
host, so Caddy's ports are the only way in.

One instance and one app container is a deliberate ceiling, not an oversight.
`ConnectionManager` in `backend/app/routers/realtime.py` holds WebSocket
connections in process memory, so a second replica would put participants of the
same interview into separate rooms — their edits would reach the database but
never each other. See *Scaling past one instance* below.

### What you need first

- A domain you can add an A record to.
- AWS credentials with permission to create VPC, EC2, and IAM resources.
- This repository reachable over HTTPS without credentials. The instance clones
  it on boot and has no secrets, so a private repository needs a deploy key
  installed by hand.

### Deploy

```sh
aws cloudformation deploy \
  --template-file deploy/aws/sdip-stack.yaml \
  --stack-name sdip \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      DomainName=interviews.example.com \
      TlsEmail=you@example.com \
      RepoUrl=https://github.com/you/ai-system-desing-canva.git
```

Nothing in the template is region-specific — the subnet takes the first
availability zone of whatever region you deploy into, and the AMI resolves from
an SSM public parameter that exists everywhere — so the region comes from your
CLI configuration, or from an explicit `--region`. Choose the one closest to the
people interviewing: every canvas edit round-trips through this single instance,
so its distance from participants is felt directly as lag.

`CAPABILITY_IAM` is required because the stack creates an instance role granting
Session Manager access — that is what lets you get a shell without opening port
22 or managing a key pair. Add `KeyName` and `SshCidr` parameters only if you
want conventional SSH as a fallback.

Then read the Elastic IP out of the stack and point your domain at it:

```sh
aws cloudformation describe-stacks --stack-name sdip \
  --query 'Stacks[0].Outputs' --output table
```

Certificate issuance fails until that A record resolves, which is normal on a
first deploy — Caddy keeps retrying and the site comes up on its own once DNS
propagates.

### Watch the first boot

The stack reports `CREATE_COMPLETE` as soon as the instance launches, not when
the app is serving traffic. Building the frontend bundle and starting the
containers takes several minutes more. To follow it:

```sh
aws ssm start-session --target <InstanceId from the stack outputs>
sudo tail -f /var/log/sdip-bootstrap.log
```

The JWT signing secret and the database password are generated on the instance
during that boot and written only to `/opt/sdip/.env` with mode `600`. They are
not stack parameters, so they never appear in the template, the stack events, or
the instance metadata. Regenerating `SDIP_JWT_SECRET` logs everyone out, which
is the intended effect if you ever need to revoke every issued token.

### Ship a new version

```sh
cd /opt/sdip
sudo git pull
sudo docker compose -f docker-compose.prod.yaml up -d --build
```

Rebuilding restarts the app container, which drops open WebSockets. Clients
reconnect about a second later and reload the canvas from the database, so an
interview in progress sees a brief "Reconnecting" badge rather than losing work.

### Back up

The PostgreSQL volume lives on the instance's root EBS volume, and deleting the
stack terminates the instance and that volume with it. Nothing is backed up for
you. At minimum, dump the database before any risky change:

```sh
sudo docker compose -f docker-compose.prod.yaml exec -T postgres \
  pg_dump -U sdip sdip | gzip > "sdip-$(date +%F).sql.gz"
```

For anything you care about, put that on a cron job writing to S3, or move the
database to RDS by pointing `SDIP_DATABASE_URL` at it and dropping the
`postgres` service from the compose file.

### What it costs

About $19/month in `eu-west-1` at list price: $13.43 for the `t4g.small`
instance, $1.76 for 20 GiB of gp3, and $3.65 for the public IPv4 address. Data
transfer for a handful of concurrent interviews is negligible. Instance and
storage rates vary by region; the IPv4 charge does not.

### Scaling past one instance

When one box is no longer enough, the fix is contained to `broadcast_message` in
`backend/app/routers/realtime.py:56`: replace the in-process fan-out with
PostgreSQL `LISTEN`/`NOTIFY` — no new infrastructure, since the database is
already there — or with Redis pub/sub. Only once every replica can reach every
connection does adding replicas become safe.

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

## End-to-end tests

`e2e/` holds Playwright tests that drive the compose deployment through a real
browser: the interviewer logs in, creates a session, shares the join link, a
second client joins as the candidate and edits the canvas, and the interviewer's
screen is checked for that edit.

```sh
make e2e
```

Playwright brings the stack up with `docker compose up --build` and stops it
afterwards, reusing a deployment that is already running on the app port. See
`e2e/README.md` for configuration and how to run it headed or in the debugger.
