import { expect, test } from "@playwright/test";

test("桌面壳最小可访问性 gate", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "主导航" })).toBeVisible();
  await expect(page.getByLabel("聊天输入")).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  await expect(page.getByRole("status", { name: "运行状态" })).toBeVisible();
});
