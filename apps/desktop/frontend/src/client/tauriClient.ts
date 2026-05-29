import { createRequestId, createTraceId } from "./id";
import { getTauriTransport, type TauriTransport } from "./runtime";
import type {
  CommandOptions,
  RpcAccepted,
  RpcContext,
  RpcError,
  RpcEvent,
  RpcEventType,
  RpcMethod,
  RpcTaskType,
  UnlistenFn
} from "./types/rpc";
import { createRpcError } from "./types/rpc";

const MOCK_METHOD_TO_COMMAND: Partial<Record<RpcMethod, string>> = {
  "sidecar.hello": "sidecar_hello",
  "sidecar.health": "sidecar_health",
  "sidecar.cancel": "sidecar_cancel",
  "config.get_all": "config_get_all",
  "config.save_system": "config_save_system",
  "chat.send": "chat_send",
  "chat.retry": "chat_retry",
  "logs.query": "logs_query",
  "tools.list": "tools_list",
  "tools.call": "tools_call",
  "tools.audit_query": "tools_audit_query",
  "plugins.refresh": "plugins_refresh",
  "plugins.enable": "plugins_enable",
  "plugins.disable": "plugins_disable",
  "plugins.status": "plugins_status",
  "mcp.list_servers": "mcp_list_servers",
  "mcp.refresh": "mcp_refresh",
  "mcp.call_tool": "mcp_call_tool",
  "security.list_grants": "security_list_grants",
  "diagnostics.run": "diagnostics_run",
  "diagnostics.export": "diagnostics_export"
};

const TAURI_METHOD_TO_COMMAND: Partial<Record<RpcMethod, string>> = {
  "sidecar.hello": "sidecar_hello",
  "sidecar.health": "sidecar_health",
  "sidecar.cancel": "sidecar_cancel",
  "config.get_all": "config_get_all",
  "config.save_system": "config_save_system",
  "chat.send": "chat_send",
  "chat.retry": "chat_retry",
  "logs.query": "logs_query",
  "tools.list": "tools_list",
  "tools.call": "tools_call",
  "tools.audit_query": "tools_audit_query",
  "plugins.refresh": "plugins_refresh",
  "plugins.enable": "plugins_enable",
  "plugins.disable": "plugins_disable",
  "plugins.status": "plugins_status",
  "mcp.list_servers": "mcp_list_servers",
  "mcp.refresh": "mcp_refresh",
  "mcp.call_tool": "mcp_call_tool",
  "security.list_grants": "security_list_grants",
  "diagnostics.run": "diagnostics_run",
  "diagnostics.export": "diagnostics_export"
};

const LONG_TASK_METHODS = new Set<RpcMethod>([
  "chat.send",
  "chat.retry",
  "tools.call",
  "plugins.refresh",
  "mcp.refresh",
  "mcp.call_tool",
  "diagnostics.run",
  "diagnostics.export"
]);
const DEFAULT_TASK_TIMEOUT_MS = 30_000;

interface RustCommandEnvelope {
  request_id: string;
  trace_id: string;
  accepted: boolean;
  result: unknown;
}

export type TerminalState = "done" | "error" | "cancelled";

export interface TrackedTask {
  request_id: string;
  trace_id: string;
  task_type: RpcTaskType;
  terminal_state: TerminalState | null;
  last_sequence: number;
  error: RpcError | null;
  timeout_id: ReturnType<typeof globalThis.setTimeout> | null;
}

const taskRegistry = new Map<string, TrackedTask>();

export function makeRpcContext(options: CommandOptions = {}): RpcContext {
  return {
    request_id: options.request_id ?? createRequestId(),
    trace_id: options.trace_id ?? createTraceId(),
    parent_trace_id: options.parent_trace_id ?? null,
    session_id: options.session_id ?? "",
    deadline_ms: options.deadline_ms
  };
}

export function normalizeRpcError(error: unknown, fallbackCode = "rpc.request_failed"): RpcError {
  if (typeof error === "object" && error !== null) {
    const record = error as Record<string, unknown>;
    if (typeof record.code === "string" && typeof record.user_message === "string") {
      return {
        code: record.code,
        message: String(record.message ?? record.user_message),
        user_message: record.user_message,
        retryable: Boolean(record.retryable),
        details: (record.details as Record<string, unknown>) ?? {}
      };
    }
  }

  return createRpcError(
    fallbackCode,
    error instanceof Error ? error.message : "请求失败，请查看平台日志。",
    { summary: String(error) },
    true
  );
}

