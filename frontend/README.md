# Interview Canvas frontend

The frontend implementation for the Interview Canvas platform.

See the [product and technical specification](../docs/spec.md).

## Development

```sh
bun install
bun run dev
```

The frontend talks to `http://localhost:8091` by default and automatically logs
in as the seeded development user. Override the connection or credentials with
`VITE_API_BASE_URL`, `VITE_API_EMAIL`, and `VITE_API_PASSWORD`.
