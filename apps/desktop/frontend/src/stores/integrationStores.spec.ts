import { afterEach, describe, expect, it } from "vitest";
import { setTauriTransportForTests } from "@/client/runtime";
import { clearTrackedTasks } from "@/client/tauriClient";
import { useMcpStore } from "./mcpStore";
import { usePluginStore } from "./pluginStore";
import { useToolStore } from "./toolStore";

function waitForMockEvents(): Promise<void> {
  return new Promise((resolve) => {
    globalThis.setTimeout(resolve, 80);
  });
}

afterEach(() => {
  useToolStore().dispose();
  usePluginStore().dispose();
  useMcpStore().dispose();
  clearTrackedTasks();
  setTauriTransportForTests(null);
});

describe("工具、插件和 MCP store", () => {
  it("toolStore 拉取工具、审计和安全授权，并消费 dry-run 事件", async () => {
    const toolStore = useToolStore();

    await toolStore.init();
    expect(toolStore.items.map((item) => item.tool_name)).toContain("dryrun.echo");
    expect(toolStore.auditItems[0].audit_entry_id).toBe("dryrun-audit-1");
    expect(toolStore.grants[0].grant_id).toBe("diagnostics-readonly");

    await toolStore.runDryRun("dryrun.echo");
    await waitForMockEvents();

    expect(toolStore.runningIds).toEqual([]);
    expect(toolStore.lastResult).toContain("dry-run 完成");
    expect(toolStore.auditItems[0].tool_name).toBe("dryrun.echo");
  });

  it("pluginStore 拉取插件状态，并处理扫描、启用和停用事件", async () => {
    const pluginStore = usePluginStore();

    await pluginStore.init();
    expect(pluginStore.items[0]).toMatchObject({ plugin_id: "example-plugin", enabled: true });

    await pluginStore.refresh();
    await waitForMockEvents();
    expect(pluginStore.scanning).toBe(false);
    expect(pluginStore.status).toBe("idle");

    await pluginStore.disable("example-plugin");
    expect(pluginStore.enabledPluginIds).not.toContain("example-plugin");

    await pluginStore.enable("example-plugin");
    expect(pluginStore.error?.code).toBe("rpc.invalid_params");

    pluginStore.setEnableConfirmToken("example-plugin", "confirm");
    await pluginStore.enable("example-plugin");
    expect(pluginStore.enabledPluginIds).toContain("example-plugin");
  });

  it("mcpStore 拉取服务器状态，并消费 refresh 与 call_tool 事件", async () => {
    const mcpStore = useMcpStore();

    await mcpStore.init();
    expect(mcpStore.servers.map((server) => server.server_id)).toContain("local-dev");

    await mcpStore.refresh("local-dev");
    await waitForMockEvents();
    expect(mcpStore.refreshing).toBe(false);
    expect(mcpStore.serverSummaries).toContain("local-dev:ready");

    await mcpStore.callEcho("local-dev");
    await waitForMockEvents();
    expect(mcpStore.runningIds).toEqual([]);
    expect(mcpStore.lastToolResult).toBe("MCP 调用完成");
  });
});
