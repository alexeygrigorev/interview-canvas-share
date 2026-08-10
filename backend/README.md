# System Design Interview Platform backend

From the repository root, install dependencies and run the API with:

```sh
make sync
make run
```

The server listens on `http://127.0.0.1:8091` by default. Override it with,
for example, `make run HOST=0.0.0.0 PORT=8080`.

The seeded users all use `demo-password`. The login endpoint is
`POST /v1/auth/login` and accepts JSON containing `email` and `password`.

Data is stored in SQLite at `./sdip.db` by default. Set `SDIP_DATABASE_URL`
to any SQLAlchemy database URL to use a different database or location:

```sh
SDIP_DATABASE_URL=sqlite:////var/lib/sdip/sdip.db make run
```

## PostgreSQL

The psycopg 3 driver ships as a dependency, so PostgreSQL needs only a URL:

```sh
SDIP_DATABASE_URL=postgresql://sdip:sdip@localhost:5432/sdip make run
```

`postgres://` and `postgresql://` are normalized to `postgresql+psycopg://`,
which is what the installed driver registers under. Missing tables are created
at startup and an empty database is seeded with the demo data; both steps take a
PostgreSQL advisory lock so concurrent workers cannot race each other. JSON
columns (canvas elements, participant cursors) are stored as `JSONB` on
PostgreSQL and as portable `JSON` elsewhere.

Pool behavior is tunable with `SDIP_DB_POOL_SIZE` (default 5),
`SDIP_DB_MAX_OVERFLOW` (10), and `SDIP_DB_POOL_RECYCLE` (1800 seconds). These
are ignored on SQLite.

Run the backend tests with:

```sh
make test
```

The suite runs against a temporary SQLite file by default. Point it at a real
PostgreSQL server to run the same tests there — each test drops and recreates
the schema, so use a throwaway database:

```sh
SDIP_TEST_DATABASE_URL=postgresql://sdip:sdip@localhost:5432/sdip make test
```

Set `SDIP_JWT_SECRET` before deploying outside local development.
