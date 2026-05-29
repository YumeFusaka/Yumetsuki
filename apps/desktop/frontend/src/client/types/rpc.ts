export type RpcMethod =
  | "sidecar.hello"
  | "sidecar.health"
  | "sidecar.cancel"
  | "config.get_all"
  | "config.save_system"
  | "chat.send"
  | "chat.retry"
  | "logs.query"
  | "tools.list"
  | "tools.call"
  | "tools.audit_query"
  | "plugins.refresh"
  | "plugins.enable"
  | "plugins.disable"
  | "plugins.import"
  | "plugins.status"
  | "mcp.list_servers"
  | "mcp.save_server"
  | "mcp.refresh"
  | "mcp.call_tool"
  | "mcp.stop_server"
  | "security.approve"
  | "security.deny"
  | "security.revoke_grant"
  | "security.list_grants"
  | "diagnostics.run"
  | "diagnostics.export";

export type RpcEventType =
  | "sidecar.exiting"
  | "sidecar.crashed"
  | "sidecar.restarted"
  | "chat.delta"
  | "chat.done"
  | "chat.error"
  | "chat.cancelled"
  | "log.batch"
  | "tool.started"
  | "tool.result"
  | "tool.error"
  | "tool.cancelled"
  | "tool.audit"
  | "plugin.status"
  | "plugin.import_progress"
  | "plugin.done"
  | "plugin.error"
  | "plugin.cancelled"
  | "mcp.config_changed"
  | "mcp.status"
  | "mcp.tool_started"
  | "mcp.tool_done"
  | "mcp.done"
  | "mcp.error"
  | "mcp.cancelled"
  | "security.confirm_required"
  | "security.approved"
  | "security.denied"
  | "security.grant_revoked"
  | "diagnostic.progress"
  | "diagnostic.done"
  | "diagnostic.error"
  | "diagnostic.cancelled";

export type RpcTaskType = "chat" | "diagnostics" | "config" | "sidecar" | "logs" | "tools" | "plugins" | "mcp";

export interface RpcContext {
  request_id: string;
  trace_id: string;
  parent_trace_id: string | null;
  session_id: string;
  deadline_ms?: number;
}

export interface RpcRequest<TParams = unknown> extends RpcContext {
  kind: "request";
  method: RpcMethod;
  params: TParams;
  protocol_version: 1;
}

export interface RpcError {
  code: string;
  message: string;
  user_message: string;
  retryable: boolean;
  details: Record<string, unknown>;
}

export interface RpcResponse<TResult = unknown> extends RpcContext {
  kind: "response";
  ok: boolean;
  result: TResult | null;
  error: RpcError | null;
  protocol_version: 1;
}

export interface RpcAccepted extends RpcContext {
  accepted: true;
  request_id: string;
  trace_id: string;
  task_type: RpcTaskType;
}

export interface RpcEvent<TPayload = unknown> extends RpcContext {
  kind: "event";
  type: RpcEventType;
  payload: TPayload;
  sequence: number;
  timestamp_ms: number;
  protocol_version: 1;
}

export type UnlistenFn = () => void;

export interface TypedEventSubscription {
  unsubscribe: UnlistenFn;
}

export interface CommandOptions {
  request_id?: string;
  trace_id?: string;
  parent_trace_id?: string | null;
  session_id?: string;
  deadline_ms?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  request_id?: string;
  trace_id?: string;
  status?: "pending" | "streaming" | "done" | "error" | "cancelled";
}

export interface ChatDeltaPayload {
  text: string;
  is_final?: boolean;
}

export interface LogEntry {
  id: string;
  timestamp_ms: number;
  level: "debug" | "info" | "warning" | "error";
  source: string;
  event_type: string;
  summary: string;
  trace_id?: string;
}

export interface ToolItem {
  tool_name: string;
  enabled: boolean;
  requires_confirmation: boolean;
  description?: string;
}

export interface ToolAuditEntry {
  audit_entry_id: string;
  timestamp_ms: number;
  actor: string;
  action: string;
  allowed: boolean;
  tool_name?: string;
}

export interface PluginStatus {
  plugin_id: string;
  enabled: boolean;
  loaded: boolean;
  worker_state: string;
}

export interface McpServerSummary {
  server_id: string;
  enabled: boolean;
  state: string;
  tool_count: number;
}

export interface SecurityGrant {
  grant_id: string;
  capability: string;
  scope_hash: string;
}

export interface ConfigSnapshot {
  version: number;
  system: {
    theme: string;
    font_family: string;
    font_scale: number;
    bubble_scale: number;
  };
}

export interface SidecarHello {
  ready: boolean;
  protocol_version: 1;
  schema_hash: string;
  capabilities: string[];
}

export function createRpcError(
  code: string,
  userMessage: string,
  details: Record<string, unknown> = {},
  retryable = false
): RpcError {
  return {
    code,
    message: userMessage,
    user_message: userMessage,
    retryable,
    details
  };
}
