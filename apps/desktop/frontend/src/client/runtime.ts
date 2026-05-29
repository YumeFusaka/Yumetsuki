import type { RpcEvent, RpcEventType } from "./types/rpc";

export type TauriInvoke = <TResult>(command: string, args?: Record<string, unknown>) => Promise<TResult>;
export type TauriListen = <TPayload>(
  event: string,
  handler: (event: { payload: TPayload }) => void
) => Promise<() => void>;

export interface TauriTransport {
  kind?: "mock" | "tauri";
  invoke: TauriInvoke;
  listen: TauriListen;
}

const listeners = new Map<RpcEventType, Set<(event: RpcEvent) => void>>();

function getListenerSet(type: RpcEventType): Set<(event: RpcEvent) => void> {
  const existing = listeners.get(type);
  if (existing) {
    return existing;
  }
  const next = new Set<(event: RpcEvent) => void>();
  listeners.set(type, next);
  return next;
}

export function emitMockTauriEvent(event: RpcEvent): void {
  for (const listener of getListenerSet(event.type)) {
    listener(event);
  }
}

export function createMockTauriTransport(): TauriTransport {
  return {
    kind: "mock",
    async invoke<TResult>(command: string, args?: Record<string, unknown>): Promise<TResult> {
      const context = (args?.context ?? {}) as Record<string, unknown>;
      const request_id = String(context.request_id ?? "req_mock");
      const trace_id = String(context.trace_id ?? "trace_mock");
      const parent_trace_id = (context.parent_trace_id ?? null) as string | null;
      const session_id = String(context.session_id ?? "");
      const params = (args?.params ?? {}) as Record<string, unknown>;

      if (command === "sidecar_hello") {
        return {
          ready: true,
          protocol_version: 1,
          schema_hash: "dev-preview-schema",
          capabilities: [
            "config",
            "chat",
            "logs",
            "diagnostics",
            "tools",
            "plugins",
            "mcp",
            "security.grants"
          ]
        } as TResult;
      }

      if (command === "sidecar_health") {
        return {
          healthy: true
        } as TResult;
      }

      if (command === "config_get_all") {
        return {
          version: 1,
          system: {
            theme: "sakura",
            font_family: "Microsoft YaHei UI",
            font_scale: 1.3,
            bubble_scale: 1
          }
        } as TResult;
      }

      if (command === "config_save_system") {
        return {
          applied_version: 2,
          changed_scopes: ["system"]
        } as TResult;
      }

      if (command === "logs_query") {
        return {
          entries: [
            {
              id: "log_dev_boot",
              timestamp_ms: Date.now(),
              level: "info",
              source: "frontend.dev",
              event_type: "startup",
              summary: "本地开发日志已连接",
              trace_id
            }
          ]
        } as TResult;
      }

      if (command === "tools_list") {
        return {
          items: [
            { tool_name: "dryrun.echo", enabled: true, requires_confirmation: false, description: "本地 dry-run 回声工具" },
            { tool_name: "dryrun.shell", enabled: false, requires_confirmation: true, description: "需要确认的 shell 工具" }
          ]
        } as TResult;
      }

      if (command === "tools_audit_query") {
        return {
          items: [
            {
              audit_entry_id: "dryrun-audit-1",
              timestamp_ms: Date.now(),
              actor: "sidecar",
              action: "dry_run",
              allowed: true,
              tool_name: "dryrun.echo"
            }
          ],
          next_cursor: null
        } as TResult;
      }

      if (command === "plugins_status") {
        return {
          status: {
            plugin_id: String(params.plugin_id ?? "example-plugin"),
            enabled: true,
            loaded: true,
            worker_state: "idle"
          }
        } as TResult;
      }

      if (command === "plugins_enable" || command === "plugins_disable") {
        const enabled = command === "plugins_enable";
        emitMockTauriEvent({
          kind: "event",
          type: "plugin.status",
          request_id,
          trace_id,
          parent_trace_id,
          session_id,
          sequence: 1,
          timestamp_ms: Date.now(),
          protocol_version: 1,
          payload: {
            status: {
              plugin_id: String(params.plugin_id ?? "example-plugin"),
              enabled,
              loaded: enabled,
              worker_state: enabled ? "idle" : "disabled"
            }
          }
        });
        return (enabled ? { enabled: true } : { disabled: true }) as TResult;
      }

      if (command === "mcp_list_servers") {
        return {
          servers: [
            { server_id: "local-dev", enabled: true, state: "ready", tool_count: 1 },
            { server_id: "disabled-local", enabled: false, state: "disabled", tool_count: 0 }
          ]
        } as TResult;
      }

      if (command === "security_list_grants") {
        return {
          grants: [{ grant_id: "diagnostics-readonly", capability: "diagnostics.view", scope_hash: "dev-preview" }]
        } as TResult;
      }

      if (command === "sidecar_cancel") {
        return {
          request_id,
          status: "cancelled"
        } as TResult;
      }

      if (
        command === "chat_send" ||
        command === "chat_retry" ||
        command === "tools_call" ||
        command === "plugins_refresh" ||
        command === "mcp_refresh" ||
        command === "mcp_call_tool" ||
        command === "diagnostics_run" ||
        command === "diagnostics_export"
      ) {
        const task_type =
          command.startsWith("chat")
            ? "chat"
            : command.startsWith("tools")
              ? "tools"
              : command.startsWith("plugins")
                ? "plugins"
                : command.startsWith("mcp")
                  ? "mcp"
                  : "diagnostics";
        const accepted = {
          accepted: true,
          request_id,
          trace_id,
          parent_trace_id,
          session_id,
          task_type
        };

        if (command.startsWith("chat")) {
          globalThis.setTimeout(() => {
            emitMockTauriEvent({
              kind: "event",
              type: "chat.delta",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 1,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: { text: "正在生成回复。" }
            });
          }, 80);
          globalThis.setTimeout(() => {
            emitMockTauriEvent({
              kind: "event",
              type: "chat.done",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 2,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: { message_id: `msg_${request_id}` }
            });
          }, 800);
        }

        if (command === "diagnostics_run") {
          globalThis.setTimeout(() => {
            emitMockTauriEvent({
              kind: "event",
              type: "diagnostic.progress",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 1,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: { progress: 1.0, summary: "诊断完成" }
            });
          }, 20);
          globalThis.setTimeout(() => {
            emitMockTauriEvent({
              kind: "event",
              type: "diagnostic.done",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 2,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: { summary: { report_handle: `handle:report:${request_id}` } }
            });
          }, 40);
        }

        if (command === "diagnostics_export") {
          globalThis.setTimeout(() => {
            emitMockTauriEvent({
              kind: "event",
              type: "diagnostic.progress",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 1,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: { progress: 1.0, summary: "诊断导出完成" }
            });
          }, 20);
          globalThis.setTimeout(() => {
            emitMockTauriEvent({
              kind: "event",
              type: "diagnostic.done",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 2,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: { summary: { export_handle: `handle:report-export:${request_id}` } }
            });
          }, 40);
        }

        if (command === "tools_call") {
          globalThis.setTimeout(() => {
            emitMockTauriEvent({
              kind: "event",
              type: "tool.started",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 1,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: { summary: { tool_name: String(params.tool_name ?? "dryrun.echo"), dry_run: params.dry_run !== false } }
            });
            emitMockTauriEvent({
              kind: "event",
              type: "tool.audit",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 2,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: { audit_summary: { tool_name: String(params.tool_name ?? "dryrun.echo"), allowed: true } }
            });
            emitMockTauriEvent({
              kind: "event",
              type: "tool.result",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 3,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: { summary: { tool_name: String(params.tool_name ?? "dryrun.echo"), dry_run: true } }
            });
          }, 20);
        }

        if (command === "plugins_refresh") {
          globalThis.setTimeout(() => {
            emitMockTauriEvent({
              kind: "event",
              type: "plugin.status",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 1,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: { status: { plugin_id: "example-plugin", enabled: true, loaded: true, worker_state: "idle" } }
            });
            emitMockTauriEvent({
              kind: "event",
              type: "plugin.done",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 2,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: { summary: { plugin_count: 1, source: "local-dev" } }
            });
          }, 20);
        }

        if (command === "mcp_refresh" || command === "mcp_call_tool") {
          globalThis.setTimeout(() => {
            emitMockTauriEvent({
              kind: "event",
              type: command === "mcp_call_tool" ? "mcp.tool_started" : "mcp.status",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 1,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload:
                command === "mcp_call_tool"
                  ? { summary: { server_id: String(params.server_id ?? "local-dev"), tool_name: String(params.tool_name ?? "echo") } }
                  : { status: { server_id: String(params.server_id ?? "local-dev"), state: "refreshing" } }
            });
            emitMockTauriEvent({
              kind: "event",
              type: command === "mcp_call_tool" ? "mcp.tool_done" : "mcp.done",
              request_id,
              trace_id,
              parent_trace_id,
              session_id,
              sequence: 2,
              timestamp_ms: Date.now(),
              protocol_version: 1,
              payload: {
                summary: {
                  server_id: String(params.server_id ?? "local-dev"),
                  tool_name: command === "mcp_call_tool" ? String(params.tool_name ?? "echo") : undefined,
                  dry_run: true
                }
              }
            });
          }, 20);
        }

        return accepted as TResult;
      }

      return {} as TResult;
    },
    async listen<TPayload>(event: string, handler: (event: { payload: TPayload }) => void): Promise<() => void> {
      const type = event as RpcEventType;
      const wrapped = (payload: RpcEvent) => handler({ payload: payload as TPayload });
      getListenerSet(type).add(wrapped);
      return () => {
        getListenerSet(type).delete(wrapped);
      };
    }
  };
}

let overrideTransport: TauriTransport | null = null;

export function setTauriTransportForTests(transport: TauriTransport | null): void {
  overrideTransport = transport;
}

export async function getTauriTransport(): Promise<TauriTransport> {
  if (overrideTransport) {
    return overrideTransport;
  }

  const hasTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
  if (!hasTauri) {
    return createMockTauriTransport();
  }

  const [{ invoke }, { listen }] = await Promise.all([
    import("@tauri-apps/api/core"),
    import("@tauri-apps/api/event")
  ]);

  return { kind: "tauri", invoke, listen };
}
