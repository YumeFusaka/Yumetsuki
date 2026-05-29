import { expect, test } from "@playwright/test";

test("平台日志占位列表保持可滚动", async ({ page }) => {
  await page.goto("/logs/system");
  await expect(page.getByTestId("virtual-log-list")).toBeVisible();
});
