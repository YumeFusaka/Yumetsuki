import { test } from '@playwright/test'

test('stress placeholder', async ({ page }) => {
  await page.goto('/diagnostics')
})
