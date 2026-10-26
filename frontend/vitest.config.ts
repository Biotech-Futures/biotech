import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { configDefaults, defineConfig } from 'vitest/config'

// Deliberately standalone rather than merging vite.config.ts: that config
// imports vite-plugin-vue-devtools, which touches `localStorage` at import
// time and so crashes any config load outside a browser. Keep the plugin
// and alias list in step with vite.config.ts by hand.
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    exclude: [...configDefaults.exclude, 'e2e/**'],
    // Router tests load lazy route views inside the test, which can pass 5s on a busy runner.
    testTimeout: 15_000,
    root: fileURLToPath(new URL('./', import.meta.url)),
  },
})
