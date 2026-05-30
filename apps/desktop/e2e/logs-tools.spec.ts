import { expect, test } from '@playwright/test'

test('logs and tools routes are reachable', async ({ page }) => {
  await page.goto('/logs/conversation')
  await expect(page.getByTestId('log-list')).toBeVisible()
  await page.goto('/tools/plugins')
  await expect(page.getByText('未迁移入口保持禁用占位')).toBeVisible()
})
