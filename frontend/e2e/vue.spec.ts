import { test, expect } from '@playwright/test'

// A logged-out visit to any path lands on the sign-in screen. This replaces
// the create-vue scaffold assertion ("You did it!"), which was never true
// for this app and kept the whole e2e project permanently red.
test('the landing page is the sign-in screen', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('h1.legacy-brand-title')).toHaveText(
    'BIOTech Connect',
  )
})
