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

The repository layer uses SQLAlchemy's backend-neutral APIs so another
supported database, such as PostgreSQL, can be selected later by installing
its driver and changing this URL.

Run the backend tests with:

```sh
make test
```

Set `SDIP_JWT_SECRET` before deploying outside local development.
