import process from 'node:process'
import { defineConfig, devices } from '@playwright/test'

/**
 * Where the app is. The ticket suite drives both sides of support through
 * the one Vue portal: a student in the Support Centre and a support agent in
 * the portal's own ticket queue (/admin/tickets). The React admin app used to
 * be the agent's side; it is being retired and nothing here drives it.
 *
 * When E2E_PORTAL_URL is set the harness has already started every server it
 * wants tested (the portal and the backend it talks to) and Playwright must
 * not start its own; the webServer block below switches off accordingly.
 * E2E_API_URL is that backend, which the specs call directly to check what
 * was (and was not) written. It has to be the same origin the portal was
 * built against (VITE_API_BASE_URL), or the two would be looking at
 * different databases.
 */
export const PORTAL_URL =
  process.env.E2E_PORTAL_URL ??
  (process.env.CI ? 'http://localhost:4173' : 'http://localhost:5173')
export const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000'

/**
 * A Chromium to launch instead of the build this Playwright version pins.
 * For machines where that build is not installed and cannot be (no network,
 * or an older cache): point it at any Chrome for Testing binary in
 * ~/Library/Caches/ms-playwright. Unset, Playwright uses its own.
 */
const CHROMIUM_PATH = process.env.E2E_CHROMIUM_PATH || undefined

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// require('dotenv').config();

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './e2e',
  /* Maximum time one test can run for. */
  timeout: 30 * 1000,
  expect: {
    /**
     * Maximum time expect() should wait for the condition to be met.
     * For example in `await expect(locator).toHaveText();`
     */
    timeout: 5000,
  },
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Maximum time each action such as `click()` can take. Defaults to 0 (no limit). */
    actionTimeout: 0,
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: PORTAL_URL,

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',

    /* Headless on CI and under the harness (E2E_PORTAL_URL): a harness run
     * must not open windows on the desktop of whoever started it. Pass
     * --headed to watch one. */
    headless: !!process.env.CI || !!process.env.E2E_PORTAL_URL,
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        ...(CHROMIUM_PATH ? { launchOptions: { executablePath: CHROMIUM_PATH } } : {}),
      },
    },
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
      },
    },
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
      },
    },

    /* Test against mobile viewports. */
    // {
    //   name: 'Mobile Chrome',
    //   use: {
    //     ...devices['Pixel 5'],
    //   },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: {
    //     ...devices['iPhone 12'],
    //   },
    // },

    /* Test against branded browsers. */
    // {
    //   name: 'Microsoft Edge',
    //   use: {
    //     channel: 'msedge',
    //   },
    // },
    // {
    //   name: 'Google Chrome',
    //   use: {
    //     channel: 'chrome',
    //   },
    // },
  ],

  /* Folder for test artifacts such as screenshots, videos, traces, etc. */
  // outputDir: 'test-results/',

  /* Run your local dev server before starting the tests — unless the
   * harness said (via E2E_PORTAL_URL) that it runs the servers itself. */
  webServer: process.env.E2E_PORTAL_URL
    ? undefined
    : {
        /**
         * Use the dev server by default for faster feedback loop.
         * Use the preview server on CI for more realistic testing.
         * Playwright will re-use the local server if there is already a dev-server running.
         */
        command: process.env.CI ? 'npm run preview' : 'npm run dev',
        port: process.env.CI ? 4173 : 5173,
        reuseExistingServer: !process.env.CI,
      },
})
