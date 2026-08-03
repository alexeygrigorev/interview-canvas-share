# System Design Interview Platform backend

From the repository root, install dependencies and run the API with:

```sh
make sync
make run
```

The server listens on `http://127.0.0.1:8000` by default. Override it with,
for example, `make run HOST=0.0.0.0 PORT=8080`.

The seeded users all use `demo-password`. The login endpoint is
`POST /v1/auth/login` and accepts JSON containing `email` and `password`.

Run the backend tests with:

```sh
make test
```

Set `SDIP_JWT_SECRET` before deploying outside local development.
