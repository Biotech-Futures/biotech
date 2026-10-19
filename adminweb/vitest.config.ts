import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";

// Standalone rather than merging vite.config.ts, for the same reason the Vue
// app keeps its own: that config loads the TanStack Router plugin and the
// devtools plugin, which do work at import time that has no business running
// in a test process. Keep the alias list in step with tsconfig.json by hand.
//
// Everything this needs was already in package.json — @testing-library/react,
// @testing-library/dom, jsdom and vitest. What was missing was this file, and
// without it `pnpm test` ran in the Node environment where nothing can render.
// That is why the only tests here were schema tests, and why every behaviour
// in the queue, the detail panel and the nav had no cover at all.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    exclude: [...configDefaults.exclude, "e2e/**"],
    root: fileURLToPath(new URL("./", import.meta.url)),
  },
});
