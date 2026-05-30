import { expect, test } from '@playwright/test'

test('startup shows shell and schema hash', async ({ page }) => {
  await page.goto('/diagnostics')
  await expect(page.getByTestId('diagnostics-page')).toBeVisible()
  await expect(page.getByTestId('schema-hash')).toHaveText(/[0-9a-f]{64}/)
})
