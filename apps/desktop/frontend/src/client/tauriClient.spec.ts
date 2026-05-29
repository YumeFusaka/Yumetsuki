import { describe, expect, it, vi } from "vitest";
import { emitMockTauriEvent, setTauriTransportForTests, type TauriTransport } from "./runtime";
import {
  clearTrackedTasks,
  getTrackedTask,
  invokeCommand,
  markTerminalEvent,
  registerAcceptedTask,
  subscribeEvent
} from "./tauriClient";
import type { RpcAccepted, RpcEvent } from "./types/rpc";

describe("typed Tauri client", () => {
  it("注入或透传 request_id、trace_id 和 parent_trace_id", async () => {
    let capturedArgs: Record<string, unknown> | undefined;
    const transport: TauriTransport = {
      async invoke<TResult>(_command: string, args?: Record<string, unknown>): Promise<TResult> {
        capturedArgs = args;
        return { ready: true } as TResult;
      },
      async listen() {
        return () => undefined;
      }
    };

    setTauriTransportForTests(transport);
    await invokeCommand("sidecar.hello", {}, {
      request_id: "req_keep",
      trace_id: "trace_keep",
      parent_trace_id: "trace_parent"
    });

    expect(capturedArgs?.context).toMatchObject({
      request_id: "req_keep",
      trace_id: "trace_keep",
      parent_trace_id: "trace_parent"
    });
    setTauriTransportForTests(null);
  });

  it("长任务 accepted 后进入本地 registry", async () => {
    clearTrackedTasks();
    const accepted = await invokeCommand<RpcAccepted>("chat.send", { message: "你好" }, { request_id: "req_chat" });

    expect(accepted.accepted).toBe(true);
    expect(getTrackedTask("req_chat")).toMatchObject({
      request_id: "req_chat",
      task_type: "chat",
      terminal_state: null
    });
  });

  it("终态事件先到时，后续 accepted 不会复活已完成任务", () => {
    clearTrackedTasks();
    registerAcceptedTask({
      accepted: true,
      request_id: "req_race",
      trace_id: "trace_race",
      parent_trace_id: null,
      session_id: "",
      task_type: "chat"
    });

    const event: RpcEvent = {
      kind: "event",
      type: "chat.done",
      request_id: "req_race",
      trace_id: "trace_race",
      parent_trace_id: null,
      session_id: "",
      sequence: 1,
      timestamp_ms: Date.now(),
      protocol_version: 1,
      payload: { message_id: "msg_race" }
    };

    expect(markTerminalEvent(event).accepted).toBe(true);
    const trackedBefore = getTrackedTask("req_race");
    expect(trackedBefore?.terminal_state).toBe("done");

    const trackedAfter = registerAcceptedTask({
      accepted: true,
      request_id: "req_race",
      trace_id: "trace_race_2",
      parent_trace_id: null,
      session_id: "",
      task_type: "chat"
    });

    expect(trackedAfter.terminal_state).toBe("done");
    expect(trackedAfter.trace_id).toBe("trace_race_2");
  });

  it("可以兼容 Rust 命令返回的 wrapper 并自动解包短任务结果", async () => {
    const transport: TauriTransport = {
      async invoke<TResult>(_command: string): Promise<TResult> {
        return {
          accepted: false,
          request_id: "req_short",
          trace_id: "trace_short",
          result: {
            ready: true,
            protocol_version: 1,
            schema_hash: "schema",
            capabilities: ["sidecar.hello"]
          }
        } as TResult;
      },
      async listen() {
        return () => undefined;
      }
    };

    setTauriTransportForTests(transport);
    const hello = await invokeCommand("sidecar.hello");
    expect(hello).toMatchObject({
      ready: true,
      protocol_version: 1,
      schema_hash: "schema"
    });
    setTauriTransportForTests(null);
  });

  it("可以兼容 Rust 命令返回的 wrapper 并归一化长任务 accepted", async () => {
    clearTrackedTasks();
    const transport: TauriTransport = {
      async invoke<TResult>(_command: string): Promise<TResult> {
        return {
          accepted: true,
          request_id: "req_long",
          trace_id: "trace_long",
          result: {
            status: "accepted",
            task_type: "chat.send",
            sidecar_generation: 2
          }
        } as TResult;
      },
      async listen() {
        return () => undefined;
      }
    };

    setTauriTransportForTests(transport);
    const accepted = await invokeCommand<RpcAccepted>("chat.send", { message: "你好" }, { request_id: "req_long" });

    expect(accepted.request_id).toBe("req_long");
    expect(accepted.trace_id).toBe("trace_long");
    expect(accepted.task_type).toBe("chat");
    expect(getTrackedTask("req_long")).toMatchObject({
      request_id: "req_long",
      task_type: "chat"
    });
    setTauriTransportForTests(null);
  });

  it("真实 Tauri transport 不调用未注册的命令", async () => {
    const transport: TauriTransport = {
      kind: "tauri",
      async invoke<TResult>(): Promise<TResult> {
        throw new Error("不应触发真实 Tauri command");
      },
      async listen() {
        return () => undefined;
      }
    };

    setTauriTransportForTests(transport);
    await expect(invokeCommand("config.save_api" as never)).rejects.toMatchObject({
      code: "rpc.method_not_found"
    });
    setTauriTransportForTests(null);
  });

  it("开发 transport 也不会暴露未桥接的业务命令", async () => {
    setTauriTransportForTests(null);
    await expect(invokeCommand("mcp.save_server", {
      draft: { server_id: "local-dev" },
      base_version: 1,
      confirm_token: "confirm"
    })).rejects.toMatchObject({
      code: "rpc.method_not_found"
    });
  });

  it("重复终态只接受第一次，乱序事件归一化为 rpc.event_out_of_order", async () => {
    clearTrackedTasks();
    await invokeCommand<RpcAccepted>("chat.send", { message: "你好" }, { request_id: "req_terminal" });

    const doneEvent: RpcEvent = {
      kind: "event",
      type: "chat.done",
      request_id: "req_terminal",
      trace_id: "trace_terminal",
      parent_trace_id: null,
      session_id: "",
      sequence: 2,
      timestamp_ms: Date.now(),
      protocol_version: 1,
      payload: {}
    };

    expect(markTerminalEvent(doneEvent).accepted).toBe(true);
    expect(markTerminalEvent({ ...doneEvent, sequence: 3 }).accepted).toBe(false);
    const outOfOrder = markTerminalEvent({ ...doneEvent, request_id: "req_terminal", sequence: 1 });
    expect(outOfOrder.error?.code).toBe("rpc.event_out_of_order");
  });

  it("工具和 MCP 的非 done 命名终态也会关闭长任务", async () => {
    clearTrackedTasks();
    await invokeCommand<RpcAccepted>("tools.call", {
      tool_name: "dryrun.echo",
      source: "test",
      arguments: {},
      dry_run: true
    }, { request_id: "req_tool_terminal" });
    expect(markTerminalEvent({
      kind: "event",
      type: "tool.result",
      request_id: "req_tool_terminal",
      trace_id: "trace_tool",
      parent_trace_id: null,
      session_id: "",
      sequence: 1,
      timestamp_ms: Date.now(),
      protocol_version: 1,
      payload: { summary: { tool_name: "dryrun.echo" } }
    }).accepted).toBe(true);
    expect(getTrackedTask("req_tool_terminal")?.terminal_state).toBe("done");

    await invokeCommand<RpcAccepted>("mcp.call_tool", {
      server_id: "local-dev",
      tool_name: "echo",
      arguments: {}
    }, { request_id: "req_mcp_terminal" });
    expect(markTerminalEvent({
      kind: "event",
      type: "mcp.tool_done",
      request_id: "req_mcp_terminal",
      trace_id: "trace_mcp",
      parent_trace_id: null,
      session_id: "",
      sequence: 1,
      timestamp_ms: Date.now(),
      protocol_version: 1,
      payload: { summary: { server_id: "local-dev" } }
    }).accepted).toBe(true);
    expect(getTrackedTask("req_mcp_terminal")?.terminal_state).toBe("done");
  });

  it("unsubscribe 后不再接收事件", async () => {
    const handler = vi.fn();
    const unsubscribe = await subscribeEvent("chat.delta", handler);

    emitMockTauriEvent({
      kind: "event",
      type: "chat.delta",
      request_id: "req_event",
      trace_id: "trace_event",
      parent_trace_id: null,
      session_id: "",
      sequence: 1,
      timestamp_ms: Date.now(),
      protocol_version: 1,
      payload: { text: "a" }
    });
    unsubscribe();
    emitMockTauriEvent({
      kind: "event",
      type: "chat.delta",
      request_id: "req_event",
      trace_id: "trace_event",
      parent_trace_id: null,
      session_id: "",
      sequence: 2,
      timestamp_ms: Date.now(),
      protocol_version: 1,
      payload: { text: "b" }
    });

    expect(handler).toHaveBeenCalledTimes(1);
  });
});
