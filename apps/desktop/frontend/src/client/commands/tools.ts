import { invokeCommand } from "../tauriClient";
import type { CommandOptions, RpcAccepted, ToolAuditEntry, ToolItem } from "../types/rpc";

export interface ToolCallParams {
  tool_name: string;
  source?: string;
  arguments: Record<string, unknown>;
  confirm_token?: string;
  dry_run?: boolean;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalizeToolItem(value: unknown): ToolItem {
  const record = isRecord(value) ? value : {};
  return {
    tool_name: String(record.tool_name ?? record.name ?? "unknown.tool"),
    enabled: record.enabled !== false,
    requires_confirmation: Boolean(record.requires_confirmation),
    description: typeof record.description === "string" ? record.description : undefined
  };
}

function normalizeAuditEntry(value: unknown, index: number): ToolAuditEntry {
  const record = isRecord(value) ? value : {};
  return {
    audit_entry_id: String(record.audit_entry_id ?? `audit_${index}`),
    timestamp_ms: typeof record.timestamp_ms === "number" ? record.timestamp_ms : Date.now(),
    actor: String(record.actor ?? "sidecar"),
    action: String(record.action ?? "unknown"),
    allowed: record.allowed !== false,
    tool_name: typeof record.tool_name === "string" ? record.tool_name : undefined
  };
}

export async function listTools(
  include_disabled = true,
  options?: CommandOptions
): Promise<{ items: ToolItem[] }> {
  const raw = await invokeCommand<{ items?: unknown[] }>(
    "tools.list",
    { include_disabled },
    options
  );
  return { items: (raw.items ?? []).map(normalizeToolItem) };
}

export async function queryToolAudit(
  params: { cursor?: string | null; limit?: number; filters?: Record<string, unknown> | null } = {},
  options?: CommandOptions
): Promise<{ items: ToolAuditEntry[]; next_cursor: string | null }> {
  const raw = await invokeCommand<{ items?: unknown[]; next_cursor?: string | null }>(
    "tools.audit_query",
    {
      cursor: params.cursor ?? null,
      limit: params.limit ?? 20,
      filters: params.filters ?? null
    },
    options
  );
  return {
    items: (raw.items ?? []).map(normalizeAuditEntry),
    next_cursor: raw.next_cursor ?? null
  };
}

export function callTool(params: ToolCallParams, options?: CommandOptions): Promise<RpcAccepted> {
  return invokeCommand<RpcAccepted, ToolCallParams>(
    "tools.call",
    {
      ...params,
      source: params.source ?? "desktop.tools",
      dry_run: params.dry_run ?? true
    },
    options
  );
}
