import { expect, test } from '@playwright/test'

test('shell exposes accessible landmarks', async ({ page }) => {
  await page.goto('/chat')
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()
})
