import { expect, test } from '@playwright/test'

test('chat mock shell is reachable', async ({ page }) => {
  await page.goto('/chat')
  await expect(page.getByTestId('chat-page')).toBeVisible()
})
