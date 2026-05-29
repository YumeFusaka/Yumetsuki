import { expect, test } from "@playwright/test";

test("设置页可访问", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "设置中心" })).toBeVisible();
  await expect(page.getByRole("region", { name: "基础外观" })).toBeVisible();
  await expect(page.getByLabel("主题")).toBeVisible();
  await expect(page.getByLabel("聊天字体倍率")).toBeVisible();
});
