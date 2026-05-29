import { invokeCommand } from "../tauriClient";
import type { CommandOptions, McpServerSummary, RpcAccepted } from "../types/rpc";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalizeServer(value: unknown): McpServerSummary {
  const record = isRecord(value) ? value : {};
  return {
    server_id: String(record.server_id ?? "unknown-server"),
    enabled: record.enabled !== false,
    state: String(record.state ?? (record.enabled === false ? "disabled" : "ready")),
    tool_count: typeof record.tool_count === "number" ? record.tool_count : 0
  };
}

export async function listMcpServers(
  include_disabled = true,
  options?: CommandOptions
): Promise<{ servers: McpServerSummary[] }> {
  const raw = await invokeCommand<{ servers?: unknown[] }>(
    "mcp.list_servers",
    { include_disabled },
    options
  );
  return { servers: (raw.servers ?? []).map(normalizeServer) };
}

export function refreshMcp(server_id?: string | null, options?: CommandOptions): Promise<RpcAccepted> {
  return invokeCommand<RpcAccepted>("mcp.refresh", { server_id: server_id ?? null }, options);
}

export function callMcpTool(
  server_id: string,
  tool_name: string,
  args: Record<string, unknown>,
  confirm_token?: string,
  options?: CommandOptions
): Promise<RpcAccepted> {
  return invokeCommand<RpcAccepted>(
    "mcp.call_tool",
    { server_id, tool_name, arguments: args, confirm_token: confirm_token ?? null },
    options
  );
}
