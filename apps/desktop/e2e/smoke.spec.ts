import { expect, test } from '@playwright/test'

test('smoke keeps chat, logs, and settings reachable', async ({ page }) => {
  await page.goto('/chat')
  await expect(page.getByTestId('chat-page')).toBeVisible()
  await page.getByRole('link', { name: '对话日志' }).click()
  await expect(page.getByTestId('log-list')).toBeVisible()
  await page.getByRole('link', { name: '设置' }).click()
  await expect(page.getByTestId('settings-page')).toBeVisible()
})
