import { expect, test } from "@playwright/test";

test("日志、工具和诊断页面可见", async ({ page }) => {
  await page.goto("/logs/system");
  await expect(page.getByRole("heading", { name: "日志工作台" })).toBeVisible();
  await page.goto("/tools/plugins");
  await expect(page.getByRole("heading", { name: "工具与集成" })).toBeVisible();
  await expect(page.getByText("dryrun.echo", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Dry-run" }).first().click();
  await expect(page.getByText(/dry-run 完成/)).toBeVisible();

  await page.getByRole("button", { name: "扫描" }).click();
  await expect(page.getByText("已扫描 1 个插件")).toBeVisible();
  const pluginRow = page.getByRole("listitem").filter({ hasText: "example-plugin" });
  await pluginRow.getByRole("button", { name: "停用" }).click();
  await expect(page.getByLabel("确认令牌")).toBeVisible();
  await page.getByLabel("确认令牌").fill("confirm");
  await pluginRow.getByRole("button", { name: "启用" }).click();
  await expect(pluginRow.getByRole("button", { name: "停用" })).toBeVisible();

  await page.getByRole("button", { name: "Echo" }).first().click();
  await expect(page.getByText("MCP 调用完成")).toBeVisible();

  await page.goto("/diagnostics");
  await expect(page.getByRole("heading", { name: "诊断" })).toBeVisible();
});
