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

## Tests

```sh
npm test        # vitest, the pure canvas and palette logic
npm run typecheck
```

Tests live next to the code they cover as `*.test.ts` and run in a plain Node
environment — anything that needs a browser belongs in the Playwright suite in
`../e2e`, which drives the real deployment. `vitest.config.ts` is deliberately
separate from `vite.config.ts`, whose TanStack Start plugin chain the unit tests
have no use for.
