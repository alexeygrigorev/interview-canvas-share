import { defineConfig } from "vitest/config";

/**
 * Deliberately separate from vite.config.ts: the app config pulls in the whole
 * TanStack Start / nitro plugin chain, none of which the unit tests need. The
 * `@/*` aliases still resolve - Vite reads them from tsconfig.json.
 */
export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
