import { expect, test } from "@playwright/test";

test("启动后显示应用 shell 与 sidecar 状态", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("application", { name: "Yumetsuki 桌面壳" })).toBeVisible();
  await expect(page.getByTestId("startup-status")).toContainText(/sidecar|模拟/i);
  await expect(page.getByRole("main")).not.toBeEmpty();
});
