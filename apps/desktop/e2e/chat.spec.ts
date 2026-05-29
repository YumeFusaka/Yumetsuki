import { expect, test } from "@playwright/test";

test("聊天支持发送与停止入口", async ({ page }) => {
  await page.goto("/chat");
  await page.getByLabel("聊天输入").fill("测试消息");
  await page.getByRole("button", { name: "发送消息" }).click();
  await expect(page.getByRole("button", { name: "停止当前回复" })).toBeVisible();
});
