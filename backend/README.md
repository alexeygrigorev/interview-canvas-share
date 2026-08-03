# System Design Interview Platform backend

Run the API from the repository root with:

```sh
uv run --project backend uvicorn backend.app.main:app --reload
```

The seeded users all use `demo-password`. The login endpoint is
`POST /v1/auth/login` and accepts JSON containing `email` and `password`.
