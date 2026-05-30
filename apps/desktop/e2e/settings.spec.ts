import { expect, test } from '@playwright/test'

test('settings route is reachable', async ({ page }) => {
  await page.goto('/settings/api')
  await expect(page.getByTestId('settings-page')).toBeVisible()
})
