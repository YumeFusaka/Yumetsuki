import { describe, expect, it } from "vitest";
import { emitMockTauriEvent, createMockTauriTransport, setTauriTransportForTests } from "@/client/runtime";
import type { RpcAccepted } from "@/client/types/rpc";
import { useAppStore } from "./appStore";
import { useAudioStore } from "./audioStore";
import { useCharacterStore } from "./characterStore";
import { useChatStore } from "./chatStore";
import { useConfigStore } from "./configStore";
import { useDiagnosticStore } from "./diagnosticStore";
import { useLogStore } from "./logStore";
import { useMcpStore } from "./mcpStore";
import { usePluginStore } from "./pluginStore";
import { useSttStore } from "./sttStore";
import { useThemeStore } from "./themeStore";
import { useToolStore } from "./toolStore";
import { useWindowStore } from "./windowStore";

describe("Pinia store lifecycle", () => {
  it("轻量 store 的 init 幂等，dispose 可重复释放", () => {
    const stores = [
      useWindowStore(),
      useThemeStore(),
      useAudioStore(),
      useSttStore(),
      useToolStore(),
      usePluginStore(),
      useMcpStore(),
      useCharacterStore()
    ];

    for (const store of stores) {
      store.init();
      store.init();
      expect(store.lifecycle.initCount).toBe(1);
      store.dispose();
      expect(store.lifecycle.initialized).toBe(false);
    }
  });

  it("sidecar restart reset 保留非敏感偏好并清运行态", () => {
    const windowStore = useWindowStore();
    windowStore.position = { x: 12, y: 34 };
    windowStore.dragging = true;
    windowStore.resetOnSidecarRestart();
    expect(windowStore.position).toEqual({ x: 12, y: 34 });
    expect(windowStore.dragging).toBe(false);

    const themeStore = useThemeStore();
    themeStore.tokenOverride = { accent: "#000000" };
    themeStore.resetOnSidecarRestart();
    expect(themeStore.tokenOverride).toBeNull();

    const sttStore = useSttStore();
    sttStore.recording = true;
    sttStore.resetOnSidecarRestart();
    expect(sttStore.recording).toBe(false);
    expect(sttStore.canRetry).toBe(true);
  });

  it("chatStore 将 pending request 转为 sidecar.restarted，并停止流式草稿", () => {
    const chatStore = useChatStore();
    const accepted: RpcAccepted = {
      accepted: true,
      request_id: "req_pending",
      trace_id: "trace_pending",
      parent_trace_id: null,
      session_id: "",
      task_type: "chat"
    };

    chatStore.pendingRequests.set(accepted.request_id, accepted);
    chatStore.streamingDraft = "未完成";
    chatStore.busy = true;
    chatStore.resetOnSidecarRestart();

    expect(chatStore.pendingRequests.size).toBe(0);
    expect(chatStore.streamingDraft).toBe("");
    expect(chatStore.busy).toBe(false);
    expect(chatStore.error?.code).toBe("sidecar.restarted");
  });

  it("configStore、diagnosticStore、characterStore 的 restart 语义符合 allowlist", () => {
    const configStore = useConfigStore();
    configStore.saving = true;
    configStore.draft.system.font_scale = 1.6;
    configStore.resetOnSidecarRestart();
    expect(configStore.saving).toBe(false);
    expect(configStore.needsReload).toBe(true);
    expect(configStore.draft.system.font_scale).toBe(1.6);

    const diagnosticStore = useDiagnosticStore();
    diagnosticStore.currentRequest = {
      accepted: true,
      request_id: "req_diag",
      trace_id: "trace_diag",
      parent_trace_id: null,
      session_id: "",
      task_type: "diagnostics"
    };
    diagnosticStore.reportHandle = "local/path/should-clear";
    diagnosticStore.resetOnSidecarRestart();
    expect(diagnosticStore.status).toBe("failed");
    expect(diagnosticStore.reportHandle).toBeNull();

    const characterStore = useCharacterStore();
    characterStore.recentCharacterId = "sakura";
    characterStore.resetOnSidecarRestart();
    expect(characterStore.recentCharacterId).toBe("sakura");
    expect(characterStore.resourceState).toBe("stale");
  });

  it("diagnosticStore 消费 Python sidecar 的 report_handle 和 export_handle 事件形状", () => {
    const diagnosticStore = useDiagnosticStore();
    diagnosticStore.currentRequest = {
      accepted: true,
      request_id: "req_diag_run",
      trace_id: "trace_diag",
      parent_trace_id: null,
      session_id: "",
      task_type: "diagnostics"
    };

    diagnosticStore.applyProgress({
      kind: "event",
      type: "diagnostic.progress",
      request_id: "req_diag_run",
      trace_id: "trace_diag",
      parent_trace_id: null,
      session_id: "",
      sequence: 1,
      timestamp_ms: Date.now(),
      protocol_version: 1,
      payload: { progress: 1.0, summary: "诊断完成" }
    });
    diagnosticStore.applyDone({
      kind: "event",
      type: "diagnostic.done",
      request_id: "req_diag_run",
      trace_id: "trace_diag",
      parent_trace_id: null,
      session_id: "",
      sequence: 2,
      timestamp_ms: Date.now(),
      protocol_version: 1,
      payload: { summary: { report_handle: "handle:report:req_diag_run" } }
    });

    expect(diagnosticStore.progress).toBe(100);
    expect(diagnosticStore.reportHandle).toBe("handle:report:req_diag_run");
    expect(diagnosticStore.currentRequest).toBeNull();

    diagnosticStore.exportRequest = {
      accepted: true,
      request_id: "req_diag_export",
      trace_id: "trace_diag_export",
      parent_trace_id: null,
      session_id: "",
      task_type: "diagnostics"
    };
    diagnosticStore.applyDone({
      kind: "event",
      type: "diagnostic.done",
      request_id: "req_diag_export",
      trace_id: "trace_diag_export",
      parent_trace_id: null,
      session_id: "",
      sequence: 1,
      timestamp_ms: Date.now(),
      protocol_version: 1,
      payload: { summary: { export_handle: "handle:report-export:req_diag_export" } }
    });

    expect(diagnosticStore.reportHandle).toBe("handle:report:req_diag_run");
    expect(diagnosticStore.exportHandle).toBe("handle:report-export:req_diag_export");
    expect(diagnosticStore.exportRequest).toBeNull();
  });

  it("异步 store init 可创建订阅且重复 init 不重复订阅", async () => {
    const appStore = useAppStore();
    await appStore.init();
    await appStore.init();
    expect(appStore.lifecycle.initCount).toBe(1);
    expect(appStore.lifecycle.subscriptions.length).toBe(1);
    appStore.dispose();
    expect(appStore.lifecycle.subscriptions.length).toBe(0);

    const logStore = useLogStore();
    await logStore.init();
    await logStore.init();
    expect(logStore.lifecycle.initCount).toBe(1);
    expect(logStore.entries.length).toBeGreaterThan(0);
    logStore.dispose();
  });

  it("chatStore 在事件先于 accepted 返回时不会复活终态请求", async () => {
    const baseTransport = createMockTauriTransport();
    const transport = {
      ...baseTransport,
      async invoke<TResult>(command: string, args?: Record<string, unknown>): Promise<TResult> {
        if (command === "chat_send") {
          const context = (args?.context ?? {}) as Record<string, unknown>;
          const request_id = String(context.request_id ?? "req_chat_race");
          const trace_id = String(context.trace_id ?? "trace_chat_race");
          const parent_trace_id = (context.parent_trace_id ?? null) as string | null;
          const session_id = String(context.session_id ?? "");

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
            payload: { text: "已完成" }
          });
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

          return {
            accepted: true,
            request_id,
            trace_id,
            parent_trace_id,
            session_id,
            task_type: "chat.send"
          } as TResult;
        }

        return baseTransport.invoke<TResult>(command, args);
      }
    };

    setTauriTransportForTests(transport);
    const chatStore = useChatStore();
    await chatStore.init();
    await chatStore.send("你好");

    expect(chatStore.pendingRequests.size).toBe(0);
    expect(chatStore.busy).toBe(false);
    expect(chatStore.statusText).toBe("回复完成");
    expect(chatStore.messages.at(-1)?.role).toBe("assistant");

    chatStore.dispose();
    setTauriTransportForTests(null);
  });
});
