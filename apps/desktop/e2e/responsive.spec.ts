import { expect, test } from '@playwright/test'

test('shell stays readable on narrow widths', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await page.goto('/chat')
  await expect(page.getByTestId('chat-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '聊天' })).toBeVisible()
})
