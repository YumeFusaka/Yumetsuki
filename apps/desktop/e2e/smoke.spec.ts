import { expect, test } from "@playwright/test";

test("聊天、设置、日志和工具入口可访问", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("聊天输入").fill("你好");
  await page.getByRole("button", { name: "发送消息" }).click();
  await expect(page.getByTestId("chat-status")).toContainText(/回复|发送|完成/);
  await page.getByRole("link", { name: "设置" }).click();
  await expect(page.getByRole("heading", { name: "设置中心" })).toBeVisible();
  await page.getByRole("link", { name: "日志" }).click();
  await expect(page.getByRole("heading", { name: "日志工作台" })).toBeVisible();
  await page.getByRole("link", { name: "工具" }).click();
  await expect(page.getByRole("heading", { name: "工具与集成" })).toBeVisible();
});