function inferTaskType(method: RpcMethod): RpcTaskType {
  if (method.startsWith("chat.")) {
    return "chat";
  }
  if (method.startsWith("diagnostics.")) {
    return "diagnostics";
  }
  if (method.startsWith("config.")) {
    return "config";
  }
  if (method.startsWith("logs.")) {
    return "logs";
  }
  if (method.startsWith("tools.")) {
    return "tools";
  }
  if (method.startsWith("plugins.")) {
    return "plugins";
  }
  if (method.startsWith("mcp.")) {
    return "mcp";
  }
  return "sidecar";
}

function resolveCommand(method: RpcMethod, transport: TauriTransport): string {
  const command =
    transport.kind === "tauri" ? TAURI_METHOD_TO_COMMAND[method] : MOCK_METHOD_TO_COMMAND[method];
  if (!command) {
    throw createRpcError(
      "rpc.method_not_found",
      "该功能尚未接入当前 Tauri 迁移阶段。",
      { method, phase: "tauri-migration-phase-4" },
      false
    );
  }
  return command;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isRustCommandEnvelope(value: unknown): value is RustCommandEnvelope {
  return (
    isRecord(value) &&
    typeof value.request_id === "string" &&
    typeof value.trace_id === "string" &&
    typeof value.accepted === "boolean" &&
    "result" in value
  );
}

function isRpcResponseEnvelope(value: unknown): value is { ok: boolean; result: unknown; error: unknown } {
  return isRecord(value) && value.kind === "response" && typeof value.ok === "boolean";
}

function unwrapShortResult(value: unknown): unknown {
  if (isRustCommandEnvelope(value)) {
    return value.result;
  }
  if (isRpcResponseEnvelope(value)) {
    if (!value.ok) {
      throw normalizeRpcError(value.error, "rpc.request_failed");
    }
    return value.result;
  }
  return value;
}

function taskTypeFromResult(method: RpcMethod, value: unknown): RpcTaskType {
  if (isRecord(value) && typeof value.task_type === "string") {
    if (value.task_type.startsWith("chat.")) {
      return "chat";
    }
    if (value.task_type.startsWith("diagnostics.")) {
      return "diagnostics";
    }
    if (value.task_type.startsWith("config.")) {
      return "config";
    }
    if (value.task_type.startsWith("logs.")) {
      return "logs";
    }
    if (value.task_type.startsWith("tools.")) {
      return "tools";
    }
    if (value.task_type.startsWith("plugins.")) {
      return "plugins";
    }
    if (value.task_type.startsWith("mcp.")) {
      return "mcp";
    }
  }
  return inferTaskType(method);
}

function normalizeAcceptedResult(method: RpcMethod, value: unknown, context: RpcContext): RpcAccepted {
  if (isRustCommandEnvelope(value)) {
    if (!value.accepted) {
      throw createRpcError("rpc.invalid_response", "长任务未返回 accepted。", {
        request_id: value.request_id,
        method
      });
    }
    return {
      ...context,
      request_id: value.request_id,
      trace_id: value.trace_id,
      accepted: true,
      task_type: taskTypeFromResult(method, value.result)
    };
  }

  if (isRpcResponseEnvelope(value)) {
    if (!value.ok) {
      throw normalizeRpcError(value.error, "rpc.request_failed");
    }
    return normalizeAcceptedResult(method, value.result, context);
  }

  const record = isRecord(value) ? value : {};
  return {
    ...context,
    request_id: typeof record.request_id === "string" ? record.request_id : context.request_id,
    trace_id: typeof record.trace_id === "string" ? record.trace_id : context.trace_id,
    parent_trace_id:
      typeof record.parent_trace_id === "string" || record.parent_trace_id === null
        ? record.parent_trace_id
        : context.parent_trace_id,
    session_id: typeof record.session_id === "string" ? record.session_id : context.session_id,
    accepted: true,
    task_type: taskTypeFromResult(method, record)
  };
}

export function registerAcceptedTask(accepted: RpcAccepted): TrackedTask {
  const existing = taskRegistry.get(accepted.request_id);
  if (existing) {
    existing.trace_id = accepted.trace_id;
    existing.task_type = accepted.task_type;
    return existing;
  }

  const tracked: TrackedTask = {
    request_id: accepted.request_id,
    trace_id: accepted.trace_id,
    task_type: accepted.task_type,
    terminal_state: null,
    last_sequence: 0,
    error: null,
    timeout_id: null
  };
  taskRegistry.set(accepted.request_id, tracked);
  return tracked;
}

function attachTaskTimeout(tracked: TrackedTask, deadlineMs: number): void {
  if (tracked.terminal_state || tracked.timeout_id) {
    return;
  }
  const timeoutId = globalThis.setTimeout(() => {
    markTaskTimeout(tracked.request_id);
  }, deadlineMs);
  if (typeof timeoutId === "object" && timeoutId !== null && "unref" in timeoutId) {
    (timeoutId as { unref: () => void }).unref();
  }
  tracked.timeout_id = timeoutId;
}

function clearTaskTimeout(tracked: TrackedTask): void {
  if (tracked.timeout_id) {
    globalThis.clearTimeout(tracked.timeout_id);
    tracked.timeout_id = null;
  }
}

export function getTrackedTask(requestId: string): TrackedTask | undefined {
  return taskRegistry.get(requestId);
}

export function clearTrackedTasks(): void {
  for (const tracked of taskRegistry.values()) {
    clearTaskTimeout(tracked);
  }
  taskRegistry.clear();
}

export function clearTrackedTask(requestId: string): void {
  const tracked = taskRegistry.get(requestId);
  if (tracked) {
    clearTaskTimeout(tracked);
  }
  taskRegistry.delete(requestId);
}

export function markTerminalEvent(event: RpcEvent): { accepted: boolean; error: RpcError | null } {
  const tracked = taskRegistry.get(event.request_id);
  if (!tracked) {
    return { accepted: false, error: null };
  }

  if (event.sequence <= tracked.last_sequence) {
    tracked.error = createRpcError("rpc.event_out_of_order", "事件顺序异常，已忽略迟到事件。", {
      request_id: event.request_id,
      sequence: event.sequence,
      last_sequence: tracked.last_sequence
    });
    return { accepted: false, error: tracked.error };
  }

  tracked.last_sequence = event.sequence;

  if (tracked.terminal_state) {
    return { accepted: false, error: createRpcError("rpc.duplicate_terminal", "重复终态事件已忽略。") };
  }

  if (isDoneEvent(event.type)) {
    tracked.terminal_state = "done";
  } else if (event.type.endsWith(".error")) {
    tracked.terminal_state = "error";
    tracked.error = normalizeRpcError((event.payload as { error?: unknown }).error, `${tracked.task_type}.error`);
  } else if (event.type.endsWith(".cancelled")) {
    tracked.terminal_state = "cancelled";
  }

  if (tracked.terminal_state) {
    clearTaskTimeout(tracked);
  }

  return { accepted: true, error: tracked.error };
}

function isDoneEvent(type: RpcEventType): boolean {
  return type.endsWith(".done") || type === "tool.result" || type === "mcp.tool_done";
}

export function markTaskTimeout(requestId: string): { accepted: boolean; error: RpcError | null } {
  const tracked = taskRegistry.get(requestId);
  if (!tracked || tracked.terminal_state) {
    return { accepted: false, error: null };
  }

  const error = createRpcError(
    `${tracked.task_type}.timeout`,
    "请求超时，可以重试或查看平台日志。",
    { request_id: requestId },
    true
  );
  tracked.terminal_state = "error";
  tracked.error = error;
  clearTaskTimeout(tracked);
  return { accepted: true, error };
}

export async function invokeCommand<TResult, TParams extends object = Record<string, unknown>>(
  method: RpcMethod,
  params: TParams = {} as TParams,
  options: CommandOptions = {}
): Promise<TResult> {
  const context = makeRpcContext(options);
  const transport = await getTauriTransport();
  const command = resolveCommand(method, transport);

  try {
    const rawResult = await transport.invoke<unknown>(command, {
      context,
      params
    });

    if (LONG_TASK_METHODS.has(method)) {
      const accepted = normalizeAcceptedResult(method, rawResult, context);
      const tracked = registerAcceptedTask(accepted);
      attachTaskTimeout(tracked, context.deadline_ms ?? DEFAULT_TASK_TIMEOUT_MS);
      return accepted as TResult;
    }

    return unwrapShortResult(rawResult) as TResult;
  } catch (error) {
    throw normalizeRpcError(error);
  }
}

export async function subscribeEvent<TPayload>(
  type: RpcEventType,
  handler: (event: RpcEvent<TPayload>) => void
): Promise<UnlistenFn> {
  const transport = await getTauriTransport();
  const unlisten = await transport.listen<RpcEvent<TPayload>>(type, (event) => {
    handler(event.payload);
  });
  return unlisten;
}

export function createFakeClient() {
  return {
    invokeCommand,
    subscribeEvent,
    registerAcceptedTask,
    markTerminalEvent,
    clearTrackedTask,
    clearTrackedTasks
  };
}
